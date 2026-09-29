"""Deploy the AIOps Self-Healing Infrastructure to AWS.

This script handles the full deployment lifecycle:
1. Checks prerequisites (AWS CLI, CDK, Python deps, credentials)
2. Bootstraps CDK (if needed)
3. Verifies SES email identity
4. Builds and pushes Docker image to ECR
5. Deploys all CDK stacks in order
6. Runs post-deployment health checks
7. Prints demo instructions

Usage:
    python deploy.py                    # Deploy dev environment
    python deploy.py --environment staging
    python deploy.py --environment prod
    python deploy.py --skip-docker      # Skip Docker build (use existing image)
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
    """Run a shell command and print it."""
    print(f"\n  $ {cmd}")
    result = subprocess.run(
        cmd, shell=True, capture_output=capture, text=True,
    )
    if check and result.returncode != 0:
        if capture:
            print(f"  STDERR: {result.stderr}")
        print(f"\n  ERROR: Command failed with exit code {result.returncode}")
        sys.exit(1)
    return result


def check_tool(name: str, cmd: str) -> bool:
    """Check if a tool is available."""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode == 0:
        version = result.stdout.strip().split("\n")[0]
        print(f"  [OK] {name}: {version}")
        return True
    else:
        print(f"  [MISSING] {name}")
        return False


def _has_tool(name: str) -> bool:
    """Check if a tool exists in PATH (no output)."""
    return subprocess.run(f"where {name}", shell=True, capture_output=True).returncode == 0


# ============================================================================
# Steps
# ============================================================================

def step_check_prerequisites():
    """Verify all required tools and credentials are available."""
    print("\n" + "=" * 60)
    print("  STEP 1: Checking prerequisites")
    print("=" * 60)

    tools_ok = True
    tools_ok &= check_tool("AWS CLI", "aws --version")
    tools_ok &= check_tool("CDK", "npx aws-cdk@2 --version")
    tools_ok &= check_tool("Python", "python --version")
    # Check for docker or podman
    has_docker = check_tool("Docker", "docker --version")
    has_podman = check_tool("Podman", "podman --version")
    if not has_docker and not has_podman:
        # Try full path for Podman on Windows
        has_podman = check_tool("Podman (full path)",
            r'"C:\Users\RavindraYadav\AppData\Local\Programs\Podman\podman.exe" --version')
    tools_ok &= (has_docker or has_podman)
    tools_ok &= check_tool("pip", "pip --version")

    if not tools_ok:
        print("\n  ERROR: Missing required tools. Install them and retry.")
        sys.exit(1)

    # Check AWS credentials
    print("\n  Checking AWS credentials...")
    result = subprocess.run(
        "aws sts get-caller-identity", shell=True, capture_output=True, text=True
    )
    if result.returncode != 0:
        print("  ERROR: AWS credentials not configured.")
        print("  Run: aws configure  OR  aws sso login")
        sys.exit(1)

    identity = json.loads(result.stdout)
    print(f"  [OK] AWS Account: {identity['Account']}")
    print(f"  [OK] AWS ARN: {identity['Arn']}")

    if identity["Account"] != AWS_ACCOUNT:
        print(f"\n  WARNING: Expected account {AWS_ACCOUNT}, got {identity['Account']}")
        resp = input("  Continue anyway? (y/n): ")
        if resp.lower() != "y":
            sys.exit(0)


def step_install_dependencies():
    """Install Python dependencies."""
    print("\n" + "=" * 60)
    print("  STEP 2: Installing dependencies")
    print("=" * 60)
    run("pip install -e \".[cdk]\" --quiet")


def step_bootstrap_cdk(environment: str):
    """Bootstrap CDK in the target account/region."""
    print("\n" + "=" * 60)
    print("  STEP 3: Bootstrapping CDK")
    print("=" * 60)
    run(f"npx aws-cdk@2 bootstrap aws://{AWS_ACCOUNT}/{AWS_REGION}")


def step_verify_ses_email():
    """Verify SES email identity for sending notifications."""
    print("\n" + "=" * 60)
    print("  STEP 4: Verifying SES email identity")
    print("=" * 60)

    email = _cdk_config.get("costCenterEmail", "ravindya@in.ibm.com")

    # Check if already verified
    result = run(
        f"aws ses get-identity-verification-attributes "
        f"--identities {email} --region {AWS_REGION}",
        capture=True,
    )
    attrs = json.loads(result.stdout)
    status = attrs.get("VerificationAttributes", {}).get(email, {}).get("VerificationStatus")

    if status == "Success":
        print(f"  [OK] {email} is already verified in SES")
    else:
        print(f"  Sending verification email to {email}...")
        run(f"aws ses verify-email-identity --email-address {email} --region {AWS_REGION}")
        print(f"  [ACTION REQUIRED] Check your inbox and click the verification link.")
        print(f"  Waiting 30 seconds for verification...")
        time.sleep(30)

        # Re-check
        result = run(
            f"aws ses get-identity-verification-attributes "
            f"--identities {email} --region {AWS_REGION}",
            capture=True,
        )
        attrs = json.loads(result.stdout)
        status = attrs.get("VerificationAttributes", {}).get(email, {}).get("VerificationStatus")
        if status != "Success":
            print(f"  WARNING: Email not yet verified (status: {status})")
            print(f"  Deployment will continue but emails won't send until verified.")


def step_create_ecr_and_push_image(environment: str, skip_docker: bool):
    """Create ECR repository and push the Docker image."""
    print("\n" + "=" * 60)
    print("  STEP 5: Building and pushing Docker image")
    print("=" * 60)

    if skip_docker:
        print("  Skipping Docker build (--skip-docker flag set)")
        return "latest-dev"

    # Determine container runtime
    container_cmd = "docker"
    if not _has_tool("docker"):
        podman_path = r"C:\Users\RavindraYadav\AppData\Local\Programs\Podman\podman.exe"
        if os.path.isfile(podman_path):
            container_cmd = f'"{podman_path}"'
        elif _has_tool("podman"):
            container_cmd = "podman"
        else:
            print("  ERROR: No container runtime found (docker or podman)")
            sys.exit(1)

    # Create ECR repo if it doesn't exist
    result = subprocess.run(
        f"aws ecr describe-repositories --repository-names {ECR_REPO} --region {AWS_REGION}",
        shell=True, capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"  Creating ECR repository: {ECR_REPO}")
        run(f"aws ecr create-repository --repository-name {ECR_REPO} "
            f"--image-scanning-configuration scanOnPush=true "
            f"--region {AWS_REGION}")

    # Login to ECR
    print("  Logging into ECR...")
    run(f"aws ecr get-login-password --region {AWS_REGION} | "
        f"{container_cmd} login --username AWS --password-stdin "
        f"{AWS_ACCOUNT}.dkr.ecr.{AWS_REGION}.amazonaws.com")

    # Build image
    image_tag = f"deploy-{environment}-{int(time.time())}"
    full_uri = f"{AWS_ACCOUNT}.dkr.ecr.{AWS_REGION}.amazonaws.com/{ECR_REPO}:{image_tag}"

    print(f"  Building image: {full_uri}")
    run(f"{container_cmd} build --network=host -t {full_uri} .")

    # Push image (with Docker v2 format for ECR compatibility)
    print(f"  Pushing to ECR...")
    run(f"{container_cmd} push --format=v2s2 {full_uri}")

    print(f"  [OK] Image pushed: {image_tag}")
    return image_tag


def step_deploy_stacks(environment: str, image_tag: str):
    """Deploy all CDK stacks."""
    print("\n" + "=" * 60)
    print(f"  STEP 6: Deploying CDK stacks (environment: {environment})")
    print("=" * 60)

    context_args = (
        f"--context environment={environment} "
        f"--context imageTag={image_tag}"
    )

    # Synth first to catch errors early
    print("\n  Synthesizing templates...")
    run(f"npx aws-cdk@2 synth --all {context_args}")

    # Deploy all stacks
    print("\n  Deploying all stacks (this takes 5-10 minutes)...")
    run(f"npx aws-cdk@2 deploy --all {context_args} --require-approval never")

    print("\n  [OK] All stacks deployed successfully!")


def step_post_deploy_health_check(environment: str):
    """Run post-deployment health checks."""
    print("\n" + "=" * 60)
    print("  STEP 7: Post-deployment verification")
    print("=" * 60)

    # Get service endpoint from CloudFormation outputs
    print("  Checking ECS service status...")
    cluster = f"aiops-cluster-{environment}"
    service = f"aiops-service-{environment}"

    result = run(
        f"aws ecs describe-services --cluster {cluster} "
        f"--services {service} --region {AWS_REGION}",
        capture=True, check=False,
    )

    if result.returncode == 0:
        data = json.loads(result.stdout)
        services = data.get("services", [])
        if services:
            svc = services[0]
            running = svc.get("runningCount", 0)
            desired = svc.get("desiredCount", 0)
            status = svc.get("status", "UNKNOWN")
            print(f"  [OK] Service: {status} (running: {running}/{desired})")
        else:
            print("  [WARN] Service not found yet — may still be starting")
    else:
        print("  [WARN] Could not check service status")

    # Check SQS queue exists
    print("  Checking SQS queue...")
    result = run(
        f"aws sqs get-queue-url --queue-name aiops-main-{environment} --region {AWS_REGION}",
        capture=True, check=False,
    )
    if result.returncode == 0:
        queue_url = json.loads(result.stdout).get("QueueUrl", "")
        print(f"  [OK] SQS Queue: {queue_url}")
    else:
        print("  [WARN] Queue not found")

    # Check DynamoDB table
    print("  Checking DynamoDB table...")
    result = run(
        f"aws dynamodb describe-table --table-name AiopsIncidentMemory-{environment} --region {AWS_REGION}",
        capture=True, check=False,
    )
    if result.returncode == 0:
        print(f"  [OK] DynamoDB table: AiopsIncidentMemory-{environment}")
    else:
        print("  [WARN] Table not found")


def step_print_demo_instructions(environment: str, image_tag: str):
    """Print instructions for running the demo."""
    print("\n" + "=" * 60)
    print("  DEPLOYMENT COMPLETE!")
    print("=" * 60)
    print(f"""
  Environment: {environment}
  Image Tag:   {image_tag}
  Account:     {AWS_ACCOUNT}
  Region:      {AWS_REGION}

  ── Next Steps ──────────────────────────────────────────────

  1. Wait 2-3 minutes for ECS tasks to reach RUNNING state

  2. Test the health endpoint:
     aws ecs execute-command --cluster aiops-cluster-{environment} \\
       --task <TASK_ID> --container AiopsContainer \\
       --interactive --command "curl -s http://localhost:8080/health"

  3. Send a test alert to trigger the pipeline:
     python demo/trigger_scenario.py --scenario inject \\
       --alert-name HighCPUUsage --severity critical

  4. Check CloudWatch logs:
     aws logs tail /aiops/{environment}/ecs --follow --region {AWS_REGION}

  5. Check metrics in CloudWatch Dashboard:
     https://{AWS_REGION}.console.aws.amazon.com/cloudwatch/home?region={AWS_REGION}#dashboards:name=AIOps-{environment}

  6. To destroy all resources:
     python destroy.py --environment {environment}
""")


# ============================================================================
# Main
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="Deploy AIOps to AWS")
    parser.add_argument("--environment", default="dev", choices=ENVIRONMENTS)
    parser.add_argument("--skip-docker", action="store_true",
                        help="Skip Docker build, use existing image")
    parser.add_argument("--skip-bootstrap", action="store_true",
                        help="Skip CDK bootstrap step")
    args = parser.parse_args()

    print("╔══════════════════════════════════════════════════════════════╗")
    print("║   AIOps Self-Healing Infrastructure — AWS Deployment        ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print(f"  Target: {args.environment} | Account: {AWS_ACCOUNT} | Region: {AWS_REGION}")

    step_check_prerequisites()
    step_install_dependencies()

    if not args.skip_bootstrap:
        step_bootstrap_cdk(args.environment)

    step_verify_ses_email()
    image_tag = step_create_ecr_and_push_image(args.environment, args.skip_docker)
    step_deploy_stacks(args.environment, image_tag)
    step_post_deploy_health_check(args.environment)
    step_print_demo_instructions(args.environment, image_tag)


if __name__ == "__main__":
    main()
