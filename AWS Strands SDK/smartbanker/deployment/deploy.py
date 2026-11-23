"""SmartBanker deployment script — deploys via AgentCore Runtime + Gateway.

Architecture:
  - 12 Lambda tool functions deployed via CloudFormation
  - AgentCore Gateway created with Lambda targets (tools exposed as MCP)
  - Agent deployed to AgentCore Runtime via `agentcore launch`
  - Streamlit UI connects to deployed agent

Usage: python deployment/deploy.py

Requires: aws cli, bedrock-agentcore-starter-toolkit (pip install bedrock-agentcore-starter-toolkit)
"""
import json
import os
import subprocess
import sys
import zipfile
import time

REGION = "us-east-1"
STACK_NAME = "smartbanker-tools"
S3_BUCKET = "smartbanker-lambda-deploy-533267042240"
DYNAMODB_TABLE = "smartbanker_stm"
LAMBDA_PREFIX = "smartbanker"
ACCOUNT_ID = "533267042240"
GATEWAY_NAME = "SmartBankerGateway"

LAMBDAS = {
    "transaction_fetcher": {
        "description": "Retrieves user transaction data for spending analysis",
        "params": {"user_id": {"type": "string", "description": "User identifier"}, "days": {"type": "number", "description": "Days of history"}},
        "required": ["user_id"],
    },
    "balance_checker": {
        "description": "Checks current account balances",
        "params": {"user_id": {"type": "string", "description": "User identifier"}},
        "required": ["user_id"],
    },
    "investment_data_api": {
        "description": "Retrieves market and investment data",
        "params": {"query": {"type": "string", "description": "Investment query"}, "risk_tolerance": {"type": "string", "description": "Risk level: low/medium/high"}},
        "required": ["query"],
    },
    "budgeting_calculator": {
        "description": "Calculates budget allocations and savings potential",
        "params": {"user_id": {"type": "string", "description": "User identifier"}, "income": {"type": "number", "description": "Monthly income"}, "target_savings_pct": {"type": "number", "description": "Target savings percentage"}},
        "required": ["user_id", "income"],
    },
    "service_request_processor": {
        "description": "Processes routine banking service requests",
        "params": {"request_type": {"type": "string", "description": "Type of service request"}, "description": {"type": "string", "description": "Request description"}, "user_id": {"type": "string", "description": "User identifier"}},
        "required": ["request_type", "description"],
    },
    "escalation_tracker": {
        "description": "Tracks escalation of service requests",
        "params": {"request_id": {"type": "string", "description": "Service request ID"}, "reason": {"type": "string", "description": "Escalation reason"}},
        "required": ["request_id"],
    },
    "document_guidance": {
        "description": "Provides guidance on required documents for banking operations",
        "params": {"document_type": {"type": "string", "description": "Type of document or operation"}, "user_id": {"type": "string", "description": "User identifier"}},
        "required": ["document_type"],
    },
    "loan_product_catalog": {
        "description": "Retrieves available loan products from bank catalog",
        "params": {"loan_type": {"type": "string", "description": "Type of loan"}, "user_tier": {"type": "string", "description": "User programme tier"}},
        "required": [],
    },
    "tier_pricing_engine": {
        "description": "Calculates tier-specific preferential pricing",
        "params": {"user_tier": {"type": "string", "description": "User programme tier"}, "base_rate": {"type": "number", "description": "Base interest rate"}},
        "required": [],
    },
    "activity_analyzer": {
        "description": "Analyzes user banking activity metrics",
        "params": {"user_id": {"type": "string", "description": "User identifier"}, "period_months": {"type": "number", "description": "Analysis period in months"}},
        "required": ["user_id"],
    },
    "tier_benefit_mapper": {
        "description": "Maps tier benefits to user activity for value assessment",
        "params": {"user_tier": {"type": "string", "description": "User programme tier"}},
        "required": ["user_tier"],
    },
    "compliance_rule_checker": {
        "description": "Validates requests against compliance rules",
        "params": {"request_context": {"type": "string", "description": "Request context to check"}, "rule_set": {"type": "string", "description": "Rule set to apply"}},
        "required": ["request_context"],
    },
}

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run(cmd, check=True):
    print(f"  > {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0 and check:
        print(f"  STDERR: {result.stderr.strip()[:300]}")
    return result


def step(msg):
    print(f"\n{'='*60}")
    print(f"  {msg}")
    print(f"{'='*60}")


# -----------------------------------------------------------------------
# Step 1: S3 bucket
# -----------------------------------------------------------------------
def create_s3_bucket():
    step("Step 1: Create S3 bucket for Lambda packages")
    result = run(f"aws s3 mb s3://{S3_BUCKET} --region {REGION}", check=False)
    if result.returncode == 0 or "BucketAlreadyOwnedByYou" in result.stderr:
        print(f"  Bucket {S3_BUCKET} ready")
    else:
        print(f"  Note: {result.stderr.strip()[:200]}")


# -----------------------------------------------------------------------
# Step 2: Package and upload Lambdas
# -----------------------------------------------------------------------
def package_and_upload_lambdas():
    step("Step 2: Package and upload Lambda functions")
    for name in LAMBDAS:
        handler_file = os.path.join(PROJECT_ROOT, "lambdas", name, "handler.py")
        if not os.path.exists(handler_file):
            print(f"  SKIP {name} — handler.py not found")
            continue
        zip_path = os.path.join(PROJECT_ROOT, "deployment", f"{name}.zip")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(handler_file, "handler.py")
        run(f'aws s3 cp "{zip_path}" s3://{S3_BUCKET}/lambdas/{name}.zip --region {REGION}')
        print(f"  Uploaded {name}.zip")
        os.remove(zip_path)


# -----------------------------------------------------------------------
# Step 3: DynamoDB table
# -----------------------------------------------------------------------
def create_dynamodb_table():
    step("Step 3: Create DynamoDB table")
    result = run(f"aws dynamodb describe-table --table-name {DYNAMODB_TABLE} --region {REGION}", check=False)
    if result.returncode == 0:
        print(f"  Table {DYNAMODB_TABLE} already exists")
        return
    run(
        f"aws dynamodb create-table --table-name {DYNAMODB_TABLE} "
        f"--attribute-definitions AttributeName=user_id,AttributeType=S AttributeName=timestamp,AttributeType=S "
        f"--key-schema AttributeName=user_id,KeyType=HASH AttributeName=timestamp,KeyType=RANGE "
        f"--billing-mode PAY_PER_REQUEST --region {REGION}"
    )
    print(f"  Table {DYNAMODB_TABLE} created")


# -----------------------------------------------------------------------
# Step 4: Deploy Lambda functions via CloudFormation (no API Gateway)
# -----------------------------------------------------------------------
def generate_cfn_template():
    resources = {}
    resources["ToolLambdaRole"] = {
        "Type": "AWS::IAM::Role",
        "Properties": {
            "RoleName": f"{LAMBDA_PREFIX}-tool-lambda-role",
            "AssumeRolePolicyDocument": {
                "Version": "2012-10-17",
                "Statement": [
                    {"Effect": "Allow", "Principal": {"Service": "lambda.amazonaws.com"}, "Action": "sts:AssumeRole"},
                    {"Effect": "Allow", "Principal": {"Service": "bedrock.amazonaws.com"}, "Action": "sts:AssumeRole"},
                ],
            },
            "ManagedPolicyArns": ["arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"],
            "Policies": [{
                "PolicyName": "DynamoDBAccess",
                "PolicyDocument": {
                    "Version": "2012-10-17",
                    "Statement": [{
                        "Effect": "Allow",
                        "Action": ["dynamodb:GetItem", "dynamodb:Query", "dynamodb:PutItem", "dynamodb:DeleteItem"],
                        "Resource": f"arn:aws:dynamodb:{REGION}:{ACCOUNT_ID}:table/{DYNAMODB_TABLE}",
                    }],
                },
            }],
        },
    }

    for name in LAMBDAS:
        safe = name.replace("_", "")
        resources[f"Fn{safe}"] = {
            "Type": "AWS::Lambda::Function",
            "Properties": {
                "FunctionName": f"{LAMBDA_PREFIX}-{name}",
                "Runtime": "python3.11",
                "Handler": "handler.handler",
                "Role": {"Fn::GetAtt": ["ToolLambdaRole", "Arn"]},
                "Code": {"S3Bucket": S3_BUCKET, "S3Key": f"lambdas/{name}.zip"},
                "Timeout": 30,
                "MemorySize": 256,
            },
        }

    outputs = {}
    for name in LAMBDAS:
        safe = name.replace("_", "")
        outputs[f"{safe}Arn"] = {
            "Description": f"ARN for {name} Lambda",
            "Value": {"Fn::GetAtt": [f"Fn{safe}", "Arn"]},
        }
    outputs["LambdaRoleArn"] = {
        "Description": "IAM Role ARN for Lambda tools",
        "Value": {"Fn::GetAtt": ["ToolLambdaRole", "Arn"]},
    }

    return {
        "AWSTemplateFormatVersion": "2010-09-09",
        "Description": "SmartBanker Lambda tool functions for AgentCore Gateway",
        "Resources": resources,
        "Outputs": outputs,
    }


def deploy_lambdas():
    step("Step 4: Deploy Lambda functions via CloudFormation")
    template = generate_cfn_template()
    path = os.path.join(PROJECT_ROOT, "deployment", "cfn_template.json")
    with open(path, "w") as f:
        json.dump(template, f, indent=2)
    run(f'aws s3 cp "{path}" s3://{S3_BUCKET}/cfn/smartbanker-tools.json --region {REGION}')

    result = run(f"aws cloudformation describe-stacks --stack-name {STACK_NAME} --region {REGION}", check=False)
    action = "update-stack" if result.returncode == 0 else "create-stack"
    print(f"  {action.replace('-', ' ').title()}...")

    run(
        f"aws cloudformation {action} --stack-name {STACK_NAME} "
        f"--template-url https://{S3_BUCKET}.s3.amazonaws.com/cfn/smartbanker-tools.json "
        f"--capabilities CAPABILITY_NAMED_IAM --region {REGION}"
    )


def wait_for_stack():
    step("Step 5: Waiting for CloudFormation...")
    for i in range(60):
        result = run(
            f'aws cloudformation describe-stacks --stack-name {STACK_NAME} --region {REGION} '
            f'--query "Stacks[0].StackStatus" --output text', check=False
        )
        status = result.stdout.strip()
        print(f"  [{i*10}s] {status}")
        if status in ("CREATE_COMPLETE", "UPDATE_COMPLETE"):
            return True
        if "FAILED" in status or "ROLLBACK_COMPLETE" in status:
            run(f'aws cloudformation describe-stack-events --stack-name {STACK_NAME} --region {REGION} '
                f'--query "StackEvents[?ResourceStatus==\'CREATE_FAILED\'].[LogicalResourceId,ResourceStatusReason]" --output table')
            return False
        time.sleep(10)
    return False


# -----------------------------------------------------------------------
# Step 6: Create AgentCore Gateway + add Lambda targets
# -----------------------------------------------------------------------
def create_gateway():
    step("Step 6: Create AgentCore Gateway")
    result = run(f"agentcore gateway list-mcp-gateways --region {REGION}", check=False)
    if GATEWAY_NAME in result.stdout:
        print(f"  Gateway {GATEWAY_NAME} already exists")
        # Get existing gateway details
        result = run(f"agentcore gateway get-mcp-gateway --name {GATEWAY_NAME} --region {REGION}")
        return parse_gateway_output(result.stdout)

    result = run(
        f"agentcore gateway create-mcp-gateway --name {GATEWAY_NAME} --region {REGION} --enable_semantic_search"
    )
    print(f"  Gateway {GATEWAY_NAME} created")
    return parse_gateway_output(result.stdout)


def parse_gateway_output(output):
    """Extract gateway ARN, URL, and role ARN from CLI output."""
    info = {"arn": "", "url": "", "role_arn": ""}
    for line in output.split("\n"):
        line = line.strip()
        if "arn:aws" in line and "gateway" in line.lower():
            info["arn"] = line.split()[-1] if line.split() else line
        if "gateway" in line.lower() and "amazonaws.com" in line:
            for word in line.split():
                if "amazonaws.com" in word:
                    info["url"] = word.strip("'\"")
        if "role" in line.lower() and "arn:aws:iam" in line:
            for word in line.split():
                if "arn:aws:iam" in word:
                    info["role_arn"] = word.strip("'\"")
    return info


def add_lambda_targets(gateway_info):
    step("Step 7: Add Lambda targets to AgentCore Gateway")
    gateway_arn = gateway_info.get("arn", "")
    gateway_url = gateway_info.get("url", "")
    role_arn = gateway_info.get("role_arn", "")

    if not gateway_arn:
        print("  ERROR: Could not determine gateway ARN. Add targets manually.")
        print_manual_gateway_instructions()
        return

    for name, schema in LAMBDAS.items():
        lambda_arn = f"arn:aws:lambda:{REGION}:{ACCOUNT_ID}:function:{LAMBDA_PREFIX}-{name}"
        target_config = {
            "lambdaArn": lambda_arn,
            "toolSchema": {
                "inlinePayload": [{
                    "name": name,
                    "description": schema["description"],
                    "inputSchema": {
                        "type": "object",
                        "properties": schema["params"],
                        "required": schema["required"],
                    },
                }],
            },
        }
        config_path = os.path.join(PROJECT_ROOT, "deployment", f"target_{name}.json")
        with open(config_path, "w") as f:
            json.dump(target_config, f)

        result = run(
            f'agentcore gateway create-mcp-gateway-target '
            f'--gateway-arn {gateway_arn} '
            f'--gateway-url {gateway_url} '
            f'--role-arn {role_arn} '
            f'--name {name} '
            f'--target-type lambda '
            f'--target-payload "$(type {config_path})" '
            f'--region {REGION}',
            check=False,
        )
        status = "OK" if result.returncode == 0 else "FAILED"
        print(f"  {status} {name}")
        os.remove(config_path)


# -----------------------------------------------------------------------
# Step 8: Configure and deploy agent to AgentCore Runtime
# -----------------------------------------------------------------------
def deploy_agent_runtime():
    step("Step 8: Deploy agent to AgentCore Runtime")
    print("  Configuring agent for AgentCore Runtime...")
    run(f"agentcore configure --entrypoint main.py --non-interactive", check=False)
    print("  Launching agent...")
    run("agentcore launch", check=False)
    print("  Checking status...")
    run("agentcore status", check=False)


# -----------------------------------------------------------------------
# Step 9: Smoke test
# -----------------------------------------------------------------------
def smoke_test():
    step("Step 9: Smoke test deployed Lambdas")
    tests = {
        "transaction_fetcher": {"user_id": "test", "days": 7},
        "balance_checker": {"user_id": "test"},
        "budgeting_calculator": {"user_id": "test", "income": 5000, "target_savings_pct": 20},
    }
    for name, payload in tests.items():
        func = f"{LAMBDA_PREFIX}-{name}"
        payload_str = json.dumps(payload)
        outfile = os.path.join(PROJECT_ROOT, "deployment", f"_out_{name}.json")
        result = run(
            f'aws lambda invoke --function-name {func} '
            f'--payload "{payload_str}" '
            f'--cli-binary-format raw-in-base64-out '
            f'--region {REGION} "{outfile}"',
            check=False,
        )
        if result.returncode == 0 and os.path.exists(outfile):
            with open(outfile) as f:
                resp = json.load(f)
            body = json.loads(resp.get("body", "{}")) if isinstance(resp, dict) and "body" in resp else resp
            print(f"  {name}: OK — {json.dumps(body)[:100]}")
            os.remove(outfile)
        else:
            print(f"  {name}: FAILED")


def print_manual_gateway_instructions():
    """Print instructions for manual gateway setup if automated setup fails."""
    print("\n  Manual Gateway Setup:")
    print(f"  1. agentcore gateway create-mcp-gateway --name {GATEWAY_NAME} --region {REGION}")
    print(f"  2. For each tool, create a target with:")
    print(f"     agentcore gateway create-mcp-gateway-target \\")
    print(f"       --gateway-arn <arn> --gateway-url <url> --role-arn <role> \\")
    print(f"       --name <tool_name> --target-type lambda \\")
    print(f"       --target-payload '<json>' --region {REGION}")
    print(f"  3. Update .env with gateway credentials")
    print(f"  4. agentcore configure --entrypoint main.py --non-interactive")
    print(f"  5. agentcore launch")


# -----------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------
if __name__ == "__main__":
    print("SmartBanker Deployment (AgentCore Runtime + Gateway)")
    print(f"Region: {REGION} | Account: {ACCOUNT_ID}")
    print(f"Stack: {STACK_NAME} | Gateway: {GATEWAY_NAME}")

    create_s3_bucket()
    package_and_upload_lambdas()
    create_dynamodb_table()
    deploy_lambdas()
    success = wait_for_stack()

    if not success:
        print("\nLambda deployment failed. Fix CloudFormation errors and retry.")
        sys.exit(1)

    smoke_test()

    # AgentCore Gateway + Runtime (requires agentcore CLI)
    result = run("agentcore --version", check=False)
    if result.returncode != 0:
        print("\n  agentcore CLI not found. Install with: pip install bedrock-agentcore-starter-toolkit")
        print_manual_gateway_instructions()
    else:
        gateway_info = create_gateway()
        add_lambda_targets(gateway_info)
        deploy_agent_runtime()

    print(f"\n{'='*60}")
    print("  DEPLOYMENT COMPLETE")
    print(f"  Run UI locally: streamlit run ui/app.py")
    print(f"  Test agent: agentcore invoke '{{\"prompt\": \"Analyze my spending\"}}'")
    print(f"{'='*60}")
