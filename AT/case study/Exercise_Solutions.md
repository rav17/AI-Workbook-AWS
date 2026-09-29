# Architectural Thinking Workshop - Exercise Solutions
## Case Study: Electronic Census System (ECS) for the Republic of Bolumbia

---

# EXERCISE 1: Requirements Definition

---

## What is a System Context Diagram?

A **System Context Diagram** is the highest-level architectural view of a system. It shows the system as a single box in the center, surrounded by all the external entities (actors and systems) that interact with it. Its purpose is to clearly define the **boundary** of what you are building and what lies outside it. It answers: "What are we building, who uses it, and what does it connect to?"

**Key characteristics:**
- The system under design is shown as a single box/shape at the center
- **Human actors** (people or roles that interact with the system) are shown around it — typically as stick figures or labeled circles
- **System actors** (external systems that integrate with your system) are shown as rectangles or labeled boxes
- **Arrows/lines** between actors and the system represent interactions, data flows, or communication channels
- Labels on arrows describe the nature of the interaction (e.g., "HTTPS", "Data Transfer", "SMS")

**What to include:**
- ALL human roles that directly use the system (not just "user" — be specific: "Respondent", "Administrator", "Help Desk")
- ALL external systems that exchange data with your system (even if indirectly)
- The communication channel/protocol on each connection
- Directionality (who initiates, who responds) if relevant

**How to read a System Context Diagram:**
- The central box = the system you are designing (treat it as a black box — no internals shown)
- Everything outside the box = NOT your responsibility to build (but you must integrate with it)
- Arrows = data or interactions that cross your boundary
- If an actor or system is NOT connected to the central box, it's out of scope

**Relationship to other models:**
- **Output to:** Use Case Model (actors become the "who" in use cases), Location Model (actors tell you where users are), AOD (actors and integrations appear at the edges)
- This is typically the FIRST diagram drawn in any architecture engagement

**Why it matters:**
- Establishes clear scope — what is IN vs OUT of the project
- Identifies all stakeholders and interfaces early
- Forms the basis for integration requirements
- Serves as a communication tool for both business and technical audiences
- Prevents scope creep — if it's not on this diagram, it's not your problem

**Notation used here:** UML-style — stick figures for human actors, rounded rectangles for system actors, a central rectangle for the system, and labeled directed arrows for interactions.

---

## What is a High-Level Use Case Model (Bubble Diagram)?

A **High-Level Use Case Model** (also called a "Bubble Diagram") is a visual representation of WHAT the system does from the users' perspective, without detailing HOW. Each "bubble" (ellipse) represents a use case — a distinct goal that an actor can accomplish using the system. It answers: "What are all the things this system lets people do?"

**Key characteristics:**
- A **system boundary** rectangle encloses all use cases — this is the scope of what the system provides
- **Actors** (stick figures) are placed outside the boundary, representing roles that interact with the system
- **Use cases** (ellipses/ovals) represent high-level functional goals the system supports
- **Lines** connect actors to the use cases they participate in
- Use cases are named with short verb phrases (e.g., "Submit Form", "View Receipt")
- This is NOT a detailed use case specification — it does NOT include scenarios, steps, or alternate flows

**What to include:**
- Every distinct functional goal a user can accomplish (not sub-steps)
- All actor roles (don't lump everyone into "User" — be specific)
- Group related use cases visually if helpful
- Optionally color-code by priority or phase

**How to read a Use Case Bubble Diagram:**
- Rectangle = system boundary (everything inside is what we build)
- Each oval/ellipse = one use case (one user goal)
- Stick figures = actor roles (placed OUTSIDE the boundary)
- Lines from actor to oval = "this actor participates in this use case"
- No arrows between ovals in a high-level model (keep it simple)

**Relationship to other models:**
- **Input from:** System Context Diagram (provides the actors)
- **Output to:** Component Model (each use case drives component identification), Sequence Diagrams (each use case becomes a scenario to model)

**Why it matters:**
- Gives a quick visual summary of all system capabilities
- Maps who uses what — helps identify missing functionality
- Drives further architectural decomposition (each use case can be broken into components)
- Useful for prioritization in agile contexts (which use cases are most important?)
- Forms the basis for test planning (each use case = at least one test scenario)

**Notation used here:** Standard UML Use Case Diagram style — rectangle for system boundary, ellipses for use cases, stick figures for actors, and association lines.

---

## 1.1 System Context Diagram

### Human Actors:
| Actor | Description |
|-------|-------------|
| **Respondent** | Bolumbian resident who completes the Census form online (desktop or mobile) |
| **Census Collector** | Field worker (~27,000) who delivers/collects paper forms, receives SMS notifications |
| **DoS Administrator** | Department of Statistics staff managing Census operations |
| **Help Desk Operator** | DoS staff supporting respondents with Census/ECS questions |
| **Developer/Tester** | Organization staff building, testing, and deploying the ECS application |
| **Support Staff** | Organization staff monitoring and supporting the ECS hosting environment |

### System Actors:
| System | Description |
|--------|-------------|
| **DoS Electronic Census Processing** | Receives submitted Census data and CFN/address details from ECS |
| **DoS Forms Processing** | Processes paper Census forms (out of ECS scope, but integration point) |
| **SMS Gateway / Mobile Phone Network** | Sends SMS notifications to Census Collectors |
| **Bolumbia Post** | Handles mailed paper forms (out of scope for ECS) |

### System Context Diagram (Textual Representation):

```
                    +------------------+
                    |   Respondent     |
                    | (Desktop/Mobile) |
                    +--------+---------+
                             |
                     HTTPS (Internet)
                             |
                    +--------v---------+
                    |                  |
                    |       ECS        |
                    | (Electronic      |
                    |  Census System)  |
                    |                  |
                    +--+----+----+--+--+
                       |    |    |  |
          +------------+    |    |  +---------------+
          |                 |    |                  |
          v                 v    v                  v
+------------------+ +------+-------+  +-----------+--------+
| DoS Electronic   | | SMS Gateway  |  | Census Help Desk   |
| Census Processing| | (Mobile Net) |  | (usage info)       |
+------------------+ +--------------+  +--------------------+
                           |
                           v
                  +-----------------+
                  | Census Collector|
                  +-----------------+

Internal actors: Developer/Tester, Support Staff, DoS Administrator
```

## 1.2 High-Level Use Case Model (Bubble Diagram)

### Respondent Use Cases:
- UC_01: Logon to ECS
- UC_02: Navigate Census Form Sections
- UC_03: Complete Address Section
- UC_04: Complete Person Section
- UC_05: Complete Dwelling Section
- UC_06: Complete Feedback Section
- UC_07: Save Progress (partial form)
- UC_08: Resume Incomplete Form
- UC_09: Submit Completed Form
- UC_10: View Receipt/Confirmation
- UC_11: Logoff
- UC_12: Submit Form (Mobile Device)

### DoS Administrator Use Cases:
- UC_20: Monitor Submission Statistics
- UC_21: Generate Daily Reports
- UC_22: Transfer Data to DoS Processing
- UC_23: Send Collector Notifications (SMS)

### Support Staff Use Cases:
- UC_30: Monitor System Health
- UC_31: Manage Application Deployment
- UC_32: Provide Help Desk Support Information

## 1.3 Key Non-Functional Requirements (Qualities)

| Quality | Requirement |
|---------|-------------|
| **Performance** | System must handle peak load on Census Night (~9.5M households, significant % online simultaneously). Target: page response time < 3 seconds under peak load. |
| **Scalability** | Must scale from near-zero to millions of concurrent users within hours (Census Night spike). Cloud-based elastic scaling required. |
| **Availability** | 99.99% uptime during the enumeration period (August). Any downtime = lost Census responses. |
| **Security** | Protect personally identifiable information (PII). Only staff under Statistics Act can access raw data. Encryption in transit (TLS) and at rest. Credential-based access (CFN + ECN). |
| **Privacy** | Maintain perception of privacy. DoS holds unique security access key. Compliance with privacy legislation. |
| **Usability** | Accessible to all Bolumbians regardless of technical skill. Support multiple browsers and mobile devices. No additional software required. |
| **Accessibility** | Must comply with government accessibility standards (WCAG). Support screen readers, keyboard navigation. |
| **Reliability** | No data loss. All submitted forms must be reliably stored and transferred to DoS processing. |
| **Supportability** | Comprehensive monitoring, logging, and alerting. Help desk integration. |
| **Legal Compliance** | Meet Electronic Transactions Act 2009. Legal equivalence with paper form. |
| **Portability** | Support major desktop browsers (Chrome, Firefox, Safari, Edge) and mobile devices (iOS, Android). |
| **Capacity** | ~9.5 million potential submissions. ~29 pages average per form. Storage for all responses during enumeration period. |

---

# EXERCISE 2: Architecture Overview Diagram (AOD)

---

## What is an Architecture Overview Diagram (AOD)?

An **Architecture Overview Diagram (AOD)** is a single-page visual summary that communicates the overall shape of the solution to a broad audience. It bridges the gap between business stakeholders (who need to see scope and purpose) and technical teams (who need to see structure).

**Key characteristics:**
- Shows the system's major **tiers or layers** (e.g., presentation, application, data, integration)
- Shows **external actors** at the top or sides — who uses the system and through which channels
- Shows **external integrations** — other systems your solution connects to
- Uses a **system boundary** (often labeled "Cloud" or "Hosting Environment") to delineate what you own
- Includes **technology annotations** where relevant (e.g., "HTTPS", "REST API")
- Is deliberately **not too detailed** — one page, readable by anyone in 30 seconds

**Questions to ask when creating an AOD:**
- Who is the intended audience? (Business? IT within the project? IT outside?)
- What aspect of architecture does it address? (Functional? Operational? Both?)
- When in the project lifecycle is it drawn? (Day 1, Day 31, Day 101?)
- How long will it be useful? (One meeting? A week? The whole project?)

**Why it matters:**
- Creates shared understanding across all stakeholders
- Acts as the "north star" diagram that other detailed views elaborate
- Useful in proposals, kick-offs, and governance reviews
- Exposes major integration points and deployment choices early

---

## Audience: Business and IT stakeholders (proposal phase)
## Lifecycle: Day 1 of architecture engagement (high-level)
## Useful for: Duration of the project

### Architecture Overview Diagram (Textual):

```
+================================================================+
|                    ELECTRONIC CENSUS SYSTEM (ECS)                |
|                    Architecture Overview                         |
+================================================================+

USERS/CHANNELS:
+-------------+    +----------------+    +------------------+
| Desktop     |    | Mobile Device  |    | Census Collector |
| Browser     |    | (App/Browser)  |    | (SMS)            |
+------+------+    +-------+--------+    +--------+---------+
       |                   |                      |
       +----------+--------+                      |
                  |                               |
              INTERNET                        MOBILE NET
                  |                               |
=====+============|===============================|=======+========
     |            |          CLOUD HOSTING        |       |
     |   +--------v---------+              +------v----+  |
     |   | CDN / WAF /      |              | SMS       |  |
     |   | Load Balancer    |              | Gateway   |  |
     |   +--------+---------+              +-----------+  |
     |            |                                       |
     |   +--------v---------+                             |
     |   | Web/App Tier     |                             |
     |   | (Presentation +  |                             |
     |   |  Business Logic) |                             |
     |   +--------+---------+                             |
     |            |                                       |
     |   +--------v---------+                             |
     |   | Data Tier        |                             |
     |   | (Census DB +     |                             |
     |   |  Session Store)  |                             |
     |   +--------+---------+                             |
     |            |                                       |
     |   +--------v---------+    +-----------------+      |
     |   | Integration Tier |<-->| DoS Electronic  |      |
     |   | (Data Transfer)  |    | Census Processing|     |
     |   +------------------+    +-----------------+      |
     |                                                    |
     |   +------------------+    +-----------------+      |
     |   | Monitoring &     |    | Dev/Test        |      |
     |   | Support Tools    |    | Environment     |      |
     |   +------------------+    +-----------------+      |
     |                                                    |
=====+====================================================+========

INTEGRATION:
- DoS Electronic Census Processing (data transfer)
- SMS Gateway (collector notifications)
- Census Help Desk (usage information)
```

### Key Architectural Decisions:
1. **Cloud-hosted** - elastic scaling for Census Night peak
2. **Web-based** - no client software installation required
3. **Responsive design** - single codebase for desktop and mobile
4. **Stateless application tier** - enables horizontal scaling
5. **Secure credential-based access** - CFN + ECN for authentication

---

# EXERCISE 3: Component Modeling (Functional Aspect)

---

## What is Component Modeling?

**Component Modeling** is the process of decomposing a system into logical components and defining how they collaborate to deliver functionality. It belongs to the **Functional Aspect** of architecture and answers: "What are the building blocks of the system and how do they work together?"

It has two complementary views:

### Structural View — Logical Component Relationship Diagram

A **Component Relationship Diagram** shows the static structure of the system's internals:

- **Components** are shown as labeled rectangles (often with `<<component>>` stereotype), each with a clear, single responsibility
- **Actors** (external to the system) are shown connecting to "edge" components — the entry points into the system
- **Arrows/dependencies** between components show which component uses or calls which other component
- **External systems** (databases, third-party services) are shown at the edges

**Key principles:**
- Each component should have a clear **responsibility** (what it does)
- Components communicate through well-defined **interfaces**
- "Edge" components face external actors; "internal" components are hidden from the outside
- Cross-cutting concerns (security, logging) may connect to many components

### Behavioral View — Sequence Diagram

A **Sequence Diagram** shows how components interact over time to fulfill a specific use case:

- **Lifelines** (vertical dashed lines) represent actors and components
- **Messages** (horizontal arrows between lifelines) represent calls/requests, labeled with what's happening
- Time flows top-to-bottom — earlier interactions are at the top
- Shows the **order** of interactions needed to accomplish a goal
- Can include conditional logic (alt/opt fragments)

**Why it matters:**
- Validates that the component model actually works — data can flow from actor to result
- Exposes missing components or responsibilities
- Identifies critical paths and potential bottlenecks
- Drives interface/API design

---

## 3.1 Structural View - Logical Component Relationship Diagram

### Components:

| Component | Responsibilities |
|-----------|-----------------|
| **Presentation Manager** | Renders Census form pages, handles user interactions, form navigation, responsive UI |
| **Authentication Manager** | Validates CFN + ECN credentials, manages session, handles logon/logoff |
| **Form Manager** | Manages Census form lifecycle, section navigation, save/resume, form submission |
| **Validation Engine** | Validates field-level and cross-field rules, mandatory field checks |
| **Data Access Manager** | CRUD operations on Census response data, caching, persistence |
| **Integration Manager** | Handles data transfer to DoS systems, SMS notifications via gateway |
| **Session Manager** | Manages user sessions, timeouts, concurrent access |
| **Notification Service** | Sends SMS to Census Collectors, generates receipts |
| **Reporting Service** | Generates daily reports, submission statistics |
| **Security Manager** | Encryption, access control, audit logging |

### Component Relationships:
```
[Respondent] --> [Presentation Manager] --> [Authentication Manager]
                                        --> [Form Manager]
                                        --> [Session Manager]

[Form Manager] --> [Validation Engine]
               --> [Data Access Manager]
               --> [Integration Manager]

[Integration Manager] --> [DoS Electronic Census Processing]
                      --> [Notification Service] --> [SMS Gateway]

[Data Access Manager] --> [Census Database]

[Security Manager] <-- (all components)
```

## 3.2 Behavioral View - Sequence Diagram: UC_01 Logon

```
Respondent    Presentation    Authentication    Data Access    Session
    |         Manager          Manager          Manager       Manager
    |             |                |                |             |
    |--Request -->|                |                |             |
    |  logon page |                |                |             |
    |             |                |                |             |
    |<-Display----|                |                |             |
    |  logon page |                |                |             |
    |             |                |                |             |
    |--Enter CFN--|                |                |             |
    |  ECN,Submit |                |                |             |
    |             |--Validate----->|                |             |
    |             |  credentials   |                |             |
    |             |                |--Lookup CFN--->|             |
    |             |                |  + ECN         |             |
    |             |                |<-Result--------|             |
    |             |                |                |             |
    |             |                |   [If valid]   |             |
    |             |                |-Create-------->|             |
    |             |                |  session       |--Create---->|
    |             |                |                |  session    |
    |             |<-Auth success--|                |             |
    |             |                |                |             |
    |<-Display----|                |                |             |
    |  initial    |                |                |             |
    |  section    |                |                |             |
    |             |                |                |             |
    |             |   [If invalid] |                |             |
    |             |<-Auth failure--|                |             |
    |<-Display----|                |                |             |
    |  error msg  |                |                |             |
```

## 3.3 Behavioral View - Sequence Diagram: UC_12 Submit Form (Mobile)

```
Respondent    Presentation    Form        Validation   Data Access  Integration  Notification
    |         Manager        Manager      Engine       Manager      Manager      Service
    |             |             |            |             |            |            |
    |--Press----->|             |            |             |            |            |
    |  Submit btn |             |            |             |            |            |
    |             |--Submit---->|            |             |            |            |
    |             |  form       |            |             |            |            |
    |             |             |--Validate->|             |            |            |
    |             |             |  all fields|             |            |            |
    |             |             |<-Valid-----|             |            |            |
    |             |             |            |             |            |            |
    |             |             |--Save final------------>|            |            |
    |             |             |  form data |             |            |            |
    |             |             |<-Confirmed-|-------------|            |            |
    |             |             |            |             |            |            |
    |             |             |--Transfer data---------->|----------->|            |
    |             |             |  to DoS    |             |            |            |
    |             |             |            |             |            |--Send SMS->|
    |             |             |            |             |            | to Collector|
    |             |             |--Generate  |             |            |            |
    |             |             |  receipt # |             |            |            |
    |             |<-Thank you--|            |             |            |            |
    |             |  + receipt# |            |             |            |            |
    |<-Display----|             |            |             |            |            |
    |  Thank you  |             |            |             |            |            |
    |  + receipt  |             |            |             |            |            |
    |             |             |            |             |            |            |
    |--Submit---->|             |            |             |            |            |
    |  feedback   |             |            |             |            |            |
    |             |--Save------>|            |             |            |            |
    |             |  feedback   |--Store-----|------------>|            |            |
    |             |<-Complete---|            |             |            |            |
    |<-Display----|             |            |             |            |            |
    |  final scrn |             |            |             |            |            |
```

---

# EXERCISE 4: Location & Deployment Unit Model

---

## What is a Location Model?

A **Location Model** identifies the physical or logical **places** where parts of the system will exist and where users/actors reside. It is the starting point for the Operational Aspect of architecture and answers: "Where are all the participants in this system physically or logically situated, and how are they connected?"

**Key characteristics:**
- Each **location** is shown as a large rounded box representing a geographical or logical place (e.g., "Cloud Data Center", "User's Home", "Government Premises")
- **Connections** between locations show the communication links (e.g., Internet, VPN, Mobile Network, LAN)
- Annotations on connections describe the type of network, protocol, and any constraints (bandwidth, latency, security)
- Locations are NOT servers — they are places that will CONTAIN servers (nodes) in later models

**What to include:**
- Where the **users** are (e.g., "Respondent's Home", "Field workers mobile")
- Where the **system** will be hosted (e.g., "Cloud DC Primary Region", "Cloud DC DR Region")
- Where **integrated systems** live (e.g., "Government Data Center")
- Where **support/admin** happens (e.g., "Internal Network")
- The **network type** between each pair of locations (Internet, VPN, Leased Line, LAN, Mobile Network)

**How to read a Location Model diagram:**
- Each box = one distinct location/place
- Lines between boxes = network connectivity
- Labels on lines = type of connection and any constraints
- No servers or software are shown yet — just geography and connectivity

**Relationship to other models:**
- **Input from:** System Context Diagram (identifies who is where)
- **Output to:** LOM (locations become the "backdrop" zones in which nodes are placed)

**Why it matters:**
- Identifies network constraints (latency, bandwidth, security boundaries)
- Drives decisions about where to deploy what
- Exposes integration challenges (e.g., crossing firewalls, dealing with unreliable networks)
- Surfaces data sovereignty and compliance issues (data must stay in-country)
- Foundation for the Logical and Physical Operational Models

---

## What is a Deployment Unit Model?

A **Deployment Unit (DU) Model** groups logical components into **units that are deployed together** as a single package to a runtime environment. It answers: "How do we package our components for deployment, and where does each package run?"

**Key characteristics:**
- Each DU is a cohesive set of components that share the same **deployment lifecycle** — they are built, versioned, deployed, and scaled together
- DUs map to **deployable artifacts** (e.g., a WAR/JAR file, a Docker container image, a microservice, a database schema)
- The model shows which components belong to which DU, where each DU will run, and the **dependencies** between DUs
- DUs are typically shown as "folder" or "package" shapes containing a list of their components

**How to decide what goes into a DU together:**
- Components that must be deployed **atomically** (one fails, all fail) → same DU
- Components that need to **scale independently** → separate DUs
- Components that share the same **technology stack** → candidates for the same DU
- Components with different **security classification** → separate DUs
- Components with different **change frequency** → separate DUs (so fast-changing code doesn't force redeployment of stable code)

**Relationship to other models:**
- **Input:** Component Model (Exercise 3) — provides the components to be grouped
- **Output:** Logical Operational Model (Exercise 5) — DUs are placed inside Logical Nodes

**How to read a DU Model diagram:**
- Each "folder" icon is one Deployment Unit
- Inside each folder: the list of components it contains
- Below or beside: the deployment target (what type of server/environment it runs on)
- Dashed arrows between DUs show runtime dependencies (which DU calls which)

**Why it matters:**
- Bridges the gap from functional (what it does) to operational (where it runs)
- Drives decisions about packaging, scaling granularity, and technology choices
- Informs CI/CD pipeline design — each DU is independently buildable and deployable
- Determines how many different server types/tiers you need in your infrastructure
- Affects cost — fewer DUs = simpler, but less flexible; more DUs = more complex, but independently scalable

---

## 4.1 Location Model

```
+================================================================+
|                          LOCATIONS                               |
+================================================================+

+-----------------------+          +---------------------------+
| RESPONDENT LOCATION   |          | DoS DATA CENTER           |
| (Anywhere in Bolumbia)|          | (Government premises)     |
| - Home/Office         |          | - Electronic Census       |
| - Desktop/Mobile      |          |   Processing System       |
|                       |          | - Census Database          |
+-----------+-----------+          +-------------+-------------+
            |                                    |
        INTERNET                          SECURE NETWORK
            |                                    |
+-----------v-----------+          +-------------v-------------+
| CLOUD HOSTING         |          | DoS INTERNAL NETWORK      |
| ENVIRONMENT           |<-------->| - Admin Systems           |
| (Cloud Provider DC)   |  Secure  | - Help Desk               |
| - Primary Region      |  Link    |                           |
| - DR Region           |          +---------------------------+
+-----------------------+
            |
    MOBILE NETWORK
            |
+-----------v-----------+
| CENSUS COLLECTOR      |
| (Field - Mobile)      |
+------------------------+
```

### Locations:
1. **Respondent Location** - homes/offices across Bolumbia (9.5M dwellings)
2. **Cloud Hosting Environment** - primary + disaster recovery regions
3. **DoS Data Center** - government premises, secure
4. **Census Collector (Field)** - mobile devices across Bolumbia
5. **DoS Internal Network** - admin, help desk

## 4.2 Deployment Unit Model

| Deployment Unit | Components Contained | Deployment Target |
|----------------|---------------------|-------------------|
| **DU_Web** | Presentation Manager, Session Manager | Web Server Tier (Cloud) |
| **DU_App** | Form Manager, Validation Engine, Authentication Manager, Security Manager | Application Server Tier (Cloud) |
| **DU_Integration** | Integration Manager, Notification Service, Reporting Service | Integration Server (Cloud) |
| **DU_Data** | Data Access Manager | Database Server (Cloud) |
| **DU_Mobile_App** | Mobile Presentation (responsive web) | Respondent's Mobile Device |
| **DU_Monitoring** | Monitoring tools, Log aggregation | Operations Server (Cloud) |

---

# EXERCISE 5: Logical & Physical Operational Models

---

## What is a Logical Operational Model (LOM)?

The **Logical Operational Model (LOM)** shows HOW the system is deployed in a technology-independent way. It combines the Location Model, Deployment Units, and Logical Nodes into a single view that shows what runs where and how parts communicate. It answers: "If I could look at the running system from above, what would I see — without worrying about specific products or server counts?"

**Key characteristics:**
- **Locations** from the Location Model are shown as background regions/zones
- **Logical Nodes** (LN) are placed within locations — they represent abstract execution environments (e.g., "Web Server", "App Server", "Database Server") without specifying vendor, count, or sizing
- **Deployment Units** are placed inside logical nodes to show what software runs on what node
- **Actors** are shown at the edges connecting into the system
- **Access mechanisms** (protocols, ports) are labeled on connections between nodes
- **Security zones** (DMZ, App Zone, Data Zone) group nodes by trust level

**How to read a LOM diagram:**
- Background colored regions = security zones / locations
- Boxes inside regions = Logical Nodes (abstract server roles)
- Text inside nodes = DUs deployed on that node
- Arrows between nodes = runtime communication with protocol labels
- Actors at the edges = who/what initiates the interaction

**Relationship to other models:**
- **Input from:** Location Model (provides the zones), DU Model (provides the software packages), Component Model (provides the logic)
- **Output to:** POM (each Logical Node becomes one or more Physical Nodes)

**Key difference from AOD:**
- AOD is for communication (one page, high level, audience = everyone)
- LOM is for engineering (precise, shows zones/protocols/DUs, audience = technical team)

**Why it matters:**
- First view where you can validate that the system will actually work end-to-end at runtime
- Drives infrastructure architecture decisions
- Exposes security boundaries and integration protocols
- Input to capacity planning and cost estimation
- Can be reviewed without committing to specific vendor products

---

## What is a Physical Operational Model (POM)?

The **Physical Operational Model (POM)** translates the LOM into reality — specifying actual **physical nodes** with sizing, quantities, technologies, and redundancy. It answers: "Exactly how many servers do we need, what technology will they run, and how do we handle failure?"

**Key characteristics:**
- Each Logical Node from the LOM becomes one or more **Physical Nodes** (PN) — specific servers, clusters, or managed services
- Shows **quantities** (e.g., "x4 Web Servers", "x2 Active-Active Load Balancers")
- Shows **scaling strategy** (auto-scaling groups, clusters, replicas)
- Shows **redundancy and failover** (HA pairs, DR region, replication arrows)
- Annotates with **technology choices** (e.g., "Redis", "PostgreSQL", "Kubernetes", "AWS ALB")
- Addresses **NFR impact**: how each key NFR (performance, availability, security, scalability) translates into physical infrastructure decisions

**How to read a POM diagram:**
- Each labeled box = one Physical Node (a real or virtual server/service)
- "x4" or "x8+" = number of instances (or auto-scaling range)
- Dashed arrows labeled "replication" = data synchronization to DR
- Annotations at the bottom = which NFR drove which physical decision
- Separate bounded region = DR (Disaster Recovery) environment

**Relationship to other models:**
- **Input from:** LOM (each logical node gets translated), NFR list (drives quantities and redundancy)
- **Output to:** Infrastructure provisioning, cost estimation, performance test planning

**The key translation from LOM → POM:**
| LOM (Logical) | POM (Physical) | Driven by NFR |
|---|---|---|
| LN: Web Server | PN: Web Server x4 (auto-scaling) | Scalability, Performance |
| LN: App Server | PN: App Server x8 (auto-scaling) | Scalability, Performance |
| LN: Database | PN: DB HA Cluster + 2 Read Replicas | Availability, Performance |
| LN: Integration | PN: Integration x2 + Message Queue | Reliability |
| (none in LOM) | PN: CDN, WAF, DDoS Protection | Security, Performance |
| (none in LOM) | DR Region (warm standby) | Availability |

**Why it matters:**
- Directly drives procurement, cloud provisioning, and infrastructure-as-code
- Enables cost estimation (number of VMs, storage, bandwidth)
- Validates that NFRs can actually be met with the chosen topology
- Input to capacity planning and performance testing strategy
- Contractual basis — this is what gets built and billed

---

## 5.1 Logical Operational Model (LOM)

```
+====================CLOUD HOSTING ENVIRONMENT======================+
|                                                                    |
|  +--INTERNET ZONE (DMZ)--+    +--APPLICATION ZONE--+              |
|  |                        |    |                    |              |
|  | [LN: Web Server]       |    | [LN: App Server]  |              |
|  |  - DU_Web             |--->|  - DU_App          |              |
|  |  - Load Balancer       |    |                    |              |
|  |  - WAF/CDN             |    +--------+-----------+              |
|  +------------------------+             |                          |
|                                         v                          |
|  +--INTEGRATION ZONE-----+    +--DATA ZONE----------+             |
|  |                        |    |                      |            |
|  | [LN: Integration Svr]  |    | [LN: Database Server]|           |
|  |  - DU_Integration     |    |  - DU_Data           |            |
|  +----------+-------------+    +----------------------+            |
|             |                                                      |
+============|======================================================+
             |
    Secure Link (VPN/Direct Connect)
             |
+============v=================+      +========================+
| DoS DATA CENTER              |      | RESPONDENT LOCATION    |
| [LN: DoS Processing Server] |      | [Actor: Respondent]    |
|  - Electronic Census Proc.  |      |  via Internet/Mobile   |
+==============================+      +========================+

ACCESS MECHANISMS:
- Respondent --> Web Server: HTTPS (443)
- Web Server --> App Server: Internal HTTPS
- App Server --> Database: JDBC/encrypted
- Integration Svr --> DoS Processing: Secure File Transfer / API
- Integration Svr --> SMS Gateway: HTTPS API
```

## 5.2 Physical Operational Model (POM)

```
+====================CLOUD HOSTING - PRIMARY REGION=================+
|                                                                    |
|  INTERNET ZONE (DMZ):                                             |
|  +--[PN: CDN Edge Nodes (Global)]                                 |
|  +--[PN: WAF / DDoS Protection]                                   |
|  +--[PN: Load Balancer x2 (Active-Active)]                        |
|  +--[PN: Web Server x4+ (Auto-scaling group)]                     |
|       DU_Web deployed                                              |
|                                                                    |
|  APPLICATION ZONE:                                                 |
|  +--[PN: App Server x8+ (Auto-scaling group)]                     |
|       DU_App deployed                                              |
|  +--[PN: Session Cache Cluster (Redis/Memcached) x3]              |
|                                                                    |
|  DATA ZONE:                                                        |
|  +--[PN: Primary DB Server (HA Cluster - Active/Standby)]         |
|  +--[PN: Read Replica DB x2]                                      |
|       DU_Data deployed                                             |
|                                                                    |
|  INTEGRATION ZONE:                                                 |
|  +--[PN: Integration Server x2]                                    |
|       DU_Integration deployed                                      |
|  +--[PN: Message Queue (for async processing)]                     |
|                                                                    |
|  OPERATIONS ZONE:                                                  |
|  +--[PN: Monitoring Server]                                        |
|  +--[PN: Log Aggregation Server]                                   |
|  +--[PN: Bastion/Jump Host]                                        |
|       DU_Monitoring deployed                                       |
+====================================================================+

+====================CLOUD HOSTING - DR REGION======================+
|  (Warm standby with replicated database)                           |
|  +--[PN: Web/App Servers (scaled down, auto-scale on failover)]   |
|  +--[PN: DB Replica (async replication from primary)]             |
+====================================================================+

KEY NFR IMPACTS ON PHYSICAL MODEL:
- PERFORMANCE/SCALABILITY: Auto-scaling web+app tiers, CDN, caching
- AVAILABILITY: Multi-AZ deployment, DB HA cluster, DR region
- SECURITY: WAF, DDoS protection, network segmentation, encryption
- CAPACITY: Read replicas, message queue for async data transfer
```

---

# EXERCISE 7 (6): Agile - Initial Architecture

---

## What is an Architecture-on-a-Page?

An **Architecture-on-a-Page** is a concise, single-page visual summary of the entire solution that can be created very early — often in Sprint 0 or during a scoping workshop. It captures just enough architecture to start development, deferring detailed decisions to later. It answers: "If someone new joins the project, can they understand the whole solution in 60 seconds from one page?"

**Key characteristics:**
- Fits on a **single page** (or single slide) — forces brevity and prioritization
- Includes: business context, users, channels, solution layers, key integrations, technology choices, decisions, risks, and NFRs
- Is **deliberately incomplete** — it captures what's known and flags what's uncertain
- Created in **2-3 days** during initial architecture activities
- Uses a combination of boxes, layers, bullet lists, and annotations — not strict UML

**Typical sections:**
1. **Context banner** — what the system is, who it's for, key numbers
2. **Users & Channels** — who interacts and how
3. **Solution Architecture** — layered/tiered view of the system internals
4. **Key Integrations** — external systems
5. **Architectural Decisions** — major choices made (and why)
6. **Key Risks** — what could go wrong, with mitigations
7. **NFRs** — the quality requirements that shape the architecture
8. **Technology Stack** — chosen technologies (if decided)

**How to read an Architecture-on-a-Page:**
- Top/header = business context and scope (who, what, when)
- Left/center = users, channels, and the solution layers (how it's built)
- Right = decisions, risks, technology — the "meta" information about the architecture
- Bottom = cross-cutting concerns (NFRs, constraints)

**Relationship to other models:**
- **Input from:** All previous exercises (context, use cases, components, NFRs, integrations)
- **Output to:** Development team (enough to start Sprint 1), stakeholder presentations, governance reviews
- This is the "elevator pitch" version of your entire architecture

**Key difference from other diagrams:**
- AOD = just the system structure
- Architecture-on-a-Page = structure + context + decisions + risks + NFRs — everything on one page

**Why it matters:**
- Enables early alignment between stakeholders
- Gives developers enough direction to start coding
- Acts as a living document that evolves with the project
- Perfect for agile contexts where heavy upfront documentation isn't desired
- Forces the architect to prioritize what's MOST important

---

## What is an Initial Security Viewpoint?

An **Initial Security Viewpoint** captures the security architecture of the system — how threats are mitigated and data is protected. Created early, it ensures security is built in from day one, not bolted on later. It answers: "How do we protect data, control access, and defend against attacks?"

**Key characteristics:**
- Shows **security zones** — areas of different trust levels separated by firewalls/controls (e.g., Untrusted Internet → DMZ → Application → Data → Government)
- Documents **authentication & authorization** approach — how users prove identity, how access is controlled
- Specifies **data protection** — encryption in transit and at rest, who can access what
- Details **network security** — WAF, DDoS protection, segmentation, VPN
- Lists **compliance requirements** — laws, regulations, standards that apply
- Identifies security-specific **risks and mitigations**

**What to include:**
- Zone boundaries with firewalls between them
- Authentication mechanism (e.g., credentials, MFA, OAuth)
- Encryption standards (TLS version, AES key length)
- Who can access what data (access control matrix)
- Audit/logging approach
- Regulatory requirements (privacy laws, data sovereignty)

**How to read a Security Viewpoint diagram:**
- Columns or nested boxes = security zones (left = least trusted, right = most trusted)
- Firewall icons between zones = network-level enforcement points
- Labels inside zones = security controls applied there (e.g., input validation, encryption)
- Tables below the diagram = detailed security policies (auth rules, data protection, compliance)

**Relationship to other models:**
- **Input from:** NFRs (security requirements), System Context (who accesses), LOM (zones/nodes)
- **Output to:** Infrastructure decisions (WAF products, key management), development standards (secure coding), operations procedures (incident response)

**Why it matters:**
- Security breaches are catastrophic for a Census system (PII of entire population)
- Early identification of security requirements drives architectural decisions (zones, encryption, key management)
- Regulatory compliance (Privacy Act, Electronic Transactions Act) must be designed in
- Builds stakeholder confidence that privacy and security are taken seriously
- Without this viewpoint, security gets "bolted on" too late and becomes expensive to fix

---

## 7.1 Architecture-on-a-Page

```
+================================================================+
|          ECS - ARCHITECTURE ON A PAGE                           |
|          Electronic Census System for Republic of Bolumbia      |
+================================================================+

BUSINESS CONTEXT:
- 23M population, 9.5M dwellings, ~27,000 collectors
- Census Night peak (first Tuesday, August)
- 3-year timeline to delivery
- Cloud-hosted, internet-delivered

USERS:             CHANNELS:          KEY INTEGRATIONS:
- Respondents      - Desktop Browser   - DoS Electronic Census Processing
- Collectors       - Mobile Browser    - SMS Gateway (Collector notifs)
- DoS Admin        - SMS               - Census Help Desk
- Support Staff

+--------------------SOLUTION ARCHITECTURE----------------------+
|                                                               |
|  [CDN + WAF]  -->  [Load Balancer]  -->  [Web Tier]          |
|                                           (Responsive UI)     |
|                                               |               |
|                                          [App Tier]           |
|                                     (Business Logic,          |
|                                      Auth, Validation)        |
|                                               |               |
|                              [Cache]     [Database]           |
|                              (Session)   (Census Data)        |
|                                               |               |
|                                     [Integration Tier]        |
|                                      (Data Transfer,          |
|                                       Notifications)          |
+---------------------------------------------------------------+

KEY ARCHITECTURAL DECISIONS:
1. Cloud-native deployment (elastic scaling for Census Night)
2. Stateless app tier with shared session cache
3. Responsive web design (no native mobile app needed)
4. Credential-based auth (CFN + ECN, no registration)
5. Asynchronous data transfer to DoS systems
6. Multi-region DR strategy

KEY RISKS:
- Census Night peak load (mitigation: auto-scaling + load testing)
- Data security/privacy (mitigation: encryption, access controls)
- Browser compatibility (mitigation: progressive enhancement)
- Single point of failure (mitigation: HA at every tier)

TECHNOLOGY CHOICES:
- Cloud: AWS/Azure/GCP (IaaS + PaaS)
- Web: HTML5, CSS3, JavaScript (responsive framework)
- App: Java/Node.js on containers
- DB: PostgreSQL/Oracle (relational, ACID-compliant)
- Cache: Redis
- Integration: REST APIs + Message Queue
- Monitoring: Cloud-native monitoring + APM
```

## 7.2 Initial Security Viewpoint

```
+================================================================+
|          ECS - INITIAL SECURITY VIEWPOINT                       |
+================================================================+

SECURITY ZONES:
+--Internet--+  +--DMZ--+  +--App Zone--+  +--Data Zone--+  +--DoS--+
| Respondent |->| WAF   |->| App Servers|->| Database    |->| DoS   |
| (untrusted)|  | CDN   |  | (trusted)  |  | (restricted)|  | Proc. |
+------------+  | LB    |  +------------+  +-------------+  +-------+
                +-------+

AUTHENTICATION & AUTHORIZATION:
- Respondent access: CFN + ECN (unique per dwelling)
- No self-registration (credentials delivered physically)
- Session timeout after inactivity (e.g., 20 minutes)
- Rate limiting on login attempts (brute force protection)
- Admin access: Multi-factor authentication

DATA PROTECTION:
- In-transit: TLS 1.2+ for all connections
- At-rest: AES-256 encryption for Census data
- Only Statistics Act employees can access raw respondent data
- DoS holds unique security access key to managed data
- PII masking in logs and monitoring

NETWORK SECURITY:
- WAF rules (OWASP Top 10 protection)
- DDoS protection (cloud-native + CDN)
- Network segmentation (DMZ, App, Data zones)
- VPN/Direct Connect to DoS network
- No direct internet access to data tier

COMPLIANCE:
- Electronic Transactions Act 2009
- Privacy legislation (data handling, retention)
- Government security classification requirements
- Audit logging of all access and changes
- Data sovereignty (hosted within Bolumbia or approved jurisdiction)

INCIDENT RESPONSE:
- 24/7 security monitoring during enumeration period
- Automated alerting on suspicious activity
- Incident response plan and escalation procedures
- Regular penetration testing pre-Census
```

---

## Summary of Deliverables

| Exercise | Deliverable |
|----------|-------------|
| Ex 1 | System Context Diagram, Use Case Model, NFR List |
| Ex 2 | Architecture Overview Diagram |
| Ex 3 | Component Relationship Diagram + 2 Sequence Diagrams |
| Ex 4 | Location Model + Deployment Unit Model |
| Ex 5 | Logical Operational Model + Physical Operational Model |
| Ex 7 | Architecture-on-a-Page + Initial Security Viewpoint |
