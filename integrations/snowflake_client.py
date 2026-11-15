"""Optional Snowflake connector for source metadata discovery."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class SnowflakeClient:
    """Wrapper around ``snowflake-connector-python`` for read-only discovery.

    This client is intentionally **read-only**: it never modifies source
    tables.  Passwords are never logged.
    """

    def __init__(
        self,
        account: str = "",
        user: str = "",
        password: str = "",
        role: str = "",
        warehouse: str = "",
        database: str = "",
        schema: str = "",
    ) -> None:
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

        self._account = account
        self._user = user
        self._password = password  # never logged
        self._role = role
        self._warehouse = warehouse
        self._database = database
        self._schema = schema
        self._connection: Any = None

        logger.info(
            "SnowflakeClient configured (account=%s, user=%s, database=%s)",
            account,
            user,
            database,
        )

    # ── connection management ───────────────────────────────────────────

    def _connect(self) -> Any:
        """Lazily open (and cache) a Snowflake connection."""
        if self._connection is not None:
            return self._connection

        try:
            import snowflake.connector  # type: ignore[import-untyped]

            conn_kwargs: Dict[str, str] = {
                "account": self._account.strip(),
                "user": self._user.strip(),
                "password": self._password,
            }
            if self._role:
                conn_kwargs["role"] = self._role.strip()
            if self._warehouse:
                conn_kwargs["warehouse"] = self._warehouse.strip()
            if self._database:
                conn_kwargs["database"] = self._database.strip()
            if self._schema:
                conn_kwargs["schema"] = self._schema.strip()

            self._connection = snowflake.connector.connect(**conn_kwargs)
            logger.info("Snowflake connection established.")
            return self._connection
        except Exception:
            logger.exception("Failed to connect to Snowflake (password hidden).")
            raise

    def close(self) -> None:
        """Close the Snowflake connection if open."""
        if self._connection is not None:
            try:
                self._connection.close()
            except Exception:
                logger.warning("Error closing Snowflake connection.", exc_info=True)
            finally:
                self._connection = None

    # ── discovery ───────────────────────────────────────────────────────

    def test_connection(self) -> bool:
        """Return True if Snowflake is reachable."""
        try:
            conn = self._connect()
            cursor = conn.cursor()
            cursor.execute("SELECT CURRENT_VERSION()")
            version = cursor.fetchone()
            logger.info("Snowflake connection test OK — version %s", version)
            return True
        except Exception:
            logger.exception("Snowflake connection test failed.")
            return False

    def execute_query(self, query: str) -> List[Dict[str, Any]]:
        """Execute a read-only query and return results as list of dicts."""
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute(query)
        columns = [col[0].lower() for col in cursor.description] if cursor.description else []
        rows = cursor.fetchall()
        return [dict(zip(columns, row)) for row in rows]

    def discover_databases(self) -> List[str]:
        """List databases accessible to the current role."""
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute("SHOW DATABASES")
        rows = cursor.fetchall()
        databases = [row[1] for row in rows]
        logger.info("Discovered %d databases.", len(databases))
        return databases

    def discover_schemas(self, database: Optional[str] = None) -> List[str]:
        """List schemas in *database* (or the configured default)."""
        db = database or self._database
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute(f"SHOW SCHEMAS IN DATABASE {db}")
        rows = cursor.fetchall()
        schemas = [row[1] for row in rows]
        logger.info("Discovered %d schemas in %s.", len(schemas), db)
        return schemas

    def discover_tables(
        self,
        database: Optional[str] = None,
        schema: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Return a list of tables with basic metadata."""
        db = database or self._database
        sch = schema or self._schema or "PUBLIC"
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute(f"SHOW TABLES IN {db}.{sch}")
        rows = cursor.fetchall()
        tables: List[Dict[str, Any]] = []
        for row in rows:
            tables.append(
                {
                    "database": db,
                    "schema": sch,
                    "name": row[1],
                    "kind": row[3] if len(row) > 3 else "TABLE",
                    "rows": row[5] if len(row) > 5 else None,
                }
            )
        logger.info("Discovered %d tables in %s.%s.", len(tables), db, sch)
        return tables

    def get_columns(
        self,
        table: str,
        database: Optional[str] = None,
        schema: Optional[str] = None,
    ) -> List[Dict[str, str]]:
        """Return column-level metadata for *table*."""
        db = database or self._database
        sch = schema or self._schema or "PUBLIC"
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute(f"SHOW COLUMNS IN {db}.{sch}.{table}")
        rows = cursor.fetchall()
        columns: List[Dict[str, str]] = []
        for row in rows:
            columns.append(
                {
                    "table": table,
                    "column_name": row[2],
                    "data_type": row[3] if len(row) > 3 else "UNKNOWN",
                    "is_nullable": row[5] if len(row) > 5 else "YES",
                }
            )
        logger.info("Discovered %d columns for %s.%s.%s.", len(columns), db, sch, table)
        return columns

    def get_primary_keys(
        self,
        table: str,
        database: Optional[str] = None,
        schema: Optional[str] = None,
    ) -> List[str]:
        """Return primary key column names for *table* (best-effort)."""
        db = database or self._database
        sch = schema or self._schema or "PUBLIC"
        conn = self._connect()
        cursor = conn.cursor()
        try:
            cursor.execute(
                f"SHOW PRIMARY KEYS IN {db}.{sch}.{table}"
            )
            rows = cursor.fetchall()
            pk_cols = [row[4] for row in rows]
            logger.info("Primary keys for %s.%s.%s: %s", db, sch, table, pk_cols)
            return pk_cols
        except Exception:
            logger.debug("Could not retrieve PKs for %s.%s.%s.", db, sch, table)
            return []

    def get_foreign_keys(
        self,
        table: str,
        database: Optional[str] = None,
        schema: Optional[str] = None,
    ) -> List[Dict[str, str]]:
        """Return foreign key relationships for *table* (best-effort)."""
        db = database or self._database
        sch = schema or self._schema or "PUBLIC"
        conn = self._connect()
        cursor = conn.cursor()
        try:
            cursor.execute(
                f"SHOW IMPORTED KEYS IN {db}.{sch}.{table}"
            )
            rows = cursor.fetchall()
            fks: List[Dict[str, str]] = []
            for row in rows:
                fks.append(
                    {
                        "fk_column": row[7] if len(row) > 7 else "",
                        "pk_table": row[2] if len(row) > 2 else "",
                        "pk_column": row[3] if len(row) > 3 else "",
                    }
                )
            return fks
        except Exception:
            logger.debug("Could not retrieve FKs for %s.%s.%s.", db, sch, table)
            return []
