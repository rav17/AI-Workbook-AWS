"""NetworkStack — VPC, subnets, NAT Gateway, and VPC endpoints."""

from typing import Any

import aws_cdk as cdk
from aws_cdk import aws_ec2 as ec2
from constructs import Construct

from ..context import CdkContext


class NetworkStack(cdk.Stack):
    """Provisions VPC, subnets, NAT Gateway, security groups, and VPC endpoints.

    Exports:
        vpc: The VPC resource.
        private_subnets: List of private subnets.
        ecs_security_group: Security group for ECS tasks.
        vpc_endpoints_security_group: Security group for VPC Interface endpoints.
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

        # VPC with 2 AZs, 2 public + 2 private subnets
        # Dev/staging: 1 NAT GW (cost savings)
        # Prod: 2 NAT GWs (one per AZ for high availability)
        is_prod = context.environment == "prod"
        self.vpc = ec2.Vpc(
            self,
            "Vpc",
            ip_addresses=ec2.IpAddresses.cidr(context.vpc_cidr),
            max_azs=2,
            nat_gateways=2 if is_prod else 1,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="Public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24,
                ),
                ec2.SubnetConfiguration(
                    name="Private",
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                    cidr_mask=24,
                ),
            ],
        )

        # ECS tasks security group — HTTPS outbound + self-referencing ingress for VPC Link
        self.ecs_security_group = ec2.SecurityGroup(
            self,
            "EcsTasksSg",
            vpc=self.vpc,
            description="Security group for ECS Fargate tasks",
            allow_all_outbound=False,
        )
        self.ecs_security_group.add_egress_rule(
            ec2.Peer.any_ipv4(),
            ec2.Port.tcp(443),
            "Allow HTTPS outbound",
        )
        # Allow API Gateway VPC Link to reach ECS tasks on port 8080
        # (VPC Link shares this security group, so self-referencing is required)
        self.ecs_security_group.add_ingress_rule(
            self.ecs_security_group,
            ec2.Port.tcp(8080),
            "Allow inbound from VPC Link on container port",
        )
        # Allow VPC Link egress to ECS tasks on port 8080 (within VPC)
        self.ecs_security_group.add_egress_rule(
            self.ecs_security_group,
            ec2.Port.tcp(8080),
            "Allow outbound to ECS tasks on container port",
        )

        # VPC endpoints security group — HTTPS inbound from ECS tasks SG only
        self.vpc_endpoints_security_group = ec2.SecurityGroup(
            self,
            "VpcEndpointsSg",
            vpc=self.vpc,
            description="Security group for VPC Interface endpoints",
            allow_all_outbound=False,
        )
        self.vpc_endpoints_security_group.add_ingress_rule(
            self.ecs_security_group,
            ec2.Port.tcp(443),
            "Allow HTTPS from ECS tasks",
        )

        # Store private subnets for cross-stack reference
        self.private_subnets = self.vpc.private_subnets

        # --- VPC Gateway Endpoints (free, route-table based) ---
        # DynamoDB Gateway Endpoint — eliminates NAT charges for DynamoDB traffic
        self.vpc.add_gateway_endpoint(
            "DynamoDbEndpoint",
            service=ec2.GatewayVpcEndpointAwsService.DYNAMODB,
        )

        # S3 Gateway Endpoint — for ECR image layer pulls and canary artifacts
        self.vpc.add_gateway_endpoint(
            "S3Endpoint",
            service=ec2.GatewayVpcEndpointAwsService.S3,
        )

        # --- VPC Interface Endpoints (private IP based, billed per AZ-hour) ---
        # These reduce latency and eliminate NAT data processing charges for
        # high-volume AWS API calls from ECS tasks.

        # SQS Interface Endpoint
        self.vpc.add_interface_endpoint(
            "SqsEndpoint",
            service=ec2.InterfaceVpcEndpointAwsService.SQS,
            security_groups=[self.vpc_endpoints_security_group],
            subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
        )

        # SSM Interface Endpoint (for parameter store and send command)
        self.vpc.add_interface_endpoint(
            "SsmEndpoint",
            service=ec2.InterfaceVpcEndpointAwsService.SSM,
            security_groups=[self.vpc_endpoints_security_group],
            subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
        )

        # SSM Messages Endpoint (for SSM RunCommand output)
        self.vpc.add_interface_endpoint(
            "SsmMessagesEndpoint",
            service=ec2.InterfaceVpcEndpointAwsService.SSM_MESSAGES,
            security_groups=[self.vpc_endpoints_security_group],
            subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
        )

        # CloudWatch Logs Interface Endpoint
        self.vpc.add_interface_endpoint(
            "LogsEndpoint",
            service=ec2.InterfaceVpcEndpointAwsService.CLOUDWATCH_LOGS,
            security_groups=[self.vpc_endpoints_security_group],
            subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
        )

        # Secrets Manager Interface Endpoint
        self.vpc.add_interface_endpoint(
            "SecretsManagerEndpoint",
            service=ec2.InterfaceVpcEndpointAwsService.SECRETS_MANAGER,
            security_groups=[self.vpc_endpoints_security_group],
            subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
        )

        # Bedrock Runtime Interface Endpoint (for AI reasoning calls)
        self.vpc.add_interface_endpoint(
            "BedrockRuntimeEndpoint",
            service=ec2.InterfaceVpcEndpointAwsService("bedrock-runtime"),
            security_groups=[self.vpc_endpoints_security_group],
            subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
        )
