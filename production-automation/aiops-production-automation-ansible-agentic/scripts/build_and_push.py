"""Build and push Docker image to ECR using AWS CodeBuild.

Usage:
    python scripts/build_and_push.py --tag latest-dev --region us-east-1

This script creates a temporary CodeBuild project, zips the source,
uploads to S3, triggers a build, waits for completion, then cleans up.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
import time
import zipfile

import boto3


ACCOUNT_ID = "533267042240"
ECR_REPO = "aiops"
PROJECT_NAME = "aiops-image-build-temp"


def create_source_zip(project_root: str) -> bytes:
    """Create a zip archive of the project for CodeBuild."""
    buf = io.BytesIO()
    include_dirs = {"src", "config", "playbooks"}
    include_files = {"Dockerfile", "requirements.lock", "buildspec.yml", "ansible.cfg"}

    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for fname in include_files:
            fpath = os.path.join(project_root, fname)
            if os.path.exists(fpath):
                zf.write(fpath, fname)

        for dirname in include_dirs:
            dirpath = os.path.join(project_root, dirname)
            if os.path.isdir(dirpath):
                for root, _dirs, files in os.walk(dirpath):
                    for f in files:
                        full = os.path.join(root, f)
                        arcname = os.path.relpath(full, project_root)
                        zf.write(full, arcname)

    return buf.getvalue()


def main() -> None:
    parser = argparse.ArgumentParser(description="Build and push image via CodeBuild")
    parser.add_argument("--tag", default="latest-dev", help="Image tag")
    parser.add_argument("--region", default="us-east-1", help="AWS region")
    parser.add_argument("--profile", default="mfa", help="AWS profile")
    args = parser.parse_args()

    session = boto3.Session(profile_name=args.profile, region_name=args.region)
    s3 = session.client("s3")
    cb = session.client("codebuild")
    iam = session.client("iam")

    ecr_repo_uri = f"{ACCOUNT_ID}.dkr.ecr.{args.region}.amazonaws.com/{ECR_REPO}"
    bucket_name = f"aiops-codebuild-source-{ACCOUNT_ID}-{args.region}"

    # 1. Create S3 bucket for source (if not exists)
    print(f"[1/6] Ensuring S3 bucket: {bucket_name}")
    try:
        if args.region == "us-east-1":
            s3.create_bucket(Bucket=bucket_name)
        else:
            s3.create_bucket(
                Bucket=bucket_name,
                CreateBucketConfiguration={"LocationConstraint": args.region},
            )
    except s3.exceptions.BucketAlreadyOwnedByYou:
        pass
    except Exception as e:
        if "BucketAlreadyOwnedByYou" in str(e) or "BucketAlreadyExists" in str(e):
            pass
        else:
            raise

    # 2. Upload source zip
    print("[2/6] Zipping and uploading source code...")
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    source_zip = create_source_zip(project_root)
    s3_key = f"source/{args.tag}/source.zip"
    s3.put_object(Bucket=bucket_name, Key=s3_key, Body=source_zip)
    print(f"  Uploaded {len(source_zip)} bytes to s3://{bucket_name}/{s3_key}")

    # 3. Create/update CodeBuild service role
    role_name = "aiops-codebuild-service-role"
    print(f"[3/6] Ensuring IAM role: {role_name}")
    trust_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "codebuild.amazonaws.com"},
                "Action": "sts:AssumeRole",
            }
        ],
    }
    try:
        iam.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(trust_policy),
            Description="CodeBuild role for AIOps image builds",
        )
        # Attach policies
        iam.attach_role_policy(
            RoleName=role_name,
            PolicyArn="arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryPowerUser",
        )
        iam.attach_role_policy(
            RoleName=role_name,
            PolicyArn="arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess",
        )
        iam.attach_role_policy(
            RoleName=role_name,
            PolicyArn="arn:aws:iam::aws:policy/CloudWatchLogsFullAccess",
        )
        print("  Created role and attached policies. Waiting 10s for propagation...")
        time.sleep(10)
    except iam.exceptions.EntityAlreadyExistsException:
        print("  Role already exists.")

    role_arn = f"arn:aws:iam::{ACCOUNT_ID}:role/{role_name}"

    # 4. Create CodeBuild project
    print(f"[4/6] Creating CodeBuild project: {PROJECT_NAME}")
    try:
        cb.delete_project(name=PROJECT_NAME)
    except Exception:
        pass

    cb.create_project(
        name=PROJECT_NAME,
        description="Temporary project to build AIOps Docker image",
        source={
            "type": "S3",
            "location": f"{bucket_name}/{s3_key}",
        },
        artifacts={"type": "NO_ARTIFACTS"},
        environment={
            "type": "LINUX_CONTAINER",
            "image": "aws/codebuild/standard:7.0",
            "computeType": "BUILD_GENERAL1_SMALL",
            "privilegedMode": True,
            "environmentVariables": [
                {"name": "ECR_REPO_URI", "value": ecr_repo_uri, "type": "PLAINTEXT"},
                {"name": "IMAGE_TAG", "value": args.tag, "type": "PLAINTEXT"},
                {"name": "AWS_DEFAULT_REGION", "value": args.region, "type": "PLAINTEXT"},
            ],
        },
        serviceRole=role_arn,
    )

    # 5. Start build
    print("[5/6] Starting build...")
    build_resp = cb.start_build(projectName=PROJECT_NAME)
    build_id = build_resp["build"]["id"]
    print(f"  Build ID: {build_id}")

    # Wait for build
    print("  Waiting for build to complete...")
    while True:
        time.sleep(15)
        builds = cb.batch_get_builds(ids=[build_id])
        status = builds["builds"][0]["buildStatus"]
        phase = builds["builds"][0].get("currentPhase", "UNKNOWN")
        print(f"  Status: {status} | Phase: {phase}")
        if status != "IN_PROGRESS":
            break

    if status == "SUCCEEDED":
        print(f"\n[6/6] SUCCESS! Image pushed: {ecr_repo_uri}:{args.tag}")
    else:
        print(f"\n[6/6] FAILED! Build status: {status}")
        # Print logs
        logs = builds["builds"][0].get("logs", {})
        if logs.get("deepLink"):
            print(f"  Logs: {logs['deepLink']}")
        sys.exit(1)

    # Cleanup: delete project (keep role for reuse)
    print("\nCleaning up CodeBuild project...")
    cb.delete_project(name=PROJECT_NAME)
    print("Done!")


if __name__ == "__main__":
    main()
