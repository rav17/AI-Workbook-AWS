"""SSM Executor — executes remediation plans via AWS Systems Manager.

Runs sequential steps on target instances via SSM SendCommand.
Implements prerequisite checks, timeout handling, output capture,
and concurrency limiting.

Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass
from typing import Optional

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from src.agentic_ai.models.domain import PrerequisiteResult, RemediationPlan

logger = logging.getLogger(__name__)

MAX_STEPS = 20
MAX_PAYLOAD_CHARS = 32_000
MAX_OUTPUT_CHARS = 10_000
MAX_CONCURRENT_EXECUTIONS = 10
DEFAULT_TIMEOUT_SECONDS = 300
MIN_TIMEOUT_SECONDS = 30
MAX_TIMEOUT_SECONDS = 3600
MAX_RETRIES = 2
INITIAL_BACKOFF = 1.0


@dataclass
class StepResult:
    """Result of a single SSM step execution."""

    step_number: int
    status: str  # "success", "failure", "skipped", "timeout"
    output: str
    duration_seconds: float


@dataclass
class ExecutionResult:
    """Result of executing a full remediation plan."""

    success: bool
    steps_completed: int
    steps_skipped: int
    total_steps: int
    step_results: list[StepResult]
    total_duration_seconds: float
    output_summary: str


class SSMExecutor:
    """Executes remediation plans via AWS Systems Manager.

    Features:
    - Sequential step execution (max 20 steps), abort on failure
    - Parameter payload size validation (< 32,000 chars)
    - Prerequisite checks (registration, online, IAM role)
    - Configurable timeout (30-3600s, default 300)
    - Output capture truncated to 10,000 chars
    - Asyncio semaphore for max 10 concurrent executions
    - Retry logic for SSM API failures
    """

    def __init__(
        self,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
        ssm_client=None,
        region_name: Optional[str] = None,
    ) -> None:
        if timeout_seconds < MIN_TIMEOUT_SECONDS or timeout_seconds > MAX_TIMEOUT_SECONDS:
            self._timeout = DEFAULT_TIMEOUT_SECONDS
        else:
            self._timeout = timeout_seconds

        if ssm_client:
            self._client = ssm_client
        else:
            kwargs = {}
            if region_name:
                kwargs["region_name"] = region_name
            self._client = boto3.client("ssm", **kwargs)

        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT_EXECUTIONS)

    async def check_prerequisites(self, instance_id: str) -> PrerequisiteResult:
        """Check if an instance is ready for SSM execution.

        Verifies: registration, online status, IAM role.
        """
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self._client.describe_instance_information(
                    Filters=[{"Key": "InstanceIds", "Values": [instance_id]}]
                ),
            )
        except (ClientError, BotoCoreError) as e:
            return PrerequisiteResult(
                is_ready=False,
                registration_status=False,
                online_status=False,
                iam_role_attached=False,
                error_message=f"SSM API error: {e}",
            )

        instances = response.get("InstanceInformationList", [])
        if not instances:
            return PrerequisiteResult(
                is_ready=False,
                registration_status=False,
                online_status=False,
                iam_role_attached=False,
                error_message=f"Instance {instance_id} not registered with SSM",
            )

        info = instances[0]
        is_online = info.get("PingStatus") == "Online"
        has_role = bool(info.get("IamRole"))

        if not is_online:
            return PrerequisiteResult(
                is_ready=False,
                registration_status=True,
                online_status=False,
                iam_role_attached=has_role,
                error_message=f"Instance {instance_id} is not online",
            )

        if not has_role:
            return PrerequisiteResult(
                is_ready=False,
                registration_status=True,
                online_status=True,
                iam_role_attached=False,
                error_message=f"Instance {instance_id} has no IAM role",
            )

        return PrerequisiteResult(
            is_ready=True,
            registration_status=True,
            online_status=True,
            iam_role_attached=True,
        )

    async def execute(self, plan: RemediationPlan) -> ExecutionResult:
        """Execute a remediation plan sequentially, aborting on failure.

        Args:
            plan: The remediation plan with ordered steps.

        Returns:
            ExecutionResult with step-level details.
        """
        async with self._semaphore:
            return await self._execute_plan(plan)

    async def _execute_plan(self, plan: RemediationPlan) -> ExecutionResult:
        """Internal plan execution logic."""
        start_time = time.time()
        steps = plan.steps[:MAX_STEPS]
        step_results: list[StepResult] = []
        completed = 0
        skipped = 0

        for step in steps:
            # Validate payload size
            payload = json.dumps(step.parameters if hasattr(step, "parameters") else {})
            if len(payload) > MAX_PAYLOAD_CHARS:
                step_results.append(StepResult(
                    step_number=step.step_number,
                    status="failure",
                    output=f"Payload exceeds {MAX_PAYLOAD_CHARS} chars",
                    duration_seconds=0.0,
                ))
                skipped = len(steps) - len(step_results)
                break

            # Execute step with retry
            result = await self._execute_step(step)
            step_results.append(result)

            if result.status != "success":
                # Abort remaining steps
                skipped = len(steps) - len(step_results)
                break

            completed += 1

        total_duration = time.time() - start_time
        output_parts = [r.output for r in step_results if r.output]
        output_summary = "\n".join(output_parts)[:MAX_OUTPUT_CHARS]

        return ExecutionResult(
            success=(completed == len(steps)),
            steps_completed=completed,
            steps_skipped=skipped,
            total_steps=len(steps),
            step_results=step_results,
            total_duration_seconds=total_duration,
            output_summary=output_summary,
        )

    async def _execute_step(self, step) -> StepResult:
        """Execute a single step with retry logic."""
        backoff = INITIAL_BACKOFF
        step_start = time.time()

        for attempt in range(MAX_RETRIES + 1):
            try:
                result = await self._send_command(step)
                return result
            except (ClientError, BotoCoreError) as e:
                if attempt < MAX_RETRIES:
                    logger.warning(
                        "SSM step %d attempt %d failed: %s",
                        step.step_number,
                        attempt + 1,
                        e,
                    )
                    await asyncio.sleep(backoff)
                    backoff *= 2
                else:
                    duration = time.time() - step_start
                    return StepResult(
                        step_number=step.step_number,
                        status="failure",
                        output=f"SSM API error after retries: {e}",
                        duration_seconds=duration,
                    )

        duration = time.time() - step_start
        return StepResult(
            step_number=step.step_number,
            status="failure",
            output="Exhausted retries",
            duration_seconds=duration,
        )

    async def _send_command(self, step) -> StepResult:
        """Send an SSM command and wait for completion."""
        step_start = time.time()
        loop = asyncio.get_event_loop()

        parameters = step.parameters if hasattr(step, "parameters") else {}

        response = await loop.run_in_executor(
            None,
            lambda: self._client.send_command(
                InstanceIds=[step.target_resource],
                DocumentName=step.action,
                Parameters=parameters,
                TimeoutSeconds=self._timeout,
            ),
        )

        command_id = response["Command"]["CommandId"]

        # Poll for completion
        output = await self._poll_command(command_id, step.target_resource)
        duration = time.time() - step_start

        return StepResult(
            step_number=step.step_number,
            status=output["status"],
            output=output["output"][:MAX_OUTPUT_CHARS],
            duration_seconds=duration,
        )

    async def _poll_command(
        self, command_id: str, instance_id: str
    ) -> dict[str, str]:
        """Poll SSM command until completion or timeout."""
        loop = asyncio.get_event_loop()
        deadline = time.time() + self._timeout

        while time.time() < deadline:
            await asyncio.sleep(2)
            try:
                response = await loop.run_in_executor(
                    None,
                    lambda: self._client.get_command_invocation(
                        CommandId=command_id,
                        InstanceId=instance_id,
                    ),
                )

                status = response.get("Status", "")
                if status in ("Success",):
                    output = response.get("StandardOutputContent", "")
                    return {"status": "success", "output": output}
                elif status in ("Failed", "Cancelled", "TimedOut"):
                    output = response.get("StandardErrorContent", "")
                    return {"status": "failure", "output": output}
                # Still running — continue polling

            except ClientError as e:
                if "InvocationDoesNotExist" in str(e):
                    await asyncio.sleep(2)
                else:
                    raise

        return {"status": "timeout", "output": "Command timed out"}
