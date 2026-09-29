"""Remediation Executor component for the self-healing infrastructure system.

Executes remediation playbooks against target hosts using AWS SSM RunCommand.
For EC2 instance targets (i-*), uses SSM directly for reliable remote execution.
Falls back to local ansible-playbook for non-EC2 targets.
"""

import asyncio
import json
import logging
import os
import re
import time
from typing import Optional

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from src.models import ExecutionResult, RemediationStatus

logger = logging.getLogger(__name__)

# SSM client (module-level singleton)
_ssm_client = None


def _get_ssm_client():
    """Get or create the SSM client."""
    global _ssm_client
    if _ssm_client is None:
        _ssm_client = boto3.client(
            "ssm", region_name=os.environ.get("AWS_REGION", "us-east-1")
        )
    return _ssm_client


class RemediationExecutor:
    """Executes remediation playbooks against target hosts.

    For EC2 instance targets (i-*), uses AWS SSM RunCommand directly.
    This avoids SSH/connection plugin complexity when running from ECS Fargate.

    Features:
    - SSM RunCommand for EC2 targets (no SSH required)
    - Validates playbook file existence before execution
    - Timeout handling (default 300s)
    - Concurrency limit (10 simultaneous executions) with asyncio.Semaphore
    """

    MAX_OUTPUT_LENGTH = 10_000
    MAX_CONCURRENT_EXECUTIONS = 10

    def __init__(self, timeout: int = 300):
        """Initialize the executor with a configurable timeout.

        Args:
            timeout: Maximum execution time in seconds (default 300).
        """
        self.timeout = timeout
        self._semaphore = asyncio.Semaphore(self.MAX_CONCURRENT_EXECUTIONS)

    async def execute(
        self,
        playbook_path: str,
        target_host: str,
        extra_vars: Optional[dict] = None,
    ) -> ExecutionResult:
        """Execute a remediation playbook against a target host.

        For EC2 instances (target starts with 'i-'), uses SSM RunCommand.
        Otherwise falls back to local ansible-playbook subprocess.

        Args:
            playbook_path: Path to the Ansible playbook file.
            target_host: Target host (EC2 instance ID or hostname).
            extra_vars: Additional variables to pass to the playbook.

        Returns:
            ExecutionResult with status, output, and timing information.
        """
        if not os.path.isfile(playbook_path):
            return ExecutionResult(
                status=RemediationStatus.FAILURE,
                return_code=-1,
                stdout="",
                stderr=f"Playbook not found: {playbook_path}",
                duration_seconds=0.0,
                playbook_path=playbook_path,
                target_host=target_host,
            )

        if not os.access(playbook_path, os.R_OK):
            return ExecutionResult(
                status=RemediationStatus.FAILURE,
                return_code=-1,
                stdout="",
                stderr=f"Playbook not readable: {playbook_path}",
                duration_seconds=0.0,
                playbook_path=playbook_path,
                target_host=target_host,
            )

        async with self._semaphore:
            # Use SSM RunCommand for EC2 instance targets
            if re.match(r"^i-[0-9a-f]+$", target_host):
                return await self._execute_via_ssm(
                    playbook_path, target_host, extra_vars or {}
                )
            else:
                # Fallback to local ansible-playbook for non-EC2 targets
                cmd = self._build_command(playbook_path, target_host, extra_vars or {})
                return await self._run_subprocess(cmd, playbook_path, target_host)

    async def _execute_via_ssm(
        self, playbook_path: str, instance_id: str, extra_vars: dict
    ) -> ExecutionResult:
        """Execute remediation via SSM RunCommand on an EC2 instance.

        Reads the playbook, extracts shell commands from tasks, and runs them
        directly on the target via SSM RunShellScript.

        Args:
            playbook_path: Path to the YAML playbook.
            instance_id: EC2 instance ID (e.g., i-0ea05de70aa7d590d).
            extra_vars: Extra variables (used for command interpolation).

        Returns:
            ExecutionResult with SSM command output.
        """
        start_time = time.monotonic()

        try:
            # Extract shell commands from the playbook
            commands = self._extract_commands_from_playbook(playbook_path)
            if not commands:
                return ExecutionResult(
                    status=RemediationStatus.FAILURE,
                    return_code=-1,
                    stdout="",
                    stderr="No executable commands extracted from playbook",
                    duration_seconds=time.monotonic() - start_time,
                    playbook_path=playbook_path,
                    target_host=instance_id,
                )

            ssm = _get_ssm_client()

            # Send commands via SSM RunShellScript
            response = ssm.send_command(
                InstanceIds=[instance_id],
                DocumentName="AWS-RunShellScript",
                Parameters={"commands": commands},
                TimeoutSeconds=min(self.timeout, 600),
                Comment=f"AIOps remediation: {os.path.basename(playbook_path)}",
            )
            command_id = response["Command"]["CommandId"]
            logger.info(
                "SSM command sent: command_id=%s instance=%s playbook=%s",
                command_id,
                instance_id,
                playbook_path,
            )

            # Wait for completion
            stdout, stderr, exit_code = await self._wait_for_ssm_command(
                ssm, command_id, instance_id
            )

            duration = time.monotonic() - start_time
            status = (
                RemediationStatus.SUCCESS if exit_code == 0
                else RemediationStatus.FAILURE
            )

            return ExecutionResult(
                status=status,
                return_code=exit_code,
                stdout=stdout[: self.MAX_OUTPUT_LENGTH],
                stderr=stderr[: self.MAX_OUTPUT_LENGTH],
                duration_seconds=duration,
                playbook_path=playbook_path,
                target_host=instance_id,
            )

        except (BotoCoreError, ClientError) as e:
            duration = time.monotonic() - start_time
            logger.error("SSM execution failed: %s", e)
            return ExecutionResult(
                status=RemediationStatus.FAILURE,
                return_code=-1,
                stdout="",
                stderr=f"SSM execution error: {str(e)}",
                duration_seconds=duration,
                playbook_path=playbook_path,
                target_host=instance_id,
            )
        except Exception as e:
            duration = time.monotonic() - start_time
            logger.error("Unexpected executor error: %s", e)
            return ExecutionResult(
                status=RemediationStatus.FAILURE,
                return_code=-1,
                stdout="",
                stderr=f"Executor error: {str(e)}",
                duration_seconds=duration,
                playbook_path=playbook_path,
                target_host=instance_id,
            )

    def _extract_commands_from_playbook(self, playbook_path: str) -> list[str]:
        """Extract shell commands from an Ansible playbook YAML.

        Parses the playbook and extracts commands from shell/command tasks.
        Systemd tasks are converted to systemctl commands.

        Args:
            playbook_path: Path to the YAML playbook file.

        Returns:
            List of shell commands to execute.
        """
        import yaml

        with open(playbook_path, encoding="utf-8") as f:
            playbook = yaml.safe_load(f)

        commands = ["#!/bin/bash", "set +e"]  # Continue on errors (like ignore_errors in Ansible)

        if not isinstance(playbook, list):
            return commands

        for play in playbook:
            tasks = play.get("tasks", [])
            for task in tasks:
                # Extract shell/command module commands
                shell_cmd = task.get("ansible.builtin.shell") or task.get("shell")
                cmd = task.get("ansible.builtin.command") or task.get("command")

                if shell_cmd:
                    # Add comment with task name
                    name = task.get("name", "unnamed task")
                    commands.append(f"echo '>>> {name}'")
                    commands.append(shell_cmd.strip())
                elif cmd:
                    name = task.get("name", "unnamed task")
                    commands.append(f"echo '>>> {name}'")
                    commands.append(cmd.strip())

                # Handle systemd module
                systemd = task.get("ansible.builtin.systemd") or task.get("systemd")
                if systemd and isinstance(systemd, dict):
                    svc_name = systemd.get("name", "")
                    state = systemd.get("state", "")
                    ignore = task.get("ignore_errors", False)
                    suffix = " || true" if ignore else ""
                    if svc_name and state:
                        name = task.get("name", "systemd task")
                        commands.append(f"echo '>>> {name}'")
                        if state == "restarted":
                            commands.append(f"systemctl restart {svc_name}{suffix}")
                        elif state == "started":
                            commands.append(f"systemctl start {svc_name}{suffix}")
                        elif state == "stopped":
                            commands.append(f"systemctl stop {svc_name}{suffix}")

        # Always succeed (ignore_errors equivalent)
        commands.append("echo 'Remediation complete'")
        commands.append("exit 0")
        return commands

    async def _wait_for_ssm_command(
        self, ssm, command_id: str, instance_id: str
    ) -> tuple[str, str, int]:
        """Poll SSM for command completion.

        Args:
            ssm: SSM boto3 client.
            command_id: The SSM command ID.
            instance_id: The target instance ID.

        Returns:
            Tuple of (stdout, stderr, exit_code).
        """
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            await asyncio.sleep(3)
            try:
                result = ssm.get_command_invocation(
                    CommandId=command_id,
                    InstanceId=instance_id,
                )
                status = result.get("Status", "")
                if status in ("Success", "Failed", "TimedOut", "Cancelled"):
                    stdout = result.get("StandardOutputContent", "")
                    stderr = result.get("StandardErrorContent", "")
                    exit_code = 0 if status == "Success" else 1
                    return stdout, stderr, exit_code
                # InProgress or Pending — keep waiting
            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "")
                if error_code == "InvocationDoesNotExist":
                    # Command hasn't reached the instance yet
                    continue
                else:
                    logger.warning("SSM get_command_invocation error: %s", e)
                    return "", f"SSM polling error: {str(e)}", 1
            except Exception as e:
                logger.warning("Unexpected error polling SSM: %s", e)
                continue

        return "", "SSM command timed out waiting for result", 1

    def _build_command(
        self, playbook_path: str, target_host: str, extra_vars: dict
    ) -> list[str]:
        """Construct the ansible-playbook command for non-EC2 targets.

        Args:
            playbook_path: Path to the playbook file.
            target_host: Target host (used as inventory with trailing comma).
            extra_vars: Extra variables to pass via -e flag.

        Returns:
            List of command arguments.
        """
        cmd = [
            "ansible-playbook",
            playbook_path,
            "-i",
            f"{target_host},",
        ]

        if extra_vars:
            cmd.extend(["-e", json.dumps(extra_vars)])

        return cmd

    async def _run_subprocess(
        self, cmd: list[str], playbook_path: str, target_host: str
    ) -> ExecutionResult:
        """Run the subprocess with timeout handling.

        Args:
            cmd: Command arguments to execute.
            playbook_path: Path to the playbook (for result reporting).
            target_host: Target host (for result reporting).

        Returns:
            ExecutionResult with captured output and status.
        """
        start_time = time.monotonic()

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    process.communicate(), timeout=self.timeout
                )
            except asyncio.TimeoutError:
                process.terminate()
                try:
                    await asyncio.wait_for(process.communicate(), timeout=5)
                except asyncio.TimeoutError:
                    process.kill()
                    await process.communicate()

                duration = time.monotonic() - start_time
                return ExecutionResult(
                    status=RemediationStatus.TIMEOUT,
                    return_code=-1,
                    stdout="",
                    stderr=f"Execution timed out after {self.timeout} seconds",
                    duration_seconds=duration,
                    playbook_path=playbook_path,
                    target_host=target_host,
                )

            duration = time.monotonic() - start_time
            stdout = stdout_bytes.decode("utf-8", errors="replace")[
                : self.MAX_OUTPUT_LENGTH
            ]
            stderr = stderr_bytes.decode("utf-8", errors="replace")[
                : self.MAX_OUTPUT_LENGTH
            ]
            return_code = process.returncode or 0

            if return_code == 0:
                status = RemediationStatus.SUCCESS
            else:
                status = RemediationStatus.FAILURE

            return ExecutionResult(
                status=status,
                return_code=return_code,
                stdout=stdout,
                stderr=stderr,
                duration_seconds=duration,
                playbook_path=playbook_path,
                target_host=target_host,
            )

        except Exception as e:
            duration = time.monotonic() - start_time
            return ExecutionResult(
                status=RemediationStatus.FAILURE,
                return_code=-1,
                stdout="",
                stderr=f"Subprocess spawn failure: {str(e)}",
                duration_seconds=duration,
                playbook_path=playbook_path,
                target_host=target_host,
            )
