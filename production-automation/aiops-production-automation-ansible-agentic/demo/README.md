# End-to-End Demo: Self-Healing in Action

This demo lets you trigger real alert scenarios and watch the full pipeline
resolve them automatically — from alert firing to remediation execution.

## Quick Start

```bash
# Start the full stack (self-healing + prometheus + alertmanager + grafana + target hosts)
docker compose -f docker-compose.demo.yml up -d

# Watch the self-healing service logs
docker compose -f docker-compose.demo.yml logs -f self-healing

# Open dashboards
# Grafana:      http://localhost:3000 (admin/admin)
# Prometheus:   http://localhost:9090
# Alertmanager: http://localhost:9093
```

## Demo Scenarios

### Scenario 1: High CPU → Restart Service
```bash
# Simulate CPU spike on the target host
python demo/trigger_scenario.py --scenario high-cpu

# What happens:
# 1. stress-ng runs on the target container
# 2. Node exporter reports CPU > 90%
# 3. Prometheus fires HighCPUUsage alert
# 4. Alertmanager sends webhook to self-healing
# 5. Pipeline matches → restart_service.yml
# 6. Ansible restarts the service on the target
# 7. CPU drops, alert resolves
```

### Scenario 2: Disk Full → Clear Disk
```bash
python demo/trigger_scenario.py --scenario disk-full

# Creates a large temp file on target → triggers DiskSpaceLow alert
# Pipeline matches → clear_disk.yml → removes old logs + temp files
```

### Scenario 3: Service Down → Restart
```bash
python demo/trigger_scenario.py --scenario service-down

# Kills the target service process → triggers InstanceDown alert
# Pipeline matches → restart_service.yml → restarts the service
```

### Scenario 4: Manual Alert Injection (bypass Prometheus)
```bash
python demo/trigger_scenario.py --scenario inject --alert-name HighMemoryUsage --severity warning

# Directly sends an Alertmanager webhook payload to the self-healing service
# Useful for testing without waiting for Prometheus evaluation intervals
```

## Observing the Pipeline

```bash
# See audit log entries (each remediation is logged)
docker compose -f docker-compose.demo.yml exec self-healing cat /app/logs/audit.log | python -m json.tool

# Check Prometheus metrics from the self-healing service
curl -s http://localhost:8080/metrics

# Check which alerts are currently firing
curl -s http://localhost:9093/api/v2/alerts | python -m json.tool
```

## Architecture

```
┌─────────────────┐         ┌──────────────┐
│  Target Host    │◄────────│  Self-Healing │
│  (simulated)    │ ansible │  Service     │
│  - node-exporter│         │  :8080       │
│  - fake app     │         └──────┬───────┘
└────────┬────────┘                │ ▲
         │ :9100                   │ │ webhook
         ▼                         │ │
┌─────────────────┐         ┌──────┴───────┐
│  Prometheus     │────────►│ Alertmanager │
│  :9090          │ alerts  │ :9093        │
└─────────────────┘         └──────────────┘
```
