"""DevOpsAgentFindings construct — email AWS DevOps Agent findings to the operator.

EventBridge rule (source ``aws.aidevops``) -> Lambda -> SES + DynamoDB audit record.

Read-only towards AWS DevOps Agent and it changes nothing on any host. IAM is scoped
to Agent Spaces tagged for this project and environment, so events from other
projects' Agent Spaces in the same account are denied and ignored by the Lambda.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import aws_cdk as cdk
import jsii
from aws_cdk import (
    Duration,
    RemovalPolicy,
    aws_cloudwatch as cloudwatch,
    aws_cloudwatch_actions as cw_actions,
    aws_dynamodb as dynamodb,
    aws_events as events,
    aws_events_targets as targets,
    aws_iam as iam,
    aws_lambda as _lambda,
    aws_logs as logs,
    aws_sns as sns,
    aws_sqs as sqs,
)
from constructs import Construct

from ..context import CdkContext

# Keep in sync with HANDLED_DETAIL_TYPES in the Lambda handler (a unit test enforces it).
FINDINGS_DETAIL_TYPES = [
    "Investigation Completed",
    "Investigation Failed",
    "Investigation Linked",
    "Investigation Timed Out",
]

# Tag applied to Agent Spaces by scripts/aiops_env.py (and the documented CLI setup).
PROJECT_TAG_VALUE = "aiops-self-healing"

_ASSET_DIR = Path(__file__).resolve().parents[2] / "lambdas" / "devops_agent_findings"

_LOG_RETENTION = {
    "dev": logs.RetentionDays.ONE_MONTH,
    "staging": logs.RetentionDays.THREE_MONTHS,
    "prod": logs.RetentionDays.ONE_YEAR,
}


@jsii.implements(cdk.ILocalBundling)
class _LocalPipBundling:
    """Bundle the handler and its pinned requirements with the local pip.

    Avoids needing Docker. Returning False makes CDK fall back to the Docker image.
    """

    def __init__(self, source_dir: Path) -> None:
        self._source_dir = source_dir

    def try_bundle(self, output_dir: str, options: cdk.BundlingOptions) -> bool:
        """Install requirements into ``output_dir`` and copy the handler."""
        try:
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "install",
                    "--quiet",
                    "--disable-pip-version-check",
                    "--only-binary=:all:",
                    "--target",
                    output_dir,
                    "-r",
                    str(self._source_dir / "requirements.txt"),
                ],
                check=True,
                timeout=600,
            )
            (Path(output_dir) / "handler.py").write_bytes(
                (self._source_dir / "handler.py").read_bytes()
            )
        except (subprocess.SubprocessError, OSError) as e:
            print(f"local bundling of the findings Lambda failed, using Docker: {e}")
            return False
        return True


class DevOpsAgentFindings(Construct):
    """Provisions the findings Lambda, its EventBridge rule, DLQ and (staging/prod) alarms.

    Exports:
        function: The Lambda function.
        dlq: The dead-letter queue for failed invocations.
        rule: The EventBridge rule.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        context: CdkContext,
        table: dynamodb.ITable,
        alarm_topic: sns.ITopic | None = None,
    ) -> None:
        """Create the resources.

        Args:
            context: Validated deployment context.
            table: Incident table; used for the idempotency/audit record.
            alarm_topic: When given, DLQ-depth and Lambda-error alarms notify it.
        """
        super().__init__(scope, construct_id)
        env_name = context.environment
        is_dev = env_name == "dev"
        region, account = context.aws_region, context.aws_account

        self.dlq = sqs.Queue(
            self,
            "Dlq",
            queue_name=f"aiops-devops-findings-dlq-{env_name}",
            retention_period=Duration.days(14),
            encryption=sqs.QueueEncryption.SQS_MANAGED,
        )

        log_group = logs.LogGroup(
            self,
            "LogGroup",
            retention=_LOG_RETENTION[env_name],
            removal_policy=RemovalPolicy.DESTROY if is_dev else RemovalPolicy.RETAIN,
        )

        self.function = _lambda.Function(
            self,
            "Function",
            function_name=f"aiops-devops-findings-{env_name}",
            description="Emails AWS DevOps Agent investigation findings to the operator",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="handler.lambda_handler",
            code=_lambda.Code.from_asset(
                str(_ASSET_DIR),
                bundling=cdk.BundlingOptions(
                    image=_lambda.Runtime.PYTHON_3_12.bundling_image,
                    command=[
                        "bash",
                        "-c",
                        "pip install -r requirements.txt -t /asset-output "
                        "&& cp handler.py /asset-output/",
                    ],
                    local=_LocalPipBundling(_ASSET_DIR),
                ),
            ),
            timeout=Duration.seconds(60),
            memory_size=256,
            log_group=log_group,
            dead_letter_queue=self.dlq,
            environment={
                "TABLE_NAME": table.table_name,
                "SES_FROM_ADDRESS": context.cost_center_email,
                "OPERATOR_EMAIL": context.cost_center_email,
                "ENVIRONMENT": env_name,
            },
        )

        # Read-only DevOps Agent access. The Agent Space id is not known at deploy time
        # (it is created by scripts/aiops_env.py), so the resource is a wildcard narrowed
        # by tags: only Agent Spaces tagged for this project and environment are readable.
        self.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["aidevops:GetBacklogTask", "aidevops:ListJournalRecords"],
                resources=[f"arn:aws:aidevops:{region}:{account}:agentspace/*"],
                conditions={
                    "StringEquals": {
                        "aws:ResourceTag/project": PROJECT_TAG_VALUE,
                        "aws:ResourceTag/environment": env_name,
                    }
                },
            )
        )
        # SES identity scope per the engineering standards (sender must be verified).
        self.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["ses:SendEmail"],
                resources=[f"arn:aws:ses:{region}:{account}:identity/*"],
            )
        )
        self.function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["dynamodb:PutItem", "dynamodb:GetItem", "dynamodb:UpdateItem"],
                resources=[table.table_arn],
            )
        )

        self.rule = events.Rule(
            self,
            "Rule",
            rule_name=f"aiops-devops-findings-{env_name}",
            description="AWS DevOps Agent investigation results -> findings Lambda",
            event_pattern=events.EventPattern(
                source=["aws.aidevops"],
                detail_type=FINDINGS_DETAIL_TYPES,
            ),
            targets=[
                targets.LambdaFunction(
                    self.function,
                    dead_letter_queue=self.dlq,
                    retry_attempts=2,
                    max_event_age=Duration.hours(1),
                )
            ],
        )

        if alarm_topic is not None:
            action = cw_actions.SnsAction(alarm_topic)
            dlq_alarm = cloudwatch.Alarm(
                self,
                "DlqNotEmptyAlarm",
                alarm_name=f"aiops-devops-findings-dlq-{env_name}",
                alarm_description="A DevOps Agent finding could not be delivered",
                metric=self.dlq.metric_approximate_number_of_messages_visible(
                    period=Duration.minutes(5), statistic="Maximum"
                ),
                threshold=1,
                evaluation_periods=1,
                comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
                treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
            )
            dlq_alarm.add_alarm_action(action)
            errors_alarm = cloudwatch.Alarm(
                self,
                "ErrorsAlarm",
                alarm_name=f"aiops-devops-findings-errors-{env_name}",
                alarm_description="The DevOps Agent findings Lambda is failing",
                metric=self.function.metric_errors(
                    period=Duration.minutes(5), statistic="Sum"
                ),
                threshold=1,
                evaluation_periods=1,
                comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
                treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
            )
            errors_alarm.add_alarm_action(action)
