#!/usr/bin/env python3
"""ECR Push and Scan Script.

Pushes a Docker image to Amazon ECR with immutable tagging, polls vulnerability
scan results, and fails the build on CRITICAL/HIGH findings or scan timeout.

Environment Variables:
    IMAGE_TAG: Required. The tag for the image (e.g., "abc1234-dev").
    ECR_REPOSITORY: Optional. ECR repository name (default: "aiops-self-healing").
    AWS_REGION: Optional. AWS region (default: "us-east-1").

Requirements: 1.5, 1.7, 1.8, 1.9
"""

import base64
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass

import boto3
from botocore.exceptions import ClientError


@dataclass
class EcrConfig:
    """Configuration for ECR push and scan operations."""

    image_tag: str
    repository: str
    region: str
    scan_poll_interval_seconds: int = 10
    scan_timeout_seconds: int = 300
    push_max_retries: int = 2
    push_retry_interval_seconds: int = 30


def get_config() -> EcrConfig:
    """Read configuration from environment variables."""
    image_tag = os.environ.get("IMAGE_TAG")
    if not image_tag:
        print("ERROR: IMAGE_TAG environment variable is required")
        sys.exit(1)

    repository = os.environ.get("ECR_REPOSITORY", "aiops-self-healing")
    region = os.environ.get("AWS_REGION", "us-east-1")

    return EcrConfig(
        image_tag=image_tag,
        repository=repository,
        region=region,
    )


def get_ecr_client(region: str):
    """Create a boto3 ECR client."""
    return boto3.client("ecr", region_name=region)


def ecr_login(ecr_client, region: str) -> str:
    """Login to ECR and return the registry URI.

    Uses get_authorization_token to obtain credentials, then runs
    docker login via subprocess.

    Returns:
        The ECR registry URI (e.g., "123456789012.dkr.ecr.us-east-1.amazonaws.com").
    """
    response = ecr_client.get_authorization_token()
    auth_data = response["authorizationData"][0]
    token = base64.b64decode(auth_data["authorizationToken"]).decode("utf-8")
    username, password = token.split(":")
    registry_uri = auth_data["proxyEndpoint"].replace("https://", "")

    result = subprocess.run(
        ["docker", "login", "--username", username, "--password-stdin", registry_uri],
        input=password,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"ERROR: Docker login failed: {result.stderr}")
        sys.exit(1)

    print(f"Successfully logged in to ECR registry: {registry_uri}")
    return registry_uri


def get_environment_from_tag(image_tag: str) -> str:
    """Extract the environment suffix from an image tag.

    Args:
        image_tag: Tag in format "{sha}-{environment}" (e.g., "abc1234-dev").

    Returns:
        The environment name (e.g., "dev").
    """
    parts = image_tag.rsplit("-", 1)
    if len(parts) == 2:
        return parts[1]
    return "dev"


def tag_and_push_image(
    config: EcrConfig, registry_uri: str
) -> str:
    """Tag the local image and push to ECR with immutable tag and latest-{env} tag.

    Retries push up to config.push_max_retries times with intervals on failure.

    Returns:
        The image digest on success.

    Raises:
        SystemExit: If all push retries are exhausted or tag immutability is violated.
    """
    env = get_environment_from_tag(config.image_tag)
    full_image_uri = f"{registry_uri}/{config.repository}"
    immutable_tag = f"{full_image_uri}:{config.image_tag}"
    latest_tag = f"{full_image_uri}:latest-{env}"

    # Tag local image with both tags
    local_image = "aiops:local"

    for tag in [immutable_tag, latest_tag]:
        result = subprocess.run(
            ["docker", "tag", local_image, tag],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(f"ERROR: Failed to tag image as {tag}: {result.stderr}")
            sys.exit(1)

    # Push with retries
    digest = None
    for tag in [immutable_tag, latest_tag]:
        digest = _push_with_retries(config, tag)

    return digest


def _push_with_retries(config: EcrConfig, image_ref: str) -> str:
    """Push a single image reference to ECR with retries.

    Args:
        config: ECR configuration with retry settings.
        image_ref: Full image reference to push (e.g., "registry/repo:tag").

    Returns:
        The image digest from the push output.

    Raises:
        SystemExit: If all retries fail or immutable tag conflict detected.
    """
    last_error = ""
    for attempt in range(config.push_max_retries + 1):
        if attempt > 0:
            print(
                f"Retrying push (attempt {attempt + 1}/{config.push_max_retries + 1}) "
                f"after {config.push_retry_interval_seconds}s..."
            )
            time.sleep(config.push_retry_interval_seconds)

        result = subprocess.run(
            ["docker", "push", image_ref],
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            print(f"Successfully pushed: {image_ref}")
            # Extract digest from output
            digest = _extract_digest(result.stdout)
            return digest

        last_error = result.stderr

        # Check for immutable tag violation (ImageTagAlreadyExistsException)
        if "tag already exists" in last_error.lower() or "ImageTagAlreadyExistsException" in last_error:
            print(
                f"ERROR: Image tag immutability violation - tag already exists in "
                f"ECR repository. Cannot overwrite immutable tag: {image_ref}"
            )
            sys.exit(1)

        print(f"Push attempt {attempt + 1} failed: {last_error}")

    print(
        f"ERROR: ECR push failed after {config.push_max_retries + 1} attempts. "
        f"Last error: {last_error}"
    )
    sys.exit(1)


def _extract_digest(push_output: str) -> str:
    """Extract the image digest from docker push output.

    Args:
        push_output: The stdout from docker push command.

    Returns:
        The digest string (e.g., "sha256:abc123...") or empty string if not found.
    """
    for line in push_output.splitlines():
        if "digest:" in line.lower():
            parts = line.split()
            for i, part in enumerate(parts):
                if part.lower() == "digest:" and i + 1 < len(parts):
                    return parts[i + 1]
                if part.startswith("sha256:"):
                    return part
    return ""


def poll_scan_results(ecr_client, config: EcrConfig) -> bool:
    """Poll ECR scan results until complete or timeout.

    Polls every config.scan_poll_interval_seconds for up to
    config.scan_timeout_seconds.

    Args:
        ecr_client: boto3 ECR client.
        config: ECR configuration.

    Returns:
        True if scan passed (no CRITICAL/HIGH findings), False otherwise.

    Raises:
        SystemExit: On scan timeout or CRITICAL/HIGH vulnerabilities found.
    """
    start_time = time.time()
    print(
        f"Polling ECR scan results for {config.repository}:{config.image_tag} "
        f"(timeout: {config.scan_timeout_seconds}s)..."
    )

    while True:
        elapsed = time.time() - start_time
        if elapsed >= config.scan_timeout_seconds:
            print(
                f"ERROR: ECR scan timed out after {config.scan_timeout_seconds} seconds. "
                f"Scan did not complete within the allowed time window."
            )
            sys.exit(1)

        try:
            response = ecr_client.describe_image_scan_findings(
                repositoryName=config.repository,
                imageId={"imageTag": config.image_tag},
            )
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code == "ScanNotFoundException":
                print("Scan not yet started, waiting...")
                time.sleep(config.scan_poll_interval_seconds)
                continue
            raise

        scan_status = response.get("imageScanStatus", {}).get("status", "")

        if scan_status == "COMPLETE":
            return _evaluate_scan_findings(response)
        elif scan_status == "FAILED":
            description = response.get("imageScanStatus", {}).get("description", "Unknown")
            print(f"ERROR: ECR scan failed: {description}")
            sys.exit(1)
        else:
            print(f"  Scan status: {scan_status} (elapsed: {int(elapsed)}s)")
            time.sleep(config.scan_poll_interval_seconds)


def _evaluate_scan_findings(scan_response: dict) -> bool:
    """Evaluate scan findings for CRITICAL or HIGH severity vulnerabilities.

    Args:
        scan_response: The response from describe_image_scan_findings.

    Returns:
        True if no CRITICAL/HIGH findings.

    Raises:
        SystemExit: If CRITICAL or HIGH vulnerabilities are found.
    """
    findings = scan_response.get("imageScanFindings", {}).get("findings", [])
    severity_counts = scan_response.get("imageScanFindings", {}).get(
        "findingSeverityCounts", {}
    )

    critical_count = severity_counts.get("CRITICAL", 0)
    high_count = severity_counts.get("HIGH", 0)

    if critical_count > 0 or high_count > 0:
        print(
            f"ERROR: ECR scan found {critical_count} CRITICAL and "
            f"{high_count} HIGH severity vulnerabilities:"
        )
        print("-" * 70)
        for finding in findings:
            severity = finding.get("severity", "UNKNOWN")
            if severity in ("CRITICAL", "HIGH"):
                name = finding.get("name", "Unknown")
                package_name = (
                    finding.get("attributes", [{}])[0].get("value", "Unknown")
                    if finding.get("attributes")
                    else "Unknown"
                )
                # Try to extract package info from attributes
                for attr in finding.get("attributes", []):
                    if attr.get("key") == "package_name":
                        package_name = attr.get("value", "Unknown")
                        break

                print(f"  [{severity}] {name} - Package: {package_name}")
        print("-" * 70)
        sys.exit(1)

    total_findings = len(findings)
    print(
        f"ECR scan complete: {total_findings} total findings, "
        f"0 CRITICAL, 0 HIGH. Scan passed."
    )
    return True


def write_artifact(image_tag: str, digest: str) -> None:
    """Write image-tag.json deployment artifact.

    Args:
        image_tag: The image tag that was pushed.
        digest: The image digest from ECR.
    """
    artifact = {
        "image_tag": image_tag,
        "digest": digest,
    }
    with open("image-tag.json", "w") as f:
        json.dump(artifact, f, indent=2)
    print("Wrote deployment artifact: image-tag.json")
    print(f"  image_tag: {image_tag}")
    print(f"  digest: {digest}")


def main():
    """Main entry point for ECR push and scan."""
    print("=" * 70)
    print("ECR Push and Scan")
    print("=" * 70)

    # Read configuration
    config = get_config()
    print(f"Repository: {config.repository}")
    print(f"Image Tag:  {config.image_tag}")
    print(f"Region:     {config.region}")
    print()

    # Create ECR client
    ecr_client = get_ecr_client(config.region)

    # Step 1: Login to ECR
    print("[1/4] Logging in to ECR...")
    registry_uri = ecr_login(ecr_client, config.region)
    print()

    # Step 2: Tag and push image
    print("[2/4] Tagging and pushing image to ECR...")
    digest = tag_and_push_image(config, registry_uri)
    print()

    # Step 3: Poll scan results
    print("[3/4] Polling ECR scan results...")
    poll_scan_results(ecr_client, config)
    print()

    # Step 4: Write artifact
    print("[4/4] Writing deployment artifact...")
    write_artifact(config.image_tag, digest)
    print()

    print("=" * 70)
    print("ECR Push and Scan completed successfully!")
    print("=" * 70)


if __name__ == "__main__":
    main()
