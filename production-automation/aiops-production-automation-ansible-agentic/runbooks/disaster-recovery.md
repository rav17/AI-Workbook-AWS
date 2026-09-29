# Disaster Recovery Plan

## Recovery Objectives

| Metric | Target | Rationale |
|--------|--------|-----------|
| RTO (Recovery Time Objective) | 30 minutes | Time to restore service after a full stack failure |
| RPO (Recovery Point Objective) | 1 hour | Maximum data loss window for incident memory |
| MTTR (Mean Time to Recovery) | 15 minutes | For single-component failures with auto-scaling |

## Data Protection Strategy

### DynamoDB Incident Memory Table
- **PITR (Point-in-Time Recovery)**: Enabled for production
- **Retention**: 35-day continuous backups via PITR
- **AWS Backup**: Daily snapshots at 02:00 UTC, retained 35 days
- **Cross-region**: Not configured (single-region deployment)

### SQS Queues
- **Main queue**: 14-day message retention (prod)
- **DLQ**: 14-day retention, messages survive component restarts
- **No backup needed**: Messages are transient; unprocessed alerts re-fire from Alertmanager

### Secrets Manager
- **Versioning**: Automatic version history retained by AWS
- **Rotation**: API Gateway key rotated every 90 days
- **Recovery**: Previous secret versions available for immediate rollback

### CloudWatch Logs
- **Retention**: 365 days (prod), 90 days (staging), 30 days (dev)
- **Export**: Not configured — add S3 export for long-term archival if needed

## Failure Scenarios and Recovery

### Scenario 1: ECS Service Failure (Container Crash Loop)

**Detection**: ECS unhealthy tasks alarm, composite RollbackRequired alarm
**Impact**: Alerts queue in SQS, no remediation occurs
**RTO**: 5 minutes (auto-recovery) / 15 minutes (manual)

**Auto-Recovery**:
1. ECS replaces unhealthy tasks automatically
2. New tasks pass health check within 60s
3. SQS messages are reprocessed from the queue

**Manual Recovery**:
```bash
# Check service events
aws ecs describe-services --cluster aiops-cluster-prod --services aiops-service-prod

# Force new deployment
aws ecs update-service --cluster aiops-cluster-prod --service aiops-service-prod --force-new-deployment

# Monitor rollout
aws ecs wait services-stable --cluster aiops-cluster-prod --services aiops-service-prod
```

### Scenario 2: Bad Deployment (Application Bug)

**Detection**: Health gate failure during CD, composite alarm
**Impact**: Partial or full service degradation
**RTO**: 10 minutes

**Recovery**:
```bash
# Automated: CD pipeline triggers rollback to n=1 manifest
# Manual:
make rollback ENVIRONMENT=prod MANIFEST=1

# Verify rollback
python scripts/health_gate.py --environment prod
```

### Scenario 3: DynamoDB Table Corruption or Deletion

**Detection**: DynamoDB errors in CloudWatch, health check reporting unhealthy
**Impact**: Loss of incident history (AI reasoning degrades, no deduplication context)
**RTO**: 30 minutes
**RPO**: 1 hour (PITR granularity: seconds)

**Recovery from PITR**:
```bash
# Restore to a point in time (within last 35 days)
aws dynamodb restore-table-to-point-in-time \
    --source-table-name AiopsIncidentMemory-prod \
    --target-table-name AiopsIncidentMemory-prod-restored \
    --restore-date-time "2026-07-30T10:00:00Z"

# Update SSM parameter to point to restored table
aws ssm put-parameter \
    --name /aiops/prod/dynamodb-table-name \
    --value AiopsIncidentMemory-prod-restored \
    --overwrite

# Force ECS task refresh to pick up new table name
aws ecs update-service --cluster aiops-cluster-prod --service aiops-service-prod --force-new-deployment
```

**Recovery from AWS Backup**:
```bash
aws backup start-restore-job \
    --recovery-point-arn <backup-arn> \
    --iam-role-arn <backup-role-arn> \
    --metadata '{"targetTableName": "AiopsIncidentMemory-prod-restored"}'
```

### Scenario 4: SQS Queue Deletion or Purge

**Detection**: SQS errors, health check unhealthy
**Impact**: In-flight alerts lost, new alerts fail to ingest
**RTO**: 15 minutes (recreate via CDK)

**Recovery**:
```bash
# Redeploy DataStack to recreate queues
npx aws-cdk@2 deploy DataStack --context environment=prod --require-approval never

# Alerts will re-fire from Alertmanager (it retries on webhook failure)
# No manual replay needed for most scenarios
```

### Scenario 5: Full Region Failure

**Detection**: AWS Service Health Dashboard, all health checks failing
**Impact**: Complete service outage
**RTO**: Not applicable (single-region design)

**Mitigation for future**:
- Deploy active-passive in a second region
- Use DynamoDB Global Tables for incident memory
- Route53 failover to secondary region

**Current approach**: Accept downtime during region failure. Alertmanager continues to buffer and retry. Service resumes processing once region recovers.

### Scenario 6: Secrets Compromised

**Detection**: Unauthorized access alerts, unusual API activity
**Impact**: Potential unauthorized remediation execution
**RTO**: 5 minutes

**Recovery**:
```bash
# Immediately rotate all secrets
aws secretsmanager rotate-secret --secret-id /aiops/prod/api-gateway-key

# Invalidate Slack webhook (regenerate in Slack admin)
aws secretsmanager put-secret-value \
    --secret-id /aiops/prod/slack-webhook-url \
    --secret-string "NEW_WEBHOOK_URL"

# Force ECS refresh to pick up rotated secrets
aws ecs update-service --cluster aiops-cluster-prod --service aiops-service-prod --force-new-deployment

# Review CloudTrail for unauthorized access
aws cloudtrail lookup-events \
    --lookup-attributes AttributeKey=EventSource,AttributeValue=secretsmanager.amazonaws.com \
    --start-time "2026-07-30T00:00:00Z"
```

## Rollback Verification Procedure

After any rollback or recovery:

1. **Health gate**: `python scripts/health_gate.py --environment prod`
2. **Manual verification**: `curl -s https://<endpoint>/health | jq .`
3. **Send test alert**: Verify full pipeline with a synthetic P3 alert
4. **Check metrics**: Confirm `alerts_received_total` counter incrementing
5. **Review DLQ**: Ensure no messages stuck in dead-letter queue

## Regular DR Testing

| Test | Frequency | Method |
|------|-----------|--------|
| Rollback to previous manifest | Monthly | `make rollback ENVIRONMENT=staging MANIFEST=2` |
| DynamoDB PITR restore | Quarterly | Restore to staging, validate data |
| Container crash recovery | Weekly | Kill ECS task, observe auto-recovery |
| Secret rotation | Every 90 days | Automatic via rotation Lambda |
| Full stack redeploy | Quarterly | `cdk destroy && cdk deploy` in staging |
