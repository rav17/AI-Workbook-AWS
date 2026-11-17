# Tasks: Standalone Spec Kit Flow Package

**Input**: Design documents from `specs/039-standalone-speckit-flow-package/`

**Prerequisites**: spec.md (approved), plan.md (gate approved; reviews plan-3 and plan-4 pass), research.md, data-model.md, quickstart.md, contracts/speckit-package-cli.md, contracts/snapshot-inventory.schema.json

**Verification**: Acceptance and regression test tasks accompany every changed behavior; requirement IDs (FR-xxx / SC-xxx) are cited per task. Manual checks are specified where behavior cannot be automated (real-destination assembly, consumer exercises, human docs review) with the quickstart section that defines them. Generated tests and checked boxes are not passing evidence; the Verification Commands section lists the exact commands and expected outcomes.

**Organization**: Tasks are grouped by user story (US1–US4 from spec.md) so each story is independently implementable and testable.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files or disjoint file regions, no dependency on an incomplete task)
- **[Story]**: US1 (P1 obtain package), US2 (P1 install safely), US3 (P2 update safely), US4 (P2 documentation/repo prep)
- Every task names its exact file path(s)

---

## Decisions (recorded for human review before implementation)

### D-A — Interruption-simulation mechanism for the marker-last ordering test (deferred plan-review finding 2)

**Decision**: a test-only environment-variable fault-injection hook, `SPECKIT_PACKAGE_FAULT`, read once in `main()` of `scripts/speckit_package.py`, inert by default (unset or empty = no effect), with a single allowlisted value for this feature: `corrupt-after-inventory` — after `SNAPSHOT.json` is written and before post-write verification, flip one byte of one named destination file (~10-line `_inject_fault(point, dest)` helper). Any unrecognized value is an exit-2 invalid-invocation error so typos cannot silently disable the fault.

**Rationale**: both developer and quality supports converge on this. The test convention is strictly subprocess (`tests/unit/test_speckit_bootstrap.py` `_run`, lines 18–24; custom `env=` precedent at line 75), so an in-process monkeypatch is unavailable; induced source drift is a race because plan.md Design §2 step 2 reads bytes once and hashes+writes from memory; killing the process mid-copy is nondeterministic; a documented CLI flag would change the approved contract surface. The env hook covers the verify→no-marker branch (`DRIFT <path> (digest mismatch)`, "must not be treated as snapshot", exit 1, marker absent, nothing deleted, rerun refused exit 2). The screen→no-marker branch needs no hook — the planted-secret positive control (T013) covers it naturally.

### D-B — How tests target fixture trees (open design divergence)

**Decision**: the **copy-scripts-into-fixture convention** (quality support's option). The approved CLI contract (`contracts/speckit-package-cli.md`) is **unchanged** — no `--source-root` / `--bundle` options are added. `scripts/speckit_package.py` resolves its source root and manifest path from its own file location (`ROOT = Path(__file__).resolve().parents[1]`, manifest at `ROOT / "scripts" / "speckit-portable-bundle.json"`), exactly as `ROOT` in `scripts/speckit_bootstrap.py` already does. The test fixture builder (T005) copies the real `scripts/speckit_package.py`, `scripts/speckit_bootstrap.py` and `scripts/portable-package/verify_snapshot.py` into `<fixture>/scripts/`, writes a small fixture bundle manifest at `<fixture>/scripts/speckit-portable-bundle.json`, and creates `<fixture>/scripts/portable-package/README.md` (synthetic content) so the capture closure is complete inside the fixture.

**Rationale**: the instruction preference is to keep the approved contract unchanged unless it concretely cannot satisfy the plan's mandated tests — and it can: every mandated test (refusals, dry-run, byte-verbatim uncommitted change, no plugin.json rewrite, planted secret, coverage assertion, drift, marker-last, assemble-twice) works against a fixture that contains copies of the real scripts, because the scripts under test are byte-identical copies exercising the real code paths. The `__file__`-relative root resolution matches the spec's own evidence note ("source-root resolution independent of working directory") and research D1; the fixture builder mirrors the existing `_make_fixture_bundle` precedent (`tests/unit/test_speckit_bootstrap.py` lines 287–307). No contract addendum task is needed. Trade-off accepted: tests exercise copies rather than the in-place file; identical bytes make this equivalent, and the repo-rooted happy path is still proven by the manual quickstart A/B acceptance runs (T029/T030).

### Secret-literal handling convention (supports finding 5; applies to every task below)

`scripts/check_secrets.py` `SCAN_PATHS` (lines 10–22) includes `tests/` and `specs/`. Therefore: (a) the planted-secret canary constant is always constructed at runtime from concatenated parts (e.g. `"AKIA" + "IOSFODNN7EXAMPLE"`), never written as one contiguous literal in any test, spec, or task file; (b) any documentation that must display the value uses the split form or a `# pragma: allowlist secret` suppression.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: create the not-yet-existing package-doc source directory and confirm tooling, so capture-closure code and tests have real files to enumerate.

- [x] T001 Create new directory `scripts/portable-package/` and stub `scripts/portable-package/README.md` containing only the six section headings from plan.md Design §5 (what-is / provenance / prerequisites / install-update-recovery / repository preparation / rights-and-assurance) plus a "DRAFT — final content in T037" marker; LF line endings. This directory does not exist yet and blocks capture-closure work (FR-003, FR-004).
- [x] T002 [P] Create stub `scripts/portable-package/verify_snapshot.py`: stdlib-only module skeleton with `argparse` (`--package` defaulting to the script's own directory per contracts/speckit-package-cli.md §3) that currently prints `ERROR verifier not implemented` and exits 2. Full implementation in T027 (FR-002).
- [x] T003 [P] Confirm `detect-secrets>=1.5.0` is pinned in `requirements-dev.txt` and importable as `python -m detect_secrets` in the dev environment; record in `tests/unit/test_speckit_package.py` module docstring (once T005 creates it) that detect-secrets is a **hard requirement** for the screen-dependent tests — no `skipif`, otherwise the gate is vacuously green (quality support; FR-002 screen precondition).

**Checkpoint**: `scripts/portable-package/` exists with both stub files; dev scanner available.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: module skeleton, helper-import surface, and the shared test harness every story's tests use.

**⚠️ CRITICAL**: no user story phase starts until this phase completes.

- [x] T004 Create `scripts/speckit_package.py` skeleton: `from __future__ import annotations`; defensive `sys.path` shim inserting the script's resolved parent directory so `import speckit_bootstrap` works regardless of invocation style (plan.md helper-import mechanism); import exactly `_sha256`, `_relative_path`, `_resolve_within`, `_atomic_write` from `speckit_bootstrap`; `ROOT = Path(__file__).resolve().parents[1]` and manifest path `ROOT / "scripts" / "speckit-portable-bundle.json"` (decision D-B); `CaptureEntry` dataclass with fields `path` (POSIX string), `sha256`, `bytes`, `origin` (`"source"`|`"package-doc"`), `source_path` (optional), `content` (raw bytes) per data-model.md §2.1; `argparse` with `inventory` and `assemble` subcommands and shared free-text validation for `--label`/`--captured-by`/`--source-ref`: "printable, no control characters, ≤ 200 chars" (data-model.md §1, verbatim constraint); exit-code constants 0/1/2. Fully type-annotated, mypy-clean, ruff-clean (FR-001, FR-002).
- [x] T005 Create `tests/unit/test_speckit_package.py` harness (no behavior tests yet): `ROOT = Path(__file__).resolve().parents[2]`; `_run(...)` subprocess helper mirroring `tests/unit/test_speckit_bootstrap.py` lines 18–24 (`subprocess.run([sys.executable, str(script), ...], capture_output=True, text=True, timeout=120)`, optional `env=`); fixture builder `_make_package_fixture(tmp_path, ...)` implementing decision D-B: copy `scripts/speckit_package.py`, `scripts/speckit_bootstrap.py`, `scripts/portable-package/verify_snapshot.py` from the repo into `<fixture>/scripts/` (+ `<fixture>/scripts/portable-package/`), write a minimal fixture bundle manifest at `<fixture>/scripts/speckit-portable-bundle.json` (mirroring `_make_fixture_bundle`, lines 287–307, including one plugin pack with `"enabled": true` in its `plugin.json` and one seed file), and create a synthetic `<fixture>/scripts/portable-package/README.md`. Also define the runtime-concatenated canary constant `CANARY_VALUE = "AKIA" + "IOSFODNN7EXAMPLE"` with label `aws_access_key_id` (never contiguous; see secret-literal convention) shared by T013 and quickstart F after T028.
- [x] T006 [P] Add `test_import_surface_pins_bootstrap_helpers` to `tests/unit/test_speckit_package.py`: `sys.path.insert(0, str(ROOT / "scripts"))`; `import speckit_bootstrap`; assert all four helpers exist and are `callable`; `_sha256(b"") == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"`; `_relative_path` raises `ValueError` on `"../x"` and `"a\\b"`; `_resolve_within` raises on a path escaping its root; `inspect.signature` arity check for `_atomic_write`. Pins the frozen-asset private surface the packager imports (plan coupling policy; FR-003). May run before T020–T027 exist.

**Checkpoint**: skeleton imports cleanly; `python -m pytest tests/unit/test_speckit_package.py -k import_surface` green; harness ready — user stories can begin.

---

## Phase 3: User Story 1 — Obtain an independent workflow-source package (Priority: P1) 🎯 MVP

**Goal**: `inventory` + `assemble` subcommands produce a byte-verbatim, digest-inventoried, secret-screened, two-directionally verified package with marker-last completion; `verify_snapshot.py` proves fidelity from the package alone.

**Independent Test**: fixture-based subprocess tests (T007–T019) pass without any real destination; then quickstart A/B against the real tree and `C:\Users\RavindraYadav\Documents\speckit-flow-portable` with the checkout renamed away for verification.

### Acceptance and Regression Tests for User Story 1 (write FIRST; all must FAIL before T020–T027)

All in `tests/unit/test_speckit_package.py`, all [P] (one file, but disjoint test functions; coordinate by appending — serialize commits if a single writer).

- [x] T007 [P] [US1] `test_inventory_prints_valid_snapshot_and_writes_nothing`: run `inventory` against a fixture; exit 0; stdout parses as JSON with `schema_version == 1`, `snapshot` object (label/captured_at/captured_by/source_reference/bundle_version/`digest_algorithm == "sha256"`), `files` sorted ascending by `path`, every `sha256` matching `[a-f0-9]{64}`, `bytes >= 0`, `origin` in {`source`,`package-doc`}, `source_path` only on package-docs — hand-rolled shape assertions per `contracts/snapshot-inventory.schema.json` (no `jsonschema` dep; it is not in requirements-dev.txt); stderr carries file count and the inventory's own SHA-256; zero filesystem writes anywhere (FR-002 side one; contract §1).
- [x] T008 [P] [US1] `test_assemble_refusals_exit_2_zero_writes`: non-empty destination; overlap in both directions (dest inside fixture root, fixture root inside dest); destination existing as a regular file; symlink leg wrapped in `try/except OSError` so only that leg is skipped when Windows symlink privilege is absent (quality gap 5). Each: exit 2, `CONFLICT`/`ERROR` text, zero writes (FR-001, Story 1.4; contract §2 `--dest`).
- [x] T009 [P] [US1] `test_assemble_dry_run_creates_nothing`: `assemble --dry-run` prints `CREATE <path>` lines and the snapshot identifier, exit 0, and creates nothing — not even the destination directory (FR-001, SC-003; contract `--dry-run`).
- [x] T010 [P] [US1] `test_capture_is_byte_verbatim_including_plugin_json`: modify one fixture allowlist file after building (simulating an uncommitted change) and keep the fixture plugin's `plugin.json` at `"enabled": true`; assemble; packaged bytes equal the modified working-tree bytes exactly, and the packaged `plugin.json` is byte-identical with `enabled` untouched — no consumer-install rewrite at capture (FR-002 Story 1.3, FR-005, FR-010; research D2).
- [x] T011 [P] [US1] `test_assemble_success_then_verifier_passes_without_source`: happy path. Assert `SNAPSHOT.json` is UTF-8 without BOM, LF-only, one trailing newline, sorted; marker `SNAPSHOT.json.sha256` content is `<sha256>  SNAPSHOT.json` + LF matching the actual inventory digest; parse the printed submitted-path-count line and assert it equals `len(SNAPSHOT.json["files"]) + 1` (finding 3 E2E leg); then **rename the fixture source tree away**, run the packaged `verify_snapshot.py` via subprocess from an unrelated cwd: `OK <n> files verified`, exit 0 (FR-002, SC-001, acceptance check 3; contract §3).
- [x] T012 [P] [US1] `test_verifier_drift_missing_marker_and_unlisted_file`: on an assembled fixture package — (a) edit one packaged file → `DRIFT <path> (digest mismatch)`, "must not be treated as snapshot <label>", exit 1; (b) delete the marker → "assembly never completed — not the named snapshot", exit 1; (c) add an unlisted file → `DRIFT <path> (unlisted file)`, exit 1 (FR-002 drift identification, SC-001; contract §3).
- [x] T013 [P] [US1] `test_planted_secret_blocks_marker_and_rerun` (**finding 1 + finding 5 positive control**): plant `aws_access_key_id = "<CANARY_VALUE>"` (runtime-concatenated constant from T005) in a fixture allowlist file; assemble → exit 1, findings reported, `SNAPSHOT.json.sha256` absent, no files deleted, "incomplete — not snapshot <label>" summary; rerun into the same destination → exit 2 non-empty refusal (FR-001 partial-failure contract, FR-002 screen gate; plan acceptance check 2).
- [x] T014 [P] [US1] `test_scan_findings_parsed_from_baseline_json` (**finding 1**): direct in-process import of `speckit_package`; feed the screen-result parser a baseline JSON document with non-empty `results` and a simulated returncode 0 → the gate fails. Asserts the contract: findings come from the emitted baseline JSON `results`, never the exit code (detect-secrets exits 0 even with findings) — same discipline as `scripts/check_secrets.py` lines 37–40 (cite in the test docstring as in-repo precedent).
- [x] T015 [P] [US1] `test_scan_coverage_assertion` (**finding 3**): direct in-process import; `_assert_coverage(submitted_count, inventory_count)` is an importable function; deterministic cases: `submitted < inventory + 1` → gate failure; `submitted == inventory + 1` → pass (the `+1` is `SNAPSHOT.json`, per plan.md Design §2 step 6).
- [x] T016 [P] [US1] `test_scanner_missing_fails_closed_label_withheld` (quality gap 2): the screen invokes the scanner as `[sys.executable, "-m", "detect_secrets", "scan", ...]`; expose the argv builder for testability and drive the gate with a patched/nonexistent module name in-process → scanner unavailability fails assembly, exit 1, label withheld, marker absent (FR-002; research D5).
- [x] T017 [P] [US1] `test_marker_last_ordering_via_fault_injection` (**finding 2**, decision D-A): run `assemble` via subprocess with `env` containing `SPECKIT_PACKAGE_FAULT=corrupt-after-inventory`; assert `DRIFT <path> (digest mismatch)` line, "must not be treated as snapshot" summary, exit 1, `SNAPSHOT.json.sha256` absent, nothing deleted; rerun without the env var into the same destination → exit 2 refusal. Also assert an unrecognized fault value exits 2, and an unset var changes nothing on the happy path (FR-001 interruption edge case; data-model.md §6 marker-last contract).
- [x] T018 [P] [US1] `test_label_and_captured_by_validation`: `--label`/`--captured-by`/`--source-ref` containing control characters, or exceeding 200 chars, or non-printable → exit 2 before any write; boundary value at exactly 200 printable chars accepted (data-model.md §1 constraint verbatim: "printable, no control characters, ≤ 200 chars"; FR-002 defense-in-depth, research D4).
- [x] T019 [P] [US1] `test_source_tree_untouched_by_assemble`: hash every file in the fixture source tree before and after a successful assemble; all digests identical, no new/removed source files (FR-005, SC-003).

### Implementation for User Story 1 (ordered; same file `scripts/speckit_package.py` for T020–T026 — not [P])

- [x] T020 [US1] Implement `_capture_closure() -> list[CaptureEntry]` in `scripts/speckit_package.py`: parse the manifest at `ROOT/scripts/speckit-portable-bundle.json` with the same validation discipline as `_collect_bundle` — explicit `include` lists required for directories (no globs), category check, casefolded ancestor/descendant collision keys (speckit_bootstrap.py lines 151–159) — but **mirror, don't import** `_collect_bundle` (it applies the `plugin.json` `enabled=False` rewrite at lines 161–167 and returns consumer-destination paths; both wrong for byte-verbatim source capture). Read raw bytes in binary mode, enumerate source-relative paths; add the 2 packaging entry points (`scripts/speckit_bootstrap.py`, `scripts/speckit-portable-bundle.json`) and the 2 package-docs with their differing `source_path` mapping (`scripts/portable-package/README.md` → `README.md`, `scripts/portable-package/verify_snapshot.py` → `verify_snapshot.py`); validate every path with `_relative_path`; unreadable/missing closure file → `ERROR <path> (<reason>)`, exit 2 (FR-002, FR-003, FR-004; research D2; makes T007/T010 pass).
- [x] T021 [US1] Implement `_inventory_bytes(entries, identifier) -> bytes` + the `inventory` subcommand in `scripts/speckit_package.py`: serialization per data-model.md §2 / `contracts/snapshot-inventory.schema.json` — `schema_version: 1`, sorted file entries, UTF-8 no BOM, LF, one trailing newline, digest regex validation, duplicate-path rejection; snapshot identifier fields incl. ISO-8601 timestamp with UTC offset and `source_reference` via read-only `git rev-parse` with `--source-ref` fallback; print document to stdout, count + inventory SHA-256 to stderr; zero writes (FR-002; research D3/D4; makes T007 pass fully).
- [x] T022 [US1] Implement `_preflight_destination(dest, root)` in `scripts/speckit_package.py`: explicit exit-2 refusals for destination existing as non-directory (file/symlink/other), non-empty directory (also the partial-result rerun guard), and resolved bidirectional overlap (`dest.is_relative_to(root) or root.is_relative_to(dest)` as in `apply_bundle`); create the destination only after all refusals pass; `CONFLICT <detail>` lines (FR-001; research D6; makes T008 pass).
- [x] T023 [US1] Implement `_plan_or_copy(entries, dest, dry_run)` in `scripts/speckit_package.py`: dry-run prints `CREATE <path>` + identifier with zero writes and stops; real run routes every destination path through a `_resolve_within`-equivalent check and writes per-file via `_atomic_write`; write failure → per-file `ERROR`, exit 1, nothing deleted (FR-001, FR-005; makes T009 pass).
- [x] T024 [US1] Implement `_write_inventory` + `_run_screen(dest, rel_paths)` + `_assert_coverage(submitted_count, inventory_count)` in `scripts/speckit_package.py` (**findings 1 and 3**): write `SNAPSHOT.json` atomically **before** the screen; invoke `[sys.executable, "-m", "detect_secrets", "scan", "--all-files", "--force-use-all-plugins", *relative_paths]` with `cwd=dest` over the explicit list (every inventoried path + `SNAPSHOT.json`; never a bare directory argument — vacuous on non-git destinations per research D5); **parse findings from the emitted baseline JSON `results`, never the exit code** (precedent: `scripts/check_secrets.py` lines 37–40); `_assert_coverage` requires submitted ≥ inventory count + 1; findings, scanner unavailability (fail closed), or coverage shortfall → exit 1, label withheld, destination left as-is (FR-002, FR-004; contract §2 steps 4–5; makes T013/T014/T015/T016 pass).
- [x] T025 [US1] Implement `_verify_destination(dest, inventory)` (two-directional: every listed file present with matching digest+length; directory walk flags any file not in the inventory except `SNAPSHOT.json` at this instant), `_write_marker` (sha256sum-format line, written **last**), failure summaries verbatim per contract §2 ("incomplete and must not be treated as snapshot `<LABEL>`", comparison guidance, user-directed recovery, nothing deleted), and `main()` sequencing preflight→capture→copy→inventory→screen→verify→marker with exit codes 0/1/2 (FR-001, FR-002, SC-001; data-model.md §6; makes T011/T012/T019 pass).
- [x] T026 [US1] Implement `_inject_fault(point, dest)` + the `SPECKIT_PACKAGE_FAULT` env hook in `scripts/speckit_package.py` per decision D-A: read once in `main()`; allowlist `{"corrupt-after-inventory"}` — after `SNAPSHOT.json` write, before verification, flip one byte of one named destination file; unrecognized value → exit 2; unset → inert (finding 2; makes T017 pass).
- [x] T027 [US1] Implement `scripts/portable-package/verify_snapshot.py` fully (replaces T002 stub; stdlib-only): parse + hand-rolled schema-shape validation of `SNAPSHOT.json`, re-apply `_relative_path` rules (self-contained copy of the rules — the package must not import the maintainer tool), two-directional check (listed files match digest+length; no unlisted files besides `SNAPSHOT.json` + marker), marker digest check, marker-absence message "assembly never completed — not the named snapshot", plain-text `OK`/`DRIFT`/`ERROR`, exit 0/1/2, `--package` defaulting to its own directory, and the honesty statement (unsigned digests; self-digest check detects accidental corruption only) (FR-002, SC-001; contract §3; research D9; makes T011/T012 pass).
- [x] T028 [US1] Fix the quickstart canary (**finding 5**) in `specs/039-standalone-speckit-flow-package/quickstart.md` section F: the current canary labels an AWS **access key ID** value as `aws_secret_access_key` — relabel the pair so detect-secrets classifies it (use `aws_access_key_id = "<AKIA-value>"` for the AWSKeyDetector, written in split/suppressed form per the secret-literal convention so `scripts/check_secrets.py` scanning `specs/` does not trip); add `--force-use-all-plugins` to the standalone canary scan so its flags match the assemble gate exactly; state that the identical runtime-constructed constant lives in `tests/unit/test_speckit_package.py` (T005/T013). Also sweep `spec.md`/`plan.md` for any contiguous occurrence of the canary literal and split/suppress it (developer CI-landmine note).

**Checkpoint (US1 / MVP)**: T007–T019 all green via `python -m pytest tests/unit/test_speckit_package.py`; fixture packages assemble, screen, verify, and mark end-to-end.

### Manual acceptance for User Story 1 (implementation phase; requires final README T037 for the deliverable run)

- [ ] T029 [US1] Manual quickstart A (maintainer capture/assemble): run `inventory` (record count — 151 expected at bundle 1.1.0, computed not hard-coded — and the out-of-band inventory digest), `assemble --dry-run` (zero writes), real `assemble` to `C:\Users\RavindraYadav\Documents\speckit-flow-portable` (exit 0, "assemble complete: snapshot <label>"), `git --no-pager status --short` unchanged, then all three refusal commands (exit 2 each). Record outputs as evidence (FR-001, FR-002, FR-005, SC-001, SC-003).
- [ ] T030 [US1] Manual quickstart B (receiving-side verification): with the checkout renamed/unavailable and cwd elsewhere, `python "<package>\verify_snapshot.py"` → OK exit 0; `Get-FileHash` spot check of `SNAPSHOT.json` against the out-of-band digest; negative test: edit a packaged file → `DRIFT ... (digest mismatch)` exit 1, then restore (FR-002, SC-001, acceptance checks 3 and 6).

---

## Phase 4: User Story 2 — Install into a different project safely (Priority: P1)

**Goal**: the packaged (unchanged) installer works by explicit path from the assembled package: dry-run, clean install, conflict preflight, neutral defaults.

**Independent Test**: automated packaged-installer dry-run from an assembled fixture package; full existing bootstrap suite green and unchanged; manual quickstart C against a disposable `$env:TEMP` target.

- [x] T031 [P] [US2] Add `test_packaged_installer_dry_run_from_assembled_package` to `tests/unit/test_speckit_package.py`: assemble a fixture package, then run `<package>/scripts/speckit_bootstrap.py install --target <fresh tmp dir> --dry-run` via subprocess from an unrelated cwd → `CREATE` lines, "DRY RUN install complete", exit 0, zero writes in package, target, and fixture source (FR-006, FR-007, SC-002 cheap automation per quality support).
- [ ] T032 [US2] Regression gate: `scripts/speckit_bootstrap.py`, `scripts/speckit-portable-bundle.json` and `tests/unit/test_speckit_bootstrap.py` are byte-unchanged by this feature (`git --no-pager diff --stat` on those paths is empty) and the full existing suite is green: `python -m pytest tests/unit/test_speckit_bootstrap.py` — including `test_optional_packs_stay_disabled_after_install` and `test_source_plugin_enablement_does_not_leak_to_target` which carry FR-010 (FR-006–FR-010, SC-004; research D10).
- [ ] T033 [US2] Manual quickstart C (consumer install, SC-002, Story 2.1–2.3, 2.5): disposable target in `$env:TEMP`, cwd outside the package; packaged installer dry-run then install (ownership record created, feature pointer created only because absent); `python -m speckit_flow doctor` / `profiles validate` / `plugins validate` inside the target; conflict preview with a pre-created differing `speckit_flow/cli.py` → `CONFLICT` lines, exit 1, zero writes (FR-006, FR-007, FR-008, SC-002, SC-003).
- [ ] T034 [US2] Manual neutral-defaults inspection (acceptance check 4, Story 2.4) inside the T033 target: every installed optional `plugin.json` contains `"enabled": false`; installed learned-rules file equals the empty portable default; roster leaves AWS/compliance specialists non-auto-dispatched; no source constitution, banking knowledge, approvals or source feature pointer present (FR-010, SC-006 evidence).

**Checkpoint**: US1 + US2 independently demonstrable; packaged consumer contract proven from the delivered artifact.

---

## Phase 5: User Story 3 — Update without surrendering project ownership (Priority: P2)

**Goal**: update semantics (advance/preserve/conflict/no-delete) proven from two assembled package fixtures against the installed target.

**Independent Test**: automated assemble-twice fixture test; manual quickstart D update matrix.

- [x] T035 [P] [US3] Add `test_assemble_twice_produces_independent_update_fixtures` to `tests/unit/test_speckit_package.py`: build one fixture tree, assemble to dest A; change one shared file and one seed default in the fixture; assemble to fresh dest B with a different label; both exit 0; digests differ only for the changed files; A is untouched by the second run. These are the two package fixtures quickstart D consumes (FR-009 enabler, SC-004).
- [ ] T036 [US3] Manual quickstart D (update matrix, Story 3.1–3.5, acceptance check 7): from the newer package, `update --dry-run` then `update` against the installed `$env:TEMP` target: unmodified shared files `UPDATE`; seed files `PRESERVE` despite changed bundle defaults; locally modified/deleted shared files `CONFLICT` with zero writes; files removed from the newer bundle not deleted; verify the documented note that installed `plugin.json` digests legitimately differ from packaged ones (FR-009, FR-010, SC-004).

**Checkpoint**: all consumer-contract stories (US2+US3) closed from the delivered artifact.

---

## Phase 6: User Story 4 — Understand, validate and prepare a separate repository (Priority: P2)

**Goal**: final package README with honest boundaries; automated doc assertions; human review; documentation walkthrough.

**Independent Test**: automated README assertions against an assembled fixture package; human walkthrough of quickstart E with only the package available.

- [x] T037 [US4] Author final `scripts/portable-package/README.md` (replaces T001 stub) per plan.md Design §5, sections in order: (1) what this is / is not + contents & exclusions attribution table; (2) snapshot provenance — identifier found via `SNAPSHOT.json`, verify command, marker semantics, unsigned-digest honesty, **and the timestamp-nondeterminism note (finding 4): `SNAPSHOT.json` embeds `captured_at` (and a commit reference), so reruns produce different inventory digests and markers by design — byte-level reproducibility is per-file, not per-inventory**; label-uniqueness human convention; inventory self-hash limitation; (3) prerequisites separated (installer/verifier = Python 3.11+; Spec Kit scripts = PowerShell; repo work = Git; integration = Copilot/host) (FR-012); (4) install/update/recovery incl. conflict interpretation, interrupted-assembly and interrupted-install precautions, pointer to the consumer ownership manifest, installed-plugin.json-digest note (FR-011, FR-015); (5) repository preparation: ordered local `git init` → inspect hidden assets + 2 metadata files → `.gitignore` → stage → first local commit; no remote/publish; long-path note (FR-013); (6) **rights and assurance boundary placed BEFORE any distribution-adjacent guidance**: redistribution rights/third-party provenance not established, human/legal resolution required, no license invented, compliance examples ≠ certification, redaction ≠ complete PII protection, synthetic/deterministic checks ≠ live-host or regulatory proof, skipped checks reported as such (FR-014). Synthetic examples only; no banking text; all links relative and package-internal; LF endings.
- [x] T038 [P] [US4] Add `test_package_readme_boundaries_links_and_timestamp_note` to `tests/unit/test_speckit_package.py`: on an assembled fixture package carrying the **real** README (extend `_make_package_fixture` to optionally copy `scripts/portable-package/README.md` instead of the synthetic one): every relative Markdown link resolves to a file inside the package; the rights/assurance section appears **before** the repository-preparation/distribution-adjacent section (ordering assertion on headings); the timestamp-nondeterminism note is present (**finding 4** automated leg) (FR-011, FR-014; SC-005/SC-006 partial automation).
- [ ] T039 [US4] Manual human docs review (acceptance check 5): review `scripts/portable-package/README.md` for rights wording rules (no "open source"/"redistributable"/"approved"), synthetic-only examples, no quoted banking text, no real approval records; review byte-preserved `docs/speckit-portability.md`/`docs/speckit-profiles.md` framing adequacy (framing lives in README — the docs themselves are never edited, FR-005). Record reviewer + outcome (FR-014, SC-006). Human-only: wording judgment cannot be automated.
- [ ] T040 [US4] Manual quickstart E walkthrough (SC-005, Story 4.1–4.4): with only the package, confirm every documented journey section exists and works; repository-preparation dry exercise in a **disposable copy** only: `git init` → `git add -A` → `git status` shows hidden `.specify/`/`.github/` assets and both metadata files → one local commit; no remote, no publication (FR-011, FR-012, FR-013, FR-015, SC-005).

**Checkpoint**: all four stories independently demonstrated.

---

## Phase 7: Polish & Cross-Cutting Verification

- [ ] T041 [P] Manual boundary sweep (acceptance check 1, quickstart F; FR-004, SC-001): recursively walk the assembled real package (hidden entries included); zero matches for `.git` history, `.jsonl` lifecycle logs, session/runtime state, approval/learned-rule content, source constitution, banking knowledge file, application code, dependency manifests (`pyproject.toml`, `requirements*.txt`, `uv.lock`), project tests, `.env`/credential files; every file attributes to allowlist / 2 entry points / 4 package-only metadata files. Re-run if the bundle manifest changed during implementation.
- [ ] T042 [P] Manual standalone scan + positive control (acceptance check 2, quickstart F as fixed by T028): `detect-secrets scan --all-files --force-use-all-plugins` with cwd = package root → empty `results`; canary run with the corrected label/value pair (same flags as the gate) → non-empty `results`; clean up the canary directory (FR-002, FR-004, SC-001).
- [x] T043 Full regression + static gates from repo root: `python -m pytest tests/unit/test_speckit_package.py tests/unit/test_speckit_bootstrap.py`; `python -m ruff format --check scripts/speckit_package.py scripts/portable-package/verify_snapshot.py tests/unit/test_speckit_package.py`; `python -m ruff check` (same paths); `python -m mypy scripts/speckit_package.py` (local check; CI mypy scope is `aria/` only); `python scripts/check_secrets.py` (proves the split-canary convention holds in `tests/` and `specs/`).
- [ ] T044 Traceability closure: walk the FR/SC mapping table below and the findings table; confirm every row has recorded passing evidence (test run, command output, or named human review), with skipped/unavailable checks reported as such, never as passes (SC-006).

---

## Deferred plan-review findings → task traceability

| Finding | Resolution tasks |
|---|---|
| 1 — parse detect-secrets baseline JSON `results`, not exit code; planted-secret positive control | T013, T014, T024 (impl), T042 (manual control) |
| 2 — interruption-simulation mechanism for marker-last test | Decision D-A; T017 (test), T026 (hook impl) |
| 3 — coverage assertion `submitted >= inventory + 1` as importable function + deterministic test | T015 (in-process test), T024 (`_assert_coverage` impl), T011 (E2E printed-count leg) |
| 4 — README note on SNAPSHOT.json timestamp nondeterminism | T037 (authoring), T038 (automated presence check), T039 (human review) |
| 5 — quickstart canary ID-vs-secret mislabel + flag parity with the gate + shared constant | T028 (quickstart fix), T005 (shared split constant), T013 (automated use), T042 (manual control) |

## Requirement / success-criterion coverage map

| ID | Tasks |
|---|---|
| FR-001 | T004, T008, T009, T017, T022, T023, T025, T029 |
| FR-002 | T003, T007, T010, T011, T012, T013, T014, T015, T016, T018, T020, T021, T024, T025, T027, T029, T030, T042 |
| FR-003 | T001, T006, T020 |
| FR-004 | T020, T024, T041, T042 |
| FR-005 | T010, T019, T023, T029, T032 (unchanged assets), T039 (no doc edits) |
| FR-006 | T031, T032, T033 |
| FR-007 | T031, T032, T033 |
| FR-008 | T032, T033 |
| FR-009 | T032, T035, T036 |
| FR-010 | T010, T032, T034, T036 |
| FR-011 | T037, T038, T040 |
| FR-012 | T037, T040 |
| FR-013 | T037, T040 |
| FR-014 | T037, T038, T039 |
| FR-015 | T037, T040 |
| SC-001 | T011, T012, T025, T027, T029, T030, T041, T042 |
| SC-002 | T031, T033 |
| SC-003 | T009, T019, T029, T033 |
| SC-004 | T032, T035, T036 |
| SC-005 | T038, T040 |
| SC-006 | T034, T038, T039, T044 |

---

## Dependencies & Execution Order

### Phase dependencies

- **Phase 1 (Setup)**: none — start immediately. T001 blocks T002 (same new directory); T003 independent.
- **Phase 2 (Foundational)**: needs Phase 1 (T004/T005 copy and enumerate `scripts/portable-package/*`). T004 → T005 (fixture builder copies the skeleton); T006 after T005.
- **Phase 3 (US1)**: needs Phase 2. Tests T007–T019 first (must fail), then T020→T021→T022→T023→T024→T025→T026 sequential (single file `scripts/speckit_package.py`); T027 after T025 (verifier mirrors final inventory/marker semantics); T028 anytime after T005 (shares the canary constant). T029/T030 (manual, real destination) additionally require T037 — the real package must carry the final README, otherwise the inventory captures the stub.
- **Phase 4 (US2)**: T031 needs T025 (assembled fixture); T032 anytime after Phase 2; T033 needs T029 (real package); T034 needs T033.
- **Phase 5 (US3)**: T035 needs T025; T036 needs T033 (installed target) + T029.
- **Phase 6 (US4)**: T037 needs T001 (stub exists) and should precede T029/T030/T033; T038 needs T037 + T025; T039 needs T037; T040 needs T029 (real package).
- **Phase 7**: T041/T042 need T029; T043 needs all code tasks; T044 last.

### Cross-story note

US2/US3/US4 manual tasks intentionally chain off the single real assembled package from T029 (one deliverable, many exercises). All automated tasks remain fixture-isolated and story-independent.

### Dependency graph (condensed)

```
T001 → T002                       T003
T001,T002 → T004 → T005 → T006
T005 → {T007..T019}[P] (tests, must fail first)
T004 → T020 → T021 → T022 → T023 → T024 → T025 → T026
T025 → T027         T005 → T028
T037 (needs T001) → T029 → T030
T025 → T031[P]      (any) → T032
T029 → T033 → T034
T025 → T035[P]      T033,T029 → T036
T037 → T038[P], T039            T029 → T040
T029 → T041[P], T042[P]
all code → T043 → T044
```

### Parallel opportunities

- Phase 1: T002 ∥ T003 (after T001).
- US1 tests T007–T019 are all [P] (independent test functions; same file — a single author should write them in one pass or coordinate appends).
- After T025: T027, T031, T035 can proceed in parallel with T037 (different files).
- Phase 7: T041 ∥ T042.

### Parallel example (US1 test authoring)

```
# After T005, write in one batch (all target tests/unit/test_speckit_package.py):
T007 inventory shape/no-writes     T013 planted secret
T008 refusals                      T014 baseline-JSON parsing
T009 dry-run zero writes           T015 coverage assertion
T010 byte-verbatim/plugin.json     T016 scanner missing
T011 happy path + verifier         T017 fault-injection marker-last
T012 verifier drift/marker         T018 free-text validation
                                   T019 source untouched
```

---

## Verification Commands (implementation phase; run from repo root)

```powershell
Set-Location -LiteralPath 'C:\Users\RavindraYadav\Documents\AI-Workbook-AWS\banking-relationship-manager-agent'
python -m pytest tests/unit/test_speckit_package.py tests/unit/test_speckit_bootstrap.py
# Expected: all green; covers T006–T019, T031, T035, T038 and the unchanged installer suite (FR-001..FR-010, SC-001, SC-003, SC-004).

python -m ruff format --check scripts/speckit_package.py scripts/portable-package/verify_snapshot.py tests/unit/test_speckit_package.py
python -m ruff check scripts/speckit_package.py scripts/portable-package/verify_snapshot.py tests/unit/test_speckit_package.py
python -m mypy scripts/speckit_package.py
python scripts/check_secrets.py
# Expected: clean; the last command proves the split-canary convention (finding 5) holds in tests/ and specs/.
```

Manual acceptance (quickstart A–F as amended by T028) per T029, T030, T033, T034, T036, T040, T041, T042 — exact commands, expected outputs and failure interpretations are in `specs/039-standalone-speckit-flow-package/quickstart.md`. detect-secrets is a hard dev requirement for T013/T016/T011 — no skipif (T003).

---

## Implementation Strategy

- **MVP = User Story 1** (Phases 1–3 automated portion): the packager + verifier with all fixture tests green is a complete, independently valuable increment — stop and validate at the US1 checkpoint.
- **Incremental delivery**: US2 (T031–T032 automated) → US3 (T035) → US4 (T037–T038) each add automated value independently; all real-package manual exercises (T029 onward) run once the final README (T037) lands, then chain US2/US3/US4 manual checks off the single assembled deliverable.
- **Task sizing**: every automated task is one function/one test cluster in one named file; every manual task cites its quickstart section and expected output so completion is independently checkable.
