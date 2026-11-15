"""Fixer Agent — auto-corrects issues found by the QA Validation Agent."""

from __future__ import annotations

import copy
import json
import logging
from datetime import datetime, timezone
from typing import Any

from agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class FixerAgent(BaseAgent):
    """Reads the QA report and applies minimal, targeted corrections.

    Workflow:
    1. Filter the ``qa_report`` for actionable errors (severity ``error``
       and high-priority ``warning``).
    2. Group issues by file.
    3. For each affected file, send the original content plus the issues
       to Gemini and request a corrected version.
    4. Back up the original content, apply the correction, and record the
       change in ``state["error_corrections"]``.
    5. Optionally re-validate the corrected files using ``Validator`` to
       confirm the fix.
    """

    def __init__(self) -> None:
        super().__init__(
            name="fixer",
            description=(
                "Automatically corrects errors found by QA validation using "
                "targeted Gemini-generated patches."
            ),
            system_prompt=(
                "You are a precision dbt code fixer.  You receive a file's "
                "original content together with a list of issues reported by "
                "the QA validator.  Your job is to return a corrected version "
                "of the file that resolves every listed issue while changing "
                "as little as possible.\n\n"
                "Rules:\n"
                "1. Make the *minimum* change required to fix each issue.  Do "
                "not refactor, reformat, or reorganise code that is not broken.\n"
                "2. Preserve the original CTE structure, indentation style, "
                "and comment blocks.\n"
                "3. If a ``ref()`` or ``source()`` target is invalid and you "
                "cannot confidently determine the correct target, add a "
                "``-- FIXME:`` comment instead of guessing.\n"
                "4. For naming-convention violations, rename the model "
                "reference consistently throughout the file.\n"
                "5. For YAML errors, ensure the output is valid YAML that "
                "conforms to the dbt schema specification.\n"
                "6. Return a JSON object with two keys:\n"
                "   - ``corrected_content``: the full corrected file content.\n"
                "   - ``changes``: an array of objects, each with ``issue_rule``, "
                "``description``, and ``lines_changed`` (int).\n\n"
                "Be precise.  Every character matters in SQL and YAML."
            ),
        )

    # ------------------------------------------------------------------
    # execute
    # ------------------------------------------------------------------
    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        """Fix errors found by QA and track corrections in state."""
        self._update_agent_status(state, "running", "Fixing QA errors")
        logger.info("FixerAgent starting")

        try:
            qa_report: dict[str, Any] = state.get("qa_report", {})
            issues: list[dict[str, Any]] = qa_report.get("issues", [])

            # Filter to actionable issues
            actionable = [
                i for i in issues
                if i.get("severity") in ("error", "warning")
            ]

            if not actionable:
                logger.info("No actionable issues to fix")
                self._update_agent_status(
                    state, "completed", "No actionable issues found"
                )
                state.setdefault("error_corrections", [])
                return state

            # Group by file
            issues_by_file: dict[str, list[dict[str, Any]]] = {}
            for issue in actionable:
                fname = issue.get("file", "unknown")
                issues_by_file.setdefault(fname, []).append(issue)

            # Locate the original content for each file
            all_artefacts: dict[str, str] = {}
            for artefact_key in (
                "generated_models",
                "generated_yaml",
                "generated_tests",
                "generated_docs",
            ):
                artefacts = state.get(artefact_key, {})
                if isinstance(artefacts, dict):
                    all_artefacts.update(artefacts)

            corrections: list[dict[str, Any]] = list(
                state.get("error_corrections", [])
            )
            files_fixed = 0

            for file_path, file_issues in issues_by_file.items():
                original = all_artefacts.get(file_path)
                if original is None:
                    logger.warning(
                        "Cannot fix '%s': file not found in generated artefacts",
                        file_path,
                    )
                    corrections.append(
                        {
                            "file": file_path,
                            "status": "skipped",
                            "reason": "File not found in generated artefacts",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        }
                    )
                    continue

                # Back up original
                backup_content = copy.deepcopy(original)

                # Ask Gemini for the fix
                corrected = self._fix_file(file_path, original, file_issues)
                if corrected is None:
                    corrections.append(
                        {
                            "file": file_path,
                            "status": "failed",
                            "reason": "Gemini returned no correction",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        }
                    )
                    continue

                corrected_content: str = corrected.get("corrected_content", "")
                changes: list[dict[str, Any]] = corrected.get("changes", [])

                if not corrected_content:
                    corrections.append(
                        {
                            "file": file_path,
                            "status": "failed",
                            "reason": "Empty corrected_content from Gemini",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        }
                    )
                    continue

                # Apply the correction to whichever artefact dict owns it
                self._apply_correction(state, file_path, corrected_content)
                files_fixed += 1

                corrections.append(
                    {
                        "file": file_path,
                        "status": "fixed",
                        "issues_addressed": len(file_issues),
                        "changes": changes,
                        "backup": backup_content,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                )

                logger.info(
                    "Fixed %d issue(s) in %s (%d change(s))",
                    len(file_issues),
                    file_path,
                    len(changes),
                )

            state["error_corrections"] = corrections

            status_msg = (
                f"Fixed {files_fixed}/{len(issues_by_file)} file(s), "
                f"{len(actionable)} issue(s) addressed"
            )
            logger.info(status_msg)
            self._update_agent_status(state, "completed", status_msg)

        except Exception as exc:
            logger.exception("FixerAgent failed: %s", exc)
            self._update_agent_status(state, "error", str(exc))
            state.setdefault("errors", []).append(
                {
                    "agent": self.name,
                    "error": str(exc),
                    "phase": "error_correction",
                }
            )

        return state

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _fix_file(
        self,
        file_path: str,
        original: str,
        issues: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        """Send one file + its issues to Gemini and return the fix."""
        prompt_parts: list[str] = [
            f"Fix the following file: `{file_path}`\n",
            "## Original Content\n"
            f"```\n{original}\n```\n",
            "## Issues to Fix\n"
            f"```json\n{json.dumps(issues, indent=2)}\n```\n",
            "Return JSON with `corrected_content` (full file string) and "
            "`changes` (array of {issue_rule, description, lines_changed}).",
        ]
        prompt = "\n".join(prompt_parts)

        try:
            return self._call_gemini_json(prompt)
        except Exception as exc:
            logger.error("Gemini fix call failed for %s: %s", file_path, exc)
            return None

    @staticmethod
    def _apply_correction(
        state: dict[str, Any],
        file_path: str,
        corrected_content: str,
    ) -> None:
        """Write the corrected content back to the correct artefact dict."""
        for artefact_key in (
            "generated_models",
            "generated_yaml",
            "generated_tests",
            "generated_docs",
        ):
            artefacts = state.get(artefact_key)
            if isinstance(artefacts, dict) and file_path in artefacts:
                artefacts[file_path] = corrected_content
                return
        # If not found in any known dict, place in generated_models as fallback
        state.setdefault("generated_models", {})[file_path] = corrected_content
