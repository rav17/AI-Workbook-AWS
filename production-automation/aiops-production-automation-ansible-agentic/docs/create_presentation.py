"""Generate the AIOps Self-Healing Infrastructure presentation (PPTX)."""

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE


def add_title_slide(prs, title, subtitle):
    slide = prs.slides.add_slide(prs.slide_layouts[0])
    slide.shapes.title.text = title
    slide.placeholders[1].text = subtitle


def add_content_slide(prs, title, bullets, notes=""):
    slide = prs.slides.add_slide(prs.slide_layouts[1])
    slide.shapes.title.text = title
    tf = slide.placeholders[1].text_frame
    tf.clear()
    for i, bullet in enumerate(bullets):
        if i == 0:
            tf.paragraphs[0].text = bullet
            tf.paragraphs[0].font.size = Pt(18)
        else:
            p = tf.add_paragraph()
            p.text = bullet
            p.font.size = Pt(18)
            p.space_before = Pt(6)
    if notes:
        slide.notes_slide.notes_text_frame.text = notes


def add_two_column_slide(prs, title, left_items, right_items, left_title="", right_title=""):
    slide = prs.slides.add_slide(prs.slide_layouts[5])  # Blank
    # Title
    txBox = slide.shapes.add_textbox(Inches(0.5), Inches(0.3), Inches(9), Inches(0.8))
    tf = txBox.text_frame
    tf.text = title
    tf.paragraphs[0].font.size = Pt(28)
    tf.paragraphs[0].font.bold = True
    tf.paragraphs[0].font.color.rgb = RGBColor(0x1A, 0x3A, 0x5C)

    # Left column
    left_box = slide.shapes.add_textbox(Inches(0.5), Inches(1.3), Inches(4.5), Inches(5.5))
    tf_left = left_box.text_frame
    tf_left.word_wrap = True
    if left_title:
        tf_left.paragraphs[0].text = left_title
        tf_left.paragraphs[0].font.bold = True
        tf_left.paragraphs[0].font.size = Pt(16)
        tf_left.paragraphs[0].font.color.rgb = RGBColor(0x00, 0x72, 0xC6)
    for item in left_items:
        p = tf_left.add_paragraph()
        p.text = item
        p.font.size = Pt(14)
        p.space_before = Pt(4)

    # Right column
    right_box = slide.shapes.add_textbox(Inches(5.2), Inches(1.3), Inches(4.5), Inches(5.5))
    tf_right = right_box.text_frame
    tf_right.word_wrap = True
    if right_title:
        tf_right.paragraphs[0].text = right_title
        tf_right.paragraphs[0].font.bold = True
        tf_right.paragraphs[0].font.size = Pt(16)
        tf_right.paragraphs[0].font.color.rgb = RGBColor(0x00, 0x72, 0xC6)
    for item in right_items:
        p = tf_right.add_paragraph()
        p.text = item
        p.font.size = Pt(14)
        p.space_before = Pt(4)


def main():
    prs = Presentation()
    prs.slide_width = Inches(10)
    prs.slide_height = Inches(7.5)

    # =========================================================================
    # SLIDE 1: Title
    # =========================================================================
    add_title_slide(
        prs,
        "AIOps Self-Healing Infrastructure",
        "AI-Powered Automated Incident Remediation with Human-in-the-Loop\n\n"
        "Ravindra Yadav | Platform Engineering\n"
        "August 2026"
    )

    # =========================================================================
    # SLIDE 2: Problem Statement
    # =========================================================================
    add_content_slide(prs, "The Problem", [
        "⏱️  Average MTTR: 30+ minutes for routine infrastructure issues",
        "😴  Alert fatigue: Operators drowning in repetitive incidents",
        "🔄  Same issues, same fixes — repeated manually every time",
        "💸  Engineering time wasted on known, solvable problems",
        "🌊  Alert storms overwhelm teams during outages",
        "",
        "What if infrastructure could heal itself?",
    ], notes="Discuss how repetitive alerts like high CPU, disk full, service down consume engineer time. "
             "Mention that 70% of production incidents follow known patterns with documented fixes.")

    # =========================================================================
    # SLIDE 3: Solution Overview
    # =========================================================================
    add_content_slide(prs, "Our Solution: Self-Healing Pipeline", [
        "✅ Automated detection → analysis → remediation → verification",
        "🤖 AI reasoning (Amazon Bedrock) for unknown alert patterns",
        "📋 Rule-based matching for known patterns (Ansible playbooks)",
        "👤 Human-in-the-loop: Email approval before execution",
        "🛡️ 7-layer safety guardrails prevent harmful actions",
        "📊 Full observability: traces, metrics, audit trail",
        "",
        "MTTR: 30 min → 3 min | Cost: 60-90% AI savings via model routing",
    ], notes="Key selling point: combines AI intelligence with operational safety. "
             "Not fully autonomous — human approves before execution.")

    # =========================================================================
    # SLIDE 4: Architecture Diagram
    # =========================================================================
    add_content_slide(prs, "Architecture: End-to-End Flow", [
        "1️⃣  CloudWatch Alarm → SNS → Lambda → POST /webhook",
        "2️⃣  Storm Detection + Fleet Breaker (backpressure)",
        "3️⃣  Normalize → Enrich (asset context) → Match (playbook)",
        "4️⃣  If match: Email with 'Approve' button (Rule Mode)",
        "    If no match: Bedrock AI reasons → Email with suggestions (AI Mode)",
        "5️⃣  7 Guardrail Checks → Execute (Ansible via SSM)",
        "6️⃣  Baking Period → Verify fix → Record outcome",
        "",
        "All stages traced (OpenTelemetry → X-Ray) with incident_id correlation",
    ], notes="Walk through the flow step by step. Emphasize that each stage has "
             "failure handling and the pipeline never silently swallows errors.")

    # =========================================================================
    # SLIDE 5: Two Operating Modes
    # =========================================================================
    add_two_column_slide(
        prs,
        "Two Operating Modes",
        [
            "• Known alert pattern matched",
            "• Playbook exists (e.g. fix_high_cpu.yml)",
            "• Email: RCA + 'Approve' button",
            "• One click → Ansible executes fix",
            "• Automated verification post-fix",
            "",
            "Example: HighCPUUsage → kill stress-ng",
        ],
        [
            "• Unknown alert pattern",
            "• No matching playbook found",
            "• Bedrock AI analyzes the situation",
            "• Email: AI-generated suggestions",
            "• Operator resolves manually",
            "",
            "Example: NetworkFloodDetected → AI suggests",
        ],
        left_title="🔧 Rule Mode (Known Issues)",
        right_title="🧠 AI Agent Mode (Novel Issues)",
    )

    # =========================================================================
    # SLIDE 6: AI/LLM Integration
    # =========================================================================
    add_content_slide(prs, "AI Integration: Amazon Bedrock", [
        "🧠 Intelligent Model Router — Cost-optimized inference:",
        "    • SIMPLE (Nova Lite ~$0.0003): Known alerts, >90% success",
        "    • MODERATE (Nova Pro ~$0.001): Mixed history, P2",
        "    • COMPLEX (Claude Sonnet ~$0.003): Novel, P1, all-failed",
        "",
        "🔄 Auto-Escalation: If confidence < 0.5, re-invoke with next tier",
        "⛓️ Fallback Chain: Sonnet → Nova Pro → Haiku → Nova Lite → Rules",
        "📚 Context: Up to 50 historical incidents fed into prompt",
        "🛡️ Bedrock Guardrails: Native content filtering (defense-in-depth)",
        "",
        "Result: 60-90% cost reduction vs always using Claude Sonnet",
    ], notes="Explain the model routing decision tree. SIMPLE handles 70% of alerts "
             "at 10x cheaper cost. Only novel/P1 alerts hit the expensive model.")

    # =========================================================================
    # SLIDE 7: Safety & Guardrails
    # =========================================================================
    add_content_slide(prs, "7-Layer Safety Engine", [
        "① Self-Protection — Never targets AIOps infrastructure",
        "② Maintenance Window — Defers during scheduled maintenance",
        "③ Circuit Breaker — Blocks after repeated host failures",
        "④ Concurrency Guard — One remediation per host at a time",
        "⑤ Blast Radius Classifier — Risk classification (LOW→CRITICAL)",
        "⑥ Health Checker — Verifies target is reachable via SSM",
        "⑦ Approval Gate — Human approval for HIGH/CRITICAL risk",
        "⑧ Plan Validator — Blocks dangerous AI-generated commands",
        "",
        "Short-circuits on first DENY | 15s overall timeout = DENY",
    ], notes="This is the key differentiator from fully autonomous systems. "
             "Every remediation passes through all 7 checks. The engine is audited.")

    # =========================================================================
    # SLIDE 8: Infrastructure (CDK)
    # =========================================================================
    add_content_slide(prs, "AWS Infrastructure (6 CDK Stacks)", [
        "🌐 Network — VPC, 2 AZs, NAT GW, 7 VPC Endpoints",
        "💾 Data — DynamoDB (TTL, 3 GSIs), SQS+DLQ, ECR",
        "⚙️ Compute — ECS Fargate, API Gateway, Auto-Scaling",
        "👁️ Observability — Alarms, Dashboard, WAF, Synthetics, Budget",
        "📡 Monitoring — Amazon Managed Prometheus + ADOT Collector",
        "🎯 Simulation — EC2 target, break/fix SSM docs, alert Lambdas",
        "",
        "Environment-driven: dev ($200/mo) | staging ($500) | prod ($2000)",
        "Deploy: npx aws-cdk@2 deploy --all --context environment=dev",
    ], notes="Explain the stack ordering dependency: Network → Data → Compute → Observability. "
             "All infra is IaC, no manual console clicks.")

    # =========================================================================
    # SLIDE 9: Resilience Features
    # =========================================================================
    add_two_column_slide(
        prs,
        "Resilience & Backpressure",
        [
            "• Storm Detector: Rate limit + grouping",
            "  50 alerts/min threshold",
            "  Groups by (alert+service)",
            "  HTTP 429 when overloaded",
            "",
            "• Graceful Shutdown:",
            "  25s drain period",
            "  Release DynamoDB locks",
            "  SIGHUP config reload",
        ],
        [
            "• Fleet Circuit Breaker:",
            "  5 failures/5min → HALT ALL",
            "  10min cooldown",
            "  Adaptive ramp-up recovery",
            "  (1→2→4→8→max concurrent)",
            "",
            "• Human-in-the-Loop:",
            "  HMAC-signed tokens (30min)",
            "  DynamoDB persistence",
            "  Anti-link-scanner (GET→POST)",
        ],
        left_title="🌊 Backpressure",
        right_title="🔒 Safety",
    )

    # =========================================================================
    # SLIDE 10: Demo Plan
    # =========================================================================
    add_content_slide(prs, "Live Demo Plan (10 min)", [
        "DEMO 1 — Rule Mode (5 min):",
        "  ① Run: python demo/break_target.py --mode cpu --duration 600",
        "  ② Watch: CloudWatch detects CPU > 80% → alarm fires",
        "  ③ Show: Email arrives with RCA + 'Approve' button",
        "  ④ Click approve → Ansible kills stress-ng → CPU drops",
        "  ⑤ Show: Audit log, metrics, incident in DynamoDB",
        "",
        "DEMO 2 — AI Mode (5 min):",
        "  ① Invoke: aws lambda invoke --function-name aiops-network-alert-dev",
        "  ② Show: No matching playbook → AI Agent Mode activates",
        "  ③ Show: Bedrock Nova Pro generates analysis + suggestions",
        "  ④ Show: Email with AI-generated remediation steps",
        "  ⑤ Discuss: Model routing decision, cost, confidence",
    ], notes="Rule Mode demo takes ~3 min for alarm to fire. Use pre-recorded backup "
             "if timing is tight. AI Mode is instant (Lambda direct invoke).")

    # =========================================================================
    # SLIDE 11: Key Metrics & Results
    # =========================================================================
    add_content_slide(prs, "Results & Impact", [
        "📉 MTTR Reduction: 30 min → 3 min (90% faster)",
        "💰 AI Cost: 60-90% reduction via intelligent model routing",
        "🛡️ Safety: 0 unintended actions (7-layer guardrails)",
        "📊 Coverage: 7 alert types auto-remediable (expandable)",
        "🔍 Observability: Full trace from alert to remediation",
        "⚡ Throughput: 50 concurrent pipelines, 10 concurrent executions",
        "🌊 Storm Resilient: Handles 50+ alerts/min without degradation",
        "",
        "Test Coverage: >80% (unit + property-based + CDK assertion)",
    ], notes="These are projected/measured metrics. MTTR assumes operator "
             "clicks approve within 1 minute of receiving email.")

    # =========================================================================
    # SLIDE 12: Future Roadmap
    # =========================================================================
    add_content_slide(prs, "Roadmap & Next Steps", [
        "🔜 Phase 2:",
        "  • Auto-approve for LOW risk + high-confidence patterns",
        "  • Slack integration (in addition to email)",
        "  • Multi-step remediation plans from AI",
        "",
        "🔮 Phase 3:",
        "  • Predictive alerting (before incidents happen)",
        "  • Cross-service correlation (graph-based root cause)",
        "  • Self-learning playbook generation from AI outcomes",
        "  • Integration with PagerDuty/ServiceNow/Jira",
    ], notes="Phase 2 focuses on reducing human friction for well-known patterns. "
             "Phase 3 moves toward predictive and proactive healing.")

    # =========================================================================
    # SLIDE 13: Thank You
    # =========================================================================
    add_title_slide(
        prs,
        "Thank You",
        "Questions?\n\n"
        "GitHub: aiops-production-automation-ansible-agentic\n"
        "Contact: ravindya@in.ibm.com\n\n"
        "\"Infrastructure that heals itself — with humans in the loop.\""
    )

    # Save
    output_path = "docs/AIOps-Self-Healing-Infrastructure-Presentation.pptx"
    prs.save(output_path)
    print(f"Presentation saved to: {output_path}")
    print(f"Total slides: {len(prs.slides)}")


if __name__ == "__main__":
    main()
