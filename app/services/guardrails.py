"""Guardrails service (P5.3) — three deterministic layers.

- Input scope   : block prompt-injection attempts and disallowed action requests
                  BEFORE any model call (FR-COM-009 support; injection defence).
- PII redaction : mask PII in text persisted to the audit log (never the RM answer).
- Output scan   : flag advice/recommendation phrasing and expose a standard
                  compliance disclaimer (FR-COM-008 / FR-COM-012).

All checks are regex/keyword based so they run without the LLM and are unit-testable.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List

from app.config import settings
from app.constants import (
    GUARDRAIL_DISALLOWED_ACTION,
    GUARDRAIL_INJECTION,
    GUARDRAIL_OK,
)

# ── Input guardrail patterns ──────────────────────────────────────────────────

_INJECTION_PATTERNS = [
    r"ignore (all|any|the)? ?(previous|prior|above) (instructions|prompts?)",
    r"disregard (the|your|all|any)? ?(system )?(prompt|instructions)",
    r"reveal (your|the) (system )?(prompt|instructions)",
    r"what (is|are) your (system )?(prompt|instructions)",
    r"you are now (a|an|no longer)",
    r"act as (a|an) (?!relationship)",   # role-hijack, but allow 'act as a relationship...'
    r"developer mode|jailbreak|do anything now|\bDAN\b",
]

# Requests to perform state-changing actions the assistant must never take
# (read-only system — FR-COM-009). Detected on input for an early, clear refusal.
_DISALLOWED_ACTION_PATTERNS = [
    r"\b(execute|place|book|submit|make)\b.{0,20}\b(trade|order|buy|sell)\b",
    r"\b(buy|sell)\b.{0,20}\b(shares?|stocks?|units?|securities|now)\b",
    r"\b(send|draft|compose)\b.{0,20}\b(e-?mail|message|sms)\b",
    r"\b(transfer|withdraw|move|remit)\b.{0,20}\b(funds?|money|cash|amount)\b",
    r"\b(update|modify|change|delete|create)\b.{0,25}\b(record|crm|task|profile|account)\b",
]

_INJECTION_RE = [re.compile(p, re.IGNORECASE) for p in _INJECTION_PATTERNS]
_DISALLOWED_RE = [re.compile(p, re.IGNORECASE) for p in _DISALLOWED_ACTION_PATTERNS]


@dataclass
class InputCheck:
    """Result of the input-scope guardrail."""

    allowed: bool
    category: str = GUARDRAIL_OK
    reason: str = ""


def check_input(message: str) -> InputCheck:
    """Screen an incoming message for injection or disallowed-action requests."""
    if not settings.GUARDRAILS_ENABLED:
        return InputCheck(True, GUARDRAIL_OK, "")
    text = message or ""
    for rx in _INJECTION_RE:
        if rx.search(text):
            return InputCheck(False, GUARDRAIL_INJECTION, f"matched: {rx.pattern}")
    for rx in _DISALLOWED_RE:
        if rx.search(text):
            return InputCheck(False, GUARDRAIL_DISALLOWED_ACTION, f"matched: {rx.pattern}")
    return InputCheck(True, GUARDRAIL_OK, "")


# ── PII redaction (for audit records only) ────────────────────────────────────

_PII_RULES = [
    (re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"), "[EMAIL]"),
    (re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b"), "[PAN]"),                       # India PAN
    (re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b"), "[AADHAAR]"),                   # India Aadhaar
    (re.compile(r"\b(?:\d[ -]?){13,19}\b"), "[CARD/ACCT]"),                    # card/account numbers
    (re.compile(r"(?<!\d)(?:\+?\d{1,3}[ -]?)?(?:\d[ -]?){10}(?!\d)"), "[PHONE]"),
]


def redact_pii(text: str) -> str:
    """Mask common PII patterns when PII_MASKING_ENABLED is true; otherwise return as-is.

    Applied to audit records, never the RM answer.
    """
    if not text or not settings.PII_MASKING_ENABLED:
        return text
    out = text
    for rx, repl in _PII_RULES:
        out = rx.sub(repl, out)
    return out


# ── Output guardrail ──────────────────────────────────────────────────────────

_ADVICE_PATTERNS = [
    r"\byou should (buy|sell|invest|rebalance|switch|move)\b",
    r"\bI (recommend|suggest|advise)\b",
    r"\b(we|I) would (recommend|suggest|advise)\b",
    r"\b(buy|sell) (recommendation|rating)\b",
]
_ADVICE_RE = [re.compile(p, re.IGNORECASE) for p in _ADVICE_PATTERNS]


@dataclass
class OutputScan:
    """Result of the output-compliance guardrail."""

    flags: List[str] = field(default_factory=list)

    @property
    def has_flags(self) -> bool:
        return bool(self.flags)


def scan_output(text: str) -> OutputScan:
    """Flag advice/recommendation phrasing in a generated answer (non-destructive)."""
    if not settings.GUARDRAILS_ENABLED:
        return OutputScan(flags=[])
    flags: List[str] = []
    for rx in _ADVICE_RE:
        if rx.search(text or ""):
            flags.append(f"advice_phrasing:{rx.pattern}")
    return OutputScan(flags=flags)
