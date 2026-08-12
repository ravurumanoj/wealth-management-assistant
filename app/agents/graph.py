"""LangGraph workflow for the Wealth Management RM Assistant.

Node flow
---------
router ──► greeting path ──► END          (regex fast-path, no LLM)
       ──► general       ──► synthesizer ──► END
       ──► portfolio_only/crm_only/both ──► agent_executor ──► synthesizer
                                                synthesizer ──► END            (sufficient)
                                                synthesizer ──► clarification_request ──► END  (not sufficient, retry < MAX)
                                                synthesizer ──► END            (retry >= MAX, partial answer)
"""
from __future__ import annotations

import asyncio

from langgraph.graph import StateGraph, END

from app.agents.state import AgentState
from app.agents.router import router_agent
from app.agents.portfolio_insights import portfolio_insights_agent
from app.agents.relationship_intelligence import relationship_intelligence_agent
from app.agents.synthesizer import synthesizer_agent
from app.constants import MAX_RETRIES
from app.utils.logger import logger

# ── Standalone node functions ─────────────────────────────────────────────────

async def agent_executor_node(state: AgentState) -> dict:
    """Run portfolio and/or CRM agents based on route; parallel for 'both'."""
    route = state.get("route", "")
    logger.info(f"agent_executor_node: route={route}")

    if route == "portfolio_only":
        data = await portfolio_insights_agent.collect_data(state)
        return {"portfolio_output": data}

    if route == "crm_only":
        data = await relationship_intelligence_agent.collect_data(state)
        return {"crm_output": data}

    # "both" — run in parallel
    portfolio_task = portfolio_insights_agent.collect_data(state)
    crm_task = relationship_intelligence_agent.collect_data(state)
    portfolio_data, crm_data = await asyncio.gather(portfolio_task, crm_task)
    return {"portfolio_output": portfolio_data, "crm_output": crm_data}


async def clarification_request_node(state: AgentState) -> dict:
    """Increment retry_count; final_output already set by synthesizer."""
    return {"retry_count": (state.get("retry_count") or 0) + 1}


# ── Routing helpers ───────────────────────────────────────────────────────────

def _route_from_router(state: AgentState) -> str:
    """Map state['route'] to the next graph node after router."""
    route = state.get("route", "general")
    if route == "general":
        return "synthesizer"
    return "agent_executor"   # portfolio_only | crm_only | both


def _route_from_synthesizer(state: AgentState) -> str:
    """Decide whether to end or ask for clarification."""
    if state.get("is_sufficient", True):
        return END
    retry_count = state.get("retry_count") or 0
    if retry_count < MAX_RETRIES:
        return "clarification_request"
    return END   # max retries reached — return partial answer


# ── Graph assembly ────────────────────────────────────────────────────────────

def create_graph() -> StateGraph:
    workflow = StateGraph(AgentState)

    workflow.add_node("router",                router_agent.classify_and_route)
    workflow.add_node("agent_executor",        agent_executor_node)
    workflow.add_node("synthesizer",           synthesizer_agent.run)
    workflow.add_node("clarification_request", clarification_request_node)

    workflow.set_entry_point("router")

    workflow.add_conditional_edges("router", _route_from_router, {
        "synthesizer":    "synthesizer",
        "agent_executor": "agent_executor",
    })

    workflow.add_edge("agent_executor", "synthesizer")

    workflow.add_conditional_edges("synthesizer", _route_from_synthesizer, {
        END:                     END,
        "clarification_request": "clarification_request",
    })

    workflow.add_edge("clarification_request", END)

    return workflow.compile()


app_graph = create_graph()


