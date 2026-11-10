from __future__ import annotations

from pathlib import Path
from typing import Any

from aws_cdk import Duration, RemovalPolicy, Stack
from aws_cdk import aws_apigateway as apigateway
from aws_cdk import aws_cognito as cognito
from aws_cdk import aws_events as events
from aws_cdk import aws_events_targets as targets
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from constructs import Construct

from cdk.cdk_constructs.observability import (
    add_api_alarms,
    add_lambda_alarms,
    add_sensitive_findings_alarm,
    protected_log_group,
)
from cdk.stacks.stateful_stack import StatefulStack


class ApplicationStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        env_name: str,
        stateful_stack: StatefulStack,
        user_pool_arn: str,
        tenant_claim_name: str,
        idempotency_ttl_seconds: int | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        artifact_path = Path(__file__).resolve().parents[2] / "build-artifacts" / "lambda"
        if not artifact_path.is_dir():
            raise RuntimeError(
                "Lambda deployment artifact is missing; run "
                "`python scripts/build_artifacts.py --target lambda` first"
            )
        code = lambda_.Code.from_asset(
            str(artifact_path),
        )
        request_environment = {
            "ENVIRONMENT": env_name,
            "TENANT_CLAIM_NAME": tenant_claim_name,
            "SESSION_TABLE_NAME": stateful_stack.session_table.table_name,
            "IDEMPOTENCY_TABLE_NAME": stateful_stack.idempotency_table.table_name,
            "WORKFLOW_EVENT_BUS_NAME": stateful_stack.workflow_event_bus.event_bus_name,
            "AGENTCORE_RUNTIME_ARN_PARAMETER": f"/aria/{env_name}/agentcore/runtime-arn",
        }
        if idempotency_ttl_seconds is not None:
            request_environment["IDEMPOTENCY_TTL_SECONDS"] = str(idempotency_ttl_seconds)
        log_removal_policy = RemovalPolicy.RETAIN if env_name != "dev" else RemovalPolicy.DESTROY
        request_log_group = protected_log_group(
            self,
            "RequestFunctionLogGroup",
            removal_policy=log_removal_policy,
        )
        request_function = lambda_.Function(
            self,
            "RequestFunction",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="aria.api.lambda_entry.handler",
            code=code,
            timeout=Duration.seconds(28),
            tracing=lambda_.Tracing.ACTIVE,
            environment=request_environment,
            log_group=request_log_group,
        )
        add_lambda_alarms(
            self,
            env_name=env_name,
            function=request_function,
            topic=stateful_stack.operations_topic,
            alarm_prefix=f"{env_name}-RequestFunction",
        )
        add_sensitive_findings_alarm(
            self,
            env_name=env_name,
            log_group=request_log_group,
            topic=stateful_stack.operations_topic,
            alarm_prefix=f"{env_name}-RequestFunction",
        )
        stateful_stack.session_table.grant_read_write_data(request_function)
        stateful_stack.idempotency_table.grant_read_write_data(request_function)
        stateful_stack.workflow_event_bus.grant_put_events_to(request_function)
        runtime_arn_pattern = (
            f"arn:aws:bedrock-agentcore:{self.region}:{self.account}:runtime/aria_"
            f"{env_name}_runtime-*"
        )
        request_function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "bedrock-agentcore:InvokeAgentRuntime",
                    "bedrock-agentcore:InvokeAgentRuntimeForUser",
                ],
                resources=[runtime_arn_pattern],
            )
        )
        runtime_arn_parameter_arn = self.format_arn(
            service="ssm",
            resource="parameter",
            resource_name=f"aria/{env_name}/agentcore/runtime-arn",
        )
        request_function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["ssm:GetParameter"],
                resources=[runtime_arn_parameter_arn],
            )
        )

        api = apigateway.RestApi(
            self,
            "AriaApi",
            rest_api_name=f"aria-api-{env_name}",
            deploy_options=apigateway.StageOptions(
                stage_name=env_name,
                tracing_enabled=True,
            ),
        )
        user_pool = cognito.UserPool.from_user_pool_arn(
            self,
            "ClientUserPool",
            user_pool_arn,
        )
        authorizer = apigateway.CognitoUserPoolsAuthorizer(
            self,
            "ClientAuthorizer",
            cognito_user_pools=[user_pool],
            identity_source=apigateway.IdentitySource.header("Authorization"),
        )
        api.root.add_resource("messages").add_method(
            "POST",
            apigateway.LambdaIntegration(
                request_function,
                timeout=Duration.seconds(29),
            ),
            authorization_type=apigateway.AuthorizationType.COGNITO,
            authorizer=authorizer,
        )
        add_api_alarms(
            self,
            env_name=env_name,
            api=api,
            topic=stateful_stack.operations_topic,
        )

        event_log_group = protected_log_group(
            self,
            "EventFunctionLogGroup",
            removal_policy=log_removal_policy,
        )
        event_function = lambda_.Function(
            self,
            "EventFunction",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="aria.events.lambda_handler.handler",
            code=code,
            tracing=lambda_.Tracing.ACTIVE,
            environment={"ENVIRONMENT": env_name},
            log_group=event_log_group,
        )
        add_lambda_alarms(
            self,
            env_name=env_name,
            function=event_function,
            topic=stateful_stack.operations_topic,
            alarm_prefix=f"{env_name}-EventFunction",
        )
        add_sensitive_findings_alarm(
            self,
            env_name=env_name,
            log_group=event_log_group,
            topic=stateful_stack.operations_topic,
            alarm_prefix=f"{env_name}-EventFunction",
        )
        events.Rule(
            self,
            "RetentionEvents",
            event_bus=stateful_stack.workflow_event_bus,
            event_pattern=events.EventPattern(
                source=["aria"],
                detail_type=["MaturityDue", "LargeOutflowDetected"],
            ),
            targets=[targets.LambdaFunction(event_function)],
        )
        self.request_function = request_function
        self.event_function = event_function
        self.api = api
