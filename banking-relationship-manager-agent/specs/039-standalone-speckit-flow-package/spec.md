# Feature Specification: Standalone Spec Kit Flow Package

**Feature Branch**: Not created or changed by this stage; allocated feature `039-standalone-speckit-flow-package`.

**Created**: 2026-11-16

**Status**: Draft — requirements only; human approval pending.

**Input**: Create a self-contained, commit-ready standalone folder containing the portable Spec Kit / `speckit_flow` installer and allow-listed assets from the confirmed CURRENT WORKING TREE snapshot. Preserve the source and document contents, prerequisites, installation, integration, validation, updates, and later initialization/commit as a separate repository. Proposed destination: `C:\Users\RavindraYadav\Documents\speckit-flow-portable`, outside the existing checkout.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Obtain an independent workflow-source package (Priority: P1)

As a workflow maintainer, I want a complete, bounded copy of the portable workflow so I can maintain it independently without copying the banking application or depending on the original checkout.

**Why this priority**: An incomplete or application-coupled export cannot serve as the requested standalone repository.

**Independent Test**: Compare the assembled folder with its declared snapshot inventory, make the original checkout unavailable to the test, and inspect package contents and installer availability. No consumer installation or repository initialization is needed for this inventory test.

**Acceptance Scenarios**:

1. **Given** the approved working-tree snapshot, **When** the standalone folder is assembled in later implementation, **Then** it contains every explicitly allow-listed source file, the installer, the bundle manifest, and explicitly inventoried package-only documentation/metadata, with no unrelated source-project content.
2. **Given** portable seeds whose source locations differ from their installed locations, **When** the standalone folder is inspected, **Then** the source layout required by its installer is intact; the folder is an installer source, not a pre-installed consumer project.
3. **Given** selected files have uncommitted changes, **When** their packaged copies are compared, **Then** those copies match the approved working-tree bytes rather than an older committed revision, and assembly has not changed source files or source Git state.
4. **Given** the output path already contains files or overlaps the original checkout, **When** assembly is requested, **Then** it stops with an actionable explanation without overwriting existing content or modifying the source.

---

### User Story 2 - Install into a different project safely (Priority: P1)

As a receiving-project developer, I want to preview and install the workflow from the standalone folder so I can adopt it without access to the banking repository or damage to my project's files.

**Why this priority**: The exported assets are useful only if the existing portable installation contract still works independently.

**Independent Test**: With only the standalone folder and documented prerequisites available, invoke its installer by an explicit path while the current directory is elsewhere, using a disposable existing non-banking target.

**Acceptance Scenarios**:

1. **Given** a separate existing target and an unrelated current directory, **When** the documented dry-run command is invoked using a quoted standalone installer path, **Then** it reports intended actions and leaves source, package, and target files unchanged, including installation metadata and feature pointers.
2. **Given** a compatible clean target, **When** installation runs, **Then** it installs the declared consumer assets and ownership record, preserves unrelated target files and any existing feature pointer, and requires no files from the original checkout.
3. **Given** multiple differing destination files, **When** installation is attempted, **Then** all detected content conflicts are identified before any target writes; a non-success status and textual explanation distinguish conflicts from success.
4. **Given** installed assets and the stated integration prerequisites, **When** the developer follows the integration and validation guide, **Then** engine health, profile validation and plugin validation can be checked without importing application code or source-project approvals.
5. **Given** a target without a feature pointer, **When** installation succeeds, **Then** it creates only a receiving-project pointer using the existing next-sequential-feature convention, not a feature directory or a copied source pointer.

---

### User Story 3 - Update without surrendering project ownership (Priority: P2)

As a receiving-project maintainer, I want predictable updates that protect local policy and edits so that adopting a newer standalone snapshot does not silently replace my work.

**Why this priority**: Safe ongoing use requires the same ownership protections as the existing portable installer.

**Independent Test**: Use two isolated workflow-source fixtures and an installed disposable target with both local seed changes and modified shared files. Verify preview, conflict and successful-update cases.

**Acceptance Scenarios**:

1. **Given** a newer shared asset and an unchanged previously owned target copy, **When** update succeeds, **Then** the shared asset advances and the ownership record reflects it, while existing project-owned seeds and unrelated files remain unchanged.
2. **Given** a modified or deleted previously installed shared file, **When** update runs, **Then** it reports the conflict and writes no target files; documentation explains comparison, manual resolution and retry without bypassing the ownership record.
3. **Given** a file that was identical before installation but was not claimed as shared, **When** a later bundle changes that file, **Then** update reports a conflict rather than silently taking ownership.
4. **Given** an asset removed from a newer bundle, **When** update runs, **Then** the target's existing copy is not silently deleted.
5. **Given** local seed customizations, **When** an update is previewed, **Then** existing seed files are preserved and the guide explains how to compare new defaults separately.

---

### User Story 4 - Understand, validate and prepare a separate repository (Priority: P2)

As a developer receiving the folder, I want one portable-first entry point so I can understand what I received, operate it safely, and later initialize and commit it without consulting the banking application.

**Why this priority**: The current portability guide assumes the application checkout; independent ownership requires a different starting point.

**Independent Test**: Have a developer follow only the standalone entry documentation in an isolated local exercise, checking every documented step and local reference. Any initialization/commit demonstration occurs only in a disposable copy during later validation.

**Acceptance Scenarios**:

1. **Given** only the standalone folder, **When** the developer opens its entry documentation, **Then** they can find contents/exclusions, prerequisites, install preview/install, integration, validation, update, conflict recovery, and separate repository initialization/commit guidance.
2. **Given** a developer ready to version the folder, **When** they follow the preparation guidance, **Then** they can inspect the complete intended inventory, check for sensitive or generated files, and initialize/stage/commit locally without copying the original `.git` history, selecting a remote, publishing, or implying redistribution permission.
3. **Given** no established redistribution license, **When** the developer reads repository preparation guidance, **Then** the unresolved ownership/third-party rights limitation is visible before any external distribution guidance; no license or certification is invented.
4. **Given** limited host capabilities or unavailable optional tooling, **When** validation is documented or reported, **Then** deterministic checks, skipped/unavailable checks and unverified live-host behavior are distinguished explicitly.

### Edge Cases

- Assembly destination is non-empty, equals the original checkout, or is an ancestor/descendant of it: refuse before copying; do not clean or merge an existing folder.
- An allow-listed file is missing, unreadable, or differs from the captured snapshot inventory record: identify each affected file as drift from the named snapshot rather than silently omitting it; the result is not described or labeled as that snapshot.
- Assembly is interrupted or encounters a filesystem error after copying starts: a partial package may remain; assembly makes no rollback claim and does not delete anything already written. Report the failure and incompleteness in plain text; the partial result is never presented as the named snapshot, and incompleteness is confirmable by comparison against the snapshot inventory record. Recovery is user-directed per FR-001/FR-015; a rerun against the partial destination triggers the existing non-empty-destination refusal.
- Installer source and consumer target are equal or overlap in either direction, including resolved aliases: reject without target writes.
- Consumer target does not exist, manifest is invalid, an included asset is missing, a path escapes its root, a path traverses a symlink, or destinations collide: retain installer rejection behavior and identify the failure.
- Paths contain spaces or invocation occurs outside the standalone folder: documented commands remain usable with quoted explicit paths.
- Repeated install, update before install, or malformed ownership records: report the appropriate corrective action rather than resetting ownership.
- A seed exists versus a new seed is introduced: preserve the existing file; allow installation of an absent new seed under the existing ownership contract. Do not promise recreation of previously installed deleted files.
- Interruption or filesystem failure after writes begin: do not claim whole-operation rollback. Explain that conflict preflight is not a transaction guarantee and document inspection/recovery precautions.
- Existing project instructions, constitution, feature pointer, knowledge and verification decisions: do not overwrite or import source versions.
- Optional plugin examples, redacted audit output or synthetic checks: do not present them as regulatory certification, complete PII assurance, actual-host safety proof or accessibility certification.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001 — Bounded independent deliverable**: The deliverable MUST be a standalone workflow-source folder outside the original checkout, at the confirmed proposed destination unless the human changes it. Assembly MUST refuse non-empty or source-overlapping destinations without writing into them. It MUST NOT initialize Git, commit, create a remote or publish anything automatically. If a filesystem error or interruption occurs after copying starts, a partial package may remain: assembly MUST NOT claim rollback and MUST NOT delete anything already written or any other destination contents. It MUST report in plain text what failed, that the destination is incomplete and must not be treated as the named snapshot, and that incompleteness can be confirmed by comparing the destination against the snapshot inventory record, so an incomplete package cannot silently enter later use. Recovery is user-directed: the developer inspects the partial destination and removes or relocates it themselves, or chooses a different empty destination, before rerunning; assembly never merges into or cleans a non-empty destination, so the refusal above applies equally to partial results (recovery guidance in FR-015). Acceptance: Story 1.4, Story 4.2 and the interrupted-assembly edge case.
- **FR-002 — Snapshot fidelity**: Every copied portable source asset MUST match its approved current-working-tree snapshot, including uncommitted versions; no substitution from repository history is permitted. At capture, the snapshot MUST be assigned a human-readable snapshot identifier (unique label, capture timestamp and capturing human/invocation reference) and a snapshot inventory record listing every captured file path — all allow-listed paths plus the two packaging entry points — each with a per-file content identity (a technology-neutral, collision-resistant digest recomputable by a third party). The identifier and inventory record MUST be delivered inside the package so the receiving developer can verify fidelity without the original checkout. Verification is two-sided: before assembly, the developer can inspect the captured inventory and confirm it reflects the approved working tree; after assembly, packaged files are compared against that inventory. A failing comparison MUST identify each differing or missing file as drift from the named snapshot, and the result MUST NOT be described or labeled as that snapshot once any discrepancy is found. Acceptance: Story 1.1–1.3 and the missing/drifted-source edge case.
- **FR-003 — Complete source closure**: The folder MUST include `scripts/speckit_bootstrap.py`, `scripts/speckit-portable-bundle.json`, and every source file explicitly selected by that manifest, preserving the installer-required source paths, including portable seed inputs. The installer and manifest are packaging entry points even though they are not currently consumer bundle entries. Acceptance: Story 1.1–1.2 and Story 2.1–2.2.
- **FR-004 — Explicit inclusion boundary**: Every delivered file MUST be attributable either to the captured allowlist, the two packaging entry points, or explicitly inventoried standalone documentation/metadata; the snapshot identifier and snapshot inventory record (FR-002) are part of that package-only metadata, and captured content itself remains subject to this requirement's no-credentials/no-customer-data boundary. The folder MUST exclude unrelated application/infrastructure code, application dependency manifests, original Git history, source constitution, banking knowledge, source project tests, feature artifacts, runtime state, sessions, audits, approvals, credentials and customer data. Source attribution notices in selected assets MUST be preserved. Acceptance: Story 1.1 and Story 4.2.
- **FR-005 — Preserve source**: Package assembly and consumer installation/update MUST NOT change original source files, branch, pointer, index or commits. The copied portable assets MUST NOT be rewritten to remove branding or manufacture domain neutrality; portable-first guidance MUST instead distinguish reusable tooling from source-specific examples. Acceptance: Story 1.3 and Story 2.1.
- **FR-006 — Independent invocation**: The packaged installer MUST support install, update and their dry-run modes using only packaged assets and documented prerequisites, when invoked by explicit path from another working directory. It MUST reject missing or overlapping consumer targets. Acceptance: Stories 2 and 3; path/overlap edge cases.
- **FR-007 — Preview and conflict safety**: Dry-run MUST perform no filesystem writes. Install/update MUST detect and report destination content conflicts before any writes when conflicts are present. Statuses MUST be readable as text without relying on color and distinguish success, conflict and invalid-operation failures. Acceptance: Story 2.1, Story 2.3 and Story 3.2.
- **FR-008 — Receiving-project ownership**: Installation MUST preserve unrelated files, existing receiving-project instructions and feature pointer. It MUST create the existing ownership record and, only when absent, the receiving-project feature pointer without creating a feature directory. It MUST NOT install a source constitution, source decisions or a pre-approved verification command. Acceptance: Story 2.2, Story 2.4–2.5.
- **FR-009 — Safe update contract**: Updates MUST replace shared assets only under the existing recorded-ownership/content-match rules, preserve existing project-owned seeds, report locally modified/deleted shared files and unowned differing files as conflicts, and not delete files removed from the bundle. Acceptance: Story 3.1–3.5.
- **FR-010 — Neutral defaults and authority**: Consumer installations MUST use the manifest's portable seeds, empty project learned-rules default, and disabled optional plugin defaults; they MUST NOT inherit source enablement, source worker confirmations, banking policy, gates or verification approvals. AWS/compliance specialists may be available but MUST NOT be made automatic project requirements by packaging. Acceptance: Story 2.4, with installed seed/default inspection.
- **FR-011 — Portable-first documentation**: A root entry document MUST explain the folder as a standalone installer source, distinguish it from a separate existing consumer target, and cover contents/exclusions, snapshot provenance — surfacing the named snapshot identifier and where to find the snapshot inventory record — prerequisites, installation preview/install, integration, validation, updates and safe recovery. All local documentation links needed for these journeys MUST resolve within the package. Acceptance: Story 4.1.
- **FR-012 — Honest prerequisites and validation**: Documentation MUST separate prerequisites for running the installer from those for Spec Kit scripts, integration and live host workflows. It MUST identify supported prerequisite versions grounded in the existing contract, state that self-contained assets do not bundle external tools, and provide repeatable health/profile/plugin validation steps with expected results and failure interpretation. Reports MUST identify unavailable/skipped checks and distinguish deterministic validation from real Copilot/LLM behavior. Acceptance: Story 2.4 and Story 4.4.
- **FR-013 — Repository preparation**: Documentation MUST provide ordered local initialization, inspection, staging and first-commit guidance for the standalone folder, including checking intended hidden assets and excluding generated files/secrets. These instructions MUST NOT execute as part of packaging or require copying source history or creating a remote. Acceptance: Story 4.2.
- **FR-014 — Rights and assurance boundary**: Documentation MUST state that redistribution rights and third-party provenance have not been established, require appropriate human resolution before external distribution, and avoid inventing a license or implying public-release authorization. Examples MUST be synthetic; optional compliance examples MUST NOT imply certification, and audit redaction MUST NOT be described as complete PII protection. Acceptance: Story 4.3 and the assurance edge case.
- **FR-015 — Recovery guidance**: Documentation MUST explain backup/diff inspection before writes, manual comparison/resolution of shared-file conflicts, separate review of new seed defaults, and precautions following interrupted writes — both interrupted assembly (inspect the partial destination against the snapshot inventory record, then remove/relocate it yourself or choose a different empty destination before rerunning, per FR-001) and interrupted consumer installs/updates. It MUST NOT recommend bypassing ownership protection, promise automatic all-or-nothing rollback, or instruct automated cleanup of user data. Acceptance: Story 3.2, Story 3.5 and the interruption edge cases.

### Key Entities *(include if feature involves data)*

- **Approved source snapshot**: The working-tree versions authorized for copying, distinct from a Git commit; named by a snapshot identifier (unique label, capture timestamp, capture reference) and described by a snapshot inventory record listing every captured path with per-file content identity. Both are delivered inside the package so drift is detectable without the original checkout.
- **Standalone workflow-source folder**: The independently usable installer source, containing the captured selected assets, entry points and explicitly inventoried package-only documentation/metadata.
- **Bundle manifest**: The existing explicit consumer allowlist, relating source paths to destination paths, categories, version and seed ownership. It is not by itself the complete standalone packaging inventory.
- **Consumer project**: A separate existing non-overlapping installation target retaining its own constitution, code, knowledge, decisions and project customizations.
- **Installed ownership record**: The receiving project's existing record of installed bundle version and owned file content identities, used to distinguish replaceable shared assets from conflicts.
- **Project-owned seed**: A portable initial default that becomes receiving-project policy/configuration; an existing seed is preserved on update.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001 — Complete bounded package**: Inventory checks performed against the captured snapshot inventory record (not the live source tree, which may have changed since capture) account for 100% of selected assets and packaging entry points, find zero unexplained delivered files, zero prohibited source-project artifacts and zero content-identity differences between packaged copies and the inventory record for the named snapshot identifier. Fidelity claims attach only to an assembly run that completes this inventory verification; any discrepancy is reported per file as drift and the result is not labeled as that snapshot.
- **SC-002 — Independent adoption**: With the original checkout unavailable and the current directory outside the package, a developer completes preview, clean installation, integration and all three documented health/profile/plugin checks in one isolated non-banking target using only the standalone guide and stated prerequisites, without undocumented source access.
- **SC-003 — No collateral changes**: In all dry-run and preflight-conflict acceptance cases, there are zero target filesystem changes; across assembly and consumer exercises, there are zero original source-file or Git-state changes. A successful install preserves 100% of unrelated target files and pre-existing project pointers.
- **SC-004 — Safe maintenance**: Every update acceptance case has the specified result: eligible shared files advance, existing seeds and unrelated files remain unchanged, modified/deleted/unowned shared conflicts prevent all writes, and removed upstream files are not deleted.
- **SC-005 — Usable handover**: One developer completes the contents/prerequisites, installation/integration/validation, update/recovery and local repository-preparation walkthroughs in an isolated exercise without needing the application guide or undocumented steps; all required local links resolve and all failure/status meanings remain understandable without color.
- **SC-006 — Accurate boundaries**: The entry documentation explicitly states every rights, external-prerequisite, project-policy and validation limitation in FR-010–FR-014; validation reporting contains zero claims that skipped checks, simulated human decisions or synthetic checks prove live-host operation or regulatory compliance.

## Assumptions

- The human confirmed the delegated `feature` profile, current-working-tree copying, source preservation and human gates after specify and plan. This invocation writes specifications only; assembly, plan, test execution, Git initialization, commits and publication are not authorized here.
- The proposed destination is the intended output location. It is not a consumer target. A later assembly preflight must check availability; this specification does not claim that folder exists or is empty.
- A snapshot is content-based, not a claim that the current Git commit includes all selected versions. This stage has not captured a complete byte-level snapshot. Later capture must assign the snapshot identifier, produce the snapshot inventory record (FR-002), and disclose drift relative to the approved source rather than silently refreshing it.
- The existing manifest and installer define the portable contract; this feature packages them rather than redesigning the workflow engine, adding profiles, changing gates, or introducing a new distribution service/package registry.
- New package-only material is limited to documentation and metadata necessary for independent use, inventory and clean repository preparation. A root portable-first entry point supplements the byte-preserved bundled guide; the banking application README and dependency files are not reused.
- Self-contained means no dependency on the original checkout for workflow assets. Users still supply Python 3.11+, PowerShell for relevant scripts, Git for their later repository work, and Spec Kit/Copilot/host capabilities for integration as documented. No external tools, accounts or host capabilities are implicitly provisioned.
- Local preparation is not public distribution. No LICENSE/NOTICE/COPYING or explicit redistribution grant has been established by the supplied compliance evidence; this is a documented limitation, not permission to choose a license or a blocker to specifying local packaging.
- Domain-specific policy in `.specify/memory/constitution.md` applies to Aria, not future consumers. Relevant safeguards here are source preservation, no secrets/customer data, explicit evidence limits and human-controlled decisions; banking-service controls are not exported.
- This is not the `full-lifecycle` route, so the route-specific system-context diagram is not required. No optional conceptual sketch is needed to settle this scope.

### Evidence and Settled Scope

- **Human invocation brief (2026-11-16)**: approved current-working-tree versions, proposed external destination, delegated feature profile, source preservation, specification-only scope and no Git/publication actions.
- **`scripts/speckit-portable-bundle.json`, `files` and `bundle_version`**: current explicit allowlist, portable source-to-destination mappings and seed classifications; version observed `1.1.0`. Installer and manifest themselves are additional packaging entry points.
- **`scripts/speckit_bootstrap.py`, `ROOT`, `_collect_bundle`, `apply_bundle`, `main`**: source-root resolution independent of working directory, exact includes, disabled installed plugins, overlap rejection, dry-run/conflict behavior, ownership/seed updates and textual statuses. Per-file writes do not establish whole-operation rollback.
- **`docs/speckit-portability.md`, Prerequisites / What's included / What's deliberately excluded / Configure and validate / Update / Validation evidence and boundaries**: supported prerequisites, receiving-project responsibility, consumer installation/update contract and limits of existing evidence. Existing source-app-oriented entry commands motivate standalone-first documentation.
- **`docs/speckit-profiles.md`, Document-grounded clarification and project practices**: reuse confirmed decisions and disclose uncertain evidence rather than reopening settled scope.
- **`.specify/memory/constitution.md`, Governance; `.specify/knowledge/banking-compliance.md`**: application-policy applicability considered; do not transplant banking policy, customer data or secrets.
- **Supplied design/compliance contributions**: integrated through source-versus-consumer separation, installer closure, safe updates, portable-first documentation, non-color statuses and rights/assurance boundaries. Contributions were text only, not independent review evidence.
