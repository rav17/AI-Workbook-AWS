"""Generate the Aria Architectural Thinking diagrams as editable draw.io files.

Run from anywhere: python docs/architecture/generate_diagrams.py
"""

from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import quoteattr

OUT = Path(__file__).resolve().parent

# Palette
HUMAN = "fillColor=#fff2cc;strokeColor=#d6b656;"
INT = "fillColor=#dae8fc;strokeColor=#6c8ebf;"
EXT = "fillColor=#f5f5f5;strokeColor=#666666;fontColor=#333333;"
AWS = "fillColor=#ffe6cc;strokeColor=#d79b00;"
DATA = "fillColor=#d5e8d4;strokeColor=#82b366;"
SEC = "fillColor=#f8cecc;strokeColor=#b85450;"
OBS = "fillColor=#e1d5e7;strokeColor=#9673a6;"
AWS_ICON_COLORS = {
    "api_gateway": "#E7157B",
    "cloudwatch": "#E7157B",
    "dynamodb": "#C925D1",
    "eventbridge": "#E7157B",
    "general_saml_token": "#232F3E",
    "kms": "#DD344C",
    "lambda": "#ED7100",
    "machine_learning": "#01A88D",
    "secrets_manager": "#DD344C",
    "sns": "#E7157B",
    "sqs": "#7B68EE",
}
ZONE = (
    "fillColor=none;dashed=1;strokeWidth=2;verticalAlign=top;fontStyle=1;align=left;spacingLeft=8;"
)
BOX = "rounded=1;whiteSpace=wrap;html=1;fontSize=11;"


class Diagram:
    def __init__(self, name: str, title: str, w: int = 1600, h: int = 1000) -> None:
        self.name, self.w, self.h = name, w, h
        self.cells: list[str] = []
        self.n = 1
        self.text(title, 20, 8, w - 40, 30, "fontSize=18;fontStyle=1;align=center;")

    def _id(self) -> str:
        self.n += 1
        return f"c{self.n}"

    def box(self, label, x, y, w, h, style=INT, extra=BOX) -> str:
        i = self._id()
        self.cells.append(
            f'<mxCell id="{i}" value={quoteattr(label)} style="{extra}{style}" vertex="1" parent="1">'
            f'<mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>'
        )
        return i

    def aws_box(self, label, x, y, w, h, icon, style=AWS) -> str:
        card_id = self.box("", x, y, w, h, style)
        icon_id = self._id()
        icon_color = AWS_ICON_COLORS[icon]
        icon_style = (
            "outlineConnect=0;fontColor=#232F3E;gradientColor=none;strokeColor=none;"
            f"fillColor={icon_color};labelPosition=center;verticalLabelPosition=bottom;"
            "verticalAlign=top;align=center;fontSize=8;shape=mxgraph.aws4.resourceIcon;"
            f"resIcon=mxgraph.aws4.{icon};"
        )
        self.cells.append(
            f'<mxCell id="{icon_id}" value="" style="{icon_style}" vertex="1" parent="1">'
            f'<mxGeometry x="{x + 8}" y="{y + (h - 36) // 2}" width="36" height="36" as="geometry"/></mxCell>'
        )
        self.text(
            label,
            x + 52,
            y + 4,
            w - 58,
            h - 8,
            "fontSize=10;align=left;verticalAlign=middle;",
        )
        return card_id

    def zone(self, label, x, y, w, h, color="#6c8ebf") -> str:
        return self.box(
            label,
            x,
            y,
            w,
            h,
            ZONE + f"strokeColor={color};fontColor={color};",
            "rounded=1;html=1;whiteSpace=wrap;arcSize=3;",
        )

    def text(self, label, x, y, w, h, style="fontSize=11;align=left;verticalAlign=top;") -> str:
        i = self._id()
        self.cells.append(
            f'<mxCell id="{i}" value={quoteattr(label)} style="text;html=1;whiteSpace=wrap;{style}" vertex="1" parent="1">'
            f'<mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>'
        )
        return i

    def ellipse(self, label, x, y, w, h, style=INT) -> str:
        return self.box(label, x, y, w, h, style, "ellipse;whiteSpace=wrap;html=1;fontSize=11;")

    def actor(self, label, x, y, style="") -> str:
        i = self._id()
        self.cells.append(
            f'<mxCell id="{i}" value={quoteattr(label)} style="shape=umlActor;verticalLabelPosition=bottom;'
            f'verticalAlign=top;html=1;fontSize=11;fillColor=#fff2cc;strokeColor=#d6b656;{style}" vertex="1" parent="1">'
            f'<mxGeometry x="{x}" y="{y}" width="30" height="60" as="geometry"/></mxCell>'
        )
        return i

    def edge(self, s, t, label="", style="") -> str:
        i = self._id()
        self.cells.append(
            f'<mxCell id="{i}" value={quoteattr(label)} style="endArrow=block;endFill=1;html=1;fontSize=10;'
            f'strokeWidth=1.5;{style}" edge="1" parent="1" source="{s}" target="{t}">'
            f'<mxGeometry relative="1" as="geometry"/></mxCell>'
        )
        return i

    def line(self, x1, y1, x2, y2, label="", style="") -> str:
        i = self._id()
        self.cells.append(
            f'<mxCell id="{i}" value={quoteattr(label)} style="html=1;fontSize=10;endArrow=block;endFill=1;{style}" '
            f'edge="1" parent="1"><mxGeometry relative="1" as="geometry">'
            f'<mxPoint x="{x1}" y="{y1}" as="sourcePoint"/><mxPoint x="{x2}" y="{y2}" as="targetPoint"/>'
            f"</mxGeometry></mxCell>"
        )
        return i

    def save(self, filename: str) -> None:
        xml = (
            '<mxfile host="app.diagrams.net"><diagram id="d1" name='
            + quoteattr(self.name)
            + f'><mxGraphModel dx="1400" dy="900" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" '
            f'arrows="1" fold="1" page="1" pageScale="1" pageWidth="{self.w}" pageHeight="{self.h}" math="0" shadow="0">'
            '<root><mxCell id="0"/><mxCell id="1" parent="0"/>'
            + "".join(self.cells)
            + "</root></mxGraphModel></diagram></mxfile>"
        )
        (OUT / filename).write_text(xml, encoding="utf-8")
        print("wrote", filename)


def legend(d: Diagram, x: int, y: int, items: list[tuple[str, str]]) -> None:
    for k, (label, style) in enumerate(items):
        d.box(label, x + k * 150, y, 140, 26, style, BOX)


# ---------------------------------------------------------------- Exercise 1
def system_context() -> None:
    d = Diagram(
        "System Context",
        "Exercise 1 - System Context Diagram: Aria AI Relationship Manager",
        1600,
        900,
    )
    cl = d.actor("Client\n(Premier / Imperia)", 40, 110)
    rm = d.actor("Human RM /\nUnderwriter", 40, 290)
    co = d.actor("Compliance\nOfficer", 40, 470)
    ops = d.actor("Platform Admin /\nOperations (on-call)", 40, 650)
    ch = d.box("Web Chat UI /\nMobile Banking App\n(channel apps)", 300, 105, 190, 70, EXT)
    idp = d.box("Amazon Cognito\n(Identity Provider, JWT + tenant claim)", 640, 60, 300, 60, EXT)
    aria = d.box(
        "<b>ARIA</b><br/>AI Relationship Manager<br/><br/>Guarded conversations, workflow state,<br/>CRM / KB / risk / compliance tools,<br/>escalation, proactive retention",
        600,
        300,
        380,
        200,
        INT + "strokeWidth=3;fontSize=13;",
    )
    crm = d.box(
        "CRM System\n(Salesforce / CRM Next)\nsystem of record: profile, activity",
        1150,
        90,
        260,
        80,
        EXT,
    )
    cbs = d.box("Core Banking System\n(balances, maturities, outflows)", 1150, 220, 260, 70, EXT)
    kyc = d.box(
        "KYC / AML Provider\n(authoritative - NOT yet configured;\nfail-closed)",
        1150,
        340,
        260,
        80,
        EXT + "dashed=1;",
    )
    kb = d.box("Bedrock Knowledge Base\n(rates, policies, source dates)", 1150, 470, 260, 70, EXT)
    llm = d.box("Amazon Bedrock\nClaude FM + Guardrails", 1150, 590, 260, 70, EXT)
    eb = d.box("Banking event sources\n(maturity / large-outflow events)", 640, 700, 300, 70, EXT)
    ack = d.box("Operations alerting\n(SNS / CloudWatch)", 300, 650, 190, 60, EXT)

    d.edge(cl, ch, "chat messages")
    d.edge(ch, aria, "HTTPS POST /messages\n(Cognito JWT)")
    d.edge(aria, idp, "validates JWT / tenant claim", "dashed=1;")
    d.edge(aria, rm, "escalation ticket + full context\n+ expected timeline")
    d.edge(aria, co, "AML flags / KYC escalations")
    d.edge(ops, ack, "subscribes")
    d.edge(
        ack, aria, "alarms on API/Lambda/log findings", "dashed=1;startArrow=block;endArrow=none;"
    )
    d.edge(aria, crm, "read profile & segment;\nlog interactions, reminders")
    d.edge(aria, cbs, "maturity / outflow data")
    d.edge(aria, kyc, "KYC status / AML checks")
    d.edge(aria, kb, "retrieve rates + citations")
    d.edge(aria, llm, "InvokeModel, guardrail checks")
    d.edge(eb, aria, "EventBridge events")
    legend(
        d, 300, 830, [("Human actor", HUMAN), ("External system", EXT), ("System in scope", INT)]
    )
    d.save("01_System_Context_Diagram.drawio")


def use_case() -> None:
    d = Diagram(
        "Use Case Model", "Exercise 1 - High-level Use Case Model (bubble diagram)", 1500, 900
    )
    d.zone("ARIA (system boundary)", 330, 60, 820, 780, "#6c8ebf")
    cl = d.actor("Client", 80, 150)
    rm = d.actor("Human RM", 80, 380)
    co = d.actor("Compliance\nOfficer", 80, 560)
    ops = d.actor("Platform Admin /\nOps", 1250, 560)
    ev = d.actor("Banking Event\nSource (system)", 1250, 150)
    crm = d.actor("CRM / Core\nBanking (system)", 1250, 370)
    bubbles = [
        ("Manage Client Profile\n& Risk Appetite", 370, 100, [cl, crm]),
        ("Wallet Profiling &\nConsolidation", 640, 100, [cl, crm]),
        ("Product Recommendation\n& Offers", 910, 100, [cl]),
        ("Retention &\nMaturity Management", 370, 260, [ev, cl]),
        ("Service Query\nResolution (KB)", 640, 260, [cl]),
        ("CRM Interaction\nLogging", 910, 260, [crm]),
        ("Regulatory Compliance\n(KYC / AML)", 370, 420, [co, cl]),
        ("Human Escalation", 640, 420, [rm]),
        ("Security & Guardrails\n(credentials, injection)", 910, 420, [cl]),
        ("Session, Workflow State\n& Memory", 370, 580, [cl]),
        ("Authenticated API Access", 640, 580, [cl]),
        ("Observability &\nOperations", 910, 580, [ops]),
    ]
    for label, x, y, actors in bubbles:
        b = d.ellipse(label, x, y, 220, 110)
        for a in actors:
            d.edge(a, b, "", "endArrow=none;endFill=0;strokeColor=#666666;")
    d.text(
        "Bubbles group the 14 user stories / FR-001..FR-039 of specs/001-ai-relationship-manager (no individual use cases shown).",
        340,
        770,
        800,
        50,
        "fontSize=11;fontStyle=2;",
    )
    d.save("01_Use_Case_Diagram.drawio")


def nfr() -> None:
    d = Diagram("Key NFRs", "Exercise 1 - Key Qualities (Non-Functional Requirements)", 1400, 820)
    rows = [
        (
            "Security",
            "Cognito JWT + tenant claim; credentials redacted/never stored; prompt-injection blocked; KMS everywhere; permissions boundary; least-privilege IAM; auth outside the model",
            "100% credential messages rejected before agent (SC-002)",
        ),
        (
            "Compliance",
            "KYC gate before products; AML flagging; fail closed when no authoritative KYC provider; risk disclosure; no guaranteed returns",
            "100% market recs have risk assessment (SC-001)",
        ),
        (
            "Availability",
            "Managed serverless services; DLQ for events; graceful CRM/KB degradation; session recovery from DynamoDB",
            "99.9% monthly API availability (proposed)",
        ),
        (
            "Performance",
            "Bounded context/memory top-k, tool filtering, timeouts + bounded retries",
            "API p95 < 1,000 ms (proposed)",
        ),
        (
            "Data integrity",
            "Typed workflow state, atomic patches, optimistic revisions, idempotency keys",
            "Rejected patch preserves prior state (SC-010)",
        ),
        (
            "Privacy / Retention",
            "Tenant-scoped memory namespaces; no client-data memory writes until approved; 7-day masked logs; erasure operation",
            "30-day short-term event expiry",
        ),
        (
            "Observability",
            "Structured redacted logs, X-Ray tracing, CloudWatch alarms -> encrypted SNS topic, sensitive-log findings metric",
            "Alarm on 5xx > 1%, Lambda errors/throttles",
        ),
        (
            "Maintainability / Extensibility",
            "Shared framework + manifest-driven agents; CDK constructs; Ruff, typing, pytest, Hypothesis, CDK assertions",
            "New agent without framework/CDK changes (SC-016)",
        ),
        (
            "Deployability",
            "CDK v2, 4 stacks, deterministic synth, OIDC federated deploy, cdk diff review, RETAIN + termination protection in prod",
            "No long-lived keys (FR-031)",
        ),
        (
            "Scalability",
            "Pay-per-request DynamoDB, Lambda, AgentCore Runtime sessions; multi-tenant",
            "High-value retail & wealth clients",
        ),
    ]
    html = '<table border="1" cellpadding="6" style="border-collapse:collapse;width:100%;font-size:11px;"><tr style="background:#dae8fc;font-weight:bold"><td>Quality</td><td>Requirement / mechanism</td><td>Target / measure</td></tr>'
    for q, r, t in rows:
        html += f"<tr><td><b>{q}</b></td><td>{r}</td><td>{t}</td></tr>"
    html += "</table>"
    d.text(html, 30, 60, 1340, 700, "fontSize=11;")
    d.save("01_Key_NFRs.drawio")


# ---------------------------------------------------------------- Exercise 2
def overview() -> None:
    d = Diagram(
        "Architecture Overview",
        "Exercise 2 - Architecture Overview Diagram (functional + operational, audience: project IT)",
        1600,
        1000,
    )
    # Channels
    d.zone("Channels", 30, 60, 220, 230, "#d6b656")
    client = d.box("Client\n(Web chat / Mobile app)", 50, 100, 180, 60, HUMAN)
    d.box("Human RM / Compliance", 50, 180, 180, 50, HUMAN)
    # Edge
    d.zone("Edge & Identity", 280, 60, 260, 230, "#b85450")
    api = d.box("API Gateway REST\nPOST /messages\nCognito authorizer", 300, 100, 220, 70, AWS)
    cog = d.box("Amazon Cognito\nUser Pool", 300, 190, 220, 50, AWS)
    # Request layer
    d.zone("Request & Event Handling (Lambda)", 570, 60, 300, 230, "#d79b00")
    req = d.box(
        "Request Lambda\naria.api.lambda_entry\nidentity, idempotency,\nsession map",
        590,
        100,
        260,
        80,
        AWS,
    )
    evl = d.box(
        "Event Lambda\naria.events.lambda_handler\nmaturity / outflow", 590, 195, 260, 70, AWS
    )
    # Runtime
    d.zone("AgentCore Runtime (Python 3.13) - Aria agent", 570, 330, 560, 330, "#6c8ebf")
    run = d.box("Framework Runner\nlazy config, context, hooks,\ncleanup", 590, 370, 250, 70, INT)
    grd = d.box("Guardrail Processor\ninput/output, fail-closed", 860, 370, 250, 70, SEC)
    strands = d.box("Strands Agent (AriaAgent)\nprompt + tool loop", 590, 460, 250, 70, INT)
    wf = d.box(
        "Workflow Engine\nstate, patch, validator,\ndependencies, next-step", 860, 460, 250, 70, INT
    )
    tools = d.box(
        "Domain Tools: CRM - Knowledge - Risk - Maturity - Compliance - Escalation",
        590,
        550,
        520,
        50,
        INT,
    )
    d.text(
        "Wire-protocol: Runtime session id per conversation",
        590,
        615,
        520,
        30,
        "fontSize=10;fontStyle=2;",
    )
    # AgentCore & AI services
    d.zone("AgentCore & AI Services", 1170, 330, 400, 330, "#d79b00")
    mem = d.box("AgentCore Memory\n(tenant-scoped retrieval)", 1190, 370, 360, 55, AWS)
    gw = d.box(
        "AgentCore Gateway (MCP, IAM)\n-> Lambda tool: get_risk_questionnaire",
        1190,
        440,
        360,
        55,
        AWS,
    )
    brk = d.box("Amazon Bedrock Claude\n+ Bedrock Guardrails", 1190, 510, 360, 55, AWS)
    kb = d.box("Bedrock Knowledge Base\n(rates, policies)", 1190, 580, 360, 55, AWS)
    # State
    d.zone("Stateful Services", 30, 330, 500, 330, "#82b366")
    d.box("DynamoDB Session table\n(workflow state, revisions)", 50, 370, 220, 55, DATA)
    d.box("DynamoDB Idempotency table\n(TTL)", 290, 370, 220, 55, DATA)
    d.box("EventBridge bus\naria-workflow-{env}", 50, 440, 220, 55, DATA)
    d.box("SQS workflow queue + DLQ", 290, 440, 220, 55, DATA)
    d.box("Secrets Manager\n(provider credentials)", 50, 510, 220, 55, DATA)
    d.box("SSM Parameter Store\n(runtime ARN, memory id)", 290, 510, 220, 55, DATA)
    d.box("KMS CMK (rotation)", 50, 580, 460, 50, DATA)
    # External
    d.zone("External Systems", 1170, 60, 400, 230, "#666666")
    d.box("CRM (Salesforce / CRM Next)", 1190, 100, 360, 45, EXT)
    d.box("Core Banking System", 1190, 155, 360, 45, EXT)
    d.box("KYC / AML provider (not configured)", 1190, 210, 360, 45, EXT + "dashed=1;")
    # Cross-cutting
    d.box(
        "Observability: structured redacted logs - X-Ray - CloudWatch alarms - SNS ops topic",
        30,
        700,
        1540,
        45,
        OBS,
    )
    d.box(
        "Platform: AWS CDK v2 (Stateful -> Application -> Gateway -> Runtime stacks) - permissions boundary - GitHub OIDC deploy",
        30,
        760,
        1540,
        45,
        EXT,
    )
    d.edge(client, api, "HTTPS")
    d.edge(api, cog, "verify JWT", "dashed=1;")
    d.edge(api, req, "invoke")
    d.edge(req, run, "InvokeAgentRuntime\n(SigV4, resource policy)")
    d.edge(run, grd)
    d.edge(run, strands)
    d.edge(strands, wf)
    d.edge(strands, tools)
    d.edge(run, mem, "retrieve", "dashed=1;")
    d.edge(strands, gw, "MCP tools", "dashed=1;")
    d.edge(strands, brk, "InvokeModel", "dashed=1;")
    d.edge(tools, kb, "retrieve", "dashed=1;")
    d.save("02_Architecture_Overview.drawio")


# ---------------------------------------------------------------- Exercise 3
def component_model() -> None:
    d = Diagram(
        "Component Model", "Exercise 3 - Logical Component Model (structural view)", 1700, 1000
    )
    cl = d.actor("Client", 30, 120)
    rm = d.actor("Human RM", 30, 330)
    ev = d.actor("Event Source", 30, 520)
    ops = d.actor("Ops", 30, 700)
    d.zone("Edge components", 110, 60, 260, 780, "#b85450")
    chat = d.box(
        "Chat API Edge\n(REST/WebSocket handler,\nauth, idempotency)", 130, 100, 220, 80, SEC
    )
    evt = d.box("Event Intake Edge\n(normalize, route events)", 130, 500, 220, 70, SEC)
    adm = d.box("Escalation Notification\nEdge", 130, 310, 220, 60, SEC)
    d.zone("Aria core", 400, 60, 760, 780, "#6c8ebf")
    orch = d.box("Conversation Orchestrator\n(AriaAgent / Strands loop)", 640, 100, 260, 70)
    guard = d.box(
        "Guardrail Engine\n(credential redaction, injection, output sanitization)",
        420,
        100,
        200,
        90,
        SEC,
    )
    sess = d.box("Session Manager\n(user<->conversation<->runtime session)", 420, 230, 200, 70)
    runner = d.box("Agent Framework Runner\n(config, context, hooks, cleanup)", 640, 230, 260, 70)
    wf = d.box(
        "Workflow State Engine\n(state, patch, validator,\ndependency resolver, next-step)",
        920,
        230,
        220,
        90,
    )
    mem = d.box("Memory Service\n(bounded, tenant-scoped)", 420, 360, 200, 60)
    tg = d.box("Tool Gateway / Tool Filter\n(allowlist, MCP)", 640, 360, 260, 60)
    obs = d.box("Observability\n(redacted logs, traces)", 920, 360, 220, 60, OBS)
    d.text("Domain tools", 420, 460, 200, 20, "fontStyle=1;")
    crm = d.box("CRM Tool", 420, 490, 150, 45)
    kbt = d.box("Knowledge Tool", 590, 490, 150, 45)
    risk = d.box("Risk Tool", 760, 490, 150, 45)
    mat = d.box("Maturity / Retention Tool", 930, 490, 200, 45)
    comp = d.box("Compliance Tool\n(KYC / AML)", 420, 560, 150, 55)
    esc = d.box("Escalation Tool", 590, 560, 150, 55)
    pers = d.box("Persistence Store\n(session, idempotency)", 760, 560, 200, 55, DATA)
    d.zone("External / managed", 1200, 60, 460, 780, "#666666")
    x_crm = d.box("CRM System", 1230, 100, 190, 50, EXT)
    x_kb = d.box("Knowledge Base", 1230, 180, 190, 50, EXT)
    x_llm = d.box("Foundation Model", 1440, 100, 190, 50, EXT)
    x_cbs = d.box("Core Banking", 1230, 260, 190, 50, EXT)
    x_kyc = d.box("KYC/AML Provider", 1230, 340, 190, 50, EXT + "dashed=1;")
    x_mem = d.box("Long-term Memory\nStore", 1440, 180, 190, 50, EXT)
    x_gw = d.box("Gateway-hosted tools", 1440, 260, 190, 50, EXT)
    x_dbs = d.box("Durable state DB", 1230, 560, 190, 50, EXT)
    x_alert = d.box("Alerting channel", 1440, 700, 190, 50, EXT)
    for a, b in [(cl, chat), (ev, evt), (rm, adm), (ops, x_alert)]:
        d.edge(a, b, "", "endArrow=none;endFill=0;")
    d.edge(chat, guard, "message")
    d.edge(chat, sess, "resolve session")
    d.edge(guard, orch, "sanitized")
    d.edge(sess, runner)
    d.edge(runner, orch, "invoke")
    d.edge(orch, wf, "propose patch")
    d.edge(runner, mem, "retrieve")
    d.edge(orch, tg)
    d.edge(tg, crm)
    d.edge(tg, kbt)
    d.edge(tg, risk)
    d.edge(tg, mat)
    d.edge(tg, comp)
    d.edge(tg, esc)
    d.edge(crm, x_crm)
    d.edge(kbt, x_kb)
    d.edge(mat, x_cbs)
    d.edge(comp, x_kyc)
    d.edge(orch, x_llm, "reason")
    d.edge(mem, x_mem)
    d.edge(tg, x_gw, "", "dashed=1;")
    d.edge(wf, pers, "persist rev")
    d.edge(pers, x_dbs)
    d.edge(esc, adm, "ticket")
    d.edge(evt, mat, "evaluate event")
    d.edge(orch, obs, "", "dashed=1;")
    d.text(
        "<b>Responsibilities</b><br/>Guardrail Engine: fail-closed input/output checks.<br/>Workflow State Engine: only authority for validated state; model proposes, code applies.<br/>Session Manager: authenticated mapping to a recoverable runtime session.<br/>Tool Gateway: capability allowlist; authorization stays in IAM/backend.<br/>Memory: untrusted, never overrides workflow state.",
        410,
        660,
        740,
        160,
        "fontSize=11;",
    )
    d.save("03_Component_Model.drawio")


def sequence(name, title, filename, parts, msgs, w=1700) -> None:
    d = Diagram(name, title, w, 140 + 40 * (len(msgs) + 2))
    gap = (w - 120) // len(parts)
    xs = []
    height = 100 + 40 * (len(msgs) + 1)
    for i, p in enumerate(parts):
        cx = 60 + gap * i + gap // 2
        xs.append(cx)
        d.box(p, cx - 70, 50, 140, 50, INT)
        d.line(cx, 100, cx, height, "", "dashed=1;endArrow=none;strokeColor=#999999;")
    for k, (a, b, label, *dash) in enumerate(msgs):
        y = 130 + 40 * k
        style = "dashed=1;" if dash and dash[0] else ""
        if a == b:
            d.text(label, xs[a] + 10, y - 14, 220, 28, "fontSize=10;fontStyle=2;")
        else:
            d.line(
                xs[a],
                y,
                xs[b],
                y,
                label,
                style + "verticalAlign=bottom;labelBackgroundColor=#ffffff;",
            )
    d.save(filename)


def sequences() -> None:
    sequence(
        "UC Authenticated Chat Message",
        "Exercise 3 - Sequence: Authenticated client message (primary journey)",
        "03_Sequence_Chat_Message.drawio",
        [
            "Client",
            "API Gateway\n+ Cognito",
            "Request Lambda",
            "DynamoDB",
            "AgentCore\nRuntime",
            "Guardrails",
            "Memory /\nGateway",
            "Bedrock\nClaude",
        ],
        [
            (0, 1, "POST /messages (JWT)"),
            (1, 1, "verify JWT"),
            (1, 2, "invoke (verified principal)"),
            (2, 3, "idempotency check + resolve session"),
            (3, 2, "runtime session id", 1),
            (2, 4, "InvokeAgentRuntime (SigV4)"),
            (4, 5, "process_input (fail-closed)"),
            (5, 4, "sanitized / blocked", 1),
            (4, 6, "retrieve memory (top-k), list allowed tools"),
            (4, 7, "converse with tools"),
            (7, 4, "response (tool calls)", 1),
            (4, 5, "process_output"),
            (4, 2, "processed response", 1),
            (2, 3, "persist state / idempotency result"),
            (2, 1, "response", 1),
            (1, 0, "200 OK + reply", 1),
        ],
    )
    sequence(
        "UC Proactive Maturity Event",
        "Exercise 3 - Sequence: Proactive maturity / outflow event",
        "03_Sequence_Proactive_Event.drawio",
        [
            "Banking event\nsource",
            "EventBridge\nbus",
            "Event Lambda",
            "Maturity tool",
            "Knowledge\nBase",
            "SQS queue\n/ DLQ",
            "Client / RM\nnotification",
        ],
        [
            (0, 1, "put event (maturity / outflow)"),
            (1, 2, "rule match -> invoke"),
            (2, 2, "normalize + require event id/client id"),
            (2, 3, "evaluate_maturity_event / outflow"),
            (3, 2, "<= 30 days: notify; else none", 1),
            (3, 4, "current reinvestment rate"),
            (4, 3, "rate + source date", 1),
            (2, 5, "enqueue workflow action"),
            (5, 6, "outreach with reinvestment options"),
            (5, 5, "after 3 failures -> DLQ + alarm"),
        ],
        w=1500,
    )


# ---------------------------------------------------------------- Exercise 4
def location_model() -> None:
    d = Diagram("Location Model", "Exercise 4 - Location Model", 1500, 800)
    a = d.box(
        "LL_Client\nClient devices (many)\n- Web browser\n- Mobile banking app",
        40,
        100,
        280,
        140,
        HUMAN,
        BOX + "strokeWidth=2;",
    )
    b = d.box(
        "LL_Bank_Internal (Human RMs, Compliance)\n- RM / compliance workstations\n- CRM UI",
        40,
        380,
        280,
        150,
        HUMAN,
        BOX + "strokeWidth=2;",
    )
    c = d.box(
        "LL_AWS_Region (1 region, multi-AZ managed services)\n- API / Lambda / Runtime\n- Data & Messaging\n- AI services",
        500,
        100,
        420,
        280,
        AWS,
        BOX + "strokeWidth=2;",
    )
    e = d.box(
        "LL_Bank_DC / SaaS\nCRM (Salesforce / CRM Next)\nCore Banking System\nKYC / AML provider",
        1100,
        100,
        320,
        160,
        EXT,
        BOX + "strokeWidth=2;",
    )
    f = d.box(
        "LL_CICD\nGitHub Actions (OIDC)\nDeveloper workstations",
        500,
        480,
        420,
        120,
        EXT,
        BOX + "strokeWidth=2;",
    )
    d.edge(a, c, "Internet (HTTPS/TLS)")
    d.edge(b, c, "Corporate network / VPN (escalation, admin)")
    d.edge(c, e, "HTTPS APIs (private link / VPN)")
    d.edge(f, c, "OIDC role assumption + CloudFormation deploy")
    d.save("04_Location_Model.drawio")


def deployment_units() -> None:
    d = Diagram(
        "Deployment Unit Model",
        "Exercise 4 - Deployment Unit Model (from component model)",
        1500,
        900,
    )
    rows = [
        (
            "DU_Chat_API",
            "Chat API Edge",
            "aria.api.lambda_entry, rest_handler, runtime_session (Lambda py3.11 artifact)",
            60,
        ),
        (
            "DU_Event_Handler",
            "Event Intake Edge + Maturity Tool",
            "aria.events.*, tools.maturity_tool (Lambda)",
            170,
        ),
        (
            "DU_Aria_Runtime",
            "Orchestrator, Guardrails, Workflow Engine, Framework Runner, Domain Tools",
            "aria/ + aria.agents.aria entrypoint (AgentCore Runtime py3.13 code asset)",
            280,
        ),
        (
            "DU_Gateway_Tool",
            "Tool Gateway tools",
            "aria.api.gateway_handler (Lambda; exposes get_risk_questionnaire only)",
            390,
        ),
        (
            "DU_Infra_Stateful",
            "Persistence, Memory store, Secrets, Event bus, Queues",
            "CDK StatefulStack (DynamoDB, KMS, SQS, EventBridge, AgentCore Memory)",
            500,
        ),
        (
            "DU_Infra_Platform",
            "App / Gateway / Runtime stacks",
            "CDK Application, Gateway, Runtime stacks + MMDSv2 custom resource",
            610,
        ),
        (
            "DU_Observability",
            "Observability",
            "Log groups with data protection, alarms, SNS topic",
            720,
        ),
    ]
    d.text("<b>Deployment Unit</b>", 60, 40, 300, 20)
    d.text("<b>Components hosted</b>", 400, 40, 400, 20)
    d.text("<b>Packaging / technology</b>", 900, 40, 500, 20)
    for du, comp, pkg, y in rows:
        d.box(du, 60, y, 300, 80, INT)
        d.box(comp, 400, y, 450, 80, HUMAN)
        d.box(pkg, 900, y, 520, 80, DATA)
    d.save("04_Deployment_Unit_Model.drawio")


# ---------------------------------------------------------------- Exercise 5
def lom() -> None:
    d = Diagram(
        "LOM",
        "Exercise 5 - Logical Operational Model (locations, nodes, deployment units)",
        1700,
        1000,
    )
    d.zone("LL_Client", 20, 60, 220, 300, "#d6b656")
    cl = d.actor("Client", 100, 100)
    br = d.box("Browser / Mobile app", 40, 220, 180, 50, HUMAN)
    d.zone("LL_Bank_Internal", 20, 400, 220, 220, "#d6b656")
    rmw = d.box("RM / Compliance\nworkstation", 40, 450, 180, 60, HUMAN)
    d.zone("LL_AWS_Region", 280, 60, 1000, 900, "#d79b00")
    d.zone("Presentation / Edge", 300, 100, 220, 260, "#b85450")
    ln1 = d.box(
        "Edge Gateway Node\n[API Gateway + Cognito authorizer]\nDU: -", 320, 140, 180, 90, SEC
    )
    ln_idp = d.box("Identity Node\n[User pool]", 320, 250, 180, 60, SEC)
    d.zone("Application", 540, 100, 380, 410, "#6c8ebf")
    ln2 = d.box("Request Handler Node\nDU_Chat_API", 560, 140, 340, 60)
    ln3 = d.box("Event Handler Node\nDU_Event_Handler", 560, 215, 340, 60)
    ln4 = d.box(
        "Agent Runtime Node\nDU_Aria_Runtime\n(Orchestrator, Guardrails, Workflow, Tools)",
        560,
        290,
        340,
        90,
    )
    ln5 = d.box("Tool Gateway Node\nDU_Gateway_Tool", 560, 395, 340, 60)
    d.zone("AI / Knowledge Services", 960, 100, 300, 410, "#d79b00")
    ln6 = d.box("Foundation Model Node\n(Claude + Guardrails)", 980, 140, 260, 60, AWS)
    ln7 = d.box("Memory Node\n(AgentCore Memory)", 980, 215, 260, 60, AWS)
    ln8 = d.box("Knowledge Node\n(Bedrock KB)", 980, 290, 260, 60, AWS)
    d.zone("Data & Messaging", 300, 560, 960, 160, "#82b366")
    ln9 = d.box("State DB Node\nsession + idempotency", 320, 600, 200, 80, DATA)
    ln10 = d.box("Event Bus Node", 540, 600, 180, 80, DATA)
    ln11 = d.box("Queue Node\n(+ DLQ)", 740, 600, 180, 80, DATA)
    ln12 = d.box("Secrets / Config Node\n(+ KMS)", 940, 600, 200, 80, DATA)
    d.zone("Operations", 300, 760, 960, 170, "#9673a6")
    ln13 = d.box("Monitoring Node\nlogs, traces, alarms\nDU_Observability", 320, 800, 280, 90, OBS)
    ln14 = d.box("Notification Node\n(SNS topic)", 640, 800, 220, 90, OBS)
    d.zone("LL_Bank_DC / SaaS", 1320, 60, 360, 400, "#666666")
    x1 = d.box("CRM Node", 1350, 110, 300, 60, EXT)
    x2 = d.box("Core Banking Node", 1350, 190, 300, 60, EXT)
    x3 = d.box("KYC / AML Node\n(not configured)", 1350, 270, 300, 60, EXT + "dashed=1;")
    d.zone("LL_CICD", 1320, 500, 360, 160, "#666666")
    x4 = d.box("CI/CD runner\n(GitHub Actions + OIDC)", 1350, 550, 300, 70, EXT)
    d.edge(cl, br, "", "endArrow=none;")
    d.edge(br, ln1, "HTTPS / TLS 1.2+")
    d.edge(rmw, ln14, "alert / escalation", "dashed=1;")
    d.edge(ln1, ln_idp, "JWT verify", "dashed=1;")
    d.edge(ln1, ln2, "invoke")
    d.edge(ln2, ln4, "SigV4 InvokeAgentRuntime")
    d.edge(ln2, ln9, "")
    d.edge(ln3, ln10, "")
    d.edge(ln10, ln3, "rules", "dashed=1;")
    d.edge(ln3, ln11)
    d.edge(ln4, ln5, "MCP (IAM)")
    d.edge(ln4, ln6)
    d.edge(ln4, ln7)
    d.edge(ln4, ln8)
    d.edge(ln4, x1, "HTTPS")
    d.edge(ln3, x2, "HTTPS")
    d.edge(ln4, x3, "HTTPS", "dashed=1;")
    d.edge(ln13, ln14, "alarms")
    d.edge(x4, ln2, "CloudFormation deploy", "dashed=1;")
    d.save("05_LOM.drawio")


def pom() -> None:
    d = Diagram(
        "POM", "Exercise 5 - Physical Operational Model (unsized, AWS services)", 1700, 1000
    )
    d.zone("Client / Bank locations", 20, 60, 220, 360, "#d6b656")
    cbrowser = d.box("Client browser / mobile app", 40, 110, 180, 55, HUMAN)
    d.box("RM / Compliance workstation (corporate)", 40, 300, 180, 70, HUMAN)
    d.zone("AWS Region (multi-AZ managed; account per environment)", 280, 60, 1100, 920, "#d79b00")
    d.zone("Edge & Identity", 300, 100, 220, 220, "#b85450")
    apigw = d.box(
        "Amazon API Gateway\nREST, Cognito authorizer,\nthrottling, X-Ray", 320, 140, 180, 80, AWS
    )
    cog = d.box("Amazon Cognito user pool\n(JWT, tenant claim)", 320, 235, 180, 60, AWS)
    d.zone("Compute", 540, 100, 420, 330, "#6c8ebf")
    lam1 = d.box("Lambda py3.11\nRequest handler (x86_64)", 560, 140, 180, 60, AWS)
    lam2 = d.box("Lambda py3.11\nEvent handler", 770, 140, 170, 60, AWS)
    rt = d.box(
        "Bedrock AgentCore Runtime\nPython 3.13 code asset (S3)\nMMDSv2 required, PUBLIC network\nresource policy: request Lambda role only",
        560,
        225,
        380,
        90,
        AWS,
    )
    lam3 = d.box("Lambda py3.11\nGateway tool", 560, 335, 180, 60, AWS)
    gwy = d.box("AgentCore Gateway\nMCP, AWS_IAM authorizer", 770, 335, 170, 60, AWS)
    d.zone("AI services", 1000, 100, 360, 330, "#d79b00")
    brk = d.box("Amazon Bedrock\nClaude model (approved id)", 1020, 140, 320, 55, AWS)
    gr = d.box("Bedrock Guardrails", 1020, 210, 320, 45, AWS)
    mem = d.box(
        "AgentCore Memory\n(semantic, preference, summary;\nKMS, 30-day events)",
        1020,
        270,
        320,
        70,
        AWS,
    )
    kb = d.box(
        "Bedrock Knowledge Base\n(+ OpenSearch Serverless, S3 docs)", 1020, 355, 320, 55, AWS
    )
    d.zone("Stateful (KMS CMK encrypted)", 300, 470, 1060, 200, "#82b366")
    d.box("DynamoDB\nsession table (PITR, streams)", 320, 520, 200, 80, DATA)
    d.box("DynamoDB\nidempotency table (TTL)", 540, 520, 180, 80, DATA)
    d.box("EventBridge bus\n+ rules", 740, 520, 150, 80, DATA)
    d.box("SQS queue + DLQ", 910, 520, 140, 80, DATA)
    d.box("Secrets Manager\nSSM Parameters", 1070, 520, 150, 80, DATA)
    d.box("AWS KMS CMK", 1235, 520, 110, 80, DATA)
    d.zone("Operations & Security", 300, 710, 1060, 250, "#9673a6")
    d.box("CloudWatch Logs\n7-day, data protection masking", 320, 760, 220, 70, OBS)
    d.box("CloudWatch alarms\nAPI 5xx/p95, Lambda, log findings", 560, 760, 220, 70, OBS)
    d.box("SNS topic (KMS)\nno default subscriber", 800, 760, 200, 70, OBS)
    d.box("X-Ray tracing", 1020, 760, 150, 70, OBS)
    d.box("IAM permissions boundary\nleast-privilege roles", 320, 850, 300, 60, SEC)
    d.box("CDK Nag / assertions (CI)", 640, 850, 240, 60, SEC)
    d.zone("CI/CD", 1420, 60, 260, 200, "#666666")
    d.box("GitHub Actions\nOIDC deploy role\ncdk synth / diff / deploy", 1440, 110, 220, 90, EXT)
    d.zone("Bank DC / SaaS", 1420, 300, 260, 340, "#666666")
    d.box("CRM (Salesforce / CRM Next)", 1440, 350, 220, 55, EXT)
    d.box("Core Banking System", 1440, 420, 220, 55, EXT)
    d.box("KYC / AML provider (to be selected)", 1440, 490, 220, 55, EXT + "dashed=1;")
    d.text(
        "NFR-driven changes vs LOM: Cognito + resource policy (security), DLQ + managed multi-AZ (availability), KMS CMKs + PITR (data protection), alarms + SNS (operability), SSM handoff to avoid reverse stack dependency.",
        300,
        925,
        1060,
        50,
        "fontSize=10;fontStyle=2;",
    )
    d.edge(cbrowser, apigw, "HTTPS / TLS")
    d.edge(apigw, cog, "", "dashed=1;")
    d.edge(apigw, lam1)
    d.edge(lam1, rt, "SigV4")
    d.edge(rt, gwy, "MCP")
    d.edge(gwy, lam3)
    d.edge(rt, brk)
    d.edge(rt, mem, "", "dashed=1;")
    d.edge(rt, gr, "", "dashed=1;")
    d.edge(rt, kb, "", "dashed=1;")
    d.save("05_POM.drawio")


# ---------------------------------------------------------------- Exercise 7
def aop() -> None:
    d = Diagram(
        "Architecture on a Page", "Exercise 7 - Architecture on a Page: Aria on AWS", 1700, 1000
    )
    d.text(
        "<b>Vision:</b> A safe, compliant, context-aware AI relationship manager for Premier / Imperia clients with deterministic workflow state, guarded model use, and human escalation.",
        30,
        45,
        1640,
        40,
        "fontSize=12;",
    )
    # flow lane
    d.box("1. Channel\nWeb / Mobile\nclient", 30, 110, 200, 90, HUMAN)
    d.box("2. Edge & AuthN\nAPI Gateway +\nCognito JWT", 290, 110, 200, 90, AWS)
    d.box("3. Request Lambda\nidentity, idempotency,\nsession mapping", 550, 110, 200, 90, AWS)
    d.box(
        "4. AgentCore Runtime\nAria agent (Strands)\nGuardrails - Workflow - Tools",
        810,
        110,
        240,
        90,
        INT + "strokeWidth=3;",
    )
    d.box(
        "5. AI Services\nBedrock Claude - Guardrails\nKnowledge Base - Memory",
        1110,
        110,
        240,
        90,
        AWS,
    )
    d.box("6. Enterprise systems\nCRM - Core Banking -\nKYC/AML provider", 1410, 110, 240, 90, EXT)
    for x in (230, 490, 750, 1050, 1350):
        d.line(x, 155, x + 60, 155)
    d.zone("Key architecture decisions", 30, 260, 800, 420, "#6c8ebf")
    d.text(
        "<b>AD1</b> Authorization outside the model: Cognito + IAM + resource policy; tool visibility is not authz.<br/>"
        "<b>AD2</b> Workflow state is authoritative (typed patches, revisions, dependency invalidation); memory never overrides it.<br/>"
        "<b>AD3</b> Fail closed: guardrails, missing KYC provider, unavailable KB -> escalate, never fabricate.<br/>"
        "<b>AD4</b> Shared framework + manifest-driven agents; business logic stays in agent/domain modules.<br/>"
        "<b>AD5</b> Managed serverless AgentCore (Runtime, Memory, Gateway) over self-run containers.<br/>"
        "<b>AD6</b> 4 CDK stacks by lifecycle: Stateful -> Application -> Gateway -> Runtime; SSM only for runtime handoff.<br/>"
        "<b>AD7</b> Gateway publishes only no-argument risk questionnaire until user-to-customer mapping is approved.<br/>"
        "<b>AD8</b> Memory writes disabled until data-owner retention/consent policy approved.",
        50,
        300,
        760,
        360,
        "fontSize=11;",
    )
    d.zone("Event-driven retention path", 860, 260, 790, 200, "#82b366")
    d.box("Banking events", 880, 320, 150, 60, EXT)
    d.box("EventBridge bus", 1060, 320, 150, 60, DATA)
    d.box("Event Lambda\n(maturity <= 30d,\nlarge outflow)", 1240, 320, 170, 60, AWS)
    d.box("SQS + DLQ ->\nclient / RM outreach", 1440, 320, 190, 60, DATA)
    for x in (1030, 1210, 1410):
        d.line(x, 350, x + 30, 350)
    d.zone("Risks / open items", 860, 490, 790, 190, "#b85450")
    d.text(
        "- No authoritative KYC/CRM provider contract yet (recommendations fail closed).<br/>"
        "- SLOs (99.9%, p95 &lt; 1s) proposed, not approved.<br/>"
        "- Memory extraction/retention policy and erasure SLA undecided.<br/>"
        "- Customer-specific Gateway actions need authenticated user-to-customer mapping.<br/>"
        "- AWS deployment / invocation not yet verified end to end.",
        880,
        525,
        750,
        140,
        "fontSize=11;",
    )
    d.box(
        "Cross-cutting: Observability (redacted logs, X-Ray, alarms) - Security (KMS, boundary, masking) - Delivery (CDK, OIDC, tests)",
        30,
        710,
        1620,
        50,
        OBS,
    )
    d.box(
        "Quality: Ruff - typing - pytest/Hypothesis - CDK assertions - secret scan",
        30,
        780,
        1620,
        45,
        EXT,
    )
    d.save("07_Architecture_On_A_Page.drawio")


def security() -> None:
    d = Diagram("Security Viewpoint", "Exercise 7 - Initial Security Viewpoint", 1700, 1000)
    d.zone("Untrusted: Internet / client", 20, 60, 220, 300, "#b85450")
    dev = d.box("Client device\n(untrusted input)", 40, 120, 180, 70, HUMAN)
    d.box("Attacker:\nprompt injection,\ncredential phishing", 40, 220, 180, 80, SEC)
    d.zone("Trust boundary 1: Edge", 280, 60, 260, 300, "#d79b00")
    t1 = d.box(
        "API Gateway\nTLS, throttling,\nCognito authorizer\n(JWT, audience, tenant claim)",
        300,
        120,
        220,
        110,
        AWS,
    )
    d.zone(
        "Trust boundary 2: Application (IAM roles + permissions boundary)",
        580,
        60,
        560,
        300,
        "#6c8ebf",
    )
    t2 = d.box(
        "Request Lambda\nverified principal only;\nidempotency; SSM runtime ARN",
        600,
        120,
        220,
        100,
        AWS,
    )
    t3 = d.box(
        "AgentCore Runtime\nresource policy: only request\nLambda role may invoke;\nJWT re-validated in runtime",
        860,
        120,
        260,
        100,
        AWS,
    )
    d.zone("Content controls", 580, 400, 560, 200, "#b85450")
    d.box(
        "Input guardrails: PIN/CVV/OTP/password redaction,\nprompt-injection block, audit log",
        600,
        440,
        250,
        80,
        SEC,
    )
    d.box(
        "Output guardrails + disclosure rules;\nno internal detail leakage", 870, 440, 250, 80, SEC
    )
    d.zone("Trust boundary 3: Data & secrets", 20, 400, 540, 280, "#82b366")
    d.box("KMS CMK (rotation) on DynamoDB,\nSecrets, SNS, Memory", 40, 450, 240, 80, DATA)
    d.box("Tenant-scoped memory namespaces;\nno new client-data writes", 300, 450, 240, 80, DATA)
    d.box(
        "Secrets Manager: provider creds\n(never in repo, check_secrets.py)", 40, 560, 240, 80, DATA
    )
    d.box(
        "Logs: 7-day retention + data\nprotection masking + findings alarm", 300, 560, 240, 80, DATA
    )
    d.zone("Trust boundary 4: Tools & enterprise", 1180, 60, 480, 620, "#666666")
    d.box(
        "AgentCore Gateway: AWS_IAM (SigV4);\nallowlist = get_risk_questionnaire only",
        1200,
        120,
        440,
        80,
        AWS,
    )
    d.box(
        "Backend authorization is authoritative;\ntool filtering is only context optimization",
        1200,
        220,
        440,
        70,
        SEC,
    )
    d.box(
        "CRM / CBS / KYC: provider credentials from\nSecrets Manager; KYC missing => fail closed",
        1200,
        310,
        440,
        70,
        EXT,
    )
    d.box("Bedrock model: role scoped to approved\nmodel id only", 1200, 400, 440, 60, AWS)
    d.box(
        "Escalation: full context to human RM,\nAML flags to compliance", 1200, 480, 440, 60, HUMAN
    )
    d.zone("Governance & delivery", 20, 720, 1640, 240, "#9673a6")
    d.box(
        "GitHub OIDC federated role,\nno long-lived keys,\nenvironment approvals",
        40,
        770,
        300,
        80,
        EXT,
    )
    d.box(
        "CDK: permissions boundary, tags,\ntermination protection + RETAIN (prod)",
        370,
        770,
        320,
        80,
        EXT,
    )
    d.box(
        "CI gates: Ruff, typing, security scan,\nsecret scan, CDK assertions",
        720,
        770,
        320,
        80,
        EXT,
    )
    d.box("Alarms -> encrypted SNS;\nsubscriber required before prod", 1070, 770, 300, 80, OBS)
    d.box(
        "Open: data-owner approval for memory,\nKYC provider, retention/erasure SLA",
        1400,
        770,
        240,
        80,
        SEC,
    )
    d.edge(dev, t1, "TLS")
    d.edge(t1, t2, "validated JWT")
    d.edge(t2, t3, "SigV4")
    d.save("07_Security_Viewpoint.drawio")


def end_state_architecture() -> None:
    d = Diagram(
        "ARIA End-State Architecture",
        "ARIA Relationship Manager Agent - End-State Architecture",
        2400,
        900,
    )
    d.text(
        "Authenticated client and banking-event flows; "
        "deterministic workflow state remains authoritative. "
        "KYC/AML provider integration is not yet configured.",
        35,
        45,
        2330,
        30,
        "fontSize=12;align=center;fontColor=#555555;",
    )

    d.zone("External Actors & Event Sources", 30, 95, 240, 625, "#666666")
    d.zone("Client Channels & Identity", 290, 95, 230, 625, "#d6b656")
    d.zone("Request & Event Handling", 540, 95, 260, 625, "#d79b00")
    d.zone("AgentCore Runtime - Aria", 820, 95, 360, 625, "#6c8ebf")
    d.zone("Managed AI Services", 1200, 95, 270, 625, "#d79b00")
    d.zone("Enterprise Integrations", 1490, 95, 260, 625, "#666666")
    d.zone("State & Event Backbone", 1770, 95, 275, 625, "#82b366")
    d.zone("Security, Operations & Delivery", 2065, 95, 305, 625, "#9673a6")

    client = d.box(
        "Premier / Imperia Client\n(Web or mobile app)", 50, 150, 200, 65, HUMAN
    )
    rm = d.box(
        "Relationship Manager /\nCompliance Officer",
        50,
        270,
        200,
        65,
        HUMAN,
    )
    event_source = d.box("Core banking events\n(maturity / large outflow)", 50, 410, 200, 70, EXT)

    api = d.aws_box("Amazon API Gateway\nREST: POST /messages", 310, 160, 190, 70, "api_gateway")
    cognito = d.aws_box("Amazon Cognito\nJWT authorizer", 310, 290, 190, 65, "general_saml_token")

    request = d.aws_box("Request Lambda\nidentity, idempotency,\nsession mapping", 558, 155, 224, 85, "lambda")
    event_handler = d.aws_box(
        "Event Lambda\nevaluate maturity / outflow\nreturn recommended action",
        558,
        310,
        224,
        70,
        "lambda",
    )
    session = d.box(
        "Runtime session coordinator\nauthenticated conversation mapping",
        558,
        450,
        224,
        85,
        INT,
    )

    runner = d.box("Framework Runner\ncontext, hooks, cleanup", 840, 145, 320, 65, INT)
    guardrails = d.box(
        "Guardrail Processor\ninput / output checks; fail closed",
        840,
        230,
        320,
        65,
        SEC,
    )
    agent = d.aws_box(
        "Aria Agent (Strands)\nmanaged AgentCore Runtime",
        840,
        315,
        320,
        65,
        "machine_learning",
        INT + "strokeWidth=3;",
    )
    workflow = d.box(
        "Workflow Engine\nvalidated state patches,\nrevision & dependencies",
        840,
        410,
        150,
        100,
        INT,
    )
    tools = d.box(
        "Domain Tools\nCRM - Knowledge - Risk -\nMaturity - Compliance - Escalation",
        1005,
        410,
        155,
        100,
        INT,
    )

    model = d.aws_box("Amazon Bedrock\nClaude foundation model", 1218, 145, 234, 65, "machine_learning")
    kb = d.aws_box("Bedrock Knowledge Base\npolicies / product information", 1218, 235, 234, 65, "machine_learning")
    memory = d.aws_box("AgentCore Memory\ntenant-scoped retrieval", 1218, 325, 234, 65, "machine_learning")
    gateway = d.aws_box(
        "AgentCore Gateway (MCP)\nIAM-authorized risk questionnaire",
        1218,
        415,
        234,
        75,
        "machine_learning",
    )

    crm = d.box(
        "CRM\nprofile & interaction history", 1508, 145, 224, 65, EXT
    )
    core = d.box("Core Banking\nbalances / maturities", 1508, 235, 224, 65, EXT)
    kyc = d.box(
        "KYC / AML provider\nnot yet configured",
        1508,
        325,
        224,
        65,
        EXT + "dashed=1;",
    )
    gateway_tool = d.aws_box("Gateway tool Lambda\nget_risk_questionnaire", 1508, 425, 224, 65, "lambda")
    escalation = d.box("Human escalation\nRM handoff with context", 1508, 525, 224, 65, HUMAN)

    state = d.aws_box("DynamoDB\nsession / workflow state", 1788, 150, 238, 65, "dynamodb", DATA)
    idempotency = d.aws_box("DynamoDB\nidempotency records", 1788, 240, 238, 65, "dynamodb", DATA)
    bus = d.aws_box("Amazon EventBridge\nworkflow event bus", 1788, 385, 238, 65, "eventbridge", DATA)
    d.aws_box(
        "SQS workflow queue + DLQ\nprovisioned; trigger wiring pending",
        1788,
        480,
        238,
        65,
        "sqs",
        DATA,
    )

    d.aws_box("AWS KMS\nencryption keys", 2085, 145, 265, 55, "kms", SEC)
    d.aws_box(
        "Secrets Manager + SSM\nprovider secrets / runtime config",
        2085,
        220,
        265,
        65,
        "secrets_manager",
        SEC,
    )
    observability = d.aws_box(
        "CloudWatch + X-Ray\nredacted logs, metrics, traces",
        2085,
        335,
        265,
        65,
        "cloudwatch",
        OBS,
    )
    alerts = d.aws_box("CloudWatch alarms -> SNS\noperations notifications", 2085, 420, 265, 60, "sns", OBS)
    d.box(
        "AWS CDK v2 + GitHub OIDC\nStateful -> Application -> Gateway -> Runtime",
        2085,
        525,
        265,
        75,
        EXT,
    )

    d.edge(client, api, "HTTPS")
    d.edge(api, cognito, "JWT validation", "dashed=1;")
    d.edge(api, request, "invoke")
    d.edge(request, session, "verified identity")
    d.edge(session, runner, "InvokeAgentRuntime / SigV4")
    d.edge(request, idempotency, "claim / replay", "dashed=1;")
    d.edge(runner, guardrails)
    d.edge(guardrails, agent, "sanitized input")
    d.edge(agent, workflow, "propose state changes")
    d.edge(agent, tools, "tool calls")
    d.edge(session, state, "load / save session", "dashed=1;")
    d.edge(agent, model, "inference", "dashed=1;")
    d.edge(tools, kb, "retrieve", "dashed=1;")
    d.edge(runner, memory, "retrieve context", "dashed=1;")
    d.edge(agent, gateway, "MCP", "dashed=1;")
    d.edge(tools, crm, "read / log")
    d.edge(tools, core, "account data")
    d.edge(tools, kyc, "verification", "dashed=1;")
    d.edge(gateway, gateway_tool, "invoke")
    d.edge(tools, escalation, "handoff")
    d.edge(escalation, rm, "context handoff")
    d.edge(event_source, bus, "banking events")
    d.edge(bus, event_handler, "event trigger")
    d.edge(workflow, state, "validated workflow state", "dashed=1;")
    d.edge(observability, alerts, "alarms")
    d.save("08_Aria_End_State_Architecture.drawio")


if __name__ == "__main__":
    system_context()
    use_case()
    nfr()
    overview()
    component_model()
    sequences()
    location_model()
    deployment_units()
    lom()
    pom()
    aop()
    end_state_architecture()
    security()
