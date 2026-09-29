"""Add speaker notes to the existing PPTX presentation."""

from pptx import Presentation

pptx_path = "AIOps_Self_Healing_Infrastructure_Presentation.pptx"
prs = Presentation(pptx_path)

# Speaker notes for each slide (index 0 = slide 1)
notes = [
    # Slide 1: Title
    (
        "Welcome everyone. Today I'll walk you through our AIOps Self-Healing Infrastructure platform. "
        "This is a production-grade solution that combines AI-powered reasoning with Ansible automation "
        "to detect, analyze, and remediate production incidents automatically — with human oversight for safety. "
        "The platform is built entirely on AWS using services like Amazon Bedrock for AI, ECS Fargate for compute, "
        "DynamoDB for state management, and CDK for infrastructure as code."
    ),
    # Slide 2: Problem Statement
    (
        "Let's start with WHY we built this. In most organizations, incident response is still heavily manual. "
        "When an alert fires at 3 AM, an on-call engineer gets paged, logs into systems, reads runbooks, "
        "and manually executes remediation steps. MTTR averages 30-90 minutes. "
        "60% or more of production alerts are repetitive — same issue, same fix, over and over. "
        "Engineers face alert fatigue, especially during storms when hundreds of alerts fire simultaneously. "
        "There's no organizational learning — the knowledge stays in people's heads, not in systems."
    ),
    # Slide 3: Solution Overview
    (
        "Our solution is a fully automated self-healing platform with two operating modes. "
        "Rule Mode handles known alerts — things we've seen before and have pre-vetted Ansible playbooks for. "
        "AI Agent Mode handles unknown alerts — it uses Amazon Bedrock to analyze the situation and suggest remediation. "
        "The key insight is: we don't need expensive AI for every alert. 70% of alerts are repetitive and can be handled "
        "by cheap, fast models or even rule-based matching. We reserve premium AI for truly novel situations. "
        "Human-in-the-loop approval ensures operators stay in control for high-risk actions. "
        "And the system learns from every incident — outcomes feed back into the model router and effectiveness scorer."
    ),
    # Slide 4: Architecture Flow
    (
        "Here's the end-to-end flow. An EC2 instance experiences an issue — say CPU spikes above 80%. "
        "CloudWatch detects this, triggers an alarm, sends to SNS, which invokes a Lambda. "
        "The Lambda sends an Alertmanager-format webhook to our ECS Fargate service via API Gateway. "
        "The service runs the alert through our 8-stage pipeline: normalize the payload, enrich with asset metadata, "
        "match to a playbook, evaluate through 7 guardrail layers, get human approval if needed, "
        "execute the Ansible playbook, validate the fix worked via baking period, and finally store the outcome. "
        "The whole thing runs asynchronously with up to 50 concurrent pipelines."
    ),
    # Slide 5: Section - AWS Infrastructure
    (
        "Let's dive into the AWS infrastructure layer. Everything is defined as Infrastructure as Code using AWS CDK v2 in Python."
    ),
    # Slide 6: CDK Stack Architecture
    (
        "We have 6 CDK stacks, each responsible for one concern. "
        "The Network stack creates the VPC with 2 availability zones, NAT gateways, and VPC endpoints. "
        "The Data stack provisions DynamoDB for incident memory with 4 Global Secondary Indexes, SQS with a dead-letter queue, and an ECR repository. "
        "The Compute stack is the largest — it creates the ECS Fargate cluster, task definitions, IAM roles with least-privilege policies, "
        "API Gateway HTTP API, Secrets Manager secrets, and SSM parameters. "
        "Observability adds SNS topics, CloudWatch alarms, and budget alerts. "
        "Monitoring optionally deploys Prometheus and Grafana on ECS. "
        "Simulation creates a target EC2 instance with stress-ng and Lambda functions to trigger test alerts. "
        "Stacks are deployed in dependency order: Network → Data → Compute → Observability."
    ),
    # Slide 7: Network & Security
    (
        "On the network side, ECS tasks run in private subnets with no public IPs. "
        "All AWS API traffic goes through VPC endpoints — this means Bedrock calls, DynamoDB operations, SQS messaging "
        "never leave the AWS backbone network. Gateway endpoints for DynamoDB and S3 are free and eliminate NAT data processing charges. "
        "On security: every IAM policy is scoped to specific resource ARNs. "
        "API Gateway has WAF with rate limiting at 100 requests per 5 minutes per IP. "
        "Secrets are in Secrets Manager with automatic 90-day rotation via a custom Lambda. "
        "Approval tokens are HMAC-signed to prevent forgery. "
        "Payloads are validated with Pydantic models and capped at 1 MB."
    ),
    # Slide 8: Section - AI/LLM
    (
        "Now let's talk about the AI layer — this is where Amazon Bedrock comes in. "
        "We use a multi-model strategy to balance cost and capability."
    ),
    # Slide 9: Model Router
    (
        "The Model Router is our cost optimization engine. Instead of always calling Claude Sonnet at 3 dollars per thousand calls, "
        "we classify each alert's complexity and route to the cheapest model that can handle it. "
        "SIMPLE alerts — seen 5 or more times, over 90 percent historical success rate, low severity — go to Nova Lite at 30 cents per thousand calls. "
        "That's 70% of all alerts. MODERATE alerts — limited history, mixed outcomes — go to Nova Pro at 1 dollar per thousand. "
        "COMPLEX alerts — never seen before, P1 severity, all past attempts failed — get Claude Sonnet. That's only 10% of alerts. "
        "The auto-escalation feature means if a cheaper model returns low confidence (below 0.5), "
        "we automatically retry with the next-tier model. This gives us 60-90% cost savings without sacrificing quality."
    ),
    # Slide 10: Reasoning Agent
    (
        "The AI Reasoning Agent is the brain of the system. When invoked, it first retrieves historical incidents "
        "from DynamoDB — same alert name, same service — to provide context about what worked before and what didn't. "
        "It builds a structured prompt with a stable prefix (good for prompt caching) and a variable suffix with the current alert details. "
        "The prompt includes: system role as an SRE expert, alert context, service topology, past outcomes, and excluded actions. "
        "We invoke Bedrock with a 30-second timeout, 2 retries with exponential backoff. "
        "The response is parsed into a structured RemediationPlan with steps, confidence score, and reasoning. "
        "Confidence gating ensures P1 alerts require 80% confidence, general alerts require 70%. "
        "If the primary model fails, we try the fallback chain: Claude Sonnet → Nova Pro → Haiku → Nova Lite. "
        "If ALL models fail, we fall back to rule-based playbook matching — the system never fully stops."
    ),
    # Slide 11: Section - Pipeline
    (
        "Let's look at how alerts flow through the system — the event-driven pipeline architecture."
    ),
    # Slide 12: Pipeline Stages
    (
        "The pipeline has 8 stages, each with clear responsibilities and failure handling. "
        "Normalize: converts the Alertmanager webhook JSON into our internal NormalizedAlert dataclass with a unique UUID. "
        "Enrich: looks up the target host in our asset inventory YAML to add service name, owner, location. "
        "Match: evaluates rules from playbook_mapping.yml — first match wins. If no rule matches, we go to AI mode. "
        "Guardrails: all 7 safety checks run in sequence with short-circuit on the first DENY or DEFER. "
        "Approval: for high-risk actions, an email is sent with an approve button. Low-risk actions auto-proceed. "
        "Execute: Ansible playbook runs via asyncio subprocess with a 300-second timeout. "
        "Baking: after execution, we monitor whether the original alarm resolves and the host comes back healthy. "
        "Notify: outcome is persisted to DynamoDB, audit log is written, and stakeholders are notified. "
        "The whole thing supports 50 concurrent pipelines via asyncio Semaphore."
    ),
    # Slide 13: Storm Detection
    (
        "Alert storms are one of the biggest challenges in production operations. "
        "When a database goes down, you might get hundreds of alerts — APITimeout, ConnectionRefused, HealthCheckFailed — all symptoms of the same root cause. "
        "Our Storm Detector uses a sliding window algorithm to track alert rate. "
        "When rate exceeds 50 per minute, it enters storm mode and groups alerts by alert_name plus service. "
        "Only one representative per group gets processed — this reduces noise 10 to 50x. "
        "If the internal queue exceeds capacity, it returns HTTP 429 and Alertmanager automatically retries later. "
        "Separately, our Alert Inhibition rules suppress symptom alerts when a root-cause alert is active. "
        "For example, when DatabaseDown fires, we automatically suppress APITimeout, ConnectionRefused, and HealthCheckFailed. "
        "This prevents us from trying to fix 20 symptoms when there's really just one problem."
    ),
    # Slide 14: Section - Safety
    (
        "Safety is the most critical aspect of any automated remediation system. "
        "If you get this wrong, automation causes more damage than the original incident. "
        "We've built defense-in-depth with multiple safety layers."
    ),
    # Slide 15: 7-Layer Guardrail Engine
    (
        "The Guardrail Engine runs 7 checks in a fixed order with short-circuit semantics. "
        "First, Self-Protection: never target our own automation controllers, monitoring infrastructure, or secret vaults. "
        "Second, Maintenance Window: if we're in a scheduled maintenance window, defer the action — don't execute. "
        "Third, Circuit Breaker: if this specific host has failed too many times recently, stop trying. "
        "Fourth, Concurrency Guard: bulkhead isolation ensures one service can't monopolize all execution slots. "
        "Fifth, Blast Radius Classifier: scores the risk as low, medium, high, or critical based on service and action type. "
        "Sixth, Health Checker: looks at downstream service dependencies — if they're already degraded, elevates risk. "
        "Seventh, Approval Gate: for high or critical risk, requires human click before proceeding. "
        "Plus the Plan Validator for AI-generated plans. "
        "The whole evaluation has a 15-second timeout — if it takes too long, it auto-DENYs. "
        "Any check returning DENY immediately stops evaluation and blocks the action."
    ),
    # Slide 16: Plan Validator
    (
        "The Plan Validator is specifically for AI-generated remediation plans. "
        "AI models can sometimes suggest dangerous commands — rm -rf, shutting down hosts, flushing iptables. "
        "We maintain a regex-based denylist in denied_commands.yml that blocks these patterns. "
        "Even if the AI suggests it, even if it seems reasonable in context — if it matches a denied pattern, it's rejected. "
        "We also enforce parameter bounds: no action can target more than 5 hosts, no plan can have more than 10 steps, "
        "no timeout can exceed 600 seconds, and no host can have more than 3 AI-generated executions per hour. "
        "Filesystem operations are restricted to specific paths: /var/log, /tmp, /opt/app, /var/cache. "
        "This is inspired by Amazon Bedrock Guardrails' denied topics pattern — a hard safety layer between AI output and execution."
    ),
    # Slide 17: Fleet Breaker
    (
        "The Fleet Circuit Breaker is a global safety net. Unlike the per-host breaker that tracks individual host failures, "
        "this one tracks failures across ALL hosts. "
        "Scenario: a bad Ansible playbook gets deployed. Every execution fails. Without a fleet breaker, "
        "the system would keep trying on every host, potentially causing damage fleet-wide. "
        "With the fleet breaker: after 5 failures within 5 minutes across any hosts, ALL automation pauses. "
        "After a 10-minute cooldown, recovery uses adaptive ramp-up: first allow 1 concurrent execution. "
        "If that succeeds, allow 2. Then 4, then 8, back to normal. "
        "This prevents the thundering herd problem where all paused work resumes simultaneously. "
        "The per-host breaker complements this by preventing repeated failed attempts on a single broken host."
    ),
    # Slide 18: Section - Configuration
    (
        "One of the key design principles is that operational behavior is configuration-driven, not code-driven. "
        "Operators can change routing rules, safety bounds, and concurrency limits without deploying new code."
    ),
    # Slide 19: 12 YAML Files
    (
        "We have 12 YAML configuration files that control the system's behavior. "
        "On the routing side: playbook_mapping.yml maps alert names to Ansible playbooks. "
        "asset_inventory.yml is the host registry — hostnames, IPs, services, owners. "
        "service_dependencies.yml defines which services depend on which, used by the health checker. "
        "execution_dependencies.yaml defines ordering constraints — like 'drain connections before restart'. "
        "risk_classification.yml scores blast radius per service-action pair. "
        "resource_conflicts.yaml defines what to do when two actions compete for the same resource. "
        "On the safety side: denied_commands.yml blocks dangerous AI commands. "
        "protected_hosts.yml lists hosts that automation must never target. "
        "inhibition_rules.yml suppresses symptom alerts when root cause is active. "
        "maintenance_windows.yml defines when to defer actions. "
        "bulkhead_limits.yml caps concurrency per service. "
        "stop_conditions.yml lists alarms to monitor during execution. "
        "All of these are loaded at startup and can be updated without code changes."
    ),
    # Slide 20: Section - Approval
    (
        "Human-in-the-loop is essential for trust. Operators need to feel they're in control, "
        "especially for high-risk actions. Let me show you how our approval workflow works."
    ),
    # Slide 21: Approval Workflow
    (
        "When a high-risk action is identified, the system sends an email via Amazon SES. "
        "The email contains a root cause analysis — either AI-generated or based on historical patterns — "
        "along with the alert details, proposed remediation steps, and a time-limited Approve button. "
        "The approval token is HMAC-signed using a secret from Secrets Manager, stored in DynamoDB with TTL, "
        "and expires after 30 minutes. If the operator clicks the link, it first shows a confirmation page (GET request), "
        "then the actual execution happens on POST. This two-step design prevents email link scanners from auto-triggering remediation. "
        "The token is consumed atomically via DynamoDB conditional writes — exactly-once semantics. "
        "Because tokens are in DynamoDB, they survive ECS task restarts, rolling deployments, and scaling events. "
        "Any task in the fleet can validate and consume the token."
    ),
    # Slide 22: Section - Execution
    (
        "Once approved, the system executes the remediation. Let's look at the execution layer."
    ),
    # Slide 23: Ansible Execution
    (
        "The Remediation Executor runs Ansible playbooks as asyncio subprocesses. "
        "It validates that the playbook file exists and is readable before spawning the process. "
        "Each execution has a configurable timeout — default 300 seconds. "
        "If the timeout is exceeded, we send SIGTERM first, wait 5 seconds for graceful shutdown, "
        "then SIGKILL if the process is still running. "
        "Concurrency is limited to 10 simultaneous executions via an asyncio Semaphore. "
        "Output is captured and truncated to 10,000 characters to prevent memory issues. "
        "We have playbooks for: fixing high CPU by killing runaway processes, restarting systemd services, "
        "clearing disk by removing old logs and temp files, and restarting specific processes. "
        "In production, execution happens via SSM RunCommand — no SSH keys needed. "
        "EC2 instances must be tagged with 'managed-by: aiops' to be targetable."
    ),
    # Slide 24: Stop Conditions & Baking
    (
        "Two safety mechanisms operate during and after execution. "
        "Stop Conditions are CloudWatch alarms monitored every 10 seconds DURING remediation. "
        "If our remediation is making things worse — for example, healthy host count drops to zero, "
        "or 5xx error rate spikes above 100 per minute — we immediately abort the execution. "
        "There's a 15-second grace period to let things stabilize before we start monitoring. "
        "A global stop condition fires if more than 3 services degrade simultaneously — that halts all automation. "
        "This is inspired by AWS Fault Injection Simulator stop conditions. "
        "Baking Validation happens AFTER execution completes. We monitor whether the original CloudWatch alarm resolves "
        "and whether the target host returns to a healthy state. "
        "If the alarm doesn't resolve, the outcome is marked as INEFFECTIVE. "
        "This feeds back into the effectiveness scorer, which influences future model routing decisions. "
        "Over time, the system learns which remediations actually work."
    ),
    # Slide 25: Section - Observability
    (
        "You can't operate what you can't observe. Let's look at our observability strategy."
    ),
    # Slide 26: Observability
    (
        "We have four pillars of observability. "
        "Structured JSON logging goes to CloudWatch via the awslogs driver. Every log entry includes timestamp, level, logger name, "
        "message, and incident_id when available. Retention varies by environment: 30 days for dev, 90 for staging, 365 for prod. "
        "Custom CloudWatch metrics in the AIOps namespace track alerts received, remediation success/failure/timeout, "
        "AI reasoning latency, and storm suppression counts. "
        "CloudWatch Alarms alert us when: DLQ depth exceeds 5 messages, AI latency p95 goes above 15 seconds, "
        "or remediation failure rate exceeds 30%. A composite alarm detects when rollback is needed. "
        "Distributed tracing via OpenTelemetry and X-Ray gives us end-to-end request visibility. "
        "Each pipeline stage emits a span with the incident_id attribute, and Bedrock calls emit GenAI semantic convention spans "
        "with model name, token counts, and latency. Tracing is optional and gracefully degrades if not installed."
    ),
    # Slide 27: Section - CI/CD
    (
        "Let's look at how we deploy this safely to production."
    ),
    # Slide 28: CI/CD Pipeline
    (
        "Our CI pipeline runs on every push and PR via GitHub Actions. "
        "It starts with linting using ruff — both code style checks and formatting verification. "
        "Then unit tests with a minimum 80% coverage requirement. "
        "Property-based tests using Hypothesis generate random inputs to find edge cases. "
        "CDK synth validates that all CloudFormation templates can be generated without errors. "
        "CDK assertion tests verify specific resource configurations like IAM policies. "
        "Finally, Docker build, ECR push, and vulnerability scanning. "
        "The CD pipeline deploys stacks in dependency order. For production, there's a manual approval gate with 4-hour timeout. "
        "A health gate after deployment requires 3 consecutive healthy responses from the service within 5 minutes. "
        "If the health gate fails, automatic rollback kicks in using the previous deployment manifest stored in SSM. "
        "We keep a 5-slot sliding window of deployment manifests for quick rollback. "
        "Branch strategy: main deploys to dev, staging branch to staging, version tags to production."
    ),
    # Slide 29: Section - Cost
    (
        "Cost optimization is built into every layer of the architecture. Let me break it down."
    ),
    # Slide 30: Cost Optimization
    (
        "The biggest cost savings come from intelligent model routing. "
        "Instead of spending 3 dollars per thousand invocations on Claude Sonnet for every alert, "
        "70% of alerts use Nova Lite at 30 cents per thousand — that's a 10x reduction for the majority of traffic. "
        "On infrastructure: dev uses a single NAT Gateway saving about 45 dollars per month versus prod's two. "
        "VPC Gateway Endpoints for DynamoDB and S3 are free and eliminate NAT data processing charges "
        "which can be significant for high-throughput workloads. "
        "DynamoDB uses PAY_PER_REQUEST billing — no over-provisioning, pay only for what you use. "
        "ECR lifecycle rules prevent storage bloat. ECS auto-scaling means we're not paying for idle compute. "
        "Operationally, storm detection prevents wasteful parallel remediations during outages. "
        "Alert inhibition means we don't waste AI calls and execution time on symptom alerts. "
        "Bulkhead limits prevent runaway costs from one misbehaving service."
    ),
    # Slide 31: Section - Resilience
    (
        "Production systems must be resilient. Let me show you the patterns we've implemented."
    ),
    # Slide 32: Resilience Patterns
    (
        "We've implemented 11 resilience patterns. "
        "Retry with Fallback: Bedrock calls retry twice with exponential backoff, then try the next model in the chain. "
        "Circuit Breaker at two levels: per-host prevents hammering a broken target, fleet-wide prevents systemic damage. "
        "Bulkhead Isolation: each service group has its own concurrency limit, so a noisy neighbor can't starve others. "
        "Backpressure: storm detector, HTTP 429 responses, and SQS visibility timeout work together to prevent overload. "
        "Graceful Degradation: if Bedrock is completely down, we fall back to rule-based playbook matching — the system keeps working. "
        "Idempotency: alert fingerprints in DynamoDB with TTL prevent duplicate processing. "
        "Host Locks: DynamoDB conditional writes prevent two remediations from running on the same host simultaneously. "
        "Graceful Shutdown: on SIGTERM we stop accepting new work, drain in-progress pipelines for 25 seconds, release locks, then exit. "
        "DLQ: messages that fail 3 times move to the dead-letter queue for manual investigation. "
        "Stop Conditions: if the target system gets worse during remediation, we abort immediately. "
        "Adaptive Ramp-up: after a fleet breaker reset, we slowly increase load to prevent thundering herd."
    ),
    # Slide 33: Section - Demo
    (
        "Let me show you a concrete demo scenario to bring all this together."
    ),
    # Slide 34: Demo Flow
    (
        "Here's our demo scenario: simulating a high CPU alert and watching the system remediate it. "
        "Step 1: We run stress-ng on our target EC2 instance to push CPU above 80%. "
        "Step 2: Within about 1 minute, CloudWatch detects the threshold breach and the alarm triggers. "
        "Step 3: SNS delivers to a Lambda function that formats an Alertmanager webhook and POSTs to our ECS service. "
        "Step 4: The pipeline normalizes the alert, enriches it with host metadata, and matches it to fix_high_cpu.yml. "
        "Step 5: All 7 guardrail checks pass — this is a low-risk, well-known playbook. "
        "Step 6: An email is sent to the operator with the root cause analysis and an Approve button. "
        "Step 7: The operator clicks the approve link. "
        "Step 8: Ansible executes the playbook on the EC2 instance via SSM, killing the stress-ng process. "
        "Step 9: CPU drops back to normal, CloudWatch alarm resolves. "
        "Step 10: The successful outcome is recorded in DynamoDB. Next time this alert fires, "
        "the model router knows it has high success rate and routes to the cheapest model. "
        "Total end-to-end time is about 2-3 minutes, mostly waiting for the CloudWatch alarm evaluation period."
    ),
    # Slide 35: Key Differentiators
    (
        "Let me highlight what makes this solution different from other AIOps tools. "
        "First, the AI plus Rules hybrid approach: we don't force everything through AI. Known issues use fast, safe, pre-vetted rules. "
        "AI is reserved for novel situations where its reasoning actually adds value. "
        "Second, human-in-the-loop: operators stay in control. The system suggests and executes, but humans approve high-risk actions. "
        "Third, configuration-driven: ops teams can change behavior with YAML files, no code deployment needed. "
        "Fourth, cost-optimized AI: intelligent model routing saves 60-90% compared to always using premium models. "
        "Fifth, defense-in-depth safety: 7 guardrail layers plus fleet breaker plus stop conditions. "
        "Sixth, production-ready: VPC endpoints, Secrets Manager, WAF, least-privilege IAM — not a demo-ware solution. "
        "Seventh, full observability: structured logs, custom metrics, distributed tracing, dashboards. "
        "Eighth, self-improving: the effectiveness scorer and feedback loop mean the system gets better over time. "
        "Ninth, AWS-native: built entirely on managed AWS services with CDK IaC. "
        "Tenth, thoroughly tested: unit tests, property-based tests with Hypothesis, CDK assertions, and integration tests."
    ),
    # Slide 36: Tech Stack
    (
        "Quick summary of our technology stack. "
        "On the application side: Python 3.11 with FastAPI for the async web framework, "
        "Pydantic for payload validation, Ansible for playbook execution, asyncio for concurrency, "
        "Hypothesis for property-based testing, Ruff for linting and formatting, and OpenTelemetry for tracing. "
        "On the AWS side: ECS Fargate for serverless compute, Amazon Bedrock for AI with both Nova and Claude models, "
        "DynamoDB for state management and incident memory, SQS with DLQ for reliable messaging, "
        "API Gateway HTTP API for ingress with WAF, SES for approval emails, "
        "Secrets Manager for credential management, SSM for running commands on EC2 and storing parameters, "
        "CloudWatch for logs, metrics, and alarms, WAF for API protection, and CDK v2 for infrastructure as code."
    ),
    # Slide 37: Thank You
    (
        "Thank you for your time. I'm happy to answer any questions about the architecture, "
        "the AI strategy, the safety mechanisms, or the operational aspects of the platform. "
        "The source code is available in our repository with full documentation, demo guides, and deployment instructions."
    ),
]


# Apply notes to each slide
for i, slide in enumerate(prs.slides):
    if i < len(notes):
        notes_slide = slide.notes_slide
        notes_slide.notes_text_frame.text = notes[i]

prs.save(pptx_path)
print(f"Speaker notes added to all {len(prs.slides)} slides.")
print(f"File saved: {pptx_path}")
