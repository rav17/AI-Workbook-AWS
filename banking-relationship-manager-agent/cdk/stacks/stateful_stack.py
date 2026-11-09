from __future__ import annotations

from typing import Any

import aws_cdk as cdk
from aws_cdk import Duration, RemovalPolicy, Stack, Tags
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_events as events
from aws_cdk import aws_iam as iam
from aws_cdk import aws_kms as kms
from aws_cdk import aws_secretsmanager as secretsmanager
from aws_cdk import aws_sns as sns
from aws_cdk import aws_sqs as sqs
from aws_cdk import aws_ssm as ssm
from constructs import Construct

from cdk.cdk_constructs.observability import add_sensitive_findings_alarm, protected_log_group


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
        idempotency_table = dynamodb.Table(
            self,
            "IdempotencyTable",
            partition_key=dynamodb.Attribute(
                name="idempotency_id", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            encryption=dynamodb.TableEncryption.CUSTOMER_MANAGED,
            encryption_key=key,
            point_in_time_recovery=True,
            time_to_live_attribute="expires_at",
            removal_policy=removal_policy,
        )
        statement_data_key = kms.Key(
            self,
            "StatementDataKey",
            alias="aria/statement-data-key",
            enable_key_rotation=True,
            removal_policy=removal_policy,
        )
        statement_entitlements_table = dynamodb.Table(
            self,
            "StatementEntitlementsTable",
            partition_key=dynamodb.Attribute(
                name="principal_scope", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(name="statement_ref", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            encryption=dynamodb.TableEncryption.CUSTOMER_MANAGED,
            encryption_key=statement_data_key,
            point_in_time_recovery=True,
            removal_policy=removal_policy,
        )
        statement_transactions_table = dynamodb.Table(
            self,
            "StatementTransactionsTable",
            partition_key=dynamodb.Attribute(
                name="statement_ref", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="transaction_key", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            encryption=dynamodb.TableEncryption.CUSTOMER_MANAGED,
            encryption_key=statement_data_key,
            point_in_time_recovery=True,
            removal_policy=removal_policy,
        )
        statement_transactions_table.add_global_secondary_index(
            index_name="StatementTransactionIdIndex",
            partition_key=dynamodb.Attribute(
                name="statement_transaction_id", type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL,
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

        workflow_log_group = protected_log_group(
            self,
            "WorkflowLogGroup",
            removal_policy=removal_policy,
        )
        operations_topic = sns.Topic(
            self,
            "OperationsAlarmTopic",
            master_key=key,
            enforce_ssl=True,
            display_name=f"Aria {env_name} operations alarms",
        )
        alarm_arn_pattern = f"arn:{self.partition}:cloudwatch:{self.region}:{self.account}:alarm:*"
        operations_topic.add_to_resource_policy(
            iam.PolicyStatement(
                sid="AllowCloudWatchAlarmsToPublish",
                effect=iam.Effect.ALLOW,
                principals=[iam.ServicePrincipal("cloudwatch.amazonaws.com")],
                actions=["sns:Publish"],
                resources=[operations_topic.topic_arn],
                conditions={
                    "StringEquals": {"aws:SourceAccount": self.account},
                    "ArnLike": {"aws:SourceArn": alarm_arn_pattern},
                },
            )
        )
        key.add_to_resource_policy(
            iam.PolicyStatement(
                sid="AllowCloudWatchAlarmsToUseOperationsTopicKey",
                effect=iam.Effect.ALLOW,
                principals=[iam.ServicePrincipal("cloudwatch.amazonaws.com")],
                actions=["kms:Decrypt", "kms:GenerateDataKey*"],
                resources=["*"],
                conditions={
                    "StringEquals": {"aws:SourceAccount": self.account},
                    "ArnLike": {"aws:SourceArn": alarm_arn_pattern},
                },
            )
        )
        add_sensitive_findings_alarm(
            self,
            env_name=env_name,
            log_group=workflow_log_group,
            topic=operations_topic,
            alarm_prefix=f"{env_name}-Workflow",
        )

        memory_role = iam.Role(
            self,
            "AgentCoreMemoryRole",
            assumed_by=iam.ServicePrincipal(
                "bedrock-agentcore.amazonaws.com",
                conditions={
                    "StringEquals": {"aws:SourceAccount": self.account},
                    "ArnLike": {
                        "aws:SourceArn": (
                            f"arn:aws:bedrock-agentcore:{self.region}:{self.account}:memory/*"
                        )
                    },
                },
            ),
            description="AgentCore Memory role for Aria embedding and extraction",
        )
        memory_role.add_to_policy(
            iam.PolicyStatement(
                actions=["bedrock:InvokeModel"],
                resources=[
                    f"arn:aws:bedrock:{self.region}::foundation-model/amazon.titan-embed-text-v2:0"
                ],
            )
        )
        memory = cdk.CfnResource(
            self,
            "AgentCoreMemory",
            type="AWS::BedrockAgentCore::Memory",
            properties={
                "Name": f"aria_{env_name}_agent_memory",
                "Description": "Aria relationship manager short and long term memory",
                "EventExpiryDuration": 30,
                "MemoryExecutionRoleArn": memory_role.role_arn,
                "EncryptionKeyArn": key.key_arn,
                "NamespaceKeys": [
                    {
                        "Key": "tenantid",
                        "Validation": {"RegexPattern": "^[a-f0-9]{32}$"},
                    }
                ],
                "MemoryStrategies": [
                    {
                        "SemanticMemoryStrategy": {
                            "Name": "AriaSemanticFacts",
                            "NamespaceTemplates": ["/tenants/{tenantid}/users/{actorId}/facts"],
                        }
                    },
                    {
                        "UserPreferenceMemoryStrategy": {
                            "Name": "AriaUserPreferences",
                            "NamespaceTemplates": [
                                "/tenants/{tenantid}/users/{actorId}/preferences"
                            ],
                        }
                    },
                    {
                        "SummaryMemoryStrategy": {
                            "Name": "AriaSummaries",
                            "NamespaceTemplates": [
                                "/tenants/{tenantid}/users/{actorId}/summaries/{sessionId}"
                            ],
                        }
                    },
                ],
            },
        )
        memory_id = memory.get_att("MemoryId").to_string()
        memory_id_parameter = ssm.StringParameter(
            self,
            "AgentCoreMemoryId",
            parameter_name=f"/aria/{env_name}/agentcore-memory-id",
            string_value=memory_id,
            description="AgentCore Memory ID for Aria runtime and gateway consumers",
        )

        Tags.of(self).add("environment", env_name)
        self.session_table = table
        self.idempotency_table = idempotency_table
        self.statement_data_key = statement_data_key
        self.statement_entitlements_table = statement_entitlements_table
        self.statement_transactions_table = statement_transactions_table
        self.provider_secret = provider_secret
        self.workflow_event_bus = event_bus
        self.workflow_queue = queue
        self.session_key = key
        self.agentcore_memory = memory
        self.agentcore_memory_id_parameter = memory_id_parameter
        self.agentcore_memory_id = memory_id
        self.operations_topic = operations_topic
