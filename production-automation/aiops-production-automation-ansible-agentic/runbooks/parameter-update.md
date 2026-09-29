# Parameter Update Runbook — Updating SSM Parameters Without Service Restart

## Overview

This runbook describes how to update SSM Parameter Store values for the AIOps service without requiring a service restart or redeployment. The application periodically refreshes parameters at a configurable interval (default 300 seconds / 5 minutes).

## Prerequisites

- AWS CLI v2 configured with appropriate credentials
- Access to the target environment's SSM Parameter Store
- Set environment variables:

```bash
export ENVIRONMENT="{ENVIRONMENT}"        # dev | staging | prod
export AWS_REGION="{AWS_REGION}"
```

## Available Parameters

All parameters are stored under `/aiops/{ENVIRONMENT}/`:

| Parameter | Type | Valid Values | Default |
|-----------|------|--------------|---------|
| `operating-mode` | String | `rules_only`, `ai_only`, `ai_with_fallback` | `rules_only` |
| `escalation-threshold` | String | Float 0.0–1.0 | `0.5` |
| `correlation-window-seconds` | String | Integer 1–86400 | `300` |
| `max-concurrent-pipelines` | String | Integer 1–500 | `50` |
| `bedrock-model-id` | String | Non-empty Bedrock model ID | Required |
| `sqs-queue-url` | String | Non-empty SQS URL | From DataStack |
| `dynamodb-table-name` | String | Non-empty table name | From DataStack |
| `audit-log-group-name` | String | Non-empty log group | From ObservabilityStack |
| `asset-inventory-path` | String | File path | `/app/config/asset_inventory.yml` |
| `mapping-config-path` | String | File path | `/app/config/playbook_mapping.yml` |

## Procedure

### Step 1: Check Current Parameter Value

```bash
PARAM_NAME="operating-mode"  # Replace with target parameter

aws ssm get-parameter \
  --name "/aiops/${ENVIRONMENT}/${PARAM_NAME}" \
  --region "${AWS_REGION}" \
  --query 'Parameter.{Value:Value,Version:Version,LastModified:LastModifiedDate}' \
  --output table
```

Record the current value for rollback if needed.

### Step 2: Update the Parameter

```bash
PARAM_NAME="operating-mode"    # Replace with target parameter
NEW_VALUE="ai_with_fallback"   # Replace with new value

aws ssm put-parameter \
  --name "/aiops/${ENVIRONMENT}/${PARAM_NAME}" \
  --value "${NEW_VALUE}" \
  --type String \
  --overwrite \
  --region "${AWS_REGION}" \
  --output json
```

### Step 3: Wait for Refresh Interval

The service refreshes parameters at the configured interval (default 300 seconds). The change will take effect for the next alert processed after the refresh completes.

```bash
echo "Parameter updated. Waiting for refresh interval (default 300s)..."
echo "Change will be effective within $(date -u -d '+5 minutes' +%H:%M:%S) UTC"
sleep 300
```

### Step 4: Verify New Value in Application Logs

Check that the application has picked up the new value:

```bash
aws logs filter-log-events \
  --log-group-name "/ecs/aiops-${ENVIRONMENT}" \
  --start-time "$(date -u -d '10 minutes ago' +%s)000" \
  --filter-pattern "\"${PARAM_NAME}\" \"${NEW_VALUE}\"" \
  --region "${AWS_REGION}" \
  --limit 5 \
  --query 'events[*].message' \
  --output text
```

If no log entries are found, wait another refresh interval and try again.

### Step 5: Verify Service Health

Confirm the service is still healthy after the parameter change:

```bash
curl -s https://api.{DOMAIN}/health | jq '.dependencies'
```

Check for any errors in recent logs:

```bash
aws logs filter-log-events \
  --log-group-name "/ecs/aiops-${ENVIRONMENT}" \
  --start-time "$(date -u -d '10 minutes ago' +%s)000" \
  --filter-pattern '"level":"ERROR"' \
  --region "${AWS_REGION}" \
  --limit 10 \
  --query 'events[*].message' \
  --output text
```

## Rollback

If the parameter change causes issues, revert to the previous value:

```bash
PARAM_NAME="operating-mode"
PREVIOUS_VALUE="rules_only"  # Value recorded in Step 1

aws ssm put-parameter \
  --name "/aiops/${ENVIRONMENT}/${PARAM_NAME}" \
  --value "${PREVIOUS_VALUE}" \
  --type String \
  --overwrite \
  --region "${AWS_REGION}" \
  --output json
```

Wait another refresh interval (300s) for the rollback to take effect.

## Bulk Parameter Update

To update multiple parameters at once:

```bash
# Update multiple parameters
aws ssm put-parameter --name "/aiops/${ENVIRONMENT}/escalation-threshold" --value "0.7" --type String --overwrite --region "${AWS_REGION}"
aws ssm put-parameter --name "/aiops/${ENVIRONMENT}/correlation-window-seconds" --value "600" --type String --overwrite --region "${AWS_REGION}"
aws ssm put-parameter --name "/aiops/${ENVIRONMENT}/max-concurrent-pipelines" --value "100" --type String --overwrite --region "${AWS_REGION}"
```

All changes will be picked up at the next refresh interval.

## Parameter History

View the change history for a parameter:

```bash
aws ssm get-parameter-history \
  --name "/aiops/${ENVIRONMENT}/${PARAM_NAME}" \
  --region "${AWS_REGION}" \
  --query 'Parameters[*].{Value:Value,Version:Version,Modified:LastModifiedDate,ModifiedBy:LastModifiedUser}' \
  --output table
```

## Notes

- The refresh interval is configurable: minimum 60 seconds, maximum 3600 seconds, default 300 seconds.
- If the SSM fetch fails during a refresh, the application retains the last successfully fetched values and logs a warning.
- Changes take effect for the **next alert processed** after a successful refresh — in-progress processing is not interrupted.
- Invalid parameter values (e.g., `operating-mode` set to an unrecognized value) will be rejected by the application at refresh time, and the previous valid value will be retained.
- No service restart or ECS task redeployment is required for parameter changes.
