# Research: Standalone Spec Kit Flow Package

All decisions below were resolved against the current working tree on 2026-11-17
(`scripts/speckit_bootstrap.py`, `scripts/speckit-portable-bundle.json` 1.1.0,
`docs/speckit-portability.md`, `tests/unit/test_speckit_bootstrap.py`,
`requirements-dev.txt`, `scripts/check_secrets.py`, `.github/workflows/quality.yml`,
`pyproject.toml`). No NEEDS CLARIFICATION items remain.

## D1. Where the assembly logic lives

- **Decision**: New maintainer-side script `scripts/speckit_package.py` with
  subcommands `inventory` and `assemble`. It imports helper functions from
  `speckit_bootstrap` (same directory; `sys.path[0]` is `scripts/` when invoked as
  `python scripts/speckit_package.py`, and the module additionally inserts its own
  resolved parent directory into `sys.path` defensively so the sibling import works
  regardless of invocation style; tests invoke via subprocess exactly like
  `tests/unit/test_speckit_bootstrap.py` does). The tool itself is **not** delivered
  in the package. **Coupling policy**: the imported underscore-private helpers
  (`_sha256`, `_relative_path`, `_resolve_within`, `_atomic_write`) belong to a file
  that is simultaneously a frozen captured asset, so the coupling is stable by
  construction for this feature; an **import-surface test** in
  `tests/unit/test_speckit_package.py` pins the presence and callability of exactly
  these names so any later installer edit that breaks the surface fails fast
  (installer-side note for tasks: do not rename these helpers without updating the
  packager and its tests together).
- **Rationale**: Reuses audited primitives (`_sha256`, `_relative_path`,
  `_resolve_within`, `_atomic_write`, manifest validation discipline) without
  touching the installer, whose bytes are themselves a captured asset — modifying it
  would churn the snapshot and the consumer contract for no functional reason.
  Keeping the assembler out of the package minimizes delivered surface; the receiving
  developer never needs to re-assemble.
- **Alternatives rejected**:
  - *Add a `package` subcommand to `speckit_bootstrap.py`*: changes a captured
    asset and the consumer CLI surface; mixes maintainer-only and consumer concerns.
  - *Copy-paste the helpers into a standalone module*: divergence risk; two copies of
    security-sensitive path validation.
  - *PowerShell script*: loses the tested Python path-safety primitives and
    cross-platform behavior.

## D2. Byte-verbatim capture; no plugin.json transformation

- **Decision**: Capture reads raw bytes in binary mode and applies **no**
  transformation. The `enabled=False` plugin.json rewrite inside `_collect_bundle` is
  a consumer-install-time behavior and is not reused at capture/assembly.
  Documentation states that installed `plugin.json` digests legitimately differ from
  packaged (source) digests.
- **Rationale**: FR-002 demands snapshot fidelity to approved working-tree bytes;
  FR-005 forbids rewriting. FR-010 (disabled plugin defaults) is already enforced by
  the packaged installer at consumer install time, verified by acceptance check 4.
  Text-mode reads or CRLF translation would silently break digests (devsecops).
- **Alternatives rejected**: *Reuse `_collect_bundle` output as the capture source* —
  it returns destination-mapped, partially transformed content, which is the consumer
  view, not the source snapshot; it would also drop the installer-required source
  layout (e.g. `.specify/templates/portable/roster.json` must stay at its source path
  so the packaged installer can find it).

## D3. Digest and inventory serialization conventions

- **Decision**: SHA-256, lowercase hex, over raw bytes (stdlib `hashlib`; the
  installer's only hash). Inventory `SNAPSHOT.json`: `schema_version: 1` (own
  schema, distinct from the installer's install-manifest schema), declared
  `digest_algorithm: "sha256"` (declared, not assumed), per-file entries with
  POSIX-relative sorted paths, digest, byte length; UTF-8 without BOM, LF, one
  trailing newline; digests regex-validated `[a-f0-9]{64}`; duplicate paths rejected
  — all following `_manifest_bytes`/`_read_install_manifest` conventions.
- **Rationale**: Recomputable by any third party offline (`Get-FileHash`,
  `certutil -hashfile`, `sha256sum`); deterministic serialization makes the inventory
  itself reproducible and diffable; conventions already proven in this repo.
- **Alternatives rejected**: SHA-512/BLAKE2 (no interop advantage here, breaks
  uniformity with the installer); including per-file mtime (non-deterministic,
  no verification value); CSV/sha256sum-only format (cannot carry the snapshot
  identifier metadata or declare its algorithm/schema).

## D4. Snapshot identifier and uncommitted-content authorization

- **Decision**: Identifier = required `--label` (human-readable name; uniqueness
  across snapshots is a **documented human convention** stated in the package README
  — the tool keeps no registry and does not enforce it),
  ISO-8601 capture timestamp with UTC offset, required `--captured-by`
  (human/invocation reference), source reference (repo, branch, HEAD commit via
  read-only `git rev-parse`, with explicit `--source-ref` fallback) recorded **as
  reference only**, plus manifest `bundle_version` at capture (1.1.0). The free-text
  fields (`--label`, `--captured-by`, `--source-ref`) are validated at parse time:
  printable characters only, no control characters, bounded length (≤ 200 chars);
  they are also inside the content-screened set because `SNAPSHOT.json` is written
  before the screen (D5). The plan and
  README state that the human snapshot approval is the gate that authorizes capturing
  uncommitted working-tree content (which has never passed commit review), and that
  the per-file digest inventory is the audit trail of exactly which bytes were
  approved.
- **Rationale**: FR-002 names these identifier components; compliance requires the
  uncommitted-delta authorization to be explicit and auditable; devsecops requires
  the commit to be labeled a reference, not a fidelity claim (the tree differs from
  HEAD — confirmed: `git status` currently shows uncommitted changes to bundle
  manifest and docs).
- **Alternatives rejected**: deriving the label from the commit hash (misrepresents a
  working-tree snapshot as a commit); auto-generated anonymous labels (loses the
  human accountability reference).

## D5. Content screening placement and invocation

- **Decision**: `assemble` copies the captured files, writes `SNAPSHOT.json`, and
  then runs detect-secrets (subprocess; pinned `>=1.5.0` in `requirements-dev.txt`)
  **with `cwd=<destination>`** as
  `detect-secrets scan --all-files --force-use-all-plugins <relative paths…>`,
  passing the **explicit file list** — every inventoried path plus `SNAPSHOT.json` —
  and **asserting coverage**: the submitted-path count must be ≥ inventory file count
  + 1 or the gate fails. The screen runs **before** the completion marker is written;
  any finding, scanner unavailability, or coverage shortfall fails assembly and the
  snapshot label never attaches to an unscreened result. Free-text identifier fields
  (`--label`, `--captured-by`, `--source-ref`) are additionally validated at parse
  time (printable, no control characters, ≤ 200 chars) as defense-in-depth. The only
  delivered bytes outside the screen are the completion marker, which is
  machine-generated (hex digest + fixed filename, no free text) — a stated residual,
  not a hidden one. The screen is documented as heuristic, not complete PII
  assurance; human review of docs language and synthetic-example rules is a separate
  acceptance item. A planted-secret positive-control test proves the gate is not
  vacuous.
- **Rationale**: Compliance requires content screening of every captured file before
  the package is "declared assembled"; the marker is that declaration, so the scan
  must gate the marker. **Empirical review-verified finding (detect-secrets 1.5.0 /
  Windows)**: `detect-secrets scan <directory>` enumerates via `git ls-files` and
  silently scans **zero** files in a non-git destination, exiting 0 — the original
  bare-directory design was a vacuous gate. `cwd=destination` + `--all-files` +
  explicit file list is the verified working form; because the baseline output does
  not enumerate scanned files, coverage is guaranteed by explicit-argument
  construction and asserted by count (argv length is far below Windows limits at
  ~151 paths; chunked invocation is permitted if the manifest ever grows near the
  limit). Writing `SNAPSHOT.json` before the screen puts the rendered free-text
  metadata inside the screened set, so the screen covers all delivered bytes except
  the no-free-text marker. `scripts/check_secrets.py` cannot be reused: its
  `SCAN_PATHS` omits `speckit_flow/` and `.specify/`, and it scans the repo, not the
  destination. No new dependency: detect-secrets is already a pinned dev dependency
  of this repo (maintainer-side only — the receiving-side verifier stays pure
  stdlib).
- **Alternatives rejected**: *bare directory-path invocation (original design)* —
  empirically vacuous on a non-git destination (above); *separate manual scan step
  after assembly* — the marker would certify an unscreened package, violating the
  compliance ordering; *extend check_secrets.py SCAN_PATHS* — still repo-rooted,
  still wouldn't scan the destination or the generated metadata; *vendoring a
  scanner into the package* — new delivered surface and an implied assurance level
  the tool cannot honor; *screening the marker too* — would require writing the
  marker before the screen, inverting the marker-last completion contract for a file
  containing no free text.

## D6. Destination safety and path discipline

- **Decision**: Refuse destinations that exist as anything other than a directory
  (regular file, symlink or other non-directory — an explicit exit-2 refusal, not an
  incidental mkdir error); refuse non-empty destination directories (also the rerun
  guard after partial failure); refuse bidirectional resolved-path overlap with the
  source root (same
  check as `apply_bundle`); validate every inventory path with `_relative_path`
  (rejects absolute, `.`/`..`, backslash, NUL, `<>:"|?*`, reserved device names,
  trailing dots/spaces); route all destination I/O through a `_resolve_within`
  equivalent (per-component symlink rejection + containment). Casefolded
  ancestor/descendant collision keys (from `_collect_bundle`) enforce inventory path
  uniqueness on Windows. Documented residual limitation: `Path.resolve()` does not
  canonicalize `subst`/mapped-drive/hardlink aliases — a stated limitation, not
  complete alias detection. Documented commands always show quoted paths; long-path
  guidance (shallow destination or long-path-enabled Python) included.
- **Rationale**: FR-001 and the overlap/symlink edge cases; reuse of the already
  audited validation beats inventing parallel rules (devsecops).
- **Alternatives rejected**: *delete-and-recreate destination* (spec explicitly
  forbids cleaning/merging); *Windows junction/alias canonicalization via Win32
  APIs* (out of proportion; honesty about the limitation is the spec-compliant
  posture).

## D7. Failure model: per-file atomicity, marker-last, no rollback

- **Decision**: Per-file atomic writes via the `_atomic_write` pattern; **no
  whole-run rollback claimed or implemented**; nothing already written is ever
  deleted. `SNAPSHOT.json.sha256` (sha256sum-format line for `SNAPSHOT.json`) is
  written last, only after the content screen and full two-directional post-write
  verification pass. Contract: destination *is* the named snapshot iff marker present
  AND inventory comparison passes. Failures print plain-text per-file
  `ERROR`/`DRIFT` lines plus an incompleteness statement naming the snapshot label
  the result must NOT be called; recovery is user-directed (inspect, remove/relocate,
  or choose another empty destination). Exit codes: 0 success, 1 drift/screen
  findings after copying started, 2 refusal/invalid invocation.
- **Rationale**: FR-001's no-rollback/no-delete mandate; devsecops marker-last
  design; the marker also solves the inventory self-hash impossibility by carrying
  the inventory's own digest (also printed for out-of-band recording). Mirrors the
  installer's textual, color-free status discipline and 0/1/2 exit convention.
- **Alternatives rejected**: *staging dir + final rename* (an attractive
  all-or-nothing design, but the spec explicitly models and requires honest partial
  results with non-empty-destination refusal on rerun — and rename-into-place of a
  whole tree is itself non-atomic across volumes); *writing a "FAILED" marker file
  into the partial destination* (assembly must not keep writing after failure is
  declared; absence of the marker already encodes failure).

## D8. Package-only docs: authored in-repo and captured like any file

- **Decision**: `scripts/portable-package/README.md` → package `README.md` and
  `scripts/portable-package/verify_snapshot.py` → package `verify_snapshot.py`,
  authored during implementation, reviewed in-repo, captured byte-verbatim with
  inventory entries recording their differing `source_path`. README is static: it
  points to `SNAPSHOT.json` for the snapshot identifier rather than embedding a
  label that doesn't exist at authoring time. Only these two files plus the two
  generated metadata files are package-only; everything else is allowlist or entry
  point (FR-004 attribution closed).
- **Rationale**: Package docs must themselves be inside the inventory (FR-004) and
  reviewable before capture (compliance: new docs are the highest-risk fresh
  surface — synthetic examples only, no quoted banking text, no real approval
  records). Authoring in-repo gives them normal review and the same digest fidelity
  as other assets.
- **Alternatives rejected**: *generating README text inside the assembler* (ungoverned
  content, cannot be reviewed as a file, label-embedding temptation creates a
  circular-freshness problem); *placing the verifier under package `scripts/`*
  (would imply it is part of the consumer bundle contract; the root location marks it
  package-only metadata).

## D9. Receiving-side verification tooling

- **Decision**: Ship stdlib-only `verify_snapshot.py` at the package root performing
  the two-directional check (every listed file exists with matching digest and
  length; no unlisted files besides `SNAPSHOT.json` + marker) plus marker/inventory
  digest validation; plain-text output, exit 0/1/2. Quickstart additionally documents
  raw `Get-FileHash` / `certutil -hashfile` / `sha256sum` spot-check commands.
  Honest statement everywhere: unsigned digests detect corruption and casual
  tampering only; integrity otherwise rests on the delivery channel and the
  out-of-band identifier/inventory digest; code signing/PKI out of scope.
- **Rationale**: SC-001/FR-002 verification must work from the package alone,
  offline, with the checkout inaccessible; a bundled verifier (itself inventoried —
  though its self-digest check detects accidental corruption only: a tampered
  verifier can misreport, so independent digest commands against the out-of-band
  inventory digest remain the tamper-evidence path) is the only way the package is
  self-sufficient without asking the developer to hand-write JSON parsing.
- **Alternatives rejected**: *documented one-liners only* (error-prone,
  no two-directional sweep); *reusing the consumer ownership manifest mechanism*
  (different trust role — it records what the installer wrote into a consumer
  project, not what the package contains; conflating them is exactly what devsecops
  warned against — the README instead points consumers at the existing ownership
  manifest/update preflight).

## D10. Consumer contract: packaged, not modified

- **Decision**: Zero changes to `speckit_bootstrap.py`, the bundle manifest, or any
  captured asset. Install/update/dry-run/conflict/ownership/seed semantics (FR-006 –
  FR-009) are satisfied by packaging the existing, tested contract with its required
  source layout intact. Acceptance exercises them from the assembled package against
  disposable targets.
- **Rationale**: Spec assumption — "the existing manifest and installer define the
  portable contract; this feature packages them"; the existing
  `tests/unit/test_speckit_bootstrap.py` suite plus the documented portability
  contract already evidence FR-006–FR-010 behavior.
- **Alternatives rejected**: any installer enhancement (scope creep, invalidates the
  approved snapshot premise).

## D11. Line endings and encoding of generated artifacts

- **Decision**: Generated `SNAPSHOT.json` and marker: UTF-8, no BOM, LF only.
  Captured files: binary copy, endings untouched. New in-repo sources
  (`speckit_package.py`, `portable-package/*`, feature docs): authored LF.
- **Rationale**: Deterministic digests and diffs; matches `_manifest_bytes` output
  style; conductor's LF output requirement.
- **Alternatives rejected**: platform-native endings (would make the inventory bytes
  and their out-of-band digest machine-dependent).
