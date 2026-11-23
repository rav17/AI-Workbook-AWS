# Architectural Thinking — Complete Topic Guide

> **Course Context:** This guide covers all topics from the IBM Architectural Thinking Workshop
> (*Learnings-selected* modules 01–10) and the accompanying hands-on exercises
> (*Exercises-selected* EX01–EX07). Each module section contains three parts in order:
> **Theory → Exercise → ECS Example**, so you can see the concept, practice it, then watch it
> applied to the Electronic Census System (ECS) for the Republic of Bolumbia.

---

## Diagrams

All diagrams are draw.io (`.drawio`) files in the [`diagrams-drawio/`](diagrams-drawio/) folder.
Open them with **[app.diagrams.net](https://app.diagrams.net)** (free, browser-based) or the
[draw.io VS Code extension](https://marketplace.visualstudio.com/items?itemName=hediet.vscode-drawio).

| # | File | Used In |
|---|---|---|
| 0 | [`00_topics_thread_overview.drawio`](diagrams-drawio/00_topics_thread_overview.drawio) | Module 2 + Appendix |
| 1 | [`01_architectural_thinking_process.drawio`](diagrams-drawio/01_architectural_thinking_process.drawio) | Module 1 |
| 2 | [`02_ecs_system_context_diagram.drawio`](diagrams-drawio/02_ecs_system_context_diagram.drawio) | Module 3 / Exercise 01 |
| 3 | [`03_ecs_architecture_overview.drawio`](diagrams-drawio/03_ecs_architecture_overview.drawio) | Module 5 / Exercise 02 |
| 4 | [`04_ecs_component_model.drawio`](diagrams-drawio/04_ecs_component_model.drawio) | Module 6 / Exercise 03 |
| 5 | [`05_ecs_sequence_uc01_logon.drawio`](diagrams-drawio/05_ecs_sequence_uc01_logon.drawio) | Module 6 / Exercise 03 |
| 6 | [`06_ecs_logical_operational_model.drawio`](diagrams-drawio/06_ecs_logical_operational_model.drawio) | Module 7 / Exercises 04 & 05 |
| 7 | [`07_ecs_prescribed_operational_model.drawio`](diagrams-drawio/07_ecs_prescribed_operational_model.drawio) | Module 7 / Exercise 05 |
| 8 | [`08_ecs_agile_initial_architecture.drawio`](diagrams-drawio/08_ecs_agile_initial_architecture.drawio) | Module 9 / Exercise 07 |

---

## Table of Contents

1. [Module 1 — What is Architectural Thinking?](#module-1--what-is-architectural-thinking)
2. [Module 2 — What is Architecture?](#module-2--what-is-architecture)
3. [Module 3 — Requirements Aspect · Exercise 01](#module-3--requirements-aspect--exercise-01)
4. [Module 4 — Architectural Decisions and Principles](#module-4--architectural-decisions-and-principles)
5. [Module 5 — Architecture Overview · Exercise 02](#module-5--architecture-overview--exercise-02)
6. [Module 6 — Functional Aspect: Component Modeling · Exercise 03](#module-6--functional-aspect-component-modeling--exercise-03)
7. [Module 7 — Operational Aspect: Operational Modeling · Exercises 04 & 05](#module-7--operational-aspect-operational-modeling--exercises-04--05)
8. [Module 8 — Validation and Viability](#module-8--validation-and-viability)
9. [Module 9 — Agile for Architects · Exercise 07](#module-9--agile-for-architects--exercise-07)
10. [Module 10 — Course Summary and Architect Career](#module-10--course-summary-and-architect-career)
11. [Appendix — ECS Case Study Background](#appendix--ecs-case-study-background)

---

## Module 1 — What is Architectural Thinking?

> 📊 **Diagram:** [`01_architectural_thinking_process.drawio`](diagrams-drawio/01_architectural_thinking_process.drawio)

### 1.1 Theory

#### Core Idea
Architectural thinking is an **iterative, structured process** for solving complex IT problems. It is *not* rushing to a solution; it is deliberately exploring requirements, understanding constraints, and producing a validated architecture before committing to delivery.

#### Inputs, Process, Outputs
| Input | Process | Output |
|---|---|---|
| **Requirements** — what must the system do? | Analyze, decide, design | **Architecture** — how the system is structured |
| **Assets** — what already exists? | Iterate and refine | **Viability** — will it actually work? |
| **Qualities** — how good must it be? | Validate against stakeholders | Sign-off artifacts |

#### Key Principles
- Learn multiple architecture styles — avoid the **"golden hammer"** anti-pattern (treating every problem as a nail because you only carry one tool).
- Fixing a problem often creates another; think holistically.
- Architecture is iterative, never a single pass.

#### Anti-pattern: Golden Hammer
> "When you have a preferred solution style (a 'golden hammer'), every problem begins to look the same, like a silver nail."

### 1.2 ECS Example

Bolumbia's Department of Statistics (DoS) has run a paper-based census for over 100 years. The lead architect could simply reach for the same web-form stack used on the last government project. Instead, they pause:

- They ask: *what is different this time?* — 9.5 million households, a single night of peak load, legal compliance requirements, data sovereignty.
- They recognise the **iterative loop**: requirements → architecture → viability, and back again as assumptions are challenged.
- They resist the golden hammer of "let's just do it the same way as before" and explore cloud-native elastic scaling as a genuinely better fit for the peak-load problem.

> **Learning reinforced:** Architectural thinking is problem-specific. The process forces you to understand the problem before reaching for a solution.

---

## Module 2 — What is Architecture?

> 📊 **Diagram:** [`00_topics_thread_overview.drawio`](diagrams-drawio/00_topics_thread_overview.drawio) — module relationships overview

### 2.1 Theory

#### Definitions
**Architecture as an artefact:**
> The architecture of a system describes its overall *static structure* and *dynamic behavior*. It models the system's elements, their externally manifested properties, and the relationships among them.

**Architecture as a discipline:**
> An engineering discipline that studies methods of designing IT systems that provide a solution to a business problem, satisfying functional and non-functional requirements while balancing stakeholder concerns.

#### Architecture vs. Design
| Dimension | Architecture | Design |
|---|---|---|
| Focus | "Black boxes" — components and nodes as opaque units | "White boxes" — the insides of components |
| Scale | At the level of the system's elements | Inside those elements |
| Question | *What is the structure?* | *How is each part built internally?* |

#### Architectural Domains
- **Business Architecture (BA)** — processes, org models, value streams
- **IT Architecture (ITA)** — the technical system itself; the focus of this course
- **Enterprise Architecture (EA)** — governs multiple solutions across an organization
- **Solution Architecture (SA)** — specific IT solution within EA guardrails

#### Two Complementary Aspects of IT Architecture
```
IT Architecture
├── Functional Aspect   — What the system does; Component Model
└── Operational Aspect  — Where and how it runs; Operational Model
```

#### Why Architecture Matters
- Blueprint that can be reviewed and validated
- Communication tool for all stakeholders
- Foundation for delivery planning, cost estimates, parallel development
- Contractual basis for scope and SLAs
- Enables full life-cycle traceability

### 2.2 ECS Example

The ECS is a *solution-level IT architecture*. As architects we define:
- **Static structure:** components like Form Engine, AuthenticationService, DataAccessLayer
- **Dynamic behavior:** how a respondent logs in, navigates form sections, and submits

The Solution Architect designs within the **Enterprise Architecture** guardrails set by the DoS IT governance team (e.g., "all new systems must use cloud infrastructure"). The architecture sits between:
- **Above:** DoS business requirements (what the census must collect)
- **At:** The ECS architecture (how components and nodes are connected)
- **Below:** Detailed design (how each component's internals are coded)

> **Learning reinforced:** Architecture is not just diagrams — it is the set of decisions that determine the structure and behavior of the system, made at the right level of abstraction.

---

## Module 3 — Requirements Aspect · Exercise 01

> 📊 **Diagram:** [`02_ecs_system_context_diagram.drawio`](diagrams-drawio/02_ecs_system_context_diagram.drawio) — ECS System Context Diagram

### 3.1 Theory

#### Why Requirements Are Critical
- 37% of organizations cite inaccurate requirements as the primary cause of project failure.
- ~30–40% of software development budget is wasted on rework; half of that traces to poor requirements.

#### Four Types of Requirements
| Type | Description | Example |
|---|---|---|
| **Functional Requirements (FR)** | What the system must *do* | "The system shall allow respondents to log on using CFN and ECN." |
| **Non-Functional Requirements (NFR)** | How *good* the system must be | "The system shall respond within 3 seconds at the 95th percentile." |
| **Constraints** | Limitations that cannot be changed | "The solution must be cloud-hosted." |
| **Future Requirements** | Anticipated changes or enhancements | "The system may need to support non-private dwellings in a future release." |

#### Sources of Requirements
- **Project Context** — business objectives, assumptions, SOW
- **Enterprise Architecture** — principles, standards, reference architectures
- **Business Case** — investment drivers, ROI criteria
- **IBM Design Thinking** — empathy maps, Hills, user stories

#### SMART Requirements
Requirements must be:
- **S**pecific — unambiguous and at the right level of detail
- **M**easurable — verifiable; includes a success criterion
- **A**ttainable — technically and resource feasible
- **R**ealizable — realistic within constraints
- **T**raceable — linked from inception through test

As a group, requirements must also be *non-conflicting* and *prioritized* (MoSCoW: Must / Should / Could / Would).

#### System Context Diagram (SCD)
The SCD captures the **boundary** of the target system and all external actors (human and system) that interact with it. It answers:
1. *Who* interacts with the system?
2. *What* data flows in/out?
3. *How* does communication happen?

#### Functional Requirements Tools
- Use Case Model (bubble diagram + use case specifications)
- User Stories (Agile) — "As a [role], I want [action] so that [benefit]"
- Business Process Models
- IBM Design Thinking Hills

#### Non-Functional Requirement Categories
| NFR Category | Examples |
|---|---|
| Performance | Response time, throughput, concurrent users |
| Availability | HA / CO / CA; MTTR, MTTF, MTBF |
| Security | Authentication, authorization, confidentiality, integrity, non-repudiation |
| Scalability | Vertical (scale up) vs. horizontal (scale out) |
| Volumetrics | Data volume, user count, transaction rate |
| Reliability | Probability of failure, fault tolerance |
| Maintainability | Ease of change, support cost |
| Compliance | Legal, regulatory, audit requirements |
| Disaster Recovery | RPO (Recovery Point Objective), RTO (Recovery Time Objective) |

#### Availability Concepts
```
HA  — High Availability: no unscheduled outages during service hours
CO  — Continuous Operations: 24×7, unscheduled outages may occur
CA  — Continuous Availability (HA + CO): always available, no outages
```

#### Constraints
- **Business constraints:** regulatory, organizational, geographic, risk tolerance, project (time / budget / scope)
- **IT constraints:** existing infrastructure, skills, standards, implementation languages

#### Requirements Management
Requirements are *dynamic*. They need:
- Change management processes
- Requirements Traceability Matrix (RTM) linking requirements → design → tests
- Iterative sign-off with stakeholders

### 3.2 Exercise 01 — Requirements Definition

**Objective:** Produce three artefacts for the ECS case study:
1. A **System Context Diagram** including both human and system actors
2. A **Use Case Model** (bubble diagram) — do not write full use case specifications, just the diagram
3. A **list of key NFRs** the solution must satisfy

**Tips:**
- Debate *which questions to ask*, not the answers.
- Use the instructors "in role" as DoS subject matter experts.
- A good System Context has 6–10 actors; anything more suggests the boundary is wrong.

**Expected deliverables:**
- Flip-chart / slide showing SCD with labelled interfaces
- Use Case bubble diagram grouped by subject area
- Prioritised NFR list using MoSCoW (at least 5 NFRs across different categories)

### 3.3 ECS Example

#### System Context Diagram
> 📊 Open [`02_ecs_system_context_diagram.drawio`](diagrams-drawio/02_ecs_system_context_diagram.drawio) for the full interactive diagram.

```
Human Actors:
  [Respondent]         ──HTTPS──────────────────►  [ECS]
  [Census Collector]   ◄──SMS notification ────────[ECS]
  [DoS Admin User]     ──HTTPS (admin portal)─────►[ECS]
  [Support Staff]      ──monitor/operate───────────[ECS]
  [Developer/Tester]   ──deploy/update─────────────[ECS]

System Actors:
  [DoS Electronic Census Processing System] ◄──census returns + CFN──[ECS]
  [SMS Gateway]        ◄──dispatch collector alert──────────────────[ECS]
  [Census Help Desk]   ◄──usage reports (daily)────────────────────[ECS]

Out of scope:
  [Bolumbia Post]      paper form fallback — not handled by ECS
  [Analysis Systems]   downstream analytics — separate proposal
```

#### Use Case Model (Key Use Cases)
- **UC_01:** Logon (CFN + ECN credentials)
- **UC_02:** Navigate Form Sections
- **UC_03–UC_11:** Complete Person / Dwelling / Address / Feedback Sections
- **UC_12:** Submit Form (desktop and mobile)
- **UC_13:** View Receipt
- **UC_ADM_01:** View Operational Reports
- **UC_ADM_02:** Manage Census Period Configuration

#### Key NFRs
| ID | Category | Requirement | Priority |
|---|---|---|---|
| NFR-PERF-001 | Performance | Page render < 3s at 95th percentile, 500K concurrent respondents | Must |
| NFR-AVAIL-001 | Availability | HA during Census Night (7pm–midnight); no unscheduled outages | Must |
| NFR-SCALE-001 | Scalability | Support up to 1 million concurrent submissions on Census Night | Must |
| NFR-SEC-001 | Security | Authentication via CFN + ECN; JWT tokens; TLS 1.3 in transit | Must |
| NFR-SEC-002 | Security | All census data encrypted at rest (AES-256); DoS-only access to raw data | Must |
| NFR-VOL-001 | Volumetrics | ~9.5 million households; ~3 persons/dwelling; ~50 questions/person | Must |
| NFR-DR-001 | Disaster Recovery | RPO ≤ 1 hour; RTO ≤ 4 hours | Must |
| NFR-COMP-001 | Compliance | Comply with Electronic Transactions Act 2009 and Statistics Act | Must |
| NFR-LOCAL-001 | Data Sovereignty | All census data stored within Bolumbia | Must |
| NFR-MAINT-001 | Maintainability | System must be operable after Census Night for support and reporting | Should |

#### Key Constraints
- Cloud-hosted (DoS project scope requirement)
- No software to install on respondent's device (browser + mobile app only)
- 3-year delivery window to Census Night
- Non-private dwellings out of scope for this release

#### SMART Requirement Example
> ❌ Not SMART: "The system must be fast."
>
> ✅ SMART (NFR-PERF-001): "The ECS shall render each census form page within **3 seconds** at the **95th percentile** for a load of **500,000 concurrent respondents**, measured at the server during **scheduled service hours on Census Night**, using a standard test transaction set approved by DoS."

---

## Module 4 — Architectural Decisions and Principles

### 4.1 Theory

#### What is an Architectural Decision?
A formally documented choice between competing options that explains *why* the solution looks the way it does.

**Elements of an Architectural Decision record:**
| Field | Purpose |
|---|---|
| Unique ID | e.g., AD-001 |
| Decision Statement | "The system will use JWT tokens for authentication." |
| Issue / Problem | What choice needed to be made? |
| Assumptions | What is taken as true? |
| Alternatives | Enumerated options (≥2 alternatives required!) |
| Decision | Which alternative was chosen |
| Justification | Why |
| Implications | Impact on other architectural elements |

#### Best Practices for Decisions
1. State the decision as a question to be answered.
2. Research alternatives well, considering future requirements.
3. Align with enterprise architecture principles.
4. State assumptions explicitly.
5. Document implications on other decisions.
6. Record stakeholder approval.

#### Architectural Principles
**Principle** vs. **Decision**:
- Decisions are made *inside* the project context.
- Principles are imposed *from outside* (Enterprise Architecture); they govern all projects.

**Structure of a principle:**
- **Name** — short identifier
- **Statement** — what the principle requires
- **Motivation** — why the enterprise wants this
- **Implication** — consequences (usually positive for enterprise, may add cost to project)

#### Guidance Hierarchy
```
Policy     → Legally binding; no exceptions possible
Principle  → Enterprise-wide rule; exceptions can be granted by governance
Guideline  → Best practice; not binding; no formal exceptions required
```

#### Pragmatic Decision-Making (Solution Optimization)
Architects must "start with the winning price and see what can go into the solution" rather than build the perfect solution and then cut costs. Proven optimization patterns include:

| # | Pattern | Description |
|---|---|---|
| 1 | Check value proposition | Align solution to client's stated business value |
| 2 | Simplify the architecture | Remove elegance where it adds no value |
| 3 | Breakthrough the design | Apply Osborne's checklist to break assumptions |
| 4 | Integrate facilities | Reduce management overhead; consolidate technology |
| 5 | Rightshape platforms | Challenge dogma around platform selection |
| 6 | Reuse existing assets | Leverage architecture components, tools, processes |
| 7 | Recycle existing code | Wrap or re-engineer rather than rewrite |
| 8 | Apply frameworks | Use rigid development processes with templates |
| 9 | Optimize app dev environment | Apply easiest environment to non-critical functions |
| 10 | Optimize delivery model | 3-tier delivery (onsite/local/global) |
| 11 | Rationalize license lifecycle | Time software acquisition correctly |

### 4.2 ECS Example

#### Enterprise Architecture Principle Applied
| Field | Content |
|---|---|
| **Name** | Cloud First |
| **Statement** | All new DoS systems shall be hosted on a public cloud platform. |
| **Motivation** | Maximize infrastructure flexibility; minimize capital expenditure; enable elastic Census Night scaling. |
| **Implication** | Solution Architects must design for cloud-native or cloud-compatible deployments. On-premises nodes require a governance exception. |

#### Architectural Decision — AD-001
| Field | Content |
|---|---|
| **ID** | AD-001 |
| **Decision** | ECS will use a stateless web tier with a shared Redis session cache. |
| **Problem** | How do we handle ~1 million concurrent respondents on Census Night without single-server session bottlenecks? |
| **Assumptions** | IBM Cloud IaaS supports elastic horizontal scaling of Kubernetes pods; Redis provides sub-millisecond session lookup. |
| **Alternative 1** | Stateful sessions pinned to a single web server cluster using sticky routing |
| **Alternative 2** | Stateless web tier; all session state externalised to a shared Redis cluster |
| **Decision Taken** | Alternative 2 — Stateless web tier |
| **Justification** | Stateless design allows unlimited horizontal Kubernetes pod scaling. Redis HA pair provides fast shared session access. Directly addresses NFR-SCALE-001 (1M concurrent users). |
| **Implications** | (1) Redis cluster node added to the Operational Model. (2) Session data must store only session tokens — no sensitive census response data in Redis. (3) Redis HA pair must be included in DR planning. |

#### Architectural Decision — AD-002
| Field | Content |
|---|---|
| **ID** | AD-002 |
| **Decision** | ECS will use IBM App ID as the identity provider for CFN/ECN authentication. |
| **Problem** | How should ECS validate respondent credentials without building a bespoke identity store? |
| **Assumptions** | IBM App ID supports custom identity sources; it can be configured to validate against DoS pre-populated CFN/ECN database. |
| **Alternative 1** | Custom-built authentication service with direct PostgreSQL lookup |
| **Alternative 2** | IBM App ID (SaaS IAM) with custom identity registry adapter |
| **Decision Taken** | Alternative 2 |
| **Justification** | Reuses IBM Cloud managed service; reduces bespoke code; built-in JWT issuance, audit logging, and MFA capability for future use. Applies optimization **Pattern 6 — Reuse Existing Assets**. |
| **Implications** | App ID SaaS dependency must be assessed for compliance with DoS data sovereignty requirement. |

#### Solution Optimization Patterns Applied
- **Pattern 1 — Value Proposition Check:** DoS business case requires 60% uptake by Census Night. Every decision is evaluated against this target.
- **Pattern 2 — Simplify the Architecture:** Team considered a complex microservices mesh but chose a simpler three-tier architecture (web / app / data) because the form-filling workflow is inherently sequential.

---

## Module 5 — Architecture Overview · Exercise 02

> 📊 **Diagram:** [`03_ecs_architecture_overview.drawio`](diagrams-drawio/03_ecs_architecture_overview.drawio) — ECS Architecture Overview

### 5.1 Theory

#### Purpose
The AOD communicates a **high-level shared vision** of the architecture to all stakeholders — business and technical. It is primarily a *communication* artefact, not a specification.

#### Key Questions an AOD Answers
- Who is the intended audience?
- Which aspect(s) are depicted — functional, operational, logical, physical?
- How "good" is the architecture at a glance?
- When in the project lifecycle was it drawn (Day 1 vs. Day 101)?

#### What an AOD Contains
- Range of delivery mechanisms (browser, mobile, kiosk, etc.)
- Separation of functions (layering)
- Architecture model (e.g., three-tier, four-tier)
- Use of hardware (distributed servers, cloud)
- Access to legacy systems
- Key annotations (scope, HA indicators, integration points)

#### Best Practices
1. Support the value proposition conversation.
2. Tailor to the audience (Enterprise view for business, technical view for IT).
3. Go beyond the enterprise view — show functional *and* operational thinking.
4. Leverage reference architectures as a starting point.
5. Less is often more; avoid crowding.
6. Depict NFR thinking (e.g., annotate HA zones).
7. Show higher-level abstractions, not fine-grained details.
8. Use real system names, not generic labels (e.g., "DoS Processing System" not "Legacy System").
9. Use annotations to convey additional meaning.

#### Anti-patterns
- Information overload (too many details on one diagram)
- Information underload (too vague to be useful)
- Unexplained acronyms
- Wrong level of technical detail for the audience

### 5.2 Exercise 02 — Architecture Overview Diagram

**Objective:** Create an Architecture Overview Diagram (AOD) for the ECS.

**Consider these questions as you draw:**
- Who is your intended audience? (Business? IT? Governance?)
- What aspects does your diagram cover? (Functional? Operational? Both?)
- How will you annotate NFRs like HA and security without cluttering the diagram?
- When in the project lifecycle is this diagram being drawn?

**Expected deliverables:**
- One AOD slide/flip-chart covering users → delivery channels → ECS layers → integration points
- Annotations for key NFRs (e.g., HA zone label, encrypted data note)
- A 2-sentence explanation of the audience and purpose of your diagram

### 5.3 ECS Example

> 📊 Open [`03_ecs_architecture_overview.drawio`](diagrams-drawio/03_ecs_architecture_overview.drawio) for the full interactive diagram.

```
USER CHANNELS
  [Respondent Desktop Browser]  [Respondent Mobile App]
  [DoS Admin Portal]  [Support Staff Monitoring]
         │ HTTPS / TLS 1.3
         ▼
ECS CLOUD HOSTING ENVIRONMENT (IBM Cloud — Bolumbia Region)
  ┌─────────────────────────────────────────────────────────┐
  │  WEB TIER  (IBM CIS + Kubernetes, 2–20 pods, auto-scale)│ ◄─HA annotation
  │  Load Balancer │ WAF │ DialogControl (React + Node.js)  │
  ├─────────────────────────────────────────────────────────┤
  │  APP TIER  (Kubernetes, 4–40 pods, auto-scale)          │
  │  AuthService │ FormEngine │ SubmissionService           │
  │  NotificationService │ ReportingService                 │
  ├─────────────────────────────────────────────────────────┤
  │  DATA TIER  (IBM Managed DBs, HA pair + DR replica)     │ ◄─Encrypted
  │  Redis Session Cache │ PostgreSQL (credentials+forms)   │
  │  IBM API Connect (integration gateway)                  │
  └─────────────────────────────────────────────────────────┘
         │ REST API (mTLS)           │ SMPP/REST
         ▼                          ▼
  [DoS Electronic Census      [SMS Gateway]
   Processing System]         (Collector alerts)
```

**Audience:** Business sponsors + IT governance board (Day 30 of project, proposal review).

**Best practices applied:**
- Audience is mixed business/IT — no code-level detail, but technology names are real.
- HA zone and encryption are annotated.
- Scope boundary is shown (DoS analytics system is outside the boundary).
- Integration points use real system names ("DoS Electronic Census Processing System") not "Legacy System".

---

## Module 6 — Functional Aspect: Component Modeling · Exercise 03

> 📊 **Diagrams:**
> - [`04_ecs_component_model.drawio`](diagrams-drawio/04_ecs_component_model.drawio) — ECS Logical Component Model
> - [`05_ecs_sequence_uc01_logon.drawio`](diagrams-drawio/05_ecs_sequence_uc01_logon.drawio) — UC_01 Logon Sequence Diagram

### 6.1 Theory

#### Why Model Functionally?
Complex systems cannot be understood without decomposing them into **components** — modular, cohesive units of functionality with well-defined interfaces.

#### Component Model
A formal representation of:
- **Static View** — component relationship diagram (structure)
- **Dynamic View** — component interaction/sequence diagram (behavior)

#### Component Classifications
| Dimension | Types |
|---|---|
| **Application vs. Technical** | Application: implements business function; Technical: supports runtime (web server, ESB, DB) |
| **Logical vs. Physical** | Logical: functional responsibility without implementation detail; Physical: actual product/technology selected |

#### Three Steps of Component Modeling
```
Step 1: Identification   → What are the components?
Step 2: Specification    → What are their interfaces?
Step 3: Implementation   → How are they realized (COTS, custom build)?
```

#### Step 1 — Component Identification Principles
| Principle | Definition | Good | Bad |
|---|---|---|---|
| **High Cohesion** | Responsibilities within a component are strongly related | Payment component handles only payment logic | A component handles login, reporting, AND billing |
| **Loose Coupling** | Minimal dependencies between components | Components communicate via defined interfaces | One component directly reads another's internal data |
| **Isolation** | Product/technology dependencies confined to few places | Proxy pattern separates tech choice from logic | Every component hardwired to a specific database API |
| **Granularity** | Appropriate size for the level of abstraction | Business process component at application level | One component per database column |
| **Layering** | Components organized by generality | Dialog → Business → Services → Middleware → System | All logic in one flat layer |

#### Step 2 — Component Specification
For each interface:
- Specify **operations and signatures** (parameters, return types)
- Specify **pre- and post-conditions** (contract of behavior)

#### Step 3 — Component Implementation
Map logical components to physical realization:
- COTS packages (SAP, Salesforce, IBM App ID, etc.)
- Custom-built applications
- Standard platform components

Enterprise guideline: **Reuse before Customise before Buy before Build**

#### Subsystems
A subsystem is a label grouping related components. It has no intrinsic interface of its own — interfaces belong to the components inside it.

#### UML Notation
- **Class diagrams** for static structural views
- **Sequence diagrams** for dynamic behavioral views

### 6.2 Exercise 03 — Component Modeling

**Given use cases (from ECS case study):**

**UC_01: Logon**
- Actor: Respondent
- Main scenario:
  1. Actor requests logon page by providing URL
  2. System displays the Logon page
  3. Actor enters CFN, ECN and presses "Logon"
  4. System verifies credentials — if valid, renders initial section; if invalid, displays error

**UC_12: Submit Form (from mobile device)**
- Actor: Respondent
- Main scenario:
  1. Actor presses "Submit Form" button
  2. System displays "Thank you" page with Receipt Number; asks for feedback
  3. Actor completes feedback and presses "Submit Feedback"
  4. System displays final screen

**Objective:** Produce the following for both use cases:
1. **Structural view** (component relationship diagram) — logical actors connected to "edge" components, which connect to other components
2. **Responsibilities** documented for each component
3. **Two sequence diagrams** — one per use case

**Expected deliverables:**
- Completed logical component relationship diagram
- Component responsibility list (interfaces and signatures if time permits)
- Two completed sequence diagrams with actors and all interacting components

### 6.3 ECS Example

> 📊 Open [`04_ecs_component_model.drawio`](diagrams-drawio/04_ecs_component_model.drawio) for the full component relationship diagram.

#### Component Identification (Step 1)

**Application Layer Components:**
| Component | Subsystem | Responsibilities |
|---|---|---|
| `DialogControl` | ECS_Frontend | Manages form navigation flow; routes requests; handles session timeout |
| `AuthenticationService` | ECS_Frontend | Validates CFN + ECN; issues/invalidates session tokens |
| `FormEngine` | ECS_FormProcessing | Renders sections; validates answers; saves partial responses |
| `SubmissionService` | ECS_FormProcessing | Accepts final form; generates receipt; triggers DoS notification |
| `NotificationService` | ECS_Integration | Sends SMS to Census Collector confirming online submission |
| `ReportingService` | ECS_Integration | Generates daily operational reports for DoS |

**Technical Layer Components:**
| Component | Responsibilities |
|---|---|
| `SessionStore` | Shared Redis-based store for stateless session tokens |
| `DataAccessLayer` | Abstracts all database access (credential lookups, form persistence) |
| `APIGateway` | Manages outbound integration to DoS backend and SMS Gateway |

**Design principle checks:**
> ✅ **High Cohesion:** `FormEngine` handles *only* form navigation and validation — no auth, no notification logic.
>
> ✅ **Loose Coupling:** `FormEngine` invokes `SubmissionService` through its defined interface; it has no knowledge of how the DoS transfer works.
>
> ✅ **Layering:** DialogControl (UI) → FormEngine (Business) → DataAccessLayer (Data)

#### Component Specification (Step 2) — Selected Interfaces

`AuthenticationService`:
```
authenticate(cfn: String, ecn: String) : SessionToken
  Pre-condition:  cfn and ecn are non-null, non-empty strings
  Post-condition: Returns a valid SessionToken if credentials match;
                  throws AuthenticationException otherwise

invalidate(token: SessionToken) : void
  Post-condition: SessionToken is permanently invalidated in SessionStore
```

`FormEngine`:
```
loadSection(token: SessionToken, sectionId: String) : SectionPage
  Pre-condition:  token is valid; sectionId is a recognised census section
  Post-condition: Returns rendered section page with questions

saveAnswer(token: SessionToken, questionId: String, answer: String) : void
  Post-condition: Answer persisted to DataAccessLayer for this respondent
```

`SubmissionService`:
```
submitForm(token: SessionToken, formData: FormResponse) : ReceiptNumber
  Pre-condition:  All mandatory sections are complete and validated
  Post-condition: Response persisted; receipt generated; NotificationService triggered
```

#### Sequence Diagram: UC_01 Logon
> 📊 Open [`05_ecs_sequence_uc01_logon.drawio`](diagrams-drawio/05_ecs_sequence_uc01_logon.drawio) for the full interactive diagram.

```
Respondent  →  DialogControl    : requestLogonPage()
DialogControl  →  Respondent    : displayLogonPage
Respondent  →  DialogControl    : submitCredentials(cfn, ecn)
DialogControl  →  AuthService   : authenticate(cfn, ecn)
  AuthService  →  DataAccessLayer : lookupCredentials(cfn, ecn)
  DataAccessLayer  →  AuthService : credentialRecord (match confirmed)
  AuthService  →  SessionStore    : createSession(userId)
  SessionStore  →  AuthService    : sessionToken (JWT)
AuthService  →  DialogControl    : sessionToken
DialogControl  →  Respondent     : redirect to InitialSection (JWT in HttpOnly cookie)

[alt] Invalid credentials:
  AuthService  →  DialogControl  : AuthenticationException
  DialogControl  →  Respondent   : displayError("Invalid CFN/ECN — please try again")
```

#### Sequence Diagram: UC_12 Submit Form (Mobile)
```
Respondent  →  DialogControl    : pressSubmitForm()
DialogControl  →  FormEngine    : validateAllSections(token)
  FormEngine  →  DataAccessLayer : getFormData(token)
  DataAccessLayer  →  FormEngine  : formData (all sections)
FormEngine  →  DialogControl    : validationOK
DialogControl  →  SubmissionService : submitForm(token, formData)
  SubmissionService  →  DataAccessLayer : persistSubmission(formData)
  SubmissionService  →  NotificationService : sendCollectorSMS(cfn, address)
  SubmissionService  →  APIGateway : transferToDoS(cfn, address)
SubmissionService  →  DialogControl : receiptNumber
DialogControl  →  Respondent    : displayThankYouPage(receiptNumber)
Respondent  →  DialogControl    : submitFeedback(feedback)
DialogControl  →  FormEngine    : saveFeedback(token, feedback)
DialogControl  →  Respondent    : displayFinalScreen
```

#### Component Implementation (Step 3)
| Logical Component | Physical Implementation |
|---|---|
| `DialogControl` | React.js SPA (browser) + Node.js BFF (backend for frontend) |
| `AuthenticationService` | IBM App ID (cloud IAM — SaaS) |
| `FormEngine` | Custom Node.js microservice (Kubernetes) |
| `SubmissionService` | Custom Node.js microservice (Kubernetes) |
| `SessionStore` | IBM Databases for Redis (PaaS, HA pair) |
| `DataAccessLayer` | PostgreSQL ORM on IBM Databases for PostgreSQL |
| `APIGateway` | IBM API Connect (PaaS) |

---

## Module 7 — Operational Aspect: Operational Modeling · Exercises 04 & 05

> 📊 **Diagrams:**
> - [`06_ecs_logical_operational_model.drawio`](diagrams-drawio/06_ecs_logical_operational_model.drawio) — Logical Operational Model (LOM)
> - [`07_ecs_prescribed_operational_model.drawio`](diagrams-drawio/07_ecs_prescribed_operational_model.drawio) — Prescribed Operational Model (POM)

### 7.1 Theory

#### Purpose
The Operational Model (OM) answers: **Where does everything go, and how do we ensure the NFRs are met?**

It is complementary to the Component Model:
- Component Model: *what* runs (functional structure)
- Operational Model: *where* and *how* it runs (deployment structure)

#### Operational Modeling Steps
```
1. Understand NFRs                        → What performance/availability targets must be met?
2. ALOM (optional, separate course)       → Application-level node placement
3. Logical Operational Model (LOM)        → Logical nodes, locations, DUs
4. Prescribed Operational Model (POM)     → Real products, technologies, sizing
```

#### Key Model Elements

**Locations** — Geographic regions where the system is deployed and actors reside.
- Logical: `LL_Office`, `LL_Remote`, `LL_Cloud`
- Prescribed: `PL_IBM_Cloud_Bolumbia`

**Nodes** — Computing environments within a location.
- Logical: `LN_App_Server`, `LN_Database`
- Prescribed: `PN_IBM_Kubernetes_Service`

**Deployment Units (DUs)** — All the "bits" needed to bring a component to life:
| DU Type | Symbol | Description |
|---|---|---|
| Presentation | `U_<name>` | Entry point for actors (web UI, mobile UI) |
| Data | `D_<name>` | Data managed by the component |
| Execution | `E_<name>` | Runtime instance of the component |
| Installation | `I_<name>` | Files needed to install/deploy the component |
| Technical | `TE_<name>` | Technical infrastructure DU |

> **Notation:** Capital `D` = Master copy of data; lower-case `d` = copy/replica

#### Logical Operational Model (LOM)
The LOM places all DUs onto logical nodes across logical locations:
- Derived from Component Model, NFRs, System Context, Business Roles & Locations
- Shows static relationships (node-to-node connections) — does not specify real products yet

**Key placement considerations per DU type:**
- *Presentation DU:* Actor location, skill level, access frequency
- *Execution DU:* Transaction frequency, processing load, response time requirement
- *Data DU:* Scope, volatility, size, lifetime, master vs. copy
- *Installation DU:* Release frequency, size

#### Prescribed Operational Model (POM)
The POM transforms the LOM into real product and technology specifications:
- **Unsized POM:** selects products and technologies (qualitative)
- **Sized POM:** adds quantitative configuration for performance, availability, security

**Product selection approach:**
1. Identify the "Givens" (client IT standards, existing tech)
2. Spot the "Obvious" products (only one viable option)
3. Evaluate the "Adjacent" components (harder choices requiring analysis)

#### Cloud in the POM
| Deployment Model | Description |
|---|---|
| Public | Shared infrastructure; lower cost; elastic |
| Private | Dedicated; higher control; fixed capacity |
| Managed | Infrastructure managed by cloud provider |
| Hybrid | Mix of public and private based on workload NFRs |

| Service Model | Acronym | Description |
|---|---|---|
| Infrastructure as a Service | IaaS | Raw VMs, networking, storage |
| Platform as a Service | PaaS | Runtime, databases, middleware |
| Software as a Service | SaaS | Application functionality as a service |
| Business Process as a Service | BPaaS | Automated business process outsourcing |

**Cloud@POM 4-Step Approach:** Plan → Define → Select → Configure

#### Transaction Walkthroughs
Used to validate the OM at every level:
- Trace each key transaction from end to end through all nodes and connections
- Ask: what happens if this node fails? Is the failure detected? How is data recovered?

### 7.2 Exercise 04 — Location and Deployment Unit Model

**Objective:** Create the first two building blocks of the Logical Operational Model.

**Steps:**
1. **Create a Location Model** — identify all geographic locations where actors and components will reside; use the System Context Diagram and business roles as input
2. **Create a Deployment Unit Model** — for each component in the Component Model answer, list its Presentation, Data, Execution, and Installation DUs; characterise each DU (volatility, size, access frequency)

**Expected deliverables:**
- Completed Location Model with all `LL_` locations labelled and actor counts
- Completed DU Model table listing all DUs per component

### 7.3 Exercise 05 — Logical and Physical Operational Models

**Objective:** Complete the full LOM and create an unsized POM.

**LOM Steps:**
- Use the Location and DU Models from Exercise 04
- Place Actors and Logical Nodes within each Location
- Add connections between Nodes (access mechanism + integration type)
- Place Deployment Units onto their Nodes

**POM Steps:**
- Starting from the LOM, select real technologies for each Logical Node
- Consider how key NFRs (HA, scalability, security, DR) affect the technology choice
- Identify any additional Physical Nodes required to satisfy NFRs (e.g., load balancers, failover nodes)

**Expected deliverables:**
- A complete LOM diagram with locations, nodes, DUs, actors, and connections
- An unsized POM showing technology selections for each node and connection

### 7.4 ECS Example

> 📊 Open the diagrams for the full interactive versions:
> - [`06_ecs_logical_operational_model.drawio`](diagrams-drawio/06_ecs_logical_operational_model.drawio) — LOM
> - [`07_ecs_prescribed_operational_model.drawio`](diagrams-drawio/07_ecs_prescribed_operational_model.drawio) — POM

#### Step 1 — NFRs Driving the Model
| NFR | Impact on Operational Design |
|---|---|
| 1M concurrent users (Census Night peak) | Web and App tiers must auto-scale horizontally |
| HA during Census Night (7pm–midnight) | Kubernetes rolling updates; Redis HA pair; PostgreSQL primary+standby |
| Data sovereignty (Bolumbia only) | All nodes must be in IBM Cloud Bolumbia region |
| RPO ≤ 1 hour | Async replication to DR region |
| RTO ≤ 4 hours | DR PostgreSQL replica must be promotable within 4 hours |

#### Step 2 — Location Model (Exercise 04 deliverable)
```
LL_Respondent_Home    (9.5M households, internet-connected)
LL_Respondent_Mobile  (subset, mobile network access)
LL_Cloud_Primary      (IBM Cloud — Bolumbia region, 1..n auto-scaled nodes)
LL_Cloud_DR           (IBM Cloud — Bolumbia secondary region, standby)
LL_DoS_Datacenter     (existing DoS backend infrastructure)
```

#### Step 3 — Deployment Unit Model (Exercise 04 deliverable)
| Component | Presentation DU | Execution DU | Data DU | Installation DU |
|---|---|---|---|---|
| `DialogControl` | `U_form_browser` | `E_dialog_control` | — | `I_dialog_ctrl` |
| `AuthService` | `U_logon_page` | `E_auth_service` | `D_credential_store` | `I_auth_service` |
| `FormEngine` | — | `E_form_engine` | `D_partial_response` | `I_form_engine` |
| `SubmissionService` | — | `E_submission_svc` | `D_submitted_forms` | `I_submission_svc` |
| `SessionStore` | — | `E_session_store` | `D_session_data` | `I_redis` |
| `NotificationService` | — | `E_notification_svc` | — | `I_notification_svc` |

**DU Characterisation:**
| DU | Volatility | Size | Lifetime | Master/Copy |
|---|---|---|---|---|
| `D_credential_store` | Low (set pre-Census) | Medium (9.5M CFN/ECN pairs) | Long-lived | Master (Primary only) |
| `D_partial_response` | High (every page save) | Small (per household) | Session-scoped | Master (no copy needed) |
| `D_submitted_forms` | Write-once (on submit) | Large (9.5M × ~28 pages) | 7 years (audit) | Master + DR copy |
| `D_session_data` | High (per request) | Very small (JWT token only) | 2 hours (expiry) | No copy required |

#### Logical Operational Model — LOM (Exercise 05 deliverable)
```
LL_Respondent_Home/Mobile
  A_Respondent ──[HTTPS/TLS]──►

LL_Cloud_Primary (IBM Cloud, auto-scaled)
  LN_Web_Tier
    U_form_browser [U]  U_logon_page [U]  E_dialog_control [E]
  LN_App_Tier
    E_auth_service [E]  E_form_engine [E]
    E_submission_svc [E]  E_notification_svc [E]
  LN_Session_Cache
    D_session_data [D, encrypted]
  LN_Database
    D_credential_store [D, Master]
    D_partial_response [D, Master]
    D_submitted_forms [D, Master]
  LN_API_Gateway
    E_api_gateway [E]

LL_Cloud_DR (standby, Bolumbia secondary region)
  LN_Database_DR
    d_submitted_forms [d, copy — async replication]
    d_credential_store [d, copy]

LL_DoS_Datacenter
  A_DoS_Processing_System ◄── REST API (batch nightly)
  A_SMS_Gateway ◄── SMPP/REST
```

#### Prescribed Operational Model — POM (Exercise 05 deliverable)
| Logical Node | Prescribed Technology | Sizing | NFR Driver |
|---|---|---|---|
| `LN_Web_Tier` | IBM Kubernetes Service (IKS), Kubernetes Ingress + IBM CIS WAF | 2–20 pods, 4 vCPU/8GB each | NFR-SCALE-001: 1M concurrent |
| `LN_App_Tier` | IBM Kubernetes Service (IKS) | 4–40 pods, 4 vCPU/16GB each | NFR-SCALE-001 |
| Auth within App Tier | IBM App ID (SaaS) | Managed SaaS — auto-scales | AD-002: reuse IBM service |
| `LN_Session_Cache` | IBM Databases for Redis (PaaS, HA pair) | 8GB each node | NFR-AVAIL-001: no re-login on Census Night |
| `LN_Database` | IBM Databases for PostgreSQL (PaaS, HA primary + 2 standby) | 32 vCPU, 256GB RAM, 4TB SSD encrypted | NFR-AVAIL-001 + NFR-SEC-002 |
| `LN_Database_DR` | IBM Databases for PostgreSQL (PaaS, streaming replica) | Same spec as primary | NFR-DR-001: RPO ≤ 1h |
| `LN_API_Gateway` | IBM API Connect (PaaS) | Managed SaaS | Integration standardisation |
| Connections | TLS 1.3 (all tiers); internal gRPC/REST; mTLS to external systems | 10Gbps internal | NFR-SEC-001 |

**Cloud Deployment Model:** Public Cloud (IBM Cloud, Bolumbia region).

**Service Models:** IaaS (VPC networking) + PaaS (IKS, PostgreSQL, Redis, API Connect) + SaaS (App ID, IBM CIS).

> **Transaction Walkthrough — Census Night Peak Validation:**
> Respondent browser → IBM CIS (TLS termination + WAF) → IKS Web Tier pod (auto-scaled) → gRPC → IKS App Tier FormEngine pod → Redis session lookup (< 1ms) → PostgreSQL credential read → form page rendered < 3s.
> If one App Tier pod crashes: Kubernetes detects failure in ~5s, routes to healthy pods immediately; MTTR (pod restart) < 30s. ✅ Meets NFR-AVAIL-001.

---

## Module 8 — Validation and Viability

### 8.1 Theory

#### Why Validate?
"Humans are imperfect and so are solutions created by them." Catching architectural flaws early is dramatically cheaper than catching them in production.

#### Viability Assessment
Confirms that the proposed solution **can** be delivered and will work:
- Does the architecture fit the wider enterprise context?
- Can it be designed and built within available means?
- Will it perform? Will it be available?
- Is the project team capable of delivering?
- Are technical risks identified and mitigated?

#### Validation
Confirms the architecture **is** correct — that it satisfies requirements:
- Key artefact: **Requirements Traceability and Verification Matrix (RTVM)**
  - Maps every FR and NFR → architectural component → test case
  - Used throughout the project (not just at the end)

#### V-Model for Testing
All tests must trace to requirements; all requirements must have associated tests:
```
Requirements        ←→  Acceptance Testing
High-Level Design   ←→  System Testing
Detailed Design     ←→  Integration Testing
Code                ←→  Unit Testing
```

#### RAID Log
Every project must track:
| RAID Element | Definition |
|---|---|
| **Risk** | Possibility of something negative happening |
| **Assumption** | Believed to be true without direct evidence; must be validated |
| **Issue** | Something currently causing deviation from the requirements baseline |
| **Dependency** | Something that must be in place before the project completes |

#### Risk Management Approach
- **Remove** — eliminate the root cause
- **Contain** — reduce probability or impact
- **Accept** — consciously acknowledge and monitor (for low-impact risks)

#### IBM Tools
- **GS Risk Tool** — structured risk assessment questionnaire
- **CVM (Client Value Management)** — overall project viability
- **TDA / ITR** — quality checkpoints for complex, cross-LOB deals

### 8.2 ECS Example

#### Viability Assessment
| Question | Finding |
|---|---|
| Can the 3-year timeline accommodate dev, UAT, and hardening? | Feasible — but UAT window (3 months) must be committed by DoS before contract sign. Log as Assumption. |
| Is cloud-first viable given data sovereignty? | IBM Cloud Bolumbia region is compliant — confirmed with IBM Cloud legal team. |
| Can the team deliver a 1M-concurrent-user system? | Technically feasible with IKS auto-scaling, but load test must be completed 6 months before Census Night. Log as Risk. |
| Is the team capable? | Risk: team has no prior IBM App ID implementation experience — training plan required. |

#### RAID Log (Sample)
| Type | ID | Description | Action |
|---|---|---|---|
| Risk | R-001 | IBM Cloud Bolumbia region capacity insufficient on Census Night | Containment: pre-purchase reserved IKS capacity; full load test 6 months prior |
| Risk | R-002 | Team lacks IBM App ID expertise | Remove: 2-week App ID training in Sprint 1; IBM lab services on call |
| Assumption | A-001 | DoS Electronic Census Processing API is stable and documented | Validate by Week 4; if incorrect, integration scope may increase significantly |
| Assumption | A-002 | DoS will complete CFN/ECN pre-population before enumeration period | DoS to provide written confirmation; dependency on DoS delivery team |
| Issue | I-001 | Mobile app requirement added late; original scope was browser-only | Re-assess effort with PM; mobile sprint added to backlog |
| Dependency | D-001 | DoS must complete CFN/ECN pre-population 6 months before Census Night | Add to project plan as formal dependency milestone |

#### RTVM (Sample)
| Requirement ID | Requirement | Component / Node | Test Case | Test Type |
|---|---|---|---|---|
| NFR-PERF-001 | Page render < 3s at 95th percentile, 500K concurrent | `LN_Web_Tier`, `LN_App_Tier` | TC-PERF-001: Load test 500K virtual users | Performance |
| NFR-AVAIL-001 | HA during Census Night | IKS + Redis HA + PostgreSQL HA | TC-AVAIL-001: Pod failure injection; verify <30s recovery | Availability |
| NFR-SEC-001 | Authentication via CFN + ECN; JWT tokens | `AuthenticationService` (IBM App ID) | TC-SEC-001: Valid + invalid CFN/ECN pairs; token expiry test | Security |
| NFR-DR-001 | RPO ≤ 1h, RTO ≤ 4h | PostgreSQL DR replica | TC-DR-001: Full DR failover drill | Disaster Recovery |
| FR-FORM-001 | Respondent can submit completed census form | `SubmissionService`, `FormEngine` | TC-FORM-001: End-to-end form completion and submission | Functional |
| NFR-COMP-001 | Comply with Electronic Transactions Act 2009 | Full system | TC-COMP-001: Legal compliance checklist + audit log review | Compliance |

---

## Module 9 — Agile for Architects · Exercise 07

> 📊 **Diagram:** [`08_ecs_agile_initial_architecture.drawio`](diagrams-drawio/08_ecs_agile_initial_architecture.drawio) — Architecture-on-a-Page + Security Viewpoint

### 9.1 Theory

#### Agile Manifesto (Key Values)
```
Individuals and interactions    over processes and tools
Working software                over comprehensive documentation
Customer collaboration          over contract negotiation
Responding to change            over following a plan
```

#### Traditional vs. Agile
| Dimension | Traditional | Agile |
|---|---|---|
| Fixed | Scope | Time and Cost |
| Flexible | Time and Cost (often) | Scope |
| Best for | Known requirements, high complexity, predictable delivery | Exploratory requirements, flexible scope, POC/MVP culture |

#### Flavours of Agile
- **Scrum** — sprints, product owner, scrum master, backlog
- **Extreme Programming (XP)** — pair programming, TDD, refactoring
- **Kanban** — flow-based, WIP limits, continuous delivery
- **SAFe (Scaled Agile Framework)** — portfolio, program, and team levels for large enterprises
- **LeSS, Nexus, DAD** — other enterprise scaling approaches

#### Scrum Key Concepts
- **Sprint** — time-boxed unit (1–4 weeks) of development
- **Product Backlog** — ordered list of requirements (user stories, use cases)
- **Sprint Backlog** — work committed to the current sprint
- **Sprint Review** — playback to stakeholders
- **Sprint Retrospective** — team reflection and improvement

#### Role of the Architect in Agile
| Option | Description |
|---|---|
| Part of Scrum Team | Takes on architecturally significant tasks directly |
| Scrum Stakeholder | Influences Product Owner's backlog prioritization decisions |
| Scrum Product Owner | Makes prioritization and "definition of done" decisions |

#### Intentional Architecture vs. Emergent Design
- **Intentional Architecture** — high-level decisions made up front that constrain and guide teams
- **Emergent Design** — detailed design that evolves sprint-by-sprint within the intentional architecture
- These two are *complementary*, not competing

#### Initial Architecture (Sprint 0)
Created in project initiation (days to weeks):
1. **Architecture-on-a-page** — users, key components, integration points, scope boundary
2. **Initial Functional Viewpoint** — key Component Model with descriptions
3. **Initial Operational Viewpoint** — environments (dev, test, prod), redundancy, connectivity
4. **Initial Security Viewpoint** — authentication flow, identity management steps

Key NFRs to capture early: Performance (95th percentile, peak TPS), Capacity (registered vs. concurrent users), Reliability (HA, DR), Security (auth, encryption).

#### Modern Architectural Styles
| Style | Characteristic | Best for |
|---|---|---|
| **Monolith** | Single deployable unit | Small teams, simple domains |
| **Microservices** | Fine-grained, independently deployable services | Large teams, independent scaling needs |
| **Cloud-Native** | Elastic horizontal scaling, containers, IaC | High-availability, variable workloads |

**Microservice trade-offs:**
- ✅ Independent deployment, scaling, and team ownership
- ⚠️ Remote call overhead, service proliferation, governance complexity

#### DevOps
DevOps unites Development and Operations in a shared culture and toolchain:
- **CI:** every code commit is built and tested automatically
- **CD:** every passing build is deployable
- **Continuous Operations:** deployment and monitoring are automated
- **Release on Demand:** production deployments are a business decision

### 9.2 Exercise 07 — Agile: Initial Architecture

**Objective:** Create two viewpoints from the "initial architecture" for the ECS case study.

**Instructions:**
- Work from the Case Study Background and lectures
- Use PowerPoint to document your viewpoints
- Ensure all critical elements are covered

**Viewpoint 1 — Architecture-on-a-Page** must include:
- **Users:** internal/external, main users impacted
- **Key Components:** software elements to be procured or developed (logical and/or physical)
- **Integration Points:** key integration points for the "golden path" (not everything, just the most important)
- **Scope Boundary:** what is in/out of scope

**Viewpoint 2 — Initial Security Viewpoint** must include:
- Authentication and authorization flow (key steps, not exhaustive)
- Identity management approach
- Key security controls (encryption in transit, at rest)

**Note:** At this stage "unknown is OK and common" — capture what you know and flag gaps.

### 9.3 ECS Example

> 📊 Open [`08_ecs_agile_initial_architecture.drawio`](diagrams-drawio/08_ecs_agile_initial_architecture.drawio) for the full interactive diagram.

#### Architecture-on-a-Page (Sprint 0 Output)

**Users:**
- Respondents (9.5M households) — external, primary users
- Census Collectors (~27K) — receive SMS notifications only
- DoS Admin Users — internal, operational monitoring
- Support Staff — internal, infrastructure monitoring

**Key Components:**
- AuthService (IBM App ID — SaaS)
- FormEngine (Custom Node.js microservice)
- SubmissionService (Custom Node.js microservice)
- NotificationService (Custom Node.js microservice)
- SessionStore (IBM Redis — PaaS)
- DataStore (IBM PostgreSQL — PaaS)

**Integration Points (golden path):**
- DoS Electronic Census Processing System → REST API batch transfer (nightly)
- SMS Gateway → SMPP/REST (real-time collector notifications)

**Scope Boundary:**
- ✅ IN: Census form completion online (desktop + mobile); form submission; collector SMS
- ❌ OUT: Census data analysis systems; non-private dwellings; paper form scanning

**Key NFRs (bullet-point, Sprint 0 format):**
```
Performance:    Page render < 3s at 95th percentile; peak 1M concurrent users
Availability:   HA during Census Night (7pm–midnight); maintenance windows permitted
Security:       CFN/ECN auth; TLS 1.3 in transit; AES-256 at rest; DoS data sovereignty
DR:             RPO ≤ 1h, RTO ≤ 4h
Compliance:     Electronic Transactions Act 2009
```

#### Initial Security Viewpoint (Sprint 0 Output)

**Authentication Flow:**
```
1. Respondent → HTTPS → IBM CIS (WAF + TLS 1.3 termination)
2. CIS → IKS Kubernetes Ingress → DialogControl (web tier pod)
3. DialogControl → IBM App ID: authenticate(cfn, ecn)
4. App ID → PostgreSQL credential store lookup
5. Credential match confirmed
6. App ID → JWT token issued (RS256, 1-hour expiry)
7. JWT stored in HttpOnly + Secure cookie in respondent browser
8. All subsequent API calls: JWT validated by App ID at App Tier boundary
9. Data at rest: AES-256 (PostgreSQL TDE enabled; Redis encryption at rest enabled)
10. All inter-service communication: mTLS (mutual TLS)
```

**Gap flagged at Sprint 0:** Account lockout policy after N failed CFN/ECN attempts — to be confirmed with DoS security team in Sprint 1.

#### Architecture Runway — Enablers for ECS
| Enabler | Sprint | Description |
|---|---|---|
| E1 | Sprint 1–2 | IBM Cloud IKS cluster provisioned; CI/CD pipeline: GitHub → Jenkins → Docker → IKS |
| E2 | Sprint 2–3 | AuthService implemented using IBM App ID; CFN/ECN validation tested |
| E3 | Sprint 3–4 | FormEngine: basic section navigation and answer persistence |
| E4 | Sprint 4–5 | DoS Electronic Census Processing System integration (API contract agreed) |
| E5 | Sprint 6 | Load testing framework established; performance baseline captured |
| E6 | Sprint 8 | DR environment provisioned; failover drill completed |

#### Agile Delivery Model for ECS
- **Methodology:** Scrum, 3-week sprints
- **Architect role:** Scrum Stakeholder — influences backlog prioritization to ensure NFR-driven enablers are not deprioritized in favour of features
- **Architecture documentation:** Living document — Component Model and Operational Model refined each sprint
- **Architectural style:** Microservices (FormEngine, AuthService, SubmissionService independently deployable and scalable)
- **DevOps pipeline:** GitHub → Jenkins CI → Docker build → IBM Container Registry → IKS rolling deploy → Automated regression tests
- **Intentional architecture constraint:** All components must be stateless (AD-001); all state externalised to Redis or PostgreSQL

---

## Module 10 — Course Summary and Architect Career

### 10.1 The Architectural Thinking Process — Final View

```
Requirements → Architecture → Viability
     ↑               ↑             ↑
"What to solve?" "How it works?" "Will it work?"

The process is iterative. Each arrow goes both ways.
New information discovered in any phase feeds back to the others.
```

### 10.2 How All ECS Topics Connect

> 📊 **Open diagram:** [`00_topics_thread_overview.drawio`](diagrams-drawio/00_topics_thread_overview.drawio) — interactive visual of all modules and the ECS thread

```
Module 1: Architectural Thinking
   Iterative process; avoid golden hammer
   ECS: Team iterates rather than blindly reusing last project's stack
         ↓
Module 2: What is Architecture
   Structure + behavior; functional + operational aspects
   ECS: ECS defined as solution-level IT system; EA guardrails from DoS
         ↓
Module 3: Requirements  ──────────────── Exercise 01
   SCD, Use Cases, NFRs, Constraints, SMART requirements
   ECS: SCD (7 actors); 10 NFRs; 4 constraints; SMART NFR-PERF-001
         ↓
Module 4: Decisions & Principles
   AD template; Policies/Principles/Guidelines; Solution Optimization
   ECS: "Cloud First" principle; AD-001 stateless web tier; AD-002 IBM App ID
         ↓
Module 5: Architecture Overview ──────── Exercise 02
   Communication artefact; audience-tailored; best practices
   ECS: 3-tier AOD for business/IT governance audience; HA + encryption annotated
         ↓
Module 6: Functional Aspect ──────────── Exercise 03
   Component Model (Identify → Specify → Implement)
   ECS: 9 components; 3 subsystems; UC_01 Logon + UC_12 Submit sequence diagrams
         ↓
Module 7: Operational Aspect ─────────── Exercises 04 & 05
   Location Model → DU Model → LOM → POM (cloud technology selection)
   ECS: 5 locations; 15 DUs; LOM with DR; POM: IKS + Redis + PostgreSQL + API Connect
         ↓
Module 8: Validation & Viability
   Viability assessment; RTVM; V-Model; RAID log
   ECS: 4 RAID entries; 6 RTVM rows mapping NFRs → components → test cases
         ↓
Module 9: Agile for Architects ────────── Exercise 07
   Sprint 0 initial architecture; architecture runway; microservices; DevOps
   ECS: Architecture-on-a-page + security viewpoint; 6 enablers; GitHub→IKS pipeline
         ↓
Module 10: Summary & Career
   Architect as leader; certification path; lifelong learning
```

### 10.3 IBM Architect Career Ladder
| Band | Title | Certification |
|---|---|---|
| 7 | Associate Architect | Entry point to career |
| 8 | Advisory Architect | Level 1 (Experienced) |
| 9 | Senior Architect | Level 2 (Expert) |
| 10 | Executive Architect | Level 3 (Thought Leader) |
| — | Distinguished Engineer / IBM Fellow | Beyond certification levels |

### 10.4 Final Advice
- Architecture effort is proportional to **complexity**, not the delivery methodology.
- Create "fit for purpose" architecture — avoid gold-plating.
- Find a mentor; start your certification journey.
- Lifelong learning is essential — "to be a leader is to be a teacher."

---

## Appendix — ECS Case Study Background

### About the Case Study
All exercises in this course are based on a single case study: the **Electronic Census System (ECS)** for the Republic of Bolumbia.

### Client
The **Department of Statistics (DoS)** of the Republic of Bolumbia — a prosperous country with a population of over 23 million people. DoS has run a Population and Housing Census for over 100 years, currently every 5 years. The next census is 3 years away.

### Business Purpose
The Census accurately measures the number and key characteristics of people in Bolumbia on **Census Night** (first Tuesday of August, 3 years from now). Everyone in Bolumbia is **legally required** to complete a Census form.

### ECS Scope
**In scope:**
- Online census completion via desktop browser or mobile app
- Cloud-hosted implementation, testing, and production deployment
- Support services for application and infrastructure

**Out of scope:**
- Downstream analysis of census data (separate proposal)
- Non-private dwellings (paper-based for this first release)

### Key Definitions
| Term | Meaning |
|---|---|
| **CFN** | Census Form Number — unique 7-digit number per dwelling assigned by the Census Collector |
| **ECN** | Electronic Census Number — unique 12-digit random number per form; used with CFN as login credentials |
| **CWL** | Collector Workload — ~27,000 collector workloads in total |
| **DoS** | Department of Statistics — the client |
| **ECS** | Electronic Census System — the target system you are architecting |
| **Enumeration Period** | The month of August — period during which Census responses must be submitted |
| **Census Night** | First Tuesday of August, 3 years from now — questions must be answered as of this date |

### Census Form Structure
| Section | Pages (average) |
|---|---|
| Address Section | 1 page (dwelling address details) |
| Person Section | 21 pages average (~3 persons × 7 pages per person; 50 questions per person) |
| Dwelling Section | 6 pages average (~3 persons × 2 pages) |
| Feedback Section | 1 page (optional feedback before submission) |
| **Total** | **~29 pages per average dwelling** |

### Census Business Process
1. ECS developed, tested, and deployed to production hosting by IBM delivery team
2. At the start of enumeration period: ~27,000 Census Collectors deliver paper forms to ~9.5M households, each with an ECN envelope
3. During August: respondents complete Census online via ECS or via paper form
4. ECS transfers CFN + address of online respondents to DoS Electronic Census Processing System
5. DoS sends SMS to the relevant Collector confirming the household has responded online (via ECS)
6. ECS transfers all submitted ECS returns to DoS Electronic Census Processing System
7. Census Collectors return to remaining households to collect paper forms
8. ECS is monitored and supported by IBM hosting support staff
9. Census Help Desk (DoS) handles respondent queries; IBM provides application usage information

---

*Guide synthesized from IBM Architectural Thinking Workshop materials (Version 7). Case study based on the Electronic Census System (ECS) for the Republic of Bolumbia, used under course license.*
