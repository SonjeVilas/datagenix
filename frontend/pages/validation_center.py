"""Validation Center page — aggregated validation results."""

from __future__ import annotations

import logging
from typing import Any

import streamlit as st

logger = logging.getLogger(__name__)

try:
    from backend.validator import Validator
except ImportError:
    Validator = None

try:
    from backend.orchestrator import run_pipeline
except ImportError:
    run_pipeline = None


def render_validation_center_page() -> None:
    """Render the Validation Center page."""
    st.markdown("## ✅ Validation Center")
    st.markdown("Review validation results, fix errors, and re-run checks.")
    st.markdown("---")

    state = st.session_state.get("current_project_state", {})
    validation_results = state.get("validation_results", {})
    qa_report = state.get("qa_report", {})
    error_corrections = state.get("error_corrections", [])

    # Tabs
    tab_overall, tab_parse, tab_compile, tab_sqlfluff, tab_qa, tab_history = st.tabs([
        "📊 Overall",
        "🔍 dbt Parse",
        "⚙️ dbt Compile",
        "🧹 SQLFluff",
        "🤖 QA Agent",
        "📜 Fix History",
    ])

    with tab_overall:
        _render_overall_tab(validation_results, qa_report)

    with tab_parse:
        _render_validation_tab(
            validation_results.get("dbt_parse", {}),
            "dbt Parse",
            "Checks that dbt can parse all model files without errors.",
        )

    with tab_compile:
        _render_validation_tab(
            validation_results.get("dbt_compile", {}),
            "dbt Compile",
            "Checks that dbt can compile all models into executable SQL.",
        )

    with tab_sqlfluff:
        _render_validation_tab(
            validation_results.get("sqlfluff", {}),
            "SQLFluff Lint",
            "SQL linting results from SQLFluff style checks.",
        )

    with tab_qa:
        _render_qa_tab(qa_report)

    with tab_history:
        _render_fix_history(error_corrections)

    # Actions
    st.markdown("---")
    st.markdown("### 🔧 Actions")
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("🔄 Re-run All Validations", type="primary", width='stretch'):
            _run_validations()

    with col2:
        if st.button("🔧 Fix Errors (Fixer Agent)", width='stretch'):
            _run_fixer_agent()

    with col3:
        if st.button("📋 Export Report", width='stretch'):
            _export_report(validation_results, qa_report)


def _render_overall_tab(validation_results: dict, qa_report: dict) -> None:
    """Render the overall validation summary."""
    st.markdown("### 📊 Validation Summary")

    if not validation_results and not qa_report:
        st.info("No validation results yet. Run validations after generating a project.", icon="📊")
        return

    # Summary metrics
    total_errors = 0
    total_warnings = 0
    checks_passed = 0
    checks_total = 0

    for check_name, result in validation_results.items():
        if isinstance(result, dict):
            checks_total += 1
            errors = result.get("errors", [])
            warns = result.get("warnings", [])
            total_errors += len(errors) if isinstance(errors, list) else 0
            total_warnings += len(warns) if isinstance(warns, list) else 0
            if result.get("passed") or result.get("valid") or not errors:
                checks_passed += 1

    if qa_report:
        checks_total += 1
        qa_errors = qa_report.get("errors", [])
        total_errors += len(qa_errors) if isinstance(qa_errors, list) else 0
        if qa_report.get("passed"):
            checks_passed += 1

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Checks Passed", f"{checks_passed}/{checks_total}")
    with col2:
        st.metric("Errors", total_errors)
    with col3:
        st.metric("Warnings", total_warnings)
    with col4:
        status = "✅ PASS" if total_errors == 0 else "❌ FAIL"
        st.metric("Overall Status", status)

    # Per-check status
    st.markdown("---")
    st.markdown("### Check Results")
    for check_name, result in validation_results.items():
        if isinstance(result, dict):
            errors = result.get("errors", [])
            passed = result.get("passed") or result.get("valid") or not errors
            icon = "✅" if passed else "❌"
            st.markdown(f"{icon} **{check_name}** — {'Passed' if passed else f'{len(errors)} error(s)'}")


def _render_validation_tab(result: dict, title: str, description: str) -> None:
    """Render a single validation check tab."""
    st.markdown(f"### {title}")
    st.caption(description)

    if not result:
        st.info(f"No {title} results available.", icon="📊")
        return

    passed = result.get("passed") or result.get("valid") or not result.get("errors", [])

    if passed:
        st.success(f"✅ {title} passed!", icon="✅")
    else:
        st.error(f"❌ {title} failed.", icon="❌")

    errors = result.get("errors", [])
    warnings = result.get("warnings", [])

    if errors:
        st.markdown(f"**Errors ({len(errors)}):**")
        for i, err in enumerate(errors):
            if isinstance(err, dict):
                file_ref = err.get("file", "")
                line = err.get("line", "")
                msg = err.get("message", str(err))
                st.markdown(f"  {i+1}. `{file_ref}:{line}` — {msg}")
            else:
                st.markdown(f"  {i+1}. {err}")

    if warnings:
        st.markdown(f"**Warnings ({len(warnings)}):**")
        for i, warn in enumerate(warnings):
            if isinstance(warn, dict):
                st.markdown(f"  {i+1}. `{warn.get('file', '')}` — {warn.get('message', str(warn))}")
            else:
                st.markdown(f"  {i+1}. {warn}")

    # Raw output
    if result.get("raw_output"):
        with st.expander("📄 Raw Output"):
            st.code(result["raw_output"], language="text")


def _render_qa_tab(qa_report: dict) -> None:
    """Render the QA agent report tab."""
    st.markdown("### 🤖 QA Validation Report")

    if not qa_report:
        st.info("No QA report available. Run the QA agent to validate the project.", icon="🤖")
        return

    passed = qa_report.get("passed", False)
    if passed:
        st.success("✅ QA Validation passed!", icon="✅")
    else:
        st.error("❌ QA Validation found issues.", icon="❌")

    # Score
    score = qa_report.get("score")
    if score is not None:
        st.progress(min(score / 100, 1.0), text=f"Quality Score: {score}/100")

    # Categories
    categories = qa_report.get("categories", {})
    if categories:
        st.markdown("**Category Scores:**")
        for cat, cat_score in categories.items():
            st.markdown(f"  - **{cat}**: {cat_score}")

    # Issues
    issues = qa_report.get("issues", []) or qa_report.get("errors", [])
    if issues:
        st.markdown(f"**Issues ({len(issues)}):**")
        for issue in issues:
            if isinstance(issue, dict):
                severity = issue.get("severity", "error")
                icon = "❌" if severity == "error" else "⚠️"
                st.markdown(f"  {icon} [{severity.upper()}] {issue.get('message', str(issue))}")
                if issue.get("file"):
                    st.caption(f"     File: `{issue['file']}`")
                if issue.get("suggestion"):
                    st.caption(f"     💡 Suggestion: {issue['suggestion']}")
            else:
                st.markdown(f"  - {issue}")

    # Recommendations
    recommendations = qa_report.get("recommendations", [])
    if recommendations:
        with st.expander("💡 Recommendations"):
            for rec in recommendations:
                st.markdown(f"  - {rec}")


def _render_fix_history(error_corrections: list) -> None:
    """Render the error correction history."""
    st.markdown("### 📜 Error Correction History")

    if not error_corrections:
        st.info("No error corrections recorded.", icon="📜")
        return

    for i, correction in enumerate(error_corrections):
        if isinstance(correction, dict):
            with st.expander(
                f"Fix #{i+1} — {correction.get('agent', 'Unknown')} "
                f"({correction.get('timestamp', 'Unknown time')})"
            ):
                st.markdown(f"**File:** `{correction.get('file', 'N/A')}`")
                st.markdown(f"**Error:** {correction.get('error', 'N/A')}")
                st.markdown(f"**Fix Applied:** {correction.get('fix', 'N/A')}")
                if correction.get("before"):
                    st.code(correction["before"], language="sql")
                if correction.get("after"):
                    st.code(correction["after"], language="sql")
        else:
            st.markdown(f"  {i+1}. {correction}")


def _run_validations() -> None:
    """Re-run all validations."""
    if Validator is not None:
        with st.spinner("Running validations..."):
            try:
                validator = Validator()
                state = st.session_state.get("current_project_state", {})
                results = validator.validate_all(state)
                state["validation_results"] = results
                st.session_state["current_project_state"] = state
                st.success("Validations complete!", icon="✅")
                st.rerun()
            except Exception as e:
                st.error(f"Validation error: {e}", icon="❌")
                logger.exception("Validation error")
    else:
        st.warning("Validator module not available.", icon="⚠️")


def _run_fixer_agent() -> None:
    """Trigger the fixer agent to fix errors."""
    state = st.session_state.get("current_project_state", {})
    validation_results = state.get("validation_results", {})

    has_errors = any(
        bool(r.get("errors", []))
        for r in validation_results.values()
        if isinstance(r, dict)
    )

    if not has_errors:
        st.info("No errors to fix!", icon="✅")
        return

    if run_pipeline is not None:
        with st.spinner("🔧 Fixer agent is working on errors..."):
            try:
                state["current_agent"] = "error_correction"
                result = run_pipeline(state)
                st.session_state["current_project_state"] = result
                st.success("Error correction complete! Re-run validations to check.", icon="✅")
                st.rerun()
            except Exception as e:
                st.error(f"Fixer agent error: {e}", icon="❌")
    else:
        st.warning("Backend orchestrator not available.", icon="⚠️")


def _export_report(validation_results: dict, qa_report: dict) -> None:
    """Export validation report as downloadable text."""
    import json

    report = {
        "validation_results": validation_results,
        "qa_report": qa_report,
    }
    report_json = json.dumps(report, indent=2, default=str)
    st.download_button(
        "📥 Download Report JSON",
        data=report_json,
        file_name="validation_report.json",
        mime="application/json",
    )
