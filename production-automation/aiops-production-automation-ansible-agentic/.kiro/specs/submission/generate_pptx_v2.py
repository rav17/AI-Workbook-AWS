"""Generate a polished Stand and Deliver presentation with better visuals."""

from pptx import Presentation
from pptx.util import Inches, Pt, Cm, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from pptx.oxml.ns import qn
from copy import deepcopy
import os

prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)

# IBM Design Language Colors
IBM_BLUE_90 = RGBColor(0x00, 0x1D, 0x6C)
IBM_BLUE_70 = RGBColor(0x00, 0x43, 0xCE)
IBM_BLUE_60 = RGBColor(0x0F, 0x62, 0xFE)
IBM_BLUE_40 = RGBColor(0x78, 0xA9, 0xFF)
IBM_BLUE_20 = RGBColor(0xD0, 0xE2, 0xFF)
COOL_GRAY_90 = RGBColor(0x21, 0x27, 0x2A)
COOL_GRAY_70 = RGBColor(0x4D, 0x53, 0x58)
COOL_GRAY_50 = RGBColor(0x69, 0x70, 0x77)
COOL_GRAY_30 = RGBColor(0xA2, 0xA9, 0xB0)
COOL_GRAY_10 = RGBColor(0xF2, 0xF4, 0xF8)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
GREEN_50 = RGBColor(0x24, 0xA1, 0x48)
RED_60 = RGBColor(0xDA, 0x1E, 0x28)
TEAL_50 = RGBColor(0x00, 0x9D, 0x9A)
PURPLE_60 = RGBColor(0x8A, 0x3F, 0xFC)


def set_gradient_bg(slide, color1, color2):
    """Set a gradient background on a slide."""
    bg = slide.background
    fill = bg.fill
    fill.gradient()
    fill.gradient_stops[0].color.rgb = color1
    fill.gradient_stops[1].color.rgb = color2


def add_accent_bar(slide, top=Inches(0), width=Inches(0.15), height=None):
    """Add a thin accent bar on the left side."""
    if height is None:
        height = prs.slide_height
    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, top, width, height)
    bar.fill.solid()
    bar.fill.fore_color.rgb = IBM_BLUE_60
    bar.line.fill.background()
    return bar


def add_footer(slide, text="Ravindra Yadav | IBM Consulting | AIOps Self-Healing Infrastructure"):
    """Add a subtle footer to the slide."""
    footer = slide.shapes.add_textbox(Inches(0.5), Inches(7.0), Inches(12), Inches(0.4))
    tf = footer.text_frame
    p = tf.paragraphs[0]
    p.text = text
    p.font.size = Pt(9)
    p.font.color.rgb = COOL_GRAY_50
    p.alignment = PP_ALIGN.LEFT


def add_slide_number(slide, num, total=20):
    """Add slide number in bottom right."""
    num_box = slide.shapes.add_textbox(Inches(12.2), Inches(7.0), Inches(1), Inches(0.4))
    tf = num_box.text_frame
    p = tf.paragraphs[0]
    p.text = f"{num}/{total}"
    p.font.size = Pt(9)
    p.font.color.rgb = COOL_GRAY_50
    p.alignment = PP_ALIGN.RIGHT


def make_title_slide(title, subtitle, slide_num):
    """Create a visually striking title slide with gradient."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_gradient_bg(slide, IBM_BLUE_90, IBM_BLUE_70)

    # Decorative circle in top-right
    circle = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(10), Inches(-1), Inches(4), Inches(4))
    circle.fill.solid()
    circle.fill.fore_color.rgb = IBM_BLUE_60
    circle.line.fill.background()

    # Smaller circle
    circle2 = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(11.5), Inches(5), Inches(2.5), Inches(2.5))
    circle2.fill.solid()
    circle2.fill.fore_color.rgb = IBM_BLUE_60
    circle2.line.fill.background()

    # Title text
    txBox = slide.shapes.add_textbox(Inches(1.2), Inches(2.2), Inches(9), Inches(1.5))
    tf = txBox.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = title
    p.font.size = Pt(40)
    p.font.bold = True
    p.font.color.rgb = WHITE
    p.font.name = 'IBM Plex Sans'

    # Subtitle
    if subtitle:
        sub_box = slide.shapes.add_textbox(Inches(1.2), Inches(4.0), Inches(9), Inches(2.5))
        tf = sub_box.text_frame
        tf.word_wrap = True
        for i, line in enumerate(subtitle.split('\n')):
            if i == 0:
                p = tf.paragraphs[0]
            else:
                p = tf.add_paragraph()
            p.text = line
            p.font.size = Pt(18)
            p.font.color.rgb = IBM_BLUE_20
            p.font.name = 'IBM Plex Sans'
            p.space_after = Pt(4)

    # Bottom line accent
    line_shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(1.2), Inches(3.8), Inches(3), Pt(4))
    line_shape.fill.solid()
    line_shape.fill.fore_color.rgb = IBM_BLUE_40
    line_shape.line.fill.background()

    add_slide_number(slide, slide_num)
    return slide


def make_section_slide(title, slide_num):
    """Create a section divider slide."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_gradient_bg(slide, IBM_BLUE_70, IBM_BLUE_90)

    # Large number
    num_box = slide.shapes.add_textbox(Inches(1), Inches(1.5), Inches(3), Inches(3))
    tf = num_box.text_frame
    p = tf.paragraphs[0]
    section_num = title.split('.')[0] if '.' in title else ""
    p.text = section_num
    p.font.size = Pt(120)
    p.font.bold = True
    p.font.color.rgb = IBM_BLUE_40

    # Title
    title_box = slide.shapes.add_textbox(Inches(1), Inches(4.5), Inches(11), Inches(2))
    tf = title_box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    # Remove number prefix for display
    display_title = title.split('. ', 1)[1] if '. ' in title else title
    p.text = display_title
    p.font.size = Pt(36)
    p.font.bold = True
    p.font.color.rgb = WHITE
    p.font.name = 'IBM Plex Sans'

    add_slide_number(slide, slide_num)
    return slide


def make_content_slide(title, bullets, slide_num, two_col=False, icon_bullets=False):
    """Create a content slide with left accent bar and clean layout."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])

    # White background with subtle gray bottom strip
    bg = slide.background
    fill = bg.fill
    fill.solid()
    fill.fore_color.rgb = WHITE

    # Left accent bar
    add_accent_bar(slide)

    # Title
    title_box = slide.shapes.add_textbox(Inches(0.6), Inches(0.3), Inches(12), Inches(0.9))
    tf = title_box.text_frame
    p = tf.paragraphs[0]
    p.text = title
    p.font.size = Pt(26)
    p.font.bold = True
    p.font.color.rgb = COOL_GRAY_90
    p.font.name = 'IBM Plex Sans'

    # Underline
    ul = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.6), Inches(1.15), Inches(2.5), Pt(3))
    ul.fill.solid()
    ul.fill.fore_color.rgb = IBM_BLUE_60
    ul.line.fill.background()

    # Content
    if two_col and len(bullets) > 5:
        mid = len(bullets) // 2
        left_bullets = bullets[:mid]
        right_bullets = bullets[mid:]

        # Left column
        left_box = slide.shapes.add_textbox(Inches(0.6), Inches(1.5), Inches(5.8), Inches(5.2))
        tf = left_box.text_frame
        tf.word_wrap = True
        for i, b in enumerate(left_bullets):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.text = b
            p.font.size = Pt(16)
            p.font.color.rgb = COOL_GRAY_90
            p.space_after = Pt(10)

        # Right column
        right_box = slide.shapes.add_textbox(Inches(6.8), Inches(1.5), Inches(5.8), Inches(5.2))
        tf = right_box.text_frame
        tf.word_wrap = True
        for i, b in enumerate(right_bullets):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.text = b
            p.font.size = Pt(16)
            p.font.color.rgb = COOL_GRAY_90
            p.space_after = Pt(10)
    else:
        content_box = slide.shapes.add_textbox(Inches(0.6), Inches(1.5), Inches(12), Inches(5.5))
        tf = content_box.text_frame
        tf.word_wrap = True
        for i, b in enumerate(bullets):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            if b == "":
                p.space_after = Pt(6)
                continue
            # Check if it's a sub-bullet (starts with spaces or •)
            if b.startswith("  ") or b.startswith("•"):
                p.text = b.strip().lstrip("• ")
                p.font.size = Pt(15)
                p.font.color.rgb = COOL_GRAY_70
                p.level = 1
                p.space_after = Pt(6)
            else:
                p.text = b
                p.font.size = Pt(17)
                p.font.color.rgb = COOL_GRAY_90
                p.space_after = Pt(10)

    add_footer(slide)
    add_slide_number(slide, slide_num)
    return slide


def make_code_slide(title, description, code, slide_num):
    """Create a slide with a code snippet in a dark themed box."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    bg = slide.background
    fill = bg.fill
    fill.solid()
    fill.fore_color.rgb = WHITE

    add_accent_bar(slide)

    # Title
    title_box = slide.shapes.add_textbox(Inches(0.6), Inches(0.3), Inches(12), Inches(0.9))
    tf = title_box.text_frame
    p = tf.paragraphs[0]
    p.text = title
    p.font.size = Pt(24)
    p.font.bold = True
    p.font.color.rgb = COOL_GRAY_90
    p.font.name = 'IBM Plex Sans'

    # Description
    if description:
        desc_box = slide.shapes.add_textbox(Inches(0.6), Inches(1.1), Inches(12), Inches(0.6))
        tf = desc_box.text_frame
        p = tf.paragraphs[0]
        p.text = description
        p.font.size = Pt(14)
        p.font.color.rgb = COOL_GRAY_70
        p.font.italic = True

    # Dark code block
    code_top = Inches(1.8) if description else Inches(1.4)
    code_bg = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE,
        Inches(0.4), code_top, Inches(12.5), Inches(5.0)
    )
    code_bg.fill.solid()
    code_bg.fill.fore_color.rgb = RGBColor(0x1E, 0x1E, 0x2E)  # Dark background
    code_bg.line.fill.background()
    # Round corners
    code_bg.shadow.inherit = False

    tf = code_bg.text_frame
    tf.word_wrap = True
    tf.margin_top = Pt(16)
    tf.margin_left = Pt(20)
    tf.margin_right = Pt(20)
    p = tf.paragraphs[0]
    p.text = code
    p.font.name = 'Consolas'
    p.font.size = Pt(12)
    p.font.color.rgb = RGBColor(0xCD, 0xD6, 0xF4)  # Light text on dark

    add_footer(slide)
    add_slide_number(slide, slide_num)
    return slide


def make_screenshot_slide(title, caption, slide_num):
    """Create a slide with a nice placeholder for screenshots."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    bg = slide.background
    fill = bg.fill
    fill.solid()
    fill.fore_color.rgb = COOL_GRAY_10

    add_accent_bar(slide)

    # Title
    title_box = slide.shapes.add_textbox(Inches(0.6), Inches(0.3), Inches(12), Inches(0.9))
    tf = title_box.text_frame
    p = tf.paragraphs[0]
    p.text = title
    p.font.size = Pt(24)
    p.font.bold = True
    p.font.color.rgb = COOL_GRAY_90
    p.font.name = 'IBM Plex Sans'

    # Screenshot placeholder with shadow effect
    placeholder = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE,
        Inches(1.2), Inches(1.5), Inches(10.9), Inches(4.8)
    )
    placeholder.fill.solid()
    placeholder.fill.fore_color.rgb = WHITE
    placeholder.line.color.rgb = COOL_GRAY_30
    placeholder.line.width = Pt(1.5)

    # Inner text
    tf = placeholder.text_frame
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    p.text = "📷"
    p.font.size = Pt(48)
    p.alignment = PP_ALIGN.CENTER
    p2 = tf.add_paragraph()
    p2.text = "INSERT SCREENSHOT HERE"
    p2.font.size = Pt(18)
    p2.font.color.rgb = COOL_GRAY_50
    p2.alignment = PP_ALIGN.CENTER
    p3 = tf.add_paragraph()
    p3.text = f"({caption})"
    p3.font.size = Pt(13)
    p3.font.color.rgb = COOL_GRAY_50
    p3.font.italic = True
    p3.alignment = PP_ALIGN.CENTER

    add_footer(slide)
    add_slide_number(slide, slide_num)
    return slide


def make_two_box_slide(title, left_title, left_items, right_title, right_items, slide_num):
    """Create a slide with two colored info boxes side by side."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    bg = slide.background
    fill = bg.fill
    fill.solid()
    fill.fore_color.rgb = WHITE

    add_accent_bar(slide)

    # Title
    title_box = slide.shapes.add_textbox(Inches(0.6), Inches(0.3), Inches(12), Inches(0.9))
    tf = title_box.text_frame
    p = tf.paragraphs[0]
    p.text = title
    p.font.size = Pt(26)
    p.font.bold = True
    p.font.color.rgb = COOL_GRAY_90
    p.font.name = 'IBM Plex Sans'

    # Underline
    ul = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.6), Inches(1.15), Inches(2.5), Pt(3))
    ul.fill.solid()
    ul.fill.fore_color.rgb = IBM_BLUE_60
    ul.line.fill.background()

    # Left box
    left_box = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.5), Inches(1.5), Inches(5.9), Inches(5.3)
    )
    left_box.fill.solid()
    left_box.fill.fore_color.rgb = RGBColor(0xE8, 0xF5, 0xE9)  # Light green
    left_box.line.color.rgb = GREEN_50
    left_box.line.width = Pt(1.5)
    tf = left_box.text_frame
    tf.word_wrap = True
    tf.margin_top = Pt(16)
    tf.margin_left = Pt(16)
    p = tf.paragraphs[0]
    p.text = left_title
    p.font.size = Pt(18)
    p.font.bold = True
    p.font.color.rgb = GREEN_50
    p.space_after = Pt(12)
    for item in left_items:
        p = tf.add_paragraph()
        p.text = f"• {item}"
        p.font.size = Pt(14)
        p.font.color.rgb = COOL_GRAY_90
        p.space_after = Pt(6)

    # Right box
    right_box = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE, Inches(6.8), Inches(1.5), Inches(5.9), Inches(5.3)
    )
    right_box.fill.solid()
    right_box.fill.fore_color.rgb = RGBColor(0xE3, 0xF2, 0xFD)  # Light blue
    right_box.line.color.rgb = IBM_BLUE_60
    right_box.line.width = Pt(1.5)
    tf = right_box.text_frame
    tf.word_wrap = True
    tf.margin_top = Pt(16)
    tf.margin_left = Pt(16)
    p = tf.paragraphs[0]
    p.text = right_title
    p.font.size = Pt(18)
    p.font.bold = True
    p.font.color.rgb = IBM_BLUE_60
    p.space_after = Pt(12)
    for item in right_items:
        p = tf.add_paragraph()
        p.text = f"• {item}"
        p.font.size = Pt(14)
        p.font.color.rgb = COOL_GRAY_90
        p.space_after = Pt(6)

    add_footer(slide)
    add_slide_number(slide, slide_num)
    return slide


# ============================================================
# BUILD ALL SLIDES
# ============================================================
slide_num = 1

# SLIDE 1: Title
make_title_slide(
    "AIOps Self-Healing Infrastructure",
    "IBM Consulting — Generative & Agentic AI\n"
    "SRE/DevOps Engineer | Experienced Level\n\n"
    "Ravindra Yadav\n"
    "August 2026",
    slide_num
)
slide_num += 1

# SLIDE 2: Agenda
make_content_slide(
    "Agenda",
    [
        "① Business Problem & Client Need",
        "② IBM Generative & Agentic AI Offering",
        "③ Amazon Bedrock — AI Agent Implementation",
        "④ Solution Architecture & Key Work Products",
        "⑤ Delivery Approach (IBM Garage, IaC, CI/CD)",
        "⑥ Risks & IBM Trustworthy AI Principles",
        "⑦ Live Demo: Rule Mode & AI Agent Mode",
        "⑧ Summary & Key Takeaways",
    ],
    slide_num
)
slide_num += 1

# SLIDE 3: Section - Business Problem
make_section_slide("1. Business Problem", slide_num)
slide_num += 1

# SLIDE 4: Business Problem Detail
make_content_slide(
    "The Challenge: Alert Fatigue & Slow MTTR",
    [
        "⚠️  SRE teams receive hundreds of alerts daily — most require manual triage",
        "⏱️  Mean Time to Resolution: 15–30+ minutes before operator even starts troubleshooting",
        "🔄  Inconsistent remediation: different operators apply different fixes",
        "📈  Infrastructure scales faster than headcount — need intelligent automation",
        "",
        "Our Solution:",
        "  • AI-powered platform that detects, diagnoses, and remediates autonomously",
        "  • Two modes: Rule-based (known issues) + AI Agent (novel incidents)",
        "  • Human-in-the-loop approval for safety-critical actions",
        "  • Target: Reduce MTTR from 30 min → under 5 min",
    ],
    slide_num
)
slide_num += 1

# SLIDE 5: Architecture (two-box)
make_two_box_slide(
    "Two Operating Modes",
    "✅ Rule Mode (Playbook Found)",
    [
        "Alert matches known pattern",
        "Playbook selected from YAML rules",
        "Email with RCA + Approve button",
        "One click → Ansible executes fix",
        "Full audit trail recorded",
    ],
    "🤖 AI Agent Mode (No Playbook)",
    [
        "Novel alert, no playbook match",
        "Bedrock AI analyzes with history",
        "Generates confidence-scored plan",
        "Email with AI suggestions",
        "Operator applies steps manually",
    ],
    slide_num
)
slide_num += 1

# SLIDE 6: Section - IBM Offering
make_section_slide("2. IBM Offering Alignment", slide_num)
slide_num += 1

# SLIDE 7: IBM Offering
make_content_slide(
    "IBM Generative & Agentic AI Offering",
    [
        "🏢  AIOps for IT Operations",
        "  • Automated incident detection, correlation, and resolution using AI",
        "",
        "🧠  Generative AI for SRE",
        "  • LLMs generate root cause analyses & remediation recommendations",
        "",
        "🤖  Agentic AI Patterns",
        "  • Autonomous agents with memory, reasoning, and structured output",
        "  • Confidence scoring and escalation logic",
        "",
        "📐  IBM Consulting 'Client First...with a Point of View'",
        "  • Transforms reactive operations → proactive, self-healing infrastructure",
    ],
    slide_num
)
slide_num += 1

# SLIDE 8: Section - Bedrock
make_section_slide("3. Amazon Bedrock Implementation", slide_num)
slide_num += 1

# SLIDE 9: Bedrock Models
make_content_slide(
    "Amazon Bedrock — 4-Model Fallback Chain",
    [
        "🥇  Primary: Anthropic Claude 3 Sonnet — Complex root cause analysis",
        "🥈  Secondary: Amazon Nova Pro — Cost-effective reasoning",
        "🥉  Tertiary: Anthropic Claude 3 Haiku — Lightweight classification",
        "🏅  Final: Amazon Nova Lite — Last resort before rule-based fallback",
        "",
        "Agent Capabilities:",
        "  • Memory — Retrieves 50 historical incidents from DynamoDB",
        "  • Reasoning — Structured prompts with context + excluded failed actions",
        "  • Output — JSON RemediationPlan with confidence scores (0.0–1.0)",
        "  • Escalation — P1 requires 80% confidence, others require 70%",
        "  • Graceful degradation — Rule-based matching if all models fail",
    ],
    slide_num
)
slide_num += 1

# SLIDE 10: Code - Fallback
make_code_slide(
    "Code: Multi-Model Fallback Chain",
    "AIReasoningAgent._invoke_with_retry() — Tries each model with retry and timeout",
    (
        "models_to_try = [self._config.model_id] + [\n"
        "    m for m in self._config.FALLBACK_MODELS\n"
        "    if m != self._config.model_id\n"
        "]\n"
        "\n"
        "for model_id in models_to_try:\n"
        "    backoff = INITIAL_BACKOFF_SECONDS\n"
        "    for attempt in range(MAX_RETRIES + 1):\n"
        "        try:\n"
        "            result = await asyncio.wait_for(\n"
        "                self._invoke_model(prompt, model_id=model_id),\n"
        "                timeout=REASONING_TIMEOUT_SECONDS,  # 30s\n"
        "            )\n"
        "            return result  # Success!\n"
        "        except ClientError as e:\n"
        "            if error_code in ('AccessDeniedException',\n"
        "                              'ResourceNotFoundException'):\n"
        "                break  # Try next model\n"
        "            elif 'Throttl' in error_code:\n"
        "                await asyncio.sleep(backoff)\n"
        "                backoff *= 2\n"
        "\n"
        "raise TimeoutError('All models exhausted')  # → Rule-based fallback"
    ),
    slide_num
)
slide_num += 1

# SLIDE 11: Code - Prompt Engineering
make_code_slide(
    "Code: Prompt Engineering with Historical Context",
    "Structured prompt injects incident history and excludes always-failed actions",
    (
        "prompt = f\"\"\"You are an AI remediation agent.\n"
        "\n"
        "ALERT CONTEXT:\n"
        "- Alert Name: {alert_name}\n"
        "- Severity: {severity}\n"
        "- Service: {service_name}\n"
        "- Target Resource: {target_resource}\n"
        "- Labels: {json.dumps(labels)}\n"
        "\n"
        "HISTORICAL CONTEXT ({included} incidents,\n"
        "  {success_count} successes, {failure_count} failures):\n"
        "{history_text}\n"
        "\n"
        "EXCLUDED ACTIONS (all past attempts failed):\n"
        "  {', '.join(excluded_actions)}\n"
        "\n"
        "Respond with JSON:\n"
        "{{'action': '...', 'confidence': 0.0-1.0,\n"
        "  'reasoning': '...', 'steps': [...]}}\"\"\""
    ),
    slide_num
)
slide_num += 1

# SLIDE 12: Section - Work Products
make_section_slide("4. Solution & Work Products", slide_num)
slide_num += 1

# SLIDE 13: Work Products Overview
make_content_slide(
    "Key Deliverables (10 Work Products)",
    [
        "① AI Reasoning Agent — Bedrock, 4-model fallback, confidence scoring",
        "② 7-Layer Guardrail Engine — Safety checks with short-circuit logic",
        "③ Self-Healing Pipeline — 5-stage orchestrator, 50 concurrent pipelines",
        "④ Email Approval System — SES, HTML RCA, token-based approval links",
        "⑤ Concurrency Safety — Host locking, dedup, circuit breaker, priority queue",
        "⑥ Infrastructure as Code — 6 AWS CDK stacks in Python",
        "⑦ CI/CD Pipeline — GitHub Actions: lint → test → synth → scan → deploy",
        "⑧ Operational Runbooks — 8 guides (DR, rollback, scale, incident response)",
        "⑨ Ansible Playbooks — fix_high_cpu, restart_service, clear_disk",
        "⑩ Test Suite — Unit, Property (Hypothesis), Integration, CDK, Load",
    ],
    slide_num
)
slide_num += 1

# SLIDE 14: Guardrails Code
make_code_slide(
    "Code: 7-Layer Guardrail Safety Engine",
    "Sequential checks with short-circuit semantics — 15-second overall timeout",
    (
        "class GuardrailEngine:\n"
        "    \"\"\"Evaluation order:\n"
        "    1. Self-Protection    5. Blast Radius Classifier\n"
        "    2. Maintenance Window 6. Health Checker\n"
        "    3. Circuit Breaker    7. Approval Gate\n"
        "    4. Concurrency Guard\n"
        "    \"\"\"\n"
        "\n"
        "    async def evaluate(self, action: RemediationAction):\n"
        "        try:\n"
        "            result = await asyncio.wait_for(\n"
        "                self._run_checks(action, checks_passed),\n"
        "                timeout=15  # DENY on timeout\n"
        "            )\n"
        "        except asyncio.TimeoutError:\n"
        "            return GuardrailDecision(type=DENY,\n"
        "                reason='Timed out after 15 seconds')\n"
        "\n"
        "    async def _run_checks(self, action, passed):\n"
        "        for check in self._checks:\n"
        "            result = await check.check(action)\n"
        "            if result != ALLOW:\n"
        "                return result  # Short-circuit!\n"
        "            passed.append(check.name)"
    ),
    slide_num
)
slide_num += 1

# SLIDE 15: Section - Delivery
make_section_slide("5. Delivery Approach", slide_num)
slide_num += 1

# SLIDE 16: Delivery Approach
make_content_slide(
    "IBM Garage Methodology — Iterative Delivery",
    [
        "Sprint 1:  Core Pipeline — normalize → enrich → match → execute → notify",
        "Sprint 2:  AI Reasoning Agent — Bedrock integration, prompt engineering",
        "Sprint 3:  Guardrail Safety Engine — 7 layers, short-circuit, timeout",
        "Sprint 4:  Concurrency & Observability — Locking, metrics, dashboards",
        "Sprint 5:  CI/CD & Infrastructure — CDK stacks, GitHub Actions, ECR scan",
        "Sprint 6:  Runbooks & Documentation — 8 operational guides, demo scripts",
        "",
        "Key Architecture Decisions:",
        "  • Email over Slack — Universal access, no third-party dependency",
        "  • SSM over SSH — No key management, works with private subnets",
        "  • CloudWatch-native — Reduced complexity vs. external Prometheus",
        "  • Twelve-Factor App — Env vars, stateless Fargate, explicit dependencies",
    ],
    slide_num
)
slide_num += 1

# SLIDE 17: Section - Risks
make_section_slide("6. Risks & Trustworthy AI", slide_num)
slide_num += 1

# SLIDE 18: Risks & Ethics
make_two_box_slide(
    "Risks & IBM Trustworthy AI Principles",
    "⚠️ Risks Addressed",
    [
        "AI hallucination → Confidence thresholds",
        "Blast radius → 7-layer guardrails",
        "Cascading failures → Circuit breaker",
        "Model unavailability → 4-model fallback",
        "Unauthorized execution → Token expiry",
        "Bias → Exclude always-failed actions",
    ],
    "🛡️ Trustworthy AI Applied",
    [
        "Transparency: Full audit trail",
        "Explainability: Reasoning in emails",
        "Robustness: Graceful degradation",
        "Governance: Human approval gate",
        "Safety: 'Do nothing' on failure",
        "Privacy: No PII, encrypted at rest",
    ],
    slide_num
)
slide_num += 1

# SLIDE 19: Section - Demo
make_section_slide("7. Demo Evidence", slide_num)
slide_num += 1

# SLIDES 20-25: Screenshots
make_screenshot_slide(
    "Rule Mode — CloudWatch Alarm Triggered",
    "CloudWatch CPU alarm fires on target EC2 (stress-ng → CPU > 80%)",
    slide_num
)
slide_num += 1

make_screenshot_slide(
    "Rule Mode — Approval Email Received",
    "HTML email with RCA, severity badge, and 'Approve Auto-Remediation' button",
    slide_num
)
slide_num += 1

make_screenshot_slide(
    "Rule Mode — Remediation Executed Successfully",
    "After clicking Approve: Ansible playbook executed via SSM, CPU normalized",
    slide_num
)
slide_num += 1

make_screenshot_slide(
    "AI Agent Mode — Novel Alert (No Playbook)",
    "NetworkLatencyHigh alert triggered — no matching playbook in system",
    slide_num
)
slide_num += 1

make_screenshot_slide(
    "AI Agent Mode — AI-Generated Analysis Email",
    "Bedrock-generated root cause analysis with confidence score and suggested steps",
    slide_num
)
slide_num += 1

make_screenshot_slide(
    "CloudWatch Dashboard — Operational Metrics",
    "Remediation success rate, AI reasoning latency (p50/p95/p99), queue depth",
    slide_num
)
slide_num += 1

# SLIDE 26: Summary
make_content_slide(
    "Summary & Key Takeaways",
    [
        "✅  Built end-to-end Generative & Agentic AI platform for SRE/DevOps",
        "",
        "🧠  Amazon Bedrock (Claude + Nova) for intelligent root cause analysis",
        "🛡️  7-layer guardrail safety engine for Trustworthy AI",
        "👤  Human-in-the-loop approval via email for HIGH/CRITICAL actions",
        "☁️  Production-grade: 6 CDK stacks, CI/CD, observability, 8 runbooks",
        "",
        "📊  Impact: MTTR reduced from 30+ min to < 5 min (with approval)",
        "",
        "🏭  Delivered using IBM Garage Methodology",
        "🤝  IBM Trustworthy AI principles embedded throughout",
    ],
    slide_num
)
slide_num += 1

# SLIDE 27: Thank You
make_title_slide(
    "Thank You",
    "Ravindra Yadav\n"
    "SRE/DevOps Engineer\n"
    "IBM Consulting\n\n"
    "Questions?",
    slide_num
)

# ============================================================
# SAVE
# ============================================================
output_path = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    'Stand_and_Deliver_GenAI_SRE_DevOps_v2.pptx'
)
prs.save(output_path)
print(f"Presentation saved to: {output_path}")
print(f"Total slides: {len(prs.slides)}")
