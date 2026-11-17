# Implementation Plan: Standalone Spec Kit Flow Package

**Branch**: `039-standalone-speckit-flow-package` | **Date**: 2026-11-17 | **Spec**: `specs/039-standalone-speckit-flow-package/spec.md`

**Input**: Feature specification from `specs/039-standalone-speckit-flow-package/spec.md` (specify gate human-approved)

## Summary

Assemble a standalone, commit-ready workflow-source folder at
`C:\Users\RavindraYadav\Documents\speckit-flow-portable` containing a byte-verbatim,
digest-inventoried snapshot of the portable Spec Kit tooling: the installer
(`scripts/speckit_bootstrap.py`), the bundle manifest
(`scripts/speckit-portable-bundle.json`, `bundle_version` `1.1.0`), every file that
manifest explicitly selects, and a small, explicitly inventoried set of package-only
documentation/metadata (root `README.md`, stdlib verifier `verify_snapshot.py`,
snapshot inventory `SNAPSHOT.json`, completion marker `SNAPSHOT.json.sha256`).

The technical approach is a new maintainer-side, stdlib-only CLI
`scripts/speckit_package.py` that reuses the proven primitives already in
`scripts/speckit_bootstrap.py` (`_sha256`, `_relative_path`, `_resolve_within`,
`_atomic_write`, manifest parsing/overlap-rejection conventions from
`_collect_bundle`/`apply_bundle`/`_manifest_bytes`) to: capture an in-memory snapshot
with a human-named identifier and per-file SHA-256 inventory; refuse non-empty,
non-directory or source-overlapping destinations; copy byte-verbatim with per-file
atomic writes; write the inventory; run a blocking, coverage-asserted detect-secrets
content screen over the assembled files (inventory included); verify two-directionally
against the inventory; and only then write the completion marker that lets the result
be called the named snapshot. The existing consumer install/update contract
(`apply_bundle`) is packaged, not modified. Evidence: `scripts/speckit_bootstrap.py`
(all named functions verified in current working tree), `scripts/speckit-portable-bundle.json`
(1.1.0, 147 explicitly enumerated source files), `docs/speckit-portability.md`
(consumer contract and exclusions), `tests/unit/test_speckit_bootstrap.py`
(subprocess-driven test pattern to mirror).

No feature-local `codebase.md` exists; evidence above was gathered directly from the
current working tree during this planning pass (2026-11-17), including uncommitted
versions of `scripts/speckit-portable-bundle.json` and `docs/speckit-portability.md`.

## Technical Context

**Language/Version**: Python 3.11+ (`requires-python = ">=3.11"` in `pyproject.toml`); PowerShell only for documented invocation examples

**Primary Dependencies**: Python standard library only for capture/assembly/verification code (`hashlib`, `json`, `pathlib`, `tempfile`, `os`, `argparse`, `subprocess`). The mandatory content screen shells out to `detect-secrets` (already pinned `>=1.5.0` in `requirements-dev.txt`); no new dependency is introduced.

**Storage**: Filesystem only — source working tree (read-only), destination folder, JSON inventory record

**Testing**: pytest (`[tool.pytest.ini_options] testpaths = ["tests"]`); new `tests/unit/test_speckit_package.py` mirroring the subprocess style of `tests/unit/test_speckit_bootstrap.py`

**Target Platform**: Windows (primary, documented quoted paths), portable to macOS/Linux like the existing bootstrap script

**Project Type**: CLI packaging tooling inside an existing repository (brownfield delta; no application code touched)

**Performance Goals**: N/A — ~151 small files; single-pass hashing and copying completes in seconds

**Constraints**: Offline; stdlib-only receiving-side verification; never modifies source files or Git state; no network, no AWS/cloud footprint (aws-platform confirmed zero cloud scope; FR-010 is a negative constraint only); byte-verbatim copies (binary mode, never text mode — CRLF translation would break digests)

**Scale/Scope**: One new ~400-line maintainer CLI, two new package-only docs authored in-repo, one new test module, no changes to `speckit_bootstrap.py`, the bundle manifest, or any captured asset

## Constitution Check

*Constitution `.specify/memory/constitution.md` v1.0.0 governs the Aria banking agent.
Per the approved spec's assumptions, banking-service controls are not exported;
the applicable principles for this tooling-only feature are:*

| Principle | Applicability | Status |
|---|---|---|
| I, III, IV, V (agent state/context/session) | N/A — no agent runtime, no AWS, no conversation state | Pass (out of scope) |
| II Deterministic safety | Applicable analogue: path safety, overlap refusal and content screening enforced in code, not documentation promises | Pass — reuses `_relative_path`/`_resolve_within` validation and adds destination refusals |
| VI Python quality | Applicable: type hints, small cohesive module, explicit exception handling, deterministic tests | Pass — stdlib typed CLI + pytest coverage planned |
| Security & Compliance (no secrets/customer data persisted or shipped) | Applicable: FR-004 boundary, blocking detect-secrets screen, prohibited-artifact sweep | Pass — designed in (see Content boundary below) |
| Development gates (focused unit tests, CI checks) | Applicable | Pass — ruff/mypy-clean module, pytest tests before implement gate |

**Initial check: PASS. Post-design re-check (after Phase 1 artifacts below): PASS — no violations, Complexity Tracking empty.**

## Project practices

- **Project root / fingerprint**: `banking-relationship-manager-agent`, practices fingerprint `7991a8ad9448a559…` (from `python -m speckit_flow codebase practices --json`, 2026-11-17).
- **Commands** (working directory = repo root; CI uses `uv run`, local `python` works):
  - Tests: `python -m pytest tests/unit/test_speckit_package.py tests/unit/test_speckit_bootstrap.py` (`pyproject.toml` `[tool.pytest.ini_options] testpaths = ["tests"]`; CI: `.github/workflows/quality.yml` runs `uv run python -m pytest --cov=aria --cov-fail-under=70` — coverage gate measures `aria` only, so the new script does not move the gate).
  - Lint/format: `python -m ruff format --check .` and `python -m ruff check .` (quality.yml; `line-length = 100`, `select = ["E","F","I","UP"]`).
  - Types: CI runs `uv run python -m mypy aria` — `scripts/` is outside the mypy CI scope; still write the new script mypy-clean with full annotations (matching `speckit_bootstrap.py` style).
  - Secrets: CI runs `uv run python scripts/check_secrets.py`; its `SCAN_PATHS` (lines 10–22) covers `scripts/`, `docs/`, `specs/`, `.github/` but **omits `speckit_flow/` and `.specify/`** — therefore the assembly-time screen must run detect-secrets against the assembled destination itself (`cwd=destination`, `scan --all-files`, explicit file list + coverage assertion — see Design §2 step 6), not via the CI wrapper. A bare `detect-secrets scan <directory>` is NOT acceptable: empirically (1.5.0/Windows) it enumerates via `git ls-files` and silently scans zero files in a non-git destination.
- **Conventions**: `from __future__ import annotations`, dataclasses, `PurePosixPath` relative paths, textual `CREATE/UPDATE/CONFLICT/ERROR` statuses without color, exit codes 0/1/2 (all observed in `scripts/speckit_bootstrap.py`); tests invoke scripts via `subprocess.run([sys.executable, str(script), ...])` (observed in `tests/unit/test_speckit_bootstrap.py` lines 14–24).
- **Unknowns/conflicts**: none material. CI never exercises an out-of-repo destination; assembly acceptance checks (quickstart) cover that gap manually.

## Project Structure

### Documentation (this feature)

```
specs/039-standalone-speckit-flow-package/
├── spec.md              # approved
├── plan.md              # this file
├── research.md          # Phase 0 decisions
├── data-model.md        # Phase 1 entities
├── quickstart.md        # Phase 1 validation guide
└── contracts/
    ├── speckit-package-cli.md        # maintainer CLI + verifier contract
    └── snapshot-inventory.schema.json # SNAPSHOT.json schema
```

`tasks.md` follows from `/speckit-tasks`. This is the `feature` profile (not `quick`,
not `full-lifecycle`): all four artifacts are produced; no system-context diagram is
required (spec assumption, confirmed).

### Source Code (repository root) — delta only

```
scripts/
├── speckit_bootstrap.py           # UNCHANGED (captured asset; its helpers are imported)
├── speckit-portable-bundle.json   # UNCHANGED (captured allowlist, 1.1.0)
├── speckit_package.py             # NEW maintainer-side CLI (not itself packaged)
└── portable-package/              # NEW package-only doc sources (captured into package)
    ├── README.md                  # package root entry document (FR-011..FR-015 content)
    └── verify_snapshot.py         # stdlib receiving-side verifier (copied to package root)
tests/unit/
└── test_speckit_package.py        # NEW pytest module
docs/speckit-portability.md        # UNCHANGED (byte-preserved into package; FR-005 forbids rewriting)
```

**Helper-import mechanism and coupling policy**: `scripts/` is not a Python package;
`speckit_package.py` imports `speckit_bootstrap` as a sibling module — when invoked as
`python scripts/speckit_package.py`, `sys.path[0]` is `scripts/`, and the module also
defensively inserts its own resolved parent directory into `sys.path` so the import
works regardless of invocation style. The imported underscore-private helpers
(`_sha256`, `_relative_path`, `_resolve_within`, `_atomic_write`) belong to a file that
is simultaneously a frozen captured asset, so the coupling is stable by construction
for this feature; an **import-surface test** in `tests/unit/test_speckit_package.py`
pins the presence and callability of exactly these names so any future edit to the
installer's private surface fails fast. Vendoring copies was rejected (divergence risk
in security-sensitive path validation — research D1).

**Unchanged behavior that must remain unchanged**: every behavior of
`speckit_bootstrap.py` (install/update/dry-run/conflict/ownership/seed/disabled-plugin
semantics), the bundle manifest contents, all captured assets byte-for-byte, source Git
state, and all existing tests.

## Design

### 1. Snapshot capture (FR-002, FR-004)

`speckit_package.py` builds the capture set in memory before any destination write:

1. **Closure enumeration**: parse `scripts/speckit-portable-bundle.json` with the same
   validation discipline as `_collect_bundle` (explicit `include` lists required for
   directories — no globs, ever), but enumerate **source-relative paths** and read
   **raw bytes with no transformation**. Critically, the `plugin.json`
   `enabled=False` rewrite in `_collect_bundle` is a consumer-install-time transform
   and MUST NOT be applied at capture: the package carries source bytes verbatim, and
   the packaged installer re-applies the disabled default when a consumer installs.
   Documentation states explicitly that installed `plugin.json` digests legitimately
   differ from packaged ones.
2. **Add packaging entry points**: `scripts/speckit_bootstrap.py` and
   `scripts/speckit-portable-bundle.json` (not consumer bundle entries; required by FR-003).
3. **Add package-only docs**: `scripts/portable-package/README.md` → package `README.md`,
   `scripts/portable-package/verify_snapshot.py` → package `verify_snapshot.py`
   (explicit two-entry mapping hard-coded in the tool; recorded in the inventory with
   their differing `source_path`).
4. **Per-file record**: package-relative POSIX path (validated by `_relative_path`),
   lowercase-hex SHA-256 of raw bytes (`_sha256`), byte length. Casefolded
   ancestor/descendant collision keys (as in `_collect_bundle`) guarantee uniqueness on
   Windows, including against reserved names `SNAPSHOT.json` / `SNAPSHOT.json.sha256`.
5. **Snapshot identifier**: required `--label` (human-readable name; uniqueness across
   snapshots is a **documented human convention** stated in the package README — the
   tool keeps no registry and does not enforce it), capture
   timestamp as ISO-8601 with UTC offset (`datetime.now().astimezone().isoformat()`),
   required `--captured-by` (capturing human/invocation reference), source reference
   (repo + branch + HEAD commit, recorded **as reference only** — the snapshot is the
   working tree, which includes uncommitted deltas), and `bundle_version` read from the
   manifest (`1.1.0` at planning time).
6. **Inventory record** (`SNAPSHOT.json`): schema in `data-model.md` and
   `contracts/snapshot-inventory.schema.json`. Serialization follows `_manifest_bytes`
   conventions: `schema_version` field, sorted file entries, UTF-8 without BOM, LF, one
   trailing newline, digests regex-validated (`[a-f0-9]{64}`), duplicate paths rejected.
   The inventory is self-describing (declares `digest_algorithm: "sha256"` rather than
   assuming it) and verifiable from the package alone with the checkout inaccessible.
   **Honest limitation**: the inventory cannot self-hash; its own SHA-256 is written to
   the completion marker and printed for out-of-band recording.
7. **Pre-assembly inspection** (FR-002 "two-sided"): subcommand `inventory` prints the
   exact inventory JSON to stdout without writing anything, so the human can inspect
   what the approved working tree contains before authorizing assembly. The human
   snapshot approval is the gate that authorizes capturing uncommitted content;
   automated controls verify the boundary but do not substitute for that approval, and
   the per-file digest inventory is the audit trail of exactly which uncommitted bytes
   were approved.

Expected scale at manifest 1.1.0: 147 manifest-selected files + 2 entry points +
2 package-only docs = 151 inventoried files; the authoritative count is computed at
capture, never hard-coded.

### 2. Assembly procedure (FR-001, FR-005, FR-007 analogue)

Subcommand `assemble --dest <path> --label <l> --captured-by <ref> [--dry-run]`,
strictly ordered:

1. **Destination preflight (before any write)**: resolve destination; refuse if it
   exists as anything other than a directory (regular file, symlink or other
   non-directory — an explicit exit-2 refusal, not an incidental mkdir error); refuse
   if it exists and is non-empty (this also blocks silent resume onto a partial
   package); refuse bidirectional overlap with the resolved source root
   (`dest.is_relative_to(root) or root.is_relative_to(dest)`, exactly as
   `apply_bundle` rejects source/target overlap). Residual limitation documented, not
   solved: `Path.resolve()` does not canonicalize `subst`/mapped drives or hardlink
   aliases — stated limitation, not complete alias detection. Create the destination
   directory only after all refusal checks pass (an existing *empty* directory is
   acceptable).
2. **Capture** (section 1) entirely in memory. All destination paths route through the
   `_resolve_within` equivalent (per-component symlink rejection + containment check).
   Because bytes are read once and both hashed and written from memory, a source file
   changing mid-run cannot desynchronize digest and copy; an unreadable/missing
   allow-listed file aborts before any destination write with a per-file `ERROR` line.
3. **Dry run** stops here, printing planned `CREATE <path>` lines and the computed
   identifier; zero filesystem writes.
4. **Copy**: per-file atomic writes (`_atomic_write`: temp file in final directory,
   fsync, `os.replace`). No whole-run rollback exists or is claimed.
5. **Write `SNAPSHOT.json`** (atomic) — written **before** the content screen so the
   rendered metadata bytes are inside the screened set (the free-text `label`,
   `captured_by` and `source_reference` values are embedded here). Those free-text
   fields are additionally validated at argument parsing as defense-in-depth:
   printable characters only, no control characters, bounded length (≤ 200 chars).
6. **Content screen (blocking)**: run detect-secrets via subprocess **with
   `cwd=<destination>`** as `detect-secrets scan --all-files --force-use-all-plugins
   <relative paths…>`, passing the **explicit file list**: every inventoried path plus
   `SNAPSHOT.json`. Empirical review-verified finding (detect-secrets 1.5.0 /
   Windows): invoking `scan` on a bare directory path enumerates via `git ls-files`
   and silently scans **zero** files in a non-git destination, exiting 0 — a vacuous
   gate; the `cwd=destination` + `--all-files` + explicit-list form is the verified
   working mechanism (argv length is far below Windows limits at ~151 paths; chunked
   invocation is permitted if the manifest ever grows near the limit).
   **Coverage assertion**: the packager MUST count the paths it submits and fail the
   gate unless that count ≥ inventory file count + 1 (the +1 is `SNAPSHOT.json`), so
   a silently empty scan fails assembly. Any finding, scanner unavailability, or
   coverage shortfall fails assembly before the marker is written: the result is
   never declared the named snapshot. The only delivered bytes outside the screen are
   the completion marker — machine-generated (hex digest + fixed filename, no free
   text); this residual exposure is stated, not hidden. The screen is documented as
   heuristic — not complete PII assurance. Human review obligations that automation
   cannot satisfy (banking-policy language in docs, synthetic-only examples in new
   package docs) are acceptance-check items, not code. The CI wrapper
   `scripts/check_secrets.py` is not reused (its `SCAN_PATHS` omits `speckit_flow/`
   and `.specify/`, and it scans the repo, not the destination).
7. **Post-write verification (two-directional)**: re-read every destination file and
   compare digest + length against the inventory; walk the whole destination and fail
   on any file not in the inventory (only `SNAPSHOT.json` itself is expected-extra at
   this instant). Any mismatch → per-file plain-text drift report (section 4).
8. **Completion marker LAST**: write `SNAPSHOT.json.sha256` containing the
   sha256sum-format line `<sha256>  SNAPSHOT.json`. Contract: *the destination is the
   named snapshot if and only if the marker is present AND inventory comparison
   passes.* A crash at any earlier step leaves no marker; the step-1 non-empty refusal
   forces user-directed inspection/removal before rerun.

**Source preservation (FR-005)**: the tool opens source files read-only, never writes
inside the repository, never invokes Git mutations (`git rev-parse` read-only calls
only, with a `--source-ref` fallback if git is unavailable), and never rewrites
captured content (no branding removal, no neutrality edits).

### 3. Inclusion boundary and prohibited artifacts (FR-004, SC-001)

- **Assembled package layout (normative)**: the package root contains exactly
  `README.md`, `verify_snapshot.py`, `SNAPSHOT.json` and `SNAPSHOT.json.sha256`;
  every captured file keeps its **source-relative path** under the root (`scripts/`,
  `speckit_flow/`, `.github/`, `.specify/`, `docs/` — full normative tree in
  `data-model.md` §4). This mirroring is load-bearing for FR-006–FR-009: the
  packaged `apply_bundle` resolves manifest source paths relative to its own
  location exactly as it does in the repo, so the package must reproduce the source
  layout, never the consumer-install layout.
- **Delivered-file attribution** (every package file maps to exactly one): (a) the 147
  manifest allowlist files, (b) 2 packaging entry points, (c) 4 package-only
  doc/metadata files (`README.md`, `verify_snapshot.py`, `SNAPSHOT.json`,
  `SNAPSHOT.json.sha256` — the last **two** generated metadata files are excluded
  from the inventory by design: `SNAPSHOT.json` cannot self-hash, and the marker
  carries the inventory digest; both exclusions documented in README). Nothing else;
  the two-directional verification enforces it mechanically.
- **Prohibited-artifact exclusions verified at acceptance** (allowlist-by-construction
  plus an explicit sweep): zero Git history (`.git`), sessions/runtime state
  (`tmp-strands-sessions/`, `.specify/sessions`, state/audit files), audit/approval
  records, learned rules (`.specify/rules/` project file is a *portable seed template*
  `templates/portable/rules.json`, i.e. the empty default — verified empty), feature
  artifacts (`specs/`), source constitution (`.specify/memory/`), banking knowledge
  (`.specify/knowledge/banking-compliance.md` — manifest includes only
  `knowledge/README.md`; confirmed), application code (`aria/`, `cdk/`), dependency
  manifests (`pyproject.toml`, `requirements*.txt`, `uv.lock`), project tests, env or
  credential files. Any future manifest edit during implementation re-triggers this
  boundary check (acceptance check 1).
- **Leak-vector handling without rewriting (FR-005)**: `docs/speckit-portability.md`
  and `docs/speckit-profiles.md` may reference the banking source context; they are
  byte-preserved, and the package-local `README.md` is the portable-first entry point
  that frames them ("reusable tooling vs. source-specific examples"). Compliance agent
  definitions and the compliance plugin ship verbatim; FR-010 is satisfied because the
  *installer* (unchanged) writes `enabled: false` plugin manifests at consumer install
  and the portable roster seed leaves AWS/compliance specialists non-auto-dispatched —
  acceptance check 4 inspects a disposable install to confirm this behavior is
  preserved. Attribution notices are preserved verbatim; digest identity is the proof
  (a byte-identical file necessarily retains its notices) — README states this linkage.
- **Package metadata hygiene**: inventory/README contain no machine-identifying or
  credential context (no local absolute paths beyond the documented example
  destination, no usernames in generated fields other than the explicit
  `--captured-by` value the human chooses).

### 4. Partial failure and drift reporting (FR-001 partial-failure contract, FR-002 drift identification; recovery documentation lives in README per FR-015)

Mirrors the installer's textual discipline (no color, stable prefixes):

- Per-file lines: `ERROR <path> (<reason>)` for read/copy failures,
  `DRIFT <path> (missing|digest mismatch|unlisted file)` for verification failures.
- Summary on any failure after copying starts, verbatim semantics: what failed; the
  destination is **incomplete and must not be treated as snapshot `<label>`**;
  incompleteness is confirmable by comparing the destination against the snapshot
  inventory record (or capture output if `SNAPSHOT.json` was never written); recovery
  is user-directed — inspect, then remove/relocate the partial destination yourself or
  pick a different empty destination before rerunning. Assembly never deletes
  anything already written and never merges into or cleans a non-empty destination.
- Exit codes (contract): `0` assembled + screened + verified + marked; `1` completed
  copy phase but screen findings or drift (partial/unnamed result remains on disk);
  `2` refused before any write, or invalid invocation/environment.

### 5. Package-local documentation set (FR-011–FR-015)

One root `README.md` (authored at `scripts/portable-package/README.md`, synthetic
examples only, no quoted banking text, no real approval records), with these sections;
all links resolve inside the package:

1. **What this is / is not**: standalone installer source, not a pre-installed
   consumer project; contents & exclusions table (the FR-004 attribution above).
2. **Snapshot provenance**: the identifier lives in `SNAPSHOT.json` at the package
   root (README is byte-captured before the label exists, so it points rather than
   embeds); how to verify (`python verify_snapshot.py`), marker semantics, and the
   honest integrity statement: unsigned digests detect corruption and casual
   tampering; end-to-end integrity rests on the delivery channel plus the out-of-band
   snapshot identifier/inventory digest; no code signing/PKI (out of scope).
3. **Prerequisites, separated** (FR-012): running installer/verifier = Python 3.11+
   only; Spec Kit scripts = PowerShell; later repo work = Git; integration/live
   workflows = Spec Kit/Copilot host capabilities. States that the package bundles no
   external tools; grounded in `docs/speckit-portability.md` Prerequisites.
4. **Install / update / recovery**: quoted-explicit-path dry-run → install → doctor /
   profiles validate / plugins validate; update with ownership-record semantics;
   conflict interpretation and manual resolution; interrupted-write precautions for
   both assembly (per section 4) and consumer installs (conflict preflight is not a
   transaction guarantee). Points at the existing consumer ownership manifest
   (`.specify/speckit-portable-manifest.json`) and update preflight — no second
   consumer verification mechanism is invented; `SNAPSHOT.json` (package trust role)
   and the ownership manifest (consumer trust role) are explicitly distinguished.
5. **Repository preparation** (FR-013): ordered local `git init` → inspect (including
   hidden `.specify/`/`.github/` assets and the two metadata files) → `.gitignore`
   considerations → stage → first local commit. No remote, no publishing, no source
   history. Long-path note: keep the destination shallow or enable Windows long paths.
6. **Rights and assurance boundary** (FR-014) — placed **before** any
   distribution-adjacent guidance: redistribution rights and third-party provenance
   have not been established; appropriate human/legal resolution is required before
   any external distribution; no LICENSE/NOTICE file is created and no license is
   suggested; local git-init guidance does not imply distribution permission; no
   "open source"/"redistributable"/"approved" wording anywhere. Disclaimers:
   compliance examples are not certification; audit redaction is not complete PII
   protection; synthetic checks do not prove live-host or regulatory behavior;
   deterministic validation ≠ real Copilot/LLM behavior; unavailable/skipped checks
   are reported as such.

`verify_snapshot.py` (package-only, stdlib; satisfies FR-002's
verify-without-the-checkout requirement): reads `SNAPSHOT.json`, re-validates every
path with the `_relative_path` rules, two-directional check (every listed file exists
with matching digest and length; no unlisted files besides the two metadata files),
checks the marker digest, prints plain-text `OK`/`DRIFT`/`ERROR` lines, exit 0/1/2. It
checks its own inventory entry, which detects **accidental corruption of the verifier
only** — a tampered verifier could misreport its own digest, so this is not tamper
assurance; independent spot-checks of the verifier and inventory with
`Get-FileHash`/`certutil`/`sha256sum` against the out-of-band inventory digest are the
tamper-evidence path (README states this).

### 6. Acceptance checks (compliance-recommended; all offline)

1. **Boundary sweep** — walk the assembled package; every file attributes to
   allowlist / entry points / enumerated metadata; prohibited-artifact list has zero
   hits. Re-run if the manifest changes during implementation.
2. **Secret/PII scan** — the blocking screen built into `assemble` (`cwd=destination`,
   `scan --all-files --force-use-all-plugins`, explicit file list, coverage assertion
   ≥ inventory count + 1): zero findings is a precondition of the snapshot label.
   Also runnable standalone per quickstart F — which must use the same
   `cwd` + `--all-files` form, never a bare directory argument — including a
   **planted-secret positive control** proving the gate is not vacuous.
3. **Inventory verifiability from the package alone** — move/rename the checkout (or
   run as a different user without access), then `python verify_snapshot.py` passes.
4. **Neutral-defaults inspection** — disposable consumer install from the package:
   installed plugins all `enabled: false`, project rules file is the empty default,
   roster does not auto-dispatch AWS/compliance specialists, no source approvals/
   constitution/knowledge/feature pointer imported, existing pointer preserved.
5. **Docs boundary-language review** — human review of `README.md` for rights wording
   rules, synthetic-only examples, and no banking text; review of byte-preserved docs
   for portable-first framing adequacy (framing lives in README, not edits).
6. **Attribution preservation** — digest identity of captured assets equals source
   digests (automatic from verification); README states this linkage.
7. **Consumer-contract exercise from the package (explicitly in scope)** — one
   dry-run → install → update → conflict pass of the **packaged** installer, invoked
   from the assembled package against disposable targets (quickstart C and D), closes
   FR-006–FR-009 coverage from the delivered artifact itself rather than only from
   the source tree.

Plus regression: full existing `tests/unit/test_speckit_bootstrap.py` suite unchanged
and green; new `tests/unit/test_speckit_package.py` covers refusals (non-empty,
overlap in both directions, destination existing as a regular file or symlink),
dry-run write-freedom, byte-verbatim capture of an uncommitted change in a fixture
tree, no plugin.json rewrite at capture, a **planted-secret positive control** (a
fixture tree containing a synthetic credential makes `assemble` exit 1 with findings
and no marker — proves the screen is not vacuous), the screen **coverage-assertion**
failure path, an **import-surface test** pinning the `speckit_bootstrap` helpers the
packager imports (`_sha256`, `_relative_path`, `_resolve_within`, `_atomic_write` —
fails fast if the frozen asset's private surface ever changes), drift reporting,
marker-last ordering (the interruption-simulation mechanism — fault-injection flag,
planted secret, or induced drift — is deliberately deferred to tasks under the
subprocess test convention), two-directional verification, and exit codes. Exact
commands: `quickstart.md`.

### Success-criteria traceability

| SC | Proven by |
|---|---|
| SC-001 | Acceptance checks 1, 2, 3, 6; `assemble` post-write verification; `verify_snapshot.py` run (quickstart B) |
| SC-002 | Quickstart C (checkout unavailable, current directory outside the package) |
| SC-003 | Quickstart A step 4 (`git status` unchanged) plus zero-write dry-run/conflict checks in quickstart A, C, D |
| SC-004 | Quickstart D update matrix; acceptance check 7 |
| SC-005 | Quickstart E documentation walkthrough |
| SC-006 | Acceptance check 5 (docs boundary-language review) plus quickstart E rights/assurance checks |

## Risks and stated limitations

- `resolve()` alias canonicalization gap (subst/mapped drives) — documented, not solved.
- Unsigned digests — tamper-evidence only against corruption/casual modification; stated honestly.
- detect-secrets is heuristic — stated; human review checklist compensates. Directory-path invocation is additionally version/VCS-sensitive (empirically scans zero files in a non-git destination on pinned 1.5.0/Windows) — mitigated by the explicit-file-list invocation with `cwd=destination` and `--all-files`, the coverage assertion, and the planted-secret positive-control test.
- The completion marker is written after the screen and is itself unscreened — machine-generated content only (hex digest + fixed filename, no free text); stated residual exposure. Free-text identifier fields are screened via `SNAPSHOT.json` and bounded/validated at parse time.
- Working-tree snapshot is inherently racy against concurrent edits — mitigated by single-read capture-to-memory and post-write verification; the human should not edit the tree during assembly (documented).
- `SNAPSHOT.json.sha256` cannot be protected by the inventory (self-hash impossibility) — mitigated by printing the inventory digest for out-of-band recording.

## Complexity Tracking

*No constitution violations — table intentionally empty.*
