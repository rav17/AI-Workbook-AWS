"""DataStack — DynamoDB table and SQS queues for AIOps incident processing."""

from typing import Any

import aws_cdk as cdk
from aws_cdk import (
    CfnOutput,
    Duration,
    aws_backup as backup,
    aws_dynamodb as dynamodb,
    aws_ecr as ecr,
    aws_events as events,
    aws_sqs as sqs,
)
from constructs import Construct

from ..context import CdkContext


class DataStack(cdk.Stack):
    """Provisions DynamoDB incident memory table and SQS main/DLQ queues.

    Resources created:
        - DynamoDB table with 3 GSIs (AlertNameIndex, ServiceIndex, OutcomeIndex)
        - SQS dead-letter queue (DLQ)
        - SQS main queue with redrive policy to DLQ
        - Prod-only: PITR, AWS Backup daily plan (35-day retention)

    Exports:
        table: The DynamoDB table resource.
        queue: The main SQS queue.
        dlq: The dead-letter queue.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        context: CdkContext,
        **kwargs: Any,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)
        self._context = context

        env_name = context.environment
        is_prod = env_name == "prod"

        # --- ECR Repository ---
        self.ecr_repository = ecr.Repository(
            self,
            "EcrRepo",
            repository_name="aiops",
            image_scan_on_push=True,
            image_tag_mutability=ecr.TagMutability.MUTABLE,
            lifecycle_rules=[
                ecr.LifecycleRule(
                    description="Remove untagged images after 7 days",
                    tag_status=ecr.TagStatus.UNTAGGED,
                    max_image_age=Duration.days(7),
                    rule_priority=1,
                ),
                ecr.LifecycleRule(
                    description="Keep last 20 images",
                    max_image_count=20,
                    rule_priority=10,
                ),
            ],
            removal_policy=cdk.RemovalPolicy.RETAIN,
        )

        # --- SQS Dead-Letter Queue ---
        self.dlq = sqs.Queue(
            self,
            "Dlq",
            queue_name=f"aiops-dlq-{env_name}",
            retention_period=Duration.days(14),
            encryption=sqs.QueueEncryption.SQS_MANAGED,
        )

        # --- SQS Main Queue ---
        self.queue = sqs.Queue(
            self,
            "MainQueue",
            queue_name=f"aiops-main-{env_name}",
            visibility_timeout=Duration.seconds(300),
            retention_period=Duration.days(14 if is_prod else 4),
            encryption=sqs.QueueEncryption.SQS_MANAGED,
            dead_letter_queue=sqs.DeadLetterQueue(
                max_receive_count=3,
                queue=self.dlq,
            ),
        )

        # --- DynamoDB Table ---
        self.table = dynamodb.Table(
            self,
            "IncidentMemory",
            table_name=f"AiopsIncidentMemory-{env_name}",
            partition_key=dynamodb.Attribute(
                name="incident_id", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="timestamp", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            time_to_live_attribute="expiry_timestamp",
            point_in_time_recovery=is_prod,
            encryption=dynamodb.TableEncryption.AWS_MANAGED,
        )

        # --- Global Secondary Indexes ---
        gsi_definitions = [
            ("AlertNameIndex", "alert_name"),
            ("ServiceIndex", "service_name"),
            ("OutcomeIndex", "outcome"),
        ]
        for gsi_name, pk_name in gsi_definitions:
            self.table.add_global_secondary_index(
                index_name=gsi_name,
                partition_key=dynamodb.Attribute(
                    name=pk_name, type=dynamodb.AttributeType.STRING
                ),
                sort_key=dynamodb.Attribute(
                    name="timestamp", type=dynamodb.AttributeType.STRING
                ),
            )

        # TokenIndex GSI — enables O(1) lookup of approval tokens
        # without requiring the caller to know the incident_id.
        # Used by DynamoApprovalStore.get_by_token() for the
        # /approve/{token} endpoint in multi-task ECS deployments.
        self.table.add_global_secondary_index(
            index_name="TokenIndex",
            partition_key=dynamodb.Attribute(
                name="token", type=dynamodb.AttributeType.STRING
            ),
        )

        # --- Prod-only: AWS Backup daily plan (35-day retention) ---
        if is_prod:
            backup_plan = backup.BackupPlan(
                self,
                "DynamoBackupPlan",
                backup_plan_name=f"aiops-dynamo-backup-{env_name}",
            )
            backup_plan.add_rule(
                backup.BackupPlanRule(
                    delete_after=Duration.days(35),
                    schedule_expression=events.Schedule.cron(
                        hour="2", minute="0"
                    ),
                )
            )
            backup_plan.add_selection(
                "DynamoSelection",
                resources=[backup.BackupResource.from_dynamo_db_table(self.table)],
            )

        # --- CloudFormation Outputs ---
        CfnOutput(
            self,
            "TableName",
            value=self.table.table_name,
            export_name=f"AiopsDynamoTableName-{env_name}",
        )
        CfnOutput(
            self,
            "QueueUrl",
            value=self.queue.queue_url,
            export_name=f"AiopsQueueUrl-{env_name}",
        )
        CfnOutput(
            self,
            "DlqUrl",
            value=self.dlq.queue_url,
            export_name=f"AiopsDlqUrl-{env_name}",
        )
        CfnOutput(
            self,
            "EcrRepositoryUri",
            value=self.ecr_repository.repository_uri,
            export_name=f"AiopsEcrRepoUri-{env_name}",
        )
