"""Shared sub-agent execution: parallel / sequential dispatch, sequential
producer→consumer hand-off, targeted re-fetch, and the sufficiency check.

Used by both the streaming orchestrator and the LangGraph pipeline so the two
paths behave identically.
"""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional, Set, Tuple

from app.agents.portfolio_insights import portfolio_insights_agent
from app.agents.relationship_intelligence import relationship_intelligence_agent
from app.agents.state import AgentState
from app.constants import (
    AGENT_CRM,
    AGENT_PORTFOLIO,
    EXEC_MODE_SEQUENTIAL,
    ROUTE_BOTH,
    ROUTE_CRM_ONLY,
    ROUTE_PORTFOLIO_ONLY,
    SEQUENTIAL_HANDOFF_MAX_LEN,
)
from app.utils.logger import logger

# Maps a sub-agent identifier to (singleton, state-output key, human label).
_AGENT_REGISTRY = {
    AGENT_PORTFOLIO: (portfolio_insights_agent, "portfolio_output", "Portfolio"),
    AGENT_CRM: (relationship_intelligence_agent, "crm_output", "CRM"),
}


def targets_for_route(route: str) -> Set[str]:
    """Return the set of sub-agents a data route requires."""
    if route == ROUTE_PORTFOLIO_ONLY:
        return {AGENT_PORTFOLIO}
    if route == ROUTE_CRM_ONLY:
        return {AGENT_CRM}
    if route == ROUTE_BOTH:
        return {AGENT_PORTFOLIO, AGENT_CRM}
    return set()


def _handoff_context(producer_label: str, output: Dict[str, Any]) -> str:
    """Condense a producer's tool results into a short instruction for the consumer."""
    results = (output or {}).get("tool_results") or {}
    if not results:
        return ""
    lines = [
        f"Context from the {producer_label} agent — use it to target what you "
        f"retrieve (do not fetch everything blindly):"
    ]
    for tool, res in results.items():
        text = str(res)
        if len(text) > SEQUENTIAL_HANDOFF_MAX_LEN:
            text = text[:SEQUENTIAL_HANDOFF_MAX_LEN] + "…"
        lines.append(f"- {tool}: {text}")
    return "\n".join(lines)


def _merge_extra(*parts: Optional[str]) -> Optional[str]:
    """Join non-empty extra-context fragments with blank lines."""
    joined = "\n\n".join(p for p in parts if p)
    return joined or None


async def execute_agents(
    state: AgentState,
    route: str,
    execution_mode: str = "",
    producer: str = "",
    history: Optional[List[dict]] = None,
    summary: Optional[str] = None,
    targets: Optional[Set[str]] = None,
    replan_instruction: Optional[str] = None,
) -> Dict[str, Any]:
    """Run the required sub-agents and return their outputs keyed by state field.

    Args:
        route:              The data route (portfolio_only | crm_only | both).
        execution_mode:     parallel | sequential (only meaningful for 'both').
        producer:           Which sub-agent runs first when sequential.
        targets:            Explicit subset of sub-agents to run (used by the
                            re-fetch loop to re-run only the failing agent[s]).
                            Defaults to the full set for the route.
        replan_instruction: Re-fetch instruction injected into each target.

    Returns:
        A dict with ``portfolio_output`` and/or ``crm_output`` for the agents run.
    """
    run_targets = targets if targets is not None else targets_for_route(route)
    if not run_targets:
        return {}

    # Sequential hand-off — only when both agents are in play and a producer is set.
    both_present = {AGENT_PORTFOLIO, AGENT_CRM} <= run_targets
    if (
        route == ROUTE_BOTH
        and execution_mode == EXEC_MODE_SEQUENTIAL
        and producer in _AGENT_REGISTRY
        and both_present
    ):
        return await _run_sequential(
            state, producer, history, summary, replan_instruction
        )

    return await _run_parallel(
        state, run_targets, history, summary, replan_instruction
    )


async def _run_parallel(
    state: AgentState,
    run_targets: Set[str],
    history: Optional[List[dict]],
    summary: Optional[str],
    replan_instruction: Optional[str],
) -> Dict[str, Any]:
    """Dispatch the target sub-agents concurrently."""
    names: List[str] = [name for name in (AGENT_PORTFOLIO, AGENT_CRM) if name in run_targets]
    tasks = [
        _AGENT_REGISTRY[name][0].collect_data(
            state, history=history, summary=summary, extra_context=replan_instruction
        )
        for name in names
    ]
    results = await asyncio.gather(*tasks)
    outputs: Dict[str, Any] = {}
    for name, data in zip(names, results):
        outputs[_AGENT_REGISTRY[name][1]] = data
    logger.info(f"execute_agents: parallel run for {names}")
    return outputs


async def _run_sequential(
    state: AgentState,
    producer: str,
    history: Optional[List[dict]],
    summary: Optional[str],
    replan_instruction: Optional[str],
) -> Dict[str, Any]:
    """Run the producer, then feed its result into the consumer."""
    consumer = AGENT_CRM if producer == AGENT_PORTFOLIO else AGENT_PORTFOLIO
    prod_agent, prod_key, prod_label = _AGENT_REGISTRY[producer]
    cons_agent, cons_key, _ = _AGENT_REGISTRY[consumer]

    logger.info(f"execute_agents: sequential run, producer={producer} consumer={consumer}")

    producer_output = await prod_agent.collect_data(
        state, history=history, summary=summary, extra_context=replan_instruction
    )
    handoff = _handoff_context(prod_label, producer_output)
    consumer_extra = _merge_extra(replan_instruction, handoff)
    consumer_output = await cons_agent.collect_data(
        state, history=history, summary=summary, extra_context=consumer_extra
    )
    return {prod_key: producer_output, cons_key: consumer_output}


def evaluate_sufficiency(
    route: str,
    portfolio_output: Optional[Dict[str, Any]],
    crm_output: Optional[Dict[str, Any]],
) -> Tuple[bool, str, Set[str]]:
    """Check whether the agents that should have run actually returned data.

    Returns (is_sufficient, missing_description, missing_targets).
    """
    needs_portfolio = route in (ROUTE_PORTFOLIO_ONLY, ROUTE_BOTH)
    needs_crm = route in (ROUTE_CRM_ONLY, ROUTE_BOTH)

    missing_desc: List[str] = []
    missing_targets: Set[str] = set()

    if needs_portfolio and not (portfolio_output or {}).get("tool_results"):
        missing_desc.append("portfolio data")
        missing_targets.add(AGENT_PORTFOLIO)
    if needs_crm and not (crm_output or {}).get("tool_results"):
        missing_desc.append("CRM / interaction data")
        missing_targets.add(AGENT_CRM)

    return (not missing_targets, " and ".join(missing_desc), missing_targets)
