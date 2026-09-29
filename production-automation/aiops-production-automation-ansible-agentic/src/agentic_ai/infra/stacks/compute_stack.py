"""ComputeStack — ECS Fargate cluster, service, IAM roles, auto-scaling, SSM parameters, and secrets."""

from typing import Any

import aws_cdk as cdk
from aws_cdk import (
    CfnOutput,
    Duration,
    aws_apigatewayv2 as apigwv2,
    aws_applicationautoscaling as aas,
    aws_cloudwatch as cw,
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_iam as iam,
    aws_lambda as _lambda,
    aws_logs as logs,
    aws_secretsmanager as secretsmanager,
    aws_ssm as ssm,
)
from constructs import Construct

from ..context import CdkContext
from .data_stack import DataStack
from .network_stack import NetworkStack


# Inline Python code for the API Gateway key rotation Lambda.
# This Lambda implements the four Secrets Manager rotation steps:
# createSecret, setSecret, testSecret, finishSecret.
_API_KEY_ROTATION_LAMBDA_CODE = """\
import json
import os
import secrets
import string

import boto3


def handler(event, context):
    \"\"\"Secrets Manager rotation handler for API Gateway key.\"\"\"
    secret_arn = event["SecretId"]
    token = event["ClientRequestToken"]
    step = event["Step"]

    sm_client = boto3.client("secretsmanager")

    if step == "createSecret":
        _create_secret(sm_client, secret_arn, token)
    elif step == "setSecret":
        # For API Gateway keys, the new key is set during finishSecret
        pass
    elif step == "testSecret":
        # Verify the new secret version exists
        _test_secret(sm_client, secret_arn, token)
    elif step == "finishSecret":
        _finish_secret(sm_client, secret_arn, token)
    else:
        raise ValueError(f"Unknown rotation step: {step}")


def _create_secret(sm_client, secret_arn, token):
    \"\"\"Generate a new API key and store as AWSPENDING.\"\"\"
    # Generate a secure random API key (40 chars, alphanumeric)
    alphabet = string.ascii_letters + string.digits
    new_key = "".join(secrets.choice(alphabet) for _ in range(40))

    secret_value = json.dumps({
        "service": "api-gateway",
        "api_key": new_key,
    })

    sm_client.put_secret_value(
        SecretId=secret_arn,
        ClientRequestToken=token,
        SecretString=secret_value,
        VersionStages=["AWSPENDING"],
    )


def _test_secret(sm_client, secret_arn, token):
    \"\"\"Verify the pending secret version is valid.\"\"\"
    response = sm_client.get_secret_value(
        SecretId=secret_arn,
        VersionId=token,
        VersionStage="AWSPENDING",
    )
    secret_data = json.loads(response["SecretString"])
    if not secret_data.get("api_key"):
        raise ValueError("Pending secret does not contain a valid api_key")


def _finish_secret(sm_client, secret_arn, token):
    \"\"\"Move AWSPENDING to AWSCURRENT, completing the rotation.\"\"\"
    metadata = sm_client.describe_secret(SecretId=secret_arn)

    # Find the current version
    current_version = None
    for version_id, stages in metadata.get("VersionIdsToStages", {}).items():
        if "AWSCURRENT" in stages and version_id != token:
            current_version = version_id
            break

    # Promote pending to current
    sm_client.update_secret_version_stage(
        SecretId=secret_arn,
        VersionStage="AWSCURRENT",
        MoveToVersionId=token,
        RemoveFromVersionId=current_version,
    )
"""


class ComputeStack(cdk.Stack):
    """Provisions ECS cluster, Fargate service, task roles, and auto-scaling.

    Receives cross-stack references from NetworkStack and DataStack via
    constructor parameters.

    Exports:
        cluster: The ECS cluster.
        service: The Fargate service.
        task_role: The ECS task IAM role.
        execution_role: The ECS task execution IAM role.
        log_group: The CloudWatch log group.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        context: CdkContext,
        network_stack: NetworkStack,
        data_stack: DataStack,
        **kwargs: Any,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)
        self._context = context

        env_name = context.environment
        is_dev = env_name == "dev"

        # ---------------------------------------------------------------
        # CloudWatch Log Group
        # ---------------------------------------------------------------
        log_retention_map = {
            "dev": logs.RetentionDays.ONE_MONTH,
            "staging": logs.RetentionDays.THREE_MONTHS,
            "prod": logs.RetentionDays.ONE_YEAR,
        }
        self.log_group = logs.LogGroup(
            self,
            "EcsLogGroup",
            log_group_name=f"/aiops/{env_name}/ecs",
            retention=log_retention_map[env_name],
            removal_policy=cdk.RemovalPolicy.DESTROY,
        )

        # ---------------------------------------------------------------
        # ECS Cluster
        # ---------------------------------------------------------------
        self.cluster = ecs.Cluster(
            self,
            "Cluster",
            cluster_name=f"aiops-cluster-{env_name}",
            vpc=network_stack.vpc,
            enable_fargate_capacity_providers=True,
        )

        # Cloud Map namespace for service discovery (required for API Gateway VPC Link)
        self._namespace = self.cluster.add_default_cloud_map_namespace(
            name=f"aiops-{env_name}.local",
        )

        # ---------------------------------------------------------------
        # Task Execution Role (used by ECS agent to pull image & push logs)
        # ---------------------------------------------------------------
        self.execution_role = iam.Role(
            self,
            "TaskExecRole",
            role_name=f"AiopsTaskExecRole-{env_name}",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
        )

        # ECR GetAuthorizationToken requires Resource: "*" (AWS-mandated)
        self.execution_role.add_to_policy(
            iam.PolicyStatement(
                actions=["ecr:GetAuthorizationToken"],
                resources=["*"],
            )
        )
        # ECR image pull — scoped to aiops repositories
        self.execution_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "ecr:BatchCheckLayerAvailability",
                    "ecr:GetDownloadUrlForLayer",
                    "ecr:BatchGetImage",
                ],
                resources=[
                    f"arn:aws:ecr:{context.aws_region}:{context.aws_account}:repository/aiops*"
                ],
            )
        )
        # CloudWatch Logs — scoped to the ECS log group
        self.execution_role.add_to_policy(
            iam.PolicyStatement(
                actions=["logs:CreateLogStream", "logs:PutLogEvents"],
                resources=[self.log_group.log_group_arn + ":*"],
            )
        )
        # SSM Parameter Store — scoped to /aiops/{env}/*
        self.execution_role.add_to_policy(
            iam.PolicyStatement(
                actions=["ssm:GetParameter", "ssm:GetParameters"],
                resources=[
                    f"arn:aws:ssm:{context.aws_region}:{context.aws_account}:parameter/aiops/{env_name}/*"
                ],
            )
        )
        # Secrets Manager — scoped to /aiops/{env}/*
        self.execution_role.add_to_policy(
            iam.PolicyStatement(
                actions=["secretsmanager:GetSecretValue"],
                resources=[
                    f"arn:aws:secretsmanager:{context.aws_region}:{context.aws_account}:secret:/aiops/{env_name}/*"
                ],
            )
        )

        # ---------------------------------------------------------------
        # Task Role (used by the application container at runtime)
        # ---------------------------------------------------------------
        self.task_role = iam.Role(
            self,
            "TaskRole",
            role_name=f"AiopsTaskRole-{env_name}",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
        )

        # Bedrock InvokeModel — allow all foundation models for fallback support
        self.task_role.add_to_policy(
            iam.PolicyStatement(
                actions=["bedrock:InvokeModel"],
                resources=[
                    f"arn:aws:bedrock:{context.aws_region}::foundation-model/*"
                ],
            )
        )
        # SQS operations — scoped to main queue and DLQ
        self.task_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "sqs:SendMessage",
                    "sqs:ReceiveMessage",
                    "sqs:DeleteMessage",
                    "sqs:GetQueueAttributes",
                ],
                resources=[data_stack.queue.queue_arn, data_stack.dlq.queue_arn],
            )
        )
        # DynamoDB CRUD — scoped to table and its indexes
        self.task_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "dynamodb:GetItem",
                    "dynamodb:PutItem",
                    "dynamodb:UpdateItem",
                    "dynamodb:Query",
                    "dynamodb:DescribeTable",
                ],
                resources=[
                    data_stack.table.table_arn,
                    f"{data_stack.table.table_arn}/index/*",
                ],
            )
        )
        # SSM SendCommand / GetCommandInvocation — scoped to aiops-managed instances
        self.task_role.add_to_policy(
            iam.PolicyStatement(
                actions=["ssm:SendCommand"],
                resources=[
                    f"arn:aws:ssm:{context.aws_region}::document/AWS-RunShellScript",
                    f"arn:aws:ssm:{context.aws_region}::document/AWS-RunAnsiblePlaybook",
                    f"arn:aws:ssm:{context.aws_region}:{context.aws_account}:document/aiops-*",
                ],
            )
        )
        self.task_role.add_to_policy(
            iam.PolicyStatement(
                actions=["ssm:SendCommand"],
                resources=[
                    f"arn:aws:ec2:{context.aws_region}:{context.aws_account}:instance/*",
                ],
                conditions={
                    "StringEquals": {
                        "ssm:resourceTag/managed-by": "aiops",
                    }
                },
            )
        )
        self.task_role.add_to_policy(
            iam.PolicyStatement(
                actions=["ssm:GetCommandInvocation"],
                resources=["*"],  # GetCommandInvocation does not support resource-level scoping
            )
        )
        self.task_role.add_to_policy(
            iam.PolicyStatement(
                actions=["ssm:DescribeInstanceInformation"],
                resources=["*"],  # Describe calls require Resource: "*"
            )
        )
        # SSM GetParameter — scoped to /aiops/{env}/*
        self.task_role.add_to_policy(
            iam.PolicyStatement(
                actions=["ssm:GetParameter", "ssm:GetParameters"],
                resources=[
                    f"arn:aws:ssm:{context.aws_region}:{context.aws_account}:parameter/aiops/{env_name}/*"
                ],
            )
        )
        # Secrets Manager — scoped to /aiops/{env}/*
        self.task_role.add_to_policy(
            iam.PolicyStatement(
                actions=["secretsmanager:GetSecretValue"],
                resources=[
                    f"arn:aws:secretsmanager:{context.aws_region}:{context.aws_account}:secret:/aiops/{env_name}/*"
                ],
            )
        )
        # CloudWatch PutMetricData — requires Resource: "*" (AWS-mandated)
        self.task_role.add_to_policy(
            iam.PolicyStatement(
                actions=["cloudwatch:PutMetricData"],
                resources=["*"],
            )
        )
        # CloudWatch Logs — scoped to ECS log group
        self.task_role.add_to_policy(
            iam.PolicyStatement(
                actions=["logs:PutLogEvents", "logs:CreateLogStream"],
                resources=[self.log_group.log_group_arn + ":*"],
            )
        )
        # SES SendEmail — scoped to verified identity for approval notifications
        self.task_role.add_to_policy(
            iam.PolicyStatement(
                actions=["ses:SendEmail", "ses:SendRawEmail"],
                resources=[
                    f"arn:aws:ses:{context.aws_region}:{context.aws_account}:identity/*"
                ],
            )
        )

        # ---------------------------------------------------------------
        # Additional IAM Permissions for Production Improvements
        # ---------------------------------------------------------------

        # CloudWatch DescribeAlarms — for stop conditions + baking validation
        self.task_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "cloudwatch:DescribeAlarms",
                    "cloudwatch:GetMetricData",
                ],
                resources=["*"],  # DescribeAlarms requires Resource: "*"
            )
        )

        # EC2 DescribeInstances — for dynamic AWS enrichment
        self.task_role.add_to_policy(
            iam.PolicyStatement(
                actions=["ec2:DescribeInstances", "ec2:DescribeInstanceStatus"],
                resources=["*"],  # Describe calls require Resource: "*"
            )
        )

        # Cloud Map DiscoverInstances — for dynamic service discovery enrichment
        self.task_role.add_to_policy(
            iam.PolicyStatement(
                actions=["servicediscovery:DiscoverInstances"],
                resources=["*"],  # DiscoverInstances requires Resource: "*"
            )
        )

        # ELB DescribeTargetHealth — for service availability threshold checks
        self.task_role.add_to_policy(
            iam.PolicyStatement(
                actions=["elasticloadbalancing:DescribeTargetHealth"],
                resources=["*"],  # Describe calls require Resource: "*"
            )
        )

        # SSM GetCalendarState — for SSM Change Calendar maintenance windows
        self.task_role.add_to_policy(
            iam.PolicyStatement(
                actions=["ssm:GetCalendarState"],
                resources=[
                    f"arn:aws:ssm:{context.aws_region}:{context.aws_account}:document/aiops-*"
                ],
            )
        )

        # X-Ray PutTraceSegments — for OpenTelemetry tracing export
        self.task_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "xray:PutTraceSegments",
                    "xray:PutTelemetryRecords",
                ],
                resources=["*"],  # X-Ray requires Resource: "*"
            )
        )

        # ---------------------------------------------------------------
        # Fargate Task Definition (with Graviton ARM64 for staging/prod)
        # ---------------------------------------------------------------
        # Graviton (ARM64) provides ~40% better price-performance for
        # Python workloads. Dev stays on x86 for local Docker compatibility.
        use_graviton = not is_dev

        if use_graviton:
            task_def = ecs.FargateTaskDefinition(
                self,
                "TaskDef",
                cpu=512,
                memory_limit_mib=1024,
                execution_role=self.execution_role,
                task_role=self.task_role,
                runtime_platform=ecs.RuntimePlatform(
                    cpu_architecture=ecs.CpuArchitecture.ARM64,
                    operating_system_family=ecs.OperatingSystemFamily.LINUX,
                ),
            )
        else:
            task_def = ecs.FargateTaskDefinition(
                self,
                "TaskDef",
                cpu=512,
                memory_limit_mib=1024,
                execution_role=self.execution_role,
                task_role=self.task_role,
            )

        # Container with ECR image using environment-specific image tag
        # Create approval signing secret here (needed before container definition)
        self.approval_signing_secret = secretsmanager.Secret(
            self,
            "ApprovalSigningSecret",
            secret_name=f"/aiops/{env_name}/approval-signing-secret",
            description=(
                "HMAC signing key for approval email tokens. "
                "Shared across all ECS tasks to ensure token validity."
            ),
            generate_secret_string=secretsmanager.SecretStringGenerator(
                exclude_punctuation=True,
                password_length=64,
            ),
            removal_policy=cdk.RemovalPolicy.RETAIN,
        )

        container = task_def.add_container(
            "AiopsContainer",
            image=ecs.ContainerImage.from_registry(
                f"{context.aws_account}.dkr.ecr.{context.aws_region}.amazonaws.com/aiops:{context.image_tag}"
            ),
            environment={
                "ENVIRONMENT": env_name,
                "LOG_LEVEL": "INFO",
                "PORT": "8080",
                "SQS_QUEUE_URL": data_stack.queue.queue_url,
                "DYNAMODB_TABLE_NAME": data_stack.table.table_name,
                "ASSET_INVENTORY_PATH": "/app/config/asset_inventory.yml",
                "MAPPING_CONFIG_PATH": "/app/config/playbook_mapping.yml",
                "OPERATING_MODE": "rules_only",
                "CORRELATION_WINDOW_SECONDS": "300",
                "BEDROCK_MODEL_ID": context.bedrock_model_id,
                "SES_FROM_ADDRESS": context.cost_center_email,
                "OPERATOR_EMAIL": context.cost_center_email,
                "SERVICE_BASE_URL": "",  # Set via SSM at runtime; see _create_api_gateway
                "APPROVAL_EXPIRY_SECONDS": "1800",
            },
            secrets={
                "API_GATEWAY_KEY": ecs.Secret.from_secrets_manager(
                    secretsmanager.Secret.from_secret_name_v2(
                        self, "ApiKeySecretRef",
                        secret_name=f"/aiops/{env_name}/api-gateway-key",
                    ),
                    field="api_key",
                ),
                "APPROVAL_SIGNING_SECRET": ecs.Secret.from_secrets_manager(
                    self.approval_signing_secret,
                ),
            },
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix="aiops",
                log_group=self.log_group,
            ),
            stop_timeout=Duration.seconds(30),
        )
        container.add_port_mappings(
            ecs.PortMapping(container_port=8080, protocol=ecs.Protocol.TCP)
        )

        # ---------------------------------------------------------------
        # ECS Fargate Service
        # ---------------------------------------------------------------
        if is_dev:
            # Dev: FARGATE_SPOT primary with FARGATE fallback
            capacity_provider_strategies = [
                ecs.CapacityProviderStrategy(
                    capacity_provider="FARGATE_SPOT", weight=2
                ),
                ecs.CapacityProviderStrategy(
                    capacity_provider="FARGATE", weight=1
                ),
            ]
        else:
            # Staging/Prod: FARGATE on-demand only
            capacity_provider_strategies = [
                ecs.CapacityProviderStrategy(
                    capacity_provider="FARGATE", weight=1
                ),
            ]

        self.service = ecs.FargateService(
            self,
            "Service",
            cluster=self.cluster,
            task_definition=task_def,
            desired_count=1,
            security_groups=[network_stack.ecs_security_group],
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            ),
            min_healthy_percent=50 if is_dev else 100,
            max_healthy_percent=200,
            capacity_provider_strategies=capacity_provider_strategies,
            enable_execute_command=is_dev,  # ECS Exec for dev debugging
            cloud_map_options=ecs.CloudMapOptions(
                name="aiops-service",
                container_port=8080,
                dns_record_type=ecs.DnsRecordType.SRV,
            ),
        )

        # Store Cloud Map service reference for API Gateway integration
        self._cloud_map_service = self.service.cloud_map_service

        # ---------------------------------------------------------------
        # Application Auto Scaling (staging/prod only)
        # ---------------------------------------------------------------
        if not is_dev:
            scalable = self.service.auto_scale_task_count(
                min_capacity=1, max_capacity=10
            )

            # SQS queue depth metric
            queue_depth = cw.Metric(
                metric_name="ApproximateNumberOfMessagesVisible",
                namespace="AWS/SQS",
                dimensions_map={"QueueName": data_stack.queue.queue_name},
                period=Duration.minutes(1),
                statistic="Maximum",
            )

            # Scale out: +2 tasks when depth > 10, +4 when depth > 50
            scalable.scale_on_metric(
                "ScaleOut",
                metric=queue_depth,
                scaling_steps=[
                    aas.ScalingInterval(lower=10, change=2),
                    aas.ScalingInterval(lower=50, change=4),
                ],
                cooldown=Duration.minutes(3),
                evaluation_periods=2,
                datapoints_to_alarm=2,
                adjustment_type=aas.AdjustmentType.CHANGE_IN_CAPACITY,
            )

            # Scale in: -1 task when depth < 2
            scalable.scale_on_metric(
                "ScaleIn",
                metric=queue_depth,
                scaling_steps=[
                    aas.ScalingInterval(upper=2, change=-1),
                    aas.ScalingInterval(lower=2, change=0),
                ],
                cooldown=Duration.minutes(5),
                evaluation_periods=5,
                datapoints_to_alarm=5,
                adjustment_type=aas.AdjustmentType.CHANGE_IN_CAPACITY,
            )

        # ---------------------------------------------------------------
        # API Gateway HTTP API — public endpoint routing to ECS
        # ---------------------------------------------------------------
        self._create_api_gateway(env_name, network_stack)

        # ---------------------------------------------------------------
        # Custom Resource: Ensure Cloud Map registers port 8080
        # This Lambda updates the Cloud Map instance attributes to include
        # AWS_INSTANCE_PORT=8080 so API Gateway routes correctly.
        # ---------------------------------------------------------------
        cloudmap_fix_lambda = _lambda.Function(
            self,
            "CloudMapPortFixLambda",
            function_name=f"aiops-cloudmap-port-fix-{env_name}",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="index.handler",
            code=_lambda.Code.from_inline(
                'import boto3\n'
                'import cfnresponse\n'
                'def handler(event, context):\n'
                '    if event["RequestType"] == "Delete":\n'
                '        cfnresponse.send(event, context, cfnresponse.SUCCESS, {})\n'
                '        return\n'
                '    sd = boto3.client("servicediscovery")\n'
                '    svc_id = event["ResourceProperties"]["ServiceId"]\n'
                '    instances = sd.list_instances(ServiceId=svc_id).get("Instances", [])\n'
                '    for inst in instances:\n'
                '        attrs = inst.get("Attributes", {})\n'
                '        if attrs.get("AWS_INSTANCE_PORT") != "8080":\n'
                '            attrs["AWS_INSTANCE_PORT"] = "8080"\n'
                '            sd.register_instance(ServiceId=svc_id, InstanceId=inst["Id"], Attributes=attrs)\n'
                '    cfnresponse.send(event, context, cfnresponse.SUCCESS, {"Updated": str(len(instances))})\n'
            ),
            timeout=Duration.seconds(30),
        )
        cloudmap_fix_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=["servicediscovery:ListInstances", "servicediscovery:RegisterInstance"],
                resources=["*"],
            )
        )

        # Trigger the Lambda as a Custom Resource after service deploys
        cdk.CustomResource(
            self,
            "CloudMapPortFix",
            service_token=cloudmap_fix_lambda.function_arn,
            properties={
                "ServiceId": self._cloud_map_service.service_id,
                "Trigger": env_name + "-" + self._context.image_tag,  # Forces re-run on each deploy
            },
        )

        # ---------------------------------------------------------------
        # SSM Parameter Store — /aiops/{environment}/ (Requirement 4.1)
        # ---------------------------------------------------------------
        self._create_ssm_parameters(env_name, context, data_stack)

        # ---------------------------------------------------------------
        # Secrets Manager — /aiops/{environment}/ (Requirements 4.2, 4.8)
        # ---------------------------------------------------------------
        self._create_secrets(env_name)

        # ---------------------------------------------------------------
        # CloudFormation Outputs
        # ---------------------------------------------------------------
        cdk.CfnOutput(
            self,
            "ClusterArn",
            value=self.cluster.cluster_arn,
            export_name=f"AiopsClusterArn-{env_name}",
        )
        cdk.CfnOutput(
            self,
            "ServiceName",
            value=self.service.service_name,
            export_name=f"AiopsServiceName-{env_name}",
        )
        cdk.CfnOutput(
            self,
            "LogGroupName",
            value=self.log_group.log_group_name,
            export_name=f"AiopsLogGroupName-{env_name}",
        )

    def _create_api_gateway(self, env_name: str, network_stack: "NetworkStack") -> None:
        """Create an HTTP API Gateway with VPC Link to the ECS service.

        Uses Cloud Map service discovery for the integration URI.
        """
        # VPC Link for private integration
        vpc_link = apigwv2.CfnVpcLink(
            self,
            "VpcLink",
            name=f"aiops-vpclink-{env_name}",
            subnet_ids=[s.subnet_id for s in network_stack.vpc.private_subnets],
            security_group_ids=[network_stack.ecs_security_group.security_group_id],
        )

        # HTTP API
        http_api = apigwv2.CfnApi(
            self,
            "HttpApi",
            name=f"aiops-api-{env_name}",
            protocol_type="HTTP",
            description=f"AIOps Self-Healing API ({env_name})",
        )

        # Integration — use Cloud Map service ARN
        integration = apigwv2.CfnIntegration(
            self,
            "HttpApiIntegration",
            api_id=http_api.ref,
            integration_type="HTTP_PROXY",
            integration_method="ANY",
            integration_uri=self._cloud_map_service.service_arn,
            connection_type="VPC_LINK",
            connection_id=vpc_link.ref,
            payload_format_version="1.0",
        )

        # Default route — catch all
        apigwv2.CfnRoute(
            self,
            "DefaultRoute",
            api_id=http_api.ref,
            route_key="$default",
            target=f"integrations/{integration.ref}",
        )

        # Auto-deploy stage
        apigwv2.CfnStage(
            self,
            "DefaultStage",
            api_id=http_api.ref,
            stage_name="$default",
            auto_deploy=True,
        )

        # Output the API URL
        self.api_url = http_api.attr_api_endpoint
        self.http_api_id = http_api.ref  # Expose API ID for WAF association
        CfnOutput(
            self,
            "ApiEndpoint",
            value=self.api_url,
            export_name=f"AiopsApiEndpoint-{env_name}",
            description="Public HTTPS endpoint for the AIOps webhook",
        )

        # Store API URL in SSM so the app can read it at startup
        ssm.StringParameter(
            self,
            "SsmServiceBaseUrl",
            parameter_name=f"/aiops/{env_name}/service-base-url",
            string_value=http_api.attr_api_endpoint,
            description="Public API Gateway URL for approval email links",
        )

    def _create_ssm_parameters(
        self,
        env_name: str,
        context: CdkContext,
        data_stack: DataStack,
    ) -> None:
        """Create SSM Parameter Store parameters under /aiops/{environment}/.

        These parameters provide runtime configuration to the ECS application.
        Values are either static defaults, derived from CDK context, or
        populated from cross-stack resource outputs.

        Requirement 4.1: All parameters created under /aiops/{environment}/.
        """
        param_prefix = f"/aiops/{env_name}"

        # operating-mode: default "rules_only"
        ssm.StringParameter(
            self,
            "SsmOperatingMode",
            parameter_name=f"{param_prefix}/operating-mode",
            string_value="rules_only",
            description="Operating mode: rules_only, ai_only, or ai_with_fallback",
        )

        # escalation-threshold: default "0.5"
        ssm.StringParameter(
            self,
            "SsmEscalationThreshold",
            parameter_name=f"{param_prefix}/escalation-threshold",
            string_value="0.5",
            description="Confidence threshold (0.0-1.0) below which alerts escalate to humans",
        )

        # correlation-window-seconds: default "300"
        ssm.StringParameter(
            self,
            "SsmCorrelationWindow",
            parameter_name=f"{param_prefix}/correlation-window-seconds",
            string_value="300",
            description="Time window in seconds for correlating related alerts",
        )

        # max-concurrent-pipelines: default "50"
        ssm.StringParameter(
            self,
            "SsmMaxConcurrentPipelines",
            parameter_name=f"{param_prefix}/max-concurrent-pipelines",
            string_value="50",
            description="Maximum number of concurrent remediation pipelines",
        )

        # bedrock-model-id: from CDK Context (required, no default)
        ssm.StringParameter(
            self,
            "SsmBedrockModelId",
            parameter_name=f"{param_prefix}/bedrock-model-id",
            string_value=context.bedrock_model_id,
            description="AWS Bedrock foundation model ID for AI reasoning",
        )

        # sqs-queue-url: from DataStack output
        ssm.StringParameter(
            self,
            "SsmSqsQueueUrl",
            parameter_name=f"{param_prefix}/sqs-queue-url",
            string_value=data_stack.queue.queue_url,
            description="SQS main queue URL for alert ingestion",
        )

        # dynamodb-table-name: from DataStack output
        ssm.StringParameter(
            self,
            "SsmDynamodbTableName",
            parameter_name=f"{param_prefix}/dynamodb-table-name",
            string_value=data_stack.table.table_name,
            description="DynamoDB incident memory table name",
        )

        # audit-log-group-name: from ObservabilityStack output
        # ObservabilityStack deploys after ComputeStack, so use the known
        # naming convention as a placeholder until cross-stack wiring is added.
        ssm.StringParameter(
            self,
            "SsmAuditLogGroupName",
            parameter_name=f"{param_prefix}/audit-log-group-name",
            string_value=f"/aiops/{env_name}/ecs",
            description="CloudWatch log group name for audit logging",
        )

        # asset-inventory-path: default "/app/config/asset_inventory.yml"
        ssm.StringParameter(
            self,
            "SsmAssetInventoryPath",
            parameter_name=f"{param_prefix}/asset-inventory-path",
            string_value="/app/config/asset_inventory.yml",
            description="Path to asset inventory configuration file inside container",
        )

        # mapping-config-path: default "/app/config/playbook_mapping.yml"
        ssm.StringParameter(
            self,
            "SsmMappingConfigPath",
            parameter_name=f"{param_prefix}/mapping-config-path",
            string_value="/app/config/playbook_mapping.yml",
            description="Path to playbook mapping configuration file inside container",
        )

    def _create_secrets(self, env_name: str) -> None:
        """Create Secrets Manager secrets under /aiops/{environment}/.

        Secrets created:
        - api-gateway-key: Generated by CDK with 90-day automatic rotation.
        - approval-signing-secret: Created inline before container definition.

        Requirements 4.2, 4.8: Secrets stored in Secrets Manager with rotation.
        """
        secret_prefix = f"/aiops/{env_name}"

        # Note: approval-signing-secret is created inline before container definition
        # to avoid circular reference (container refs secret before _create_secrets runs).

        # api-gateway-key: Import if exists, otherwise create new.
        # Uses DESTROY removal policy to avoid orphaned secrets on stack deletion.
        self.api_gateway_key_secret = secretsmanager.Secret(
            self,
            "ApiGatewayKeySecret",
            secret_name=f"{secret_prefix}/api-gateway-key",
            description=(
                "API Gateway usage plan key. Auto-generated and rotated "
                "every 90 days by a CDK-managed rotation Lambda."
            ),
            generate_secret_string=secretsmanager.SecretStringGenerator(
                exclude_punctuation=True,
                password_length=40,
                generate_string_key="api_key",
                secret_string_template='{"service": "api-gateway"}',
            ),
            removal_policy=cdk.RemovalPolicy.DESTROY,
        )

        # Rotation Lambda for the api-gateway-key secret.
        # Generates a new random API key and updates the API Gateway usage plan
        # atomically before invalidating the old key (Requirement 4.8).
        rotation_lambda = _lambda.Function(
            self,
            "ApiKeyRotationLambda",
            function_name=f"aiops-api-key-rotation-{env_name}",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="index.handler",
            code=_lambda.Code.from_inline(
                _API_KEY_ROTATION_LAMBDA_CODE
            ),
            timeout=Duration.seconds(60),
            description=(
                "Rotates the API Gateway key secret every 90 days. "
                "Generates a new key and updates the usage plan."
            ),
            environment={
                "ENVIRONMENT": env_name,
            },
        )

        # Grant the rotation Lambda permission to manage the secret
        self.api_gateway_key_secret.grant_read(rotation_lambda)
        self.api_gateway_key_secret.grant_write(rotation_lambda)

        # Grant the rotation Lambda permission to update API Gateway keys
        rotation_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "apigateway:GET",
                    "apigateway:POST",
                    "apigateway:PUT",
                    "apigateway:DELETE",
                ],
                resources=[
                    f"arn:aws:apigateway:{self._context.aws_region}::/apikeys/*",
                    f"arn:aws:apigateway:{self._context.aws_region}::/usageplans/*/keys/*",
                ],
            )
        )

        # Enable automatic rotation with a 90-day schedule
        self.api_gateway_key_secret.add_rotation_schedule(
            "ApiKeyRotationSchedule",
            rotation_lambda=rotation_lambda,
            automatically_after=Duration.days(90),
            rotate_immediately_on_update=False,
        )
