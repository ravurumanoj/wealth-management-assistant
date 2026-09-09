from __future__ import annotations

import asyncio
import time
from typing import AsyncGenerator, Optional

from langchain_core.messages import HumanMessage

from app.agents.base import extract_text as _extract_text
from app.agents.graph import app_graph
from app.agents.memory import long_term_memory
from app.agents.memory.episodic_store import episodic_memory
from app.agents.execution import evaluate_sufficiency, execute_agents, targets_for_route
from app.config import settings
from app.services import audit
from app.services.entitlements import is_client_authorized, resolve_rm_id, authorized_client_ids
from app.services.guardrails import check_input, scan_output
from app.constants import (
    AGENT_CRM,
    AGENT_PORTFOLIO,
    AGENT_STEP_NODE,
    AGENT_USED_BLOCKED,
    AGENT_USED_CLARIFICATION,
    AGENT_USED_DENIED,
    COMPLIANCE_DISCLAIMER,
    DATA_ROUTES,
    DEFAULT_CLIENT_ID,
    ENTITLEMENT_DENIED_MESSAGE,
    INPUT_BLOCKED_MESSAGE,
    MAX_RETRIES,
    ROUTE_BOTH,
    ROUTE_CRM_ONLY,
    ROUTE_GENERAL,
    ROUTE_GREETING,
    ROUTE_OUT_OF_SCOPE,
    ROUTE_PORTFOLIO_ONLY,
    STEP_CLARIFICATION,
    STEP_GENERAL,
    STEP_ROUTER,
    STEP_SYNTHESIZER,
)
from app.prompts.replan import REPLAN_INSTRUCTION_TEMPLATE
from app.utils.logger import logger


async def process_chat(message: str, session_id: str, metadata: dict = None) -> dict:
    """Non-streaming REST path — run full LangGraph pipeline and return result."""
    logger.info(f"process_chat: session={session_id}")
    client_id = (metadata or {}).get("client_id") or DEFAULT_CLIENT_ID
    rm_id = resolve_rm_id(metadata)
    started = time.monotonic()

    # ── Input guardrail — block injection / disallowed actions before any LLM ──
    input_check = check_input(message)
    if not input_check.allowed:
        audit.audit_turn(
            session_id=session_id or "", client_id=client_id, rm_id=rm_id,
            route="", query=message, response=INPUT_BLOCKED_MESSAGE,
            outcome="blocked", guardrail_flags=[input_check.category],
            latency_ms=int((time.monotonic() - started) * 1000),
        )
        return {"final_output": INPUT_BLOCKED_MESSAGE, "next_agent": AGENT_USED_BLOCKED, "citations": []}

    # ── Entitlement — deny a selected-but-unauthorized client before retrieval ─
    if client_id != DEFAULT_CLIENT_ID and not is_client_authorized(rm_id, client_id):
        audit.audit_turn(
            session_id=session_id or "", client_id=client_id, rm_id=rm_id,
            route="", query=message, response=ENTITLEMENT_DENIED_MESSAGE,
            outcome="entitlement_denied", entitlement="denied",
            latency_ms=int((time.monotonic() - started) * 1000),
        )
        return {"final_output": ENTITLEMENT_DENIED_MESSAGE, "next_agent": AGENT_USED_DENIED, "citations": []}

    # Long-term episodic recall (per client) injected into the initial state.
    ltm_context = ""
    try:
        episodes = await asyncio.to_thread(episodic_memory.search, client_id, message)
        ltm_context = episodic_memory.format_context(episodes)
    except Exception as e:
        logger.warning(f"process_chat episodic recall failed: {e}")

    initial_state = {
        "messages": [HumanMessage(content=message)],
        "session_id": session_id,
        "metadata": metadata or {},
        "route": "",
        "execution_mode": "",
        "producer": "",
        "portfolio_output": {},
        "crm_output": {},
        "final_output": "",
        "citations": [],
        "ltm_context": ltm_context,
        "needs_clarification": False,
        "is_sufficient": True,
        "clarification_needed": "",
        "replan_instruction": "",
        "retry_count": 0,
        "next_agent": "",
    }
    try:
        result = await app_graph.ainvoke(
            initial_state, config={"configurable": {"thread_id": session_id}}
        )
        logger.info(f"process_chat complete: session={session_id}")

        route = result.get("route", "")
        final_output = result.get("final_output", "")
        guardrail_flags = []

        # ── Output guardrail — disclaimer on data answers ─────────────────────
        if route in DATA_ROUTES and final_output and not result.get("needs_clarification"):
            guardrail_flags = scan_output(final_output).flags
            if settings.GUARDRAILS_ENABLED:
                final_output = f"{final_output}\n\n{COMPLIANCE_DISCLAIMER}"
                result["final_output"] = final_output

        # ── Persist episodic memory + audit ───────────────────────────────────
        if route in DATA_ROUTES and not result.get("needs_clarification"):
            try:
                await asyncio.to_thread(
                    episodic_memory.add_episode,
                    client_id, session_id or "", message, final_output, route,
                )
            except Exception as e:
                logger.warning(f"process_chat episodic write failed: {e}")

        audit.audit_turn(
            session_id=session_id or "", client_id=client_id, rm_id=rm_id,
            route=route, query=message, response=final_output,
            outcome="clarification_requested" if result.get("needs_clarification") else "completed",
            tools_used=(
                (result.get("portfolio_output") or {}).get("tools_called", [])
                + (result.get("crm_output") or {}).get("tools_called", [])
            ),
            guardrail_flags=guardrail_flags,
            latency_ms=int((time.monotonic() - started) * 1000),
        )
        return result
    except Exception as e:
        logger.error(f"process_chat error: {e}", exc_info=True)
        raise


async def stream_agent(
    message: str, session_id: str, metadata: dict = None
) -> AsyncGenerator[dict, None]:
    """Streaming path — yields SSE-style dicts as the pipeline progresses.

    Flow:
      1. Router classifies the query (route + execution plan for 'both').
      2. Short-circuits: greeting -> direct reply, out_of_scope -> safe decline,
         general -> synthesizer (no tools).
      3. Data routes pass through the clarification gate; if the query is
         ambiguous/under-specified the RM is asked to disambiguate and the turn ends.
      4. Otherwise sub-agents run (parallel or sequential) inside a re-fetch loop;
         missing data triggers a targeted re-dispatch until sufficient or retries
         are exhausted, after which a partial answer is synthesized.

    Event shapes:
      {"type": "step",     "node": str, "state": "running"|"done"}
      {"type": "activity", "icon": str, "msg": str, "done"?: bool}
      {"type": "token",    "content": str}
      {"type": "done",     "agent_used": str, "full_response": str}
      {"type": "error",    "message": str}
    """
    from app.agents.router import router_agent
    from app.agents.clarification import clarification_agent
    from app.agents.direct_response import direct_responder
    from app.agents.synthesizer import synthesizer_agent
    from app.services.memory import memory_service

    client_id = (metadata or {}).get("client_id") or DEFAULT_CLIENT_ID
    active_portfolio_ids = (metadata or {}).get("active_portfolio_ids") or []
    rm_id = resolve_rm_id(metadata)
    started = time.monotonic()

    if not message or not message.strip():
        yield {"type": "error", "message": "Message cannot be empty."}
        return

    # ── Input guardrail — block injection / disallowed actions before any LLM ──
    input_check = check_input(message)
    if not input_check.allowed:
        yield {"type": "token", "content": INPUT_BLOCKED_MESSAGE}
        yield {"type": "done", "agent_used": AGENT_USED_BLOCKED, "full_response": INPUT_BLOCKED_MESSAGE}
        audit.audit_turn(
            session_id=session_id or "", client_id=client_id, rm_id=rm_id,
            route="", query=message, response=INPUT_BLOCKED_MESSAGE,
            outcome="blocked", guardrail_flags=[input_check.category],
            latency_ms=int((time.monotonic() - started) * 1000),
        )
        return

    # Prepend active portfolio context so the sub-agents know the scope.
    original_message = message
    if active_portfolio_ids:
        ids_str = ", ".join(active_portfolio_ids)
        message = f"[Active portfolios in scope: {ids_str}]\n\n{message}"

    state_base: dict = {
        "messages": [HumanMessage(content=message)],
        "session_id": session_id or "",
        "metadata": metadata or {},
        "route": "",
        "execution_mode": "",
        "producer": "",
        "portfolio_output": {},
        "crm_output": {},
        "final_output": "",
        "citations": [],
        "ltm_context": "",
        "needs_clarification": False,
        "is_sufficient": True,
        "clarification_needed": "",
        "replan_instruction": "",
        "retry_count": 0,
        "next_agent": "",
    }

    # ── Load memory ───────────────────────────────────────────────────────────
    raw_history = memory_service.get_history(session_id or "")
    prior_history = raw_history[:-1] if (raw_history and raw_history[-1].get("role") == "user") else raw_history
    existing_summary = memory_service.get_summary(session_id or "")

    # ── 1. Intent classification + execution planning ─────────────────────────
    yield {"type": "step", "node": STEP_ROUTER, "state": "running"}
    yield {"type": "activity", "icon": "route", "msg": "Router: classifying query..."}
    try:
        decision, updated_summary = await router_agent.decide(
            original_message, history=prior_history, existing_summary=existing_summary
        )
    except Exception as e:
        logger.error(f"router.decide error: {e}", exc_info=True)
        yield {"type": "error", "message": "Router failed. Please try again."}
        return

    if updated_summary and updated_summary != existing_summary:
        try:
            memory_service.save_summary(session_id or "", updated_summary)
        except Exception:
            pass

    route = decision.route
    state_base["route"] = route
    state_base["execution_mode"] = decision.execution_mode or ""
    state_base["producer"] = decision.producer or ""
    yield {"type": "step", "node": STEP_ROUTER, "state": "done"}
    yield {"type": "activity", "icon": "route", "msg": f"Router: intent = {route}", "done": True}
    logger.info(f"stream_agent: route={route} mode={decision.execution_mode} session={session_id}")

    # ── 2a. Greeting → direct reply (skip synthesizer) ────────────────────────
    if route == ROUTE_GREETING:
        yield {"type": "step", "node": STEP_GENERAL, "state": "running"}
        yield {"type": "activity", "icon": "write", "msg": "Direct reply..."}
        full_response = ""
        async for token in direct_responder.stream_greeting(original_message, prior_history):
            full_response += token
            yield {"type": "token", "content": token}
        yield {"type": "step", "node": STEP_GENERAL, "state": "done"}
        yield {"type": "activity", "icon": "check", "msg": "Done", "done": True}
        yield {"type": "done", "agent_used": ROUTE_GREETING, "full_response": full_response}
        audit.audit_turn(
            session_id=session_id or "", client_id=client_id, rm_id=rm_id,
            route=route, query=original_message, response=full_response,
            outcome="completed", latency_ms=int((time.monotonic() - started) * 1000),
        )
        return

    # ── 2b. Out of scope → safe decline (deterministic) ──────────────────────
    if route == ROUTE_OUT_OF_SCOPE:
        yield {"type": "step", "node": STEP_GENERAL, "state": "running"}
        yield {"type": "activity", "icon": "shield", "msg": "Out of scope — declining."}
        full_response = direct_responder.safe_decline()
        yield {"type": "token", "content": full_response}
        yield {"type": "step", "node": STEP_GENERAL, "state": "done"}
        yield {"type": "activity", "icon": "check", "msg": "Done", "done": True}
        yield {"type": "done", "agent_used": ROUTE_OUT_OF_SCOPE, "full_response": full_response}
        audit.audit_turn(
            session_id=session_id or "", client_id=client_id, rm_id=rm_id,
            route=route, query=original_message, response=full_response,
            outcome="out_of_scope", latency_ms=int((time.monotonic() - started) * 1000),
        )
        return

    # ── 2c. General wealth question → synthesizer with no tool data ───────────
    if route == ROUTE_GENERAL:
        yield {"type": "step", "node": STEP_GENERAL, "state": "running"}
        yield {"type": "activity", "icon": "write", "msg": "Synthesizer: generating response..."}
        full_response = ""
        async for token in synthesizer_agent.stream_run(state_base, prior_history, updated_summary):
            full_response += token
            yield {"type": "token", "content": token}
        yield {"type": "step", "node": STEP_GENERAL, "state": "done"}
        yield {"type": "activity", "icon": "check", "msg": "Done", "done": True}
        yield {"type": "done", "agent_used": ROUTE_GENERAL, "full_response": full_response}
        audit.audit_turn(
            session_id=session_id or "", client_id=client_id, rm_id=rm_id,
            route=route, query=original_message, response=full_response,
            outcome="completed", latency_ms=int((time.monotonic() - started) * 1000),
        )
        _save_long_term(client_id, session_id, original_message, full_response, route)
        return

    # ── 3. Data routes: entitlement enforcement + clarification gate ──────────
    if route in DATA_ROUTES:
        # Enforce client-level entitlement BEFORE any retrieval (FR-COM-001/003).
        if not is_client_authorized(rm_id, client_id):
            yield {"type": "token", "content": ENTITLEMENT_DENIED_MESSAGE}
            yield {"type": "done", "agent_used": AGENT_USED_DENIED, "full_response": ENTITLEMENT_DENIED_MESSAGE}
            audit.audit_turn(
                session_id=session_id or "", client_id=client_id, rm_id=rm_id,
                route=route, query=original_message, response=ENTITLEMENT_DENIED_MESSAGE,
                outcome="entitlement_denied", entitlement="denied",
                latency_ms=int((time.monotonic() - started) * 1000),
            )
            return

        yield {"type": "step", "node": STEP_CLARIFICATION, "state": "running"}
        yield {"type": "activity", "icon": "route", "msg": "Checking if the request is specific enough..."}
        gate = await clarification_agent.assess(
            original_message,
            client_id=client_id,
            active_portfolio_ids=active_portfolio_ids,
            history=prior_history,
            summary=updated_summary,
            authorized_client_ids=authorized_client_ids(rm_id),
        )
        if gate.needs_clarification:
            yield {"type": "step", "node": STEP_CLARIFICATION, "state": "done"}
            yield {"type": "activity", "icon": "route", "msg": "Need clarification from RM", "done": True}
            yield {"type": "token", "content": gate.question}
            yield {"type": "done", "agent_used": AGENT_USED_CLARIFICATION, "full_response": gate.question}
            audit.audit_turn(
                session_id=session_id or "", client_id=client_id, rm_id=rm_id,
                route=route, query=original_message, response=gate.question,
                outcome="clarification_requested",
                latency_ms=int((time.monotonic() - started) * 1000),
            )
            return
        yield {"type": "step", "node": STEP_CLARIFICATION, "state": "done"}
        yield {"type": "activity", "icon": "check", "msg": "Request is specific — retrieving data", "done": True}

    # ── 3b. Long-term episodic recall (per client, across sessions) ───────────
    try:
        episodes = await asyncio.to_thread(episodic_memory.search, client_id, original_message)
        if episodes:
            state_base["ltm_context"] = episodic_memory.format_context(episodes)
            yield {"type": "activity", "icon": "route",
                   "msg": f"Recalled {len(episodes)} prior interaction(s) for this client", "done": True}
    except Exception as e:
        logger.warning(f"episodic recall failed: {e}")

    # ── 4. Sub-agent retrieval with re-fetch/replan loop ──────────────────────
    run_targets = targets_for_route(route)
    replan_instruction: Optional[str] = None
    missing_desc = ""
    is_sufficient = True

    try:
        for attempt in range(MAX_RETRIES + 1):
            async for ev in _emit_agent_steps(run_targets, "running"):
                yield ev

            outputs = await execute_agents(
                state_base,
                route=route,
                execution_mode=state_base["execution_mode"],
                producer=state_base["producer"],
                history=prior_history,
                summary=updated_summary,
                targets=run_targets,
                replan_instruction=replan_instruction,
            )
            state_base.update(outputs)

            async for ev in _emit_agent_done_steps(run_targets, state_base):
                yield ev

            is_sufficient, missing_desc, missing_targets = evaluate_sufficiency(
                route, state_base.get("portfolio_output"), state_base.get("crm_output")
            )
            if is_sufficient or attempt >= MAX_RETRIES:
                break

            # Re-fetch only the failing sub-agent(s) with a structured instruction.
            run_targets = missing_targets
            replan_instruction = REPLAN_INSTRUCTION_TEMPLATE.format(
                missing=missing_desc, client_id=client_id
            )
            yield {"type": "activity", "icon": "route",
                   "msg": f"Data incomplete ({missing_desc}) — re-fetching (attempt {attempt + 2})..."}
    except Exception as e:
        logger.error(f"Agent data collection error: {e}", exc_info=True)
        yield {"type": "error", "message": f"Failed to retrieve data: {str(e)}"}
        return

    # ── 5. Synthesize and stream the final response ───────────────────────────
    partial_missing = missing_desc if not is_sufficient else None
    if partial_missing:
        yield {"type": "activity", "icon": "shield",
               "msg": f"Proceeding with partial data — {partial_missing} unavailable"}

    yield {"type": "step", "node": STEP_SYNTHESIZER, "state": "running"}
    yield {"type": "activity", "icon": "write", "msg": "Synthesizer: generating response..."}
    full_response = ""
    try:
        async for token in synthesizer_agent.stream_run(
            state_base, prior_history, updated_summary, partial_missing=partial_missing
        ):
            full_response += token
            yield {"type": "token", "content": token}
    except Exception as e:
        logger.error(f"Synthesizer stream error: {e}", exc_info=True)
        if full_response:
            yield {"type": "done", "agent_used": route, "full_response": full_response}
        else:
            yield {"type": "error", "message": f"Synthesis error: {str(e)}"}
        return

    if not full_response:
        yield {"type": "error", "message": "The model returned an empty response."}
        return

    # ── Output guardrail — flag advice phrasing, append compliance disclaimer ─
    output_scan = scan_output(full_response)
    if settings.GUARDRAILS_ENABLED:
        disclaimer = f"\n\n{COMPLIANCE_DISCLAIMER}"
        yield {"type": "token", "content": disclaimer}
        full_response += disclaimer

    yield {"type": "step", "node": STEP_SYNTHESIZER, "state": "done"}
    yield {"type": "activity", "icon": "check", "msg": "Done", "done": True}
    yield {"type": "done", "agent_used": route, "full_response": full_response}

    # ── Audit (FR-COM-011) ────────────────────────────────────────────────────
    tools_used = (
        (state_base.get("portfolio_output") or {}).get("tools_called", [])
        + (state_base.get("crm_output") or {}).get("tools_called", [])
    )
    audit.audit_turn(
        session_id=session_id or "", client_id=client_id, rm_id=rm_id,
        route=route, query=original_message, response=full_response,
        outcome="completed" if is_sufficient else "partial",
        tools_used=tools_used, entitlement="allowed",
        guardrail_flags=output_scan.flags,
        latency_ms=int((time.monotonic() - started) * 1000),
    )

    # Persist this turn to long-term episodic memory (per client), off the hot path.
    try:
        await asyncio.to_thread(
            episodic_memory.add_episode,
            client_id, session_id or "", original_message, full_response, route
        )
    except Exception as e:
        logger.warning(f"episodic write failed: {e}")


async def _emit_agent_steps(targets, state: str) -> AsyncGenerator[dict, None]:
    """Yield 'running' step + activity events for each sub-agent about to run."""
    labels = {
        AGENT_PORTFOLIO: "Portfolio Agent: fetching data...",
        AGENT_CRM: "CRM Agent: fetching interaction data...",
    }
    for agent_name in (a for a in (AGENT_PORTFOLIO, AGENT_CRM) if a in targets):
        yield {"type": "step", "node": AGENT_STEP_NODE[agent_name], "state": state}
        yield {"type": "activity", "icon": "agent", "msg": labels[agent_name]}


async def _emit_agent_done_steps(targets, state_base: dict) -> AsyncGenerator[dict, None]:
    """Yield 'done' step + tool-summary activity events for each sub-agent that ran."""
    output_key = {AGENT_PORTFOLIO: "portfolio_output", AGENT_CRM: "crm_output"}
    label = {AGENT_PORTFOLIO: "Portfolio", AGENT_CRM: "CRM"}
    for agent_name in (a for a in (AGENT_PORTFOLIO, AGENT_CRM) if a in targets):
        tools = (state_base.get(output_key[agent_name]) or {}).get("tools_called", [])
        yield {"type": "step", "node": AGENT_STEP_NODE[agent_name], "state": "done"}
        yield {"type": "activity", "icon": "tool",
               "msg": f"{label[agent_name]}: {', '.join(tools) or 'no tools called'}", "done": True}


def _save_long_term(client_id: str, session_id: str, query: str, answer: str, intent: str) -> None:
    """Persist turn facts to long-term memory (non-blocking, fail-silent)."""
    try:
        long_term_memory.save_turn_facts(
            client_id=client_id,
            session_id=session_id or "",
            query=query,
            answer=answer,
            intent=intent,
        )
    except Exception:
        logger.warning("stream_agent: long-term memory save failed (non-fatal)")


