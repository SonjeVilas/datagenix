"""Main application dashboard and multi-page router for dbt Project Factory."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

import streamlit as st

from backend.database import Database
from frontend.components.workflow_viz import AGENT_PIPELINE, render_progress_bar
from frontend.pages import (
    render_agents_page,
    render_data_sources_page,
    render_execution_history_page,
    render_new_project_page,
    render_project_explorer_page,
    render_settings_page,
    render_sql_editor_page,
    render_validation_center_page,
    render_yaml_editor_page,
)
from frontend.styles import inject_metric_card, load_custom_css

logger = logging.getLogger(__name__)


def _init_global_state() -> None:
    """Initialize top-level application session state variables."""
    if "current_project_state" not in st.session_state:
        st.session_state["current_project_state"] = {}
    if "db" not in st.session_state:
        st.session_state["db"] = Database()


def render_dashboard_home(db: Database) -> None:
    """Render the executive overview dashboard."""
    st.markdown("## 🏭 dbt Project Factory")
    st.markdown(
        "Autonomous multi-agent data engineering platform powered by **Google Gemini** "
        "and **LangGraph**. Converts natural-language requirements into production-grade dbt projects."
    )
    st.markdown("---")

    # 1. Top Metrics Bar
    metrics = db.get_metrics()
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        inject_metric_card("Total Projects", metrics.get("total_projects", 0), "Generated projects", "blue")
    with c2:
        inject_metric_card(
            "Validations Passed",
            metrics.get("successful_validations", 0),
            "100% syntactic & semantic",
            "green",
        )
    with c3:
        inject_metric_card(
            "Validations Failed",
            metrics.get("failed_validations", 0),
            "Self-healing targets",
            "red" if metrics.get("failed_validations", 0) > 0 else "blue",
        )
    with c4:
        inject_metric_card(
            "Agent Executions",
            metrics.get("total_agent_executions", 0),
            "Across 11 specialized roles",
            "purple",
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # 2. Current Project Quick View
    current_state = st.session_state.get("current_project_state", {})
    proj_name = current_state.get("project_name")
    if proj_name:
        st.markdown(f"### 📍 Active Workspace: **{proj_name}**")
        agent_statuses = current_state.get("agent_status", {})
        agents_data = [
            {"id": a["id"], "name": a["name"], "status": agent_statuses.get(a["id"], {}).get("status", "waiting")}
            for a in AGENT_PIPELINE
        ]
        render_progress_bar(agents_data)
        st.markdown("---")

    # 3. Two-column Layout: Recent Projects & Quick Actions
    col_left, col_right = st.columns([2, 1])

    with col_left:
        st.markdown("### 📁 Recent Projects")
        projects = db.list_projects(limit=10)
        if projects:
            table_data = []
            for p in projects:
                table_data.append({
                    "Project Name": p["project_name"],
                    "Status": p["status"].capitalize(),
                    "Created": p["created_at"][:19].replace("T", " "),
                    "Output Path": p["output_path"] or "In Memory",
                })
            st.dataframe(table_data, use_container_width=True)
        else:
            st.info("No projects generated yet. Click **Create New Project** to start.")

    with col_right:
        st.markdown("### ⚡ Quick Actions")
        if st.button("🚀 Create New Project", use_container_width=True, type="primary"):
            st.session_state["nav_selection"] = "🚀 New Project"
            st.rerun()

        if st.button("🤖 Inspect AI Agents", use_container_width=True):
            st.session_state["nav_selection"] = "🤖 AI Agents"
            st.rerun()

        if st.button("🔧 API Key & Settings", use_container_width=True):
            st.session_state["nav_selection"] = "🔧 Settings"
            st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("### ℹ️ Architecture Summary")
        st.caption(
            "• **11 Autonomous Agents** orchestrated via LangGraph\n"
            "• **Layers**: Staging → Intermediate → Marts (Facts & Dims)\n"
            "• **Dialect**: Snowflake SQL with CTE pattern & ref()/source()\n"
            "• **Validation**: sqlglot + pyyaml + dbt compile checks\n"
            "• **Self-Healing**: Fixer agent auto-repairs validation errors"
        )


def main() -> None:
    """Streamlit entry point."""
    st.set_page_config(
        page_title="dbt Project Factory",
        page_icon="🏭",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    load_custom_css()
    _init_global_state()
    db: Database = st.session_state["db"]

    # Sidebar Navigation
    pages = [
        "📊 Dashboard",
        "🚀 New Project",
        "🤖 AI Agents",
        "🗄️ Data Sources",
        "📁 Project Explorer",
        "📝 SQL Editor",
        "⚙️ YAML Editor",
        "🛡️ Validation Center",
        "📜 Execution History",
        "🔧 Settings",
    ]

    if "nav_selection" not in st.session_state:
        st.session_state["nav_selection"] = pages[0]

    with st.sidebar:
        st.markdown("### 🏭 dbt Project Factory")
        st.caption("v1.0.0 • Multi-Agent AI Platform")
        st.markdown("---")

        selected = st.radio(
            "Navigation",
            options=pages,
            index=pages.index(st.session_state["nav_selection"])
            if st.session_state["nav_selection"] in pages
            else 0,
            label_visibility="collapsed",
        )
        st.session_state["nav_selection"] = selected

        st.markdown("---")
        # Warehouse status badge
        curr_state = st.session_state.get("current_project_state", {})
        if "snowflake_connected" in st.session_state:
            sf_connected = bool(st.session_state["snowflake_connected"])
        elif curr_state.get("snowflake_connected") is not None:
            sf_connected = bool(curr_state.get("snowflake_connected"))
        else:
            try:
                from config.settings import get_settings
                sf_connected = get_settings().snowflake_configured
            except Exception:
                sf_connected = False
            st.session_state["snowflake_connected"] = sf_connected

        if sf_connected:
            st.success("❄️ Snowflake: Connected", icon="✅")
        else:
            st.caption("❄️ Snowflake: Disconnected (Offline mode)")

        # Active project indicator
        active_proj = curr_state.get("project_name")
        if active_proj:
            st.caption(f"Active: **{active_proj}**")

    # Routing
    if selected == "📊 Dashboard":
        render_dashboard_home(db)
    elif selected == "🚀 New Project":
        render_new_project_page()
    elif selected == "🤖 AI Agents":
        render_agents_page()
    elif selected == "🗄️ Data Sources":
        render_data_sources_page()
    elif selected == "📁 Project Explorer":
        render_project_explorer_page()
    elif selected == "📝 SQL Editor":
        render_sql_editor_page()
    elif selected == "⚙️ YAML Editor":
        render_yaml_editor_page()
    elif selected == "🛡️ Validation Center":
        render_validation_center_page()
    elif selected == "📜 Execution History":
        render_execution_history_page()
    elif selected == "🔧 Settings":
        render_settings_page()


if __name__ == "__main__":
    main()

