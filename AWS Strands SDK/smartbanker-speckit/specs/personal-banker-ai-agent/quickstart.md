# Quickstart: Personal Banker AI Agent

## Overview
This guide helps you get started with the Personal Banker AI Agent, a multi-agent financial assistant built with AWS Bedrock and AgentCore.

## Prerequisites
- Python 3.11+
- AWS account with Bedrock and AgentCore access
- AWS CLI configured with appropriate permissions
- Docker (for local development)

## Installation
1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd personal-banker-ai-agent
   ```

2. Create virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Configure AWS:
   ```bash
   aws configure
   # Ensure Bedrock model access is enabled
   ```

## Configuration
1. Copy configuration template:
   ```bash
   cp src/config/settings.example.py src/config/settings.py
   ```

2. Update settings.py with your values:
   - AWS region
   - Bedrock model IDs
   - AgentCore memory configuration
   - Tool gateway endpoints

## Running the Agent
1. Start the agent runner:
   ```bash
   python -m src.agents.agent_runner
   ```

2. The agent will be available at the configured endpoint.

## Testing
Run the test suite:
```bash
pytest tests/
```

## Deployment
For production deployment to AWS AgentCore:
1. Build the container:
   ```bash
   docker build -t personal-banker-agent .
   ```

2. Deploy using AgentCore CLI:
   ```bash
   agentcore deploy --image personal-banker-agent
   ```

## First Interaction
Try a sample query:
```json
{
  "user_id": "test_user",
  "query": "Help me analyze my recent spending"
}
```

The agent will respond with spending insights and recommendations.

## Troubleshooting
- Check AWS permissions for Bedrock and AgentCore
- Verify model access in Bedrock console
- Ensure AgentCore memory is initialized
- Review logs in src/observability/logger.py