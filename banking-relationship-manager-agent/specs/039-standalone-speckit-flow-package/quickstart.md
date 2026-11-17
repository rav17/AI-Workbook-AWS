# Quickstart: Standalone Spec Kit Flow Package — validation guide

Runnable scenarios proving the feature end-to-end. All checks are offline and use
stdlib/commodity tooling; the only non-stdlib tool (`detect-secrets`) is a pinned dev
dependency of the source repo and runs on the maintainer side only. Commands are
PowerShell 5.1/7-compatible with quoted explicit paths. Contracts:
`contracts/speckit-package-cli.md`; inventory schema:
`contracts/snapshot-inventory.schema.json`.

## Prerequisites

- **Maintainer side** (this repo): Python 3.11+, dev dependencies installed
  (`detect-secrets>=1.5.0` from `requirements-dev.txt`), Git available (read-only use).
- **Receiving side** (package alone): Python 3.11+ only for verification/install;
  PowerShell for Spec Kit scripts; Git only for the optional local repo preparation.
- Destination `C:\Users\RavindraYadav\Documents\speckit-flow-portable` must not
  exist or must be an empty directory; it must not be inside the checkout.

## A. Maintainer: capture, inspect, assemble (SC-001, Story 1)

```powershell
Set-Location -LiteralPath 'C:\Users\RavindraYadav\Documents\AI-Workbook-AWS\banking-relationship-manager-agent'

# 1. Pre-assembly inspection (FR-002 side one): print inventory, zero writes.
python scripts/speckit_package.py inventory --label "speckit-flow-portable-2026-11-17-01" --captured-by "<human approval reference>"
# Expected: SNAPSHOT.json document on stdout; file count (151 at bundle 1.1.0) and
# the inventory's own SHA-256 on stderr. Record that digest out of band.
# The human reviews this inventory; their snapshot approval is what authorizes
# capturing uncommitted working-tree content.

# 2. Dry-run assembly: planned CREATE lines only, zero writes.
python scripts/speckit_package.py assemble --dest "C:\Users\RavindraYadav\Documents\speckit-flow-portable" --label "speckit-flow-portable-2026-11-17-01" --captured-by "<human approval reference>" --dry-run

# 3. Real assembly: copy -> SNAPSHOT.json -> detect-secrets screen (explicit file
#    list, coverage-asserted) -> verify -> marker.
python scripts/speckit_package.py assemble --dest "C:\Users\RavindraYadav\Documents\speckit-flow-portable" --label "speckit-flow-portable-2026-11-17-01" --captured-by "<human approval reference>"
# Expected: exit 0; final lines include the inventory digest and
# "assemble complete: snapshot speckit-flow-portable-2026-11-17-01".

# 4. Source preservation check (SC-003): zero source/Git changes.
git --no-pager status --short   # identical to pre-assembly output
```

**Refusal cases (FR-001 / Story 1.4)** — each must exit 2 with a textual
explanation and zero writes:

```powershell
python scripts/speckit_package.py assemble --dest "C:\Users\RavindraYadav\Documents\speckit-flow-portable" --label x --captured-by y   # non-empty now -> refused
python scripts/speckit_package.py assemble --dest "C:\Users\RavindraYadav\Documents\AI-Workbook-AWS\banking-relationship-manager-agent\sub" --label x --captured-by y   # overlaps source -> refused
New-Item -ItemType File -Path "$env:TEMP\speckit-dest-as-file" -Force | Out-Null
python scripts/speckit_package.py assemble --dest "$env:TEMP\speckit-dest-as-file" --label x --captured-by y   # destination exists as a file (same refusal for a symlink) -> refused
```

**Failure/drift behavior**: interrupt or corrupt a copy in a scratch run; expect
per-file `ERROR`/`DRIFT` lines, an "incomplete — not snapshot <label>" statement, no
marker, no deletions; rerunning against the partial folder triggers the non-empty
refusal (recovery is user-directed).

## B. Receiving developer: verify the package alone (FR-002, acceptance check 3)

Run with the original checkout renamed/unavailable, from any working directory:

```powershell
python "C:\Users\RavindraYadav\Documents\speckit-flow-portable\verify_snapshot.py"
# Expected: "OK <N> files verified; snapshot speckit-flow-portable-2026-11-17-01 intact",
# exit 0 — where <N> equals the number of entries in SNAPSHOT.json's "files" array
# (151 at bundle 1.1.0; derived from the inventory, never hard-coded).

# Independent spot checks (any one):
Get-FileHash "C:\Users\RavindraYadav\Documents\speckit-flow-portable\SNAPSHOT.json" -Algorithm SHA256   # compare to out-of-band digest
certutil -hashfile "C:\Users\RavindraYadav\Documents\speckit-flow-portable\scripts\speckit_bootstrap.py" SHA256
# macOS/Linux: sha256sum -c SNAPSHOT.json.sha256   (run inside the package root)
```

Negative test: edit any packaged file, rerun the verifier — expect `DRIFT <path>
(digest mismatch)`, "must not be treated as snapshot <label>", exit 1. Restore the file.

## C. Consumer install into a disposable non-banking target (SC-002, Story 2)

```powershell
New-Item -ItemType Directory -Path "$env:TEMP\speckit-consumer-demo" | Out-Null
Set-Location -LiteralPath "$env:TEMP"   # current directory deliberately outside the package

python "C:\Users\RavindraYadav\Documents\speckit-flow-portable\scripts\speckit_bootstrap.py" install --target "$env:TEMP\speckit-consumer-demo" --dry-run
# Expected: CREATE lines, "DRY RUN install complete", exit 0, zero writes anywhere.

python "C:\Users\RavindraYadav\Documents\speckit-flow-portable\scripts\speckit_bootstrap.py" install --target "$env:TEMP\speckit-consumer-demo"
# Expected: exit 0; ownership record created at the documented consumer location;
# feature pointer created only because none existed; package and source untouched.

Set-Location -LiteralPath "$env:TEMP\speckit-consumer-demo"
python -m speckit_flow doctor               # expected: healthy engine report
python -m speckit_flow profiles validate    # expected: all profiles valid
python -m speckit_flow plugins validate     # expected: valid; all optional plugins disabled
```

**Neutral-defaults inspection (FR-010, acceptance check 4)** — run inside the
disposable target: confirm every installed optional plugin manifest contains
`"enabled": false`; confirm the installed project learned-rules file equals the empty
portable default; confirm the roster leaves AWS/compliance specialists available but
not auto-dispatched; confirm no source constitution and no banking knowledge file
were installed (both paths absent in the target).

**Conflict preview (Story 2.3)**: pre-create a differing
`speckit_flow/cli.py` in a second fresh target, run install — expect `CONFLICT`
lines for all differing files, "No files written; resolve the conflicts before
retrying.", exit 1, zero target writes.

## D. Update safety (SC-004, Story 3)

Using two package fixtures (assemble twice from fixture trees with one changed
shared file and one changed seed default) and the installed target from C:

```powershell
python "<newer-package>\scripts\speckit_bootstrap.py" update --target "$env:TEMP\speckit-consumer-demo" --dry-run
python "<newer-package>\scripts\speckit_bootstrap.py" update --target "$env:TEMP\speckit-consumer-demo"
```

Expected: unmodified shared files advance (`UPDATE`); seed files report `PRESERVE`
even when bundle defaults changed; locally modified/deleted shared files produce
`CONFLICT` with zero writes; files removed from the newer bundle are not deleted.
Note: installed `plugin.json` digests legitimately differ from packaged ones
(installer writes `enabled: false` at install time; capture is byte-verbatim).

## E. Documentation walkthrough (SC-005/SC-006, Story 4)

With only the package available: open `README.md`; confirm sections for contents/
exclusions, snapshot provenance (identifier found via `SNAPSHOT.json`),
prerequisites (installer vs Spec Kit scripts vs integration vs live-host, separated),
install/update/validation, conflict recovery, interrupted-write precautions, local
repository preparation, and the rights/assurance boundary appearing **before** any
distribution-adjacent guidance (no LICENSE, no redistribution/approval wording,
compliance examples not certification, redaction not complete PII protection,
synthetic checks not live-host proof). Every relative link resolves inside the
package. Repository preparation dry exercise (disposable copy only):
`git init` → `git add -A` → `git status` (hidden `.specify/` and `.github/` assets
visible in the staging inventory) → one local commit. No remote is created and no
publication occurs.

## F. Repository regression + acceptance sweeps (maintainer)

```powershell
Set-Location -LiteralPath 'C:\Users\RavindraYadav\Documents\AI-Workbook-AWS\banking-relationship-manager-agent'
python -m pytest tests/unit/test_speckit_package.py tests/unit/test_speckit_bootstrap.py   # new suite + unchanged installer suite green
python -m ruff format --check scripts/speckit_package.py; python -m ruff check scripts/speckit_package.py
python -m mypy scripts/speckit_package.py   # local check; CI mypy scope is aria/ only

# Acceptance check 2 (secret/PII scan; embedded in assemble with an explicit file
# list + coverage assertion >= inventory count + 1). Standalone re-run — MUST use
# cwd=package + --all-files: a bare directory argument silently scans zero files in a
# non-git destination on pinned detect-secrets 1.5.0 and is NOT a valid check.
Set-Location -LiteralPath 'C:\Users\RavindraYadav\Documents\speckit-flow-portable'
detect-secrets scan --all-files --force-use-all-plugins
# Expected: empty "results" ({}). The empty result is only meaningful because
# cwd + --all-files guarantee file enumeration.

# Positive control (proves the scanner is not vacuous in this environment); the
# automated equivalent — a planted synthetic secret makes `assemble` exit 1 with
# findings and no marker — lives in tests/unit/test_speckit_package.py (T013),
# which constructs the identical runtime-concatenated constant (CANARY_LABEL /
# CANARY_VALUE, T005). The value below is split on purpose per the secret-literal
# convention: scripts/check_secrets.py scans specs/, so this file must never
# contain the contiguous literal.
New-Item -ItemType Directory -Path "$env:TEMP\speckit-screen-canary" -Force | Out-Null
$canaryValue = 'AKIA' + 'IOSFODNN7EXAMPLE'   # synthetic AWS-docs example access key ID
Set-Content -Path "$env:TEMP\speckit-screen-canary\canary.txt" -Value ('aws_access_key_id = "' + $canaryValue + '"')
Set-Location -LiteralPath "$env:TEMP\speckit-screen-canary"
detect-secrets scan --all-files --force-use-all-plugins
# Expected: non-empty "results" naming canary.txt with type "AWS Access Key"
# (AWSKeyDetector; flags identical to the assemble gate).
Set-Location -LiteralPath 'C:\Users\RavindraYadav\Documents\AI-Workbook-AWS\banking-relationship-manager-agent'
Remove-Item -Recurse -Force "$env:TEMP\speckit-screen-canary"
```

**Acceptance check 1 (boundary sweep, prohibited artifacts)** — search the assembled
package recursively (including hidden entries) and expect **zero** matches for: any
Git history directory, any `.jsonl` lifecycle log, any session or runtime state
file, approval/learned-rule records with content, the source constitution, the
banking knowledge file, application code, dependency manifests
(`pyproject.toml`, `requirements*.txt`, `uv.lock`), project tests, and any `.env` or
credential-bearing file. Every file present must attribute to the allowlist, the two
packaging entry points, or the four enumerated package-only metadata/doc files.

Expected failure interpretation throughout: any `DRIFT`/`CONFLICT`/`ERROR` line names
the exact file and reason in plain text (readable without color); exit 1 = content
problem (drift/conflict/screen finding), exit 2 = refusal or invalid invocation.
Deterministic checks above do not prove live Copilot/LLM behavior; skipped or
unavailable checks must be reported as such, never as passes.
