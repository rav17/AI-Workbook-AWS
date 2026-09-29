# CI/CD Replication Prompt

> Paste this prompt into Claude Code in any CDK-based project to replicate the production-grade CI/CD pattern from `uw017-stormforce-agents`.

---

## REPO ARCHETYPE

Before implementing anything, understand the target structure every CDK + GitHub Actions project must follow.

### Repository Layout

```
repo-root/
├── .github/
│   ├── actions/
│   │   └── setup-cdk/
│   │       └── action.yml          # Reusable composite action (Python + Node + CDK)
│   └── workflows/
│       ├── ci-cd.yml               # Main pipeline: dev / test / qa
│       ├── prod-deploy.yml         # Production-only workflow
│       └── cleanup-stuck-stack.yml # Callable: fix bad CloudFormation states
├── cdk/                            # Infrastructure package root — isolated
│   ├── app.py                      # Stack wiring + deploy order
│   ├── cdk.json                    # Context: envs, accounts, regions, config
│   ├── requirements.txt            # CDK deps only (never imports src/)
│   └── tests/                      # CDK unit tests (aws-cdk-lib assertions)
├── src/                            # Application package root — isolated
│   ├── pyproject.toml              # App deps, test runner, lint/type config
│   └── src/
│       ├── lambdas/                # One subdirectory per Lambda
│       ├── agents/                 # One subdirectory per agent (agent.yaml + code)
│       └── shared/                 # Lambda Layer source (shared across Lambdas)
├── neeito/                         # IAM permission boundary (org-specific)
│   └── dev.json                    # appPermissionBoundary + buildPolicyDocument
├── infra_config.json               # Accounts, regions, table names
└── CLAUDE.md                       # AI assistant instructions (optional)
```

**Non-negotiable: two isolated package roots.** `cdk/` and `src/` have separate dependency files and are never cross-imported. CDK synth does not execute Lambda code; Lambda code never imports CDK constructs.

### CDK Stack Topology

Order stacks so each layer only depends on layers below it. This determines the deploy order:

```
1. stateful        → KMS CMK, DynamoDB, Secrets Manager, SQS DLQs, SNS, EventBridge
2. shared-layer    → Lambda Layer (shared code) + SSM param with layer ARN
3. gateway         → API Gateway + integration Lambdas
4. compute-role    → Shared IAM execution role (MUST exist before runtimes deploy)
5. runtime-*       → One stack per agent/service (depends on compute-role)
6. ingest          → Inbound endpoints + EventBridge routing
7. observability   → CloudWatch dashboards + alarms
```

**Cross-stack sharing rule:** Pass ARNs between stacks via SSM Parameter Store. Never use CloudFormation `Fn::ImportValue` — it creates hard locks that prevent surgical deploys.

```python
# Producer stack — write ARN to SSM
ssm.StringParameter(self, "LayerArn",
    parameter_name="/myapp/layer-arn",
    string_value=layer.layer_version_arn)

# Consumer stack — read at deploy time (not synth time)
layer_arn = ssm.StringParameter.value_for_string_parameter(self, "/myapp/layer-arn")
```

**Critical:** Service-generated ARNs (e.g. AgentCore Runtime) are not deterministic. The Lambda must read them from SSM at cold start via an env var pointing to the SSM path — do NOT resolve them with `{{resolve:ssm:...}}` (fails if param doesn't exist yet during bootstrap).

### Environment Strategy

Define all environments in `cdk/cdk.json`:

```json
{
  "context": {
    "dev":  { "account": "111111111111", "region": "us-east-1" },
    "test": { "account": "222222222222", "region": "us-east-1" },
    "qa":   { "account": "333333333333", "region": "us-east-1" },
    "prod": { "account": "444444444444", "region": "us-east-1" }
  }
}
```

| Branch | Environment | Removal Policy | Approval gate |
|--------|-------------|----------------|---------------|
| `develop` | dev | DESTROY | None |
| `test` | test | DESTROY | None |
| `release/*` | qa | RETAIN | Required reviewers |
| `main` | prod | RETAIN | Required reviewers |

### Secrets and Config Hierarchy

| What | Where | How accessed |
|------|-------|--------------|
| API keys, credentials | AWS Secrets Manager | Lambda reads at cold start |
| Cross-stack ARNs | SSM Parameter Store | CDK reads at deploy time |
| Account IDs, regions | `cdk/cdk.json` context | `app.node.try_get_context()` |
| Deploy role ARN | GitHub environment variable (`vars.`) | `${{ vars.AWS_DEPLOY_ROLE_ARN }}` |
| Nothing sensitive | GitHub `secrets.` | Avoid — prefer SSM / Secrets Manager |

### CDK Nag (Compliance Gate)

Every `cdk synth` must run `AwsSolutionsChecks`. Violations block CI. Add to `cdk/app.py`:

```python
from cdk_nag import AwsSolutionsChecks
cdk.Aspects.of(app).add(AwsSolutionsChecks(verbose=True))
```

Suppress with documented reasons only — never suppress blindly:

```python
NagSuppressions.add_resource_suppressions(resource, [
    {"id": "AwsSolutions-IAM5", "reason": "Lambda ENI management requires wildcard per AWS docs"},
], apply_to_children=True)
```

### AWS Authentication — OIDC Only

Never put `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` in GitHub secrets. Use OIDC exclusively.

**One-time setup per AWS account:**
```bash
aws iam create-open-id-connect-provider \
  --url https://token.actions.githubusercontent.com \
  --client-id-list sts.amazonaws.com \
  --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1
```

**IAM role trust policy (one role per account):**
```json
{
  "Effect": "Allow",
  "Principal": {
    "Federated": "arn:aws:iam::<ACCOUNT>:oidc-provider/token.actions.githubusercontent.com"
  },
  "Action": "sts:AssumeRoleWithWebIdentity",
  "Condition": {
    "StringEquals": { "token.actions.githubusercontent.com:aud": "sts.amazonaws.com" },
    "StringLike":   { "token.actions.githubusercontent.com:sub": "repo:ORG/REPO:*" }
  }
}
```

**In the workflow:**
```yaml
permissions:
  contents: read      # workflow level — minimum always
  id-token: write     # only on jobs that need AWS credentials

- uses: aws-actions/configure-aws-credentials@v4
  with:
    role-to-assume: ${{ vars.AWS_DEPLOY_ROLE_ARN }}
    aws-region: us-east-1
    role-session-duration: 5400
    role-skip-session-tagging: true
```

Always verify immediately after:
```bash
aws sts get-caller-identity
```

### GitHub Actions Workflow Graph

```
push / PR
    │
    ├── lint  ──────────────────────────────────────────┐
    │                                                   │
    ├── python-test  (needs: lint,     if: always())   │
    │                                                   │
    └── cdk-test     (needs: lint,     if: always())   │
                                                        │
         ┌──────────────────────────────────────────────┘
         │
         ├── [PR only]   cdk-diff       → posts diff as PR comment (read-only AWS)
         │
         └── [push only] detect-changes → which stacks changed?
                         resolve-env    → which AWS account + env name?
                         auto-preflight → fix stuck stacks (dev/test only)
                         deploy         → cdk deploy (surgical or full)
```

**Concurrency rules:**
- `cancel-in-progress: true` — lint and test jobs only
- `cancel-in-progress: false` — always on deploy and preflight (torn infra is dangerous)
- One concurrency group per environment: `deploy-dev`, `deploy-test`, `deploy-prod`
- Set a timeout on every job (lint: 10 min, deploy: 90 min)

### Surgical Deploy Pattern

Only redeploy stacks whose source changed. Map file paths to stack names:

```yaml
- name: Detect changes
  run: |
    CHANGED=$(git diff --name-only ${{ github.event.before }} HEAD)
    # Force-push or first deploy: treat all as changed
    if [ -z "${{ github.event.before }}" ] || [ "${{ github.event.before }}" = "0000000000000000000000000000000000000000" ]; then
      echo "force_all=true" >> $GITHUB_OUTPUT && exit 0
    fi
    if echo "$CHANGED" | grep -q "src/shared/";    then echo "shared_layer=true" >> $GITHUB_OUTPUT; fi
    if echo "$CHANGED" | grep -q "src/lambdas/";   then echo "gateway=true"      >> $GITHUB_OUTPUT; fi
    if echo "$CHANGED" | grep -q "cdk/";           then echo "force_all=true"    >> $GITHUB_OUTPUT; fi
```

Deploy only the changed stacks, in dependency order:
```bash
cdk deploy "${STACKS_TO_DEPLOY[@]}" \
  --require-approval never \
  --concurrency 10 \
  --progress events \
  -c env=<env>
```

### Self-Hosted vs GitHub-Hosted Runners

Use **self-hosted runners** when:
- AWS accounts require a corporate proxy
- VPC-internal access is needed
- Your org mandates a specific runner fleet (SDP, NEEito build roles, etc.)

```yaml
runs-on: [self-hosted, your-runner-label]
```

Use **GitHub-hosted runners** (`ubuntu-latest`) only when public internet access is available and no proxy is required.

---

I need you to implement a GitHub Actions CI/CD workflow for this project that follows the same production-grade pattern used in our reference implementation. Work through the following phases in order.

---

## PHASE 1 — EXPLORE (read-only, no edits yet)

Read every file listed below in full. Do not skip or summarize — you will need the exact content to implement correctly.

1. **CLAUDE.md** (root) — conventions, naming rules, CDK commands, known pitfalls
2. **cdk/app.py** — full stack list, dependency order, how stacks are wired
3. **cdk/cdk.json** — environment configs (accounts, regions, Lambda settings, model IDs)
4. **cdk/requirements.txt** — CDK Python dependencies
5. **src/pyproject.toml** — agent package: Python version, test runner, lint/type tools
6. **neeito/dev.json** (if present) — IAM permission boundary sections
7. **infra_config.json** (if present) — project-level config (accounts, regions, table names)
8. Any existing files in **.github/workflows/** — don't overwrite patterns already correct
9. **src/src/agents/** — list all agent subdirectories and their agent.yaml files
10. **src/src/step_functions/** (if present) — list all state machine directories
11. **src/src/lambdas/** — list all Lambda subdirectories

From this exploration, extract and record:

- **Resource prefix** (e.g., `uw017-stormforce-agents-*`)
- **SSM prefix** (e.g., `/uw017/stormforce-agents/`)
- **CDK app_code** and **team_name** from cdk.json context
- **Full ordered stack list** from app.py (exact CDK stack IDs)
- **Which stacks are "retained"** (RETAIN removal policy in qa/prod)
- **All SSM parameters** read at deploy time (cross-stack ARN handoff)
- **All Secrets Manager secrets** that must exist before deploy
- **Branch → environment → AWS account** mapping
- **Self-hosted runner label** (look in any existing workflow or CLAUDE.md)
- **Python version** in pyproject.toml
- **CDK version** in cdk/requirements.txt or any existing workflow
- **AWS proxy settings** (from CLAUDE.md or existing workflows)
- **GitHub environment variable names** (VPC_ID, SUBNET_IDS, AWS_DEPLOY_ROLE_ARN, etc.)
- **Test commands**: pytest paths, ruff, mypy, cdk tests
- **Any project-specific pre-deploy bootstrap steps** (KMS alias, SG creation, etc.)

Do NOT proceed to Phase 2 until you have extracted every item above.

---

## PHASE 2 — PLAN

State your implementation plan before writing any file. Include:

1. The complete job graph (names, triggers, needs-chain, concurrency groups)
2. The branch → environment mapping you will implement
3. The full ordered stack list for surgical deploy
4. Which SSM parameters will be read during deploy and for what purpose
5. Which secrets will be verified before deploy
6. Any project-specific bootstrap steps you identified
7. Confirmation that OIDC (not static credentials) will be used

Wait for my approval before proceeding to Phase 3.

---

## PHASE 3 — IMPLEMENT

Implement the following files. Each section describes what to build and the exact patterns to follow.

### 3a. `.github/actions/setup-cdk/action.yml`

A reusable composite action that installs Python, Node.js, and CDK. Use these exact versions unless the project's cdk/requirements.txt or existing workflow specifies otherwise:

- Python: match `pyproject.toml` `requires-python`
- Node.js: 24
- CDK: extract exact version from `pip show aws-cdk-lib` output or cdk/requirements.txt

```yaml
name: Setup CDK
description: Install Python, Node, and CDK CLI
runs:
  using: composite
  steps:
    - uses: actions/setup-python@v5
      with:
        python-version: "<version>"
    - uses: actions/setup-node@v4
      with:
        node-version: "24"
    - name: Install CDK
      shell: bash
      run: npm install -g aws-cdk@<version>
    - name: Install CDK Python deps
      shell: bash
      working-directory: cdk
      run: pip install -r requirements.txt -q
```

### 3b. `.github/workflows/ci-cd.yml`

Implement ALL of the following jobs in dependency order.

**Workflow-level settings:**

```yaml
name: CI/CD
on:
  push:
    branches: [develop, test, "release/**"]
  pull_request:
    branches: [develop, test, "release/**"]
  workflow_dispatch:
    inputs:
      commit_sha:
        description: "Commit SHA to deploy (leave blank for HEAD)"
        required: false
      deploy_mode:
        description: "full | surgical (default: surgical)"
        required: false
        default: surgical
        type: choice
        options: [surgical, full]

permissions:
  contents: read
```

**Job: `lint`**

- Runner: `[self-hosted, <runner-label>]`
- Timeout: 10 minutes
- Concurrency: `lint-${{ github.ref }}`, cancel-in-progress: true
- Steps: checkout → setup-uv (cache on `src/pyproject.toml`) → `uv sync --extra dev` → ruff (continue-on-error) → mypy (continue-on-error)

**Job: `python-test`**

- Needs: `lint` with `if: always()`
- Concurrency: `python-test-${{ github.ref }}`, cancel-in-progress: true
- Steps: checkout → setup-uv → `uv sync --extra dev` → `uv run pytest tests/ -v --tb=short`

**Job: `cdk-test`**

- Needs: `lint` with `if: always()`
- Concurrency: `cdk-test-${{ github.ref }}`, cancel-in-progress: true
- Steps: checkout → `./.github/actions/setup-cdk` → `python -m pytest cdk/tests/ -v --tb=short`

**Job: `cdk-diff`** (PR only)

- Condition: `if: github.event_name == 'pull_request'`
- Needs: `python-test`, `cdk-test`
- Permissions: add `pull-requests: write`, `id-token: write`
- Steps: checkout → setup-cdk → OIDC credentials (role-duration: 1800s) → map PR base branch to CDK env → `cdk diff --all -c env=<env>` → post as PR comment via `actions/github-script@v8`

**Job: `detect-changes`** (non-PR only)

- Condition: `if: github.event_name != 'pull_request'`
- Needs: `python-test`, `cdk-test` (with `if: always()`)
- Outputs: one boolean flag per CDK stack + aggregate `any_change`
- Logic: `git diff --name-only ${{ github.event.before }} HEAD`; handle null SHA (force-push) by treating as full-change; map source paths to stack names from app.py; discover agents/step-functions dynamically from yaml files

**Job: `resolve-env`** (non-PR only)

- Condition: `if: github.event_name != 'pull_request'`
- Needs: same as detect-changes
- Outputs:
  - `env_name`: dev | test | qa | prod (from branch ref)
  - `is_rollback`: true if `inputs.commit_sha` is non-empty

**Job: `auto-preflight`** (dev/test only)

- Condition: env != qa/prod AND event != PR AND tests passed
- Needs: python-test, cdk-test, detect-changes, resolve-env
- Concurrency: `deploy-${{ needs.resolve-env.outputs.env_name }}`, cancel-in-progress: **false**
- Calls `./.github/workflows/cleanup-stuck-stack.yml` with environment + action: preflight

**Job: `deploy`**

- Condition: not PR, not develop branch, tests passed, preflight success-or-skipped
- Needs: python-test, cdk-test, detect-changes, resolve-env, auto-preflight
- Permissions: `contents: read`, `actions: write`, `id-token: write`
- Environment: `${{ needs.resolve-env.outputs.env_name }}` (triggers approval gate for qa/prod)
- Concurrency: `deploy-${{ needs.resolve-env.outputs.env_name }}`, cancel-in-progress: **false**
- Timeout: 90 minutes

**Deploy job steps — implement ALL of these:**

1. **Checkout** at `${{ inputs.commit_sha || github.sha }}` with `fetch-depth: 0`
2. **Setup CDK** via `./.github/actions/setup-cdk`
3. **OIDC credentials**: `role-to-assume: ${{ vars.AWS_DEPLOY_ROLE_ARN }}`, duration: 5400s, `role-skip-session-tagging: true` → verify with `aws sts get-caller-identity`
4. **Verify required secrets** exist in Secrets Manager — fail fast with a clear error message if any are missing
5. **Deployment gap detection**: compare `github.event.before` to last-deployed SHA variable; set `FORCE_ALL=true` if a gap is found
6. **Restore CDK build cache** (`cdk/.build`, key on requirements.txt hashes across shared + agents + lambdas)
7. **Read retained resource ARNs from SSM** (KMS key, API Gateway IDs, etc.) → set as env vars for CDK context
8. **Restore CDK output cache** (`cdk/cdk.out`, key on env + retained-resource mode + all source hashes)
9. **CDK synth** (only if cache miss): `cdk synth -c env=<env> --quiet`
10. **Determine deploy mode**: set `FORCE_ALL=true` if push event, deploy_mode=full, is_rollback, or gap detected
11. **Stuck stack check** (qa/prod only — dev/test handled by auto-preflight): scan all stacks; fail if any are in a bad state with clear remediation instructions
12. **Bootstrap on first deploy** (dev/test only): deploy stacks in dependency order one-by-one; handle ROLLBACK_COMPLETE by deleting first; skip for qa/prod
13. **Build `STACKS_TO_DEPLOY`**: if FORCE_ALL, use full ordered stack list; otherwise include only changed stacks + any stack in NOT_FOUND state from detect-changes outputs
14. **CDK deploy**:
    ```bash
    cdk deploy --app cdk.out "${STACKS_TO_DEPLOY[@]}" \
      --require-approval never \
      --concurrency 10 \
      --progress events \
      -c env=<env>
    ```
15. **Post-deploy verification**: all deployed stacks must be in `*_COMPLETE` state; if rollback, also verify Lambda functions are Active and SSM params exist
16. **Update last-deployed SHA**:
    ```bash
    gh variable set last_deployed_sha_<branch_slug> \
      --body "${{ github.sha }}" \
      --env <env>
    ```

### 3c. `.github/workflows/cleanup-stuck-stack.yml`

A callable workflow (`workflow_call`). Inputs: `environment` (dev/test/qa/prod), `action` (preflight | remediate).

Discover all project stacks from CloudFormation. For each stack:

| Stack state | Action |
|---|---|
| ROLLBACK_COMPLETE / CREATE_FAILED | `delete-stack`, wait for completion |
| ROLLBACK_FAILED | Delete; retry with `--retain-resources` on DELETE_FAILED |
| DELETE_FAILED | Delete with `--retain-resources` listing stuck resources |
| UPDATE_ROLLBACK_FAILED | Fail with manual remediation instructions |
| *_IN_PROGRESS | Fail — another deploy is in progress |
| All other states | Skip |

### 3d. `.github/workflows/prod-deploy.yml`

A separate workflow for production deployments.

**Triggers:**

```yaml
on:
  pull_request:
    branches: [master]
    types: [closed]
  workflow_dispatch:
    inputs:
      commit_sha:
        description: "Commit SHA for rollback (blank = HEAD)"
        required: false
      deploy_mode:
        description: "full | surgical"
        type: choice
        options: [surgical, full]
        default: surgical
```

**Jobs:**

1. **`validate`**: determine if this is a real deploy (merged PR from `release/*` → master, or workflow_dispatch from master). Output `should_deploy`, `deploy_sha`, `is_rollback`.
2. **`python-test`**: same as ci-cd.yml; condition `needs.validate.outputs.should_deploy == 'true'`
3. **`cdk-test`**: same; same condition
4. **`deploy`**: same as ci-cd.yml deploy job, with these differences:
   - Environment: `prod` (requires manual approval)
   - Always full-deploy on merged PR path; surgical only on explicit `workflow_dispatch` with `deploy_mode=surgical`
   - Bootstrap guard: fail if SSM params are missing (prod should never need first-time bootstrap)
   - Upload `cdk.out` as a workflow artifact for audit

---

## PHASE 4 — SELF-REVIEW

After writing all files, verify every item below. Fix any issues before reporting done.

- [ ] Every `github.event.inputs.*` reference has a `|| inputs.*` fallback where the workflow has both `push` and `workflow_dispatch` triggers
- [ ] No job silently unblocks a downstream job when skipped — check every `needs` chain
- [ ] Deploy job `if:` condition works for all event types that trigger the workflow
- [ ] `cancel-in-progress: true` ONLY on lint/test jobs — NEVER on deploy or preflight
- [ ] AWS credentials always uses OIDC `role-to-assume`, never static `aws-access-key-id`
- [ ] `id-token: write` is on the specific jobs that need OIDC, NOT at workflow level
- [ ] Proxy env vars are set on the deploy job if the project uses a corporate proxy
- [ ] All CDK commands run with `working-directory: cdk`
- [ ] All pytest commands run with `working-directory: src` where applicable
- [ ] Stack names in deploy commands exactly match CDK stack IDs from app.py (case-sensitive)
- [ ] SSM paths, secret names, and resource prefixes are this project's (not the reference project's)
- [ ] Self-hosted runner label matches the actual runner for this project

---

## GHA Best Practices Applied

### Workflow Hygiene
- Pinned action versions — no `@main` or `@latest`; use `@v4` or full commit SHA
- Minimum permissions at workflow level (`contents: read`); elevated per-job only
- `id-token: write` on specific jobs that need OIDC — never at workflow level
- Timeouts on every job — prevents hung self-hosted runners
- Explicit `working-directory` on all CDK and pytest commands

### Authentication and Secrets
- OIDC over static credentials — no `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` in secrets
- Deploy role ARN stored as a GitHub environment **variable** (`vars.`), not a secret
- Sensitive values (API keys, tokens) in AWS Secrets Manager — not GitHub secrets
- Verify `aws sts get-caller-identity` immediately after credential step
- Check all required Secrets Manager secrets exist before the deploy starts — fail fast

### Concurrency and Safety
- `cancel-in-progress: false` on deploy and preflight concurrency groups — prevents torn infrastructure
- `cancel-in-progress: true` on lint and test jobs only — saves runner time on rapid pushes
- One concurrency group per environment (`deploy-dev`, `deploy-prod`, etc.)
- Verify all deployed stacks are in `*_COMPLETE` state after every deploy
- Track last-deployed SHA; detect gaps (missed commits) and force a full deploy to close them

### CDK-Specific
- Content-hash cache keys for `cdk/.build` and `cdk/cdk.out` — prevents stale synth output
- Surgical deploys — path-based change detection; only redeploy stacks whose source changed
- Explicit stack ordering in `cdk deploy` command — respects CDK dependency chain
- Full deploy forced when: `cdk/` changes, `workflow_dispatch` with `deploy_mode=full`, rollback, or SHA gap
- Handle `ROLLBACK_COMPLETE` / `CREATE_FAILED` stacks before deploy — delete and redeploy

### Governance
- Approval gates via GitHub Environments for qa and prod
- `workflow_dispatch` inputs include `commit_sha` for emergency rollback to any known-good SHA
- Upload `cdk.out` as a workflow artifact for audit trail (especially on prod deploys)
- Separate `prod-deploy.yml` workflow — production path is distinct, auditable, and approval-gated
- Never use `--no-verify`, `--force`, or skip hooks without documented justification

### Non-Negotiables Checklist

| Rule | Why |
|------|-----|
| Two isolated package roots (`cdk/` and `src/`) | CDK synth must never execute application code |
| OIDC only — no static AWS credentials | Static keys rot, leak, and can't be scoped per-environment |
| SSM for cross-stack ARN handoff — not `Fn::ImportValue` | Export locks prevent surgical deploys |
| CDK nag on every synth | Compliance violations caught before they reach AWS |
| `cancel-in-progress: false` on deploy | A cancelled mid-deploy leaves stacks in `*_IN_PROGRESS` |
| Verify stack states post-deploy | CloudFormation returns exit 0 even on partial rollback |
| Secrets Manager, not GitHub secrets | Rotation, audit trail, and no risk of log exposure |
| Approval gates for qa and prod | Human sign-off before touching retained-policy resources |
| Explicit stack deploy order | Implicit parallelism breaks when one stack's output feeds another |
| Post-deploy SHA tracking | Ensures every commit is deployed; gaps in SHA history force full deploys |
