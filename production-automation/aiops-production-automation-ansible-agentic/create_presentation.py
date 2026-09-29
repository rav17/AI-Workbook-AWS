"""Generate a detailed PPTX presentation for the AIOps Self-Healing Infrastructure solution."""

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

prs = Presentation()
prs.slide_width = Inches(13.33)
prs.slide_height = Inches(7.5)

# Color palette
DARK_BG = RGBColor(0x1A, 0x1A, 0x2E)
ACCENT_BLUE = RGBColor(0x00, 0x96, 0xD6)
ACCENT_ORANGE = RGBColor(0xFF, 0x99, 0x00)
ACCENT_GREEN = RGBColor(0x2E, 0xCC, 0x71)
ACCENT_RED = RGBColor(0xE7, 0x4C, 0x3C)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
LIGHT_GRAY = RGBColor(0xF0, 0xF0, 0xF5)
DARK_TEXT = RGBColor(0x2C, 0x3E, 0x50)
SUBTLE_GRAY = RGBColor(0x7F, 0x8C, 0x8D)


def add_dark_bg(slide):
    """Add a dark background to a slide."""
    bg = slide.background
    fill = bg.fill
    fill.solid()
    fill.fore_color.rgb = DARK_BG


def add_light_bg(slide):
    """Add a light background to a slide."""
    bg = slide.background
    fill = bg.fill
    fill.solid()
    fill.fore_color.rgb = LIGHT_GRAY


def add_title_slide(title, subtitle):
    """Create a title slide with dark background."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])  # Blank
    add_dark_bg(slide)

    # Title
    txBox = slide.shapes.add_textbox(Inches(1), Inches(2.2), Inches(11), Inches(1.5))
    tf = txBox.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = title
    p.font.size = Pt(40)
    p.font.bold = True
    p.font.color.rgb = WHITE
    p.alignment = PP_ALIGN.CENTER

    # Subtitle
    txBox2 = slide.shapes.add_textbox(Inches(2), Inches(4.0), Inches(9), Inches(1.2))
    tf2 = txBox2.text_frame
    tf2.word_wrap = True
    p2 = tf2.paragraphs[0]
    p2.text = subtitle
    p2.font.size = Pt(20)
    p2.font.color.rgb = ACCENT_BLUE
    p2.alignment = PP_ALIGN.CENTER

    return slide


def add_section_slide(title):
    """Create a section divider slide."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_dark_bg(slide)

    txBox = slide.shapes.add_textbox(Inches(1), Inches(3.0), Inches(11), Inches(1.5))
    tf = txBox.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = title
    p.font.size = Pt(36)
    p.font.bold = True
    p.font.color.rgb = ACCENT_ORANGE
    p.alignment = PP_ALIGN.CENTER

    return slide


def add_content_slide(title, bullets, notes=""):
    """Create a content slide with title and bullet points."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_light_bg(slide)

    # Title bar
    shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), Inches(13.33), Inches(1.1))
    shape.fill.solid()
    shape.fill.fore_color.rgb = DARK_BG
    shape.line.fill.background()

    txBox = slide.shapes.add_textbox(Inches(0.5), Inches(0.15), Inches(12), Inches(0.9))
    tf = txBox.text_frame
    p = tf.paragraphs[0]
    p.text = title
    p.font.size = Pt(26)
    p.font.bold = True
    p.font.color.rgb = WHITE

    # Bullets
    txBox2 = slide.shapes.add_textbox(Inches(0.8), Inches(1.4), Inches(11.5), Inches(5.8))
    tf2 = txBox2.text_frame
    tf2.word_wrap = True

    for i, bullet in enumerate(bullets):
        if i == 0:
            p = tf2.paragraphs[0]
        else:
            p = tf2.add_paragraph()

        # Support sub-bullets with "  - " prefix
        if bullet.startswith("  - "):
            p.text = bullet.strip("  - ")
            p.font.size = Pt(16)
            p.font.color.rgb = SUBTLE_GRAY
            p.level = 1
            p.space_before = Pt(4)
        else:
            p.text = bullet
            p.font.size = Pt(18)
            p.font.color.rgb = DARK_TEXT
            p.level = 0
            p.space_before = Pt(10)

    if notes:
        slide.notes_slide.notes_text_frame.text = notes

    return slide


def add_two_column_slide(title, left_title, left_bullets, right_title, right_bullets):
    """Create a two-column content slide."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_light_bg(slide)

    # Title bar
    shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), Inches(13.33), Inches(1.1))
    shape.fill.solid()
    shape.fill.fore_color.rgb = DARK_BG
    shape.line.fill.background()

    txBox = slide.shapes.add_textbox(Inches(0.5), Inches(0.15), Inches(12), Inches(0.9))
    tf = txBox.text_frame
    p = tf.paragraphs[0]
    p.text = title
    p.font.size = Pt(26)
    p.font.bold = True
    p.font.color.rgb = WHITE

    # Left column title
    ltBox = slide.shapes.add_textbox(Inches(0.5), Inches(1.3), Inches(5.8), Inches(0.5))
    ltf = ltBox.text_frame
    lp = ltf.paragraphs[0]
    lp.text = left_title
    lp.font.size = Pt(20)
    lp.font.bold = True
    lp.font.color.rgb = ACCENT_BLUE

    # Left bullets
    lbBox = slide.shapes.add_textbox(Inches(0.7), Inches(1.9), Inches(5.6), Inches(5.0))
    lbf = lbBox.text_frame
    lbf.word_wrap = True
    for i, b in enumerate(left_bullets):
        p = lbf.paragraphs[0] if i == 0 else lbf.add_paragraph()
        p.text = b
        p.font.size = Pt(16)
        p.font.color.rgb = DARK_TEXT
        p.space_before = Pt(8)

    # Right column title
    rtBox = slide.shapes.add_textbox(Inches(6.8), Inches(1.3), Inches(5.8), Inches(0.5))
    rtf = rtBox.text_frame
    rp = rtf.paragraphs[0]
    rp.text = right_title
    rp.font.size = Pt(20)
    rp.font.bold = True
    rp.font.color.rgb = ACCENT_ORANGE

    # Right bullets
    rbBox = slide.shapes.add_textbox(Inches(7.0), Inches(1.9), Inches(5.6), Inches(5.0))
    rbf = rbBox.text_frame
    rbf.word_wrap = True
    for i, b in enumerate(right_bullets):
        p = rbf.paragraphs[0] if i == 0 else rbf.add_paragraph()
        p.text = b
        p.font.size = Pt(16)
        p.font.color.rgb = DARK_TEXT
        p.space_before = Pt(8)

    return slide


# ============================================================
# SLIDE 1: Title Slide
# ============================================================
add_title_slide(
    "AIOps Self-Healing Infrastructure",
    "Automated Incident Detection, AI-Powered Reasoning & Remediation\n"
    "Built on AWS with Amazon Bedrock, ECS Fargate & Ansible"
)

# ============================================================
# SLIDE 2: Problem Statement
# ============================================================
add_content_slide(
    "The Problem: Manual Incident Response is Broken",
    [
        "Mean Time to Resolve (MTTR) for production incidents: 30-90 minutes",
        "On-call engineers face alert fatigue — 60%+ of alerts are repetitive",
        "Manual runbook execution is error-prone under pressure",
        "Night/weekend incidents wait hours for human response",
        "Alert storms during outages create cascading confusion",
        "No organizational learning — same issues fixed the same way repeatedly",
    ]
)

# ============================================================
# SLIDE 3: Solution Overview
# ============================================================
add_content_slide(
    "Our Solution: AI-Powered Self-Healing Platform",
    [
        "Fully automated pipeline: Alert → AI Analysis → Remediation → Verification",
        "Two operating modes for safety and coverage:",
        "  - Rule Mode: Known alerts matched to pre-vetted Ansible playbooks",
        "  - AI Agent Mode: Unknown alerts analyzed by Amazon Bedrock (Nova/Claude)",
        "Human-in-the-loop approval via email for high-risk actions",
        "7-layer guardrail engine prevents dangerous automated actions",
        "Learns from every incident — improves over time via feedback loop",
        "Cost-optimized AI routing: 60-90% savings vs. always using premium models",
    ]
)


# ============================================================
# SLIDE 4: Architecture Overview (High-Level Flow)
# ============================================================
add_content_slide(
    "End-to-End Architecture Flow",
    [
        "1. EC2 Instance → CloudWatch detects anomaly (CPU, Disk, Network)",
        "2. CloudWatch Alarm → SNS → Lambda → POST /webhook to ECS Service",
        "3. ECS Fargate Service receives alert (FastAPI + Storm Detection)",
        "4. Pipeline: Normalize → Enrich → Match Playbook → Guardrails → Execute",
        "5. Rule Mode: Email with 'Approve' button → Operator clicks → Ansible runs",
        "6. AI Mode: Bedrock analyzes → Email with suggested steps → Advisory only",
        "7. Post-Execution: Baking validation confirms fix effectiveness",
        "8. Feedback Loop: Outcome stored in DynamoDB → Improves future routing",
    ]
)

# ============================================================
# SLIDE 5: Section - AWS Infrastructure
# ============================================================
add_section_slide("AWS Infrastructure (CDK)")

# ============================================================
# SLIDE 6: CDK Stack Architecture
# ============================================================
add_content_slide(
    "Infrastructure as Code — 6 CDK Stacks",
    [
        "Aiops-{env}-Network: VPC, 2 AZs, NAT Gateways, VPC Endpoints, Security Groups",
        "  - VPC Endpoints: DynamoDB, S3, SQS, SSM, Logs, Secrets Manager, Bedrock",
        "Aiops-{env}-Data: DynamoDB (incident memory), SQS + DLQ, ECR Repository",
        "  - DynamoDB: PAY_PER_REQUEST, TTL, PITR (prod), 4 GSIs",
        "Aiops-{env}-Compute: ECS Fargate, IAM Roles, API Gateway, Secrets, SSM Params",
        "  - Auto-scaling: CPU/SQS-based, 1-4 tasks (prod: 2-8)",
        "Aiops-{env}-Observability: SNS Topics, CloudWatch Alarms, Budget Alerts",
        "Aiops-{env}-Monitoring: Prometheus + Grafana on ECS (optional)",
        "Aiops-{env}-Simulation: EC2 target instance, stress-ng triggers, Lambda alerts",
    ]
)


# ============================================================
# SLIDE 7: Network & Security Architecture
# ============================================================
add_two_column_slide(
    "Network & Security Architecture",
    "Network Design",
    [
        "• VPC with 2 AZs (public + private subnets)",
        "• Prod: 2 NAT Gateways (HA)",
        "• Dev/Staging: 1 NAT Gateway (cost savings)",
        "• ECS tasks in private subnets only",
        "• VPC Gateway Endpoints: DynamoDB, S3 (free)",
        "• VPC Interface Endpoints: SQS, SSM,",
        "  Logs, Secrets Manager, Bedrock Runtime",
        "• All AWS API traffic stays within VPC",
    ],
    "Security Controls",
    [
        "• IAM Least Privilege — resource-scoped ARNs",
        "• WAF on API Gateway (rate limit 100/5min/IP)",
        "• Secrets Manager with 90-day auto-rotation",
        "• No hardcoded credentials anywhere",
        "• Security Groups: least-privilege ingress/egress",
        "• Payload validation (Pydantic, 1MB limit)",
        "• HMAC-signed approval tokens",
        "• DynamoDB encryption (AWS-managed keys)",
    ],
)

# ============================================================
# SLIDE 8: Section - AI/LLM Architecture
# ============================================================
add_section_slide("AI / LLM Architecture (Amazon Bedrock)")

# ============================================================
# SLIDE 9: Intelligent Model Routing
# ============================================================
add_content_slide(
    "Intelligent Model Router — Cost-Optimized AI",
    [
        "Problem: Using Claude Sonnet for ALL alerts is expensive ($0.003/call)",
        "Solution: Classify alert complexity → route to cheapest capable model",
        "",
        "SIMPLE (70% of alerts): Amazon Nova Lite — ~$0.0003/invocation",
        "  - Seen 5+ times, >90% historical success rate, single host, P3-P5",
        "MODERATE (20%): Amazon Nova Pro — ~$0.001/invocation",
        "  - Limited history, mixed outcomes, 2-3 correlated alerts, P2",
        "COMPLEX (10%): Claude Sonnet — ~$0.003/invocation",
        "  - Never seen before, P1 severity, all past attempts failed, 4+ correlated",
        "",
        "Auto-Escalation: If confidence < 0.5, automatically upgrades to next tier",
        "Result: 60-90% cost reduction compared to always using premium models",
    ]
)


# ============================================================
# SLIDE 10: AI Reasoning Agent
# ============================================================
add_content_slide(
    "AI Reasoning Agent — How It Thinks",
    [
        "1. Retrieves historical incidents from DynamoDB (same alert/service)",
        "2. Builds structured prompt with cacheable prefix + variable suffix:",
        "  - System role: \"You are an SRE expert analyzing production alerts\"",
        "  - Context: alert details, service topology, past outcomes",
        "  - Excluded actions: commands from denied_commands.yml",
        "3. Invokes Bedrock model (30s timeout, 2 retries, exponential backoff)",
        "4. Parses JSON response → RemediationPlan (steps, confidence, reasoning)",
        "5. Confidence gating: P1 requires ≥0.8, general requires ≥0.7",
        "6. Fallback chain on failure: Claude Sonnet → Nova Pro → Haiku → Nova Lite",
        "7. Ultimate fallback: Rule-based PlaybookMapper (no AI needed)",
        "8. Bedrock Guardrails (optional): native content filtering for defense-in-depth",
    ]
)

# ============================================================
# SLIDE 11: Section - Pipeline & Event-Driven Design
# ============================================================
add_section_slide("Pipeline & Event-Driven Architecture")

# ============================================================
# SLIDE 12: Pipeline Stages
# ============================================================
add_content_slide(
    "Self-Healing Pipeline — 8 Stages",
    [
        "Stage 1 — NORMALIZE: Parse Alertmanager webhook → standardized format",
        "Stage 2 — ENRICH: Asset inventory lookup (hostname, service, owner, location)",
        "Stage 3 — MATCH: Playbook mapping rules (YAML-driven, first-match wins)",
        "Stage 4 — GUARDRAILS: 7-layer safety evaluation (short-circuit on DENY)",
        "Stage 5 — APPROVAL: Email with RCA + approve button (high-risk actions)",
        "Stage 6 — EXECUTE: Ansible playbook via asyncio subprocess (10 concurrent max)",
        "Stage 7 — BAKING: Post-execution monitoring (alarm resolution + host health)",
        "Stage 8 — NOTIFY: Outcome notification + audit log + DynamoDB record",
        "",
        "Concurrency: Up to 50 simultaneous pipelines via asyncio.Semaphore",
        "Each alert gets a unique UUID incident_id for end-to-end tracing",
    ]
)


# ============================================================
# SLIDE 13: Storm Detection & Backpressure
# ============================================================
add_content_slide(
    "Alert Storm Detection & Backpressure",
    [
        "Problem: Infrastructure-wide outages trigger hundreds of alerts simultaneously",
        "",
        "Storm Detector (sliding window algorithm):",
        "  - Tracks alert rate in configurable window (default: 50/minute threshold)",
        "  - Groups alerts by (alert_name + service) during storm mode",
        "  - Processes only ONE representative per group (reduces noise 10-50x)",
        "  - HTTP 429 when internal queue exceeds capacity (Alertmanager retries)",
        "  - Auto-exits storm mode after 2 minutes below threshold",
        "",
        "Alert Inhibition (root-cause suppression):",
        "  - DatabaseDown active → suppress APITimeout, ConnectionRefused, HealthCheckFailed",
        "  - NetworkPartition → suppress ServiceUnreachable, DNSResolutionFailed",
        "  - DiskFull → suppress LogRotationFailed, DatabaseWriteError",
        "  - Prevents redundant remediations for symptom alerts",
    ]
)

# ============================================================
# SLIDE 14: Section - Safety & Guardrails
# ============================================================
add_section_slide("Safety & Guardrail Engine")

# ============================================================
# SLIDE 15: 7-Layer Guardrail Engine
# ============================================================
add_content_slide(
    "7-Layer Guardrail Engine (Short-Circuit Evaluation)",
    [
        "1. Self-Protection: Never target automation controllers, monitoring infra, vaults",
        "2. Maintenance Window: Defer actions during scheduled windows (recurring/one-time)",
        "3. Circuit Breaker: CLOSED → OPEN → HALF_OPEN state machine per host",
        "4. Concurrency Guard: Bulkhead isolation — max concurrent per service group",
        "5. Blast Radius Classifier: Risk scoring (low/medium/high/critical) per action",
        "6. Health Checker: Checks downstream dependencies before risky operations",
        "7. Approval Gate: Requires human click for high/critical risk actions",
        "8. Plan Validator: Blocks dangerous AI-generated commands (regex denylist)",
        "",
        "15-second overall timeout → auto-DENY if evaluation takes too long",
        "Any check returning DENY or DEFER short-circuits remaining checks",
        "All decisions logged with full audit trail in DynamoDB",
    ]
)


# ============================================================
# SLIDE 16: Plan Validator (AI Safety)
# ============================================================
add_content_slide(
    "AI Plan Validator — Denied Commands & Safety Bounds",
    [
        "Blocks dangerous patterns in AI-generated remediation plans:",
        "  - rm -rf /  (recursive root delete)",
        "  - shutdown, halt, poweroff (host shutdown)",
        "  - dd if= (raw disk writes)",
        "  - iptables -F (firewall flush)",
        "  - curl | sh (piped remote scripts)",
        "  - chmod 777 (world-writable permissions)",
        "",
        "Parameter bounds enforced:",
        "  - Max timeout: 600 seconds per action",
        "  - Max target hosts: 5 per plan",
        "  - Max plan steps: 10",
        "  - Max AI executions per host: 3/hour",
        "",
        "Allowed filesystem paths: /var/log/, /tmp/, /opt/app/, /var/cache/",
    ]
)

# ============================================================
# SLIDE 17: Fleet Circuit Breaker
# ============================================================
add_content_slide(
    "Fleet-Wide Circuit Breaker — Prevents Cascading Damage",
    [
        "Problem: Bad playbook deployed to all hosts → every execution fails",
        "",
        "Fleet Breaker (global across all hosts):",
        "  - Tracks failures in sliding window (default: 5 failures in 5 minutes)",
        "  - CLOSED → OPEN: All automation paused fleet-wide",
        "  - 10-minute cooldown before recovery attempt",
        "  - Adaptive ramp-up: allows 1 → 2 → 4 → 8 → max concurrent",
        "  - Each ramp level requires success before advancing",
        "  - Prevents thundering herd after recovery",
        "",
        "Per-Host Circuit Breaker (separate per target):",
        "  - Tracks failures per individual host",
        "  - CLOSED → OPEN → HALF_OPEN → CLOSED state machine",
        "  - Prevents repeated failed attempts on a broken host",
    ]
)


# ============================================================
# SLIDE 18: Section - Configuration-Driven Design
# ============================================================
add_section_slide("Configuration-Driven Design (12 YAML Files)")

# ============================================================
# SLIDE 19: Configuration Files Overview
# ============================================================
add_two_column_slide(
    "12 YAML Config Files — Declarative Safety & Routing",
    "Routing & Mapping",
    [
        "• playbook_mapping.yml",
        "  Alert → Ansible playbook rules",
        "• asset_inventory.yml",
        "  Host/IP/service registry",
        "• service_dependencies.yml",
        "  Dependency graph + availability thresholds",
        "• execution_dependencies.yaml",
        "  DAG ordering between actions",
        "• risk_classification.yml",
        "  Blast radius scoring per (service, action)",
        "• resource_conflicts.yaml",
        "  Conflict resolution: QUEUE / REJECT / PREEMPT",
    ],
    "Safety & Protection",
    [
        "• denied_commands.yml",
        "  AI plan safety blocklist",
        "• protected_hosts.yml",
        "  Untouchable hosts (automation infra)",
        "• inhibition_rules.yml",
        "  Root-cause → symptom suppression",
        "• maintenance_windows.yml",
        "  Scheduled deferral windows",
        "• bulkhead_limits.yml",
        "  Per-service concurrency caps",
        "• stop_conditions.yml",
        "  CloudWatch alarms monitored during execution",
    ],
)

# ============================================================
# SLIDE 20: Section - Human-in-the-Loop
# ============================================================
add_section_slide("Human-in-the-Loop Approval Workflow")


# ============================================================
# SLIDE 21: Approval Workflow
# ============================================================
add_content_slide(
    "Email-Based Approval Workflow",
    [
        "Flow: Alert → Pipeline → Match → Generate Approval Token → Send Email",
        "",
        "Email contains:",
        "  - Root Cause Analysis (AI-generated or rule-based)",
        "  - Alert details (name, severity, host, timestamp)",
        "  - Proposed remediation steps",
        "  - 'Approve Auto-Remediation' button (time-limited link)",
        "",
        "Security measures:",
        "  - HMAC-signed tokens (Secrets Manager-backed signing key)",
        "  - 30-minute expiry (configurable)",
        "  - DynamoDB-backed storage (survives ECS task restarts)",
        "  - Exactly-once consumption (DynamoDB conditional writes)",
        "  - Two-step: GET shows confirmation page → POST executes",
        "  - Prevents email link-scanner auto-approval",
    ]
)

# ============================================================
# SLIDE 22: Section - Execution & Remediation
# ============================================================
add_section_slide("Execution & Remediation Layer")

# ============================================================
# SLIDE 23: Ansible Execution
# ============================================================
add_content_slide(
    "Ansible Playbook Execution",
    [
        "Executor capabilities:",
        "  - asyncio subprocess with configurable timeout (default 300s)",
        "  - SIGTERM → 5s grace period → SIGKILL escalation",
        "  - Concurrency: 10 simultaneous executions (Semaphore-limited)",
        "  - Output captured + truncated to 10,000 chars (stdout/stderr)",
        "",
        "Available playbooks:",
        "  - fix_high_cpu.yml — Kills stress-ng / runaway processes",
        "  - restart_service.yml — Systemd service restart with health check",
        "  - clear_disk.yml — Remove old logs + temp files",
        "  - restart_process.yml — Process-level restart",
        "",
        "Execution via SSM RunCommand (no SSH keys needed):",
        "  - EC2 instances tagged 'managed-by: aiops'",
        "  - SSM documents: AWS-RunShellScript, AWS-RunAnsiblePlaybook",
    ]
)


# ============================================================
# SLIDE 24: Stop Conditions & Baking Period
# ============================================================
add_content_slide(
    "Runtime Safety: Stop Conditions & Baking Validation",
    [
        "Stop Conditions (monitored DURING execution):",
        "  - CloudWatch alarms polled every 10 seconds",
        "  - If any alarm fires → immediate abort of remediation",
        "  - Examples: HealthyHostCount < 1, 5xx spike > 100/min, DB connections > 95%",
        "  - Global: MultiServiceDegradation > 3 services → halt all automation",
        "  - 15-second grace period before monitoring starts",
        "",
        "Baking Validation (AFTER execution):",
        "  - Monitors alarm resolution after remediation completes",
        "  - Checks host health (can target come back healthy?)",
        "  - If alarm doesn't resolve → marks outcome as INEFFECTIVE",
        "  - Feeds back into effectiveness scorer for future routing",
        "  - Inspired by AWS CodeDeploy bake time / SageMaker Deployment Guardrails",
    ]
)

# ============================================================
# SLIDE 25: Section - Observability
# ============================================================
add_section_slide("Observability & Operations")

# ============================================================
# SLIDE 26: Observability Stack
# ============================================================
add_content_slide(
    "Observability: Logging, Metrics, Tracing, Alarms",
    [
        "Structured JSON Logging (CloudWatch via awslogs driver):",
        "  - Retention: 30d (dev) / 90d (staging) / 365d (prod)",
        "  - Always includes: timestamp, level, logger, incident_id",
        "",
        "Custom Metrics (CloudWatch Namespace: AIOps/{environment}):",
        "  - alerts_received, remediation_success/failure/timeout",
        "  - AI reasoning latency, storm suppression count",
        "",
        "CloudWatch Alarms (staging/prod):",
        "  - DLQ depth > 5, AI latency p95 > 15s, failure rate > 30%",
        "  - Composite: RollbackRequired (ECS unhealthy AND DLQ depth)",
        "",
        "Distributed Tracing (OpenTelemetry → X-Ray):",
        "  - Each pipeline stage emits a span with incident_id",
        "  - Bedrock calls emit GenAI semantic convention spans",
    ]
)


# ============================================================
# SLIDE 27: Section - CI/CD
# ============================================================
add_section_slide("CI/CD Pipeline & Deployment")

# ============================================================
# SLIDE 28: CI/CD Pipeline
# ============================================================
add_two_column_slide(
    "CI/CD Pipeline — GitHub Actions",
    "CI (on push/PR)",
    [
        "1. Lint: ruff check + ruff format",
        "2. Unit tests (coverage >= 80%)",
        "3. Property-based tests (Hypothesis)",
        "4. CDK synth (validate templates)",
        "5. CDK assertion tests",
        "6. Docker build + ECR push",
        "7. Vulnerability scan",
        "",
        "Branch Strategy:",
        "  main → dev",
        "  staging → staging",
        "  v*.*.* tags → prod",
    ],
    "CD (on CI success)",
    [
        "1. Resolve image tag + environment",
        "2. Production approval gate (4h timeout)",
        "3. Deploy stacks in order:",
        "   Network → Data → Compute",
        "   → Health Gate → Observability",
        "4. Health gate: 3 consecutive healthy",
        "   responses within 5 minutes",
        "5. Rollback: automatic on health failure",
        "   (previous manifest from SSM)",
        "6. Store manifest in SSM (5-slot window)",
        "",
        "Safety: CDK diff uploaded as artifact",
    ],
)

# ============================================================
# SLIDE 29: Section - Cost Optimization
# ============================================================
add_section_slide("Cost Optimization")


# ============================================================
# SLIDE 30: Cost Optimization
# ============================================================
add_content_slide(
    "Cost Optimization Strategies",
    [
        "AI Model Routing (biggest savings):",
        "  - 70% of alerts use Nova Lite ($0.0003) instead of Claude ($0.003)",
        "  - 60-90% reduction in Bedrock costs",
        "",
        "Infrastructure cost controls:",
        "  - Dev: 1 NAT Gateway, 1 ECS task, short log retention",
        "  - VPC Gateway Endpoints (DynamoDB, S3) = free, avoids NAT data charges",
        "  - DynamoDB PAY_PER_REQUEST (no over-provisioning)",
        "  - ECR lifecycle rules (keep last 20 images, remove untagged after 7d)",
        "  - ECS auto-scaling: scale to zero in dev, min 2 in prod",
        "",
        "Operational cost controls:",
        "  - Storm detection prevents wasteful parallel remediations",
        "  - Alert inhibition avoids fixing symptoms (only root cause)",
        "  - Bulkhead limits prevent runaway automation costs",
    ]
)

# ============================================================
# SLIDE 31: Section - Resilience Patterns
# ============================================================
add_section_slide("Resilience & Fault Tolerance")

# ============================================================
# SLIDE 32: Resilience Patterns
# ============================================================
add_content_slide(
    "Resilience Patterns Implemented",
    [
        "Retry + Fallback: Bedrock calls → 2 retries, exponential backoff, model chain",
        "Circuit Breaker: Per-host (prevents repeated failures) + Fleet-wide (global halt)",
        "Bulkhead Isolation: Per-service concurrency limits prevent monopolization",
        "Backpressure: Storm detector + HTTP 429 + SQS visibility timeout",
        "Graceful Degradation: If Bedrock fails → fall back to rule-based mapping",
        "Idempotency: Alert fingerprint dedup in DynamoDB (TTL-based expiry)",
        "Host Locks: DynamoDB conditional PutItem prevents conflicting remediations",
        "Graceful Shutdown: SIGTERM → drain 25s → release locks → exit cleanly",
        "DLQ: Failed messages retry 3x then move to dead-letter queue",
        "Stop Conditions: Abort mid-execution if target system degrades",
        "Adaptive Ramp-up: After circuit breaker reset, slowly increase load",
    ]
)


# ============================================================
# SLIDE 33: Section - Demo
# ============================================================
add_section_slide("Demo Scenario")

# ============================================================
# SLIDE 34: Demo Flow
# ============================================================
add_content_slide(
    "Demo: High CPU Alert → Auto-Remediation",
    [
        "1. Trigger: Run stress-ng on EC2 target instance (CPU > 80%)",
        "2. Detection: CloudWatch Alarm triggers within 1 minute",
        "3. Webhook: SNS → Lambda → POST /webhook to ECS service",
        "4. Pipeline: Normalize → Enrich → Match 'fix_high_cpu.yml'",
        "5. Guardrails: All 7 checks pass (low risk, known playbook)",
        "6. Approval: Email sent with RCA + 'Approve' button",
        "7. Operator: Clicks approve link in email",
        "8. Execution: Ansible kills stress-ng process on EC2 via SSM",
        "9. Verification: CPU drops, CloudWatch alarm resolves",
        "10. Feedback: Success recorded in DynamoDB → future routing improved",
        "",
        "End-to-end time: ~2-3 minutes (mostly waiting for alarm threshold)",
    ]
)

# ============================================================
# SLIDE 35: Key Differentiators
# ============================================================
add_content_slide(
    "Key Differentiators",
    [
        "AI + Rules Hybrid: Not purely AI — known issues use fast, safe rules",
        "Human-in-the-Loop: Operators stay in control for high-risk actions",
        "Configuration-Driven: 12 YAML files = full control without code changes",
        "Cost-Optimized AI: Intelligent model routing saves 60-90% on LLM costs",
        "Defense-in-Depth: 7 guardrail layers + fleet breaker + stop conditions",
        "Production-Ready: VPC endpoints, Secrets Manager, WAF, IAM least privilege",
        "Observable: Structured logs, custom metrics, distributed tracing, dashboards",
        "Self-Improving: Effectiveness scorer + feedback loop improves over time",
        "AWS-Native: CDK IaC, ECS Fargate, Bedrock, DynamoDB, SQS, SES",
        "Fully Tested: Unit + Property-based + CDK assertion + Integration tests",
    ]
)


# ============================================================
# SLIDE 36: Tech Stack Summary
# ============================================================
add_two_column_slide(
    "Technology Stack",
    "Application Layer",
    [
        "• Python 3.11+",
        "• FastAPI (async web framework)",
        "• Pydantic (payload validation)",
        "• Ansible (playbook execution)",
        "• asyncio (concurrency)",
        "• Hypothesis (property-based testing)",
        "• Ruff (linting + formatting)",
        "• OpenTelemetry (tracing)",
    ],
    "AWS Services",
    [
        "• ECS Fargate (compute)",
        "• Amazon Bedrock (AI - Nova/Claude)",
        "• DynamoDB (state/memory)",
        "• SQS + DLQ (message queue)",
        "• API Gateway HTTP API (ingress)",
        "• SES (approval emails)",
        "• Secrets Manager (credentials)",
        "• SSM (run commands + params)",
        "• CloudWatch (logs/metrics/alarms)",
        "• WAF (API protection)",
        "• CDK v2 (IaC)",
    ],
)

# ============================================================
# SLIDE 37: Thank You / Q&A
# ============================================================
add_title_slide(
    "Thank You",
    "Questions & Discussion\n\n"
    "github.com/your-org/aiops-production-automation-ansible-agentic"
)

# ============================================================
# Save the presentation
# ============================================================
output_path = "AIOps_Self_Healing_Infrastructure_Presentation.pptx"
prs.save(output_path)
print(f"Presentation saved to: {output_path}")
print(f"Total slides: {len(prs.slides)}")
