"""CDK stack definitions for the AIOps Self-Healing Infrastructure.

Contains the four layered stacks:
- NetworkStack: VPC, subnets, NAT Gateway, VPC endpoints
- DataStack: DynamoDB, SQS queues, KMS keys
- ComputeStack: ECS cluster, Fargate service, IAM roles
- ObservabilityStack: CloudWatch alarms, dashboards, SNS topics
"""
