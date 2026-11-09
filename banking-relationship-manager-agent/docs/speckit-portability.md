# Reuse the Spec Kit workflow in another project

This repository contains an application and a reusable Spec Kit workflow. To use
the workflow in another repository, install only its allow-listed workflow files;
do not copy the repository as a whole.

## Prerequisites

- An existing target project using GitHub Copilot and Spec Kit.
- Python 3.11 or newer.
- PowerShell support for the Spec Kit scripts (`powershell` on Windows or
  PowerShell Core on other platforms).
- A clone of this repository containing the bootstrap script.

## Install

Run these commands from this workflow source repository, with the target
directory already created:

```powershell
python scripts/speckit_bootstrap.py install --target "C:\path\to\target-project" --dry-run
python scripts/speckit_bootstrap.py install --target "C:\path\to\target-project"
```

Use the equivalent quoted path on macOS/Linux. Review the dry-run, then inspect
the target's `git diff` before using the workflow. The installer reports all
conflicting destination files before it writes anything. It never replaces a
different existing file during installation.

The installer adds `.specify/feature.json` only if absent, pointing to the next
available sequential `specs/NNN-new-feature` path. It does not create that
feature directory. The Spec Kit specify workflow updates the pointer when the
first real feature is created.

## What's included

The bundle includes the lifecycle engine, Spec Kit skills, conductor and agent
definitions, stage/profile/rule/sensor data, hooks, workflow integration,
templates, docs, and optional example plugin packs. The portable agent roster
leaves AWS-platform and compliance specialists available but not auto-dispatched;
add their stage support only when relevant to the receiving project. These are the reusable
AI-DLC-inspired capabilities: lifecycle stages, profiles, agents, human gates,
reviews, audit/state, rules, knowledge support, sensors, units, verification,
and optional plugins.

Optional plugin packs are installed disabled. Before enabling one, review its
guidance and confirm its required agents are listed in the conductor.
Source-project plugin enablement is not inherited. Source-project learned rules
are not exported; the target starts with an empty project-rules file. Directory
entries in the bundle enumerate exact files, so unrelated agents, skills, hooks,
profiles or plugins added to the source repository are not automatically copied.

The optional `codebase-analysis` pack is included with its scanner and
`speckit-codebase` skill. In a receiving project, explicitly enable the pack to
use the architect-led `brownfield` route. Tooling-only projects automatically
skip its analysis stage with an audited reason; recognized application code
runs it. See [analysis scope and limits](./speckit-profiles.md#optional-existing-codebase-analysis).
No banking assumptions, project tests or approval decisions are carried over.

The `operational-readiness` pack is also included disabled, with its templates,
structural sensor and `speckit-readiness` skill. A receiving project can opt
into `release-ready` to require evidence-backed release/runbook records at the
existing deploy/operate human gates. It performs no deployment or live checks
and does not certify evidence truth. See
[operational readiness](./speckit-profiles.md#optional-operational-readiness).
Installed plugin files remain project-owned seeds on update.

The disabled `walking-skeleton` pack and `speckit-skeleton` skill add an optional
thin-journey checkpoint before full implementation. It reuses receiving-project
verification approval, existing construction units, developer/quality agents
and human gates. Tracked-file checkpoints are portable; no source-project test
command or preapproved verify policy is installed. See
[walking skeleton](./speckit-profiles.md#optional-walking-skeleton-checkpoint).

## What's deliberately excluded

The installer does not copy application code, `.specify/memory/constitution.md`,
banking knowledge, project tests, `pyproject.toml`, repository-specific command
sensors, `.specify/feature.json`, or a pre-approved verify command. The target
project supplies its own constitution, knowledge, test/build command and
verification approval. The installer's allowlist is in
`scripts/speckit-portable-bundle.json`.

## Configure and validate

From the target project:

```powershell
specify integration use copilot
python -m speckit_flow doctor
python -m speckit_flow profiles validate
python -m speckit_flow plugins validate
```

Create a project-specific constitution and customize profiles, stages, agents,
rules, sensors and knowledge using the documented `.specify/custom/` and plugin
mechanisms. Propose the project's actual check command with
`python -m speckit_flow verify propose --actor agent:developer -- <command>`;
a human must approve it before it can run at construction checkpoints. Never reuse a verification command from
this repository without reviewing it.

## Update

From a newer workflow source checkout, run:

```powershell
python scripts/speckit_bootstrap.py update --target "C:\path\to\target-project" --dry-run
python scripts/speckit_bootstrap.py update --target "C:\path\to\target-project"
```

The installed `.specify/speckit-portable-manifest.json` records the files and
hashes last installed by the tool:

- Shared engine, skills, agents, hooks and scripts update only when their content
  still matches the previous installed hash.
- Seed configuration (profiles, roster, stages, rules, sensors, initialization
  settings), templates and plugins become project-owned. Existing seed files
  are preserved on update, even if new bundle defaults differ.
- Identical files already present before installation are not claimed as shared
  files. A later differing shared version is reported as a conflict.
- Locally modified or deleted shared files are reported as conflicts. No files
  are written when preflight finds any conflict. Files removed from a newer
  bundle are not deleted in the target.

Resolve shared-file conflicts manually, then rerun the update. To accept an
upstream shared-file version, compare it and explicitly copy its content to the
target; the next update records the accepted hash. Review new seed defaults
separately rather than overwriting local policy. Do not edit the ownership
manifest to bypass conflicts. Source and target directories must not overlap.

## Validation evidence and boundaries

The automated acceptance test installs into an isolated non-banking Git
repository and completes the CLI lifecycle: specify, plan, tasks and implement.
It writes sample reading-list requirements/design/tasks, implements a small
function, runs standard-library tests through a verification command, records
a construction-unit checkpoint and verifies the final state and audit chain.
It also tests missing sensor results and agent approvals being refused.

Human decisions are simulated only in this disposable test fixture; no real
project gate or verification command is approved by the installer. This is a
deterministic CLI acceptance test, not a live Copilot/LLM skill-generation test.
The existing workflow-engine integration test requires `specify_cli`; when that
module is unavailable, pytest reports its skip explicitly.
