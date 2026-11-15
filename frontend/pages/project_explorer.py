"""Project Explorer page — file browser and editor."""

from __future__ import annotations

import io
import logging
import os
import zipfile
from pathlib import Path
from typing import Any

import streamlit as st

from frontend.components.project_tree import render_project_tree
from frontend.components.code_viewer import render_single_file

logger = logging.getLogger(__name__)

try:
    from backend.file_manager import FileManager
except ImportError:
    FileManager = None

try:
    from config.settings import Settings
except ImportError:
    Settings = None


def _get_project_files() -> dict[str, str]:
    """Gather all generated project files from session state or disk."""
    state = st.session_state.get("current_project_state", {})
    all_files: dict[str, str] = {}

    # Merge generated models, YAML, tests, and docs
    for key in ("generated_models", "generated_yaml", "generated_tests", "generated_docs"):
        files = state.get(key, {})
        if isinstance(files, dict):
            all_files.update(files)

    # Fallback to scanning disk if in-memory is empty
    output_path = state.get("project_output_path")
    if not all_files and output_path and os.path.isdir(output_path):
        root_p = Path(output_path)
        for p in root_p.rglob("*"):
            if p.is_file() and not p.name.startswith("."):
                try:
                    rel = str(p.relative_to(root_p)).replace("\\", "/")
                    all_files[rel] = p.read_text(encoding="utf-8")
                except Exception:
                    pass

    return all_files


def _get_project_path() -> str | None:
    """Get the path to the generated project on disk."""
    state = st.session_state.get("current_project_state", {})
    output_path = state.get("project_output_path")
    if output_path and os.path.isdir(output_path):
        return output_path
    return None


def _create_zip(files: dict[str, str], project_name: str) -> bytes:
    """Create a ZIP archive from file dict."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for filepath, content in sorted(files.items()):
            arcname = f"{project_name}/{filepath}"
            zf.writestr(arcname, content)
    return buffer.getvalue()


def render_project_explorer_page() -> None:
    """Render the project file explorer page."""
    st.markdown("## 📁 Project Explorer")
    st.markdown("Browse, view, and edit generated dbt project files.")
    st.markdown("---")

    all_files = _get_project_files()
    project_path = _get_project_path()
    project_name = st.session_state.get("current_project_state", {}).get(
        "project_name", "dbt_project"
    )

    if not all_files and not project_path:
        st.info(
            "No project files generated yet. Go to **New Project** to create one.",
            icon="📂",
        )
        return

    # Download controls
    col_dl1, col_dl2 = st.columns([1, 3])
    with col_dl1:
        if all_files:
            zip_bytes = _create_zip(all_files, project_name)
            st.download_button(
                "📦 Download Project ZIP",
                data=zip_bytes,
                file_name=f"{project_name}.zip",
                mime="application/zip",
                width='stretch',
            )
    with col_dl2:
        st.metric("Total Files", len(all_files))

    st.markdown("---")

    # Two-column layout: tree on left, viewer on right
    col_tree, col_viewer = st.columns([1, 2])

    with col_tree:
        if project_path:
            selected = render_project_tree(
                root_path=project_path,
                project_name=project_name,
                key_prefix="explorer_tree",
            )
        else:
            selected = render_project_tree(
                files=all_files,
                project_name=project_name,
                key_prefix="explorer_tree",
            )

    with col_viewer:
        if selected:
            _render_file_viewer(selected, all_files, project_path)
        else:
            st.info("Select a file from the tree to view its contents.", icon="👈")


def _render_file_viewer(
    filepath: str,
    files: dict[str, str],
    project_path: str | None,
) -> None:
    """Render the file content viewer and editor."""
    content: str | None = None

    # Try to get content from in-memory files dict
    if filepath in files:
        content = files[filepath]
    elif os.path.isfile(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
        except (FileNotFoundError, PermissionError, UnicodeDecodeError) as e:
            st.error(f"Cannot read file: {e}", icon="❌")
            return
    elif project_path:
        # Check potential disk locations safely without duplicate folder joins
        candidates = [
            os.path.join(project_path, filepath),
        ]
        base_name = os.path.basename(project_path)
        if base_name and base_name in filepath:
            try:
                candidates.append(os.path.join(project_path, os.path.relpath(filepath, base_name)))
            except ValueError:
                pass

        for cand in candidates:
            if cand and os.path.isfile(cand):
                try:
                    with open(cand, "r", encoding="utf-8") as f:
                        content = f.read()
                    break
                except (FileNotFoundError, PermissionError, UnicodeDecodeError) as e:
                    st.error(f"Cannot read file: {e}", icon="❌")
                    return

    if content is None:
        st.warning(f"File content not found: {filepath}", icon="⚠️")
        return

    st.markdown(f"### 📄 {Path(filepath).name}")

    # View/Edit toggle
    edit_mode = st.toggle("✏️ Edit Mode", key=f"edit_toggle_{filepath}")

    if edit_mode:
        edited_content = st.text_area(
            "File content",
            value=content,
            height=500,
            key=f"editor_{filepath}",
            label_visibility="collapsed",
        )

        col1, col2 = st.columns(2)
        with col1:
            if st.button("💾 Save Changes", key=f"save_{filepath}", type="primary"):
                # Update in session state
                state = st.session_state.get("current_project_state", {})
                for key in ("generated_models", "generated_yaml", "generated_tests", "generated_docs"):
                    gen_files = state.get(key, {})
                    if isinstance(gen_files, dict) and filepath in gen_files:
                        gen_files[filepath] = edited_content
                        state[key] = gen_files
                        break
                st.session_state["current_project_state"] = state

                # Also save to disk if possible
                if project_path and FileManager is not None:
                    try:
                        fm = FileManager(project_path)
                        save_rel = filepath
                        base_name = os.path.basename(project_path)
                        if base_name and base_name in save_rel:
                            try:
                                save_rel = os.path.relpath(save_rel, base_name)
                            except ValueError:
                                pass
                        fm.write_file(save_rel, edited_content)
                    except Exception as e:
                        logger.warning(f"Could not save to disk: {e}")

                st.success(f"Saved changes to {filepath}", icon="💾")
                st.rerun()
        with col2:
            if st.button("↩️ Cancel", key=f"cancel_{filepath}"):
                st.rerun()
    else:
        updated = render_single_file(filepath, content, editable=False, key_prefix="explorer_view")

    # Download individual file
    st.markdown("---")
    st.download_button(
        f"⬇️ Download {Path(filepath).name}",
        data=content,
        file_name=Path(filepath).name,
        key=f"download_{filepath}",
    )
