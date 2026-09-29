"""Image tag builder and canary decision utilities.

Pure, stateless functions for constructing Docker image tags
and making canary deployment decisions based on metrics.
"""

import re

VALID_ENVIRONMENTS = {"dev", "staging", "prod"}
HEX_PATTERN = re.compile(r"^[0-9a-f]+$")


def build_image_tag(sha: str, env: str) -> str:
    """Build a Docker image tag from a commit SHA and environment name.

    The tag format is ``{sha[:7]}-{env}`` where sha is the first 7 characters
    of a lowercase hexadecimal Git commit SHA.

    Args:
        sha: A lowercase hexadecimal string (Git commit SHA). Must be at least
            7 characters long and contain only hex digits [0-9a-f].
        env: The target environment. Must be one of "dev", "staging", or "prod".

    Returns:
        A string in the format ``{sha[:7]}-{env}`` (e.g., ``abc1234-prod``).

    Raises:
        ValueError: If sha is not a valid lowercase hex string of at least 7
            characters, or if env is not one of the valid environments.
    """
    if not isinstance(sha, str) or len(sha) < 7:
        raise ValueError(
            f"sha must be a lowercase hex string of at least 7 characters, got '{sha}'"
        )
    if not HEX_PATTERN.match(sha):
        raise ValueError(
            f"sha must contain only lowercase hex characters [0-9a-f], got '{sha}'"
        )
    if env not in VALID_ENVIRONMENTS:
        raise ValueError(
            f"env must be one of {sorted(VALID_ENVIRONMENTS)}, got '{env}'"
        )
    return f"{sha[:7]}-{env}"


def canary_decision(error_rate: float, latency_p95: float) -> str:
    """Decide whether to proceed or rollback a canary deployment.

    Evaluates metrics from a canary observation window and returns a decision.
    The canary proceeds only if both thresholds are met:
    - error_rate < 5.0 (percent)
    - latency_p95 < 15000 (milliseconds)

    Args:
        error_rate: The error rate as a percentage (0.0–100.0).
        latency_p95: The 95th percentile latency in milliseconds.

    Returns:
        "PROCEED" if both thresholds are satisfied, "ROLLBACK" otherwise.
    """
    if error_rate < 5.0 and latency_p95 < 15000:
        return "PROCEED"
    return "ROLLBACK"
