"""Deploy the AIOps Self-Healing Infrastructure to AWS (single command).

Thin wrapper around ``scripts/aiops_env.py up``, which does the full, idempotent
provisioning: preflight checks, CDK bootstrap, ECR repo, image build via CodeBuild
(no local Docker needed), all CDK stacks, the AWS DevOps Agent space + webhook,
an ECS restart and a /health check.

Usage (run with the project virtualenv's Python):
    python deploy.py                       # dev, with AWS DevOps Agent
    python deploy.py --environment staging
    python deploy.py --skip-docker         # reuse the existing aiops:latest-<env> image
    python deploy.py --no-devops-agent     # skip the AWS DevOps Agent setup
    python deploy.py --dry-run             # preflight + synth only, no changes
    python deploy.py --profile default     # AWS CLI profile (default: mfa)

Tear down with: python destroy.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "scripts"))

import aiops_env  # noqa: E402


def main() -> int:
    """Parse legacy-compatible flags and run `aiops_env.py up`."""
    parser = argparse.ArgumentParser(description="Deploy AIOps to AWS (all stacks + DevOps Agent)")
    parser.add_argument("--environment", default="dev", choices=aiops_env.ENVIRONMENTS)
    parser.add_argument("--profile", default="mfa", help="AWS CLI profile (default: mfa)")
    parser.add_argument("--skip-docker", action="store_true",
                        help="Skip the image build and reuse aiops:latest-<env>")
    parser.add_argument("--no-devops-agent", action="store_true",
                        help="Skip the AWS DevOps Agent setup")
    parser.add_argument("--dry-run", action="store_true", help="Preflight + synth only")
    parser.add_argument("--skip-bootstrap", action="store_true",
                        help="Ignored: bootstrap is only run when CDKToolkit is missing")
    args = parser.parse_args()

    forwarded = ["up", "--env", args.environment, "--profile", args.profile]
    if args.skip_docker:
        forwarded.append("--skip-build")
    if args.no_devops_agent:
        forwarded.append("--no-devops-agent")
    if args.dry_run:
        forwarded.append("--dry-run")
    return aiops_env.main(forwarded)


if __name__ == "__main__":
    raise SystemExit(main())
