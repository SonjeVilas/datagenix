"""Reusable agent status card component."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import streamlit as st


_STATUS_STYLES: dict[str, dict[str, str]] = {
    "waiting": {"class": "status-waiting", "icon": "⏳", "label": "Waiting"},
    "running": {"class": "status-running", "icon": "🔄", "label": "Running"},
    "completed": {"class": "status-completed", "icon": "✅", "label": "Completed"},
    "failed": {"class": "status-failed", "icon": "❌", "label": "Failed"},
    "error": {"class": "status-failed", "icon": "❌", "label": "Error"},
    "requires_approval": {"class": "status-approval", "icon": "⚠️", "label": "Requires Approval"},
}


def _format_duration(start: str | datetime | None, end: str | datetime | None) -> str:
    """Calculate and format duration between two timestamps."""
    if not start:
        return "—"
    try:
        if isinstance(start, str):
            start = datetime.fromisoformat(start)
        if end is None:
            end = datetime.now()
        elif isinstance(end, str):
            end = datetime.fromisoformat(end)
        delta = end - start
        total_seconds = int(delta.total_seconds())
        if total_seconds < 60:
            return f"{total_seconds}s"
        minutes, seconds = divmod(total_seconds, 60)
        if minutes < 60:
            return f"{minutes}m {seconds}s"
        hours, minutes = divmod(minutes, 60)
        return f"{hours}h {minutes}m"
    except (ValueError, TypeError):
        return "—"


def render_agent_card(agent_info: dict[str, Any]) -> None:
    """Render a single agent status card.

    Args:
        agent_info: Dictionary with keys:
            - name (str): Agent display name
            - description (str): Agent role description
            - status (str): One of waiting/running/completed/failed/error/requires_approval
            - start_time (str | None): ISO timestamp
            - end_time (str | None): ISO timestamp
            - output_summary (str | None): Brief output summary
            - error (str | None): Error message if failed
    """
    name = agent_info.get("name", "Unknown Agent")
    description = agent_info.get("description", "")
    status = agent_info.get("status", "waiting").lower().replace(" ", "_")
    start_time = agent_info.get("start_time")
    end_time = agent_info.get("end_time")
    output_summary = agent_info.get("output_summary", "")
    error = agent_info.get("error", "")

    style = _STATUS_STYLES.get(status, _STATUS_STYLES["waiting"])
    duration = _format_duration(start_time, end_time if status != "running" else None)

    with st.container():
        st.markdown(
            f"""
            <div class="agent-card">
                <div style="display:flex;justify-content:space-between;align-items:flex-start;">
                    <div>
                        <div class="agent-name">{style['icon']} {name}</div>
                        <div class="agent-description">{description}</div>
                    </div>
                    <span class="status-badge {style['class']}">{style['label']}</span>
                </div>
                <div class="agent-meta" style="margin-top:0.5rem;">
                    ⏱️ Duration: {duration}
                    {f' &nbsp;|&nbsp; 🕐 Started: {start_time[:19] if start_time else "—"}' if start_time else ''}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if error and status in ("failed", "error"):
            st.error(f"**Error:** {error}", icon="🚨")

        if output_summary and status == "completed":
            with st.expander("📄 Output Summary", expanded=False):
                st.markdown(output_summary)


def render_agent_grid(agents: list[dict[str, Any]], columns: int = 2) -> None:
    """Render a grid of agent status cards.

    Args:
        agents: List of agent info dicts (see render_agent_card).
        columns: Number of columns in the grid.
    """
    if not agents:
        st.info("No agents to display.", icon="ℹ️")
        return

    rows = [agents[i : i + columns] for i in range(0, len(agents), columns)]
    for row in rows:
        cols = st.columns(columns)
        for idx, agent in enumerate(row):
            with cols[idx]:
                render_agent_card(agent)
