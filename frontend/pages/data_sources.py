"""Data Sources management page."""

from __future__ import annotations

import json
import logging
from typing import Any

import streamlit as st

logger = logging.getLogger(__name__)

try:
    from config.settings import Settings
except ImportError:
    Settings = None

try:
    from integrations.snowflake_client import SnowflakeClient
except ImportError:
    SnowflakeClient = None


def _init_state() -> None:
    """Initialize session state for data sources page."""
    defaults = {
        "ds_connection_status": None,
        "ds_databases": [],
        "ds_schemas": [],
        "ds_tables": [],
        "ds_columns": [],
        "ds_selected_db": None,
        "ds_selected_schema": None,
        "ds_selected_table": None,
        "ds_manual_metadata": {},
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def render_data_sources_page() -> None:
    """Render the data sources management page."""
    _init_state()

    st.markdown("## 🗄️ Data Sources")
    st.markdown("Connect to Snowflake or upload source metadata for your dbt project.")
    st.markdown("---")

    tab_sf, tab_manual, tab_catalog = st.tabs([
        "❄️ Snowflake Connection",
        "📤 Manual Upload",
        "📖 Source Catalog",
    ])

    with tab_sf:
        _render_snowflake_tab()

    with tab_manual:
        _render_manual_upload_tab()

    with tab_catalog:
        _render_catalog_tab()


def _render_snowflake_tab() -> None:
    """Render Snowflake connection and schema browser."""
    st.markdown("### ❄️ Snowflake Connection")

    # Connection form
    with st.form("snowflake_connection_form"):
        st.markdown("**Connection Details** (also configurable in Settings)")
        col1, col2 = st.columns(2)
        with col1:
            sf_account = st.text_input("Account", key="ds_sf_account")
            sf_user = st.text_input("Username", key="ds_sf_user")
            sf_role = st.text_input("Role", value="SYSADMIN", key="ds_sf_role")
        with col2:
            sf_warehouse = st.text_input("Warehouse", key="ds_sf_warehouse")
            sf_password = st.text_input("Password", type="password", key="ds_sf_password")
            sf_database = st.text_input("Database (optional)", key="ds_sf_database")

        submitted = st.form_submit_button("🔌 Test Connection", type="primary")

    if submitted:
        if not sf_account or not sf_user or not sf_password:
            st.error("Account, Username, and Password are required.", icon="⚠️")
        elif SnowflakeClient is not None:
            with st.spinner("Testing Snowflake connection..."):
                try:
                    client = SnowflakeClient(
                        account=sf_account,
                        user=sf_user,
                        password=sf_password,
                        role=sf_role,
                        warehouse=sf_warehouse,
                        database=sf_database,
                    )
                    if client.test_connection():
                        st.session_state.ds_connection_status = "connected"
                        st.session_state["snowflake_connected"] = True
                        curr_state = st.session_state.get("current_project_state", {})
                        curr_state["snowflake_connected"] = True
                        st.session_state["current_project_state"] = curr_state
                        st.success("✅ Successfully connected to Snowflake!", icon="❄️")
                    else:
                        st.session_state.ds_connection_status = "failed"
                        st.session_state["snowflake_connected"] = False
                        st.error("Connection test failed.", icon="❌")
                except Exception as e:
                    st.session_state.ds_connection_status = "failed"
                    st.error(f"Connection error: {e}", icon="❌")
                    logger.exception("Snowflake connection error")
        else:
            st.warning("Snowflake client not available. Install snowflake-connector-python.", icon="⚠️")

    # Schema browser
    if st.session_state.ds_connection_status == "connected":
        st.markdown("---")
        st.markdown("### 🔍 Schema Browser")
        _render_schema_browser()


def _render_schema_browser() -> None:
    """Render the Snowflake schema browser: databases → schemas → tables → columns."""
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("**Databases**")
        databases = st.session_state.get("ds_databases", [])
        if not databases:
            st.info("Click 'Fetch Databases' to load.")
            if st.button("📥 Fetch Databases"):
                # In a real implementation this would call SnowflakeClient
                st.session_state.ds_databases = ["ANALYTICS", "RAW", "STAGING"]
                st.rerun()
        else:
            selected_db = st.radio(
                "Select Database",
                databases,
                key="ds_db_radio",
                label_visibility="collapsed",
            )
            st.session_state.ds_selected_db = selected_db

    with col2:
        st.markdown("**Schemas**")
        if st.session_state.ds_selected_db:
            schemas = st.session_state.get("ds_schemas", [])
            if schemas:
                selected_schema = st.radio(
                    "Select Schema",
                    schemas,
                    key="ds_schema_radio",
                    label_visibility="collapsed",
                )
                st.session_state.ds_selected_schema = selected_schema
            else:
                if st.button("📥 Fetch Schemas"):
                    st.info("Fetching schemas... (connect SnowflakeClient for real data)")
        else:
            st.caption("Select a database first.")

    with col3:
        st.markdown("**Tables**")
        if st.session_state.ds_selected_schema:
            tables = st.session_state.get("ds_tables", [])
            if tables:
                selected_table = st.radio(
                    "Select Table",
                    tables,
                    key="ds_table_radio",
                    label_visibility="collapsed",
                )
                st.session_state.ds_selected_table = selected_table
            else:
                if st.button("📥 Fetch Tables"):
                    st.info("Fetching tables... (connect SnowflakeClient for real data)")
        else:
            st.caption("Select a schema first.")

    # Columns display
    if st.session_state.ds_selected_table:
        st.markdown("---")
        st.markdown(f"**Columns for `{st.session_state.ds_selected_table}`**")
        columns = st.session_state.get("ds_columns", [])
        if columns:
            import pandas as pd
            df = pd.DataFrame(columns)
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No column metadata loaded for this table.")


def _render_manual_upload_tab() -> None:
    """Render manual metadata upload section."""
    st.markdown("### 📤 Upload Source Metadata")
    st.markdown(
        "Upload files describing your source tables, columns, and data types. "
        "Supported formats: CSV, JSON, YAML."
    )

    uploaded_files = st.file_uploader(
        "Upload metadata files",
        type=["csv", "json", "yaml", "yml"],
        accept_multiple_files=True,
        key="ds_metadata_uploader",
    )

    if uploaded_files:
        for f in uploaded_files:
            try:
                content = f.read().decode("utf-8")
                st.session_state.ds_manual_metadata[f.name] = content
                st.success(f"✅ Loaded: {f.name} ({f.size / 1024:.1f} KB)")

                with st.expander(f"Preview: {f.name}"):
                    if f.name.endswith(".json"):
                        try:
                            st.json(json.loads(content))
                        except json.JSONDecodeError:
                            st.code(content, language="json")
                    elif f.name.endswith((".yml", ".yaml")):
                        st.code(content, language="yaml")
                    elif f.name.endswith(".csv"):
                        import pandas as pd
                        from io import StringIO
                        df = pd.read_csv(StringIO(content))
                        st.dataframe(df, use_container_width=True, hide_index=True)
                    else:
                        st.code(content)
            except Exception as e:
                st.error(f"Error reading {f.name}: {e}")

    # Store in project state
    if st.session_state.ds_manual_metadata:
        if st.button("💾 Save Metadata to Project", type="primary"):
            state = st.session_state.get("current_project_state", {})
            state["source_metadata_manual"] = st.session_state.ds_manual_metadata
            st.session_state["current_project_state"] = state
            st.success("Metadata saved to project state.", icon="✅")


def _render_catalog_tab() -> None:
    """Render the source catalog viewer."""
    st.markdown("### 📖 Source Catalog")

    state = st.session_state.get("current_project_state", {})
    catalog = state.get("source_catalog", {})

    if not catalog:
        st.info(
            "No source catalog available yet. Run the **Data Discovery** agent "
            "or upload metadata to populate the catalog.",
            icon="📂",
        )
        return

    # Display catalog
    tables = catalog.get("tables", [])
    if not tables:
        st.info("Catalog is empty.", icon="📂")
        return

    for table_info in tables:
        table_name = table_info.get("name", "unknown")
        schema_name = table_info.get("schema", "")
        db_name = table_info.get("database", "")
        full_name = ".".join(filter(None, [db_name, schema_name, table_name]))

        with st.expander(f"📊 {full_name}"):
            cols_data = table_info.get("columns", [])
            if cols_data:
                import pandas as pd
                df = pd.DataFrame(cols_data)
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.caption("No column metadata.")

            if table_info.get("row_count"):
                st.metric("Row Count", f"{table_info['row_count']:,}")
