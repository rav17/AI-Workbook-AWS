# Shared Architecture View Change Proposal

Use this record before changing a solution-wide baseline view. Use synthetic
examples only; do not include customer data or secrets. Do not infer the owner,
review outcome, or approval.

- Affected baseline view: [verified repository-relative path]
- Rationale: [why a shared-view change is proposed]
- Expected impact on other feature views or features: [known impacts and any
  unknowns requiring review]
- Designated architecture owner: [identity and role]
- Review outcome: [pending / rejected / conditional / explicitly approved]
- Conditions, if conditional: [each condition, or not applicable]
- Evidence each condition is satisfied: [evidence per condition, or not
  applicable; leave unsatisfied conditions explicit]
- Subsequent explicit owner approval: [owner identity and role, recorded
  date/time with timezone, and explicit approval after all conditions are
  evidenced as satisfied; otherwise not recorded]

## Application decision

Pending, rejected, and conditional outcomes block application. Recording that
conditions are satisfied does not itself approve the change. Apply the shared
view only after the designated architecture owner records explicit approval,
after all conditional requirements have been evidenced as satisfied. Structural
XML/graph validation is not authorization. If approval is absent or the outcome
is unclear, do not apply the proposed change.
