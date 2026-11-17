"""Provision or destroy a complete AIOps environment with a single command.

    python scripts/aiops_env.py up      [--env dev] [--profile mfa] [--skip-build] [--dry-run]
    python scripts/aiops_env.py down    [--env dev] [--profile mfa] [--yes] [--include-ecr]
    python scripts/aiops_env.py status  [--env dev] [--profile mfa]

``up`` (idempotent; safe to re-run):
    1. Preflight: AWS CLI >= 2.39, credentials for the cdk.json account, npx.
    2. CDK bootstrap (if missing) and the shared ``aiops`` ECR repository.
    3. Build and push the image ``aiops:latest-<env>`` with CodeBuild (no local Docker).
    4. ``cdk deploy --all`` (Network, Data, Compute, Observability, Monitoring, Simulation).
    5. AWS DevOps Agent: IAM roles, Agent Space ``aiops-<env>``, account association,
       operator web app, and an HMAC webhook. The webhook secret goes straight into
       Secrets Manager and is never printed.
    6. Restart the ECS service (it reads secrets at start) and wait for ``/health`` = 200.

``down``:
    1. Confirm (type the environment name; ``--yes`` skips this for dev only).
    2. Delete the Agent Space ``aiops-<env>`` and its two IAM roles (stops agent billing).
    3. ``cdk destroy --all``.
    4. dev only: purge leftovers that would block the next ``up`` (DynamoDB table,
       secrets, log groups, SSM parameters under ``/aiops/<env>/``).
       staging/prod: leftovers are reported and kept, unless ``--purge-retained``.
    5. Verify nothing is left and exit non-zero if something is.

Kept on ``down``: the shared ``aiops`` ECR repository (use ``--include-ecr``), the CDK
bootstrap stack, the CodeBuild helper role/bucket, and SES identities.

Requires the virtualenv with ``.[cdk]`` installed. Run with that Python, for example
``.venv\\Scripts\\python.exe scripts/aiops_env.py up``.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parent.parent
_CDK_CONTEXT = json.loads((ROOT / "cdk.json").read_text(encoding="utf-8"))["context"]
ACCOUNT: str = _CDK_CONTEXT["awsAccount"]
REGION: str = _CDK_CONTEXT["awsRegion"]
ECR_REPO = "aiops"
ENVIRONMENTS = ("dev", "staging", "prod")
MIN_AWS_CLI = (2, 39)
DESTROY_ATTEMPTS = 3
DESTROY_RETRY_SECONDS = 60
TAGS = {"project": "aiops-self-healing", "managed-by": "aiops_env.py"}

AGENT_SPACE_POLICY = "arn:aws:iam::aws:policy/AIDevOpsAgentAccessPolicy"
OPERATOR_APP_POLICY = "arn:aws:iam::aws:policy/AIDevOpsOperatorAppAccessPolicy"


class StepError(Exception):
    """A provisioning or teardown step failed."""


# ---------------------------------------------------------------------------
# Pure helpers (unit tested)
# ---------------------------------------------------------------------------


def parse_cli_version(text: str) -> tuple[int, int]:
    """Extract (major, minor) from ``aws --version`` output; (0, 0) if unknown."""
    match = re.search(r"aws-cli/(\d+)\.(\d+)", text or "")
    return (int(match.group(1)), int(match.group(2))) if match else (0, 0)


def names_for(env: str) -> dict[str, str]:
    """Resource names for an environment."""
    return {
        "space": f"aiops-{env}",
        "space_role": f"aiops-{env}-DevOpsAgentRole-AgentSpace",
        "app_role": f"aiops-{env}-DevOpsAgentRole-WebappAdmin",
        "webhook_secret": f"/aiops/{env}/devops-agent-webhook",
        "table": f"AiopsIncidentMemory-{env}",
        "cluster": f"aiops-cluster-{env}",
        "stack_prefix": f"Aiops-{env}-",
        "param_prefix": f"/aiops/{env}/",
    }


def webhook_action(stored_url: str, live_url: Optional[str]) -> str:
    """Decide what to do with the Agent Space webhook.

    Returns:
        "create" if no webhook exists, "keep" if Secrets Manager already holds this
        webhook (url and secret are always written together), or "recreate" when a
        webhook exists but its one-time secret was never stored and can't be read back.
    """
    if not live_url:
        return "create"
    return "keep" if stored_url == live_url else "recreate"


def trust_policy(actions: list[str]) -> dict:
    """Trust policy for DevOps Agent roles (confused-deputy protected)."""
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "aidevops.amazonaws.com"},
                "Action": actions,
                "Condition": {
                    "StringEquals": {"aws:SourceAccount": ACCOUNT},
                    "ArnLike": {"aws:SourceArn": f"arn:aws:aidevops:{REGION}:{ACCOUNT}:agentspace/*"},
                },
            }
        ],
    }


# ---------------------------------------------------------------------------
# Command runners
# ---------------------------------------------------------------------------


def _say(msg: str) -> None:
    print(msg, flush=True)


def _exe(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise StepError(f"'{name}' not found on PATH")
    return path


def _env_with_venv() -> dict[str, str]:
    """Put this Python first on PATH so ``cdk.json``'s ``python -m ...`` app uses it."""
    env = dict(os.environ)
    env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + env.get("PATH", "")
    env["AWS_PAGER"] = ""
    return env


class Runner:
    """Runs aws/cdk commands for one profile, with consistent timeouts and logging."""

    def __init__(self, profile: str) -> None:
        self.profile = profile
        self.env = _env_with_venv()
        self.env["AWS_PROFILE"] = profile
        self._tmp = tempfile.TemporaryDirectory(prefix="aiops-env-")

    def close(self) -> None:
        """Remove temporary policy/config files."""
        self._tmp.cleanup()

    def json_file(self, obj: Any) -> str:
        """Write JSON to a temp file and return a ``file://`` URI for the CLI."""
        path = Path(self._tmp.name) / f"{time.time_ns()}.json"
        path.write_text(json.dumps(obj), encoding="utf-8")
        return f"file://{path}"

    def aws(self, *args: str, check: bool = True, quiet: bool = False) -> Any:
        """Run an AWS CLI command and return parsed JSON (or None for empty output).

        Args:
            args: CLI arguments after ``aws``.
            check: Raise StepError on a non-zero exit code.
            quiet: Don't echo the command or its output (used for secret-bearing calls).
        """
        cmd = [
            _exe("aws"), *args, "--region", REGION, "--output", "json",
            "--cli-connect-timeout", "10", "--cli-read-timeout", "60",
        ]
        if not quiet:
            _say("    $ aws " + " ".join(args))
        # utf-8, not the Windows locale codec: agent summaries contain non-ASCII text
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=self.env,
        )
        if proc.returncode != 0:
            err = (proc.stderr or "").strip().splitlines()
            message = err[-1] if err else f"exit {proc.returncode}"
            if check:
                raise StepError(f"aws {args[0]} {args[1] if len(args) > 1 else ''}: {message}")
            return {"__error__": message}
        out = proc.stdout.strip()
        return json.loads(out) if out else None

    def cdk(self, *args: str, check: bool = True) -> int:
        """Run ``npx aws-cdk@2 ...`` streaming output; return the exit code."""
        cmd = [_exe("npx"), "aws-cdk@2", *args, "--profile", self.profile]
        _say("    $ npx aws-cdk@2 " + " ".join(args))
        code = subprocess.run(cmd, cwd=ROOT, env=self.env).returncode
        if check and code != 0:
            raise StepError(f"cdk {args[0]} failed (exit {code})")
        return code


def _is_error(result: Any) -> bool:
    return isinstance(result, dict) and "__error__" in result


# ---------------------------------------------------------------------------
# Shared steps
# ---------------------------------------------------------------------------


def preflight(run: Runner, need_devops_cli: bool = True) -> None:
    """Check tools and that credentials point at the cdk.json account."""
    _say("\n[preflight]")
    version_text = subprocess.run(
        [_exe("aws"), "--version"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=run.env,
    ).stdout
    version = parse_cli_version(version_text)
    _say(f"    AWS CLI {version[0]}.{version[1]}")
    if need_devops_cli and version < MIN_AWS_CLI:
        raise StepError(
            f"AWS CLI {MIN_AWS_CLI[0]}.{MIN_AWS_CLI[1]}+ is required for 'devops-agent' commands"
        )
    _exe("npx")
    identity = run.aws("sts", "get-caller-identity")
    if identity["Account"] != ACCOUNT:
        raise StepError(f"Credentials are for {identity['Account']}, cdk.json expects {ACCOUNT}")
    _say(f"    Account {ACCOUNT} as {identity['Arn']}")


def env_stacks(run: Runner, env: str) -> list[dict]:
    """CloudFormation stacks for this environment that are not deleted."""
    prefix = names_for(env)["stack_prefix"]
    stacks: list[dict] = []
    token: Optional[str] = None
    while True:
        args = ["cloudformation", "list-stacks"]
        if token:
            args += ["--starting-token", token]
        page = run.aws(*args, quiet=True)
        stacks += [
            s for s in page.get("StackSummaries", [])
            if s["StackName"].startswith(prefix) and s["StackStatus"] != "DELETE_COMPLETE"
        ]
        token = page.get("NextToken")
        if not token:
            return stacks


def stack_output(run: Runner, stack: str, key: str) -> str:
    """Read a CloudFormation output value ('' if missing)."""
    data = run.aws("cloudformation", "describe-stacks", "--stack-name", stack, quiet=True)
    for output in data["Stacks"][0].get("Outputs", []):
        if output["OutputKey"] == key:
            return output["OutputValue"]
    return ""


def find_spaces(run: Runner, env: str) -> list[dict]:
    """Agent Spaces named aiops-<env>."""
    data = run.aws("devops-agent", "list-agent-spaces", quiet=True) or {}
    return [s for s in data.get("agentSpaces", []) if s.get("name") == names_for(env)["space"]]


# ---------------------------------------------------------------------------
# up
# ---------------------------------------------------------------------------


def ensure_bootstrap(run: Runner) -> None:
    """Bootstrap CDK in the account/region if the CDKToolkit stack is missing."""
    _say("\n[cdk bootstrap]")
    found = run.aws("cloudformation", "describe-stacks", "--stack-name", "CDKToolkit",
                    check=False, quiet=True)
    if _is_error(found):
        run.cdk("bootstrap", f"aws://{ACCOUNT}/{REGION}")
    else:
        _say("    CDKToolkit present")


def ensure_ecr(run: Runner) -> None:
    """Create the shared ECR repository if it doesn't exist (CI pushes before deploy)."""
    _say("\n[ecr]")
    found = run.aws("ecr", "describe-repositories", "--repository-names", ECR_REPO,
                    check=False, quiet=True)
    if _is_error(found):
        run.aws("ecr", "create-repository", "--repository-name", ECR_REPO,
                "--image-scanning-configuration", "scanOnPush=true")
    else:
        _say(f"    repository '{ECR_REPO}' present")


def build_image(run: Runner, env: str, skip: bool) -> str:
    """Build and push aiops:latest-<env> via CodeBuild, or verify it exists."""
    tag = f"latest-{env}"
    _say(f"\n[image {ECR_REPO}:{tag}]")
    if not skip:
        code = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "build_and_push.py"),
             "--tag", tag, "--region", REGION, "--profile", run.profile],
            cwd=ROOT, env=run.env,
        ).returncode
        if code != 0:
            raise StepError("image build failed (see CodeBuild logs above)")
    found = run.aws("ecr", "describe-images", "--repository-name", ECR_REPO,
                    "--image-ids", f"imageTag={tag}", check=False, quiet=True)
    if _is_error(found):
        raise StepError(f"image {ECR_REPO}:{tag} not found in ECR")
    _say("    image present in ECR")
    return tag


def ensure_role(run: Runner, name: str, actions: list[str], managed_arn: str,
                inline: Optional[tuple[str, dict]], description: str) -> bool:
    """Create an IAM role if missing. Returns True if it was created."""
    found = run.aws("iam", "get-role", "--role-name", name, check=False, quiet=True)
    if not _is_error(found):
        _say(f"    role {name} present")
        return False
    run.aws("iam", "create-role", "--role-name", name,
            "--assume-role-policy-document", run.json_file(trust_policy(actions)),
            "--description", description,
            "--tags", *[f"Key={k},Value={v}" for k, v in TAGS.items()])
    run.aws("iam", "attach-role-policy", "--role-name", name, "--policy-arn", managed_arn)
    if inline:
        run.aws("iam", "put-role-policy", "--role-name", name, "--policy-name", inline[0],
                "--policy-document", run.json_file(inline[1]))
    return True


def store_webhook(profile: str, secret_id: str, url: str, secret: str, web_app_url: str) -> None:
    """Write the webhook credentials to Secrets Manager (value never printed)."""
    import boto3  # local import: only needed for `up`

    client = boto3.Session(profile_name=profile, region_name=REGION).client("secretsmanager")
    client.put_secret_value(
        SecretId=secret_id,
        SecretString=json.dumps({"url": url, "secret": secret, "web_app_url": web_app_url}),
    )


def read_stored_webhook_url(profile: str, secret_id: str) -> str:
    """URL currently stored in the webhook secret ('' if unset or missing)."""
    import boto3

    client = boto3.Session(profile_name=profile, region_name=REGION).client("secretsmanager")
    try:
        value = client.get_secret_value(SecretId=secret_id)["SecretString"]
        return json.loads(value).get("url", "")
    except Exception:  # noqa: BLE001 - missing secret / bad JSON both mean "not stored"
        return ""


def setup_devops_agent(run: Runner, env: str) -> None:
    """Create (or reuse) the Agent Space and wire its webhook into Secrets Manager."""
    n = names_for(env)
    _say("\n[aws devops agent]")
    created = ensure_role(
        run, n["space_role"], ["sts:AssumeRole"], AGENT_SPACE_POLICY,
        ("AllowCreateServiceLinkedRoles", {
            "Version": "2012-10-17",
            "Statement": [{
                "Sid": "AllowCreateServiceLinkedRoles", "Effect": "Allow",
                "Action": ["iam:CreateServiceLinkedRole"],
                "Resource": [f"arn:aws:iam::{ACCOUNT}:role/aws-service-role/"
                             "resource-explorer-2.amazonaws.com/AWSServiceRoleForResourceExplorer"],
            }],
        }),
        f"AWS DevOps Agent space role for AIOps {env} (read-only investigations)",
    )
    created |= ensure_role(
        run, n["app_role"], ["sts:AssumeRole", "sts:TagSession"], OPERATOR_APP_POLICY,
        None, f"AWS DevOps Agent operator web app role for AIOps {env}",
    )
    if created:
        _say("    waiting 15s for IAM propagation")
        time.sleep(15)

    spaces = find_spaces(run, env)
    if len(spaces) > 1:
        raise StepError(f"{len(spaces)} Agent Spaces named {n['space']}; delete the extras first")
    if spaces:
        space_id = spaces[0]["agentSpaceId"]
        _say(f"    Agent Space {n['space']} present ({space_id})")
    else:
        resp = run.aws("devops-agent", "create-agent-space", "--name", n["space"],
                       "--description", f"AIOps self-healing ({env}): investigations forwarded "
                       "by the AIOps pipeline. Investigation only; no elevated actions.",
                       "--tags", ",".join(f"{k}={v}" for k, v in {**TAGS, "environment": env}.items()))
        space_id = resp["agentSpace"]["agentSpaceId"]
        _say(f"    created Agent Space {n['space']} ({space_id})")

    associations = (run.aws("devops-agent", "list-associations", "--agent-space-id", space_id,
                            quiet=True) or {}).get("associations", [])
    if not any(a.get("serviceId") == "aws" for a in associations):
        config = run.json_file({"aws": {
            "assumableRoleArn": f"arn:aws:iam::{ACCOUNT}:role/{n['space_role']}",
            "accountId": ACCOUNT, "accountType": "monitor",
        }})
        for attempt in range(4):  # the new role can take a moment to become assumable
            result = run.aws("devops-agent", "associate-service", "--agent-space-id", space_id,
                             "--service-id", "aws", "--configuration", config, check=False)
            if not _is_error(result):
                break
            if attempt == 3:
                raise StepError(f"account association failed: {result['__error__']}")
            time.sleep(15)
    else:
        _say("    account association present")

    # get-operator-app returns an error OR empty output when the app isn't enabled yet.
    app = run.aws("devops-agent", "get-operator-app", "--agent-space-id", space_id,
                  check=False, quiet=True)
    if not isinstance(app, dict) or _is_error(app) or not app.get("operatorAppUrl"):
        app = run.aws("devops-agent", "enable-operator-app", "--agent-space-id", space_id,
                      "--auth-flow", "iam", "--operator-app-role-arn",
                      f"arn:aws:iam::{ACCOUNT}:role/{n['app_role']}") or {}
    else:
        _say("    operator web app already enabled")
    web_app_url = app.get("operatorAppUrl") or f"https://{space_id}.aidevops.global.app.aws"

    channel = next((a for a in associations if a.get("serviceId") == "event_channel"), None)
    live_url = None
    if channel:
        hooks = run.aws("devops-agent", "list-webhooks", "--agent-space-id", space_id,
                        "--association-id", channel["associationId"], quiet=True) or {}
        live_url = next((h.get("webhookUrl") for h in hooks.get("webhooks", [])), None)
    action = webhook_action(read_stored_webhook_url(run.profile, n["webhook_secret"]), live_url)
    if action == "keep":
        _say("    webhook present and stored in Secrets Manager")
    else:
        if action == "recreate":
            _say("    webhook secret is unrecoverable; recreating the webhook")
            run.aws("devops-agent", "disassociate-service", "--agent-space-id", space_id,
                    "--association-id", channel["associationId"])
        _say("    $ aws devops-agent associate-service --service-id event_channel  (output hidden)")
        resp = run.aws("devops-agent", "associate-service", "--agent-space-id", space_id,
                       "--service-id", "event_channel",
                       "--configuration", run.json_file({"eventChannel": {}}), quiet=True) or {}
        hook = resp.get("webhook") or {}
        if not hook.get("webhookUrl") or not hook.get("webhookSecret"):
            raise StepError("webhook response had no URL/secret; rotate it in the console")
        store_webhook(run.profile, n["webhook_secret"], hook["webhookUrl"],
                      hook["webhookSecret"], web_app_url)
        hook = resp = None  # drop the secret from memory as soon as it is stored
        _say(f"    HMAC webhook created and stored in {n['webhook_secret']} (secret not shown)")
    _say(f"    operator web app: {web_app_url}")


def restart_and_check(run: Runner, env: str) -> None:
    """Restart ECS so tasks load the webhook secret, then wait for /health = 200."""
    n = names_for(env)
    compute = f"{n['stack_prefix']}Compute"
    service = stack_output(run, compute, "ServiceName")
    _say("\n[ecs restart + health]")
    run.aws("ecs", "update-service", "--cluster", n["cluster"], "--service", service,
            "--force-new-deployment", quiet=True)
    _say(f"    waiting for {service} to stabilise")
    run.aws("ecs", "wait", "services-stable", "--cluster", n["cluster"], "--services", service,
            quiet=True)
    url = stack_output(run, compute, "ApiEndpoint").rstrip("/") + "/health"
    deadline = time.time() + 300
    last = ""
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=10) as resp:  # noqa: S310 - our https API
                if resp.status == 200:
                    _say(f"    {url} -> 200")
                    return
                last = f"HTTP {resp.status}"
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}"
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last = str(e)
        time.sleep(15)
    raise StepError(f"health check did not return 200 within 5 minutes ({last})")


def cmd_up(run: Runner, args: argparse.Namespace) -> int:
    """Provision everything for one environment."""
    env = args.env
    preflight(run, need_devops_cli=not args.no_devops_agent)
    ensure_bootstrap(run) if not args.dry_run else _say("\n[cdk bootstrap] (dry run: check only)")
    if args.dry_run:
        _say("\n[dry run] synthesizing all stacks; no AWS changes will be made")
        run.cdk("synth", "--all", "--quiet", "--context", f"environment={env}",
                "--context", f"imageTag=latest-{env}",
                "--context", f"devopsAgentEnabled={'false' if args.no_devops_agent else 'true'}")
        stacks = env_stacks(run, env)
        _say(f"    existing {env} stacks: {[s['StackName'] for s in stacks] or 'none'}")
        if not args.no_devops_agent:
            _say(f"    existing Agent Space {names_for(env)['space']}: "
                 f"{'yes' if find_spaces(run, env) else 'no'}")
        _say("\nDRY RUN OK - re-run without --dry-run to provision.")
        return 0

    ensure_ecr(run)
    tag = build_image(run, env, args.skip_build)
    _say(f"\n[cdk deploy --all] environment={env}")
    run.cdk("deploy", "--all", "--require-approval", "never",
            "--context", f"environment={env}", "--context", f"imageTag={tag}",
            "--context", f"devopsAgentEnabled={'false' if args.no_devops_agent else 'true'}")
    if not args.no_devops_agent:
        setup_devops_agent(run, env)
    restart_and_check(run, env)
    endpoint = stack_output(run, f"{names_for(env)['stack_prefix']}Compute", "ApiEndpoint")
    _say(f"\nUP COMPLETE: {env}\n    API: {endpoint}\n"
         f"    Logs: aws logs tail /aiops/{env}/ecs --follow --profile {run.profile}\n"
         f"    Tear down: python scripts/aiops_env.py down --env {env}")
    return 0


# ---------------------------------------------------------------------------
# down
# ---------------------------------------------------------------------------


def delete_role(run: Runner, name: str) -> None:
    """Detach/delete all policies and delete an IAM role (no-op if missing)."""
    if _is_error(run.aws("iam", "get-role", "--role-name", name, check=False, quiet=True)):
        return
    attached = run.aws("iam", "list-attached-role-policies", "--role-name", name, quiet=True)
    for policy in attached.get("AttachedPolicies", []):
        run.aws("iam", "detach-role-policy", "--role-name", name, "--policy-arn", policy["PolicyArn"])
    inline = run.aws("iam", "list-role-policies", "--role-name", name, quiet=True)
    for policy_name in inline.get("PolicyNames", []):
        run.aws("iam", "delete-role-policy", "--role-name", name, "--policy-name", policy_name)
    run.aws("iam", "delete-role", "--role-name", name)


def teardown_devops_agent(run: Runner, env: str) -> None:
    """Delete the Agent Space(s) named aiops-<env> and the two roles."""
    n = names_for(env)
    _say("\n[aws devops agent]")
    for space in find_spaces(run, env):
        run.aws("devops-agent", "delete-agent-space", "--agent-space-id", space["agentSpaceId"])
        _say(f"    deleted Agent Space {n['space']} ({space['agentSpaceId']})")
    for role in (n["space_role"], n["app_role"]):
        delete_role(run, role)
    _say("    IAM roles removed")


def purge_retained(run: Runner, env: str) -> None:
    """Delete leftovers with fixed names that would block the next `up`."""
    n = names_for(env)
    _say("\n[purge leftovers]")
    if not _is_error(run.aws("dynamodb", "describe-table", "--table-name", n["table"],
                             check=False, quiet=True)):
        run.aws("dynamodb", "delete-table", "--table-name", n["table"])
        run.aws("dynamodb", "wait", "table-not-exists", "--table-name", n["table"], quiet=True)

    secrets = run.aws("secretsmanager", "list-secrets", "--include-planned-deletion",
                      "--filters", f"Key=name,Values={n['param_prefix']}", quiet=True)
    for secret in secrets.get("SecretList", []):
        if not secret["Name"].startswith(n["param_prefix"]):
            continue
        if secret.get("DeletedDate"):  # scheduled: restore so it can be force-deleted now
            run.aws("secretsmanager", "restore-secret", "--secret-id", secret["ARN"])
        run.aws("secretsmanager", "delete-secret", "--secret-id", secret["ARN"],
                "--force-delete-without-recovery")

    groups = run.aws("logs", "describe-log-groups", "--log-group-name-prefix", n["param_prefix"],
                     quiet=True)
    for group in groups.get("logGroups", []):
        run.aws("logs", "delete-log-group", "--log-group-name", group["logGroupName"])

    params = run.aws("ssm", "get-parameters-by-path", "--path", n["param_prefix"].rstrip("/"),
                     "--recursive", quiet=True)
    names = [p["Name"] for p in params.get("Parameters", [])]
    for i in range(0, len(names), 10):
        run.aws("ssm", "delete-parameters", "--names", *names[i:i + 10])
    _say("    leftovers purged")


def report_leftovers(run: Runner, env: str) -> list[str]:
    """List anything for this environment that still exists."""
    n = names_for(env)
    left = [f"stack {s['StackName']} ({s['StackStatus']})" for s in env_stacks(run, env)]
    left += [f"Agent Space {n['space']}" for _ in find_spaces(run, env)]
    for role in (n["space_role"], n["app_role"]):
        if not _is_error(run.aws("iam", "get-role", "--role-name", role, check=False, quiet=True)):
            left.append(f"IAM role {role}")
    if not _is_error(run.aws("dynamodb", "describe-table", "--table-name", n["table"],
                             check=False, quiet=True)):
        left.append(f"DynamoDB table {n['table']}")
    secrets = run.aws("secretsmanager", "list-secrets", "--filters",
                      f"Key=name,Values={n['param_prefix']}", quiet=True)
    left += [f"secret {s['Name']}" for s in secrets.get("SecretList", [])
             if s["Name"].startswith(n["param_prefix"])]
    return left


def confirm(env: str, assume_yes: bool) -> bool:
    """Require typing the environment name (always for staging/prod)."""
    if assume_yes and env == "dev":
        return True
    _say(f"\nThis DELETES every AIOps '{env}' resource in {ACCOUNT}/{REGION}, including the "
         f"Agent Space aiops-{env} and its investigation history.")
    return input(f"Type '{env}' to continue: ").strip() == env


def cmd_down(run: Runner, args: argparse.Namespace) -> int:
    """Destroy everything for one environment."""
    env = args.env
    preflight(run)
    if not confirm(env, args.yes):
        _say("Aborted.")
        return 1

    teardown_devops_agent(run, env)

    # ECS race: CloudFormation can delete the cluster while the just-deleted service
    # still holds the Fargate capacity provider ("capacity provider is in use"),
    # leaving Compute in DELETE_FAILED. It clears within a minute, so retry.
    destroy_code, remaining = 1, []
    for attempt in range(1, DESTROY_ATTEMPTS + 1):
        _say(f"\n[cdk destroy --all] environment={env} (attempt {attempt}/{DESTROY_ATTEMPTS})")
        destroy_code = run.cdk("destroy", "--all", "--force", "--context", f"environment={env}",
                               check=False)
        remaining = env_stacks(run, env)
        if destroy_code == 0 and not remaining:
            break
        if attempt < DESTROY_ATTEMPTS:
            _say(f"    {len(remaining)} stack(s) left; retrying in {DESTROY_RETRY_SECONDS}s")
            time.sleep(DESTROY_RETRY_SECONDS)
    if destroy_code != 0 or remaining:
        _say(f"    WARNING: cdk destroy exit={destroy_code}, stacks left: "
             f"{[s['StackName'] for s in remaining]}")

    if not remaining and (env == "dev" or args.purge_retained):
        purge_retained(run, env)
    elif not remaining:
        _say("\n[leftovers] kept for staging/prod (re-run with --purge-retained to delete)")

    if args.include_ecr:
        _say("\n[ecr] deleting shared repository (all environments' images)")
        run.aws("ecr", "delete-repository", "--repository-name", ECR_REPO, "--force", check=False)

    left = report_leftovers(run, env)
    if left:
        _say("\nDOWN INCOMPLETE - still present:\n    " + "\n    ".join(left))
        return 2
    _say(f"\nDOWN COMPLETE: nothing left for '{env}'.\n"
         "    Kept (shared): ECR repo 'aiops', CDKToolkit, CodeBuild helper role/bucket, SES identity.\n"
         f"    Re-create: python scripts/aiops_env.py up --env {env}")
    return 0


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------


def cmd_status(run: Runner, args: argparse.Namespace) -> int:
    """Read-only summary of what exists for an environment."""
    env = args.env
    n = names_for(env)
    preflight(run)
    _say(f"\n[status {env}]")
    stacks = env_stacks(run, env)
    for stack in stacks:
        _say(f"    stack {stack['StackName']}: {stack['StackStatus']}")
    if not stacks:
        _say("    no stacks")
    spaces = find_spaces(run, env)
    _say(f"    Agent Space {n['space']}: "
         + (", ".join(s["agentSpaceId"] for s in spaces) if spaces else "none"))
    _say(f"    webhook stored in Secrets Manager: "
         f"{'yes' if read_stored_webhook_url(run.profile, n['webhook_secret']) else 'no'}")
    if any(s["StackName"] == f"{n['stack_prefix']}Compute" for s in stacks):
        _say(f"    API: {stack_output(run, n['stack_prefix'] + 'Compute', 'ApiEndpoint')}")
    return 0


# ---------------------------------------------------------------------------


def main(argv: Optional[list[str]] = None) -> int:
    """Entry point."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("command", choices=("up", "down", "status"))
    parser.add_argument("--env", default="dev", choices=ENVIRONMENTS)
    parser.add_argument("--profile", default="mfa", help="AWS CLI profile (default: mfa)")
    parser.add_argument("--skip-build", action="store_true", help="up: reuse aiops:latest-<env>")
    parser.add_argument("--no-devops-agent", action="store_true",
                        help="up: skip the AWS DevOps Agent setup")
    parser.add_argument("--dry-run", action="store_true",
                        help="up: preflight + synth only, no changes")
    parser.add_argument("--yes", "-y", action="store_true",
                        help="down: skip confirmation (dev only)")
    parser.add_argument("--purge-retained", action="store_true",
                        help="down: also delete retained data for staging/prod")
    parser.add_argument("--include-ecr", action="store_true",
                        help="down: also delete the shared ECR repository")
    args = parser.parse_args(argv)

    run = Runner(args.profile)
    started = time.time()
    try:
        handler = {"up": cmd_up, "down": cmd_down, "status": cmd_status}[args.command]
        code = handler(run, args)
    except StepError as e:
        _say(f"\nFAILED: {e}")
        code = 1
    except KeyboardInterrupt:
        _say("\nInterrupted.")
        code = 130
    finally:
        run.close()
    _say(f"({args.command} finished in {int(time.time() - started)}s, exit {code})")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
