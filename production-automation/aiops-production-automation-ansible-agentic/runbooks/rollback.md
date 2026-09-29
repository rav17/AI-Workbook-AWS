# Rollback Runbook — Manual Deployment Rollback

## Overview

This runbook describes how to roll back a deployment of the AIOps service to a previous known-good state. There are two paths: automated (via the CD pipeline) and manual (via the Makefile target).

## Prerequisites

- AWS CLI v2 configured with appropriate credentials
- Access to the GitHub repository (for automated path)
- Access to the target environment's SSM Parameter Store
- Set environment variables:

```bash
export ENVIRONMENT="{ENVIRONMENT}"        # dev | staging | prod
export CLUSTER_NAME="aiops-${ENVIRONMENT}"
export SERVICE_NAME="aiops-service-${ENVIRONMENT}"
export AWS_REGION="{AWS_REGION}"
```

## Determine Rollback Target

List available deployment manifests (last 5 successful deployments):

```bash
for n in 1 2 3 4 5; do
  echo "=== Manifest n=${n} ==="
  aws ssm get-parameter \
    --name "/aiops/${ENVIRONMENT}/deployment-history/${n}" \
    --region "${AWS_REGION}" \
    --query 'Parameter.Value' \
    --output text 2>/dev/null || echo "Not found"
done
```

Each manifest contains: Image_Tag, commit SHA, CDK stack versions, timestamp, and Health_Gate result.

## Path A: Automated Rollback (CD Pipeline)

### Step 1: Trigger CD Pipeline Rollback

The CD pipeline automatically triggers rollback when a Health_Gate fails. To manually trigger:

```bash
gh workflow run cd.yml \
  -f environment="${ENVIRONMENT}" \
  -f rollback=true \
  -f manifest_n=1
```

### Step 2: Monitor Pipeline Progress

```bash
gh run list --workflow=cd.yml --limit=5
```

Watch for the rollback run to complete. The pipeline will:
1. Retrieve the deployment manifest (n=1 by default)
2. Re-deploy the stored Image_Tag
3. Run the Health_Gate check
4. Report success/failure

### Step 3: Verify via Health_Gate

The pipeline publishes Health_Gate metrics automatically. Verify:

```bash
aws cloudwatch get-metric-statistics \
  --namespace "AIOps/${ENVIRONMENT}" \
  --metric-name "DeploymentHealthGatePassed" \
  --start-time "$(date -u -d '15 minutes ago' +%Y-%m-%dT%H:%M:%S)" \
  --end-time "$(date -u +%Y-%m-%dT%H:%M:%S)" \
  --period 60 \
  --statistics Maximum \
  --region "${AWS_REGION}" \
  --output table
```

A value of `1` indicates the Health_Gate passed.

## Path B: Manual Rollback (Makefile Target)

### Step 1: Review Available Manifests

```bash
make rollback ENVIRONMENT=${ENVIRONMENT} MANIFEST=1 --dry-run
```

This will display the manifest contents for review without executing the rollback.

### Step 2: Execute Manual Rollback

```bash
make rollback ENVIRONMENT=${ENVIRONMENT} MANIFEST=1
```

This command:
1. Retrieves the specified deployment manifest from SSM Parameter Store
2. Displays the manifest for operator review
3. Invokes the CD pipeline with stored Image_Tag and CDK context
4. Exits non-zero if the manifest doesn't exist

### ⚠️ WARNING — Production Rollback

Rolling back production will deploy a previous version of the application. Ensure:
- The rollback target (manifest n) is a known-good deployment
- Any database schema changes since the target deployment are backward-compatible
- All team members are notified before executing

```bash
# Confirm before proceeding
echo "Rolling back ${ENVIRONMENT} to manifest n=${MANIFEST_N}"
echo "Image_Tag: $(aws ssm get-parameter --name "/aiops/${ENVIRONMENT}/deployment-history/${MANIFEST_N}" --region "${AWS_REGION}" --query 'Parameter.Value' --output text | jq -r '.image_tag')"
read -p "Proceed? (yes/no): " CONFIRM
[ "${CONFIRM}" = "yes" ] || exit 1
```

### Step 3: Verify Rollback Success

Check service health:

```bash
curl -s https://api.{DOMAIN}/health | jq '.dependencies'
```

Verify all CloudWatch alarms are in OK state:

```bash
aws cloudwatch describe-alarms \
  --alarm-name-prefix "aiops-${ENVIRONMENT}" \
  --state-value ALARM \
  --region "${AWS_REGION}" \
  --query 'MetricAlarms[*].{name:AlarmName,state:StateValue}' \
  --output table
```

Verify the ECS service is running the expected image:

```bash
TASK_DEF=$(aws ecs describe-services \
  --cluster "${CLUSTER_NAME}" \
  --services "${SERVICE_NAME}" \
  --region "${AWS_REGION}" \
  --query 'services[0].taskDefinition' \
  --output text)

aws ecs describe-task-definition \
  --task-definition "${TASK_DEF}" \
  --region "${AWS_REGION}" \
  --query 'taskDefinition.containerDefinitions[0].image' \
  --output text
```

## Post-Rollback Actions

1. Investigate the root cause of the failed deployment
2. Notify the team via Slack with details of the rollback
3. Create a post-incident ticket if the failure impacted production traffic
4. Verify the DLQ depth has not grown during the rollback window:

```bash
aws sqs get-queue-attributes \
  --queue-url "https://sqs.${AWS_REGION}.amazonaws.com/{ACCOUNT_ID}/aiops-dlq-${ENVIRONMENT}" \
  --attribute-names ApproximateNumberOfMessagesVisible \
  --region "${AWS_REGION}" \
  --output text
```

## Notes

- Automated rollback bypasses the manual approval gate for prod.
- Rollback must complete and pass Health_Gate within 15 minutes.
- Maximum 5 deployment manifests are retained; older ones are rotated out.
- If the specified manifest (n) does not exist, the Makefile target exits non-zero.
