"""SimulationStack — Deploys a target EC2 instance for end-to-end production simulation.

Creates:
- EC2 instance (t3.micro) with SSM Agent, node-exporter, stress-ng, and a fake app
- Security group allowing Prometheus scraping from private subnets
- IAM instance profile with SSM managed policy
- UserData that installs and starts all components
- A "break" SSM document that triggers high CPU (for testing)
- A "fix" Ansible playbook that kills the stress process

Tag: managed-by=aiops (required for SSM SendCommand permission scoping)
"""

from typing import Any

import aws_cdk as cdk
from aws_cdk import (
    CfnOutput,
    Duration,
    aws_cloudwatch as cw,
    aws_cloudwatch_actions as cw_actions,
    aws_ec2 as ec2,
    aws_iam as iam,
    aws_lambda as _lambda,
    aws_sns as sns,
    aws_sns_subscriptions as sns_subs,
    aws_ssm as ssm,
)
from constructs import Construct

from ..context import CdkContext
from .network_stack import NetworkStack


# UserData script that installs node-exporter, stress-ng, and a fake web app
_USER_DATA = """\
#!/bin/bash
set -e

# Install dependencies
dnf install -y stress-ng python3 curl

# Install node_exporter
cd /tmp
curl -sLO https://github.com/prometheus/node_exporter/releases/download/v1.8.1/node_exporter-1.8.1.linux-amd64.tar.gz
tar xzf node_exporter-1.8.1.linux-amd64.tar.gz
cp node_exporter-1.8.1.linux-amd64/node_exporter /usr/local/bin/
chmod +x /usr/local/bin/node_exporter

# Create fake web app
cat > /opt/fake_app.py << 'APPEOF'
from http.server import HTTPServer, BaseHTTPRequestHandler
import json, os

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "healthy", "pid": os.getpid()}).encode())
        else:
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"AIOps Target Host")
    def log_message(self, *a): pass

HTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
APPEOF

# Create systemd services
cat > /etc/systemd/system/node-exporter.service << 'EOF'
[Unit]
Description=Node Exporter
After=network.target

[Service]
ExecStart=/usr/local/bin/node_exporter --web.listen-address=:9100
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

cat > /etc/systemd/system/fake-app.service << 'EOF'
[Unit]
Description=Fake Web Application
After=network.target

[Service]
ExecStart=/usr/bin/python3 /opt/fake_app.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Start services
systemctl daemon-reload
systemctl enable node-exporter fake-app
systemctl start node-exporter fake-app

echo "Target host setup complete" > /var/log/aiops-setup.log
"""

# Lambda code for the alert trigger — supports event-based override for testing AI mode
_ALERT_LAMBDA_CODE = """\
import json
import urllib.request
import os
import boto3


def handler(event, context):
    ssm = boto3.client("ssm")
    env = os.environ["ENVIRONMENT"]
    instance_id = os.environ.get("INSTANCE_ID", "unknown")
    default_alert = os.environ.get("ALERT_NAME", "HighCPUUsage")

    # Determine alert parameters — allow override via direct invoke payload
    alert_name = default_alert
    severity = "critical"
    service_name = "web-frontend"
    summary = f"{default_alert} detected on {instance_id} (CloudWatch alarm)"

    if isinstance(event, dict):
        # Direct invoke with custom payload (for testing AI mode)
        if "alert_name" in event:
            alert_name = event["alert_name"]
            severity = event.get("severity", "critical")
            service_name = event.get("service_name", "unknown-service")
            summary = event.get("summary", f"{alert_name} on {instance_id}")
            instance_id = event.get("instance", instance_id)
        # SNS trigger from CloudWatch Alarm
        elif "Records" in event:
            for rec in event.get("Records", []):
                msg = json.loads(rec.get("Sns", {}).get("Message", "{}"))
                if msg.get("NewStateValue") == "ALARM":
                    summary = msg.get("NewStateReason", summary)

    # Get webhook URL from SSM
    try:
        resp = ssm.get_parameter(Name=f"/aiops/{env}/service-base-url")
        base_url = resp["Parameter"]["Value"]
        if base_url.startswith("https://https://"):
            base_url = base_url.replace("https://https://", "https://")
    except Exception as e:
        print(f"SSM error: {e}")
        return {"error": str(e)}

    # Build and send Alertmanager webhook payload
    payload = json.dumps({
        "version": "4",
        "groupKey": f"cw-{alert_name}",
        "status": "firing",
        "receiver": "aiops",
        "alerts": [{
            "status": "firing",
            "labels": {
                "alertname": alert_name,
                "severity": severity,
                "instance": instance_id,
                "service_name": service_name,
                "job": "cloudwatch",
            },
            "annotations": {
                "summary": summary,
            },
            "startsAt": "2026-08-01T00:00:00Z",
            "endsAt": "0001-01-01T00:00:00Z",
            "fingerprint": f"cw-{alert_name}-{instance_id}",
        }],
    }).encode()

    req = urllib.request.Request(
        f"{base_url}/webhook", data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        print(f"Webhook sent: status={resp.status} alert={alert_name}")
        return {"status": resp.status, "alert": alert_name}
    except Exception as e:
        print(f"Webhook failed: {e}")
        return {"error": str(e)}
"""


class SimulationStack(cdk.Stack):
    """Deploys a target EC2 instance for production simulation testing."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        context: CdkContext,
        network_stack: NetworkStack,
        **kwargs: Any,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        env_name = context.environment

        # -----------------------------------------------------------
        # Security Group for target instance
        # -----------------------------------------------------------
        self.target_sg = ec2.SecurityGroup(
            self,
            "TargetSg",
            vpc=network_stack.vpc,
            description="Security group for AIOps simulation target",
            allow_all_outbound=True,
        )
        # Allow Prometheus scraping from within VPC
        self.target_sg.add_ingress_rule(
            ec2.Peer.ipv4(network_stack.vpc.vpc_cidr_block),
            ec2.Port.tcp(9100),
            "Allow Prometheus scrape from VPC",
        )
        # Allow health check from within VPC
        self.target_sg.add_ingress_rule(
            ec2.Peer.ipv4(network_stack.vpc.vpc_cidr_block),
            ec2.Port.tcp(8080),
            "Allow health check from VPC",
        )

        # -----------------------------------------------------------
        # IAM Role for EC2 with SSM access
        # -----------------------------------------------------------
        self.instance_role = iam.Role(
            self,
            "TargetInstanceRole",
            role_name=f"AiopsTargetInstance-{env_name}",
            assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "AmazonSSMManagedInstanceCore"
                ),
            ],
        )

        # -----------------------------------------------------------
        # EC2 Instance
        # -----------------------------------------------------------
        self.instance = ec2.Instance(
            self,
            "TargetInstance",
            instance_type=ec2.InstanceType.of(
                ec2.InstanceClass.T3, ec2.InstanceSize.MICRO
            ),
            machine_image=ec2.AmazonLinuxImage(
                generation=ec2.AmazonLinuxGeneration.AMAZON_LINUX_2023,
            ),
            vpc=network_stack.vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
            ),
            security_group=self.target_sg,
            role=self.instance_role,
            user_data=ec2.UserData.custom(_USER_DATA),
        )

        # Tag for SSM SendCommand scoping
        cdk.Tags.of(self.instance).add("managed-by", "aiops")
        cdk.Tags.of(self.instance).add("service_name", "web-frontend")
        cdk.Tags.of(self.instance).add("Name", f"aiops-target-{env_name}")

        # -----------------------------------------------------------
        # SSM Document: "Break" — triggers high CPU for testing
        # -----------------------------------------------------------
        ssm.CfnDocument(
            self,
            "BreakDocument",
            name=f"aiops-break-cpu-{env_name}",
            document_type="Command",
            content={
                "schemaVersion": "2.2",
                "description": "Simulate high CPU on target instance for AIOps testing",
                "parameters": {
                    "Duration": {
                        "type": "String",
                        "default": "120",
                        "description": "Duration in seconds to run CPU stress",
                    }
                },
                "mainSteps": [
                    {
                        "action": "aws:runShellScript",
                        "name": "StressCPU",
                        "inputs": {
                            "runCommand": [
                                "nohup stress-ng --cpu $(nproc) --timeout {{Duration}}s &",
                                "echo 'CPU stress started for {{Duration}} seconds'",
                            ]
                        },
                    }
                ],
            },
        )

        # -----------------------------------------------------------
        # SSM Document: "Fix" — kills stress and restarts app
        # -----------------------------------------------------------
        ssm.CfnDocument(
            self,
            "FixDocument",
            name=f"aiops-fix-cpu-{env_name}",
            document_type="Command",
            content={
                "schemaVersion": "2.2",
                "description": "Fix high CPU by killing stress processes and restarting the app",
                "mainSteps": [
                    {
                        "action": "aws:runShellScript",
                        "name": "KillStressAndRestart",
                        "inputs": {
                            "runCommand": [
                                "pkill -f stress-ng || true",
                                "systemctl restart fake-app",
                                "sleep 2",
                                "curl -s http://localhost:8080/health",
                                "echo 'Remediation complete: stress killed, app restarted'",
                            ]
                        },
                    }
                ],
            },
        )

        # -----------------------------------------------------------
        # CloudWatch Alarm → Lambda → Webhook (automatic alert trigger)
        # When EC2 CPU > 80% for 1 minute, Lambda sends Alertmanager
        # payload to the self-healing webhook endpoint.
        # -----------------------------------------------------------
        # Get API Gateway URL from SSM (set by ComputeStack)
        api_url_param = f"/aiops/{env_name}/service-base-url"

        alert_lambda = _lambda.Function(
            self,
            "AlertTriggerLambda",
            function_name=f"aiops-alert-trigger-{env_name}",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="index.handler",
            timeout=Duration.seconds(30),
            code=_lambda.Code.from_inline(_ALERT_LAMBDA_CODE),
            environment={
                "ENVIRONMENT": env_name,
                "INSTANCE_ID": self.instance.instance_id,
                "ALERT_NAME": "HighCPUUsage",
            },
        )
        alert_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=["ssm:GetParameter"],
                resources=[f"arn:aws:ssm:{context.aws_region}:{context.aws_account}:parameter/aiops/{env_name}/*"],
            )
        )

        # SNS topic for the alarm
        alarm_topic = sns.Topic(self, "CpuAlarmTopic", topic_name=f"aiops-cpu-alarm-{env_name}")
        alarm_topic.add_subscription(sns_subs.LambdaSubscription(alert_lambda))

        # CloudWatch Alarm: CPU > 80% for 1 minute → sends HighCPUUsage (has playbook)
        cpu_alarm = cw.Alarm(
            self,
            "HighCpuAlarm",
            alarm_name=f"aiops-target-cpu-{env_name}",
            metric=cw.Metric(
                metric_name="CPUUtilization",
                namespace="AWS/EC2",
                dimensions_map={"InstanceId": self.instance.instance_id},
                period=Duration.minutes(1),
                statistic="Average",
            ),
            threshold=80,
            evaluation_periods=1,
            datapoints_to_alarm=1,
            comparison_operator=cw.ComparisonOperator.GREATER_THAN_THRESHOLD,
            treat_missing_data=cw.TreatMissingData.NOT_BREACHING,
        )
        cpu_alarm.add_alarm_action(cw_actions.SnsAction(alarm_topic))

        # CloudWatch Alarm: Network packets in > 1000/min → sends NetworkFloodDetected (NO playbook = AI mode)
        network_alarm = cw.Alarm(
            self,
            "NetworkFloodAlarm",
            alarm_name=f"aiops-target-network-{env_name}",
            metric=cw.Metric(
                metric_name="NetworkPacketsIn",
                namespace="AWS/EC2",
                dimensions_map={"InstanceId": self.instance.instance_id},
                period=Duration.minutes(1),
                statistic="Sum",
            ),
            threshold=1000,
            evaluation_periods=1,
            datapoints_to_alarm=1,
            comparison_operator=cw.ComparisonOperator.GREATER_THAN_THRESHOLD,
            treat_missing_data=cw.TreatMissingData.NOT_BREACHING,
        )

        # Second Lambda for network alert (triggers AI mode since no playbook exists)
        network_alert_lambda = _lambda.Function(
            self,
            "NetworkAlertLambda",
            function_name=f"aiops-network-alert-{env_name}",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="index.handler",
            timeout=Duration.seconds(30),
            code=_lambda.Code.from_inline(_ALERT_LAMBDA_CODE),
            environment={
                "ENVIRONMENT": env_name,
                "INSTANCE_ID": self.instance.instance_id,
                "ALERT_NAME": "NetworkFloodDetected",
            },
        )
        network_alert_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=["ssm:GetParameter"],
                resources=[f"arn:aws:ssm:{context.aws_region}:{context.aws_account}:parameter/aiops/{env_name}/*"],
            )
        )

        # SNS topic for network alarm
        network_topic = sns.Topic(self, "NetworkAlarmTopic", topic_name=f"aiops-network-alarm-{env_name}")
        network_topic.add_subscription(sns_subs.LambdaSubscription(network_alert_lambda))
        network_alarm.add_alarm_action(cw_actions.SnsAction(network_topic))

        # -----------------------------------------------------------
        # Outputs
        # -----------------------------------------------------------
        CfnOutput(
            self,
            "TargetInstanceId",
            value=self.instance.instance_id,
            export_name=f"AiopsTargetInstanceId-{env_name}",
        )
        CfnOutput(
            self,
            "TargetPrivateIp",
            value=self.instance.instance_private_ip,
            export_name=f"AiopsTargetPrivateIp-{env_name}",
        )
