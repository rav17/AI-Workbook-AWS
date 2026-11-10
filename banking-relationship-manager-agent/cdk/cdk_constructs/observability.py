from __future__ import annotations

from typing import Any

from aws_cdk import Duration, RemovalPolicy
from aws_cdk import aws_apigateway as apigateway
from aws_cdk import aws_cloudwatch as cloudwatch
from aws_cdk import aws_cloudwatch_actions as cloudwatch_actions
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from aws_cdk import aws_sns as sns
from constructs import Construct


def protected_log_group(
    scope: Construct,
    construct_id: str,
    *,
    removal_policy: RemovalPolicy,
) -> logs.LogGroup:
    identifiers = [
        logs.DataIdentifier.EMAILADDRESS,
        logs.DataIdentifier.ADDRESS,
        logs.DataIdentifier.SSN_US,
        logs.DataIdentifier.PHONENUMBER_US,
        logs.DataIdentifier.BANKACCOUNTNUMBER_US,
        logs.DataIdentifier.CREDITCARDNUMBER,
        logs.DataIdentifier.CREDITCARDSECURITYCODE,
        logs.DataIdentifier.AWSSECRETKEY,
        logs.DataIdentifier.OPENSSHPRIVATEKEY,
        logs.DataIdentifier.PGPPRIVATEKEY,
        logs.DataIdentifier.PKCSPRIVATEKEY,
        logs.DataIdentifier.PUTTYPRIVATEKEY,
    ]
    policy = logs.DataProtectionPolicy(
        name=f"{construct_id}-sensitive-data-protection",
        description="Audit and mask common personal, financial, and credential data",
        identifiers=identifiers,
    )
    return logs.LogGroup(
        scope,
        construct_id,
        retention=logs.RetentionDays.ONE_WEEK,
        data_protection_policy=policy,
        removal_policy=removal_policy,
    )


def _positive_context_number(scope: Construct, key: str, default: float) -> float:
    value: Any = scope.node.try_get_context(key)
    if value is None:
        return default
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"CDK context {key} must be a positive number") from exc
    if number <= 0:
        raise ValueError(f"CDK context {key} must be a positive number")
    return number


def _add_alarm(
    scope: Construct,
    alarm_id: str,
    *,
    metric: cloudwatch.IMetric,
    threshold: float,
    topic: sns.ITopic,
    description: str,
    evaluation_periods: int = 2,
) -> cloudwatch.Alarm:
    alarm = cloudwatch.Alarm(
        scope,
        alarm_id,
        alarm_name=alarm_id,
        metric=metric,
        threshold=threshold,
        evaluation_periods=evaluation_periods,
        datapoints_to_alarm=evaluation_periods,
        comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
        treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        alarm_description=description,
    )
    alarm.add_alarm_action(cloudwatch_actions.SnsAction(topic))
    return alarm


def add_lambda_alarms(
    scope: Construct,
    *,
    env_name: str,
    function: lambda_.IFunction,
    topic: sns.ITopic,
    alarm_prefix: str,
) -> None:
    period = Duration.minutes(5)
    _add_alarm(
        scope,
        f"{alarm_prefix}ErrorsAlarm",
        metric=function.metric_errors(period=period, statistic="sum"),
        threshold=1,
        topic=topic,
        description=f"Provisional {env_name} threshold: any Lambda errors for {alarm_prefix}.",
        evaluation_periods=1,
    )
    _add_alarm(
        scope,
        f"{alarm_prefix}ThrottlesAlarm",
        metric=function.metric_throttles(period=period, statistic="sum"),
        threshold=1,
        topic=topic,
        description=f"Provisional {env_name} threshold: any Lambda throttles for {alarm_prefix}.",
        evaluation_periods=1,
    )


def add_sensitive_findings_alarm(
    scope: Construct,
    *,
    env_name: str,
    log_group: logs.ILogGroup,
    topic: sns.ITopic,
    alarm_prefix: str,
) -> None:
    metric = cloudwatch.Metric(
        namespace="AWS/Logs",
        metric_name="LogEventsWithFindings",
        statistic="sum",
        period=Duration.minutes(5),
    )
    _add_alarm(
        scope,
        f"{alarm_prefix}SensitiveFindingsAlarm",
        metric=metric,
        threshold=1,
        topic=topic,
        description=(
            f"Provisional {env_name} security threshold: any audited sensitive log event. "
            f"Review log group {log_group.log_group_name}; do not copy raw matches into alerts."
        ),
        evaluation_periods=1,
    )


def add_api_alarms(
    scope: Construct,
    *,
    env_name: str,
    api: apigateway.RestApi,
    topic: sns.ITopic,
) -> None:
    period = Duration.minutes(5)
    errors = api.metric_server_error(period=period, statistic="sum")
    requests = api.metric_count(period=period, statistic="sum")
    error_rate = cloudwatch.MathExpression(
        expression="IF(requests >= 100, 100 * errors / requests, 0)",
        using_metrics={"errors": errors, "requests": requests},
        label="API 5xx percentage (minimum 100 requests)",
        period=period,
    )
    error_threshold = _positive_context_number(scope, "alarm_api_error_rate_percent", 1.0)
    latency_threshold = _positive_context_number(scope, "alarm_api_p95_latency_ms", 1000.0)
    _add_alarm(
        scope,
        f"aria-{env_name}-api-error-rate",
        metric=error_rate,
        threshold=error_threshold,
        topic=topic,
        description=(
            f"Provisional {env_name} API 5xx rate threshold is "
            f"{error_threshold}% over five minutes; "
            "minimum sample size is 100 requests."
        ),
    )
    _add_alarm(
        scope,
        f"aria-{env_name}-api-p95-latency",
        metric=api.metric_latency(period=period, statistic="p95"),
        threshold=latency_threshold,
        topic=topic,
        description=(
            f"Provisional {env_name} API p95 latency threshold is "
            f"{latency_threshold} ms over five minutes."
        ),
    )
