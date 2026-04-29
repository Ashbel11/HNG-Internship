import json
import os
from pathlib import Path

CONFIG_DIR = Path.home() / ".insighta"
CONFIG_FILE = CONFIG_DIR / "config.json"


def _ensure_dir():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def save_tokens(access_token: str, refresh_token: str):
    _ensure_dir()
    CONFIG_FILE.write_text(
        json.dumps({"access_token": access_token, "refresh_token": refresh_token}, indent=2)
    )


def get_tokens() -> dict | None:
    if not CONFIG_FILE.exists():
        return None
    try:
        return json.loads(CONFIG_FILE.read_text())
    except Exception:
        return None


def clear_tokens():
    if CONFIG_FILE.exists():
        CONFIG_FILE.write_text(json.dumps({}))


def is_logged_in() -> bool:
    tokens = get_tokens()
    return bool(tokens and tokens.get("access_token"))