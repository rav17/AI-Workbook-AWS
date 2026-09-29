"""Retrieve a deployment manifest from SSM Parameter Store for rollback.

Provides get_manifest(env, n) to retrieve a specific manifest slot.
Exits with code 1 if the manifest is not found.

Manifest path: /aiops/{environment}/deployment-history/{n}

Usage:
    python scripts/rollback_trigger.py [--environment ENV] [--manifest-slot N]

Environment variables (fallback if CLI args not provided):
    ENVIRONMENT: Target environment (dev, staging, prod)
    MANIFEST_SLOT: Manifest slot number (1-5, default 1)
"""

import argparse
import json
import os
import sys

import boto3
from botocore.exceptions import ClientError


def get_parameter_name(environment: str, n: int) -> str:
    """Get the SSM parameter name for a given environment and manifest slot."""
    return f"/aiops/{environment}/deployment-history/{n}"


def get_manifest(environment: str, n: int, ssm_client=None) -> dict | None:
    """Retrieve a deployment manifest from SSM Parameter Store.

    Args:
        environment: Target environment (dev, staging, prod).
        n: Manifest slot number (1 = most recent, up to 5 = oldest).
        ssm_client: Optional boto3 SSM client (created if not provided).

    Returns:
        Parsed manifest dictionary, or None if not found.
    """
    if ssm_client is None:
        ssm_client = boto3.client("ssm")

    param_name = get_parameter_name(environment, n)
    try:
        response = ssm_client.get_parameter(Name=param_name)
        manifest_json = response["Parameter"]["Value"]
        return json.loads(manifest_json)
    except ClientError as e:
        if e.response["Error"]["Code"] == "ParameterNotFound":
            return None
        raise


def main() -> None:
    """Main entry point for retrieving a deployment manifest."""
    parser = argparse.ArgumentParser(
        description="Retrieve a deployment manifest from SSM Parameter Store"
    )
    parser.add_argument(
        "--environment",
        default=os.environ.get("ENVIRONMENT", ""),
        help="Target environment (dev, staging, prod)",
    )
    parser.add_argument(
        "--manifest-slot",
        type=int,
        default=int(os.environ.get("MANIFEST_SLOT", "1")),
        help="Manifest slot number (1-5, default 1 = most recent)",
    )
    args = parser.parse_args()

    environment = args.environment
    manifest_slot = args.manifest_slot

    if not environment:
        print("ERROR: Environment is required (--environment or ENVIRONMENT env var)", file=sys.stderr)
        sys.exit(1)

    if environment not in {"dev", "staging", "prod"}:
        print(
            f"ERROR: Environment must be one of dev, staging, prod. Got: '{environment}'",
            file=sys.stderr,
        )
        sys.exit(1)

    if manifest_slot < 1 or manifest_slot > 5:
        print(
            f"ERROR: Manifest slot must be between 1 and 5. Got: {manifest_slot}",
            file=sys.stderr,
        )
        sys.exit(1)

    manifest = get_manifest(environment, manifest_slot)

    if manifest is None:
        param_name = get_parameter_name(environment, manifest_slot)
        print(
            f"ERROR: Manifest not found at {param_name}",
            file=sys.stderr,
        )
        sys.exit(1)

    # Output the manifest as formatted JSON
    print(json.dumps(manifest, indent=2))
    print(
        f"\nManifest retrieved successfully from slot {manifest_slot} for environment '{environment}'",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
