# BugPilot
### AI-Powered Engineering Bug Intelligence Agent

> **Data Architecture**: BugPilot runs on a persistent, multi-tenant **PostgreSQL / SQLite** database path by default (`PROVIDER_MODE=postgres`). All issue creation, status updates, sprint assignments, and status transitions dynamically flow through analytics, MCP tools, and agent workflows in real time. Synthetic demo data is also supported via `PROVIDER_MODE=synthetic`, and real Jira Cloud instances can be connected via Atlassian OAuth (`PROVIDER_MODE=jira_cloud`).

---

## Architecture

```
User / React Frontend (TypeScript + Vite)
 ↓ HTTP REST API (JWT + RBAC + Multi-Tenant Isolation)
FastAPI Backend (Port 8000)
 ↓
Orchestrator Agent
 ↓         ↓         ↓
Bug       Trend     Risk       Specialist Agents
Analyst   Analyst   Analyst
 ↓         ↓         ↓
         MCP Client
              ↓
         MCP Server (Read-Only Tools)
              ↓
         AnalyticsService
              ↓
         DataProvider Interface
              ↓
   ┌──────────┴──────────┐
   │                     │
PostgresProvider    SyntheticProvider
(Live DB default)   (Demo Mode)
   │
PostgreSQL / SQLite DB
(issues, sprints, users, orgs)
```

### Data Access Contract (STRICT)
```
✅ Agent → MCP Client → MCP Server → AnalyticsService → DataProvider → Data
❌ Agent → DataProvider (FORBIDDEN)
❌ Agent → Data files  (FORBIDDEN)
❌ Any RAG / embeddings / vector DB (FORBIDDEN)
```
Agents never import `providers/` or `backend/database` directly — verified via static analysis test suites.

---

## Data Providers & Live Dynamic Path

| Provider | Mode Flag | Data Label | Storage | Features |
|----------|-----------|------------|---------|----------|
| **`PostgresProvider` (Default)** | `postgres` | `PostgreSQL` / `SQLite` | Persistent SQLite/PostgreSQL | Fully dynamic live user CRUD, sprint tracking (`sprint_id`), status transition reopen tracking (`reopen_count`), and real-time agent/MCP intelligence. |
| **`SyntheticProvider`** | `synthetic` | `Synthetic Demo Data` | In-memory generated data | Instant demonstration mode with 1000 generated bugs across 14 sprints for offline testing. |
| **`JiraCloudProvider`** | `jira_cloud` | `Jira Cloud` | Atlassian Cloud | Live Jira issues via OAuth 2.0 (3LO) connection. |

### Live-Data Features
- **Sprint Management**: Live sprints stored in database (`SprintModel` / `sprints` table) per tenant (`organization_id`).
- **Sprint Linkage**: Issues link to sprints via `sprint_id`. MCP metric tools filter dynamically by `sprint_id`.
- **Reopen Tracking**: Automatic status transition detection (from `Resolved`/`Closed` to `Open`/`In Progress`) increments `reopen_count` on `IssueModel` and updates `reopened_count` in domain analytics.
- **Alembic Migrations**: Full schema evolution managed via `alembic/versions/`.

---

## Technology Stack

| Layer | Technology |
|-------|-----------|
| **API** | FastAPI + Uvicorn |
| **Database** | SQLAlchemy 2.0 ORM + Alembic migrations (SQLite by default, Postgres-compatible) |
| **Auth & Security** | PyJWT + Passlib(bcrypt) + RBAC (Admin, Manager, Developer, Viewer) + Tenant Isolation |
| **Validation** | Pydantic v2 + pydantic-settings |
| **LLM** | Google Gemini API — provides live, evidence-grounded AI analysis when `GEMINI_API_KEY` is configured, with seamless, automatic fallback to deterministic reporting templates when the key is unset or unavailable |
| **MCP** | Official MCP Python SDK (`mcp>=1.0.0`) |
| **Analytics** | Pure Python stdlib + Pydantic |
| **Reporting** | ReportLab (PDF export) |
| **Frontend** | React 18 + TypeScript + Vite |
| **Testing** | pytest + pytest-asyncio + httpx + pytest-cov |

---

## MCP Server & Tools

### Startup Command
Run the MCP Server standalone over `stdio` transport:

**Windows (PowerShell)**
```powershell
.\.venv\Scripts\python -m mcp_server.server
```
**macOS / Linux**
```bash
.venv/bin/python -m mcp_server.server
```

### Exposed READ-ONLY Tools

| Tool | Parameters | Description |
|------|------------|-------------|
| `search_bugs` | `query: str`, `limit: int = 20` | Search bugs by keyword in key, title, or description. |
| `get_bug` | `bug_id: str` | Retrieve details for a single bug by key or ID. |
| `get_bug_metrics` | `sprint_id: Optional[str]`, `component: Optional[str]` | Get summary & breakdown metrics. |
| `get_bug_trends` | `sprint_id: Optional[str]`, `component: Optional[str]` | Get creation/resolution and sprint trends. |
| `get_aging_bugs` | `min_age_days: float = 0.0`, `limit: int = 50` | Get open bugs sorted descending by age in days. |
| `get_reopened_bugs` | `component: Optional[str]`, `limit: int = 50` | Get bugs reopened one or more times. |
| `get_component_risk` | `component: Optional[str]` | Get component risk scores & metrics. |
| `get_release_risk` | `release: Optional[str]` | Get release risk scores & metrics. |

---

## REST API (`/api/v1`)

| Method | Path | Description |
|---|---|---|
| GET | `/api/health`, `/api/v1/health` | Liveness/readiness, includes active provider mode |
| GET | `/api/v1/agents` | List available agents |
| GET | `/api/v1/tools` | List available MCP tools |
| GET | `/api/v1/metrics` | Scoped bug metrics |
| POST | `/api/v1/chat` | Orchestrated agent chat |
| POST | `/api/v1/auth/login`, `/auth/register` | Credential auth |
| GET | `/api/v1/auth/me`, `/auth/roles` | Current user, available RBAC roles |
| GET/POST | `/api/v1/auth/atlassian/login`, `/callback`, `/status`, `/logout` | Atlassian OAuth 2.0 (3LO) flow |
| GET/POST/PUT/DELETE | `/api/v1/issues[/{issue_id}]` | Issue CRUD (Postgres/SQLite-backed) |
| GET/POST | `/api/v1/auth/jira/authorize`, `/callback` | Legacy Jira connect flow |

---

## Setup & Run

### Prerequisites
- Python 3.12+
- Node.js 18+ (for frontend)

### 1. Clone and enter the project
```bash
git clone <repo-url> bugpilot
cd bugpilot
```

### 2. Activate virtual environment and install backend dependencies

**Windows (PowerShell)**
```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```
**macOS / Linux**
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure environment
```bash
cp .env.example .env   # Windows: copy .env.example .env
```
Defaults work out of the box with local SQLite and the postgres provider. Set `GEMINI_API_KEY` to enable live LLM analysis calls.

### 4. Run Backend Test Suite (287 Tests)
```bash
pytest -q
```

### 5. Build and Run Frontend
```bash
cd frontend
npm install
npm run build
npm run dev
```

### 6. Run the API Server
```bash
uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```
