from __future__ import annotations

import os
import textwrap
from typing import Protocol

from src.models.transport import post_json


class LLMClient(Protocol):
    def generate(self, prompt: str, system_prompt: str | None = None, max_tokens: int = 800) -> str:
        ...


class EndpointLLMClient:
    """Configured chat-message endpoint; no service is selected implicitly."""

    def __init__(self, model: str, base_url: str, api_key: str | None = None) -> None:
        if not model or model == "analysis-model":
            raise ValueError("Set MODEL_NAME to a model served by your endpoint")
        self.model, self.base_url, self.api_key = model, base_url, api_key

    def generate(self, prompt: str, system_prompt: str | None = None, max_tokens: int = 800) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        result = post_json(self.base_url, "chat/completions", {
            "model": self.model, "messages": messages, "max_tokens": max_tokens,
        }, self.api_key)
        try:
            text = result["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ValueError("The configured endpoint returned no assistant message") from exc
        if not isinstance(text, str) or not text.strip():
            raise ValueError("The configured endpoint returned an empty assistant message")
        return text


class DeterministicStubLLM:
    """Offline plumbing fixture. Its output does not measure model quality."""

    def __init__(self, name: str = "stub-llm") -> None:
        self.name = name

    def generate(self, prompt: str, system_prompt: str | None = None, max_tokens: int = 800) -> str:
        snippet = textwrap.shorten(prompt.replace("\n", " "), width=180, placeholder="...")
        return f"LLM:{self.name} RESPONSE\n{snippet}"


def get_default_llm_client(model: str | None = None, api_key: str | None = None) -> LLMClient:
    base_url = os.getenv("LLM_BASE_URL", "").strip()
    key = api_key or os.getenv("LLM_API_KEY")
    if not base_url:
        if key:
            raise ValueError("LLM_API_KEY is set; configure LLM_BASE_URL before using live mode")
        return DeterministicStubLLM()
    return EndpointLLMClient(model or os.getenv("MODEL_NAME", ""), base_url, key)
