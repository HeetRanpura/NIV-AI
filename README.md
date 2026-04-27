# NIV AI

NIV AI is a risk-aware home buying decision intelligence system for Indian
property buyers. It combines deterministic financial math, India-specific real
estate cost rules, behavioral bias detection, multi-agent AI reasoning, and
report generation to help a buyer answer one high-stakes question:

> Is this property financially safe to buy, or should I wait, renegotiate, or
> walk away?

The product is intentionally more conservative than a normal EMI calculator.
Most calculators answer "Can I afford the EMI?" NIV AI asks a harder set of
questions:

- What is the true acquisition cost after GST, stamp duty, registration, bank
  fees, legal verification, maintenance deposit, and property tax?
- Does the household survive realistic shocks such as job loss, income drop,
  emergency expense, and interest-rate increase?
- Will the bank likely reject the loan because fixed obligations are too high?
- Is the buyer emotionally committed, anchored, overconfident, or reacting to
  scarcity pressure?
- What safer price, down payment, or waiting period would make the decision
  defensible?

The repository contains a FastAPI backend, deterministic finance engines,
multi-agent AI orchestration, Firebase/Google Cloud integrations, and static
frontend assets for a Firebase-hosted web experience.

---

## Table of Contents

- [Product Summary](#product-summary)
- [Live Deployment](#live-deployment)
- [Core Capabilities](#core-capabilities)
- [Technology Stack](#technology-stack)
- [Repository Structure](#repository-structure)
- [Application Flow](#application-flow)
- [Backend Architecture](#backend-architecture)
- [AI Agent Architecture](#ai-agent-architecture)
- [Data Model](#data-model)
- [API Surface](#api-surface)
- [Configuration](#configuration)
- [Local Development](#local-development)
- [Testing](#testing)
- [Deployment](#deployment)
- [Security Model](#security-model)
- [Cost Model](#cost-model)
- [Roadmap](#roadmap)

---

## Product Summary

NIV AI is designed for Indian households evaluating a residential property
purchase. The primary user is a prospective home buyer who has a specific
property in mind and wants a structured, bias-resistant decision audit before
committing capital.

The application turns buyer inputs into:

- a clear buy/wait/avoid verdict,
- a monthly EMI and affordability profile,
- an India-specific hidden cost breakdown,
- bank underwriting risk indicators,
- stress-test survivability,
- behavioral bias flags,
- a multi-section decision report,
- and post-analysis actions such as a counter-offer letter or bank inquiry
  draft.

The system separates arithmetic from AI interpretation. Financial calculations
are deterministic Python functions. LLM agents consume those computed numbers
and produce structured explanations, challenges, and final narratives.

At a product level, NIV AI sits between the buyer, the property decision, and
the expert workflows that usually happen after a risky purchase is already in
motion.

<p align="center">
  <img src="https://cdn.simpleicons.org/googlegemini/8E75B2" alt="Gemini" width="18">
  <img src="https://cdn.simpleicons.org/groq/F55036" alt="Groq" width="18">
  <img src="https://cdn.simpleicons.org/openrouter/111111" alt="OpenRouter" width="18">
  <img src="https://cdn.simpleicons.org/firebase/FFCA28" alt="Firebase" width="18">
  <img src="https://cdn.simpleicons.org/googlecloud/4285F4" alt="Google Cloud" width="18">
</p>

```mermaid
%%{init: {"theme":"base","themeVariables":{"primaryColor":"#fef3c7","primaryBorderColor":"#f59e0b","primaryTextColor":"#111827","lineColor":"#475569","secondaryColor":"#dbeafe","tertiaryColor":"#dcfce7","fontFamily":"Inter, Arial"}}}%%
flowchart LR
    Buyer["fa:fa-home Buyer"]:::person --> Web["fa:fa-desktop NIV AI Web App"]:::product
    Family["fa:fa-users Family / Co-buyer"]:::person --> Web
    Advisor["fa:fa-briefcase CA / Bank / Lawyer"]:::expert <-- "PDF report + action items" --> Buyer

    Web --> Decision["fa:fa-scale-balanced Decision Intelligence Result"]:::decision

    Decision --> Verdict["fa:fa-circle-check Buy / Wait / Avoid verdict"]:::safe
    Decision --> Numbers["fa:fa-calculator EMI, FOIR, runway, true cost"]:::math
    Decision --> Risks["fa:fa-triangle-exclamation Stress scenarios + risk factors"]:::risk
    Decision --> Bias["fa:fa-brain Behavioral bias flags"]:::ai
    Decision --> Actions["fa:fa-file-signature Negotiation, bank, document actions"]:::action

    Gemini["fa:fa-bolt Gemini + Groq + OpenRouter"]:::ai --> Web
    Firebase["fa:fa-fire Firebase / Firestore"]:::cloud --> Web
    Storage["fa:fa-cloud Cloud Storage"]:::cloud --> Web

    classDef person fill:#e0f2fe,stroke:#0284c7,stroke-width:2px,color:#0f172a;
    classDef product fill:#fef3c7,stroke:#d97706,stroke-width:3px,color:#111827;
    classDef decision fill:#ede9fe,stroke:#7c3aed,stroke-width:2px,color:#111827;
    classDef safe fill:#dcfce7,stroke:#16a34a,stroke-width:2px,color:#052e16;
    classDef math fill:#dbeafe,stroke:#2563eb,stroke-width:2px,color:#172554;
    classDef risk fill:#fee2e2,stroke:#dc2626,stroke-width:2px,color:#450a0a;
    classDef ai fill:#fae8ff,stroke:#c026d3,stroke-width:2px,color:#3b0764;
    classDef action fill:#ffedd5,stroke:#ea580c,stroke-width:2px,color:#431407;
    classDef cloud fill:#f1f5f9,stroke:#64748b,stroke-width:2px,color:#0f172a;
```

---

## Live Deployment

- Frontend: `https://elegant-verbena-494508-a-e207e.web.app`
- Observed live frontend assets: `index.html`, `app.html`, `style.css`,
  `app.js`
- Observed live API base in deployed `app.js`:
  `https://niv-ai-216564346797.asia-south1.run.app`
- Repository Firebase Hosting configuration serves the `frontend` directory.

> Note: the deployed application appears more complete than some checked-in
> frontend files in this repository snapshot. The backend source and local
> prototype still document the intended FastAPI, Firebase, deterministic engine,
> and multi-agent architecture.

---

## Core Capabilities

### Buyer Intake

- Income and spouse/co-borrower income
- Existing EMIs and monthly expenses
- Liquid savings and down payment
- Property price, area, configuration, location, builder, possession date
- RERA and GST identifiers where available
- Property readiness status
- Loan tenure and expected interest rate
- Optional behavioral checklist and user notes

### Deterministic Financial Analysis

- EMI calculation using standard amortization
- EMI-to-income ratio
- Post-EMI surplus
- 12-month cash flow projection
- Savings depletion month
- Safe property price and maximum property price thresholds
- Total interest payable
- FOIR underwriting check
- Building age / LTV risk where construction year is provided

### India-Specific Cost Engine

- GST slab classification:
  - ready-to-move: 0 percent
  - affordable under-construction: 1 percent
  - standard under-construction: 5 percent
- State and district-level stamp duty
- Female buyer stamp duty concession where applicable
- Registration fee
- Maintenance deposit
- Bank processing fee
- Legal / technical verification fee
- Annual municipal property tax estimate

### Stress Testing

- Base case
- 30 percent income drop
- 6-month job loss
- 2 percent interest-rate hike
- INR 5 lakh emergency expense
- Scenario-level survivability, buffer months, severity, and breaking point

### AI Reasoning

- Behavioral analysis agent
- Validation agent
- Presentation agent
- Context continuity agent
- Conversation agent
- Roundtable agents:
  - Marcus: financial analyst
  - Zara: risk strategist
  - Soren: behavioral economist
- Decision synthesizer for the final verdict and audit
- Brochure analyzer using Gemini Vision for property document extraction

### Reporting and Actions

- Verdict and confidence
- Primary reasons and key warnings
- Safe price recommendation
- Suggested actions
- Chart-ready data for dashboards
- PDF report generation
- GCS signed URLs for report access
- Comparison and what-if analysis patterns

---

## Technology Stack

| Layer | Technology | Purpose |
|---|---|---|
| Frontend | <img src="https://cdn.simpleicons.org/html5/E34F26" alt="HTML5" width="16"> HTML, <img src="https://cdn.simpleicons.org/css/1572B6" alt="CSS" width="16"> CSS, <img src="https://cdn.simpleicons.org/javascript/F7DF1E" alt="JavaScript" width="16"> JavaScript | Static web app, wizard, report UI, charts |
| Hosting | <img src="https://cdn.simpleicons.org/firebase/FFCA28" alt="Firebase" width="16"> Firebase Hosting | CDN-backed static frontend hosting |
| Backend | <img src="https://cdn.simpleicons.org/fastapi/009688" alt="FastAPI" width="16"> FastAPI | HTTP and WebSocket API layer |
| Runtime | <img src="https://cdn.simpleicons.org/python/3776AB" alt="Python" width="16"> Python 3.11, <img src="https://cdn.simpleicons.org/python/3776AB" alt="Uvicorn" width="16"> Uvicorn | Backend execution |
| Validation | <img src="https://cdn.simpleicons.org/pydantic/E92063" alt="Pydantic" width="16"> Pydantic | Typed request and response schemas |
| AI | <img src="https://cdn.simpleicons.org/googlegemini/8E75B2" alt="Gemini" width="16"> Google Generative AI SDK, <img src="https://cdn.simpleicons.org/groq/F55036" alt="Groq" width="16"> Groq, <img src="https://cdn.simpleicons.org/openrouter/111111" alt="OpenRouter" width="16"> OpenRouter | Gemini Flash, Gemini Vision, structured agent calls, provider fallback |
| Local AI fallback | <img src="https://cdn.simpleicons.org/ollama/000000" alt="Ollama" width="16"> Ollama | Local model path for development |
| Database | <img src="https://cdn.simpleicons.org/firebase/FFCA28" alt="Firestore" width="16"> Firestore | User sessions, inputs, simulation results, verdicts |
| Storage | <img src="https://cdn.simpleicons.org/googlecloud/4285F4" alt="Google Cloud Storage" width="16"> Google Cloud Storage | PDF report storage and signed URLs |
| PDF | <img src="https://cdn.simpleicons.org/adobeacrobatreader/B91C1C" alt="PDF" width="16"> ReportLab | Report rendering |
| Auth | <img src="https://cdn.simpleicons.org/firebase/FFCA28" alt="Firebase Auth" width="16"> Firebase Auth, Firebase Admin SDK | Token verification and scoped data access |
| Deployment | <img src="https://cdn.simpleicons.org/docker/2496ED" alt="Docker" width="16"> Docker, <img src="https://cdn.simpleicons.org/googlecloud/4285F4" alt="Cloud Run" width="16"> Cloud Run, <img src="https://cdn.simpleicons.org/railway/0B0D0E" alt="Railway" width="16"> Railway | Containerized backend deployment |

The stack is intentionally split into static delivery, deterministic compute,
AI reasoning, and cloud persistence so each layer can evolve independently.

<p align="center">
  <img src="https://cdn.simpleicons.org/html5/E34F26" alt="HTML5" width="18">
  <img src="https://cdn.simpleicons.org/css/1572B6" alt="CSS" width="18">
  <img src="https://cdn.simpleicons.org/javascript/F7DF1E" alt="JavaScript" width="18">
  <img src="https://cdn.simpleicons.org/python/3776AB" alt="Python" width="18">
  <img src="https://cdn.simpleicons.org/fastapi/009688" alt="FastAPI" width="18">
  <img src="https://cdn.simpleicons.org/firebase/FFCA28" alt="Firebase" width="18">
  <img src="https://cdn.simpleicons.org/googlecloud/4285F4" alt="Google Cloud" width="18">
  <img src="https://cdn.simpleicons.org/docker/2496ED" alt="Docker" width="18">
  <img src="https://cdn.simpleicons.org/groq/F55036" alt="Groq" width="18">
  <img src="https://cdn.simpleicons.org/googlegemini/8E75B2" alt="Gemini" width="18">
  <img src="https://cdn.simpleicons.org/openrouter/111111" alt="OpenRouter" width="18">
</p>

```mermaid
%%{init: {"theme":"base","themeVariables":{"primaryColor":"#eff6ff","primaryBorderColor":"#2563eb","lineColor":"#334155","fontFamily":"Inter, Arial"}}}%%
flowchart LR
    subgraph FE["fa:fa-window-maximize Frontend"]
        HTML["fa:fa-code HTML"]:::frontend
        CSS["fa:fa-palette CSS"]:::frontend
        JS["fa:fa-js JavaScript"]:::frontend
        FirebaseHosting["fa:fa-fire Firebase Hosting"]:::hosting
    end

    subgraph BE["fa:fa-server Backend"]
        Python["fa:fa-python Python 3.11"]:::backend
        FastAPI["fa:fa-bolt FastAPI"]:::backend
        Pydantic["fa:fa-check-double Pydantic"]:::backend
        Docker["fa:fa-box Docker"]:::deploy
    end

    subgraph AI["fa:fa-brain AI Providers"]
        Groq["fa:fa-gauge-high Groq"]:::ai
        GeminiFlash["fa:fa-gem Gemini Flash"]:::ai
        GeminiVision["fa:fa-image Gemini Vision"]:::vision
        OpenRouter["fa:fa-route OpenRouter"]:::ai
    end

    subgraph DATA["fa:fa-database Data + Reports"]
        Firestore["fa:fa-fire Firestore"]:::data
        GCS["fa:fa-cloud Cloud Storage"]:::data
        ReportLab["fa:fa-file-pdf ReportLab"]:::report
    end

    FirebaseHosting --> FastAPI
    FastAPI --> Groq
    FastAPI --> GeminiFlash
    FastAPI --> GeminiVision
    FastAPI --> OpenRouter
    FastAPI --> Firestore
    FastAPI --> GCS
    ReportLab --> GCS
    Docker --> FastAPI

    classDef frontend fill:#dbeafe,stroke:#2563eb,stroke-width:2px,color:#172554;
    classDef hosting fill:#fff7ed,stroke:#f97316,stroke-width:2px,color:#431407;
    classDef backend fill:#dcfce7,stroke:#16a34a,stroke-width:2px,color:#052e16;
    classDef deploy fill:#e0f2fe,stroke:#0284c7,stroke-width:2px,color:#082f49;
    classDef ai fill:#fae8ff,stroke:#c026d3,stroke-width:2px,color:#3b0764;
    classDef vision fill:#fef3c7,stroke:#d97706,stroke-width:2px,color:#422006;
    classDef data fill:#f1f5f9,stroke:#475569,stroke-width:2px,color:#0f172a;
    classDef report fill:#fee2e2,stroke:#dc2626,stroke-width:2px,color:#450a0a;
```

---

## Repository Structure

```text
NIV-AI/
|-- backend/
|   |-- main.py                         # FastAPI routes and app bootstrap
|   |-- schemas/
|   |   `-- schemas.py                  # Pydantic models and response contracts
|   |-- engines/
|   |   |-- compute.py                  # Headless deterministic calculation bundle
|   |   |-- india_defaults.py           # India-specific acquisition cost engine
|   |   `-- pdf_generator.py            # ReportLab PDF rendering
|   |-- agents/
|   |   |-- base_agent.py               # Gemini/Ollama routing, JSON parsing, retries
|   |   |-- deterministic/              # Pure Python finance and risk modules
|   |   |-- ai_reasoning/               # Behavioral, brochure, synthesizer agents
|   |   |-- validation/                 # Assumption and conflict validation
|   |   |-- presentation/               # Chart/report presentation model builder
|   |   |-- context_interaction/         # Follow-up conversation and context state
|   |   `-- orchestration/              # Central orchestrator
|   |-- roundtable/                     # Multi-agent discussion engine
|   |-- firebase/                       # Firebase Admin and Firestore operations
|   |-- storage/                        # GCS upload and signed URL helpers
|   |-- auth/                           # Firebase token verification middleware
|   |-- integration_test.py
|   `-- test_deterministic.py
|-- frontend/
|   |-- index.html
|   |-- dashboard.html
|   |-- onboarding.html
|   |-- history.html
|   |-- compare.html
|   |-- impact.html
|   |-- niv-ai .html                    # Older standalone prototype
|   |-- css/
|   `-- js/
|-- Dockerfile
|-- firebase.json
|-- firestore.rules
|-- requirements.txt
`-- README.md
```

## Application Flow

The user experience is deliberately shaped like a guided audit rather than a
single calculator form. Each screen adds context that is later used by either
the deterministic engines or the AI agents.

<p align="center">
  <img src="https://cdn.simpleicons.org/html5/E34F26" alt="HTML5" width="18">
  <img src="https://cdn.simpleicons.org/javascript/F7DF1E" alt="JavaScript" width="18">
  <img src="https://cdn.simpleicons.org/firebase/FFCA28" alt="Firebase" width="18">
</p>

```mermaid
%%{init: {"theme":"base","themeVariables":{"primaryColor":"#f8fafc","primaryBorderColor":"#334155","lineColor":"#64748b","fontFamily":"Inter, Arial"}}}%%
flowchart TD
    A["fa:fa-door-open Landing Page"]:::entry --> B["fa:fa-mouse-pointer Analyze Property CTA"]:::entry
    B --> C["fa:fa-list-check Guided Intake Wizard"]:::wizard

    C --> E["fa:fa-wallet Financial Profile"]:::finance
    E --> E1["Income + co-borrower income"]:::finance
    E --> E2["Savings, rent, expenses"]:::finance
    E --> E3["Existing EMIs"]:::finance

    C --> F["fa:fa-building Property Profile"]:::property
    F --> F1["Price, location, carpet area"]:::property
    F --> F2["Down payment, tenure, rate"]:::property
    F --> F3["Builder, RERA, possession"]:::property

    C --> G["fa:fa-shield-halved Risk Context"]:::risk
    G --> G1["Job stability + growth"]:::risk
    G --> G2["Dependents + commute"]:::risk
    G --> G3["Photos, QR, documents"]:::risk

    G --> H{"fa:fa-brain Behavioral friction?"}:::decision
    H -- "Triggered" --> I["Challenge questions"]:::ai
    H -- "Not triggered" --> J["Run analysis"]:::action
    I --> J

    J --> K["fa:fa-gears Finance engines"]:::math
    J --> L["fa:fa-robot AI agent review"]:::ai
    K --> M["fa:fa-chart-line Report model"]:::report
    L --> M
    M --> N["fa:fa-file-lines Verdict dashboard"]:::report
    N --> O["What-if, compare, export, share"]:::action

    classDef entry fill:#e0f2fe,stroke:#0284c7,stroke-width:2px,color:#082f49;
    classDef wizard fill:#ede9fe,stroke:#7c3aed,stroke-width:2px,color:#2e1065;
    classDef finance fill:#dcfce7,stroke:#16a34a,stroke-width:2px,color:#052e16;
    classDef property fill:#fef3c7,stroke:#d97706,stroke-width:2px,color:#422006;
    classDef risk fill:#fee2e2,stroke:#dc2626,stroke-width:2px,color:#450a0a;
    classDef decision fill:#f5f3ff,stroke:#8b5cf6,stroke-width:3px,color:#2e1065;
    classDef ai fill:#fae8ff,stroke:#c026d3,stroke-width:2px,color:#3b0764;
    classDef math fill:#dbeafe,stroke:#2563eb,stroke-width:2px,color:#172554;
    classDef report fill:#f1f5f9,stroke:#475569,stroke-width:2px,color:#0f172a;
    classDef action fill:#ffedd5,stroke:#ea580c,stroke-width:2px,color:#431407;
```

The major user-facing use cases are broader than the initial verdict. A buyer
can inspect the analysis, compare alternatives, generate documents, and share a
decision package with advisors.

<p align="center">
  <img src="https://cdn.simpleicons.org/whatsapp/25D366" alt="WhatsApp" width="18">
  <img src="https://cdn.simpleicons.org/adobeacrobatreader/B91C1C" alt="PDF" width="18">
  <img src="https://cdn.simpleicons.org/googlegemini/8E75B2" alt="Gemini" width="18">
</p>

```mermaid
%%{init: {"theme":"base","themeVariables":{"primaryColor":"#ffffff","primaryBorderColor":"#111827","lineColor":"#475569","fontFamily":"Inter, Arial"}}}%%
flowchart LR
    Buyer["fa:fa-user Home Buyer"]:::actor --> Core["fa:fa-house NIV AI"]:::core
    Admin["fa:fa-user-gear System Admin"]:::actor --> Ops["Operations"]:::ops

    Core --> U1["Check affordability"]:::finance
    Core --> U2["Find hidden costs"]:::finance
    Core --> U3["Stress-test loan"]:::risk
    Core --> U4["Detect bias"]:::ai
    Core --> U5["Review verdict"]:::report
    Core --> U6["Compare property"]:::action
    Core --> U7["Generate report"]:::report
    Core --> U8["Create counter-offer"]:::action
    Core --> U9["Draft bank email"]:::action

    Ops --> O1["Configure API keys"]:::ops
    Ops --> O2["Deploy frontend"]:::ops
    Ops --> O3["Deploy backend"]:::ops
    Ops --> O4["Monitor costs"]:::ops

    classDef actor fill:#e0f2fe,stroke:#0284c7,stroke-width:2px,color:#082f49;
    classDef core fill:#fef3c7,stroke:#d97706,stroke-width:3px,color:#422006;
    classDef finance fill:#dcfce7,stroke:#16a34a,stroke-width:2px,color:#052e16;
    classDef risk fill:#fee2e2,stroke:#dc2626,stroke-width:2px,color:#450a0a;
    classDef ai fill:#fae8ff,stroke:#c026d3,stroke-width:2px,color:#3b0764;
    classDef report fill:#f1f5f9,stroke:#475569,stroke-width:2px,color:#0f172a;
    classDef action fill:#ffedd5,stroke:#ea580c,stroke-width:2px,color:#431407;
    classDef ops fill:#ede9fe,stroke:#7c3aed,stroke-width:2px,color:#2e1065;
```

### Landing Page

The deployed landing page positions NIV AI as a Mumbai-first home buying
decision engine. It emphasizes:

- deterministic math,
- stress testing,
- behavioral challenge,
- a six-agent pipeline,
- RERA and property intelligence,
- and post-analysis services.

### Analysis Wizard

The analysis app collects a structured buyer profile across three broad stages:

1. Financial profile
   - monthly income,
   - spouse/co-borrower income,
   - liquid savings,
   - existing EMIs,
   - expenses,
   - rent.

2. Property details
   - property price,
   - location,
   - down payment,
   - tenure,
   - interest rate,
   - carpet area,
   - readiness,
   - builder,
   - RERA and GST identifiers.

3. Final risk context
   - job stability,
   - expected growth,
   - dependents,
   - commute distance,
   - property and financial notes,
   - optional document/photo uploads.

### Behavioral Friction Gate

Before submitting risky inputs, the frontend can ask additional behavioral
questions. This is meant to surface hidden commitment bias, FOMO, delay
tolerance, liquidity awareness, and job-loss preparedness.

### Analysis Output

The report presents:

- verdict,
- confidence,
- risk reasons,
- computed numbers,
- stress-test outcomes,
- property signals,
- hidden costs,
- blind spots,
- path-to-safe recommendations,
- and export/share actions.

---

## Backend Architecture

The FastAPI backend is intentionally thin at the route layer. Route handlers
validate authentication and ownership, convert request bodies into Pydantic
models, call deterministic engines and orchestrator methods, then return typed
responses.

Key backend responsibilities:

- initialize Firebase Admin,
- initialize the AI orchestrator,
- validate Firebase tokens,
- enforce session ownership,
- persist session state,
- run deterministic calculations,
- call AI agents,
- stream roundtable messages,
- generate PDF reports,
- upload reports to GCS.

<p align="center">
  <img src="https://cdn.simpleicons.org/fastapi/009688" alt="FastAPI" width="18">
  <img src="https://cdn.simpleicons.org/python/3776AB" alt="Python" width="18">
  <img src="https://cdn.simpleicons.org/firebase/FFCA28" alt="Firebase" width="18">
  <img src="https://cdn.simpleicons.org/googlecloud/4285F4" alt="Google Cloud" width="18">
</p>

```mermaid
%%{init: {"theme":"base","themeVariables":{"primaryColor":"#eff6ff","primaryBorderColor":"#2563eb","lineColor":"#334155","fontFamily":"Inter, Arial"}}}%%
flowchart LR
    subgraph Client["fa:fa-desktop Client Layer"]
        Browser["Browser"]:::client
        Wizard["Analysis Wizard"]:::client
        Dashboard["Report Dashboard"]:::client
    end

    subgraph API["fa:fa-server FastAPI Service"]
        Routes["HTTP routes"]:::api
        Auth["Firebase token middleware"]:::security
        WS["Roundtable WebSocket"]:::api
        Orchestrator["Agent orchestrator"]:::ai
    end

    subgraph Finance["fa:fa-calculator Deterministic Finance"]
        Cost["India cost engine"]:::math
        EMI["EMI + cash flow"]:::math
        Scenario["Scenario simulator"]:::risk
        Score["Risk scorer"]:::risk
    end

    subgraph Cloud["fa:fa-cloud Cloud Services"]
        Firestore["Firestore"]:::cloud
        Storage["Cloud Storage"]:::cloud
        Gemini["Gemini / Groq / OpenRouter"]:::ai
    end

    Browser --> Wizard
    Browser --> Dashboard
    Wizard --> Routes
    Dashboard --> Routes
    Dashboard --> WS
    Routes --> Auth
    Auth --> Firestore
    Routes --> Finance
    Routes --> Orchestrator
    Orchestrator --> Gemini
    Finance --> Firestore
    Routes --> Storage

    classDef client fill:#dbeafe,stroke:#2563eb,stroke-width:2px,color:#172554;
    classDef api fill:#dcfce7,stroke:#16a34a,stroke-width:2px,color:#052e16;
    classDef security fill:#fee2e2,stroke:#dc2626,stroke-width:2px,color:#450a0a;
    classDef math fill:#fef3c7,stroke:#d97706,stroke-width:2px,color:#422006;
    classDef risk fill:#ffedd5,stroke:#ea580c,stroke-width:2px,color:#431407;
    classDef ai fill:#fae8ff,stroke:#c026d3,stroke-width:2px,color:#3b0764;
    classDef cloud fill:#f1f5f9,stroke:#475569,stroke-width:2px,color:#0f172a;
```

The full analysis request keeps arithmetic, persistence, AI interpretation, and
report rendering as separate responsibilities.

<p align="center">
  <img src="https://cdn.simpleicons.org/firebase/FFCA28" alt="Firestore" width="18">
  <img src="https://cdn.simpleicons.org/googlegemini/8E75B2" alt="Gemini" width="18">
  <img src="https://cdn.simpleicons.org/googlecloud/4285F4" alt="Cloud Storage" width="18">
</p>

```mermaid
%%{init: {"theme":"base","themeVariables":{"actorBkg":"#dbeafe","actorBorder":"#2563eb","actorTextColor":"#172554","activationBkgColor":"#fef3c7","activationBorderColor":"#d97706","sequenceNumberColor":"#ffffff","lineColor":"#475569","fontFamily":"Inter, Arial"}}}%%
sequenceDiagram
    autonumber
    participant U as Buyer Browser
    participant F as Frontend JS
    participant API as FastAPI
    participant DB as Firestore
    participant Math as Finance Engines
    participant AI as Agent Orchestrator
    participant LLM as Groq / Gemini / OpenRouter
    participant GCS as Cloud Storage

    U->>F: Submit property audit form
    F->>API: POST /analyze/{session_id}
    API->>DB: Verify session ownership
    API->>DB: Save financial inputs
    API->>Math: Run cost, EMI, FOIR, scenarios, risk score
    Math-->>API: Deterministic result bundle
    API->>DB: Save simulation results
    API->>AI: Run behavioral, validation, presentation agents
    AI->>LLM: Structured JSON prompts
    LLM-->>AI: Agent outputs
    AI-->>API: AnalysisResponse
    API-->>F: Verdict and report data
    F-->>U: Render dashboard
    U->>F: Request PDF / export
    F->>API: GET /report/{session_id}
    API->>GCS: Upload generated PDF
    GCS-->>API: Signed URL
    API-->>F: Download link
```

The deterministic path is the backbone of the product. It is intentionally
pure Python and should remain testable without calling external model APIs.

<p align="center">
  <img src="https://cdn.simpleicons.org/python/3776AB" alt="Python" width="18">
  <img src="https://cdn.simpleicons.org/pydantic/E92063" alt="Pydantic" width="18">
</p>

```mermaid
%%{init: {"theme":"base","themeVariables":{"primaryColor":"#ecfeff","primaryBorderColor":"#0891b2","lineColor":"#334155","fontFamily":"Inter, Arial"}}}%%
flowchart TD
    Input["fa:fa-keyboard UserInput"]:::input --> Normalize["Normalize state, district, buyer flags"]:::input
    Normalize --> Loan["Loan amount"]:::math
    Normalize --> Cost["True acquisition cost"]:::cost
    Normalize --> Afford["Affordability calculation"]:::math

    Cost --> GST["GST slab classifier"]:::cost
    Cost --> Stamp["District stamp duty"]:::cost
    Cost --> Fees["Bank + legal + maintenance fees"]:::cost
    Cost --> Total["True total cost"]:::cost

    Afford --> EMI["Monthly EMI"]:::math
    Afford --> Ratio["EMI / income"]:::math
    Afford --> Surplus["Post-EMI surplus"]:::math
    Afford --> Cash["12-month cash flow"]:::math
    Afford --> FOIR["FOIR underwriting check"]:::risk
    Afford --> LTV["Building age / LTV risk"]:::risk

    EMI --> Scenario["Stress scenario simulator"]:::scenario
    Surplus --> Scenario
    Cash --> Scenario
    Scenario --> S1["Base case"]:::scenario
    Scenario --> S2["30 percent income drop"]:::scenario
    Scenario --> S3["6-month job loss"]:::scenario
    Scenario --> S4["2 percent rate hike"]:::scenario
    Scenario --> S5["INR 5L emergency"]:::scenario

    S1 --> RiskScore["Composite risk score"]:::risk
    S2 --> RiskScore
    S3 --> RiskScore
    S4 --> RiskScore
    S5 --> RiskScore
    FOIR --> RiskScore
    Ratio --> RiskScore
    Total --> Output["ComputeAllOutput"]:::output
    RiskScore --> Output

    classDef input fill:#e0f2fe,stroke:#0284c7,stroke-width:2px,color:#082f49;
    classDef math fill:#dcfce7,stroke:#16a34a,stroke-width:2px,color:#052e16;
    classDef cost fill:#fef3c7,stroke:#d97706,stroke-width:2px,color:#422006;
    classDef scenario fill:#ffedd5,stroke:#ea580c,stroke-width:2px,color:#431407;
    classDef risk fill:#fee2e2,stroke:#dc2626,stroke-width:2px,color:#450a0a;
    classDef output fill:#ede9fe,stroke:#7c3aed,stroke-width:3px,color:#2e1065;
```

### Important Backend Modules

| File | Responsibility |
|---|---|
| `backend/main.py` | FastAPI app, routes, startup, CORS, session and report APIs |
| `backend/schemas/schemas.py` | All request/response Pydantic models |
| `backend/engines/compute.py` | One-call deterministic calculation bundle |
| `backend/engines/india_defaults.py` | GST, stamp duty, registration, hidden fees |
| `backend/agents/deterministic/financial_reality.py` | EMI, surplus, FOIR, cash flow, LTV risk |
| `backend/agents/deterministic/scenario_simulation.py` | Stress scenarios |
| `backend/agents/deterministic/risk_scorer.py` | Composite risk score |
| `backend/agents/orchestration/orchestrator.py` | Central AI pipeline controller |
| `backend/roundtable/discussion_engine.py` | Live specialist discussion flow |
| `backend/firebase/firestore_ops.py` | Firestore CRUD helpers |
| `backend/storage/gcs_client.py` | PDF upload and signed URLs |

---

## AI Agent Architecture

All text-based agents inherit from `BaseAgent`, which centralizes:

- prompt assembly,
- Gemini/Ollama routing,
- retry handling,
- JSON extraction,
- invalid JSON recovery,
- streaming support.

### Model Routing

`USE_OLLAMA=true`

- Uses local Ollama.
- Default model: `llama3.2:3b`.
- Useful for local testing without API spend.
- Produces leaner outputs where needed.

`USE_OLLAMA=false`

- Uses Gemini 2.0 Flash through the Google Generative AI SDK.
- Intended for production-grade multi-agent and full-audit generation.
- Brochure analysis always uses Gemini Vision because there is no equivalent
  local multimodal path in the current codebase.

### Blackboard Pattern

The orchestrator uses a per-session blackboard as the shared state container.
This lets agents reason over a single evolving state instead of passing large
custom payloads between every step.

The blackboard includes:

- user inputs,
- behavioral intake,
- deterministic results,
- behavioral analysis,
- validation output,
- presentation output,
- roundtable transcript,
- final verdict,
- active flags,
- open questions.

<p align="center">
  <img src="https://cdn.simpleicons.org/groq/F55036" alt="Groq" width="18">
  <img src="https://cdn.simpleicons.org/googlegemini/8E75B2" alt="Gemini" width="18">
  <img src="https://cdn.simpleicons.org/openrouter/111111" alt="OpenRouter" width="18">
</p>

```mermaid
%%{init: {"theme":"base","themeVariables":{"primaryColor":"#fae8ff","primaryBorderColor":"#c026d3","lineColor":"#475569","fontFamily":"Inter, Arial"}}}%%
flowchart LR
    subgraph BB["fa:fa-clipboard Shared Blackboard"]
        UI["User input"]:::input
        BI["Behavioral intake"]:::input
        DR["Deterministic results"]:::math
        CTX["Conversation context"]:::input
    end

    subgraph FirstPass["Parallel first pass"]
        BA["fa:fa-brain Behavioral Analysis"]:::ai
        VA["fa:fa-magnifying-glass Validation Agent"]:::ai
    end

    subgraph Presentation["Presentation assembly"]
        PA["fa:fa-chart-pie Presentation Agent"]:::report
        Charts["Chart data"]:::report
        Cards["Warning cards"]:::risk
        PDFModel["PDF content model"]:::report
    end

    subgraph Roundtable["Live specialist roundtable"]
        Marcus["Marcus: Financial Analyst"]:::expert
        Zara["Zara: Risk Strategist"]:::risk
        Soren["Soren: Behavioral Economist"]:::expert
        Conv["Convergence Checker"]:::decision
    end

    subgraph Final["Final synthesis"]
        DS["fa:fa-pen-nib Decision Synthesizer"]:::ai
        Verdict["VerdictOutput"]:::decision
        Audit["6-domain audit"]:::report
    end

    BB --> BA
    BB --> VA
    BA --> PA
    VA --> PA
    DR --> PA
    PA --> Charts
    PA --> Cards
    PA --> PDFModel
    BA --> Soren
    VA --> Zara
    DR --> Marcus
    Marcus --> Conv
    Zara --> Conv
    Soren --> Conv
    Conv --> DS
    PDFModel --> DS
    DS --> Verdict
    DS --> Audit

    classDef input fill:#e0f2fe,stroke:#0284c7,stroke-width:2px,color:#082f49;
    classDef math fill:#dcfce7,stroke:#16a34a,stroke-width:2px,color:#052e16;
    classDef ai fill:#fae8ff,stroke:#c026d3,stroke-width:2px,color:#3b0764;
    classDef report fill:#f1f5f9,stroke:#475569,stroke-width:2px,color:#0f172a;
    classDef risk fill:#fee2e2,stroke:#dc2626,stroke-width:2px,color:#450a0a;
    classDef expert fill:#fef3c7,stroke:#d97706,stroke-width:2px,color:#422006;
    classDef decision fill:#ede9fe,stroke:#7c3aed,stroke-width:3px,color:#2e1065;
```

The roundtable has a clear discussion arc. It is designed to avoid repetitive
agent output by changing the task in each round: observe, challenge, converge,
then conclude.

<p align="center">
  <img src="https://cdn.simpleicons.org/groq/F55036" alt="Groq" width="18">
  <img src="https://cdn.simpleicons.org/googlegemini/8E75B2" alt="Gemini" width="18">
</p>

```mermaid
%%{init: {"theme":"base","themeVariables":{"primaryColor":"#fef3c7","primaryBorderColor":"#d97706","lineColor":"#475569","fontFamily":"Inter, Arial"}}}%%
stateDiagram-v2
    [*] --> WaitingForAnalysis
    WaitingForAnalysis --> Round1Opening: analysis complete
    Round1Opening --> Round2Challenge: opening observations
    Round2Challenge --> Round3Converge: direct challenges complete
    Round3Converge --> CheckConvergence: positions established
    CheckConvergence --> DecisionSynthesis: converged
    CheckConvergence --> Round4Conclusion: one more round needed
    Round4Conclusion --> DecisionSynthesis: final conclusions
    DecisionSynthesis --> VerdictReady: synthesizer returns JSON
    VerdictReady --> PersistVerdict: stream verdict first
    PersistVerdict --> [*]

    WaitingForAnalysis --> Error: missing blackboard state
    Round1Opening --> Error: AI call failure
    Round2Challenge --> Error: invalid JSON
    Round3Converge --> Error: websocket disconnect
    Error --> [*]
```

---

## Data Model

Core domain models live in `backend/schemas/schemas.py`.

Important model groups:

- input models:
  - `UserInput`,
  - `BehavioralIntake`,
  - `ConversationMessage`.
- deterministic outputs:
  - `IndiaCostBreakdown`,
  - `FinancialRealityOutput`,
  - `ScenarioOutput`,
  - `AllScenariosOutput`,
  - `RiskScoreOutput`.
- AI outputs:
  - `BehavioralAnalysisOutput`,
  - `ValidationOutput`,
  - `PresentationOutput`,
  - `VerdictOutput`.
- session and report outputs:
  - `SessionStartResponse`,
  - `AnalysisResponse`,
  - `ReportOutput`.

The persisted Firestore model is session-centered. Every behavioral answer,
input snapshot, simulation output, discussion message, verdict, and report is
attached back to a buyer-owned session.

<p align="center">
  <img src="https://cdn.simpleicons.org/firebase/FFCA28" alt="Firestore" width="18">
</p>

```mermaid
%%{init: {"theme":"base","themeVariables":{"primaryColor":"#f1f5f9","primaryBorderColor":"#475569","lineColor":"#64748b","fontFamily":"Inter, Arial"}}}%%
erDiagram
    USER ||--o{ SESSION : owns
    SESSION ||--o{ BEHAVIORAL_INTAKE : contains
    SESSION ||--o{ FINANCIAL_INPUT : stores
    SESSION ||--o{ SIMULATION_RESULT : stores
    SESSION ||--o{ DISCUSSION_MESSAGE : streams
    SESSION ||--o{ VERDICT : produces
    SESSION ||--o{ REPORT : generates

    USER {
        string uid
        string auth_provider
    }

    SESSION {
        string session_id
        string user_id
        string title
        string city
        string state
        string status
        string created_at
        string updated_at
        number property_price
        string risk_label
        string verdict_summary
    }

    BEHAVIORAL_INTAKE {
        number question_id
        string question
        string answer
        string bias_signal
    }

    FINANCIAL_INPUT {
        number monthly_income
        number monthly_expenses
        number total_savings
        number down_payment
        number property_price
        number annual_interest_rate
        number tenure_years
        string property_type
    }

    SIMULATION_RESULT {
        object india_cost_breakdown
        object financial_reality
        object all_scenarios
        object risk_score
    }

    DISCUSSION_MESSAGE {
        string agent
        string message_type
        string content
        number round
        string timestamp
        string directed_at
    }

    VERDICT {
        string verdict
        number confidence
        array primary_reasons
        array key_warnings
        number safe_price_recommendation
        string final_narrative
    }

    REPORT {
        string gcs_url
        string generated_at
    }
```

---

## API Surface

The API surface separates fast deterministic calculation, authenticated session
workflows, AI-heavy analysis, streaming roundtable discussion, and report
generation.

<p align="center">
  <img src="https://cdn.simpleicons.org/fastapi/009688" alt="FastAPI" width="18">
  <img src="https://cdn.simpleicons.org/firebase/FFCA28" alt="Firebase" width="18">
  <img src="https://cdn.simpleicons.org/googlegemini/8E75B2" alt="Gemini" width="18">
</p>

```mermaid
%%{init: {"theme":"base","themeVariables":{"primaryColor":"#eff6ff","primaryBorderColor":"#2563eb","lineColor":"#475569","fontFamily":"Inter, Arial"}}}%%
flowchart TB
    Client["fa:fa-desktop Frontend Client"]:::client --> Health["GET /health"]:::public
    Client --> Calc["POST /api/v1/calculate"]:::public
    Client --> SessionStart["POST /session/start"]:::auth
    Client --> SessionGet["GET /session/{session_id}"]:::auth
    Client --> History["GET /session/history/{user_id}"]:::auth
    Client --> Behavioral["POST /behavioral/{session_id}"]:::auth
    Client --> Analyze["POST /analyze/{session_id}"]:::analysis
    Client --> Brochure["POST /analyze/brochure/{session_id}"]:::vision
    Client --> Conversation["POST /conversation/{session_id}"]:::analysis
    Client --> Roundtable["WS /roundtable/{session_id}"]:::stream
    Client --> Report["GET /report/{session_id}"]:::report

    Calc --> Math["Deterministic engines only"]:::math
    Analyze --> Full["Finance + AI orchestration"]:::analysis
    Brochure --> GeminiVision["Gemini Vision extraction"]:::vision
    Roundtable --> Live["Live specialist discussion"]:::stream
    Report --> PDF["PDF generation + signed URL"]:::report

    classDef client fill:#dbeafe,stroke:#2563eb,stroke-width:2px,color:#172554;
    classDef public fill:#dcfce7,stroke:#16a34a,stroke-width:2px,color:#052e16;
    classDef auth fill:#fef3c7,stroke:#d97706,stroke-width:2px,color:#422006;
    classDef analysis fill:#fae8ff,stroke:#c026d3,stroke-width:2px,color:#3b0764;
    classDef vision fill:#ede9fe,stroke:#7c3aed,stroke-width:2px,color:#2e1065;
    classDef stream fill:#ffedd5,stroke:#ea580c,stroke-width:2px,color:#431407;
    classDef report fill:#f1f5f9,stroke:#475569,stroke-width:2px,color:#0f172a;
    classDef math fill:#ecfeff,stroke:#0891b2,stroke-width:2px,color:#164e63;
```

### Health

```http
GET /health
```

Returns service health, service name, and version.

### Headless Deterministic Calculate

```http
POST /api/v1/calculate
```

Runs deterministic calculations only. This endpoint is designed for fast
frontend recalculation and can be used for sliders, comparison tools, and
batch testing without LLM spend.

### Session Management

```http
POST /session/start
GET /session/{session_id}
GET /session/history/{user_id}
```

Creates and retrieves authenticated user sessions.

### Behavioral Intake

```http
POST /behavioral/{session_id}
```

Stores behavioral questionnaire answers for the session.

### Full Analysis

```http
POST /analyze/{session_id}
```

Runs:

1. financial input persistence,
2. India cost calculation,
3. affordability calculation,
4. scenario simulation,
5. risk scoring,
6. behavioral analysis,
7. validation,
8. presentation generation,
9. analysis response assembly.

### Brochure Analysis

```http
POST /analyze/brochure/{session_id}
```

Accepts image or PDF property brochure uploads and uses Gemini Vision to
extract structured property details.

Supported MIME types:

- `image/jpeg`
- `image/png`
- `image/webp`
- `image/heic`
- `application/pdf`

### Conversation

```http
POST /conversation/{session_id}
```

Handles follow-up questions after analysis and decides which agents need to
rerun based on the user's natural-language update.

### Roundtable Streaming

```http
WS /roundtable/{session_id}?token={firebase_id_token}
```

Streams a live multi-agent discussion and sends a final verdict event when the
decision synthesizer completes.

### PDF Report

```http
GET /report/{session_id}
```

Generates or retrieves a PDF report, uploads it to Cloud Storage, and returns a
signed URL.

---

## Configuration

Create a `.env` file from `.env.example`.

```bash
cp .env.example .env
```

Required groups:

### Gemini

```env
GEMINI_API_KEY=your_gemini_api_key_here
USE_OLLAMA=false
```

For local-only AI testing:

```env
USE_OLLAMA=true
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2:3b
```

### Firebase

```env
FIREBASE_PROJECT_ID=your_firebase_project_id
FIREBASE_PRIVATE_KEY_ID=your_private_key_id
FIREBASE_PRIVATE_KEY=your_private_key
FIREBASE_CLIENT_EMAIL=your_client_email
FIREBASE_CLIENT_ID=your_client_id
GOOGLE_APPLICATION_CREDENTIALS=serviceAccountKey.json
```

### Google Cloud Storage

```env
GCS_BUCKET_NAME=your_gcs_bucket_name
GCS_PROJECT_ID=your_gcp_project_id
```

### App URLs

```env
FRONTEND_URL=http://localhost:3000
BACKEND_URL=http://localhost:8000
PORT=8080
```

### Auth

```env
JWT_SECRET_KEY=your_jwt_secret_key_minimum_32_characters
JWT_ALGORITHM=HS256
JWT_EXPIRY_HOURS=24
```

---

## Local Development

### 1. Create a Python environment

```bash
python -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
```

Edit `.env` with Firebase, GCS, and AI settings.

### 4. Start the backend

From the `backend` directory:

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 5. Serve the frontend

The repository uses Firebase Hosting for static assets. For a quick local
static preview, serve the `frontend` folder with any static file server.

Example:

```bash
python -m http.server 3000 --directory frontend
```

Then open:

```text
http://localhost:3000
```

---

## Testing

The repository includes deterministic and integration-style tests:

```bash
python backend/test_deterministic.py
python backend/integration_test.py
```

Recommended additional validation:

- run `/health`,
- run `/api/v1/calculate` with a sample `UserInput`,
- test Firebase token verification,
- test Firestore session creation,
- test GCS report upload in a staging bucket,
- test one Gemini-backed agent path with `USE_OLLAMA=false`,
- test one local model path with `USE_OLLAMA=true`.

---

## Deployment

The repository supports a containerized backend and static frontend deployment.
The live deployment observed during analysis uses Firebase Hosting for the
frontend and a containerized FastAPI backend exposed over HTTPS.

<p align="center">
  <img src="https://cdn.simpleicons.org/docker/2496ED" alt="Docker" width="18">
  <img src="https://cdn.simpleicons.org/firebase/FFCA28" alt="Firebase" width="18">
  <img src="https://cdn.simpleicons.org/googlecloud/4285F4" alt="Google Cloud" width="18">
  <img src="https://cdn.simpleicons.org/railway/0B0D0E" alt="Railway" width="18">
</p>

```mermaid
%%{init: {"theme":"base","themeVariables":{"primaryColor":"#f8fafc","primaryBorderColor":"#334155","lineColor":"#475569","fontFamily":"Inter, Arial"}}}%%
flowchart LR
    Dev["fa:fa-code Developer"]:::dev --> Git["fa:fa-github GitHub Repository"]:::repo
    Git --> Build["fa:fa-box Docker build"]:::build
    Build --> BackendHost["fa:fa-server Container backend hosting"]:::backend

    Dev --> FirebaseDeploy["fa:fa-fire Firebase deploy"]:::firebase
    FirebaseDeploy --> Hosting["fa:fa-globe Firebase Hosting CDN"]:::firebase

    BackendHost --> Env["Runtime environment variables"]:::config
    BackendHost --> Firestore["Firestore"]:::cloud
    BackendHost --> Bucket["Cloud Storage bucket"]:::cloud
    BackendHost --> Providers["Groq + Gemini + OpenRouter"]:::ai

    Hosting --> Browser["User browser"]:::client
    Browser --> BackendHost

    classDef dev fill:#e0f2fe,stroke:#0284c7,stroke-width:2px,color:#082f49;
    classDef repo fill:#f1f5f9,stroke:#475569,stroke-width:2px,color:#0f172a;
    classDef build fill:#dbeafe,stroke:#2563eb,stroke-width:2px,color:#172554;
    classDef backend fill:#dcfce7,stroke:#16a34a,stroke-width:2px,color:#052e16;
    classDef firebase fill:#fef3c7,stroke:#d97706,stroke-width:2px,color:#422006;
    classDef config fill:#ffedd5,stroke:#ea580c,stroke-width:2px,color:#431407;
    classDef cloud fill:#f1f5f9,stroke:#64748b,stroke-width:2px,color:#0f172a;
    classDef ai fill:#fae8ff,stroke:#c026d3,stroke-width:2px,color:#3b0764;
    classDef client fill:#ede9fe,stroke:#7c3aed,stroke-width:2px,color:#2e1065;
```

### Backend: Container Hosting

The `Dockerfile` builds a Python 3.11 container and starts Uvicorn. The same
container shape can be deployed on Cloud Run, Railway, or any platform that can
run an HTTP container on the configured `PORT`.

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PORT=8080
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
```

The backend host should be configured with:

- `PORT=8080`,
- Firebase service account credentials,
- Gemini API key,
- GCS bucket configuration,
- frontend CORS origin,
- appropriate memory and timeout settings for AI calls.

### Frontend: Firebase Hosting

`firebase.json` points hosting at the `frontend` directory and rewrites all
routes to `index.html`.

```json
{
  "hosting": {
    "public": "frontend",
    "rewrites": [
      {
        "source": "**",
        "destination": "/index.html"
      }
    ]
  }
}
```

Deploy with:

```bash
firebase deploy --only hosting
```

---

## Security Model

The security model is session-scoped: the backend verifies identity first, then
checks ownership before reading or writing session data.

<p align="center">
  <img src="https://cdn.simpleicons.org/firebase/FFCA28" alt="Firebase Auth" width="18">
  <img src="https://cdn.simpleicons.org/fastapi/009688" alt="FastAPI" width="18">
</p>

```mermaid
%%{init: {"theme":"base","themeVariables":{"primaryColor":"#fee2e2","primaryBorderColor":"#dc2626","lineColor":"#475569","fontFamily":"Inter, Arial"}}}%%
flowchart TD
    Browser["fa:fa-desktop Browser"]:::client --> Token["Firebase ID token"]:::auth
    Token --> Verify["FastAPI verify_token dependency"]:::api
    Verify --> Admin["Firebase Admin verify_id_token"]:::firebase
    Admin --> UID["Authenticated UID"]:::safe

    UID --> Session["Load session from Firestore"]:::data
    Session --> Owner{"session.user_id == UID?"}:::decision
    Owner -- "Yes" --> Allow["Allow scoped read/write"]:::safe
    Owner -- "No" --> Deny["403 Access denied"]:::deny

    Allow --> Data["Session, inputs, results, reports"]:::data
    Deny --> Stop["Stop request"]:::deny

    classDef client fill:#dbeafe,stroke:#2563eb,stroke-width:2px,color:#172554;
    classDef auth fill:#fef3c7,stroke:#d97706,stroke-width:2px,color:#422006;
    classDef api fill:#dcfce7,stroke:#16a34a,stroke-width:2px,color:#052e16;
    classDef firebase fill:#ffedd5,stroke:#ea580c,stroke-width:2px,color:#431407;
    classDef safe fill:#bbf7d0,stroke:#16a34a,stroke-width:2px,color:#052e16;
    classDef data fill:#f1f5f9,stroke:#475569,stroke-width:2px,color:#0f172a;
    classDef decision fill:#ede9fe,stroke:#7c3aed,stroke-width:3px,color:#2e1065;
    classDef deny fill:#fecaca,stroke:#b91c1c,stroke-width:2px,color:#450a0a;
```

### Authentication

Authenticated endpoints use Firebase ID token verification through Firebase
Admin. The backend extracts the user UID and checks that the requested session
belongs to that UID.

### Authorization

Session reads and writes are scoped by `user_id`. If a user attempts to access
another user's session, the API returns `403 Access denied`.

### Firestore Rules

The included Firestore rules restrict session access to authenticated users
where `session.user_id == request.auth.uid`. Discussion messages inherit the
same session ownership constraint.

### File Upload Guardrails

Brochure upload handling validates:

- MIME type,
- max file size,
- session existence,
- session ownership.

### AI Output Guardrails

The agent base class instructs models to return strict JSON, retries failures,
and extracts JSON from imperfect LLM output. Deterministic calculations are
never delegated to the LLM.

---

## Cost Model

NIV AI is designed to stay lean at MVP scale. The frontend, RERA scraping, RBI
scraping, OCR, and QR scanning do not create meaningful per-user cost. The main
variable cost is LLM and vision usage, followed by backend hosting once traffic
grows beyond free or credit-backed tiers.

<p align="center">
  <img src="https://cdn.simpleicons.org/groq/F55036" alt="Groq" width="18">
  <img src="https://cdn.simpleicons.org/googlegemini/8E75B2" alt="Gemini" width="18">
  <img src="https://cdn.simpleicons.org/openrouter/111111" alt="OpenRouter" width="18">
  <img src="https://cdn.simpleicons.org/firebase/FFCA28" alt="Firebase" width="18">
  <img src="https://cdn.simpleicons.org/railway/0B0D0E" alt="Railway" width="18">
  <img src="https://cdn.simpleicons.org/whatsapp/25D366" alt="WhatsApp" width="18">
</p>

```mermaid
%%{init: {"theme":"base","themeVariables":{"primaryColor":"#fef3c7","primaryBorderColor":"#d97706","lineColor":"#475569","fontFamily":"Inter, Arial"}}}%%
flowchart TB
    Cost["fa:fa-coins Operational cost drivers"]:::root --> LLM["LLM API calls"]:::hot
    Cost --> Vision["Gemini Vision photos"]:::hot
    Cost --> Hosting["Firebase Hosting"]:::low
    Cost --> Backend["Railway FastAPI container"]:::medium
    Cost --> Domain["Optional .app domain"]:::low
    Cost --> WhatsApp["WhatsApp report delivery"]:::medium
    Cost --> GST["GST verification API"]:::low
    Cost --> Free["MahaRERA, RBI, OCR, QR"]:::free

    LLM --> Groq["Groq: low-cost structured reasoning"]:::provider
    LLM --> GeminiFlash["Gemini Flash: synthesis + fallback"]:::provider
    LLM --> OpenRouter["OpenRouter: provider routing"]:::provider
    Vision --> Photo["3-5 property photos when uploaded"]:::vision
    Free --> RERA["Public portal scraping"]:::free
    Free --> RBI["RBI and bank-rate scraping"]:::free
    Free --> OCR["Local pytesseract + pyzbar"]:::free

    classDef root fill:#fef3c7,stroke:#d97706,stroke-width:3px,color:#422006;
    classDef hot fill:#fee2e2,stroke:#dc2626,stroke-width:2px,color:#450a0a;
    classDef medium fill:#ffedd5,stroke:#ea580c,stroke-width:2px,color:#431407;
    classDef low fill:#dbeafe,stroke:#2563eb,stroke-width:2px,color:#172554;
    classDef free fill:#dcfce7,stroke:#16a34a,stroke-width:2px,color:#052e16;
    classDef provider fill:#fae8ff,stroke:#c026d3,stroke-width:2px,color:#3b0764;
    classDef vision fill:#ede9fe,stroke:#7c3aed,stroke-width:2px,color:#2e1065;
```

### Operational Cost Breakdown

#### 1. LLM API Calls: Primary Variable Cost

Agents route across Groq, Gemini Flash, and OpenRouter with capability-based
fallback. A full analysis uses roughly six agent calls, with each call ranging
from a few hundred to a few thousand tokens depending on the depth of the
report and whether narrative synthesis is requested.

| Provider | Usage Scenario | Unit Cost | Notes |
|---|---|---:|---|
| <img src="https://cdn.simpleicons.org/groq/F55036" alt="Groq" width="16"> Groq, Llama models | Primary reasoning for most agents | ~$0.05-$0.10 input / ~$0.30-$0.50 output per 1M tokens | Extremely cheap; the workhorse for high-volume structured JSON calls |
| <img src="https://cdn.simpleicons.org/googlegemini/8E75B2" alt="Gemini" width="16"> Gemini Flash via OpenRouter or direct API | Final synthesis, narrative reasoning, fallback agent reasoning, counter-offer letter | Varies by model tier | Used when stronger synthesis or fallback reliability is needed |
| <img src="https://cdn.simpleicons.org/openrouter/111111" alt="OpenRouter" width="16"> OpenRouter | Provider routing and fallback | Depends on selected model | Lets the system route around provider outages or model-specific limits |

Estimated per-analysis LLM cost: **INR 2-INR 8 per full audit** for six agents
when most calls are routed through the cheapest provider first.

#### 2. Google Gemini Vision: Property Photo Inspection

Gemini Flash Image / Gemini Vision processes uploaded property photos for
visible defects and construction-quality signals.

| Item | Cost |
|---|---:|
| Per image | $0.039, approximately INR 3.3 |
| Per full analysis with 3-5 photos | Approximately INR 10-INR 17 |

Buyers can upload up to five photos. This cost is only incurred when the photo
inspection feature is actively used.

#### 3. Frontend Hosting: Firebase

The static frontend assets in `frontend/` are deployed through <img src="https://cdn.simpleicons.org/firebase/FFCA28" alt="Firebase" width="16"> Firebase Hosting.

| Firebase Plan | Included | Monthly Cost at MVP Scale |
|---|---|---:|
| Spark, free | 10 GB storage, 360 MB/day transfer | INR 0 |
| Blaze, pay as you go | Beyond free quota: ~$0.20/GiB transfer | INR 0-INR 500 if traffic spikes |

For the current MVP, the Spark free tier comfortably covers expected usage.

#### 4. Backend Hosting: Railway Containerized FastAPI

The backend can run as a <img src="https://cdn.simpleicons.org/docker/2496ED" alt="Docker" width="16"> Dockerized <img src="https://cdn.simpleicons.org/fastapi/009688" alt="FastAPI" width="16"> FastAPI service on <img src="https://cdn.simpleicons.org/railway/0B0D0E" alt="Railway" width="16"> Railway with autoscaling
support.

| Plan | Included | Estimated Monthly Cost |
|---|---|---:|
| Hobby | $5 free credit/month | INR 0-INR 400 if staying within credits |
| Pro, small app | $20/month minimum, suitable for 1 vCPU and 1-2 GB RAM | Approximately INR 1,700 |

A small-to-medium app on Railway typically runs $10-$30/month. For MVP traffic,
such as a few hundred analyses per month, the Hobby tier with credits is
sufficient.

#### 5. Domain: Optional .app TLD

The current deployed URL uses Firebase's free `*.web.app` subdomain:

```text
https://elegant-verbena-494508-a-e207e.web.app
```

A custom `.app` domain would add:

| Item | Annual Cost |
|---|---:|
| `.app` domain registration / renewal | $22-$35/year, approximately INR 1,850-INR 2,900 |
| Monthly equivalent | Approximately INR 150-INR 250 |

Firebase Hosting includes the free `*.web.app` subdomain, so a custom domain is
optional.

#### 6. WhatsApp Business API: Report Delivery

The <img src="https://cdn.simpleicons.org/whatsapp/25D366" alt="WhatsApp" width="16"> WhatsApp integration can deliver verdicts and key numbers directly to a
buyer.

| Message Type | Cost per Message in India |
|---|---:|
| Utility, report delivery | INR 0.11-INR 0.12 |
| First 1,000 service conversations/month | Free |

Estimated monthly cost: if 500 reports are delivered via WhatsApp per month at
the utility rate, the cost is roughly **INR 55-INR 60/month**.

#### 7. GST Verification API

The GST checker integration validates builder GSTIN numbers.

| Provider Example | Cost |
|---|---:|
| Apify GST Verifier | $5 / 1,000 results, approximately INR 420 / 1,000 |
| Per verification | Approximately INR 0.42 |

At a few hundred verifications per month, this remains negligible:
approximately **INR 20-INR 50/month**.

#### 8. MahaRERA Lookup

The RERA lookup integration scrapes the MahaRERA public portal. No paid API is
used. It fetches builder registration status, complaint count, and completion
data directly from Maharashtra RERA's publicly accessible website.

Cost: **INR 0**.

#### 9. RBI Repo Rate and Bank Rate Scraping

The bank-rate integration scrapes `rbi.org.in` for the current repo rate and
fetches top bank home loan rates.

Cost: **INR 0**.

#### 10. OCR and QR Code Scanning

`pytesseract` for OCR and `pyzbar` for QR code scanning run locally as Python
libraries. No external API is called.

Cost: **INR 0**.

### Consolidated Monthly Cost Estimate

| Line Item | MVP Traffic, ~500 analyses/month | Moderate Traffic, ~2,000 analyses/month |
|---|---:|---:|
| LLM API calls, all agents | INR 1,500-INR 4,000 | INR 6,000-INR 16,000 |
| Gemini Vision, photos | INR 500-INR 1,500 | INR 2,000-INR 6,000 |
| Firebase Hosting | INR 0, free tier | INR 0-INR 400 |
| Railway backend hosting | INR 0-INR 400, Hobby credits | INR 1,700-INR 2,500 |
| Domain, `.app` annualized | INR 200/month | INR 200/month |
| WhatsApp delivery | INR 55-INR 60 | INR 220-INR 240 |
| GST verification | INR 20-INR 50 | INR 80-INR 200 |
| MahaRERA scraping | INR 0 | INR 0 |
| RBI scraping | INR 0 | INR 0 |
| OCR / QR scanning | INR 0 | INR 0 |
| Total | **INR 2,300-INR 6,200** | **INR 10,200-INR 25,300** |

### Unit Economics

| Metric | MVP Stage |
|---|---:|
| Cost per full analysis, six-agent audit with photos | Approximately INR 8-INR 25 |
| Premium report price, future | INR 299-INR 999 |
| Break-even at INR 499/report | Approximately 30-50 premium conversions/month |

### Cost Summary

NIV AI can run entirely free or near-free at MVP scale. Firebase Hosting,
MahaRERA scraping, RBI scraping, OCR, and QR scanning all cost nothing for the
expected early usage pattern. Railway's Hobby plan provides enough credits for
light traffic, and LLM costs are minimized by routing the bulk of agent calls
through Groq first.

The primary scaling cost is LLM tokens. As usage grows, Groq remains the
cost-minimizing backbone. Gemini Flash is used when synthesis quality, fallback
reliability, or multimodal capability justifies the higher marginal cost. There
is no fixed per-user infrastructure fee; costs scale mainly with the number of
analyses and optional photo inspections.

```mermaid
%%{init: {"theme":"base","themeVariables":{"pie1":"#dcfce7","pie2":"#fee2e2","pie3":"#dbeafe","pie4":"#ffedd5","pie5":"#ede9fe","pie6":"#f1f5f9","pie7":"#fae8ff","fontFamily":"Inter, Arial"}}}%%
pie showData
    title MVP Monthly Cost Share, Representative Midpoint
    "LLM API calls" : 2750
    "Gemini Vision" : 1000
    "Firebase Hosting" : 0
    "Railway Backend" : 200
    "Domain" : 200
    "WhatsApp" : 60
    "GST Verification" : 35
```

---

## Roadmap

Future development areas:

- Multi-city expansion across Bengaluru, Hyderabad, Pune, and Delhi-NCR with local price medians, stamp duty rules, and RERA data so the adversarial audit is no longer Mumbai-only.
- WhatsApp-native analysis that runs the full three-step intake, agent audit, and verdict delivery inside a chat flow without needing a browser or app download.
- Ownership OS as a post-purchase companion with alerts for possession delays against RERA timelines, maintenance escalation, interest-rate resets, and resale conditions.
- Property Health Score, a 0-100 trust layer for real estate that synthesizes RERA compliance, builder track record, litigation history, construction signals, and micro-market pricing.
- Vernacular voice input for Hindi, Marathi, Tamil, and Telugu so the full intake flow works for buyers who prefer speaking over typing.
- Family co-buyer mode where multiple decision-makers contribute finances and risk tolerance and the verdict adapts to the combined household picture.
- Automated loan negotiation that generates bank-specific counter-offer scripts using live rate data and a buyer's credit and affordability profile.
- Pre-disbursal lender screening as a B2B API that lets housing finance companies run the adversarial stress-test engine before a loan is approved and disbursed.

---

## Disclaimer

NIV AI is an informational decision-support tool. It does not replace a
SEBI-registered financial advisor, lawyer, chartered accountant, bank loan
officer, or licensed property professional. Users should independently verify
all financial, legal, tax, and property assumptions before making a purchase.
