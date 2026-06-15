from typing import TypedDict, Annotated, Sequence, List, Dict, Any
from langchain_core.messages import BaseMessage
import operator

class AgentState(TypedDict):
    """
    State for the LangGraph agents.
    """
    # Messages list with additive operator
    messages: Annotated[Sequence[BaseMessage], operator.add]
    
    # Track the current active agent
    next_agent: str
    
    # Metadata and session info
    session_id: str
    metadata: Dict[str, Any]
    
    # Final response to be returned to user
    final_output: str

