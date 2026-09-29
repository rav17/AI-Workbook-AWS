"""MonitoringStack — Amazon Managed Prometheus, Alertmanager sidecar, and ADOT collector.

Deploys a fully self-contained monitoring pipeline in AWS:
- Amazon Managed Service for Prometheus (AMP) workspace for metric storage
- ADOT (AWS Distro for OpenTelemetry) collector as ECS sidecar for scraping and remote-write
- Alertmanager as ECS sidecar that evaluates alert rules and forwards to the self-healing webhook
- Alert rules and Alertmanager config stored in SSM Parameter Store for hot-reloading
"""

from typing import Any

import aws_cdk as cdk
from aws_cdk import (
    CfnOutput,
    aws_aps as aps,
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_iam as iam,
    aws_logs as logs,
    aws_ssm as ssm,
)
from constructs import Construct

from ..context import CdkContext
from .network_stack import NetworkStack


# Alertmanager configuration template — routes alerts to self-healing webhook
_ALERTMANAGER_CONFIG = """\
global:
  resolve_timeout: 5m

route:
  receiver: aiops-webhook
  group_by: [alertname, service_name]
  group_wait: 10s
  group_interval: 30s
  repeat_interval: 1h
  routes:
    - match:
        severity: critical
      receiver: aiops-webhook
      group_wait: 5s
      repeat_interval: 5m
    - match:
        severity: warning
      receiver: aiops-webhook
      group_wait: 15s

receivers:
  - name: aiops-webhook
    webhook_configs:
      - url: http://localhost:8080/webhook
        send_resolved: true
        max_alerts: 20

inhibit_rules:
  - source_match:
      severity: critical
    target_match:
      severity: warning
    equal: [alertname, instance]
"""

# Prometheus scrape and remote-write config for ADOT collector
_PROMETHEUS_CONFIG_TEMPLATE = """\
global:
  scrape_interval: 15s
  evaluation_interval: 15s

rule_files:
  - /etc/prometheus/alert_rules.yml

scrape_configs:
  - job_name: aiops-self-healing
    metrics_path: /metrics
    scrape_interval: 10s
    static_configs:
      - targets: ['localhost:8080']
        labels:
          service: aiops
          environment: '{environment}'

remote_write:
  - url: '{amp_remote_write_url}'
    sigv4:
      region: '{region}'
    queue_config:
      max_samples_per_send: 1000
      max_shards: 5
      capacity: 2500

alerting:
  alertmanagers:
    - static_configs:
        - targets: ['localhost:9093']
"""

# Alert rules for self-contained monitoring
_ALERT_RULES = """\
groups:
  - name: aiops_service_alerts
    rules:
      - alert: AIOpsServiceDown
        expr: up{job="aiops-self-healing"} == 0
        for: 30s
        labels:
          severity: critical
          service_name: aiops
        annotations:
          summary: AIOps self-healing service is down

      - alert: HighRemediationFailureRate
        expr: >
          (sum(rate(remediation_failure_total[5m])) /
          (sum(rate(remediation_success_total[5m])) + sum(rate(remediation_failure_total[5m])) + 0.001)) > 0.3
        for: 5m
        labels:
          severity: warning
          service_name: aiops
        annotations:
          summary: Remediation failure rate exceeds 30 percent

      - alert: HighAlertIngestionRate
        expr: sum(rate(alerts_received_total[5m])) > 10
        for: 2m
        labels:
          severity: warning
          service_name: aiops
        annotations:
          summary: Alert ingestion rate is unusually high

      - alert: NoPlaybookMatchSpike
        expr: sum(rate(no_playbook_match_total[5m])) > 3
        for: 5m
        labels:
          severity: warning
          service_name: aiops
        annotations:
          summary: Many alerts have no matching playbook

      - alert: HighCPUUsage
        expr: 100 - (avg by(instance)(rate(node_cpu_seconds_total{mode="idle"}[1m])) * 100) > 90
        for: 1m
        labels:
          severity: critical
          service_name: web-frontend
        annotations:
          summary: High CPU usage detected
"""


class MonitoringStack(cdk.Stack):
    """Deploys Amazon Managed Prometheus and Alertmanager ECS sidecar.

    Architecture:
        [Node Exporters / App Metrics]
                    |
        [ADOT Collector sidecar] --remote-write--> [AMP Workspace]
                    |
        [Prometheus rule evaluation]
                    |
        [Alertmanager sidecar] --webhook--> [Self-Healing Service (localhost:8080)]

    The ADOT collector and Alertmanager run as sidecar containers in the same
    ECS task as the self-healing service, enabling localhost communication.

    Exports:
        amp_workspace_id: The AMP workspace ID.
        amp_endpoint: The AMP remote write endpoint.
    """

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
        self._context = context

        env_name = context.environment
        is_dev = env_name == "dev"

        # ---------------------------------------------------------------
        # Amazon Managed Service for Prometheus (AMP) Workspace
        # ---------------------------------------------------------------
        self.amp_workspace = aps.CfnWorkspace(
            self,
            "AmpWorkspace",
            alias=f"aiops-{env_name}",
            tags=[
                cdk.CfnTag(key="environment", value=env_name),
                cdk.CfnTag(key="project", value="aiops-self-healing"),
                cdk.CfnTag(key="managed-by", value="cdk"),
            ],
        )

        amp_remote_write_url = (
            f"https://aps-workspaces.{context.aws_region}.amazonaws.com"
            f"/workspaces/{self.amp_workspace.attr_workspace_id}/api/v1/remote_write"
        )

        # ---------------------------------------------------------------
        # Log Group for monitoring sidecars
        # ---------------------------------------------------------------
        self.monitoring_log_group = logs.LogGroup(
            self,
            "MonitoringLogGroup",
            log_group_name=f"/aiops/{env_name}/monitoring",
            retention=logs.RetentionDays.ONE_MONTH,
            removal_policy=cdk.RemovalPolicy.DESTROY,
        )

        # ---------------------------------------------------------------
        # Store configs in SSM Parameter Store for easy updates
        # ---------------------------------------------------------------
        prometheus_config = _PROMETHEUS_CONFIG_TEMPLATE.format(
            environment=env_name,
            amp_remote_write_url=amp_remote_write_url,
            region=context.aws_region,
        )

        ssm.StringParameter(
            self,
            "PrometheusConfig",
            parameter_name=f"/aiops/{env_name}/monitoring/prometheus-config",
            string_value=prometheus_config,
            description="Prometheus scrape and remote-write configuration",
        )

        ssm.StringParameter(
            self,
            "AlertmanagerConfig",
            parameter_name=f"/aiops/{env_name}/monitoring/alertmanager-config",
            string_value=_ALERTMANAGER_CONFIG,
            description="Alertmanager routing configuration",
        )

        ssm.StringParameter(
            self,
            "AlertRules",
            parameter_name=f"/aiops/{env_name}/monitoring/alert-rules",
            string_value=_ALERT_RULES,
            description="Prometheus alert rules for AIOps service",
        )

        # ---------------------------------------------------------------
        # IAM Role for ADOT Collector (Prometheus remote-write to AMP)
        # ---------------------------------------------------------------
        self.adot_task_role = iam.Role(
            self,
            "AdotTaskRole",
            role_name=f"AiopsAdotRole-{env_name}",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
        )

        # AMP remote write permissions
        self.adot_task_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "aps:RemoteWrite",
                    "aps:GetSeries",
                    "aps:GetLabels",
                    "aps:GetMetricMetadata",
                ],
                resources=[self.amp_workspace.attr_arn],
            )
        )

        # SSM read permissions for config retrieval
        self.adot_task_role.add_to_policy(
            iam.PolicyStatement(
                actions=["ssm:GetParameter", "ssm:GetParameters"],
                resources=[
                    f"arn:aws:ssm:{context.aws_region}:{context.aws_account}:parameter/aiops/{env_name}/monitoring/*"
                ],
            )
        )

        # Note: The compute task role's AMP write permission is added in
        # ComputeStack itself to avoid cross-stack references.

        # ---------------------------------------------------------------
        # ECS Task Definition with sidecars (separate from main service)
        # This creates a dedicated monitoring task with ADOT + Alertmanager
        # that scrapes the main service via service discovery.
        # ---------------------------------------------------------------
        # For simplicity, we add sidecar containers to the EXISTING task
        # definition by providing a separate monitoring service that
        # runs alongside the main service in the same VPC.
        # ---------------------------------------------------------------
        # --- Monitoring ECS Task Definition (separate execution role to avoid cycle) ---
        monitoring_exec_role = iam.Role(
            self,
            "MonitoringExecRole",
            role_name=f"AiopsMonitoringExecRole-{env_name}",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
        )
        monitoring_exec_role.add_to_policy(
            iam.PolicyStatement(
                actions=["ecr:GetAuthorizationToken"],
                resources=["*"],
            )
        )
        monitoring_exec_role.add_to_policy(
            iam.PolicyStatement(
                actions=["logs:CreateLogStream", "logs:PutLogEvents"],
                resources=[self.monitoring_log_group.log_group_arn + ":*"],
            )
        )

        monitoring_task_def = ecs.FargateTaskDefinition(
            self,
            "MonitoringTaskDef",
            cpu=256,
            memory_limit_mib=512,
            execution_role=monitoring_exec_role,
            task_role=self.adot_task_role,
        )

        # --- ADOT Collector container (Prometheus scraper + remote-write) ---
        monitoring_task_def.add_container(
            "AdotCollector",
            image=ecs.ContainerImage.from_registry(
                "public.ecr.aws/aws-observability/aws-otel-collector:v0.40.0"
            ),
            essential=True,
            environment={
                "AOT_CONFIG_CONTENT": self._get_adot_config(
                    env_name, amp_remote_write_url, context.aws_region
                ),
            },
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix="adot",
                log_group=self.monitoring_log_group,
            ),
            port_mappings=[
                ecs.PortMapping(container_port=4317, protocol=ecs.Protocol.TCP),
                ecs.PortMapping(container_port=8889, protocol=ecs.Protocol.TCP),
            ],
        )

        # --- Alertmanager container (evaluates rules, sends webhooks) ---
        monitoring_task_def.add_container(
            "Alertmanager",
            image=ecs.ContainerImage.from_registry(
                "prom/alertmanager:v0.27.0"
            ),
            essential=True,
            command=[
                "--config.file=/etc/alertmanager/alertmanager.yml",
                "--storage.path=/alertmanager",
                "--web.listen-address=:9093",
                f"--web.external-url=http://alertmanager.aiops-{env_name}.internal:9093",
            ],
            environment={
                "ALERTMANAGER_CONFIG": _ALERTMANAGER_CONFIG,
            },
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix="alertmanager",
                log_group=self.monitoring_log_group,
            ),
            port_mappings=[
                ecs.PortMapping(container_port=9093, protocol=ecs.Protocol.TCP),
            ],
        )

        # --- Monitoring ECS Service ---
        # Look up the cluster by name to avoid cross-stack exports
        monitoring_cluster = ecs.Cluster.from_cluster_attributes(
            self,
            "ImportedCluster",
            cluster_name=f"aiops-cluster-{env_name}",
            vpc=network_stack.vpc,
            security_groups=[],
        )

        if not is_dev:
            self.monitoring_service = ecs.FargateService(
                self,
                "MonitoringService",
                cluster=monitoring_cluster,
                task_definition=monitoring_task_def,
                desired_count=1,
                security_groups=[network_stack.ecs_security_group],
                vpc_subnets=ec2.SubnetSelection(
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
                ),
                service_name=f"aiops-monitoring-{env_name}",
            )
        else:
            # Dev: still deploy monitoring for testing
            self.monitoring_service = ecs.FargateService(
                self,
                "MonitoringService",
                cluster=monitoring_cluster,
                task_definition=monitoring_task_def,
                desired_count=1,
                security_groups=[network_stack.ecs_security_group],
                vpc_subnets=ec2.SubnetSelection(
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
                ),
                service_name=f"aiops-monitoring-{env_name}",
                capacity_provider_strategies=[
                    ecs.CapacityProviderStrategy(
                        capacity_provider="FARGATE_SPOT", weight=1
                    ),
                ],
            )

        # ---------------------------------------------------------------
        # CloudFormation Outputs
        # ---------------------------------------------------------------
        CfnOutput(
            self,
            "AmpWorkspaceId",
            value=self.amp_workspace.attr_workspace_id,
            export_name=f"AiopsAmpWorkspaceId-{env_name}",
        )
        CfnOutput(
            self,
            "AmpEndpoint",
            value=amp_remote_write_url,
            export_name=f"AiopsAmpEndpoint-{env_name}",
        )
        CfnOutput(
            self,
            "MonitoringServiceName",
            value=self.monitoring_service.service_name,
            export_name=f"AiopsMonitoringServiceName-{env_name}",
        )

    @staticmethod
    def _get_adot_config(env_name: str, amp_url: str, region: str) -> str:
        """Generate the ADOT collector configuration for Prometheus pipeline."""
        return f"""\
extensions:
  sigv4auth:
    region: "{region}"
    service: "aps"

receivers:
  prometheus:
    config:
      global:
        scrape_interval: 15s
      scrape_configs:
        - job_name: aiops-self-healing
          metrics_path: /metrics
          scrape_interval: 10s
          dns_sd_configs:
            - names:
                - aiops-service-{env_name}.aiops-{env_name}.local
              type: A
              port: 8080
          static_configs:
            - targets: ['localhost:8080']
              labels:
                service: aiops
                environment: {env_name}

exporters:
  prometheusremotewrite:
    endpoint: "{amp_url}"
    auth:
      authenticator: sigv4auth
    resource_to_telemetry_conversion:
      enabled: true

service:
  extensions: [sigv4auth]
  pipelines:
    metrics:
      receivers: [prometheus]
      exporters: [prometheusremotewrite]
"""
