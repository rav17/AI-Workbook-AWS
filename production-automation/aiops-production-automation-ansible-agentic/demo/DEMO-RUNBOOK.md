# Demo Runbook: P1 Incident to AWS DevOps Agent RCA Email

A step-by-step script for showing the solution to an audience. The demo creates a real fault on
two EC2 targets and lets the CloudWatch alarms raise the alerts (nothing calls the alert Lambda
directly). Each alert goes through the self-healing pipeline and AWS DevOps Agent, and into the
operator's inbox as an approval or advisory email and a root cause analysis (RCA) email.

| Host | Fault | Alarm | Alert | Pipeline path |
|------|-------|-------|-------|---------------|
| Primary | Memory held at about 88% (available below 20%) | `aiops-target-memory-dev` | `HighMemoryUsage` | Rule mode: approval email for `fix_high_memory.yml` |
| Secondary | HTTP flood on port 8080, sent by the primary | `aiops-target-network-dev` | `NetworkFloodDetected` | AI mode: advisory email (no playbook) |

Both alerts are critical, so both are also forwarded to DevOps Agent. The primary's CPU alarm
stays OK: the memory stress holds memory without spinning, and no CPU load is generated.

Related: [DEMO-GUIDE.md](../DEMO-GUIDE.md) (rule and AI modes), [docs/devops-agent-integration.md](../docs/devops-agent-integration.md),
[architecture diagram](../architecture/aiops-self-healing-architecture.drawio),
[solution architect deck](../docs/AIOps-Solution-Architect-Deck.pptx).

## What the audience sees

| # | Moment | Where | Time |
|---|--------|-------|------|
| 1 | Memory load starts on the primary and the flood starts towards the secondary | Terminal | 0:00 |
| 2 | Memory and network alarms go to ALARM on their own | Terminal C | 1 to 2 min |
| 3 | Pipeline sends the approval and advisory emails and forwards both to DevOps Agent | ECS log tail | 1 to 2 min |
| 4 | Operator approves; `fix_high_memory.yml` kills the memory stress | Inbox, ECS log tail | any time |
| 5 | Two investigations appear with priority CRITICAL, then complete | DevOps Agent web app or CLI | about 5 min |
| 6 | Two RCA emails arrive (about 1 s after each completion) | Operator inbox | 5 to 6 min |

## Prerequisites

| Item | Check |
|------|-------|
| AWS CLI 2.39 or newer | `aws --version` (older versions have no `devops-agent` commands) |
| Python venv with dependencies | `.\.venv\Scripts\python.exe -m pip install -e ".[dev,cdk]"` |
| Node.js 20+ and CDK | `npx aws-cdk@2 --version` |
| SES sender and recipient verified | `aws ses list-identities --region us-east-1`; the operator address is `costCenterEmail` in `cdk.json` |
| MFA device | Needed for every AWS call (account policy `ForceMFA`) |

SES in a new account is in sandbox mode: both the sender and the recipient must be verified.

## 1. Authenticate

```powershell
.\scripts\mfa_auth.ps1 -TokenCode <6-digit-code>
$env:AWS_PROFILE = "mfa"
```

The credentials last 12 hours. If a command returns `ExpiredToken`, run this step again.

## 2. Create the environment (once, about 20 to 25 minutes)

```powershell
.\.venv\Scripts\python.exe scripts\aiops_env.py up --env dev
```

The command builds the image in CodeBuild, deploys the six CDK stacks, creates the DevOps Agent Space,
roles and HMAC webhook, stores the webhook in Secrets Manager, restarts ECS and waits for `/health`.
It also enables the findings Lambda (`devopsAgentFindingsEnabled=true`) that sends the RCA email.

Check the result at any time (read-only):

```powershell
.\.venv\Scripts\python.exe scripts\aiops_env.py status --env dev
```

Do this at least an hour before recording. A new Agent Space runs billed `SYSTEM_LEARNING` tasks
while it maps the account.

## 3. Rehearse (preflight only, changes nothing)

```powershell
.\.venv\Scripts\python.exe demo\trigger_p1_incident.py --dry-run
```

Every preflight line must say `OK`:

- the memory, network and CPU alarms exist, have ALARM and OK actions, watch the right host
  (memory and CPU on the primary, network on the secondary), and are not already in ALARM
- the memory metric (`mem_available_percent`) is arriving from the CloudWatch agent
- the findings Lambda exists and the DevOps Agent webhook secret has a non-empty URL

If an alarm is still in ALARM from a previous take, wait for it to return to OK.

## 4. Record the demo

Open three terminals (all with `$env:AWS_PROFILE = "mfa"`) and the DevOps Agent web app
(the URL is in `status`).

**Terminal A: pipeline log**

```powershell
aws logs tail /aiops/dev/ecs --region us-east-1 --follow --since 5m `
  --filter-pattern '?remediation ?playbook ?DevOps ?approval ?advisory'
```

This shows the approval and advisory emails, the DevOps Agent forwarding, and the playbook run
(SSM command sent, completion status). A filter of just `"DevOps Agent"` hides the playbook lines.

**Terminal B: findings Lambda log**

```powershell
$g = aws logs describe-log-groups --log-group-name-prefix Aiops-dev-Observability-DevOpsAgentFindings `
  --region us-east-1 --query "logGroups[0].logGroupName" --output text
aws logs tail $g --region us-east-1 --follow
```

The findings Lambda's log group has a generated name (it is not `/aws/lambda/aiops-devops-findings-dev`).

**Terminal C: fire the incident**

```powershell
.\.venv\Scripts\python.exe demo\trigger_p1_incident.py
```

Options: `--duration 900` (longer load; default 600), `--no-wait` (start the load and exit),
`--skip-preflight`, `--dry-run`. The script waits until both alarms are in ALARM and exits non-zero
if either does not fire or the CPU alarm fires.

Narration points:

1. *Terminal C*: the script only creates load through SSM. It does not send any alert itself; the
   CloudWatch alarms detect the load, the same way production would.
2. *Terminal C*: `aiops-target-network-dev -> ALARM` (secondary) and
   `aiops-target-memory-dev -> ALARM` (primary), usually within 1 to 2 minutes.
3. *Terminal A*: `Approval email sent` for `HighMemoryUsage`, `AI advisory email sent` for
   `NetworkFloodDetected`, and `Incident forwarded to AWS DevOps Agent` for both
   (`trigger=critical` and `trigger=unmatched`). The pipeline never blocks on the agent.
4. *Inbox*: approve the `HighMemoryUsage` email. Terminal A shows `Executing approved remediation`,
   `SSM command sent ... playbook=playbooks/fix_high_memory.yml` and
   `Approved remediation completed ... status=success`. Do not approve if the load should keep
   running for the rest of the demo.
5. *Web app*: two investigations, references `aiops-<incident_id>-critical` and
   `aiops-<incident_id>-unmatched`. The agent has read-only access and looks at CloudWatch, SSM
   history and the instances.
6. *Terminal B*: when each investigation completes, EventBridge invokes the findings Lambda, which reads
   the summary and sends the RCA email.
7. *Inbox*: the RCA emails. Point out that DevOps Agent changed nothing; the only change on a host was
   the playbook the operator approved.

Stop the load early if needed:

```powershell
aws ssm send-command --instance-ids <instance-id> --document-name AWS-RunShellScript `
  --parameters 'commands=["pkill stress-ng"]' --region us-east-1
```

## 5. Verify without the inbox

```powershell
# Newest investigations (replace <space> with the Agent Space id from status)
aws devops-agent list-backlog-tasks --agent-space-id <space> --sort-field CREATED_AT --order DESC --region us-east-1

# Audit records written by the findings Lambda (status sent)
aws dynamodb scan --table-name AiopsIncidentMemory-dev --region us-east-1 `
  --filter-expression "begins_with(incident_id, :p)" --expression-attribute-values '{":p":{"S":"devops-finding#"}}'

# Failures
aws sqs get-queue-attributes --region us-east-1 --attribute-names ApproximateNumberOfMessages `
  --queue-url (aws sqs get-queue-url --queue-name aiops-devops-findings-dlq-dev --region us-east-1 --query QueueUrl --output text)
```

Each record shows `status`, `detail_type` (Completed or Linked) and the `task_id`.

### Follow one incident by ID

Every log line for an alert carries its `incident_id` (shown in Terminal A, the emails and the
DevOps Agent reference `aiops-<incident_id>-...`). To see the whole story of one incident:

```powershell
# First block of the ID: no hyphens, so no quoting is needed
aws logs tail /aiops/dev/ecs --region us-east-1 --since 2h --filter-pattern ea3dea34

# Full ID: escape the inner quotes (needed in Windows PowerShell 5.1)
aws logs tail /aiops/dev/ecs --region us-east-1 --since 2h `
  --filter-pattern '\"ea3dea34-3759-464c-9855-2d00564e3f4d\"'
```

Replace the example ID with your own. Notes:

- `--since` is required for a finished incident. Without it, `aws logs tail` looks back only
  10 minutes, and `--follow` then waits for new lines that never come.
- Windows PowerShell 5.1 drops inner double quotes when it calls `aws.exe`, so
  `'"ea3dea34-..."'` reaches CloudWatch unquoted and matches nothing (the hyphens need quotes).
  Use the first block of the ID or the escaped form above. PowerShell 7 (`pwsh`) passes the
  quotes correctly.
- The `SSM command sent ... playbook=...` line has no incident ID; it shows with the Terminal A
  filter. To read the playbook's own output on the host:

```powershell
aws ssm get-command-invocation --command-id <command_id from the log> `
  --instance-id <primary instance id> --region us-east-1 --query StandardOutputContent --output text
```

## 6. Optional: show the other two modes

The main demo already shows rule mode (`HighMemoryUsage`) and AI mode (`NetworkFloodDetected`).
For the CPU playbook:

| Mode | Command | Result |
|------|---------|--------|
| Rule mode (CPU) | `python demo/break_target.py --mode cpu --duration 600` | The CPU alarm fires; approval email; click Approve; SSM runs `fix_high_cpu.yml` |

Without `--trigger-alert`, `break_target.py` only creates load and the alarm raises the alert.
`--trigger-alert` calls the alert Lambda directly, which skips the alarm.

## Expected side effects (not errors)

- When the load ends (default 600 s), both alarms return to OK and send `resolved`. A `HighMemoryUsage`
  approval that was never clicked is cancelled; the link then shows "Alert already resolved".
- The secondary's CPU alarm does not exist by design; the primary's must stay OK. If it fires, a
  `HighCPUUsage` approval email follows and the script exits non-zero.
- The advisory email has "Did this help?" links. An answer is recorded as the incident outcome and
  feeds model routing for future `NetworkFloodDetected` alerts.
- The agent can see the `SendCommand` calls in CloudTrail, so the RCA may name the stress test as a
  deliberate demo fault injection. It still reports the symptoms with timestamps. Tell the audience
  this is a synthetic fault.

## Last verified run

2026-11-19, dev, us-east-1, `trigger_p1_incident.py` (default 600 s, alarm-driven):

| UTC | Event |
|-----|-------|
| 05:23 | Memory load on the primary and flood towards the secondary started through SSM |
| 05:24:52 | Memory alarm to ALARM (available memory 13.7%); network alarm to ALARM |
| 05:24:54 | `NetworkFloodDetected` (secondary) forwarded to DevOps Agent (`trigger=unmatched`); advisory email at 05:24:58 |
| 05:24:56 | `HighMemoryUsage` (primary): approval email sent; forwarded to DevOps Agent (`trigger=critical`) |
| 05:26:28 | Approval confirmed; SSM ran `fix_high_memory.yml` |
| 05:26:38 | Playbook completed (`success`, 9.2 s): killed `stress-ng-vm` at 46.5% memory; available memory back to 59% |
| 05:28:52 | Memory alarm back to OK. The primary's CPU alarm stayed OK throughout |

Earlier run, 2026-11-18, with the previous version of the script (direct alert
`CriticalServiceOutage`, `--duration 420`):

| UTC | Event |
|-----|-------|
| 06:36:33 | Load started on `i-05e764bd3f50c4659` through SSM |
| 06:37:15 | `CriticalServiceOutage` accepted by the webhook (HTTP 200); DevOps Agent INVESTIGATION created, priority CRITICAL |
| 06:37:26 | Simulation alarm `NetworkFloodDetected` fires; linked to the main investigation |
| 06:41:29 | Simulation alarm `HighCPUUsage` fires; linked |
| 06:42:49 | Investigation COMPLETED (about 5.5 minutes) with a 5,684-character summary |
| 06:42:50 | Findings Lambda sends the RCA email; audit record `sent`; DLQ 0 |

The rule matched 3 events and invoked the Lambda 3 times. SES accepted every message with no bounces.

## 7. Clean up (stop the billing)

```powershell
.\.venv\Scripts\python.exe scripts\aiops_env.py down --env dev
```

This removes the Agent Space, both IAM roles, the stacks and the retained leftovers (table, secrets, log groups).
It cannot be undone. Costs while up: NAT gateway, ECS task, interface endpoints, and DevOps Agent at about
$0.0083 per active second (roughly $0.60 to $0.90 per investigation).

## Troubleshooting

| Symptom | Cause and fix |
|---------|---------------|
| `ExpiredToken` or `AccessDenied ... explicit deny ... ForceMFA` | Run step 1 again and set `AWS_PROFILE=mfa` |
| Preflight: webhook has empty `url` | `aiops_env.py up` did not finish the Agent step; run it again (it is idempotent) |
| Preflight: findings Lambda not found | The stack was deployed without `devopsAgentFindingsEnabled=true`; run `aiops_env.py up --env dev` again |
| No `Incident forwarded` log line | Task started before the webhook was stored; force a new ECS deployment (`up` does this) |
| Investigation created, no email | Check Terminal B and the DLQ; confirm SES sender and recipient are verified |
| Email says the agent could not find the host | The agent reports what it can see; run with load (`--duration 600`) and wait a few minutes after the instance has metrics |
| Second take links to the first investigation | The agent groups the same host and alert; wait for the first to finish |
| Preflight: alarm "already in ALARM" | The previous take's load is still running or the alarm has not cleared; wait a few minutes |
| Preflight: network alarm watches the wrong host | The Simulation stack predates the two-host layout; run `aiops_env.py up --env dev` again |
| An alarm does not fire | Check `mem_available_percent` in CloudWatch (agent installed by the SSM association) and that `fake-app` answers on port 8080 on the secondary |
| `aws logs tail ... --filter-pattern '"<incident_id>"'` prints nothing | Add `--since 2h`, and in Windows PowerShell 5.1 use the first block of the ID or `'\"<id>\"'` (see Follow one incident by ID) |
| `stress-ng` install fails | The target needs internet through NAT; check the Simulation stack |
