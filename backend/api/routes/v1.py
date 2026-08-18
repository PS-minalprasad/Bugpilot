"""
BugPilot — FastAPI API v1 Router & Endpoints (Phase 9)
======================================================
Implements:
- GET  /api/v1/health
- GET  /api/v1/agents
- GET  /api/v1/tools
- POST /api/v1/chat
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from backend.config import settings
from backend.core.exceptions import ValidationError
from mcp_client import MCPClient
from agents import OrchestratorAgent, ReportAgent, ReflectionAgent

from backend.security.auth import User
from backend.security.dependencies import enforce_tenant_isolation
from backend.api.routes.auth import auth_router
from backend.api.routes.issues import issues_router

router = APIRouter(prefix="/v1", tags=["v1"])
router.include_router(auth_router)
router.include_router(issues_router)


# Pydantic Schemas
class HealthV1Response(BaseModel):
    status: str = "ok"
    app: str = settings.APP_NAME
    version: str = settings.APP_VERSION
    env: str = settings.ENV
    data_source: str = settings.DATA_LABEL


class AgentInfo(BaseModel):
    name: str
    description: str
    role: str


class AgentsV1Response(BaseModel):
    count: int
    agents: List[AgentInfo]
    data_source: str = settings.DATA_LABEL


class ToolInfo(BaseModel):
    name: str
    description: str
    input_schema: Dict[str, Any]


class ToolsV1Response(BaseModel):
    count: int
    tools: List[ToolInfo]
    data_source: str = settings.DATA_LABEL


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000, description="Chat message or engineering analysis prompt")


class ChatResponse(BaseModel):
    execution_id: str
    request_id: str
    answer: str
    intent: Optional[str] = None
    agents_used: List[str]
    tools_used: List[str]
    execution_steps: List[Dict[str, Any]] = Field(default_factory=list)
    metrics: Dict[str, Any]
    reflection: Dict[str, Any]
    data_source: str = settings.DATA_LABEL
    elapsed_seconds: float


@router.get("/health", response_model=HealthV1Response, summary="GET /api/v1/health")
async def get_health_v1() -> HealthV1Response:
    """Returns v1 health status."""
    return HealthV1Response(
        status="ok",
        app=settings.APP_NAME,
        version=settings.APP_VERSION,
        env=settings.ENV,
        data_source=settings.DATA_LABEL,
    )





@router.get("/agents", response_model=AgentsV1Response, summary="GET /api/v1/agents")
async def get_agents_v1() -> AgentsV1Response:
    """Discovers available specialist and coordinator agents."""
    agents = [
        AgentInfo(
            name="Orchestrator Agent",
            description="Coordinates specialist agents & MCP tools in an iterative reasoning loop",
            role="Coordinator",
        ),
        AgentInfo(
            name="Bug Analyst",
            description="Analyzes bug counts, severity, priority, status, unresolved and reopened metrics",
            role="Specialist Analyst",
        ),
        AgentInfo(
            name="Trend Analyst",
            description="Analyzes historical creation vs resolution trends and sprint velocity",
            role="Specialist Analyst",
        ),
        AgentInfo(
            name="Risk Analyst",
            description="Evaluates component risk scores, release risk profiles, and aging bugs",
            role="Specialist Analyst",
        ),
        AgentInfo(
            name="Report Agent",
            description="Synthesizes structured engineering reports from ground-truth evidence",
            role="Reporting Specialist",
        ),
        AgentInfo(
            name="Reflection Agent",
            description="Validates answers and metrics against ground-truth evidence",
            role="Validation Specialist",
        ),
    ]
    return AgentsV1Response(
        count=len(agents),
        agents=agents,
        data_source=settings.DATA_LABEL,
    )


@router.get("/tools", response_model=ToolsV1Response, summary="GET /api/v1/tools")
async def get_tools_v1() -> ToolsV1Response:
    """Discovers exposed read-only tools dynamically via MCPClient."""
    async with MCPClient() as client:
        discovered = client.discovered_tools
        tool_list = [
            ToolInfo(
                name=t.name,
                description=t.description,
                input_schema=t.input_schema,
            )
            for t in discovered.values()
        ]
        return ToolsV1Response(
            count=len(tool_list),
            tools=tool_list,
            data_source=settings.DATA_LABEL,
        )


@router.get("/metrics", summary="GET /api/v1/metrics")
async def get_metrics_v1(
    project: Optional[str] = None,
    component: Optional[str] = None,
    current_user: User = Depends(enforce_tenant_isolation),
):
    tool_args: Dict[str, Any] = {"org_id": current_user.org_id}
    if project:
        tool_args["project"] = project
    if component:
        tool_args["component"] = component

    async with MCPClient() as client:
        metrics_res = await client.call_tool("get_bug_metrics", tool_args)
        trends_res = await client.call_tool("get_bug_trends", tool_args)
        risk_res = await client.call_tool("get_component_risk", tool_args)
        aging_res = await client.call_tool("get_aging_bugs", tool_args)
        
        data_source = metrics_res.get("data_source") or settings.DATA_LABEL

        return {
            "summary": metrics_res.get("summary", {}),
            "trends": trends_res.get("creation_resolution_trends", []),
            "component_risks": risk_res.get("component_risks", []),
            "aging_bugs_count": aging_res.get("count", 0),
            "data_source": data_source,
            "org_id": current_user.org_id,
        }


@router.post("/chat", response_model=ChatResponse, summary="POST /api/v1/chat")
async def post_chat_v1(
    chat_req: ChatRequest,
    current_user: User = Depends(enforce_tenant_isolation),
    x_request_id: Optional[str] = Header(default=None),
) -> ChatResponse:
    """Connects user message to the real Orchestrator agent workflow with tenant isolation."""
    if not chat_req.message or not chat_req.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    request_id = str(x_request_id) if (x_request_id and isinstance(x_request_id, str)) else f"req-{uuid.uuid4().hex[:8]}"
    start_time = time.time()

    async with MCPClient() as client:
        orchestrator = OrchestratorAgent(mcp_client=client)
        try:
            orc_res = await orchestrator.run(chat_req.message, org_id=current_user.org_id)
        except Exception as err:
            raise HTTPException(status_code=500, detail=f"Orchestration failed: {str(err)}")

        if orc_res.intent == "OUT_OF_DOMAIN":
            return ChatResponse(
                execution_id=orc_res.execution_id,
                request_id=request_id,
                answer=orc_res.final_answer,
                intent="OUT_OF_DOMAIN",
                agents_used=[],
                tools_used=[],
                metrics={},
                reflection={"verdict": "CONFIRM", "quality_score": 1.0, "gaps": [], "corrections": []},
                data_source=settings.DATA_LABEL,
                elapsed_seconds=round(time.time() - start_time, 3),
            )

        agents_used = list({step.agent_name for step in orc_res.execution_steps})
        tools_used = list({step.tool_name for step in orc_res.execution_steps})

        # Fetch metrics evidence if get_bug_metrics was executed
        metrics_data = {}
        if "get_bug_metrics" in tools_used:
            try:
                metrics_res = await client.call_tool("get_bug_metrics", {"org_id": current_user.org_id})
                metrics_data = metrics_res.get("summary", {})
            except Exception:
                pass

        # Perform Reflection Agent validation
        reflection_agent = ReflectionAgent()
        eval_res, ref_model = reflection_agent.reflect(orc_res.final_answer, {"intent": orc_res.intent, "summary": metrics_data})

        reflection_info = {
            "verdict": eval_res.verdict,
            "quality_score": eval_res.quality_score,
            "gaps": eval_res.gaps,
            "corrections": eval_res.corrections,
        }

        answer = eval_res.corrected_answer if eval_res.verdict == "CORRECT" and eval_res.corrected_answer else orc_res.final_answer
        elapsed = time.time() - start_time

        return ChatResponse(
            execution_id=orc_res.execution_id,
            request_id=request_id,
            answer=answer,
            intent=orc_res.intent,
            agents_used=agents_used,
            tools_used=tools_used,
            execution_steps=[s.model_dump() for s in orc_res.execution_steps],
            metrics=metrics_data,
            reflection=reflection_info,
            data_source=settings.DATA_LABEL,
            elapsed_seconds=round(elapsed, 3),
        )
