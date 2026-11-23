# Dockerfile for AIOps Self-Healing Infrastructure
# Requirements: 10.1, 10.2, 10.4, 10.6
#
# - Python base image with Ansible installation
# - Non-root user for security
# - SIGTERM graceful shutdown with 30s drain period (via src.main entrypoint)
# - Default port 8080
# - Container starts within 30 seconds

FROM python:3.11-slim AS base

# Set environment variables for runtime configuration
# PORT: Webhook listener port (Requirement 10.2)
# PYTHONUNBUFFERED: Ensure logs are flushed immediately for structured JSON output
# DRAIN_TIMEOUT: Graceful shutdown drain period in seconds (Requirement 10.6)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    LOG_LEVEL=INFO \
    ASSET_INVENTORY_PATH=/app/config/asset_inventory.yml \
    MAPPING_CONFIG_PATH=/app/config/mapping_config.yml \
    AUDIT_LOG_PATH=/app/audit.log

# Install system dependencies and Ansible (Requirement 10.1)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc \
        libffi-dev \
        openssh-client \
        sshpass \
    && pip install --no-cache-dir ansible-core \
    && apt-get purge -y gcc libffi-dev \
    && apt-get autoremove -y \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user (Requirement 10.1)
RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ ./src/
COPY config/ ./config/ 2>/dev/null || true
COPY playbooks/ ./playbooks/ 2>/dev/null || true

# Create audit log directory with proper permissions
RUN mkdir -p /app/logs && chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose the application port (Requirement 10.2 - default 8080)
EXPOSE 8080

# Configure SIGTERM as the stop signal for graceful shutdown (Requirement 10.6)
# The entrypoint (src.main) handles SIGTERM by:
# 1. Stopping acceptance of new alerts
# 2. Waiting up to 30s for in-progress pipelines to drain
# 3. Exiting with code 0 if drained, non-zero if timeout exceeded
STOPSIGNAL SIGTERM

# Health check to verify container starts within 30 seconds (Requirement 10.4)
HEALTHCHECK --interval=10s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT}/health')" || exit 1

# Run via src.main entrypoint which provides:
# - Configuration validation (exits non-zero if required env vars missing)
# - SIGTERM handler with 30s drain period
# - SIGHUP handler for config reload
# - Structured JSON logging to stdout/stderr
CMD ["python", "-m", "src.main"]
