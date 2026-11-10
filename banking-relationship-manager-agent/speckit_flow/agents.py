from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from speckit_flow.models import STAGE_LEADS, STAGES, FlowError, Profile

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ROSTER_FILE = REPO_ROOT / ".specify" / "agents" / "roster.json"

ROLES: tuple[str, ...] = ("domain", "reviewer", "composer", "conductor")
TIERS: tuple[str, ...] = ("judgment", "templated", "balanced")
EXPECTED_COUNTS = {"domain": 11, "reviewer": 2, "composer": 1, "conductor": 1}
_ID_RE = re.compile(r"^[a-z][a-z0-9-]*$")


@dataclass(frozen=True)
class Agent:
    id: str
    role: str
    tier: str
    file: str
    leads: tuple[str, ...]
    supports: tuple[str, ...]
    can_edit: bool
    source: str = "core"

    @property
    def agent_name(self) -> str:
        return f"speckit-{self.id}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "role": self.role,
            "tier": self.tier,
            "file": self.file,
            "leads": list(self.leads),
            "supports": list(self.supports),
            "can_edit": self.can_edit,
            "source": self.source,
        }


def _read_items(path: Path, what: str) -> list[Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FlowError(f"cannot read {what} {path}: {exc}") from exc
    items = data.get("agents") if isinstance(data, dict) else None
    if not isinstance(items, list):
        raise FlowError(f"{what} must be an object with an 'agents' list")
    return items


def _build(item: Any, source: str) -> Agent:
    try:
        return Agent(
            id=str(item["id"]),
            role=str(item["role"]),
            tier=str(item["tier"]),
            file=str(item["file"]),
            leads=tuple(item.get("leads", ())),
            supports=tuple(item.get("supports", ())),
            can_edit=bool(item["can_edit"]),
            source=source,
        )
    except (KeyError, TypeError, AttributeError) as exc:
        raise FlowError(f"malformed roster entry: {item!r}") from exc


def _extra_sources(specify_dir: Path) -> list[tuple[str, Path]]:
    """Add-only agent files: enabled plugins by name, then the project overlay."""
    from speckit_flow import plugins

    try:
        found = [
            (f"plugin:{p.name}", p.path / "agents.json") for p in plugins.discover(specify_dir)
        ]
    except plugins.PluginError as exc:
        raise FlowError(str(exc)) from exc
    found.append(("custom", specify_dir / "custom" / "agents.json"))
    return [(source, p) for source, p in found if p.is_file()]


def load_roster(path: Path = DEFAULT_ROSTER_FILE) -> dict[str, Agent]:
    roster: dict[str, Agent] = {}
    for item in _read_items(path, "roster"):
        agent = _build(item, "core")
        if agent.id in roster:
            raise FlowError(f"duplicate agent id {agent.id!r}")
        roster[agent.id] = agent
    for source, extra_path in _extra_sources(path.parent.parent):
        for item in _read_items(extra_path, f"{source} agents"):
            agent = _build(item, source)
            if agent.id in roster:
                raise FlowError(f"{source}: agent id {agent.id!r} already exists; extras only add")
            if agent.role != "domain" or agent.leads:
                raise FlowError(
                    f"{source}: agent {agent.id!r} must be a domain agent that only supports stages"
                )
            roster[agent.id] = agent
    return roster


def parse_frontmatter(text: str) -> dict[str, Any]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise FlowError("agent file has no frontmatter")
    out: dict[str, Any] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            return out
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        value = value.strip()
        if value.startswith("["):
            try:
                out[key.strip()] = json.loads(value.replace("'", '"'))
            except json.JSONDecodeError as exc:
                raise FlowError(f"bad list for {key.strip()!r} in agent frontmatter") from exc
        elif value in ("true", "false"):
            out[key.strip()] = value == "true"
        else:
            out[key.strip()] = value
    raise FlowError("agent frontmatter is not closed")


def _check_agent_file(agent: Agent, roster: dict[str, Agent], root: Path) -> list[str]:
    path = root / agent.file
    if not path.is_file():
        return [f"{agent.id}: agent file {agent.file} is missing"]
    try:
        meta = parse_frontmatter(path.read_text(encoding="utf-8"))
    except (OSError, FlowError) as exc:
        return [f"{agent.id}: {exc}"]
    problems: list[str] = []
    if meta.get("name") != agent.agent_name:
        problems.append(f"{agent.id}: frontmatter name must be {agent.agent_name!r}")
    if not meta.get("description"):
        problems.append(f"{agent.id}: description is required")
    if meta.get("disable-model-invocation") is True:
        problems.append(f"{agent.id}: disable-model-invocation prevents automated dispatch")
    tools = meta.get("tools")
    if not isinstance(tools, list):
        return [*problems, f"{agent.id}: tools must be a list"]
    if ("edit" in tools) != agent.can_edit:
        problems.append(f"{agent.id}: 'edit' tool must match can_edit={agent.can_edit}")
    if agent.role == "conductor":
        if "agent" not in tools:
            problems.append(f"{agent.id}: conductor needs the 'agent' tool")
        if "execute" not in tools:
            problems.append(f"{agent.id}: conductor needs the 'execute' tool for preflight")
        core = {
            a.agent_name for a in roster.values() if a.role != "conductor" and a.source == "core"
        }
        everyone = {a.agent_name for a in roster.values() if a.role != "conductor"}
        listed = set(meta.get("agents") or [])
        if not core <= listed <= everyone:
            problems.append(
                f"{agent.id}: 'agents' must list every core agent and only roster agents"
            )
        if meta.get("user-invocable") is False:
            problems.append(f"{agent.id}: conductor must be user-invocable")
    else:
        if "agent" in tools:
            problems.append(f"{agent.id}: only the conductor may hold the 'agent' tool")
        if meta.get("user-invocable") is not False:
            problems.append(f"{agent.id}: must set user-invocable: false")
    if agent.leads and "execute" not in tools:
        problems.append(f"{agent.id}: stage lead needs 'execute' for stage skill helpers")
    return problems


def undispatchable(roster: dict[str, Agent], root: Path = REPO_ROOT) -> list[str]:
    """Extra agents the conductor cannot dispatch because its 'agents' list omits them."""
    conductor = next((a for a in roster.values() if a.role == "conductor"), None)
    if conductor is None:
        return []
    try:
        meta = parse_frontmatter((root / conductor.file).read_text(encoding="utf-8"))
    except (OSError, FlowError):
        return []
    listed = set(meta.get("agents") or [])
    return sorted(
        a.agent_name for a in roster.values() if a.source != "core" and a.agent_name not in listed
    )


def validate_roster(roster: dict[str, Agent], root: Path = REPO_ROOT) -> list[str]:
    problems: list[str] = []
    for role, expected in EXPECTED_COUNTS.items():
        found = sum(1 for a in roster.values() if a.role == role and a.source == "core")
        if found != expected:
            problems.append(f"expected {expected} {role} agent(s), found {found}")
    for agent in roster.values():
        if not _ID_RE.match(agent.id):
            problems.append(f"invalid agent id {agent.id!r}")
        if agent.role not in ROLES:
            problems.append(f"{agent.id}: unknown role {agent.role!r}")
        if agent.tier not in TIERS:
            problems.append(f"{agent.id}: unknown tier {agent.tier!r}")
        for stage in (*agent.leads, *agent.supports):
            if stage not in STAGES:
                problems.append(f"{agent.id}: unknown stage {stage!r}")
        if agent.leads and agent.role != "domain":
            problems.append(f"{agent.id}: only domain agents may lead stages")
        problems.extend(_check_agent_file(agent, roster, root))
    for stage in STAGES:
        leads = [a.id for a in roster.values() if stage in a.leads]
        if stage in STAGE_LEADS:
            leads.append(STAGE_LEADS[stage])
        if len(leads) != 1 or leads[0] not in roster:
            problems.append(f"stage {stage!r} needs exactly one lead, found {leads}")
    return problems


def resolve_assignments(profile: Profile, roster: dict[str, Agent]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for stage in profile.stages:
        override = profile.assignments.get(stage)
        if override is not None:
            lead = override["lead"]
            support = list(override.get("support", []))
            for name in (lead, *support):
                if name not in roster:
                    raise FlowError(f"profile {profile.id}: unknown agent {name!r} for {stage!r}")
            if roster[lead].role != "domain":
                raise FlowError(f"profile {profile.id}: lead for {stage!r} must be a domain agent")
            if lead in support:
                raise FlowError(f"profile {profile.id}: {lead!r} cannot lead and support {stage!r}")
        else:
            leads = [a.id for a in roster.values() if stage in a.leads]
            if stage in STAGE_LEADS and STAGE_LEADS[stage] in roster:
                leads.append(STAGE_LEADS[stage])
            if len(leads) != 1:
                raise FlowError(f"stage {stage!r} has no single lead in the roster")
            lead = leads[0]
            support = [a.id for a in roster.values() if stage in a.supports]
        result[stage] = {"lead": lead, "support": support}
    return result


ENGINE_ACTOR = "agent:workflow"


def check_actor(actor: str, roster: dict[str, Agent]) -> None:
    if actor == ENGINE_ACTOR:
        return
    if actor.startswith("agent:") and actor.split(":", 1)[1] not in roster:
        raise FlowError(f"unknown agent actor {actor!r}; use an id from the roster")
