"""Agents package.

    base                       → shared LLM singleton + history helpers (BaseAgent)
    state                      → AgentState TypedDict
    router                     → RouterAgent (greeting fast-path + intent classification)
    portfolio_insights         → PortfolioInsightsAgent (data collector via 4 API tools)
    relationship_intelligence  → RelationshipIntelligenceAgent (data collector via MCP)
    synthesizer                → SynthesizerAgent (merge data + generate response)
    graph                      → LangGraph wiring
    orchestrator               → process_chat / stream_agent entry points
    memory.long_term_memory    → episodic / semantic / procedural / preferences
"""

from app.agents.orchestrator import process_chat, stream_agent

__all__ = ["process_chat", "stream_agent"]
