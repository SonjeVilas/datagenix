"""
Data Architect Agent for Datagenix.

Designs the full dbt project architecture: layer structure (staging,
intermediate, marts), model inventory with naming conventions, materialization
strategies, and the dependency DAG.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional, Union

from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

from agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pydantic v2 schemas
# ---------------------------------------------------------------------------

class ModelDefinition(BaseModel):
    name: str = Field(..., description="Model name following naming convention")
    description: Optional[str] = Field(default="")
    layer: Optional[str] = Field(default="marts", description="staging | intermediate | marts")
    materialization: Optional[str] = Field(default="view", description="view | table | incremental | ephemeral")
    schema_name: Optional[str] = Field(default="", description="Target schema override")
    tags: list[str] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list, description="Model names this depends on")
    source_tables: list[str] = Field(default_factory=list, description="Source tables (for staging models)")
    grain: Optional[str] = Field(default="", description="Primary grain of the model")
    unique_key: Optional[str] = Field(default="", description="Unique key expression for incremental")
    incremental_strategy: Optional[str] = Field(default="", description="merge | delete+insert | append")

    @field_validator("description", "layer", "materialization", "schema_name", "grain", "unique_key", "incremental_strategy", mode="before")
    @classmethod
    def _coerce_opt_str(cls, v: Any) -> str:
        return str(v) if v is not None else ""

    @field_validator("tags", "depends_on", "source_tables", mode="before")
    @classmethod
    def _coerce_list_str(cls, v: Any) -> list[str]:
        if isinstance(v, list):
            return [str(x) for x in v if x is not None]
        return []


class LayerDefinition(BaseModel):
    name: str = Field(..., description="Layer name: staging, intermediate, or marts")
    description: Optional[str] = Field(default="")
    directory: str = Field(..., description="Relative directory path, e.g. models/staging")
    schema_prefix: Optional[str] = Field(default="")
    default_materialization: Optional[str] = Field(default="view")
    models: list[Union[ModelDefinition, str]] = Field(default_factory=list)

    @field_validator("description", "schema_prefix", "default_materialization", mode="before")
    @classmethod
    def _coerce_layer_str(cls, v: Any) -> str:
        return str(v) if v is not None else ""


class DagEdge(BaseModel):
    upstream: str = Field(..., description="Upstream model name")
    downstream: str = Field(..., description="Downstream model name")


class Architecture(BaseModel):
    layers: list[LayerDefinition] = Field(default_factory=list)
    models: list[ModelDefinition] = Field(default_factory=list, description="Flat list of all models across layers")
    dag_edges: list[DagEdge] = Field(default_factory=list, description="Explicit DAG edges")
    naming_conventions: dict[str, str] = Field(
        default_factory=lambda: {
            "staging": "stg_<source>__<table>",
            "intermediate": "int_<entity>__<verb>",
            "dimension": "dim_<entity>",
            "fact": "fct_<entity>",
        },
        description="Naming convention templates per model type",
    )
    materialization_strategy: dict[str, str] = Field(
        default_factory=lambda: {
            "staging": "view",
            "intermediate": "ephemeral",
            "marts_dimensions": "table",
            "marts_facts": "incremental",
        },
        description="Default materialization per layer/type",
    )
    design_decisions: list[str] = Field(default_factory=list, description="Key architectural decisions")

    @model_validator(mode="after")
    def _sync_models(self) -> Architecture:
        # If models is empty or fewer than layers models, sync them
        if not self.models:
            flat_models = []
            for layer in self.layers:
                for m in layer.models:
                    if isinstance(m, ModelDefinition):
                        flat_models.append(m)
                    elif isinstance(m, str):
                        flat_models.append(ModelDefinition(name=m, layer=layer.name))
            self.models = flat_models
        return self


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class ArchitectAgent(BaseAgent):
    """Designs the dbt project architecture from spec and source catalog."""

    def __init__(self) -> None:
        super().__init__(
            name="data_architect",
            description=(
                "Designs the complete dbt project architecture including layer structure, "
                "model inventory, naming conventions, materialization strategies, and DAG."
            ),
            system_prompt=(
                "You are a principal analytics engineer and data architect specializing in "
                "dbt project design. You have extensive experience building enterprise-grade "
                "data warehouses on Snowflake using the dbt framework.\n\n"
                "Your role is to take a project specification and a source catalog and "
                "produce a complete dbt architecture that follows industry best practices:\n\n"
                "1. **Layer design**: Define a clear staging → intermediate → marts pipeline. "
                "Staging models (prefixed stg_) are 1:1 with source tables and perform only "
                "renaming, type casting, and basic cleaning. Intermediate models (prefixed "
                "int_) join, filter, and reshape data. Marts models are either dimensions "
                "(prefixed dim_) or facts (prefixed fct_) that serve the business.\n\n"
                "2. **Naming conventions**: stg_<source>__<table>, int_<entity>__<verb>, "
                "dim_<entity>, fct_<entity>. Strictly follow these patterns.\n\n"
                "3. **Materialization strategy**: staging → view (fast, no storage cost); "
                "intermediate → ephemeral or view; dimensions → table; facts → incremental "
                "(merge on unique key). Override per model when justified.\n\n"
                "4. **DAG construction**: Every model must declare its dependencies. The DAG "
                "must be a directed acyclic graph with no cycles. Staging depends on sources "
                "only; intermediates on staging or other intermediates; marts on intermediates "
                "or staging.\n\n"
                "5. **Design decisions**: Document trade-offs (star schema vs OBT, wide vs "
                "narrow tables, incremental strategy choices) and justify them.\n\n"
                "Return a single JSON object (no markdown fences) with keys: layers, models, "
                "dag_edges, naming_conventions, materialization_strategy, design_decisions."
            ),
        )

    def execute(self, state: dict) -> dict:
        """Design the dbt architecture and populate state.architecture."""
        logger.info("ArchitectAgent: starting execution")
        self._update_agent_status(state, "running", "Designing dbt project architecture")

        try:
            project_spec: dict = state.get("project_specification", {})
            source_catalog: dict = state.get("source_catalog", {})

            if not project_spec:
                raise ValueError("No project_specification found in state — run RequirementAgent first")

            # ----------------------------------------------------------
            # Build prompt
            # ----------------------------------------------------------
            prompt = (
                "Design a complete dbt project architecture based on the following inputs.\n\n"
                f"## Project Specification\n{json.dumps(project_spec, indent=2)}\n\n"
                f"## Source Catalog\n{json.dumps(source_catalog, indent=2)}\n\n"
                "Requirements:\n"
                "- Create a staging model (stg_) for every source table.\n"
                "- Create intermediate models (int_) for necessary joins and transformations.\n"
                "- Create dimension (dim_) and fact (fct_) models for the marts layer.\n"
                "- Assign materializations: staging=view, intermediate=ephemeral, "
                "dims=table, facts=incremental where appropriate.\n"
                "- Build a complete dependency DAG (dag_edges).\n"
                "- Document naming conventions and design decisions.\n\n"
                "Return a JSON object with keys:\n"
                "  layers (list of layer objects with name, description, directory, "
                "schema_prefix, default_materialization, models),\n"
                "  models (flat list of all model objects with name, description, layer, "
                "materialization, schema_name, tags, depends_on, source_tables, grain, "
                "unique_key, incremental_strategy),\n"
                "  dag_edges (list with upstream, downstream),\n"
                "  naming_conventions (dict mapping type to pattern),\n"
                "  materialization_strategy (dict mapping layer to materialization),\n"
                "  design_decisions (list of strings).\n\n"
                "Return ONLY the JSON object, no markdown fences."
            )

            # ----------------------------------------------------------
            # Call Gemini
            # ----------------------------------------------------------
            logger.info("ArchitectAgent: calling Gemini for architecture design")
            raw_response: dict = self._call_gemini_json(prompt)

            # ----------------------------------------------------------
            # Validate
            # ----------------------------------------------------------
            architecture = Architecture.model_validate(raw_response)
            architecture_dict: dict = architecture.model_dump()

            total_models = len(architecture.models)
            layer_counts = {}
            for model in architecture.models:
                layer_counts[model.layer] = layer_counts.get(model.layer, 0) + 1

            logger.info(
                "ArchitectAgent: designed %d models across %d layers: %s",
                total_models,
                len(architecture.layers),
                layer_counts,
            )

            # ----------------------------------------------------------
            # Update state
            # ----------------------------------------------------------
            state["architecture"] = architecture_dict

            state.setdefault("execution_history", []).append({
                "agent": self.name,
                "action": "architecture_design",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "summary": (
                    f"Designed architecture with {total_models} models, "
                    f"{len(architecture.dag_edges)} DAG edges, "
                    f"layers: {layer_counts}"
                ),
            })

            self._update_agent_status(
                state,
                "completed",
                f"Architecture designed: {total_models} models, {len(architecture.dag_edges)} edges",
            )
            logger.info("ArchitectAgent: execution completed successfully")

        except ValidationError as exc:
            error_msg = f"ArchitectAgent: Pydantic validation failed — {exc}"
            logger.error(error_msg)
            state.setdefault("errors", []).append(error_msg)
            self._update_agent_status(state, "error", error_msg)

        except ValueError as exc:
            error_msg = f"ArchitectAgent: {exc}"
            logger.error(error_msg)
            state.setdefault("errors", []).append(error_msg)
            self._update_agent_status(state, "error", error_msg)

        except Exception as exc:
            error_msg = f"ArchitectAgent: unexpected error — {exc}"
            logger.exception(error_msg)
            state.setdefault("errors", []).append(error_msg)
            self._update_agent_status(state, "error", error_msg)

        return state
