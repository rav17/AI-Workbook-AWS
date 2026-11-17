# Spec Kit Flow portable package

A byte-verbatim, digest-inventoried snapshot of the portable Spec Kit Flow
workflow tooling, captured from a source working tree by a named human. Start
here; every link below is relative and stays inside this package.

## 1. What this package is (and is not)

This package **is**:

- the source files of the portable Spec Kit workflow (engine modules, skills,
  agent definitions, templates, profiles, scripts and workflow documentation),
  copied byte-for-byte from the capturing working tree;
- the consumer installer [scripts/speckit_bootstrap.py](scripts/speckit_bootstrap.py)
  and its allowlist manifest
  [scripts/speckit-portable-bundle.json](scripts/speckit-portable-bundle.json);
- a self-describing snapshot record: [SNAPSHOT.json](SNAPSHOT.json) plus the
  completion marker `SNAPSHOT.json.sha256`, verifiable offline with
  [verify_snapshot.py](verify_snapshot.py).

This package **is not**: an application, a product release, a backup of the
source project, or a statement of rights (see section 5 before doing anything
distribution-adjacent with it).

Every delivered file attributes to exactly one of the following:

| Attribution | Files |
|---|---|
| Bundle allowlist | Every file explicitly enumerated by [scripts/speckit-portable-bundle.json](scripts/speckit-portable-bundle.json) (no globs; explicit include lists only) |
| Packaging entry points | [scripts/speckit_bootstrap.py](scripts/speckit_bootstrap.py), [scripts/speckit-portable-bundle.json](scripts/speckit-portable-bundle.json) |
| Package-only documentation | This `README.md`, [verify_snapshot.py](verify_snapshot.py) |
| Generated package metadata | [SNAPSHOT.json](SNAPSHOT.json), `SNAPSHOT.json.sha256` (both excluded from the inventory by design: the inventory cannot contain its own hash, and the marker carries the inventory digest) |

Deliberately **excluded** (verified at assembly and swept at acceptance): Git
history, session/runtime state, audit and approval records, learned-rule
content (only the empty portable seed ships), feature specifications, the
source project's constitution and domain knowledge, application code,
dependency manifests, project tests, and any environment or credential files.
Two source documents (`docs/speckit-portability.md`, `docs/speckit-profiles.md`,
present in the full package) are byte-preserved from the source project: treat
the reusable tooling instructions as portable and any source-specific examples
in them as illustrations, not requirements.

## 2. Snapshot provenance and verification

The snapshot identifier lives in [SNAPSHOT.json](SNAPSHOT.json) under
`snapshot`: a human-chosen `label`, the capture timestamp `captured_at`, the
capturing human/invocation reference `captured_by`, a source reference
(repository/branch/commit — a reference only, never a fidelity claim: the
captured working tree may contain uncommitted changes, and the per-file digests
are the authoritative record), the `bundle_version` of the allowlist manifest,
and the declared `digest_algorithm` (`sha256`).

Verify the package from this folder, offline:

```
python verify_snapshot.py
```

Expected: `OK <n> files verified; snapshot <label> intact`, exit code 0. Any
`DRIFT <path> (missing|digest mismatch|unlisted file)` line names the exact
problem; exit 1 means the folder must not be treated as the named snapshot;
exit 2 means the inventory itself is unreadable or invalid.

Marker semantics: this folder *is* the named snapshot **if and only if**
`SNAPSHOT.json.sha256` exists **and** inventory comparison passes. The marker
is written last by the assembling tool, after a blocking content screen and a
full two-directional verification; if it is absent, assembly never completed
and the folder is not the named snapshot.

Honesty notes:

- Digests are unsigned. They detect corruption and casual tampering only;
  integrity otherwise rests on the delivery channel plus the out-of-band
  recorded snapshot label and inventory digest (no code signing, no PKI). A
  tampered verifier can misreport its own digest, so for tamper evidence use an
  independent digest command (`Get-FileHash`, `certutil -hashfile`,
  `sha256sum`) against the out-of-band inventory digest.
- The inventory cannot contain its own hash; its SHA-256 lives in the
  completion marker and is printed at assembly time for out-of-band recording.
- Timestamp nondeterminism (by design): `SNAPSHOT.json` embeds `captured_at`
  and a source commit reference, so re-running assembly over identical sources
  produces a different inventory digest and completion marker — byte-level
  reproducibility is per-file, not per-inventory. Compare per-file digests, not
  inventory digests, when comparing two captures.
- Label uniqueness across snapshots is a human convention (record labels and
  inventory digests out of band); no tool-enforced registry exists.

## 3. Prerequisites

Kept separate on purpose; you only need the rows you intend to use.

| Activity | Requirement |
|---|---|
| Installer (`scripts/speckit_bootstrap.py`) and verifier (`verify_snapshot.py`) | Python 3.11+ (standard library only) |
| Spec Kit workflow helper scripts (under `.specify/scripts/powershell/` after install) | PowerShell |
| Repository preparation (section 6) | Git |
| Workflow execution in an editor/agent host | A GitHub Copilot-compatible host; live agent behavior is outside what this package can prove (section 5) |

## 4. Install, update and recovery

Install into a target project (always preview first):

```
python "scripts/speckit_bootstrap.py" install --target "C:\path\to\your-project" --dry-run
python "scripts/speckit_bootstrap.py" install --target "C:\path\to\your-project"
```

Update an existing install the same way with `update`. Statuses are plain
text: `CREATE` (new file), `UPDATE` (unmodified shared file advanced),
`UNCHANGED`, `PRESERVE` (your seed/pointer files are never overwritten),
`CONFLICT` (your local change differs from the bundle — **zero files are
written** when any conflict is reported; exit 1). Resolve or move the
conflicting file, then re-run; `--dry-run` previews without writing.

- Ownership record: the installer writes
  `.specify/speckit-portable-manifest.json` **in the target project**; the
  update preflight uses it to distinguish your edits from bundle changes. It is
  not part of this package and is unrelated to `SNAPSHOT.json`.
- The feature pointer `.specify/feature.json` is created only when absent and
  preserved afterwards.
- Installed `plugin.json` digests legitimately differ from the packaged bytes:
  capture is byte-verbatim, while the installer writes optional plugin packs
  with `"enabled": false` at install time. Enabling a plugin is always your
  explicit, local decision.
- Interrupted assembly (this package was produced incompletely): no
  `SNAPSHOT.json.sha256` marker will exist; run `python verify_snapshot.py`
  before trusting any received folder, and discard folders that fail.
- Interrupted install: per-file writes are atomic and the ownership record is
  written last; re-run the same command with `--dry-run` to see the remaining
  work, then without it. Nothing is deleted by install, update, or any failure
  path.

## 5. Rights and assurance boundary

Read this before any distribution-adjacent step, including section 6.

- Redistribution rights for this package's contents are **not established** by
  this package, and third-party provenance of included material has not been
  cleared. Resolving rights is a human/legal task for the people who own the
  source project; nothing here substitutes for that resolution.
- No license text is included, and none is implied. The absence of a license
  file is deliberate, not an oversight.
- Compliance-related agents, plugins and examples in the workflow are
  illustrative tooling, **not** certification, accreditation, or regulatory
  sign-off of anything you build with them.
- The assembly-time secret screen and any redaction conventions are heuristic;
  they are **not** complete PII or secret protection, and they do not replace
  your own review of what you commit or share.
- All examples in this document are synthetic. Deterministic checks (digest
  verification, installer dry-runs, unit-style exercises) do not prove live
  LLM/host behavior or regulatory outcomes; checks that were skipped or
  unavailable must be reported as such, never as passes.

## 6. Repository preparation

Make this folder a **local** repository (no remote, no publication — see
section 5 first). Work on a disposable copy if you are experimenting.

1. `git init`
2. `git status` — confirm the staging inventory shows the hidden asset
   directories `.specify/` and `.github/` plus the two metadata files
   [SNAPSHOT.json](SNAPSHOT.json) and `SNAPSHOT.json.sha256`. If hidden entries
   are missing, your copy step dropped them; re-copy including hidden files.
3. Optionally add a `.gitignore` for your own scratch files (the package itself
   needs no ignores).
4. `git add -A`
5. `git commit -m "Import Spec Kit Flow portable snapshot <label>"` — one local
   commit; creating remotes or publishing is out of scope for this document and
   gated on section 5.

Windows long-path note: some installed paths are deep; if Git reports path
errors, enable long paths (`git config core.longpaths true`, and the Windows
`LongPathsEnabled` policy if needed).
