# 🐞 BugPilot

### AI-Powered Engineering Bug Intelligence Agent

BugPilot is a **production-oriented, multi-agent AI system** that analyzes engineering bug data through an **agentic ReAct workflow** and a **Model Context Protocol (MCP) tool layer**.

Instead of allowing agents to access the database directly, BugPilot enforces a strict architecture:

**React / Vite → FastAPI → ReAct Orchestrator → Specialist Agents → MCP Client → MCP Server → Analytics → Data Provider → SQLite**

The current system uses **synthetic Jira-compatible data persisted in SQLite**. The data layer is abstracted behind a provider interface so that the agent and MCP layers remain decoupled from the underlying data source.

---

## 🎯 Project Objective

Engineering teams often have large numbers of bugs distributed across projects, components, sprints, releases, and environments.

Finding meaningful answers such as:

- Which bugs are highest risk?
- Which components are becoming unstable?
- Which defects have been reopened?
- Which bugs are aging beyond acceptable limits?
- Is a release ready from a defect-risk perspective?
- Which issues are related to a particular bug?
- What are the historical trends?

usually requires manually querying and correlating multiple sources of information.

**BugPilot automates this analysis using AI agents and deterministic analytics exposed through MCP tools.**

---

# 🏗️ System Architecture

```text
┌─────────────────────────────────────────────────────────────────────┐
│                    React + Vite Frontend                            │
│                       TypeScript UI                                 │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                │ HTTP REST API
                                │ JWT + RBAC + Tenant Isolation
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     FastAPI Backend                                 │
│                         Port 8000                                   │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    ReAct Orchestrator                               │
│                                                                     │
│       Goal → LLM Decision → Tool/Agent Call → Observation           │
│                         ↑                    │                       │
│                         └──── Next Decision ┘                       │
│                                                                     │
│              Groq Primary + Ollama Fallback                        │
└───────────────┬────────────────────┬────────────────┬───────────────┘
                │                    │                │
                ▼                    ▼                ▼
        ┌──────────────┐    ┌──────────────┐  ┌──────────────┐
        │ Bug Analyst  │    │ Trend Analyst│  │ Risk Analyst │
        │    Agent     │    │    Agent     │  │    Agent     │
        └──────┬───────┘    └──────┬───────┘  └──────┬───────┘
               │                   │                 │
               └───────────────────┼─────────────────┘
                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         MCP Client                                  │
│                                                                     │
│              Dynamic Tool Discovery                                 │
│              Tool Validation                                        │
│              Timeout / Execution Controls                           │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                │ MCP / JSON-RPC over stdio
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         MCP Server                                  │
│                                                                     │
│                   10 Read-Only Tools                                │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      AnalyticsService                               │
│                                                                     │
│        Deterministic Metrics + Trend + Risk Calculations            │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       DataProvider                                  │
│                                                                     │
│              SQLDataProvider / Provider Contract                    │
│                     organization_id scoping                         │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         SQLite                                     │
│                                                                     │
│              Synthetic Jira-Compatible Bug Data                    │
│              Issues • Sprints • Releases • Users                    │
│              History • Comments • Audit Information                 │
└─────────────────────────────────────────────────────────────────────┘
```

---

# 🔐 Strict Data Access Architecture

One of the core design principles of BugPilot is **separation between reasoning and data access**.

### Allowed

```text
Agent
  ↓
MCP Client
  ↓
MCP Server
  ↓
AnalyticsService
  ↓
DataProvider
  ↓
SQLite
```

### Forbidden

```text
Agent ────────────────→ Database ❌

Agent ────────────────→ SQLite file ❌

Agent ────────────────→ Data files ❌
```

Agents do not receive direct database access.

Instead, they interact with structured MCP tools. This provides:

- Controlled data access
- Tool-level validation
- Centralized authorization boundaries
- Easier testing
- Easier provider replacement
- Separation of AI reasoning from deterministic data operations

---

# 🤖 Agentic Architecture

BugPilot is designed around a **ReAct-style agent loop**.

ReAct means **Reasoning + Acting**.

The orchestrator repeatedly decides what action should happen next based on the user goal and previous observations.

```text
User Query
    ↓
Understand Goal
    ↓
Check Guardrails
    ↓
Inspect Available Tools
    ↓
LLM Decision
    ↓
CALL_TOOL / DELEGATE / FINISH
    ↓
Execute Action
    ↓
Receive Observation
    ↓
Evaluate Observation
    ↓
Next Decision
    ↓
FINISH
```

The system does not simply execute one hardcoded tool for every query.

The orchestrator determines which available tool or specialist agent is appropriate based on the task.

---

# 🧠 ReAct Decision Types

The orchestrator can make three major types of decisions.

## `CALL_TOOL`

Used when an MCP tool can directly provide the required evidence.

Example:

```text
User:
"Show me the oldest open authentication bugs."

Possible execution:

search_bugs
      ↓
get_aging_bugs
      ↓
FINISH
```

## `DELEGATE`

Used when a specialist agent is better suited to the requested analysis.

Available specialists include:

- Bug Analyst
- Trend Analyst
- Risk Analyst

## `FINISH`

Used when sufficient evidence has been collected and the final response can be generated.

---

# 👥 Specialist Agents

BugPilot separates specialized analytical responsibilities.

## Bug Analyst

Focuses on individual defects and their technical details.

Typical analysis:

- Severity
- Priority
- Status
- Root cause
- Reproduction information
- Environment
- Business impact
- Related defects

---

## Trend Analyst

Focuses on historical patterns.

Typical analysis:

- Bug creation trends
- Resolution trends
- Sprint trends
- Component patterns
- Release trends
- Reopen patterns

---

## Risk Analyst

Focuses on engineering risk.

Typical analysis:

- Severity
- Priority
- Production impact
- Security impact
- Aging
- Reopen frequency
- Component blast radius
- Release risk

---

# 🔌 MCP Architecture

BugPilot uses the **Model Context Protocol (MCP)** as the controlled tool interface between agents and the data/analytics layer.

The MCP layer provides a standardized boundary:

```text
AI Agent
   ↓
MCP Client
   ↓
MCP Server
   ↓
MCP Tool
   ↓
AnalyticsService
   ↓
DataProvider
```

The client dynamically discovers the tools exposed by the MCP server instead of requiring the agent layer to directly access implementation-specific database functions.

---

# 🛠️ MCP Tools

BugPilot currently exposes **10 read-only analytical tools**.

| # | Tool | Parameters | Purpose |
|---|------|------------|---------|
| 1 | `search_bugs` | `query`, `limit` | Search defects using keywords |
| 2 | `get_bug` | `bug_id` | Retrieve complete details for a specific bug |
| 3 | `get_bug_metrics` | `sprint_id`, `component`, `project` | Calculate bug counts and severity/status distributions |
| 4 | `get_bug_trends` | `sprint_id`, `component`, `project` | Analyze creation, resolution, and sprint trends |
| 5 | `get_aging_bugs` | `min_age_days`, `limit` | Identify old unresolved defects |
| 6 | `get_reopened_bugs` | `component`, `limit` | Identify defects that were reopened |
| 7 | `get_component_risk` | `component`, `project` | Calculate component-level risk |
| 8 | `get_release_risk` | `release` | Evaluate release readiness from defect risk |
| 9 | `get_bug_history` | `bug_id` | Retrieve status history and discussion information |
| 10 | `get_related_bugs` | `bug_id`, `limit` | Find related defects |

All MCP tools are designed to be:

- Read-only
- Tenant-scoped
- Schema validated
- Dynamically discoverable
- Separated from direct database access

---

# 📊 Deterministic Analytics

A key architectural decision in BugPilot is that **deterministic calculations are not delegated entirely to the LLM**.

Examples include:

```text
Bug Count
Severity Distribution
Aging
Reopen Count
Trend Calculation
Risk Metrics
Release Risk
```

These calculations are handled by application code.

The LLM is responsible for:

```text
Understanding the user goal
        ↓
Selecting tools
        ↓
Interpreting observations
        ↓
Reasoning over evidence
        ↓
Generating the final explanation
```

The application layer is responsible for:

```text
Fetching data
        ↓
Filtering data
        ↓
Aggregating data
        ↓
Calculating deterministic metrics
```

This reduces the risk of the LLM inventing numerical results.

---

# 🔍 Evidence-Grounded Analysis

BugPilot follows an evidence-first approach.

For complex queries, the orchestrator can gather multiple pieces of evidence before producing its final answer.

Example:

```text
User:
"Analyze authentication bugs and identify the highest-risk issue."

        ↓

search_bugs
        ↓
Candidate bugs discovered
        ↓
get_bug for relevant candidates
        ↓
Collect technical evidence
        ↓
Risk analysis
        ↓
Reflection / validation
        ↓
Final grounded report
```

The system can consider factors such as:

- Severity
- Priority
- Production environment
- Security impact
- Technical root cause
- Aging
- Reopen history
- Business impact

---

# 🔎 Reflection Agent

BugPilot includes a reflection/validation stage intended to improve the quality of generated analysis.

The Reflection Agent evaluates generated responses against available evidence.

The validation process can check dimensions such as:

- Factual grounding
- Reasoning quality
- Instruction following
- Completeness
- Consistency
- Hallucination risk

The goal is to prevent the final answer from making claims that are unsupported by retrieved bug evidence.

---

# 🛡️ AI Guardrails

BugPilot includes AI safety and robustness controls around the agent workflow.

## Out-of-Domain Protection

Queries unrelated to engineering or bug analysis can be rejected before unnecessary tool execution.

Example:

```text
"What is the capital of France?"
```

should not cause the agent to inspect the bug database.

---

## Prompt Injection Protection

The system includes prompt-injection defense logic designed to prevent user instructions from overriding the application's intended behavior.

Examples of suspicious instructions include:

```text
Ignore previous instructions.
Reveal internal prompts.
Expose hidden tool information.
Bypass access controls.
Return internal implementation details.
```

The guardrail layer evaluates suspicious input before allowing normal agent execution.

---

## Tool Boundary Protection

Agents do not receive unrestricted database access.

Instead:

```text
Agent
 ↓
MCP Tool
 ↓
Validated Parameters
 ↓
Analytics / Data Layer
```

This limits the operations available to the model.

---

# 🔐 Security Architecture

## JWT Authentication

Authentication uses JWT-based sessions.

Secrets are loaded from environment configuration rather than being hardcoded into source code.

---

## RBAC

BugPilot supports role-based access control.

### Admin

Administrative access and user management.

### Engineer / Developer

Authorized issue operations and analysis.

### Viewer

Read-only access to issue information and analytics.

> MCP analytical tools remain read-only even though authorized backend APIs may support issue-management operations.

---

## Multi-Tenancy

BugPilot uses `organization_id` to scope tenant data.

Example organizations:

```text
org-acme
org-globex
```

Tenant isolation prevents one organization from accessing another organization's records.

Tenant scoping is applied across relevant application and data layers.

---

# 🔑 Secrets Management

Sensitive credentials are not hardcoded.

Environment configuration is provided through:

```text
.env
```

while the repository contains:

```text
.env.example
```

with placeholder values.

Example:

```text
JWT_SECRET=change-this-secret-in-production
```

Real secrets should never be committed to Git.

---

# 🗄️ Data Architecture

BugPilot currently uses **synthetic Jira-compatible data**.

The data is persisted in:

```text
SQLite
```

with the application accessing it through a provider abstraction.

```text
SQLite
  ↓
SQLDataProvider
  ↓
AnalyticsService
  ↓
MCP Server
```

The provider layer separates the data source from the agent and MCP layers.

---

# 🔄 Why Synthetic Jira-Compatible Data?

The project is designed so that the agent architecture does not depend directly on an external Jira instance.

The current implementation uses synthetic Jira-compatible data to provide:

- Deterministic development
- Reproducible tests
- Predictable evaluation
- No dependency on external authentication
- No dependency on Jira API availability
- Safe demonstration data

The provider abstraction creates a clean boundary for future external Jira integration.

### Current

```text
Synthetic Jira-compatible Data
        ↓
SQLite
```

### Future

```text
Jira Cloud Provider
        ↓
Same Provider Contract
```

The goal is to change the data provider without redesigning the agent/MCP architecture.

---

# 🧩 Provider Abstraction

The provider layer separates the data source from the rest of the application.

Conceptually:

```text
             ┌────────────────────┐
             │   Provider Contract│
             └─────────┬──────────┘
                       │
              ┌────────┴─────────┐
              │                  │
              ▼                  ▼
       SQLDataProvider     Future Jira Provider
              │
              ▼
           SQLite
```

This makes the system easier to test, maintain, and extend.

---

# 🧪 Testing Strategy

BugPilot includes unit and integration tests covering important application behavior.

Testing areas include:

- Configuration
- Authentication
- RBAC
- Multi-tenancy
- MCP tools
- Agent behavior
- AI guardrails
- Prompt injection protection
- Evaluation framework
- Production observability
- API routes
- Data access
- Analytics

Run the test suite:

```bash
pytest tests/unit tests/integration -q
```

> The test count in project documentation should always reflect the latest actual test run.

---

# 📈 Agent Evaluation Framework

BugPilot includes an evaluation framework for measuring agent quality rather than relying only on whether the application starts successfully.

Run:

```bash
python -m evaluation.run_eval
```

The evaluation framework measures dimensions such as:

### 1. Task / Goal Success

Did the agent correctly fulfill the requested objective?

### 2. Tool Selection

Did the agent select appropriate MCP tools?

### 3. Tool Execution Success

Did selected tools execute successfully?

### 4. Tool Usage Efficiency

Did the agent avoid unnecessary tool calls?

### 5. Reasoning Quality

How well did the agent reason over the available evidence?

### 6. Groundedness

Are generated claims supported by retrieved data?

### 7. Hallucination Detection

Does the response contain unsupported claims?

### 8. Reliability

How does the system behave with missing or invalid data?

### 9. Latency

Measures:

- Mean
- P50
- P95
- P99
- Maximum latency

### 10. Instruction Following

Does the response follow required output structure and constraints?

### 11. Safety & Robustness

Measures behavior against:

- Prompt injection attempts
- Out-of-domain requests
- Invalid inputs
- Tool misuse scenarios

---

# ⚡ Scalability Testing

The evaluation framework includes concurrency testing.

Configured concurrency levels include:

```text
1
5
10
25
50
```

The purpose is to identify:

- Latency degradation
- Error rates
- Resource saturation
- Concurrency limitations
- Capacity bottlenecks

The evaluation output can highlight warning conditions when configured thresholds are exceeded.

---

# 💰 LLM Architecture

BugPilot uses an LLM Gateway abstraction.

```text
                 LLM Gateway
                     │
          ┌──────────┴──────────┐
          ▼                     ▼
     Groq Provider        Ollama Provider
       Primary               Fallback
          │                     │
    llama-3.3-70b          llama3.1:8b
```

This abstraction prevents the orchestration layer from being tightly coupled to a single LLM provider.

---

# 🌐 API Architecture

The backend is implemented using:

```text
FastAPI
```

Core API areas include:

- Health
- Authentication
- Agents
- MCP tools
- Chat
- Metrics
- Application operations

The frontend communicates with the backend through HTTP APIs.

The frontend does not directly access the database.

---

# 💻 Frontend

The frontend uses:

```text
React
TypeScript
Vite
```

The UI provides an engineering workspace for interacting with BugPilot's analysis capabilities.

All application data flows through the backend API.

---

# 🧱 Technology Stack

| Layer | Technology |
|---|---|
| Frontend | React 18 + TypeScript + Vite |
| Backend | FastAPI + Uvicorn |
| Validation | Pydantic v2 |
| Agent Architecture | ReAct-style Orchestrator |
| Specialist Agents | Bug / Trend / Risk Analysts |
| LLM Gateway | Groq + Ollama |
| Primary LLM | Llama 3.3 70B |
| Fallback LLM | Llama 3.1 8B |
| Tool Protocol | MCP Python SDK |
| Transport | stdio / JSON-RPC |
| ORM | SQLAlchemy 2.0 |
| Database | SQLite |
| Authentication | JWT |
| Password Hashing | bcrypt / Passlib |
| Authorization | RBAC |
| Testing | Pytest |
| Frontend Build | Vite |

---

# 🚀 Setup

## Prerequisites

Install:

- Python 3.12+
- Node.js 18+
- Git

---

## 1. Clone Repository

```bash
git clone https://github.com/PS-minalprasad/Bugpilot.git
cd Bugpilot
```

---

## 2. Create Python Environment

### Windows

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### macOS / Linux

```bash
python -m venv .venv
source .venv/bin/activate
```

---

## 3. Install Backend Dependencies

```bash
pip install -r requirements.txt
```

---

## 4. Configure Environment

### Windows

```powershell
Copy-Item .env.example .env
```

### macOS / Linux

```bash
cp .env.example .env
```

Update environment values as required.

**Never commit the real `.env` file.**

---

# ▶️ Running BugPilot

## Start MCP Server

### Windows

```powershell
.\.venv\Scripts\python -m mcp_server.server
```

### macOS / Linux

```bash
.venv/bin/python -m mcp_server.server
```

---

## Start FastAPI Backend

```bash
uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

Backend:

```text
http://127.0.0.1:8000
```

---

## Start Frontend

```bash
cd frontend
npm install
npm run dev
```

Build the frontend:

```bash
npm run build
```

---

# 🧪 Running Tests

Run all unit and integration tests:

```bash
pytest tests/unit tests/integration -q
```

Run AI guardrail tests:

```bash
pytest tests/unit/test_ai_guardrails.py -v
```

Run configuration tests:

```bash
pytest tests/unit/test_config.py -v
```

---

# 📊 Running Evaluation

Run the agent evaluation framework:

```bash
python -m evaluation.run_eval
```

The evaluation framework generates metrics for agent quality, reliability, latency, safety, and tool usage.

---

# 🔎 Example Queries

Once BugPilot is running, examples of supported engineering questions include:

```text
Tell me about the authentication bugs.
```

```text
Which bugs are currently the highest risk?
```

```text
Show me the oldest unresolved bugs.
```

```text
Which components have the highest risk?
```

```text
Which bugs have been reopened?
```

```text
Is the current release ready from a bug-risk perspective?
```

```text
Find bugs related to BP-157.
```

```text
Compare authentication bugs and identify the highest-risk issue.
```

---

# 🔄 Example Agent Execution

For a query such as:

```text
"Analyze authentication bugs and identify the highest-risk issue."
```

a possible execution flow is:

```text
User Query
    ↓
Intent / Safety Check
    ↓
ReAct Orchestrator
    ↓
Discover MCP Tools
    ↓
search_bugs
    ↓
Candidate Issues
    ↓
get_bug
    ↓
Detailed Evidence
    ↓
Risk Analysis
    ↓
Reflection / Validation
    ↓
Final Grounded Report
```

The exact trajectory depends on the task and the decisions made by the orchestrator.

---

# 📁 Project Structure

```text
bugpilot/
│
├── agents/
│   ├── orchestrator.py
│   ├── bug_analyst.py
│   ├── trend_analyst.py
│   ├── risk_analyst.py
│   └── reflection_agent.py
│
├── analytics/
│   └── ...
│
├── models/
│   └── ...
│
├── providers/
│   ├── data_provider.py
│   └── sql_data_provider.py
│
├── mcp_client/
│   └── ...
│
├── mcp_server/
│   ├── server.py
│   └── tools/
│
├── backend/
│   ├── api/
│   │   └── routes/
│   ├── core/
│   ├── llm/
│   │   └── providers/
│   ├── security/
│   ├── services/
│   ├── config.py
│   └── main.py
│
├── evaluation/
│   ├── evaluator.py
│   └── run_eval.py
│
├── tests/
│   ├── unit/
│   └── integration/
│
├── frontend/
│
├── generate_pdf.py
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

### Key Architectural Modules

| Module | Responsibility |
|---|---|
| `agents/` | ReAct orchestrator, specialist agents, and reflection agent |
| `analytics/` | Deterministic bug metrics, trends, and risk calculations |
| `models/` | Domain and response models such as `Bug`, `Report`, and `ReflectionResult` |
| `providers/` | Data-provider abstraction and SQL/SQLite implementation |
| `mcp_client/` | MCP client, dynamic tool discovery, and tool execution |
| `mcp_server/` | MCP server and read-only analytical tools |
| `backend/` | FastAPI API, authentication, security, LLM gateway, and application services |
| `evaluation/` | Agent evaluation, quality metrics, and scalability testing |
| `tests/` | Unit and integration test suites |
| `frontend/` | React + TypeScript + Vite user interface |



---

# 🎯 Design Principles

BugPilot follows several core engineering principles.

### 1. Separation of Concerns

AI reasoning, tool execution, analytics, and data access are separate layers.

### 2. No Direct Agent Database Access

Agents access data only through MCP tools.

### 3. Deterministic Analytics

Numerical calculations are handled by application code rather than relying entirely on LLM reasoning.

### 4. Provider Abstraction

The data source is separated from the agent and MCP layers.

### 5. Evidence-Grounded Generation

The final response should be based on retrieved system evidence.

### 6. Defense in Depth

Security is implemented through multiple layers:

```text
Authentication
      ↓
RBAC
      ↓
Tenant Isolation
      ↓
Tool Validation
      ↓
AI Guardrails
      ↓
MCP Boundary
```

### 7. Testability

Synthetic deterministic data and provider abstraction make the system reproducible and easier to test.

---

# ⚠️ Current Limitations

BugPilot currently uses **synthetic Jira-compatible data** rather than depending on a live Jira Cloud instance for its core demonstration workflow.

Therefore:

- Jira Cloud is not required to run the demonstration.
- Data is not automatically synchronized from a live Jira project.
- Real-time Jira webhook synchronization is not currently the primary data flow.
- The current architecture is designed to allow a future external Jira provider.

This limitation is intentional for reproducible development and evaluation.

---

# 🔮 Future Improvements

## Live Jira Integration

Connect the provider layer to Jira Cloud APIs.

```text
Jira Cloud
    ↓
Jira Provider
    ↓
Provider Contract
    ↓
AnalyticsService
    ↓
MCP Server
```

## Real-Time Synchronization

Add Jira webhooks/event processing for near-real-time updates.

## Background Processing

Introduce background workers for:

- Synchronization
- Large evaluations
- Report generation
- Scheduled analytics

## Production Observability

Expand monitoring with:

- OpenTelemetry
- Prometheus
- Grafana
- Distributed tracing
- Structured audit events

## Enterprise Authentication

Potential integrations:

- SSO
- OAuth
- Enterprise identity providers

---

# 🏆 What Makes BugPilot Different?

BugPilot is not simply an LLM chatbot connected to a database.

It combines:

```text
                    BugPilot
                       │
       ┌───────────────┼────────────────┐
       │               │                │
       ▼               ▼                ▼
   Multi-Agent       ReAct            MCP
   Architecture     Reasoning        Tool Layer
       │               │                │
       └───────────────┼────────────────┘
                       │
                       ▼
               Deterministic
                  Analytics
                       │
                       ▼
               Evidence-Grounded
                    Analysis
                       │
                       ▼
              Security + RBAC
                       │
                       ▼
                 Evaluation
```

The architecture is designed to keep **LLM reasoning, deterministic computation, tool execution, and data access separated**.

---

# 📌 Project Status

### Current Implementation

- ✅ React + Vite frontend
- ✅ FastAPI backend
- ✅ ReAct-style orchestration
- ✅ Specialist agents
- ✅ MCP client
- ✅ MCP server
- ✅ Dynamic MCP tool discovery
- ✅ 10 read-only analytical MCP tools
- ✅ SQLite persistence
- ✅ Synthetic Jira-compatible dataset
- ✅ Data provider abstraction
- ✅ JWT authentication
- ✅ RBAC
- ✅ Multi-tenancy
- ✅ AI guardrails
- ✅ Prompt-injection protection
- ✅ Reflection / validation
- ✅ Automated evaluation framework
- ✅ Unit and integration testing

### Data Source

**Synthetic Jira-compatible data**

### External Jira

Designed for future provider integration; not required for the current demonstration workflow.

---

