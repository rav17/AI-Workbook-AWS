# CLI Contract: `scripts/speckit_package.py` and package verifier

Textual statuses only (no color); exit codes follow the repository convention
established by `scripts/speckit_bootstrap.py` (0 success / 1 content problem /
2 refusal or invalid invocation). All documented examples use quoted explicit paths.
Maintainer tool is stdlib-only except the subprocess call to `detect-secrets`
(pinned `>=1.5.0` in `requirements-dev.txt`); it is **not** delivered in the package.

## 1. `inventory` — pre-assembly inspection (no writes)

```
python scripts/speckit_package.py inventory --label <LABEL> --captured-by <REF> [--source-ref <TEXT>] [--output "<NEW FILE OUTSIDE CHECKOUT>"]
```

| Aspect | Contract |
|---|---|
| Behavior | Enumerates the capture closure (manifest allowlist + 2 packaging entry points + 2 package-docs), validates every path, computes per-file SHA-256 + byte length, prints the exact `SNAPSHOT.json` document to stdout. Zero filesystem writes anywhere, except the single `--output` file when given: exclusive create (never overwrites), refused inside the source repository, bytes identical to what stdout would carry. `--output` is the documented way to save the reviewed inventory because shell redirection can re-encode it. |
| Purpose | FR-002 two-sided verification, side one: the human inspects the captured inventory and confirms it reflects the approved working tree before authorizing assembly. |
| stderr extras | The inventory's own SHA-256 (for out-of-band recording) and the file count. |
| Exit codes | 0 inventory printed; 2 manifest invalid, allow-listed file missing/unreadable, unsafe path, or bad arguments (message: `ERROR <detail>`). |

## 2. `assemble` — capture, copy, screen, verify, mark

```
python scripts/speckit_package.py assemble --dest "<ABSOLUTE PATH>" --inventory "<REVIEWED SNAPSHOT.json>" --inventory-sha256 <APPROVED DIGEST> [--dry-run]
```

| Argument | Contract |
|---|---|
| `--dest` | Required. Destination folder. Refused (exit 2, zero writes) if: it exists as anything other than a directory (regular file, symlink or other non-directory — an explicit refusal, not an incidental mkdir error); it exists and is non-empty (also the rerun guard over partial results); or its resolved path and the resolved source repo root are equal or ancestor/descendant in either direction. An existing **empty** directory is accepted; a missing one is created after all refusals pass. Known limitation (documented, not solved): `resolve()` does not canonicalize subst/mapped-drive/hardlink aliases. |
| `--inventory` | Required. The inventory file the human reviewed (saved with `inventory --output`). Label, captured-by, captured-at, source reference and bundle version are taken from it; assemble no longer accepts `--label`, `--captured-by` or `--source-ref`. |
| `--inventory-sha256` | Required. The digest the human approved. The file's SHA-256 must equal it, else exit 2 with zero writes. |
| Snapshot label (from the reviewed inventory; set via `inventory --label`) | Required snapshot label. Uniqueness across snapshots is a documented human convention (package README), not tool-enforced — no registry exists. Validated: printable, no control characters, ≤ 200 chars (same validation applies to `--captured-by` and `--source-ref`). |
| `inventory --captured-by` (recorded in the reviewed inventory) | Required capturing human / invocation reference. |
| `inventory --source-ref` (recorded in the reviewed inventory) | Optional override/fallback for the repository/branch/commit reference when `git` is unavailable (otherwise read-only `git rev-parse` is used). |
| `--dry-run` | Capture + preflight only; print `CREATE <path>` per planned file and the snapshot identifier; **zero filesystem writes**. |

### Ordered behavior (non-dry-run)

1. Destination preflight refusals (above) — before any write.
2. Read `--inventory`, require its SHA-256 to equal `--inventory-sha256`, and validate the complete inventory schema (required fields/types and no unknown properties). Then capture the current closure in memory and compare its exact serialized inventory—including metadata, paths, digests and lengths—with the reviewed bytes. Invalid inventory, unreadable/missing closure file or drift → exit 2, zero destination writes. An existing empty destination remains empty on refusal.
3. Per-file atomic copies (temp file + fsync + `os.replace`); source repository is never written to; captured bytes are copied verbatim (no plugin.json rewrite — that remains a consumer-install-time transform by the packaged installer).
4. Write `SNAPSHOT.json` atomically using the exact reviewed inventory bytes (UTF-8 no BOM, LF, sorted, trailing newline) — **before** the screen, so reviewed metadata is inside the screened set.
5. Blocking content screen: subprocess **with `cwd=<dest>`**: `detect-secrets scan --all-files --force-use-all-plugins <relative paths…>` over the **explicit file list** — every inventoried path plus `SNAPSHOT.json`. A bare directory argument is forbidden: empirically (detect-secrets 1.5.0/Windows) it enumerates via `git ls-files` and silently scans zero files in a non-git destination. **Coverage assertion**: the submitted-path count MUST be ≥ inventory file count + 1, else the gate fails. Findings, missing scanner, or coverage shortfall → exit 1, label withheld, destination left as-is. The completion marker is the only delivered file outside the screen (machine-generated hex digest + fixed filename, no free text — stated residual).
6. Two-directional post-write verification against the inventory (every listed file present with matching digest+length; no unlisted files besides `SNAPSHOT.json` itself at this instant).
7. Write completion marker `SNAPSHOT.json.sha256` **last**; print the inventory digest and `assemble complete: snapshot <LABEL>`.

### Output lines (stable prefixes)

```
CREATE <path>               planned/performed copy
ERROR <path> (<reason>)     per-file read/copy failure
DRIFT <path> (missing|digest mismatch|unlisted file)
CONFLICT <detail>           destination refusal detail (preflight)
```

On any failure after copying starts, a plain-text summary states: what failed; the
destination is incomplete and must not be treated as snapshot `<LABEL>`;
incompleteness is confirmable by comparing against the snapshot inventory record;
recovery is user-directed (inspect, then remove/relocate the partial destination or
choose a different empty destination before rerunning). Nothing already written is
deleted; no rollback is claimed.

### Exit codes

| Code | Meaning |
|---|---|
| 0 | Assembled, screened, verified, marker written — destination is the named snapshot. |
| 1 | Copying started but screen findings or drift/verification failure — partial, unnamed result remains. |
| 2 | Refused before any destination write (non-empty dest, overlap, invalid manifest/closure/arguments) or runtime error before copy. |

## 3. Package verifier — `verify_snapshot.py` (delivered at package root; stdlib-only, offline)

```
python "<package>\verify_snapshot.py" [--package "<dir>"]    # default: the script's own directory
```

| Aspect | Contract |
|---|---|
| Checks | Parse + schema-validate `SNAPSHOT.json` (path safety rules re-applied); every listed file exists with matching SHA-256 and byte length; directory walk finds no files absent from the inventory other than `SNAPSHOT.json` and `SNAPSHOT.json.sha256`; marker content matches the inventory's actual digest; marker absence reported as "assembly never completed — not the named snapshot". |
| Output | Plain text: `OK <n> files verified; snapshot <LABEL> intact` or per-file `DRIFT <path> (<reason>)` lines plus a summary that the folder must not be treated as snapshot `<LABEL>`. |
| Exit codes | 0 intact; 1 drift/marker mismatch/marker missing; 2 unreadable/invalid inventory or invocation error. |
| Honesty | Prints that unsigned digests detect corruption and casual tampering only; integrity otherwise rests on the delivery channel plus the out-of-band snapshot identifier/inventory digest; no code signing/PKI. The verifier's check of its own inventory entry detects accidental corruption only — a tampered verifier can misreport its own digest; independent digest commands (`Get-FileHash`/`certutil`/`sha256sum`) against the out-of-band inventory digest are the tamper-evidence path. |

## 4. Consumer-facing contract (unchanged, referenced not redefined)

The packaged `scripts/speckit_bootstrap.py` CLI is the existing contract:
`install|update --target <dir> [--dry-run]`, exit 0/1/2, `CREATE/UPDATE/UNCHANGED/
PRESERVE/CONFLICT` statuses, ownership record `.specify/speckit-portable-manifest.json`,
feature-pointer creation only when absent. This feature changes none of it; package
docs point to it instead of inventing a second consumer mechanism.
