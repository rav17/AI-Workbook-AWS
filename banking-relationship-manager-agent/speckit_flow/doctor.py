from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from speckit_flow import agents, audit, rules, sensors
from speckit_flow import state as flow_state
from speckit_flow.models import FlowError
from speckit_flow.profiles import load_profiles


@dataclass
class Check:
    name: str
    status: str
    detail: str

    def to_dict(self) -> dict[str, str]:
        return {"name": self.name, "status": self.status, "detail": self.detail}


def _guarded(name: str, fn: Callable[[], tuple[str, str]]) -> Check:
    try:
        status, detail = fn()
    except (FlowError, OSError, ValueError) as exc:
        return Check(name, "fail", str(exc))
    return Check(name, status, detail)


def run_doctor(
    root: Path,
    profiles_dir: Path,
    roster_file: Path,
    sensors_file: Path,
    rules_file: Path,
    feature_dir: Path | None = None,
) -> list[Check]:
    checks: list[Check] = []

    def profiles_check() -> tuple[str, str]:
        return "ok", f"{len(load_profiles(profiles_dir))} profile(s) valid"

    def roster_check() -> tuple[str, str]:
        roster = agents.load_roster(roster_file)
        problems = agents.validate_roster(roster, root)
        if problems:
            raise FlowError("; ".join(problems))
        return "ok", f"{len(roster)} agents valid"

    def sensors_check() -> tuple[str, str]:
        if not sensors_file.is_file():
            return "warn", "no sensor configuration; gates are not sensor-checked"
        return "ok", f"{len(sensors.load_sensors(sensors_file))} sensor(s) valid"

    def rules_check() -> tuple[str, str]:
        if not rules_file.is_file():
            return "warn", "no rules file yet"
        return "ok", f"{len(rules.load_rules(rules_file))} rule(s) loaded"

    def hooks_check() -> tuple[str, str]:
        hook = root / ".github" / "hooks" / "speckit-guard.json"
        if not hook.is_file():
            return "warn", "guard hook config missing"
        json.loads(hook.read_text(encoding="utf-8"))
        if not (root / "scripts" / "speckit_guard.py").is_file():
            raise FlowError("hook script scripts/speckit_guard.py missing")
        return "ok", "guard hook configured"

    def workflow_check() -> tuple[str, str]:
        path = root / ".specify" / "workflows" / "speckit" / "workflow.yml"
        if not path.is_file():
            return "warn", "workflow file missing"
        if "speckit_flow" not in path.read_text(encoding="utf-8"):
            raise FlowError("workflow does not call speckit_flow lifecycle steps")
        return "ok", "workflow wired to speckit_flow"

    for name, fn in (
        ("profiles", profiles_check),
        ("roster", roster_check),
        ("sensors", sensors_check),
        ("rules", rules_check),
        ("hooks", hooks_check),
        ("workflow", workflow_check),
    ):
        checks.append(_guarded(name, fn))

    if feature_dir is not None and (feature_dir / flow_state.STATE_FILE).is_file():

        def state_check() -> tuple[str, str]:
            st = flow_state.load_state(feature_dir)
            return "ok", f"profile={st.profile}"

        def audit_check() -> tuple[str, str]:
            broken = audit.verify_chain(feature_dir)
            if broken:
                raise FlowError(f"audit integrity problem: {broken}")
            if audit.is_parked(feature_dir):
                return "ok", "audit chain intact (feature is parked)"
            return "ok", "audit chain intact"

        checks.append(_guarded("feature-state", state_check))
        checks.append(_guarded("audit-chain", audit_check))
    else:
        checks.append(Check("feature", "skip", "no initialized feature directory"))
    return checks


def render(checks: list[Check]) -> str:
    return "\n".join(f"{c.status:4} {c.name}: {c.detail}" for c in checks)
