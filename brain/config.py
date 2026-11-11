"""Config loading. Model IDs, thresholds and paths come from config/agent.yaml only."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
KEY_NAMES = ("SARVAM_API_KEY", "SARVAM_AI_API_KEY")  # same key, two spellings


@lru_cache(maxsize=1)
def load_config() -> dict[str, Any]:
    with (ROOT / "config" / "agent.yaml").open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_api_key() -> str:
    load_dotenv(ROOT / ".env")
    for name in KEY_NAMES:
        if os.environ.get(name):
            return os.environ[name]
    raise RuntimeError(f"Set one of {KEY_NAMES} in .env or the environment")
