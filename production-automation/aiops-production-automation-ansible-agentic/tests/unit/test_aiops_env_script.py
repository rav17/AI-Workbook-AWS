"""Unit tests for the pure helpers in scripts/aiops_env.py."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_PATH = Path(__file__).resolve().parents[2] / "scripts" / "aiops_env.py"
_spec = importlib.util.spec_from_file_location("aiops_env", _PATH)
aiops_env = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(aiops_env)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("aws-cli/2.39.7 Python/3.14.8 Windows/11 exe/AMD64", (2, 39)),
        ("aws-cli/2.34.9 Python/3.13.11", (2, 34)),
        ("aws-cli/2.100.0", (2, 100)),
        ("", (0, 0)),
        ("garbage", (0, 0)),
    ],
)
def test_parse_cli_version(text, expected) -> None:
    assert aiops_env.parse_cli_version(text) == expected


def test_old_cli_is_below_minimum() -> None:
    assert aiops_env.parse_cli_version("aws-cli/2.34.9") < aiops_env.MIN_AWS_CLI
    assert aiops_env.parse_cli_version("aws-cli/2.39.0") >= aiops_env.MIN_AWS_CLI


@pytest.mark.parametrize(
    ("stored", "live", "action"),
    [
        ("", None, "create"),  # no webhook yet
        ("https://hook/a", None, "create"),  # stale secret, webhook gone
        ("https://hook/a", "https://hook/a", "keep"),  # already wired
        ("", "https://hook/a", "recreate"),  # one-time secret was never stored
        ("https://hook/old", "https://hook/a", "recreate"),
    ],
)
def test_webhook_action(stored, live, action) -> None:
    assert aiops_env.webhook_action(stored, live) == action


def test_names_are_environment_scoped() -> None:
    n = aiops_env.names_for("dev")
    assert n["space"] == "aiops-dev"
    assert n["table"] == "AiopsIncidentMemory-dev"
    assert n["webhook_secret"] == "/aiops/dev/devops-agent-webhook"
    assert all("dev" in v for v in n.values())
    assert aiops_env.names_for("prod")["param_prefix"] == "/aiops/prod/"


def test_trust_policy_is_confused_deputy_protected() -> None:
    stmt = aiops_env.trust_policy(["sts:AssumeRole"])["Statement"][0]
    assert stmt["Principal"] == {"Service": "aidevops.amazonaws.com"}
    assert stmt["Condition"]["StringEquals"]["aws:SourceAccount"] == aiops_env.ACCOUNT
    assert stmt["Condition"]["ArnLike"]["aws:SourceArn"].endswith(":agentspace/*")


def test_down_without_yes_for_prod_requires_typing(monkeypatch) -> None:
    monkeypatch.setattr("builtins.input", lambda _prompt: "dev")
    assert aiops_env.confirm("prod", assume_yes=True) is False  # --yes never bypasses prod
    monkeypatch.setattr("builtins.input", lambda _prompt: "prod")
    assert aiops_env.confirm("prod", assume_yes=True) is True
    assert aiops_env.confirm("dev", assume_yes=True) is True


def test_runner_decodes_cli_output_as_utf8(monkeypatch) -> None:
    """Agent summaries contain non-ASCII text (for example an arrow); the Windows
    locale codec (cp1252) used to crash the script on it."""
    import json
    import subprocess

    payload = {"summary": "disk full \u2192 clear /var"}
    seen: dict = {}

    def fake_run(cmd, **kwargs):
        seen.update(kwargs)
        return subprocess.CompletedProcess(
            cmd, 0, stdout=json.dumps(payload), stderr=""
        )

    monkeypatch.setattr(aiops_env, "_exe", lambda name: name)
    monkeypatch.setattr(aiops_env.subprocess, "run", fake_run)
    runner = aiops_env.Runner("test-profile")
    try:
        assert runner.aws("devops-agent", "list-agent-spaces", quiet=True) == payload
    finally:
        runner.close()
    assert seen["encoding"] == "utf-8"
    assert seen["errors"] == "replace"
