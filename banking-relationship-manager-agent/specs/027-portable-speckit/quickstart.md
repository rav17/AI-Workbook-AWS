# Quickstart: Use Spec Kit in Another Project

## Prerequisites

- A GitHub Copilot project with the Spec Kit CLI/integration available.
- Python 3.11 or newer.
- A clone of this repository containing the portable setup command.
- A clean Git working tree or a review of the installer's dry-run output.

## Install

From the workflow source repository, run:

```powershell
python scripts/speckit_bootstrap.py install --target "C:\path\to\your-project" --dry-run
python scripts/speckit_bootstrap.py install --target "C:\path\to\your-project"
```

Use the equivalent quoted path on macOS/Linux. Review the created files in the
target project before using the workflow.

## Configure the target project

1. Review the portable constitution template and write project-owned principles;
   do not copy this repository's Aria constitution.
2. Set the Copilot integration in the target project and initialize the active
   feature pointer.
3. Configure project-specific profiles, stages, agents, rules, sensors and
   knowledge in their supported `.specify/` locations.
   The portable roster keeps AWS-platform and compliance specialists available
   but not auto-dispatched; add their stage support only when relevant.
4. Propose the project's actual test/build command with
   `python -m speckit_flow verify propose --actor agent:developer -- <command>`,
   then have a human approve it. Do not approve a command copied from another project.
5. If enabling an optional plugin, follow its README and add any extra agent to
   the conductor before running `doctor`.

## Validate

```powershell
python -m speckit_flow doctor
python -m speckit_flow profiles validate
python -m speckit_flow plugins validate
```

Initialize a disposable feature and run the neutral specify/plan/tasks/implement path
before adopting it for production work. Inspect `git diff` to confirm that no
application files or project-owned configuration were replaced.

## Update

Run the bootstrap `update` command from the newer workflow source checkout. It
updates only files unchanged since the previous installation and reports local
modifications as conflicts for human resolution.
Existing seed configuration, templates and plugins are preserved rather than
updated automatically. See the portability guide for conflict-resolution steps
and CLI acceptance-test boundaries.
