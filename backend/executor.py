"""Safe execution service for dbt commands with approval gates and log capture."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional

from integrations.dbt_runner import DbtRunner

logger = logging.getLogger(__name__)


class ExecutionSecurityError(Exception):
    """Raised when an execution violates safety policies."""
    pass


class SafeExecutor:
    """Controls the execution of dbt and warehouse operations.

    Enforces:
    1. Human approval requirements for warehouse-connected tasks.
    2. Prevention of destructive operations against production databases.
    3. Safe subprocess invocation with timeouts and output capture.
    """

    def __init__(self, project_dir: Path | str) -> None:
        self.project_dir = Path(project_dir).resolve()
        self.runner = DbtRunner(self.project_dir)

    def execute_offline(self, command: str) -> Dict[str, Any]:
        """Execute safe offline commands (parse, compile, deps, docs generate)."""
        logger.info("Executing safe offline command: dbt %s in %s", command, self.project_dir)
        if command == "parse":
            return self.runner.parse()
        elif command == "compile":
            return self.runner.compile()
        elif command == "deps":
            return self.runner.deps()
        elif command == "docs":
            return self.runner.docs_generate()
        else:
            raise ExecutionSecurityError(
                f"Command 'dbt {command}' is not in the allowed offline command list."
            )

    def execute_with_approval(
        self,
        command: str,
        target: str = "dev",
        user_approved: bool = False,
        select: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute warehouse-affecting commands (test, run, build) only with explicit approval."""
        if not user_approved:
            logger.warning("Execution of 'dbt %s' blocked: user approval required.", command)
            return {
                "passed": False,
                "error": "Human approval required before warehouse execution.",
                "requires_approval": True,
                "command": f"dbt {command} --target {target}",
            }

        # Guard against production target without double check
        if target.lower() in ("prod", "production"):
            raise ExecutionSecurityError(
                "Automated execution against target 'prod' is strictly disallowed."
            )

        logger.info("User-approved execution: dbt %s (target=%s, select=%s)", command, target, select)
        if command == "test":
            return self.runner.test(target=target, select=select)
        elif command == "run":
            return self.runner.run(target=target, select=select)
        elif command == "build":
            return self.runner.build(target=target, select=select)
        else:
            raise ExecutionSecurityError(f"Unsupported warehouse command: 'dbt {command}'")

