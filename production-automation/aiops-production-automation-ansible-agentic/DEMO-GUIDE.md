# AIOps Self-Healing Infrastructure — Demo Guide

Complete guide to deploy, test all three remediation modes, and tear down.

---

## Prerequisites

| Tool | Required | Check |
|------|----------|-------|
| AWS CLI v2 | Yes | `aws --version` |
| Node.js 20+ | Yes | `node --version` |
| Python 3.11+ | Yes | `python --version` |
| CDK (global) | Yes | `cdk --version` |
| MFA device | Yes | Configured for your IAM user |
| SES verified email | Yes | For approval/notification emails |

---

## Step 1: Deploy Everything

### 1.1 Authenticate with MFA

```powershell
.\scripts\mfa_auth.ps1 -TokenCode YOUR_6_DIGIT_CODE
```

This writes temporary credentials to `~/.aws/credentials` under the `[mfa]` profile.
Credentials last 12 hours and work across all terminals.

Verify:
```powershell
aws s3 ls --profile mfa
```

### 1.2 Install Dependencies

```powershell
pip install -e ".[dev,cdk]"
```

### 1.3 CDK Synth (validate templates)

```powershell
cdk synth --all --context environment=dev --profile mfa
```

### 1.4 Deploy CDK Stacks

```powershell
# Deploy all stacks in order (~10 minutes)
cdk deploy Aiops-dev-Network Aiops-dev-Data Aiops-dev-Compute Aiops-dev-Observability Aiops-dev-Monitoring Aiops-dev-Simulation --context environment=dev --require-approval never --profile mfa
```

Or use the Makefile:
```powershell
$env:AWS_PROFILE = "mfa"
make deploy ENVIRONMENT=dev
```

### 1.5 Build and Push Docker Image

Local podman has networking issues on Windows. Use CodeBuild instead:

```powershell
$env:AWS_PROFILE = "mfa"
python scripts/build_and_push.py --tag latest-dev --region us-east-1 --profile mfa
```

This creates a temporary CodeBuild project, builds the image in AWS, pushes to ECR, and cleans up.

### 1.6 Force ECS to Pull New Image

```powershell
aws ecs update-service --cluster aiops-cluster-dev --service <SERVICE_NAME> --force-new-deployment --region us-east-1 --profile mfa
```

### 1.7 Fix Cloud Map Port Registration

After each ECS deployment, the new task registers without port 8080. Fix it:

```powershell
# Get current instance
$inst = aws servicediscovery list-instances --service-id srv-pva2aprxa5q7qzu6 --region us-east-1 --profile mfa --query "Instances[0]" --output json | ConvertFrom-Json
$id = $inst.Id
$ip = $inst.Attributes.AWS_INSTANCE_IPV4

# Register with port
aws servicediscovery register-instance --service-id srv-pva2aprxa5q7qzu6 --instance-id $id --attributes "AWS_INSTANCE_IPV4=$ip,AWS_INSTANCE_PORT=8080,AWS_INIT_HEALTH_STATUS=HEALTHY" --region us-east-1 --profile mfa
```

### 1.8 Verify Health

```powershell
curl -s https://<API_GATEWAY_ID>.execute-api.us-east-1.amazonaws.com/health
```

Expected:
```json
{"status":"healthy","dependencies":{"sqs":"healthy","dynamodb":"healthy","ansible_binary":"ok","mapping_config":"ok","asset_inventory":"ok"}}
```

---

## Step 2: Test CPU Stress (Rule Mode)

**Scenario**: High CPU alert fires, system finds matching playbook, sends email with Approve button, operator clicks, SSM kills stress-ng.

### Quick Test (immediate alert, no CloudWatch wait)

```powershell
$env:AWS_PROFILE = "mfa"
python demo/break_target.py --mode cpu --duration 120 --trigger-alert
```

### Full Test (via CloudWatch alarm, ~2 min delay)

```powershell
python demo/break_target.py --mode cpu --duration 600
```

### What Happens

1. `stress-ng --cpu 2` runs on target EC2 for the specified duration
2. Alert `HighCPUUsage` fires (immediately with `--trigger-alert`, or via CloudWatch)
3. Pipeline matches rule: `high-cpu-web` to `playbooks/fix_high_cpu.yml`
4. Approval email sent to configured address
5. Email link scanner or operator clicks Approve
6. SSM RunCommand executes `pkill stress-ng` + restarts app on target
7. `remediation_success_total` increments

### Verify

```powershell
# Check metrics — confirm remediation succeeded
curl -s https://<API_URL>/metrics | Select-String "remediation_success"

# Check CloudWatch alarm state
aws cloudwatch describe-alarms --alarm-names aiops-target-cpu-dev --region us-east-1 --profile mfa --query "MetricAlarms[0].StateValue" --output text

# Verify stress-ng was killed on the target
aws ssm send-command --instance-ids <INSTANCE_ID> --document-name AWS-RunShellScript --parameters commands=["ps aux | grep stress-ng | grep -v grep || echo No stress-ng running"] --region us-east-1 --profile mfa --output text --query Command.CommandId

# Check logs for the full pipeline flow
aws logs tail /aiops/dev/ecs --region us-east-1 --since 5m --profile mfa
```

Expected metrics output:
```
remediation_success_total{alert_name="HighCPUUsage",severity="P1"} 1
```

Expected log flow:
```
Pipeline started
Rule matched: high-cpu-web → playbooks/fix_high_cpu.yml (sending approval email)
Approval stored: incident=... token=... expires=...
Approval email sent for incident ... to ravindya@in.ibm.com
Approval consumed: incident=... token=...
Executing approved remediation: incident=... action=Execute playbooks/fix_high_cpu.yml
SSM command sent: command_id=... instance=i-0ea05de70aa7d590d
Approved remediation completed: incident=... status=success duration=...
```

---

## Step 3: Test Memory Pressure (Rule Mode)

**Scenario**: High memory alert fires, playbook matched, approval sent, SSM restarts the app process.

### Quick Test

```powershell
$env:AWS_PROFILE = "mfa"
python demo/break_target.py --mode memory --duration 120 --trigger-alert
```

### Full Test

```powershell
python demo/break_target.py --mode memory --duration 300
```

### What Happens

1. `stress-ng --vm 2 --vm-bytes 80%` allocates memory on target EC2
2. Alert `HighMemoryUsage` fires
3. Pipeline matches rule: `memory-pressure` to `playbooks/restart_process.yml`
4. Approval email sent
5. Operator approves, SSM kills processes and restarts app
6. Memory freed when stress-ng dies, app restarts cleanly

### Expected Log Flow

```
Pipeline started
Rule matched: memory-pressure -> playbooks/restart_process.yml
Approval email sent
Approval consumed
SSM command sent: command_id=...
Approved remediation completed: status=success
```

---

## Step 4: Test Network Flood (AI Agent Mode)

**Scenario**: Unknown network alert fires, no playbook match, AI (Bedrock) analyzes, advisory email with suggested steps sent (no auto-execute).

### Quick Test

```powershell
$env:AWS_PROFILE = "mfa"
python demo/break_target.py --mode network --duration 60 --trigger-alert
```

### Full Test

```powershell
python demo/break_target.py --mode network --duration 300
```

### What Happens

1. Rapid-fire curl/DNS requests flood the target network interface
2. Alert `NetworkFloodDetected` fires (no matching playbook rule)
3. Pipeline switches to AI Agent Mode
4. Amazon Bedrock (Nova Pro) analyzes the alert context
5. Advisory email sent with AI-generated suggested remediation steps
6. No auto-execute: operator must fix manually

### Alternative: Custom Unknown Alert

Test AI mode with any alert that has no playbook mapping:

```powershell
$env:AWS_PROFILE = "mfa"
python -c "
import boto3, json
client = boto3.client('lambda', region_name='us-east-1')
payload = {
    'alert_name': 'DatabaseConnectionPoolExhausted',
    'severity': 'critical',
    'service_name': 'postgres-primary',
    'instance': 'db-server-01:5432',
    'summary': 'All 100 DB connections exhausted, queries timing out'
}
r = client.invoke(FunctionName='aiops-alert-trigger-dev', Payload=json.dumps(payload).encode())
print(json.loads(r['Payload'].read()))
"
```

### Expected Log Flow

```
Pipeline started
No playbook match for 'NetworkFloodDetected' - switching to AI agent mode
Model amazon.nova-pro-v1:0 ...
AI advisory email sent for incident ...
```

---

## Step 5: Monitor and Observe

### Health Endpoint

```powershell
curl -s https://<API_URL>/health | python -m json.tool
```

### Prometheus Metrics

```powershell
curl -s https://<API_URL>/metrics
```

Key metrics:
- `alerts_received_total` — total alerts processed
- `remediation_success_total` — successful fixes
- `remediation_failure_total` — failed attempts
- `no_playbook_match_total` — AI mode triggers

### ECS Logs (real-time)

```powershell
aws logs tail /aiops/dev/ecs --region us-east-1 --follow --profile mfa
```

### CloudWatch Alarms

```powershell
aws cloudwatch describe-alarms --alarm-name-prefix aiops --region us-east-1 --profile mfa --query "MetricAlarms[].{Name:AlarmName,State:StateValue}" --output table
```

---

## Step 6: Destroy Everything

### 6.1 Destroy All Stacks

```powershell
cdk destroy --all --context environment=dev --force --profile mfa
```

Or in reverse order:
```powershell
cdk destroy Aiops-dev-Simulation --context environment=dev --force --profile mfa
cdk destroy Aiops-dev-Monitoring --context environment=dev --force --profile mfa
cdk destroy Aiops-dev-Observability --context environment=dev --force --profile mfa
cdk destroy Aiops-dev-Compute --context environment=dev --force --profile mfa
cdk destroy Aiops-dev-Data --context environment=dev --force --profile mfa
cdk destroy Aiops-dev-Network --context environment=dev --force --profile mfa
```

### 6.2 Clean Up Orphaned Resources

```powershell
# CodeBuild source bucket
aws s3 rb s3://aiops-codebuild-source-533267042240-us-east-1 --force --profile mfa

# CodeBuild IAM role
aws iam detach-role-policy --role-name aiops-codebuild-service-role --policy-arn arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryPowerUser --profile mfa
aws iam detach-role-policy --role-name aiops-codebuild-service-role --policy-arn arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess --profile mfa
aws iam detach-role-policy --role-name aiops-codebuild-service-role --policy-arn arn:aws:iam::aws:policy/CloudWatchLogsFullAccess --profile mfa
aws iam delete-role --role-name aiops-codebuild-service-role --profile mfa
```

### 6.3 Verify Cleanup

```powershell
aws cloudformation list-stacks --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE --region us-east-1 --profile mfa --query "StackSummaries[?contains(StackName,'Aiops')]" --output table
```

Should return empty.

---

## Quick Reference

| Command | Description |
|---------|-------------|
| `python demo/break_target.py --mode cpu --trigger-alert` | CPU stress + immediate alert |
| `python demo/break_target.py --mode memory --trigger-alert` | Memory stress + immediate alert |
| `python demo/break_target.py --mode network --trigger-alert` | Network flood + immediate alert |
| `python demo/break_target.py --mode cpu --duration 600` | CPU stress, wait for CloudWatch |
| `python scripts/mfa_auth.ps1 -TokenCode XXXXXX` | Refresh MFA credentials (12h) |
| `python scripts/build_and_push.py --tag latest-dev` | Build + push image via CodeBuild |
| `curl <API_URL>/health` | Service health check |
| `curl <API_URL>/metrics` | Prometheus metrics |

---

## Costs

| Resource | ~Cost/month (dev) |
|----------|-------------------|
| ECS Fargate (SPOT) | $8 |
| NAT Gateway | $32 |
| EC2 t3.micro (simulation) | $8 |
| API Gateway | $1 |
| DynamoDB (on-demand) | $1 |
| AMP Workspace | $0 (if no data) |
| CloudWatch | $3 |
| SES | $0 |
| **Total** | **~$53/month** |

Destroy when not testing to avoid NAT Gateway charges:
`cdk destroy --all --context environment=dev --force --profile mfa`

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| MFA expired | `.\scripts\mfa_auth.ps1 -TokenCode NEW_CODE` |
| 500 from API Gateway | Re-register Cloud Map port 8080 (Step 1.7) |
| `Internal Server Error` on health | Same as above, port not registered |
| No email received | Verify SES: `aws ses get-identity-verification-attributes --identities YOUR_EMAIL --region us-east-1` |
| Remediation fails quickly (1-2s) | Check logs for SSM errors; may need `set +e` in playbook commands |
| `consumed` reserved keyword error | Fixed in latest code, rebuild and push image |
| Alarm stays OK after stress | CloudWatch needs 2 consecutive datapoints; use `--trigger-alert` instead |
| Podman build fails (nftables) | Use `python scripts/build_and_push.py` (CodeBuild) instead |
| ECR push 403 | MFA expired or wrong profile, re-authenticate |
| AI says reasoning_timeout | Enable Bedrock models: Console, Bedrock, Model Access, Enable Nova Pro |
