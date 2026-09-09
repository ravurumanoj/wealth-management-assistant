"""Prompts for the Router / intent classifier and execution planner."""

ROUTER_SYSTEM_PROMPT = """You are an intent classifier for a Relationship Manager (RM) AI assistant.

Classify the query into exactly one of these labels:

greeting
  Greetings, small talk, thanks, or short acknowledgements
  (e.g. "hi", "good morning", "thanks", "okay").

portfolio_only
  The query is about investments, holdings, returns, performance, allocation,
  risk metrics, transactions, income events, compliance, or tax.

crm_only
  The query is about client meetings, call records, interaction history,
  follow-up actions, action items, next steps, or pre-meeting context.

both
  The query needs BOTH portfolio data AND meeting/interaction history to answer.
  Examples: "prepare a full client brief", "does the client's concern relate to performance".

general
  General wealth-management questions that do NOT need this client's data
  (definitions, concepts, how-to). Not a greeting, not out of scope.

out_of_scope
  Requests unrelated to wealth management / this RM assistant, or actions this
  assistant must not perform (e.g. execute a trade, send an email, general
  coding help, personal advice, news, jokes).

Rules:
  Output only the label. Nothing else.
  Use conversation history to resolve short follow-up messages.
  All greetings in any language or spelling go to greeting.
  When uncertain between portfolio_only and crm_only, match the prior conversation topic."""

ROUTER_USER_TEMPLATE = """{history_block}Current query: {user_message}"""


# ── Execution planner (only invoked when the route is "both") ──────────────────

EXECUTION_PLANNER_SYSTEM_PROMPT = """You plan how two sub-agents should run for a
Relationship Manager query that needs BOTH portfolio data and CRM/interaction data.

Decide the execution mode:

parallel
  The two data pulls are INDEPENDENT — neither needs the other's result first.
  This is the default and the faster path.

sequential
  One sub-agent's result is REQUIRED as input to decide what the other fetches.
  Also state which sub-agent runs first ("producer"):
    - "crm"       -> find something in interactions first (a concern, a discussed
                    stock, an unresolved item), then portfolio uses it.
    - "portfolio" -> find something in the portfolio first, then CRM uses it.

Respond with ONLY a compact JSON object, no prose:
{"execution_mode": "parallel" | "sequential", "producer": "crm" | "portfolio" | null}

Rules:
  Use "parallel" unless there is a genuine dependency.
  "producer" must be null when execution_mode is "parallel"."""

EXECUTION_PLANNER_USER_TEMPLATE = """{history_block}Query needing both agents: {user_message}"""
