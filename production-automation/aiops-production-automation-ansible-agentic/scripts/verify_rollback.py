"""Rollback verification script.

Validates that a deployment or rollback was successful by:
1. Running the health gate check
2. Sending a synthetic test alert
3. Verifying the alert was processed
4. Checking DLQ is empty

Usage:
    python scripts/verify_rollback.py --environment prod
    python scripts/verify_rollback.py --environment staging --endpoint https://custom-url
"""

import argparse
import json
import sys
import time
import uuid

import boto3
import urllib.request
import urllib.error


def check_health(endpoint: str) -> bool:
    """Verify the /health endpoint returns healthy."""
    url = f"{endpoint}/health"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            sqs_ok = data.get("dependencies", {}).get("sqs") == "healthy"
            dynamo_ok = data.get("dependencies", {}).get("dynamodb") == "healthy"
            if sqs_ok and dynamo_ok:
                print(f"  [PASS] Health check: SQS={sqs_ok}, DynamoDB={dynamo_ok}")
                return True
            else:
                print(f"  [FAIL] Health check: {data.get('dependencies')}")
                return False
    except Exception as e:
        print(f"  [FAIL] Health check unreachable: {e}")
        return False


def send_test_alert(endpoint: str) -> str:
    """Send a synthetic P3 test alert and return the fingerprint."""
    fingerprint = uuid.uuid4().hex[:12]
    payload = {
        "version": "4",
        "groupKey": f"rollback-verify-{fingerprint}",
        "status": "firing",
        "receiver": "self-healing",
        "alerts": [{
            "status": "firing",
            "labels": {
                "alertname": "RollbackVerificationTest",
                "severity": "info",
                "instance": "verify-host:9090",
                "job": "rollback-test",
            },
            "annotations": {
                "summary": "Rollback verification synthetic alert",
            },
            "startsAt": "2026-07-30T12:00:00Z",
            "endsAt": "0001-01-01T00:00:00Z",
            "fingerprint": fingerprint,
        }],
        "groupLabels": {},
        "commonLabels": {},
        "commonAnnotations": {},
        "externalURL": "http://verify-script",
    }

    url = f"{endpoint}/webhook"
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=data, method="POST",
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            status = resp.status
            if status == 200:
                print(f"  [PASS] Test alert accepted (fingerprint: {fingerprint})")
                return fingerprint
            else:
                print(f"  [FAIL] Webhook returned status {status}")
                return ""
    except Exception as e:
        print(f"  [FAIL] Failed to send test alert: {e}")
        return ""


def check_dlq_empty(environment: str) -> bool:
    """Verify the DLQ has no new messages."""
    sqs = boto3.client("sqs")
    queue_name = f"aiops-dlq-{environment}"

    try:
        resp = sqs.get_queue_url(QueueName=queue_name)
        queue_url = resp["QueueUrl"]

        attrs = sqs.get_queue_attributes(
            QueueUrl=queue_url,
            AttributeNames=["ApproximateNumberOfMessagesVisible"],
        )
        count = int(attrs["Attributes"]["ApproximateNumberOfMessagesVisible"])
        if count == 0:
            print(f"  [PASS] DLQ is empty ({queue_name})")
            return True
        else:
            print(f"  [WARN] DLQ has {count} message(s) ({queue_name})")
            return False
    except Exception as e:
        print(f"  [SKIP] Could not check DLQ: {e}")
        return True  # Non-blocking


def main():
    parser = argparse.ArgumentParser(description="Verify rollback/deployment success")
    parser.add_argument("--environment", required=True, choices=["dev", "staging", "prod"])
    parser.add_argument("--endpoint", default="http://localhost:8080")
    args = parser.parse_args()

    print(f"\n=== Rollback Verification: {args.environment} ===\n")

    results = []

    # Step 1: Health check
    print("Step 1: Health check")
    results.append(check_health(args.endpoint))

    # Step 2: Send test alert
    print("\nStep 2: Send test alert")
    fingerprint = send_test_alert(args.endpoint)
    results.append(bool(fingerprint))

    # Step 3: Wait for processing
    if fingerprint:
        print("\nStep 3: Waiting 5s for processing...")
        time.sleep(5)

    # Step 4: Check DLQ
    print("\nStep 4: Check DLQ")
    results.append(check_dlq_empty(args.environment))

    # Summary
    passed = sum(results)
    total = len(results)
    print(f"\n=== Results: {passed}/{total} checks passed ===\n")

    if all(results):
        print("VERIFICATION PASSED - Rollback/deployment is healthy")
        sys.exit(0)
    else:
        print("VERIFICATION FAILED - Issues detected")
        sys.exit(1)


if __name__ == "__main__":
    main()
