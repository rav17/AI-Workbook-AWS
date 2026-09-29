"""Rebuild PPTX with LESS content per slide so text fits within the slide area."""

from pptx import Presentation
from pptx.util import Pt, Emu
from pptx.dml.color import RGBColor
from pptx.oxml.ns import qn
from lxml import etree
import os

BASE = os.path.dirname(os.path.abspath(__file__))
template_path = os.path.join(BASE, "Communication Sector Summit 2026_paper_presentation_submission_template.pptx")
output_path = os.path.join(BASE, "Energy_Utilities_IT_Final.pptx")

prs = Presentation(template_path)

# Content area below header — constrained to stay within slide
CONTENT_TOP = Emu(int(1.2 * 914400))
CONTENT_LEFT = Emu(int(0.6 * 914400))
CONTENT_WIDTH = Emu(int(10.2 * 914400))
CONTENT_HEIGHT = Emu(int(5.7 * 914400))  # Reduced to avoid overflow

DARK = RGBColor(0x1A, 0x1A, 0x2E)
GRAY = RGBColor(0x55, 0x55, 0x55)
BODY = RGBColor(0x33, 0x33, 0x33)


def setup_slide(idx):
    slide = prs.slides[idx]
    shape = slide.shapes[1]
    shape.top = CONTENT_TOP
    shape.left = CONTENT_LEFT
    shape.width = CONTENT_WIDTH
    shape.height = CONTENT_HEIGHT
    tf = shape.text_frame
    tf.clear()
    tf.word_wrap = True
    txBody = tf._txBody
    bodyPr = txBody.find(qn("a:bodyPr"))
    if bodyPr is not None:
        for child in list(bodyPr):
            if child.tag in (qn("a:normAutofit"), qn("a:spAutoFit"), qn("a:noAutofit")):
                bodyPr.remove(child)
        etree.SubElement(bodyPr, qn("a:noAutofit"))
    return tf


def write(tf, lines):
    first = True
    for text, size, bold, italic, color in lines:
        if first:
            p = tf.paragraphs[0]
            first = False
        else:
            p = tf.add_paragraph()
        p.text = text
        if p.runs:
            r = p.runs[0]
            r.font.size = Pt(size)
            r.font.bold = bold
            r.font.italic = italic
            r.font.color.rgb = color


# ==========================================================
# SLIDE 1 — Problem (max 10 lines, 16-18pt body)
# ==========================================================
tf = setup_slide(0)
write(tf, [
    ("When Your Billing System Crashes at 3 AM, Who Fixes It?", 26, True, False, DARK),
    ("", 10, False, False, BODY),
    ("Energy & utilities IT: billing, portals, meter data, ERP.", 16, False, False, BODY),
    ("When it breaks: engineer paged \u2192 VPN \u2192 diagnose \u2192 fix. 15\u201345 min.", 16, False, False, BODY),
    ("", 8, False, False, BODY),
    ("\u2022  200\u2013400 alerts/day \u2014 1,000+ during billing cycles", 15, False, False, BODY),
    ("\u2022  25\u201340 min MTTR for routine issues", 15, False, False, BODY),
    ("\u2022  23% of outages extended by incorrect manual fixes", 15, False, False, BODY),
    ("\u2022  60%+ alerts are repetitive \u2014 same issue, same fix", 15, False, False, BODY),
    ("\u2022  Alert fatigue: engineers ignore alerts after 20+ in shift", 15, False, False, BODY),
    ("", 10, False, False, BODY),
    ("What if IT infrastructure could fix routine problems itself?", 18, True, True, DARK),
])

# ==========================================================
# SLIDE 2 — Solution (max 12 lines, compact)
# ==========================================================
tf = setup_slide(1)
write(tf, [
    ("AI-Powered Self-Healing IT Infrastructure", 26, True, False, DARK),
    ("Fixes problems before business users notice", 14, False, True, GRAY),
    ("", 8, False, False, BODY),
    ("1. DETECT \u2014 CloudWatch alarm in <60s", 15, False, False, BODY),
    ("2. UNDERSTAND \u2014 Enrich: app, team, customers, dependencies", 15, False, False, BODY),
    ("3. DECIDE \u2014 Known \u2192 playbook | New \u2192 AI (Bedrock)", 15, False, False, BODY),
    ("4. SAFETY \u2014 7-layer guardrails (short-circuit on DENY)", 15, False, False, BODY),
    ("5. APPROVE \u2014 Email + one-click approve (30-min expiry)", 15, False, False, BODY),
    ("6. HEAL \u2014 Ansible via SSM | Stop conditions monitor live", 15, False, False, BODY),
    ("7. VERIFY \u2014 Baking period confirms fix worked", 15, False, False, BODY),
    ("", 8, False, False, BODY),
    ("Alert \u2192 Resolution in under 3 minutes", 18, True, False, DARK),
    ("", 6, False, False, BODY),
    ("Bedrock (Nova/Claude) | Ansible+SSM | 7-Layer Safety | ECS Fargate", 12, False, False, GRAY),
])


# ==========================================================
# SLIDE 3 — Benefits (4 categories, 2 lines each max)
# ==========================================================
tf = setup_slide(2)
write(tf, [
    ("Why This Matters for Utility IT", 26, True, False, DARK),
    ("", 8, False, False, BODY),
    ("Business", 18, True, False, DARK),
    ("\u2022  80% MTTR reduction (25 min \u2192 3 min) | Fewer SLA breaches", 14, False, False, BODY),
    ("\u2022  24/7 coverage without headcount | Billing cycle protection", 14, False, False, BODY),
    ("", 6, False, False, BODY),
    ("Technical", 18, True, False, DARK),
    ("\u2022  60\u201390% AI cost savings via intelligent model routing", 14, False, False, BODY),
    ("\u2022  Zero SSH keys | Self-improving effectiveness scorer", 14, False, False, BODY),
    ("", 6, False, False, BODY),
    ("Operational Safety", 18, True, False, DARK),
    ("\u2022  7 guardrails + fleet breaker + stop conditions", 14, False, False, BODY),
    ("\u2022  Storm: 1,000 alerts \u2192 ~20 actions | DBs never auto-remediated", 14, False, False, BODY),
    ("", 6, False, False, BODY),
    ("Compliance", 18, True, False, DARK),
    ("\u2022  Full DynamoDB audit trail | SOX-ready | Change mgmt compatible", 14, False, False, BODY),
    ("\u2022  HMAC-signed tokens | Exactly-once execution | 30-min expiry", 14, False, False, BODY),
])

# ==========================================================
# SLIDE 4 — Architecture & Roadmap (compact)
# ==========================================================
tf = setup_slide(3)
write(tf, [
    ("Architecture & Roadmap", 26, True, False, DARK),
    ("", 6, False, False, BODY),
    ("AWS Architecture (6 CDK Stacks)", 16, True, False, DARK),
    ("VPC+Endpoints | ECS Fargate | DynamoDB+SQS | API GW+WAF | Bedrock | SSM", 13, False, False, BODY),
    ("", 6, False, False, BODY),
    ("Implemented Today", 16, True, False, DARK),
    ("\u2713  Full 7-step pipeline with AI reasoning + human approval", 13, False, False, BODY),
    ("\u2713  3-tier model routing + 4-model fallback chain", 13, False, False, BODY),
    ("\u2713  7-layer safety + fleet breaker + stop conditions + baking", 13, False, False, BODY),
    ("\u2713  12 YAML configs | OpenTelemetry tracing | CI/CD + auto-rollback", 13, False, False, BODY),
    ("", 6, False, False, BODY),
    ("Next (Q3\u2013Q4 2026)", 16, True, False, DARK),
    ("\u2192  ServiceNow/BMC | Predictive alerting | AI-generated runbooks", 13, False, False, BODY),
    ("\u2192  Teams/Slack approval | Multi-cloud support", 13, False, False, BODY),
    ("", 6, False, False, BODY),
    ("Vision: 10 engineers managing what used to need 40.", 15, False, True, DARK),
    ("IT shifts from firefighting \u2192 digital transformation.", 15, False, True, BODY),
    ("", 8, False, False, BODY),
    ("Ravindra Yadav  |  ravindya@in.ibm.com  |  IBM", 12, True, False, GRAY),
])

prs.save(output_path)
print(f"PPTX saved: {output_path}")


# ==========================================================
# ADD SPEAKER NOTES (using direct XML for reliability)
# ==========================================================
notes_text = [
    "TALKING POINTS:\n\nOpen with story: 3:14 AM, billing cycle, meter data server 95% CPU. Engineer wakes, VPNs in, 20 min diagnosing routine issue fixed 12 times before.\n\nKey stats: 200-400 alerts/day typical. 25-40 min MTTR. 23% of outages caused by fix itself. 60%+ repetitive. Alert fatigue after 20+ per shift.\n\nTransition: What if infrastructure could fix routine problems itself with human oversight?",

    "TALKING POINTS:\n\nWalk through 7 steps:\n1. DETECT: CloudWatch, alarm in 60s.\n2. UNDERSTAND: Enrich - host, service, owner, impact.\n3. DECIDE: Known=playbook. New=Bedrock AI. Router: 70% Nova Lite $0.0003, 20% Nova Pro $0.001, 10% Claude $0.003. Saves 60-90%.\n4. SAFETY: 7 guardrails short-circuit. Plan validator blocks dangerous commands.\n5. APPROVE: HMAC-signed, 30-min expiry, two-step prevents scanner auto-approval.\n6. HEAL: SSM no SSH. Stop conditions poll 10s. Fleet breaker halts if 5+ failures.\n7. VERIFY: Baking period. Outcome feeds back.\n\nKey: Under 3 minutes for known problems.",

    "TALKING POINTS:\n\nBusiness: MTTR 25 to 3 min. 24/7 without headcount. Billing cycle protection.\n\nTechnical: 70% alerts use Nova Lite (10x cheaper). SSM no bastion. Effectiveness scorer tracks what works.\n\nSafety: 7 guardrails short-circuit. Fleet breaker 5 failures = pause all. Storm: 1000 alerts to 20. Inhibition: DatabaseDown suppresses APITimeout.\n\nCompliance: Full audit trail. Conditional writes = exactly-once. Structured logging with incident_id.",

    "TALKING POINTS:\n\nArchitecture: 6 CDK stacks. ECS Fargate serverless. VPC endpoints. $150/month at rest.\n\nImplemented: NOT a POC. CI/CD health gates auto-rollback. 3-tier routing + 4-model fallback. 12 YAML files. OpenTelemetry tracing.\n\nRoadmap: ServiceNow. Predictive alerting. AI-generated runbooks.\n\nClose: 10 engineers managing what used to need 40. IT shifts from firefighting to digital transformation."
]

for i, slide in enumerate(prs.slides):
    ns = slide.notes_slide
    body = ns.notes_text_frame._txBody
    # Remove existing paragraphs
    for p_elem in body.findall(qn("a:p")):
        body.remove(p_elem)
    # Add notes as paragraphs
    for line in notes_text[i].split("\n"):
        p_elem = etree.SubElement(body, qn("a:p"))
        r_elem = etree.SubElement(p_elem, qn("a:r"))
        t_elem = etree.SubElement(r_elem, qn("a:t"))
        t_elem.text = line

prs.save(output_path)
print("Speaker notes added.")
print("Done!")
