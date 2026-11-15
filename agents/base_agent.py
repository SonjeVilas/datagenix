"""Base Agent interface for all specialized dbt Project Factory agents."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
import logging
from typing import Any, Dict, Optional

from integrations.gemini_client import GeminiClient

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Abstract base class for all dbt Project Factory agents.

    Provides common Gemini client access, state status updates,
    and structured error handling.
    """

    def __init__(
        self,
        name: str,
        description: str,
        system_prompt: str,
    ) -> None:
        self.name = name
        self.description = description
        self.system_prompt = system_prompt
        self._gemini_client: Optional[GeminiClient] = None

    def _get_client(self) -> GeminiClient:
        """Lazily initialize or return the GeminiClient singleton."""
        if self._gemini_client is None:
            self._gemini_client = GeminiClient()
        return self._gemini_client

    def _call_gemini_json(self, prompt: str) -> Dict[str, Any]:
        """Send prompt to Gemini with system prompt and parse response as JSON."""
        client = self._get_client()
        return client.generate_json(
            prompt=prompt,
            system_prompt=self.system_prompt,
        )

    def _call_gemini(self, prompt: str) -> str:
        """Send prompt to Gemini with system prompt and return text."""
        client = self._get_client()
        return client.generate(
            prompt=prompt,
            system_prompt=self.system_prompt,
        )

    def _update_agent_status(
        self,
        state: Dict[str, Any],
        status: str,
        message: str = "",
    ) -> None:
        """Update agent execution status in shared state."""
        now = datetime.now(timezone.utc).isoformat()
        agent_statuses = state.setdefault("agent_status", {})
        curr = agent_statuses.get(self.name, {})

        update_info = {
            "name": self.name,
            "status": status,
            "message": message,
            "updated_at": now,
        }

        if status == "running":
            update_info["started_at"] = curr.get("started_at", now)
            state["current_agent"] = self.name
        elif status in ("completed", "error", "failed"):
            update_info["started_at"] = curr.get("started_at", now)
            update_info["completed_at"] = now
            if "started_at" in curr:
                try:
                    start_dt = datetime.fromisoformat(curr["started_at"])
                    end_dt = datetime.fromisoformat(now)
                    update_info["duration_seconds"] = round((end_dt - start_dt).total_seconds(), 2)
                except Exception:
                    pass

        agent_statuses[self.name] = {**curr, **update_info}

    @abstractmethod
    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the agent's core responsibility and return the updated state."""
        raise NotImplementedError

