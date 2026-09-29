"""Generate the Stand and Deliver presentation for the GenAI SRE/DevOps badge."""

from pptx import Presentation
from pptx.util import Inches, Pt, Cm, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
import os

prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)

# Color scheme
IBM_BLUE = RGBColor(0x05, 0x30, 0xAD)
DARK_GRAY = RGBColor(0x2D, 0x2D, 0x2D)
LIGHT_GRAY = RGBColor(0x6C, 0x75, 0x7D)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
GREEN = RGBColor(0x28, 0xA7, 0x45)
RED = RGBColor(0xDC, 0x35, 0x45)
ORANGE = RGBColor(0xFD, 0x7E, 0x14)


def add_title_slide(title, subtitle=""):
    slide = prs.slides.add_slide(prs.slide_layouts[6])  # Blank
    # Background
    bg = slide.background
    fill = bg.fill
    fill.solid()
    fill.fore_color.rgb = IBM_BLUE
    # Title
    txBox = slide.shapes.add_textbox(Inches(1), Inches(2), Inches(11), Inches(2))
    tf = txBox.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = title
    p.font.size = Pt(36)
    p.font.bold = True
    p.font.color.rgb = WHITE
    p.alignment = PP_ALIGN.CENTER
    # Subtitle
    if subtitle:
        p2 = tf.add_paragraph()
        p2.text = subtitle
        p2.font.size = Pt(20)
        p2.font.color.rgb = WHITE
        p2.alignment = PP_ALIGN.CENTER
    return slide


def add_content_slide(title, bullets=None, code=None, note=""):
    slide = prs.slides.add_slide(prs.slide_layouts[6])  # Blank
    # Title bar
    shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, Inches(1.2))
    shape.fill.solid()
    shape.fill.fore_color.rgb = IBM_BLUE
    shape.line.fill.background()
    tf = shape.text_frame
    tf.margin_top = Pt(12)
    tf.margin_left = Pt(24)
    p = tf.paragraphs[0]
    p.text = title
    p.font.size = Pt(28)
    p.font.bold = True
    p.font.color.rgb = WHITE
    # Content area
    top = Inches(1.5)
    if bullets:
        txBox = slide.shapes.add_textbox(Inches(0.8), top, Inches(11.5), Inches(5.5))
        tf = txBox.text_frame
        tf.word_wrap = True
        for i, bullet in enumerate(bullets):
            if i == 0:
                p = tf.paragraphs[0]
            else:
                p = tf.add_paragraph()
            p.text = bullet
            p.font.size = Pt(18)
            p.font.color.rgb = DARK_GRAY
            p.space_after = Pt(8)
            p.level = 0

    if code:
        code_top = Inches(4.0) if bullets else Inches(1.5)
        code_height = Inches(3.0) if bullets else Inches(5.5)
        # Code background box
        code_bg = slide.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE,
            Inches(0.5), code_top, Inches(12.3), code_height
        )
        code_bg.fill.solid()
        code_bg.fill.fore_color.rgb = RGBColor(0xF4, 0xF4, 0xF4)
        code_bg.line.color.rgb = RGBColor(0xDD, 0xDD, 0xDD)
        # Code text
        tf = code_bg.text_frame
        tf.word_wrap = True
        tf.margin_top = Pt(8)
        tf.margin_left = Pt(12)
        p = tf.paragraphs[0]
        p.text = code
        p.font.name = 'Consolas'
        p.font.size = Pt(11)
        p.font.color.rgb = DARK_GRAY

    if note:
        note_box = slide.shapes.add_textbox(Inches(0.8), Inches(6.8), Inches(11.5), Inches(0.5))
        tf = note_box.text_frame
        p = tf.paragraphs[0]
        p.text = note
        p.font.size = Pt(12)
        p.font.italic = True
        p.font.color.rgb = LIGHT_GRAY

    return slide

def add_screenshot_slide(title, caption):
    """Add a slide with a placeholder for a screenshot."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    # Title bar
    shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, Inches(1.2))
    shape.fill.solid()
    shape.fill.fore_color.rgb = IBM_BLUE
    shape.line.fill.background()
    tf = shape.text_frame
    tf.margin_top = Pt(12)
    tf.margin_left = Pt(24)
    p = tf.paragraphs[0]
    p.text = title
    p.font.size = Pt(28)
    p.font.bold = True
    p.font.color.rgb = WHITE

    # Placeholder box
    placeholder = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE,
        Inches(1.5), Inches(1.8), Inches(10.3), Inches(4.5)
    )
    placeholder.fill.solid()
    placeholder.fill.fore_color.rgb = RGBColor(0xF8, 0xF9, 0xFA)
    placeholder.line.color.rgb = RGBColor(0xAD, 0xB5, 0xBD)
    placeholder.line.width = Pt(2)
    tf = placeholder.text_frame
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    p.text = f"[INSERT SCREENSHOT HERE]"
    p.font.size = Pt(24)
    p.font.color.rgb = LIGHT_GRAY
    p.alignment = PP_ALIGN.CENTER

    # Caption
    cap_box = slide.shapes.add_textbox(Inches(1.5), Inches(6.5), Inches(10.3), Inches(0.6))
    tf = cap_box.text_frame
    p = tf.paragraphs[0]
    p.text = caption
    p.font.size = Pt(14)
    p.font.italic = True
    p.font.color.rgb = DARK_GRAY
    p.alignment = PP_ALIGN.CENTER

    return slide

# ============================================================
# SLIDE 1: TITLE
# ============================================================
add_title_slide(
    "AIOps Self-Healing Infrastructure",
    "IBM Consulting Generative & Agentic AI\n"
    "SRE/DevOps Engineer — Experienced Level\n\n"
    "Ravindra Yadav | August 2026"
)

# ============================================================
# SLIDE 2: AGENDA
# ============================================================
add_content_slide(
    "Agenda",
    bullets=[
        "1. Business Problem & Client Need",
        "2. IBM Generative & Agentic AI Offering",
        "3. Amazon Bedrock — AI Agent Implementation",
        "4. Solution Architecture & Work Products",
        "5. Delivery Approach (IBM Garage, IaC, CI/CD)",
        "6. Risks & IBM Trustworthy AI",
        "7. Demo: Rule Mode & AI Agent Mode",
    ]
)

# ============================================================
# SLIDE 3: BUSINESS PROBLEM
# ============================================================
add_content_slide(
    "1. Business Problem",
    bullets=[
        "Problem: SRE teams face alert fatigue, slow MTTR (15-30+ min), inconsistent remediation",
        "Goal: Build an AI-powered self-healing platform that autonomously detects, diagnoses, and remediates",
        "Approach: Two operating modes — Rule Mode (playbook match) + AI Agent Mode (Bedrock reasoning)",
        "Key constraint: Human-in-the-loop approval for HIGH/CRITICAL risk actions",
        "Target: Reduce MTTR from 30 min to < 5 min with operator approval",
    ]
)

# ============================================================
# SLIDE 4: ARCHITECTURE
# ============================================================
add_content_slide(
    "Architecture Overview",
    bullets=[
        "EC2 Target → CloudWatch Alarm → SNS → Lambda → ECS Fargate (Self-Healing Service)",
        "",
        "Pipeline: Normalize → Enrich → Match Playbook → Guardrails → Execute → Notify",
        "",
        "Rule Mode: Playbook found → Email with 'Approve' button → Click → Ansible executes fix",
        "AI Mode: No playbook → Bedrock analyzes → Email with AI suggestions → Operator acts",
    ],
    note="6 CDK Stacks: Network | Data | Compute | Observability | Monitoring | Simulation"
)

# ============================================================
# SLIDE 5: IBM OFFERING
# ============================================================
add_content_slide(
    "2. IBM Generative & Agentic AI Offering",
    bullets=[
        "AIOps for IT Operations — Automated incident detection, correlation, and resolution",
        "Generative AI for SRE — LLMs for root cause analysis and remediation planning",
        "Agentic AI Patterns — Autonomous agents with memory, reasoning, and confidence scoring",
        "",
        "Aligns with IBM Consulting's 'Client First...with a Point of View' perspective",
        "Demonstrates how Gen AI transforms reactive operations → proactive self-healing",
    ]
)

# ============================================================
# SLIDE 6: BEDROCK / STRATEGIC PARTNER
# ============================================================
add_content_slide(
    "3. Amazon Bedrock — Strategic Partner AI",
    bullets=[
        "4-Model Fallback Chain:",
        "  1. Claude 3 Sonnet → 2. Nova Pro → 3. Claude 3 Haiku → 4. Nova Lite",
        "",
        "Agentic AI Pattern:",
        "  • Memory: 50 historical incidents from DynamoDB",
        "  • Reasoning: Structured prompts with context + excluded failed actions",
        "  • Output: JSON RemediationPlan with confidence scores (0.0–1.0)",
        "  • Escalation: P1 requires 80% confidence, others 70%",
        "",
        "Graceful degradation: If all models fail → rule-based playbook matching",
    ]
)

# ============================================================
# SLIDE 7: CODE — AI AGENT
# ============================================================
add_content_slide(
    "Code: AI Reasoning Agent — Fallback Chain",
    bullets=["Multi-model invocation with retry, timeout, and graceful fallback:"],
    code=(
        "models_to_try = [self._config.model_id] + [\n"
        "    m for m in self._config.FALLBACK_MODELS if m != self._config.model_id\n"
        "]\n"
        "for model_id in models_to_try:\n"
        "    for attempt in range(MAX_RETRIES + 1):\n"
        "        result = await asyncio.wait_for(\n"
        "            self._invoke_model(prompt, model_id=model_id),\n"
        "            timeout=REASONING_TIMEOUT_SECONDS,  # 30s\n"
        "        )\n"
        "        return result  # Success!\n"
        "raise TimeoutError('All models exhausted')"
    )
)

# ============================================================
# SLIDE 8: CODE — PROMPT ENGINEERING
# ============================================================
add_content_slide(
    "Code: Prompt Engineering with Historical Context",
    bullets=["Structured prompt with excluded failed actions and confidence scoring:"],
    code=(
        'prompt = f"""You are an AI remediation agent.\n'
        '\n'
        'ALERT CONTEXT:\n'
        '- Alert: {alert_name} | Severity: {severity}\n'
        '- Service: {service_name} | Target: {target_resource}\n'
        '\n'
        'HISTORICAL CONTEXT ({included} incidents,\n'
        '  {success_count} successes, {failure_count} failures):\n'
        '{history_text}\n'
        '\n'
        'EXCLUDED ACTIONS (always failed): {excluded_actions}\n'
        '\n'
        'Respond with JSON: {{"action": "...",\n'
        '  "confidence": 0.0-1.0, "steps": [...]}}"""'
    )
)

# ============================================================
# SLIDE 9: WORK PRODUCTS
# ============================================================
add_content_slide(
    "4. Key Work Products Delivered",
    bullets=[
        "1. AI Reasoning Agent — Bedrock integration, 4-model fallback, confidence scoring",
        "2. 7-Layer Guardrail Safety Engine — Self-protection, circuit breaker, blast radius",
        "3. Self-Healing Pipeline — 5-stage orchestrator, 50 concurrent pipelines",
        "4. Email Approval System — SES, HTML RCA emails, token-based approval links",
        "5. Concurrency Safety — Host locking, deduplication, priority queue, dependency graph",
        "6. Infrastructure as Code — 6 CDK stacks (Python), environment-aware deployment",
        "7. CI/CD Pipeline — GitHub Actions: lint → test → synth → build → scan → push",
        "8. Operational Runbooks — 8 guides (DR, rollback, scale, incident response)",
        "9. Ansible Playbooks — fix_high_cpu, restart_service, clear_disk",
        "10. Test Suite — Unit, Property (Hypothesis), Integration, CDK, Load (Locust)",
    ]
)

# ============================================================
# SLIDE 10: GUARDRAILS CODE
# ============================================================
add_content_slide(
    "Code: 7-Layer Guardrail Safety Engine",
    bullets=[
        "Evaluation order with short-circuit semantics and 15-second timeout:"
    ],
    code=(
        "class GuardrailEngine:\n"
        "    # 1. Self-Protection\n"
        "    # 2. Maintenance Window\n"
        "    # 3. Circuit Breaker\n"
        "    # 4. Concurrency Guard\n"
        "    # 5. Blast Radius Classifier\n"
        "    # 6. Health Checker\n"
        "    # 7. Approval Gate\n"
        "\n"
        "    async def evaluate(self, action):\n"
        "        result = await asyncio.wait_for(\n"
        "            self._run_checks(action, checks_passed),\n"
        "            timeout=15,  # DENY on timeout\n"
        "        )\n"
        "        # Short-circuits on first non-ALLOW\n"
        "        for check in self._checks:\n"
        "            result = await check.check(action)\n"
        "            if result != ALLOW: return result"
    )
)

# ============================================================
# SLIDE 11: DELIVERY APPROACH
# ============================================================
add_content_slide(
    "5. Delivery Approach — IBM Methods",
    bullets=[
        "IBM Garage Methodology — 6 iterative sprints:",
        "  Sprint 1: Core pipeline | Sprint 2: AI agent | Sprint 3: Guardrails",
        "  Sprint 4: Concurrency/Observability | Sprint 5: CI/CD & IaC | Sprint 6: Runbooks",
        "",
        "Architecture Decision Records:",
        "  • Email over Slack (universal access)",
        "  • Human-in-the-loop for HIGH/CRITICAL risk",
        "  • SSM over SSH (no key management)",
        "  • CloudWatch-native (reduced operational complexity)",
        "",
        "Twelve-Factor App: Env vars, stateless Fargate, explicit deps, disposability",
        "Observability-First: Structured JSON logging, Prometheus metrics, audit trails",
    ]
)

# ============================================================
# SLIDE 12: RISKS & TRUSTWORTHY AI
# ============================================================
add_content_slide(
    "6. Risks & IBM Trustworthy AI",
    bullets=[
        "Key Risks Addressed:",
        "  • AI hallucination → Confidence thresholds + human approval gate",
        "  • Blast radius → 7-layer guardrails, CRITICAL classification for DBs",
        "  • Cascading failures → Circuit breaker + concurrency guard",
        "  • Model unavailability → 4-model fallback chain + rule-based degradation",
        "",
        "IBM Trustworthy AI Principles:",
        "  • Transparency: Full audit trail (model used, confidence, reasoning, outcome)",
        "  • Explainability: 2048-char reasoning explanation in approval emails",
        "  • Robustness: Graceful degradation, 15s guardrail timeout",
        "  • Governance: Human approval for HIGH/CRITICAL, protected hosts config",
        "  • Safety: 'Do nothing' on failure, self-protection check",
    ]
)

# ============================================================
# SLIDE 13-17: DEMO SCREENSHOTS
# ============================================================
add_screenshot_slide(
    "7. Demo: Rule Mode — CloudWatch Alarm",
    "CloudWatch CPU alarm triggered on target EC2 instance (stress-ng → CPU > 80%)"
)

add_screenshot_slide(
    "Demo: Rule Mode — Approval Email Received",
    "Email with RCA, severity-coded alert, and 'Approve Auto-Remediation' button"
)

add_screenshot_slide(
    "Demo: Rule Mode — Remediation Executed",
    "After clicking Approve: Ansible playbook executed via SSM, CPU returns to normal"
)

add_screenshot_slide(
    "Demo: AI Agent Mode — No Playbook Match",
    "Alert triggered with no matching playbook (e.g., NetworkLatencyHigh)"
)

add_screenshot_slide(
    "Demo: AI Agent Mode — AI-Generated Email",
    "Email with Bedrock-generated root cause analysis and suggested remediation steps"
)

add_screenshot_slide(
    "Demo: CloudWatch Dashboard",
    "AIOps metrics — remediation success rate, AI latency, queue depth, ECS task count"
)

# ============================================================
# SLIDE 18: SUMMARY
# ============================================================
add_content_slide(
    "Summary",
    bullets=[
        "Built end-to-end Generative & Agentic AI platform for SRE/DevOps operations",
        "",
        "Amazon Bedrock (Claude + Nova) for intelligent root cause analysis",
        "7-layer guardrail safety engine for Trustworthy AI",
        "Human-in-the-loop approval via email for HIGH/CRITICAL actions",
        "Production-grade: CI/CD, IaC (6 CDK stacks), observability, 8 runbooks",
        "",
        "Impact: MTTR reduced from 30+ min to < 5 min (with operator approval)",
        "",
        "Delivered using IBM Garage Methodology and Trustworthy AI principles",
    ]
)

# ============================================================
# SLIDE 19: THANK YOU
# ============================================================
slide = add_title_slide(
    "Thank You",
    "Ravindra Yadav\n"
    "SRE/DevOps Engineer\n"
    "IBM Consulting"
)

# ============================================================
# SAVE
# ============================================================
output_path = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    'Stand_and_Deliver_GenAI_SRE_DevOps_Intermediate.pptx'
)
prs.save(output_path)
print(f"Presentation saved to: {output_path}")
print(f"Total slides: {len(prs.slides)}")
