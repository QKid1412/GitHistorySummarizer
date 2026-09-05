"""Protocol for an LLM provider; swap this adapter for a local model later."""

from __future__ import annotations

from typing import Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMClient(Protocol):
    def structured(self, *, system_prompt: str, user_prompt: str, response_model: type[T]) -> T:
        """Return a Pydantic-validated structured response."""

