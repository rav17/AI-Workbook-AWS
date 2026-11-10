from __future__ import annotations

import hashlib
import importlib
import json
import re
from dataclasses import dataclass
from typing import Any

from aria.framework.contracts import GatewayTransport, MemoryClient, RuntimeClient
from aria.framework.memory import MemoryEntry, MemoryStore
from aria.session.manager import SessionManager


class AgentCoreMemoryDataPlaneClient:
    """Tenant-bound boto3 client for documented AgentCore Memory data-plane APIs."""

    def __init__(
        self,
        *,
        memory_id: str,
        tenant_id: str,
        user_id: str,
        session_id: str,
        client: Any = None,
    ) -> None:
        if not all((memory_id, tenant_id, user_id, session_id)):
            raise ValueError("memory, tenant, user, and session identifiers are required")
        self.memory_id = memory_id
        self.tenant_id = tenant_id
        self.tenant_key = hashlib.sha256(tenant_id.encode("utf-8")).hexdigest()[:32]
        self.actor_id = hashlib.sha256(f"{tenant_id}:{user_id}".encode()).hexdigest()[:32]
        self.session_id = hashlib.sha256(session_id.encode("utf-8")).hexdigest()[:32]
        self.namespace_path = f"/tenants/{self.tenant_key}/users/{self.actor_id}/"
        if client is None:
            client = importlib.import_module("boto3").client("bedrock-agentcore")
        self.client = client

    def _validate_tenant(self, tenant_id: str) -> None:
        if tenant_id != self.tenant_id:
            raise PermissionError("memory tenant does not match authenticated tenant")

    def retrieve(self, tenant_id: str, limit: int, query: str) -> list[dict[str, Any]]:
        self._validate_tenant(tenant_id)
        response = self.client.retrieve_memory_records(
            memoryId=self.memory_id,
            namespacePath=self.namespace_path,
            maxResults=min(max(1, limit), 5),
            searchCriteria={
                "searchQuery": query.strip() or "important facts and preferences",
                "topK": min(max(1, limit), 5),
            },
        )
        records = []
        for record in response.get("memoryRecordSummaries", []):
            content = record.get("content", {})
            text = content.get("text") if isinstance(content, dict) else None
            namespaces = record.get("namespaces", [])
            namespace = next(
                (
                    value
                    for value in namespaces
                    if isinstance(value, str)
                    and value.lstrip("/").startswith(self.namespace_path.lstrip("/"))
                ),
                None,
            )
            record_id = record.get("memoryRecordId")
            if isinstance(text, str) and isinstance(namespace, str) and isinstance(record_id, str):
                records.append(
                    {
                        "key": f"{namespace}|{record_id}",
                        "value": text,
                        "tenant_id": tenant_id,
                    }
                )
        return records

    def add(self, tenant_id: str, key: str, value: str) -> None:
        self._validate_tenant(tenant_id)
        raise PermissionError(
            "AgentCore Memory writes are disabled until the data-owner policy is approved"
        )

    def delete(self, tenant_id: str, record_id: str | None = None) -> int:
        self._validate_tenant(tenant_id)
        namespace, separator, memory_record_id = (record_id or "").rpartition("|")
        normalized_namespace = namespace.lstrip("/")
        if (
            not separator
            or not normalized_namespace.startswith(self.namespace_path.lstrip("/"))
            or not re.fullmatch(r"mem-[A-Za-z0-9_-]+", memory_record_id)
        ):
            raise ValueError("a tenant-scoped AgentCore Memory record ID is required for deletion")
        self.client.delete_memory_record(
            memoryId=self.memory_id,
            memoryRecordId=memory_record_id,
            namespace=namespace,
        )
        return 1

    def delete_all_for_user(self, tenant_id: str) -> int:
        self._validate_tenant(tenant_id)
        namespace_path = self.namespace_path.rstrip("/")
        next_token: str | None = None
        seen_tokens: set[str] = set()
        seen_records: set[tuple[str, str]] = set()
        deleted = 0

        while True:
            request: dict[str, Any] = {
                "memoryId": self.memory_id,
                "namespacePath": namespace_path,
                "maxResults": 100,
            }
            if next_token is not None:
                request["nextToken"] = next_token
            response = self.client.list_memory_records(**request)
            summaries = response.get("memoryRecordSummaries", [])
            if not isinstance(summaries, list):
                raise ValueError("AgentCore Memory returned invalid erasure records")

            for summary in summaries:
                if not isinstance(summary, dict):
                    raise ValueError("AgentCore Memory returned an invalid erasure record")
                record_id = summary.get("memoryRecordId")
                namespaces = summary.get("namespaces")
                matching_namespace = (
                    next(
                        (
                            namespace
                            for namespace in namespaces or []
                            if isinstance(namespace, str)
                            and namespace.lstrip("/").startswith(namespace_path.lstrip("/") + "/")
                        ),
                        None,
                    )
                    if isinstance(namespaces, list)
                    else None
                )
                if (
                    not isinstance(record_id, str)
                    or not re.fullmatch(r"mem-[A-Za-z0-9_-]+", record_id)
                    or not isinstance(matching_namespace, str)
                ):
                    raise ValueError(
                        "AgentCore Memory returned a record outside the authenticated "
                        "user namespace"
                    )

                record_key = (matching_namespace, record_id)
                if record_key in seen_records:
                    continue
                seen_records.add(record_key)
                self.delete(tenant_id, f"{matching_namespace}|{record_id}")
                deleted += 1

            next_token = response.get("nextToken")
            if next_token is None:
                return deleted
            if not isinstance(next_token, str) or not next_token:
                raise ValueError("AgentCore Memory returned an invalid erasure page token")
            if next_token in seen_tokens:
                raise RuntimeError("AgentCore Memory repeated an erasure page token")
            seen_tokens.add(next_token)


@dataclass(frozen=True)
class RuntimeSession:
    session_id: str
    tenant_id: str
    user_id: str
    runtime_session_id: str
    revision: int


class AgentCoreRuntimeAdapter:
    """Maps an authenticated conversation to one recoverable Runtime session."""

    def __init__(
        self,
        session_manager: SessionManager,
        client: RuntimeClient | None = None,
    ) -> None:
        self.session_manager = session_manager
        self.client = client

    def resolve(
        self,
        tenant_id: str,
        user_id: str,
        conversation_id: str = "default",
    ) -> RuntimeSession:
        session_user_id = f"{user_id}:{conversation_id}"
        session = self.session_manager.start_session(tenant_id, session_user_id)
        runtime_session_id = session["state"].get("runtime_session_id")
        if not runtime_session_id:
            runtime_session_id = self._create_or_recover(session["session_id"])
            updated = self.session_manager.update_session_state(
                session["session_id"],
                {"runtime_session_id": runtime_session_id},
                expected_revision=session["revision"],
            )
            if not updated:
                session = self.session_manager.get_session(session["session_id"])
                runtime_session_id = session["state"].get("runtime_session_id", runtime_session_id)
            else:
                session = self.session_manager.get_session(session["session_id"])

        return RuntimeSession(
            session_id=session["session_id"],
            tenant_id=tenant_id,
            user_id=user_id,
            runtime_session_id=runtime_session_id,
            revision=session["revision"],
        )

    def _create_or_recover(self, session_id: str) -> str:
        if self.client is None:
            return hashlib.sha256(session_id.encode()).hexdigest()
        return self.client.create_or_recover_session(session_id)

    def acquire(self, runtime_session: RuntimeSession) -> bool:
        return self.session_manager.lock_session(runtime_session.session_id)

    def release(self, runtime_session: RuntimeSession) -> None:
        self.session_manager.release_session(runtime_session.session_id)


class AgentCoreRuntimeClient:
    """Invokes an IAM-authorized Runtime with a backend-verified principal."""

    def __init__(self, *, runtime_arn: str, client: Any = None) -> None:
        if not runtime_arn:
            raise ValueError("AgentCore Runtime ARN is required")
        self.runtime_arn = runtime_arn
        if client is None:
            client = importlib.import_module("boto3").client("bedrock-agentcore")
        self.client = client

    def create_or_recover_session(self, session_id: str) -> str:
        return hashlib.sha256(session_id.encode()).hexdigest()

    def invoke(
        self,
        payload: dict[str, Any],
        *,
        runtime_session_id: str,
        tenant_id: str,
        user_id: str,
    ) -> dict[str, Any]:
        if not all((runtime_session_id, tenant_id, user_id)):
            raise ValueError("Runtime session and verified principal are required")
        runtime_user_id = hashlib.sha256(f"{tenant_id}:{user_id}".encode()).hexdigest()
        request_payload = {
            **payload,
            "_verified_principal": {"tenant_id": tenant_id, "user_id": user_id},
        }
        response = self.client.invoke_agent_runtime(
            agentRuntimeArn=self.runtime_arn,
            runtimeSessionId=runtime_session_id,
            runtimeUserId=runtime_user_id,
            contentType="application/json",
            accept="application/json",
            payload=json.dumps(request_payload).encode("utf-8"),
        )
        status_code = int(response.get("statusCode", 200))
        body = response.get("response", b"{}")
        if hasattr(body, "read"):
            body = body.read()
        if isinstance(body, bytes):
            body = body.decode("utf-8")
        if status_code >= 400:
            raise RuntimeError(f"AgentCore Runtime returned status {status_code}")
        result = json.loads(body) if isinstance(body, str) else body
        if not isinstance(result, dict):
            raise ValueError("AgentCore Runtime returned a non-object response")
        return result


class AgentCoreMemoryAdapter:
    """Applies tenant and retrieval bounds around an AgentCore Memory client."""

    def __init__(
        self,
        client: MemoryClient | None = None,
        local_store: MemoryStore | None = None,
        max_items: int = 5,
    ) -> None:
        self.client = client
        self.local_store = local_store or MemoryStore()
        self.max_items = max(1, max_items)

    def retrieve(
        self,
        tenant_id: str,
        limit: int | None = None,
        query: str = "important facts and preferences",
    ) -> list[MemoryEntry]:
        bounded_limit = min(max(1, limit or self.max_items), self.max_items)
        if self.client is not None:
            records = self.client.retrieve(tenant_id, bounded_limit, query)
            entries = []
            for record in records:
                if not isinstance(record, dict):
                    raise ValueError("AgentCore Memory returned an invalid memory record")
                key = record.get("key")
                value = record.get("value")
                record_tenant_id = record.get("tenant_id")
                if (
                    not isinstance(key, str)
                    or not key
                    or not isinstance(value, str)
                    or not isinstance(record_tenant_id, str)
                ):
                    raise ValueError("AgentCore Memory returned an invalid memory record")
                if record_tenant_id != tenant_id:
                    raise PermissionError("AgentCore Memory returned a record for another tenant")
                entries.append(MemoryEntry(key=key, value=value, tenant_id=record_tenant_id))
            return entries
        return self.local_store.retrieve(tenant_id, bounded_limit)

    def add(self, tenant_id: str, key: str, value: str) -> None:
        if self.client is not None:
            self.client.add(tenant_id, key, value)
            return
        self.local_store.add(MemoryEntry(key=key, value=value, tenant_id=tenant_id))

    def delete(self, tenant_id: str, key: str | None = None) -> int:
        if self.client is not None:
            delete = getattr(self.client, "delete", None)
            if not callable(delete):
                raise RuntimeError("configured AgentCore Memory client does not support deletion")
            return int(delete(tenant_id, key))
        return self.local_store.delete(tenant_id, key)


class AgentCoreGatewayAdapter:
    """Separates Gateway discovery/tool visibility from authorization."""

    def __init__(self, transport: GatewayTransport, scopes: list[str]) -> None:
        self.transport = transport
        self.scopes = list(scopes)

    def discover(self, query: str) -> list[Any]:
        return self.transport.discover_tools(query, self.scopes)

    def authorize(self, tool_name: str) -> bool:
        return self.transport.authorize(tool_name, self.scopes)

    def discover_authorized(self, query: str) -> list[Any]:
        tools = self.discover(query)
        return [tool for tool in tools if self.authorize(self._tool_name(tool))]

    def discover_semantic_authorized(
        self,
        query: str,
        capability_filter: set[str] | None = None,
    ) -> list[Any]:
        query_terms = {term.lower() for term in query.split() if term.strip()}
        candidates = []
        for tool in self.discover(query):
            name = self._tool_name(tool)
            description = self._tool_value(tool, "description")
            capabilities = self._tool_value(tool, "capabilities") or []
            capability_set = {str(capability) for capability in capabilities}
            if capability_filter and not capability_filter.intersection(capability_set):
                continue

            searchable = f"{name} {description}".lower()
            if query_terms and not any(term in searchable for term in query_terms):
                continue
            if self.authorize(name):
                candidates.append(tool)
        return candidates

    @staticmethod
    def _tool_name(tool: Any) -> str:
        if isinstance(tool, dict):
            return str(tool.get("name", ""))
        return str(getattr(tool, "name", ""))

    @staticmethod
    def _tool_value(tool: Any, key: str) -> Any:
        if isinstance(tool, dict):
            return tool.get(key)
        return getattr(tool, key, None)
