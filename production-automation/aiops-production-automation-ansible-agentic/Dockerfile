FROM python:3.11-slim AS base

# TARGETPLATFORM is automatically set by BuildKit/BuildX.
# No need to declare it explicitly.

# Install system dependencies and Ansible
RUN apt-get update && apt-get install -y --no-install-recommends \
    ansible \
    openssh-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install the AWS SSM connection plugin for Ansible
RUN ansible-galaxy collection install community.aws amazon.aws --force

# Create non-root user
RUN useradd --create-home --shell /bin/bash appuser

WORKDIR /app

# Install Python dependencies from lock file for reproducibility
COPY requirements.lock ./requirements.lock
RUN pip install --no-cache-dir -r requirements.lock

# Copy application code
COPY src/ ./src/
COPY config/ ./config/
COPY playbooks/ ./playbooks/
COPY ansible.cfg ./ansible.cfg

# Set ownership
RUN chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Default environment variables
ENV PORT=8080
ENV LOG_LEVEL=INFO
ENV PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Expose port
EXPOSE ${PORT}

# Graceful shutdown: SIGTERM handling with 30s drain period
STOPSIGNAL SIGTERM

# Application entrypoint
CMD ["python", "-m", "src.main"]
