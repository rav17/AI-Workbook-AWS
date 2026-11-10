from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from scripts.build_artifacts import (
    MAX_LAMBDA_UNCOMPRESSED_BYTES,
    _python_platform,
    _validate_bundle,
)


def test_artifact_targets_use_runtime_specific_linux_platforms() -> None:
    assert _python_platform("lambda") == "x86_64-manylinux2014"
    assert _python_platform("runtime") == "x86_64-manylinux_2_28"

    with pytest.raises(ValueError, match="Unsupported artifact target"):
        _python_platform("unknown")


def test_artifact_rejects_repository_test_and_virtualenv_roots(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    (bundle / "tests").mkdir(parents=True)
    (bundle / "tests" / "test_local.py").write_text("pass", encoding="ascii")

    with pytest.raises(RuntimeError, match="Forbidden path"):
        _validate_bundle(bundle, "lambda")


def test_artifact_enforces_lambda_uncompressed_size_limit(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    oversized = bundle / "payload.bin"
    with oversized.open("wb") as stream:
        stream.truncate(MAX_LAMBDA_UNCOMPRESSED_BYTES + 1)

    with pytest.raises(RuntimeError, match="limit"):
        _validate_bundle(bundle, "lambda")


def test_runtime_artifact_allows_linux_dependency_test_data(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    dependency_tests = bundle / "vendor" / "package" / "tests"
    dependency_tests.mkdir(parents=True)
    (dependency_tests / "test_vendor.py").write_text("pass", encoding="ascii")

    assert _validate_bundle(bundle, "runtime") > 0


def test_github_workflow_actions_are_pinned_to_full_commit_shas() -> None:
    repository_root = Path(__file__).resolve().parents[2]
    workflow_paths = (
        repository_root / ".github/workflows/quality.yml",
        repository_root / ".github/workflows/deploy.yml",
    )

    for workflow_path in workflow_paths:
        workflow = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
        actions = [
            step["uses"]
            for job in workflow["jobs"].values()
            for step in job.get("steps", [])
            if "uses" in step
        ]
        assert actions
        assert all(re.fullmatch(r"[^@]+@[0-9a-f]{40}", action) for action in actions)


def test_deploy_workflow_requires_boundary_before_production_synthesis() -> None:
    workflow_path = Path(__file__).resolve().parents[2] / ".github/workflows/deploy.yml"
    deploy_job = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))["jobs"]["deploy"]
    steps = deploy_job["steps"]

    assert "CDK_PERMISSIONS_BOUNDARY_ARN" in deploy_job["env"]
    assert any(
        "CDK_PERMISSIONS_BOUNDARY_ARN is required outside dev" in step.get("run", "")
        for step in steps
    )
    cdk_stages = [
        step["name"] for step in steps if step.get("name") in {"Synthesize", "Diff", "Deploy"}
    ]
    assert cdk_stages == ["Synthesize", "Diff", "Deploy"]
