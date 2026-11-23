"""Remediation Executor component for the self-healing infrastructure system.

Invokes Ansible playbooks against target hosts and captures execution results.
Validates playbook file existence before subprocess invocation.
"""

import asyncio
import os
import time
from typing import Optional

from src.models import ExecutionResult, RemediationStatus


class RemediationExecutor:
    """Executes Ansible playbooks against target hosts.

    Features:
    - Validates playbook file existence before subprocess invocation
    - Invokes ansible-playbook via asyncio subprocess
    - Captures stdout/stderr truncated to 10,000 characters each
    - Implements timeout handling (default 300s) with SIGTERM → SIGKILL after 5s
    - Implements concurrency limit (10 simultaneous executions) with asyncio.Semaphore
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
        """Execute an Ansible playbook against a target host.

        Validates playbook existence before spawning a subprocess.
        Constructs the ansible-playbook command with target host as inventory
        and extra vars passed via -e flag.

        Args:
            playbook_path: Path to the Ansible playbook file.
            target_host: Target host for playbook execution.
            extra_vars: Additional variables to pass to the playbook.

        Returns:
            ExecutionResult with status, output, and timing information.
        """
        # Validate playbook file existence before subprocess invocation
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

        # Build the ansible-playbook command
        cmd = self._build_command(playbook_path, target_host, extra_vars or {})

        # Acquire semaphore slot for concurrency limiting
        async with self._semaphore:
            return await self._run_subprocess(cmd, playbook_path, target_host)

    def _build_command(
        self, playbook_path: str, target_host: str, extra_vars: dict
    ) -> list[str]:
        """Construct the ansible-playbook command.

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
            import json
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
                # Send SIGTERM first
                process.terminate()
                try:
                    # Wait 5 seconds for graceful shutdown
                    await asyncio.wait_for(process.communicate(), timeout=5)
                except asyncio.TimeoutError:
                    # Force kill if SIGTERM didn't work
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
