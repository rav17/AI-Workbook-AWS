from __future__ import annotations

import boto3


def handler(event: dict, context: object) -> dict[str, str]:
    properties = event.get("ResourceProperties", {})
    runtime_id = properties.get("AgentRuntimeId")
    if not runtime_id:
        raise ValueError("AgentRuntimeId is required")

    if event.get("RequestType") != "Delete":
        client = boto3.client("bedrock-agentcore-control")
        current_runtime = client.get_agent_runtime(agentRuntimeId=runtime_id)
        client.update_agent_runtime(
            agentRuntimeId=runtime_id,
            agentRuntimeArtifact=current_runtime["agentRuntimeArtifact"],
            roleArn=current_runtime["roleArn"],
            metadataConfiguration={"requireMMDSV2": True},
        )

    return {"PhysicalResourceId": str(runtime_id)}
