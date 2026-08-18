# BugPilot
### AI-Powered Engineering Bug Intelligence Agent

> **Core Architecture**: BugPilot runs on a clean, end-to-end decoupled pipeline:
> **React / Vite** $\longrightarrow$ **FastAPI Backend** $\longrightarrow$ **ReAct Orchestrator** $\longrightarrow$ **Specialist Agents** $\longrightarrow$ **MCP Client** $\longrightarrow$ **MCP Server** $\longrightarrow$ **10 Read-Only Tools** $\longrightarrow$ **SQLite Database (Synthetic Jira Data)**.

---

## 1. System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       React / Vite Frontend (TypeScript)                     │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ HTTP REST API (JWT + RBAC + Tenant Isolation)
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          FastAPI Backend (Port 8000)                         │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                       ReAct Orchestrator Agent                              │
│         Dynamic reasoning loop: Goal → LLM Decision → Tool Call →           │
│                    Observation → Next Decision → FINISH                     │
│               [Groq Primary API + Local Ollama Fallback]                    │
└───────────┬──────────────────────────┼──────────────────────────┬───────────┘
            │                          │                          │
            ▼                          ▼                          ▼
┌──────────────────────┐   ┌──────────────────────┐   ┌──────────────────────┐
│  Bug Analyst Agent   │   │ Trend Analyst Agent  │   │ Risk Analyst Agent   │
└───────────┬──────────┘   └──────────┬───────────┘   └──────────┬───────────┘
            │                          │                          │
            └──────────────────────────┼──────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                                 MCP Client                                  │
│                 Dynamic tool discovery, timeout & sandboxing                │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ stdio JSON-RPC Transport
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         MCP Server (mcp_server)                             │
│                  Exposes 10 Strict READ-ONLY Tools                          │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              AnalyticsService                               │
│              Deterministic metric calculation & statistical trends          │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                 DataProvider Interface (SQLDataProvider / SQLite)           │
│                 Multi-tenant tenant isolation (`organization_id`)           │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    SQLite Database (`sqlite:///./bugpilot.db`)              │
│       Realistic Jira-style Defect Catalog, Sprints, Users & Audit Trails    │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Strict Data Access Contract
```
✅ Agent → MCP Client → MCP Server → AnalyticsService → DataProvider → SQLite Data
❌ Agent → Direct Database Access (FORBIDDEN)
❌ Agent → Direct Data File Reading (FORBIDDEN)
❌ External Vector Database / RAG dependencies (FORBIDDEN)
```
Agents interact exclusively through dynamically discovered MCP tools, preserving sandboxing and full testability.

---

## 2. 10 MCP Tools Reference

All 10 tools are strictly **read-only**, tenant-scoped (`org_id`), and dynamically discovered via the MCP protocol:

| # | Tool Name | Required / Optional Parameters | Description & Evidence Returned |
|---|-----------|-------------------------------|---------------------------------|
| 1 | `search_bugs` | `query: str`, `limit: int = 20` | Search bugs by keyword in issue key, title, summary, or description. |
| 2 | `get_bug` | `bug_id: str` | Retrieve complete details for a single bug (severity, priority, root cause, business impact, environment, reproduction steps, fix version). |
| 3 | `get_bug_metrics` | `sprint_id: Optional[str]`, `component: Optional[str]`, `project: Optional[str]` | Aggregated bug counts, open vs. resolved distributions, and severity breakdowns. |
| 4 | `get_bug_trends` | `sprint_id: Optional[str]`, `component: Optional[str]`, `project: Optional[str]` | Monthly creation vs. resolution trends and historical sprint completion velocity. |
| 5 | `get_aging_bugs` | `min_age_days: float = 0.0`, `limit: int = 50` | Open defects sorted descending by age in days to highlight SLA risk. |
| 6 | `get_reopened_bugs` | `component: Optional[str]`, `limit: int = 50` | Defects that transitioned from Resolved/Closed back to Open/In Progress (`reopen_count > 0`). |
| 7 | `get_component_risk` | `component: Optional[str]`, `project: Optional[str]` | Component-level risk scores (0–100), active open issue counts, and blast radius indicators. |
| 8 | `get_release_risk` | `release: Optional[str]` | Fix version / release readiness assessment, overall risk score, and deployment verdict. |
| 9 | `get_bug_history` | `bug_id: str` | Chronological status transition history, reopen timestamps, and developer discussion comments. |
| 10 | `get_related_bugs` | `bug_id: str`, `limit: int = 10` | Related defects sharing component context, technical root cause, or explicit linked issue IDs. |

---

## 3. Dynamic ReAct Orchestration & Comparative Analysis

The Orchestrator Agent operates on a genuine **Reasoning + Action (ReAct)** loop:
1. **Intent & Out-of-Domain Guardrail**: Early checks filter non-engineering queries without wasting LLM/tool invocations.
2. **Dynamic Tool Selection**: LLM decides each action (`CALL_TOOL`, `DELEGATE`, or `FINISH`) based on the query, dynamically discovered tools, and accumulated observations.
3. **Iterative Multi-Candidate Inspection**:
   - For comparative and ranking queries (*"analyze authentication bugs and identify the highest-risk issue"*), `search_bugs` discovers candidates.
   - The Orchestrator iteratively invokes `get_bug` on **each candidate defect** before allowing `FINISH`, ensuring full technical evidence (root cause, blast radius, reproduction steps) is gathered.
4. **Differentiated Evidence-Grounded Risk Scoring**:
   - Evaluates severity, priority, status, production environment, security impact (e.g. SOC2/session hijacking), and technical root causes (e.g. race condition, crash).
   - Generates non-saturating scores (0.0–99.5) to avoid artificial 100/100 ties.
5. **Reflection Agent Quality Evaluation**:
   - Validates generated reports against ground-truth MCP data to prevent hallucinations and confirm accurate reporting.

---

## 4. Multi-Tenancy & RBAC Security

- **Tenant Isolation**: Every database record (`issues`, `sprints`, `users`, `audit_logs`) is strictly scoped by `organization_id` (e.g. `org-acme`). Cross-organization data access is blocked at the repository and MCP layers.
- **Role-Based Access Control (RBAC)**:
  - **Admin**: Full access, user management, and issue administration.
  - **Engineer / Developer**: Create, update, transition, and analyze issues.
  - **Viewer**: Read-only access to issues, analytics, and reports.
- **Secrets Management**: No secret keys or credentials are hardcoded. JWT secrets, API keys, and environment variables are strictly loaded from `.env` and excluded from version control.

---

## 5. Technology Stack

| Layer | Component | Technology |
|---|---|---|
| **Frontend** | Interactive UI | React 18 + TypeScript + Vite |
| **Backend API** | REST API Server | FastAPI + Uvicorn + Pydantic v2 |
| **Orchestration** | Agent Loop | ReAct Agent Framework + Specialist Delegation |
| **LLM Gateway** | Inference Engine | Groq API (`llama-3.3-70b-versatile`) Primary + Local Ollama (`llama3.1:8b`) Fallback |
| **Tool Protocol** | Tooling Layer | Official Python MCP SDK (`mcp>=1.0.0`) via `stdio` |
| **Data Layer** | Persistent Database | SQLAlchemy 2.0 ORM + SQLite (`sqlite:///./bugpilot.db`) |
| **Security** | Auth & RBAC | PyJWT (HS256) + Passlib (bcrypt) + Header-based Tenant Scoping |
| **Quality** | Reflection & Test | Reflection Agent Grounding + Pytest (320 tests, 100% pass) |

---

## 6. Setup & Execution Guide

### Prerequisites
- Python 3.12+
- Node.js 18+ (for frontend)

### 1. Backend Setup
```bash
# Clone and enter project
cd bugpilot

# Create and activate virtual environment
python -m venv .venv
# Windows: .\.venv\Scripts\activate | macOS/Linux: source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment (defaults to SQLite with zero setup)
cp .env.example .env
```

### 2. Run Standalone MCP Server
```powershell
# Windows
.\.venv\Scripts\python -m mcp_server.server

# macOS / Linux
.venv/bin/python -m mcp_server.server
```

### 3. Run FastAPI Backend
```bash
uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

### 4. Build & Run Frontend
```bash
cd frontend
npm install
npm run build
npm run dev
```

### 5. Execute Test Suite
```bash
# Run all unit and integration tests (320 tests)
pytest tests/unit tests/integration -q
```
