# SmartBanker AI — Streamlit UI

Local web interface for the Personal Banker AI Agent.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run in local mode (no AWS required)
streamlit run ui/app.py
```

## Execution Modes

### Local Mode (default)
Runs the agent in-process. No AWS credentials or deployed backend needed. Uses local stub tools.

### Remote Mode
Connects to the AWS-deployed agent via AgentCore Gateway. Requires:
- Deployed backend (see `deployment/` for instructions)
- AgentCore Gateway URL
- Valid AWS credentials (for IAM-authenticated endpoints)

Configure the Gateway URL in the sidebar after switching to Remote mode.

## Features

- Chat interface with conversation history
- Structured recommendation cards with risk/confidence indicators
- Service request submission form
- Proactive notifications panel
- Color-coded status indicators
- Explainability and disclaimer display
