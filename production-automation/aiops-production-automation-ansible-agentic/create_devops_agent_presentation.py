"""Generate PPTX presentation: AIOps Platform + AWS DevOps Agent Integration (Next Phase).

This adds slides for the planned AWS DevOps Agent integration as Option B:
DevOps Agent as a "second opinion" for novel/complex incidents alongside the
existing rule-based pipeline.
"""

from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
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
ACCENT_PURPLE = RGBColor(0x9B, 0x59, 0xB6)
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
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    add_dark_bg(slide)

    txBox = slide.shapes.add_textbox(Inches(1), Inches(2.2), Inches(11), Inches(1.5))
    tf = txBox.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = title
    p.font.size = Pt(40)
    p.font.bold = True
    p.font.color.rgb = WHITE
    p.alignment = PP_ALIGN.CENTER

    txBox2 = slide.shapes.add_textbox(Inches(2), Inches(4.0), Inches(9), Inches(1.5))
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

    shape = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), Inches(13.33), Inches(1.1)
    )
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

    txBox2 = slide.shapes.add_textbox(Inches(0.8), Inches(1.4), Inches(11.5), Inches(5.8))
    tf2 = txBox2.text_frame
    tf2.word_wrap = True

    for i, bullet in enumerate(bullets):
        if i == 0:
            p = tf2.paragraphs[0]
        else:
            p = tf2.add_paragraph()

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

    shape = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), Inches(13.33), Inches(1.1)
    )
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
# SLIDES
# ============================================================

# --- SLIDE 1: Title ---
add_title_slide(
    "AIOps Self-Healing Infrastructure",
    "Phase 2 Roadmap: AWS DevOps Agent Integration\n\n"
    "Autonomous Incident Investigation for Novel/Complex Alerts"
)

# --- SLIDE 2: Current Architecture (Summary) ---
add_content_slide(
    "Current State — Production-Ready Self-Healing Platform",
    [
        "Rule Mode: Known alerts → matched playbook → email approval → auto-remediation",
        "AI Agent Mode: Unknown alerts → Bedrock reasoning → advisory email (manual fix)",
        "7-layer guardrail engine with fleet-wide circuit breaker",
        "Cost-optimized model routing (Nova Lite / Nova Pro / Claude Sonnet)",
        "Storm detection, alert inhibition, concurrency control",
        "Full CI/CD with CDK IaC (6 stacks), health gates, auto-rollback",
        "",
        "GAP: AI Agent Mode sends advisory emails — no autonomous investigation",
        "GAP: No cross-signal correlation (code deploys, logs, topology)",
        "GAP: No self-improving investigation skills (only success/fail tracking)",
    ]
)


# --- SLIDE 3: Why AWS DevOps Agent ---
add_content_slide(
    "Why AWS DevOps Agent? — Closing the Gap",
    [
        "AWS DevOps Agent (GA March 2026) — AI-powered autonomous operations agent",
        "",
        "What it adds that we DON'T have today:",
        "  - Autonomous multi-signal investigation (metrics + logs + deploys + code)",
        "  - Auto-discovery topology (replaces static asset_inventory.yml)",
        "  - Learned investigation skills (gets smarter from past investigations)",
        "  - Proactive incident prevention (pattern analysis → improvement recommendations)",
        "  - Cross-account visibility (dev/staging/prod in one view)",
        "  - MCP extensibility (Datadog, Splunk, PagerDuty, custom tools)",
        "",
        "What we KEEP (our existing strengths):",
        "  - Rule-based fast path (sub-second matching for known issues)",
        "  - 7-layer guardrail engine + fleet circuit breaker",
        "  - Ansible/SSM execution with approval workflow",
        "  - Cost-optimized model routing for Bedrock calls",
    ]
)

# --- SLIDE 4: Integration Strategy ---
add_section_slide("Integration Strategy: Option B")

# --- SLIDE 5: Option B Explained ---
add_two_column_slide(
    "Option B — DevOps Agent as 'Second Opinion'",
    "Existing Pipeline (Unchanged)",
    [
        "• Alert → Pipeline → PlaybookMapper",
        "• Match found → Approval email",
        "• Operator approves → Ansible executes",
        "• Guardrails + baking validation",
        "• Feedback loop → DynamoDB",
        "",
        "Zero changes to rule-based path",
        "Keeps MTTR < 3 min for known issues",
        "Preserves all safety guarantees",
    ],
    "New: DevOps Agent Path",
    [
        "• No playbook match → trigger DevOps Agent",
        "• Agent investigates autonomously:",
        "  - Correlates CloudWatch + logs + deploys",
        "  - Maps topology + dependencies",
        "  - Generates RCA + mitigation plan",
        "• Result sent as enriched advisory email",
        "• Future: Agent executes via our MCP tools",
        "",
        "Handles the 30% of alerts that currently",
        "get generic 'manual investigation' emails",
    ],
)


# --- SLIDE 6: Architecture Diagram (Text-Based) ---
add_content_slide(
    "Integrated Architecture — Dual-Path Design",
    [
        "Alert Ingestion (unchanged):",
        "  - CloudWatch → SNS → Lambda → POST /webhook → ECS Pipeline",
        "",
        "Path A — Known Alerts (Rule Mode, unchanged):",
        "  - PlaybookMapper match → Guardrails → Approval → Ansible → SSM",
        "",
        "Path B — Novel Alerts (DevOps Agent, NEW):",
        "  - No playbook match → Trigger DevOps Agent investigation",
        "  - Agent Space correlates: CloudWatch metrics + logs + recent deploys",
        "  - Agent builds topology-aware RCA",
        "  - Returns: root cause + confidence + mitigation steps",
        "  - Our system: Sends enriched advisory email with Agent findings",
        "",
        "Path C — Future (DevOps Agent + Auto-Execute):",
        "  - Agent calls our execution tools via MCP",
        "  - Still passes through our guardrail engine",
        "  - Human approval required for high-risk actions",
    ]
)

# --- SLIDE 7: DevOps Agent Features We Use ---
add_section_slide("DevOps Agent Features — What We Leverage")

# --- SLIDE 8: Feature 1 - Autonomous Investigation ---
add_content_slide(
    "Feature 1: Autonomous Incident Investigation",
    [
        "Current: AIReasoningAgent builds a prompt → invokes single Bedrock model",
        "DevOps Agent: Multi-step autonomous investigation across multiple signals",
        "",
        "Investigation capabilities:",
        "  - Correlates CloudWatch metrics with recent code deployments",
        "  - Searches CloudWatch Logs for error patterns around alert time",
        "  - Identifies recent infrastructure changes (scaling events, config updates)",
        "  - Maps blast radius using auto-discovered topology",
        "  - Generates structured RCA with confidence scoring",
        "",
        "Example: CPU spike alert",
        "  - Current: 'CPU high on host X, consider killing top process'",
        "  - DevOps Agent: 'CPU spike started 2 min after deploy #847 which",
        "    added a recursive loop in payment-service/checkout.py:142'",
    ]
)


# --- SLIDE 9: Feature 2 - Topology Auto-Discovery ---
add_content_slide(
    "Feature 2: Auto-Discovery Topology",
    [
        "Current: Static config/asset_inventory.yml (manually maintained)",
        "DevOps Agent: Live auto-discovery of all resources + relationships",
        "",
        "What topology provides:",
        "  - System view: services, databases, queues, load balancers",
        "  - Container view: ECS tasks, pods, containers",
        "  - Resource view: individual EC2 instances, Lambda functions",
        "  - Dependency mapping: 'service A calls service B via this ALB'",
        "  - Cross-account: dev/staging/prod in one topology graph",
        "",
        "Impact on our system:",
        "  - Replaces Enricher + AssetInventory static lookup",
        "  - BlastRadiusClassifier gets real dependency data (not static YAML)",
        "  - Alert correlation becomes topology-aware (not just label matching)",
        "  - No more stale inventory — topology updates automatically",
    ]
)

# --- SLIDE 10: Feature 3 - Learned Skills ---
add_content_slide(
    "Feature 3: Learned Investigation Skills",
    [
        "Current: EffectivenessScorer tracks success/failure rates per playbook",
        "DevOps Agent: Learns HOW to investigate, not just what succeeded",
        "",
        "Built-in learned skills:",
        "  - Agent Space Understanding — knows your architecture",
        "  - Understanding Code Dependencies — maps code to infra",
        "  - Understanding Pipeline Topology — deployment awareness",
        "  - Tool Use Best Practices — learns which tools help for which alerts",
        "",
        "Custom learned skill (from our incident history):",
        "  - Learns investigation patterns from past DevOps Agent investigations",
        "  - Encodes: 'For HighCPU alerts on payment-service, always check",
        "    recent deploys first, then connection pool exhaustion'",
        "  - Gets smarter over time without code changes",
        "",
        "Complements our ModelRouter — Agent learns WHEN to investigate deeply",
    ]
)

# --- SLIDE 11: Feature 4 - Proactive Prevention ---
add_content_slide(
    "Feature 4: Proactive Incident Prevention",
    [
        "Current: Purely reactive — process alerts AFTER they fire",
        "DevOps Agent: Analyzes patterns to PREVENT future incidents",
        "",
        "Prevention categories:",
        "  - Observability gaps: 'Service X has no alarm for error rate'",
        "  - Infrastructure risks: 'Host Y has hit 80% disk 3 times this month'",
        "  - Deployment risks: 'Last 3 deploys to service Z caused alerts'",
        "  - Resilience improvements: 'Add retry logic to database connections'",
        "",
        "How it integrates with our system:",
        "  - Surfaces recommendations in Ops Backlog (DevOps Agent web app)",
        "  - We can auto-create CloudWatch alarms for identified gaps",
        "  - Feed prevention insights into our playbook_mapping.yml",
        "  - Convert repeated advisory emails into new playbook rules",
    ]
)


# --- SLIDE 12: Feature 5 - MCP + Custom Agents ---
add_content_slide(
    "Feature 5: MCP Integration & Custom SRE Agents",
    [
        "MCP Servers extend DevOps Agent's reach into our tools:",
        "  - Connect our ECS pipeline as a custom MCP tool",
        "  - DevOps Agent can query: 'What playbooks are available for this alert?'",
        "  - DevOps Agent can invoke: 'Execute fix_high_cpu.yml on host X'",
        "  - Still passes through our guardrail engine (via MCP response)",
        "",
        "Custom SRE Agent (future):",
        "  - Define a specialized agent with OUR system prompt + tools",
        "  - Runs on schedule: 'Every 6 hours, check effectiveness scores'",
        "  - On-demand: 'Investigate why playbook Y keeps failing on host Z'",
        "  - Accesses our DynamoDB incident history + playbook configs",
        "",
        "Remote MCP endpoint:",
        "  - Access DevOps Agent from Kiro IDE or CLI",
        "  - Engineers can ask: 'What happened with incident INC-12345?'",
    ]
)

# --- SLIDE 13: Feature 6 - Runbooks ---
add_content_slide(
    "Feature 6: Runbooks & Release Management",
    [
        "Runbooks in DevOps Agent:",
        "  - Guide the agent during investigations (like our playbook_mapping.yml)",
        "  - But dynamic — agent decides which runbook applies based on findings",
        "  - Encode team knowledge: 'For database alerts, always check connection pool first'",
        "  - Works alongside our static playbook rules",
        "",
        "Release Management (Preview):",
        "  - Release readiness code reviews for our CDK + playbook changes",
        "  - Automated release testing in isolated verification environments",
        "  - Catches: 'This playbook change breaks remediation for HighMemory alerts'",
        "  - Validates CDK changes don't break the self-healing pipeline",
        "",
        "On-Demand SRE Tasks:",
        "  - Natural language queries: 'Show all P1 incidents this week'",
        "  - 'Why did last 3 remediations for DiskFull on host X fail?'",
        "  - Complements our email-only operator interface",
    ]
)

# --- SLIDE 14: Implementation Plan ---
add_section_slide("Implementation Plan — 4 Phases")


# --- SLIDE 15: Phase 1 ---
add_content_slide(
    "Phase 1: Agent Space Setup & Investigation (Weeks 1-3)",
    [
        "Goal: DevOps Agent investigates novel alerts, sends enriched advisory emails",
        "",
        "Tasks:",
        "  - Create Agent Space via CDK (new Aiops-{env}-DevOpsAgent stack)",
        "  - Associate AWS accounts (monitoring account + service accounts)",
        "  - IAM role: DevOpsAgentRole with read access to CloudWatch, Logs, EC2",
        "  - Configure runbooks from our existing runbooks/ directory",
        "  - Wire _send_ai_advisory_email() to trigger DevOps Agent investigation",
        "  - DevOps Agent returns RCA → replace generic AI advisory with Agent findings",
        "",
        "Integration point: src/app.py → _send_ai_advisory_email()",
        "  - Current: Calls AIReasoningAgent.reason() → generic steps",
        "  - New: Calls DevOps Agent API → topology-aware investigation results",
        "",
        "Rollback: Feature flag /aiops/{env}/use-devops-agent (SSM parameter)",
    ]
)

# --- SLIDE 16: Phase 2 ---
add_content_slide(
    "Phase 2: Topology & Enrichment (Weeks 4-5)",
    [
        "Goal: Replace static asset inventory with live topology data",
        "",
        "Tasks:",
        "  - Enable auto-discovery for all AIOps-managed accounts",
        "  - Map DevOps Agent topology to our Enricher interface",
        "  - Create adapter: TopologyEnricher (calls Agent Space topology API)",
        "  - Dual-mode: try topology first, fall back to asset_inventory.yml",
        "  - Feed topology into BlastRadiusClassifier (real dependency graph)",
        "  - Update AlertCorrelator to use topology relationships",
        "",
        "Benefits:",
        "  - No more stale asset_inventory.yml",
        "  - Blast radius assessment based on actual dependency graph",
        "  - Cross-service correlation (topology-aware, not just label matching)",
        "",
        "Zero downtime: Adapter pattern, old path remains as fallback",
    ]
)

# --- SLIDE 17: Phase 3 ---
add_content_slide(
    "Phase 3: MCP Tools & Bidirectional Integration (Weeks 6-8)",
    [
        "Goal: DevOps Agent can call our execution tools; our pipeline can query Agent",
        "",
        "MCP Server (our pipeline exposed TO DevOps Agent):",
        "  - Tool: list_playbooks → returns available playbooks for alert type",
        "  - Tool: check_guardrails → evaluates action through 7-layer engine",
        "  - Tool: execute_remediation → triggers approved playbook execution",
        "  - Tool: get_incident_history → queries DynamoDB incident store",
        "  - Hosted on ECS (same cluster) or as Lambda behind API Gateway",
        "",
        "MCP Client (our pipeline calling DevOps Agent):",
        "  - Query: investigate_incident → full autonomous investigation",
        "  - Query: get_topology → live resource dependency map",
        "  - Query: get_recommendations → proactive improvement suggestions",
        "",
        "Security: MCP server behind VPC, DevOps Agent accesses via private connection",
    ]
)


# --- SLIDE 18: Phase 4 ---
add_content_slide(
    "Phase 4: Autonomous Execution & Prevention (Weeks 9-12)",
    [
        "Goal: DevOps Agent can trigger approved remediations autonomously",
        "",
        "Autonomous execution (with safety):",
        "  - DevOps Agent investigates → produces mitigation plan",
        "  - Plan routed through our GuardrailEngine.evaluate()",
        "  - LOW risk: auto-execute (no human approval needed)",
        "  - MEDIUM risk: email approval (existing workflow)",
        "  - HIGH/CRITICAL: always requires human approval",
        "  - All executions pass through fleet circuit breaker",
        "",
        "Proactive prevention loop:",
        "  - DevOps Agent surfaces improvement recommendations",
        "  - Auto-create CloudWatch alarms for identified gaps",
        "  - Auto-generate playbook rules from repeated advisory patterns",
        "  - Convert 'AI Mode' alerts into 'Rule Mode' alerts over time",
        "",
        "Custom SRE Agent: Scheduled health checks + trend analysis",
    ]
)

# --- SLIDE 19: Timeline & Milestones ---
add_content_slide(
    "Timeline & Milestones",
    [
        "Phase 1 (Weeks 1-3): Investigation Integration",
        "  - Milestone: Novel alerts get DevOps Agent RCA in advisory emails",
        "  - Success metric: RCA quality score > current AI advisory (A/B test)",
        "",
        "Phase 2 (Weeks 4-5): Topology Enrichment",
        "  - Milestone: Asset inventory auto-refreshed from topology",
        "  - Success metric: Zero stale-inventory incidents",
        "",
        "Phase 3 (Weeks 6-8): MCP Bidirectional Integration",
        "  - Milestone: DevOps Agent can query and execute via our tools",
        "  - Success metric: Agent uses guardrails for all execution requests",
        "",
        "Phase 4 (Weeks 9-12): Autonomous Execution + Prevention",
        "  - Milestone: LOW risk actions auto-execute without human approval",
        "  - Success metric: 50% reduction in advisory-only emails",
    ]
)

# --- SLIDE 20: Risk & Mitigation ---
add_section_slide("Risks & Mitigation")


# --- SLIDE 21: Risks ---
add_two_column_slide(
    "Risks & Mitigation Strategy",
    "Risks",
    [
        "• Latency: DevOps Agent investigation",
        "  takes 30-120s (vs. 5s for Bedrock call)",
        "",
        "• Cost: $0.498/agent-minute",
        "  (~$15-60/investigation)",
        "",
        "• Availability: If DevOps Agent is down,",
        "  novel alerts get no AI analysis",
        "",
        "• Data access: Agent needs IAM role",
        "  with read access to CloudWatch/Logs",
        "",
        "• Vendor dependency: DevOps Agent is",
        "  a managed service with limited control",
    ],
    "Mitigations",
    [
        "• Rule-based path unchanged (fast)",
        "  DevOps Agent only for novel alerts",
        "",
        "• Only triggered for unmatched alerts",
        "  (~30% of total, not all traffic)",
        "",
        "• Fallback: existing AIReasoningAgent",
        "  remains as degraded-mode backup",
        "",
        "• Least-privilege IAM role",
        "  Read-only, scoped to AIOps resources",
        "",
        "• Feature flag: instant disable via SSM",
        "  parameter without code deployment",
    ],
)

# --- SLIDE 22: Cost Analysis ---
add_content_slide(
    "Cost Impact Analysis",
    [
        "Current AI costs (Bedrock model routing):",
        "  - ~$0.0003-$0.003 per alert analysis",
        "  - ~$50-100/month for typical alert volume (1000 alerts/month)",
        "",
        "DevOps Agent costs (additional, not replacement):",
        "  - $0.498/agent-minute (investigation time)",
        "  - Novel alerts only: ~300/month × 2-min avg = 600 agent-minutes",
        "  - Estimated: ~$300/month additional",
        "  - AWS Support plan credit offsets most/all of this",
        "",
        "ROI justification:",
        "  - Reduces manual investigation time for novel alerts",
        "  - Current: engineer spends 30-90 min investigating manually",
        "  - With Agent: investigation in 2-5 min, engineer reviews",
        "  - At $100/hr engineer cost: saves ~$5,000-15,000/month",
    ]
)


# --- SLIDE 23: What Stays / What Changes ---
add_two_column_slide(
    "What Stays vs. What Changes",
    "Unchanged (Our Strengths)",
    [
        "• Rule-based pipeline (fast, proven)",
        "• 7-layer guardrail engine",
        "• Fleet + per-host circuit breakers",
        "• Ansible/SSM execution layer",
        "• Email approval workflow",
        "• Storm detection + inhibition",
        "• Cost-optimized model routing",
        "• DynamoDB incident memory",
        "• CI/CD pipeline + CDK IaC",
        "• All 12 YAML config files",
    ],
    "New / Enhanced",
    [
        "• Novel alert investigation (DevOps Agent)",
        "• Live topology (replaces static YAML)",
        "• Learned investigation skills",
        "• Proactive prevention recommendations",
        "• MCP tools (bidirectional)",
        "• Custom SRE Agent (scheduled tasks)",
        "• Richer advisory emails (topology-aware RCA)",
        "• On-demand chat interface for operators",
        "• Cross-account visibility",
        "• Release readiness validation (future)",
    ],
)

# --- SLIDE 24: CDK Changes ---
add_content_slide(
    "Infrastructure Changes — New CDK Stack",
    [
        "New stack: Aiops-{env}-DevOpsAgent",
        "  - Agent Space resource (CloudFormation: AWS::DevOpsAgent::AgentSpace)",
        "  - IAM Role: DevOpsAgentRole-{env} (read-only CloudWatch, Logs, EC2)",
        "  - Account Association (links AWS account to Agent Space)",
        "  - Operator App (web UI for ops team)",
        "",
        "Existing stack changes:",
        "  - ComputeStack: Add devopsagent:* permissions to ECS task role",
        "  - ComputeStack: New SSM param /aiops/{env}/use-devops-agent",
        "  - ComputeStack: New SSM param /aiops/{env}/devops-agent-space-id",
        "  - DataStack: No changes",
        "  - NetworkStack: No changes (Agent is a managed service, not in VPC)",
        "",
        "Deploy order: existing stacks first, DevOpsAgent stack last",
        "Rollback: Delete DevOpsAgent stack, flip feature flag to 'false'",
    ]
)

# --- SLIDE 25: Success Metrics ---
add_content_slide(
    "Success Metrics & KPIs",
    [
        "Phase 1 KPIs:",
        "  - RCA quality: A/B test Agent RCA vs. current AIReasoningAgent",
        "  - Investigation time: < 3 minutes for 90% of novel alerts",
        "  - Fallback rate: < 5% failures requiring fallback to old path",
        "",
        "Phase 2 KPIs:",
        "  - Topology freshness: < 5 min lag for resource discovery",
        "  - Enrichment accuracy: 100% of active hosts found in topology",
        "",
        "Phase 3 KPIs:",
        "  - MCP tool availability: 99.9% uptime",
        "  - Guardrail pass-through: 100% of Agent executions checked",
        "",
        "Phase 4 KPIs:",
        "  - Auto-execution rate: 30% of novel alerts fully autonomous",
        "  - Advisory-to-playbook conversion: 10 new rules/quarter from prevention",
        "  - MTTR reduction: 50% for novel alerts (from 60 min to 30 min)",
    ]
)


# --- SLIDE 26: Summary ---
add_content_slide(
    "Summary — The Best of Both Worlds",
    [
        "KEEP: Fast, safe, battle-tested rule-based pipeline for known issues",
        "ADD: AWS DevOps Agent for autonomous investigation of novel/complex alerts",
        "",
        "Integration philosophy: 'Second opinion, not replacement'",
        "  - DevOps Agent handles investigation (the BRAIN)",
        "  - Our pipeline handles execution (the HANDS)",
        "  - Guardrails ensure safety regardless of who initiates",
        "",
        "End state: Self-improving loop",
        "  - Novel alert → DevOps Agent investigates → produces playbook",
        "  - Playbook added to rules → next time it's a 'known issue'",
        "  - System gets smarter: fewer novel alerts over time",
        "  - Prevention recommendations reduce total alert volume",
        "",
        "Timeline: 12 weeks to full integration, value from Week 3",
    ]
)

# --- SLIDE 27: Thank You ---
add_title_slide(
    "Next Phase: AWS DevOps Agent",
    "Autonomous Investigation for Novel Alerts\n"
    "Preserving Safety | Improving Over Time | Reducing MTTR\n\n"
    "Questions?"
)

# ============================================================
# Save
# ============================================================
output_path = "AIOps_DevOps_Agent_Integration_Plan.pptx"
prs.save(output_path)
print(f"Presentation saved to: {output_path}")
print(f"Total slides: {len(prs.slides)}")
