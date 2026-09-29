"""VpcEndpoints construct — provisions 9 VPC endpoints for AWS service access."""

from aws_cdk import aws_ec2 as ec2
from constructs import Construct

INTERFACE_SERVICES = [
    ec2.InterfaceVpcEndpointAwsService.ECR,
    ec2.InterfaceVpcEndpointAwsService.ECR_DOCKER,
    ec2.InterfaceVpcEndpointAwsService.SQS,
    ec2.InterfaceVpcEndpointAwsService.SSM,
    ec2.InterfaceVpcEndpointAwsService.SECRETS_MANAGER,
    ec2.InterfaceVpcEndpointAwsService.CLOUDWATCH_LOGS,
    ec2.InterfaceVpcEndpointAwsService.BEDROCK_RUNTIME,
]


class VpcEndpoints(Construct):
    """Provisions gateway and interface VPC endpoints for AWS service access.

    Gateway endpoints (free, route via route table):
        - S3
        - DynamoDB

    Interface endpoints (ENI in private subnets):
        - ECR API
        - ECR Docker
        - SQS
        - SSM
        - Secrets Manager
        - CloudWatch Logs
        - Bedrock Runtime
    """

    def __init__(
        self,
        scope: Construct,
        id: str,
        vpc: ec2.Vpc,
        sg: ec2.SecurityGroup,
    ) -> None:
        super().__init__(scope, id)

        # Gateway endpoints (free, route via route table)
        vpc.add_gateway_endpoint(
            "S3Endpoint",
            service=ec2.GatewayVpcEndpointAwsService.S3,
        )
        vpc.add_gateway_endpoint(
            "DynamoDbEndpoint",
            service=ec2.GatewayVpcEndpointAwsService.DYNAMODB,
        )

        # Interface endpoints (ENI in private subnets)
        for svc in INTERFACE_SERVICES:
            vpc.add_interface_endpoint(
                f"{svc.short_name}Endpoint",
                service=svc,
                subnets=ec2.SubnetSelection(
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                ),
                security_groups=[sg],
                private_dns_enabled=True,
            )
