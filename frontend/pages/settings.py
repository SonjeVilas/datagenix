"""Settings page for API keys, connections, and preferences."""

from __future__ import annotations

import logging
from typing import Any

import streamlit as st

logger = logging.getLogger(__name__)

try:
    from config.settings import Settings
except ImportError:
    Settings = None

try:
    from integrations.gemini_client import GeminiClient
except ImportError:
    GeminiClient = None

try:
    from integrations.snowflake_client import SnowflakeClient
except ImportError:
    SnowflakeClient = None


def _load_settings() -> dict[str, Any]:
    """Load current settings."""
    defaults = {
        "gemini_api_key": "",
        "gemini_model": "gemini-3.5-flash-lite",
        "snowflake_account": "",
        "snowflake_user": "",
        "snowflake_password": "",
        "snowflake_role": "SYSADMIN",
        "snowflake_warehouse": "",
        "snowflake_database": "",
        "snowflake_schema": "",
        "project_output_dir": "generated_projects",
        "max_retries": 3,
        "log_level": "INFO",
    }

    if Settings is not None:
        try:
            s = Settings()
            return {
                "gemini_api_key": s.gemini_api_key.get_secret_value() if hasattr(s.gemini_api_key, 'get_secret_value') else str(s.gemini_api_key),
                "gemini_model": getattr(s, "gemini_model", defaults["gemini_model"]),
                "snowflake_account": getattr(s, "snowflake_account", ""),
                "snowflake_user": getattr(s, "snowflake_user", ""),
                "snowflake_password": s.snowflake_password.get_secret_value() if hasattr(getattr(s, 'snowflake_password', None), 'get_secret_value') else str(getattr(s, "snowflake_password", "")),
                "snowflake_role": getattr(s, "snowflake_role", "SYSADMIN"),
                "snowflake_warehouse": getattr(s, "snowflake_warehouse", ""),
                "snowflake_database": getattr(s, "snowflake_database", ""),
                "snowflake_schema": getattr(s, "snowflake_schema", ""),
                "project_output_dir": getattr(s, "project_output_dir", defaults["project_output_dir"]),
                "max_retries": getattr(s, "max_retries", defaults["max_retries"]),
                "log_level": getattr(s, "log_level", defaults["log_level"]),
            }
        except Exception as e:
            logger.warning(f"Could not load settings from config: {e}")

    return defaults


def render_settings_page() -> None:
    """Render the Settings page."""
    st.markdown("## ⚙️ Settings")
    st.markdown("Configure API keys, connections, and application preferences.")
    st.markdown("---")

    current = _load_settings()

    with st.form("settings_form"):
        # Gemini Settings
        st.markdown("### 🤖 Gemini AI Configuration")
        col1, col2 = st.columns(2)

        with col1:
            gemini_key = st.text_input(
                "Gemini API Key *",
                value=current["gemini_api_key"],
                type="password",
                help="Your Google Gemini API key.",
                key="set_gemini_key",
            )
        with col2:
            model_options = ["gemini-3.5-flash-lite", "gemini-3.5-flash", "gemini-3.8-flash"]
            current_model = current.get("gemini_model", "gemini-3.5-flash-lite")
            default_index = model_options.index(current_model) if current_model in model_options else 0
            gemini_model = st.selectbox(
                "Gemini Model",
                options=model_options,
                index=default_index,
                key="set_gemini_model",
            )

        st.markdown("---")

        # Snowflake Settings
        st.markdown("### ❄️ Snowflake Connection")
        col1, col2, col3 = st.columns(3)

        with col1:
            sf_account = st.text_input(
                "Account",
                value=current["snowflake_account"],
                placeholder="org-account",
                key="set_sf_account",
            )
            sf_user = st.text_input(
                "Username",
                value=current["snowflake_user"],
                key="set_sf_user",
            )
        with col2:
            sf_password = st.text_input(
                "Password",
                value=current["snowflake_password"],
                type="password",
                key="set_sf_password",
            )
            sf_role = st.text_input(
                "Role",
                value=current["snowflake_role"],
                key="set_sf_role",
            )
        with col3:
            sf_warehouse = st.text_input(
                "Warehouse",
                value=current["snowflake_warehouse"],
                key="set_sf_warehouse",
            )
            sf_database = st.text_input(
                "Database",
                value=current["snowflake_database"],
                key="set_sf_database",
            )

        sf_schema = st.text_input(
            "Schema",
            value=current["snowflake_schema"],
            key="set_sf_schema",
        )

        st.markdown("---")

        # Project Settings
        st.markdown("### 📁 Project Configuration")
        col1, col2, col3 = st.columns(3)

        with col1:
            output_dir = st.text_input(
                "Project Output Directory",
                value=current["project_output_dir"],
                key="set_output_dir",
            )
        with col2:
            max_retries = st.number_input(
                "Max Retries",
                value=current["max_retries"],
                min_value=1,
                max_value=10,
                key="set_max_retries",
            )
        with col3:
            log_level = st.selectbox(
                "Log Level",
                options=["DEBUG", "INFO", "WARNING", "ERROR"],
                index=["DEBUG", "INFO", "WARNING", "ERROR"].index(
                    current["log_level"]
                )
                if current["log_level"] in ["DEBUG", "INFO", "WARNING", "ERROR"]
                else 1,
                key="set_log_level",
            )

        st.markdown("---")

        # Submit
        submitted = st.form_submit_button("💾 Save Settings", type="primary", width='stretch')

    if submitted:
        _save_settings(
            gemini_key=gemini_key,
            gemini_model=gemini_model,
            sf_account=sf_account,
            sf_user=sf_user,
            sf_password=sf_password,
            sf_role=sf_role,
            sf_warehouse=sf_warehouse,
            sf_database=sf_database,
            sf_schema=sf_schema,
            output_dir=output_dir,
            max_retries=max_retries,
            log_level=log_level,
        )

    # Test buttons (outside form)
    st.markdown("### 🧪 Connection Tests")

    test_feedback = st.session_state.pop("snowflake_test_feedback", None)
    if test_feedback:
        kind, msg = test_feedback
        if kind == "success":
            st.success(msg, icon="❄️")
        else:
            st.error(msg, icon="❌")

    gemini_feedback = st.session_state.pop("gemini_test_feedback", None)
    if gemini_feedback:
        kind, msg = gemini_feedback
        if kind == "success":
            st.success(msg, icon="🤖")
        else:
            st.error(msg, icon="❌")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("🤖 Test Gemini Connection", width='stretch'):
            _test_gemini_connection()

    with col2:
        if st.button("❄️ Test Snowflake Connection", width='stretch'):
            _test_snowflake_connection()


def _save_settings(**kwargs: Any) -> None:
    """Save settings to .env file and session state."""
    import os

    env_path = os.path.join(os.getcwd(), ".env")
    env_lines = [
        f"GEMINI_API_KEY={kwargs['gemini_key']}",
        f"GEMINI_MODEL={kwargs['gemini_model']}",
        f"SNOWFLAKE_ACCOUNT={kwargs['sf_account']}",
        f"SNOWFLAKE_USER={kwargs['sf_user']}",
        f"SNOWFLAKE_PASSWORD={kwargs['sf_password']}",
        f"SNOWFLAKE_ROLE={kwargs['sf_role']}",
        f"SNOWFLAKE_WAREHOUSE={kwargs['sf_warehouse']}",
        f"SNOWFLAKE_DATABASE={kwargs['sf_database']}",
        f"SNOWFLAKE_SCHEMA={kwargs['sf_schema']}",
        f"PROJECT_OUTPUT_DIR={kwargs['output_dir']}",
        f"MAX_RETRIES={kwargs['max_retries']}",
        f"LOG_LEVEL={kwargs['log_level']}",
    ]

    try:
        with open(env_path, "w", encoding="utf-8") as f:
            f.write("\n".join(env_lines) + "\n")
        st.success("✅ Settings saved to .env file!", icon="💾")
    except Exception as e:
        st.error(f"Could not save .env file: {e}", icon="❌")
        logger.exception("Settings save error")

    # Store in session state for immediate use
    st.session_state["app_settings"] = kwargs
    try:
        from config.settings import get_settings
        get_settings.cache_clear()
    except Exception:
        pass


def _test_gemini_connection() -> None:
    """Test the Gemini API connection."""
    settings = st.session_state.get("app_settings", {})
    api_key = settings.get("gemini_key", "")
    if not api_key:
        api_key = st.session_state.get("set_gemini_key", "")
    if not api_key:
        try:
            from config.settings import get_settings
            api_key = get_settings().gemini_api_key.get_secret_value()
        except Exception:
            api_key = ""

    if not api_key:
        st.error("Please enter or save a Gemini API key first.", icon="⚠️")
        return

    model = settings.get("gemini_model")
    if not model:
        model = st.session_state.get("set_gemini_model")
    if not model:
        try:
            from config.settings import get_settings
            model = get_settings().gemini_model
        except Exception:
            model = "gemini-3.5-flash-lite"

    if GeminiClient is not None:
        with st.spinner(f"Testing Gemini connection with model '{model}'..."):
            try:
                client = GeminiClient(api_key=api_key, model=model)
                response = client.generate("Say 'Hello, dbt Project Factory!' in one sentence.", system_prompt="You are a helpful assistant.")
                st.session_state["gemini_test_feedback"] = (
                    "success",
                    f"✅ Gemini connected successfully using model `{model}`!\n\n**Response:** {response[:200]}",
                )
                st.rerun()
            except Exception as e:
                st.session_state["gemini_test_feedback"] = ("error", f"❌ Gemini connection failed: {e}")
                st.rerun()
    else:
        st.warning("GeminiClient not available. Check backend installation.", icon="⚠️")


def _test_snowflake_connection() -> None:
    """Test the Snowflake connection."""
    settings = st.session_state.get("app_settings", {})
    account = settings.get("sf_account") or st.session_state.get("set_sf_account")
    user = settings.get("sf_user") or st.session_state.get("set_sf_user")
    password = settings.get("sf_password") or st.session_state.get("set_sf_password")
    role = settings.get("sf_role") or st.session_state.get("set_sf_role", "")
    warehouse = settings.get("sf_warehouse") or st.session_state.get("set_sf_warehouse", "")
    database = settings.get("sf_database") or st.session_state.get("set_sf_database", "")
    schema = settings.get("sf_schema") or st.session_state.get("set_sf_schema", "")

    if not account or not user or not password:
        try:
            from config.settings import get_settings
            s = get_settings()
            account = account or s.snowflake_account
            user = user or s.snowflake_user
            password = password or (s.snowflake_password.get_secret_value() if hasattr(s.snowflake_password, "get_secret_value") else str(s.snowflake_password))
            role = role or s.snowflake_role
            warehouse = warehouse or s.snowflake_warehouse
            database = database or s.snowflake_database
            schema = schema or s.snowflake_schema
        except Exception:
            pass

    if not account or not user or not password:
        st.error("Please enter Snowflake Account, Username, and Password (and click 'Save Settings').", icon="⚠️")
        return

    if SnowflakeClient is not None:
        with st.spinner("Testing Snowflake connection..."):
            try:
                client = SnowflakeClient(
                    account=account,
                    user=user,
                    password=password,
                    role=role or "ACCOUNTADMIN",
                    warehouse=warehouse or "COMPUTE_WH",
                    database=database or "",
                    schema=schema or "",
                )
                if client.test_connection():
                    st.session_state["snowflake_connected"] = True
                    curr_state = st.session_state.get("current_project_state", {})
                    curr_state["snowflake_connected"] = True
                    st.session_state["current_project_state"] = curr_state
                    st.session_state["snowflake_test_feedback"] = ("success", "✅ Snowflake connection successful!")
                    st.rerun()
                else:
                    st.session_state["snowflake_connected"] = False
                    curr_state = st.session_state.get("current_project_state", {})
                    curr_state["snowflake_connected"] = False
                    st.session_state["current_project_state"] = curr_state
                    st.session_state["snowflake_test_feedback"] = ("error", "❌ Snowflake connection test returned False.")
                    st.rerun()
            except Exception as e:
                st.session_state["snowflake_connected"] = False
                curr_state = st.session_state.get("current_project_state", {})
                curr_state["snowflake_connected"] = False
                st.session_state["current_project_state"] = curr_state
                st.session_state["snowflake_test_feedback"] = ("error", f"❌ Snowflake connection failed: {e}")
                st.rerun()
    else:
        st.warning("SnowflakeClient not available. Install snowflake-connector-python.", icon="⚠️")
