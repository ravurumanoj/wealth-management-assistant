"""Structured re-fetch instruction for the post-dispatch replan loop.

When retrieved data is insufficient, the orchestrator injects this instruction
into the failing sub-agent(s) and re-dispatches them (FR-ORC-005) instead of
immediately asking the RM. The instruction is templated (deterministic, no extra
LLM call) so the retry behaviour stays cheap and auditable.
"""

REPLAN_INSTRUCTION_TEMPLATE = (
    "RE-FETCH REQUIRED. The previous attempt did not return: {missing}. "
    "For client '{client_id}', call the appropriate tools now to obtain this data. "
    "Do not answer from memory — you must invoke the tools."
)
