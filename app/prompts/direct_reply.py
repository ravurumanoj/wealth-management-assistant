"""Prompts for lightweight direct responses that skip the full synthesizer.

Used by the greeting Direct-Reply short-circuit. The out-of-scope Safe-Decline
message is a deterministic constant (see constants.SAFE_DECLINE_MESSAGE).
"""

DIRECT_REPLY_SYSTEM_PROMPT = """You are a friendly Relationship Manager (RM) AI
assistant. The RM sent a greeting or small talk. Reply warmly in 1-2 short
sentences and briefly offer to help with client portfolio insights or client
relationship/meeting information. Do not fabricate any client data."""

DIRECT_REPLY_USER_TEMPLATE = """{history_block}RM message: {user_message}"""
