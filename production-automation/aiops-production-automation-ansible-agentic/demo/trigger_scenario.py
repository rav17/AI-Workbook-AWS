"""Trigger demo scenarios to test the full self-healing pipeline end-to-end.

Usage:
    python demo/trigger_scenario.py --scenario high-cpu
    python demo/trigger_scenario.py --scenario disk-full
    python demo/trigger_scenario.py --scenario service-down
    python demo/trigger_scenario.py --scenario inject --alert-name TestAlert --severity critical
"""

import argparse
import json
import subprocess
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone


SELF_HEALING_URL = "http://localhost:8080"
TARGET_CONTAINER = "target-host"


def inject_alert(alert_name: str, severity: str, instance: str = "web-server-01:9100",
                 service_name: str = "web-frontend", description: str = "") -> bool:
    """Directly inject an Alertmanager webhook payload into the self-healing service."""
    payload = {
        "version": "4",
        "groupKey": f"demo-{alert_name}",
        "status": "firing",
        "receiver": "aiops-webhook",
        "alerts": [{
            "status": "firing",
            "labels": {
                "alertname": alert_name,
                "severity": severity,
                "instance": instance,
                "job": "node-exporter",
                "service_name": service_name,
            },
            "annotations": {
                "summary": f"[DEMO] {alert_name} on {instance}",
                "description": description or f"Demo scenario triggered at {datetime.now(timezone.utc).isoformat()}",
            },
            "startsAt": datetime.now(timezone.utc).isoformat(),
            "endsAt": "0001-01-01T00:00:00Z",
            "generatorURL": "http://prometheus:9090/graph",
            "fingerprint": f"demo-{alert_name}-{int(time.time())}",
        }],
        "groupLabels": {"alertname": alert_name},
        "commonLabels": {"severity": severity},
        "commonAnnotations": {},
        "externalURL": "http://alertmanager:9093",
    }

    url = f"{SELF_HEALING_URL}/webhook"
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, method="POST",
                                headers={"Content-Type": "application/json"})

    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            result = json.loads(resp.read())
            print(f"  ✓ Alert injected: {result}")
            return True
    except urllib.error.URLError as e:
        print(f"  ✗ Failed to inject alert: {e}")
        print(f"    Is the self-healing service running at {SELF_HEALING_URL}?")
        return False


def run_docker_exec(container: str, command: str) -> bool:
    """Run a command inside a docker container."""
    cmd = ["docker", "compose", "-f", "docker-compose.demo.yml",
           "exec", "-T", container] + command.split()
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            print(f"  ✓ Executed on {container}: {command}")
            return True
        else:
            print(f"  ✗ Failed on {container}: {result.stderr.strip()}")
            return False
    except subprocess.TimeoutExpired:
        print(f"  ✗ Timed out on {container}: {command}")
        return False
    except FileNotFoundError:
        print("  ✗ docker compose not found. Is Docker installed?")
        return False


def scenario_high_cpu():
    """Simulate high CPU: run stress tool on target, then inject alert."""
    print("\n=== Scenario: High CPU Usage ===\n")
    print("Step 1: Generating CPU load on target host...")
    run_docker_exec(TARGET_CONTAINER, "stress-ng --cpu 2 --timeout 60s --quiet")

    print("\nStep 2: Injecting HighCPUUsage alert...")
    inject_alert(
        alert_name="HighCPUUsage",
        severity="critical",
        instance="web-server-01:9100",
        service_name="web-frontend",
        description="CPU usage is above 90% for 1 minute",
    )

    print("\nStep 3: Watching pipeline (check logs with: docker compose -f docker-compose.demo.yml logs -f self-healing)")
    print("         Expected: Pipeline matches 'high-cpu-web' rule → executes restart_service.yml")


def scenario_disk_full():
    """Simulate disk full: create large file on target, then inject alert."""
    print("\n=== Scenario: Disk Space Low ===\n")
    print("Step 1: Creating large temp file on target host...")
    run_docker_exec(TARGET_CONTAINER, "dd if=/dev/zero of=/tmp/fill_disk bs=1M count=100")

    print("\nStep 2: Injecting DiskSpaceCritical alert...")
    inject_alert(
        alert_name="DiskSpaceCritical",
        severity="warning",
        instance="web-server-01:9100",
        service_name="web-frontend",
        description="Disk usage is above 85% on /",
    )

    print("\nStep 3: Expected: Pipeline matches 'disk-full' rule → executes clear_disk.yml")


def scenario_service_down():
    """Simulate service down: stop the fake service, then inject alert."""
    print("\n=== Scenario: Service Down ===\n")
    print("Step 1: Stopping target application process...")
    run_docker_exec(TARGET_CONTAINER, "pkill -f fake_app || true")

    print("\nStep 2: Injecting ServiceDown alert...")
    inject_alert(
        alert_name="ServiceDown",
        severity="critical",
        instance="web-server-01:9100",
        service_name="web-frontend",
        description="Service has been unreachable for 30 seconds",
    )

    print("\nStep 3: Expected: Pipeline matches 'service-down' rule → executes restart_service.yml")


def scenario_inject(alert_name: str, severity: str):
    """Directly inject a custom alert."""
    print("\n=== Scenario: Manual Alert Injection ===\n")
    print(f"Injecting alert: {alert_name} (severity: {severity})")
    inject_alert(alert_name=alert_name, severity=severity)


def main():
    parser = argparse.ArgumentParser(description="Trigger AIOps demo scenarios")
    parser.add_argument("--scenario", required=True,
                        choices=["high-cpu", "disk-full", "service-down", "inject"],
                        help="Which scenario to trigger")
    parser.add_argument("--alert-name", default="TestAlert",
                        help="Alert name (for inject scenario)")
    parser.add_argument("--severity", default="warning",
                        help="Severity (for inject scenario)")
    args = parser.parse_args()

    print("╔══════════════════════════════════════════════════════════╗")
    print("║      AIOps Self-Healing Pipeline — Demo Trigger         ║")
    print("╚══════════════════════════════════════════════════════════╝")

    if args.scenario == "high-cpu":
        scenario_high_cpu()
    elif args.scenario == "disk-full":
        scenario_disk_full()
    elif args.scenario == "service-down":
        scenario_service_down()
    elif args.scenario == "inject":
        scenario_inject(args.alert_name, args.severity)

    print("\n--- Done. Monitor the pipeline with: ---")
    print("  docker compose -f docker-compose.demo.yml logs -f self-healing")
    print("  curl -s http://localhost:8080/metrics | grep remediation")


if __name__ == "__main__":
    main()
