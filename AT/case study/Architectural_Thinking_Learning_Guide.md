# Architectural Thinking: A Practical Learning Guide

> **For working professionals who want to apply architectural thinking in daily software work — not just pass an exam.**

---

## Table of Contents

1. [Lecture 1: Architectural Thinking Overview](#lecture-1-architectural-thinking-overview)
2. [Lecture 2: What Is Architecture?](#lecture-2-what-is-architecture)
3. [Lecture 3: Requirements Aspect](#lecture-3-requirements-aspect)
4. [Lecture 4: Architectural Decisions and Principles](#lecture-4-architectural-decisions-and-principles)
5. [Lecture 5: Architecture Overview](#lecture-5-architecture-overview)
6. [Lecture 6: Functional Aspect](#lecture-6-functional-aspect)
7. [Lecture 7: Operational Aspect](#lecture-7-operational-aspect)
8. [Lecture 8: Validation and Viability](#lecture-8-validation-and-viability)
9. [Lecture 9: Agile for Architects](#lecture-9-agile-for-architects)
10. [Lecture 10: Summary and Close](#lecture-10-summary-and-close)
11. [Quick Reference: Architectural Thinking in Daily Practice](#quick-reference-architectural-thinking-in-daily-practice)

---

## Lecture 1: Architectural Thinking Overview

### What It Covers
This is the "big picture" session. It frames what architectural thinking actually is — a process of taking requirements, applying knowledge of existing assets and patterns, producing an architecture, and then validating it will actually work. It sets the tone: architecture is iterative, messy, and requires resisting the urge to jump to solutions.

### Key Concepts & Frameworks

- **The AT Process Model**: Requirements → Architecture → Viability (with Assets feeding in)
  - *What does the system have to do?* (Requirements)
  - *How is it structured and how does it work?* (Architecture)
  - *After all that, will it work?* (Viability)
  - *Is there anything done this before?* (Assets)
- **The "Golden Hammer" Anti-pattern**: When you have a preferred solution style, every problem looks like a nail. Avoid defaulting to familiar tech.
- **Architecture is iterative and complex**: Not a linear process — expect cycles of discovery and refinement.
- **Inputs-Process-Outputs thinking**: Always ask "what's coming in, what are we doing, what goes out?"

### Practical Takeaways: How to Apply This Monday Morning

- **Resist jumping to solutions.** When a new project lands, spend time understanding the problem before proposing technology.
- **Check your biases.** Ask yourself: "Am I recommending this because it's the best fit, or because it's what I know?"
- **Look for existing assets.** Before building from scratch, check if reference architectures, patterns, or prior solutions exist.
- **Accept imperfection.** Fixing one problem often creates another — design with this awareness.

### Models/Templates/Checklists
| Artifact | Purpose |
|----------|---------|
| AT Process Diagram | Shows the flow from requirements through architecture to viability |
| Course Agenda/Structure | Maps the full journey: Requirements → Decisions → Overview → Functional → Operational → Validation → Agile |

### 💡 Real-World Example

**🎯 What this lecture wants you to learn:** Architecture is a THINKING PROCESS (Requirements → Architecture → Viability), not just drawing diagrams. You must resist jumping to solutions, check your biases, and validate that your design will actually work.

**Scenario:** Your team is asked to build a new customer notification service.

❌ **Without Architectural Thinking (Golden Hammer):**
> "Let's use Kafka — I used it on my last project and it worked great." → You build a Kafka-based system for 50 notifications/day. It's over-engineered, expensive to maintain, and nobody on the team knows Kafka well enough to debug it in production.

✅ **With Architectural Thinking (following the process):**
> 1. **Requirements (What is to be solved?):** "How many notifications? What channels (email, SMS, push)? What's the delivery SLA? What happens if one fails?"
> 2. **Assets (What's available?):** "Do we already have an email gateway? Does our cloud provider have a managed notification service?"
> 3. **Architecture (How should it work?):** For 50 notifications/day, a simple queue + Lambda is cheaper, simpler, and fits the team's skills. Kafka is overkill.
> 4. **Viability (Will it work?):** "If volume grows 100x next year, can we swap in Kafka later without rewriting everything?" (Yes, if we design the interface abstractly.)

**Lesson:** The lecture teaches you that 10 minutes of structured thinking (Requirements → Architecture → Viability) saves months of unnecessary complexity. The "golden hammer" trap is real — always ask "is this the right tool?" not "how do I use my favorite tool?"

---

## Lecture 2: What Is Architecture?

### What It Covers
Defines what architecture actually means (as both an artifact and a discipline), distinguishes it from design, explains why it matters even in cloud/agile/package-driven projects, and positions the different types of architects (solution, enterprise, business, IT) in the ecosystem.

### Key Concepts & Frameworks

- **Architecture (artifact)**: Describes a system's overall static structure and dynamic behavior — its elements, their properties, and relationships.
- **Architecture (discipline)**: Engineering discipline that designs IT systems to solve business problems, balancing stakeholder concerns within constraints.
- **Architecture vs. Design**:
  - Architecture = *between* the elements (black boxes)
  - Design = *inside* the elements (white boxes)
  - Architecture ensures the system "does the right things"; Design ensures it "does things right"
- **Scale is relative**: What's "architecture" at one level is "design" at a lower level and "requirements" at a higher level.
- **Two Aspects of IT Architecture**:
  - **Functional Aspect** (What does it do? How are apps organized?)
  - **Operational Aspect** (Where does it run? How are computers connected?)
- **Architectural Domains**: Business Architecture ↔ IT Architecture; Enterprise Architecture ↔ Solution Architecture
- **Why architecture is NOT optional** — even with cloud, packages, agile, or Design Thinking:
  - It's a communication tool, delivery planning input, cost estimation basis, and contract foundation
  - Enables parallel development, commercial agreements, and risk understanding

### Practical Takeaways: How to Apply This Monday Morning

- **Think in black boxes first.** Define what components do and how they interact before diving into implementation details.
- **Match effort to risk.** The effort on architecture should be proportionate to the risk and return of the project.
- **Communicate intent.** Architecture's primary job is communication — if your diagrams don't help others understand the system, they're not doing their job.
- **Know your role.** Solution Architects solve specific business problems; Enterprise Architects ensure solutions fit the bigger picture.
- **Don't fall for the "we don't need architecture" trap.** Whether it's cloud, COTS, or agile — the system still needs structure, deployment decisions, and NFR validation.

### Models/Templates/Checklists
| Concept | Quick Definition |
|---------|-----------------|
| Functional Aspect | What the system does — application structure and behavior |
| Operational Aspect | Where it runs — infrastructure, nodes, connections |
| Logical vs Physical | Abstract/technology-agnostic vs. specific products/tech |
| Application vs Technical | Business functions vs. supporting middleware/infrastructure |

### 💡 Real-World Example

**🎯 What this lecture wants you to learn:** Architecture describes the STRUCTURE between elements (black boxes), while Design describes what's INSIDE elements (white boxes). Architecture has two main aspects — Functional (what it does) and Operational (where it runs). Even in cloud/agile, you still need architecture because it's fundamentally a communication tool.

**Scenario:** Your team is building an e-commerce checkout service.

**Architecture (between the boxes — black box thinking):**
> "The Checkout Service communicates with the Payment Gateway via a REST API, the Inventory Service via async events, and the Notification Service via a message queue. Each is independently deployable."

**Design (inside the box — white box thinking):**
> "Inside the Checkout Service, we'll use the Strategy pattern for payment providers, a state machine for order status, and PostgreSQL for persistence."

**Why this distinction matters in practice:**
- The architect decides the Payment Gateway is called via REST with a 3-second timeout — that's **architecture** (affects other teams, contracts, failure modes).
- The developer decides to use a retry library with exponential backoff inside the service — that's **design** (internal, doesn't affect anyone else).
- If the developer decided to switch from REST to direct database access to the Payment Gateway's DB — that's an **architectural violation** because it crosses a boundary.

**The two aspects in this example:**
- **Functional Aspect:** Checkout Service calls Payment Gateway (what it does)
- **Operational Aspect:** Checkout Service runs on Kubernetes in AWS us-east-1, Payment Gateway is an external SaaS (where it runs)

**Rule of thumb:** If changing a decision would require another team to change their code → it's architecture. If it's contained within one team's codebase → it's design.

---

## Lecture 3: Requirements Aspect

### What It Covers
The most comprehensive module — covers how to elicit, classify, document, and manage requirements from an architect's perspective. Includes functional requirements (use cases, user stories), non-functional requirements (performance, availability, security, scalability), constraints, and future requirements. Emphasizes that bad requirements are the #1 cause of project failure.

### Key Concepts & Frameworks

- **Four Types of Requirements**:
  - **Functional Requirements (FRs)**: What the system does (qualitative, descriptive)
  - **Non-Functional Requirements (NFRs)**: How good the system is (quantitative, prescriptive)
  - **Constraints**: Things you can't change (existing infra, skills, budget, regulations)
  - **Future Requirements**: How the system might evolve (change cases)
- **Sources of Requirements**: Project Context, Enterprise Architecture, Business Case, IBM Design Thinking
- **SMART Requirements**: Specific, Measurable, Attainable, Realizable, Traceable
- **MoSCoW Prioritization**: Must / Should / Could / Would
- **System Context Diagram**: Defines the system boundary — who/what interacts with the system and how
- **NFR Categories**:
  - **Runtime (observable)**: Performance, Availability, Security, Usability, Volumetrics
  - **Non-runtime (development-time)**: Scalability, Maintainability, Portability, Compliance
- **Availability Concepts**: HA (High Availability), CO (Continuous Operations), CA (Continuous Availability); MTTR, MTTF, MTBF
- **Security Dimensions**: Authentication, Authorization, Integrity, Confidentiality, Non-repudiation
- **Performance requires specifics**: What, When, Where, For what workload, For which users, What percentile
- **Architecturally Significant Requirements**: Those that touch critical or many parts of the solution

### Practical Takeaways: How to Apply This Monday Morning

- **Draw a System Context Diagram early.** It forces you to define boundaries and external interfaces before diving into internals.
- **Never accept vague NFRs.** "The system must be fast" is useless. Push for: "95th percentile response < 2 seconds for 500 concurrent users during business hours."
- **Separate what you're told from what you assume.** Document assumptions explicitly — they become requirements or constraints once validated.
- **Use the "opposing forces" mental model.** Every NFR decision involves tradeoffs (performance vs. security, availability vs. cost). Make these visible.
- **Identify architecturally significant requirements early.** These drive the structure — high-volume functions, security needs, integration points, stringent SLAs.
- **Don't confuse all stakeholders as equal.** A security requirement from compliance may outweigh a nice-to-have from an end user.

### Models/Templates/Checklists

| Artifact | Purpose |
|----------|---------|
| System Context Diagram | Defines system boundary, external actors, and interfaces |
| Use Case Model | Groups all use cases showing actors and system scope |
| NFR Template (NFR-PERF-001) | Structured capture: unique ID, success criteria, measurement point |
| Requirements Traceability Matrix | Links requirements through design, implementation, and test |
| MoSCoW Prioritization | Must/Should/Could/Would ranking |

**NFR Checklist** — ask for each system:
- [ ] Performance targets (response time, throughput)
- [ ] Volumetrics (users, data size, transactions/sec)
- [ ] Availability (HA/CO/CA? Scheduled maintenance windows?)
- [ ] Security (AuthN, AuthZ, encryption, audit)
- [ ] Scalability (vertical/horizontal? Growth projections?)
- [ ] Disaster Recovery (RPO, RTO)
- [ ] Compliance (regulatory, audit trails)
- [ ] Maintainability and supportability

### 💡 Real-World Example

**🎯 What this lecture wants you to learn:** Requirements come in 4 types (Functional, Non-Functional, Constraints, Future). NFRs must be SPECIFIC and MEASURABLE — vague NFRs are useless. A System Context Diagram defines your system boundary. And "architecturally significant" requirements are the ones that shape your entire system.

**Scenario:** You're architecting a healthcare appointment booking system.

**Bad NFR (vague):** "The system must be fast and always available."

**Good NFRs (SMART — Specific, Measurable, Attainable, Realizable, Traceable):**

| ID | Type | NFR | Success Criteria |
|---|---|---|---|
| NFR-PERF-001 | Performance | Appointment search results must load quickly | 95th percentile < 2 seconds for up to 200 concurrent searches during peak hours (8-10 AM) |
| NFR-AVAIL-001 | Availability | System must be highly available during clinic hours | 99.9% uptime Mon-Sat 7AM-9PM; planned maintenance window: Sunday 2-6AM |
| NFR-SEC-001 | Security | Patient data must be protected | All PII encrypted at rest (AES-256) and in transit (TLS 1.2+); access logged for audit |
| NFR-SCALE-001 | Scalability | System must handle growth | Support 10x current user base within 12 months without architectural change |

**The 4 requirement types in this example:**
- **Functional:** "Users can search available slots and book appointments"
- **Non-Functional:** "Search returns in < 2s for 200 concurrent users" (measurable!)
- **Constraint:** "Must integrate with hospital's existing HL7/FHIR system" (can't change this)
- **Future:** "May add video consultations in Phase 2" (plan for extension)

**System Context Diagram (in practice):**
```
[Patient] --HTTPS--> [Booking System] --HL7/FHIR--> [Hospital EHR]
[Doctor]  --HTTPS--> [Booking System] --SMTP------> [Email Service]
[Admin]   --VPN----> [Booking System] --API-------> [SMS Gateway]
```

**Lesson:** The specific numbers (2 seconds, 99.9%, 200 concurrent, AES-256) drive real architectural decisions. "Fast" and "available" drive nothing. The System Context Diagram took 5 minutes but prevented 3 weeks of arguments about scope.

---

## Lecture 4: Architectural Decisions and Principles

### What It Covers
How to formally document the "why" behind your architecture. Covers the difference between decisions (made within a project) and principles (imposed from outside, typically by enterprise architecture). Also introduces pragmatic solution optimization — designing to a price point rather than gold-plating then cost-cutting.

### Key Concepts & Frameworks

- **Architectural Decision**: A formally documented choice where multiple alternatives exist. Template:
  - Unique ID (e.g., AD-065)
  - Issue/Problem statement
  - Assumptions
  - Alternatives (must have >1 or it's not a decision!)
  - Decision taken
  - Justification
  - Implications on other parts of the solution
- **Architectural Principles**: Enterprise-wide rules that constrain all solutions. Structure:
  - Name → Statement → Motivation → Implication
  - Example: "Buy before Build" — increases acquisition cost but reduces ownership cost
- **Guidance Hierarchy**:
  - **Policy**: Legally binding, non-negotiable (data protection, regulations)
  - **Principle**: Enterprise rule, exceptions possible with governance approval
  - **Guideline**: Best practice, not binding, no formal exception needed
- **Solution Optimization Patterns** (11 patterns to avoid over-engineering):
  1. Check Value Proposition
  2. Simplify the Architecture
  3. Breakthrough the Design (Osborne's checklist)
  4. Integrate the Facilities
  5. Rightshape Platforms and Processors
  6. Re-use Existing Assets
  7. Recycle Existing Code
  8. Apply Frameworks or Skeletons
  9. Optimize the Application Development Environment
  10. Optimize the Delivery Model
  11. Rationalize SW/HW License Lifecycle
- **"Design to cost" vs. "Design then cost-cut"**: Start with the winning price and see what fits, rather than designing ideal then slashing.

### Practical Takeaways: How to Apply This Monday Morning

- **Document decisions as you make them.** Don't wait until the end — future-you (or the next architect) needs to know WHY.
- **Never have a single-alternative decision.** If there's only one option, it's a constraint, not a decision. Always research alternatives.
- **Know your enterprise's principles before designing.** Non-compliance discovered late is expensive. Ask early: "What are the givens?"
- **Design to a cost target.** Set the budget first, then shape the solution to fit — don't over-engineer and then painfully cut.
- **Apply the "Simplify the Architecture" pattern constantly.** Ask: "Is this layer actually needed? Does this elegance add real value?"
- **Get stakeholder sign-off on decisions.** Decisions without approval become disputes later.

### Models/Templates/Checklists

| Template | Fields |
|----------|--------|
| Architectural Decision Record | ID, Issue, Assumptions, Alternatives, Decision, Justification, Implications |
| Architectural Principle | Name, Statement, Motivation, Implication |
| Decisions Register | Collection of all ADs for the project |

**Decision-Making Pitfalls to Avoid:**
- [ ] Undocumented or ambiguous decisions
- [ ] Single-alternative decisions (not real decisions)
- [ ] Decisions buried in design documents instead of a register
- [ ] Missing dependencies between related decisions
- [ ] No formal approval process

### 💡 Real-World Example

**🎯 What this lecture wants you to learn:** Every architectural choice should be formally documented as a DECISION with multiple alternatives, justification, and implications. Decisions are different from Principles (enterprise-wide rules). Always "design to a cost" rather than "design ideal then cut."

**Scenario:** Choosing a database for a new order management service.

**Architectural Decision Record:**

| Field | Content |
|---|---|
| **ID** | AD-012 |
| **Issue** | Which database to use for order data (high write volume, ACID required, complex queries for reporting) |
| **Assumptions** | ~5000 orders/day initially, growing to 50K/day in 2 years. Team has SQL experience. |
| **Alternative 1** | PostgreSQL (open source, strong ACID, JSON support, team knows it) |
| **Alternative 2** | MongoDB (flexible schema, horizontal scaling, but weaker ACID, team needs training) |
| **Alternative 3** | AWS DynamoDB (managed, serverless scaling, but limited query flexibility, vendor lock-in) |
| **Decision** | PostgreSQL with read replicas |
| **Justification** | ACID compliance is mandatory for financial data. Team expertise reduces delivery risk. Read replicas handle reporting load. Horizontal scaling via sharding can be added later if needed. |
| **Implications** | Must provision read replicas from day 1. Need connection pooling. Reporting queries go to replicas only. DBA skills needed for operations. |

**Enterprise Principle example that constrained this decision:**
> **Name:** "Cloud-First"  
> **Statement:** All new solutions must use managed cloud services unless a documented exception is granted.  
> **Implication on AD-012:** We chose AWS RDS PostgreSQL (managed) rather than self-hosted PostgreSQL — the principle pushed us toward managed even though self-hosted is cheaper.

**Why this is better than just saying "we'll use Postgres":** In 18 months when someone asks "why didn't we use DynamoDB?" — the answer is documented with reasoning. No guessing, no blame, no re-litigation.

---

## Lecture 5: Architecture Overview

### What It Covers
The Architecture Overview (AO) is the single most important communication artifact for an architect. It's an informal, high-level diagram (or set of diagrams) that conveys the "governing ideas and candidate building blocks" of the system to diverse stakeholders — from business sponsors to development teams.

### Key Concepts & Frameworks

- **Architecture Overview Purpose**:
  - Communicate conceptual understanding to sponsors and stakeholders
  - Provide a shared high-level vision of scope
  - Explore and evaluate alternative architectural options
  - Enable early validation of architectural approach implications
  - Onboard new team members quickly
- **Characteristics of a Good AO**:
  - Informal diagrams (not necessarily UML or formal notation)
  - Can show functional views, operational views, or a combination
  - May include static (structure) or dynamic (collaboration) views
  - Can show alternatives for stakeholder discussion
- **10 Best Practices**:
  1. Clearly support the value proposition
  2. Target the right stakeholder (business vs. technical audience)
  3. Don't stop at one view — each view promotes different thinking
  4. Leverage reference architectures
  5. "Less may be more" — avoid overcrowding
  6. Clearly depict architecture building blocks
  7. Show NFR thinking (HA, security zones, etc.)
  8. Use higher-level abstractions, not fine-grained details
  9. Use real system names, not generic labels
  10. Use annotations to convey context (scope, release boundaries, etc.)
- **Anti-Patterns**:
  - Information overload (too much in one diagram)
  - Information underload (too little to be useful)
  - Unexplained acronyms
  - Technical details inappropriate for a business audience

### Practical Takeaways: How to Apply This Monday Morning

- **Create an AO diagram within the first week of any project.** Even a rough sketch on a whiteboard. It forces alignment.
- **Communication is the primary purpose.** If nobody looks at your architecture diagrams, they're failing. Optimize for understanding, not completeness.
- **Tailor to audience.** Show the CTO a different view than the development lead. Business stakeholders need business language.
- **Keep it on one page.** The moment your overview needs scrolling, it's not an overview anymore.
- **Use it as a living artifact.** Update it as the architecture evolves — it's not a one-time deliverable.

### Models/Templates/Checklists

| Element to Include | What to Show |
|--------------------|--------------|
| Delivery mechanisms | Web, mobile, kiosk, API, etc. |
| Separation of functions | Layers, zones, subsystems |
| Architecture model | N-tier, microservices, event-driven, etc. |
| Hardware/infrastructure | Servers, cloud services, network boundaries |
| Legacy access | Integration with existing systems |
| Key integrations | External system touchpoints |

### 💡 Real-World Example

**🎯 What this lecture wants you to learn:** The Architecture Overview is your #1 COMMUNICATION tool. It must be informal, one-page, tailored to the audience, and convey the "governing ideas" of the system. Different stakeholders need different views. It's NOT about formal notation — it's about understanding.

**Scenario:** You need to explain a food delivery platform's architecture to both the CEO and the engineering team.

**For the CEO (business audience):**
> A simple diagram showing: "Customers order via mobile app → Our platform matches them with restaurants → Delivery partners get notified → Food arrives." With annotations about "Peak capacity: 100K orders/hour" and "Available in 15 cities."

**For the Engineering Lead (technical audience):**
> Same system but showing: API Gateway → Order Service → Restaurant Matching Engine → Notification Service → Driver App. With annotations about "gRPC between services", "Redis for real-time driver location", "PostgreSQL for orders."

**Same system, different AOD for different audiences.** The CEO doesn't need to know about gRPC. The engineer doesn't need to know about city expansion plans. Both diagrams fit on one page.

**Applying the lecture's "10 Best Practices":**
1. ✅ Supports value proposition ("faster delivery for customers")
2. ✅ Targets the right stakeholder (two versions)
3. ✅ Uses real system names ("Redis", "PostgreSQL" — not just "cache" and "database")
4. ✅ Shows NFR thinking ("100K orders/hour" annotation)
5. ✅ Less is more — no 50-box diagram; just the key building blocks

---

## Lecture 6: Functional Aspect

### What It Covers
Deep dive into Component Modeling — how to decompose a system into components, specify their interfaces, and decide how to implement them. This is the "what does the system do internally?" question. Covers principles like cohesion, coupling, isolation, granularity, and layering that determine whether your architecture is good or fragile.

### Key Concepts & Frameworks

- **Component Model**: A formal representation of the internal structure (static view) and behavior (dynamic view) of the solution.
- **Three Steps of Component Modeling**:
  1. **Component Identification**: What are the components? (partition, assign responsibilities, ensure good structure)
  2. **Component Specification**: What are their interfaces? (operations, signatures, pre/post-conditions)
  3. **Component Implementation**: How are they realized? (products, packages, custom build)
- **Component Types**:
  - **Application Components**: Implement business functions (e.g., Payment Processing)
  - **Technical Components**: Support roles like middleware, security, databases
  - **Logical**: Technology-agnostic, focused on responsibility
  - **Physical**: Actual products/packages used for implementation
- **Key Quality Principles**:

| Principle | Good | Bad |
|-----------|------|-----|
| **Cohesion** (within a component) | High — responsibilities are related and work together | Low — unrelated responsibilities bundled together |
| **Coupling** (between components) | Loose — minimal, well-defined interfaces | Strong — components depend on each other's internals |
| **Isolation** | High — product/tech dependencies decoupled via patterns | Low — every component tied to specific technology |
| **Granularity** | Right-sized for the context | Too fine (overhead) or too coarse (monolith) |

- **Layering**: Separating components by generality:
  - Dialog Control layer
  - Business Processing layer (use case logic)
  - Business Services layer (reusable business components)
  - Middleware layer
  - System Software layer
- **Subsystems**: Logical groupings that label major parts (e.g., "Security subsystem", "Order Management subsystem")
- **Component Relationships shown via**:
  - Component Relationship Diagrams (static — who depends on whom)
  - Component Interaction Diagrams / Sequence Diagrams (dynamic — how they collaborate at runtime)
- **Reuse Guideline**: Reuse before Customize before Buy before Build

### Practical Takeaways: How to Apply This Monday Morning

- **Apply the "high cohesion, loose coupling" test to every component.** If a component handles unrelated things, split it. If two components constantly need each other's internals, merge or redesign the interface.
- **Define interfaces before implementations.** Specify what a component offers (operations, data in/out) before deciding how to build it.
- **Use layering to control dependencies.** Components should only depend on things in the same or lower layer — never upward.
- **Isolate technology choices.** Use patterns (Proxy, Adapter, Mediator) so that changing a database or middleware doesn't ripple through the entire system.
- **Start with reference architectures.** Don't reinvent component structures — adapt proven patterns.
- **Document component responsibilities in a catalog.** Even a simple table: Component | Responsibilities | Interfaces | Dependencies.

### Models/Templates/Checklists

| Artifact | Purpose |
|----------|---------|
| Component Relationship Diagram | Static structure — who depends on whom |
| Component Interaction Diagram (Sequence) | Dynamic behavior — runtime collaboration |
| Component/Service Catalog | Table of components with responsibilities and interfaces |
| Subsystem Grouping | Logical partitioning for communication and work allocation |

**Component Quality Checklist:**
- [ ] Is each component highly cohesive? (Single clear purpose)
- [ ] Are components loosely coupled? (Interact via interfaces, not internals)
- [ ] Are technology dependencies isolated?
- [ ] Is granularity appropriate? (Not too big, not too small)
- [ ] Are layers respected? (No upward dependencies)
- [ ] Do interfaces have clear contracts (operations + signatures)?

### 💡 Real-World Example

**🎯 What this lecture wants you to learn:** Decompose systems into COMPONENTS with high cohesion (each does one thing well) and loose coupling (they interact via clean interfaces, not internal knowledge). Use the three-step process: Identify → Specify → Implement. Validate with sequence diagrams to prove data can actually flow.

**Scenario:** Designing an online banking transfer service.

**Bad Component Design (low cohesion, high coupling):**
```
TransferService:
  - validateAccount()
  - executeTransfer()
  - sendEmailNotification()  ← Why is email sending here?
  - generatePDFStatement()   ← Why is PDF generation here?
  - updateFraudScore()       ← Why is fraud logic here?
```
This component does too many unrelated things. If the email system changes, you redeploy the transfer logic. If fraud rules change, you risk breaking transfers.

**Good Component Design (high cohesion, loose coupling):**
```
TransferService:          → Only handles transfer logic
  - validateTransfer()
  - executeTransfer()
  - getTransferStatus()

NotificationService:      → Only handles notifications
  - sendEmail()
  - sendSMS()
  - sendPush()

FraudDetectionService:    → Only handles fraud
  - assessRisk()
  - flagSuspicious()

ReportingService:         → Only handles reports
  - generateStatement()
```
Each component has ONE clear job. They communicate through interfaces (events or APIs). You can change the fraud engine without touching transfers.

**Applying the lecture's three steps:**
1. **Identify:** Split by responsibility — transfers, notifications, fraud, reports
2. **Specify:** Define interfaces — `TransferService.executeTransfer(fromAccount, toAccount, amount) → TransferResult`
3. **Implement:** TransferService = custom Java; NotificationService = AWS SNS; FraudDetection = third-party API

**The test:** "Can I explain this component's purpose in one sentence without using 'and'?" If not, split it.

---

## Lecture 7: Operational Aspect

### What It Covers
The "where does everything go?" question. Covers how to take your component model and deploy it onto real infrastructure — locations, nodes, and connections. Introduces the structured approach of Location Model → Node Model → Deployment Unit Model → Logical Operational Model (LOM) → Prescribed Operational Model (POM), including cloud deployment considerations.

### Key Concepts & Frameworks

- **Operational Model Purpose**: Describes what runs where, ensures achievement of service levels (performance, availability), and describes management/operation of the IT system.
- **Key Relationship**: Functional Aspect (what it does) + Operational Aspect (where it runs) = Complete Architecture
- **The Operational Modeling Technique (4 Steps)**:
  1. **Understand NFRs** — What service levels must be met?
  2. **Application Logical Operational Model (ALOM)** — Application-level nodes and placement
  3. **Logical Operational Model (LOM)** — Logical components on logical nodes in locations
  4. **Prescribed Operational Model (POM)** — Real technologies, products, and sizing
- **Key Building Blocks**:

| Element | What It Represents | Example |
|---------|-------------------|---------|
| **Location** | Geographic place where IT operates | LL_Office, LL_Cloud, LL_Remote |
| **Node** | A processing point (logical or physical) | LN_Application Server, PN_IBM Power |
| **Deployment Unit (DU)** | Aspect of a component that gets deployed | Presentation, Execution, Data, Installation |
| **Connection** | Communication path between nodes | Internal high-speed, external intermittent |
| **Zone** | Security/network boundary | Red Zone, Yellow Zone, Green Zone |

- **Deployment Units (DUs)** — The "bits" that bring a component to life:
  - **Presentation (U_)**: Entry point for actors (web UI, API endpoint)
  - **Execution (E_)**: Runtime processing (app server instances)
  - **Data (D_)**: Information the component uses/manages
  - **Installation (I_)**: Files needed to install/configure
- **LOM → POM Transformation**:
  - Identify "Givens" (mandated by standards/existing IT)
  - Spot "Obvious" products (clear choices)
  - Evaluate "Adjacent" components (harder choices, may need formal selection)
- **Cloud POM Approach (4 Steps)**: Plan → Define → Select → Configure
  - Deployment models: Public, Private, Hybrid, Managed, Hosted
  - Service models: IaaS, PaaS, SaaS, BPaaS
- **Transaction Walkthroughs**: Trace transactions through the OM to validate it works — check failure scenarios, detection, recovery.

### Practical Takeaways: How to Apply This Monday Morning

- **Think in deployment units, not just components.** A "Payment Service" component has a UI (Presentation), processing logic (Execution), a database (Data), and install scripts (Installation). Each may land in different locations.
- **Start with locations.** Where are your users? Where is your data center/cloud? This drives everything else.
- **Use the DU framework for placement decisions.** For each component, ask: Where does the UI render? Where does logic execute? Where does data live? How is it installed/updated?
- **Validate with walkthroughs.** Trace a key user journey through your operational model. What happens if node X fails? Is it detected? Can the user continue?
- **Don't skip the LOM.** Going straight to product choices (POM) without a logical model means your technology decisions aren't justified by architecture.
- **Cloud doesn't eliminate operational thinking.** You still need to decide: which services, what sizing, what redundancy, what connectivity.

### Models/Templates/Checklists

| Artifact | Purpose |
|----------|---------|
| Location Model | Geographic structure of deployment |
| Node Model | Processing points and their types |
| Deployment Unit Model | All DUs per component with NFR characteristics |
| Logical Operational Model (LOM) | DUs placed on nodes in locations (technology-agnostic) |
| Prescribed Operational Model (POM) | Specific products, sizing, configuration |
| OM Walkthrough Diagram | Transaction trace for validation |

**DU Characterization Table:**

| DU Type | Key Questions |
|---------|---------------|
| Presentation | Who uses it? Where are they? How do they access it? |
| Execution | How often? How heavy? Batch or interactive? |
| Data | How big? How volatile? Master or copy? Retention? |
| Installation | How deployed? How updated? Configuration needs? |

### 💡 Real-World Example

**🎯 What this lecture wants you to learn:** Take your components and figure out WHERE they run using a structured process: Location Model → Deployment Units → LOM (logical, technology-agnostic) → POM (physical, specific products). NFRs drive the translation from logical to physical. Each component has multiple deployable parts (Presentation, Execution, Data, Installation).

**Scenario:** Deploying a ride-sharing app.

**Step 1 — Thinking in Deployment Units:**
Your "Ride Matching Service" component actually has 4 deployable parts:

| DU Type | What Gets Deployed | Where |
|---|---|---|
| **Presentation (U_)** | Mobile app screens for riders/drivers | App stores (iOS/Android) |
| **Execution (E_)** | Matching algorithm + business logic | Cloud app servers (auto-scaling) |
| **Data (D_)** | Ride history, driver locations, pricing | Database cluster + Redis cache |
| **Installation (I_)** | Terraform scripts, Helm charts, CI/CD pipeline | DevOps tooling |

**Step 2 — LOM → POM transformation driven by NFRs:**

| LOM (Logical, technology-free) | NFR Driver | POM (Physical, specific choices) |
|---|---|---|
| LN: App Server | Scalability (1M concurrent rides) | 20 Kubernetes pods, auto-scale to 100 |
| LN: Database | Availability (99.99%) | Aurora PostgreSQL Multi-AZ + 3 read replicas |
| LN: Cache | Performance (< 200ms match time) | Redis Cluster 6 nodes, in-memory |
| — | Security | WAF + API Gateway + VPN to payment processor |
| — | Disaster Recovery (RPO < 5min) | Cross-region replication, warm standby |

**Step 3 — Validate with a walkthrough:**
> "Rider opens app → request hits Load Balancer → routes to App Pod → queries Redis for nearby drivers → matches driver → writes to DB → sends push notification. **What if Redis is down?** → Fallback to DB query (slower but functional). **What if a Pod crashes mid-match?** → Kubernetes restarts it, retry from queue."

**Lesson:** The jump from "we need an app server" (LOM) to "20 Kubernetes pods auto-scaling to 100" (POM) is driven entirely by NFRs — not guesswork. And the walkthrough caught the Redis-failure edge case before production.

---

## Lecture 8: Validation and Viability

### What It Covers
How to ensure your architecture will actually work and can actually be delivered. Covers two complementary concerns: **Viability** (can it be built and will it work?) and **Validation** (does it meet the requirements?). Introduces risk management, the RAID framework, the Requirements Traceability and Verification Matrix (RTVM), and the V-model for testing.

### Key Concepts & Frameworks

- **Viability** = Can the solution be designed, developed, and delivered within available means? Will it perform? Will it be available?
- **Validation** = Does the solution satisfy functional and non-functional requirements? Does it do what's needed?
- **Why it matters**: Fixing flawed solutions early is dramatically cheaper than fixing them late. Common causes of troubled projects are almost all avoidable.
- **Viability Assessment Questions**:
  - Does the architecture fit the wider enterprise context?
  - Will the deployed solution be operable and maintainable?
  - Can it be designed within available means (budget, time, skills)?
  - What are the technical risks and how can they be contained?
  - Is the team capable of delivering?
- **Validation via RTVM (Requirements Traceability and Verification Matrix)**:
  - Maps EVERY requirement (FR and NFR) to solution components
  - Provides basis for test planning
  - Framework for risk management
  - Used throughout the project, not just at the end
- **The V-Model**: Every test relates to a requirement, and every requirement has an associated test case.
- **RAID Framework**:

| Element | Definition | Action Required |
|---------|-----------|-----------------|
| **R**isk | Possibility of something negative happening | Remove, contain, or accept |
| **A**ssumption | Taken on faith, not yet verified | Verify → becomes requirement or constraint |
| **I**ssue | Currently causing deviation from baseline | Resolve or re-assess architecture |
| **D**ependency | Something expected to be in place before completion | Document and manage during delivery |

- **Even well-designed solutions are imperfect** due to: limited budgets, new information arriving, skilled resource turnover, and insufficient time.

### Practical Takeaways: How to Apply This Monday Morning

- **Maintain a RAID log from day one.** Don't wait for problems to surface — proactively capture Risks, Assumptions, Issues, and Dependencies.
- **Build your RTVM incrementally.** For every requirement you accept, immediately ask: "How will we prove this is met?"
- **Challenge your own architecture.** Ask viability questions: Can we actually build this? Do we have the skills? Can we afford it?
- **Validate continuously, not at the end.** Use the V-model mindset — every level of design should map back to requirements and forward to tests.
- **Don't fear medium-high risk.** Most real projects start with medium-high risk assessments. The key is having containment plans, not avoiding all risk.
- **Turn assumptions into requirements.** Every assumption is a hidden risk. Validate them early and make them explicit.

### Models/Templates/Checklists

| Artifact | Purpose |
|----------|---------|
| RTVM (Requirements Traceability Verification Matrix) | Maps requirements → design → test |
| RAID Log | Tracks Risks, Assumptions, Issues, Dependencies |
| V-Model | Ensures test coverage maps to every requirement level |
| Viability Assessment Checklist | Structured questions about deliverability |

**Viability Quick-Check:**
- [ ] Is the proposed solution technically feasible?
- [ ] Do we have (or can we get) the skills needed?
- [ ] Is the infrastructure in place or achievable?
- [ ] Are there containment plans for top risks?
- [ ] Does the cost fit the budget?
- [ ] Is the timeline realistic for this complexity?
- [ ] Have we validated with walkthroughs or prototypes?

### 💡 Real-World Example

**🎯 What this lecture wants you to learn:** Validation = does it meet requirements? Viability = can we actually build and deliver it? Use RAID (Risks, Assumptions, Issues, Dependencies) to track project health. Use RTVM to trace every requirement to a test. Walk through transactions on your operational model to find hidden failure modes.

**Scenario:** Your team built a payment processing system. Before go-live, you need to validate it.

**RAID Log (real entries):**

| Type | Description | Status | Action |
|---|---|---|---|
| **Risk** | Payment gateway may throttle during Black Friday peak | Open | Load test with 5x expected volume by Nov 1 |
| **Assumption** | Average transaction takes < 500ms | Needs validation | Run performance benchmark this sprint |
| **Issue** | Timeout errors seen when payment gateway is slow (>3s) | Active | Implement circuit breaker pattern (JIRA-456) |
| **Dependency** | PCI-DSS compliance certificate needed from cloud provider | Waiting | Requested from AWS, ETA Oct 15 |

**RTVM (tracing one requirement end-to-end):**

| Requirement | Design Element | Implementation | Test |
|---|---|---|---|
| NFR-SEC-002: All card data encrypted | Payment Service uses tokenization via Stripe | `PaymentService.tokenize()` method | Test: Verify no raw card numbers in DB or logs |
| NFR-PERF-001: < 2s checkout | Async order confirmation, cached product catalog | Redis cache + async event on checkout | Load test: 1000 concurrent checkouts, measure p95 |

**Transaction Walkthrough (validation by tracing through the operational model):**
> "User clicks Pay → hits Load Balancer → routes to App Server Pod 3 → calls Payment Service → Payment Service calls Stripe API (external) → **What if Stripe is down?** → Circuit breaker activates → user gets 'retry in 30s' message → order saved as PENDING → background job retries in 2 min."

This walkthrough **revealed the need for a circuit breaker** — something invisible in the static diagram. That's why the lecture says "validate actively, not passively."

**Viability check questions applied:**
- ✅ Can we build it? (Team has Node.js + Stripe experience)
- ⚠️ Can we afford it? (Stripe fees at scale need budget validation)
- ❌ Do we have PCI compliance? (Dependency — waiting on AWS certificate)

---

## Lecture 9: Agile for Architects

### What It Covers
How architects operate effectively in agile environments. Covers when to use agile vs. traditional methods, the architect's role in Scrum/SAFe, the concept of "Initial Architecture" (enough to get started without Big Design Up Front), modern architectural styles (microservices, APIs), and DevOps practices.

### Key Concepts & Frameworks

- **Agile Manifesto Essentials** (relevant to architects):
  - Working software over comprehensive documentation
  - Responding to change over following a plan
  - Architecture effort is a function of **complexity**, not methodology
- **Traditional vs. Agile**:
  - Traditional: fixes scope, estimates cost/time
  - Agile: fixes time and cost, scope is negotiable
- **When to Use Which**:

| Factor | Traditional | Agile |
|--------|------------|-------|
| Complexity | High | Low to medium |
| Requirements | Known/stable | Exploratory/evolving |
| MVP scope | 80%+ of full scope | Highly flexible |
| Client culture | Predictability demanded | Tolerates unknown |

- **Architect's Role in Agile Teams** (3 options):
  1. Part of the Scrum team, taking architecturally significant tasks
  2. Stakeholder influencing the Product Owner's backlog and priorities
  3. Acting as Product Owner (for platform/component teams)
- **Intentional Architecture vs. Emergent Design**:
  - Intentional = Upfront decisions that constrain teams (infrastructure, integration patterns, security)
  - Emergent = Design decisions that arise during sprints and feed back into architecture
  - **"Value Initial Architecture Up Front over Big Architecture Up Front"**
- **Architecture Runway**: Architecture enablers implemented through sprints to support future business features.
- **Initial Architecture — What "Enough" Looks Like**:
  1. Architecture-on-a-Page (scope, key components, users, integration points)
  2. Key NFRs (performance, capacity, security, reliability — even as bullet points)
  3. Initial Component Model (key components and relationships)
  4. Initial Operational View (environments, redundancy, connectivity)
  5. Initial Security View (authentication flow for key concerns)
- **Microservices Architecture Style**:
  - Decentralized Ownership → Development agility (Inverse Conway Maneuver)
  - Fine-grained Deployment → Deployment agility (independent release cycles)
  - Cloud-native Infrastructure → Operational agility (elastic scaling, disposable containers)
- **DevOps**: Development + Operations participating together across the entire service lifecycle
  - Maturity: CI/CT → CD → Continuous Operations → Release on Demand
  - Deployment Pipeline: Visibility → Feedback → Continual deployment
- **Scaling Agile Factors**: Team size, domain complexity, geographic distribution, compliance requirements, organizational complexity

### Practical Takeaways: How to Apply This Monday Morning

- **Don't skip architecture in agile — right-size it.** Complexity drives architecture effort, not methodology. A complex microservices system needs just as much architectural thinking as a traditional one.
- **Create your "architecture on a page" in the first sprint.** Capture: users, key components, integration points, infrastructure outline. One slide. Iterate from there.
- **Capture NFRs early, even as assumptions.** "We assume < 2s response time, 99.9% availability, 1000 concurrent users." Refine later but establish the boundary.
- **Maintain the architecture runway.** Ensure technical enablers (logging infrastructure, CI/CD pipelines, shared services) are in the backlog and get prioritized.
- **Attend stand-ups.** The architect needs to hear what's emerging and guide the team when implementation deviates from architectural intent.
- **Protect scope through impact analysis.** When scope changes arrive, describe implications in architectural and cost terms — don't just say "no."
- **Be mindful of service granularity.** Too fine → performance death by network calls. Too coarse → monolith problems. Find the balance.

### Models/Templates/Checklists

| Artifact | Purpose |
|----------|---------|
| Architecture-on-a-Page | One-slide scope and vision for stakeholders |
| Initial NFR Bullet Points | Minimal set of quality requirements |
| Architecture Runway Backlog | Technical enablers to be implemented in sprints |
| Component Model (lightweight) | Key components and relationships |

**"Is My Initial Architecture Enough?" Checklist:**
- [ ] Can stakeholders understand the solution scope from the AO?
- [ ] Are key NFRs captured (even as assumptions)?
- [ ] Is the component model sufficient for teams to start work in parallel?
- [ ] Is the operational view clear enough for infrastructure provisioning?
- [ ] Are primary security concerns addressed (authentication flow)?
- [ ] Are key architectural decisions documented?

### 💡 Real-World Example

**🎯 What this lecture wants you to learn:** In agile, architects don't disappear — they right-size their effort. Create "Initial Architecture" (enough to start, not a 200-page doc). Use "Intentional Architecture" for cross-team constraints while allowing "Emergent Design" within teams. Maintain an "Architecture Runway" of enablers in the backlog.

**Scenario:** Your team starts a new project to build an internal employee skills portal. Sprint 0 = 2 weeks.

**Initial Architecture created in Sprint 0 (just enough to start):**

**Architecture-on-a-Page (one slide):**
> - **Users:** 5000 employees, HR admins, managers
> - **Channels:** Web browser (responsive), SSO login via company Azure AD
> - **Solution:** React SPA → Node.js API → PostgreSQL | Hosted on company Azure subscription
> - **Integrations:** Azure AD (auth), existing HR system (employee data sync), Slack (notifications)
> - **Key NFRs:** < 2s page load, 99.5% uptime (business hours), GDPR-compliant data handling
> - **Key Decisions:** AD-001: Use existing Azure AD (not build custom auth). AD-002: Monolith first, extract services later if needed.
> - **Top Risk:** HR system API is undocumented — need spike in Sprint 1 to test integration.

**Intentional Architecture (architect decides, teams must follow):**
- All services authenticate via Azure AD tokens (non-negotiable)
- All APIs follow OpenAPI 3.0 spec (enables contract testing)
- All deployments go through the shared CI/CD pipeline

**Emergent Design (teams discover during sprints, architect incorporates):**
- Sprint 2: Team discovers HR API paginates weirdly → adapter pattern added
- Sprint 4: Search is slow → team proposes Elasticsearch → architect evaluates and approves

**Architecture Runway (enablers in the backlog):**
- Sprint 1: Set up CI/CD pipeline + Azure infrastructure (enabler)
- Sprint 2: Implement auth middleware (enabler)
- Sprint 3: Set up monitoring/alerting (enabler)

**What this enables:**
- Frontend team starts building React components immediately (they know the API shape)
- Backend team starts scaffolding Node.js service (they know the data model roughly)
- DevOps sets up Azure infrastructure (they know the hosting model)
- Product Owner can refine backlog knowing the constraints

**What it intentionally DEFERS:**
- Exact database schema (emerges from user stories)
- Caching strategy (measure first, optimize later)
- Microservice extraction (premature at this scale)

**Lesson:** "Initial Architecture" isn't "no architecture" — it's "enough architecture to move safely, deferred everywhere else." Complexity drives architecture effort, not methodology.

---

## Lecture 10: Summary and Close

### What It Covers
Wraps up the course by revisiting all key objectives, positioning the architect career path (from Associate to Distinguished Engineer), and emphasizing that this course is a starting point — not a finishing point. Highlights the importance of leadership, mentorship, and continuous learning.

### Key Concepts & Frameworks

- **The Complete AT Process (revisited)**: Requirements → Architecture → Viability, informed by Assets (reference architectures, patterns, building blocks)
- **What You Should Now Be Able To Do**:
  - Describe architecture and its models (functional, operational)
  - Elicit and analyze architecturally significant requirements
  - Classify NFRs and architect for them
  - Create Architecture Overviews
  - Make and document architectural decisions
  - Apply principles (loose coupling, high cohesion, buy before build)
  - Build Component Models and Operational Models
  - Validate architectures and assess viability
  - Work effectively as an architect in agile teams
- **Career Growth Path**: Associate Architect → Advisory → Senior → Executive → Distinguished Engineer → Fellow
- **Leadership is essential**: Architects are leaders on every project — communicating, negotiating, guiding.
- **Recommended Next Steps**:
  - Design Thinking
  - Operational Modeling (deeper)
  - Component Modeling (deeper)
  - Performance Engineering
  - Enterprise Architecture
  - Find a mentor

### Practical Takeaways: How to Apply This Monday Morning

- **Start practicing immediately.** You won't become a master architect from a course — only from applying the thinking repeatedly.
- **Find a mentor.** Someone who has navigated architectural challenges and can provide feedback on your thinking.
- **Think like an architect in every task.** Even small features benefit from asking: "What are the requirements? What's the structure? What are the tradeoffs? Will this work?"
- **Build your own reference library.** Collect patterns, decisions, and models from every project. They become your reusable assets.
- **Leadership = Communication.** The best architecture in the world is useless if you can't explain it, defend it, and get buy-in.

### 💡 Real-World Example: End-to-End Thinking in a Small Feature

**🎯 What this lecture wants you to learn:** Architectural thinking isn't just for big projects or senior architects. It's a DAILY PRACTICE that every developer can apply. The complete process (Requirements → Architecture → Viability) works at any scale — from a full system to a single feature. Start practicing now, find a mentor, and build your own library of patterns.

**Scenario:** You're a developer asked to "add export to Excel" for a reports page.

**Without architectural thinking:** You add a button, write the Excel generation inline in the controller, and ship it. It works for 100 rows but crashes with 100K rows. Nobody thought about it.

**With architectural thinking (takes 15 extra minutes):**

| Step | Question | Answer |
|---|---|---|
| **Requirements** | How big can the export be? | Ask PM: up to 500K rows. NFR: must complete < 30s |
| **Constraints** | Server memory limit? | 512MB per pod — can't hold 500K rows in memory |
| **Decision** | Sync vs async? | AD: Async — generate file in background, notify user when ready |
| **Component** | Where does generation logic live? | New ReportExportService component (not in the controller) |
| **Operational** | Where does the file go? | S3 bucket with 24-hour TTL — not local disk (stateless pods) |
| **Validation** | What if it fails halfway? | Retry logic + "Export Failed" notification to user |
| **Risk** | What if 50 users export simultaneously? | Queue with max 5 concurrent exports, others wait in line |

**Result:** You shipped a feature that works at scale, doesn't crash, and handles edge cases. Your PM is happy. Your SRE team isn't paged at 2AM. And it only took 15 minutes more thinking upfront.

**This is architectural thinking applied to everyday work — not just big projects.**

---

## Quick Reference: Architectural Thinking in Daily Practice

### The 5-Minute Architecture Mindset

Before diving into any technical work, ask yourself:

1. **What's the problem?** (Not the solution — the problem.)
2. **Who cares?** (Stakeholders, users, operators)
3. **What are the constraints?** (Budget, timeline, existing tech, skills, regulations)
4. **What has worked before?** (Reference architectures, patterns, existing assets)
5. **How will we know it works?** (Validation criteria, test strategy)

---

### Daily Habits of Effective Architectural Thinkers

| Habit | What It Looks Like |
|-------|-------------------|
| **Think in tradeoffs** | Never present one option. Always: "We could do A (faster, less flexible) or B (slower, more scalable)." |
| **Document decisions** | Even in a Slack message: "We chose X because Y. We considered Z but rejected it because..." |
| **Draw the boundary** | Before building, sketch what's inside vs. outside your system (System Context). |
| **Name your assumptions** | "We're assuming 500 users. If it's 5000, this design breaks here." |
| **Validate early** | Build a spike/PoC for the riskiest part first, not the easiest. |
| **Keep NFRs visible** | Put response time, availability, and security targets on the team board — not buried in a doc. |
| **Separate what from how** | Define what a component does before deciding which product implements it. |

---

### The Architecture Toolkit — What to Reach For

| Situation | Tool/Approach |
|-----------|---------------|
| Starting a new project | System Context Diagram → Architecture Overview → Initial NFRs |
| Designing internals | Component Model (identify → specify → implement) |
| Deciding deployment | Deployment Units → Location Model → LOM → POM |
| Making a technology choice | Architectural Decision Record (with alternatives!) |
| Validating the design | Transaction walkthroughs + RTVM + RAID log |
| Communicating to business | Architecture-on-a-Page (one slide, plain language) |
| Working in agile | Initial Architecture → Architecture Runway → Enablers in sprints |
| Assessing risk | RAID framework + Viability Assessment checklist |

---

### Key Principles to Live By

1. **Avoid the Golden Hammer.** The tool you know best isn't always the right one.
2. **Requirements drive architecture, not technology.** Start with what needs to be solved.
3. **Architecture is communication.** If others can't understand your design, it's not serving its purpose.
4. **High cohesion, loose coupling — always.** This applies to components, teams, and services.
5. **Design to a cost.** Shape solutions to fit reality, don't gold-plate then cost-cut.
6. **Validate continuously.** Don't wait until the end to find out it doesn't work.
7. **Intentional over Big.** Enough architecture to align the team, not a 200-page document nobody reads.
8. **Document the why.** Code shows what was built. Decisions show why it was built that way.
9. **Reuse before Customize before Buy before Build.** In that order.
10. **Accept imperfection and iterate.** Architecture evolves. Ship a viable version, learn, improve.

---

### Quick-Reference Glossary

| Term | Plain-Language Definition |
|------|--------------------------|
| **Functional Aspect** | What the system does — its components, interfaces, and behavior |
| **Operational Aspect** | Where the system runs — infrastructure, nodes, network, deployment |
| **Component Model** | Map of the system's internal building blocks and how they interact |
| **Operational Model** | Map of where components are deployed and how infrastructure is organized |
| **Architecture Overview** | High-level "one-pager" that communicates the solution approach |
| **NFR** | Non-functional requirement — how good the system needs to be (speed, uptime, security) |
| **Deployment Unit** | One aspect (UI, logic, data, install) of a component that gets deployed somewhere |
| **LOM** | Logical Operational Model — deployment design without specific product choices |
| **POM** | Prescribed Operational Model — specific products, versions, sizing, configuration |
| **RTVM** | Requirements Traceability Verification Matrix — links requirements to design to tests |
| **RAID** | Risks, Assumptions, Issues, Dependencies — project health tracker |
| **Architecture Runway** | Backlog of technical enablers that support future business features |
| **Intentional Architecture** | Upfront architectural decisions that constrain and guide agile teams |
| **Emergent Design** | Design decisions that arise during sprints as teams learn more |

---

### Your First Week Checklist for Any New Project

- [ ] Read/understand the business case and project context
- [ ] Identify key stakeholders and their primary concerns
- [ ] Draw a System Context Diagram (system boundary + external actors)
- [ ] Capture top 5 architecturally significant requirements (FRs and NFRs)
- [ ] Identify known constraints (tech standards, budget, timeline, skills)
- [ ] Sketch an Architecture Overview (one page, informal)
- [ ] List top 3 architectural decisions that need to be made
- [ ] Document initial assumptions in a RAID log
- [ ] Find relevant reference architectures or prior similar solutions
- [ ] Identify the riskiest aspect and plan early validation (PoC/spike)

---

> **Remember**: You don't need to be a master architect to think like one. Start with the questions, use the frameworks as thinking tools (not bureaucratic templates), and iterate. Every project you apply this thinking to makes you better.
