# Bootstrap CLI Contract

## Install

`python scripts/speckit_bootstrap.py install --target <project-path> [--dry-run]`

- Resolves the bundle source relative to the script, not the current working directory.
- Rejects a missing target, source/destination paths that escape their respective roots, symlink traversal, and unsafe relative paths.
- Prints each planned action (`create`, `unchanged`, `conflict`) and exits non-zero if any conflict prevents a complete install.
- Does not modify conflicting files.
- Creates the installation manifest only after a successful install.
- Directory entries require explicit `include` file lists; recursive copying is not supported.
- Rejects overlapping source/target roots, destination aliases and file/directory collisions before writes.

## Update

`python scripts/speckit_bootstrap.py update --target <project-path> [--dry-run]`

- Updates unchanged installer-owned files from the current bundle.
- Preserves existing seed configuration, templates and optional plugins; these become project-owned after install.
- Leaves locally modified, removed, or conflicting files untouched and reports them.
- Does not remove files merely because they are absent from a newer bundle.
- Updates the ownership manifest only after successful writes.
- Identical preexisting files are not claimed as installer-owned.
- All detected conflicts prevent every planned write, including the ownership manifest.

## Doctor

After installation, run `python -m speckit_flow doctor` from the target project.
The installed workflow's existing validation commands remain the authoritative
check for profiles, agents, sensors, plugins, rules, hooks and workflow wiring.
