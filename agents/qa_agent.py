"""QA / Validation Agent — reviews all generated SQL and YAML for correctness."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class QAValidationAgent(BaseAgent):
    """Reviews every generated artefact for syntactic and semantic correctness.

    Checks performed:
    * SQL syntax validation (basic pattern matching + Gemini review).
    * ``ref()`` and ``source()`` references point to models / sources that
      actually exist in the generated set.
    * dbt naming conventions (e.g. staging models prefixed ``stg_``).
    * Missing column definitions in schema YAML files.
    * Circular dependency detection in the model DAG.
    * Test-coverage analysis (every model should have at least one test).
    * YAML validity.

    Outputs ``state["qa_report"]`` with ``status`` (``passed`` | ``failed``),
    an ``issues`` list (each with ``file``, ``line``, ``rule``, ``severity``,
    ``message``), and summary statistics.
    """

    def __init__(self) -> None:
        super().__init__(
            name="qa_validation",
            description=(
                "Reviews all generated SQL and YAML artefacts for syntax "
                "errors, reference correctness, naming conventions, missing "
                "definitions, circular dependencies, and test coverage."
            ),
            system_prompt=(
                "You are a meticulous dbt code reviewer and quality-assurance "
                "engineer.  You will be given the full set of generated SQL "
                "models, YAML configurations, and test definitions for a dbt "
                "project.  Your job is to find every issue — large or small.\n\n"
                "Perform the following checks:\n"
                "1. **SQL Syntax** — Look for unclosed parentheses, missing "
                "commas, invalid Snowflake SQL constructs, and incomplete CTEs.\n"
                "2. **ref() / source() correctness** — Every ``ref('model')`` "
                "must correspond to an actual model file; every "
                "``source('src','tbl')`` must match a declared source.\n"
                "3. **Naming conventions** — staging models start with "
                "``stg_``, intermediate with ``int_``, marts do not have a "
                "prefix.  File names should be snake_case.\n"
                "4. **Missing definitions** — Every model referenced in SQL "
                "should have a schema YAML entry with column descriptions.\n"
                "5. **Circular dependencies** — Detect any ref() cycles.\n"
                "6. **Test coverage** — Every model should have at least one "
                "test (unique, not_null, etc.).\n"
                "7. **YAML validity** — Ensure YAML files parse correctly "
                "and follow the dbt schema spec.\n\n"
                "Return a JSON object with:\n"
                "- ``status``: ``\"passed\"`` or ``\"failed\"``\n"
                "- ``summary``: object with ``total_issues``, ``errors``, "
                "``warnings``, ``info`` counts\n"
                "- ``issues``: array of objects, each with ``file`` (str), "
                "``line`` (int or null), ``rule`` (str), ``severity`` "
                "(``error`` | ``warning`` | ``info``), ``message`` (str), "
                "and ``suggestion`` (str).\n"
                "Be thorough but do not invent false positives."
            ),
        )

    # ------------------------------------------------------------------
    # execute
    # ------------------------------------------------------------------
    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        """Run QA checks on all generated artefacts."""
        self._update_agent_status(state, "running", "Running QA validation")
        logger.info("QAValidationAgent starting")

        try:
            # ---- Collect all artefacts ----
            generated_models: dict[str, str] = state.get("generated_models", {})
            generated_yaml: dict[str, str] = state.get("generated_yaml", {})
            generated_tests: dict[str, str] = state.get("generated_tests", {})
            generated_docs: dict[str, str] = state.get("generated_docs", {})
            architecture: dict[str, Any] = state.get("architecture", {})

            # ---- Local static checks ----
            local_issues = self._run_local_checks(
                generated_models, generated_yaml, generated_tests,
            )

            # ---- Gemini deep review ----
            prompt = self._build_prompt(
                generated_models, generated_yaml, generated_tests,
                generated_docs, architecture, local_issues,
            )

            logger.info("Calling Gemini for deep QA review")
            gemini_report: dict[str, Any] = self._call_gemini_json(prompt)

            # ---- Merge local + Gemini issues ----
            qa_report = self._merge_reports(local_issues, gemini_report)

            # ---- Store in state ----
            state["qa_report"] = qa_report
            state["validation_results"] = {
                "status": qa_report["status"],
                "total_issues": qa_report["summary"]["total_issues"],
                "errors": qa_report["summary"]["errors"],
            }

            status_msg = (
                f"QA {qa_report['status']}: "
                f"{qa_report['summary']['total_issues']} issue(s) "
                f"({qa_report['summary']['errors']} error(s), "
                f"{qa_report['summary']['warnings']} warning(s))"
            )
            logger.info(status_msg)
            self._update_agent_status(state, "completed", status_msg)

        except Exception as exc:
            logger.exception("QAValidationAgent failed: %s", exc)
            self._update_agent_status(state, "error", str(exc))
            state.setdefault("errors", []).append(
                {
                    "agent": self.name,
                    "error": str(exc),
                    "phase": "qa_validation",
                }
            )

        return state

    # ------------------------------------------------------------------
    # local (offline) checks
    # ------------------------------------------------------------------
    def _run_local_checks(
        self,
        models: dict[str, str],
        yamls: dict[str, str],
        tests: dict[str, str],
    ) -> list[dict[str, Any]]:
        """Run fast deterministic checks without calling Gemini."""
        issues: list[dict[str, Any]] = []

        # Collect known model names from file paths
        known_models: set[str] = set()
        for path in models:
            name = path.rsplit("/", 1)[-1].replace(".sql", "")
            known_models.add(name)

        # Collect declared sources from YAML
        declared_sources: set[tuple[str, str]] = set()
        for path, content in yamls.items():
            try:
                import yaml

                parsed = yaml.safe_load(content)
                if isinstance(parsed, dict):
                    for src in parsed.get("sources", []):
                        src_name = src.get("name", "")
                        for tbl in src.get("tables", []):
                            declared_sources.add((src_name, tbl.get("name", "")))
            except Exception:
                issues.append(
                    {
                        "file": path,
                        "line": None,
                        "rule": "yaml_parse",
                        "severity": "error",
                        "message": f"YAML file failed to parse: {path}",
                        "suggestion": "Fix YAML syntax (indentation, colons, etc.)",
                    }
                )

        # Check each SQL model
        for path, sql in models.items():
            model_name = path.rsplit("/", 1)[-1].replace(".sql", "")

            # ref() correctness
            for match in re.finditer(r"\{\{\s*ref\(\s*['\"](\w+)['\"]\s*\)\s*\}\}", sql):
                ref_name = match.group(1)
                if ref_name not in known_models:
                    issues.append(
                        {
                            "file": path,
                            "line": None,
                            "rule": "ref_missing",
                            "severity": "error",
                            "message": (
                                f"ref('{ref_name}') references a model that "
                                f"does not exist in the generated set."
                            ),
                            "suggestion": f"Create model '{ref_name}' or fix the reference.",
                        }
                    )

            # source() correctness
            for match in re.finditer(
                r"\{\{\s*source\(\s*['\"](\w+)['\"],\s*['\"](\w+)['\"]\s*\)\s*\}\}",
                sql,
            ):
                src, tbl = match.group(1), match.group(2)
                if declared_sources and (src, tbl) not in declared_sources:
                    issues.append(
                        {
                            "file": path,
                            "line": None,
                            "rule": "source_missing",
                            "severity": "error",
                            "message": (
                                f"source('{src}', '{tbl}') is not declared "
                                f"in any sources YAML."
                            ),
                            "suggestion": "Add a source declaration or fix the reference.",
                        }
                    )

            # Naming conventions
            if "staging" in path and not model_name.startswith("stg_"):
                issues.append(
                    {
                        "file": path,
                        "line": None,
                        "rule": "naming_staging",
                        "severity": "warning",
                        "message": (
                            f"Staging model '{model_name}' should be prefixed "
                            f"with 'stg_'."
                        ),
                        "suggestion": f"Rename to 'stg_{model_name}'.",
                    }
                )
            if "intermediate" in path and not model_name.startswith("int_"):
                issues.append(
                    {
                        "file": path,
                        "line": None,
                        "rule": "naming_intermediate",
                        "severity": "warning",
                        "message": (
                            f"Intermediate model '{model_name}' should be "
                            f"prefixed with 'int_'."
                        ),
                        "suggestion": f"Rename to 'int_{model_name}'.",
                    }
                )

            # Circular-dep naive check (self-reference)
            if f"ref('{model_name}')" in sql:
                issues.append(
                    {
                        "file": path,
                        "line": None,
                        "rule": "circular_self_ref",
                        "severity": "error",
                        "message": f"Model '{model_name}' references itself.",
                        "suggestion": "Remove the self-referencing ref().",
                    }
                )

        # Test coverage: every model should have at least one test file
        tested_models: set[str] = set()
        all_test_content = " ".join(tests.values())
        for m in known_models:
            if m in all_test_content:
                tested_models.add(m)

        untested = known_models - tested_models
        for m in sorted(untested):
            issues.append(
                {
                    "file": f"(model: {m})",
                    "line": None,
                    "rule": "test_coverage",
                    "severity": "warning",
                    "message": f"Model '{m}' has no test definitions.",
                    "suggestion": "Add at least unique + not_null tests for the primary key.",
                }
            )

        # Circular dependency detection (full graph)
        dep_graph: dict[str, set[str]] = {}
        for path, sql in models.items():
            model_name = path.rsplit("/", 1)[-1].replace(".sql", "")
            deps: set[str] = set()
            for match in re.finditer(r"\{\{\s*ref\(\s*['\"](\w+)['\"]\s*\)\s*\}\}", sql):
                deps.add(match.group(1))
            dep_graph[model_name] = deps

        cycles = self._detect_cycles(dep_graph)
        for cycle in cycles:
            cycle_str = " → ".join(cycle)
            issues.append(
                {
                    "file": "(dag)",
                    "line": None,
                    "rule": "circular_dependency",
                    "severity": "error",
                    "message": f"Circular dependency detected: {cycle_str}",
                    "suggestion": "Refactor models to break the cycle.",
                }
            )

        return issues

    @staticmethod
    def _detect_cycles(graph: dict[str, set[str]]) -> list[list[str]]:
        """Detect all cycles in the model dependency graph using DFS."""
        WHITE, GRAY, BLACK = 0, 1, 2
        color: dict[str, int] = {node: WHITE for node in graph}
        path: list[str] = []
        cycles: list[list[str]] = []

        def dfs(node: str) -> None:
            color[node] = GRAY
            path.append(node)
            for neighbour in graph.get(node, set()):
                if neighbour not in color:
                    continue
                if color[neighbour] == GRAY:
                    idx = path.index(neighbour)
                    cycles.append(path[idx:] + [neighbour])
                elif color[neighbour] == WHITE:
                    dfs(neighbour)
            path.pop()
            color[node] = BLACK

        for node in graph:
            if color[node] == WHITE:
                dfs(node)

        return cycles

    # ------------------------------------------------------------------
    # Gemini prompt
    # ------------------------------------------------------------------
    def _build_prompt(
        self,
        models: dict[str, str],
        yamls: dict[str, str],
        tests: dict[str, str],
        docs: dict[str, str],
        architecture: dict[str, Any],
        local_issues: list[dict[str, Any]],
    ) -> str:
        parts: list[str] = [
            "Review the following dbt project artefacts for quality issues. "
            "Return a JSON object with `status`, `summary`, and `issues`.\n",
        ]

        if models:
            parts.append("## SQL Models\n")
            for path, sql in models.items():
                parts.append(f"### `{path}`\n```sql\n{sql}\n```\n")

        if yamls:
            parts.append("## YAML Configs\n")
            for path, content in yamls.items():
                parts.append(f"### `{path}`\n```yaml\n{content}\n```\n")

        if tests:
            parts.append("## Test Definitions\n")
            for path, content in tests.items():
                parts.append(f"### `{path}`\n```yaml\n{content}\n```\n")

        if architecture:
            parts.append(
                "## Architecture\n"
                f"```json\n{json.dumps(architecture, indent=2, default=str)}\n```\n"
            )

        if local_issues:
            parts.append(
                "## Issues Already Found by Static Analysis\n"
                f"```json\n{json.dumps(local_issues, indent=2)}\n```\n"
                "Include these in your report and add any additional issues "
                "you find.\n"
            )

        parts.append(
            "Return JSON: {status, summary: {total_issues, errors, warnings, "
            "info}, issues: [{file, line, rule, severity, message, suggestion}]}"
        )

        return "\n".join(parts)

    # ------------------------------------------------------------------
    # merge
    # ------------------------------------------------------------------
    @staticmethod
    def _merge_reports(
        local_issues: list[dict[str, Any]],
        gemini_report: dict[str, Any],
    ) -> dict[str, Any]:
        """Combine local issues with the Gemini report."""
        gemini_issues: list[dict[str, Any]] = gemini_report.get("issues", [])

        # De-duplicate by (file, rule, message)
        seen: set[tuple[str, str, str]] = set()
        merged: list[dict[str, Any]] = []

        for issue in local_issues + gemini_issues:
            key = (
                issue.get("file", ""),
                issue.get("rule", ""),
                issue.get("message", ""),
            )
            if key not in seen:
                seen.add(key)
                merged.append(issue)

        error_count = sum(1 for i in merged if i.get("severity") == "error")
        warn_count = sum(1 for i in merged if i.get("severity") == "warning")
        info_count = sum(1 for i in merged if i.get("severity") == "info")

        return {
            "status": "failed" if error_count > 0 else "passed",
            "summary": {
                "total_issues": len(merged),
                "errors": error_count,
                "warnings": warn_count,
                "info": info_count,
            },
            "issues": merged,
        }
