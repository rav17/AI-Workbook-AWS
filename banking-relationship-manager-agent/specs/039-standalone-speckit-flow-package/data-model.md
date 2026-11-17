# Data Model: Standalone Spec Kit Flow Package

All structures are JSON on the filesystem or in-memory dataclasses; no database.
Serialization conventions: UTF-8 without BOM, LF, one trailing newline, sorted file
entries (see research D3, D11).

## 1. Snapshot identifier

Embedded as the `snapshot` object of the inventory record; names the approved
working-tree capture (which is content-based, not a Git commit).

| Field | Type | Rules |
|---|---|---|
| `label` | string | Required, non-empty human-readable name chosen by the capturing human (e.g. `speckit-flow-portable-2026-11-17-01`). Uniqueness across snapshots is a **human convention documented in the package README** — the tool keeps no registry and does not enforce it. Validated at parse time: printable, no control characters, ≤ 200 chars. Fidelity claims attach to this label only after assembly fully verifies (marker present + inventory match). |
| `captured_at` | string | Required. ISO-8601 timestamp **with UTC offset** (e.g. `2026-11-17T10:04:00+05:30`). |
| `captured_by` | string | Required. Capturing human / invocation reference (`--captured-by`). Validated like `label` (printable, control-free, ≤ 200 chars). The human snapshot approval this references is what authorizes capturing uncommitted working-tree content; the per-file digests below are its audit trail. |
| `source_reference` | object | Required, **reference only** — not a fidelity claim. `{"repository": string, "branch": string, "commit": string}` from read-only `git rev-parse` (or `--source-ref` fallback). The working tree may differ from `commit`; packaged bytes are authoritative via digests. |
| `bundle_version` | string | Required. `bundle_version` read from `scripts/speckit-portable-bundle.json` at capture (`1.1.0` at planning time). |
| `digest_algorithm` | string | Required, declared (not assumed). Fixed `"sha256"` for schema_version 1. |

## 2. Snapshot inventory record — `SNAPSHOT.json` (package root)

Self-describing; verifiable from the package alone with the checkout inaccessible.
Schema: `contracts/snapshot-inventory.schema.json`.

| Field | Type | Rules |
|---|---|---|
| `schema_version` | integer | Required, `1`. Distinct schema from the installer's consumer install manifest (`.specify/speckit-portable-manifest.json`, its own `schema_version: 1`) — different trust roles, never conflated. |
| `snapshot` | object | The snapshot identifier (section 1). |
| `files` | array | Required, non-empty, sorted ascending by `path` (byte order). One entry per delivered file **except** `SNAPSHOT.json` itself and `SNAPSHOT.json.sha256` (self-hash impossibility; see section 3). Duplicate paths rejected; casefolded ancestor/descendant collision check enforces uniqueness on case-insensitive filesystems. |

### 2.1 Inventory file entry

| Field | Type | Rules |
|---|---|---|
| `path` | string | Package-relative POSIX path. Validated by the installer's `_relative_path` rules: non-empty, relative, no `.`/`..` segments, no `\\ : < > " | ? * NUL`, no reserved device names (CON, PRN, AUX, NUL, COM1–9, LPT1–9), no trailing dot/space in any segment. |
| `sha256` | string | Lowercase hex, exactly matching `[a-f0-9]{64}`, computed over raw bytes (binary mode — never text mode). |
| `bytes` | integer | ≥ 0, exact byte length; secondary corruption signal and cheap pre-hash check. |
| `origin` | string | `"source"` (captured allowlist file or packaging entry point — package path equals source-relative path) or `"package-doc"` (package-only documentation/metadata). |
| `source_path` | string | Present only when `origin` is `"package-doc"` and the in-repo authoring path differs from the package path (e.g. `scripts/portable-package/README.md` → `README.md`). Same path validation rules. |

**Honest limitation (recorded in README)**: the inventory cannot contain its own
hash. Its SHA-256 is written to the completion marker and printed by `assemble` for
out-of-band recording alongside the label.

## 3. Completion marker — `SNAPSHOT.json.sha256` (package root)

Single sha256sum-format text line: `<sha256-of-SNAPSHOT.json>  SNAPSHOT.json` + LF.
Written **last**, only after the content screen and full two-directional post-write
verification pass. Machine-generated content only (hex digest + fixed filename, no
free text); it is the only delivered file outside the content-screened set — a stated
residual, acceptable because it embeds no free-text fields (`SNAPSHOT.json`, which
does, is written before the screen and is screened).

**Contract**: the destination *is* the named snapshot **iff** the marker is present
**and** inventory comparison passes. Not listed in the inventory (explicitly
documented package-only metadata per FR-004); verifiable with `sha256sum -c`,
`Get-FileHash`, or `verify_snapshot.py`.

## 4. Assembled package layout

Captured files keep their **source-relative** paths (the package is an installer
*source*; e.g. the roster seed stays at `.specify/templates/portable/roster.json`,
not its installed destination `.specify/agents/roster.json`). This mirroring is
normative and load-bearing for FR-006–FR-009: the packaged `apply_bundle` resolves
manifest source paths relative to its own location exactly as it does in the repo.

```
<destination>/                              attribution (FR-004)
├── README.md                               package-doc (from scripts/portable-package/README.md)
├── verify_snapshot.py                      package-doc (from scripts/portable-package/verify_snapshot.py)
├── SNAPSHOT.json                           package metadata (generated; inventories all others)
├── SNAPSHOT.json.sha256                    package metadata (generated last; excluded from inventory)
├── scripts/
│   ├── speckit_bootstrap.py                packaging entry point
│   ├── speckit-portable-bundle.json        packaging entry point (allowlist, 1.1.0)
│   ├── speckit_guard.py                    allowlist (category scripts)
│   └── speckit_session.py                  allowlist
├── speckit_flow/                           allowlist: 29 enumerated engine modules
├── .github/
│   ├── skills/                             allowlist: 21 enumerated skill files
│   ├── agents/                             allowlist: 17 enumerated agent definitions
│   ├── hooks/                              allowlist: 2 hook manifests
│   └── instructions/speckit-workflow.instructions.md
├── .specify/
│   ├── .gitignore                          allowlist
│   ├── profiles/                           allowlist: 12 profile files (seed)
│   ├── stages/stages.json                  allowlist (seed)
│   ├── plugins/                            allowlist: 34 enumerated plugin files (seed; bytes verbatim — enabled flags unmodified at capture)
│   ├── scripts/powershell/                 allowlist: 6 scripts
│   ├── templates/                          allowlist: 9 templates (seed) + portable/ seed sources (roster, rules, init-options, integration, sensors)
│   ├── workflows/                          allowlist: registry + speckit/workflow.yml
│   ├── integrations/                       allowlist: copilot + speckit manifests
│   └── knowledge/README.md                 allowlist (banking knowledge file NOT included)
└── docs/
    ├── speckit-profiles.md                 allowlist (byte-preserved)
    └── speckit-portability.md              allowlist (byte-preserved)
```

Expected at manifest 1.1.0: 147 allowlist files + 2 entry points + 2 package-docs =
**151 inventoried files** + 2 generated metadata files. Counts are computed at
capture, never hard-coded; a manifest edit re-triggers the boundary check.

**Prohibited (zero occurrences, swept at acceptance)**: `.git` history, sessions and
runtime state, audit/approval records, learned rules content (only the empty portable
seed ships), feature artifacts (`specs/`), source constitution, banking knowledge,
application code (`aria/`, `cdk/`), dependency manifests
(`pyproject.toml`, `requirements*.txt`, `uv.lock`), project tests, env/credential
files, customer data.

## 5. Relationships

```
bundle manifest (scripts/speckit-portable-bundle.json, in package)
  ├─ enumerates ─► 147 allowlist files (source paths → consumer destinations, categories, seed flags)
  └─ is itself ──► packaging entry point + inventory entry

snapshot inventory (SNAPSHOT.json)                  TRUST ROLE: package fidelity
  ├─ supersets the manifest closure: + 2 entry points + 2 package-docs
  ├─ names ─► snapshot identifier (section 1)
  └─ verified by ─► verify_snapshot.py / manual digest commands  (two-directional)

completion marker (SNAPSHOT.json.sha256)
  └─ certifies ─► screen + verification completed; binds inventory bytes

consumer ownership record (.specify/speckit-portable-manifest.json in a TARGET project)
  ├─ TRUST ROLE: consumer install/update ownership — created by the packaged installer
  │  at install time in the consumer project; NOT part of the package; NOT the inventory
  └─ installed digests may legitimately differ from inventory digests for plugin.json
     files (installer writes enabled:false at install time; capture is byte-verbatim)
```

- **Bundle manifest vs inventory**: the manifest is the consumer allowlist and
  mapping; it is *not* the complete packaging inventory (spec Key Entities). The
  inventory is the only complete delivered-file account.
- **Inventory vs ownership record**: package-fidelity evidence vs consumer-ownership
  state; the receiving docs point consumers at the existing ownership
  manifest/update preflight rather than inventing a second consumer mechanism.

## 6. State transitions (assembly run)

```
PREFLIGHT ──refusal (non-empty dest | overlap | bad args)──► REFUSED (exit 2, zero writes)
   │ pass
CAPTURE (in-memory; label assigned, digests computed)
   │ read failure ──► ABORTED (exit 2, zero destination writes)
   │ pass    [--dry-run exits here: planned actions printed, zero writes]
COPY (per-file atomic writes)
   │ write failure ──► PARTIAL (exit 1: per-file ERROR lines, "incomplete, not snapshot <label>",
   │                   nothing deleted, rerun blocked by non-empty refusal, user-directed recovery)
WRITE SNAPSHOT.json (atomic; rendered free-text metadata now on disk, inside the screened set)
SCREEN (detect-secrets: cwd=destination, --all-files, explicit file list = inventory + SNAPSHOT.json;
        coverage assertion: submitted paths >= inventory count + 1)
   │ findings / scanner unavailable / coverage shortfall ──► PARTIAL-UNSCREENED (exit 1, label withheld)
VERIFY (two-directional vs inventory)
   │ any mismatch ──► DRIFT (exit 1: per-file DRIFT lines, label withheld)
   │ pass
WRITE MARKER (last) ──► NAMED SNAPSHOT (exit 0; inventory digest printed for out-of-band record)
```

A crash at any point before the marker leaves no marker: the destination is never
presentable as the named snapshot, and incompleteness is confirmable by comparison
against the inventory (or capture output if `SNAPSHOT.json` was never written).
