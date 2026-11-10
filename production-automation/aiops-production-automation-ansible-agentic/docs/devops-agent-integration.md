# AWS DevOps Agent Integration

AWS DevOps Agent investigates incidents and proposes mitigations. It does **not**
execute anything in our pipeline. Our solution remains the only component that
changes hosts, and every change still goes through PlanValidator and the human
approval gate.

| Phase | Scope | Status |
|---|---|---|
| 1 | Forward selected incidents to a DevOps Agent generic webhook (HMAC) | **Implemented, verified end to end in dev (2026-11-10)** |
| 2 | Consume DevOps Agent mitigation plans via EventBridge → approval → SSM | Planned (future) |
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

Rule-matched, non-critical alerts are **not** forwarded; the fast rule path is unchanged.

### Safety and cost controls (`src/devops_agent.py`)

- **Off unless configured:** requires `DEVOPS_AGENT_ENABLED=true` **and** a non-empty https webhook URL and secret.
- **Never blocks the pipeline:** runs in a worker thread with a 5s timeout and 2 retries (1s, 2s backoff). Auth and format errors (4xx except 429) are not retried. All failures are logged with `incident_id` and never raised.
- **Cost guard:** DevOps Agent bills per active agent-second. There is a per-task cap of `DEVOPS_AGENT_MAX_PER_HOUR` (default 20) and per-incident de-duplication. The cap is per ECS task, so the fleet-wide maximum is cap × task count. Set an AWS Budget filtered on *AWS DevOps Agent* as well.
- **Minimal data:** only the alert name, severity, host, service, environment, region, summary and our incident reference are sent. DevOps Agent ignores the `data` field, so all context goes into `description`.
- **Traceability:** `incidentId` is `aiops-<our incident_id>-<trigger>`. Search for it in the Agent Space.

### Configuration

| Setting | Where | Default |
|---|---|---|
| `devopsAgentEnabled` | CDK context (`--context devopsAgentEnabled=true`) | `false` |
| `DEVOPS_AGENT_FORWARD_ON` | Task env (`compute_stack.py`) | `unmatched,failed,critical` |
| `DEVOPS_AGENT_MAX_PER_HOUR` | Task env (`compute_stack.py`) | `20` |
| URL, HMAC secret, web app URL | Secrets Manager `/aiops/{env}/devops-agent-webhook` (JSON keys `url`, `secret`, `web_app_url`) | Empty placeholders |

CDK creates the secret with **empty `url`/`web_app_url` and a random placeholder
`secret`**, so ECS tasks always start. Forwarding stays inactive until real values are stored.

### Current dev setup (created 2026-11-10, us-east-1)

| Resource | Value |
|---|---|
| Agent Space | `aiops-dev` (`2a6779d7-b19a-440c-8417-b06295e9da84`), elevated actions **off** |
| Agent Space role | `aiops-dev-DevOpsAgentRole-AgentSpace`: AWS managed `AIDevOpsAgentAccessPolicy` + inline Resource Explorer service-linked-role permission |
| Operator app role | `aiops-dev-DevOpsAgentRole-WebappAdmin`: AWS managed `AIDevOpsOperatorAppAccessPolicy` |
| Account association | `533267042240` as `monitor` |
| Operator web app | https://2a6779d7-b19a-440c-8417-b06295e9da84.aidevops.global.app.aws |
| Generic webhook | HMAC, association `831cd395-703e-497f-ba32-d24a2ddb3463`, stored in `/aiops/dev/devops-agent-webhook` |

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

## Phase 2 — Consume mitigation plans (planned, future)

Goal: turn DevOps Agent mitigation plans into proposed actions that go through
our existing safety path, without bypassing it.

Planned design:

1. An EventBridge rule on source `aws.aidevops`, detail-type *Mitigation Completed*, triggers a Lambda.
2. The Lambda fetches the mitigation summary and plan from the DevOps Agent API and puts it on SQS.
3. The pipeline converts the plan into a `RemediationPlan`, then runs **PlanValidator** (denylist), creates a **human approval** request (with duplicate suppression), and executes via SSM only after Confirm.
4. Code or IaC changes are routed to a pull request (Kiro CLI headless, as in the AWS sample) instead of being executed.

Open questions before building:

- Confirm the exact API operation and response schema for fetching mitigation plans (taken from an AWS blog, not yet from the API reference).
- Map free-text mitigation steps to allow-listed actions; never run raw shell from a plan.
- Decide whether to manage the Agent Space and webhook as IaC (`AWS::DevOpsAgent::*` resources). The webhook secret is not returned by CloudFormation and must be rotated after deploy.

**Prerequisites:** guardrail engine initialisation is fixed, and PlanValidator now runs. `concurrency_guard`
and `health_checker` still need implementations (see *Guardrails status* below). Also enable Bedrock model
access for Claude Sonnet/Haiku 4.5: our own AI path returned `AccessDeniedException` in the dev test.

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
