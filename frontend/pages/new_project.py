"""New Project creation wizard page."""

from __future__ import annotations

import logging
from typing import Any

import streamlit as st

logger = logging.getLogger(__name__)

# Conditional imports for backend modules
try:
    from config.settings import Settings
except ImportError:
    Settings = None

try:
    from backend.state import ProjectState
except ImportError:
    ProjectState = None

try:
    from backend.orchestrator import run_pipeline, create_graph
except ImportError:
    run_pipeline = None
    create_graph = None


def _init_session_state() -> None:
    """Initialize session state for the new project page."""
    defaults = {
        "np_project_name": "",
        "np_description": "",
        "np_requirements": "",
        "np_target_schema": "analytics",
        "np_materialization": "view",
        "np_snowflake_enabled": False,
        "np_pipeline_running": False,
        "np_clarification_messages": [],
        "np_uploaded_requirements": None,
        "np_uploaded_metadata": None,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


def render_new_project_page() -> None:
    """Render the guided project creation wizard."""
    _init_session_state()

    st.markdown("## 🚀 Create New dbt Project")
    st.markdown("Follow the guided wizard to generate a complete dbt project from your business requirements.")
    st.markdown("---")

    # Step 1: Project Info
    st.markdown("### 📝 Step 1: Project Information")
    col1, col2 = st.columns(2)
    with col1:
        st.session_state.np_project_name = st.text_input(
            "Project Name *",
            value=st.session_state.np_project_name,
            placeholder="e.g., customer_analytics",
            help="Use lowercase with underscores. This will be the dbt project name.",
        )
    with col2:
        st.session_state.np_description = st.text_input(
            "Project Description",
            value=st.session_state.np_description,
            placeholder="e.g., Customer analytics data warehouse models",
        )

    st.markdown("---")

    # Step 2: Business Requirements
    st.markdown("### 📋 Step 2: Business Requirements")
    st.session_state.np_requirements = st.text_area(
        "Business Requirements *",
        value=st.session_state.np_requirements,
        height=250,
        placeholder=(
            "Describe your data transformation requirements in detail.\n\n"
            "Example:\n"
            "- We have customer orders from our e-commerce platform in Snowflake\n"
            "- Need to build staging models for raw tables: orders, customers, products\n"
            "- Create intermediate models for order line items with product details\n"
            "- Build mart models for: daily revenue, customer lifetime value, product performance\n"
            "- Apply SCD Type 2 for customer dimension\n"
            "- Include data quality tests for primary keys and not-null constraints"
        ),
        help="Be as detailed as possible. The AI agents will parse these requirements.",
    )

    # File upload for requirements docs
    st.markdown("**📎 Or upload a requirements document:**")
    uploaded_req = st.file_uploader(
        "Upload requirements (TXT, PDF)",
        type=["txt", "pdf"],
        key="np_req_uploader",
        help="Upload a text or PDF file containing your requirements.",
    )
    if uploaded_req is not None:
        st.session_state.np_uploaded_requirements = uploaded_req
        if uploaded_req.type == "text/plain":
            try:
                content = uploaded_req.read().decode("utf-8")
                if not st.session_state.np_requirements:
                    st.session_state.np_requirements = content
                st.success(f"📄 Loaded requirements from {uploaded_req.name}")
            except Exception as e:
                st.error(f"Error reading file: {e}")
        else:
            st.info("📄 PDF uploaded. Content will be extracted during analysis.")

    st.markdown("---")

    # Step 3: Source Metadata
    st.markdown("### 🗃️ Step 3: Source Data")
    tab_snowflake, tab_manual = st.tabs(["❄️ Snowflake Connection", "📤 Manual Upload"])

    with tab_snowflake:
        st.session_state.np_snowflake_enabled = st.toggle(
            "Enable Snowflake Connection",
            value=st.session_state.np_snowflake_enabled,
            help="Connect to Snowflake to automatically discover source metadata.",
        )
        if st.session_state.np_snowflake_enabled:
            st.info(
                "Snowflake connection details are configured in **Settings**. "
                "The Data Discovery agent will query your Snowflake account for schema metadata.",
                icon="ℹ️",
            )

    with tab_manual:
        st.markdown("Upload source metadata files describing your data sources:")
        uploaded_meta = st.file_uploader(
            "Upload metadata (CSV, JSON, YAML)",
            type=["csv", "json", "yaml", "yml"],
            key="np_meta_uploader",
            accept_multiple_files=True,
            help="Upload files describing your source tables, columns, and data types.",
        )
        if uploaded_meta:
            st.session_state.np_uploaded_metadata = uploaded_meta
            for f in uploaded_meta:
                st.success(f"✅ Uploaded: {f.name} ({f.size / 1024:.1f} KB)")

    st.markdown("---")

    # Step 4: Project Configuration
    st.markdown("### ⚙️ Step 4: Configuration")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.session_state.np_target_schema = st.text_input(
            "Target Schema",
            value=st.session_state.np_target_schema,
            help="Default target schema for dbt models.",
        )
    with col2:
        st.session_state.np_materialization = st.selectbox(
            "Default Materialization",
            options=["view", "table", "incremental", "ephemeral"],
            index=["view", "table", "incremental", "ephemeral"].index(
                st.session_state.np_materialization
            ),
            help="Default materialization strategy for models.",
        )
    with col3:
        st.selectbox(
            "dbt Version Target",
            options=["1.7.x", "1.8.x", "1.9.x"],
            index=0,
            key="np_dbt_version",
        )

    st.markdown("---")

    # Action buttons
    st.markdown("### 🎯 Launch")
    col1, col2, col3 = st.columns([2, 1, 1])

    with col1:
        analyze_clicked = st.button(
            "🤖 Analyze Requirements & Generate Project",
            type="primary",
            use_container_width=True,
            disabled=st.session_state.np_pipeline_running,
        )
    with col2:
        if st.button("🔄 Reset Form", use_container_width=True):
            for key in list(st.session_state.keys()):
                if key.startswith("np_"):
                    del st.session_state[key]
            st.rerun()
    with col3:
        if st.button("📋 Preview Config", use_container_width=True):
            _show_config_preview()

    # Handle analyze button
    if analyze_clicked:
        if not st.session_state.np_project_name:
            st.error("Please provide a project name.", icon="⚠️")
            return
        if not st.session_state.np_requirements:
            st.error("Please provide business requirements.", icon="⚠️")
            return
        _run_analysis()

    # Clarification conversation
    if st.session_state.np_clarification_messages:
        st.markdown("---")
        st.markdown("### 💬 Clarification Conversation")
        for msg in st.session_state.np_clarification_messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        user_input = st.chat_input("Respond to clarification questions...")
        if user_input:
            st.session_state.np_clarification_messages.append(
                {"role": "user", "content": user_input}
            )
            st.rerun()


def _show_config_preview() -> None:
    """Show a preview of the project configuration."""
    config = {
        "project_name": st.session_state.np_project_name or "(not set)",
        "description": st.session_state.np_description or "(not set)",
        "requirements_length": f"{len(st.session_state.np_requirements)} characters",
        "snowflake_enabled": st.session_state.np_snowflake_enabled,
        "target_schema": st.session_state.np_target_schema,
        "materialization": st.session_state.np_materialization,
    }
    st.json(config)


def _run_analysis() -> None:
    """Trigger the agent pipeline for project generation."""
    st.session_state.np_pipeline_running = True

    # Build initial state
    initial_state: dict[str, Any] = {
        "project_name": st.session_state.np_project_name,
        "project_description": st.session_state.np_description,
        "business_requirements": st.session_state.np_requirements,
        "snowflake_connected": st.session_state.np_snowflake_enabled,
        "target_schema": st.session_state.np_target_schema,
        "default_materialization": st.session_state.np_materialization,
    }

    # Process uploaded metadata files
    if st.session_state.np_uploaded_metadata:
        metadata_contents: dict[str, str] = {}
        for f in st.session_state.np_uploaded_metadata:
            try:
                content = f.read().decode("utf-8")
                metadata_contents[f.name] = content
            except Exception as e:
                st.warning(f"Could not read {f.name}: {e}")
        initial_state["source_metadata_manual"] = metadata_contents

    # Run the pipeline
    if run_pipeline is not None:
        with st.spinner("🤖 AI Agents are analyzing your requirements and generating the dbt project..."):
            try:
                result = run_pipeline(initial_state)
                st.session_state.np_pipeline_running = False
                if result:
                    st.session_state["current_project_state"] = result
                    st.success(
                        "✅ Project generation complete! Navigate to **Project Explorer** to view your files.",
                        icon="🎉",
                    )
                    # Check for clarification questions
                    spec = result.get("project_specification", {})
                    questions = spec.get("clarification_questions", [])
                    if questions:
                        st.session_state.np_clarification_messages.append({
                            "role": "assistant",
                            "content": "I have some clarification questions:\n\n"
                            + "\n".join(f"- {q}" for q in questions),
                        })
            except Exception as e:
                st.session_state.np_pipeline_running = False
                st.error(f"Pipeline execution failed: {e}", icon="🚨")
                logger.exception("Pipeline execution error")
    else:
        st.session_state.np_pipeline_running = False
        st.warning(
            "Backend orchestrator not available. Please ensure all backend modules are installed.",
            icon="⚠️",
        )
