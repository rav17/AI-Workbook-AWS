# Feature: self-healing-infrastructure, Property 15: Executor command construction
"""Property-based tests for the Remediation Executor component.

Property 15: Executor command construction
*For any* valid playbook path, target host, and alert context (incident ID,
alert name, severity, labels, annotations), the Remediation Executor SHALL
construct an ansible-playbook command with the target host as inventory and
all context fields passed as extra variables.

**Validates: Requirements 5.1**
"""

import asyncio
import json
import os
import tempfile
from unittest.mock import patch, AsyncMock

from hypothesis import given, settings
from hypothesis import strategies as st

from src.executor import RemediationExecutor
from src.models import RemediationStatus


# --- Hypothesis Strategies ---

# Strategy for generating valid playbook paths
playbook_path_strategy = st.text(
    min_size=5,
    max_size=100,
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_-/.")
).map(lambda p: f"/playbooks/{p}.yml")

# Strategy for generating valid target hosts
target_host_strategy = st.one_of(
    # Hostname format
    st.text(
        min_size=1,
        max_size=50,
        alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_-."),
    ),
    # IP address format
    st.tuples(
        st.integers(min_value=1, max_value=255),
        st.integers(min_value=0, max_value=255),
        st.integers(min_value=0, max_value=255),
        st.integers(min_value=1, max_value=255),
    ).map(lambda t: f"{t[0]}.{t[1]}.{t[2]}.{t[3]}"),
    # Hostname with port
    st.text(
        min_size=1,
        max_size=30,
        alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_-."),
    ).flatmap(
        lambda host: st.integers(min_value=1, max_value=65535).map(
            lambda port: f"{host}:{port}"
        )
    ),
)

# Strategy for generating incident IDs (UUID-like)
incident_id_strategy = st.uuids().map(str)

# Strategy for generating alert names
alert_name_strategy = st.text(
    min_size=1,
    max_size=50,
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_-"),
)

# Strategy for generating severity values
severity_strategy = st.sampled_from(["P1", "P2", "P3"])

# Strategy for generating labels dictionaries
labels_strategy = st.dictionaries(
    keys=st.text(
        alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_-"),
        min_size=1,
        max_size=20,
    ),
    values=st.text(
        min_size=1,
        max_size=50,
        alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_-.:/"),
    ),
    min_size=0,
    max_size=5,
)

# Strategy for generating annotations dictionaries
annotations_strategy = st.dictionaries(
    keys=st.text(
        alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_-"),
        min_size=1,
        max_size=20,
    ),
    values=st.text(
        min_size=0,
        max_size=100,
        alphabet=st.characters(whitelist_categories=("L", "N", "P", "Z"), whitelist_characters=" "),
    ),
    min_size=0,
    max_size=5,
)

# Strategy for generating extra_vars dictionaries (alert context)
extra_vars_strategy = st.fixed_dictionaries(
    {
        "incident_id": incident_id_strategy,
        "alert_name": alert_name_strategy,
        "severity": severity_strategy,
    },
    optional={
        "labels": labels_strategy.map(lambda d: json.dumps(d)),
        "annotations": annotations_strategy.map(lambda d: json.dumps(d)),
    },
)


# --- Property 15: Executor command construction ---


class TestExecutorCommandConstruction:
    """Property tests for executor command construction (Property 15).

    **Validates: Requirements 5.1**

    For any valid playbook path, target host, and alert context (incident ID,
    alert name, severity, labels, annotations), the Remediation Executor SHALL
    construct an ansible-playbook command with the target host as inventory and
    all context fields passed as extra variables.
    """

    @given(
        playbook_path=playbook_path_strategy,
        target_host=target_host_strategy,
        extra_vars=extra_vars_strategy,
    )
    @settings(max_examples=100, deadline=5000)
    def test_command_includes_ansible_playbook(
        self,
        playbook_path: str,
        target_host: str,
        extra_vars: dict,
    ) -> None:
        """The constructed command SHALL include 'ansible-playbook' as the
        first element.

        **Validates: Requirements 5.1**
        """
        executor = RemediationExecutor()
        cmd = executor._build_command(playbook_path, target_host, extra_vars)

        assert cmd[0] == "ansible-playbook", (
            f"Expected first command element to be 'ansible-playbook', got '{cmd[0]}'"
        )

    @given(
        playbook_path=playbook_path_strategy,
        target_host=target_host_strategy,
        extra_vars=extra_vars_strategy,
    )
    @settings(max_examples=100, deadline=5000)
    def test_command_includes_inventory_flag_with_host(
        self,
        playbook_path: str,
        target_host: str,
        extra_vars: dict,
    ) -> None:
        """The constructed command SHALL include the inventory flag '-i' followed
        by the target host with a trailing comma.

        **Validates: Requirements 5.1**

        The trailing comma tells Ansible to treat the value as a host list
        rather than an inventory file path.
        """
        executor = RemediationExecutor()
        cmd = executor._build_command(playbook_path, target_host, extra_vars)

        assert "-i" in cmd, "Command must include '-i' inventory flag"
        i_index = cmd.index("-i")
        inventory_value = cmd[i_index + 1]

        assert inventory_value == f"{target_host},", (
            f"Expected inventory value '{target_host},' (host with trailing comma), "
            f"got '{inventory_value}'"
        )

    @given(
        playbook_path=playbook_path_strategy,
        target_host=target_host_strategy,
        extra_vars=extra_vars_strategy,
    )
    @settings(max_examples=100, deadline=5000)
    def test_command_includes_extra_vars_flag(
        self,
        playbook_path: str,
        target_host: str,
        extra_vars: dict,
    ) -> None:
        """The constructed command SHALL include the extra vars flag '-e' when
        extra variables are provided.

        **Validates: Requirements 5.1**

        Extra variables pass alert context (incident ID, alert name, severity,
        labels, annotations) to the Ansible playbook.
        """
        executor = RemediationExecutor()
        cmd = executor._build_command(playbook_path, target_host, extra_vars)

        if extra_vars:
            assert "-e" in cmd, (
                "Command must include '-e' flag when extra_vars are provided"
            )
            e_index = cmd.index("-e")
            extra_vars_json = cmd[e_index + 1]

            # The extra vars value should be valid JSON
            parsed = json.loads(extra_vars_json)
            assert parsed == extra_vars, (
                f"Extra vars JSON should match input. "
                f"Expected {extra_vars}, got {parsed}"
            )

    @given(
        playbook_path=playbook_path_strategy,
        target_host=target_host_strategy,
        extra_vars=extra_vars_strategy,
    )
    @settings(max_examples=100, deadline=5000)
    def test_command_includes_playbook_path(
        self,
        playbook_path: str,
        target_host: str,
        extra_vars: dict,
    ) -> None:
        """The constructed command SHALL include the playbook path.

        **Validates: Requirements 5.1**
        """
        executor = RemediationExecutor()
        cmd = executor._build_command(playbook_path, target_host, extra_vars)

        assert playbook_path in cmd, (
            f"Command must include the playbook path '{playbook_path}'. "
            f"Command was: {cmd}"
        )

    @given(
        playbook_path=playbook_path_strategy,
        target_host=target_host_strategy,
    )
    @settings(max_examples=100, deadline=5000)
    def test_command_without_extra_vars_omits_e_flag(
        self,
        playbook_path: str,
        target_host: str,
    ) -> None:
        """When no extra variables are provided (empty dict), the command SHALL
        NOT include the '-e' flag.

        **Validates: Requirements 5.1**
        """
        executor = RemediationExecutor()
        cmd = executor._build_command(playbook_path, target_host, {})

        assert "-e" not in cmd, (
            "Command should not include '-e' flag when extra_vars is empty"
        )

    @given(
        playbook_path=playbook_path_strategy,
        target_host=target_host_strategy,
        incident_id=incident_id_strategy,
        alert_name=alert_name_strategy,
        severity=severity_strategy,
        labels=labels_strategy,
        annotations=annotations_strategy,
    )
    @settings(max_examples=100, deadline=5000)
    def test_command_passes_all_context_fields_as_extra_vars(
        self,
        playbook_path: str,
        target_host: str,
        incident_id: str,
        alert_name: str,
        severity: str,
        labels: dict,
        annotations: dict,
    ) -> None:
        """The command SHALL pass all alert context fields (incident_id,
        alert_name, severity, labels, annotations) as extra variables.

        **Validates: Requirements 5.1**

        This verifies the full context is available to the Ansible playbook
        for use in remediation tasks.
        """
        extra_vars = {
            "incident_id": incident_id,
            "alert_name": alert_name,
            "severity": severity,
            "labels": json.dumps(labels),
            "annotations": json.dumps(annotations),
        }

        executor = RemediationExecutor()
        cmd = executor._build_command(playbook_path, target_host, extra_vars)

        # Verify -e flag is present
        assert "-e" in cmd, "Command must include '-e' flag for extra vars"
        e_index = cmd.index("-e")
        extra_vars_json = cmd[e_index + 1]

        # Parse and verify all context fields are present
        parsed = json.loads(extra_vars_json)
        assert parsed["incident_id"] == incident_id
        assert parsed["alert_name"] == alert_name
        assert parsed["severity"] == severity
        assert parsed["labels"] == json.dumps(labels)
        assert parsed["annotations"] == json.dumps(annotations)

    @given(
        playbook_path=playbook_path_strategy,
        target_host=target_host_strategy,
        extra_vars=extra_vars_strategy,
    )
    @settings(max_examples=100, deadline=5000)
    def test_command_structure_order(
        self,
        playbook_path: str,
        target_host: str,
        extra_vars: dict,
    ) -> None:
        """The command SHALL have ansible-playbook first, followed by the
        playbook path, then inventory flag and host, with extra vars appended.

        **Validates: Requirements 5.1**

        This ensures the command structure is valid for ansible-playbook CLI.
        The actual structure is: ansible-playbook <playbook> -i <host>, [-e <vars>]
        """
        executor = RemediationExecutor()
        cmd = executor._build_command(playbook_path, target_host, extra_vars)

        # ansible-playbook must be first
        assert cmd[0] == "ansible-playbook"

        # playbook path must come right after ansible-playbook
        playbook_index = cmd.index(playbook_path)
        assert playbook_index == 1, (
            f"Playbook path should be at index 1, got index {playbook_index}"
        )

        # -i must come after the playbook path
        i_index = cmd.index("-i")
        assert i_index > playbook_index, (
            f"'-i' flag (index {i_index}) should come after playbook path "
            f"(index {playbook_index})"
        )

        # If extra vars present, -e should come after -i and its value
        if extra_vars and "-e" in cmd:
            e_index = cmd.index("-e")
            assert e_index > i_index + 1, (
                f"'-e' flag (index {e_index}) should come after '-i' and its value "
                f"(index {i_index + 1})"
            )


# --- Property 16: Output capture and truncation ---
# Feature: self-healing-infrastructure, Property 16: Output capture and truncation


class TestOutputCaptureAndTruncation:
    """Property tests for output capture and truncation (Property 16).

    **Validates: Requirements 5.2**

    For any playbook execution that produces stdout/stderr output, the Executor
    SHALL capture the output and truncate it to 10,000 characters each.
    """

    @given(
        output_length=st.integers(min_value=0, max_value=20000),
    )
    @settings(max_examples=100, deadline=5000)
    def test_stdout_truncated_to_max_length(
        self,
        output_length: int,
    ) -> None:
        """Stdout output SHALL be truncated to MAX_OUTPUT_LENGTH (10,000) characters.

        **Validates: Requirements 5.2**
        """
        executor = RemediationExecutor(timeout=300)

        # The MAX_OUTPUT_LENGTH is 10,000
        generated_output = "x" * output_length
        stdout_bytes = generated_output.encode("utf-8")
        stderr_bytes = b""

        # Create a mock process
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(return_value=(stdout_bytes, stderr_bytes))
        mock_process.returncode = 0

        # Create a real playbook file for validation
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yml", delete=False
        ) as tmp:
            tmp.write("---\n- hosts: all\n")
            tmp_path = tmp.name

        try:
            with patch("asyncio.create_subprocess_exec", return_value=mock_process):
                result = asyncio.run(executor.execute(tmp_path, "localhost"))

            if output_length > executor.MAX_OUTPUT_LENGTH:
                assert len(result.stdout) == executor.MAX_OUTPUT_LENGTH, (
                    f"Expected stdout truncated to {executor.MAX_OUTPUT_LENGTH}, "
                    f"got {len(result.stdout)}"
                )
            else:
                assert len(result.stdout) == output_length, (
                    f"Expected stdout length {output_length}, got {len(result.stdout)}"
                )
        finally:
            os.unlink(tmp_path)

    @given(
        output_length=st.integers(min_value=0, max_value=20000),
    )
    @settings(max_examples=100, deadline=5000)
    def test_stderr_truncated_to_max_length(
        self,
        output_length: int,
    ) -> None:
        """Stderr output SHALL be truncated to MAX_OUTPUT_LENGTH (10,000) characters.

        **Validates: Requirements 5.2**
        """
        executor = RemediationExecutor(timeout=300)

        generated_output = "e" * output_length
        stdout_bytes = b""
        stderr_bytes = generated_output.encode("utf-8")

        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(return_value=(stdout_bytes, stderr_bytes))
        mock_process.returncode = 0

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yml", delete=False
        ) as tmp:
            tmp.write("---\n- hosts: all\n")
            tmp_path = tmp.name

        try:
            with patch("asyncio.create_subprocess_exec", return_value=mock_process):
                result = asyncio.run(executor.execute(tmp_path, "localhost"))

            if output_length > executor.MAX_OUTPUT_LENGTH:
                assert len(result.stderr) == executor.MAX_OUTPUT_LENGTH, (
                    f"Expected stderr truncated to {executor.MAX_OUTPUT_LENGTH}, "
                    f"got {len(result.stderr)}"
                )
            else:
                assert len(result.stderr) == output_length, (
                    f"Expected stderr length {output_length}, got {len(result.stderr)}"
                )
        finally:
            os.unlink(tmp_path)

    @given(
        stdout_len=st.integers(min_value=10001, max_value=50000),
        stderr_len=st.integers(min_value=10001, max_value=50000),
    )
    @settings(max_examples=50, deadline=5000)
    def test_both_outputs_independently_truncated(
        self,
        stdout_len: int,
        stderr_len: int,
    ) -> None:
        """Both stdout and stderr SHALL be independently truncated.

        **Validates: Requirements 5.2**
        """
        executor = RemediationExecutor(timeout=300)

        stdout_bytes = ("o" * stdout_len).encode("utf-8")
        stderr_bytes = ("e" * stderr_len).encode("utf-8")

        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(return_value=(stdout_bytes, stderr_bytes))
        mock_process.returncode = 0

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yml", delete=False
        ) as tmp:
            tmp.write("---\n- hosts: all\n")
            tmp_path = tmp.name

        try:
            with patch("asyncio.create_subprocess_exec", return_value=mock_process):
                result = asyncio.run(executor.execute(tmp_path, "localhost"))

            assert len(result.stdout) == executor.MAX_OUTPUT_LENGTH
            assert len(result.stderr) == executor.MAX_OUTPUT_LENGTH
        finally:
            os.unlink(tmp_path)


# --- Property 17: Non-zero return code marks failure ---
# Feature: self-healing-infrastructure, Property 17: Non-zero return code marks failure


class TestNonZeroReturnCodeMarksFailure:
    """Property tests for non-zero return code handling (Property 17).

    **Validates: Requirements 5.4**

    For any playbook execution that returns a non-zero exit code, the Executor
    SHALL mark the result as FAILURE.
    """

    @given(
        return_code=st.integers(min_value=1, max_value=255),
    )
    @settings(max_examples=100, deadline=5000)
    def test_nonzero_return_code_produces_failure_status(
        self,
        return_code: int,
    ) -> None:
        """Any non-zero return code SHALL result in FAILURE status.

        **Validates: Requirements 5.4**
        """
        executor = RemediationExecutor(timeout=300)

        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(return_value=(b"output", b"error"))
        mock_process.returncode = return_code

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yml", delete=False
        ) as tmp:
            tmp.write("---\n- hosts: all\n")
            tmp_path = tmp.name

        try:
            with patch("asyncio.create_subprocess_exec", return_value=mock_process):
                result = asyncio.run(executor.execute(tmp_path, "localhost"))

            assert result.status == RemediationStatus.FAILURE, (
                f"Expected FAILURE status for return code {return_code}, "
                f"got {result.status}"
            )
            assert result.return_code == return_code, (
                f"Expected return_code={return_code}, got {result.return_code}"
            )
        finally:
            os.unlink(tmp_path)

    @given(
        return_code=st.just(0),
    )
    @settings(max_examples=10, deadline=5000)
    def test_zero_return_code_produces_success_status(
        self,
        return_code: int,
    ) -> None:
        """A zero return code SHALL result in SUCCESS status.

        **Validates: Requirements 5.4**
        """
        executor = RemediationExecutor(timeout=300)

        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(return_value=(b"ok", b""))
        mock_process.returncode = return_code

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yml", delete=False
        ) as tmp:
            tmp.write("---\n- hosts: all\n")
            tmp_path = tmp.name

        try:
            with patch("asyncio.create_subprocess_exec", return_value=mock_process):
                result = asyncio.run(executor.execute(tmp_path, "localhost"))

            assert result.status == RemediationStatus.SUCCESS, (
                f"Expected SUCCESS status for return code 0, got {result.status}"
            )
        finally:
            os.unlink(tmp_path)

    @given(
        return_code=st.integers(min_value=1, max_value=255),
    )
    @settings(max_examples=100, deadline=5000)
    def test_nonzero_return_code_preserves_output(
        self,
        return_code: int,
    ) -> None:
        """Even with non-zero return code, stdout/stderr SHALL be captured.

        **Validates: Requirements 5.4**
        """
        executor = RemediationExecutor(timeout=300)

        stdout_content = f"task output for code {return_code}"
        stderr_content = f"error output for code {return_code}"

        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(
            return_value=(stdout_content.encode(), stderr_content.encode())
        )
        mock_process.returncode = return_code

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yml", delete=False
        ) as tmp:
            tmp.write("---\n- hosts: all\n")
            tmp_path = tmp.name

        try:
            with patch("asyncio.create_subprocess_exec", return_value=mock_process):
                result = asyncio.run(executor.execute(tmp_path, "localhost"))

            assert result.stdout == stdout_content, (
                f"Expected stdout='{stdout_content}', got '{result.stdout}'"
            )
            assert result.stderr == stderr_content, (
                f"Expected stderr='{stderr_content}', got '{result.stderr}'"
            )
        finally:
            os.unlink(tmp_path)


# --- Property 18: Non-existent playbook fails without subprocess ---
# Feature: self-healing-infrastructure, Property 18: Non-existent playbook fails without subprocess


# Strategy for generating non-existent playbook paths
nonexistent_path_strategy = st.one_of(
    # Absolute paths that don't exist
    st.text(
        min_size=1,
        max_size=50,
        alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_-"),
    ).map(lambda p: f"/nonexistent_dir_xyz_12345/{p}/playbook.yml"),
    # Relative paths that don't exist
    st.text(
        min_size=1,
        max_size=50,
        alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_-"),
    ).map(lambda p: f"nonexistent_relative_xyz_12345/{p}/run.yml"),
    # Paths with various extensions
    st.text(
        min_size=1,
        max_size=50,
        alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_-"),
    ).map(lambda p: f"/tmp/no_such_path_xyz_99999/{p}.yaml"),
)

# Strategy for generating target hosts for Property 18
target_host_p18_strategy = st.one_of(
    # IP addresses
    st.tuples(
        st.integers(min_value=1, max_value=254),
        st.integers(min_value=0, max_value=255),
        st.integers(min_value=0, max_value=255),
        st.integers(min_value=1, max_value=254),
    ).map(lambda t: f"{t[0]}.{t[1]}.{t[2]}.{t[3]}"),
    # Hostnames
    st.text(
        min_size=1,
        max_size=30,
        alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="-"),
    ).map(lambda h: f"{h}.example.com"),
)

# Strategy for generating extra vars for Property 18
extra_vars_p18_strategy = st.one_of(
    st.just(None),
    st.just({}),
    st.dictionaries(
        keys=st.text(
            min_size=1,
            max_size=20,
            alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_"),
        ),
        values=st.text(min_size=0, max_size=50),
        min_size=1,
        max_size=5,
    ),
)




class TestNonExistentPlaybookFailsWithoutSubprocess:
    """Property tests for non-existent playbook handling (Property 18).

    **Validates: Requirements 5.7**

    For any playbook path that does not exist or is not readable, the Executor
    SHALL return a FAILURE result with an appropriate error message without
    invoking a subprocess.
    """

    @given(
        playbook_path=nonexistent_path_strategy,
        target_host=target_host_p18_strategy,
        extra_vars=extra_vars_p18_strategy,
    )
    @settings(max_examples=100, deadline=5000)
    def test_nonexistent_playbook_returns_failure(
        self,
        playbook_path: str,
        target_host: str,
        extra_vars: dict,
    ) -> None:
        """When a non-existent playbook path is provided, execution SHALL fail
        immediately with FAILURE status.

        **Validates: Requirements 5.7**

        Strategy: Generate random non-existent paths and verify the executor
        returns a FAILURE result without attempting subprocess execution.
        """
        executor = RemediationExecutor(timeout=300)
        result = asyncio.run(executor.execute(playbook_path, target_host, extra_vars))

        assert result.status == RemediationStatus.FAILURE, (
            f"Expected FAILURE status for non-existent playbook '{playbook_path}', "
            f"but got {result.status}"
        )

    @given(
        playbook_path=nonexistent_path_strategy,
        target_host=target_host_p18_strategy,
        extra_vars=extra_vars_p18_strategy,
    )
    @settings(max_examples=100, deadline=5000)
    def test_nonexistent_playbook_no_subprocess_spawned(
        self,
        playbook_path: str,
        target_host: str,
        extra_vars: dict,
    ) -> None:
        """No subprocess SHALL be spawned for non-existent playbooks.

        **Validates: Requirements 5.7**

        Strategy: Patch asyncio.create_subprocess_exec and verify it is never
        called when the playbook path doesn't exist.
        """
        executor = RemediationExecutor(timeout=300)

        with patch("asyncio.create_subprocess_exec") as mock_subprocess:
            result = asyncio.run(
                executor.execute(playbook_path, target_host, extra_vars)
            )

            mock_subprocess.assert_not_called(), (
                f"Subprocess was spawned for non-existent playbook '{playbook_path}'. "
                "The executor should fail immediately without invoking a subprocess."
            )

        assert result.status == RemediationStatus.FAILURE

    @given(
        playbook_path=nonexistent_path_strategy,
        target_host=target_host_p18_strategy,
    )
    @settings(max_examples=100, deadline=5000)
    def test_nonexistent_playbook_error_message_indicates_not_found(
        self,
        playbook_path: str,
        target_host: str,
    ) -> None:
        """The error message SHALL indicate the playbook was not found.

        **Validates: Requirements 5.7**

        Strategy: Verify the stderr field contains information about the
        playbook path being inaccessible.
        """
        executor = RemediationExecutor(timeout=300)
        result = asyncio.run(executor.execute(playbook_path, target_host))

        # The error message should reference the playbook path
        assert playbook_path in result.stderr, (
            f"Expected error message to contain the playbook path '{playbook_path}', "
            f"but stderr was: '{result.stderr}'"
        )

        # The error message should indicate the file was not found or not readable
        error_indicators = ["not found", "not readable", "inaccessible", "does not exist"]
        has_indicator = any(
            indicator in result.stderr.lower() for indicator in error_indicators
        )
        assert has_indicator, (
            f"Expected error message to indicate playbook not found/not readable, "
            f"but stderr was: '{result.stderr}'"
        )

    @given(
        playbook_path=nonexistent_path_strategy,
        target_host=target_host_p18_strategy,
        extra_vars=extra_vars_p18_strategy,
    )
    @settings(max_examples=100, deadline=5000)
    def test_nonexistent_playbook_preserves_metadata(
        self,
        playbook_path: str,
        target_host: str,
        extra_vars: dict,
    ) -> None:
        """The ExecutionResult SHALL preserve the playbook path and target host
        even when the playbook doesn't exist.

        **Validates: Requirements 5.7**

        Strategy: Verify the result contains the correct playbook_path and
        target_host fields for traceability.
        """
        executor = RemediationExecutor(timeout=300)
        result = asyncio.run(executor.execute(playbook_path, target_host, extra_vars))

        assert result.playbook_path == playbook_path, (
            f"Expected playbook_path '{playbook_path}' in result, "
            f"but got '{result.playbook_path}'"
        )
        assert result.target_host == target_host, (
            f"Expected target_host '{target_host}' in result, "
            f"but got '{result.target_host}'"
        )

    @given(
        playbook_path=nonexistent_path_strategy,
        target_host=target_host_p18_strategy,
    )
    @settings(max_examples=100, deadline=5000)
    def test_nonexistent_playbook_zero_duration(
        self,
        playbook_path: str,
        target_host: str,
    ) -> None:
        """When a playbook doesn't exist, the execution duration SHALL be zero
        since no subprocess was invoked.

        **Validates: Requirements 5.7**

        Strategy: Verify that duration_seconds is 0.0 for non-existent playbooks,
        confirming no time was spent on subprocess execution.
        """
        executor = RemediationExecutor(timeout=300)
        result = asyncio.run(executor.execute(playbook_path, target_host))

        assert result.duration_seconds == 0.0, (
            f"Expected duration_seconds to be 0.0 for non-existent playbook, "
            f"but got {result.duration_seconds}"
        )
