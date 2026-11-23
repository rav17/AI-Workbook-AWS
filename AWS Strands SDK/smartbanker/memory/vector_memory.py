"""Vector memory for long-term semantic patterns. Traces: R10, R11."""
from __future__ import annotations

import json
import logging
import uuid
from typing import Optional

import boto3

from config.models import FinancialPattern, SimilarPattern
from config.settings import MemoryConfig

logger = logging.getLogger(__name__)


class VectorMemoryManager:
    """Long-term semantic memory using Bedrock Titan embeddings + OpenSearch.

    Stores financial behaviour patterns, past recommendations, failure outcomes,
    and user preference embeddings as vectors.  Supports semantic similarity
    search with configurable top-K.

    Traces: R10.1, R10.2, R10.3, R10.4, R11.
    """

    def __init__(
        self,
        config: Optional[MemoryConfig] = None,
        *,
        region: str = "us-east-1",
        embedding_model: str = "amazon.titan-embed-text-v2:0",
        index_name: str = "smartbanker_ltm",
        endpoint: str = "",
        default_k: int = 5,
    ):
        if config is not None:
            region = config.aws_region
            default_k = config.default_k

        self.bedrock = boto3.client("bedrock-runtime", region_name=region)
        self.embedding_model = embedding_model
        self.index_name = index_name
        self.endpoint = endpoint
        self.default_k = default_k
        # In production this would be an OpenSearch client.
        # Using in-memory store for portability / local dev.
        self._store: list[dict] = []

    # ------------------------------------------------------------------
    # Embedding generation
    # ------------------------------------------------------------------

    def _get_embedding(self, text: str) -> list[float]:
        """Generate embedding via Bedrock Titan. Traces: R10.1."""
        response = self.bedrock.invoke_model(
            modelId=self.embedding_model,
            body=json.dumps({"inputText": text}),
            contentType="application/json",
        )
        result = json.loads(response["body"].read())
        return result["embedding"]

    # ------------------------------------------------------------------
    # Store
    # ------------------------------------------------------------------

    def store_pattern(self, pattern: FinancialPattern) -> None:
        """Store financial pattern with embedding to long-term memory.

        If the pattern already carries a pre-computed embedding it is reused;
        otherwise one is generated via Bedrock Titan.

        Traces: R10.1, R10.3.
        """
        embedding = pattern.embedding
        if not embedding:
            try:
                embedding = self._get_embedding(pattern.content)
                pattern.embedding = embedding
            except Exception:
                logger.warning(
                    "Failed to generate embedding for pattern %s; storing without vector",
                    pattern.pattern_id,
                )
                embedding = []

        self._store.append(
            {
                "pattern": pattern.model_dump(),
                "embedding": embedding,
            }
        )
        logger.info(
            "Stored pattern %s (type=%s, user=%s)",
            pattern.pattern_id,
            pattern.pattern_type,
            pattern.user_id,
        )

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search_patterns(
        self,
        query: str,
        k: int | None = None,
        user_id: str | None = None,
    ) -> list[SimilarPattern]:
        """Semantic similarity search over stored patterns.

        Returns the top *k* results ordered by descending cosine similarity.
        When *user_id* is provided only patterns belonging to that user are
        considered.

        Traces: R10.2, R10.4.
        """
        k = k or self.default_k

        try:
            query_embedding = self._get_embedding(query)
        except Exception:
            logger.warning("Failed to generate query embedding; returning empty results")
            return []

        scored: list[tuple[float, dict]] = []
        for item in self._store:
            pat = item["pattern"]
            if user_id and pat.get("user_id") != user_id:
                continue
            emb = item["embedding"]
            if not emb:
                continue
            score = self._cosine_similarity(query_embedding, emb)
            scored.append((score, pat))

        scored.sort(key=lambda x: x[0], reverse=True)

        results = [
            SimilarPattern(
                pattern_id=p.get("pattern_id", ""),
                content=p.get("content", ""),
                similarity_score=round(s, 6),
                metadata=p.get("metadata", {}),
            )
            for s, p in scored[:k]
        ]

        for r in results:
            logger.debug(
                "Pattern %s matched with score %.4f",
                r.pattern_id,
                r.similarity_score,
            )

        return results

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        """Compute cosine similarity between two vectors."""
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return dot / (norm_a * norm_b)
