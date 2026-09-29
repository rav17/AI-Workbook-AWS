"""ObservabilityStack — CloudWatch alarms, dashboard, SNS, synthetics, budgets."""

from typing import Any

import aws_cdk as cdk
from aws_cdk import (
    Duration,
    RemovalPolicy,
    aws_budgets as budgets,
    aws_cloudwatch as cloudwatch,
    aws_cloudwatch_actions as cw_actions,
    aws_iam as iam,
    aws_logs as logs,
    aws_s3 as s3,
    aws_sns as sns,
    aws_synthetics as synthetics,
)
from constructs import Construct

from ..context import CdkContext
from .compute_stack import ComputeStack
from .data_stack import DataStack

# Default monthly budget limits per environment (USD)
_DEFAULT_BUDGET_LIMITS: dict[str, int] = {
    "dev": 200,
    "staging": 500,
    "prod": 2000,
}


class ObservabilityStack(cdk.Stack):
    """Provisions CloudWatch alarms, dashboard, SNS topic, synthetics canary, and budgets.

    Receives cross-stack references from ComputeStack and DataStack via
    constructor parameters.

    Exports:
        alarm_topic: The SNS topic for alarm notifications.
        dashboard: The CloudWatch dashboard.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        context: CdkContext,
        compute_stack: ComputeStack,
        data_stack: DataStack | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)
        self._context = context
        self._compute_stack = compute_stack
        self._data_stack = data_stack

        env_name = context.environment
        is_dev = env_name == "dev"

        # --- SNS Topic (all environments) ---
        self.alarm_topic = sns.Topic(
            self,
            "AlarmTopic",
            topic_name=f"aiops-alarms-{env_name}",
            display_name=f"AIOps Alarms - {env_name}",
        )

        # --- CloudWatch Alarms (staging/prod only) ---
        # Dev environment: no alarms created (Requirement 5.2)
        if not is_dev:
            self._create_alarms(env_name, compute_stack, data_stack)

        # --- CloudWatch Dashboard (staging/prod only) ---
        if not is_dev:
            self._create_dashboard(env_name, compute_stack, data_stack)
        else:
            self.dashboard = None

        # --- CloudWatch Synthetics Canary (staging/prod only; Requirement 10.6) ---
        if not is_dev:
            self._create_synthetics_canary(env_name)

        # --- AWS Budgets (all environments) ---
        self._create_budget()

        # --- WAF WebACL for API Gateway (staging/prod only) ---
        if not is_dev:
            self._create_waf(env_name, compute_stack)

        # --- DORA Metrics Dashboard (staging/prod only) ---
        if not is_dev:
            self._create_dora_dashboard(env_name)

    def _create_alarms(
        self,
        env_name: str,
        compute_stack: ComputeStack,
        data_stack: DataStack | None,
    ) -> None:
        """Create 4 core CloudWatch alarms + composite rollback alarm.

        Requirements 2.8, 2.12, 7.5:
        - DLQ depth > 5 messages (1×1min)
        - AI reasoning latency p95 > 15000ms (2×5min)
        - Remediation failure rate > 30% (2×5min)
        - ECS unhealthy task count > 0 (1×1min)
        - Composite alarm: ECS unhealthy AND DLQ depth for 5+ min
        """
        alarm_action = cw_actions.SnsAction(self.alarm_topic)

        # Determine DLQ queue name
        dlq_queue_name = (
            data_stack.dlq.queue_name if data_stack else f"aiops-dlq-{env_name}"
        )

        # --- Alarm 1: DLQ Depth ---
        dlq_depth_metric = cloudwatch.Metric(
            metric_name="ApproximateNumberOfMessagesVisible",
            namespace="AWS/SQS",
            dimensions_map={"QueueName": dlq_queue_name},
            period=Duration.minutes(1),
            statistic="Maximum",
        )

        self.dlq_depth_alarm = cloudwatch.Alarm(
            self,
            "DlqDepthAlarm",
            alarm_name=f"DlqDepth-{env_name}",
            alarm_description=(
                f"DLQ has more than 5 messages visible in {env_name} environment"
            ),
            metric=dlq_depth_metric,
            threshold=5,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            evaluation_periods=1,
            datapoints_to_alarm=1,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )
        self.dlq_depth_alarm.add_alarm_action(alarm_action)

        # --- Alarm 2: AI Reasoning Latency P95 ---
        ai_latency_metric = cloudwatch.Metric(
            metric_name="AIReasoningLatency",
            namespace=f"AIOps/{env_name}",
            period=Duration.minutes(5),
            statistic="p95",
        )

        self.ai_latency_alarm = cloudwatch.Alarm(
            self,
            "AILatencyP95Alarm",
            alarm_name=f"AILatencyP95-{env_name}",
            alarm_description=(
                f"AI reasoning latency p95 exceeds 15 seconds in {env_name}"
            ),
            metric=ai_latency_metric,
            threshold=15000,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            evaluation_periods=2,
            datapoints_to_alarm=2,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )
        self.ai_latency_alarm.add_alarm_action(alarm_action)

        # --- Alarm 3: Remediation Failure Rate (Metric Math) ---
        failure_count_metric = cloudwatch.Metric(
            metric_name="RemediationFailureCount",
            namespace=f"AIOps/{env_name}",
            period=Duration.minutes(5),
            statistic="Sum",
        )

        total_executed_metric = cloudwatch.Metric(
            metric_name="RemediationsExecuted",
            namespace=f"AIOps/{env_name}",
            period=Duration.minutes(5),
            statistic="Sum",
        )

        failure_rate_expression = cloudwatch.MathExpression(
            expression="(failures / total) * 100",
            using_metrics={
                "failures": failure_count_metric,
                "total": total_executed_metric,
            },
            period=Duration.minutes(5),
            label="Remediation Failure Rate (%)",
        )

        self.remediation_failure_alarm = cloudwatch.Alarm(
            self,
            "RemediationFailureRateAlarm",
            alarm_name=f"RemediationFailureRate-{env_name}",
            alarm_description=(
                f"Remediation failure rate exceeds 30% in {env_name}"
            ),
            metric=failure_rate_expression,
            threshold=30,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            evaluation_periods=2,
            datapoints_to_alarm=2,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )
        self.remediation_failure_alarm.add_alarm_action(alarm_action)

        # --- Alarm 4: ECS Unhealthy Tasks ---
        ecs_unhealthy_metric = cloudwatch.Metric(
            metric_name="UnhealthyTaskCount",
            namespace="AWS/ECS",
            dimensions_map={
                "ClusterName": compute_stack.cluster.cluster_name,
                "ServiceName": compute_stack.service.service_name,
            },
            period=Duration.minutes(1),
            statistic="Maximum",
        )

        self.ecs_unhealthy_alarm = cloudwatch.Alarm(
            self,
            "EcsUnhealthyTasksAlarm",
            alarm_name=f"EcsUnhealthyTasks-{env_name}",
            alarm_description=(
                f"ECS service has unhealthy tasks in {env_name}"
            ),
            metric=ecs_unhealthy_metric,
            threshold=0,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            evaluation_periods=1,
            datapoints_to_alarm=1,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )
        self.ecs_unhealthy_alarm.add_alarm_action(alarm_action)

        # --- Composite Alarm: RollbackRequired (Requirement 7.5) ---
        # Fires when BOTH EcsUnhealthyTasks AND DlqDepth are in ALARM
        # for 5+ minutes continuously.
        cloudwatch.CfnCompositeAlarm(
            self,
            "RollbackRequiredAlarm",
            alarm_name=f"RollbackRequired-{env_name}",
            alarm_description=(
                f"Both ECS unhealthy tasks and DLQ depth alarms active for 5+ min in {env_name}. "
                "Manual or automated rollback may be needed."
            ),
            alarm_rule=(
                f"ALARM(\"{self.ecs_unhealthy_alarm.alarm_arn}\") AND "
                f"ALARM(\"{self.dlq_depth_alarm.alarm_arn}\")"
            ),
            actions_enabled=True,
            alarm_actions=[self.alarm_topic.topic_arn],
            actions_suppressor=None,
            actions_suppressor_extension_period=None,
            actions_suppressor_wait_period=None,
        )

    def _create_dashboard(
        self,
        env_name: str,
        compute_stack: ComputeStack,
        data_stack: DataStack | None,
    ) -> None:
        """Create CloudWatch dashboard with specified widget layout.

        Layout (24-unit wide grid):
        - Row 1: ECS Task Count (8w) | SQS Queue Depth (8w) | DLQ Depth (8w)
        - Row 2: AI Reasoning Latency p50/p95/p99 (12w) | Bedrock Invocations+Errors (12w)
        - Row 3: Remediation Success/Failure/Escalation (12w) | ECS CPU+Memory (12w)
        """
        # Determine queue names
        main_queue_name = (
            data_stack.queue.queue_name if data_stack else f"aiops-main-{env_name}"
        )
        dlq_queue_name = (
            data_stack.dlq.queue_name if data_stack else f"aiops-dlq-{env_name}"
        )

        cluster_name = compute_stack.cluster.cluster_name
        service_name = compute_stack.service.service_name

        # --- Row 1 Widgets ---

        # ECS Task Count (current vs desired)
        ecs_task_count_widget = cloudwatch.GraphWidget(
            title="ECS Task Count",
            width=8,
            left=[
                cloudwatch.Metric(
                    metric_name="DesiredTaskCount",
                    namespace="ECS/ContainerInsights",
                    dimensions_map={
                        "ClusterName": cluster_name,
                        "ServiceName": service_name,
                    },
                    period=Duration.minutes(1),
                    statistic="Average",
                    label="Desired",
                ),
                cloudwatch.Metric(
                    metric_name="RunningTaskCount",
                    namespace="ECS/ContainerInsights",
                    dimensions_map={
                        "ClusterName": cluster_name,
                        "ServiceName": service_name,
                    },
                    period=Duration.minutes(1),
                    statistic="Average",
                    label="Running",
                ),
            ],
        )

        # SQS Main Queue Depth
        sqs_queue_depth_widget = cloudwatch.GraphWidget(
            title="SQS Queue Depth",
            width=8,
            left=[
                cloudwatch.Metric(
                    metric_name="ApproximateNumberOfMessagesVisible",
                    namespace="AWS/SQS",
                    dimensions_map={"QueueName": main_queue_name},
                    period=Duration.minutes(1),
                    statistic="Maximum",
                    label="Messages Visible",
                ),
            ],
        )

        # DLQ Depth
        dlq_depth_widget = cloudwatch.GraphWidget(
            title="DLQ Depth",
            width=8,
            left=[
                cloudwatch.Metric(
                    metric_name="ApproximateNumberOfMessagesVisible",
                    namespace="AWS/SQS",
                    dimensions_map={"QueueName": dlq_queue_name},
                    period=Duration.minutes(1),
                    statistic="Maximum",
                    label="DLQ Messages",
                ),
            ],
        )

        # --- Row 2 Widgets ---

        # AI Reasoning Latency (p50, p95, p99)
        ai_latency_widget = cloudwatch.GraphWidget(
            title="AI Reasoning Latency",
            width=12,
            left=[
                cloudwatch.Metric(
                    metric_name="AIReasoningLatency",
                    namespace=f"AIOps/{env_name}",
                    period=Duration.minutes(5),
                    statistic="p50",
                    label="p50",
                ),
                cloudwatch.Metric(
                    metric_name="AIReasoningLatency",
                    namespace=f"AIOps/{env_name}",
                    period=Duration.minutes(5),
                    statistic="p95",
                    label="p95",
                ),
                cloudwatch.Metric(
                    metric_name="AIReasoningLatency",
                    namespace=f"AIOps/{env_name}",
                    period=Duration.minutes(5),
                    statistic="p99",
                    label="p99",
                ),
            ],
        )

        # Bedrock Invocations + Errors
        bedrock_widget = cloudwatch.GraphWidget(
            title="Bedrock Invocations & Errors",
            width=12,
            left=[
                cloudwatch.Metric(
                    metric_name="AIReasoningInvocations",
                    namespace=f"AIOps/{env_name}",
                    period=Duration.minutes(5),
                    statistic="Sum",
                    label="Invocations",
                ),
                cloudwatch.Metric(
                    metric_name="BedrockThrottleCount",
                    namespace=f"AIOps/{env_name}",
                    period=Duration.minutes(5),
                    statistic="Sum",
                    label="Throttles",
                ),
            ],
        )

        # --- Row 3 Widgets ---

        # Remediation Success/Failure/Escalation
        remediation_widget = cloudwatch.GraphWidget(
            title="Remediation Outcomes",
            width=12,
            left=[
                cloudwatch.Metric(
                    metric_name="RemediationSuccessCount",
                    namespace=f"AIOps/{env_name}",
                    period=Duration.minutes(5),
                    statistic="Sum",
                    label="Success",
                ),
                cloudwatch.Metric(
                    metric_name="RemediationFailureCount",
                    namespace=f"AIOps/{env_name}",
                    period=Duration.minutes(5),
                    statistic="Sum",
                    label="Failure",
                ),
                cloudwatch.Metric(
                    metric_name="HumanEscalationsCount",
                    namespace=f"AIOps/{env_name}",
                    period=Duration.minutes(5),
                    statistic="Sum",
                    label="Escalation",
                ),
            ],
        )

        # ECS CPU + Memory Utilization
        ecs_resource_widget = cloudwatch.GraphWidget(
            title="ECS CPU & Memory Utilization",
            width=12,
            left=[
                cloudwatch.Metric(
                    metric_name="CpuUtilized",
                    namespace="ECS/ContainerInsights",
                    dimensions_map={
                        "ClusterName": cluster_name,
                        "ServiceName": service_name,
                    },
                    period=Duration.minutes(1),
                    statistic="Average",
                    label="CPU %",
                ),
                cloudwatch.Metric(
                    metric_name="MemoryUtilized",
                    namespace="ECS/ContainerInsights",
                    dimensions_map={
                        "ClusterName": cluster_name,
                        "ServiceName": service_name,
                    },
                    period=Duration.minutes(1),
                    statistic="Average",
                    label="Memory %",
                ),
            ],
        )

        # --- Assemble Dashboard ---
        self.dashboard = cloudwatch.Dashboard(
            self,
            "Dashboard",
            dashboard_name=f"AIOps-{env_name}",
            widgets=[
                # Row 1: ECS Tasks | SQS Depth | DLQ Depth
                [ecs_task_count_widget, sqs_queue_depth_widget, dlq_depth_widget],
                # Row 2: AI Latency | Bedrock Invocations
                [ai_latency_widget, bedrock_widget],
                # Row 3: Remediation Outcomes | ECS Resources
                [remediation_widget, ecs_resource_widget],
            ],
        )

    def _create_synthetics_canary(self, env_name: str) -> None:
        """Create CloudWatch Synthetics canary for staging/prod environments.

        The canary POSTs a synthetic Alertmanager payload to the API Gateway
        /webhook endpoint every 5 minutes and asserts HTTP 200 within 2 seconds.

        Requirements:
            9.5: CloudWatch Synthetics canary for endpoint monitoring.
            10.6: Dev environment excluded from canary creation.
        """
        region = self._context.aws_region
        account = self._context.aws_account

        # --- S3 Bucket for canary artifacts ---
        canary_artifacts_bucket = s3.Bucket(
            self,
            "CanaryArtifactsBucket",
            bucket_name=f"aiops-canary-artifacts-{env_name}-{account}",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            encryption=s3.BucketEncryption.S3_MANAGED,
            lifecycle_rules=[
                s3.LifecycleRule(
                    expiration=Duration.days(30),
                    id="expire-canary-artifacts",
                )
            ],
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
        )

        # --- Canary Log Group: /aiops/{env}/canary with 30-day retention ---
        canary_log_group = logs.LogGroup(
            self,
            "CanaryLogGroup",
            log_group_name=f"/aiops/{env_name}/canary",
            retention=logs.RetentionDays.ONE_MONTH,
            removal_policy=RemovalPolicy.DESTROY,
        )

        # --- IAM Role for canary execution ---
        canary_role = iam.Role(
            self,
            "CanaryRole",
            role_name=f"aiops-canary-role-{env_name}",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description=f"Execution role for AIOps synthetics canary ({env_name})",
        )

        # S3 permissions for canary artifacts
        canary_artifacts_bucket.grant_read_write(canary_role)

        # CloudWatch Logs permissions for canary log group
        canary_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                ],
                resources=[
                    canary_log_group.log_group_arn,
                    canary_log_group.log_group_arn + ":*",
                ],
            )
        )

        # CloudWatch metrics publishing (required by Synthetics runtime)
        canary_role.add_to_policy(
            iam.PolicyStatement(
                actions=["cloudwatch:PutMetricData"],
                resources=["*"],  # CloudWatch PutMetricData requires * (AWS-mandated)
            )
        )

        # S3 GetBucketLocation (required by Synthetics runtime)
        canary_role.add_to_policy(
            iam.PolicyStatement(
                actions=["s3:GetBucketLocation"],
                resources=[canary_artifacts_bucket.bucket_arn],
            )
        )

        # S3 list permissions for artifact prefix (required by Synthetics runtime)
        canary_role.add_to_policy(
            iam.PolicyStatement(
                actions=["s3:ListAllMyBuckets"],
                resources=["*"],
            )
        )

        # --- Canary inline script ---
        # POSTs a synthetic Alertmanager payload to /webhook, asserts HTTP 200 within 2s
        canary_script = self._get_canary_script()

        # --- CfnCanary (using L1 construct for stable API) ---
        # Use the real API endpoint from ComputeStack
        api_endpoint = self._compute_stack.api_url

        synthetics.CfnCanary(
            self,
            "SyntheticsCanary",
            name=f"aiops-canary-{env_name}",
            artifact_s3_location=f"s3://{canary_artifacts_bucket.bucket_name}/",
            execution_role_arn=canary_role.role_arn,
            runtime_version="syn-python-selenium-3.0",
            schedule=synthetics.CfnCanary.ScheduleProperty(
                expression="rate(5 minutes)",
            ),
            start_canary_after_creation=True,
            code=synthetics.CfnCanary.CodeProperty(
                handler="index.handler",
                script=canary_script,
            ),
            run_config=synthetics.CfnCanary.RunConfigProperty(
                timeout_in_seconds=60,
                environment_variables={
                    "API_ENDPOINT": api_endpoint,
                },
            ),
            success_retention_period=30,
            failure_retention_period=30,
        )

        # --- Canary Alarm: triggers SNS after 2 consecutive failures ---
        canary_alarm = cloudwatch.Alarm(
            self,
            "CanaryAlarm",
            alarm_name=f"CanaryFailed-{env_name}",
            alarm_description=(
                f"AIOps synthetics canary ({env_name}) has failed 2 consecutive times. "
                "The /webhook endpoint may be unreachable or returning errors."
            ),
            metric=cloudwatch.Metric(
                metric_name="SuccessPercent",
                namespace="CloudWatchSynthetics",
                dimensions_map={"CanaryName": f"aiops-canary-{env_name}"},
                period=Duration.minutes(5),
                statistic="Average",
            ),
            threshold=100,
            comparison_operator=cloudwatch.ComparisonOperator.LESS_THAN_THRESHOLD,
            evaluation_periods=2,
            datapoints_to_alarm=2,
            treat_missing_data=cloudwatch.TreatMissingData.BREACHING,
        )

        # Wire canary alarm to the SNS topic
        canary_alarm.add_alarm_action(cw_actions.SnsAction(self.alarm_topic))

        # --- CfnOutputs ---
        cdk.CfnOutput(
            self,
            "CanaryName",
            value=f"aiops-canary-{env_name}",
            export_name=f"AiopsCanaryName-{env_name}",
        )
        cdk.CfnOutput(
            self,
            "CanaryArtifactsBucketOutput",
            value=canary_artifacts_bucket.bucket_name,
            export_name=f"AiopsCanaryBucket-{env_name}",
        )

    @staticmethod
    def _get_canary_script() -> str:
        """Return the inline Python script for the CloudWatch Synthetics canary.

        The script POSTs a synthetic Alertmanager payload to the API Gateway
        /webhook endpoint and asserts HTTP 200 response within 2 seconds.
        """
        return '''\
import json
import http.client
import os
import ssl
import time


def handler(event, context):
    """CloudWatch Synthetics canary handler.

    POSTs a synthetic Alertmanager payload to the /webhook endpoint
    and asserts HTTP 200 within 2 seconds.
    """
    api_endpoint = os.environ.get("API_ENDPOINT", "")
    # Parse the endpoint URL to extract host and path base
    # Expected format: https://{id}.execute-api.{region}.amazonaws.com/{stage}
    if api_endpoint.startswith("https://"):
        api_endpoint = api_endpoint[len("https://"):]
    elif api_endpoint.startswith("http://"):
        api_endpoint = api_endpoint[len("http://"):]

    # Split host and base path
    parts = api_endpoint.split("/", 1)
    host = parts[0]
    base_path = "/" + parts[1] if len(parts) > 1 else ""
    webhook_path = f"{base_path}/webhook"

    # Synthetic Alertmanager payload
    payload = json.dumps({
        "version": "4",
        "groupKey": "canary-test",
        "status": "firing",
        "receiver": "aiops",
        "alerts": [
            {
                "status": "firing",
                "labels": {
                    "alertname": "SyntheticCanaryTest",
                    "severity": "info",
                    "service": "canary",
                    "instance": "synthetic",
                },
                "annotations": {
                    "summary": "Synthetic canary health check",
                    "description": "This is a synthetic alert from CloudWatch Synthetics canary.",
                },
                "startsAt": "2024-01-01T00:00:00Z",
                "generatorURL": "http://canary/synthetic",
            }
        ],
    })

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "CloudWatch-Synthetics-Canary",
        "X-Canary-Test": "true",
    }

    start_time = time.time()

    conn = http.client.HTTPSConnection(host, timeout=2)
    try:
        conn.request("POST", webhook_path, body=payload, headers=headers)
        response = conn.getresponse()
        elapsed = time.time() - start_time

        status_code = response.status
        body = response.read().decode("utf-8", errors="replace")

        if status_code != 200:
            raise Exception(
                f"Expected HTTP 200, got {status_code}. Body: {body[:500]}"
            )
        if elapsed > 2.0:
            raise Exception(
                f"Response took {elapsed:.2f}s, exceeded 2s threshold."
            )

        return {
            "statusCode": status_code,
            "elapsed": round(elapsed, 3),
            "body": body[:200],
        }
    finally:
        conn.close()
'''

    def _create_waf(self, env_name: str, compute_stack: ComputeStack) -> None:
        """Create AWS WAF WebACL for API Gateway webhook protection.

        Rules:
        1. Rate limit: 100 requests per 5 minutes per IP
        2. Size constraint: Block requests > 1 MB
        3. AWS Managed Rules: Common Rule Set (XSS, SQLi protection)

        The WebACL is REGIONAL scope (required for API Gateway).
        Cost: ~$8-9/month (WebACL + rules + request inspection).
        """
        from aws_cdk import aws_wafv2 as wafv2

        # --- Rate-based rule: 100 requests / 5 min per IP ---
        rate_limit_rule = wafv2.CfnWebACL.RuleProperty(
            name="RateLimitPerIP",
            priority=1,
            action=wafv2.CfnWebACL.RuleActionProperty(block={}),
            statement=wafv2.CfnWebACL.StatementProperty(
                rate_based_statement=wafv2.CfnWebACL.RateBasedStatementProperty(
                    limit=100,  # 100 requests per 5-minute window per IP
                    aggregate_key_type="IP",
                ),
            ),
            visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
                sampled_requests_enabled=True,
                cloud_watch_metrics_enabled=True,
                metric_name=f"AiopsRateLimit-{env_name}",
            ),
        )

        # --- Size constraint: block > 1 MB request bodies ---
        size_constraint_rule = wafv2.CfnWebACL.RuleProperty(
            name="MaxBodySize",
            priority=2,
            action=wafv2.CfnWebACL.RuleActionProperty(block={}),
            statement=wafv2.CfnWebACL.StatementProperty(
                size_constraint_statement=wafv2.CfnWebACL.SizeConstraintStatementProperty(
                    field_to_match=wafv2.CfnWebACL.FieldToMatchProperty(body={}),
                    comparison_operator="GT",
                    size=1048576,  # 1 MB
                    text_transformations=[
                        wafv2.CfnWebACL.TextTransformationProperty(
                            priority=0, type="NONE"
                        )
                    ],
                ),
            ),
            visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
                sampled_requests_enabled=True,
                cloud_watch_metrics_enabled=True,
                metric_name=f"AiopsBodySize-{env_name}",
            ),
        )

        # --- AWS Managed Rules: Common Rule Set (XSS, SQLi, bad bots) ---
        managed_rules = wafv2.CfnWebACL.RuleProperty(
            name="AWSManagedCommonRules",
            priority=3,
            override_action=wafv2.CfnWebACL.OverrideActionProperty(none={}),
            statement=wafv2.CfnWebACL.StatementProperty(
                managed_rule_group_statement=wafv2.CfnWebACL.ManagedRuleGroupStatementProperty(
                    vendor_name="AWS",
                    name="AWSManagedRulesCommonRuleSet",
                ),
            ),
            visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
                sampled_requests_enabled=True,
                cloud_watch_metrics_enabled=True,
                metric_name=f"AiopsManagedRules-{env_name}",
            ),
        )

        # --- WebACL ---
        self.waf_acl = wafv2.CfnWebACL(
            self,
            "WafWebAcl",
            name=f"aiops-waf-{env_name}",
            scope="REGIONAL",
            default_action=wafv2.CfnWebACL.DefaultActionProperty(allow={}),
            description=f"WAF for AIOps API Gateway ({env_name})",
            rules=[rate_limit_rule, size_constraint_rule, managed_rules],
            visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
                sampled_requests_enabled=True,
                cloud_watch_metrics_enabled=True,
                metric_name=f"AiopsWaf-{env_name}",
            ),
        )

        # --- Associate WebACL with API Gateway ---
        # Use the HTTP API ID stored on ComputeStack for a reliable ARN
        api_id = compute_stack.http_api_id
        api_arn = (
            f"arn:aws:apigateway:{self._context.aws_region}::"
            f"/apis/{api_id}/stages/$default"
        )

        wafv2.CfnWebACLAssociation(
            self,
            "WafAssociation",
            resource_arn=api_arn,
            web_acl_arn=self.waf_acl.attr_arn,
        )

        # --- Outputs ---
        cdk.CfnOutput(
            self,
            "WafWebAclArn",
            value=self.waf_acl.attr_arn,
            export_name=f"AiopsWafArn-{env_name}",
        )

    def _create_dora_dashboard(self, env_name: str) -> None:
        """Create DORA Metrics CloudWatch Dashboard.

        Tracks the four DORA metrics:
        1. Deployment Frequency — deploys per week
        2. Lead Time for Changes — commit to production
        3. Change Failure Rate — % of deploys triggering rollback
        4. Mean Time to Recovery — failed deploy to successful rollback

        Plus additional operational metrics:
        5. Canary success rate
        6. Health gate pass rate
        7. Pipeline duration (CI + CD)
        """
        # Custom metrics published by CD pipeline scripts
        deploy_frequency = cloudwatch.Metric(
            metric_name="DeploymentCount",
            namespace=f"AIOps/{env_name}/DORA",
            period=Duration.days(7),
            statistic="Sum",
            label="Deploys / Week",
        )

        lead_time = cloudwatch.Metric(
            metric_name="LeadTimeSeconds",
            namespace=f"AIOps/{env_name}/DORA",
            period=Duration.days(1),
            statistic="Average",
            label="Lead Time (avg seconds)",
        )

        change_failure_rate = cloudwatch.MathExpression(
            expression="(rollbacks / deploys) * 100",
            using_metrics={
                "rollbacks": cloudwatch.Metric(
                    metric_name="RollbackCount",
                    namespace=f"AIOps/{env_name}/DORA",
                    period=Duration.days(7),
                    statistic="Sum",
                ),
                "deploys": cloudwatch.Metric(
                    metric_name="DeploymentCount",
                    namespace=f"AIOps/{env_name}/DORA",
                    period=Duration.days(7),
                    statistic="Sum",
                ),
            },
            period=Duration.days(7),
            label="Change Failure Rate (%)",
        )

        mttr = cloudwatch.Metric(
            metric_name="MeanTimeToRecoverySeconds",
            namespace=f"AIOps/{env_name}/DORA",
            period=Duration.days(7),
            statistic="Average",
            label="MTTR (avg seconds)",
        )

        # --- Dashboard Layout ---
        dora_dashboard = cloudwatch.Dashboard(
            self,
            "DoraDashboard",
            dashboard_name=f"AIOps-Deployments-{env_name}",
            widgets=[
                # Row 1: DORA metrics
                [
                    cloudwatch.SingleValueWidget(
                        title="Deployment Frequency (7d)",
                        metrics=[deploy_frequency],
                        width=6,
                    ),
                    cloudwatch.SingleValueWidget(
                        title="Lead Time (avg)",
                        metrics=[lead_time],
                        width=6,
                    ),
                    cloudwatch.GaugeWidget(
                        title="Change Failure Rate",
                        metrics=[change_failure_rate],
                        width=6,
                        left_y_axis=cloudwatch.YAxisProps(min=0, max=100),
                    ),
                    cloudwatch.SingleValueWidget(
                        title="MTTR (avg)",
                        metrics=[mttr],
                        width=6,
                    ),
                ],
                # Row 2: Operational deployment health
                [
                    cloudwatch.GraphWidget(
                        title="Deployments Over Time",
                        width=12,
                        left=[
                            cloudwatch.Metric(
                                metric_name="DeploymentCount",
                                namespace=f"AIOps/{env_name}/DORA",
                                period=Duration.days(1),
                                statistic="Sum",
                                label="Deploys/day",
                            ),
                            cloudwatch.Metric(
                                metric_name="RollbackCount",
                                namespace=f"AIOps/{env_name}/DORA",
                                period=Duration.days(1),
                                statistic="Sum",
                                label="Rollbacks/day",
                            ),
                        ],
                    ),
                    cloudwatch.GraphWidget(
                        title="Pipeline Duration",
                        width=12,
                        left=[
                            cloudwatch.Metric(
                                metric_name="PipelineDurationSeconds",
                                namespace=f"AIOps/{env_name}/DORA",
                                period=Duration.days(1),
                                statistic="p50",
                                label="p50",
                            ),
                            cloudwatch.Metric(
                                metric_name="PipelineDurationSeconds",
                                namespace=f"AIOps/{env_name}/DORA",
                                period=Duration.days(1),
                                statistic="p95",
                                label="p95",
                            ),
                        ],
                    ),
                ],
                # Row 3: Health gates and canary
                [
                    cloudwatch.GraphWidget(
                        title="Health Gate & Canary Success",
                        width=12,
                        left=[
                            cloudwatch.Metric(
                                metric_name="HealthGatePassCount",
                                namespace=f"AIOps/{env_name}/DORA",
                                period=Duration.days(1),
                                statistic="Sum",
                                label="Health Gate Pass",
                            ),
                            cloudwatch.Metric(
                                metric_name="HealthGateFailCount",
                                namespace=f"AIOps/{env_name}/DORA",
                                period=Duration.days(1),
                                statistic="Sum",
                                label="Health Gate Fail",
                            ),
                        ],
                    ),
                    cloudwatch.GraphWidget(
                        title="Remediation Storm & Fleet Breaker",
                        width=12,
                        left=[
                            cloudwatch.Metric(
                                metric_name="StormActivations",
                                namespace=f"AIOps/{env_name}",
                                period=Duration.days(1),
                                statistic="Sum",
                                label="Storm Activations",
                            ),
                            cloudwatch.Metric(
                                metric_name="FleetBreakerTrips",
                                namespace=f"AIOps/{env_name}",
                                period=Duration.days(1),
                                statistic="Sum",
                                label="Fleet Breaker Trips",
                            ),
                        ],
                    ),
                ],
            ],
        )

    def _create_budget(self) -> None:
        """Create an AWS Budget with 80% and 100% threshold alerts.

        Fails synthesis if costCenterEmail is absent (enforced in
        validate_cdk_context, but guarded here as well).
        """
        env_name = self._context.environment
        cost_center_email = self._context.cost_center_email

        # Requirement 10.4: Fail synthesis if costCenterEmail is absent
        if not cost_center_email or not cost_center_email.strip():
            raise ValueError(
                "CDK context validation failed: costCenterEmail is required for budget alerts"
            )

        # Budget amount: configurable via CDK_Context monthlyBudgetUsd,
        # falling back to environment-specific defaults.
        budget_amount = int(
            self._context.monthly_budget_usd
            if self._context.monthly_budget_usd
            else str(_DEFAULT_BUDGET_LIMITS.get(env_name, 200))
        )

        # Notification subscriber for alerts
        subscriber = budgets.CfnBudget.SubscriberProperty(
            address=cost_center_email,
            subscription_type="EMAIL",
        )

        # Alert at 80% threshold (Requirement 10.2)
        alert_80 = budgets.CfnBudget.NotificationWithSubscribersProperty(
            notification=budgets.CfnBudget.NotificationProperty(
                comparison_operator="GREATER_THAN",
                notification_type="ACTUAL",
                threshold=80,
                threshold_type="PERCENTAGE",
            ),
            subscribers=[subscriber],
        )

        # Alert at 100% threshold (Requirement 10.3)
        alert_100 = budgets.CfnBudget.NotificationWithSubscribersProperty(
            notification=budgets.CfnBudget.NotificationProperty(
                comparison_operator="GREATER_THAN",
                notification_type="ACTUAL",
                threshold=100,
                threshold_type="PERCENTAGE",
            ),
            subscribers=[subscriber],
        )

        # Requirement 10.1: Create AWS Budget per environment
        budgets.CfnBudget(
            self,
            "MonthlyBudget",
            budget=budgets.CfnBudget.BudgetDataProperty(
                budget_name=f"aiops-{env_name}-monthly",
                budget_type="COST",
                time_unit="MONTHLY",
                budget_limit=budgets.CfnBudget.SpendProperty(
                    amount=budget_amount,
                    unit="USD",
                ),
            ),
            notifications_with_subscribers=[alert_80, alert_100],
        )
