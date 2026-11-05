from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from speckit_flow.stagedefs import StageDef, StageDefError, load_stage_defs


class FlowError(Exception):
    """Raised for any user-facing validation or state error."""


def _load_stage_table() -> list[StageDef]:
    try:
        return load_stage_defs()
    except StageDefError as exc:
        raise FlowError(f"invalid stage definitions: {exc}") from exc


STAGE_DEFS: tuple[StageDef, ...] = tuple(_load_stage_table())
STAGES: tuple[str, ...] = tuple(s.id for s in STAGE_DEFS)
OPTIONAL_STAGES: tuple[str, ...] = tuple(s.id for s in STAGE_DEFS if s.optional)
STAGE_REQUIRES: dict[str, tuple[str, ...]] = {s.id: s.requires for s in STAGE_DEFS if s.requires}
STAGE_LEADS: dict[str, str] = {s.id: s.lead for s in STAGE_DEFS if s.lead}
FIRST_STAGE: str = next(s.id for s in STAGE_DEFS if not s.optional)
DEPTHS: tuple[str, ...] = ("minimal", "standard", "comprehensive")
EVENT_TYPES: tuple[str, ...] = (
    "profile_selected",
    "profile_changed",
    "stage_started",
    "stage_completed",
    "stage_skipped",
    "gate_approved",
    "gate_rejected",
    "failure",
    "review_recorded",
    "gate_overridden",
    "rule_proposed",
    "rule_approved",
    "rule_discarded",
    "route_composed",
    "sensor_run",
    "intent_switched",
    "intent_parked",
    "intent_resumed",
    "stage_redone",
    "question_asked",
    "question_answered",
    "unit_defined",
    "unit_checkpoint",
)
STATUSES: tuple[str, ...] = ("pending", "in_progress", "done", "skipped")
EXEMPTIONS: tuple[str, ...] = ("implement-without-tasks",)
DEFAULT_PROFILE = "feature"

_ID_RE = re.compile(r"^[a-z][a-z0-9-]*$")
_ACTOR_RE = re.compile(r"^(human|agent):.+")
_PROFILE_FIELDS = {
    "id",
    "description",
    "stages",
    "depth",
    "gates",
    "exemptions",
    "assignments",
    "test_strategy",
    "guard_policy",
    "ceremony",
}
CEREMONY_KEYS: tuple[str, ...] = ("learning", "reviews")
TEST_STRATEGIES: tuple[str, ...] = ("standard", "required")
GUARD_POLICIES: tuple[str, ...] = ("", "standard", "strict")


def _parse_ceremony(raw: Any) -> dict[str, bool]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise FlowError("profile ceremony must be an object")
    unknown = set(raw) - set(CEREMONY_KEYS)
    if unknown:
        raise FlowError(f"profile ceremony has unknown keys: {sorted(unknown)}")
    if not all(isinstance(v, bool) for v in raw.values()):
        raise FlowError("profile ceremony values must be true or false")
    return dict(raw)


@dataclass(frozen=True)
class Profile:
    id: str
    description: str
    stages: tuple[str, ...]
    depth: str
    gates: tuple[str, ...]
    exemptions: tuple[str, ...] = ()
    assignments: dict[str, Any] = field(default_factory=dict)
    test_strategy: str = "standard"
    guard_policy: str = ""
    ceremony: dict[str, bool] = field(default_factory=dict)

    def ceremony_on(self, name: str) -> bool:
        """Optional ceremony defaults to on; a profile can switch a named item off."""
        return self.ceremony.get(name, True)

    @property
    def strict(self) -> bool:
        """Strict guard policy; comprehensive depth implies it unless set explicitly."""
        return self.guard_policy == "strict" or (
            not self.guard_policy and self.depth == "comprehensive"
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any], expected_id: str | None = None) -> Profile:
        unknown = set(data) - _PROFILE_FIELDS
        if unknown:
            raise FlowError(f"profile has unknown fields: {sorted(unknown)}")
        missing = {"id", "description", "stages", "depth", "gates"} - set(data)
        if missing:
            raise FlowError(f"profile is missing fields: {sorted(missing)}")
        raw_assignments = data.get("assignments") or {}
        if not isinstance(raw_assignments, dict):
            raise FlowError("profile assignments must be an object")
        profile = cls(
            id=str(data["id"]),
            description=str(data["description"]),
            stages=tuple(data["stages"]),
            depth=str(data["depth"]),
            gates=tuple(data["gates"]),
            exemptions=tuple(data.get("exemptions", ())),
            assignments=dict(raw_assignments),
            test_strategy=str(data.get("test_strategy", "standard")),
            guard_policy=str(data.get("guard_policy", "")),
            ceremony=_parse_ceremony(data.get("ceremony")),
        )
        profile.validate(expected_id)
        return profile

    def validate(self, expected_id: str | None = None) -> None:
        if self.strict and not self.ceremony_on("reviews"):
            raise FlowError(f"profile {self.id}: strict guard policy needs ceremony reviews on")
        if self.test_strategy not in TEST_STRATEGIES:
            raise FlowError(
                f"profile {self.id}: test_strategy must be one of {list(TEST_STRATEGIES)}"
            )
        if self.guard_policy not in GUARD_POLICIES:
            raise FlowError(f"profile {self.id}: guard_policy must be 'standard' or 'strict'")
        if not _ID_RE.match(self.id):
            raise FlowError(f"invalid profile id: {self.id!r}")
        if expected_id is not None and expected_id != self.id:
            raise FlowError(f"profile id {self.id!r} does not match filename {expected_id!r}")
        if not self.description:
            raise FlowError(f"profile {self.id}: description is required")
        if self.depth not in DEPTHS:
            raise FlowError(f"profile {self.id}: depth must be one of {list(DEPTHS)}")
        if not self.stages:
            raise FlowError(f"profile {self.id}: stages must not be empty")
        if len(set(self.stages)) != len(self.stages):
            raise FlowError(f"profile {self.id}: duplicate stages")
        for stage in self.stages:
            if stage not in STAGES:
                raise FlowError(f"profile {self.id}: unknown stage {stage!r}")
        order = [STAGES.index(s) for s in self.stages]
        if order != sorted(order):
            raise FlowError(f"profile {self.id}: stages must be in canonical order {list(STAGES)}")
        for exemption in self.exemptions:
            if exemption not in EXEMPTIONS:
                raise FlowError(f"profile {self.id}: unknown exemption {exemption!r}")
        before = STAGES[: STAGES.index(FIRST_STAGE)]
        rest = [s for s in self.stages if s not in before]
        if not rest or rest[0] != FIRST_STAGE:
            raise FlowError(f"profile {self.id}: {FIRST_STAGE} must be the first stage")
        for stage in self.stages:
            for req in STAGE_REQUIRES.get(stage, ()):
                if req not in self.stages:
                    raise FlowError(f"profile {self.id}: {stage} requires {req}")
        if (
            "implement" in self.stages
            and "tasks" not in self.stages
            and "implement-without-tasks" not in self.exemptions
        ):
            raise FlowError(f"profile {self.id}: implement requires tasks")
        for gate in self.gates:
            if gate not in self.stages:
                raise FlowError(f"profile {self.id}: gate {gate!r} is not in stages")
        for stage, entry in self.assignments.items():
            if stage not in self.stages:
                raise FlowError(f"profile {self.id}: assignment for stage {stage!r} not in route")
            support = entry.get("support", []) if isinstance(entry, dict) else None
            if (
                not isinstance(entry, dict)
                or set(entry) - {"lead", "support"}
                or not isinstance(entry.get("lead"), str)
                or not isinstance(support, list)
                or not all(isinstance(s, str) for s in support)
            ):
                raise FlowError(
                    f"profile {self.id}: assignment for {stage!r} needs a 'lead' string "
                    "and an optional 'support' list of strings"
                )

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "id": self.id,
            "description": self.description,
            "stages": list(self.stages),
            "depth": self.depth,
            "gates": list(self.gates),
        }
        if self.exemptions:
            out["exemptions"] = list(self.exemptions)
        if self.assignments:
            out["assignments"] = {k: dict(v) for k, v in self.assignments.items()}
        if self.test_strategy != "standard":
            out["test_strategy"] = self.test_strategy
        if self.guard_policy:
            out["guard_policy"] = self.guard_policy
        if self.ceremony:
            out["ceremony"] = dict(self.ceremony)
        return out


@dataclass
class StageRecord:
    status: str = "pending"
    reason: str | None = None
    updated_at: str = ""


@dataclass
class FeatureState:
    feature: str
    profile: str
    depth: str
    stages: dict[str, StageRecord] = field(default_factory=dict)
    current_stage: str | None = None
    pending_gate: str | None = None
    revision: int = 0
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "feature": self.feature,
            "profile": self.profile,
            "depth": self.depth,
            "current_stage": self.current_stage,
            "pending_gate": self.pending_gate,
            "revision": self.revision,
            "updated_at": self.updated_at,
            "stages": {
                name: {"status": r.status, "reason": r.reason, "updated_at": r.updated_at}
                for name, r in self.stages.items()
            },
        }

    @classmethod
    def from_dict(cls, data: Any) -> FeatureState:
        try:
            stages = {
                name: StageRecord(
                    status=rec["status"], reason=rec.get("reason"), updated_at=rec["updated_at"]
                )
                for name, rec in data["stages"].items()
            }
            state = cls(
                feature=data["feature"],
                profile=data["profile"],
                depth=data["depth"],
                stages=stages,
                current_stage=data["current_stage"],
                pending_gate=data["pending_gate"],
                revision=int(data["revision"]),
                updated_at=data["updated_at"],
            )
        except (KeyError, TypeError, AttributeError, ValueError) as exc:
            raise FlowError(f"state.json is corrupt: {exc!r}") from exc
        for rec in state.stages.values():
            if rec.status not in STATUSES:
                raise FlowError(f"state.json is corrupt: bad status {rec.status!r}")
        return state


@dataclass(frozen=True)
class AuditEvent:
    seq: int
    ts: str
    type: str
    stage: str | None
    actor: str
    detail: str
    prev_hash: str

    def validate(self) -> None:
        if self.type not in EVENT_TYPES:
            raise FlowError(f"unknown event type {self.type!r}")
        if not _ACTOR_RE.match(self.actor):
            raise FlowError("actor must look like 'human:<label>' or 'agent:<label>'")
        if len(self.detail) > 500:
            raise FlowError("event detail exceeds 500 characters")

    def to_dict(self) -> dict[str, Any]:
        return {
            "seq": self.seq,
            "ts": self.ts,
            "type": self.type,
            "stage": self.stage,
            "actor": self.actor,
            "detail": self.detail,
            "prev_hash": self.prev_hash,
        }


REVIEWERS: tuple[str, ...] = ("spec", "plan", "code")
VERDICTS: tuple[str, ...] = ("pass", "concerns", "block")
SEVERITIES: tuple[str, ...] = ("info", "warning", "major", "blocker")
RULE_STATUSES: tuple[str, ...] = ("pending", "active", "discarded")
_SHA_RE = re.compile(r"^[a-f0-9]{64}$")
_RULE_ID_RE = re.compile(r"^R-\d{3,}$")
_RULE_ORIGIN_RE = re.compile(r"^(manual|gate:[^:\s]+:[a-z]+|finding:[^:\s]+:[a-z]+-\d+:\d+)$")


@dataclass(frozen=True)
class Finding:
    severity: str
    file: str
    section: str
    note: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity,
            "file": self.file,
            "section": self.section,
            "note": self.note,
        }


@dataclass(frozen=True)
class Review:
    id: str
    stage: str
    reviewer: str
    author: str
    verdict: str
    findings: tuple[Finding, ...]
    files: dict[str, str]
    created_at: str

    def validate(self) -> None:
        if self.reviewer not in REVIEWERS:
            raise FlowError(f"reviewer must be one of {list(REVIEWERS)}")
        if self.stage not in STAGES:
            raise FlowError(f"unknown stage {self.stage!r}")
        if not self.author or not _ACTOR_RE.match(self.author):
            raise FlowError("author must look like 'human:<label>' or 'agent:<label>'")
        if self.author.split(":", 1)[1] == self.reviewer or self.author == self.reviewer:
            raise FlowError("reviewer must differ from the author of the reviewed output")
        if self.verdict not in VERDICTS:
            raise FlowError(f"verdict must be one of {list(VERDICTS)}")
        if not self.files:
            raise FlowError("a review must cover at least one file")
        for path, digest in self.files.items():
            if not _SHA_RE.match(digest):
                raise FlowError(f"bad fingerprint for {path!r}")
        severities = {f.severity for f in self.findings}
        for finding in self.findings:
            if finding.severity not in SEVERITIES:
                raise FlowError(f"unknown severity {finding.severity!r}")
            if finding.file not in self.files:
                raise FlowError(f"finding cites {finding.file!r}, which is not a reviewed file")
            if not finding.section.strip():
                raise FlowError("every finding must cite a section")
            if not finding.note.strip() or len(finding.note) > 500:
                raise FlowError("finding note must be 1-500 characters")
        if "blocker" in severities and self.verdict != "block":
            raise FlowError("a blocker finding forces verdict 'block'")
        if self.verdict == "pass" and severities & {"major", "blocker"}:
            raise FlowError("verdict 'pass' is invalid with major or blocker findings")
        if not self.findings and self.verdict != "pass":
            raise FlowError("findings may be empty only when the verdict is 'pass'")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "stage": self.stage,
            "reviewer": self.reviewer,
            "author": self.author,
            "verdict": self.verdict,
            "created_at": self.created_at,
            "files": dict(self.files),
            "findings": [f.to_dict() for f in self.findings],
        }


@dataclass
class Rule:
    id: str
    text: str
    origin: str
    status: str
    proposed_at: str
    decided_by: str | None = None

    def validate(self) -> None:
        if not _RULE_ID_RE.match(self.id):
            raise FlowError(f"invalid rule id {self.id!r}")
        if not 1 <= len(self.text.strip()) <= 300:
            raise FlowError("rule text must be 1-300 characters")
        if not _RULE_ORIGIN_RE.match(self.origin):
            raise FlowError(f"invalid rule origin {self.origin!r}")
        if self.status not in RULE_STATUSES:
            raise FlowError(f"invalid rule status {self.status!r}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "text": self.text,
            "origin": self.origin,
            "status": self.status,
            "proposed_at": self.proposed_at,
            "decided_by": self.decided_by,
        }


@dataclass(frozen=True)
class KnowledgeDoc:
    path: str
    title: str
    stages: tuple[str, ...]


@dataclass(frozen=True)
class Route:
    profile: Profile
    reasons: dict[str, str]

    def validate(self, feature: str) -> None:
        self.profile.validate()
        if self.profile.id != f"custom-{feature}":
            raise FlowError(f"route id must be 'custom-{feature}'")
        for stage in self.profile.stages:
            if not self.reasons.get(stage, "").strip():
                raise FlowError(f"route needs a reason for stage {stage!r}")
        extra = set(self.reasons) - set(self.profile.stages)
        if extra:
            raise FlowError(f"reasons given for stages not in the route: {sorted(extra)}")

    def to_dict(self) -> dict[str, Any]:
        return {**self.profile.to_dict(), "reasons": dict(self.reasons)}

    @classmethod
    def from_dict(cls, data: Any) -> Route:
        if not isinstance(data, dict):
            raise FlowError("route must be a JSON object")
        body = {k: v for k, v in data.items() if k != "reasons"}
        reasons = data.get("reasons")
        if not isinstance(reasons, dict):
            raise FlowError("route needs a 'reasons' object with one entry per stage")
        return cls(Profile.from_dict(body), {str(k): str(v) for k, v in reasons.items()})
