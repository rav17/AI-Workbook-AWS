"""Create a real incident on two hosts and let the CloudWatch alarms raise it.

Nothing here calls the alert Lambda. The script only creates load; the Simulation
stack's own alarms detect it and send the alerts, the same way production would.
One fault per host:

  primary    memory held at ~88% (available < 20%)  -> aiops-target-memory-<env>
             also sends the HTTP flood to the secondary
  secondary  receives the flood on port 8080         -> aiops-target-network-<env>

Expected emails:
  * HighMemoryUsage (primary): approval email for playbooks/fix_high_memory.yml
  * NetworkFloodDetected (secondary): AI advisory email (no playbook)
  * DevOps Agent RCA email for each (both are critical), a few minutes later

The primary's CPU alarm must stay OK: the memory stress holds memory without
spinning (stress-ng --vm-hang 0) and no CPU load is generated.

What it does, in order:
  1. Preflight: alarms exist with ALARM and OK actions, the network alarm watches the
     secondary, the memory metric is arriving, the DevOps Agent webhook and findings
     Lambda are configured, and no alarm is already in ALARM.
  2. Starts the load through SSM.
  3. Waits for the memory and network alarms to go to ALARM and checks that the
     CPU alarm stayed OK.
  4. When the load ends, the alarms return to OK and send "resolved", which
     cancels any remediation still waiting for approval.

Requirements: Simulation stack with two targets (SecondaryTargetInstanceId and
SecondaryTargetPrivateIp outputs) and the CloudWatch agent association; stacks
deployed with devopsAgentEnabled=true and devopsAgentFindingsEnabled=true
(see docs/devops-agent-integration.md).

Usage:
    python demo/trigger_p1_incident.py --dry-run     # preflight only
    python demo/trigger_p1_incident.py               # 600 s of load, then watch alarms
    python demo/trigger_p1_incident.py --duration 900
    python demo/trigger_p1_incident.py --no-wait     # start the load and exit
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

# Reuse the stress helpers from the existing demo script (same directory).
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from break_target import (  # noqa: E402
    _stress_memory,
    flood_network_from_peer,
    get_config,
    get_secondary_instance_id,
    get_secondary_private_ip,
    get_target_instance_id,
)

_BOTO_CONFIG = Config(connect_timeout=5, read_timeout=30, retries={"max_attempts": 3})

MEMORY_ALARM = "aiops-target-memory-{env}"
NETWORK_ALARM = "aiops-target-network-{env}"
CPU_ALARM = "aiops-target-cpu-{env}"  # must stay OK


def _check(label: str, ok: bool, detail: str = "") -> bool:
    """Print a preflight result line and return the outcome."""
    mark = "OK  " if ok else "FAIL"
    print(f"  [{mark}] {label}{(' - ' + detail) if detail else ''}")
    return ok


def _alarm_instance(alarm: dict) -> str:
    """Return the InstanceId dimension an alarm watches, or ""."""
    for dim in alarm.get("Dimensions", []):
        if dim["Name"] == "InstanceId":
            return dim["Value"]
    return ""


def preflight(region: str, env_name: str, primary_id: str, secondary_id: str) -> bool:
    """Verify everything the alarm-driven demo depends on. Returns True if all pass."""
    cw = boto3.client("cloudwatch", region_name=region, config=_BOTO_CONFIG)
    lam = boto3.client("lambda", region_name=region, config=_BOTO_CONFIG)
    sm = boto3.client("secretsmanager", region_name=region, config=_BOTO_CONFIG)
    all_ok = True

    expected_host = {
        MEMORY_ALARM.format(env=env_name): primary_id,
        NETWORK_ALARM.format(env=env_name): secondary_id,
        CPU_ALARM.format(env=env_name): primary_id,
    }
    try:
        found = {
            a["AlarmName"]: a
            for a in cw.describe_alarms(AlarmNames=list(expected_host))["MetricAlarms"]
        }
    except (ClientError, BotoCoreError) as exc:
        return _check("CloudWatch alarms", False, str(exc))
    for name, host in expected_host.items():
        alarm = found.get(name)
        if alarm is None:
            all_ok &= _check(
                f"alarm {name}", False, "not found (deploy the Simulation stack)"
            )
            continue
        ready = bool(
            alarm["ActionsEnabled"] and alarm["AlarmActions"] and alarm["OKActions"]
        )
        watched = _alarm_instance(alarm)
        detail = f"watches {watched}, state {alarm['StateValue']}"
        if not ready:
            detail = "actions disabled or missing ALARM/OK action"
        elif watched != host:
            detail = (
                f"watches {watched}, expected {host} (redeploy the Simulation stack)"
            )
        all_ok &= _check(f"alarm {name}", ready and watched == host, detail)
        if alarm["StateValue"] == "ALARM":
            all_ok &= _check(
                f"{name} is idle",
                False,
                "already in ALARM; wait for it to return to OK",
            )

    end = datetime.now(timezone.utc)
    points = cw.get_metric_statistics(
        Namespace="CWAgent",
        MetricName="mem_available_percent",
        Dimensions=[{"Name": "InstanceId", "Value": primary_id}],
        StartTime=end - timedelta(minutes=10),
        EndTime=end,
        Period=60,
        Statistics=["Average"],
    )["Datapoints"]
    all_ok &= _check(
        "memory metric (CloudWatch agent)",
        bool(points),
        f"{len(points)} datapoints in 10 min"
        if points
        else "no mem_available_percent data",
    )

    name = f"aiops-devops-findings-{env_name}"
    try:
        lam.get_function_configuration(FunctionName=name)
        all_ok &= _check("findings Lambda (sends RCA email)", True, name)
    except (ClientError, BotoCoreError) as exc:
        all_ok &= _check("findings Lambda (sends RCA email)", False, f"{name}: {exc}")

    secret_id = f"/aiops/{env_name}/devops-agent-webhook"
    try:
        raw = sm.get_secret_value(SecretId=secret_id)["SecretString"]
        url_set = bool(json.loads(raw).get("url"))
        all_ok &= _check(
            "DevOps Agent webhook configured",
            url_set,
            secret_id
            if url_set
            else f"{secret_id} has an empty 'url' (run aiops_env.py up)",
        )
    except (ClientError, BotoCoreError, ValueError) as exc:
        all_ok &= _check("DevOps Agent webhook configured", False, str(exc))
    return all_ok


def wait_for_alarms(region: str, env_name: str, timeout: int) -> bool:
    """Poll until the memory and network alarms are in ALARM, or ``timeout`` passes.

    Returns:
        True if both alarms fired and the CPU alarm never left OK.
    """
    cw = boto3.client("cloudwatch", region_name=region, config=_BOTO_CONFIG)
    expected = {
        MEMORY_ALARM.format(env=env_name): "HighMemoryUsage",
        NETWORK_ALARM.format(env=env_name): "NetworkFloodDetected",
    }
    cpu = CPU_ALARM.format(env=env_name)
    fired: set[str] = set()
    cpu_tripped = False
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        alarms = cw.describe_alarms(AlarmNames=[*expected, cpu])["MetricAlarms"]
        states = {a["AlarmName"]: (a["StateValue"], _alarm_instance(a)) for a in alarms}
        now = datetime.now(timezone.utc).strftime("%H:%M:%SZ")
        for name, alert in expected.items():
            state, host = states.get(name, ("?", ""))
            if state == "ALARM" and name not in fired:
                fired.add(name)
                print(f"  {now}  {name} -> ALARM: {alert} for {host}")
        if states.get(cpu, ("",))[0] == "ALARM" and not cpu_tripped:
            cpu_tripped = True
            print(f"  WARNING: {cpu} went to ALARM; a HighCPUUsage email will follow")
        if len(fired) == len(expected):
            break
        time.sleep(15)
    for name in expected:
        if name not in fired:
            print(f"  {name} did not fire within {timeout}s")
    return len(fired) == len(expected) and not cpu_tripped


def main() -> None:
    """Entry point."""
    parser = argparse.ArgumentParser(
        description="Create a real two-host incident; the CloudWatch alarms raise it"
    )
    parser.add_argument("--environment", default="dev")
    parser.add_argument(
        "--duration",
        type=int,
        default=600,
        help="Load duration in seconds. EC2 network metrics can lag several "
        "minutes, so keep it at 600 or more. Default: 600",
    )
    parser.add_argument(
        "--no-wait",
        action="store_true",
        help="Start the load and exit without watching the alarms",
    )
    parser.add_argument("--skip-preflight", action="store_true")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run the preflight and print the plan; change nothing",
    )
    args = parser.parse_args()

    region = get_config()["awsRegion"]
    env_name = args.environment

    print("=" * 64)
    print("  AIOps incident simulation (alarms raise the alerts)")
    print("=" * 64)
    print(f"  Environment: {env_name}   Region: {region}")

    primary_id = get_target_instance_id(region, env_name)
    secondary_id = get_secondary_instance_id(region, env_name)
    secondary_ip = get_secondary_private_ip(region, env_name)
    if not (primary_id and secondary_id and secondary_ip):
        print(
            "  ERROR: the Simulation stack needs TargetInstanceId, "
            "SecondaryTargetInstanceId and SecondaryTargetPrivateIp outputs "
            f"(redeploy Aiops-{env_name}-Simulation)."
        )
        sys.exit(1)
    print(f"  Primary   (memory pressure, sends flood): {primary_id}")
    print(
        f"  Secondary (receives flood on :8080):      {secondary_id} ({secondary_ip})"
    )
    print()

    if not args.skip_preflight:
        print("  Preflight")
        if not preflight(region, env_name, primary_id, secondary_id):
            print("\n  Preflight failed. Fix the items above or use --skip-preflight.")
            sys.exit(1)
        print()

    if args.dry_run:
        print("  Dry run: nothing was changed.")
        return

    print(f"  [1/2] Creating load for {args.duration}s")
    print(f"  Memory pressure on {primary_id}...")
    _stress_memory(primary_id, region, args.duration)
    print(f"  Network flood {primary_id} -> {secondary_ip}:8080...")
    flood_network_from_peer(primary_id, secondary_ip, region, args.duration)

    if args.no_wait:
        print(
            "\n  [2/2] Not waiting (--no-wait). The alarms fire within a few minutes."
        )
        ok = True
    else:
        wait = min(args.duration, 900)
        print(f"\n  [2/2] Waiting up to {wait}s for the alarms")
        ok = wait_for_alarms(region, env_name, wait)

    print(f"""
  Expected emails:
    * HighMemoryUsage on {primary_id}: approval email for
      playbooks/fix_high_memory.yml (do not approve if the load should keep running)
    * NetworkFloodDetected on {secondary_id}: AI advisory email with a
      "did this help?" link
    * DevOps Agent RCA email for each, a few minutes after the alarm

  When the load ends (~{args.duration}s) both alarms return to OK and send "resolved";
  any approval still pending is cancelled.

  Watch:
    aws logs tail /aiops/{env_name}/ecs --region {region} --follow
    aws cloudwatch describe-alarms --alarm-name-prefix aiops-target- --region {region} \\
        --query "MetricAlarms[].[AlarmName,StateValue]" --output table
""")
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
