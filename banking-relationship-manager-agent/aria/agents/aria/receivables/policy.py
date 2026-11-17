from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from aria.agents.aria.receivables.models import (
    EvidenceType,
    PolicyRecord,
    SnapshotEntry,
    SnapshotManifest,
    SourceRecord,
    deep_freeze,
)

FEATURE_RELATIVE = Path("specs/004-receivables-exception-resolution")
POLICY_PROJECTION = (
    "policy_id",
    "version",
    "tenant_id",
    "currency",
    "exception_types",
    "effective_from",
    "effective_to",
    "tolerance_abs",
    "tolerance_pct",
    "weights",
    "bands",
    "competing_margin",
    "duplicate_window_days",
    "proposal_ttl_minutes",
    "confirmation_window_minutes",
)
POLICY_METADATA = {
    "approval_status_current",
    "approval_status_after_human_approval",
    "approval_record_ref",
}
POLICY_SOURCE_METADATA = POLICY_METADATA | {"declared_policy_digest"}


class PolicyApprovalError(ValueError):
    """The synthetic approval provenance or linked artifact bindings failed closed."""


def canonical_json_bytes(value: Any) -> bytes:
    def reject(item: Any) -> None:
        if isinstance(item, float):
            raise ValueError("canonical data cannot contain binary floating-point values")
        if isinstance(item, dict):
            for child in item.values():
                reject(child)
        elif isinstance(item, (list, tuple)):
            for child in item:
                reject(child)

    reject(value)
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def _domain_hash(domain: str, payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(domain.encode("ascii") + b"\0" + payload).hexdigest()


def canonical_record_digest(record: SourceRecord) -> str:
    if record.source_type == EvidenceType.POLICY:
        raw = dict(record.values)
        missing = set(POLICY_PROJECTION) - raw.keys()
        unexpected = raw.keys() - set(POLICY_PROJECTION) - POLICY_SOURCE_METADATA
        if missing or unexpected:
            raise ValueError(
                "policy record keys are invalid "
                f"(missing={sorted(missing)}, unexpected={sorted(unexpected)})"
            )
        projection = {key: raw[key] for key in POLICY_PROJECTION}
        return _domain_hash(
            "receivables-exception-resolution/policy-record/v1", canonical_json_bytes(projection)
        )
    envelope = {
        "source_type": record.source_type.value,
        "source_record_id": record.source_record_id,
        "source_version": record.source_version,
        **dict(record.values),
    }
    return _domain_hash(
        "receivables-exception-resolution/source-record/v1", canonical_json_bytes(envelope)
    )


def build_snapshot_manifest(
    records: tuple[SourceRecord, ...] | list[SourceRecord],
) -> SnapshotManifest:
    entries: list[SnapshotEntry] = []
    seen: set[tuple[str, str, str]] = set()
    for record in records:
        key = (record.source_type.value, record.source_record_id, record.source_version)
        if key in seen:
            raise ValueError("duplicate source record in snapshot manifest")
        seen.add(key)
        entries.append(
            SnapshotEntry(
                source_type=record.source_type,
                source_record_id=record.source_record_id,
                source_version=record.source_version,
                record_digest=canonical_record_digest(record),
            )
        )
    entries.sort(
        key=lambda entry: (entry.source_type.value, entry.source_record_id, entry.source_version)
    )
    body = [entry.model_dump(mode="json") for entry in entries]
    canonical = canonical_json_bytes(body)
    snapshot_id = (
        "snap-"
        + hashlib.sha256(
            b"receivables-exception-resolution/snapshot-id/v1\0" + canonical
        ).hexdigest()
    )
    snapshot_version = (
        "v1-"
        + hashlib.sha256(
            b"receivables-exception-resolution/snapshot-version/v1\0" + canonical
        ).hexdigest()
    )
    aggregate = _domain_hash("receivables-exception-resolution/snapshot-manifest/v1", canonical)
    return SnapshotManifest(
        entries=tuple(entries),
        snapshot_id=snapshot_id,
        snapshot_version=snapshot_version,
        aggregate_digest=aggregate,
    )


@dataclass(frozen=True)
class ApprovedCatalogue:
    root: Path
    fixture: dict[str, Any]
    policy: PolicyRecord
    policy_source: SourceRecord
    fixture_sha256: str
    manifest: SnapshotManifest
    approval_ref: str


def _approval_bindings(root: Path) -> dict[str, str]:
    path = root / FEATURE_RELATIVE / "approval-provenance.md"
    content = path.read_text(encoding="utf-8")
    found = dict(re.findall(r"\|\s*`([^`]+)`\s*\|\s*`([0-9a-f]{64})`\s*\|", content))
    required = {"plan.md", "synthetic-policy.md", "synthetic-fixtures.json", "quickstart.md"}
    if not required.issubset(found):
        raise PolicyApprovalError("approval provenance is missing a linked artifact binding")
    return found


def load_approved_catalogue(root: Path | None = None) -> ApprovedCatalogue:
    resolved_root = (root or Path(__file__).resolve().parents[4]).resolve()
    feature = resolved_root / FEATURE_RELATIVE
    audit_path = feature / "audit.jsonl"
    if not audit_path.is_file():
        raise PolicyApprovalError("approval audit record is unavailable")
    approved = False
    approval_ref = ""
    for line in audit_path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise PolicyApprovalError("approval audit contains invalid JSON") from exc
        if (
            row.get("seq") == 38
            and row.get("type") == "gate_approved"
            and row.get("stage") == "plan"
            and row.get("actor") == "human:human"
        ):
            approved = True
            approval_ref = "audit:seq:38:gate_approved:plan"
    if not approved:
        raise PolicyApprovalError("separate human plan gate approval is absent")
    bindings = _approval_bindings(resolved_root)
    artifact_hashes: dict[str, str] = {}
    for name in ("plan.md", "synthetic-policy.md", "synthetic-fixtures.json", "quickstart.md"):
        content = (feature / name).read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        if digest != bindings[name]:
            raise PolicyApprovalError(f"approved artifact binding mismatch: {name}")
        artifact_hashes[name] = digest
    fixture_bytes = (feature / "synthetic-fixtures.json").read_bytes()
    fixture_hash = artifact_hashes["synthetic-fixtures.json"]
    fixture = json.loads(fixture_bytes)
    raw_policy = fixture["policy"]
    if set(raw_policy) != set(POLICY_PROJECTION) | POLICY_METADATA:
        raise PolicyApprovalError("approved policy record has missing or unexpected fields")
    projected = {key: raw_policy[key] for key in POLICY_PROJECTION}
    record = SourceRecord(
        source_type=EvidenceType.POLICY,
        source_record_id=raw_policy["policy_id"],
        source_version=str(raw_policy["version"]),
        values=projected,
    )
    policy = PolicyRecord(
        policy_id=raw_policy["policy_id"],
        version=raw_policy["version"],
        tenant_id=raw_policy["tenant_id"],
        currency=raw_policy["currency"],
        exception_types=tuple(raw_policy["exception_types"]),
        effective_from=date.fromisoformat(raw_policy["effective_from"]),
        effective_to=date.fromisoformat(raw_policy["effective_to"]),
        approval_status="approved_synthetic_test_only",
        approval_record_ref=approval_ref,
        tolerance_abs=raw_policy["tolerance_abs"],
        tolerance_pct=raw_policy["tolerance_pct"],
        weights=raw_policy["weights"],
        bands=raw_policy["bands"],
        competing_margin=raw_policy["competing_margin"],
        duplicate_window_days=raw_policy["duplicate_window_days"],
        proposal_ttl_minutes=raw_policy["proposal_ttl_minutes"],
        confirmation_window_minutes=raw_policy["confirmation_window_minutes"],
        freshness_max_age_seconds=fixture["freshness_max_age_seconds"],
    )
    records: list[SourceRecord] = [record]
    for source_type, rows, key_name in (
        (EvidenceType.VIRTUAL_ACCOUNT, fixture["virtual_accounts"], "va_id"),
        (EvidenceType.INVOICE, fixture["invoices"], "invoice_id"),
        (EvidenceType.CUSTOMER, [fixture["customer"]], "customer_id"),
    ):
        for row in rows:
            records.append(
                SourceRecord(
                    source_type=source_type,
                    source_record_id=row[key_name],
                    source_version=f"fixture-v1@sha256:{fixture_hash}",
                    values=row,
                )
            )
    manifest = build_snapshot_manifest(records)
    return ApprovedCatalogue(
        root=resolved_root,
        fixture=deep_freeze(fixture),
        policy=policy,
        policy_source=record,
        fixture_sha256=fixture_hash,
        manifest=manifest,
        approval_ref=approval_ref,
    )


def verify_citation(
    citation: Any,
    records: list[SourceRecord] | tuple[SourceRecord, ...],
    manifest: SnapshotManifest,
) -> bool:
    """Resolve one citation uniquely and independently recompute record and aggregate digests."""
    verify_snapshot_manifest(manifest)
    rebuilt = build_snapshot_manifest(list(records))
    if (
        rebuilt.snapshot_id != manifest.snapshot_id
        or rebuilt.snapshot_version != manifest.snapshot_version
        or rebuilt.aggregate_digest != manifest.aggregate_digest
    ):
        raise ValueError("snapshot manifest does not match resolved records")
    matches = [
        record
        for record in records
        if record.source_type == citation.source_type
        and record.source_record_id == citation.source_record_id
        and record.source_version
        == citation.snapshot_version.replace("v1-", "fixture-v1@sha256:", 1)
    ]
    if len(matches) != 1:
        # Snapshot version is aggregate; record version is separate catalogue metadata.
        matches = [
            record
            for record in records
            if record.source_type == citation.source_type
            and record.source_record_id == citation.source_record_id
        ]
    if len(matches) != 1:
        raise ValueError("citation does not resolve uniquely")
    digest = canonical_record_digest(matches[0])
    entry = [
        item
        for item in manifest.entries
        if item.source_type == citation.source_type
        and item.source_record_id == citation.source_record_id
        and item.source_version == matches[0].source_version
    ]
    if len(entry) != 1 or digest != citation.record_digest or digest != entry[0].record_digest:
        raise ValueError("citation record digest mismatch")
    if (
        citation.snapshot_id != manifest.snapshot_id
        or citation.snapshot_version != manifest.snapshot_version
    ):
        raise ValueError("citation snapshot binding mismatch")
    return True


def verify_snapshot_manifest(manifest: SnapshotManifest) -> bool:
    body = [entry.model_dump(mode="json") for entry in manifest.entries]
    canonical = canonical_json_bytes(body)
    expected_id = (
        "snap-"
        + hashlib.sha256(
            b"receivables-exception-resolution/snapshot-id/v1\0" + canonical
        ).hexdigest()
    )
    expected_version = (
        "v1-"
        + hashlib.sha256(
            b"receivables-exception-resolution/snapshot-version/v1\0" + canonical
        ).hexdigest()
    )
    expected_digest = _domain_hash(
        "receivables-exception-resolution/snapshot-manifest/v1", canonical
    )
    if (
        expected_id != manifest.snapshot_id
        or expected_version != manifest.snapshot_version
        or expected_digest != manifest.aggregate_digest
    ):
        raise ValueError("snapshot manifest digest mismatch")
    return True
