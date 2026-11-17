# Clarifying Questions

## Q1 [role: product]
Which analyst role or authorization should be represented as the approver for the mock case-task in owner-approved test fixtures?

**Answer:** Use mock role receivables_operations_analyst as approver for owner-approved synthetic mock case-task fixtures only. This is not production authorization or approval of any stage gate.

## Q2 [role: product]
Who will supply and approve the applicable versioned operating procedure and matching, confidence, eligibility, and tolerance policy for this feature?

**Answer:** Actual human decision: I will review and approve the proposed synthetic policy, fixtures and labelled evaluation set at the plan gate. Proposed synthetic-only versioned rules may be authored for that review; no not-yet-authored policy values or real owner/production policy are approved now.

## Q3 [role: product]
Who will approve the synthetic fixtures and the exact boundary for the synthetic mock case-task write?

**Answer:** Actual human scope decision: Create-only in isolated test/demo storage; idempotent retries. The user will review and approve the proposed synthetic policy, fixtures and labelled evaluation set at the plan gate. This approves the mock-write scope only, not unreviewed fixture contents, construction commands, production permissions or financial writes.

## Q4 [role: product]
Who will approve the labelled evaluation set and its labels before results are claimed?

**Answer:** Actual human decision: I will review and approve the proposed synthetic policy, fixtures and labelled evaluation set at the plan gate. The evaluation set, labels, denominators and proposed test commands remain subject to that review; none are approved or measured now.

## Q5 [role: architect]
Does FR-014 permit isolated internal persistence of proposals, decisions, confirmation/idempotency bindings and audit when the sole business/case-management write is a create-only synthetic mock task? Recommended synthetic-only option: yes, limited to an isolated local test/demo store, with no production permissions, live resources, financial/source-record mutations or other business writes. If no, the durable workflow requires human-led spec/plan re-scoping; no answer assumed.

**Answer:** Actual human Q5 decision: Yes — isolated synthetic local storage only. Internal proposals, analyst decisions, confirmation/idempotency bindings and audit may persist ONLY in isolated synthetic local test/demo storage. The create-only mock case task remains the sole business write; no financial, source-record or production changes are permitted. This answers the persistence boundary only; it is NOT approval of the plan, proposed policy values, fixtures, labelled evaluation set or test commands.
