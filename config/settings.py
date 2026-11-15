"""Application settings using Pydantic BaseSettings with .env support."""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Central configuration loaded from environment variables / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Gemini API ──────────────────────────────────────────────────────
    gemini_api_key: SecretStr = Field(
        default=SecretStr(""),
        description="Google Gemini API key",
    )
    gemini_model: str = Field(
        default="gemini-3.5-flash",
        description="Gemini model identifier",
    )

    # ── Snowflake ───────────────────────────────────────────────────────
    snowflake_account: str = Field(default="", description="Snowflake account identifier")
    snowflake_user: str = Field(default="", description="Snowflake username")
    snowflake_password: SecretStr = Field(
        default=SecretStr(""),
        description="Snowflake password",
    )
    snowflake_role: str = Field(default="", description="Snowflake role")
    snowflake_warehouse: str = Field(default="", description="Snowflake warehouse")
    snowflake_database: str = Field(default="", description="Snowflake database")
    snowflake_schema: str = Field(default="", description="Snowflake schema")

    # ── Project ─────────────────────────────────────────────────────────
    project_output_dir: str = Field(
        default="generated_projects",
        description="Root directory for generated dbt projects",
    )
    max_retries: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum retry attempts for agent error correction",
    )
    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
    )

    # ── Derived helpers ─────────────────────────────────────────────────
    @property
    def project_output_path(self) -> Path:
        """Resolved absolute path to the project output directory."""
        return Path(self.project_output_dir).resolve()

    @property
    def snowflake_configured(self) -> bool:
        """Return True when all required Snowflake fields are set."""
        return bool(
            self.snowflake_account
            and self.snowflake_user
            and self.snowflake_password.get_secret_value()
            and self.snowflake_database
        )

    def configure_logging(self) -> None:
        """Apply the configured log level to the root logger."""
        level = getattr(logging, self.log_level.upper(), logging.INFO)
        logging.basicConfig(
            level=level,
            format="%(asctime)s | %(name)-30s | %(levelname)-7s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        logger.info("Logging configured at %s level", self.log_level.upper())


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached singleton of the application settings."""
    settings = Settings()
    settings.configure_logging()
    return settings
