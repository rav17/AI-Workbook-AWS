# Personal Banker AI Agent

A production-grade multi-agent financial assistant built for AWS Bedrock and Strands Agent SDK compatibility.

## Overview
This project provides:
- Multi-agent orchestration with coordinator, delegator, and worker agents
- AWS Bedrock integration for reasoning and embeddings
- AgentCore-managed short-term memory
- AgentCore-managed long-term semantic memory support
- Financial safety, compliance, and explainable recommendations
- Structured output contract for every specialist worker
- Observability and deployment guidance for AWS AgentCore

## Project Layout
- `src/agents/` - coordinator, delegator, worker agents
- `src/memory/` - AgentCore memory manager
- `src/tools/` - financial tool registry and schema validation
- `src/llm/` - AWS Bedrock client wrapper
- `src/observability/` - structured logging support
- `src/config/` - environment and runtime configuration
- `tests/` - unit tests and scenario validation
- `deployment/` - AWS deployment and AgentCore compatibility guidance

## Getting Started
1. Create a Python 3.11 virtual environment.
2. Install dependencies: `pip install boto3 pydantic pytest`
3. Configure environment variables for AWS and Bedrock.
4. Run tests: `pytest`

## Notes
This repository is designed as an enterprise-ready backend AI orchestration service, not a frontend application. It is intended to be deployed within AWS AgentCore compatible infrastructure.
