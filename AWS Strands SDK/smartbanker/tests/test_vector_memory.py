"""Unit tests for VectorMemoryManager (memory/vector_memory.py).

Tests use a stubbed Bedrock client so no real AWS calls are made.
The in-memory store is exercised directly.
"""
from __future__ import annotations

import io
import json
import math
import pytest
from unittest.mock import MagicMock, patch

from config.models import FinancialPattern, SimilarPattern
from config.settings import MemoryConfig
from memory.vector_memory import VectorMemoryManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fake_embedding(text: str) -> list[float]:
    """Deterministic fake embedding based on text hash (dimension 4)."""
    h = hash(text) & 0xFFFFFFFF
    return [
        ((h >> 0) & 0xFF) / 255.0,
        ((h >> 8) & 0xFF) / 255.0,
        ((h >> 16) & 0xFF) / 255.0,
        ((h >> 24) & 0xFF) / 255.0,
    ]


def _stub_bedrock() -> MagicMock:
    """Create a mock Bedrock client whose invoke_model returns fake embeddings."""
    client = MagicMock()

    def _invoke_model(**kwargs):
        body = json.loads(kwargs["body"])
        emb = _fake_embedding(body["inputText"])
        resp_body = MagicMock()
        resp_body.read.return_value = json.dumps({"embedding": emb}).encode()
        return {"body": resp_body}

    client.invoke_model.side_effect = _invoke_model
    return client


def _make_manager(default_k: int = 5) -> VectorMemoryManager:
    """Create a VectorMemoryManager with a stubbed Bedrock client."""
    mgr = object.__new__(VectorMemoryManager)
    mgr.bedrock = _stub_bedrock()
    mgr.embedding_model = "amazon.titan-embed-text-v2:0"
    mgr.index_name = "test_index"
    mgr.endpoint = ""
    mgr.default_k = default_k
    mgr._store = []
    return mgr


def _pattern(
    user_id: str = "u1",
    content: str = "spending pattern",
    pattern_type: str = "behavior",
    embedding: list[float] | None = None,
    metadata: dict | None = None,
) -> FinancialPattern:
    return FinancialPattern(
        user_id=user_id,
        pattern_type=pattern_type,
        content=content,
        embedding=embedding,
        metadata=metadata or {},
    )


# ---------------------------------------------------------------------------
# Tests – __init__ with MemoryConfig
# ---------------------------------------------------------------------------

class TestInit:
    def test_config_overrides_defaults(self):
        config = MemoryConfig(agent_id="test", aws_region="eu-west-1", default_k=10)
        with patch("memory.vector_memory.boto3") as mock_boto:
            mock_boto.client.return_value = _stub_bedrock()
            mgr = VectorMemoryManager(config=config)
        assert mgr.default_k == 10

    def test_keyword_defaults(self):
        with patch("memory.vector_memory.boto3") as mock_boto:
            mock_boto.client.return_value = _stub_bedrock()
            mgr = VectorMemoryManager(default_k=7)
        assert mgr.default_k == 7


# ---------------------------------------------------------------------------
# Tests – store_pattern
# ---------------------------------------------------------------------------

class TestStorePattern:
    def test_stores_pattern_and_generates_embedding(self):
        mgr = _make_manager()
        pat = _pattern(content="monthly groceries")
        mgr.store_pattern(pat)
        assert len(mgr._store) == 1
        assert mgr._store[0]["embedding"] == _fake_embedding("monthly groceries")

    def test_reuses_precomputed_embedding(self):
        mgr = _make_manager()
        pre = [0.1, 0.2, 0.3, 0.4]
        pat = _pattern(content="rent payment", embedding=pre)
        mgr.store_pattern(pat)
        assert mgr._store[0]["embedding"] == pre
        # Bedrock should NOT have been called
        mgr.bedrock.invoke_model.assert_not_called()

    def test_stores_without_embedding_on_bedrock_failure(self):
        mgr = _make_manager()
        mgr.bedrock.invoke_model.side_effect = RuntimeError("service unavailable")
        pat = _pattern(content="investment failure")
        mgr.store_pattern(pat)
        assert len(mgr._store) == 1
        assert mgr._store[0]["embedding"] == []

    def test_stores_all_pattern_types(self):
        mgr = _make_manager()
        for ptype in ("behavior", "recommendation", "failure", "preference"):
            mgr.store_pattern(_pattern(pattern_type=ptype, content=f"test {ptype}"))
        assert len(mgr._store) == 4
        stored_types = {item["pattern"]["pattern_type"] for item in mgr._store}
        assert stored_types == {"behavior", "recommendation", "failure", "preference"}

    def test_pattern_id_preserved(self):
        mgr = _make_manager()
        pat = _pattern(content="savings goal")
        original_id = pat.pattern_id
        mgr.store_pattern(pat)
        assert mgr._store[0]["pattern"]["pattern_id"] == original_id


# ---------------------------------------------------------------------------
# Tests – search_patterns
# ---------------------------------------------------------------------------

class TestSearchPatterns:
    def test_returns_results_ordered_by_similarity(self):
        mgr = _make_manager()
        # Store patterns with known embeddings so we control similarity
        mgr._store = [
            {"pattern": _pattern(content="a").model_dump(), "embedding": [1.0, 0.0, 0.0, 0.0]},
            {"pattern": _pattern(content="b").model_dump(), "embedding": [0.0, 1.0, 0.0, 0.0]},
            {"pattern": _pattern(content="c").model_dump(), "embedding": [0.9, 0.1, 0.0, 0.0]},
        ]
        # Query embedding will be [1, 0, 0, 0] — closest to "a", then "c", then "b"
        mgr.bedrock.invoke_model.side_effect = lambda **kw: _make_response([1.0, 0.0, 0.0, 0.0])
        results = mgr.search_patterns("test query")
        assert len(results) == 3
        assert results[0].content == "a"
        assert results[1].content == "c"
        assert results[2].content == "b"
        assert results[0].similarity_score >= results[1].similarity_score >= results[2].similarity_score

    def test_respects_k_parameter(self):
        mgr = _make_manager(default_k=10)
        for i in range(8):
            mgr._store.append(
                {"pattern": _pattern(content=f"p{i}").model_dump(), "embedding": [float(i), 0.0, 0.0, 0.0]}
            )
        mgr.bedrock.invoke_model.side_effect = lambda **kw: _make_response([1.0, 0.0, 0.0, 0.0])
        results = mgr.search_patterns("q", k=3)
        assert len(results) == 3

    def test_uses_default_k(self):
        mgr = _make_manager(default_k=2)
        for i in range(5):
            mgr._store.append(
                {"pattern": _pattern(content=f"p{i}").model_dump(), "embedding": [float(i), 0.0, 0.0, 0.0]}
            )
        mgr.bedrock.invoke_model.side_effect = lambda **kw: _make_response([1.0, 0.0, 0.0, 0.0])
        results = mgr.search_patterns("q")
        assert len(results) == 2

    def test_filters_by_user_id(self):
        mgr = _make_manager()
        mgr._store = [
            {"pattern": _pattern(user_id="u1", content="u1 pattern").model_dump(), "embedding": [1.0, 0.0, 0.0, 0.0]},
            {"pattern": _pattern(user_id="u2", content="u2 pattern").model_dump(), "embedding": [1.0, 0.0, 0.0, 0.0]},
        ]
        mgr.bedrock.invoke_model.side_effect = lambda **kw: _make_response([1.0, 0.0, 0.0, 0.0])
        results = mgr.search_patterns("q", user_id="u1")
        assert len(results) == 1
        assert results[0].content == "u1 pattern"

    def test_returns_empty_on_embedding_failure(self):
        mgr = _make_manager()
        mgr._store.append(
            {"pattern": _pattern(content="x").model_dump(), "embedding": [1.0, 0.0, 0.0, 0.0]}
        )
        mgr.bedrock.invoke_model.side_effect = RuntimeError("timeout")
        results = mgr.search_patterns("q")
        assert results == []

    def test_skips_patterns_without_embedding(self):
        mgr = _make_manager()
        mgr._store = [
            {"pattern": _pattern(content="no_emb").model_dump(), "embedding": []},
            {"pattern": _pattern(content="has_emb").model_dump(), "embedding": [1.0, 0.0, 0.0, 0.0]},
        ]
        mgr.bedrock.invoke_model.side_effect = lambda **kw: _make_response([1.0, 0.0, 0.0, 0.0])
        results = mgr.search_patterns("q")
        assert len(results) == 1
        assert results[0].content == "has_emb"

    def test_empty_store_returns_empty(self):
        mgr = _make_manager()
        mgr.bedrock.invoke_model.side_effect = lambda **kw: _make_response([1.0, 0.0, 0.0, 0.0])
        assert mgr.search_patterns("q") == []

    def test_result_contains_pattern_id_and_metadata(self):
        mgr = _make_manager()
        pat = _pattern(content="test", metadata={"intent": "savings"})
        pat_dump = pat.model_dump()
        mgr._store = [{"pattern": pat_dump, "embedding": [1.0, 0.0, 0.0, 0.0]}]
        mgr.bedrock.invoke_model.side_effect = lambda **kw: _make_response([1.0, 0.0, 0.0, 0.0])
        results = mgr.search_patterns("q")
        assert results[0].pattern_id == pat.pattern_id
        assert results[0].metadata == {"intent": "savings"}


# ---------------------------------------------------------------------------
# Tests – _cosine_similarity
# ---------------------------------------------------------------------------

class TestCosineSimilarity:
    def test_identical_vectors(self):
        assert VectorMemoryManager._cosine_similarity([1, 0, 0], [1, 0, 0]) == pytest.approx(1.0)

    def test_orthogonal_vectors(self):
        assert VectorMemoryManager._cosine_similarity([1, 0], [0, 1]) == pytest.approx(0.0)

    def test_opposite_vectors(self):
        assert VectorMemoryManager._cosine_similarity([1, 0], [-1, 0]) == pytest.approx(-1.0)

    def test_empty_vectors(self):
        assert VectorMemoryManager._cosine_similarity([], []) == 0.0

    def test_mismatched_lengths(self):
        assert VectorMemoryManager._cosine_similarity([1, 0], [1, 0, 0]) == 0.0

    def test_zero_vector(self):
        assert VectorMemoryManager._cosine_similarity([0, 0], [1, 1]) == 0.0


# ---------------------------------------------------------------------------
# Helper for building mock Bedrock responses
# ---------------------------------------------------------------------------

def _make_response(embedding: list[float]) -> dict:
    body = MagicMock()
    body.read.return_value = json.dumps({"embedding": embedding}).encode()
    return {"body": body}
