from __future__ import annotations

from types import SimpleNamespace

from cdk.custom_resources.enable_mmdsv2 import handler


def test_mmdsv2_custom_resource_preserves_runtime_artifact_and_role(monkeypatch):
    calls = []

    class FakeClient:
        def get_agent_runtime(self, *, agentRuntimeId):
            calls.append(("get", agentRuntimeId))
            return {"agentRuntimeArtifact": {"codeConfiguration": {}}, "roleArn": "role-arn"}

        def update_agent_runtime(self, **kwargs):
            calls.append(("update", kwargs))

    monkeypatch.setattr(
        "cdk.custom_resources.enable_mmdsv2.boto3.client",
        lambda service: FakeClient(),
    )

    result = handler(
        {"RequestType": "Create", "ResourceProperties": {"AgentRuntimeId": "runtime-id"}},
        SimpleNamespace(),
    )

    assert result == {"PhysicalResourceId": "runtime-id"}
    assert calls[0] == ("get", "runtime-id")
    assert calls[1][1]["agentRuntimeArtifact"] == {"codeConfiguration": {}}
    assert calls[1][1]["roleArn"] == "role-arn"
    assert calls[1][1]["metadataConfiguration"] == {"requireMMDSV2": True}


def test_mmdsv2_custom_resource_delete_is_noop(monkeypatch):
    monkeypatch.setattr(
        "cdk.custom_resources.enable_mmdsv2.boto3.client",
        lambda service: (_ for _ in ()).throw(AssertionError("delete must not call AWS")),
    )

    result = handler(
        {"RequestType": "Delete", "ResourceProperties": {"AgentRuntimeId": "runtime-id"}},
        SimpleNamespace(),
    )

    assert result == {"PhysicalResourceId": "runtime-id"}
