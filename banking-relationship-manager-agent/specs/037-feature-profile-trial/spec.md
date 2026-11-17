# Specification: feature profile trial

## User scenario

A developer wants to verify that a new feature can be initialized with the
`feature` workflow profile and that its standard stages and review gates are
recorded correctly, without changing application behavior.

## Requirements

- FR-001: The trial workflow uses the `feature` profile.
- FR-002: Its route contains specify, plan, tasks, and implement, in that order.
- FR-003: Its review gates are specify and plan.
- FR-004: The trial creates workflow artifacts only; it does not change
  application source code or production behavior.

## Scope

This is a workflow exercise to test profile selection and initialization. It is
not a product feature. Continue through planning, tasks, implementation, and
the specified review gates only if needed to exercise those stages.
