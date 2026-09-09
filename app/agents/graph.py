"""LangGraph workflow for the Wealth Management RM Assistant.

Node flow
---------
router ──► greeting        ──► direct_reply   ──► END
       ──► out_of_scope    ──► safe_decline   ──► END
       ──► general         ──► synthesizer    ──► END
       ──► portfolio/crm/both ──► clarification_gate
                                    ├─ needs clarification ──► END
                                    └─ proceed ──► agent_executor
                                                      ├─ sufficient / retries exhausted ──► synthesizer ──► END
                                                      └─ insufficient ──► replan ──► agent_executor (re-fetch)
"""
from __future__ import annotations

from langgraph.graph import StateGraph, END

from app.agents.state import AgentState
from app.agents.router import router_agent
from app.agents.clarification import clarification_agent
from app.agents.direct_response import direct_responder
from app.agents.execution import evaluate_sufficiency, execute_agents, targets_for_route
from app.agents.synthesizer import synthesizer_agent
from app.agents.checkpointer import build_checkpointer
from app.agents.base import extract_text
from app.prompts.replan import REPLAN_INSTRUCTION_TEMPLATE
from app.constants import (
    DEFAULT_CLIENT_ID,
    MAX_RETRIES,
    ROUTE_BOTH,
    ROUTE_CRM_ONLY,
    ROUTE_GENERAL,
    ROUTE_GREETING,
    ROUTE_OUT_OF_SCOPE,
    ROUTE_PORTFOLIO_ONLY,
)
from app.utils.logger import logger


# ── Node functions ────────────────────────────────────────────────────────────

async def direct_reply_node(state: AgentState) -> dict:
    """Greeting short-circuit — a short natural reply, no synthesizer."""
    messages = state.get("messages") or []
    user_msg = extract_text(messages[-1].content) if messages else ""
    reply = await direct_responder.reply_greeting(user_msg)
    return {"final_output": reply, "is_sufficient": True, "next_agent": "direct_reply"}


async def safe_decline_node(state: AgentState) -> dict:
    """Out-of-scope short-circuit — deterministic decline message."""
    return {
        "final_output": direct_responder.safe_decline(),
        "is_sufficient": True,
        "next_agent": "safe_decline",
    }


async def clarification_gate_node(state: AgentState) -> dict:
    """Pre-dispatch disambiguation gate (FR-COM-002)."""
    messages = state.get("messages") or []
    user_msg = extract_text(messages[-1].content) if messages else ""
    metadata = state.get("metadata", {}) or {}
    client_id = metadata.get("client_id") or DEFAULT_CLIENT_ID
    active_portfolio_ids = metadata.get("active_portfolio_ids") or []

    gate = await clarification_agent.assess(
        user_msg,
        client_id=client_id,
        active_portfolio_ids=active_portfolio_ids,
    )
    if gate.needs_clarification:
        return {
            "needs_clarification": True,
            "clarification_needed": gate.question,
            "final_output": gate.question,
        }
    return {"needs_clarification": False}


async def agent_executor_node(state: AgentState) -> dict:
    """Run the required sub-agents (parallel/sequential or targeted re-fetch),
    then evaluate sufficiency and prepare a replan instruction if needed."""
    route = state.get("route", "")
    replan_targets = set(state.get("replan_targets") or [])
    targets = replan_targets or targets_for_route(route)

    logger.info(f"agent_executor_node: route={route} targets={targets}")

    outputs = await execute_agents(
        state,
        route=route,
        execution_mode=state.get("execution_mode", ""),
        producer=state.get("producer", ""),
        targets=targets,
        replan_instruction=state.get("replan_instruction") or None,
    )

    portfolio_output = outputs.get("portfolio_output", state.get("portfolio_output") or {})
    crm_output = outputs.get("crm_output", state.get("crm_output") or {})

    is_sufficient, missing_desc, missing_targets = evaluate_sufficiency(
        route, portfolio_output, crm_output
    )

    result: dict = {
        "portfolio_output": portfolio_output,
        "crm_output": crm_output,
        "is_sufficient": is_sufficient,
    }
    if not is_sufficient:
        client_id = (state.get("metadata", {}) or {}).get("client_id") or DEFAULT_CLIENT_ID
        result["replan_instruction"] = REPLAN_INSTRUCTION_TEMPLATE.format(
            missing=missing_desc, client_id=client_id
        )
        result["replan_targets"] = list(missing_targets)
    return result


async def replan_node(state: AgentState) -> dict:
    """Increment the retry counter before re-dispatching the failing sub-agent(s)."""
    return {"retry_count": (state.get("retry_count") or 0) + 1}


# ── Routing helpers ───────────────────────────────────────────────────────────

def _route_from_router(state: AgentState) -> str:
    """Map the classified route to the next graph node."""
    route = state.get("route", ROUTE_GREETING)
    if route == ROUTE_GREETING:
        return "direct_reply"
    if route == ROUTE_OUT_OF_SCOPE:
        return "safe_decline"
    if route == ROUTE_GENERAL:
        return "synthesizer"
    return "clarification_gate"   # portfolio_only | crm_only | both


def _route_from_gate(state: AgentState) -> str:
    """Ask the RM to disambiguate, or proceed to retrieval."""
    if state.get("needs_clarification"):
        return END
    return "agent_executor"


def _route_from_agents(state: AgentState) -> str:
    """Synthesize when data is sufficient or retries are exhausted; else replan."""
    if state.get("is_sufficient", True):
        return "synthesizer"
    if (state.get("retry_count") or 0) >= MAX_RETRIES:
        return "synthesizer"   # partial answer
    return "replan"


# ── Graph assembly ────────────────────────────────────────────────────────────

def create_graph() -> StateGraph:
    workflow = StateGraph(AgentState)

    workflow.add_node("router",             router_agent.classify_and_route)
    workflow.add_node("direct_reply",       direct_reply_node)
    workflow.add_node("safe_decline",       safe_decline_node)
    workflow.add_node("clarification_gate", clarification_gate_node)
    workflow.add_node("agent_executor",     agent_executor_node)
    workflow.add_node("replan",             replan_node)
    workflow.add_node("synthesizer",        synthesizer_agent.run)

    workflow.set_entry_point("router")

    workflow.add_conditional_edges("router", _route_from_router, {
        "direct_reply":       "direct_reply",
        "safe_decline":       "safe_decline",
        "synthesizer":        "synthesizer",
        "clarification_gate": "clarification_gate",
    })

    workflow.add_conditional_edges("clarification_gate", _route_from_gate, {
        END:              END,
        "agent_executor": "agent_executor",
    })

    workflow.add_conditional_edges("agent_executor", _route_from_agents, {
        "synthesizer": "synthesizer",
        "replan":      "replan",
    })

    workflow.add_edge("replan", "agent_executor")
    workflow.add_edge("direct_reply", END)
    workflow.add_edge("safe_decline", END)
    workflow.add_edge("synthesizer", END)

    # Short-term graph-state persistence (Postgres, or in-memory fallback).
    checkpointer = build_checkpointer()
    if checkpointer is not None:
        return workflow.compile(checkpointer=checkpointer)
    return workflow.compile()


app_graph = create_graph()


