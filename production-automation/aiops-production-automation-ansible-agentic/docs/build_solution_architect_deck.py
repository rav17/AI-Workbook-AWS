"""Build the Solution Architect deck: docs/AIOps-Solution-Architect-Deck.pptx.

Usage:
    python docs/build_solution_architect_deck.py

Requires python-pptx. Uses architecture/aiops-self-healing-architecture.png
(export it from the .drawio file first: draw.io -x -f png --crop --scale 1.6).
"""

from __future__ import annotations

import os

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.util import Inches, Pt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIAGRAM = os.path.join(ROOT, "architecture", "aiops-self-healing-architecture.png")
OUT = os.path.join(ROOT, "docs", "AIOps-Solution-Architect-Deck.pptx")

NAVY = RGBColor(0x23, 0x2F, 0x3E)
ORANGE = RGBColor(0xED, 0x71, 0x00)
TEAL = RGBColor(0x01, 0xA8, 0x8D)
GRAY = RGBColor(0x5F, 0x6B, 0x7A)
LIGHT = RGBColor(0xF2, 0xF4, 0xF7)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
RED = RGBColor(0xDD, 0x34, 0x4C)

prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)
BLANK = prs.slide_layouts[6]


def _text(tf, lines, size=16, color=NAVY, bold_first=False, space=6):
    """Fill a text frame. Lines starting with '- ' become bullets."""
    tf.word_wrap = True
    for n, line in enumerate(lines):
        p = tf.paragraphs[0] if n == 0 else tf.add_paragraph()
        bullet = line.startswith("- ")
        run = p.add_run()
        run.text = ("\u2022 " + line[2:]) if bullet else line
        run.font.size = Pt(size + 2)
        run.font.color.rgb = color
        run.font.bold = bold_first and n == 0
        p.space_after = Pt(space)


def slide(title: str, subtitle: str = "", notes: str = ""):
    """Create a content slide with a title bar."""
    s = prs.slides.add_slide(BLANK)
    bar = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, Inches(1.0))
    bar.fill.solid()
    bar.fill.fore_color.rgb = NAVY
    bar.line.fill.background()
    accent = s.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, 0, Inches(1.0), prs.slide_width, Inches(0.06)
    )
    accent.fill.solid()
    accent.fill.fore_color.rgb = ORANGE
    accent.line.fill.background()
    tb = s.shapes.add_textbox(Inches(0.5), Inches(0.15), Inches(12.3), Inches(0.7))
    _text(tb.text_frame, [title], 28, WHITE)
    tb.text_frame.paragraphs[0].runs[0].font.bold = True
    if subtitle:
        st = s.shapes.add_textbox(Inches(0.5), Inches(1.15), Inches(12.3), Inches(0.5))
        _text(st.text_frame, [subtitle], 15, GRAY)
    if notes:
        s.notes_slide.notes_text_frame.text = notes
    return s


def bullets(s, lines, x=0.5, y=1.8, w=12.3, h=5.2, size=17):
    """Add a bullet list."""
    tb = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    _text(tb.text_frame, lines, size)
    return tb


def card(s, x, y, w, h, head, lines, color=ORANGE, size=13):
    """Add a titled card."""
    box = s.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h)
    )
    box.fill.solid()
    box.fill.fore_color.rgb = LIGHT
    box.line.color.rgb = color
    box.line.width = Pt(1.5)
    box.adjustments[0] = 0.05
    hd = s.shapes.add_textbox(
        Inches(x + 0.1), Inches(y + 0.08), Inches(w - 0.2), Inches(0.45)
    )
    _text(hd.text_frame, [head], 15, color)
    hd.text_frame.paragraphs[0].runs[0].font.bold = True
    body = s.shapes.add_textbox(
        Inches(x + 0.1), Inches(y + 0.55), Inches(w - 0.2), Inches(h - 0.6)
    )
    _text(body.text_frame, lines, size + 3, NAVY, space=5)


def table(s, x, y, w, rows, col_w, size=12, row_h=0.42):
    """Add a table; first row is the header."""
    shape = s.shapes.add_table(
        len(rows),
        len(rows[0]),
        Inches(x),
        Inches(y),
        Inches(w),
        Inches(row_h * len(rows)),
    )
    t = shape.table
    for c, cw in enumerate(col_w):
        t.columns[c].width = Inches(cw)
    for r, row in enumerate(rows):
        for c, val in enumerate(row):
            cell = t.cell(r, c)
            cell.text = val
            for p in cell.text_frame.paragraphs:
                for run in p.runs:
                    run.font.size = Pt(size + 2)
                    run.font.bold = r == 0
                    run.font.color.rgb = WHITE if r == 0 else NAVY
            cell.fill.solid()
            cell.fill.fore_color.rgb = NAVY if r == 0 else (LIGHT if r % 2 else WHITE)


# 1 ---------------------------------------------------------------- title
s = prs.slides.add_slide(BLANK)
bg = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height)
bg.fill.solid()
bg.fill.fore_color.rgb = NAVY
bg.line.fill.background()
strip = s.shapes.add_shape(
    MSO_SHAPE.RECTANGLE, Inches(0.6), Inches(3.55), Inches(2.2), Inches(0.08)
)
strip.fill.solid()
strip.fill.fore_color.rgb = ORANGE
strip.line.fill.background()
tb = s.shapes.add_textbox(Inches(0.6), Inches(1.7), Inches(12), Inches(1.8))
_text(
    tb.text_frame,
    ["AIOps Self-Healing Infrastructure", "with AWS DevOps Agent"],
    40,
    WHITE,
)
for p in tb.text_frame.paragraphs:
    p.runs[0].font.bold = True
tb2 = s.shapes.add_textbox(Inches(0.6), Inches(3.8), Inches(12), Inches(1.5))
_text(
    tb2.text_frame,
    [
        "Solution architecture for review",
        "Alert in, safe remediation out, root cause analysis by email",
    ],
    20,
    WHITE,
)
s.notes_slide.notes_text_frame.text = (
    "Audience: solution architects. Goal: explain the design, the trade-offs and what is verified "
    "versus planned. The live demo follows the deck (see demo/DEMO-RUNBOOK.md)."
)

# 2 ---------------------------------------------------------------- problem
s = slide(
    "The problem and our goal",
    "Why the on-call loop is slow and risky today",
    "Frame the problem in operations terms: alert fatigue, slow diagnosis, risky manual fixes.",
)
card(
    s,
    0.5,
    1.8,
    6.0,
    3.8,
    "Today",
    [
        "- An alert fires; a human reads it, finds the host and picks a fix",
        "- Diagnosis of unfamiliar alerts takes the longest",
        "- Manual fixes on production hosts carry blast-radius risk",
        "- Knowledge of what worked before sits in people's heads",
    ],
    RED,
)
card(
    s,
    6.8,
    1.8,
    6.0,
    3.8,
    "Goal",
    [
        "- Known problems: propose a vetted playbook, run it after approval",
        "- Unknown problems: DevOps Agent finds the root cause; AI suggests a playbook",
        "- Every change passes guardrails and a human approval gate",
        "- The operator gets one email with the root cause, the plan and the fix",
    ],
    TEAL,
)
bullets(
    s,
    [
        "Design principle: the AI investigates and advises; only our pipeline changes hosts, "
        "and only after validation and approval."
    ],
    y=5.8,
    size=18,
)

# 3 ---------------------------------------------------------------- overview
s = slide(
    "Solution overview",
    "Three paths from one alert",
    "Walk the three outcomes. Rule mode is fast and deterministic; advisory mode handles unknowns "
    "with DevOps Agent's root cause plus a Bedrock playbook suggestion; critical alerts also get an RCA.",
)
card(
    s,
    0.5,
    1.8,
    4.0,
    4.2,
    "Rule mode",
    [
        "Alert matches a playbook in config/playbook_mapping.yml",
        "- Guardrails check blast radius, circuit breaker, maintenance window",
        "- Approval email with a signed, single-use link",
        "- On approval, SSM runs the fix on the target",
    ],
    ORANGE,
)
card(
    s,
    4.65,
    1.8,
    4.0,
    4.2,
    "Advisory mode",
    [
        "No playbook matches",
        "- DevOps Agent investigates: root cause and mitigation plan",
        "- Bedrock picks a catalog playbook or drafts a new one",
        "- One advisory email; nothing runs automatically",
        "- Flag off or not forwarded: ECS sends a Bedrock advisory",
    ],
    RGBColor(0xE7, 0x15, 0x7B),
)
card(
    s,
    8.8,
    1.8,
    4.0,
    4.2,
    "DevOps Agent (RCA)",
    [
        "Critical, unmatched or failed incidents",
        "- HMAC webhook starts an investigation",
        "- Read-only access to the AWS account",
        "- EventBridge and a Lambda email the RCA (or the advisory for unmatched)",
    ],
    TEAL,
)
bullets(
    s,
    [
        "Critical alerts take the rule path and the DevOps Agent path in parallel. "
        "Advisory mode is opt-in: devopsAgentAdvisoryEnabled."
    ],
    y=6.3,
    size=16,
)

# 4 ---------------------------------------------------------------- diagram
s = prs.slides.add_slide(BLANK)
if os.path.exists(DIAGRAM):
    pic = s.shapes.add_picture(DIAGRAM, 0, 0, height=prs.slide_height)
    pic.left = int((prs.slide_width - pic.width) / 2)
s.notes_slide.notes_text_frame.text = (
    "Walk left to right. Lanes 1-3: how alerts arrive and are secured. Lane 4: the pipeline in ECS. "
    "Lane 5: state, queue, AI and email. Row 2: remediation target and the DevOps Agent RCA path. "
    "Lane 8: the operator. The editable source is architecture/aiops-self-healing-architecture.drawio."
)

# 5 ---------------------------------------------------------------- pipeline
s = slide(
    "Pipeline inside ECS Fargate",
    "Seven stages, each emitting a span and structured logs with incident_id",
    "Emphasise ordering: deduplicate before any cost is incurred; guardrails before approval.",
)
table(
    s,
    0.5,
    1.8,
    12.3,
    [
        ["Stage", "What it does", "State or dependency"],
        [
            "1 Normalize + dedup",
            "Alertmanager payload to internal model; fingerprint de-duplication; storm detector",
            "DynamoDB (TTL)",
        ],
        [
            "2 Enrich",
            "Asset inventory lookup; sensitive labels redacted before storage",
            "config/asset_inventory.yml",
        ],
        [
            "3 Rule match",
            "Alert name and service to playbook",
            "config/playbook_mapping.yml",
        ],
        [
            "4 Guardrails",
            "Self-protection, maintenance window, circuit breaker, blast radius, approval gate, "
            "plan validator",
            "config/*.yml",
        ],
        [
            "5 AI reasoning",
            "No rule matched and advisory mode off (or not forwarded); model tier by history",
            "Amazon Bedrock",
        ],
        [
            "6 Approve + execute",
            "Signed single-use token; SSM RunCommand. Alert clears first: cancel, free the dedup lock",
            "SES, SSM, DynamoDB",
        ],
        [
            "7 DevOps Agent",
            "Forward critical, unmatched and failed incidents; never blocks the pipeline",
            "Secrets Manager (webhook)",
        ],
    ],
    [2.4, 7.0, 2.9],
    12,
)

# 5b --------------------------------------------------------------- config (active)
s = slide(
    "Configuration files (1 of 2): routing and guardrails",
    "config/*.yml, all loaded by the running service. Behaviour changes by editing YAML, not code.",
    "These eight files drive decisions in the pipeline. Safety rules live in config so they can be "
    "reviewed and versioned like code.",
)
table(
    s,
    0.5,
    1.7,
    12.3,
    [
        ["File", "Purpose", "Used by"],
        [
            "playbook_mapping.yml",
            "Maps alert name (and optional service) to a playbook; first match wins. "
            "No match sends the alert to AI mode.",
            "PlaybookMapper",
        ],
        [
            "asset_inventory.yml",
            "Host metadata: hostname, IP, zone, service name, owner, lookup keys. "
            "Unknown hosts log 'No matching asset found'.",
            "Enricher",
        ],
        [
            "protected_hosts.yml",
            "Hosts automation must never target: controllers, Vault, Consul, "
            "Prometheus, Grafana.",
            "Self-protection guardrail",
        ],
        [
            "maintenance_windows.yml",
            "Recurring windows (global or per service) when remediation is "
            "deferred.",
            "Maintenance window guardrail",
        ],
        [
            "risk_classification.yml",
            "Blast-radius rules: single-instance and database services are "
            "critical; service and action patterns map to low through critical.",
            "Blast radius classifier",
        ],
        [
            "denied_commands.yml",
            "Regex patterns never allowed in AI-generated plans: rm -rf /, shutdown, "
            "dd, mkfs, firewall flush, curl piped to sh.",
            "PlanValidator",
        ],
        [
            "inhibition_rules.yml",
            "Suppress symptom alerts while a root-cause alert is active, for example "
            "DatabaseDown suppresses APITimeout.",
            "AlertInhibitor",
        ],
        [
            "stop_conditions.yml",
            "CloudWatch alarms watched during execution; any ALARM aborts the "
            "remediation.",
            "StopConditionsMonitor",
        ],
    ],
    [2.9, 6.7, 2.7],
    10,
)

# 5c --------------------------------------------------------------- config (not wired)
s = slide(
    "Configuration files (2 of 2): concurrency and dependencies",
    "Defined and tested, but not yet loaded by the running service",
    "Be direct: these four files exist and their modules are tested, but app.py does not load them yet. "
    "Today duplicate approvals are suppressed by ApprovalHandler; host-level locks are not enforced yet.",
)
table(
    s,
    0.5,
    1.8,
    12.3,
    [
        ["File", "Purpose", "Loader"],
        [
            "bulkhead_limits.yml",
            "Maximum concurrent executions per service group (database: 1, no overflow); "
            "global cap and reserved capacity for P1.",
            "concurrency/bulkhead.py",
        ],
        [
            "execution_dependencies.yaml",
            "Ordering between actions as a graph, for example drain connections, "
            "restart nginx, health check. Cycles are rejected; max 200 nodes, 500 edges.",
            "concurrency/dependency_graph.py",
        ],
        [
            "resource_conflicts.yaml",
            "Resources each action modifies and the conflict strategy: QUEUE, REJECT "
            "or PREEMPT (needs a severity gap of 2).",
            "concurrency/resource_registry.py",
        ],
        [
            "service_dependencies.yml",
            "Service dependency graph with criticality; unhealthy dependents raise "
            "the risk level.",
            "None yet (planned ServiceRegistry for the HealthChecker)",
        ],
    ],
    [2.9, 6.1, 3.3],
    10,
)
bullets(
    s,
    [
        "Active protection today: asyncio limits (50 pipelines, 10 executions per task), the fleet circuit breaker, storm detector and "
        "approval de-duplication. Wiring these four files in is the next hardening step.",
    ],
    x=0.5,
    y=5.4,
    w=12.3,
    h=1.4,
    size=15,
)

# 6 ---------------------------------------------------------------- AI design
s = slide(
    "AI design: cost-aware routing with safe fallbacks",
    "Amazon Bedrock via ModelRouter in ECS (advisory mode off). Advisory mode: see the advisory path slide.",
    "The point for architects: model choice is a cost and risk decision made per incident, "
    "and every failure mode degrades to something deterministic.",
)
table(
    s,
    0.5,
    1.8,
    6.3,
    [
        ["Tier", "When", "Model"],
        ["Simple", "Seen 5+ times, >=90% success, P3-P5", "Nova Lite"],
        ["Moderate", "Limited history, mixed outcomes, P2", "Nova Pro"],
        ["Complex", "P1, never seen, or all past fixes failed", "Claude Sonnet"],
    ],
    [1.3, 3.4, 1.6],
    12,
)
bullets(
    s,
    [
        "- History: same alert name in DynamoDB, decided outcomes only",
        "- Outcome from the operator's feedback link; pending advice is not counted",
        "- Alert resolving is recorded but not counted as success",
        "- Confidence below 0.5 escalates to the next tier",
        "- Plans need confidence of 0.7 (0.8 for P1) to be proposed",
        "- Prompt: stable cacheable prefix plus variable suffix; max output 2048 tokens",
    ],
    x=0.5,
    y=3.8,
    w=6.3,
    size=14,
)
card(
    s,
    7.1,
    1.8,
    5.7,
    5.2,
    "Failure handling",
    [
        "- 30 s timeout per invocation, 2 retries with backoff (1 s, 2 s)",
        "- Fallback chain: Claude Sonnet, Nova Pro, Claude Haiku, Nova Lite",
        "- All models fail: rule-based fallback (PlaybookMapper)",
        "- PlanValidator and config/denied_commands.yml block dangerous commands",
        "- Optional Bedrock Guardrails for content filtering",
        "- FallbackReason is recorded for observability",
    ],
    TEAL,
    14,
)

# 7 ---------------------------------------------------------------- DevOps agent
s = slide(
    "AWS DevOps Agent integration",
    "Investigation and advice only; our pipeline stays the only component that changes hosts",
    "Stress: DevOps Agent has read-only access and no write path into our systems. "
    "Forwarding is off unless the flag, URL and secret are all present.",
)
table(
    s,
    0.5,
    1.8,
    7.2,
    [
        ["Trigger", "When"],
        ["unmatched", "No playbook matched; in advisory mode it drives the advisory email"],
        ["critical", "Critical alert with a new approval request (after dedup)"],
        ["failed", "An approved remediation failed or raised an error"],
        ["resolved (opt-in)", "Off by default: no visible effect in the spike"],
    ],
    [1.9, 5.3],
    12,
)
card(
    s,
    8.0,
    1.8,
    4.8,
    3.2,
    "Controls",
    [
        "- Off unless enabled, https URL and secret set",
        "- 5 s timeout, 2 retries, never blocks",
        "- Per-task cap: 20 per hour; per-incident dedup",
        "- Redacted labels only; no secrets sent",
    ],
    ORANGE,
    13,
)
bullets(
    s,
    [
        "- Webhook authenticated with HMAC; secret lives in Secrets Manager (/aiops/{env}/devops-agent-webhook)",
        "- Agent Space roles trust only aidevops.amazonaws.com with SourceAccount and SourceArn conditions",
        "- Incident reference aiops-<incident_id>-<trigger> links the investigation back to our record",
    ],
    x=0.5,
    y=4.5,
    w=7.3,
    h=2.5,
    size=13,
)

# 8 ---------------------------------------------------------------- RCA flow
s = slide(
    "RCA email path (Phase 2)",
    "From finished investigation to the operator's inbox",
    "This is the path the demo shows. Idempotent because EventBridge delivers at least once.",
)
steps = [
    ("1", "Agent finishes", "Completed, Failed, Timed Out or Linked"),
    ("2", "EventBridge rule", "Default bus, source aws.aidevops"),
    ("3", "Findings Lambda", "GetBacklogTask, ListJournalRecords (tag-scoped IAM)"),
    (
        "4",
        "DynamoDB audit",
        "Conditional write: processing then sent; no summary text stored",
    ),
    ("5", "SES email", "Summary or explanation, HTML-escaped, cut at 6,000 characters"),
]
for n, (num, head, body) in enumerate(steps):
    card(s, 0.5 + n * 2.5, 1.9, 2.35, 2.6, f"{num}. {head}", [body], TEAL, 12)
bullets(
    s,
    [
        "- Only our incidents are emailed; manual investigations in the web app are ignored",
        "- Failed invocations retry, then land in a 14-day SQS DLQ; alarms in staging and prod",
        "- Bundles boto3 1.44.3 (the project pins 1.35.36, which has no devops-agent client)",
    ],
    y=4.9,
    size=15,
)

# 8b --------------------------------------------------------------- advisory path
s = slide(
    "Advisory path for alerts with no playbook (Phase 2b)",
    "Opt-in: devopsAgentAdvisoryEnabled. DevOps Agent finds the cause; Bedrock suggests the fix.",
    "The ECS task does not call Bedrock for these alerts. Everything happens in the findings Lambda "
    "after the investigation, so the advice is based on the real root cause.",
)
steps = [
    ("1", "Forward", "ECS sends the alert (unmatched) and skips its own Bedrock call"),
    ("2", "Investigate", "DevOps Agent: root cause and inline mitigation plan"),
    (
        "3",
        "Collect",
        "Lambda reads the summary and mitigation_summary_md; requests a plan if missing",
    ),
    (
        "4",
        "Recommend",
        "Bedrock Converse: a catalog playbook, or a drafted one; one repair round if rejected",
    ),
    ("5", "Email", "[CRITICAL] <alert> on <host> - AI Analysis & Suggested Steps"),
]
for n, (num, head, body) in enumerate(steps):
    card(s, 0.5 + n * 2.5, 1.9, 2.35, 2.4, f"{num}. {head}", [body], RGBColor(0xE7, 0x15, 0x7B), 12)
card(
    s,
    0.5,
    4.5,
    6.0,
    2.75,
    "Checks on a drafted playbook",
    [
        "- Must be a play with hosts and tasks; only shell, command, systemd",
        "- No Jinja, no aws CLI, nothing on the denied-command list",
        "- Never reuses an existing playbook name; shown for review, never run",
    ],
    TEAL,
    12,
)
card(
    s,
    6.8,
    4.5,
    6.0,
    2.75,
    "Degrades safely",
    [
        "- Not forwarded (off, capped, error): ECS sends the Bedrock advisory",
        "- No plan, request denied, Bedrock down: the email says what is missing",
        "- One advisory per summary record; a re-run after a link gets its own",
    ],
    ORANGE,
    12,
)

# 9 ---------------------------------------------------------------- security
s = slide(
    "Security model",
    "Least privilege, private networking, no standing secrets in code",
    "Cover the main review questions: network exposure, secrets, IAM scope, input trust.",
)
card(
    s,
    0.5,
    1.8,
    4.0,
    4.6,
    "Network and API",
    [
        "- ECS tasks in private subnets, no public IP",
        "- VPC endpoints for AWS APIs",
        "- WAF on API Gateway: rate limit, size limit, managed rules",
        "- Pydantic validation, 1 MB payload limit",
        "- Approval is two-step: GET shows, POST executes (link scanners cannot approve)",
    ],
    RED,
    13,
)
card(
    s,
    4.65,
    1.8,
    4.0,
    4.6,
    "Identity and secrets",
    [
        "- Secrets Manager with rotation; ecs.Secret, never plain env",
        "- Approval tokens: single-use, atomic conditional write",
        "- IAM scoped to ARNs and tags; documented wildcards only where AWS requires",
        "- Findings Lambda: tag-scoped Agent Space access; its one write asks for a mitigation plan",
    ],
    ORANGE,
    13,
)
card(
    s,
    8.8,
    1.8,
    4.0,
    4.6,
    "Data and untrusted input",
    [
        "- Sensitive labels dropped before storage and forwarding",
        "- Alert text stripped of control characters and truncated",
        "- Agent summaries HTML-escaped, never rendered as links",
        "- Agent text in prompts is bounded and its section tags removed",
        "- Logs record lengths, not text; audit has metadata only",
    ],
    TEAL,
    13,
)

# 10 --------------------------------------------------------------- reliability
s = slide(
    "Reliability and operations",
    "Idempotent, bounded and observable",
    "Architects care about failure modes. Name each mechanism and what it protects.",
)
table(
    s,
    0.5,
    1.8,
    12.3,
    [
        ["Concern", "Mechanism"],
        [
            "Duplicate alerts",
            "Fingerprint dedup in DynamoDB with TTL; SQS processed idempotently by incident_id",
        ],
        [
            "Conflicting fixes",
            "One pending approval per alert, host and playbook (lock freed if the alert clears first); "
            "50 pipelines and 10 executions per task (host locks not wired yet)",
        ],
        [
            "Overload",
            "Storm detector groups alerts; fleet circuit breaker; HTTP 429 so Alertmanager retries",
        ],
        ["Poison messages", "SQS DLQ after 3 receives; visibility timeout 300 s"],
        [
            "Dependency failure",
            "Timeouts, retries and fallbacks on Bedrock, SQS, DynamoDB; graceful degradation",
        ],
        [
            "Visibility",
            "JSON logs with incident_id; CloudWatch metrics (AIOps/{env}); alarms and dashboards",
        ],
        [
            "Tracing",
            "OpenTelemetry spans per stage; tracing failures never block the pipeline",
        ],
    ],
    [2.6, 9.7],
    12,
)

# 11 --------------------------------------------------------------- delivery
s = slide(
    "Deployment and environments",
    "Infrastructure as code with one command up and down",
    "One stack per concern. The aiops_env.py script wires the parts CloudFormation cannot create.",
)
table(
    s,
    0.5,
    1.8,
    6.4,
    [
        ["CDK stack", "Contents"],
        ["Network", "VPC, NAT, VPC endpoints"],
        ["Data", "DynamoDB, SQS and DLQ, ECR"],
        ["Compute", "ECS Fargate, API Gateway, Cloud Map, secrets"],
        ["Observability", "Alarms, SNS, budgets, DevOps Agent findings"],
        ["Monitoring", "Dashboards"],
        ["Simulation", "2 EC2 targets, CPU/memory/network alarms, CloudWatch agent, Lambdas"],
    ],
    [1.8, 4.6],
    12,
)
bullets(
    s,
    [
        "- scripts/aiops_env.py up|down|status builds the image in CodeBuild, deploys all stacks, creates the "
        "Agent Space, roles and webhook, and checks /health; up --advisory turns on advisory mode",
        "- Environments by CDK context: dev, staging, prod (prod: 2 NATs, PITR, backups, termination protection)",
        "- CI: ruff, unit and property tests, CDK synth and assertions, image scan",
        "- CD: approval gate for prod, health gate, automatic rollback from the stored manifest",
    ],
    x=7.1,
    y=1.8,
    w=5.7,
    h=5,
    size=13,
)

# 12 --------------------------------------------------------------- cost
s = slide(
    "Cost profile",
    "Pay per incident, not per host",
    "Numbers come from the docs and the spike; treat them as estimates.",
)
table(
    s,
    0.5,
    1.8,
    12.3,
    [
        ["Item", "Cost driver", "Estimate"],
        [
            "Bedrock",
            "Per invocation, by tier; advisory mode adds 1 or 2 calls per unmatched incident",
            "Nova Lite ~$0.0003, Nova Pro ~$0.001, Claude Sonnet ~$0.003",
        ],
        [
            "DevOps Agent",
            "Billed per active agent-second (~$0.0083/s)",
            "74 to 105 s per investigation: ~$0.60 to $0.90",
        ],
        [
            "Guard rails on spend",
            "Per-task cap 20 per hour; AWS Budget filtered on DevOps Agent",
            "Fleet maximum = cap x task count",
        ],
        ["Environment", "dev: 1 NAT; prod: 2 NATs", "Tear down with aiops_env.py down"],
    ],
    [2.4, 5.2, 4.7],
    12,
)
bullets(
    s,
    [
        "Standing cost is the NAT gateway, ECS task and interface endpoints. Everything else scales "
        "with incident volume."
    ],
    y=4.6,
    size=16,
)

# 13 --------------------------------------------------------------- status
s = slide(
    "Verified status, limits and roadmap",
    "What is proven, what is not",
    "Be direct about gaps. Architects trust a design that states its limits.",
)
card(
    s,
    0.5,
    1.8,
    6.0,
    4.9,
    "Verified",
    [
        "- Webhook forwarding and the RCA email path in dev (2026-11-10 and 11-18)",
        "- Advisory mode end to end (2026-11-21): root cause, mitigation plan and a drafted playbook in one email",
        "- Approval lock freed on auto-cancel (2026-11-22): a recurrence 7 minutes later got its own approval",
        "- Guardrail engine starts with 6 checks; refuses to start if init fails",
        "- Tag-scoped IAM works for the findings Lambda",
    ],
    TEAL,
    13,
)
card(
    s,
    6.8,
    1.8,
    6.0,
    4.9,
    "Limits and next steps",
    [
        "- concurrency_guard and health_checker are not active yet (no backing implementation)",
        "- Drafted playbooks are advice; the executor cannot yet run a fix on another host",
        "- Requesting a mitigation plan not seen live: plans were always inline",
        "- devopsAgentAdvisoryEnabled is not wired into cd.yml yet",
        "- Claude Sonnet needs a Marketplace subscription; until then Nova Pro answers",
        "- Phase 3: MCP server for incident history, agent skills from runbooks, topology-based inventory",
    ],
    RED,
    12,
)

# 13b -------------------------------------------------------------- live validation
s = slide(
    "Live validation: P1 incident to RCA email",
    "Dev environment, 2026-11-18, us-east-1",
    "This run used demo/trigger_p1_incident.py against a freshly deployed environment.",
)
table(
    s,
    0.5,
    1.8,
    7.4,
    [
        ["UTC", "Event"],
        ["06:36:33", "CPU and memory load started on the target (SSM)"],
        [
            "06:37:15",
            "Critical alert accepted (HTTP 200); investigation created, priority CRITICAL",
        ],
        [
            "06:37:26",
            "Simulation alarm NetworkFloodDetected; linked to the same investigation",
        ],
        ["06:41:29", "Simulation alarm HighCPUUsage; linked"],
        [
            "06:42:49",
            "Investigation COMPLETED (about 5.5 min), 5,684-character summary",
        ],
        ["06:42:50", "RCA email sent through SES; audit record status sent; DLQ 0"],
    ],
    [1.3, 6.1],
    11,
)
card(
    s,
    8.2,
    1.8,
    4.6,
    4.6,
    "What the agent found",
    [
        "- Both vCPUs saturated by stress-ng workers (about 65% each)",
        "- Memory 67 MB free of 916 MB, no swap",
        "- Traced the cause to the SSM commands in CloudTrail and to the Simulation stack",
        "- Reported it as deliberate demo fault injection",
    ],
    TEAL,
    12,
)
bullets(
    s,
    [
        "Three events matched the EventBridge rule and invoked the Lambda three times: "
        "one RCA email and two short Linked notices."
    ],
    x=0.5,
    y=5.2,
    w=7.4,
    h=1.5,
    size=14,
)

# 13c -------------------------------------------------------------- advisory validation
s = slide(
    "Live validation: no-playbook alert to advisory email",
    "Dev environment, 2026-11-21, us-east-1, advisory mode on",
    "This run used demo/trigger_p1_incident.py. The NetworkFloodDetected alert has no playbook.",
)
table(
    s,
    0.5,
    1.8,
    7.4,
    [
        ["UTC", "Event"],
        ["10:59:14", "NetworkFloodDetected forwarded (unmatched); ECS skips its Bedrock call"],
        ["11:03:50", "Investigation COMPLETED with an inline mitigation plan"],
        [
            "11:03:58",
            "Lambda: plan found; Nova Pro drafts playbooks/stop_network_flood.yml (0.9)",
        ],
        ["11:03:58", "One advisory email: fix, drafted playbook, root cause, mitigation plan"],
    ],
    [1.3, 6.1],
    11,
)
card(
    s,
    8.2,
    1.8,
    4.6,
    4.9,
    "Found and fixed on the way",
    [
        "- Nova Pro returned the YAML on one line (escaped newlines): now decoded",
        "- Drafts copied 'aws ssm send-command' from the plan: prompt fixed, one repair round",
        "- A linked alert re-ran a finished task: the lease is now per summary record",
        "- Lambda 6 to 7 s; no errors; DLQ empty",
    ],
    TEAL,
    12,
)
bullets(
    s,
    [
        "The drafted playbook stops the curl loop on the flood source and prints whether it worked. "
        "The email shows the rule to add to playbook_mapping.yml to make it an approval-gated fix."
    ],
    x=0.5,
    y=4.4,
    w=7.4,
    h=2.3,
    size=14,
)

# 14 --------------------------------------------------------------- demo
s = slide(
    "Live demo and discussion",
    "What you will see",
    "Hand over to the live demo; steps are in demo/DEMO-RUNBOOK.md.",
)
bullets(
    s,
    [
        "1. Run demo/trigger_p1_incident.py: memory load on one host, network flood on another",
        "2. CloudWatch alarms fire on their own; the script sends no alert",
        "3. Inbox: approval email for the memory alert",
        "4. Approve: SSM runs fix_high_memory.yml; pipeline log shows the result",
        "5. DevOps Agent: two investigations; RCA email (memory), advisory email with a drafted playbook (network)",
        "",
        "Questions for the room:",
        "- Where should approval sit for your risk appetite: email, chat, or a ticket system?",
        "- Which alert classes are safe to auto-approve after N successful runs?",
        "- Multi-account: one Agent Space per account, or a central monitor account?",
    ],
    size=18,
)

# --------------------------------------------------------------- speaker notes
# One entry per slide, in order. SAY = talking points; SHOW = what is on screen
# during the live demo; IF ASKED = likely questions. Replaces the short notes above.
SPEAKER_NOTES = [
    # 1 title
    """SAY:
- Today: a self-healing pipeline for AWS infrastructure, with AWS DevOps Agent for root cause analysis.
- Three things to take away: known problems are fixed with a vetted playbook after approval; unknown problems get AI advice and an independent investigation; nothing changes a host without a human saying yes.
- Plan: about 15 minutes of architecture, then a live demo on a real dev environment, then discussion.

AUDIENCE: solution architects. Focus on design, trade-offs, and what is verified versus planned.""",
    # 2 problem
    """SAY:
- Today an on-call engineer reads the alert, finds the host, and picks a fix from memory or a wiki.
- The slow part is diagnosing unfamiliar alerts. The risky part is running fixes by hand on production.
- What worked last time lives in people's heads, not in the system.

- Our goal (right card): known problems get a vetted playbook that runs after approval. Unknown problems get a DevOps Agent investigation, and AI turns its root cause into a suggested playbook. Every change passes guardrails and an approval gate.

KEY LINE (bottom of slide): the AI investigates and advises; only our pipeline changes hosts, and only after validation and approval.""",
    # 3 overview
    """SAY: one alert can take three paths.
- Rule mode (orange): the alert matches a playbook in YAML. Guardrails check it, the operator gets an approval email with a signed single-use link, and on approval SSM runs the fix.
- Advisory mode (pink): no playbook matches. DevOps Agent investigates first; then Bedrock reads its root cause and mitigation plan and either picks one of our playbooks or drafts a new one. The operator gets one advisory email. Nothing runs automatically.
- If advisory mode is off, or the alert could not be forwarded, the ECS task falls back to the older path: Bedrock suggests steps and sends the advisory email itself, with a "did this help?" link.
- DevOps Agent (teal): critical, unmatched or failed incidents go to AWS DevOps Agent, which investigates with read-only access. Critical alerts get an RCA email.
- Critical alerts take the rule path and the DevOps Agent path at the same time.

DEMO LINK: in the live demo the memory alert takes rule mode (plus an RCA), and the network alert takes the advisory path.""",
    # 4 architecture diagram
    """SAY: walk the diagram left to right.
- Alerts arrive from Alertmanager or from CloudWatch alarms through SNS and a small Lambda, then API Gateway (with WAF in staging and prod).
- The pipeline runs in ECS Fargate in private subnets.
- State lives in DynamoDB (dedup, approvals, incident history); Bedrock for AI; SES for email.
- Bottom row: SSM runs fixes on the two EC2 targets; the DevOps Agent path returns through EventBridge to the Findings Lambda.
- The Findings Lambda reads the root cause and the mitigation plan. For alerts with no playbook it asks Bedrock for a playbook and sends the advisory; for the rest it sends the RCA.
- The operator only sees email: approval, advisory, and RCA.

IF ASKED: the editable diagram is architecture/aiops-self-healing-architecture.drawio.""",
    # 5 pipeline
    """SAY: seven stages, each logs with the incident_id so one incident can be traced end to end.
- 1 Normalize and dedup: repeats are dropped before anything costs money. The storm detector groups alert floods.
- 2 Enrich: look up the host; sensitive labels are removed before storage.
- 3 Rule match: alert name to playbook.
- 4 Guardrails: self-protection, maintenance window, circuit breaker, blast radius, approval gate, plan validator.
- 5 AI reasoning: only when no rule matched and advisory mode is off (or the alert was not forwarded). In advisory mode the advice comes later, from the Findings Lambda.
- 6 Approve and execute: signed single-use token, then SSM RunCommand. If the alert clears before anyone approves, the approval is cancelled and its duplicate lock released, so a real recurrence gets a fresh approval.
- 7 DevOps Agent: forwarding never blocks the pipeline.

KEY POINT: order matters. Dedup before cost, guardrails before approval.""",
    # 6 config 1 of 2
    """SAY: behaviour is driven by YAML, reviewed and versioned like code.
- playbook_mapping.yml decides rule mode versus AI mode. In the demo, HighMemoryUsage maps to fix_high_memory.yml; NetworkFloodDetected has no entry, so it takes the advisory path.
- The advisory path reads playbooks/*.yml and this mapping at deploy time, so the AI can only pick playbooks that exist.
- protected_hosts.yml: hosts automation must never touch.
- risk_classification.yml: blast-radius rules. Unknown actions default to high risk, and production raises the level by one.
- denied_commands.yml: patterns never allowed in AI plans, such as rm -rf / or curl piped to sh.

IF ASKED: changing a file needs a new image today; hot reload exists for some loaders.""",
    # 7 config 2 of 2
    """SAY: be direct about this slide.
- These four files exist and their modules are tested, but the running service does not load them yet.
- What protects us today: asyncio limits (50 pipelines, 10 executions per task), the fleet circuit breaker, the storm detector and approval de-duplication.
- Wiring these in (host locks, bulkheads, dependency ordering) is the next hardening step.

WHY SAY IT: architects trust a design that states its gaps.""",
    # 8 AI design
    """SAY: model choice is a cost and risk decision made per incident.
- Simple (Nova Lite): this alert was seen 5 or more times with at least 90% success, at P3 to P5.
- Moderate (Nova Pro): some history or mixed results, or P2.
- Complex (Claude Sonnet): P1, never seen, or every past attempt failed.
- History comes from DynamoDB: same alert name only, and only decided outcomes. Success is the operator clicking "yes, it helped" on the advisory email. An alert clearing on its own is recorded but not counted, because it does not prove the advice worked.
- Low confidence (below 0.5) re-asks the next tier up.
- Right card: every failure degrades to something safe. Timeouts and retries, a model fallback chain, and finally the rule-based mapper.

ACCURATE WORDING (the slide is slightly ahead of the code):
- Confidence below 0.7 (0.8 for P1) flags the plan for review; the advisory email is still sent.
- The prompt is not yet ordered for Bedrock prompt caching; output is capped at 2048 tokens.

SCOPE: this slide is the ECS path. In advisory mode the Findings Lambda calls Bedrock instead, with the same model fallback chain and retry rules.

IF ASKED: Claude Sonnet needs a one-time Marketplace subscription in this account; until then Nova Pro answers.""",
    # 9 DevOps Agent integration
    """SAY: DevOps Agent investigates; it never changes anything.
- Triggers (table): unmatched (no playbook; in advisory mode this drives the advisory email), critical (in parallel with the approval), failed (an approved fix did not work). Resolved updates are off.
- Controls: off unless the flag, URL and secret are all set; 5 second timeout; never blocks; at most 20 per hour per task; one per incident.
- Security: the webhook is HMAC-signed with a secret in Secrets Manager; the agent's roles trust only the DevOps Agent service with account and ARN conditions; only redacted labels are sent.
- The reference aiops-<incident_id>-<trigger> links each investigation back to our record.""",
    # 10 RCA email path
    """SAY: how a finished investigation reaches the inbox. This is the path the demo shows.
- 1 The agent finishes: completed, failed, timed out, or linked to an earlier investigation.
- 2 EventBridge catches the event.
- 3 A Lambda reads the task and journal with tag-scoped IAM.
- 4 A conditional write in DynamoDB makes it idempotent, because EventBridge can deliver twice.
- 5 SES sends the email: summary HTML-escaped, cut at 6,000 characters.
- Only our incidents are emailed; investigations started by hand in the web app are ignored. Failures retry, then land in a dead-letter queue.""",
    # 11 advisory path (new)
    """SAY: this is what happens to an alert we have no playbook for, with advisory mode on.
- 1 The ECS task forwards it to DevOps Agent and does not call Bedrock itself. If forwarding did not happen (switched off, hourly cap, error), it falls back to its own Bedrock advisory, so the operator always gets advice.
- 2 DevOps Agent investigates. In every run so far it wrote the mitigation plan inline, in the same investigation.
- 3 The Findings Lambda reads the root cause and that plan. If there is no plan, it asks for one and waits up to 8 minutes.
- 4 Bedrock either picks one of our playbooks or drafts a new one. Left card: a draft must pass structural checks or it is removed; the model gets one chance to fix a rejected draft.
- 5 One email: the fix, the drafted playbook, the rule to add to playbook_mapping.yml, the root cause and the mitigation plan.

KEY POINT: the draft is advice. To run it, a human reviews it, saves it and maps it; from then on it goes through the normal approval email.

IF ASKED about permissions: the Lambda gets three new actions when the flag is on: ListExecutions, UpdateBacklogTask (only to request a plan) and bedrock:InvokeModel. Its timeout rises from 60 s to 15 minutes to allow for the wait.""",
    # 11 security
    """SAY: the usual review questions, one card each.
- Network and API: private subnets, VPC endpoints, WAF, payload validation. Approval is two steps (GET shows a page, POST executes) so email link scanners cannot approve by accident.
- Identity and secrets: Secrets Manager, never plain environment variables; single-use approval tokens; IAM scoped to ARNs and tags.
- Untrusted input: alert text and agent summaries are treated as data. Labels are redacted, text is escaped, logs record lengths not content.
- The advisory path passes DevOps Agent text to Bedrock, so that text is bounded and our prompt section tags are stripped from it. That stops it from posing as a different section of the prompt.""",
    # 12 reliability
    """SAY: for each failure mode, name the mechanism.
- Duplicates: fingerprint dedup with TTL.
- Conflicting fixes: one pending approval per alert, host and playbook. The lock is freed when an approval is used or when its alert clears first. Host locks are not wired yet.
- Overload: storm detector, fleet circuit breaker, HTTP 429 so Alertmanager retries.
- Poison messages: dead-letter queue after 3 tries.
- Dependencies down: timeouts, retries, fallbacks.
- Visibility: JSON logs with incident_id, metrics, alarms, OpenTelemetry tracing that never blocks the pipeline.""",
    # 13 deployment
    """SAY: one stack per concern, and one command up and down.
- aiops_env.py up builds the image in CodeBuild, deploys six stacks, creates the DevOps Agent space, roles and webhook, and checks /health. A full build is about 20 minutes; down is about 17 to 25. Add --advisory to turn on advisory mode.
- The Simulation stack is the demo target: two EC2 instances, CPU, memory and network alarms, and the CloudWatch agent for memory metrics.
- Environments come from CDK context: prod gets 2 NAT gateways, point-in-time recovery, backups and termination protection.
- CI runs lint, tests, CDK synth and an image scan; CD has a prod approval gate, a health gate and automatic rollback.""",
    # 14 cost
    """SAY: we pay per incident, not per host.
- Bedrock: fractions of a cent per call; the router keeps most calls on the cheap tiers once history builds up. Advisory mode adds one call per unmatched incident, two if a draft needs repair.
- DevOps Agent is the largest per-incident cost: roughly 60 to 90 cents per investigation. The per-task cap and an AWS Budget bound it.
- Standing cost is the NAT gateway, the ECS task and the interface endpoints. Tear dev down when it is not in use.

CAVEAT: these are estimates from the docs and our tests.""",
    # 15 status
    """SAY: what is proven and what is not.
- Verified: DevOps Agent forwarding and the RCA email; advisory mode end to end with a drafted playbook; the approval lock freed when an alert clears first; guardrails failing closed; tag-scoped IAM.
- Limits: host locks and the health checker are not active. A drafted playbook is advice; mapping it would run it on the alert host, but the network flood fix has to run on the source host, so the executor would need to target another host first. Requesting a mitigation plan when none exists has not been seen live, because the agent always wrote one inline. The advisory flag is not in the CD pipeline yet. Claude Sonnet needs a Marketplace subscription.
- Roadmap: an MCP server for incident history, agent skills from runbooks, topology-based inventory.""",
    # 16 earlier live validation
    """SAY: this is an earlier recorded run (2026-11-18) with the first version of the demo: one host and a directly fired critical alert.
- The investigation took about 5.5 minutes and the RCA email followed one second later.
- The agent found the saturated CPUs and low memory, and traced them to the SSM commands in CloudTrail. It called it a deliberate fault injection, which is correct.
- Today's demo is more realistic: the CloudWatch alarms raise the alerts themselves, one fault per host.

TRANSITION: the next slide is the advisory path on the same kind of run.""",
    # 18 advisory validation (new)
    """SAY: a recorded run of the advisory path (2026-11-21) for the alert with no playbook.
- The ECS task forwarded the alert and logged that DevOps Agent would drive the advice; it made no Bedrock call.
- The investigation took about 4.5 minutes and included a mitigation plan.
- Eight seconds later the Lambda had the plan, Nova Pro drafted stop_network_flood.yml with confidence 0.9, and one email went out.
- Right card: three earlier runs each found a bug, all fixed before this one. That is why we test against the real service and not only mocks.

IF ASKED: the draft kills the curl loop on the flood source. Our executor runs a mapped playbook on the alert's host, so we would extend it before mapping this one.

TRANSITION: let's run it live.""",
    # 17 live demo
    """BEFORE YOU START (done off screen):
- MFA session valid; python demo/trigger_p1_incident.py --dry-run shows every line OK.
- Terminal A: aws logs tail /aiops/dev/ecs --region us-east-1 --follow --since 5m --filter-pattern '?remediation ?playbook ?DevOps ?approval ?advisory'
- Terminal B: findings Lambda log (see demo/DEMO-RUNBOOK.md, step 4).
- Inbox and the DevOps Agent web app open.

STEP 1 - run the script (Terminal C), 0:00
SHOW: preflight lines, then "Allocating ... kB" and "Flooding ... :8080".
SAY: "The script only creates load through SSM. It sends no alert. One host gets memory pressure, the other receives a network flood. CloudWatch has to notice, the same way it would in production."

STEP 2 - alarms fire, 1 to 2 minutes
SHOW: "aiops-target-network-dev -> ALARM" (secondary) and "aiops-target-memory-dev -> ALARM" (primary).
SAY: "Two real alarms, two hosts. The CPU alarm stays OK because the memory stress holds memory without spinning."

STEP 3 - pipeline, a few seconds later
SHOW (Terminal A): "Approval email sent" for HighMemoryUsage, "DevOps Agent investigation drives the advisory email" for NetworkFloodDetected, and two "Incident forwarded to AWS DevOps Agent" lines (trigger=critical and trigger=unmatched).
SHOW (Inbox): the approval email.
SAY: "Memory has a vetted playbook, so we get an approval request now. Network has no playbook, so nothing is guessed yet: DevOps Agent investigates first, and the advice arrives with its findings in about five minutes."

STEP 4 - approve the memory fix
SHOW: click Approve, then Confirm on the page (two steps, so link scanners cannot approve).
SHOW (Terminal A): "Executing approved remediation", "SSM command sent ... fix_high_memory.yml", "Approved remediation completed ... status=success" (about 10 seconds).
SAY: "Guardrails are checked again after approval. The playbook found stress-ng using about half the memory and killed only that, leaving the agents running."
STEP 5 - DevOps Agent, about 5 minutes
SHOW: two investigations in the web app, priority CRITICAL, references aiops-<id>-critical and aiops-<id>-unmatched. DevOps Agent may link the second alert to the first investigation; that is its own triage.
SAY: "Read-only access. It is reading CloudWatch metrics, SSM history and CloudTrail."

STEP 6 - RCA and advisory emails
SHOW (Terminal B): "finding delivered" (memory) and "advisory delivered" with proposed_playbook (network).
SHOW (Inbox): the RCA email, then "[CRITICAL] NetworkFloodDetected on ... - AI Analysis & Suggested Steps" with the drafted playbook and the mapping rule.
SAY: "The agent changed nothing. The only change on a host was the playbook a human approved. The drafted playbook is a proposal for a human to review."

IF SOMETHING GOES WRONG:
- An alarm is slow: EC2 network metrics can lag a few minutes; keep talking through slide 9 or 10.
- Approval link says "already resolved": the load ended and the alarm cleared; that is the resolved signal working.
- Exact timings from the last run are in demo/DEMO-RUNBOOK.md.

DISCUSSION: use the three questions on the slide.""",
]
assert len(SPEAKER_NOTES) == len(prs.slides), (len(SPEAKER_NOTES), len(prs.slides))
for _slide, _notes in zip(prs.slides, SPEAKER_NOTES):
    _slide.notes_slide.notes_text_frame.text = _notes

prs.save(OUT)
print("saved", OUT)
