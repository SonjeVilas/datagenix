"""YAML Editor page with validation."""

from __future__ import annotations

import logging
from pathlib import Path

import streamlit as st

logger = logging.getLogger(__name__)

try:
    import yaml
except ImportError:
    yaml = None


def _get_yaml_files() -> dict[str, str]:
    """Get all YAML files from project state or disk."""
    state = st.session_state.get("current_project_state", {})
    yaml_files = state.get("generated_yaml", {})
    res = (
        {k: v for k, v in yaml_files.items() if k.endswith((".yml", ".yaml"))}
        if isinstance(yaml_files, dict)
        else {}
    )

    # If empty, check disk output directory
    if not res:
        output_path = state.get("project_output_path")
        if output_path and Path(output_path).exists():
            root_p = Path(output_path)
            for p in root_p.rglob("*.yml"):
                try:
                    rel = str(p.relative_to(root_p)).replace("\\", "/")
                    res[rel] = p.read_text(encoding="utf-8")
                except Exception:
                    pass
            for p in root_p.rglob("*.yaml"):
                try:
                    rel = str(p.relative_to(root_p)).replace("\\", "/")
                    res[rel] = p.read_text(encoding="utf-8")
                except Exception:
                    pass

    return res


def render_yaml_editor_page() -> None:
    """Render the YAML editor page."""
    st.markdown("## 📋 YAML Editor")
    st.markdown("View, edit, and validate dbt YAML configuration files.")
    st.markdown("---")

    yaml_files = _get_yaml_files()

    if not yaml_files:
        st.info(
            "No YAML files found. Generate a project first in **New Project**.",
            icon="📂",
        )
        return

    # File selector
    col_sidebar, col_editor = st.columns([1, 3])

    with col_sidebar:
        st.markdown("### 📁 YAML Files")
        file_list = sorted(yaml_files.keys())
        selected_file = st.radio(
            "Select a file",
            file_list,
            format_func=lambda x: f"📋 {Path(x).name}",
            key="yaml_editor_file_select",
            label_visibility="collapsed",
        )

        if selected_file:
            st.markdown("---")
            st.markdown("**File Info**")
            content = yaml_files[selected_file]
            st.caption(f"📄 {selected_file}")
            st.caption(f"📏 {len(content.splitlines())} lines")
            st.caption(f"💾 {len(content.encode('utf-8'))} bytes")

    with col_editor:
        if selected_file is None:
            st.info("Select a YAML file from the sidebar.", icon="👈")
            return

        content = yaml_files[selected_file]
        st.markdown(f"### 📄 {Path(selected_file).name}")

        # Display
        st.code(content, language="yaml", line_numbers=True)

        st.markdown("---")

        # Edit
        st.markdown("**✏️ Edit YAML**")
        edited_yaml = st.text_area(
            "YAML Content",
            value=content,
            height=400,
            key=f"yaml_edit_{selected_file}",
            label_visibility="collapsed",
        )

        # Action buttons
        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button("✅ Validate YAML", key="yaml_validate", width='stretch'):
                _validate_yaml(edited_yaml)

        with col2:
            if st.button("💾 Save", key="yaml_save", type="primary", width='stretch'):
                _save_yaml(selected_file, edited_yaml)

        with col3:
            st.download_button(
                "⬇️ Download",
                data=edited_yaml,
                file_name=Path(selected_file).name,
                key="yaml_download",
                width='stretch',
            )

        # Parsed preview
        if yaml is not None:
            with st.expander("🔍 Parsed Structure Preview"):
                try:
                    parsed = yaml.safe_load(edited_yaml)
                    if parsed:
                        st.json(parsed)
                    else:
                        st.caption("Empty YAML document.")
                except yaml.YAMLError as e:
                    st.error(f"Parse error: {e}")


def _validate_yaml(content: str) -> None:
    """Validate YAML syntax."""
    if yaml is not None:
        try:
            parsed = yaml.safe_load(content)
            if parsed is None:
                st.warning("YAML is valid but empty.", icon="⚠️")
            else:
                st.success(f"✅ Valid YAML! Contains {type(parsed).__name__} with {len(parsed) if hasattr(parsed, '__len__') else 1} top-level entries.", icon="✅")
        except yaml.YAMLError as e:
            st.error(f"❌ YAML Error: {e}", icon="❌")
    else:
        st.warning("PyYAML not installed. Cannot validate.", icon="⚠️")


def _save_yaml(filepath: str, content: str) -> None:
    """Save YAML content back to project state."""
    state = st.session_state.get("current_project_state", {})
    yaml_files = state.get("generated_yaml", {})
    if isinstance(yaml_files, dict):
        yaml_files[filepath] = content
        state["generated_yaml"] = yaml_files
        st.session_state["current_project_state"] = state
        st.success(f"💾 Saved {filepath}", icon="✅")
    else:
        st.error("Could not save: project state is invalid.", icon="❌")
