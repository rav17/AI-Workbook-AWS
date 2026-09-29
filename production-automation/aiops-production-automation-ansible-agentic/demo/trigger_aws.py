"""Send a test alert to the deployed AWS service via SQS.

Since the ECS service is in a private subnet, we send alerts
through the SQS queue (the same path Alertmanager would use in production).

Usage:
    python demo/trigger_aws.py
    python demo/trigger_aws.py --alert-name ServiceDown --severity critical
"""

import argparse
import json
import time
import uuid

import boto3


QUEUE_URL = ""  # Resolved dynamically from CloudFormation
REGION = "us-east-1"
# API Gateway endpoint (set after deployment)
API_ENDPOINT = ""  # Will be filled from CloudFormation output


def _get_queue_url() -> str:
    """Get SQS queue URL from CloudFormation stack outputs."""
    cf = boto3.client("cloudformation", region_name=REGION)
    try:
        resp = cf.describe_stacks(StackName="Aiops-dev-Data")
        for output in resp["Stacks"][0].get("Outputs", []):
            if output["OutputKey"] == "QueueUrl":
                return output["OutputValue"]
    except Exception:
        pass
    # Fallback to convention-based URL
    sts = boto3.client("sts")
    account = sts.get_caller_identity()["Account"]
    return f"https://sqs.{REGION}.amazonaws.com/{account}/aiops-main-dev"


def send_alert(alert_name: str, severity: str, instance: str, service_name: str):
    """Send a test Alertmanager payload to the SQS queue."""
    sqs = boto3.client("sqs", region_name=REGION)

    payload = {
        "version": "4",
        "groupKey": f"demo-{uuid.uuid4().hex[:8]}",
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
                "description": f"Demo alert triggered at {time.strftime('%Y-%m-%d %H:%M:%S UTC')}",
            },
            "startsAt": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "endsAt": "0001-01-01T00:00:00Z",
            "generatorURL": "http://demo/trigger_aws.py",
            "fingerprint": uuid.uuid4().hex[:12],
        }],
        "groupLabels": {"alertname": alert_name},
        "commonLabels": {"severity": severity},
        "commonAnnotations": {},
        "externalURL": "http://demo-script",
    }

    response = sqs.send_message(
        QueueUrl=_get_queue_url(),
        MessageBody=json.dumps(payload),
    )

    msg_id = response["MessageId"]
    print(f"\n  ✓ Alert sent to SQS!")
    print(f"    Message ID: {msg_id}")
    print(f"    Alert: {alert_name} ({severity})")
    print(f"    Instance: {instance}")
    print(f"    Service: {service_name}")
    print(f"\n  Check logs: aws logs tail /aiops/dev/ecs --region us-east-1 --since 1m")


def main():
    parser = argparse.ArgumentParser(description="Send test alert to AWS via SQS")
    parser.add_argument("--alert-name", default="HighCPUUsage")
    parser.add_argument("--severity", default="critical")
    parser.add_argument("--instance", default="web-server-01:9090")
    parser.add_argument("--service-name", default="web-frontend")
    args = parser.parse_args()

    print("╔══════════════════════════════════════════════════╗")
    print("║   AIOps Demo — Send Alert to AWS (via SQS)      ║")
    print("╚══════════════════════════════════════════════════╝")

    send_alert(args.alert_name, args.severity, args.instance, args.service_name)


if __name__ == "__main__":
    main()
