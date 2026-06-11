import time
from typing import Generator

import streamlit as st


def load_css(file_path: str) -> None:
    with open(file_path, "r", encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


def stream_text(text: str, delay: float = 0.012) -> Generator[str, None, None]:
    words = text.split(" ")
    out = ""
    for word in words:
        out += word + " "
        yield out
        time.sleep(delay)


def format_citations(citations: list[str]) -> str:
    if not citations:
        return ""

    items = "".join([f"<div class='citation-item'>• {item}</div>" for item in citations])
    return f"<div class='citation-card'><div class='citation-title'>Source attribution</div>{items}</div>"


def mock_response(user_message: str, client_record: dict, agent_record: dict, advisor_copilot_mode: bool = True):
    summary_block = (
        "**Advisor summary of intent**\n"
        f"- Client: {client_record['name']}\n"
        f"- Focus: {agent_record['name']}\n"
        f"- User ask: {user_message}\n\n"
        if advisor_copilot_mode else ""
    )

    answer = (
        f"{summary_block}"
        f"I’m operating in **{agent_record['name']}** mode for **{client_record['name']}**.\n\n"
        "Here is a wealth-management-style placeholder response:\n"
        f"- Portfolio context: {client_record['aum']} AUM, {client_record['risk_profile']} risk profile\n"
        f"- Compliance context: {client_record['compliance_status']}\n"
        f"- Last interaction: {client_record['last_interaction']}\n\n"
        "Connect your backend to replace this with live portfolio, CRM, compliance, and meeting-prep answers."
    )

    citations = [
        "Current Portfolio Valuation / Historical Valuation / breakdown by account, geography, currency, and asset.",
        "Performance Intelligence includes YTD, MTD, since inception, volatility, and concentration views.",
        "Meeting Preparation Support includes minutes, open points, and references from previous discussions.",
    ]

    return answer, citations
