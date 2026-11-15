"""Unit tests for configuration and settings."""

from pydantic import SecretStr
import pytest

from config.settings import Settings


def test_settings_defaults():
    settings = Settings(_env_file=None)
    assert settings.gemini_model == "gemini-3.5-flash-lite"
    assert settings.max_retries == 3
    assert settings.log_level == "INFO"
    assert settings.project_output_dir == "generated_projects"
    assert not settings.snowflake_configured


def test_settings_secret_masking():
    settings = Settings(_env_file=None, gemini_api_key=SecretStr("super-secret-key-123"))
    assert settings.gemini_api_key.get_secret_value() == "super-secret-key-123"
    assert "super-secret" not in str(settings.gemini_api_key)


def test_snowflake_configured_property():
    s_empty = Settings(_env_file=None)
    assert not s_empty.snowflake_configured

    s_full = Settings(
        _env_file=None,
        snowflake_account="xy12345",
        snowflake_user="myuser",
        snowflake_password=SecretStr("mypassword"),
        snowflake_database="ANALYTICS",
    )
    assert s_full.snowflake_configured

