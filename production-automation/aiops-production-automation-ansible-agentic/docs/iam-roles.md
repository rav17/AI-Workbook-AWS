# IAM Roles for GitHub Actions CI/CD

This document defines the IAM OIDC provider configuration, trust policies, and permission policies required for GitHub Actions CI/CD pipelines to deploy the AIOps Self-Healing Infrastructure application.

## Prerequisites

- An AWS account with the GitHub Actions OIDC provider configured
- The ECR repository `aiops-self-healing` created in the target account
- CDK bootstrap completed in the target account/region

---

## IAM OIDC Provider

Before creating the roles, register the GitHub OIDC identity provider in your AWS account:

```json
{
  "Url": "https://token.actions.githubusercontent.com",
  "ClientIdList": ["sts.amazonaws.com"],
  "ThumbprintList": ["6938fd4d98bab03faadb97b34396831e3780aea1"]
}
```

AWS CLI command:

```bash
aws iam create-open-id-connect-provider \
  --url "https://token.actions.githubusercontent.com" \
  --client-id-list "sts.amazonaws.com" \
  --thumbprint-list "6938fd4d98bab03faadb97b34396831e3780aea1"
```

---

## CI Role: `aiops-github-ci-role`

The CI role is used during the CI pipeline for ECR push/scan and CDK synthesis (read-only).

### Trust Policy

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::{account}:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        },
        "StringLike": {
          "token.actions.githubusercontent.com:sub": "repo:{owner}/{repo}:ref:refs/heads/*"
        }
      }
    }
  ]
}
```

**Placeholders:**
- `{account}` — Your 12-digit AWS account ID (e.g., `123456789012`)
- `{owner}` — GitHub organization or user (e.g., `my-org`)
- `{repo}` — GitHub repository name (e.g., `aiops-production-automation-ansible-agentic`)

### Permission Policy: `aiops-ci-policy`

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ECRLogin",
      "Effect": "Allow",
      "Action": [
        "ecr:GetAuthorizationToken"
      ],
      "Resource": "*"
    },
    {
      "Sid": "ECRPushAndScan",
      "Effect": "Allow",
      "Action": [
        "ecr:BatchCheckLayerAvailability",
        "ecr:GetDownloadUrlForLayer",
        "ecr:BatchGetImage",
        "ecr:PutImage",
        "ecr:InitiateLayerUpload",
        "ecr:UploadLayerPart",
        "ecr:CompleteLayerUpload",
        "ecr:DescribeImageScanFindings",
        "ecr:StartImageScan",
        "ecr:DescribeImages",
        "ecr:DescribeRepositories"
      ],
      "Resource": "arn:aws:ecr:{region}:{account}:repository/aiops-self-healing"
    },
    {
      "Sid": "CDKSynthReadOnly",
      "Effect": "Allow",
      "Action": [
        "cloudformation:DescribeStacks",
        "cloudformation:ListStacks",
        "cloudformation:GetTemplate",
        "cloudformation:GetTemplateSummary"
      ],
      "Resource": "arn:aws:cloudformation:{region}:{account}:stack/Aiops*/*"
    },
    {
      "Sid": "CDKBootstrapLookup",
      "Effect": "Allow",
      "Action": [
        "ssm:GetParameter"
      ],
      "Resource": "arn:aws:ssm:{region}:{account}:parameter/cdk-bootstrap/*"
    },
    {
      "Sid": "STSGetCallerIdentity",
      "Effect": "Allow",
      "Action": [
        "sts:GetCallerIdentity"
      ],
      "Resource": "*"
    }
  ]
}
```

**Placeholders:**
- `{account}` — Your 12-digit AWS account ID
- `{region}` — Target AWS region (e.g., `us-east-1`)

---

## CD Role: `aiops-github-cd-role`

The CD role is used during the CD pipeline for CDK deployments, SSM parameter operations, and ECS service updates.

### Trust Policy

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::{account}:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        },
        "StringLike": {
          "token.actions.githubusercontent.com:sub": "repo:{owner}/{repo}:ref:refs/heads/*"
        }
      }
    }
  ]
}
```

### Permission Policy: `aiops-cd-policy`

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "CloudFormationDeploy",
      "Effect": "Allow",
      "Action": [
        "cloudformation:CreateStack",
        "cloudformation:UpdateStack",
        "cloudformation:DeleteStack",
        "cloudformation:DescribeStacks",
        "cloudformation:DescribeStackEvents",
        "cloudformation:DescribeStackResources",
        "cloudformation:GetTemplate",
        "cloudformation:GetTemplateSummary",
        "cloudformation:ListStacks",
        "cloudformation:CreateChangeSet",
        "cloudformation:DescribeChangeSet",
        "cloudformation:ExecuteChangeSet",
        "cloudformation:DeleteChangeSet",
        "cloudformation:ListChangeSets",
        "cloudformation:SetStackPolicy"
      ],
      "Resource": "arn:aws:cloudformation:{region}:{account}:stack/Aiops*/*"
    },
    {
      "Sid": "CDKBootstrapAccess",
      "Effect": "Allow",
      "Action": [
        "cloudformation:DescribeStacks",
        "cloudformation:GetTemplate"
      ],
      "Resource": "arn:aws:cloudformation:{region}:{account}:stack/CDKToolkit/*"
    },
    {
      "Sid": "CDKStagingBucket",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:ListBucket",
        "s3:GetBucketLocation",
        "s3:DeleteObject"
      ],
      "Resource": [
        "arn:aws:s3:::cdk-*-assets-{account}-{region}",
        "arn:aws:s3:::cdk-*-assets-{account}-{region}/*"
      ]
    },
    {
      "Sid": "ECSServiceManagement",
      "Effect": "Allow",
      "Action": [
        "ecs:CreateCluster",
        "ecs:DeleteCluster",
        "ecs:DescribeClusters",
        "ecs:CreateService",
        "ecs:UpdateService",
        "ecs:DeleteService",
        "ecs:DescribeServices",
        "ecs:RegisterTaskDefinition",
        "ecs:DeregisterTaskDefinition",
        "ecs:DescribeTaskDefinition",
        "ecs:ListTasks",
        "ecs:DescribeTasks"
      ],
      "Resource": [
        "arn:aws:ecs:{region}:{account}:cluster/aiops-*",
        "arn:aws:ecs:{region}:{account}:service/aiops-*/*",
        "arn:aws:ecs:{region}:{account}:task-definition/Aiops*:*"
      ]
    },
    {
      "Sid": "ECSTaskDefinitionGlobal",
      "Effect": "Allow",
      "Action": [
        "ecs:RegisterTaskDefinition",
        "ecs:DeregisterTaskDefinition",
        "ecs:DescribeTaskDefinition",
        "ecs:ListTaskDefinitions"
      ],
      "Resource": "*"
    },
    {
      "Sid": "SQSManagement",
      "Effect": "Allow",
      "Action": [
        "sqs:CreateQueue",
        "sqs:DeleteQueue",
        "sqs:SetQueueAttributes",
        "sqs:GetQueueAttributes",
        "sqs:GetQueueUrl",
        "sqs:TagQueue",
        "sqs:UntagQueue",
        "sqs:ListQueueTags"
      ],
      "Resource": "arn:aws:sqs:{region}:{account}:aiops-*"
    },
    {
      "Sid": "DynamoDBManagement",
      "Effect": "Allow",
      "Action": [
        "dynamodb:CreateTable",
        "dynamodb:DeleteTable",
        "dynamodb:DescribeTable",
        "dynamodb:UpdateTable",
        "dynamodb:UpdateTimeToLive",
        "dynamodb:DescribeTimeToLive",
        "dynamodb:TagResource",
        "dynamodb:UntagResource",
        "dynamodb:ListTagsOfResource",
        "dynamodb:UpdateContinuousBackups",
        "dynamodb:DescribeContinuousBackups",
        "dynamodb:CreateBackup",
        "dynamodb:DescribeBackup"
      ],
      "Resource": "arn:aws:dynamodb:{region}:{account}:table/AiopsIncidentMemory-*"
    },
    {
      "Sid": "IAMPassRole",
      "Effect": "Allow",
      "Action": [
        "iam:PassRole"
      ],
      "Resource": [
        "arn:aws:iam::{account}:role/Aiops*"
      ],
      "Condition": {
        "StringEquals": {
          "iam:PassedToService": [
            "ecs-tasks.amazonaws.com",
            "application-autoscaling.amazonaws.com",
            "lambda.amazonaws.com"
          ]
        }
      }
    },
    {
      "Sid": "IAMRoleManagement",
      "Effect": "Allow",
      "Action": [
        "iam:CreateRole",
        "iam:DeleteRole",
        "iam:GetRole",
        "iam:UpdateRole",
        "iam:PutRolePolicy",
        "iam:DeleteRolePolicy",
        "iam:GetRolePolicy",
        "iam:AttachRolePolicy",
        "iam:DetachRolePolicy",
        "iam:ListRolePolicies",
        "iam:ListAttachedRolePolicies",
        "iam:TagRole",
        "iam:UntagRole"
      ],
      "Resource": "arn:aws:iam::{account}:role/Aiops*"
    },
    {
      "Sid": "SSMParameterOperations",
      "Effect": "Allow",
      "Action": [
        "ssm:GetParameter",
        "ssm:GetParameters",
        "ssm:GetParametersByPath",
        "ssm:PutParameter",
        "ssm:DeleteParameter",
        "ssm:AddTagsToResource",
        "ssm:RemoveTagsFromResource",
        "ssm:ListTagsForResource"
      ],
      "Resource": [
        "arn:aws:ssm:{region}:{account}:parameter/aiops/*",
        "arn:aws:ssm:{region}:{account}:parameter/cdk-bootstrap/*"
      ]
    },
    {
      "Sid": "SecretsManagerOperations",
      "Effect": "Allow",
      "Action": [
        "secretsmanager:CreateSecret",
        "secretsmanager:DeleteSecret",
        "secretsmanager:DescribeSecret",
        "secretsmanager:GetSecretValue",
        "secretsmanager:PutSecretValue",
        "secretsmanager:UpdateSecret",
        "secretsmanager:TagResource",
        "secretsmanager:UntagResource"
      ],
      "Resource": "arn:aws:secretsmanager:{region}:{account}:secret:/aiops/*"
    },
    {
      "Sid": "ECRAccess",
      "Effect": "Allow",
      "Action": [
        "ecr:GetAuthorizationToken"
      ],
      "Resource": "*"
    },
    {
      "Sid": "ECRImageAccess",
      "Effect": "Allow",
      "Action": [
        "ecr:BatchCheckLayerAvailability",
        "ecr:GetDownloadUrlForLayer",
        "ecr:BatchGetImage",
        "ecr:DescribeImages",
        "ecr:DescribeRepositories"
      ],
      "Resource": "arn:aws:ecr:{region}:{account}:repository/aiops-self-healing"
    },
    {
      "Sid": "CloudWatchLogs",
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:DeleteLogGroup",
        "logs:DescribeLogGroups",
        "logs:PutRetentionPolicy",
        "logs:DeleteRetentionPolicy",
        "logs:TagLogGroup",
        "logs:UntagLogGroup",
        "logs:ListTagsLogGroup"
      ],
      "Resource": "arn:aws:logs:{region}:{account}:log-group:/aiops/*"
    },
    {
      "Sid": "CloudWatchAlarms",
      "Effect": "Allow",
      "Action": [
        "cloudwatch:PutMetricAlarm",
        "cloudwatch:DeleteAlarms",
        "cloudwatch:DescribeAlarms",
        "cloudwatch:PutDashboard",
        "cloudwatch:DeleteDashboards",
        "cloudwatch:GetDashboard",
        "cloudwatch:ListDashboards",
        "cloudwatch:PutCompositeAlarm",
        "cloudwatch:TagResource",
        "cloudwatch:UntagResource"
      ],
      "Resource": [
        "arn:aws:cloudwatch:{region}:{account}:alarm:*aiops*",
        "arn:aws:cloudwatch::{account}:dashboard/AIOps-*"
      ]
    },
    {
      "Sid": "SNSTopicManagement",
      "Effect": "Allow",
      "Action": [
        "sns:CreateTopic",
        "sns:DeleteTopic",
        "sns:GetTopicAttributes",
        "sns:SetTopicAttributes",
        "sns:Subscribe",
        "sns:Unsubscribe",
        "sns:TagResource",
        "sns:UntagResource"
      ],
      "Resource": "arn:aws:sns:{region}:{account}:aiops-alarms-*"
    },
    {
      "Sid": "EC2VPCManagement",
      "Effect": "Allow",
      "Action": [
        "ec2:CreateVpc",
        "ec2:DeleteVpc",
        "ec2:DescribeVpcs",
        "ec2:ModifyVpcAttribute",
        "ec2:CreateSubnet",
        "ec2:DeleteSubnet",
        "ec2:DescribeSubnets",
        "ec2:CreateInternetGateway",
        "ec2:DeleteInternetGateway",
        "ec2:AttachInternetGateway",
        "ec2:DetachInternetGateway",
        "ec2:DescribeInternetGateways",
        "ec2:CreateNatGateway",
        "ec2:DeleteNatGateway",
        "ec2:DescribeNatGateways",
        "ec2:AllocateAddress",
        "ec2:ReleaseAddress",
        "ec2:DescribeAddresses",
        "ec2:CreateRouteTable",
        "ec2:DeleteRouteTable",
        "ec2:CreateRoute",
        "ec2:DeleteRoute",
        "ec2:AssociateRouteTable",
        "ec2:DisassociateRouteTable",
        "ec2:DescribeRouteTables",
        "ec2:CreateSecurityGroup",
        "ec2:DeleteSecurityGroup",
        "ec2:DescribeSecurityGroups",
        "ec2:AuthorizeSecurityGroupIngress",
        "ec2:RevokeSecurityGroupIngress",
        "ec2:AuthorizeSecurityGroupEgress",
        "ec2:RevokeSecurityGroupEgress",
        "ec2:CreateVpcEndpoint",
        "ec2:DeleteVpcEndpoints",
        "ec2:DescribeVpcEndpoints",
        "ec2:ModifyVpcEndpoint",
        "ec2:CreateTags",
        "ec2:DeleteTags",
        "ec2:DescribeTags",
        "ec2:DescribeAvailabilityZones"
      ],
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "aws:RequestedRegion": "{region}"
        }
      }
    },
    {
      "Sid": "ApplicationAutoScaling",
      "Effect": "Allow",
      "Action": [
        "application-autoscaling:RegisterScalableTarget",
        "application-autoscaling:DeregisterScalableTarget",
        "application-autoscaling:DescribeScalableTargets",
        "application-autoscaling:PutScalingPolicy",
        "application-autoscaling:DeleteScalingPolicy",
        "application-autoscaling:DescribeScalingPolicies"
      ],
      "Resource": "*"
    },
    {
      "Sid": "BudgetsManagement",
      "Effect": "Allow",
      "Action": [
        "budgets:CreateBudget",
        "budgets:ModifyBudget",
        "budgets:DeleteBudget",
        "budgets:ViewBudget",
        "budgets:DescribeBudget"
      ],
      "Resource": "arn:aws:budgets::{account}:budget/aiops-*"
    },
    {
      "Sid": "STSGetCallerIdentity",
      "Effect": "Allow",
      "Action": [
        "sts:GetCallerIdentity"
      ],
      "Resource": "*"
    }
  ]
}
```

**Placeholders:**
- `{account}` — Your 12-digit AWS account ID
- `{region}` — Target AWS region (e.g., `us-east-1`)
- `{owner}` — GitHub organization or user
- `{repo}` — GitHub repository name

---

## Setup Instructions

### 1. Create the OIDC Provider

```bash
aws iam create-open-id-connect-provider \
  --url "https://token.actions.githubusercontent.com" \
  --client-id-list "sts.amazonaws.com" \
  --thumbprint-list "6938fd4d98bab03faadb97b34396831e3780aea1"
```

### 2. Create the CI Role

```bash
# Save the CI trust policy to a file (replace placeholders first)
aws iam create-role \
  --role-name aiops-github-ci-role \
  --assume-role-policy-document file://ci-trust-policy.json \
  --description "GitHub Actions CI role for AIOps - ECR push/scan and CDK synth"

aws iam put-role-policy \
  --role-name aiops-github-ci-role \
  --policy-name aiops-ci-policy \
  --policy-document file://ci-permission-policy.json
```

### 3. Create the CD Role

```bash
# Save the CD trust policy to a file (replace placeholders first)
aws iam create-role \
  --role-name aiops-github-cd-role \
  --assume-role-policy-document file://cd-trust-policy.json \
  --description "GitHub Actions CD role for AIOps - CDK deploy, ECS, SSM, DynamoDB"

aws iam put-role-policy \
  --role-name aiops-github-cd-role \
  --policy-name aiops-cd-policy \
  --policy-document file://cd-permission-policy.json
```

### 4. Configure GitHub Repository Secrets

Add the following secrets to your GitHub repository:

| Secret Name     | Value                                                        |
|-----------------|--------------------------------------------------------------|
| `CI_ROLE_ARN`   | `arn:aws:iam::{account}:role/aiops-github-ci-role`          |
| `CD_ROLE_ARN`   | `arn:aws:iam::{account}:role/aiops-github-cd-role`          |

Add the following variables:

| Variable Name   | Value                  |
|-----------------|------------------------|
| `AWS_REGION`    | `us-east-1` (or your target region) |

---

## Security Considerations

1. **Branch scoping**: The trust policy uses `StringLike` on `sub` to scope access to all branches (`refs/heads/*`). For stricter production access, narrow this to specific branches:
   - CI: `repo:{owner}/{repo}:ref:refs/heads/main` and `repo:{owner}/{repo}:ref:refs/heads/staging`
   - CD (prod): `repo:{owner}/{repo}:ref:refs/heads/main`

2. **No long-lived credentials**: OIDC federation provides short-lived tokens (default 1 hour) — no access keys are stored in GitHub Secrets.

3. **Least privilege**: Each role has only the permissions required for its pipeline stage. The CI role cannot deploy infrastructure; the CD role cannot push images.

4. **Resource scoping**: Permissions are scoped to resource ARN patterns matching the `aiops-*` or `Aiops*` naming convention, preventing accidental modification of unrelated resources.

5. **Region locking**: EC2/VPC operations include a `aws:RequestedRegion` condition to prevent cross-region resource creation.

6. **IAM PassRole restriction**: The `iam:PassRole` permission is conditioned on the target service (`ecs-tasks`, `application-autoscaling`, `lambda`), preventing role assumption by unauthorized services.
