"""Unit tests for GeminiClient with mocked API."""

from unittest.mock import MagicMock, patch
import pytest

from integrations.gemini_client import GeminiClient


def test_gemini_client_init_requires_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with patch("integrations.gemini_client.get_settings") as mock_settings:
        mock_settings.return_value.gemini_api_key.get_secret_value.return_value = ""
        mock_settings.return_value.gemini_model = "gemini-3.5-flash"
        with pytest.raises(ValueError, match="GEMINI_API_KEY is not set"):
            GeminiClient(api_key="")


def test_gemini_client_generate_success():
    with patch("google.genai.Client") as mock_client_cls:
        mock_instance = MagicMock()
        mock_client_cls.return_value = mock_instance
        mock_response = MagicMock()
        mock_response.text = "Hello from Gemini"
        mock_instance.models.generate_content.return_value = mock_response

        client = GeminiClient(api_key="test-key-12345", model="gemini-3.5-flash")
        res = client.generate("test prompt")
        assert res == "Hello from Gemini"


def test_gemini_client_generate_json_parsing():
    with patch("google.genai.Client") as mock_client_cls:
        mock_instance = MagicMock()
        mock_client_cls.return_value = mock_instance
        mock_response = MagicMock()
        mock_response.text = '```json\n{"status": "ok", "items": [1, 2]}\n```'
        mock_instance.models.generate_content.return_value = mock_response

        client = GeminiClient(api_key="test-key-12345")
        data = client.generate_json("test prompt")
        assert data["status"] == "ok"
        assert len(data["items"]) == 2

