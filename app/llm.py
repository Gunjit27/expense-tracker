import os

import requests

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")


class LLMError(RuntimeError):
    pass


class OllamaClient:
    """Minimal client for Ollama's /api/chat endpoint, with tool calling."""

    def __init__(self, model: str = OLLAMA_MODEL, base_url: str = OLLAMA_BASE_URL, timeout: int = 120):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
        payload = {"model": self.model, "messages": messages, "stream": False, "options": {"temperature": 0}}
        if tools:
            payload["tools"] = tools
        try:
            response = requests.post(f"{self.base_url}/api/chat", json=payload, timeout=self.timeout)
            response.raise_for_status()
            return response.json()["message"]
        except (requests.RequestException, KeyError, ValueError) as exc:
            raise LLMError(f"Ollama is unavailable: {exc}") from exc
