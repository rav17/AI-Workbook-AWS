# Scale-In Runbook — Manual ECS Task Reduction

## Overview

This runbook describes how to manually reduce the ECS Fargate task count for the AIOps service. Use this when queue depth is low and you want to reduce costs by scaling in ahead of the auto-scaling cooldown period.

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

### Step 1: Verify SQS Queue Depth Is Low

```bash
aws sqs get-queue-attributes \
  --queue-url "https://sqs.${AWS_REGION}.amazonaws.com/{ACCOUNT_ID}/aiops-queue-${ENVIRONMENT}" \
  --attribute-names ApproximateNumberOfMessagesVisible ApproximateNumberOfMessagesNotVisible \
  --region "${AWS_REGION}" \
  --output table
```

**Criteria to proceed:**
- `ApproximateNumberOfMessagesVisible` < 2
- `ApproximateNumberOfMessagesNotVisible` (in-flight) is stable or decreasing

If queue depth is > 2, do NOT scale in. Wait for messages to be processed.

### Step 2: Verify Current Task Count and Health

```bash
aws ecs describe-services \
  --cluster "${CLUSTER_NAME}" \
  --services "${SERVICE_NAME}" \
  --region "${AWS_REGION}" \
  --query 'services[0].{desired:desiredCount,running:runningCount,pending:pendingCount,deployments:deployments[*].status}' \
  --output table
```

Ensure no deployments are in progress (`PRIMARY` should be the only deployment status).

### Step 3: Check DLQ Depth

Verify no messages are accumulating in the dead-letter queue:

```bash
aws sqs get-queue-attributes \
  --queue-url "https://sqs.${AWS_REGION}.amazonaws.com/{ACCOUNT_ID}/aiops-dlq-${ENVIRONMENT}" \
  --attribute-names ApproximateNumberOfMessagesVisible \
  --region "${AWS_REGION}" \
  --output text
```

If DLQ depth > 0, investigate failures before scaling in.

### Step 4: Reduce Desired Task Count

### ⚠️ WARNING — Reducing Task Count

Reducing the desired count will stop running tasks. In-progress messages on stopped tasks will return to the SQS queue after the visibility timeout (60s) and be retried. Ensure queue depth is low before proceeding.

```bash
NEW_DESIRED_COUNT=1  # Minimum is 1; adjust as needed

aws ecs update-service \
  --cluster "${CLUSTER_NAME}" \
  --service "${SERVICE_NAME}" \
  --desired-count "${NEW_DESIRED_COUNT}" \
  --region "${AWS_REGION}" \
  --output json
```

### Step 5: Verify Tasks Drain Gracefully

Monitor task shutdown — ECS sends SIGTERM and allows a 30-second stop timeout:

```bash
watch -n 10 "aws ecs describe-services \
  --cluster ${CLUSTER_NAME} \
  --services ${SERVICE_NAME} \
  --region ${AWS_REGION} \
  --query 'services[0].{desired:desiredCount,running:runningCount}' \
  --output table"
```

Wait until `runningCount` matches `desiredCount`. Tasks should drain within 2–3 minutes.

### Step 6: Verify Service Health Post Scale-In

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

Verify no CloudWatch alarms have triggered:

```bash
aws cloudwatch describe-alarms \
  --alarm-name-prefix "aiops-${ENVIRONMENT}" \
  --state-value ALARM \
  --region "${AWS_REGION}" \
  --query 'MetricAlarms[*].{name:AlarmName,state:StateValue}' \
  --output table
```

## Rollback

If service health degrades after scale-in, immediately scale back out:

```bash
aws ecs update-service \
  --cluster "${CLUSTER_NAME}" \
  --service "${SERVICE_NAME}" \
  --desired-count 3 \
  --region "${AWS_REGION}" \
  --output json
```

## Notes

- Minimum task count is 1 — never scale to 0.
- Auto-scaling will resume managing the desired count based on SQS depth metrics.
- For staging/prod, the ECS service uses 100% minimum healthy during deployments, so scale-in is safe as long as at least 1 task remains.
