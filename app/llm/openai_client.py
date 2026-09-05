"""OpenAI-compatible structured-output adapter with a single repair retry."""

from __future__ import annotations

import json
from typing import Any, TypeVar

import requests
from pydantic import BaseModel, ValidationError

from app.llm.base import LLMClient

T = TypeVar("T", bound=BaseModel)


class LLMError(RuntimeError):
    pass


class OpenAICompatibleClient(LLMClient):
    def __init__(self, api_key: str, model: str, base_url: str = "https://api.openai.com/v1", timeout: int = 90) -> None:
        if not api_key:
            raise LLMError("OPENAI_API_KEY is not configured. Add it to .env.")
        if not model:
            raise LLMError("LLM_MODEL is not configured. Add it to .env.")
        self.api_key, self.model, self.base_url, self.timeout = api_key, model, base_url.rstrip("/"), timeout

    def structured(self, *, system_prompt: str, user_prompt: str, response_model: type[T]) -> T:
        messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]
        for attempt in range(2):
            raw = self._chat(messages, response_model)
            try:
                return response_model.model_validate_json(raw)
            except ValidationError as error:
                if attempt:
                    raise LLMError(f"LLM returned invalid structured output after retry: {error}") from error
                messages.append({"role": "assistant", "content": raw})
                messages.append({"role": "user", "content": f"Your JSON failed schema validation: {error}. Return a corrected JSON object only; do not add facts."})
        raise AssertionError("unreachable")

    def _chat(self, messages: list[dict[str, str]], response_model: type[BaseModel]) -> str:
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
        }
        try:
            response = requests.post(f"{self.base_url}/chat/completions", headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}, json=payload, timeout=self.timeout)
        except requests.RequestException as error:
            raise LLMError(f"LLM API request failed: {error}") from error
        if not response.ok:
            raise LLMError(f"LLM API request failed ({response.status_code}): {response.text[:500]}")
        try:
            content = response.json()["choices"][0]["message"]["content"]
            if isinstance(content, list):
                content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
            return str(content)
        except (KeyError, IndexError, ValueError, TypeError) as error:
            raise LLMError("LLM API response did not contain a message content field.") from error

