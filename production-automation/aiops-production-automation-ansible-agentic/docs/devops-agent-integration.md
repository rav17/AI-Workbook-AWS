# AWS DevOps Agent Integration

AWS DevOps Agent investigates incidents and proposes mitigations. It does **not**
execute anything in our pipeline. Our solution remains the only component that
changes hosts, and every change still goes through PlanValidator and the human
approval gate.

| Phase | Scope | Status |
|---|---|---|
| 1 | Forward selected incidents to a DevOps Agent generic webhook (HMAC) | **Implemented** |
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

### Setup steps

1. **Create an Agent Space** in a supported Region (us-east-1 works for this project) and associate the AWS account.
2. **Create a generic webhook:** Agent Space → *Capabilities* → *Agent Space Webhook* → *Add webhook* → **HMAC**. Copy the URL and secret. The secret is shown only once.
3. **Store them in Secrets Manager.** Keep the JSON keys exactly as shown; a missing key stops ECS tasks from starting.

   ```powershell
   $value = @{ url = "<webhook-url>"; secret = "<hmac-secret>"; web_app_url = "<optional web app url>" } | ConvertTo-Json -Compress
   aws secretsmanager put-secret-value --secret-id /aiops/dev/devops-agent-webhook --secret-string $value --profile mfa --region us-east-1
   ```

4. **Enable and deploy** (or just restart the tasks if the flag is already on). ECS reads secrets at task start:

   ```powershell
   npx aws-cdk@2 deploy Aiops-dev-Compute --context environment=dev --context devopsAgentEnabled=true --profile mfa
   # or, if already deployed with the flag on:
   aws ecs update-service --cluster aiops-cluster-dev --service <service-name> --force-new-deployment --profile mfa --region us-east-1
   ```

   Every `cdk deploy` must pass `--context devopsAgentEnabled=true`, otherwise forwarding is switched off again.

5. **Verify.** The startup log should show `DevOps Agent forwarding: active=True`. Then send an alert with no matching playbook (for example `python demo/break_target.py --mode network --trigger-alert`). Expect `Incident forwarded to AWS DevOps Agent (trigger=unmatched, http=200)` in `/aiops/dev/ecs`, and a new investigation in the Agent Space.
6. **Rotating the secret:** rotate it in the Agent Space, update the Secrets Manager value (step 3), then force a new ECS deployment.

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

**Prerequisite:** fix guardrail engine initialisation first (see *Known issue* below). Phase 2 depends on PlanValidator actually running.

## Phase 3 — Deeper integration (planned, future)

- **Custom MCP server:** expose incident history (DynamoDB), the playbook catalogue and audit records so investigations know what we already tried. Host privately (for example AgentCore Gateway) with authentication.
- **Agent skills:** encode `runbooks/` and our playbook conventions as DevOps Agent skills.
- **Topology instead of static inventory:** use DevOps Agent's discovered topology to replace or augment `config/asset_inventory.yml`. The enricher currently logs `No matching asset found` for EC2 instance IDs.
- **Release readiness review** (preview, us-east-1 only) on GitHub PRs. Requires the CI workflows to run first; they currently sit outside the repository root.
- **Notifications:** route findings to Slack, PagerDuty or ServiceNow alongside email.

---

## Known issue (blocks Phase 2)

At startup, `src/app.py` fails to initialise the guardrail engine:
`ConcurrencyGuard.__init__() missing 2 required positional arguments: 'lock_store' and 'service_registry'`.
The error is caught as "non-fatal", so **no guardrail checks run** (self-protection,
maintenance windows, circuit breaker, blast radius, approval gate, PlanValidator).
Confirmed in the deployed dev logs.
