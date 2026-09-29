"""Destroy the AIOps Self-Healing Infrastructure from AWS.

Removes all CDK stacks and optionally cleans up ECR images.

Usage:
    python destroy.py                       # Destroy dev environment
    python destroy.py --environment staging
    python destroy.py --environment prod    # Requires double confirmation
    python destroy.py --include-ecr         # Also delete ECR repository and images
"""

import argparse
import json
import os
import subprocess
import sys
import time


# ============================================================================
# Configuration — read from cdk.json
# ============================================================================
import json as _json
_cdk_config = _json.load(open(os.path.join(os.path.dirname(__file__), "cdk.json")))["context"]
AWS_ACCOUNT = _cdk_config["awsAccount"]
AWS_REGION = _cdk_config["awsRegion"]
ECR_REPO = "aiops"
ENVIRONMENTS = ["dev", "staging", "prod"]


def run(cmd: str, check: bool = True, capture: bool = False) -> subprocess.CompletedProcess:
    """Run a shell command."""
    print(f"\n  $ {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=capture, text=True)
    if check and result.returncode != 0:
        if capture:
            print(f"  STDERR: {result.stderr}")
        print(f"\n  ERROR: Command failed with exit code {result.returncode}")
        sys.exit(1)
    return result


# ============================================================================
# Steps
# ============================================================================

def confirm_destroy(environment: str) -> bool:
    """Get user confirmation before destroying resources."""
    print("\n" + "=" * 60)
    print(f"  WARNING: You are about to DESTROY all resources in '{environment}'")
    print("=" * 60)
    print(f"""
  This will permanently delete:
    - ECS Cluster and service (aiops-cluster-{environment})
    - DynamoDB table (AiopsIncidentMemory-{environment}) 
    - SQS queues (aiops-main-{environment}, aiops-dlq-{environment})
    - VPC, subnets, NAT Gateway
    - CloudWatch alarms, dashboard, log groups
    - AMP workspace
    - IAM roles and policies
    - All SSM parameters under /aiops/{environment}/
""")

    if environment == "prod":
        print("  ⚠️  THIS IS THE PRODUCTION ENVIRONMENT!")
        print(f"  Type the environment name to confirm: ", end="")
        confirm = input()
        if confirm != "prod":
            print("  Aborted.")
            return False
        print(f"  Type 'DESTROY' to double-confirm: ", end="")
        confirm2 = input()
        if confirm2 != "DESTROY":
            print("  Aborted.")
            return False
    else:
        print(f"  Are you sure? (y/n): ", end="")
        confirm = input()
        if confirm.lower() != "y":
            print("  Aborted.")
            return False

    return True


def destroy_stacks(environment: str):
    """Destroy all CDK stacks for the environment."""
    print("\n" + "=" * 60)
    print(f"  Destroying CDK stacks (environment: {environment})")
    print("=" * 60)

    context_args = f"--context environment={environment}"

    # Destroy in reverse dependency order
    stacks = [
        f"Aiops-{environment}-Monitoring",
        f"Aiops-{environment}-Observability",
        f"Aiops-{environment}-Compute",
        f"Aiops-{environment}-Data",
        f"Aiops-{environment}-Network",
    ]

    for stack in stacks:
        print(f"\n  Destroying {stack}...")
        result = run(
            f"npx aws-cdk@2 destroy {stack} --force {context_args}",
            check=False,
        )
        if result.returncode != 0:
            print(f"  [WARN] Failed to destroy {stack} — may not exist")

    print("\n  [OK] All stacks destroyed")


def cleanup_ecr():
    """Delete all images from ECR repository and the repository itself."""
    print("\n" + "=" * 60)
    print("  Cleaning up ECR repository")
    print("=" * 60)

    # List images
    result = subprocess.run(
        f"aws ecr list-images --repository-name {ECR_REPO} --region {AWS_REGION}",
        shell=True, capture_output=True, text=True,
    )

    if result.returncode != 0:
        print(f"  [INFO] ECR repository '{ECR_REPO}' not found — nothing to clean")
        return

    images = json.loads(result.stdout).get("imageIds", [])
    if images:
        print(f"  Deleting {len(images)} images from ECR...")
        # Batch delete in groups of 100
        for i in range(0, len(images), 100):
            batch = images[i:i+100]
            image_ids = " ".join(
                f"imageDigest={img['imageDigest']}" if "imageDigest" in img
                else f"imageTag={img['imageTag']}"
                for img in batch
            )
            run(
                f"aws ecr batch-delete-image --repository-name {ECR_REPO} "
                f"--image-ids {image_ids} --region {AWS_REGION}",
                check=False,
            )

    # Delete repository
    print(f"  Deleting ECR repository: {ECR_REPO}")
    run(
        f"aws ecr delete-repository --repository-name {ECR_REPO} "
        f"--force --region {AWS_REGION}",
        check=False,
    )
    print("  [OK] ECR repository deleted")


def cleanup_log_groups(environment: str):
    """Delete CloudWatch log groups created by the stacks."""
    print("\n  Cleaning up residual log groups...")
    log_groups = [
        f"/aiops/{environment}/ecs",
        f"/aiops/{environment}/monitoring",
        f"/aiops/{environment}/canary",
    ]
    for lg in log_groups:
        subprocess.run(
            f"aws logs delete-log-group --log-group-name {lg} --region {AWS_REGION}",
            shell=True, capture_output=True,
        )
    print("  [OK] Log groups cleaned")


def print_summary(environment: str, include_ecr: bool):
    """Print post-destroy summary."""
    print("\n" + "=" * 60)
    print("  DESTROY COMPLETE")
    print("=" * 60)
    print(f"""
  Environment: {environment}
  ECR cleaned: {'Yes' if include_ecr else 'No (use --include-ecr to remove)'}
  
  All AWS resources for '{environment}' have been removed.
  
  Note: The following may still exist:
    - CDK bootstrap stack (CDKToolkit) — shared across envs
    - SES verified email identity — harmless, no cost
    - S3 CDK staging bucket — shared across envs
    
  To remove CDK bootstrap (only if no other CDK apps use it):
    npx aws-cdk@2 destroy --app 'echo' --force CDKToolkit
""")


# ============================================================================
# Main
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="Destroy AIOps from AWS")
    parser.add_argument("--environment", default="dev", choices=ENVIRONMENTS)
    parser.add_argument("--include-ecr", action="store_true",
                        help="Also delete ECR repository and all images")
    parser.add_argument("--yes", "-y", action="store_true",
                        help="Skip confirmation prompt (except for prod)")
    args = parser.parse_args()

    print("╔══════════════════════════════════════════════════════════════╗")
    print("║   AIOps Self-Healing Infrastructure — DESTROY               ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print(f"  Target: {args.environment} | Account: {AWS_ACCOUNT} | Region: {AWS_REGION}")

    # Confirmation
    if not args.yes or args.environment == "prod":
        if not confirm_destroy(args.environment):
            return

    # Destroy stacks
    destroy_stacks(args.environment)

    # Cleanup ECR if requested
    if args.include_ecr:
        cleanup_ecr()

    # Cleanup residual log groups
    cleanup_log_groups(args.environment)

    # Summary
    print_summary(args.environment, args.include_ecr)


if __name__ == "__main__":
    main()
