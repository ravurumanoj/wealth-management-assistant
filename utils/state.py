import streamlit as st


def initialize_state() -> None:
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {
                "role": "assistant",
                "content": (
                    "Welcome to Client 360 Wealth Assistant. I can help with portfolio insights, "
                    "client 360 context, compliance checks, meeting preparation, and next best actions."
                ),
                "citations": [
                    "Portfolio Insight Agent / Relationship Intelligence Agent / Meeting Intelligence Agent / Coaching-Next Best Action Agent",
                ],
            }
        ]

    if "chat_title" not in st.session_state:
        st.session_state.chat_title = "Client 360 Wealth Assistant"

    if "bot_subtitle" not in st.session_state:
        st.session_state.bot_subtitle = "Portfolio, relationship, compliance, and meeting support"

    if "session_id" not in st.session_state:
        st.session_state.session_id = "local-session"


def reset_chat() -> None:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": "Chat cleared. What wealth-management task would you like to work on next?",
            "citations": [],
        }
    ]


def build_payload(
    user_message: str,
    messages: list,
    session_id: str = "local-session",
    domain_context: dict | None = None,
) -> dict:
    history = [{"role": m["role"], "content": m["content"]} for m in messages]
    return {
        "message": user_message,
        "history": history,
        "metadata": {
            "source": "streamlit-wealth-assistant",
            "session_id": session_id,
            "domain_context": domain_context or {},
        },
    }
