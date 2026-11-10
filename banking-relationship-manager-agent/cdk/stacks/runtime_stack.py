from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aws_cdk import (
    CfnOutput,
    CfnResource,
    CustomResource,
    Duration,
    Stack,
    custom_resources,
)
from aws_cdk import aws_bedrockagentcore as bedrockagentcore
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_s3_assets as s3_assets
from aws_cdk import aws_ssm as ssm
from constructs import Construct

from cdk.stacks.application_stack import ApplicationStack
from cdk.stacks.gateway_stack import GatewayStack
from cdk.stacks.stateful_stack import StatefulStack


class RuntimeStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        env_name: str,
        stateful_stack: StatefulStack,
        gateway_stack: GatewayStack,
        application_stack: ApplicationStack,
        model_id: str,
        cognito_user_pool_id: str,
        cognito_app_client_id: str,
        tenant_claim_name: str,
        statement_explainer_enabled: bool = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        runtime_role = iam.Role(
            self,
            "RuntimeExecutionRole",
            assumed_by=iam.ServicePrincipal(
                "bedrock-agentcore.amazonaws.com",
                conditions={
                    "StringEquals": {"aws:SourceAccount": self.account},
                    "ArnLike": {
                        "aws:SourceArn": (
                            f"arn:aws:bedrock-agentcore:{self.region}:{self.account}:"
                            f"runtime/aria_{env_name}_runtime*"
                        )
                    },
                },
            ),
            description="AgentCore Runtime role for the Aria agent",
        )
        runtime_role.add_to_policy(
            iam.PolicyStatement(
                actions=["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
                resources=[f"arn:aws:bedrock:{self.region}::foundation-model/{model_id}"],
            )
        )
        runtime_role.add_to_policy(
            iam.PolicyStatement(
                actions=["bedrock-agentcore:RetrieveMemoryRecords"],
                resources=[
                    f"arn:aws:bedrock-agentcore:{self.region}:{self.account}:memory/"
                    f"{stateful_stack.agentcore_memory_id}"
                ],
                conditions={
                    "StringLike": {"bedrock-agentcore:namespacePath": "/tenants/*/users/*"}
                },
            )
        )
        runtime_role.add_to_policy(
            iam.PolicyStatement(
                actions=["bedrock-agentcore:InvokeGateway"],
                resources=[gateway_stack.gateway_arn],
            )
        )
        runtime_role.add_to_policy(
            iam.PolicyStatement(
                actions=["logs:CreateLogStream", "logs:PutLogEvents"],
                resources=[
                    f"arn:aws:logs:{self.region}:{self.account}:log-group:"
                    "/aws/bedrock-agentcore/runtimes/*:log-stream:*"
                ],
            )
        )

        artifact_path = Path(__file__).resolve().parents[2] / "build-artifacts" / "runtime"
        if not artifact_path.is_dir():
            raise RuntimeError(
                "AgentCore Runtime deployment artifact is missing; run "
                "`python scripts/build_artifacts.py --target runtime` first"
            )
        code_asset = s3_assets.Asset(
            self,
            "AgentRuntimeCode",
            path=str(artifact_path),
        )
        runtime = CfnResource(
            self,
            "AgentCoreRuntime",
            type="AWS::BedrockAgentCore::Runtime",
            properties={
                "AgentRuntimeName": f"aria_{env_name}_runtime",
                "Description": f"Aria relationship manager runtime ({env_name})",
                "RoleArn": runtime_role.role_arn,
                "AgentRuntimeArtifact": {
                    "CodeConfiguration": {
                        "Code": {
                            "S3": {
                                "Bucket": code_asset.s3_bucket_name,
                                "Prefix": code_asset.s3_object_key,
                            }
                        },
                        "EntryPoint": ["aria/agents/aria/agentcore_entrypoint.py"],
                        "Runtime": "PYTHON_3_13",
                    }
                },
                "NetworkConfiguration": {"NetworkMode": "PUBLIC"},
                "EnvironmentVariables": {
                    "ENVIRONMENT": env_name,
                    "AGENTCORE_MODEL_ID": model_id,
                    "COGNITO_USER_POOL_ID": cognito_user_pool_id,
                    "COGNITO_APP_CLIENT_ID": cognito_app_client_id,
                    "TENANT_CLAIM_NAME": tenant_claim_name,
                    "AGENTCORE_MEMORY_ID": stateful_stack.agentcore_memory_id,
                    "AGENTCORE_GATEWAY_ID": gateway_stack.gateway_id,
                    "STATEMENT_EXPLAINER_ENABLED": str(statement_explainer_enabled).lower(),
                },
            },
        )
        runtime.add_dependency(gateway_stack.gateway)
        runtime_arn = runtime.get_att("AgentRuntimeArn").to_string()
        runtime_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"AWS": application_stack.request_function.role.role_arn},
                    "Action": [
                        "bedrock-agentcore:InvokeAgentRuntime",
                        "bedrock-agentcore:InvokeAgentRuntimeForUser",
                    ],
                    "Resource": runtime_arn,
                },
                {
                    "Effect": "Deny",
                    "Principal": "*",
                    "Action": [
                        "bedrock-agentcore:InvokeAgentRuntime",
                        "bedrock-agentcore:InvokeAgentRuntimeForUser",
                    ],
                    "Resource": runtime_arn,
                    "Condition": {
                        "ArnNotEquals": {
                            "aws:PrincipalArn": application_stack.request_function.role.role_arn
                        }
                    },
                },
            ],
        }
        bedrockagentcore.CfnResourcePolicy(
            self,
            "RuntimeInvocationPolicy",
            resource_arn=runtime_arn,
            policy=json.dumps(runtime_policy),
        ).add_dependency(runtime)
        ssm.StringParameter(
            self,
            "RuntimeArnParameter",
            parameter_name=f"/aria/{env_name}/agentcore/runtime-arn",
            string_value=runtime_arn,
        )
        mmdsv2_handler = lambda_.Function(
            self,
            "RequireRuntimeMmdsV2Handler",
            runtime=lambda_.Runtime.PYTHON_3_13,
            handler="cdk.custom_resources.enable_mmdsv2.handler",
            code=lambda_.Code.from_asset(str(artifact_path)),
            timeout=Duration.seconds(60),
        )
        mmdsv2_handler.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "bedrock-agentcore:GetAgentRuntime",
                    "bedrock-agentcore:UpdateAgentRuntime",
                ],
                resources=[runtime.get_att("AgentRuntimeArn").to_string()],
            )
        )
        mmdsv2_provider = custom_resources.Provider(
            self,
            "RequireRuntimeMmdsV2Provider",
            on_event_handler=mmdsv2_handler,
        )
        mmdsv2_resource = CustomResource(
            self,
            "RequireRuntimeMmdsV2",
            service_token=mmdsv2_provider.service_token,
            properties={"AgentRuntimeId": runtime.get_att("AgentRuntimeId")},
        )
        mmdsv2_resource.node.add_dependency(runtime)
        CfnOutput(self, "RuntimeArn", value=runtime.get_att("AgentRuntimeArn").to_string())
        self.runtime = runtime
        self.runtime_arn = runtime_arn
        self.node.add_dependency(stateful_stack)
        self.node.add_dependency(gateway_stack)
        self.node.add_dependency(application_stack)
