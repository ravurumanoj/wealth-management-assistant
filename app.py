import os
import time

import streamlit as st

from utils.api import call_backend
from utils.helpers import load_css, stream_text, mock_response, format_citations
from utils.state import initialize_state, reset_chat, build_payload
from utils.wealth_data import AGENTS, CLIENTS, QUICK_ACTIONS, DISCLAIMER


st.set_page_config(
    page_title="Client 360 Wealth Assistant",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded",
)

initialize_state()
load_css("styles/main.css")


with st.sidebar:
    st.markdown("## ⚙️ Wealth assistant configuration")

    st.session_state.chat_title = st.text_input(
        "Assistant name", value=st.session_state.chat_title
    )
    st.session_state.bot_subtitle = st.text_input(
        "Subtitle", value=st.session_state.bot_subtitle
    )

    selected_client = st.selectbox(
        "Client context",
        options=[c["name"] for c in CLIENTS],
        index=0,
    )

    selected_agent = st.selectbox(
        "Agent focus",
        options=[a["name"] for a in AGENTS],
        index=0,
    )

    require_citations = st.toggle("Require citation panel", value=True)
    advisor_copilot_mode = st.toggle("Advisor copilot mode", value=True)
    compact_mode = st.toggle("Compact chat density", value=False)
    enable_streaming = st.toggle("Stream assistant response", value=True)

    backend_url = st.text_input(
        "Backend API URL",
        value=os.getenv("BOT_API_URL", ""),
        placeholder="https://your-api/chat",
    )
    api_key = st.text_input(
        "API key / token",
        value=os.getenv("BOT_API_KEY", ""),
        type="password",
    )

    st.markdown("---")
    st.markdown("### Conversation")
    if st.button("🧹 Clear chat", use_container_width=True):
        reset_chat()
        st.rerun()

    st.download_button(
        "⬇️ Export transcript",
        data="\
\
".join(
            [f"{m['role'].upper()}: {m['content']}" for m in st.session_state.messages]
        ),
        file_name="wealth_assistant_transcript.txt",
        mime="text/plain",
        use_container_width=True,
    )


client_record = next(c for c in CLIENTS if c["name"] == selected_client)
agent_record = next(a for a in AGENTS if a["name"] == selected_agent)

st.markdown(
    f"""
<div class="hero-card">
    <div class="hero-title">💼 {st.session_state.chat_title}</div>
    <div class="hero-subtitle">{st.session_state.bot_subtitle}</div>
    <div class="status-row">
        <span class="status-pill">Client: {client_record['name']}</span>
        <span class="status-pill">Agent: {agent_record['name']}</span>
        <span class="status-pill">{'Live API' if backend_url else 'Mock mode'}</span>
    </div>
</div>
""",
    unsafe_allow_html=True,
)

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.markdown(
        f"""
<div class="metric-card">
    <div class="metric-label">Risk Profile</div>
    <div class="metric-value">{client_record['risk_profile']}</div>
</div>
""",
        unsafe_allow_html=True,
    )
with col2:
    st.markdown(
        f"""
<div class="metric-card">
    <div class="metric-label">AUM Snapshot</div>
    <div class="metric-value">{client_record['aum']}</div>
</div>
""",
        unsafe_allow_html=True,
    )
with col3:
    st.markdown(
        f"""
<div class="metric-card">
    <div class="metric-label">KYC / AML</div>
    <div class="metric-value">{client_record['compliance_status']}</div>
</div>
""",
        unsafe_allow_html=True,
    )
with col4:
    st.markdown(
        f"""
<div class="metric-card">
    <div class="metric-label">Last Interaction</div>
    <div class="metric-value">{client_record['last_interaction']}</div>
</div>
""",
        unsafe_allow_html=True,
    )

st.markdown(
    f"<div class='disclaimer-banner'>{DISCLAIMER}</div>",
    unsafe_allow_html=True,
)

with st.container():
    st.markdown('<div class="chat-shell">', unsafe_allow_html=True)

    if len(st.session_state.messages) <= 1:
        st.markdown("#### Relationship manager quick actions")
        cols = st.columns(3)
        for i, prompt in enumerate(QUICK_ACTIONS):
            with cols[i % 3]:
                if st.button(prompt, key=f"quick_action_{i}", use_container_width=True):
                    st.session_state.prefill_message = prompt

    st.markdown("#### Available assistant lenses")
    lens_cols = st.columns(len(AGENTS))
    for i, agent in enumerate(AGENTS):
        with lens_cols[i]:
            st.markdown(
                f"<div class='agent-pill {'active' if agent['name'] == selected_agent else ''}'>{agent['name']}</div>",
                unsafe_allow_html=True,
            )

    for message in st.session_state.messages:
        avatar = "🧠" if message["role"] == "assistant" else "🙂"
        with st.chat_message(message["role"], avatar=avatar):
            st.markdown(message["content"])
            refs = message.get("citations", [])
            if require_citations and refs:
                st.markdown(format_citations(refs), unsafe_allow_html=True)

    user_input = st.chat_input("Ask about portfolio, client 360, compliance, or meeting preparation...", max_chars=4000)

    if not user_input and st.session_state.get("prefill_message"):
        user_input = st.session_state.pop("prefill_message")

    if user_input:
        user_message = {
            "role": "user",
            "content": user_input,
            "timestamp": time.strftime("%H:%M:%S"),
        }
        st.session_state.messages.append(user_message)

        with st.chat_message("user", avatar="🙂"):
            st.markdown(user_input)

        with st.chat_message("assistant", avatar="🧠"):
            placeholder = st.empty()
            try:
                with st.status("Analyzing client context...", expanded=False):
                    if backend_url:
                        assistant_text = call_backend(
                            user_message=user_input,
                            endpoint=backend_url,
                            api_key=api_key,
                            payload_builder=lambda msg: build_payload(
                                user_message=msg,
                                messages=st.session_state.messages,
                                session_id=st.session_state.get("session_id", "local-session"),
                                domain_context={
                                    "client": client_record,
                                    "agent": agent_record,
                                    "advisor_copilot_mode": advisor_copilot_mode,
                                    "require_citations": require_citations,
                                },
                            ),
                        )
                        assistant_citations = [
                            "Citations supplied by backend can be rendered here.",
                        ]
                    else:
                        assistant_text, assistant_citations = mock_response(
                            user_message=user_input,
                            client_record=client_record,
                            agent_record=agent_record,
                            advisor_copilot_mode=advisor_copilot_mode,
                        )

                if compact_mode:
                    assistant_text = assistant_text.replace("\
\
", "\
")

                if enable_streaming:
                    final_text = placeholder.write_stream(stream_text(assistant_text))
                else:
                    placeholder.markdown(assistant_text)
                    final_text = assistant_text

            except Exception as exc:
                final_text = (
                    "I couldn't reach the backend. Check the API URL, credentials, or response schema.\
\
"
                    f"**Error:** `{exc}`"
                )
                assistant_citations = []
                placeholder.markdown(final_text)

        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": final_text,
                "timestamp": time.strftime("%H:%M:%S"),
                "citations": assistant_citations,
            }
        )

    st.markdown("</div>", unsafe_allow_html=True)