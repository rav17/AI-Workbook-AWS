from __future__ import annotations

import hashlib
import json
import math
import multiprocessing
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from multiprocessing.connection import Connection
from pathlib import Path
from typing import Any, Protocol

from speckit_flow import audit, calls, state, units
from speckit_flow.models import FlowError
from speckit_flow.profiles import DEFAULT_PROFILES_DIR


@dataclass(frozen=True)
class WorkerObservation:
    """A host adapter's correlated observation, not an ownership-transfer capability."""

    call_id: int
    outcome: str

    def validate(self) -> None:
        if type(self.call_id) is not int or self.call_id < 1:
            raise FlowError("host observation needs a positive recorded call ID")
        if self.outcome not in ("running", "delayed", "unavailable", "unknown"):
            raise FlowError("host observation has an invalid outcome")


@dataclass(frozen=True)
class HostObservation:
    call_id: int
    outcome: str
    worker_id: str = ""
    identity_verified: bool = False
    exclusion_verified: bool = False

    def validate(self) -> None:
        WorkerObservation(self.call_id, self.outcome).validate()
        if (
            type(self.identity_verified) is not bool
            or type(self.exclusion_verified) is not bool
            or not isinstance(self.worker_id, str)
            or (self.worker_id and not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", self.worker_id))
            or (self.identity_verified and not self.worker_id)
            or (self.exclusion_verified and not self.identity_verified)
        ):
            raise FlowError("host identity/exclusion observation is invalid")


class RecoveryAdapter(Protocol):
    """Trusted integration code, never a user-supplied proof or executable command."""

    name: str

    def observe(self, feature_dir: Path, call_id: int) -> HostObservation: ...


def _snapshot_fingerprint(feature_dir: Path, profiles_dir: Path) -> dict[str, Any]:
    root = feature_dir.parent.parent
    try:
        current = state.load_state(feature_dir)
        profile = state.profile_for(feature_dir, current.profile, profiles_dir)
        definitions = units.load_units(feature_dir)
        sources = {
            (feature_dir / name).relative_to(root).as_posix()
            for name in (
                state.STATE_FILE,
                audit.AUDIT_FILE,
                units.UNITS_FILE,
                state.HYBRID_ROUTE_FILE,
                state.SELECTIVE_ROUTE_FILE,
            )
        }
        sources.add(".specify/verify.json")
        sources.update(name for unit in definitions for name in unit.get("files", []))
        fingerprints: dict[str, str | None] = {}
        for label in sorted(sources):
            try:
                (root / label).lstat()
            except FileNotFoundError:
                fingerprints[label] = None
                continue
            fingerprints[label] = units.tracked_fingerprints(root, [label])[label]
        payload = {"inputs": fingerprints, "profile": profile.to_dict()}
        digest = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return {"status": "available", "fingerprint": digest}
    except (FlowError, OSError):
        return {
            "status": "unavailable",
            "fingerprint": None,
            "reason": (
                "Input/route fingerprint unavailable; inspect declared inputs and file limits."
            ),
        }


def status(
    feature_dir: Path,
    *,
    profiles_dir: Path = DEFAULT_PROFILES_DIR,
    observation: WorkerObservation | None = None,
    adapter: RecoveryAdapter | None = None,
    include_evidence: bool = False,
    _progress: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """One local observation, without waiting on models, probes or worker cancellation."""
    before = _snapshot_fingerprint(feature_dir, profiles_dir) if include_evidence else None
    current = state.load_state(feature_dir)
    snapshot = audit.snapshot(feature_dir)
    if snapshot.problem or not snapshot.event_count:
        raise FlowError(f"invalid recovery audit: {snapshot.problem or 'missing or empty trail'}")
    state.profile_for(feature_dir, current.profile, profiles_dir)
    stage = current.current_stage
    recorded = calls.status(feature_dir, stage) if stage else []
    running = [call for call in recorded if call["status"] == "running"]
    if _progress is not None:
        _progress({"stage": stage, "recorded_calls": recorded})
    identity: HostObservation | None = None
    if adapter is not None:
        if observation is not None:
            raise FlowError("choose one host adapter or correlated observation, not both")
        if not isinstance(adapter.name, str) or not re.fullmatch(
            r"[a-z][a-z0-9-]{0,63}", adapter.name
        ):
            raise FlowError("recovery adapter needs a bounded name")
        if len(running) != 1:
            raise FlowError("host adapter requires one unambiguous current running reservation")
        identity = adapter.observe(feature_dir, running[0]["id"])
        if not isinstance(identity, HostObservation):
            raise FlowError("host adapter must return a typed identity observation")
        identity.validate()
        if identity.call_id != running[0]["id"]:
            raise FlowError("host adapter identity does not match the running reservation")
        observation = WorkerObservation(
            identity.call_id,
            identity.outcome if identity.identity_verified else "unknown",
        )
    checkpoint_report = units.list_units(feature_dir, include_evidence=include_evidence)
    verified = [
        unit["id"]
        for unit in checkpoint_report["units"]
        if unit["checkpointed"] and unit["coverage"] == "tracked-files"
    ]
    uncertain = [
        unit["id"]
        for unit in checkpoint_report["units"]
        if unit["status"] == "stale"
        or (unit["checkpoint_present"] and unit["coverage"] == "command-only")
    ]
    failed = [call for call in recorded if call["status"] == "failed"]
    lock_present = (feature_dir / calls.LOCK_FILE).exists()
    if observation is not None:
        observation.validate()
        if observation.call_id not in {call["id"] for call in running}:
            raise FlowError("host observation does not match a current running reservation")
    if running or lock_present:
        outcome = observation.outcome if observation is not None else "unavailable"
        reason = (
            "Recorded execution or an accounting lock remains; no host adapter establishes "
            "worker identity, liveness or safe exclusion."
            if observation is None
            else "A correlated host observation is available; it does not authorize transfer."
        )
        step = "Inspect actual host execution. Do not delete locks, steal ownership or redispatch."
    elif uncertain:
        outcome, reason = (
            "unknown",
            "Checkpoint evidence is stale or lacks tracked-source coverage.",
        )
        step = "Revalidate affected units under approved commands; do not reuse uncertain progress."
    elif failed:
        outcome, reason = (
            "unknown",
            "A recorded worker failed; failure is not proof of safe exclusion.",
        )
        step = "Inspect execution and side effects; a human must decide if a fresh attempt is safe."
    elif current.pending_gate or snapshot.parked:
        outcome, reason = "delayed", "A human gate or parked feature prevents continuation."
        step = "Present current evidence and wait for the required human decision."
    elif stage and current.stages[stage].status == "in_progress":
        outcome, reason = "unknown", "Inline or unrecorded execution may still own this stage."
        step = (
            "Confirm host execution has stopped before resuming; saved files alone are not proof."
        )
    else:
        outcome, reason = (
            "delayed",
            "No recorded worker is running; continuation uses normal preflight.",
        )
        step = "Run workflow next; use verified units only within their declared coverage."
    result = {
        "status": outcome,
        "stage": stage,
        "recorded_calls": recorded,
        "verified_units": verified,
        "uncertain_units": uncertain,
        "ready_units": checkpoint_report["ready"],
        "reason": reason,
        "next_action": step,
        "ownership_transfer_allowed": False,
        "resume_allowed": (
            not running
            and not failed
            and not uncertain
            and not lock_present
            and not current.pending_gate
            and not snapshot.parked
            and stage is not None
            and current.stages[stage].status == "pending"
        ),
        "host_evidence": "adapter_observation" if observation is not None else "not_configured",
        "host_adapter": adapter.name if adapter is not None else "not_configured",
        "worker_identity": (
            identity.worker_id if identity and identity.identity_verified else "not_verified"
        ),
        "exclusion": (
            "adapter_reported" if identity and identity.exclusion_verified else "not_verified"
        ),
        "notice": (
            "Actor labels and call statuses are attribution, not authenticated ownership. "
            "This query never cancels workers, transfers ownership or replays side effects. "
            "Direct adapter/filesystem inspection has no wall-clock guarantee; use the watchdog. "
            "Running needs a host observation."
        ),
    }
    if include_evidence:
        after = _snapshot_fingerprint(feature_dir, profiles_dir)
        assert before is not None
        available = before["status"] == after["status"] == "available"
        stable = available and before["fingerprint"] == after["fingerprint"]
        result["evidence_snapshot"] = {
            "status": (
                "stable_at_read_boundaries"
                if stable
                else "changed_during_inspection"
                if available
                else "unavailable"
            ),
            "fingerprint": after["fingerprint"] if stable else None,
            "audit_revision": snapshot.event_count,
            "reason": (
                "Beginning/end fingerprints match; this is not an atomic snapshot or grant."
                if stable
                else "Inputs changed or could not be fingerprinted; evidence is unbound."
            ),
        }
        entries = [
            {
                "id": unit["id"],
                "coverage": unit["coverage"],
                "checkpoint_present": unit["checkpoint_present"],
                "depends_on": list(unit["depends_on"]),
                **unit["checkpoint_evidence"],
            }
            for unit in checkpoint_report["units"]
        ]
        result["checkpoint_inventory"] = {
            "status": "observed" if stable else "not_verified",
            "total": len(entries),
            "counts": {
                disposition: sum(entry["status"] == disposition for entry in entries)
                for disposition in (
                    "current",
                    "stale",
                    "missing",
                    "blocked",
                    "command_only",
                    "unverified",
                )
            },
            "units": entries,
            "dependency_order": checkpoint_report["dependency_order"],
        }
    return result


def revalidation_plan(
    inventory: dict[str, Any],
    snapshot: dict[str, Any],
) -> dict[str, Any]:
    """Order review actions from engine evidence; never return an executable queue."""
    blockers = [
        {
            "code": "host_execution_not_authorized",
            "action": "Establish actual host execution/ownership safety before any new work.",
        },
        {
            "code": "external_side_effects_not_verified",
            "action": "Inspect prior side-effect outcomes; never assume automatic replay is safe.",
        },
        {
            "code": "normal_preflight_required",
            "action": "Re-enter normal route preflight and human gates before execution.",
        },
    ]
    bound = (
        inventory["status"] == "observed"
        and snapshot["status"] == "stable_at_read_boundaries"
        and snapshot["comparison"] not in ("changed", "not_verified")
    )
    if not bound:
        return {
            "status": "blocked",
            "executable": False,
            "steps": [],
            "preserve_units": [],
            "blockers": [
                {
                    "code": "fresh_bound_snapshot_required",
                    "action": "Review a fresh bound snapshot; no step order is trustworthy.",
                },
                *blockers,
            ],
        }
    by_id = {entry["id"]: entry for entry in inventory["units"]}
    order = inventory["dependency_order"]
    actions = {
        "verification_policy_not_approved": (
            "review_verification_policy",
            "Have an authorized human review the receiving-project verification policy.",
        ),
        "tracked_inputs_unavailable": (
            "restore_declared_input_access",
            "Resolve declared-input access or file constraints without substituting evidence.",
        ),
        "tracked_inputs_changed": (
            "review_changed_inputs",
            "Review changed declared files and their affected completion claims.",
        ),
        "unit_definition_changed": (
            "review_unit_definition",
            "Review changed unit scope, tasks, instructions or declared dependencies.",
        ),
        "verification_command_changed": (
            "review_verification_change",
            "Review the changed approved command; old verification does not apply.",
        ),
        "checkpoint_metadata_incomplete": (
            "review_incomplete_checkpoint",
            "Treat incomplete checkpoint metadata as unverified; do not repair it as a pass.",
        ),
        "dependency_evidence_changed": (
            "review_dependency_evidence",
            "Review changed dependency evidence before dependent completion claims.",
        ),
        "verification_record_unverified": (
            "review_verification_record",
            "Resolve the checkpoint/audit mismatch without inventing or rewriting a result.",
        ),
        "verification_recorded_failure": (
            "review_failed_verification",
            "Inspect the recorded verification failure; this plan does not retry it.",
        ),
        "checkpoint_missing": (
            "review_missing_checkpoint",
            "Identify missing completion evidence; saved files are not a passing checkpoint.",
        ),
    }
    steps = []
    for uid in order:
        unit = by_id[uid]
        if unit["status"] == "current":
            continue
        selected = [
            {"code": actions[reason][0], "action": actions[reason][1]}
            for reason in unit["reason_codes"]
            if reason in actions
        ]
        if unit["coverage"] == "command-only":
            selected.append(
                {
                    "code": "review_source_coverage",
                    "action": (
                        "Resolve command-only coverage; tracked-source completion is unverified."
                    ),
                }
            )
        selected.append(
            {
                "code": "review_completion_and_revalidation",
                "action": (
                    "Review completion criteria and propose separately authorized verification "
                    "after prerequisites; no command runs or checkpoint changes here."
                ),
            }
        )
        steps.append(
            {
                "unit": uid,
                "status": unit["status"],
                "depends_on": unit["depends_on"],
                "prerequisite_units": [
                    dep for dep in unit["depends_on"] if by_id[dep]["status"] != "current"
                ],
                "reason_codes": unit["reason_codes"],
                "changed_files": unit["changed_files"],
                "actions": selected,
            }
        )
    return {
        "status": "advisory",
        "executable": False,
        "steps": steps,
        "preserve_units": [uid for uid in order if by_id[uid]["status"] == "current"],
        "blockers": blockers,
    }


def decision_package(
    report: dict[str, Any],
    expected_fingerprint: str | None = None,
) -> dict[str, Any]:
    """Project an engine inspection into review evidence, never a recovery grant."""
    timed_out = report.get("timed_out", False)
    if expected_fingerprint is not None and (
        not isinstance(expected_fingerprint, str)
        or not re.fullmatch(r"[a-f0-9]{64}", expected_fingerprint)
    ):
        raise FlowError("expected fingerprint must be a lowercase SHA-256 digest")
    inventory = report.get(
        "checkpoint_inventory", {"status": "not_observed", "total": None, "counts": {}, "units": []}
    )
    snapshot = {
        **report.get("evidence_snapshot", {"status": "not_observed", "fingerprint": None}),
        "comparison": "not_requested"
        if expected_fingerprint is None
        else (
            "not_verified"
            if inventory["status"] != "observed"
            else "unchanged"
            if report["evidence_snapshot"]["fingerprint"] == expected_fingerprint
            else "changed"
        ),
    }
    current_units = list(report["verified_units"])
    uncertain_units = list(report["uncertain_units"])
    if "checkpoint_inventory" in report:
        current_units = [
            unit["id"]
            for unit in inventory["units"]
            if inventory["status"] == "observed" and unit["status"] == "current"
        ]
        uncertain_units = [
            unit["id"]
            for unit in inventory["units"]
            if inventory["status"] != "observed" or unit["status"] != "current"
        ]
    return {
        "decision": {
            "requested": "Review recovery readiness and identify missing authorization/evidence.",
            "status": "review_only",
            "recorded": False,
            "continuation_authorized": False,
            "ownership_transfer_authorized": False,
        },
        "scope": {
            "stage": report["stage"],
            "recorded_call_ids": [call["id"] for call in report["recorded_calls"]],
            "tracked_current_units": current_units,
            "uncertain_units": uncertain_units,
        },
        "checkpoint_inventory": inventory,
        "evidence_snapshot": snapshot,
        "revalidation_plan": revalidation_plan(inventory, snapshot),
        "evidence": {
            "inspection": "timed_out" if timed_out else "complete",
            "worker_status": report["status"],
            "audit_integrity": "not_verified" if timed_out else "checked",
            "host_evidence": report["host_evidence"],
            "worker_identity": (
                "adapter_reported"
                if report["worker_identity"] != "not_verified"
                else "not_verified"
            ),
            "exclusion": report["exclusion"],
            "checkpoint_coverage": (
                "not_observed" if timed_out else "declared_input_freshness_only"
            ),
        },
        "verification": {
            "checks_run_now": False,
            "independent_review": "not_performed",
            "semantic_completion": "not_verified",
            "resume_boundary": "not_selected",
            "external_side_effects": "not_verified",
            "keyboard_screen_reader": "not_verified",
        },
        "provenance": {
            "source": "engine recovery inspection",
            "snapshot": "non_atomic; rerun normal preflight before any action",
            "human_authorization": "not_recorded",
            "authentication": "not_established; actor labels are attribution only",
        },
        "unresolved_risks": [
            report["reason"],
            (f"Evidence snapshot: {snapshot['status']}; comparison {snapshot['comparison']}."),
            "No enforceable ownership fence or continuation/transfer operation is installed.",
            "Checkpoint freshness does not substantiate every completion criterion.",
            "Prior external side-effect outcomes are unknown; do not replay automatically.",
            "Actual host recovery and keyboard/screen-reader acceptance are not verified.",
        ],
        "allows": ["Review this evidence and prepare a separately authorized recovery plan."],
        "excludes": [
            "Starting, cancelling or replacing workers; ownership transfer or lock removal.",
            "Approving gates, resetting budgets or replaying external side effects.",
            "Deployment, customer-record changes, money movement or plugin activation.",
        ],
        "next_action": report["next_action"],
        "notice": (
            "This package contains inspection metadata, not raw evidence payloads or a decision "
            "record. Reviewing or approving it never enables continuation or ownership transfer. "
            "Tracked-current units are advisory freshness evidence, not a global resume boundary."
        ),
    }


def decision_package_text(package: dict[str, Any]) -> str:
    scope, evidence, verification = (
        package["scope"],
        package["evidence"],
        package["verification"],
    )
    inventory, snapshot = package["checkpoint_inventory"], package["evidence_snapshot"]
    inventory_lines = [
        f"Checkpoint inventory: {inventory['status']}; total {inventory['total']}",
        f"Evidence snapshot: {snapshot['status']}; fingerprint "
        f"{snapshot['fingerprint'] or 'not_verified'}; comparison {snapshot['comparison']}",
    ]
    for unit in inventory["units"]:
        inventory_lines.append(
            f"- Unit {unit['id']}: {unit['status']}; coverage {unit['coverage']}; "
            f"freshness {unit['freshness']}; "
            f"recorded verification {unit['recorded_verification']}; "
            f"checkpoint record matches {unit['checkpoint_record_matches']}; "
            f"checkpoint revision {unit['checkpoint_revision']}; "
            f"verification revision {unit['verification_revision']}; "
            "semantic completion not_verified"
        )
        inventory_lines.append(
            "  Invalidation reasons: "
            + (", ".join(unit["reason_codes"]) or "none recorded")
            + "; changed declared files: "
            + (", ".join(unit["changed_files"]) or "none observed")
        )
    plan = package["revalidation_plan"]
    plan_lines = [
        f"Revalidation plan: {plan['status']}; executable False",
        "Preserve current units: " + (", ".join(plan["preserve_units"]) or "none observed"),
        "Execution blockers:",
        *[f"- {item['code']}: {item['action']}" for item in plan["blockers"]],
    ]
    for index, step in enumerate(plan["steps"], start=1):
        plan_lines.append(
            f"{index}. Review unit {step['unit']} ({step['status']}); "
            "prerequisite units: " + (", ".join(step["prerequisite_units"]) or "none affected")
        )
        plan_lines.extend(f"   - {item['code']}: {item['action']}" for item in step["actions"])
    return "\n".join(
        [
            "Recovery review package (review only; no decision recorded)",
            f"Decision: {package['decision']['requested']}",
            f"Scope: stage {scope['stage'] or 'none'}; recorded call IDs "
            + (", ".join(str(value) for value in scope["recorded_call_ids"]) or "none"),
            "Tracked-current units (freshness only): "
            + (", ".join(scope["tracked_current_units"]) or "none observed"),
            "Uncertain units: " + (", ".join(scope["uncertain_units"]) or "none observed"),
            *inventory_lines,
            *plan_lines,
            f"Evidence: inspection {evidence['inspection']}; worker {evidence['worker_status']}; "
            f"audit {evidence['audit_integrity']}; coverage {evidence['checkpoint_coverage']}",
            f"Host evidence: {evidence['host_evidence']}; identity {evidence['worker_identity']}; "
            f"exclusion {evidence['exclusion']}",
            "Verification: no checks or independent review run now; semantic completion "
            f"{verification['semantic_completion']}; "
            f"resume boundary {verification['resume_boundary']}",
            f"External side effects: {verification['external_side_effects']}; "
            f"keyboard/screen-reader acceptance: {verification['keyboard_screen_reader']}",
            "Authorization provenance: " + "; ".join(package["provenance"].values()),
            "Unresolved risks:\n- " + "\n- ".join(package["unresolved_risks"]),
            "Allows:\n- " + "\n- ".join(package["allows"]),
            "Excludes:\n- " + "\n- ".join(package["excludes"]),
            f"Next action: {package['next_action']}",
            package["notice"],
        ]
    )


def _status_worker(
    feature_dir: Path,
    profiles_dir: Path,
    adapter: RecoveryAdapter | None,
    include_evidence: bool,
    output: Connection,
) -> None:
    try:
        result = status(
            feature_dir,
            profiles_dir=profiles_dir,
            adapter=adapter,
            include_evidence=include_evidence,
            _progress=lambda progress: output.send({"progress": progress}),
        )
        output.send({"result": result})
    except (FlowError, OSError) as exc:
        output.send({"error": str(exc)})
    finally:
        output.close()


def bounded_status(
    feature_dir: Path,
    timeout_seconds: float,
    *,
    profiles_dir: Path = DEFAULT_PROFILES_DIR,
    adapter: RecoveryAdapter | None = None,
    include_evidence: bool = False,
) -> dict[str, Any]:
    """Bound inspection in an owned process; never cancel the actual task worker."""
    if (
        isinstance(timeout_seconds, bool)
        or not math.isfinite(timeout_seconds)
        or not 0.05 <= timeout_seconds <= 60
    ):
        raise FlowError("recovery timeout must be 0.05-60 finite seconds")
    context = multiprocessing.get_context("spawn")
    reader, writer = context.Pipe(duplex=False)
    process = context.Process(
        target=_status_worker,
        args=(feature_dir, profiles_dir, adapter, include_evidence, writer),
        daemon=True,
    )
    latest: dict[str, Any] = {"stage": None, "recorded_calls": []}
    deadline = time.monotonic() + timeout_seconds
    try:
        process.start()
        writer.close()
        while reader.poll(max(0.0, deadline - time.monotonic())):
            if time.monotonic() >= deadline:
                break
            try:
                message = reader.recv()
            except EOFError as exc:
                raise FlowError("recovery inspection exited without a complete report") from exc
            if "error" in message:
                raise FlowError(message["error"])
            if "result" in message:
                return {**message["result"], "timed_out": False}
            latest = message["progress"]
            if time.monotonic() >= deadline:
                break
        result = {
            **latest,
            "status": "unknown",
            "timed_out": True,
            "verified_units": [],
            "uncertain_units": [],
            "ready_units": [],
            "progress_evidence": "not_observed",
            "reason": f"Recovery inspection exceeded {timeout_seconds:g} seconds.",
            "next_action": (
                "Inspect host execution under human direction; do not take over or replay."
            ),
            "resume_allowed": False,
            "ownership_transfer_allowed": False,
            "host_evidence": "not_verified",
            "host_adapter": "not_verified",
            "worker_identity": "not_verified",
            "exclusion": "not_verified",
            "notice": (
                "Only the owned inspection process is stopped, never the task worker. "
                "Empty evidence lists mean not observed, not no progress. "
                "Timeout is not proof of worker death or safe exclusion. "
                "OS scheduling/process cleanup can add latency; this is not a real-time guarantee."
            ),
        }
        if include_evidence:
            result["checkpoint_inventory"] = {
                "status": "not_observed",
                "total": None,
                "counts": {},
                "units": [],
            }
            result["evidence_snapshot"] = {
                "status": "not_observed",
                "fingerprint": None,
                "reason": "Inspection timed out; no bound evidence snapshot is available.",
            }
        return result
    except OSError as exc:
        raise FlowError(f"recovery inspection process failed: {type(exc).__name__}") from exc
    finally:
        reader.close()
        writer.close()
        if process.pid is not None:
            if process.is_alive():
                process.terminate()
            process.join(timeout=0.2)
            if process.is_alive():
                process.kill()
                process.join(timeout=0.2)
