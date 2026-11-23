# AWS DevOps Agent Integration

AWS DevOps Agent investigates incidents and proposes mitigations. It does **not**
execute anything in our pipeline. Our solution remains the only component that
changes hosts, and every change still goes through PlanValidator and the human
approval gate.

| Phase | Scope | Status |
|---|---|---|
| 1 | Forward selected incidents to a DevOps Agent generic webhook (HMAC) | **Implemented, verified end to end in dev (2026-11-10)** |
| 2 | Email DevOps Agent's findings to the operator (EventBridge, Lambda, SES) | **Implemented behind a flag; tested, and run live in a scratch stack (2026-11-17)** |
| 3 | Custom MCP server, agent skills, release readiness review | Planned (future) |

References: [Invoking DevOps Agent through Webhook](https://docs.aws.amazon.com/devopsagent/latest/userguide/configuring-integrations-and-knowledge-invoking-devops-agent-through-webhook.html),
[About AWS DevOps Agent](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent.html),
[Supported Regions](https://docs.aws.amazon.com/devopsagent/latest/userguide/about-aws-devops-agent-supported-regions.html).

---

## Phase 1 — Forward incidents for investigation (implemented)

### What gets forwarded

| Trigger | When | Code |
|---|---|---|
| `unmatched` | No playbook matched the alert | `src/app.py` `_process_and_notify` |
| `critical` | Critical alert with a new approval request (after duplicate suppression) | `src/app.py` `_process_and_notify` |
| `failed` | An approved remediation failed or raised an error | `src/app.py` `_execute_approved_remediation` |
| `resolved` (opt-in) | The alert recovered; sent against the original incident ids forwarded by the same task | `src/app.py` `_process_and_notify` |

Rule-matched, non-critical alerts are **not** forwarded; the fast rule path is unchanged.

`resolved` is not in the default triggers. The 2026-11-16 spike (below) found no visible effect: the
webhook accepted the update, but the task's status, version and `updatedAt` did not change and no new
task appeared (it may have been de-duplicated, because it reuses the incident id). Leave it off. It only
works for incidents forwarded by the same ECS task, so with several tasks some updates are skipped.

### Context sent with each incident (Phase 1b)

All context is in `description` (the only free-text field the agent reads):

- Redacted alert labels (sensitive-looking keys such as `*key*`, `*token*`, `*password*`, `*secret*`
  are dropped, not masked; at most 12 labels, 120 characters each) and the `runbook_url` annotation
  (https/http only).
- For `failed`: the playbook that just failed, stated as context ("Already tried and FAILED").
  The spike showed the agent uses this.
- All alert-derived text is stripped of control characters and truncated, so a value cannot start a
  new line in the description.
- **No playbook list and no output-format instruction.** An earlier version asked the agent to end its
  summary with `AIOPS_PLAYBOOK: <path>`. The spike showed the agent ignores such instructions (0 of 3);
  its summary follows a fixed template. Playbook selection will be done by our own code (Phase 2b).

Also fixed: every alert in an Alertmanager batch used the first alert's incident id. Each alert now
keeps its own id, so the de-duplication no longer skips batched alerts.

### Safety and cost controls (`src/devops_agent.py`)

- **Off unless configured:** requires `DEVOPS_AGENT_ENABLED=true` **and** a non-empty https webhook URL and secret.
- **Never blocks the pipeline:** runs in a worker thread with a 5s timeout and 2 retries (1s, 2s backoff). Auth and format errors (4xx except 429) are not retried. All failures are logged with `incident_id` and never raised.
- **Cost guard:** DevOps Agent bills per active agent-second. There is a per-task cap of `DEVOPS_AGENT_MAX_PER_HOUR` (default 20) and per-incident de-duplication. The cap is per ECS task, so the fleet-wide maximum is cap × task count. Set an AWS Budget filtered on *AWS DevOps Agent* as well.
- **Minimal data:** only the alert name, severity, host, service, environment, region, summary, redacted labels, the runbook URL, what was already tried, and our incident reference are sent. DevOps Agent ignores the `data` field, so all context goes into `description`.
- **Traceability:** `incidentId` is `aiops-<our incident_id>-<trigger>`. Search for it in the Agent Space.

### Configuration

| Setting | Where | Default |
|---|---|---|
| `devopsAgentEnabled` | CDK context (`--context devopsAgentEnabled=true`) | `false` |
| `devopsAgentForwardOn` | CDK context (`--context devopsAgentForwardOn=unmatched,failed,critical,resolved`); validated at synth | `unmatched,failed,critical` |
| `DEVOPS_AGENT_FORWARD_ON` | Task env, set from the context above (`compute_stack.py`) | `unmatched,failed,critical` |
| `DEVOPS_AGENT_ENABLED`, `DEVOPS_AGENT_FORWARD_ON` | **GitHub repository variables** read by `cd.yml` (Compute, Observability and rollback steps) | `false`, `unmatched,failed,critical` |
| `DEVOPS_AGENT_MAX_PER_HOUR` | Task env (`compute_stack.py`) | `20` |
| `devopsAgentFindingsEnabled` | CDK context; GitHub repository variable `DEVOPS_AGENT_FINDINGS_ENABLED` (read by the Observability steps of `cd.yml`) | `false` |
| `devopsAgentAdvisoryEnabled` | CDK context (`--context devopsAgentAdvisoryEnabled=true`) or `aiops_env.py up --advisory`; not wired into `cd.yml` yet. Needs the two flags above. See Phase 2b | `false` |
| `DEVOPS_AGENT_ADVISORY_MODE` | Task env, set from the context above (`compute_stack.py`) | `false` |
| URL, HMAC secret, web app URL | Secrets Manager `/aiops/{env}/devops-agent-webhook` (JSON keys `url`, `secret`, `web_app_url`) | Empty placeholders |

CDK creates the secret with **empty `url`/`web_app_url` and a random placeholder
`secret`**, so ECS tasks always start. Forwarding stays inactive until real values are stored.

### One-command provisioning

`scripts/aiops_env.py` creates and removes the whole environment, including everything below:

```powershell
.\.venv\Scripts\python.exe scripts\aiops_env.py up     --env dev   # stacks + DevOps Agent + health check
.\.venv\Scripts\python.exe scripts\aiops_env.py down   --env dev   # Agent Space, roles, stacks, leftovers
.\.venv\Scripts\python.exe scripts\aiops_env.py status --env dev   # read-only
```

The Agent Space ID changes every time `up` recreates it. Run `status` for the current value.

### Dev setup as of 2026-11-10 (recreated by `aiops_env.py up`, us-east-1)

> **Stale as of 2026-11-16:** none of these exist any more. There is no `aiops-dev` Agent Space,
> role, secret or `Aiops-dev-*` stack in the account. Run `aiops_env.py up --env dev` to recreate them
> (new ids). The table is kept as a record of the shape of the setup.

| Resource | Value |
|---|---|
| Agent Space | `aiops-dev` (`1db03cac-f242-41fc-b2f0-9de5bdb960ab`), elevated actions **off** |
| Agent Space role | `aiops-dev-DevOpsAgentRole-AgentSpace`: AWS managed `AIDevOpsAgentAccessPolicy` + inline Resource Explorer service-linked-role permission |
| Operator app role | `aiops-dev-DevOpsAgentRole-WebappAdmin`: AWS managed `AIDevOpsOperatorAppAccessPolicy` |
| Account association | `533267042240` as `monitor` |
| Operator web app | https://1db03cac-f242-41fc-b2f0-9de5bdb960ab.aidevops.global.app.aws |
| Generic webhook | HMAC `event_channel` association, stored in `/aiops/dev/devops-agent-webhook` |

Both roles trust only `aidevops.amazonaws.com`, conditioned on `aws:SourceAccount`
and `aws:SourceArn = arn:aws:aidevops:us-east-1:533267042240:agentspace/*`.

### Setup steps (CLI)

Requires AWS CLI **2.39 or newer** (2.34 has no `devops-agent` commands). The steps follow the
[AWS DevOps Agent CLI onboarding guide](https://docs.aws.amazon.com/devopsagent/latest/userguide/getting-started-with-aws-devops-agent-cli-onboarding-guide.html).

1. **IAM roles:** create the two roles above with the trust policy from the onboarding guide, and attach the managed policies.
2. **Agent Space:**

   ```powershell
   aws devops-agent create-agent-space --name aiops-dev --tags project=aiops-self-healing,environment=dev --region us-east-1 --profile mfa
   ```

3. **Associate the account** (configuration JSON in a file, to avoid shell-quoting problems):

   ```json
   {"aws":{"assumableRoleArn":"arn:aws:iam::533267042240:role/aiops-dev-DevOpsAgentRole-AgentSpace","accountId":"533267042240","accountType":"monitor"}}
   ```

   ```powershell
   aws devops-agent associate-service --agent-space-id <id> --service-id aws --configuration file://assoc.json --region us-east-1 --profile mfa
   aws devops-agent enable-operator-app --agent-space-id <id> --auth-flow iam --operator-app-role-arn arn:aws:iam::533267042240:role/aiops-dev-DevOpsAgentRole-WebappAdmin --region us-east-1 --profile mfa
   ```

4. **Create the generic webhook.** A generic webhook is an `eventChannel` association, and HMAC is the default:

   ```powershell
   aws devops-agent associate-service --agent-space-id <id> --service-id event_channel --configuration file://eventchannel.json --region us-east-1 --profile mfa
   # eventchannel.json: {"eventChannel":{}}
   ```

   The response contains `webhook.webhookUrl` and `webhook.webhookSecret`. **The secret is returned only once.** Write it straight to Secrets Manager (step 5) without printing it. `aws devops-agent list-webhooks` returns the URL but never the secret.

   *Console alternative:* Agent Space → *Capabilities* → *Agent Space Webhook* → *Add webhook* → **HMAC**.

5. **Store them in Secrets Manager.** Keep the JSON keys exactly as shown; a missing key stops ECS tasks from starting.

   ```powershell
   $value = @{ url = "<webhook-url>"; secret = "<hmac-secret>"; web_app_url = "<optional web app url>" } | ConvertTo-Json -Compress
   aws secretsmanager put-secret-value --secret-id /aiops/dev/devops-agent-webhook --secret-string $value --profile mfa --region us-east-1
   ```

6. **Enable and deploy** (or just restart the tasks if the flag is already on). ECS reads secrets at task start:

   ```powershell
   npx aws-cdk@2 deploy Aiops-dev-Compute --context environment=dev --context devopsAgentEnabled=true --profile mfa
   # or, if already deployed with the flag on:
   aws ecs update-service --cluster aiops-cluster-dev --service <service-name> --force-new-deployment --profile mfa --region us-east-1
   ```

   Every `cdk deploy` must pass `--context devopsAgentEnabled=true`, otherwise forwarding is switched off again.

7. **Verify.** The startup log should show `DevOps Agent forwarding: active=True`. Then send an alert with no matching playbook (for example `python demo/break_target.py --mode network`). Expect `Incident forwarded to AWS DevOps Agent (trigger=unmatched, http=200)` in `/aiops/dev/ecs`, and a new investigation:

   ```powershell
   aws devops-agent list-backlog-tasks --agent-space-id <id> --region us-east-1 --profile mfa
   ```

   The task's `reference.referenceId` is `aiops-<incident_id>-unmatched`. Read the findings with `list-journal-records --execution-id <executionId>`, or in the operator web app.
8. **Rotating the secret:** rotate it in the Agent Space console, update the Secrets Manager value (step 5), then force a new ECS deployment.

### Verified end-to-end run (dev, 2026-11-10)

| UTC | Event |
|---|---|
| 08:49:37 | `demo/break_target.py --mode network` ran on `i-0bde43c900bac00c7` and fired `NetworkFloodDetected` |
| 08:49:44 | Pipeline: no playbook match |
| 08:49:45 | `Incident forwarded to AWS DevOps Agent (trigger=unmatched, http=200)` |
| 08:49:45 | DevOps Agent `INVESTIGATION` task created, priority CRITICAL, reference `aiops-4acb31c9-…-unmatched` |
| 08:49:48 | Advisory email sent |
| 08:53:38 | Investigation `COMPLETED` (about 4 minutes) |

DevOps Agent identified the triggering SSM command as a deliberate, self-terminating demo and
recommended no rollback. It also flagged two real gaps, both still to be confirmed:

- The flood targeted only link-local endpoints (IMDS, VPC DNS), which CloudWatch network metrics likely don't count, so the network alarm may not measure what the alert claims.
- The instance's `Name` tag (`aiops-target-dev`) doesn't match the alarm naming, which could break Name-based matching.

### Cost notes

- Billed per active agent-second (about $0.0083/s). This account is pay-as-you-go, with no trial.
- A new Agent Space runs billed `SYSTEM_LEARNING` tasks while it maps the account.
- Check usage with `aws devops-agent get-account-usage --region us-east-1`.
- To remove everything: `aws devops-agent delete-agent-space --agent-space-id <id>`, then delete the two IAM roles and set `/aiops/dev/devops-agent-webhook` back to an empty `url`. Deleting the space can't be undone.

---

## CD pipeline and the flag

Before this change `cd.yml` never passed `devopsAgentEnabled`, so **every CD deploy switched forwarding
off again**. The Observability job matters too: `cdk deploy ...-Observability` also deploys its dependency
`...-Compute`, so it must carry the same context. All of these now pass the flag: Compute diff and
deploy, Observability diff and deploy, and the rollback deploy.

To keep forwarding on after CD deploys, set these in GitHub (Settings, Secrets and variables, Variables;
use an environment-scoped variable per environment):

| Variable | Value |
|---|---|
| `DEVOPS_AGENT_ENABLED` | `true` |
| `DEVOPS_AGENT_FORWARD_ON` (optional) | `unmatched,failed,critical` (leave `resolved` off; see the spike results) |

If the variables are unset, CD deploys with forwarding **off**, which is the previous behaviour.
`scripts/deploy.py` has its own deploy path and is not changed here.

## Spike results (2026-11-16)

Run against a temporary Agent Space (`aiops-spike`, since deleted) with three incidents sent through the real
`DevOpsAgentForwarder`. The test hosts were fake instance ids, so the agent found no telemetry and never
reached a root cause. Treat the quality of its findings as untested.

| Question | Result |
|---|---|
| Investigation time and cost | 74 to 105 seconds each, roughly $0.60 to $0.90 (estimate at about $0.0083/s) |
| Summary format | `investigation_summary_md` is a markdown **string** (Symptoms, Findings, Other Gaps), 800 to 2,800 characters, one record per execution |
| Structured form | An `investigation_summary` record holds **JSON as a string** (symptoms, findings with `finding_type`, gaps). Other record types seen: `finding`, `symptom`, `observation`, `investigation_gap`, `utilization`, `message`, `ui_investigation_summary` |
| Mitigation | No `mitigation_summary_md` and no mitigation or recommendation record in any run |
| Mapping to our incident | `task.reference.referenceId` equals the `aiops-<incident_id>-<trigger>` we sent, in all runs. `task.executionId` is present |
| Context used | Yes. The agent used the host, service, and the failed playbook with its `rc=2` |
| `AIOPS_PLAYBOOK` marker | **Not followed (0 of 3)**; the allow-list was never acknowledged. The payload no longer sends either |
| `resolved` update | Accepted by the webhook, no visible effect (status, version, `updatedAt` unchanged, no new task) |
| Scope | The agent investigates the whole associated account. It cited an unrelated alarm and another project's secret |

How to repeat the reads (replace the ids; do not print webhook secrets):

```powershell
aws devops-agent list-backlog-tasks --agent-space-id <space> --sort-field CREATED_AT --order DESC --region us-east-1 --profile mfa
aws devops-agent get-backlog-task --agent-space-id <space> --task-id <taskId> --region us-east-1 --profile mfa
aws devops-agent list-journal-records --agent-space-id <space> --execution-id <executionId> `
  --record-type investigation_summary_md --region us-east-1 --profile mfa
```

On Windows, decode the CLI output as UTF-8: the summaries contain non-ASCII characters.

## Phase 2 — Bring findings back (implemented, behind a flag)

Goal: show the operator what DevOps Agent found, in the email they already read, and keep an audit
record. It changes nothing on any host and does not touch the alert pipeline or the running app.

```
DevOps Agent finishes -> EventBridge (default bus, source aws.aidevops) -> Lambda
    1. GetBacklogTask(task_id)        -> reference "aiops-<incident>-<trigger>"
    2. ListJournalRecords(...)         -> investigation_summary_md, matched by summary_record_id
    3. DynamoDB record "devops-finding#<event id>"  (idempotency + metadata audit, no summary text)
    4. SES email to OPERATOR_EMAIL
```

**Enable it** (off by default; also needs `pip` and network at synth/deploy, see bundling below):

```powershell
npx aws-cdk@2 deploy Aiops-dev-Observability --context environment=dev --context devopsAgentFindingsEnabled=true --profile mfa
```

In CD, set the repository variable `DEVOPS_AGENT_FINDINGS_ENABLED=true`. To remove it, set the flag back to
`false` and redeploy: the Lambda, rule, DLQ and alarms are deleted and nothing else changes.

**What is built**

| Part | Where |
|---|---|
| Lambda (Python 3.12, 60s, 256 MB) | `src/agentic_ai/lambdas/devops_agent_findings/handler.py` |
| CDK construct, created by `ObservabilityStack` when the flag is on | `src/agentic_ai/infra/constructs/devops_agent_findings.py` |
| Events handled | `Investigation Completed`, `Failed`, `Timed Out`, `Linked` (rule and handler both check the list) |
| Failed invocations | Lambda retries, then an SQS DLQ (`aiops-devops-findings-dlq-<env>`, 14 days) |
| Alarms (staging/prod only, to the existing alarm topic) | DLQ not empty; Lambda errors |
| Log retention | 30 / 90 / 365 days for dev / staging / prod |

**Behaviour**

- Only our incidents: a task whose reference is not `aiops-<id>-<trigger>` (for example a manual
  investigation in the web app) is ignored.
- Other projects' Agent Spaces: IAM allows the two read calls only on Agent Spaces tagged
  `project=aiops-self-healing` and `environment=<env>` (the tags `aiops_env.py` applies). Events from other
  spaces get an access-denied and are ignored quietly. If you create the space by hand, add those tags.
- Idempotent: EventBridge is at-least-once. A conditional write marks the event `processing`, the email is
  sent, then it is marked `sent`. A retry after a failed send resends; a retry after success skips.
- No summary: the agent sometimes finishes without a summary and writes an `investigation_result` record
  instead (seen live: it could not find the host in the alert). Then the email carries that explanation under
  "Explanation". If there is neither, the email says so and points to the web app. Both lookups retry 3 times
  because a record can lag the event.
- `Linked`: a short email naming the investigation it was grouped under. `Failed` and `Timed Out`: a short notice.
- Untrusted text: the summary and title come from alert content. They are HTML-escaped, newlines are removed
  from the subject, the summary is cut at 6,000 characters, nothing is rendered as a link, and logs record
  lengths, never the text.
- IAM: `aidevops:GetBacklogTask` and `ListJournalRecords` (tag-scoped), `ses:SendEmail` on `identity/*`,
  and `dynamodb:PutItem/GetItem/UpdateItem` on the one table. No wildcard resources.

**Bundling.** The project pins boto3 1.35.36, which has no `devops-agent` client, so the Lambda bundles its own
`boto3==1.44.3` (`requirements.txt` in the Lambda folder). CDK installs it with the local `pip` at synth time and
falls back to Docker if that fails. Measured: about 27 MB unzipped, and the handler imports and finds the
`list_journal_records` paginator with that exact bundle. CI synthesizes with the flag on so a bundling failure
shows up before deploy. Tests skip bundling (`aws:cdk:bundling-stacks`).

**Verified live (2026-11-17, scratch stack and a temporary Agent Space, both deleted afterwards).** Four
incidents went through the real forwarder, EventBridge and the Lambda:

| Result | Detail |
|---|---|
| Tag-scoped IAM | Works. The Lambda read tasks and journal records of our space; no access-denied |
| Delivery | All four events produced an email and a `sent` audit record. DLQ 0, Lambda errors 0 |
| Event types seen | `Completed` with a summary (2), `Completed` with no summary (1), `Linked` (1) |
| `Linked` | Two incidents on the same host and alert within seconds: the second became `LINKED` and got the short notice |
| Timing | 0.45 to 2.2 s per invocation, 89 MB of 256 MB; the investigation itself took 1.5 to 3 minutes |
| No-summary case | Found live: the agent wrote `investigation_result` instead of a summary. The fallback to it was added, and verified by replaying that real event into the deployed Lambda (`has_result: true`) |

**Verified through the real ECS pipeline (2026-11-18, dev).** `demo/trigger_p1_incident.py` fired a critical alert; the investigation completed in about 5.5 minutes with a 5,684-character summary and the Lambda sent the RCA email one second later (audit record `sent`, DLQ 0). The agent used real telemetry and CloudTrail. Two Simulation-stack alarms were linked to the same investigation and produced short `Linked` notices. The findings Lambda's log group has a generated name; find it with `aws logs describe-log-groups --log-group-name-prefix Aiops-dev-Observability-DevOpsAgentFindings`.

Still not verified: the content of the emails as rendered by a mail client (SES accepted them), behaviour of
`Failed` and `Timed Out` events (none occurred; they are unit tested), and the usefulness of the findings on a real workload (the test hosts did not exist, so the agent
reported that it could not find them).

## Phase 2b — Advisory mode: DevOps Agent investigates, Bedrock picks the playbook (advisory only)

DevOps Agent does not name a playbook (see the spike), so the choice is made by Amazon Bedrock from the
playbook catalogue, and **nothing is executed**. Executing a chosen playbook (through the existing human
approval, guardrails and Ansible) stays deferred until `concurrency_guard` and `health_checker` are
implemented.

**Opt-in.** `devopsAgentAdvisoryEnabled=true` (requires `devopsAgentEnabled` and `devopsAgentFindingsEnabled`;
validated at synth). With `python scripts/aiops_env.py up --advisory`. Default off, which keeps the previous
behaviour (the ECS task calls Bedrock itself).

### Flow for an alert that matches no playbook

1. The ECS task forwards the alert to DevOps Agent (`unmatched`) and **does not call Bedrock**
   (`DEVOPS_AGENT_ADVISORY_MODE=true`). If forwarding did not happen (off, hourly cap, error), it falls back
   to the old Bedrock advisory email, so the operator always gets advice.
2. DevOps Agent investigates. EventBridge invokes the findings Lambda on `Investigation Completed`.
3. The Lambda reads the investigation summary, then looks for a mitigation plan (`mitigation_summary_md`
   journal record on any execution of the task). If there is none it requests one with
   `UpdateBacklogTask(taskStatus=PENDING_START)` and polls every 15 s, up to `MITIGATION_WAIT_SECONDS`
   (default 480) and never past the Lambda time left minus a 200 s reserve.
4. The Lambda asks Bedrock (Converse API; model chain Sonnet 4.5, Nova Pro, Haiku 4.5, Nova Lite; 30 s
   timeout, retries after 1 s and 2 s; optional guardrail from `BEDROCK_GUARDRAIL_ID/VERSION`) which playbook
   in the catalogue fixes the root cause.
5. One email: recommended fix (playbook, why, steps, how to verify, risks), the full investigation and root
   cause, and the DevOps Agent mitigation plan.

Failure handling: every step degrades to the next best email. Mitigation request denied or timed out, or
Bedrock down: the email still carries whatever was gathered and says what is missing. An investigation that
fails or times out still gets a recommendation from the alert data alone.

### Safety

- The playbook must be one of the paths in the catalogue (`advisory_context.json`, generated at synth from
  `playbooks/*.yml` and `config/playbook_mapping.yml`). A made-up path is discarded.
- Suggested steps matching `config/denied_commands.yml` are dropped and the email says how many.
- Summary and plan text are untrusted: prompt section tags inside them are removed, input is bounded, and
  everything is HTML-escaped in the email. Logs carry ids and statuses, never the texts.
- One advisory per DevOps Agent task (DynamoDB lease), so a task that DevOps Agent re-runs after the
  mitigation request cannot loop.

### Permissions and cost (new when the flag is on)

- Findings Lambda: `aidevops:ListExecutions` and `aidevops:UpdateBacklogTask` on tagged Agent Spaces (this
  is a write: it asks the agent to produce a plan), and `bedrock:InvokeModel` with the same scope as the
  task role. Timeout rises from 60 s to 900 s.
- DevOps Agent bills per active agent-second, so the mitigation step adds to the investigation cost.
- Bedrock cost is one Converse call per incident (a few tenths of a cent on Sonnet).

### Not verified against a live Agent Space

The mitigation request (`PENDING_START` on a completed investigation) follows an AWS sample; the AWS docs
also describe mitigation proposals appearing inline in the investigation. The code handles both (it uses a
plan that already exists, and otherwise requests one). Before relying on it, deploy with
`python scripts/aiops_env.py up --env dev --advisory`, run `demo/trigger_p1_incident.py`, and check the
`aiops-devops-findings-dev` log for `mitigation_status` (`found`, `generated`, `no_plan`, `timed_out`,
`request_failed`, `failed`).

## Phase 3 — Deeper integration (planned, future)

- **Custom MCP server:** expose incident history (DynamoDB), the playbook catalogue and audit records so investigations know what we already tried. Host privately (for example AgentCore Gateway) with authentication.
- **Agent skills:** encode `runbooks/` and our playbook conventions as DevOps Agent skills.
- **Topology instead of static inventory:** use DevOps Agent's discovered topology to replace or augment `config/asset_inventory.yml`. The enricher currently logs `No matching asset found` for EC2 instance IDs.
- **Release readiness review** (preview, us-east-1 only) on GitHub PRs. Requires the CI workflows to run first; they currently sit outside the repository root.
- **Notifications:** route findings to Slack, PagerDuty or ServiceNow alongside email.

---

## Guardrails status (prerequisite for Phase 2)

**Fixed 2026-11-10.** The guardrail engine previously failed at startup
(`ConcurrencyGuard.__init__() missing 2 required positional arguments`). The error was logged as
"non-fatal", so **no guardrail checks ran**.

It now starts with 6 checks: self_protection, maintenance_window, circuit_breaker,
blast_radius_classifier, approval_gate and plan_validator. If initialisation fails, the service
**refuses to start**. Verified in the deployed dev logs.

Still not active, because their dependencies have no implementation yet:

- `concurrency_guard`: needs a guardrails LockStore. The `concurrency.LockStore` PK/SK schema doesn't match `AiopsIncidentMemory`.
- `health_checker`: needs a ServiceRegistry.

A warning is logged at startup. Both should be implemented before Phase 2 lets DevOps Agent plans
drive execution.
