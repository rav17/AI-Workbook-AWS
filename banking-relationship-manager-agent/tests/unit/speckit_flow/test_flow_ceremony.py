from __future__ import annotations

import json
from pathlib import Path

import pytest

from speckit_flow.cli import main
from speckit_flow.models import FlowError, Profile
from speckit_flow.profiles import load_profiles

PROFILES = Path(__file__).resolve().parents[3] / ".specify" / "profiles"


def _p(**extra: object) -> dict:
    return {
        "id": "x",
        "description": "d",
        "stages": ["specify", "tasks", "implement"],
        "depth": "minimal",
        "gates": ["specify"],
        **extra,
    }


def test_ceremony_defaults_on_and_bugfix_skips_learning() -> None:
    profiles = load_profiles(PROFILES)
    assert Profile.from_dict(_p()).ceremony_on("learning")
    assert not profiles["bugfix"].ceremony_on("learning")
    assert profiles["bugfix"].ceremony_on("reviews")
    assert profiles["feature"].ceremony_on("learning")


@pytest.mark.parametrize(
    "ceremony",
    [{"nope": True}, {"learning": "no"}, ["learning"]],
)
def test_invalid_ceremony_is_refused(ceremony: object) -> None:
    with pytest.raises(FlowError):
        Profile.from_dict(_p(ceremony=ceremony))


def test_strict_policy_cannot_skip_reviews() -> None:
    with pytest.raises(FlowError, match="reviews"):
        Profile.from_dict(_p(guard_policy="strict", ceremony={"reviews": False}))
    with pytest.raises(FlowError, match="reviews"):
        Profile.from_dict(_p(depth="comprehensive", ceremony={"reviews": False}))


def test_ceremony_round_trips() -> None:
    profile = Profile.from_dict(_p(ceremony={"learning": False}))
    assert profile.to_dict()["ceremony"] == {"learning": False}


def test_rules_propose_refused_when_learning_is_off(tmp_path: Path) -> None:
    d = tmp_path / "specs" / "030-x"
    d.mkdir(parents=True)
    rules = tmp_path / "rules.json"
    base = ["--feature-dir", str(d), "--sensors-file", str(tmp_path / "none.json")]
    propose = ["rules", "propose", "--text", "Prefer small diffs", "--manual", *base]
    propose += ["--rules-file", str(rules)]
    assert main(["init", "--profile", "bugfix", *base, "--actor", "human:a"]) == 0
    assert main([*propose, "--actor", "agent:developer"]) == 1
    assert not rules.exists() or not json.loads(rules.read_text("utf-8")).get("rules")
    assert main(["switch", "--profile", "feature", "--confirm", *base, "--actor", "human:a"]) == 0
    assert main([*propose, "--actor", "agent:developer"]) == 0
