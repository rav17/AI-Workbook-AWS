# Scale-Out Runbook — Manual ECS Task Scaling

## Overview

This runbook describes how to manually scale out the AIOps ECS Fargate service when auto-scaling is insufficient or needs to be overridden. Use this when SQS queue depth is growing and auto-scaling has not responded quickly enough.

## Prerequisites

- AWS CLI v2 configured with appropriate credentials
- Access to the target environment's ECS cluster
- Set environment variables:

```bash
export ENVIRONMENT="{ENVIRONMENT}"        # dev | staging | prod
export CLUSTER_NAME="aiops-${ENVIRONMENT}"
export SERVICE_NAME="aiops-service-${ENVIRONMENT}"
export AWS_REGION="{AWS_REGION}"
```

## Procedure

### Step 1: Verify Current Task Count

```bash
aws ecs describe-services \
  --cluster "${CLUSTER_NAME}" \
  --services "${SERVICE_NAME}" \
  --region "${AWS_REGION}" \
  --query 'services[0].{desired:desiredCount,running:runningCount,pending:pendingCount}' \
  --output table
```

Record the current `desiredCount` and `runningCount` for rollback reference.

### Step 2: Check SQS Queue Depth

```bash
aws sqs get-queue-attributes \
  --queue-url "https://sqs.${AWS_REGION}.amazonaws.com/{ACCOUNT_ID}/aiops-queue-${ENVIRONMENT}" \
  --attribute-names ApproximateNumberOfMessagesVisible \
  --region "${AWS_REGION}" \
  --output text
```

Note the current queue depth — this is your baseline for verification in Step 5.

### Step 3: Update Desired Task Count

Determine the new desired count. Do not exceed the service maximum of 10 tasks.

```bash
NEW_DESIRED_COUNT=4  # Adjust as needed (max 10)

aws ecs update-service \
  --cluster "${CLUSTER_NAME}" \
  --service "${SERVICE_NAME}" \
  --desired-count "${NEW_DESIRED_COUNT}" \
  --region "${AWS_REGION}" \
  --output json
```

### Step 4: Verify New Tasks Are Healthy

Wait for tasks to reach RUNNING state (typically 60–120 seconds):

```bash
aws ecs wait services-stable \
  --cluster "${CLUSTER_NAME}" \
  --services "${SERVICE_NAME}" \
  --region "${AWS_REGION}"
```

Verify all tasks are healthy via the health endpoint:

```bash
aws ecs list-tasks \
  --cluster "${CLUSTER_NAME}" \
  --service-name "${SERVICE_NAME}" \
  --desired-status RUNNING \
  --region "${AWS_REGION}" \
  --query 'taskArns' \
  --output table
```

Check the /health endpoint returns HTTP 200 with all dependencies healthy:

```bash
curl -s https://api.{DOMAIN}/health | jq '.dependencies'
```

Expected output:
```json
{
  "sqs": "healthy",
  "dynamodb": "healthy"
}
```

### Step 5: Confirm SQS Queue Depth Is Reducing

Wait 60 seconds, then re-check the queue depth:

```bash
sleep 60

aws sqs get-queue-attributes \
  --queue-url "https://sqs.${AWS_REGION}.amazonaws.com/{ACCOUNT_ID}/aiops-queue-${ENVIRONMENT}" \
  --attribute-names ApproximateNumberOfMessagesVisible \
  --region "${AWS_REGION}" \
  --output text
```

Verify the queue depth is lower than the value recorded in Step 2. If not, consider scaling further or investigating message processing failures.

### Step 6: Monitor CloudWatch Metrics

Check the custom AutoScalingAboveNominal metric if task count exceeds 5:

```bash
aws cloudwatch get-metric-statistics \
  --namespace "AIOps/${ENVIRONMENT}" \
  --metric-name "AutoScalingAboveNominal" \
  --start-time "$(date -u -d '10 minutes ago' +%Y-%m-%dT%H:%M:%S)" \
  --end-time "$(date -u +%Y-%m-%dT%H:%M:%S)" \
  --period 60 \
  --statistics Maximum \
  --region "${AWS_REGION}" \
  --output table
```

## Rollback

If the scale-out causes issues, revert to the previous desired count:

```bash
PREVIOUS_DESIRED_COUNT=2  # Value recorded in Step 1

aws ecs update-service \
  --cluster "${CLUSTER_NAME}" \
  --service "${SERVICE_NAME}" \
  --desired-count "${PREVIOUS_DESIRED_COUNT}" \
  --region "${AWS_REGION}" \
  --output json
```

## Notes

- Auto-scaling will resume managing the desired count once the SQS-based scaling policies evaluate. Manual overrides are temporary.
- Maximum task count is 10 per the service configuration.
- For dev environment, auto-scaling is disabled — manual scaling is the only option.
