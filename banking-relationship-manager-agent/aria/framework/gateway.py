from __future__ import annotations

import re
from collections.abc import Generator, Iterable
from dataclasses import dataclass
from typing import Any

import httpx

ALLOWED_RUNTIME_GATEWAY_TOOLS = frozenset({"get_risk_questionnaire"})


class AgentCoreGatewaySigV4Auth(httpx.Auth):
    requires_request_body = True

    def __init__(self, region_name: str, session: Any = None) -> None:
        if not region_name:
            raise ValueError("AWS region is required for Gateway SigV4 signing")
        if session is None:
            from importlib import import_module

            session = import_module("boto3").Session()
        self._region_name = region_name
        self._session = session

    def auth_flow(self, request: httpx.Request) -> Generator[httpx.Request, httpx.Response, None]:
        from importlib import import_module

        credentials = self._session.get_credentials()
        if credentials is None:
            raise RuntimeError("AWS credentials are required for Gateway invocation")
        sigv4_auth = import_module("botocore.auth").SigV4Auth
        aws_request_type = import_module("botocore.awsrequest").AWSRequest
        aws_request = aws_request_type(
            method=request.method,
            url=str(request.url),
            data=request.read(),
            headers=dict(request.headers),
        )
        sigv4_auth(
            credentials.get_frozen_credentials(), "bedrock-agentcore", self._region_name
        ).add_auth(aws_request)
        request.headers.update(dict(aws_request.headers.items()))
        yield request


def gateway_mcp_url(gateway_id: str, region_name: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", gateway_id):
        raise ValueError("AgentCore Gateway ID has an invalid format")
    if not re.fullmatch(r"[a-z0-9-]+", region_name):
        raise ValueError("AWS region has an invalid format")
    return f"https://{gateway_id}.gateway.bedrock-agentcore.{region_name}.amazonaws.com/mcp"


def filter_allowed_gateway_tools(tools: Iterable[Any]) -> list[Any]:
    allowed: list[Any] = []
    for tool_item in tools:
        if isinstance(tool_item, dict):
            name = tool_item.get("tool_name", tool_item.get("name", ""))
        else:
            name = getattr(tool_item, "tool_name", getattr(tool_item, "name", ""))
        if (
            isinstance(name, str)
            and name.rsplit("___", maxsplit=1)[-1] in ALLOWED_RUNTIME_GATEWAY_TOOLS
        ):
            allowed.append(tool_item)
    return allowed


def create_gateway_mcp_client(
    gateway_id: str,
    region_name: str,
    *,
    boto3_session: Any = None,
) -> Any:
    from mcp.client.streamable_http import streamablehttp_client
    from strands.tools.mcp import MCPClient

    url = gateway_mcp_url(gateway_id, region_name)
    auth = AgentCoreGatewaySigV4Auth(region_name, boto3_session)
    return MCPClient(lambda: streamablehttp_client(url, auth=auth))


@dataclass
class GatewayClient:
    client_id: str
    scopes: list[str]
    timeout_seconds: int = 30

    def authorize(self, required_scope: str) -> bool:
        return required_scope in self.scopes

    def filter_tools(self, tools: list[Any], allowed_names: set[str]) -> list[Any]:
        return [
            tool
            for tool in tools
            if (getattr(tool, "name", None) in allowed_names or tool.get("name") in allowed_names)
        ]
