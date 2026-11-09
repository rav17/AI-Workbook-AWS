from __future__ import annotations

from pathlib import Path
from typing import Any

from aws_cdk import CfnOutput, CfnResource, RemovalPolicy, Stack
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from constructs import Construct

from cdk.cdk_constructs.observability import (
    add_lambda_alarms,
    add_sensitive_findings_alarm,
    protected_log_group,
)
from cdk.stacks.application_stack import ApplicationStack
from cdk.stacks.stateful_stack import StatefulStack


class GatewayStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        env_name: str,
        stateful_stack: StatefulStack,
        application_stack: ApplicationStack,
        **kwargs: Any,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        artifact_path = Path(__file__).resolve().parents[2] / "build-artifacts" / "lambda"
        if not artifact_path.is_dir():
            raise RuntimeError(
                "Gateway deployment artifact is missing; run "
                "`python scripts/build_artifacts.py --target lambda` first"
            )
        gateway_log_group = protected_log_group(
            self,
            "GatewayToolFunctionLogGroup",
            removal_policy=(RemovalPolicy.RETAIN if env_name != "dev" else RemovalPolicy.DESTROY),
        )
        gateway_function = lambda_.Function(
            self,
            "GatewayToolFunction",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="aria.api.gateway_handler.handler",
            code=lambda_.Code.from_asset(str(artifact_path)),
            environment={
                "ENVIRONMENT": env_name,
                "STATEMENT_ENTITLEMENTS_TABLE": stateful_stack.statement_entitlements_table.table_name,
                "STATEMENT_TRANSACTIONS_TABLE": stateful_stack.statement_transactions_table.table_name,
            },
            tracing=lambda_.Tracing.ACTIVE,
            log_group=gateway_log_group,
        )
        for table in (
            stateful_stack.statement_entitlements_table,
            stateful_stack.statement_transactions_table,
        ):
            gateway_function.add_to_role_policy(
                iam.PolicyStatement(
                    actions=["dynamodb:GetItem", "dynamodb:Query"],
                    resources=[table.table_arn, f"{table.table_arn}/index/*"],
                )
            )
        add_lambda_alarms(
            self,
            env_name=env_name,
            function=gateway_function,
            topic=stateful_stack.operations_topic,
            alarm_prefix=f"{env_name}-GatewayToolFunction",
        )
        add_sensitive_findings_alarm(
            self,
            env_name=env_name,
            log_group=gateway_log_group,
            topic=stateful_stack.operations_topic,
            alarm_prefix=f"{env_name}-GatewayToolFunction",
        )

        gateway_role = iam.Role(
            self,
            "GatewayServiceRole",
            assumed_by=iam.ServicePrincipal(
                "bedrock-agentcore.amazonaws.com",
                conditions={
                    "StringEquals": {"aws:SourceAccount": self.account},
                    "ArnLike": {
                        "aws:SourceArn": (
                            f"arn:aws:bedrock-agentcore:{self.region}:{self.account}:gateway/*"
                        )
                    },
                },
            ),
            description="AgentCore Gateway role for Aria Lambda tools",
        )
        gateway = CfnResource(
            self,
            "AgentCoreGateway",
            type="AWS::BedrockAgentCore::Gateway",
            properties={
                "Name": f"aria-{env_name}-gateway",
                "ProtocolType": "MCP",
                "AuthorizerType": "AWS_IAM",
                "RoleArn": gateway_role.role_arn,
                "Description": f"Aria relationship manager Gateway ({env_name})",
            },
        )
        gateway_arn = (
            f"arn:aws:bedrock-agentcore:{self.region}:{self.account}:gateway/{gateway.ref}"
        )
        gateway_role.add_to_policy(
            iam.PolicyStatement(
                actions=["lambda:InvokeFunction"],
                resources=[gateway_function.function_arn],
            )
        )
        CfnResource(
            self,
            "AgentCoreGatewayInvokePermission",
            type="AWS::Lambda::Permission",
            properties={
                "Action": "lambda:InvokeFunction",
                "FunctionName": gateway_function.function_arn,
                "Principal": "bedrock-agentcore.amazonaws.com",
                "SourceArn": gateway_arn,
            },
        )

        target = CfnResource(
            self,
            "AgentCoreGatewayTarget",
            type="AWS::BedrockAgentCore::GatewayTarget",
            properties={
                "GatewayIdentifier": gateway.ref,
                "Name": "aria-messages",
                "Description": "Invoke the Aria relationship manager message handler",
                "TargetConfiguration": {
                    "Mcp": {
                        "Lambda": {
                            "LambdaArn": gateway_function.function_arn,
                            "ToolSchema": {
                                "InlinePayload": [
                                    {
                                        "Name": "get_risk_questionnaire",
                                        "Description": (
                                            "Return the standard risk-appetite questionnaire"
                                        ),
                                        "InputSchema": {
                                            "Type": "object",
                                            "Properties": {},
                                            "AdditionalProperties": False,
                                        },
                                    }
                                ]
                            },
                        }
                    }
                },
                "CredentialProviderConfigurations": [
                    {"CredentialProviderType": "GATEWAY_IAM_ROLE"}
                ],
            },
        )
        target.add_dependency(gateway)
        statement_target = CfnResource(
            self,
            "AgentCoreStatementGatewayTarget",
            type="AWS::BedrockAgentCore::GatewayTarget",
            properties={
                "GatewayIdentifier": gateway.ref,
                "Name": "aria-statements",
                "Description": "Read authorized statement records through Aria's trusted entitlement boundary",
                "TargetConfiguration": {
                    "Mcp": {
                        "Lambda": {
                            "LambdaArn": gateway_function.function_arn,
                            "ToolSchema": {
                                "InlinePayload": [
                                    {
                                        "Name": "list_authorized_statements",
                                        "Description": "List active statement references assigned to a verified Runtime principal",
                                        "InputSchema": {
                                            "Type": "object",
                                            "Properties": {
                                                "tenant_id": {"Type": "string"},
                                                "user_id": {"Type": "string"},
                                                "limit": {"Type": "integer"},
                                                "page_token": {"Type": "string"},
                                            },
                                            "Required": ["tenant_id", "user_id"],
                                            "AdditionalProperties": False,
                                        },
                                    },
                                    {
                                        "Name": "get_statement_transactions",
                                        "Description": "Read a bounded page of transactions after verifying the principal's statement entitlement",
                                        "InputSchema": {
                                            "Type": "object",
                                            "Properties": {
                                                "tenant_id": {"Type": "string"},
                                                "user_id": {"Type": "string"},
                                                "statement_ref": {"Type": "string"},
                                                "start_date": {"Type": "string"},
                                                "end_date": {"Type": "string"},
                                                "page_size": {"Type": "integer"},
                                                "page_token": {"Type": "string"},
                                                "trans_id": {"Type": "string"},
                                            },
                                            "Required": [
                                                "tenant_id",
                                                "user_id",
                                                "statement_ref",
                                            ],
                                            "AdditionalProperties": False,
                                        },
                                    },
                                ]
                            },
                        }
                    }
                },
                "CredentialProviderConfigurations": [
                    {"CredentialProviderType": "GATEWAY_IAM_ROLE"}
                ],
            },
        )
        statement_target.add_dependency(gateway)
        CfnOutput(self, "GatewayId", value=gateway.ref)
        self.gateway = gateway
        self.gateway_target = target
        self.statement_gateway_target = statement_target
        self.gateway_function = gateway_function
        self.gateway_id = gateway.ref
        self.gateway_arn = gateway_arn
        self.node.add_dependency(stateful_stack)
        self.node.add_dependency(application_stack)
