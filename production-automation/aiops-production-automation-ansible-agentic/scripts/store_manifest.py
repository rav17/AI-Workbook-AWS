"""Store a new deployment manifest in SSM Parameter Store with sliding-window rotation.

Stores the new manifest as n=1, rotates existing manifests 1→2, 2→3, etc.,
capping at a maximum of 5 manifests per environment.

Manifest path: /aiops/{environment}/deployment-history/{n}

Environment variables:
    ENVIRONMENT: Target environment (dev, staging, prod)
    IMAGE_TAG: Docker image tag for this deployment
    COMMIT_SHA: Git commit SHA (optional, defaults to 'unknown')
    CDK_STACK_VERSIONS: JSON string of CDK stack versions (optional, defaults to '{}')
    HEALTH_GATE_RESULT: Health gate result - 'passed' or 'failed' (optional, defaults to 'passed')
"""

import json
import os
import sys
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

MAX_MANIFESTS = 5
SSM_PATH_PREFIX = "/aiops/{environment}/deployment-history/{n}"


def build_manifest(
    image_tag: str,
    commit_sha: str,
    cdk_stack_versions: str,
    health_gate_result: str,
) -> dict:
    """Build a deployment manifest dictionary.

    Each Deployment_Manifest contains:
    - Image_Tag
    - commit SHA
    - CDK stack versions (CloudFormation change set IDs)
    - deployment timestamp
    - Health_Gate result
    """
    return {
        "image_tag": image_tag,
        "commit_sha": commit_sha,
        "cdk_stack_versions": json.loads(cdk_stack_versions) if cdk_stack_versions else {},
        "deployment_timestamp": datetime.now(timezone.utc).isoformat(),
        "health_gate_result": health_gate_result,
    }


def get_parameter_name(environment: str, n: int) -> str:
    """Get the SSM parameter name for a given environment and manifest slot."""
    return f"/aiops/{environment}/deployment-history/{n}"


def get_existing_manifest(ssm_client, environment: str, n: int) -> str | None:
    """Retrieve an existing manifest from SSM Parameter Store.

    Returns the manifest JSON string or None if not found.
    """
    param_name = get_parameter_name(environment, n)
    try:
        response = ssm_client.get_parameter(Name=param_name)
        return response["Parameter"]["Value"]
    except ClientError as e:
        if e.response["Error"]["Code"] == "ParameterNotFound":
            return None
        raise


def rotate_manifests(ssm_client, environment: str) -> None:
    """Rotate existing manifests: move n→n+1, starting from the highest slot.

    Manifests beyond MAX_MANIFESTS are discarded (the oldest one at n=5 is
    overwritten by n=4, effectively dropping the oldest).
    """
    # Rotate from highest to lowest to avoid overwriting
    for n in range(MAX_MANIFESTS - 1, 0, -1):
        manifest_value = get_existing_manifest(ssm_client, environment, n)
        if manifest_value is not None:
            # Move manifest at slot n to slot n+1
            target_name = get_parameter_name(environment, n + 1)
            ssm_client.put_parameter(
                Name=target_name,
                Value=manifest_value,
                Type="String",
                Overwrite=True,
            )


def store_manifest(ssm_client, environment: str, manifest: dict) -> None:
    """Store a new manifest at slot n=1 after rotating existing manifests."""
    # First, rotate existing manifests
    rotate_manifests(ssm_client, environment)

    # Store new manifest at n=1
    param_name = get_parameter_name(environment, 1)
    manifest_json = json.dumps(manifest)
    ssm_client.put_parameter(
        Name=param_name,
        Value=manifest_json,
        Type="String",
        Overwrite=True,
    )
    print(f"Stored deployment manifest at {param_name}")
    print(f"Manifest: {manifest_json}")


def main() -> None:
    """Main entry point for storing a deployment manifest."""
    environment = os.environ.get("ENVIRONMENT", "")
    if not environment:
        print("ERROR: ENVIRONMENT environment variable is required", file=sys.stderr)
        sys.exit(1)

    if environment not in {"dev", "staging", "prod"}:
        print(
            f"ERROR: ENVIRONMENT must be one of dev, staging, prod. Got: '{environment}'",
            file=sys.stderr,
        )
        sys.exit(1)

    image_tag = os.environ.get("IMAGE_TAG", "")
    if not image_tag:
        print("ERROR: IMAGE_TAG environment variable is required", file=sys.stderr)
        sys.exit(1)

    commit_sha = os.environ.get("COMMIT_SHA", "unknown")
    cdk_stack_versions = os.environ.get("CDK_STACK_VERSIONS", "{}")
    health_gate_result = os.environ.get("HEALTH_GATE_RESULT", "passed")

    manifest = build_manifest(
        image_tag=image_tag,
        commit_sha=commit_sha,
        cdk_stack_versions=cdk_stack_versions,
        health_gate_result=health_gate_result,
    )

    ssm_client = boto3.client("ssm")
    store_manifest(ssm_client, environment, manifest)
    print("Deployment manifest stored successfully.")


if __name__ == "__main__":
    main()
