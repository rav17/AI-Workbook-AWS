# Incident Response Runbook — General Incident Triage

## Overview

This runbook provides a decision tree for triaging incidents in the AIOps system, starting from a CloudWatch alarm firing through diagnosis and resolution. Follow the steps in order, branching based on what you observe at each checkpoint.

## Prerequisites

- AWS CLI v2 configured with appropriate credentials
- Access to the target environment's AWS resources
- Set environment variables:

```bash
export ENVIRONMENT="{ENVIRONMENT}"        # dev | staging | prod
export CLUSTER_NAME="aiops-${ENVIRONMENT}"
export SERVICE_NAME="aiops-service-${ENVIRONMENT}"
export AWS_REGION="{AWS_REGION}"
export ACCOUNT_ID="{ACCOUNT_ID}"
```

## Decision Tree

```
Alarm Fires
    │
    ├─→ Check ECS Task Health (Step 1)
    │       │
    │       ├─ Tasks unhealthy → Go to "ECS Task Issues" (Step 2)
    │       └─ Tasks healthy → Continue
    │
    ├─→ Check SQS Queue Depth (Step 3)
    │       │
    │       ├─ Queue growing → Go to "Queue Backlog" (Step 4)
    │       └─ Queue stable → Continue
    │
    ├─→ Check DLQ Depth (Step 5)
    │       │
    │       ├─ DLQ > 5 → Go to "DLQ Investigation" (Step 6)
    │       └─ DLQ ≤ 5 → Continue
    │
    ├─→ Check Bedrock Throttling (Step 7)
    │       │
    │       ├─ Throttling detected → Follow bedrock-throttling.md
    │       └─ No throttling → Continue
    │
    └─→ Check Application Error Logs (Step 8)
            │
            ├─ Errors found → Investigate specific error pattern
            └─ No errors → False alarm / transient issue
```

## Step 1: Check ECS Task Health

```bash
aws ecs describe-services \
  --cluster "${CLUSTER_NAME}" \
  --services "${SERVICE_NAME}" \
  --region "${AWS_REGION}" \
  --query 'services[0].{desired:desiredCount,running:runningCount,pending:pendingCount,deployments:deployments[*].{status:status,desired:desiredCount,running:runningCount}}' \
  --output json
```

**Healthy indicators:**
- `runningCount` == `desiredCount`
- Only one deployment with status `PRIMARY`
- No tasks in PENDING state for > 2 minutes

If tasks are unhealthy → proceed to Step 2.
If tasks are healthy → skip to Step 3.

## Step 2: ECS Task Issues

### ⚠️ WARNING — Task Stop Operations

Stopping ECS tasks forcefully terminates in-progress work. Messages being processed will return to the SQS queue after the visibility timeout (60s). Only stop tasks as a last resort when they are unresponsive.

Check recent task stop reasons:

```bash
aws ecs list-tasks \
  --cluster "${CLUSTER_NAME}" \
  --service-name "${SERVICE_NAME}" \
  --desired-status STOPPED \
  --region "${AWS_REGION}" \
  --query 'taskArns[:5]' \
  --output text | xargs -I {} aws ecs describe-tasks \
  --cluster "${CLUSTER_NAME}" \
  --tasks {} \
  --region "${AWS_REGION}" \
  --query 'tasks[*].{taskId:taskArn,stopCode:stopCode,stoppedReason:stoppedReason,stoppedAt:stoppedAt}' \
  --output table
```

Common causes:
- **OutOfMemory**: Task exceeded 1024 MB memory → consider scaling out or investigating memory leak
- **EssentialContainerExited**: Application crash → check logs (Step 8)
- **ServiceSchedulerInitiated**: Deployment in progress or scale-in

Force a new deployment if tasks are stuck:

```bash
aws ecs update-service \
  --cluster "${CLUSTER_NAME}" \
  --service "${SERVICE_NAME}" \
  --force-new-deployment \
  --region "${AWS_REGION}" \
  --output json
```

## Step 3: Check SQS Queue Depth

```bash
aws sqs get-queue-attributes \
  --queue-url "https://sqs.${AWS_REGION}.amazonaws.com/${ACCOUNT_ID}/aiops-queue-${ENVIRONMENT}" \
  --attribute-names ApproximateNumberOfMessagesVisible ApproximateNumberOfMessagesNotVisible \
  --region "${AWS_REGION}" \
  --output table
```

**Normal:** MessagesVisible < 10, MessagesNotVisible (in-flight) proportional to task count.

If queue is growing → proceed to Step 4.
If queue is stable → skip to Step 5.

## Step 4: Queue Backlog

Queue growing indicates processing is slower than ingestion:

1. Check if tasks are processing (in-flight messages should be > 0):
```bash
aws sqs get-queue-attributes \
  --queue-url "https://sqs.${AWS_REGION}.amazonaws.com/${ACCOUNT_ID}/aiops-queue-${ENVIRONMENT}" \
  --attribute-names ApproximateNumberOfMessagesNotVisible \
  --region "${AWS_REGION}" \
  --output text
```

2. If in-flight is 0 but queue is growing → tasks are not polling. Check task health (Step 2).

3. If in-flight is > 0 → tasks are processing but slowly. Check AI latency:
```bash
aws cloudwatch get-metric-statistics \
  --namespace "AIOps/${ENVIRONMENT}" \
  --metric-name "AIReasoningLatency" \
  --start-time "$(date -u -d '15 minutes ago' +%Y-%m-%dT%H:%M:%S)" \
  --end-time "$(date -u +%Y-%m-%dT%H:%M:%S)" \
  --period 300 \
  --statistics p95 \
  --region "${AWS_REGION}" \
  --output table
```

4. If latency is high → check Bedrock throttling (Step 7) or consider scaling out (see `scale-out.md`).

## Step 5: Check DLQ Depth

```bash
aws sqs get-queue-attributes \
  --queue-url "https://sqs.${AWS_REGION}.amazonaws.com/${ACCOUNT_ID}/aiops-dlq-${ENVIRONMENT}" \
  --attribute-names ApproximateNumberOfMessagesVisible \
  --region "${AWS_REGION}" \
  --output text
```

**Normal:** DLQ depth = 0.
**Alert threshold:** DLQ depth > 5 triggers alarm.

If DLQ > 5 → proceed to Step 6.
If DLQ ≤ 5 → skip to Step 7.

## Step 6: DLQ Investigation

Sample DLQ messages to identify the failure pattern:

```bash
aws sqs receive-message \
  --queue-url "https://sqs.${AWS_REGION}.amazonaws.com/${ACCOUNT_ID}/aiops-dlq-${ENVIRONMENT}" \
  --max-number-of-messages 5 \
  --visibility-timeout 0 \
  --message-attribute-names All \
  --region "${AWS_REGION}" \
  --output json | jq '.Messages[] | {MessageId, Body: (.Body | fromjson | keys)}'
```

Check remediation failure metrics:

```bash
aws cloudwatch get-metric-statistics \
  --namespace "AIOps/${ENVIRONMENT}" \
  --metric-name "RemediationFailureCount" \
  --start-time "$(date -u -d '30 minutes ago' +%Y-%m-%dT%H:%M:%S)" \
  --end-time "$(date -u +%Y-%m-%dT%H:%M:%S)" \
  --period 300 \
  --statistics Sum \
  --region "${AWS_REGION}" \
  --output table
```

If failures are from a specific alert type → investigate that alert source.
If failures are systemic → check if Bedrock or downstream services are degraded.

For full DLQ replay procedures, see `dlq-replay.md`.

## Step 7: Check Bedrock Throttling

```bash
aws cloudwatch get-metric-statistics \
  --namespace "AIOps/${ENVIRONMENT}" \
  --metric-name "BedrockThrottleCount" \
  --start-time "$(date -u -d '15 minutes ago' +%Y-%m-%dT%H:%M:%S)" \
  --end-time "$(date -u +%Y-%m-%dT%H:%M:%S)" \
  --period 60 \
  --statistics Sum \
  --region "${AWS_REGION}" \
  --output table
```

If throttle count > 0 → follow `bedrock-throttling.md` runbook.
If throttle count = 0 → proceed to Step 8.

## Step 8: Check Application Error Logs

```bash
aws logs filter-log-events \
  --log-group-name "/ecs/aiops-${ENVIRONMENT}" \
  --start-time "$(date -u -d '30 minutes ago' +%s)000" \
  --filter-pattern '"level":"ERROR"' \
  --region "${AWS_REGION}" \
  --limit 20 \
  --query 'events[*].message' \
  --output text
```

Look for patterns:
- **Connection timeouts**: Network/VPC endpoint issues
- **Permission denied**: IAM role misconfiguration
- **Validation errors**: Malformed input data
- **Import/Module errors**: Deployment issue — consider rollback (see `rollback.md`)

Check recent warnings for additional context:

```bash
aws logs filter-log-events \
  --log-group-name "/ecs/aiops-${ENVIRONMENT}" \
  --start-time "$(date -u -d '30 minutes ago' +%s)000" \
  --filter-pattern '"level":"WARN"' \
  --region "${AWS_REGION}" \
  --limit 10 \
  --query 'events[*].message' \
  --output text
```

## Alarm Status Summary

Get all alarms and their current states:

```bash
aws cloudwatch describe-alarms \
  --alarm-name-prefix "aiops-${ENVIRONMENT}" \
  --region "${AWS_REGION}" \
  --query 'MetricAlarms[*].{Name:AlarmName,State:StateValue,Reason:StateReason}' \
  --output table
```

Check the composite rollback alarm:

```bash
aws cloudwatch describe-alarms \
  --alarm-names "RollbackRequired-${ENVIRONMENT}" \
  --region "${AWS_REGION}" \
  --query 'CompositeAlarms[*].{Name:AlarmName,State:StateValue,Reason:StateReason}' \
  --output table
```

If `RollbackRequired` is in ALARM state → consider triggering a rollback (see `rollback.md`).

## Escalation

If the issue cannot be resolved within 30 minutes:

1. Check escalation count metric:
```bash
aws cloudwatch get-metric-statistics \
  --namespace "AIOps/${ENVIRONMENT}" \
  --metric-name "HumanEscalationsCount" \
  --start-time "$(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S)" \
  --end-time "$(date -u +%Y-%m-%dT%H:%M:%S)" \
  --period 300 \
  --statistics Sum \
  --region "${AWS_REGION}" \
  --output table
```

2. Escalate to the platform engineering team via Slack/PagerDuty
3. Include: environment, alarm name, duration, actions taken, current status

## Notes

- All alarms share a single SNS topic: `aiops-alarms-{ENVIRONMENT}`
- The `RollbackRequired` composite alarm triggers when both ECS unhealthy AND DLQ depth alarms are in ALARM for 5+ minutes simultaneously.
- Dev environment has no CloudWatch alarms — incidents in dev are diagnosed manually.
- Structured logs contain: timestamp, level, incident_id, pipeline_stage, duration_ms, outcome, environment.
