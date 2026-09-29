"""
Health Gate Checker for CD Pipeline.

Polls the /health endpoint after ComputeStack deployment to verify that
all dependencies are healthy before proceeding with ObservabilityStack deployment.

Environment variables:
    HEALTH_URL: The URL to poll (e.g., https://api.example.com/health)
    MAX_WAIT_SECONDS: Maximum wait time (default 300 = 5 minutes)
    POLL_INTERVAL_SECONDS: Polling interval (default 30 seconds)
    REQUIRED_CONSECUTIVE_PASSES: Consecutive healthy responses needed (default 3)
    ENVIRONMENT: Current environment name
    IMAGE_TAG: Current image tag being deployed

Requirements: 6.1, 6.6
"""

from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

try:
    import boto3
except ImportError:
    boto3 = None  # type: ignore[assignment]


@dataclass
class HealthGateChecker:
    """Polls the /health endpoint and publishes CloudWatch metrics on completion.

    The health gate PASSES if the endpoint returns HTTP 200 with both sqs and
    dynamodb reporting "healthy" for REQUIRED_CONSECUTIVE_PASSES consecutive polls.

    The health gate FAILS if the condition is not met within MAX_WAIT_SECONDS.
    """

    health_url: str
    max_wait_seconds: int = 300
    poll_interval_seconds: int = 30
    required_consecutive_passes: int = 3
    environment: str = "dev"
    image_tag: str = "unknown"

    # Internal state
    _consecutive_healthy: int = field(default=0, init=False, repr=False)
    _elapsed_seconds: float = field(default=0.0, init=False, repr=False)
    _passed: bool = field(default=False, init=False, repr=False)

    @classmethod
    def from_env(cls) -> "HealthGateChecker":
        """Create a HealthGateChecker from environment variables."""
        health_url = os.environ.get("HEALTH_URL", "")
        if not health_url:
            print("ERROR: HEALTH_URL environment variable is required.")
            sys.exit(1)

        return cls(
            health_url=health_url,
            max_wait_seconds=int(os.environ.get("MAX_WAIT_SECONDS", "300")),
            poll_interval_seconds=int(os.environ.get("POLL_INTERVAL_SECONDS", "30")),
            required_consecutive_passes=int(
                os.environ.get("REQUIRED_CONSECUTIVE_PASSES", "3")
            ),
            environment=os.environ.get("ENVIRONMENT", "dev"),
            image_tag=os.environ.get("IMAGE_TAG", "unknown"),
        )

    def _is_healthy(self, response_json: dict[str, Any]) -> bool:
        """Check if the health response indicates all dependencies are healthy.

        Expected response format:
            {"dependencies": {"sqs": "healthy", "dynamodb": "healthy"}}
        """
        dependencies = response_json.get("dependencies", {})
        sqs_status = dependencies.get("sqs", "unhealthy")
        dynamodb_status = dependencies.get("dynamodb", "unhealthy")
        return sqs_status == "healthy" and dynamodb_status == "healthy"

    def _poll_once(self, client: httpx.Client) -> bool:
        """Poll the health endpoint once. Returns True if healthy."""
        try:
            response = client.get(self.health_url, timeout=10.0)
            if response.status_code != 200:
                print(
                    f"  Health check returned HTTP {response.status_code} — unhealthy"
                )
                return False

            data = response.json()
            if self._is_healthy(data):
                print("  Health check returned HTTP 200 — all dependencies healthy")
                return True
            else:
                deps = data.get("dependencies", {})
                print(
                    f"  Health check returned HTTP 200 but dependencies unhealthy: "
                    f"sqs={deps.get('sqs', 'unknown')}, "
                    f"dynamodb={deps.get('dynamodb', 'unknown')}"
                )
                return False

        except httpx.TimeoutException:
            print("  Health check timed out after 10s")
            return False
        except httpx.RequestError as exc:
            print(f"  Health check request error: {exc}")
            return False
        except Exception as exc:
            print(f"  Health check unexpected error: {exc}")
            return False

    def run(self) -> bool:
        """Execute the health gate polling loop.

        Returns True if the gate passed, False if it timed out.
        """
        print("=" * 60)
        print("  HEALTH GATE CHECK")
        print("=" * 60)
        print(f"  URL:                    {self.health_url}")
        print(f"  Max wait:               {self.max_wait_seconds}s")
        print(f"  Poll interval:          {self.poll_interval_seconds}s")
        print(f"  Required consecutive:   {self.required_consecutive_passes}")
        print(f"  Environment:            {self.environment}")
        print(f"  Image tag:              {self.image_tag}")
        print("=" * 60)
        print()

        start_time = time.time()
        self._consecutive_healthy = 0
        self._passed = False

        with httpx.Client() as client:
            while True:
                elapsed = time.time() - start_time
                self._elapsed_seconds = elapsed

                if elapsed >= self.max_wait_seconds:
                    print(
                        f"\nTIMEOUT: Health gate failed after {elapsed:.0f}s "
                        f"({self._consecutive_healthy}/{self.required_consecutive_passes} "
                        f"consecutive healthy)"
                    )
                    self._passed = False
                    break

                remaining = self.max_wait_seconds - elapsed
                print(
                    f"[{elapsed:.0f}s elapsed, {remaining:.0f}s remaining] "
                    f"Polling health endpoint... "
                    f"(consecutive: {self._consecutive_healthy}/{self.required_consecutive_passes})"
                )

                healthy = self._poll_once(client)

                if healthy:
                    self._consecutive_healthy += 1
                    if self._consecutive_healthy >= self.required_consecutive_passes:
                        self._elapsed_seconds = time.time() - start_time
                        print(
                            f"\nSUCCESS: Health gate passed! "
                            f"{self.required_consecutive_passes} consecutive healthy "
                            f"responses in {self._elapsed_seconds:.0f}s"
                        )
                        self._passed = True
                        break
                else:
                    # Reset counter on any non-healthy response
                    if self._consecutive_healthy > 0:
                        print(
                            f"  Resetting consecutive counter "
                            f"(was {self._consecutive_healthy})"
                        )
                    self._consecutive_healthy = 0

                # Wait before next poll
                time.sleep(self.poll_interval_seconds)

        # Publish CloudWatch metrics
        self._publish_metrics()

        return self._passed

    def _publish_metrics(self) -> None:
        """Publish deployment health gate metrics to CloudWatch.

        Metrics published:
            - DeploymentHealthGatePassed: 1 for pass, 0 for fail
            - DeploymentHealthGateDuration: total seconds elapsed
        Both tagged with Environment and ImageTag dimensions.
        """
        if boto3 is None:
            print(
                "WARNING: boto3 not available — skipping CloudWatch metric publishing."
            )
            return

        try:
            cw_client = boto3.client("cloudwatch")

            dimensions = [
                {"Name": "Environment", "Value": self.environment},
                {"Name": "ImageTag", "Value": self.image_tag},
            ]

            metric_data = [
                {
                    "MetricName": "DeploymentHealthGatePassed",
                    "Dimensions": dimensions,
                    "Value": 1.0 if self._passed else 0.0,
                    "Unit": "Count",
                },
                {
                    "MetricName": "DeploymentHealthGateDuration",
                    "Dimensions": dimensions,
                    "Value": self._elapsed_seconds,
                    "Unit": "Seconds",
                },
            ]

            cw_client.put_metric_data(
                Namespace=f"AIOps/{self.environment}",
                MetricData=metric_data,
            )

            print(
                f"\nPublished CloudWatch metrics: "
                f"DeploymentHealthGatePassed={'1' if self._passed else '0'}, "
                f"DeploymentHealthGateDuration={self._elapsed_seconds:.0f}s"
            )

        except Exception as exc:
            print(f"WARNING: Failed to publish CloudWatch metrics: {exc}")


def main() -> None:
    """Entry point for the health gate script."""
    checker = HealthGateChecker.from_env()
    passed = checker.run()

    if passed:
        print("\nHealth gate PASSED — proceeding with deployment.")
        sys.exit(0)
    else:
        print("\nHealth gate FAILED — deployment will be rolled back.")
        sys.exit(1)


if __name__ == "__main__":
    main()
