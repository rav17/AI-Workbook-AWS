# DLQ Replay Runbook — Replaying Messages from Dead-Letter Queue

## Overview

This runbook describes how to inspect and replay messages from the AIOps Dead-Letter Queue (DLQ) back to the main processing queue. Messages land in the DLQ after 3 failed processing attempts from the main queue.

## Prerequisites

- AWS CLI v2 configured with appropriate credentials
- Access to the target environment's SQS queues
- Set environment variables:

```bash
export ENVIRONMENT="{ENVIRONMENT}"        # dev | staging | prod
export AWS_REGION="{AWS_REGION}"
export ACCOUNT_ID="{ACCOUNT_ID}"
export MAIN_QUEUE_URL="https://sqs.${AWS_REGION}.amazonaws.com/${ACCOUNT_ID}/aiops-queue-${ENVIRONMENT}"
export DLQ_URL="https://sqs.${AWS_REGION}.amazonaws.com/${ACCOUNT_ID}/aiops-dlq-${ENVIRONMENT}"
```

## Procedure

### Step 1: Check DLQ Depth

```bash
aws sqs get-queue-attributes \
  --queue-url "${DLQ_URL}" \
  --attribute-names ApproximateNumberOfMessagesVisible ApproximateNumberOfMessagesNotVisible \
  --region "${AWS_REGION}" \
  --output table
```

Record the message count before proceeding.

### Step 2: Inspect DLQ Messages

Sample messages to understand the failure pattern before replaying:

```bash
aws sqs receive-message \
  --queue-url "${DLQ_URL}" \
  --max-number-of-messages 5 \
  --visibility-timeout 30 \
  --message-attribute-names All \
  --region "${AWS_REGION}" \
  --output json | jq '.Messages[] | {MessageId, Body: (.Body | fromjson), Attributes}'
```

**What to look for:**
- Are all messages from the same source/alert type?
- Do the messages contain malformed data?
- Is there a common error pattern?

If messages are malformed or should NOT be reprocessed, skip to the "Isolate Repeat Failures" section.

### Step 3: Verify Main Queue and Service Health

Before replaying, ensure the main queue is not backed up and the service is healthy:

```bash
aws sqs get-queue-attributes \
  --queue-url "${MAIN_QUEUE_URL}" \
  --attribute-names ApproximateNumberOfMessagesVisible \
  --region "${AWS_REGION}" \
  --output text

curl -s https://api.{DOMAIN}/health | jq '.dependencies'
```

Only proceed if main queue depth is manageable and service reports healthy.

### Step 4: Move Messages from DLQ to Main Queue

### ⚠️ WARNING — DLQ Replay

Replaying messages will re-trigger alert processing for all replayed messages. This may cause:
- Duplicate remediation actions if the original actions partially succeeded
- Increased load on Bedrock API and downstream systems
- Re-triggering of notifications to Slack/PagerDuty

Ensure the root cause of the original failures has been resolved before replaying.

Start the DLQ redrive using the SQS redrive API:

```bash
aws sqs start-message-move-task \
  --source-arn "arn:aws:sqs:${AWS_REGION}:${ACCOUNT_ID}:aiops-dlq-${ENVIRONMENT}" \
  --destination-arn "arn:aws:sqs:${AWS_REGION}:${ACCOUNT_ID}:aiops-queue-${ENVIRONMENT}" \
  --region "${AWS_REGION}" \
  --output json
```

For selective replay (move specific messages one at a time):

```bash
# Receive a message from DLQ
MSG=$(aws sqs receive-message \
  --queue-url "${DLQ_URL}" \
  --max-number-of-messages 1 \
  --region "${AWS_REGION}" \
  --output json)

# Extract body and receipt handle
BODY=$(echo "${MSG}" | jq -r '.Messages[0].Body')
RECEIPT=$(echo "${MSG}" | jq -r '.Messages[0].ReceiptHandle')

# Send to main queue
aws sqs send-message \
  --queue-url "${MAIN_QUEUE_URL}" \
  --message-body "${BODY}" \
  --region "${AWS_REGION}"

# Delete from DLQ after successful send
aws sqs delete-message \
  --queue-url "${DLQ_URL}" \
  --receipt-handle "${RECEIPT}" \
  --region "${AWS_REGION}"
```

### Step 5: Monitor Reprocessing

Monitor the main queue depth and processing metrics:

```bash
# Watch queue depth decrease
watch -n 30 "aws sqs get-queue-attributes \
  --queue-url ${MAIN_QUEUE_URL} \
  --attribute-names ApproximateNumberOfMessagesVisible \
  --region ${AWS_REGION} \
  --output text"
```

Check CloudWatch metrics for processing success/failure:

```bash
aws cloudwatch get-metric-statistics \
  --namespace "AIOps/${ENVIRONMENT}" \
  --metric-name "RemediationFailureCount" \
  --start-time "$(date -u -d '15 minutes ago' +%Y-%m-%dT%H:%M:%S)" \
  --end-time "$(date -u +%Y-%m-%dT%H:%M:%S)" \
  --period 60 \
  --statistics Sum \
  --region "${AWS_REGION}" \
  --output table
```

### Step 6: Isolate Repeat Failures

If messages fail reprocessing again (3+ total attempts), they will return to the DLQ. Identify and isolate these:

```bash
# Check if DLQ depth is growing again
aws sqs get-queue-attributes \
  --queue-url "${DLQ_URL}" \
  --attribute-names ApproximateNumberOfMessagesVisible \
  --region "${AWS_REGION}" \
  --output text
```

For messages that repeatedly fail:

1. Receive and inspect the failing messages:
```bash
aws sqs receive-message \
  --queue-url "${DLQ_URL}" \
  --max-number-of-messages 10 \
  --attribute-names ApproximateReceiveCount \
  --region "${AWS_REGION}" \
  --output json | jq '.Messages[] | {MessageId, ReceiveCount: .Attributes.ApproximateReceiveCount, Body: (.Body | fromjson)}'
```

2. Save failing messages to a file for investigation:
```bash
aws sqs receive-message \
  --queue-url "${DLQ_URL}" \
  --max-number-of-messages 10 \
  --visibility-timeout 60 \
  --region "${AWS_REGION}" \
  --output json > dlq-failures-$(date +%Y%m%d-%H%M%S).json
```

### ⚠️ WARNING — DLQ Purge

Purging the DLQ permanently deletes ALL messages. This is irreversible. Only purge after messages have been saved or confirmed as unrecoverable.

3. If messages are confirmed unrecoverable, purge the DLQ:
```bash
# DESTRUCTIVE — confirm before executing
read -p "Purge all messages from DLQ? This cannot be undone. (yes/no): " CONFIRM
[ "${CONFIRM}" = "yes" ] || exit 1

aws sqs purge-queue \
  --queue-url "${DLQ_URL}" \
  --region "${AWS_REGION}"
```

## Verification

After replay is complete, confirm:

1. DLQ depth is 0 (or only contains known-bad messages):
```bash
aws sqs get-queue-attributes \
  --queue-url "${DLQ_URL}" \
  --attribute-names ApproximateNumberOfMessagesVisible \
  --region "${AWS_REGION}" \
  --output text
```

2. DLQ CloudWatch alarm has returned to OK state:
```bash
aws cloudwatch describe-alarms \
  --alarm-names "aiops-${ENVIRONMENT}-dlq-depth" \
  --region "${AWS_REGION}" \
  --query 'MetricAlarms[0].StateValue' \
  --output text
```

## Notes

- DLQ message retention is 14 days — messages expire after this period.
- The main queue visibility timeout is 60 seconds — messages become available for retry after this period if not deleted.
- Messages fail to the DLQ after exactly 3 failed processing attempts (maxReceiveCount=3).
