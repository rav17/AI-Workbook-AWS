from __future__ import annotations

import json
import re
from pathlib import Path

from speckit_flow.models import DEFAULT_PROFILE, FlowError, Profile

DEFAULT_PROFILES_DIR = Path(__file__).resolve().parent.parent / ".specify" / "profiles"

_KEYWORDS: dict[str, tuple[str, ...]] = {
    "security-patch": ("cve", "vulnerability", "vulnerabilities", "security patch", "exploit"),
    "bugfix": ("bug", "fix", "defect", "crash", "regression", "broken", "error in"),
    "refactor": ("refactor", "restructure", "cleanup", "clean up", "tech debt", "rename"),
    "infra": ("infrastructure", "terraform", "cdk", "cloudformation", "deployment", "iac", "cost"),
    "poc": ("proof of concept", "poc", "prototype", "feasibility", "spike"),
    "enterprise": ("regulated", "compliance", "audit", "kyc", "aml", "high-assurance"),
}
_PRIORITY = ("security-patch", "bugfix", "refactor", "infra", "poc", "enterprise")


def load_profiles(profiles_dir: Path = DEFAULT_PROFILES_DIR) -> dict[str, Profile]:
    """Load and validate every profile; the first invalid file raises FlowError."""
    if not profiles_dir.is_dir():
        raise FlowError(f"profiles directory not found: {profiles_dir}")
    profiles: dict[str, Profile] = {}
    for path in sorted(profiles_dir.glob("*.json")):
        profiles[path.stem] = load_profile_file(path)
    if not profiles:
        raise FlowError(f"no profiles found in {profiles_dir}")
    # Project overlay: .specify/custom/profiles/*.json adds or overrides profiles by id.
    overlay = profiles_dir.parent / "custom" / "profiles"
    if overlay.is_dir():
        for path in sorted(overlay.glob("*.json")):
            profiles[path.stem] = load_profile_file(path)
    return profiles


def load_profile_file(path: Path) -> Profile:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FlowError(f"{path.name}: cannot read profile: {exc}") from exc
    if not isinstance(data, dict):
        raise FlowError(f"{path.name}: profile must be a JSON object")
    try:
        return Profile.from_dict(data, expected_id=path.stem)
    except FlowError as exc:
        raise FlowError(f"{path.name}: {exc}") from exc


def get_profile(profile_id: str, profiles_dir: Path = DEFAULT_PROFILES_DIR) -> Profile:
    profiles = load_profiles(profiles_dir)
    if profile_id not in profiles:
        raise FlowError(
            f"unknown profile {profile_id!r}; valid profiles: {', '.join(sorted(profiles))}"
        )
    return profiles[profile_id]


def suggest_profile(description: str, available: set[str] | None = None) -> tuple[str, str]:
    """Advisory keyword match; returns (profile id, reason). Defaults to feature."""
    text = description.lower()
    for profile_id in _PRIORITY:
        if available is not None and profile_id not in available:
            continue
        for keyword in _KEYWORDS[profile_id]:
            if re.search(rf"\b{re.escape(keyword)}\b", text):
                return profile_id, f"matched keyword {keyword!r}"
    return DEFAULT_PROFILE, "no specific keywords matched; using the default profile"
