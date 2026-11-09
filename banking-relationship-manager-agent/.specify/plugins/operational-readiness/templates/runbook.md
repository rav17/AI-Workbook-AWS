# Operational Runbook

Record executable-by-humans procedures, not claims that operations occurred.
Replace every placeholder; keep secrets and personal/customer data out.

## Ownership
{{Service/feature boundary, support owner, escalation role and coverage.}}
- Evidence: {{Ownership review reference.}}

## Health signals
{{Signals, dashboard/query location, normal range, thresholds and response owner.}}
- Evidence: {{Versioned monitoring configuration or reviewed planned instrumentation.}}

## Alerts
{{Routing, severity, trigger, response time expectation and acknowledgement.}}
- Evidence: {{Alert configuration/test result, or untested status with human risk review.}}

## Incidents
{{Symptoms, diagnostic steps, mitigation, recovery confirmation and escalation.}}
- Evidence: {{Reviewed incident procedure or exercise record.}}

## Rollback
{{Release rollback reference, exact operator steps, recovery/data checks and owner.}}
- Evidence: {{Versioned rollback procedure/exercise or explicitly reviewed untested status.}}

## Feedback
{{How incidents and service outcomes become candidate requirements; owner and cadence.}}
- Evidence: {{Reviewed feedback process reference; no invented operational outcomes.}}
