"""Shared project state used as the LangGraph graph state."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ProjectState(BaseModel):
    """Central state object passed through every LangGraph node.

    Each agent reads from and writes to this state.  The orchestrator
    serialises it between nodes so every field must be JSON-safe.
    """

    # ── User inputs ─────────────────────────────────────────────────────
    project_name: str = Field(default="", description="Name of the dbt project")
    project_description: str = Field(default="", description="High-level project description")
    business_requirements: str = Field(
        default="",
        description="Raw business requirements text provided by the user",
    )

    # ── Agent outputs ───────────────────────────────────────────────────
    project_specification: Dict[str, Any] = Field(
        default_factory=dict,
        description="Structured specification parsed from business requirements",
    )
    source_catalog: Dict[str, Any] = Field(
        default_factory=dict,
        description="Discovered source tables, columns, types, and relationships",
    )
    architecture: Dict[str, Any] = Field(
        default_factory=dict,
        description="dbt project architecture: layers, models, materializations, DAG",
    )
    business_logic: Dict[str, Any] = Field(
        default_factory=dict,
        description="SQL transformation rules derived from requirements",
    )
    generated_models: Dict[str, str] = Field(
        default_factory=dict,
        description="Map of relative file path → SQL model content",
    )
    generated_yaml: Dict[str, str] = Field(
        default_factory=dict,
        description="Map of relative file path → YAML config content",
    )
    generated_tests: Dict[str, str] = Field(
        default_factory=dict,
        description="Map of relative file path → test file content",
    )
    generated_docs: Dict[str, str] = Field(
        default_factory=dict,
        description="Map of relative file path → documentation content",
    )
    qa_report: Dict[str, Any] = Field(
        default_factory=dict,
        description="QA validation results with issues and severity",
    )
    validation_results: Dict[str, Any] = Field(
        default_factory=dict,
        description="Results from static / dbt validation passes",
    )

    # ── Error tracking ──────────────────────────────────────────────────
    error_corrections: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="History of error corrections applied by the fixer agent",
    )
    errors: List[str] = Field(
        default_factory=list,
        description="Accumulated error messages from any agent",
    )
    warnings: List[str] = Field(
        default_factory=list,
        description="Non-fatal warnings collected during the pipeline",
    )

    # ── Orchestration metadata ──────────────────────────────────────────
    agent_status: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="Per-agent status tracking: {agent_name: {status, message, started_at, completed_at}}",
    )
    retry_count: int = Field(
        default=0,
        description="Number of QA → fix → re-validate cycles completed",
    )
    max_retries: int = Field(
        default=3,
        description="Maximum allowed retry cycles before escalating to human",
    )
    current_agent: str = Field(
        default="",
        description="Name of the agent currently executing",
    )
    execution_history: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Ordered list of agent execution records",
    )

    # ── Flags ───────────────────────────────────────────────────────────
    human_approval_required: bool = Field(
        default=False,
        description="Set True when human review is needed (e.g. retries exhausted)",
    )
    snowflake_connected: bool = Field(
        default=False,
        description="Whether a live Snowflake connection is available",
    )

    # ── Manual / optional inputs ────────────────────────────────────────
    source_metadata_manual: Dict[str, Any] = Field(
        default_factory=dict,
        description="Manually-supplied source metadata when Snowflake is not connected",
    )
    project_output_path: str = Field(
        default="",
        description="Absolute path to the generated project directory",
    )
