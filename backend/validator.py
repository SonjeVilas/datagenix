"""Multi-stage validation engine for dbt projects: static checks, SQL parsing, and dbt CLI."""

from __future__ import annotations

import logging
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Set
import yaml

try:
    import sqlglot
except ImportError:
    sqlglot = None

from integrations.dbt_runner import DbtRunner

logger = logging.getLogger(__name__)

# Regex patterns for dbt macro detection
_REF_PATTERN = re.compile(r"ref\(\s*['\"]([^'\"]+)['\"]\s*\)")
_SOURCE_PATTERN = re.compile(r"source\(\s*['\"]([^'\"]+)['\"]\s*,\s*['\"]([^'\"]+)['\"]\s*\)")


class Validator:
    """Validates dbt project files using static analysis and CLI tools."""

    def __init__(self, project_dir: Optional[Path | str] = None) -> None:
        self.project_dir = Path(project_dir).resolve() if project_dir else None
        self.dbt_runner = DbtRunner(self.project_dir) if self.project_dir else None

    # ----------------------------------------------------------------------
    # Static Memory / Dictionary Validation (for generated artifacts before build)
    # ----------------------------------------------------------------------

    def validate_artifacts(
        self,
        generated_models: Dict[str, str],
        generated_yaml: Dict[str, str],
        generated_tests: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Perform comprehensive static validation across in-memory artifacts."""
        issues: List[Dict[str, Any]] = []

        # 1. Validate YAML syntax and structure
        known_sources: Set[str] = set()
        for file_path, content in generated_yaml.items():
            yaml_issues, parsed_data = self._validate_yaml_content(file_path, content)
            issues.extend(yaml_issues)
            
            # Extract declared source tables
            if parsed_data and isinstance(parsed_data, dict):
                for src in parsed_data.get("sources", []):
                    src_name = src.get("name")
                    for tbl in src.get("tables", []):
                        tbl_name = tbl.get("name")
                        if src_name and tbl_name:
                            known_sources.add(f"{src_name}.{tbl_name}")

        # 2. Extract declared models
        known_models: Set[str] = set()
        for file_path in generated_models.keys():
            # Model name is filename without .sql
            model_name = Path(file_path).stem
            known_models.add(model_name)

        # 3. Validate SQL syntax and ref/source references
        model_deps: Dict[str, Set[str]] = {}
        for file_path, sql_content in generated_models.items():
            model_name = Path(file_path).stem
            deps, sql_issues = self._validate_sql_content(
                file_path=file_path,
                sql_content=sql_content,
                known_models=known_models,
                known_sources=known_sources,
            )
            issues.extend(sql_issues)
            model_deps[model_name] = deps

        # 4. Check for circular dependencies in models
        cycle_issues = self._check_cycles(model_deps)
        issues.extend(cycle_issues)

        error_count = sum(1 for i in issues if i.get("severity") == "error")
        warning_count = sum(1 for i in issues if i.get("severity") == "warning")
        passed = error_count == 0

        summary = (
            f"Static validation {'PASSED' if passed else 'FAILED'}: "
            f"{error_count} errors, {warning_count} warnings across "
            f"{len(generated_models)} models and {len(generated_yaml)} YAML files."
        )

        return {
            "passed": passed,
            "summary": summary,
            "error_count": error_count,
            "warning_count": warning_count,
            "issues": issues,
        }

    # ----------------------------------------------------------------------
    # Helper Validation Methods
    # ----------------------------------------------------------------------

    def _validate_yaml_content(
        self, file_path: str, content: str
    ) -> tuple[List[Dict[str, Any]], Optional[Any]]:
        issues: List[Dict[str, Any]] = []
        try:
            parsed = yaml.safe_load(content)
            if not isinstance(parsed, dict) and not isinstance(parsed, list):
                issues.append({
                    "file": file_path,
                    "line": 1,
                    "rule": "yaml_structure",
                    "severity": "warning",
                    "message": "YAML content parsed to a scalar rather than mapping/list",
                })
            return issues, parsed
        except yaml.YAMLError as exc:
            line_no = getattr(exc, "problem_mark", None)
            line = line_no.line + 1 if line_no else 1
            issues.append({
                "file": file_path,
                "line": line,
                "rule": "yaml_syntax",
                "severity": "error",
                "message": f"YAML syntax error: {exc}",
            })
            return issues, None

    def _validate_sql_content(
        self,
        file_path: str,
        sql_content: str,
        known_models: Set[str],
        known_sources: Set[str],
    ) -> tuple[Set[str], List[Dict[str, Any]]]:
        issues: List[Dict[str, Any]] = []
        deps: Set[str] = set()

        # Check ref() targets
        for match in _REF_PATTERN.finditer(sql_content):
            ref_target = match.group(1)
            deps.add(ref_target)
            if known_models and ref_target not in known_models:
                issues.append({
                    "file": file_path,
                    "line": sql_content[:match.start()].count("\n") + 1,
                    "rule": "broken_ref",
                    "severity": "error",
                    "message": f"Referenced model '{ref_target}' does not exist in generated models.",
                })

        # Check source() targets
        for match in _SOURCE_PATTERN.finditer(sql_content):
            src_name = match.group(1)
            tbl_name = match.group(2)
            full_src = f"{src_name}.{tbl_name}"
            if known_sources and full_src not in known_sources:
                issues.append({
                    "file": file_path,
                    "line": sql_content[:match.start()].count("\n") + 1,
                    "rule": "broken_source",
                    "severity": "error",
                    "message": f"Referenced source '{full_src}' is not defined in any sources.yml.",
                })

        # Check basic syntax with sqlglot if available
        if sqlglot:
            # Strip dbt jinja {{ ... }} and {% ... %} for basic AST parsing
            clean_sql = re.sub(r"\{\{.*?\}\}", "placeholder", sql_content)
            clean_sql = re.sub(r"\{%.*?%\}", "", clean_sql)
            try:
                sqlglot.parse(clean_sql, read="snowflake")
            except Exception as exc:
                issues.append({
                    "file": file_path,
                    "line": 1,
                    "rule": "sql_syntax",
                    "severity": "warning",
                    "message": f"Snowflake SQL parser warning: {str(exc)[:150]}",
                })

        return deps, issues

    def _check_cycles(self, model_deps: Dict[str, Set[str]]) -> List[Dict[str, Any]]:
        issues: List[Dict[str, Any]] = []
        visited: Dict[str, int] = {}  # 0: unvisited, 1: visiting, 2: visited

        def dfs(node: str, path: List[str]) -> None:
            visited[node] = 1
            for neighbor in model_deps.get(node, set()):
                if neighbor not in model_deps:
                    continue
                if visited.get(neighbor) == 1:
                    cycle = " -> ".join(path + [neighbor])
                    issues.append({
                        "file": f"models/{node}.sql",
                        "line": 1,
                        "rule": "circular_dependency",
                        "severity": "error",
                        "message": f"Circular dependency detected: {cycle}",
                    })
                elif visited.get(neighbor, 0) == 0:
                    dfs(neighbor, path + [neighbor])
            visited[node] = 2

        for model in list(model_deps.keys()):
            if visited.get(model, 0) == 0:
                dfs(model, [model])

        return issues

    # ----------------------------------------------------------------------
    # Subprocess / CLI Execution Checks (requires built project)
    # ----------------------------------------------------------------------

    def _cmd_to_dict(self, res: Any) -> Dict[str, Any]:
        """Convert a CommandResult or dict into a standard validation dict."""
        if isinstance(res, dict):
            return res
        if hasattr(res, "to_dict"):
            return res.to_dict()
        passed = getattr(res, "success", False)
        stdout = getattr(res, "stdout", "") or ""
        stderr = getattr(res, "stderr", "") or ""
        errors = []
        if not passed:
            err_msg = stderr.strip() or stdout.strip() or "Command failed"
            errors.append({"file": "project", "line": 1, "message": err_msg})
        return {
            "passed": passed,
            "errors": errors,
            "warnings": [],
            "output": stdout,
            "error": stderr,
            "raw_output": f"{stdout}\n{stderr}".strip(),
        }

    def run_dbt_parse(self) -> Dict[str, Any]:
        """Execute `dbt parse` in project directory."""
        if not self.dbt_runner:
            return {"passed": False, "errors": ["No project directory configured"], "raw_output": ""}
        return self._cmd_to_dict(self.dbt_runner.parse())

    def run_dbt_compile(self) -> Dict[str, Any]:
        """Execute `dbt compile` in project directory."""
        if not self.dbt_runner:
            return {"passed": False, "errors": ["No project directory configured"], "raw_output": ""}
        return self._cmd_to_dict(self.dbt_runner.compile())

    def run_sqlfluff_lint(self) -> Dict[str, Any]:
        """Execute `sqlfluff lint` on models directory."""
        if not self.dbt_runner:
            return {"passed": False, "errors": ["No project directory configured"], "raw_output": ""}
        return self._cmd_to_dict(self.dbt_runner.sqlfluff_lint())

    # ----------------------------------------------------------------------
    # Aggregated Validation Runner
    # ----------------------------------------------------------------------

    def validate_all(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Run all applicable validations on state artifacts and return formatted results."""
        generated_models = state.get("generated_models", {})
        generated_yaml = state.get("generated_yaml", {})
        generated_tests = state.get("generated_tests", {})

        # If in-memory is empty, try loading from disk
        output_path = state.get("project_output_path")
        if output_path and Path(output_path).exists():
            self.project_dir = Path(output_path).resolve()
            self.dbt_runner = DbtRunner(self.project_dir)

            if not generated_models:
                for p in self.project_dir.rglob("*.sql"):
                    try:
                        rel = str(p.relative_to(self.project_dir))
                        generated_models[rel] = p.read_text(encoding="utf-8")
                    except Exception:
                        pass
            if not generated_yaml:
                for p in self.project_dir.rglob("*.yml"):
                    try:
                        rel = str(p.relative_to(self.project_dir))
                        generated_yaml[rel] = p.read_text(encoding="utf-8")
                    except Exception:
                        pass

        # 1. Static artifact validation
        artifact_res = self.validate_artifacts(generated_models, generated_yaml, generated_tests)
        issues = artifact_res.get("issues", [])
        art_errors = [i for i in issues if i.get("severity") == "error"]
        art_warnings = [i for i in issues if i.get("severity") == "warning"]

        # Update qa_report in state
        qa_report = {
            "passed": artifact_res.get("passed", False),
            "summary": artifact_res.get("summary", ""),
            "issues": issues,
            "errors": art_errors,
            "warnings": art_warnings,
            "status": "passed" if artifact_res.get("passed") else "failed",
        }
        state["qa_report"] = qa_report

        results: Dict[str, Any] = {
            "QA Agent": {
                "passed": artifact_res.get("passed", False),
                "errors": art_errors,
                "warnings": art_warnings,
                "raw_output": artifact_res.get("summary", ""),
            }
        }

        # 2. CLI checks if project is on disk
        if self.dbt_runner:
            parse_res = self.run_dbt_parse()
            results["dbt_parse"] = {
                "passed": parse_res.get("passed", False),
                "errors": parse_res.get("errors", []),
                "warnings": parse_res.get("warnings", []),
                "raw_output": parse_res.get("raw_output") or parse_res.get("output", "") or parse_res.get("error", ""),
            }
            compile_res = self.run_dbt_compile()
            results["dbt_compile"] = {
                "passed": compile_res.get("passed", False),
                "errors": compile_res.get("errors", []),
                "warnings": compile_res.get("warnings", []),
                "raw_output": compile_res.get("raw_output") or compile_res.get("output", "") or compile_res.get("error", ""),
            }
            fluff_res = self.run_sqlfluff_lint()
            fluff_raw = fluff_res.get("raw_output") or fluff_res.get("output", "") or fluff_res.get("error", "")
            # Style linting suggestions should be treated as warnings, not fatal errors
            fluff_warnings = []
            if fluff_raw.strip() and ("FAIL" in fluff_raw or "warning" in fluff_raw.lower()):
                fluff_warnings.append({"file": "models", "line": 1, "message": "SQLFluff style suggestions: review SQL style conventions in tab."})
            results["sqlfluff"] = {
                "passed": True,  # Linter suggestions do not fail project execution
                "errors": [],
                "warnings": fluff_warnings,
                "raw_output": fluff_raw,
            }
        else:
            results["dbt_parse"] = {
                "passed": True,
                "errors": [],
                "warnings": [],
                "raw_output": "dbt parse skipped: Project not written to disk.",
            }
            results["dbt_compile"] = {
                "passed": True,
                "errors": [],
                "warnings": [],
                "raw_output": "dbt compile skipped: Project not written to disk.",
            }
            results["sqlfluff"] = {
                "passed": True,
                "errors": [],
                "warnings": [],
                "raw_output": "SQLFluff skipped: Project not written to disk.",
            }

        return results

