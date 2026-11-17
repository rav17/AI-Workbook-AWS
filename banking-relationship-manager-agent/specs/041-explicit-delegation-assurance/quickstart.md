# Validation Guide: Explicit Delegation Assurance

These are planned checks, not a claim that the feature is already implemented.

## Prerequisites

- Human-approved feature 041 plan and verification scope.
- Use the receiving project root and existing Python development environment.
- Use temporary test features; do not change 039 to exercise a regression.
- Never read raw logs or invoke a generic worker to manufacture enforcement proof.

## Automated acceptance and regression

Run the exact focused pytest, lint, formatting and type-check commands in
[plan.md](plan.md#project-practices-and-verification-proposal). Expected outcomes:

1. Missing acceptance cannot authorize the unverified-evidence exception.
2. A decision recorded through the supported human-terminal process for eligible
   ordinary work is scoped, inspectable and explicitly unverified.
3. Agent acceptance, malformed/oversized detail, tampered audit, changed session,
   worker definitions and redo/reset boundaries cannot authorize the exception.
4. Hybrid, enterprise, security-patch and unknown-profile cases remain excluded.
5. Existing gates, failed/running call recovery and named-worker validation are
   not bypassed; 039 remains unchanged.
6. Agent actors and agent-tool acceptance calls (including a forged human actor)
   are rejected by the supported operational controls. This does not test or
   claim authentication against arbitrary local processes.

Passing these checks does not establish live host enforcement, human identity
authentication or independently detected host/session identity.

## Later use for feature 039 (separate human decision)

After feature 041 implementation passes its approved checks, inspect 039 with an
explicit feature path. Present its current stage, assigned workers/restrictions,
actual observations, missing evidence, context and risk to the human.

If the human accepts that specific limitation, they run the acceptance command
in [the CLI contract](contracts/assurance-cli.md), using their actual current
host/session identifiers. The host checks context-bound status and all normal
dispatch/recovery conditions before any separately authorized resume.

Feature 041 itself needs no new acceptance: implementation is entirely inline,
with no assigned implementation worker boundary to waive. Its plan review uses
the current selective operational-review contract, not hybrid certification.

Completing 041, accepting its specification or approving its plan does none of
those actions automatically. No external package, Git commit or publication is
authorized by these checks.
