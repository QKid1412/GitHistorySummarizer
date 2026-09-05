"""Configuration loaded from environment variables only."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    github_token: str | None
    openai_api_key: str | None
    llm_model: str | None
    max_prs: int = 20
    allow_raw_diff: bool = True
    max_diff_chars: int = 30_000
    llm_base_url: str = "https://api.openai.com/v1"
    request_timeout_seconds: int = 30

    @classmethod
    def load(cls, env_file: Path | None = None) -> "Settings":
        load_dotenv(dotenv_path=env_file, override=False)
        return cls(
            github_token=_optional("GITHUB_TOKEN"),
            openai_api_key=_optional("OPENAI_API_KEY"),
            llm_model=_optional("LLM_MODEL"),
            max_prs=_positive_int("MAX_PRS", 20),
            allow_raw_diff=_boolean("ALLOW_RAW_DIFF", True),
            max_diff_chars=_positive_int("MAX_DIFF_CHARS", 30_000),
            llm_base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/"),
        )


def _optional(name: str) -> str | None:
    value = os.getenv(name, "").strip()
    return value or None


def _positive_int(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
        return value if value > 0 else default
    except ValueError:
        return default


def _boolean(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}

