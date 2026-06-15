from langgraph.graph import StateGraph, END
from app.agents.state import AgentState
from app.agents.nodes import nodes

def create_orchestrator():
    """
    Builds the LangGraph orchestrator for Wealth Management.
    The graph handles the non-streaming REST path only.
    general / needs_clarification intents fall back to portfolio_insights.
    """
    workflow = StateGraph(AgentState)

    # Nodes
    workflow.add_node("portfolio_insights", nodes.portfolio_insights_agent)
    workflow.add_node("relationship_intelligence", nodes.relationship_intelligence_agent)

    # Conditional entry — maps all 4 classifier outputs; general/clarification
    # route to portfolio_insights as the best-effort fallback for the REST path.
    workflow.set_conditional_entry_point(
        nodes.router_node,
        {
            "portfolio_insights":        "portfolio_insights",
            "relationship_intelligence": "relationship_intelligence",
            "general":                   "portfolio_insights",
            "needs_clarification":       "portfolio_insights",
        }
    )

    workflow.add_edge("portfolio_insights", END)
    workflow.add_edge("relationship_intelligence", END)

    return workflow.compile()

app_graph = create_orchestrator()

