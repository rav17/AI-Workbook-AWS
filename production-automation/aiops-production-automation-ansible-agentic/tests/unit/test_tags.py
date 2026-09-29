"""Unit tests for the standard tagging utility."""

from unittest.mock import patch, MagicMock, call

import pytest

from src.agentic_ai.infra.context import CdkContext


def _make_context(
    environment: str = "dev",
    cost_center: str = "platform-engineering",
) -> CdkContext:
    """Create a CdkContext with sensible defaults for testing."""
    return CdkContext(
        environment=environment,
        aws_account="123456789012",
        aws_region="us-east-1",
        bedrock_model_id="anthropic.claude-3-sonnet-20240229-v1:0",
        cost_center=cost_center,
        cost_center_email="platform@example.com",
    )


class TestApplyStandardTags:
    """Tests for apply_standard_tags function."""

    def _call_with_mock(self, context, scope=None):
        """Call apply_standard_tags with Tags mocked at the module level."""
        if scope is None:
            scope = MagicMock()
        mock_tags_of = MagicMock()
        with patch("src.agentic_ai.infra.tags.Tags") as mock_tags_class:
            mock_tags_class.of.return_value = mock_tags_of
            from src.agentic_ai.infra.tags import apply_standard_tags

            apply_standard_tags(scope, context)
        return mock_tags_class, mock_tags_of, scope

    def test_applies_project_tag(self):
        context = _make_context()
        _, mock_tags_of, _ = self._call_with_mock(context)
        mock_tags_of.add.assert_any_call("project", "aiops-self-healing")

    def test_applies_environment_tag(self):
        context = _make_context(environment="prod")
        _, mock_tags_of, _ = self._call_with_mock(context)
        mock_tags_of.add.assert_any_call("environment", "prod")

    def test_applies_managed_by_tag(self):
        context = _make_context()
        _, mock_tags_of, _ = self._call_with_mock(context)
        mock_tags_of.add.assert_any_call("managed-by", "cdk")

    def test_applies_cost_center_tag(self):
        context = _make_context(cost_center="data-science")
        _, mock_tags_of, _ = self._call_with_mock(context)
        mock_tags_of.add.assert_any_call("cost-center", "data-science")

    def test_applies_all_four_tags(self):
        context = _make_context(environment="staging", cost_center="ml-ops")
        _, mock_tags_of, _ = self._call_with_mock(context)
        assert mock_tags_of.add.call_count == 4
        expected_calls = [
            call("project", "aiops-self-healing"),
            call("environment", "staging"),
            call("managed-by", "cdk"),
            call("cost-center", "ml-ops"),
        ]
        mock_tags_of.add.assert_has_calls(expected_calls)

    def test_uses_tags_of_with_scope(self):
        scope = MagicMock()
        context = _make_context()
        mock_tags_class, _, _ = self._call_with_mock(context, scope=scope)
        mock_tags_class.of.assert_called_with(scope)

    def test_empty_cost_center_raises_valueerror(self):
        from src.agentic_ai.infra.tags import apply_standard_tags

        scope = MagicMock()
        context = _make_context(cost_center="")

        with pytest.raises(ValueError, match="cost-center tag cannot be empty"):
            apply_standard_tags(scope, context)

    def test_whitespace_cost_center_raises_valueerror(self):
        from src.agentic_ai.infra.tags import apply_standard_tags

        scope = MagicMock()
        context = _make_context(cost_center="   ")

        with pytest.raises(ValueError, match="cost-center tag cannot be empty"):
            apply_standard_tags(scope, context)

    @pytest.mark.parametrize("env", ["dev", "staging", "prod"])
    def test_all_environments_tagged_correctly(self, env):
        context = _make_context(environment=env)
        _, mock_tags_of, _ = self._call_with_mock(context)
        mock_tags_of.add.assert_any_call("environment", env)
