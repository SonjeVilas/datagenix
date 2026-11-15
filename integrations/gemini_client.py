"""Gemini API client using the google-genai SDK."""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Dict, Optional, Type

from google import genai
from google.genai import types
from pydantic import SecretStr
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from config.settings import get_settings

logger = logging.getLogger(__name__)

# Regex to strip markdown fences that Gemini sometimes wraps around JSON
_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*\n?(.*?)\n?\s*```", re.DOTALL)


def _gemini_wait(retry_state: Any) -> float:
    """Smart backoff that respects Gemini 429 retry-after recommendations."""
    exc = retry_state.outcome.exception() if retry_state.outcome else None
    if exc:
        msg = str(exc)
        match = re.search(r"retry in (\d+(?:\.\d+)?)s", msg, re.IGNORECASE)
        if not match:
            match = re.search(r"retryDelay': '(\d+)s", msg)
        if match:
            delay = float(match.group(1)) + 1.5
            logger.info("Rate limit hit: backing off for %.1fs as specified by API", delay)
            return max(1.0, min(delay, 60.0))
        if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
            logger.info("Rate limit 429 hit: backing off for 15s")
            return 15.0
    return min(1.5 ** retry_state.attempt_number * 2.0, 30.0)


def _mask_secret(value: str, visible: int = 4) -> str:
    """Return a masked version of *value* safe for logging."""
    if len(value) <= visible:
        return "***"
    return value[:visible] + "***"


class GeminiClient:
    """Thin wrapper around the *google-genai* SDK with retry logic."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ) -> None:
        settings = get_settings()
        resolved_key = api_key or settings.gemini_api_key.get_secret_value()
        raw_model = model or settings.gemini_model
        if raw_model.startswith("models/"):
            raw_model = raw_model.replace("models/", "", 1)
        self.model_name = raw_model

        if not resolved_key:
            raise ValueError(
                "GEMINI_API_KEY is not set.  Provide it via .env or constructor."
            )

        self.client = genai.Client(api_key=resolved_key)
        logger.info(
            "GeminiClient initialised (model=%s, key=%s)",
            self.model_name,
            _mask_secret(resolved_key),
        )

    # ── public helpers ──────────────────────────────────────────────────

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        response_schema: Optional[Type] = None,
    ) -> str:
        """Call Gemini and return the response text.

        Parameters
        ----------
        prompt:
            The user-turn content.
        system_prompt:
            Optional system instruction prepended to the conversation.
        response_schema:
            If provided, Gemini is asked to respond with structured JSON
            matching this Pydantic model / dict schema.
        """
        return self._call(
            prompt=prompt,
            system_prompt=system_prompt,
            response_schema=response_schema,
        )

    def generate_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Call Gemini, force JSON output, and return a parsed dict.

        The method first asks the model to produce JSON via the
        ``response_mime_type`` config.  If parsing still fails it
        attempts to extract a fenced JSON block from the raw text.
        """
        raw = self._call(
            prompt=prompt,
            system_prompt=system_prompt,
            force_json=True,
        )
        return self._parse_json(raw)

    # ── internals ───────────────────────────────────────────────────────

    @retry(
        retry=retry_if_exception_type((Exception,)),
        stop=stop_after_attempt(5),
        wait=_gemini_wait,
        reraise=True,
        before_sleep=lambda rs: logger.warning(
            "Gemini call retry #%s after %s",
            rs.attempt_number,
            rs.outcome.exception() if rs.outcome else "unknown",
        ),
    )
    def _call(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        response_schema: Optional[Type] = None,
        force_json: bool = False,
    ) -> str:
        """Low-level Gemini API call with tenacity retry."""
        config_kwargs: Dict[str, Any] = {}
        if system_prompt:
            config_kwargs["system_instruction"] = system_prompt
        if force_json:
            config_kwargs["response_mime_type"] = "application/json"
        if response_schema:
            config_kwargs["response_mime_type"] = "application/json"
            config_kwargs["response_schema"] = response_schema

        config = types.GenerateContentConfig(**config_kwargs) if config_kwargs else None

        logger.debug(
            "Gemini request  model=%s  prompt_len=%d  system_len=%d",
            self.model_name,
            len(prompt),
            len(system_prompt or ""),
        )

        t0 = time.time()
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=config,
        )
        elapsed = time.time() - t0

        if not response.text:
            raise ValueError("Gemini returned an empty response")

        logger.info(
            "Gemini response  model=%s  chars=%d  elapsed=%.1fs",
            self.model_name,
            len(response.text),
            elapsed,
        )
        return response.text

    @staticmethod
    def _parse_json(raw: str) -> Dict[str, Any]:
        """Best-effort JSON parse from raw Gemini text."""
        # Try direct parse first
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass

        # Try stripping markdown fences
        match = _JSON_FENCE_RE.search(raw)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        # Last resort: find first { … } block
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(raw[start : end + 1])
            except json.JSONDecodeError:
                pass

        raise ValueError(
            f"Failed to parse JSON from Gemini response (length={len(raw)}). "
            f"First 200 chars: {raw[:200]}"
        )
