# Research

- Decision: Reuse construction units/verify; optional stage rather than another
  parallel checkpoint system. Existing units already persist command identity
  and audit but lack source binding; optional tracked files fill that gap.
- Decision: Add-on stage after analyze before implement; no core count changes.
  Requires tasks so routes cannot omit planning of the slice.
- Decision: Preserve existing checkpoints on `add_unit`; its current write
  replaces them, which would erase the skeleton when later units are added.
- Decision: A reserved unit and profile-scoped sensor enforce a meaningful
  structural minimum; humans assess actual end-to-end coverage. Reject any
  claim that a passing command proves all architecture.
- Rejected: Always-on skeletons, deployment, fixed source-project test commands
  and inferred all-repository fingerprinting. They harm portability or scope.
