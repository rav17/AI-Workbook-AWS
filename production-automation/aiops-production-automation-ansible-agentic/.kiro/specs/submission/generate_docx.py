"""Generate the Written Application Word document with code snippets and screenshot placeholders."""

from docx import Document
from docx.shared import Inches, Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.style import WD_STYLE_TYPE
import os

doc = Document()

# Set default font
style = doc.styles['Normal']
font = style.font
font.name = 'Calibri'
font.size = Pt(11)

# Helper functions
def add_heading_styled(text, level=1):
    h = doc.add_heading(text, level=level)
    return h

def add_code_block(code_text, language="python"):
    """Add a formatted code block."""
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Cm(1)
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(6)
    run = p.add_run(code_text)
    run.font.name = 'Consolas'
    run.font.size = Pt(9)
    run.font.color.rgb = RGBColor(0x1E, 0x1E, 0x1E)

def add_screenshot_placeholder(caption):
    """Add a placeholder box for screenshots."""
    doc.add_paragraph()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(f"[INSERT SCREENSHOT: {caption}]")
    run.font.size = Pt(12)
    run.font.color.rgb = RGBColor(0x99, 0x99, 0x99)
    run.font.italic = True
    p2 = doc.add_paragraph()
    p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run2 = p2.add_run(f"Figure: {caption}")
    run2.font.size = Pt(10)
    run2.font.italic = True
    doc.add_paragraph()

# ============================================================
# TITLE PAGE
# ============================================================
doc.add_paragraph()
doc.add_paragraph()
title = doc.add_heading('IBM Consulting Generative & Agentic AI', level=0)
title.alignment = WD_ALIGN_PARAGRAPH.CENTER
subtitle = doc.add_heading('SRE/DevOps Engineer — Experienced Level', level=1)
subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
sub2 = doc.add_heading('Written Application', level=2)
sub2.alignment = WD_ALIGN_PARAGRAPH.CENTER
doc.add_paragraph()
doc.add_paragraph()
info = doc.add_paragraph()
info.alignment = WD_ALIGN_PARAGRAPH.CENTER
info.add_run('Project: ').bold = True
info.add_run('AIOps Self-Healing Infrastructure Platform')
doc.add_paragraph()
info2 = doc.add_paragraph()
info2.alignment = WD_ALIGN_PARAGRAPH.CENTER
info2.add_run('Submitted by: ').bold = True
info2.add_run('Ravindra Yadav')
doc.add_paragraph()
info3 = doc.add_paragraph()
info3.alignment = WD_ALIGN_PARAGRAPH.CENTER
info3.add_run('Role: ').bold = True
info3.add_run('SRE/DevOps Engineer')
doc.add_paragraph()
info4 = doc.add_paragraph()
info4.alignment = WD_ALIGN_PARAGRAPH.CENTER
info4.add_run('Date: ').bold = True
info4.add_run('August 2026')

doc.add_page_break()

# ============================================================
# SECTION 1: CLIENT NEED / BUSINESS PROBLEM
# ============================================================
add_heading_styled('1. Client Need / Business Problem', level=1)

doc.add_paragraph(
    'Project Name: AIOps Self-Healing Infrastructure Platform\n'
    'Dates: 2025 – Present\n'
    'Objective: Reduce Mean Time to Resolution (MTTR) for production infrastructure '
    'incidents by building an AI-powered, agentic self-healing platform that autonomously '
    'detects, diagnoses, and remediates infrastructure issues — with human-in-the-loop '
    'approval for safety.'
)

add_heading_styled('Business Problem', level=2)
doc.add_paragraph(
    'Production operations teams face alert fatigue, slow incident response times, '
    'and inconsistent remediation practices. Manual triage of CloudWatch alarms leads '
    'to delays (often 15–30+ minutes) before an operator can even begin troubleshooting. '
    'This project addresses the need for an intelligent automation layer that:'
)

bullets = [
    'Automatically correlates alerts with asset context and historical incident data',
    'Uses generative AI (Amazon Bedrock) to perform root cause analysis when no existing playbook matches',
    'Proposes remediation actions to operators via email with one-click approval',
    'Executes Ansible playbooks on target infrastructure (via AWS SSM) once approved',
    'Maintains a full audit trail, structured observability, and safety guardrails to prevent unintended blast radius',
]
for b in bullets:
    doc.add_paragraph(b, style='List Bullet')

doc.add_paragraph(
    'The platform targets SRE/DevOps teams managing cloud-native workloads on AWS who '
    'need to scale their incident response capabilities without proportionally scaling headcount.'
)

add_heading_styled('System Architecture Overview', level=2)
doc.add_paragraph('The end-to-end flow of the self-healing platform:')

arch_diagram = """
┌─────────────────────────────────────────────────────────────────────────┐
│ EC2 Target Instance (stress-ng running → CPU > 80%)                      │
└───────────────┬──────────────────────────────────────────────────────────┘
                │ CloudWatch detects
                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ CloudWatch Alarm → SNS → Lambda                                          │
│ (sends Alertmanager webhook to self-healing service)                     │
└───────────────┬──────────────────────────────────────────────────────────┘
                │ POST /webhook
                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ ECS Fargate: Self-Healing Service                                        │
│                                                                          │
│ Pipeline: normalize → enrich → match playbook                           │
│                                                                          │
│ ┌─────────────────────────────┐  ┌────────────────────────────────────┐ │
│ │ RULE MODE (playbook found)  │  │ AI MODE (no playbook)              │ │
│ │ → Email with Approve button │  │ → Bedrock Nova Pro analyzes        │ │
│ │ → Click = auto-remediation  │  │ → Email with suggested steps       │ │
│ └─────────────────────────────┘  └────────────────────────────────────┘ │
└───────────────┬──────────────────────────────────────────────────────────┘
                │ Operator clicks Approve
                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Ansible executes fix_high_cpu.yml on EC2 via SSM                         │
│ (kills stress-ng → CPU drops → alert resolves)                          │
└─────────────────────────────────────────────────────────────────────────┘
"""
add_code_block(arch_diagram, "text")

doc.add_page_break()

# ============================================================
# SECTION 2: RELEVANT IBM OFFERING
# ============================================================
add_heading_styled('2. Relevant IBM Generative & Agentic AI Offering', level=1)

doc.add_paragraph(
    'This project demonstrates capabilities aligned with IBM Consulting\'s AIOps and '
    'Intelligent Automation offerings, specifically:'
)

offerings = [
    'AIOps for IT Operations — Automated incident detection, correlation, and resolution using AI',
    'Generative AI for SRE — Leveraging large language models to generate root cause analyses, '
    'remediation plans, and operational recommendations',
    'Agentic AI Patterns — Building autonomous agents that reason over incidents, retrieve '
    'historical context, and produce structured remediation plans with confidence scoring and escalation logic',
]
for o in offerings:
    doc.add_paragraph(o, style='List Bullet')

doc.add_paragraph(
    'The solution directly supports IBM Consulting\'s "Client First...with a Point of View" '
    'approach by demonstrating how generative and agentic AI transforms traditional reactive '
    'operations into proactive, self-healing infrastructure management.'
)

doc.add_page_break()

# ============================================================
# SECTION 3: USE OF WATSONX / STRATEGIC PARTNER PRODUCTS
# ============================================================
add_heading_styled('3. Use of watsonx and/or Strategic Partner Products', level=1)

doc.add_paragraph(
    'This implementation uses Amazon Bedrock as the generative AI foundation, which is a '
    'Strategic Partner product within IBM Consulting\'s multi-cloud delivery model.'
)

add_heading_styled('AI Models Used (with Fallback Chain)', level=2)
models = [
    'Anthropic Claude 3 Sonnet (via Bedrock) — Primary reasoning model for complex root cause analysis',
    'Amazon Nova Pro — Secondary model for cost-effective reasoning',
    'Anthropic Claude 3 Haiku (via Bedrock) — Lightweight fallback for simple incident classification',
    'Amazon Nova Lite — Final fallback ensuring graceful degradation',
]
for i, m in enumerate(models, 1):
    doc.add_paragraph(f'{i}. {m}')

add_heading_styled('How the AI Agent Works', level=2)
doc.add_paragraph(
    'The AIReasoningAgent class implements a full agentic AI pattern:'
)
agent_features = [
    'Memory: Retrieves up to 50 historical incidents from a DynamoDB-backed incident store, '
    'including past outcomes (success/failure) and execution durations',
    'Reasoning: Builds structured prompts with alert context, labels, historical patterns, '
    'and excluded actions (actions that always failed in the past)',
    'Structured Output: Produces a JSON RemediationPlan with confidence scores (0.0–1.0), '
    'step-by-step remediation instructions, and escalation flags',
    'Fallback Logic: If AI is unavailable (throttling, timeout, access denied), gracefully '
    'falls back to rule-based playbook matching',
    'Confidence Thresholds: P1 incidents require 80% confidence; others require 70% — '
    'below threshold triggers escalation to human operators',
]
for f in agent_features:
    doc.add_paragraph(f, style='List Bullet')

add_heading_styled('Code: AI Reasoning Agent — Model Invocation with Fallback', level=3)
doc.add_paragraph('The following code shows the multi-model fallback chain and retry logic:')

code_fallback = '''async def _invoke_with_retry(self, prompt: str) -> str:
    """Invoke Bedrock with retry, timeout, and model fallback.

    Tries the configured model first. If it fails with AccessDenied
    or ModelNotFound, tries fallback models (Nova Pro, etc.).
    """
    import asyncio

    models_to_try = [self._config.model_id] + [
        m for m in self._config.FALLBACK_MODELS
        if m != self._config.model_id
    ]

    for model_id in models_to_try:
        backoff = INITIAL_BACKOFF_SECONDS
        for attempt in range(MAX_RETRIES + 1):
            try:
                result = await asyncio.wait_for(
                    self._invoke_model(prompt, model_id=model_id),
                    timeout=REASONING_TIMEOUT_SECONDS,
                )
                if model_id != self._config.model_id:
                    logger.info("Using fallback model: %s", model_id)
                return result
            except asyncio.TimeoutError:
                if attempt == MAX_RETRIES:
                    break  # Try next model
            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "")
                if error_code in ("AccessDeniedException", "ValidationException",
                                  "ResourceNotFoundException"):
                    break  # Try next model
                elif "Throttl" in error_code and attempt < MAX_RETRIES:
                    await asyncio.sleep(backoff)
                    backoff *= 2
                else:
                    raise

    raise TimeoutError("All models exhausted")'''
add_code_block(code_fallback)

add_heading_styled('Code: Prompt Engineering with Historical Context', level=3)
doc.add_paragraph('The agent builds structured prompts that inject historical incident data:')

code_prompt = '''def _build_prompt(self, alert_name, severity, service_name,
                  target_resource, labels, history):
    """Build structured prompt with alert context and history."""
    # Count success/failure for historical context
    success_count = sum(1 for h in history if h.outcome == "success")
    failure_count = sum(1 for h in history if h.outcome == "failure")

    # Identify actions that always failed
    action_outcomes: dict[str, list[str]] = {}
    for h in history:
        if h.alert_name == alert_name:
            outcomes = action_outcomes.setdefault(h.remediation_action, [])
            outcomes.append(h.outcome)

    excluded_actions = [
        action for action, outcomes in action_outcomes.items()
        if outcomes and all(o == "failure" for o in outcomes)
    ]

    prompt = f"""You are an AI remediation agent. Analyze the alert
and produce a remediation plan.

ALERT CONTEXT:
- Alert Name: {alert_name}
- Severity: {severity}
- Service: {service_name}
- Target Resource: {target_resource}
- Labels: {json.dumps(labels)}

HISTORICAL CONTEXT ({included} incidents, {success_count} successes,
{failure_count} failures):
{history_text}

EXCLUDED ACTIONS (all past attempts failed): {excluded_actions}

Respond with JSON: {{"action": "...", "confidence": 0.0-1.0,
"reasoning": "...", "steps": [...]}}"""
    return prompt'''
add_code_block(code_prompt)

add_heading_styled('Prompt Engineering Techniques Applied', level=3)
techniques = [
    'Structured prompts with clear sections: ALERT CONTEXT, HISTORICAL CONTEXT, EXCLUDED ACTIONS',
    'Output schema enforcement (JSON format with defined fields)',
    'Historical context injection for few-shot-style learning from past incidents',
    'Token budget management with truncation by recency',
    'Temperature control (0.2) for deterministic, reproducible reasoning',
]
for t in techniques:
    doc.add_paragraph(t, style='List Bullet')

doc.add_page_break()

# ============================================================
# SECTION 4: SOLUTION / DELIVERABLES / WORK PRODUCTS
# ============================================================
add_heading_styled('4. Solution / Deliverables / Work Products', level=1)

add_heading_styled('AWS Architecture Delivered (6 CDK Stacks)', level=2)

# Table for architecture
table = doc.add_table(rows=7, cols=2)
table.style = 'Light Grid Accent 1'
hdr = table.rows[0].cells
hdr[0].text = 'Stack'
hdr[1].text = 'Resources'
data = [
    ('Network', 'VPC, 2 AZs, NAT Gateway, VPC Endpoints, Security Groups'),
    ('Data', 'DynamoDB (incident store), SQS + Dead Letter Queue, ECR Repository'),
    ('Compute', 'ECS Fargate, IAM Roles (least privilege), API Gateway, Cloud Map, Secrets Manager'),
    ('Observability', 'SNS, CloudWatch Alarms, Budget Alerts, CloudWatch Dashboard'),
    ('Monitoring', 'Amazon Managed Prometheus, ADOT Collector, Alertmanager'),
    ('Simulation', 'EC2 target instance, CloudWatch CPU/Network Alarms, Alert trigger Lambdas'),
]
for i, (stack, resources) in enumerate(data, 1):
    table.rows[i].cells[0].text = stack
    table.rows[i].cells[1].text = resources

doc.add_paragraph()

# --- Work Product 1: Self-Healing Pipeline ---
add_heading_styled('4.1 Self-Healing Pipeline (Orchestrator)', level=2)
doc.add_paragraph(
    'The orchestrator coordinates the full 5-stage pipeline: '
    'Normalize → Enrich → Match → Execute → Notify. It supports 50 concurrent '
    'pipeline executions via asyncio semaphore and integrates both the guardrail engine '
    'and concurrency manager between match and execute stages.'
)

code_orch = '''class Orchestrator:
    """Coordinates the full self-healing pipeline for alert processing.

    Processes alert payloads through sequential stages:
    1. Normalize - Extract and standardize alerts from the payload
    2. Enrich - Augment alerts with asset inventory context
    3. Match - Find a matching remediation playbook
    4. Execute - Run the matched playbook against the target host
    5. Notify - Dispatch notifications about the outcome

    Supports up to 50 concurrent pipeline executions via asyncio.Semaphore.
    """

    async def process_alert_payload(self, payload: AlertmanagerPayload) -> list[str]:
        # Stage 1: Normalize the payload into individual alerts
        normalized_alerts = self._normalizer.normalize(payload)

        # Process each alert concurrently with semaphore limiting
        tasks = [self._run_pipeline(alert) for alert in normalized_alerts]
        incident_ids = await asyncio.gather(*tasks, return_exceptions=False)
        return list(incident_ids)

    async def _run_pipeline(self, alert: NormalizedAlert) -> str:
        async with self._semaphore:
            # Stage 2: Enrich
            enriched_alert = self._enricher.enrich(alert)
            # Stage 3: Match
            playbook_match = self._mapper.match(enriched_alert)
            # Stage 3.5: Guardrail Engine Evaluation
            decision = await self._guardrail_engine.evaluate(guardrail_action)
            # Stage 4: Execute
            execution_result = await self._executor.execute(...)
            # Stage 5: Notify
            await self._dispatcher.notify_remediation(...)'''
add_code_block(code_orch)

# --- Work Product 2: 7-Layer Guardrail Safety Engine ---
add_heading_styled('4.2 Seven-Layer Guardrail Safety Engine', level=2)
doc.add_paragraph(
    'The guardrail engine evaluates every remediation action through 7 ordered checks '
    'with short-circuit semantics and a 15-second overall timeout:'
)

guardrails = [
    'Self-Protection — Prevents the agent from modifying its own infrastructure',
    'Maintenance Window — Defers actions during planned maintenance',
    'Circuit Breaker — Stops repeated failures from cascading',
    'Concurrency Guard — Prevents parallel remediation on the same host',
    'Blast Radius Classifier — Classifies risk as LOW/MEDIUM/HIGH/CRITICAL',
    'Health Checker — Validates target host health before execution',
    'Approval Gate — Human-in-the-loop email approval for HIGH/CRITICAL risk',
]
for i, g in enumerate(guardrails, 1):
    doc.add_paragraph(f'{i}. {g}')

code_guardrail = '''class GuardrailEngine:
    """Orchestrates all guardrail checks in a fixed evaluation order.
    Short-circuits on the first non-ALLOW result.
    15-second overall timeout results in DENY.
    """

    async def evaluate(self, action: RemediationAction) -> GuardrailDecision:
        start_time = time.time()
        checks_passed: list[str] = []

        try:
            result = await asyncio.wait_for(
                self._run_checks(action, checks_passed),
                timeout=EVALUATION_TIMEOUT_SECONDS,  # 15 seconds
            )
        except asyncio.TimeoutError:
            return GuardrailDecision(
                decision_type=GuardrailDecisionType.DENY,
                denying_check="guardrail_timeout",
                reason="Guardrail evaluation timed out after 15 seconds",
            )

        decision = self._build_decision(action, result, checks_passed, duration)
        if decision.decision_type != GuardrailDecisionType.ALLOW:
            await self._dispatch_notification(decision)
        return decision

    async def _run_checks(self, action, checks_passed):
        """Run all checks sequentially with short-circuit on non-ALLOW."""
        for check in self._checks:
            result = await self._run_check(check, action)
            if result.result_type != CheckResultType.ALLOW:
                return result
            checks_passed.append(check.name)
        return CheckResult(result_type=CheckResultType.ALLOW, ...)'''
add_code_block(code_guardrail)

# --- Work Product 3: Email-Based Human-in-the-Loop ---
add_heading_styled('4.3 Email-Based Human-in-the-Loop Approval', level=2)
doc.add_paragraph(
    'The system sends rich HTML emails via Amazon SES containing root cause analysis, '
    'severity-coded alerts, and one-click approval buttons. Token-based approval links '
    'expire after 30 minutes.'
)

add_heading_styled('Two Operating Modes', level=3)

# Mode table
mode_table = doc.add_table(rows=3, cols=4)
mode_table.style = 'Light Grid Accent 1'
mode_table.rows[0].cells[0].text = 'Mode'
mode_table.rows[0].cells[1].text = 'When'
mode_table.rows[0].cells[2].text = 'Email Content'
mode_table.rows[0].cells[3].text = 'Action'
mode_table.rows[1].cells[0].text = 'Rule Mode'
mode_table.rows[1].cells[1].text = 'Matching playbook exists'
mode_table.rows[1].cells[2].text = 'RCA + "Approve Auto-Remediation" button'
mode_table.rows[1].cells[3].text = 'Click → agent executes fix'
mode_table.rows[2].cells[0].text = 'AI Agent Mode'
mode_table.rows[2].cells[1].text = 'No playbook match'
mode_table.rows[2].cells[2].text = 'AI analysis + suggested remediation steps'
mode_table.rows[2].cells[3].text = 'Operator fixes manually using AI suggestions'

doc.add_paragraph()

# Screenshot placeholders for email modes
add_screenshot_placeholder('Rule Mode — Email received with "Approve Auto-Remediation" button (HighCPUUsage alert)')

add_screenshot_placeholder('AI Agent Mode — Email received with AI-generated analysis and suggested steps (NetworkLatency alert, no playbook match)')

code_email = '''class EmailNotifier:
    """Sends RCA emails with approval links via Amazon SES."""

    def send_approval_email(self, approval: PendingApproval) -> bool:
        """Send the RCA + approval link email."""
        approval_link = self._approval_handler.get_approval_link(approval)
        email_content = build_rca_email(approval, approval_link)

        self._ses.send_email(
            Source=self._from_address,
            Destination={"ToAddresses": [self._operator_email]},
            Message={
                "Subject": {"Data": email_content["subject"]},
                "Body": {
                    "Html": {"Data": email_content["html_body"]},
                    "Text": {"Data": email_content["text_body"]},
                },
            },
        )
        return True'''
add_code_block(code_email)

# --- Work Product 4: Blast Radius Classifier ---
add_heading_styled('4.4 Blast Radius Classifier', level=2)
doc.add_paragraph(
    'Classifies every remediation action by risk level using priority-ordered rules:'
)
classification_rules = [
    'Priority 1: Single-instance services → CRITICAL',
    'Priority 2: Database restart/stop → CRITICAL',
    'Priority 3: Rule match from YAML configuration',
    'Priority 4: Production environment elevation (one level up)',
    'Priority 5: Default to HIGH for unknown actions',
]
for c in classification_rules:
    doc.add_paragraph(c, style='List Bullet')

code_classifier = '''class BlastRadiusClassifier:
    """Classifies remediation actions by blast radius risk level."""

    def _classify(self, action: RemediationAction) -> RiskLevel:
        # Priority 1: Single-instance services → CRITICAL
        if action.service_name.lower() in self._single_instance_services:
            return RiskLevel.CRITICAL

        # Priority 2: Database restart/stop → CRITICAL
        if is_db and any(kw in action_lower for kw in ("restart", "stop")):
            return RiskLevel.CRITICAL

        # Priority 3: Rule match from config
        matched_risk = self._match_rules(action, rules)

        # Priority 4: Production environment elevation
        if action.environment.lower() == "prod":
            risk = risk.elevate()

        return risk'''
add_code_block(code_classifier)

doc.add_page_break()

# --- Work Product 5: Playbook Mapping ---
add_heading_styled('4.5 Playbook Mapping Configuration', level=2)
doc.add_paragraph(
    'Alert-to-playbook mapping is defined in YAML, enabling operators to add new rules '
    'without code changes:'
)

code_mapping = '''# config/playbook_mapping.yml
rules:
  - name: high-cpu-web
    conditions:
      alert_name: HighCPUUsage
      service_name: web-frontend
    playbook_path: playbooks/fix_high_cpu.yml

  - name: disk-full
    conditions:
      alert_name: DiskSpaceCritical
    playbook_path: playbooks/clear_disk.yml

  - name: service-down
    conditions:
      alert_name: ServiceDown
    playbook_path: playbooks/restart_process.yml

  - name: memory-pressure
    conditions:
      alert_name: HighMemoryUsage
    playbook_path: playbooks/restart_process.yml'''
add_code_block(code_mapping)

# --- Work Product 6: CI/CD ---
add_heading_styled('4.6 CI/CD Pipeline', level=2)
doc.add_paragraph(
    'A comprehensive GitHub Actions CI/CD pipeline ensures code quality and safe deployment:'
)
ci_stages = [
    'Lint (ruff) — Code style and format checking',
    'Unit Tests — 80% coverage gate with pytest',
    'Property-Based Tests — Hypothesis library for invariant testing',
    'CDK Synth — Validate all 6 infrastructure stacks synthesize correctly',
    'CDK Assertion Tests — Verify resource configurations in synthesized templates',
    'Docker Build — Build container image with BuildKit caching',
    'ECR Scan — Vulnerability scanning gate before push',
    'ECR Push — Push to registry with OIDC authentication (no long-lived secrets)',
]
for s in ci_stages:
    doc.add_paragraph(s, style='List Bullet')

# --- Work Product 7: Operational Runbooks ---
add_heading_styled('4.7 Operational Runbooks', level=2)
doc.add_paragraph('8 operational runbooks were delivered:')
runbooks = [
    'Incident Response — Step-by-step triage and escalation',
    'Disaster Recovery — Full stack recovery procedures',
    'DLQ Replay — Replaying failed messages from Dead Letter Queue',
    'Rollback — Safe rollback of service deployments',
    'Scale Out / Scale In — Capacity management procedures',
    'Bedrock Throttling — Handling AI model throttling events',
    'Parameter Updates — Safe SSM parameter rotation',
]
for r in runbooks:
    doc.add_paragraph(r, style='List Bullet')

doc.add_page_break()

# ============================================================
# SECTION 5: DELIVERY APPROACH
# ============================================================
add_heading_styled('5. Approach to Delivery Using IBM Tools, Techniques, and Methods', level=1)

add_heading_styled('IBM Consulting Advantage & Core Method Alignment', level=2)

doc.add_paragraph().add_run('Discovery & Framing:').bold = True
doc.add_paragraph(
    'Started with analysis of operational pain points (alert fatigue, slow MTTR, '
    'inconsistent remediation). Mapped the current-state process and identified '
    'AI intervention points.'
)

doc.add_paragraph().add_run('Architecture Decision Records:').bold = True
decisions = [
    'Email over Slack — Universal access, no dependency on third-party integrations',
    'Human-in-the-loop for HIGH/CRITICAL risk — No fully autonomous execution for dangerous actions',
    'SSM over SSH — No key management, works with private subnet instances',
    'CloudWatch-native alerting — Reduces operational complexity vs. external Prometheus',
]
for d in decisions:
    doc.add_paragraph(d, style='List Bullet')

doc.add_paragraph().add_run('Iterative Delivery (IBM Garage Methodology):').bold = True
sprints = [
    'Sprint 1: Core pipeline (normalize → enrich → match → execute)',
    'Sprint 2: AI reasoning agent with Bedrock integration',
    'Sprint 3: Guardrail safety engine (7 layers)',
    'Sprint 4: Concurrency management and observability',
    'Sprint 5: CI/CD, CDK infrastructure, deployment automation',
    'Sprint 6: Operational runbooks, demo scenarios, documentation',
]
for s in sprints:
    doc.add_paragraph(s, style='List Bullet')

doc.add_paragraph().add_run('Infrastructure as Code (IaC):').bold = True
doc.add_paragraph(
    'All infrastructure defined in AWS CDK Python, enabling reproducible deployments '
    'across environments with a single command: npx aws-cdk deploy --all.'
)

doc.add_paragraph().add_run('Observability-First Design:').bold = True
doc.add_paragraph(
    'Structured JSON logging, Prometheus metrics, CloudWatch dashboards, and audit '
    'trails built into every component from the start — not bolted on afterward.'
)

doc.add_paragraph().add_run('Twelve-Factor App Principles:').bold = True
doc.add_paragraph(
    'Configuration via environment variables, stateless compute (ECS Fargate), '
    'explicit dependency declaration, port binding, concurrency via process model, disposability.'
)

doc.add_page_break()

# ============================================================
# SECTION 6: RISKS & TRUSTWORTHY AI
# ============================================================
add_heading_styled('6. Risks, Ethical Concerns, and Trustworthy AI', level=1)

add_heading_styled('Identified Risks and Mitigations', level=2)

risk_table = doc.add_table(rows=8, cols=2)
risk_table.style = 'Light Grid Accent 1'
risk_table.rows[0].cells[0].text = 'Risk'
risk_table.rows[0].cells[1].text = 'Mitigation'
risks = [
    ('AI hallucination / incorrect remediation',
     'Confidence scoring with escalation below threshold (70%/80% for P1). '
     'Human approval required for HIGH/CRITICAL blast radius.'),
    ('Blast radius of automated actions',
     '7-layer guardrail engine classifies every action. Single-instance services '
     'and database restarts auto-classified as CRITICAL. Production environment elevation rule.'),
    ('Runaway automation (cascading failures)',
     'Circuit breaker pattern halts execution after consecutive failures. '
     'Concurrency guard prevents parallel actions on same host.'),
    ('Data accuracy (stale asset inventory)',
     'Asset enrichment uses live metadata. Historical context is bounded '
     '(max 50 incidents) and time-decayed.'),
    ('Model bias toward certain remediation patterns',
     'Historical action exclusion: actions that always failed in the past are '
     'explicitly excluded from AI consideration.'),
    ('Availability of AI service',
     '4-model fallback chain (Claude Sonnet → Nova Pro → Claude Haiku → Nova Lite). '
     'If all fail, graceful degradation to rule-based matching.'),
    ('Unauthorized execution',
     'Token-based approval with 30-minute expiry. No auto-execution without '
     'operator click for HIGH/CRITICAL.'),
]
for i, (risk, mitigation) in enumerate(risks, 1):
    risk_table.rows[i].cells[0].text = risk
    risk_table.rows[i].cells[1].text = mitigation

doc.add_paragraph()

add_heading_styled('IBM Trustworthy AI Principles Applied', level=2)

principles = [
    ('Transparency', 'Full audit logging of every decision — which model was used, '
     'confidence score, reasoning explanation, which guardrails passed/failed, and '
     'execution outcome. Operators see the complete chain of reasoning in their approval email.'),
    ('Explainability', 'The AI agent produces structured reasoning_explanation fields '
     '(up to 2048 characters) explaining why it chose a particular remediation. '
     'This is included in the operator\'s approval email for informed decision-making.'),
    ('Fairness', 'The system does not make decisions based on operator identity or '
     'team membership. All incidents are processed through the same pipeline with '
     'consistent rules regardless of origination.'),
    ('Robustness', 'The 7-layer guardrail engine, circuit breaker pattern, and '
     'multi-model fallback chain ensure the system degrades gracefully rather than '
     'failing catastrophically. A 15-second evaluation timeout ensures guardrails '
     'never block the pipeline indefinitely.'),
    ('Privacy', 'No customer PII is processed. Alert labels and asset metadata contain '
     'only infrastructure identifiers (hostnames, service names, IP addresses). '
     'Audit logs are stored in DynamoDB with encryption at rest.'),
    ('Governance', 'Human-in-the-loop approval for all HIGH and CRITICAL risk actions. '
     'Protected hosts configuration prevents automation from ever targeting critical '
     'infrastructure. Maintenance window awareness defers actions during planned change windows.'),
    ('Safety', 'Self-protection check ensures the agent cannot modify its own running '
     'infrastructure. The system is designed so that failure (AI unavailable, approval '
     'expired, guardrail denied) always results in "do nothing" rather than '
     '"do something potentially harmful."'),
]

for name, description in principles:
    p = doc.add_paragraph()
    p.add_run(f'{name}: ').bold = True
    p.add_run(description)

doc.add_page_break()

# ============================================================
# SECTION 7: EVIDENCE — SCREENSHOTS
# ============================================================
add_heading_styled('7. Evidence — Demo Screenshots', level=1)

doc.add_paragraph(
    'The following screenshots demonstrate the system in action across both operating modes:'
)

add_heading_styled('Rule Mode Demo (Playbook Found → Email → Approve → Auto-Remediate)', level=2)
doc.add_paragraph(
    'In Rule Mode, the system matches an alert to an existing Ansible playbook. '
    'The operator receives an email with full root cause analysis and a one-click '
    '"Approve Auto-Remediation" button. Clicking the button triggers the agent to '
    'execute the matched playbook on the target host.'
)

add_screenshot_placeholder('Rule Mode — CloudWatch Alarm triggered for HighCPUUsage')

add_screenshot_placeholder('Rule Mode — Email received with RCA and "Approve Auto-Remediation" button')

add_screenshot_placeholder('Rule Mode — After clicking Approve: remediation executed successfully')

add_heading_styled('AI Agent Mode Demo (No Playbook → AI Analysis → Suggested Steps)', level=2)
doc.add_paragraph(
    'In AI Agent Mode, no matching playbook exists for the alert. The AI Reasoning Agent '
    '(Amazon Bedrock) analyzes the alert with historical context and generates a '
    'remediation plan with confidence scoring. The operator receives an email with '
    'AI-generated analysis and suggested remediation steps for manual execution.'
)

add_screenshot_placeholder('AI Agent Mode — Alert triggered with no matching playbook (e.g., NetworkLatencyHigh)')

add_screenshot_placeholder('AI Agent Mode — Email received with AI-generated root cause analysis and suggested steps')

add_screenshot_placeholder('AI Agent Mode — Bedrock model invocation logs showing reasoning output')

add_heading_styled('CloudWatch Dashboard & Observability', level=2)

add_screenshot_placeholder('CloudWatch Dashboard — AIOps metrics (remediation success rate, AI latency, queue depth)')

add_screenshot_placeholder('ECS Fargate service running in AWS Console')

doc.add_page_break()

# ============================================================
# SUMMARY
# ============================================================
add_heading_styled('Summary', level=1)

doc.add_paragraph(
    'This project demonstrates end-to-end delivery of a generative and agentic AI solution '
    'for SRE/DevOps operations. It combines Amazon Bedrock\'s large language models with a '
    'production-grade safety framework, infrastructure-as-code deployment, CI/CD automation, '
    'and comprehensive observability — all following IBM Consulting\'s delivery methods and '
    'Trustworthy AI principles.'
)

doc.add_paragraph(
    'The result is a platform that transforms reactive incident response into proactive, '
    'AI-assisted self-healing while maintaining human oversight for high-risk actions.'
)

doc.add_paragraph()
doc.add_paragraph()
p_final = doc.add_paragraph()
p_final.add_run('Submitted by: ').bold = True
p_final.add_run('Ravindra Yadav')
doc.add_paragraph()
p_role = doc.add_paragraph()
p_role.add_run('Role: ').bold = True
p_role.add_run('SRE/DevOps Engineer')
doc.add_paragraph()
p_date = doc.add_paragraph()
p_date.add_run('Date: ').bold = True
p_date.add_run('August 2026')

# ============================================================
# SAVE
# ============================================================
output_path = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    'Written_Application_GenAI_SRE_DevOps_Intermediate.docx'
)
doc.save(output_path)
print(f"Document saved to: {output_path}")
