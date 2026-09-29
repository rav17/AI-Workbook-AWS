"""Break the target EC2 instance to trigger self-healing alerts.

Supports three failure modes: CPU stress, memory pressure, and network flood.
Each mode stresses the target instance and optionally triggers the alert
directly via Lambda (--trigger-alert) for immediate pipeline execution.

Usage:
    python demo/break_target.py --mode cpu                     # Stress CPU for 120s
    python demo/break_target.py --mode memory --duration 300   # Memory pressure for 5min
    python demo/break_target.py --mode network --duration 60   # Network flood for 1min
    python demo/break_target.py --mode cpu --trigger-alert     # Stress + fire alert immediately
    python demo/break_target.py --mode memory --trigger-alert  # Memory + fire alert immediately
    python demo/break_target.py --mode network --trigger-alert # Network + fire alert immediately
"""

import argparse
import json
import os
import sys
import time

import boto3


def get_config():
    """Read config from cdk.json."""
    cdk_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "cdk.json")
    with open(cdk_path) as f:
        return json.load(f)["context"]


def get_target_instance_id(region: str, env_name: str) -> str:
    """Get the target instance ID from CloudFormation outputs."""
    cf = boto3.client("cloudformation", region_name=region)
    try:
        resp = cf.describe_stacks(StackName=f"Aiops-{env_name}-Simulation")
        for output in resp["Stacks"][0].get("Outputs", []):
            if output["OutputKey"] == "TargetInstanceId":
                return output["OutputValue"]
    except Exception as e:
        print(f"  ERROR: Could not find Simulation stack: {e}")
        sys.exit(1)
    return ""


def break_cpu(instance_id: str, region: str, env_name: str, duration: int):
    """Send SSM command to stress the CPU.

    First ensures stress-ng is installed, then runs it in the background.
    """
    ssm = boto3.client("ssm", region_name=region)

    # Ensure stress-ng is installed (userdata may not have completed)
    print(f"  Ensuring stress-ng is installed on {instance_id}...")
    install_resp = ssm.send_command(
        InstanceIds=[instance_id],
        DocumentName="AWS-RunShellScript",
        Parameters={"commands": [
            "which stress-ng > /dev/null 2>&1 || dnf install -y stress-ng > /dev/null 2>&1",
            "which stress-ng && echo 'stress-ng ready' || echo 'INSTALL FAILED'",
        ]},
        Comment="AIOps: ensure stress-ng installed",
        TimeoutSeconds=60,
    )
    install_cmd_id = install_resp["Command"]["CommandId"]
    time.sleep(10)
    install_result = ssm.get_command_invocation(
        CommandId=install_cmd_id, InstanceId=instance_id
    )
    if "INSTALL FAILED" in install_result.get("StandardOutputContent", ""):
        print("  ERROR: Failed to install stress-ng on target instance")
        sys.exit(1)
    print(f"  stress-ng confirmed available")

    # Run stress via the SSM document
    print(f"  Starting CPU stress for {duration}s...")
    response = ssm.send_command(
        InstanceIds=[instance_id],
        DocumentName=f"aiops-break-cpu-{env_name}",
        Parameters={"Duration": [str(duration)]},
        Comment=f"AIOps demo: stress CPU for {duration}s",
    )

    command_id = response["Command"]["CommandId"]
    print(f"  Command sent: {command_id}")

    # Wait for execution confirmation
    time.sleep(5)
    result = ssm.get_command_invocation(
        CommandId=command_id,
        InstanceId=instance_id,
    )
    print(f"  Status: {result['Status']}")
    if result.get("StandardOutputContent"):
        print(f"  Output: {result['StandardOutputContent'].strip()}")

    # Verify stress-ng is actually running
    time.sleep(3)
    verify_resp = ssm.send_command(
        InstanceIds=[instance_id],
        DocumentName="AWS-RunShellScript",
        Parameters={"commands": ["ps aux | grep 'stress-ng' | grep -v grep | head -3"]},
        Comment="Verify stress-ng running",
    )
    time.sleep(5)
    verify_result = ssm.get_command_invocation(
        CommandId=verify_resp["Command"]["CommandId"],
        InstanceId=instance_id,
    )
    verify_output = verify_result.get("StandardOutputContent", "").strip()
    if verify_output:
        print(f"  Verified: stress-ng is running")
        print(f"    {verify_output.splitlines()[0]}")
    else:
        print("  WARNING: stress-ng process not found — may have exited early")

    return command_id


def main():
    parser = argparse.ArgumentParser(description="Break target EC2 to trigger alerts")
    parser.add_argument("--duration", type=int, default=120,
                        help="Stress duration in seconds (default: 120)")
    parser.add_argument("--environment", default="dev")
    parser.add_argument("--mode", choices=["cpu", "memory", "network"], default="cpu",
                        help="cpu=HighCPUUsage, memory=HighMemoryUsage, network=NetworkFloodDetected")
    parser.add_argument("--trigger-alert", action="store_true",
                        help="Also immediately fire the alert via Lambda (skip CloudWatch wait)")
    args = parser.parse_args()

    config = get_config()
    region = config["awsRegion"]

    print("╔══════════════════════════════════════════════════════════╗")
    print("║   AIOps Production Simulation — BREAK Target Host       ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print(f"  Environment: {args.environment}")
    print(f"  Duration: {args.duration}s")
    print()

    # Get target instance
    instance_id = get_target_instance_id(region, args.environment)
    if not instance_id:
        print("  ERROR: No target instance found")
        sys.exit(1)
    print(f"  Target instance: {instance_id}")
    print(f"  Mode: {args.mode}")

    # Ensure detailed monitoring is enabled (basic = 5min intervals, too slow for demos)
    ec2 = boto3.client("ec2", region_name=region)
    monitoring = ec2.describe_instances(
        InstanceIds=[instance_id]
    )["Reservations"][0]["Instances"][0]["Monitoring"]["State"]
    if monitoring != "enabled":
        print(f"  Enabling detailed monitoring (was: {monitoring})...")
        ec2.monitor_instances(InstanceIds=[instance_id])
        print("  Detailed monitoring enabled (1-min resolution)")

    if args.mode == "cpu":
        # --- Rule mode: stress CPU → HighCPUUsage alert (has playbook) ---
        print()
        print("  [1/3] Stressing CPU...")
        break_cpu(instance_id, region, args.environment, args.duration)

        print()
        print("  [2/3] Waiting for CloudWatch to detect high CPU (~2 min)...")
        print()
        print("  [3/3] What happens next (automatically):")
        print("        • CloudWatch detects CPU > 80%")
        print("        • Alarm fires → Lambda → webhook")
        print("        • Alert: HighCPUUsage (HAS matching playbook)")
        print("        • → RULE MODE: Email with 'Approve' button")
        print("        • You click → Ansible runs fix_high_cpu.yml")

    elif args.mode == "memory":
        # --- Memory mode: stress RAM → HighMemoryUsage alert (has playbook) ---
        # Note: No CloudWatch memory alarm exists (EC2 has no native memory metric)
        # so we always trigger the Lambda directly after stressing.
        print()
        print("  [1/2] Stressing memory...")
        _stress_memory(instance_id, region, args.duration)

        print()
        print("  [2/2] Triggering HighMemoryUsage alert via Lambda...")
        print("        (No native CloudWatch memory metric — using direct trigger)")
        _trigger_alert(instance_id, region, args.environment, args.mode)

        print()
        print("  What happens next:")
        print("        • Alert: HighMemoryUsage (HAS matching playbook)")
        print("        • → RULE MODE: Email with 'Approve' button")
        print("        • You click → SSM runs restart_process.yml")
        print("        • Process killed → memory freed")

    else:
        # --- AI mode: flood network → NetworkFloodDetected alert (no playbook) ---
        # Triggers Lambda directly since CloudWatch network alarm is unreliable
        # for short bursts.
        print()
        print("  [1/2] Flooding network packets...")
        _flood_network(instance_id, region, args.duration)

        print()
        print("  [2/2] Triggering NetworkFloodDetected alert via Lambda...")
        print("        (Direct trigger for reliable demo)")
        _trigger_alert(instance_id, region, args.environment, args.mode)

        print()
        print("  What happens next:")
        print("        • Alert: NetworkFloodDetected (NO matching playbook)")
        print("        • → AI AGENT MODE: Bedrock analyzes the issue")
        print("        • Email with 'Suggested Steps' (no auto-execute)")

    print()
    print("  Monitor:")
    print(f"    aws logs tail /aiops/{args.environment}/ecs --region {region} --follow")

    # For CPU mode, optionally fire the alert immediately via Lambda
    if args.trigger_alert and args.mode == "cpu":
        print()
        print("  ─── Triggering Alert via Lambda ───")
        _trigger_alert(instance_id, region, args.environment, args.mode)


def _trigger_alert(instance_id: str, region: str, env_name: str, mode: str):
    """Invoke the alert trigger Lambda directly to skip CloudWatch delay."""
    alert_map = {
        "cpu": {
            "alert_name": "HighCPUUsage",
            "severity": "critical",
            "service_name": "web-frontend",
            "summary": f"CPU usage exceeded 80% on {instance_id} (demo stress test)",
        },
        "memory": {
            "alert_name": "HighMemoryUsage",
            "severity": "warning",
            "service_name": "web-frontend",
            "summary": f"Memory usage exceeded 90% on {instance_id} (demo stress test)",
        },
        "network": {
            "alert_name": "NetworkFloodDetected",
            "severity": "critical",
            "service_name": "web-frontend",
            "summary": f"Network packets spike on {instance_id} (demo flood test)",
        },
    }

    payload = alert_map[mode]
    payload["instance"] = instance_id

    client = boto3.client("lambda", region_name=region)
    response = client.invoke(
        FunctionName=f"aiops-alert-trigger-{env_name}",
        Payload=json.dumps(payload).encode(),
    )

    result = json.loads(response["Payload"].read())
    status_code = result.get("status", response.get("StatusCode"))
    print(f"  Alert fired: {payload['alert_name']} → status={status_code}")
    print(f"  Pipeline is now processing the alert...")


def _stress_memory(instance_id: str, region: str, duration: int):
    """Send SSM command to stress memory on the target instance."""
    ssm = boto3.client("ssm", region_name=region)

    commands = [
        "which stress-ng > /dev/null 2>&1 || dnf install -y stress-ng > /dev/null 2>&1",
        f"nohup stress-ng --vm 2 --vm-bytes 80% --vm-keep --timeout {duration}s > /dev/null 2>&1 &",
        "sleep 2",
        "ps aux | grep 'stress-ng' | grep -v grep | head -1 && echo 'Memory stress started' || echo 'FAILED to start stress'",
        "free -m | head -3",
    ]

    print(f"  Sending memory stress command to {instance_id}...")
    response = ssm.send_command(
        InstanceIds=[instance_id],
        DocumentName="AWS-RunShellScript",
        Parameters={"commands": commands},
        Comment=f"AIOps demo: memory stress for {duration}s",
        TimeoutSeconds=60,
    )
    command_id = response["Command"]["CommandId"]
    print(f"  Command sent: {command_id}")

    time.sleep(10)
    try:
        result = ssm.get_command_invocation(
            CommandId=command_id, InstanceId=instance_id
        )
        print(f"  Status: {result['Status']}")
        if result.get("StandardOutputContent"):
            print(f"  Output: {result['StandardOutputContent'].strip()}")
    except Exception as e:
        print(f"  (Waiting for command: {e})")


def _flood_network(instance_id: str, region: str, duration: int):
    """Send SSM command to generate high external network traffic."""
    ssm = boto3.client("ssm", region_name=region)

    # Generate real external traffic by rapid-fire curl requests to AWS metadata + DNS queries
    cmd = (
        f"which dig > /dev/null 2>&1 || dnf install -y bind-utils > /dev/null 2>&1; "
        f"for i in $(seq 1 {duration}); do "
        f"curl -s http://169.254.169.254/latest/meta-data/instance-id > /dev/null & "
        f"curl -s http://169.254.169.254/latest/meta-data/ami-id > /dev/null & "
        f"dig +short amazon.com @169.254.169.253 > /dev/null & "
        f"dig +short aws.amazon.com @169.254.169.253 > /dev/null & "
        f"sleep 0.05; done; echo 'Network flood complete'"
    )

    print(f"  Sending network flood command to {instance_id}...")
    response = ssm.send_command(
        InstanceIds=[instance_id],
        DocumentName="AWS-RunShellScript",
        Parameters={"commands": [cmd]},
        Comment=f"AIOps demo: network flood for {duration}s",
        TimeoutSeconds=duration + 60,
    )
    command_id = response["Command"]["CommandId"]
    print(f"  Command sent: {command_id}")
    print(f"  Flood running in background for ~{duration}s...")
    time.sleep(5)
    result = ssm.get_command_invocation(CommandId=command_id, InstanceId=instance_id)
    print(f"  Status: {result['Status']}")


if __name__ == "__main__":
    main()
