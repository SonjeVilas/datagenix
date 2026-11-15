"""
Requirement Analysis Agent for dbt Project Factory.

Parses business requirements text via Gemini and outputs a structured
project specification including objectives, source systems, business entities,
transformation rules, and data quality requirements.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pydantic v2 schemas for validating the Gemini response
# ---------------------------------------------------------------------------

class TransformationRequirement(BaseModel):
    name: str = Field(..., description="Name of the transformation")
    description: str = Field(..., description="What the transformation does")
    source_entities: list[str] = Field(default_factory=list, description="Source entities involved")
    logic: str = Field(default="", description="High-level transformation logic")
    priority: str = Field(default="medium", description="Priority: high, medium, low")


class OutputModel(BaseModel):
    name: str = Field(..., description="Name of the output model/table")
    description: str = Field(default="", description="Purpose of the output model")
    grain: str = Field(default="", description="Grain / primary key description")
    key_columns: list[str] = Field(default_factory=list, description="Key columns in the output")
    consumers: list[str] = Field(default_factory=list, description="Downstream consumers")


class IncrementalRequirement(BaseModel):
    entity: str = Field(..., description="Entity name requiring incremental load")
    strategy: str = Field(default="timestamp", description="Incremental strategy")
    timestamp_column: str = Field(default="", description="Column used for incremental detection")
    unique_key: str = Field(default="", description="Unique key for merge")


class DataQualityRequirement(BaseModel):
    entity: str = Field(..., description="Entity the rule applies to")
    rule_type: str = Field(..., description="Type: not_null, unique, accepted_values, relationships, custom")
    column: str = Field(default="", description="Column the rule applies to")
    description: str = Field(default="", description="Description of the quality rule")
    severity: str = Field(default="warn", description="warn or error")


class ProjectSpecification(BaseModel):
    objectives: list[str] = Field(default_factory=list, description="Business objectives")
    source_systems: list[dict[str, Any]] = Field(default_factory=list, description="Source systems with names and descriptions")
    business_entities: list[dict[str, Any]] = Field(default_factory=list, description="Business entities identified")
    business_rules: list[dict[str, Any]] = Field(default_factory=list, description="Business rules extracted")
    transformation_requirements: list[TransformationRequirement] = Field(default_factory=list)
    output_models: list[OutputModel] = Field(default_factory=list)
    incremental_requirements: list[IncrementalRequirement] = Field(default_factory=list)
    data_quality_requirements: list[DataQualityRequirement] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list, description="Assumptions made during analysis")
    clarification_questions: list[str] = Field(default_factory=list, description="Questions needing human clarification")


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class RequirementAgent(BaseAgent):
    """Parses business requirements and produces a structured project specification."""

    def __init__(self) -> None:
        super().__init__(
            name="requirement_analyst",
            description=(
                "Analyzes free-text business requirements and produces a comprehensive, "
                "structured project specification for downstream dbt agents."
            ),
            system_prompt=(
                "You are a senior analytics engineer and business analyst specializing in "
                "data warehouse design and dbt (data build tool) projects. Your role is to "
                "take raw business requirements — often written in informal, non-technical "
                "language — and translate them into a precise, machine-readable project "
                "specification.\n\n"
                "When analyzing requirements you must:\n"
                "1. Identify every source system mentioned or implied, including databases, "
                "APIs, flat files, and SaaS platforms.\n"
                "2. Extract all business entities (customers, orders, products, etc.) and "
                "their expected relationships.\n"
                "3. Document explicit and implicit business rules such as exchange-rate "
                "conversions, fiscal-calendar definitions, SLA thresholds, and status mappings.\n"
                "4. Determine transformation requirements — joins, aggregations, filters, "
                "window functions, pivots, and slowly-changing-dimension handling.\n"
                "5. Propose output models (dims, facts, one-big-tables, metrics) with grain "
                "definitions and key columns.\n"
                "6. Identify any incremental-loading needs and suggest strategies "
                "(timestamp-based, unique-key merge, full-refresh).\n"
                "7. Infer data-quality expectations: not-null constraints, uniqueness, "
                "accepted-value lists, referential integrity, and freshness.\n"
                "8. List assumptions you are making and any clarification questions the "
                "business stakeholder should answer before development begins.\n\n"
                "Return your analysis as a single JSON object (no markdown fences) matching "
                "the required schema exactly. Be thorough — downstream agents depend on the "
                "completeness of your output."
            ),
        )

    def execute(self, state: dict) -> dict:
        """Analyze business requirements and populate state.project_specification."""
        logger.info("RequirementAgent: starting execution")
        self._update_agent_status(state, "running", "Analyzing business requirements")

        try:
            # ------------------------------------------------------------------
            # 1. Build the prompt from current state
            # ------------------------------------------------------------------
            business_requirements: str = state.get("business_requirements", "")
            project_name: str = state.get("project_name", "unnamed_project")
            project_description: str = state.get("project_description", "")

            if not business_requirements.strip():
                raise ValueError("No business requirements provided in state.business_requirements")

            # Include any manual source metadata hints if present
            source_hint = ""
            manual_meta: dict = state.get("source_metadata_manual", {})
            if manual_meta:
                source_hint = (
                    "\n\nAdditional source metadata provided by the user:\n"
                    f"{json.dumps(manual_meta, indent=2)}\n"
                )

            prompt = (
                f"Project Name: {project_name}\n"
                f"Project Description: {project_description}\n\n"
                f"## Business Requirements\n{business_requirements}\n"
                f"{source_hint}\n"
                "Analyze the above requirements and return a JSON object with exactly "
                "these top-level keys:\n"
                "  objectives (list[str]),\n"
                "  source_systems (list of objects with 'name', 'type', 'description'),\n"
                "  business_entities (list of objects with 'name', 'description', 'source_system', 'key_columns'),\n"
                "  business_rules (list of objects with 'name', 'description', 'logic', 'affected_entities'),\n"
                "  transformation_requirements (list of objects with 'name', 'description', "
                "'source_entities', 'logic', 'priority'),\n"
                "  output_models (list of objects with 'name', 'description', 'grain', "
                "'key_columns', 'consumers'),\n"
                "  incremental_requirements (list of objects with 'entity', 'strategy', "
                "'timestamp_column', 'unique_key'),\n"
                "  data_quality_requirements (list of objects with 'entity', 'rule_type', "
                "'column', 'description', 'severity'),\n"
                "  assumptions (list[str]),\n"
                "  clarification_questions (list[str])\n\n"
                "Return ONLY the JSON object, no markdown fences."
            )

            # ------------------------------------------------------------------
            # 2. Call Gemini and parse the response as JSON
            # ------------------------------------------------------------------
            logger.info("RequirementAgent: calling Gemini for requirement analysis")
            raw_response: dict = self._call_gemini_json(prompt)

            # ------------------------------------------------------------------
            # 3. Validate via Pydantic
            # ------------------------------------------------------------------
            spec = ProjectSpecification.model_validate(raw_response)
            specification_dict: dict = spec.model_dump()

            logger.info(
                "RequirementAgent: parsed specification with %d objectives, "
                "%d source systems, %d entities, %d output models",
                len(spec.objectives),
                len(spec.source_systems),
                len(spec.business_entities),
                len(spec.output_models),
            )

            # ------------------------------------------------------------------
            # 4. Update state
            # ------------------------------------------------------------------
            state["project_specification"] = specification_dict

            # Track execution in history
            state.setdefault("execution_history", []).append({
                "agent": self.name,
                "action": "requirement_analysis",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "summary": (
                    f"Identified {len(spec.objectives)} objectives, "
                    f"{len(spec.source_systems)} source systems, "
                    f"{len(spec.business_entities)} entities, "
                    f"{len(spec.output_models)} output models"
                ),
            })

            if spec.clarification_questions:
                state.setdefault("warnings", []).append(
                    f"RequirementAgent: {len(spec.clarification_questions)} clarification "
                    "questions were generated — review before proceeding."
                )

            self._update_agent_status(
                state,
                "completed",
                f"Specification generated with {len(spec.output_models)} output models",
            )
            logger.info("RequirementAgent: execution completed successfully")

        except ValidationError as exc:
            error_msg = f"RequirementAgent: Pydantic validation failed — {exc}"
            logger.error(error_msg)
            state.setdefault("errors", []).append(error_msg)
            self._update_agent_status(state, "error", error_msg)

        except ValueError as exc:
            error_msg = f"RequirementAgent: {exc}"
            logger.error(error_msg)
            state.setdefault("errors", []).append(error_msg)
            self._update_agent_status(state, "error", error_msg)

        except Exception as exc:
            error_msg = f"RequirementAgent: unexpected error — {exc}"
            logger.exception(error_msg)
            state.setdefault("errors", []).append(error_msg)
            self._update_agent_status(state, "error", error_msg)

        return state
