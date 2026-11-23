"""SmartBanker AI Agent — Streamlit UI.

Run locally: streamlit run ui/app.py

Modes:
- Local:  Invokes the agent in-process (no AWS required)
- Remote: Sends requests to AgentCore Gateway endpoint via HTTP

Traces: R40.
"""
from __future__ import annotations

import json
import sys
import os

import streamlit as st

# Ensure project root is on sys.path so imports work when running from ui/
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="SmartBanker AI",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Sidebar — configuration (R40.5, R40.6)
# ---------------------------------------------------------------------------

with st.sidebar:
    st.title("🏦 SmartBanker AI")
    st.caption("Personal Banker Agent")

    st.divider()
    mode = st.radio("Execution Mode", ["Local", "Remote"], index=0, help="Local runs the agent in-process. Remote calls the AgentCore Gateway.")

    if mode == "Remote":
        gateway_url = st.text_input("AgentCore Gateway URL", value="https://<gateway-id>.execute-api.us-east-1.amazonaws.com/prod", help="The AgentCore Gateway endpoint URL")
        aws_region = st.text_input("AWS Region", value="us-east-1")
    else:
        gateway_url = ""
        aws_region = "us-east-1"

    user_id = st.text_input("User ID", value="user_001")

    st.divider()

    # Service request form (R40.10)
    st.subheader("📋 Service Request")
    sr_type = st.selectbox("Request Type", [
        "account_modification", "charge_dispute", "failed_transaction_inquiry",
        "service_modification", "card_issue", "document_request",
        "kyc_update", "cheque_book_request", "other",
    ])
    sr_description = st.text_area("Description", placeholder="Describe your service request...")
    sr_submit = st.button("Submit Service Request", use_container_width=True)

    st.divider()

    # Proactive notifications trigger (R40.9)
    check_notifications = st.button("🔔 Check Proactive Notifications", use_container_width=True)


# ---------------------------------------------------------------------------
# Agent invocation helpers
# ---------------------------------------------------------------------------

def _call_local(request_text: str, uid: str) -> dict:
    """Invoke the agent in-process (local mode). R40.6."""
    from main import create_app
    app = create_app()
    response = app.process_request(uid, request_text)
    return response.model_dump()


def _call_remote(request_text: str, uid: str, url: str) -> dict:
    """Invoke the agent via AgentCore Gateway HTTP POST. R40.1."""
    import requests as req
    payload = {"user_id": uid, "request": request_text}
    try:
        resp = req.post(f"{url.rstrip('/')}/invoke", json=payload, timeout=120)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        return {
            "status": "failure",
            "correlation_id": "",
            "user_id": uid,
            "recommendations": [],
            "retries_used": 0,
            "warnings": [f"Gateway error: {str(e)}"],
        }


def call_agent(request_text: str) -> dict:
    """Route to local or remote based on mode."""
    if mode == "Remote":
        return _call_remote(request_text, user_id, gateway_url)
    return _call_local(request_text, user_id)


def _call_service_request_local(uid: str, req_type: str, description: str) -> dict:
    """Submit a service request in local mode."""
    from main import create_app
    from config.models import ServiceRequest
    app = create_app()
    sr = ServiceRequest(user_id=uid, request_type=req_type, description=description)
    response = app.handle_service_request(uid, sr)
    return response.model_dump()


def _call_proactive_local(uid: str) -> list[dict]:
    """Check proactive notifications in local mode."""
    from main import create_app
    app = create_app()
    notifications = app.check_proactive_opportunities(uid)
    return [n.model_dump() for n in notifications]


# ---------------------------------------------------------------------------
# Status color helpers (R40.8)
# ---------------------------------------------------------------------------

_STATUS_COLORS = {
    "success": "🟢",
    "partial_success": "🟡",
    "failure": "🔴",
}

_CONFIDENCE_BADGES = {
    "high": "🟢 High",
    "medium": "🟡 Medium",
    "low": "🔴 Low",
}

_RISK_BADGES = {
    "low": "🟢 Low",
    "medium": "🟡 Medium",
    "high": "🔴 High",
}


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------

def render_recommendation(rec: dict, idx: int):
    """Render a single recommendation as a structured card. R40.3."""
    status_icon = _STATUS_COLORS.get(rec.get("status", ""), "⚪")
    confidence = _CONFIDENCE_BADGES.get(rec.get("confidence", ""), rec.get("confidence", ""))
    risk = _RISK_BADGES.get(rec.get("risk_level", ""), rec.get("risk_level", ""))
    domain = rec.get("worker_domain", "unknown")

    with st.container(border=True):
        cols = st.columns([0.6, 0.2, 0.2])
        cols[0].markdown(f"**{domain.replace('_', ' ').title()}** {status_icon}")
        cols[1].markdown(f"Confidence: {confidence}")
        cols[2].markdown(f"Risk: {risk}")

        st.markdown(rec.get("recommendation", "No recommendation"))

        if rec.get("explainability_summary"):
            with st.expander("Explainability"):
                st.markdown(rec["explainability_summary"])

        if rec.get("disclaimer"):
            with st.expander("Disclaimers"):
                st.caption(rec["disclaimer"])

        if rec.get("non_fiduciary_disclaimer"):
            st.caption(f"⚠️ {rec['non_fiduciary_disclaimer']}")

        if rec.get("scope_limitation"):
            st.warning(rec["scope_limitation"])

        issues = rec.get("issues", [])
        if issues:
            with st.expander(f"Issues ({len(issues)})"):
                for issue in issues:
                    st.markdown(f"- {issue}")


def render_response(response: dict):
    """Render a full agent response. R40.2, R40.7."""
    status = response.get("status", "unknown")
    status_icon = _STATUS_COLORS.get(status, "⚪")

    st.markdown(f"{status_icon} **Status:** {status.replace('_', ' ').title()}")

    # Metadata (R40.7)
    meta_cols = st.columns(3)
    meta_cols[0].caption(f"Correlation ID: `{response.get('correlation_id', 'N/A')[:12]}...`")
    meta_cols[1].caption(f"Retries: {response.get('retries_used', 0)}")
    warnings = response.get("warnings", [])
    meta_cols[2].caption(f"Warnings: {len(warnings)}")

    # Recommendations (R40.3)
    recs = response.get("recommendations", [])
    if recs:
        for i, rec in enumerate(recs):
            render_recommendation(rec, i)
    else:
        st.info("No recommendations returned.")

    # Warnings
    if warnings:
        with st.expander(f"⚠️ Warnings ({len(warnings)})"):
            for w in warnings:
                st.markdown(f"- {w}")


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------

if "messages" not in st.session_state:
    st.session_state.messages = []

if "notifications" not in st.session_state:
    st.session_state.notifications = []


# ---------------------------------------------------------------------------
# Main chat area (R40.2, R40.4)
# ---------------------------------------------------------------------------

st.title("🏦 SmartBanker AI Agent")
st.caption(f"Mode: **{mode}** | User: **{user_id}**")

# Display conversation history (R40.4)
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if msg["role"] == "user":
            st.markdown(msg["content"])
        else:
            render_response(msg["content"])

# Chat input (R40.2)
if prompt := st.chat_input("Ask your personal banker anything..."):
    # Show user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Call agent
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            response = call_agent(prompt)
        render_response(response)
        st.session_state.messages.append({"role": "assistant", "content": response})


# ---------------------------------------------------------------------------
# Service request handling (R40.10)
# ---------------------------------------------------------------------------

if sr_submit and sr_description:
    with st.chat_message("user"):
        st.markdown(f"📋 **Service Request:** {sr_type} — {sr_description}")
    st.session_state.messages.append({"role": "user", "content": f"📋 Service Request: {sr_type} — {sr_description}"})

    with st.chat_message("assistant"):
        with st.spinner("Processing service request..."):
            if mode == "Local":
                response = _call_service_request_local(user_id, sr_type, sr_description)
            else:
                response = call_agent(f"Service request: {sr_type} - {sr_description}")
        render_response(response)
        st.session_state.messages.append({"role": "assistant", "content": response})


# ---------------------------------------------------------------------------
# Proactive notifications panel (R40.9)
# ---------------------------------------------------------------------------

if check_notifications:
    with st.spinner("Checking for proactive opportunities..."):
        if mode == "Local":
            notifications = _call_proactive_local(user_id)
        else:
            notifications = []  # Remote mode would call a dedicated endpoint

    st.session_state.notifications = notifications

if st.session_state.notifications:
    st.divider()
    st.subheader("🔔 Proactive Notifications")
    for notif in st.session_state.notifications:
        priority_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(notif.get("priority", ""), "⚪")
        with st.container(border=True):
            st.markdown(f"{priority_icon} **{notif.get('opportunity_type', '').replace('_', ' ').title()}**")
            st.markdown(notif.get("message", ""))
            st.caption(f"Priority: {notif.get('priority', 'N/A')} | Tier-specific: {notif.get('tier_specific', False)}")
