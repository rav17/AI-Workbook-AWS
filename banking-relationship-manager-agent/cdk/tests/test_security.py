from __future__ import annotations

import json

import pytest
from aws_cdk import App

from cdk.app import build_app
from cdk.stacks.stateful_stack import StatefulStack

TEST_USER_POOL_ARN = "arn:aws:cognito-idp:us-east-1:111111111111:userpool/us-east-1_test"
TEST_MODEL_ID = "amazon.nova-lite-v1:0"
TEST_COGNITO_CLIENT_ID = "test-client-id"


def test_stateful_stack_synthesizes_without_unsupported_security_configuration() -> None:
    app = App(context={"environment": "dev", "region": "us-east-1", "account": "111111111111"})
    StatefulStack(
        app,
        "AriaStatefulStack",
        env_name="dev",
        env={"account": "111111111111", "region": "us-east-1"},
    )

    template = app.synth().get_stack_by_name("AriaStatefulStack").template
    assert template["Resources"]
    resource_names = tuple(template["Resources"].keys())
    assert any(name.startswith("SessionTable") for name in resource_names)
    assert any(name.startswith("IdempotencyTable") for name in resource_names)
    assert any(name.startswith("WorkflowQueue") for name in resource_names)
    assert any(name.startswith("ProviderSecret") for name in resource_names)
    assert any(name.startswith("WorkflowEventBus") for name in resource_names)

    table_resource = next(
        resource
        for name, resource in template["Resources"].items()
        if name.startswith("SessionTable")
    )
    assert table_resource["Properties"]["SSESpecification"]["SSEEnabled"] is True
    idempotency_resource = next(
        resource
        for name, resource in template["Resources"].items()
        if name.startswith("IdempotencyTable") and resource["Type"] == "AWS::DynamoDB::Table"
    )
    assert idempotency_resource["Properties"]["KeySchema"][0]["AttributeName"] == ("idempotency_id")
    assert idempotency_resource["Properties"]["TimeToLiveSpecification"]["AttributeName"] == (
        "expires_at"
    )


def test_non_dev_stateful_stack_retains_resources_and_enables_termination_protection() -> None:
    app = App(context={"environment": "prod", "region": "us-east-1", "account": "111111111111"})
    stack = StatefulStack(
        app,
        "AriaProdStatefulStack",
        env_name="prod",
        env={"account": "111111111111", "region": "us-east-1"},
    )

    template = app.synth().get_stack_by_name("AriaProdStatefulStack").template
    table_resource = next(
        resource
        for name, resource in template["Resources"].items()
        if name.startswith("SessionTable")
    )
    assert table_resource["DeletionPolicy"] == "Retain"
    assert stack.termination_protection is True


def test_non_dev_app_requires_permissions_boundary(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CDK_PERMISSIONS_BOUNDARY_ARN", raising=False)
    monkeypatch.setenv("CDK_DEFAULT_ACCOUNT", "111111111111")
    monkeypatch.setenv("CDK_DEFAULT_REGION", "us-east-1")

    with pytest.raises(ValueError, match="permissions boundary"):
        build_app(
            context={
                "environment": "prod",
                "account": "111111111111",
                "region": "us-east-1",
                "cognito_user_pool_arn": TEST_USER_POOL_ARN,
                "bedrock_model_id": TEST_MODEL_ID,
                "cognito_app_client_id": TEST_COGNITO_CLIENT_ID,
            }
        )


def test_app_stack_synthesizes_api_and_event_handlers() -> None:
    app = build_app(
        context={
            "environment": "dev",
            "region": "us-east-1",
            "account": "111111111111",
            "cognito_user_pool_arn": TEST_USER_POOL_ARN,
            "bedrock_model_id": TEST_MODEL_ID,
            "cognito_app_client_id": TEST_COGNITO_CLIENT_ID,
            "idempotency_ttl_seconds": "3600",
        }
    )
    template = app.synth().get_stack_by_name("AriaApplicationStack").template

    resource_types = {resource["Type"] for resource in template["Resources"].values()}
    assert "AWS::Lambda::Function" in resource_types
    assert "AWS::ApiGateway::RestApi" in resource_types
    assert "AWS::Events::Rule" in resource_types

    lambda_resources = [
        resource
        for resource in template["Resources"].values()
        if resource["Type"] == "AWS::Lambda::Function"
    ]
    assert all(
        resource["Properties"]["TracingConfig"]["Mode"] == "Active" for resource in lambda_resources
    )
    request_lambda = next(
        resource
        for resource in lambda_resources
        if resource["Properties"]["Handler"] == "aria.api.lambda_entry.handler"
    )
    assert (
        request_lambda["Properties"]["Environment"]["Variables"]["IDEMPOTENCY_TTL_SECONDS"]
        == "3600"
    )

    api_stages = [
        resource
        for resource in template["Resources"].values()
        if resource["Type"] == "AWS::ApiGateway::Stage"
    ]
    assert any(resource["Properties"].get("TracingEnabled") is True for resource in api_stages)


def test_public_api_method_requires_cognito_authorization() -> None:
    app = build_app(
        context={
            "environment": "dev",
            "region": "us-east-1",
            "account": "111111111111",
            "cognito_user_pool_arn": TEST_USER_POOL_ARN,
            "bedrock_model_id": TEST_MODEL_ID,
            "cognito_app_client_id": TEST_COGNITO_CLIENT_ID,
        }
    )
    template = app.synth().get_stack_by_name("AriaApplicationStack").template

    api_methods = [
        resource
        for resource in template["Resources"].values()
        if resource["Type"] == "AWS::ApiGateway::Method"
        and resource["Properties"].get("HttpMethod") == "POST"
    ]

    assert len(api_methods) == 1
    assert api_methods[0]["Properties"]["AuthorizationType"] == "COGNITO_USER_POOLS"


def test_runtime_request_timeouts_are_explicit_and_compatible():
    app = build_app(
        context={
            "environment": "dev",
            "region": "us-east-1",
            "account": "111111111111",
            "cognito_user_pool_arn": TEST_USER_POOL_ARN,
            "bedrock_model_id": TEST_MODEL_ID,
            "cognito_app_client_id": TEST_COGNITO_CLIENT_ID,
        }
    )
    template = app.synth().get_stack_by_name("AriaApplicationStack").template
    request_lambda = next(
        resource
        for resource in template["Resources"].values()
        if resource["Type"] == "AWS::Lambda::Function"
        and resource["Properties"]["Handler"] == "aria.api.lambda_entry.handler"
    )
    request_method = next(
        resource
        for resource in template["Resources"].values()
        if resource["Type"] == "AWS::ApiGateway::Method"
        and resource["Properties"].get("HttpMethod") == "POST"
    )

    assert request_lambda["Properties"]["Timeout"] == 28
    assert request_method["Properties"]["Integration"]["TimeoutInMillis"] == 29_000


def test_agentcore_stacks_synthesize_memory_gateway_and_runtime() -> None:
    app = build_app(
        context={
            "environment": "dev",
            "region": "us-east-1",
            "account": "111111111111",
            "cognito_user_pool_arn": TEST_USER_POOL_ARN,
            "bedrock_model_id": TEST_MODEL_ID,
            "cognito_app_client_id": TEST_COGNITO_CLIENT_ID,
        }
    )
    assembly = app.synth()

    stateful = assembly.get_stack_by_name("AriaStatefulStack").template
    application = assembly.get_stack_by_name("AriaApplicationStack").template
    gateway = assembly.get_stack_by_name("AriaGatewayStack").template
    runtime = assembly.get_stack_by_name("AriaRuntimeStack").template

    stateful_types = {resource["Type"] for resource in stateful["Resources"].values()}
    gateway_types = {resource["Type"] for resource in gateway["Resources"].values()}
    runtime_types = {resource["Type"] for resource in runtime["Resources"].values()}

    assert "AWS::BedrockAgentCore::Memory" in stateful_types
    assert "AWS::BedrockAgentCore::Gateway" in gateway_types
    assert "AWS::BedrockAgentCore::GatewayTarget" in gateway_types
    assert "AWS::BedrockAgentCore::Runtime" in runtime_types
    gateway_target = next(
        resource
        for resource in gateway["Resources"].values()
        if resource["Type"] == "AWS::BedrockAgentCore::GatewayTarget"
    )
    published_tools = gateway_target["Properties"]["TargetConfiguration"]["Mcp"]["Lambda"][
        "ToolSchema"
    ]["InlinePayload"]
    assert [tool["Name"] for tool in published_tools] == ["get_risk_questionnaire"]
    assert published_tools[0]["InputSchema"]["Properties"] == {}
    statement_target = next(
        resource
        for resource in gateway["Resources"].values()
        if resource["Type"] == "AWS::BedrockAgentCore::GatewayTarget"
        and resource["Properties"]["Name"] == "aria-statements"
    )
    statement_tools = statement_target["Properties"]["TargetConfiguration"]["Mcp"]["Lambda"][
        "ToolSchema"
    ]["InlinePayload"]
    assert [tool["Name"] for tool in statement_tools] == [
        "list_authorized_statements",
        "get_statement_transactions",
    ]
    assert statement_tools[0]["InputSchema"]["Required"] == ["tenant_id", "user_id"]
    assert statement_tools[1]["InputSchema"]["Required"] == [
        "tenant_id",
        "user_id",
        "statement_ref",
    ]
    statement_tables = [
        resource
        for logical_id, resource in stateful["Resources"].items()
        if resource["Type"] == "AWS::DynamoDB::Table"
        and "Statement" in logical_id
    ]
    assert len(statement_tables) == 2
    assert all(table["Properties"]["PointInTimeRecoverySpecification"]["PointInTimeRecoveryEnabled"] for table in statement_tables)
    gateway_function = next(
        resource
        for resource in gateway["Resources"].values()
        if resource["Type"] == "AWS::Lambda::Function"
        and resource["Properties"]["Handler"] == "aria.api.gateway_handler.handler"
    )
    gateway_environment = gateway_function["Properties"]["Environment"]["Variables"]
    assert "STATEMENT_ENTITLEMENTS_TABLE" in gateway_environment
    assert "STATEMENT_TRANSACTIONS_TABLE" in gateway_environment
    gateway_iam_statements = [
        statement
        for resource in gateway["Resources"].values()
        if resource["Type"] == "AWS::IAM::Policy"
        for statement in resource["Properties"]["PolicyDocument"]["Statement"]
    ]
    assert any(
        set(statement.get("Action", [])) == {"dynamodb:GetItem", "dynamodb:Query"}
        for statement in gateway_iam_statements
    )
    request_lambda = next(
        resource
        for resource in application["Resources"].values()
        if resource["Type"] == "AWS::Lambda::Function"
        and resource["Properties"]["Handler"] == "aria.api.lambda_entry.handler"
    )
    assert (
        request_lambda["Properties"]["Environment"]["Variables"]["AGENTCORE_RUNTIME_ARN_PARAMETER"]
        == "/aria/dev/agentcore/runtime-arn"
    )
    assert "IDEMPOTENCY_TABLE_NAME" in request_lambda["Properties"]["Environment"]["Variables"]
    application_statements = [
        statement
        for resource in application["Resources"].values()
        if resource["Type"] == "AWS::IAM::Policy"
        for statement in resource["Properties"]["PolicyDocument"]["Statement"]
    ]
    assert any(
        "bedrock-agentcore:InvokeAgentRuntimeForUser"
        in (
            statement.get("Action")
            if isinstance(statement.get("Action"), list)
            else [statement.get("Action")]
        )
        for statement in application_statements
    )
    assert any(
        statement.get("Action") == "ssm:GetParameter"
        and "parameter/aria/dev/agentcore/runtime-arn" in str(statement.get("Resource"))
        for statement in application_statements
    )
    assert any(
        all(
            action in statement.get("Action", [])
            for action in ("dynamodb:PutItem", "dynamodb:DeleteItem")
        )
        and "IdempotencyTable" in str(statement.get("Resource"))
        for statement in application_statements
    )

    runtime_resource = next(
        resource
        for resource in runtime["Resources"].values()
        if resource["Type"] == "AWS::BedrockAgentCore::Runtime"
    )
    assert (
        runtime_resource["Properties"]["AgentRuntimeArtifact"]["CodeConfiguration"]["Runtime"]
        == "PYTHON_3_13"
    )
    assert (
        runtime_resource["Properties"]["EnvironmentVariables"]["AGENTCORE_MODEL_ID"]
        == TEST_MODEL_ID
    )
    assert (
        runtime_resource["Properties"]["EnvironmentVariables"]["STATEMENT_EXPLAINER_ENABLED"]
        == "false"
    )
    assert "IDEMPOTENCY_TABLE_NAME" not in runtime_resource["Properties"]["EnvironmentVariables"]
    assert "AuthorizerConfiguration" not in runtime_resource["Properties"]
    assert "RequestHeaderConfiguration" not in runtime_resource["Properties"]
    runtime_policy = next(
        resource
        for resource in runtime["Resources"].values()
        if resource["Type"] == "AWS::BedrockAgentCore::ResourcePolicy"
    )
    policy_parts = runtime_policy["Properties"]["Policy"]["Fn::Join"][1]
    policy_text = "".join("TOKEN" if isinstance(part, dict) else part for part in policy_parts)
    policy_document = json.loads(policy_text)
    assert policy_document["Statement"][0]["Principal"]["AWS"]
    assert policy_document["Statement"][1]["Effect"] == "Deny"
    assert (
        policy_document["Statement"][1]["Condition"]["ArnNotEquals"]["aws:PrincipalArn"]
        == policy_document["Statement"][0]["Principal"]["AWS"]
    )
    assert any(
        resource["Type"] == "AWS::SSM::Parameter"
        and resource["Properties"]["Name"] == "/aria/dev/agentcore/runtime-arn"
        for resource in runtime["Resources"].values()
    )
    mmdsv2_handler = next(
        resource
        for resource in runtime["Resources"].values()
        if resource["Type"] == "AWS::Lambda::Function"
        and resource["Properties"]["Handler"] == "cdk.custom_resources.enable_mmdsv2.handler"
    )
    assert mmdsv2_handler["Properties"]["Runtime"] == "python3.13"

    runtime_role = next(
        resource
        for resource in runtime["Resources"].values()
        if resource["Type"] == "AWS::IAM::Role"
        and any(
            statement.get("Principal", {}).get("Service") == "bedrock-agentcore.amazonaws.com"
            for statement in resource["Properties"]["AssumeRolePolicyDocument"]["Statement"]
        )
    )
    runtime_trust = runtime_role["Properties"]["AssumeRolePolicyDocument"]["Statement"][0]
    assert runtime_trust["Condition"]["StringEquals"]["aws:SourceAccount"] == "111111111111"
    assert runtime_trust["Condition"]["ArnLike"]["aws:SourceArn"].endswith(
        "runtime/aria_dev_runtime*"
    )

    gateway_role = next(
        resource
        for resource in gateway["Resources"].values()
        if resource["Type"] == "AWS::IAM::Role"
        and any(
            statement.get("Principal", {}).get("Service") == "bedrock-agentcore.amazonaws.com"
            for statement in resource["Properties"]["AssumeRolePolicyDocument"]["Statement"]
        )
    )
    gateway_trust = gateway_role["Properties"]["AssumeRolePolicyDocument"]["Statement"][0]
    assert gateway_trust["Condition"]["StringEquals"]["aws:SourceAccount"] == "111111111111"

    memory_role = next(
        resource
        for resource in stateful["Resources"].values()
        if resource["Type"] == "AWS::IAM::Role"
        and any(
            statement.get("Principal", {}).get("Service") == "bedrock-agentcore.amazonaws.com"
            for statement in resource["Properties"]["AssumeRolePolicyDocument"]["Statement"]
        )
    )
    memory_trust = memory_role["Properties"]["AssumeRolePolicyDocument"]["Statement"][0]
    assert memory_trust["Condition"]["StringEquals"]["aws:SourceAccount"] == "111111111111"
    memory_resource = next(
        resource
        for resource in stateful["Resources"].values()
        if resource["Type"] == "AWS::BedrockAgentCore::Memory"
    )
    assert memory_resource["Properties"]["NamespaceKeys"][0]["Key"] == "tenantid"
    namespaces = [
        namespace
        for strategy in memory_resource["Properties"]["MemoryStrategies"]
        for variant in strategy.values()
        for namespace in variant.get("NamespaceTemplates", [])
    ]
    assert len(namespaces) == 3
    assert all(namespace.startswith("/tenants/{tenantid}/users/") for namespace in namespaces)


def test_statement_explainer_runtime_flag_requires_explicit_opt_in() -> None:
    app = build_app(
        context={
            "environment": "dev",
            "region": "us-east-1",
            "account": "111111111111",
            "cognito_user_pool_arn": TEST_USER_POOL_ARN,
            "bedrock_model_id": TEST_MODEL_ID,
            "cognito_app_client_id": TEST_COGNITO_CLIENT_ID,
            "statement_explainer_enabled": "true",
        }
    )
    runtime = app.synth().get_stack_by_name("AriaRuntimeStack").template
    runtime_resource = next(
        resource
        for resource in runtime["Resources"].values()
        if resource["Type"] == "AWS::BedrockAgentCore::Runtime"
    )

    assert (
        runtime_resource["Properties"]["EnvironmentVariables"]["STATEMENT_EXPLAINER_ENABLED"]
        == "true"
    )


def test_statement_explainer_runtime_flag_rejects_ambiguous_context_value() -> None:
    with pytest.raises(ValueError, match="must be true or false"):
        build_app(
            context={
                "environment": "dev",
                "region": "us-east-1",
                "account": "111111111111",
                "cognito_user_pool_arn": TEST_USER_POOL_ARN,
                "bedrock_model_id": TEST_MODEL_ID,
                "cognito_app_client_id": TEST_COGNITO_CLIENT_ID,
                "statement_explainer_enabled": "sometimes",
            }
        )


def test_service_log_groups_have_explicit_retention_and_matching_audit_mask_policies():
    app = build_app(
        context={
            "environment": "dev",
            "region": "us-east-1",
            "account": "111111111111",
            "cognito_user_pool_arn": TEST_USER_POOL_ARN,
            "bedrock_model_id": TEST_MODEL_ID,
            "cognito_app_client_id": TEST_COGNITO_CLIENT_ID,
        }
    )
    assembly = app.synth()
    templates = [
        assembly.get_stack_by_name(stack_name).template
        for stack_name in (
            "AriaApplicationStack",
            "AriaGatewayStack",
            "AriaStatefulStack",
        )
    ]
    protected_groups = [
        resource
        for template in templates
        for resource in template["Resources"].values()
        if resource["Type"] == "AWS::Logs::LogGroup"
        and "DataProtectionPolicy" in resource.get("Properties", {})
    ]

    assert len(protected_groups) == 4
    for group in protected_groups:
        properties = group["Properties"]
        assert properties["RetentionInDays"] == 7
        policy = properties["DataProtectionPolicy"]
        if isinstance(policy, str):
            policy = json.loads(policy)
        statements = policy["Statement"]
        audit = next(statement for statement in statements if "Audit" in statement["Operation"])
        mask = next(statement for statement in statements if "Deidentify" in statement["Operation"])
        assert audit["DataIdentifier"] == mask["DataIdentifier"]
        identifier_json = json.dumps(audit["DataIdentifier"])
        assert all(
            identifier in identifier_json
            for identifier in {
                "EmailAddress",
                "Address",
                "Ssn-US",
                "PhoneNumber-US",
                "BankAccountNumber-US",
                "CreditCardNumber",
                "CreditCardSecurityCode",
                "AwsSecretKey",
            }
        )


def test_operational_alarms_use_configured_thresholds_and_publish_to_sns():
    app = build_app(
        context={
            "environment": "dev",
            "region": "us-east-1",
            "account": "111111111111",
            "cognito_user_pool_arn": TEST_USER_POOL_ARN,
            "bedrock_model_id": TEST_MODEL_ID,
            "cognito_app_client_id": TEST_COGNITO_CLIENT_ID,
            "alarm_api_error_rate_percent": "2",
            "alarm_api_p95_latency_ms": "1500",
        }
    )
    assembly = app.synth()
    templates = [
        assembly.get_stack_by_name(stack_name).template
        for stack_name in (
            "AriaApplicationStack",
            "AriaGatewayStack",
            "AriaStatefulStack",
        )
    ]
    resources = {
        logical_id: resource
        for template in templates
        for logical_id, resource in template["Resources"].items()
    }
    alarms = {
        resource["Properties"]["AlarmName"]: resource
        for resource in resources.values()
        if resource["Type"] == "AWS::CloudWatch::Alarm"
    }
    topic_id = next(
        logical_id
        for logical_id, resource in resources.items()
        if resource["Type"] == "AWS::SNS::Topic"
    )

    assert "aria-dev-api-error-rate" in alarms
    assert "aria-dev-api-p95-latency" in alarms
    assert any("SensitiveFindings" in alarm_name for alarm_name in alarms)
    assert alarms["aria-dev-api-error-rate"]["Properties"]["Threshold"] == 2
    assert alarms["aria-dev-api-p95-latency"]["Properties"]["Threshold"] == 1500
    for alarm in alarms.values():
        assert any(
            topic_id in json.dumps(action) or "OperationsAlarmTopic" in json.dumps(action)
            for action in alarm["Properties"]["AlarmActions"]
        )

    findings_alarm = next(alarm for name, alarm in alarms.items() if "SensitiveFindings" in name)
    assert findings_alarm["Properties"]["Namespace"] == "AWS/Logs"
    assert findings_alarm["Properties"]["MetricName"] == "LogEventsWithFindings"
    assert "Dimensions" not in findings_alarm["Properties"]

    topic_policy = next(
        resource for resource in resources.values() if resource["Type"] == "AWS::SNS::TopicPolicy"
    )
    topic_publish = next(
        statement
        for statement in topic_policy["Properties"]["PolicyDocument"]["Statement"]
        if isinstance(statement.get("Principal"), dict)
        and statement["Principal"].get("Service") == "cloudwatch.amazonaws.com"
    )
    assert topic_publish["Action"] == "sns:Publish"
    assert topic_publish["Condition"]["StringEquals"]["aws:SourceAccount"] == "111111111111"
    source_arn = json.dumps(topic_publish["Condition"]["ArnLike"]["aws:SourceArn"])
    assert "AWS::Partition" in source_arn
    assert ":cloudwatch:us-east-1:111111111111:alarm:*" in source_arn

    key_resource = next(
        resource for resource in resources.values() if resource["Type"] == "AWS::KMS::Key"
    )
    cloudwatch_key_statement = next(
        statement
        for statement in key_resource["Properties"]["KeyPolicy"]["Statement"]
        if isinstance(statement.get("Principal"), dict)
        and statement["Principal"].get("Service") == "cloudwatch.amazonaws.com"
    )
    assert set(cloudwatch_key_statement["Action"]) == {
        "kms:Decrypt",
        "kms:GenerateDataKey*",
    }
    assert (
        cloudwatch_key_statement["Condition"]["StringEquals"]["aws:SourceAccount"] == "111111111111"
    )
    key_source_arn = json.dumps(cloudwatch_key_statement["Condition"]["ArnLike"]["aws:SourceArn"])
    assert "AWS::Partition" in key_source_arn
    assert ":cloudwatch:us-east-1:111111111111:alarm:*" in key_source_arn
