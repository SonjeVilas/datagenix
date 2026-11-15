"""SQL Editor page with validation and formatting."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import streamlit as st

logger = logging.getLogger(__name__)

try:
    from backend.validator import Validator
except ImportError:
    Validator = None

try:
    import sqlglot
except ImportError:
    sqlglot = None


def _get_sql_files() -> dict[str, str]:
    """Get all SQL model files from project state."""
    state = st.session_state.get("current_project_state", {})
    models = state.get("generated_models", {})
    return {k: v for k, v in models.items() if k.endswith(".sql")} if isinstance(models, dict) else {}


def render_sql_editor_page() -> None:
    """Render the SQL editor page."""
    st.markdown("## 📊 SQL Editor")
    st.markdown("View, edit, validate, and format SQL model files.")
    st.markdown("---")

    sql_files = _get_sql_files()

    if not sql_files:
        st.info(
            "No SQL model files found. Generate a project first in **New Project**.",
            icon="📂",
        )
        return

    # Sidebar file selector
    col_sidebar, col_editor = st.columns([1, 3])

    with col_sidebar:
        st.markdown("### 📁 SQL Files")
        file_list = sorted(sql_files.keys())
        selected_file = st.radio(
            "Select a file",
            file_list,
            format_func=lambda x: f"📊 {Path(x).name}",
            key="sql_editor_file_select",
            label_visibility="collapsed",
        )

        # Model info
        if selected_file:
            st.markdown("---")
            st.markdown("**File Info**")
            content = sql_files[selected_file]
            st.caption(f"📄 {selected_file}")
            st.caption(f"📏 {len(content.splitlines())} lines")
            st.caption(f"💾 {len(content.encode('utf-8'))} bytes")

            # Parse dependencies
            _show_dependencies(content)

    with col_editor:
        if selected_file is None:
            st.info("Select a SQL file from the sidebar.", icon="👈")
            return

        content = sql_files[selected_file]
        st.markdown(f"### 📄 {Path(selected_file).name}")

        # Display code
        st.code(content, language="sql", line_numbers=True)

        st.markdown("---")

        # Edit area
        st.markdown("**✏️ Edit SQL**")
        edited_sql = st.text_area(
            "SQL Content",
            value=content,
            height=400,
            key=f"sql_edit_{selected_file}",
            label_visibility="collapsed",
        )

        # Action buttons
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            if st.button("✅ Validate", key="sql_validate", use_container_width=True):
                _validate_sql(edited_sql, selected_file)

        with col2:
            if st.button("🎨 Format", key="sql_format", use_container_width=True):
                formatted = _format_sql(edited_sql)
                if formatted:
                    st.session_state[f"sql_edit_{selected_file}"] = formatted
                    st.rerun()

        with col3:
            if st.button("💾 Save", key="sql_save", type="primary", use_container_width=True):
                _save_sql(selected_file, edited_sql)

        with col4:
            st.download_button(
                "⬇️ Download",
                data=edited_sql,
                file_name=Path(selected_file).name,
                key="sql_download",
                use_container_width=True,
            )


def _validate_sql(sql: str, filename: str) -> None:
    """Validate SQL content using sqlglot."""
    if sqlglot is not None:
        try:
            # Parse with Snowflake dialect
            parsed = sqlglot.transpile(sql, read="snowflake", error_level=sqlglot.ErrorLevel.RAISE)
            st.success(f"✅ SQL is valid! Parsed {len(parsed)} statement(s).", icon="✅")
        except sqlglot.errors.ParseError as e:
            st.error(f"❌ SQL Parse Error: {e}", icon="❌")
        except Exception as e:
            st.warning(f"⚠️ Validation warning: {e}", icon="⚠️")
    elif Validator is not None:
        try:
            validator = Validator()
            result = validator.validate_sql(sql, filename)
            if result.get("valid"):
                st.success("✅ SQL is valid!", icon="✅")
            else:
                for err in result.get("errors", []):
                    st.error(f"❌ {err}")
        except Exception as e:
            st.error(f"Validation error: {e}")
    else:
        st.warning(
            "No SQL validator available. Install `sqlglot` for SQL validation.",
            icon="⚠️",
        )


def _format_sql(sql: str) -> str | None:
    """Format SQL using sqlglot."""
    if sqlglot is not None:
        try:
            formatted = sqlglot.transpile(
                sql,
                read="snowflake",
                write="snowflake",
                pretty=True,
            )
            result = "\n\n".join(formatted)
            st.success("✅ SQL formatted successfully!", icon="🎨")
            return result
        except Exception as e:
            st.error(f"Format error: {e}", icon="❌")
            return None
    else:
        st.warning("Install `sqlglot` for SQL formatting.", icon="⚠️")
        return None


def _save_sql(filepath: str, content: str) -> None:
    """Save SQL content back to project state."""
    state = st.session_state.get("current_project_state", {})
    models = state.get("generated_models", {})
    if isinstance(models, dict):
        models[filepath] = content
        state["generated_models"] = models
        st.session_state["current_project_state"] = state
        st.success(f"💾 Saved {filepath}", icon="✅")
    else:
        st.error("Could not save: project state is invalid.", icon="❌")


def _show_dependencies(sql: str) -> None:
    """Parse and show model dependencies from SQL content."""
    import re

    st.markdown("**Dependencies**")

    # Find ref() calls
    refs = re.findall(r"{{\s*ref\(['\"](\w+)['\"]\)\s*}}", sql)
    sources = re.findall(r"{{\s*source\(['\"](\w+)['\"],\s*['\"](\w+)['\"]\)\s*}}", sql)

    if refs:
        st.markdown("**ref():**")
        for r in refs:
            st.caption(f"  → `{r}`")

    if sources:
        st.markdown("**source():**")
        for src, tbl in sources:
            st.caption(f"  → `{src}.{tbl}`")

    if not refs and not sources:
        st.caption("No dependencies found.")
