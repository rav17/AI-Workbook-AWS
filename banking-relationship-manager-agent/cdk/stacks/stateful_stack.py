from __future__ import annotations

from typing import Any

from aws_cdk import Duration, RemovalPolicy, Stack, Tags
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_events as events
from aws_cdk import aws_kms as kms
from aws_cdk import aws_logs as logs
from aws_cdk import aws_secretsmanager as secretsmanager
from aws_cdk import aws_sqs as sqs
from constructs import Construct


class StatefulStack(Stack):
    def __init__(
        self, scope: Construct, construct_id: str, *, env_name: str, **kwargs: Any
    ) -> None:
        removal_policy = RemovalPolicy.RETAIN if env_name != "dev" else RemovalPolicy.DESTROY
        super().__init__(
            scope,
            construct_id,
            termination_protection=env_name != "dev",
            **kwargs,
        )

        key = kms.Key(
            self,
            "SessionStateKey",
            alias="aria/session-state-key",
            enable_key_rotation=True,
            removal_policy=removal_policy,
        )

        table = dynamodb.Table(
            self,
            "SessionTable",
            partition_key=dynamodb.Attribute(name="session_id", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            encryption=dynamodb.TableEncryption.CUSTOMER_MANAGED,
            encryption_key=key,
            point_in_time_recovery=True,
            removal_policy=removal_policy,
            stream=dynamodb.StreamViewType.NEW_AND_OLD_IMAGES,
        )

        provider_secret = secretsmanager.Secret(
            self,
            "ProviderSecret",
            description="Runtime provider credentials for Aria integrations",
            encryption_key=key,
            removal_policy=removal_policy,
        )

        event_bus = events.EventBus(
            self,
            "WorkflowEventBus",
            event_bus_name=f"aria-workflow-{env_name}",
        )

        queue = sqs.Queue(
            self,
            "WorkflowQueue",
            visibility_timeout=Duration.seconds(300),
            retention_period=Duration.days(4),
            removal_policy=removal_policy,
            dead_letter_queue=sqs.DeadLetterQueue(
                max_receive_count=3,
                queue=sqs.Queue(self, "WorkflowDlq", removal_policy=removal_policy),
            ),
        )

        logs.LogGroup(
            self,
            "WorkflowLogGroup",
            retention=logs.RetentionDays.ONE_WEEK,
            removal_policy=removal_policy,
        )

        Tags.of(self).add("environment", env_name)
        self.session_table = table
        self.provider_secret = provider_secret
        self.workflow_event_bus = event_bus
        self.workflow_queue = queue
        self.session_key = key
