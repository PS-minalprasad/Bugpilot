"""
BugPilot — MCP Server Module (Phase 4)
=======================================
Real, independently runnable MCP server implementation using the official Python MCP SDK.
Exposes 10 READ-ONLY tools connecting to AnalyticsService and DataProvider.
"""

from typing import Any, Dict, Optional
from pydantic import Field

from mcp.server import MCPServer
from providers import get_data_provider
from analytics.service import AnalyticsService

def _val(val: Any, default: Any = None) -> Any:
    if hasattr(val, "default") and str(type(val)).find("FieldInfo") != -1:
        val = getattr(val, "default")
    if str(type(val)).find("FieldInfo") != -1:
        return default
    return val if val is not None else default


def _get_services(org_id: Optional[str] = None):
    org_str = _val(org_id, None)
    provider = get_data_provider(org_id=org_str)
    analytics = AnalyticsService(provider)
    return provider, analytics


# Create MCPServer instance
app = MCPServer(name="BugPilot-MCP-Server", version="1.0.0")


@app.tool(
    name="search_bugs",
    description="Search bugs by keyword in key, summary, or description (Read-Only)."
)
def search_bugs(
    query: str = Field(..., description="Text query to search bug key, summary, or description"),
    limit: int = Field(default=20, ge=1, le=500, description="Maximum number of bugs to return"),
    org_id: Optional[str] = Field(default=None, description="Organization tenant ID")
) -> Dict[str, Any]:
    """Search bugs matching query."""
    q_str = _val(query, "")
    lim_int = _val(limit, 20)
    provider, _ = _get_services(org_id)
    bugs = provider.search_bugs(query=q_str, limit=lim_int)
    fallback_ds = getattr(provider, "data_source", "SQLite")
    return {
        "count": len(bugs),
        "bugs": [b.model_dump(mode="json") for b in bugs],
        "data_source": bugs[0].data_source if bugs else fallback_ds,
    }


@app.tool(
    name="get_bug",
    description="Retrieve details for a single bug by its key/ID (Read-Only)."
)
def get_bug(
    bug_id: str = Field(..., description="Unique key or ID of the bug (e.g. PROJ-101)"),
    org_id: Optional[str] = Field(default=None, description="Organization tenant ID")
) -> Dict[str, Any]:
    """Get a single bug by ID."""
    b_id = _val(bug_id, "")
    provider, _ = _get_services(org_id)
    bug = provider.get_bug(bug_id=b_id)
    if not bug:
        return {
            "found": False,
            "error": f"Bug with key '{b_id}' not found.",
            "data_source": "Synthetic Demo Data"
        }
    return {
        "found": True,
        "bug": bug.model_dump(mode="json"),
        "data_source": bug.data_source
    }


@app.tool(
    name="get_bug_metrics",
    description="Get aggregated bug summary and breakdown metrics (Read-Only)."
)
def get_bug_metrics(
    sprint_id: Optional[str] = Field(default=None, description="Optional sprint ID filter"),
    component: Optional[str] = Field(default=None, description="Optional component name filter"),
    project: Optional[str] = Field(default=None, description="Optional project key filter"),
    org_id: Optional[str] = Field(default=None, description="Organization tenant ID")
) -> Dict[str, Any]:
    """Get summary metrics and breakdown distributions."""
    sp_id = _val(sprint_id, None)
    comp = _val(component, None)
    proj = _val(project, None)
    provider, analytics = _get_services(org_id)
    analytics_result = analytics.analyze(
        sprint_id=sp_id,
        component=comp,
        project=proj
    )
    return {
        "summary": analytics_result.summary.model_dump(mode="json"),
        "breakdowns": analytics_result.breakdowns.model_dump(mode="json"),
        "data_source": analytics_result.summary.data_source
    }


@app.tool(
    name="get_bug_trends",
    description="Get bug creation, resolution, and sprint velocity trends over time (Read-Only)."
)
def get_bug_trends(
    sprint_id: Optional[str] = Field(default=None, description="Optional sprint ID filter"),
    component: Optional[str] = Field(default=None, description="Optional component name filter"),
    project: Optional[str] = Field(default=None, description="Optional project key filter"),
    org_id: Optional[str] = Field(default=None, description="Organization tenant ID")
) -> Dict[str, Any]:
    """Get monthly and sprint trend data."""
    sp_id = _val(sprint_id, None)
    comp = _val(component, None)
    proj = _val(project, None)
    provider, analytics = _get_services(org_id)
    analytics_result = analytics.analyze(
        sprint_id=sp_id,
        component=comp,
        project=proj
    )
    return {
        "creation_resolution_trends": [
            t.model_dump(mode="json") for t in analytics_result.creation_resolution_trends
        ],
        "sprint_trends": [
            t.model_dump(mode="json") for t in analytics_result.sprint_trends
        ],
        "data_source": analytics_result.summary.data_source
    }


@app.tool(
    name="get_aging_bugs",
    description="Get open bugs sorted descending by age in days (Read-Only)."
)
def get_aging_bugs(
    min_age_days: float = Field(default=0.0, ge=0.0, description="Minimum age in days for open bugs"),
    project: Optional[str] = Field(default=None, description="Optional project key filter"),
    component: Optional[str] = Field(default=None, description="Optional component name filter"),
    limit: int = Field(default=50, ge=1, le=500, description="Maximum number of aging bugs to return"),
    org_id: Optional[str] = Field(default=None, description="Organization tenant ID")
) -> Dict[str, Any]:
    """Get aging open bugs filtered by minimum age."""
    min_age = _val(min_age_days, 0.0)
    lim_val = _val(limit, 50)
    proj_val = _val(project, None)
    comp_val = _val(component, None)

    provider, analytics = _get_services(org_id)
    analytics_result = analytics.analyze(project=proj_val, component=comp_val)
    filtered = [
        b for b in analytics_result.aging_bugs if b.age_days >= min_age
    ][:lim_val]

    return {
        "count": len(filtered),
        "aging_bugs": [b.model_dump(mode="json") for b in filtered],
        "data_source": analytics_result.summary.data_source
    }


@app.tool(
    name="get_reopened_bugs",
    description="Get bugs that have been reopened one or more times (Read-Only)."
)
def get_reopened_bugs(
    component: Optional[str] = Field(default=None, description="Optional component name filter"),
    project: Optional[str] = Field(default=None, description="Optional project key filter"),
    limit: int = Field(default=50, ge=1, le=500, description="Maximum number of reopened bugs to return"),
    org_id: Optional[str] = Field(default=None, description="Organization tenant ID")
) -> Dict[str, Any]:
    """Get reopened bugs."""
    comp_val = _val(component, None)
    proj_val = _val(project, None)
    lim_val = _val(limit, 50)
    provider, _ = _get_services(org_id)
    all_bugs = provider.get_bugs(limit=5000, component=comp_val, project=proj_val)
    reopened = [b for b in all_bugs if b.reopened_count > 0][:lim_val]
    return {
        "count": len(reopened),
        "reopened_bugs": [b.model_dump(mode="json") for b in reopened],
        "data_source": all_bugs[0].data_source if all_bugs else "Synthetic Demo Data"
    }


@app.tool(
    name="get_component_risk",
    description="Get deterministic risk assessment score and metrics for components (Read-Only)."
)
def get_component_risk(
    component: Optional[str] = Field(default=None, description="Optional component name filter"),
    project: Optional[str] = Field(default=None, description="Optional project key filter"),
    org_id: Optional[str] = Field(default=None, description="Organization tenant ID")
) -> Dict[str, Any]:
    """Get component risk metrics."""
    comp_val = _val(component, None)
    proj_val = _val(project, None)
    provider, analytics = _get_services(org_id)
    analytics_result = analytics.analyze(component=comp_val, project=proj_val)
    comp_risks = analytics_result.component_risks
    if comp_val:
        comp_risks = [c for c in comp_risks if c.name.lower() == comp_val.lower()]

    return {
        "count": len(comp_risks),
        "component_risks": [c.model_dump(mode="json") for c in comp_risks],
        "data_source": analytics_result.summary.data_source
    }


@app.tool(
    name="get_release_risk",
    description="Get deterministic risk assessment score and metrics for releases (Read-Only)."
)
def get_release_risk(
    release: Optional[str] = Field(default=None, description="Optional release/fix_version filter"),
    org_id: Optional[str] = Field(default=None, description="Organization tenant ID")
) -> Dict[str, Any]:
    """Get release risk metrics."""
    rel_val = _val(release, None)
    provider, analytics = _get_services(org_id)
    analytics_result = analytics.analyze()
    rel_risks = analytics_result.release_risks
    if rel_val:
        rel_risks = [r for r in rel_risks if r.name.lower() == rel_val.lower()]

    return {
        "count": len(rel_risks),
        "release_risks": [r.model_dump(mode="json") for r in rel_risks],
        "data_source": analytics_result.summary.data_source
    }


@app.tool(
    name="get_bug_history",
    description="Retrieve chronological status transitions, reopen history, and discussion comments for a bug (Read-Only)."
)
def get_bug_history(
    bug_id: str = Field(..., description="Unique key or ID of the bug (e.g. BP-101)"),
    org_id: Optional[str] = Field(default=None, description="Organization tenant ID")
) -> Dict[str, Any]:
    """Get chronological history and comments for a bug."""
    b_id = _val(bug_id, "")
    provider, _ = _get_services(org_id)
    history = provider.get_bug_history(bug_id=b_id)
    if not history:
        return {
            "found": False,
            "error": f"Bug history for key '{b_id}' not found.",
            "data_source": getattr(provider, "data_source", "Synthetic Demo Data")
        }
    return {
        "found": True,
        "history": history,
        "data_source": history.get("data_source", getattr(provider, "data_source", "Synthetic Demo Data"))
    }


@app.tool(
    name="get_related_bugs",
    description="Retrieve related bugs sharing component, linked issue IDs, or project context for root-cause and impact analysis (Read-Only)."
)
def get_related_bugs(
    bug_id: str = Field(..., description="Unique key or ID of the bug (e.g. BP-101)"),
    limit: int = Field(default=10, ge=1, le=100, description="Maximum number of related bugs to return"),
    org_id: Optional[str] = Field(default=None, description="Organization tenant ID")
) -> Dict[str, Any]:
    """Get related bugs."""
    b_id = _val(bug_id, "")
    lim_val = _val(limit, 10)
    provider, _ = _get_services(org_id)
    related_bugs = provider.get_related_bugs(bug_id=b_id, limit=lim_val)
    fallback_ds = getattr(provider, "data_source", "Synthetic Demo Data")
    return {
        "count": len(related_bugs),
        "related_bugs": [b.model_dump(mode="json") for b in related_bugs],
        "data_source": related_bugs[0].data_source if related_bugs else fallback_ds
    }



def main():
    """Run the MCP server using stdio transport."""
    app.run(transport="stdio")


if __name__ == "__main__":
    main()
