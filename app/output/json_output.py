"""Timestamped, non-destructive JSON output helpers."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel


def create_run_directory(base: Path = Path("output"), now: datetime | None = None) -> Path:
    stamp = (now or datetime.now()).strftime("%Y-%m-%d_%H%M%S")
    candidate = base / stamp
    suffix = 1
    while candidate.exists():
        candidate = base / f"{stamp}_{suffix:02d}"
        suffix += 1
    (candidate / "raw").mkdir(parents=True, exist_ok=False)
    (candidate / "analysis").mkdir()
    return candidate


def write_json(path: Path, data: BaseModel | dict[str, Any] | list[Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, BaseModel):
        text = data.model_dump_json(indent=2)
    else:
        import json
        text = json.dumps(data, indent=2, default=_json_default)
    path.write_text(text, encoding="utf-8")


def _json_default(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    return str(value)
