from typing import TypedDict, Annotated, Sequence, List, Dict, Any
from langchain_core.messages import BaseMessage
import operator


class AgentState(TypedDict):
    # Conversation
    messages: Annotated[Sequence[BaseMessage], operator.add]
    session_id: str
    metadata: Dict[str, Any]

    # Routing — set by router_node
    route: str  # "greeting" | "out_of_scope" | "portfolio_only" | "crm_only" | "both" | "general"

    # Execution planning for the "both" route — set by router_node
    execution_mode: str  # "parallel" | "sequential"
    producer: str        # "portfolio" | "crm" — which sub-agent runs first when sequential

    # Raw tool results — set by agent_executor_node (no LLM generation)
    portfolio_output: Dict[str, Any]
    crm_output: Dict[str, Any]

    # Synthesis — set by synthesizer_node
    final_output: str
    citations: List[Dict[str, Any]]

    # Long-term episodic recall (per client) — injected before synthesis
    ltm_context: str

    # Pre-dispatch clarification gate — set by clarification_gate_node
    needs_clarification: bool

    # Feedback loop — set by synthesizer_node / replan_node
    is_sufficient: bool
    clarification_needed: str
    replan_instruction: str
    replan_targets: List[str]
    retry_count: int

    # Backward-compat field still read by existing route handlers
    next_agent: str

