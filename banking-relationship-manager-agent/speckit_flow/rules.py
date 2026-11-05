from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from speckit_flow import audit
from speckit_flow.models import STAGES, FlowError, Rule
from speckit_flow.state import atomic_write

DEFAULT_RULES_FILE = Path(__file__).resolve().parent.parent / ".specify" / "rules" / "rules.json"
MAX_STAGE_RULES = 10
_NEGATIONS = {"not", "never", "no", "dont", "don't", "without"}
_FILLER = {"do", "does", "always", "must", "should"}
_WORD_RE = re.compile(r"[a-z0-9']+")


def load_rules(path: Path = DEFAULT_RULES_FILE) -> list[Rule]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        rules = [Rule(**item) for item in data["rules"]]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise FlowError(f"rules file is unreadable: {exc}") from exc
    for rule in rules:
        rule.validate()
    return rules


def _save(path: Path, rules: list[Rule]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(path, json.dumps({"rules": [r.to_dict() for r in rules]}, indent=2) + "\n")


def _origin(from_gate: str | None, from_finding: str | None, feature: str) -> str:
    if from_gate:
        if from_gate not in STAGES:
            raise FlowError(f"unknown stage {from_gate!r}")
        return f"gate:{feature}:{from_gate}"
    if from_finding:
        return f"finding:{feature}:{from_finding}"
    return "manual"


def propose_rule(
    feature_dir: Path,
    text: str,
    actor: str,
    *,
    from_gate: str | None = None,
    from_finding: str | None = None,
    path: Path = DEFAULT_RULES_FILE,
) -> Rule:
    """Store a pending rule; nothing becomes active without a human decision."""
    text = text.strip()
    if not 1 <= len(text) <= 300:
        raise FlowError("rule text must be 1-300 characters")
    audit.check_redaction(text)
    if from_finding and not re.match(r"^[a-z]+-\d+:\d+$", from_finding):
        raise FlowError("--from-finding must look like '<review-id>:<n>'")
    rules = load_rules(path)
    number = max((int(r.id[2:]) for r in rules), default=0) + 1
    rule = Rule(
        id=f"R-{number:03d}",
        text=text,
        origin=_origin(from_gate, from_finding, feature_dir.name),
        status="pending",
        proposed_at=audit.now_iso(),
    )
    rule.validate()
    audit.append_event(
        feature_dir, "rule_proposed", None, actor, f"rule={rule.id} origin={rule.origin}"
    )
    _save(path, [*rules, rule])
    return rule


def decide_rule(
    feature_dir: Path,
    rule_id: str,
    approve: bool,
    actor: str,
    path: Path = DEFAULT_RULES_FILE,
) -> Rule:
    if not actor.startswith("human:"):
        raise FlowError("only a human can approve or discard a rule")
    rules = load_rules(path)
    rule = next((r for r in rules if r.id == rule_id), None)
    if rule is None:
        raise FlowError(f"unknown rule {rule_id!r}")
    target = "active" if approve else "discarded"
    allowed = {("pending", "active"), ("pending", "discarded"), ("active", "discarded")}
    if (rule.status, target) not in allowed:
        raise FlowError(f"rule {rule_id} is {rule.status}; cannot move it to {target}")
    audit.append_event(
        feature_dir,
        "rule_approved" if approve else "rule_discarded",
        None,
        actor,
        f"rule={rule.id}",
    )
    rule.status, rule.decided_by = target, actor
    _save(path, rules)
    return rule


def _applies(rule: Rule, stage: str) -> bool:
    parts = rule.origin.split(":")
    if parts[0] == "gate":
        return parts[2] == stage
    if parts[0] == "finding":
        return parts[2].rsplit("-", 1)[0] == stage
    return True


def _core(text: str) -> tuple[frozenset[str], bool]:
    words = _WORD_RE.findall(text.lower())
    negated = any(w in _NEGATIONS for w in words)
    return frozenset(w for w in words if w not in _NEGATIONS and w not in _FILLER), negated


def find_conflicts(rules: list[Rule]) -> set[str]:
    """Flag rules whose wording matches but with opposite polarity."""
    flagged: set[str] = set()
    for i, first in enumerate(rules):
        core_a, neg_a = _core(first.text)
        for second in rules[i + 1 :]:
            core_b, neg_b = _core(second.text)
            if core_a == core_b and neg_a != neg_b:
                flagged.update({first.id, second.id})
    return flagged


LAYERS = ("org", "team", "project", "phase")


def _layer_path(path: Path, layer: str, stage: str | None) -> Path | None:
    if layer == "project":
        return path
    if layer == "phase":
        # Phase rules are scoped to one stage, so they need a stage to apply.
        return path.parent / "phase" / f"{stage}.json" if stage else None
    return path.parent / f"{layer}.json"


def effective_rules(path: Path = DEFAULT_RULES_FILE, stage: str | None = None) -> dict[str, Any]:
    """Merge active rules from org, team, project and phase layers; the narrower layer wins.

    org.json, team.json and phase/<stage>.json sit beside the project file and are
    human-authored. A broader rule is overridden when a narrower one has the same
    wording with opposite polarity.
    """
    layered: list[tuple[str, Rule]] = []
    for layer in LAYERS:
        layer_path = _layer_path(path, layer, stage)
        if layer_path is None:
            continue
        for rule in load_rules(layer_path):
            if rule.status == "active" and (stage is None or _applies(rule, stage)):
                layered.append((layer, rule))
    cores = [(layer, rule, *_core(rule.text)) for layer, rule in layered]
    overridden: set[tuple[str, str]] = set()
    for i, (layer_a, rule_a, core_a, neg_a) in enumerate(cores):
        for layer_b, rule_b, core_b, neg_b in cores[i + 1 :]:
            if core_a == core_b and neg_a != neg_b and layer_a != layer_b:
                overridden.add((layer_a, rule_a.id))
    kept = [(layer, rule) for layer, rule in layered if (layer, rule.id) not in overridden]
    shown = kept[-MAX_STAGE_RULES:] if stage else kept
    return {
        "rules": [{**rule.to_dict(), "layer": layer, "conflict": False} for layer, rule in shown],
        "omitted": len(kept) - len(shown),
        "overridden": [{"layer": layer, "id": rid} for layer, rid in sorted(overridden)],
    }


def list_rules(
    path: Path = DEFAULT_RULES_FILE,
    status: str | None = None,
    stage: str | None = None,
) -> dict[str, Any]:
    rules = load_rules(path)
    if stage:
        active = [r for r in rules if r.status == "active" and _applies(r, stage)]
        shown = active[-MAX_STAGE_RULES:]
        omitted = len(active) - len(shown)
    else:
        shown = [r for r in rules if status is None or r.status == status]
        omitted = 0
    conflicts = find_conflicts(shown)
    return {
        "rules": [{**r.to_dict(), "conflict": r.id in conflicts} for r in shown],
        "omitted": omitted,
    }
