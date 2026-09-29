# Bedrock Throttling Runbook — Responding to Bedrock API Throttling

## Overview

This runbook describes how to respond when Amazon Bedrock API throttling is detected. Throttling indicates the service has exceeded its provisioned throughput or account-level limits. The primary mitigation is switching the AIOps service to `rules_only` mode via SSM parameter update.

## Prerequisites

- AWS CLI v2 configured with appropriate credentials
- Access to the target environment's SSM Parameter Store and CloudWatch
- Set environment variables:

```bash
export ENVIRONMENT="{ENVIRONMENT}"        # dev | staging | prod
export AWS_REGION="{AWS_REGION}"
export CLUSTER_NAME="aiops-${ENVIRONMENT}"
export SERVICE_NAME="aiops-service-${ENVIRONMENT}"
```

## Indicators

You may be responding to this runbook due to:
- `BedrockThrottleCount` CloudWatch alarm firing
- Increased AI reasoning latency (p95 > 15s alarm)
- Manual observation of throttling errors in application logs

## Procedure

### Step 1: Check Bedrock Throttle Metrics

Confirm throttling is occurring:

```bash
aws cloudwatch get-metric-statistics \
  --namespace "AIOps/${ENVIRONMENT}" \
  --metric-name "BedrockThrottleCount" \
  --start-time "$(date -u -d '30 minutes ago' +%Y-%m-%dT%H:%M:%S)" \
  --end-time "$(date -u +%Y-%m-%dT%H:%M:%S)" \
  --period 300 \
  --statistics Sum \
  --region "${AWS_REGION}" \
  --output table
```

Check Bedrock service-level metrics:

```bash
aws cloudwatch get-metric-statistics \
  --namespace "AWS/Bedrock" \
  --metric-name "ThrottledCount" \
  --start-time "$(date -u -d '30 minutes ago' +%Y-%m-%dT%H:%M:%S)" \
  --end-time "$(date -u +%Y-%m-%dT%H:%M:%S)" \
  --period 300 \
  --statistics Sum \
  --region "${AWS_REGION}" \
  --output table
```

### Step 2: Check Current Operating Mode

```bash
aws ssm get-parameter \
  --name "/aiops/${ENVIRONMENT}/operating-mode" \
  --region "${AWS_REGION}" \
  --query 'Parameter.Value' \
  --output text
```

If already in `rules_only`, throttling should not be occurring from this service — investigate other Bedrock consumers in the account.

### Step 3: Switch to Rules-Only Mode

Update the operating mode SSM parameter to bypass Bedrock:

```bash
aws ssm put-parameter \
  --name "/aiops/${ENVIRONMENT}/operating-mode" \
  --value "rules_only" \
  --type String \
  --overwrite \
  --region "${AWS_REGION}" \
  --output json
```

The service will pick up this change at the next parameter refresh interval (default 300 seconds / 5 minutes).

### Step 4: Verify Mode Switch

Wait for the refresh interval, then verify in logs:

```bash
# Wait for parameter refresh (default 300s)
echo "Waiting for parameter refresh (up to 5 minutes)..."
sleep 300

# Check application logs for mode switch confirmation
aws logs filter-log-events \
  --log-group-name "/ecs/aiops-${ENVIRONMENT}" \
  --start-time "$(date -u -d '10 minutes ago' +%s)000" \
  --filter-pattern '"operating-mode" "rules_only"' \
  --region "${AWS_REGION}" \
  --query 'events[*].message' \
  --output text
```

### Step 5: Verify Throttling Has Stopped

```bash
aws cloudwatch get-metric-statistics \
  --namespace "AIOps/${ENVIRONMENT}" \
  --metric-name "BedrockThrottleCount" \
  --start-time "$(date -u -d '10 minutes ago' +%Y-%m-%dT%H:%M:%S)" \
  --end-time "$(date -u +%Y-%m-%dT%H:%M:%S)" \
  --period 60 \
  --statistics Sum \
  --region "${AWS_REGION}" \
  --output table
```

Throttle count should drop to 0 after mode switch takes effect.

Also check that the fallback metric is incrementing (confirming rules-only mode is active):

```bash
aws cloudwatch get-metric-statistics \
  --namespace "AIOps/${ENVIRONMENT}" \
  --metric-name "FallbackToRulesCount" \
  --start-time "$(date -u -d '10 minutes ago' +%Y-%m-%dT%H:%M:%S)" \
  --end-time "$(date -u +%Y-%m-%dT%H:%M:%S)" \
  --period 60 \
  --statistics Sum \
  --region "${AWS_REGION}" \
  --output table
```

### Step 6: Monitor Recovery

Monitor for 15–30 minutes to ensure:
- No new throttling errors
- Queue depth is not growing
- Remediations are still succeeding (in rules-only mode)

```bash
aws cloudwatch get-metric-statistics \
  --namespace "AIOps/${ENVIRONMENT}" \
  --metric-name "RemediationSuccessCount" \
  --start-time "$(date -u -d '30 minutes ago' +%Y-%m-%dT%H:%M:%S)" \
  --end-time "$(date -u +%Y-%m-%dT%H:%M:%S)" \
  --period 300 \
  --statistics Sum \
  --region "${AWS_REGION}" \
  --output table
```

## Restoring AI Mode

Once throttling has resolved (typically 15–60 minutes), restore AI processing:

### Step 1: Verify Bedrock Is Available

```bash
aws cloudwatch get-metric-statistics \
  --namespace "AWS/Bedrock" \
  --metric-name "ThrottledCount" \
  --start-time "$(date -u -d '15 minutes ago' +%Y-%m-%dT%H:%M:%S)" \
  --end-time "$(date -u +%Y-%m-%dT%H:%M:%S)" \
  --period 60 \
  --statistics Sum \
  --region "${AWS_REGION}" \
  --output table
```

Proceed only if throttle count has been 0 for at least 15 minutes.

### Step 2: Restore Operating Mode

```bash
aws ssm put-parameter \
  --name "/aiops/${ENVIRONMENT}/operating-mode" \
  --value "ai_with_fallback" \
  --type String \
  --overwrite \
  --region "${AWS_REGION}" \
  --output json
```

### Step 3: Monitor Post-Restoration

Watch for any recurrence of throttling in the first 10 minutes:

```bash
sleep 300  # Wait for refresh

aws cloudwatch get-metric-statistics \
  --namespace "AIOps/${ENVIRONMENT}" \
  --metric-name "BedrockThrottleCount" \
  --start-time "$(date -u -d '10 minutes ago' +%Y-%m-%dT%H:%M:%S)" \
  --end-time "$(date -u +%Y-%m-%dT%H:%M:%S)" \
  --period 60 \
  --statistics Sum \
  --region "${AWS_REGION}" \
  --output table
```

If throttling recurs, switch back to `rules_only` and consider requesting a Bedrock quota increase.

## Requesting a Quota Increase

If throttling is recurring, request a limit increase:

```bash
aws service-quotas request-service-quota-increase \
  --service-code bedrock \
  --quota-code "<QUOTA_CODE>" \
  --desired-value <NEW_LIMIT> \
  --region "${AWS_REGION}"
```

## Notes

- The parameter refresh interval is configurable (60–3600s, default 300s). Mode switch is not instant.
- `rules_only` mode disables AI reasoning but continues processing alerts using rule-based logic.
- `ai_with_fallback` mode uses AI but falls back to rules if AI fails — this is the recommended default.
- Valid operating modes: `rules_only`, `ai_only`, `ai_with_fallback`.
