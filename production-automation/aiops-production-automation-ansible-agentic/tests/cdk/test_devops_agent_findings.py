"""CDK assertions for the DevOps Agent findings construct (Phase 2)."""

from __future__ import annotations

import json

import aws_cdk as cdk
import pytest
from aws_cdk.assertions import Match, Template

from src.agentic_ai.infra.context import CdkContext
from src.agentic_ai.infra.stacks.compute_stack import ComputeStack
from src.agentic_ai.infra.stacks.data_stack import DataStack
from src.agentic_ai.infra.stacks.network_stack import NetworkStack
from src.agentic_ai.infra.stacks.observability_stack import ObservabilityStack

pytestmark = pytest.mark.cdk


def _observability_template(
    env_name: str = "dev", enabled: bool = True, advisory: bool = False
) -> Template:
    """Synthesize ObservabilityStack (bundling skipped: tests need no network or Docker)."""
    context = CdkContext(
        environment=env_name,
        aws_account="123456789012",
        aws_region="us-east-1",
        bedrock_model_id="amazon.nova-pro-v1:0",
        cost_center="platform-engineering",
        cost_center_email="platform@example.com",
        image_tag=f"abc1234-{env_name}",
        devops_agent_enabled=advisory,
        devops_agent_findings_enabled=enabled,
        devops_agent_advisory_enabled=advisory,
    )
    env = cdk.Environment(account=context.aws_account, region=context.aws_region)
    app = cdk.App(context={"aws:cdk:bundling-stacks": []})
    network = NetworkStack(app, "Network", context=context, env=env)
    data = DataStack(app, "Data", context=context, env=env)
    compute = ComputeStack(
        app, "Compute", context=context, network_stack=network, data_stack=data, env=env
    )
    stack = ObservabilityStack(
        app,
        "Observability",
        context=context,
        compute_stack=compute,
        data_stack=data,
        env=env,
    )
    return Template.from_stack(stack)


def _function(template: Template) -> dict:
    functions = template.find_resources("AWS::Lambda::Function")
    assert len(functions) == 1
    return next(iter(functions.values()))["Properties"]


def _statements(template: Template) -> list[dict]:
    out: list[dict] = []
    for resource in template.find_resources("AWS::IAM::Policy").values():
        out.extend(resource["Properties"]["PolicyDocument"]["Statement"])
    return out


class TestFlag:
    def test_enabling_without_the_data_stack_fails_early_with_a_clear_error(
        self,
    ) -> None:
        context = CdkContext(
            environment="dev",
            aws_account="123456789012",
            aws_region="us-east-1",
            bedrock_model_id="m",
            cost_center="c",
            cost_center_email="a@example.com",
            devops_agent_findings_enabled=True,
        )
        env = cdk.Environment(account=context.aws_account, region=context.aws_region)
        app = cdk.App(context={"aws:cdk:bundling-stacks": []})
        network = NetworkStack(app, "Network", context=context, env=env)
        data = DataStack(app, "Data", context=context, env=env)
        compute = ComputeStack(
            app,
            "Compute",
            context=context,
            network_stack=network,
            data_stack=data,
            env=env,
        )
        with pytest.raises(ValueError, match="requires the DataStack"):
            ObservabilityStack(
                app, "Observability", context=context, compute_stack=compute, env=env
            )

    def test_nothing_is_created_when_disabled(self) -> None:
        template = _observability_template(enabled=False)
        template.resource_count_is("AWS::Lambda::Function", 0)
        template.resource_count_is("AWS::Events::Rule", 0)

    def test_context_flag_defaults_to_off(self) -> None:
        assert (
            CdkContext(
                environment="dev",
                aws_account="123456789012",
                aws_region="us-east-1",
                bedrock_model_id="m",
                cost_center="c",
                cost_center_email="a@example.com",
            ).devops_agent_findings_enabled
            is False
        )


class TestLambda:
    def test_runtime_handler_and_limits(self) -> None:
        props = _function(_observability_template())
        assert props["Runtime"] == "python3.12"
        assert props["Handler"] == "handler.lambda_handler"
        assert (
            props["Timeout"] >= 60
        )  # engineering standard: Lambda timeout 60s minimum
        assert props["FunctionName"] == "aiops-devops-findings-dev"

    def test_environment_has_no_secrets_and_points_at_the_table(self) -> None:
        env = _function(_observability_template())["Environment"]["Variables"]
        assert set(env) == {
            "TABLE_NAME",
            "SES_FROM_ADDRESS",
            "OPERATOR_EMAIL",
            "ENVIRONMENT",
        }
        assert env["SES_FROM_ADDRESS"] == "platform@example.com"
        assert env["ENVIRONMENT"] == "dev"

    def test_failed_invocations_go_to_an_encrypted_dlq(self) -> None:
        template = _observability_template()
        props = _function(template)
        assert "TargetArn" in props["DeadLetterConfig"]
        template.has_resource_properties(
            "AWS::SQS::Queue",
            {
                "QueueName": "aiops-devops-findings-dlq-dev",
                "MessageRetentionPeriod": 14 * 24 * 3600,
                "SqsManagedSseEnabled": True,
            },
        )

    @pytest.mark.parametrize(
        ("env_name", "days"), [("dev", 30), ("staging", 90), ("prod", 365)]
    )
    def test_log_retention_follows_the_standard(self, env_name, days) -> None:
        _observability_template(env_name).has_resource_properties(
            "AWS::Logs::LogGroup", {"RetentionInDays": days}
        )


class TestRule:
    def test_matches_only_our_investigation_events(self) -> None:
        _observability_template().has_resource_properties(
            "AWS::Events::Rule",
            {
                "EventPattern": {
                    "source": ["aws.aidevops"],
                    "detail-type": [
                        "Investigation Completed",
                        "Investigation Failed",
                        "Investigation Linked",
                        "Investigation Timed Out",
                    ],
                },
                "State": "ENABLED",
            },
        )

    def test_target_is_the_function_with_retries_and_a_dlq(self) -> None:
        template = _observability_template()
        rule = next(iter(template.find_resources("AWS::Events::Rule").values()))[
            "Properties"
        ]
        (target,) = rule["Targets"]
        assert target["RetryPolicy"]["MaximumRetryAttempts"] == 2
        assert "Arn" in target["DeadLetterConfig"]

    def test_eventbridge_may_invoke_the_function(self) -> None:
        _observability_template().has_resource_properties(
            "AWS::Lambda::Permission",
            {"Action": "lambda:InvokeFunction", "Principal": "events.amazonaws.com"},
        )


class TestIam:
    def test_devops_agent_access_is_read_only_and_tag_scoped(self) -> None:
        statements = _statements(_observability_template())
        agent = [s for s in statements if "aidevops:GetBacklogTask" in _actions(s)]
        assert len(agent) == 1
        statement = agent[0]
        assert sorted(_actions(statement)) == [
            "aidevops:GetBacklogTask",
            "aidevops:ListJournalRecords",
        ]
        assert (
            statement["Resource"]
            == "arn:aws:aidevops:us-east-1:123456789012:agentspace/*"
        )
        assert statement["Condition"] == {
            "StringEquals": {
                "aws:ResourceTag/project": "aiops-self-healing",
                "aws:ResourceTag/environment": "dev",
            }
        }

    def test_tag_condition_follows_the_environment(self) -> None:
        statements = _statements(_observability_template("staging"))
        agent = next(s for s in statements if "aidevops:GetBacklogTask" in _actions(s))
        assert (
            agent["Condition"]["StringEquals"]["aws:ResourceTag/environment"]
            == "staging"
        )

    def test_no_wildcard_resources_for_the_function_role(self) -> None:
        statements = _statements(_observability_template())
        for statement in statements:
            resource = statement.get("Resource")
            assert (
                resource != "*"
            ), statement  # the function needs no account-wide access

    def test_ses_is_scoped_to_identities_and_dynamodb_to_the_one_table(self) -> None:
        statements = _statements(_observability_template())
        ses = next(s for s in statements if "ses:SendEmail" in _actions(s))
        assert ses["Resource"] == "arn:aws:ses:us-east-1:123456789012:identity/*"
        dynamo = next(s for s in statements if "dynamodb:PutItem" in _actions(s))
        assert sorted(_actions(dynamo)) == [
            "dynamodb:GetItem",
            "dynamodb:PutItem",
            "dynamodb:UpdateItem",
        ]
        assert "/index/" not in str(dynamo["Resource"])

    def test_no_write_access_to_devops_agent_or_other_services(self) -> None:
        allowed_prefixes = ("aidevops:", "ses:", "dynamodb:", "sqs:", "xray:", "logs:")
        for statement in _statements(_observability_template()):
            for action in _actions(statement):
                assert action.startswith(allowed_prefixes), action


class TestAlarms:
    def test_dev_has_no_alarms(self) -> None:
        template = _observability_template("dev")
        names = [
            r["Properties"].get("AlarmName", "")
            for r in template.find_resources("AWS::CloudWatch::Alarm").values()
        ]
        assert not [n for n in names if "devops-findings" in str(n)]

    @pytest.mark.parametrize("env_name", ["staging", "prod"])
    def test_staging_and_prod_alarm_on_dlq_and_errors(self, env_name) -> None:
        template = _observability_template(env_name)
        template.has_resource_properties(
            "AWS::CloudWatch::Alarm",
            {
                "AlarmName": f"aiops-devops-findings-dlq-{env_name}",
                "MetricName": "ApproximateNumberOfMessagesVisible",
                "Threshold": 1,
                "AlarmActions": Match.any_value(),
            },
        )
        template.has_resource_properties(
            "AWS::CloudWatch::Alarm",
            {
                "AlarmName": f"aiops-devops-findings-errors-{env_name}",
                "MetricName": "Errors",
                "AlarmActions": Match.any_value(),
            },
        )


class TestAdvisoryMode:
    """devopsAgentAdvisoryEnabled adds the mitigation request and the Bedrock call."""

    def test_off_keeps_the_function_small_and_read_only(self) -> None:
        template = _observability_template()
        props = _function(template)
        assert props["Timeout"] == 60
        assert "ADVISORY_MODE" not in props["Environment"]["Variables"]
        actions = {a for s in _statements(template) for a in _actions(s)}
        assert not {"bedrock:InvokeModel", "aidevops:UpdateBacklogTask"} & actions

    def test_function_gets_the_longest_timeout_and_the_settings(self) -> None:
        props = _function(_observability_template(advisory=True))
        assert props["Timeout"] == 900
        env = props["Environment"]["Variables"]
        assert env["ADVISORY_MODE"] == "true"
        assert env["BEDROCK_MODEL_ID"] == "amazon.nova-pro-v1:0"
        assert set(env) == {
            "TABLE_NAME",
            "SES_FROM_ADDRESS",
            "OPERATOR_EMAIL",
            "ENVIRONMENT",
            "ADVISORY_MODE",
            "BEDROCK_MODEL_ID",
        }

    def test_mitigation_request_is_tag_scoped_like_the_read_access(self) -> None:
        statements = _statements(_observability_template(advisory=True))
        write = next(
            s for s in statements if "aidevops:UpdateBacklogTask" in _actions(s)
        )
        assert sorted(_actions(write)) == [
            "aidevops:ListExecutions",
            "aidevops:UpdateBacklogTask",
        ]
        assert (
            write["Resource"] == "arn:aws:aidevops:us-east-1:123456789012:agentspace/*"
        )
        assert write["Condition"] == {
            "StringEquals": {
                "aws:ResourceTag/project": "aiops-self-healing",
                "aws:ResourceTag/environment": "dev",
            }
        }

    def test_bedrock_matches_the_task_role_scope(self) -> None:
        statements = _statements(_observability_template(advisory=True))
        bedrock = next(s for s in statements if "bedrock:InvokeModel" in _actions(s))
        assert _actions(bedrock) == ["bedrock:InvokeModel"]
        assert bedrock["Resource"] == [
            "arn:aws:bedrock:us-east-1::foundation-model/*",
            "arn:aws:bedrock:us-east-2::foundation-model/*",
            "arn:aws:bedrock:us-west-2::foundation-model/*",
            "arn:aws:bedrock:us-east-1:123456789012:inference-profile/us.*",
        ]

    def test_no_account_wide_resources_and_only_expected_services(self) -> None:
        allowed = (
            "aidevops:",
            "ses:",
            "dynamodb:",
            "sqs:",
            "xray:",
            "logs:",
            "bedrock:",
        )
        for statement in _statements(_observability_template(advisory=True)):
            assert statement.get("Resource") != "*", statement
            for action in _actions(statement):
                assert action.startswith(allowed), action

    def test_the_rule_still_matches_only_investigation_events(self) -> None:
        # Advisory mode polls for the mitigation plan, so it needs no Mitigation* events.
        rule = next(
            iter(
                _observability_template(advisory=True)
                .find_resources("AWS::Events::Rule")
                .values()
            )
        )["Properties"]
        assert all(
            t.startswith("Investigation") for t in rule["EventPattern"]["detail-type"]
        )

    def test_the_playbook_catalog_is_generated_next_to_the_handler(self) -> None:
        from pathlib import Path

        _observability_template(advisory=True)
        generated = (
            Path(__file__).resolve().parents[2]
            / "src/agentic_ai/lambdas/devops_agent_findings/advisory_context.json"
        )
        data = json.loads(generated.read_text(encoding="utf-8"))
        paths = {p["path"] for p in data["playbooks"]}
        assert "playbooks/fix_high_memory.yml" in paths
        assert data["denied_patterns"]


def _actions(statement: dict) -> list[str]:
    actions = statement.get("Action", [])
    return [actions] if isinstance(actions, str) else list(actions)
