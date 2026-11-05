from __future__ import annotations

import json
from pathlib import Path

import pytest

from speckit_flow.models import FlowError, Profile
from speckit_flow.profiles import (
    DEFAULT_PROFILES_DIR,
    get_profile,
    load_profile_file,
    load_profiles,
    suggest_profile,
)

REPO = Path(__file__).resolve().parents[3]


def _base(**over: object) -> dict[str, object]:
    data: dict[str, object] = {
        "id": "x",
        "description": "d",
        "stages": ["specify", "plan", "tasks", "implement"],
        "depth": "standard",
        "gates": ["plan"],
    }
    data.update(over)
    return data


def test_all_shipped_profiles_valid() -> None:
    profiles = load_profiles(DEFAULT_PROFILES_DIR)
    assert set(profiles) == {
        "feature",
        "enterprise",
        "express",
        "bugfix",
        "refactor",
        "infra",
        "security-patch",
        "poc",
        "full-lifecycle",
    }


def test_enterprise_gates_every_stage() -> None:
    p = get_profile("enterprise")
    assert p.depth == "comprehensive"
    assert set(p.gates) == set(p.stages)


@pytest.mark.parametrize(
    "over",
    [
        {"stages": ["plan", "specify"]},
        {"stages": ["plan", "tasks"]},
        {"stages": ["specify", "plan", "implement"]},
        {"stages": ["specify", "specify"]},
        {"stages": ["specify", "bogus"]},
        {"stages": []},
        {"gates": ["analyze"]},
        {"depth": "huge"},
        {"id": "Bad_ID"},
        {"exemptions": ["nope"]},
    ],
)
def test_invalid_profiles_rejected(over: dict[str, object]) -> None:
    with pytest.raises(FlowError):
        Profile.from_dict(_base(**over))


def test_unknown_and_missing_fields_rejected() -> None:
    with pytest.raises(FlowError, match="unknown fields"):
        Profile.from_dict(_base(extra=1))
    data = _base()
    del data["depth"]
    with pytest.raises(FlowError, match="missing"):
        Profile.from_dict(data)


def test_exemption_allows_implement_without_tasks() -> None:
    p = Profile.from_dict(
        _base(stages=["specify", "implement"], gates=[], exemptions=["implement-without-tasks"])
    )
    assert p.stages == ("specify", "implement")


def test_id_must_match_filename(tmp_path: Path) -> None:
    (tmp_path / "other.json").write_text(json.dumps(_base()), encoding="utf-8")
    with pytest.raises(FlowError, match="does not match filename"):
        load_profile_file(tmp_path / "other.json")


def test_unknown_profile_lists_valid() -> None:
    with pytest.raises(FlowError, match="valid profiles: .*bugfix"):
        get_profile("nope")


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("fix crash in statement parser", "bugfix"),
        ("Patch CVE-2026-1234 in dependency", "security-patch"),
        ("refactor the memory module", "refactor"),
        ("add terraform for new environment", "infra"),
        ("prototype a new idea", "poc"),
        ("add dispute summary feature", "feature"),
    ],
)
def test_suggest(text: str, expected: str) -> None:
    assert suggest_profile(text)[0] == expected


def test_feature_profile_matches_workflow_yml() -> None:
    yaml = pytest.importorskip("yaml")
    wf = yaml.safe_load((REPO / ".specify/workflows/speckit/workflow.yml").read_text("utf-8"))
    command_steps = [
        (i, s["command"].split(".")[1]) for i, s in enumerate(wf["steps"]) if "command" in s
    ]
    commands = [name for _, name in command_steps]
    gates = [
        max((i, name) for i, name in command_steps if i < idx)[1]
        for idx, step in enumerate(wf["steps"])
        if step.get("type") == "gate"
    ]
    feature = get_profile("feature")
    assert list(feature.stages) == commands
    assert list(feature.gates) == gates
