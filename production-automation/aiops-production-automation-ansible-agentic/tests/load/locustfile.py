"""Load testing configuration for the AIOps self-healing infrastructure.

Run with:
    locust -f tests/load/locustfile.py --host http://localhost:8080

Capacity planning thresholds:
    - Webhook endpoint: 60 requests/minute per source IP (rate limited)
    - Pipeline concurrency: max 50 simultaneous pipelines
    - Target: < 2s response time at p95 under sustained load
    - Auto-scaling triggers: SQS depth > 10 → +2 tasks, > 50 → +4 tasks
"""

import random
import uuid
from datetime import datetime, timezone

from locust import HttpUser, between, task


def generate_alert_payload(num_alerts: int = 1) -> dict:
    """Generate a realistic Alertmanager webhook payload."""
    alert_names = [
        "HighCPUUsage", "HighMemoryUsage", "DiskSpaceLow",
        "ServiceDown", "HighLatency", "ErrorRateHigh",
        "ConnectionPoolExhausted", "SSLCertExpiring",
    ]
    severities = ["critical", "warning", "info"]
    services = ["web-frontend", "api-server", "worker", "cache", "database"]
    hosts = [f"host-{i:03d}" for i in range(1, 21)]

    alerts = []
    for _ in range(num_alerts):
        alert_name = random.choice(alert_names)
        alerts.append({
            "status": "firing",
            "labels": {
                "alertname": alert_name,
                "severity": random.choice(severities),
                "instance": f"{random.choice(hosts)}:9090",
                "job": "node-exporter",
                "service_name": random.choice(services),
            },
            "annotations": {
                "summary": f"{alert_name} triggered",
                "description": f"Automated load test alert {uuid.uuid4().hex[:8]}",
            },
            "startsAt": datetime.now(timezone.utc).isoformat(),
            "endsAt": "0001-01-01T00:00:00Z",
            "generatorURL": "http://prometheus:9090/graph",
            "fingerprint": uuid.uuid4().hex[:12],
        })

    return {
        "version": "4",
        "groupKey": f"load-test-{uuid.uuid4().hex[:8]}",
        "status": "firing",
        "receiver": "self-healing",
        "alerts": alerts,
        "groupLabels": {"alertname": alerts[0]["labels"]["alertname"]},
        "commonLabels": {},
        "commonAnnotations": {},
        "externalURL": "http://alertmanager:9093",
    }


class WebhookUser(HttpUser):
    """Simulates Alertmanager sending webhook requests."""

    wait_time = between(0.5, 2.0)

    @task(weight=10)
    def post_single_alert(self):
        """Send a single alert payload."""
        payload = generate_alert_payload(num_alerts=1)
        self.client.post(
            "/webhook",
            json=payload,
            headers={"Content-Type": "application/json"},
        )

    @task(weight=3)
    def post_grouped_alerts(self):
        """Send a grouped alert payload (3-5 alerts)."""
        num = random.randint(3, 5)
        payload = generate_alert_payload(num_alerts=num)
        self.client.post(
            "/webhook",
            json=payload,
            headers={"Content-Type": "application/json"},
        )

    @task(weight=5)
    def health_check(self):
        """Hit the health endpoint."""
        self.client.get("/health")

    @task(weight=2)
    def metrics_check(self):
        """Hit the metrics endpoint."""
        self.client.get("/metrics")


class BurstUser(HttpUser):
    """Simulates a burst of alerts (e.g., cascading failure)."""

    wait_time = between(0.1, 0.3)

    @task
    def post_burst(self):
        """Send rapid-fire alerts simulating a cascading failure."""
        payload = generate_alert_payload(num_alerts=random.randint(5, 15))
        self.client.post(
            "/webhook",
            json=payload,
            headers={"Content-Type": "application/json"},
        )
