# Feature Specification: Walking-Skeleton Checkpoint

**Created**: 2026-11-10
**Status**: Draft
**Input**: Add a reusable opt-in checkpoint proving a minimal end-to-end slice before full implementation.

## User Scenarios & Testing

### User Story 1 - Prove the thin slice first (Priority: P1)

A developer implements one small journey crossing the planned entry, application
and output boundaries, verifies its observable result, and stops before expanding.

**Why this priority**: Early integration evidence reduces late discovery of a
design that cannot work end to end.

**Independent Test**: A small unrelated project exercises its real entry point
with known input and verifies the exact output via an approved check.

**Acceptance Scenarios**:
1. Given the optional route, when tasks finish, then a developer-led skeleton
   stage precedes full implementation and requires a human decision.
2. Given a defined minimal journey, when its approved verification passes, then
   a checkpoint records command identity and the declared files' fingerprints.
3. Given missing, failed, unapproved or stale evidence, when approval is
   attempted, then the skeleton gate remains blocked.

### User Story 2 - Keep evidence honest and current (Priority: P2)

A reviewer needs a journey report, implementation/test evidence and explicit
limitations rather than a passing command being called proof of everything.

**Why this priority**: A trivial passing check does not prove a meaningful slice.

**Independent Test**: Change source, tests, journey report or verification command;
approval fails until current evidence is captured and the command reapproved if needed.

**Acceptance Scenarios**:
1. Given a failed recheck after an earlier pass, then the older pass cannot
   authorize the gate.
2. Given a report with mocked boundaries, then guidance requires labeling them
   and human judgment of whether the slice satisfies the plan.
3. Given a successful skeleton, then subsequent full implementation can add
   construction units without destroying its recorded checkpoint.

### User Story 3 - Adopt without changing defaults (Priority: P3)

A team opts into the capability in any project without inherited domain rules.

**Why this priority**: Workflow portability is required.

**Independent Test**: Install the toolkit into a non-banking fixture, enable only
the pack, complete its checkpoint/gate and start full implementation.

**Acceptance Scenarios**:
1. Disabled installation leaves core stage counts/profiles unchanged.
2. Enabled profile uses existing developer/quality agents, approved verification,
   audit and human gates; no deployment or live services are required.

### Edge Cases
- Missing/unknown tasks, absent tracked files, path traversal and symlinks.
- Failed/timeout checks, files modified during checks, command changes.
- A new construction unit added after an earlier checkpoint.
- A thin slice using stubs or requiring live infrastructure: no automatic access.

## Requirements

### Functional Requirements
- **FR-001**: Provide a disabled optional stage between tasks and full implementation,
  led by the developer, with quality support and a human gate in its opt-in route.
- **FR-002**: Reuse construction units and human-approved verification commands;
  require a dedicated skeleton unit linked to actual feature tasks and a journey
  report plus explicitly tracked implementation and test evidence.
- **FR-003**: Capture content fingerprints of declared files and verification
  command identity on passing checks. Missing/changed files, changed/unapproved
  commands, failed rechecks or edits during verification MUST block approval.
- **FR-004**: The gate MUST require passing current skeleton evidence; only a human
  decides whether it proves the end-to-end journey. Agents MUST NOT approve.
- **FR-005**: Guidance MUST define scope, input/output, boundaries, observable
  acceptance, tests, mocks and limitations. Do not equate any passing command
  with complete architectural validation.
- **FR-006**: Adding later units MUST preserve earlier checkpoints; existing
  untracked-unit behavior and default workflows MUST otherwise remain compatible.
- **FR-007**: Tracked-file capture MUST be local, bounded, root-relative and reject
  escaping paths, symlink traversal, non-files and access failures explicitly.
- **FR-008**: Include pack, guidance and engine changes in portable installation,
  disabled by default; no source-project test commands, domain rules, live checks
  or verification approvals may be inherited.

### Key Entities
- Skeleton unit: named construction unit linked to journey tasks and declared files.
- Journey report: scope, boundaries, acceptance, evidence and limitations.
- Source-bound checkpoint: passing approved command plus file fingerprints.

## Success Criteria
- **SC-001**: A non-banking fixture verifies exact end-to-end output before full implementation starts.
- **SC-002**: Every tested missing/stale/failed/unapproved case blocks the skeleton decision.
- **SC-003**: Later unit additions preserve prior checkpoint evidence.
- **SC-004**: Default profiles/stages and disabled installation remain unchanged.

## Assumptions
- Fingerprints cover declared files only; humans assess coverage and mocked boundaries.
- This is a workflow capability, not a skeleton application generator or deployment.
- The receiving project chooses and approves its verification command.
