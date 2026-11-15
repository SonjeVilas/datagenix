"""Execution History page."""

from __future__ import annotations

import logging
from typing import Any

import streamlit as st

logger = logging.getLogger(__name__)

try:
    from backend.database import Database
except ImportError:
    Database = None


def render_execution_history_page() -> None:
    """Render the execution history page."""
    st.markdown("## 📜 Execution History")
    st.markdown("Browse past project generation runs.")
    st.markdown("---")

    history = _load_history()

    if not history:
        st.info("No execution history yet. Generate a project to see results here.", icon="📜")
        return

    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    total = len(history)
    successful = sum(1 for h in history if h.get("status") == "completed")
    failed = sum(1 for h in history if h.get("status") == "failed")
    in_progress = sum(1 for h in history if h.get("status") == "running")

    with col1:
        st.metric("Total Runs", total)
    with col2:
        st.metric("Successful", successful)
    with col3:
        st.metric("Failed", failed)
    with col4:
        st.metric("In Progress", in_progress)

    st.markdown("---")

    # History table
    st.markdown("### 📋 Past Generations")

    # Build table data
    import pandas as pd

    table_data = []
    for h in history:
        table_data.append({
            "Project": h.get("project_name", "Untitled"),
            "Date": h.get("timestamp", "Unknown"),
            "Status": h.get("status", "unknown"),
            "Agents Run": h.get("agents_completed", 0),
            "Validation": "✅ Pass" if h.get("validation_passed") else "❌ Fail",
            "Duration": h.get("duration", "—"),
        })

    df = pd.DataFrame(table_data)
    st.dataframe(
        df,
        width='stretch',
        hide_index=True,
        column_config={
            "Status": st.column_config.TextColumn("Status", width="small"),
            "Validation": st.column_config.TextColumn("Validation", width="small"),
        },
    )

    # Detail view
    st.markdown("---")
    st.markdown("### 🔍 View Details")
    if history:
        selected_idx = st.selectbox(
            "Select a run to view",
            range(len(history)),
            format_func=lambda i: (
                f"{history[i].get('project_name', 'Untitled')} — "
                f"{history[i].get('timestamp', 'Unknown')}"
            ),
            key="history_detail_select",
        )

        if selected_idx is not None:
            entry = history[selected_idx]
            _render_history_detail(entry)


def _load_history() -> list[dict[str, Any]]:
    """Load execution history from database or session state."""
    # Try database first
    if Database is not None:
        try:
            db = Database()
            records = db.get_all_runs()
            if records:
                return records
        except Exception as e:
            logger.warning(f"Could not load history from database: {e}")

    # Fall back to session state
    state = st.session_state.get("current_project_state", {})
    exec_history = state.get("execution_history", [])
    return exec_history if isinstance(exec_history, list) else []


def _render_history_detail(entry: dict[str, Any]) -> None:
    """Render detailed view of a history entry."""
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Project Details**")
        st.markdown(f"- **Name:** {entry.get('project_name', 'Untitled')}")
        st.markdown(f"- **Description:** {entry.get('project_description', '—')}")
        st.markdown(f"- **Date:** {entry.get('timestamp', 'Unknown')}")
        st.markdown(f"- **Duration:** {entry.get('duration', '—')}")
        st.markdown(f"- **Status:** {entry.get('status', 'unknown')}")

    with col2:
        st.markdown("**Execution Summary**")
        st.markdown(f"- **Agents Completed:** {entry.get('agents_completed', 0)}")
        st.markdown(f"- **Models Generated:** {entry.get('models_count', 0)}")
        st.markdown(f"- **Validation:** {'Pass' if entry.get('validation_passed') else 'Fail'}")
        st.markdown(f"- **Errors:** {entry.get('error_count', 0)}")

    # Load project button
    if st.button("📂 Load This Project", key=f"load_project_{entry.get('timestamp', '')}"):
        project_state = entry.get("state")
        if project_state:
            st.session_state["current_project_state"] = project_state
            st.success("Project loaded! Navigate to Project Explorer to view files.", icon="✅")
        else:
            st.warning("Project state data not available for this run.", icon="⚠️")
