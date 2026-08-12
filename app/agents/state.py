from typing import TypedDict, Annotated, Sequence, List, Dict, Any
from langchain_core.messages import BaseMessage
import operator


class AgentState(TypedDict):
    # Conversation
    messages: Annotated[Sequence[BaseMessage], operator.add]
    session_id: str
    metadata: Dict[str, Any]

    # Routing — set by router_node
    route: str  # "greeting" | "portfolio_only" | "crm_only" | "both" | "general"

    # Raw tool results — set by agent_executor_node (no LLM generation)
    portfolio_output: Dict[str, Any]
    crm_output: Dict[str, Any]

    # Synthesis — set by synthesizer_node
    final_output: str
    citations: List[Dict[str, Any]]

    # Feedback loop — set by synthesizer_node
    is_sufficient: bool
    clarification_needed: str
    retry_count: int

    # Backward-compat field still read by existing route handlers
    next_agent: str

