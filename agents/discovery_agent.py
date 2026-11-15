"""
Data Discovery Agent for dbt Project Factory.

Connects to Snowflake (when available) or uses manually-supplied metadata to
build a comprehensive source catalog describing tables, columns, data types,
row counts, relationships, and sample values.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional, Union

from pydantic import BaseModel, Field, ValidationError, field_validator

from agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pydantic v2 schemas
# ---------------------------------------------------------------------------

class ColumnInfo(BaseModel):
    name: str = Field(..., description="Column name")
    data_type: str = Field(..., description="SQL data type")
    is_nullable: bool = Field(default=True)
    is_primary_key: bool = Field(default=False)
    is_foreign_key: bool = Field(default=False)
    foreign_key_ref: Optional[str] = Field(default="", description="Referenced table.column if FK")
    description: Optional[str] = Field(default="")
    sample_values: list[Any] = Field(default_factory=list)

    @field_validator("foreign_key_ref", "description", mode="before")
    @classmethod
    def _coerce_str(cls, v: Any) -> str:
        return str(v) if v is not None else ""

    @field_validator("sample_values", mode="before")
    @classmethod
    def _coerce_samples(cls, v: Any) -> list[str]:
        if isinstance(v, list):
            return [str(x) for x in v if x is not None]
        return []


class TableInfo(BaseModel):
    database: Optional[str] = Field(default="")
    schema_name: Optional[str] = Field(default="", alias="schema")
    table_name: str = Field(...)
    table_type: Optional[str] = Field(default="BASE TABLE", description="BASE TABLE or VIEW")
    row_count: Optional[int] = Field(default=0)
    columns: list[ColumnInfo] = Field(default_factory=list)
    description: Optional[str] = Field(default="")

    model_config = {"populate_by_name": True}

    @field_validator("database", "schema_name", "table_type", "description", mode="before")
    @classmethod
    def _coerce_table_str(cls, v: Any) -> str:
        return str(v) if v is not None else ""

    @field_validator("row_count", mode="before")
    @classmethod
    def _coerce_int(cls, v: Any) -> int:
        try:
            return int(v) if v is not None else 0
        except (ValueError, TypeError):
            return 0


class Relationship(BaseModel):
    from_table: str = Field(...)
    from_column: str = Field(...)
    to_table: str = Field(...)
    to_column: str = Field(...)
    relationship_type: str = Field(default="many_to_one", description="one_to_one | one_to_many | many_to_one | many_to_many")


class SourceCatalog(BaseModel):
    tables: list[TableInfo] = Field(default_factory=list)
    relationships: list[Relationship] = Field(default_factory=list)
    source_databases: list[str] = Field(default_factory=list)
    source_schemas: list[str] = Field(default_factory=list)
    discovery_method: str = Field(default="manual", description="snowflake or manual or gemini_inferred")


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class DiscoveryAgent(BaseAgent):
    """Discovers source data structures from Snowflake or manual metadata."""

    def __init__(self) -> None:
        super().__init__(
            name="data_discovery",
            description=(
                "Discovers and catalogues source data structures — tables, columns, "
                "data types, row counts, and relationships — from Snowflake or "
                "manually-supplied metadata."
            ),
            system_prompt=(
                "You are a data discovery specialist with deep expertise in relational "
                "databases, Snowflake, and data cataloging. Your job is to examine raw "
                "metadata — either queried directly from Snowflake's INFORMATION_SCHEMA "
                "or supplied manually by a user — and produce a clean, normalized source "
                "catalog.\n\n"
                "When building the catalog you must:\n"
                "1. List every table with its fully-qualified name (database.schema.table), "
                "type (BASE TABLE / VIEW), and approximate row count.\n"
                "2. For each table list every column with its data type, nullability, and "
                "whether it is part of a primary or foreign key.\n"
                "3. Infer relationships between tables by matching column names, naming "
                "conventions (e.g. *_id), and explicit foreign-key constraints.\n"
                "4. Suggest short descriptions for each table and column where possible.\n"
                "5. Note any data-quality concerns you observe (wide NULLable columns, "
                "suspicious data types, missing keys).\n\n"
                "Return a single JSON object (no markdown fences) with top-level keys: "
                "tables, relationships, source_databases, source_schemas, discovery_method."
            ),
        )

    # ------------------------------------------------------------------
    # Snowflake metadata queries
    # ------------------------------------------------------------------
    @staticmethod
    def _query_snowflake_metadata(snowflake_client: Any) -> dict[str, Any]:
        """Run INFORMATION_SCHEMA queries against Snowflake and return raw metadata."""
        metadata: dict[str, Any] = {"tables": [], "columns": [], "keys": []}

        # Tables
        tables_query = (
            "SELECT table_catalog, table_schema, table_name, table_type, row_count "
            "FROM information_schema.tables "
            "WHERE table_schema NOT IN ('INFORMATION_SCHEMA') "
            "ORDER BY table_schema, table_name"
        )
        try:
            metadata["tables"] = snowflake_client.execute_query(tables_query)
        except Exception as exc:
            logger.warning("DiscoveryAgent: table query failed — %s", exc)

        # Columns
        columns_query = (
            "SELECT table_catalog, table_schema, table_name, column_name, "
            "data_type, is_nullable, column_default, ordinal_position, "
            "character_maximum_length, numeric_precision, numeric_scale "
            "FROM information_schema.columns "
            "WHERE table_schema NOT IN ('INFORMATION_SCHEMA') "
            "ORDER BY table_schema, table_name, ordinal_position"
        )
        try:
            metadata["columns"] = snowflake_client.execute_query(columns_query)
        except Exception as exc:
            logger.warning("DiscoveryAgent: columns query failed — %s", exc)

        # Primary / foreign keys / table constraints
        keys_query = (
            "SELECT tc.table_schema, tc.table_name, tc.constraint_type, tc.constraint_name "
            "FROM information_schema.table_constraints tc "
            "WHERE tc.table_schema NOT IN ('INFORMATION_SCHEMA') "
            "ORDER BY tc.table_schema, tc.table_name"
        )
        try:
            metadata["keys"] = snowflake_client.execute_query(keys_query)
        except Exception as exc:
            logger.debug("DiscoveryAgent: keys query note — %s", exc)

        return metadata

    # ------------------------------------------------------------------
    # Execute
    # ------------------------------------------------------------------
    def execute(self, state: dict) -> dict:
        """Discover source structures and populate state.source_catalog."""
        logger.info("DiscoveryAgent: starting execution")
        self._update_agent_status(state, "running", "Discovering source data structures")

        try:
            snowflake_connected: bool = state.get("snowflake_connected", False)
            raw_metadata: dict[str, Any] = {}
            discovery_method = "manual"

            # ----------------------------------------------------------
            # Path A: Live Snowflake connection
            # ----------------------------------------------------------
            if snowflake_connected:
                logger.info("DiscoveryAgent: querying Snowflake for metadata")
                discovery_method = "snowflake"
                try:
                    from integrations.snowflake_client import SnowflakeClient

                    sf_client = SnowflakeClient()
                    raw_metadata = self._query_snowflake_metadata(sf_client)
                except Exception as exc:
                    logger.warning(
                        "DiscoveryAgent: Snowflake query failed, falling back to manual — %s",
                        exc,
                    )
                    snowflake_connected = False
                    discovery_method = "manual"

            # ----------------------------------------------------------
            # Path B: Manual / user-supplied metadata
            # ----------------------------------------------------------
            if not snowflake_connected:
                manual_meta: dict = state.get("source_metadata_manual", {})
                if manual_meta:
                    raw_metadata = manual_meta
                    discovery_method = "manual"
                    logger.info("DiscoveryAgent: using manually-supplied source metadata")
                else:
                    # Use project specification to infer sources via Gemini
                    discovery_method = "gemini_inferred"
                    logger.info("DiscoveryAgent: no metadata available — asking Gemini to infer")

            # ----------------------------------------------------------
            # Build prompt
            # ----------------------------------------------------------
            project_spec: dict = state.get("project_specification", {})

            if discovery_method == "gemini_inferred":
                prompt = (
                    "Based on the following project specification, infer the most likely "
                    "source database tables, columns, data types, and relationships that "
                    "would be needed.\n\n"
                    f"Project Specification:\n{json.dumps(project_spec, indent=2)}\n\n"
                    "Return a JSON object with keys: tables (list of table objects each with "
                    "database, schema, table_name, table_type, row_count, columns, description), "
                    "relationships (list with from_table, from_column, to_table, to_column, "
                    "relationship_type), source_databases, source_schemas, discovery_method.\n"
                    "Each column object needs: name, data_type, is_nullable, is_primary_key, "
                    "is_foreign_key, foreign_key_ref, description, sample_values.\n"
                    "Return ONLY the JSON object, no markdown fences."
                )
            else:
                prompt = (
                    "Analyze the following raw source metadata and normalize it into a "
                    "clean source catalog.\n\n"
                    f"Raw Metadata:\n{json.dumps(raw_metadata, indent=2)}\n\n"
                    f"Project Specification (for context):\n{json.dumps(project_spec, indent=2)}\n\n"
                    "Return a JSON object with keys: tables, relationships, "
                    "source_databases, source_schemas, discovery_method.\n"
                    "Each table object: database, schema, table_name, table_type, row_count, "
                    "columns (list), description.\n"
                    "Each column: name, data_type, is_nullable, is_primary_key, is_foreign_key, "
                    "foreign_key_ref, description, sample_values.\n"
                    "Each relationship: from_table, from_column, to_table, to_column, "
                    "relationship_type.\n"
                    "Return ONLY the JSON object, no markdown fences."
                )

            # ----------------------------------------------------------
            # Call Gemini
            # ----------------------------------------------------------
            logger.info("DiscoveryAgent: calling Gemini to build source catalog")
            raw_response: dict = self._call_gemini_json(prompt)

            # Force correct discovery_method
            raw_response["discovery_method"] = discovery_method

            # ----------------------------------------------------------
            # Validate
            # ----------------------------------------------------------
            catalog = SourceCatalog.model_validate(raw_response)
            catalog_dict: dict = catalog.model_dump(by_alias=True)

            logger.info(
                "DiscoveryAgent: catalog built — %d tables, %d relationships, method=%s",
                len(catalog.tables),
                len(catalog.relationships),
                catalog.discovery_method,
            )

            # ----------------------------------------------------------
            # Update state
            # ----------------------------------------------------------
            state["source_catalog"] = catalog_dict

            state.setdefault("execution_history", []).append({
                "agent": self.name,
                "action": "data_discovery",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "summary": (
                    f"Discovered {len(catalog.tables)} tables, "
                    f"{len(catalog.relationships)} relationships via {discovery_method}"
                ),
            })

            self._update_agent_status(
                state,
                "completed",
                f"Catalog built: {len(catalog.tables)} tables via {discovery_method}",
            )
            logger.info("DiscoveryAgent: execution completed successfully")

        except ValidationError as exc:
            error_msg = f"DiscoveryAgent: Pydantic validation failed — {exc}"
            logger.error(error_msg)
            state.setdefault("errors", []).append(error_msg)
            self._update_agent_status(state, "error", error_msg)

        except Exception as exc:
            error_msg = f"DiscoveryAgent: unexpected error — {exc}"
            logger.exception(error_msg)
            state.setdefault("errors", []).append(error_msg)
            self._update_agent_status(state, "error", error_msg)

        return state
