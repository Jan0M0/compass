# -*- coding: utf-8 -*-
"""Compass service configuration and local identity storage.

Everything lives under ~/.compass. The product is the running service; the CLI
only talks to it over HTTP.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

HOME = Path(os.environ.get("COMPASS_HOME", Path.home() / ".compass")).expanduser()
DB_PATH = HOME / "compass.db"
CONFIG_PATH = HOME / "config.json"
LOG_DIR = HOME / "logs"
DEFAULT_PORT = int(os.environ.get("COMPASS_PORT", "8765"))
BASE_URL = os.environ.get("COMPASS_BASE_URL", f"http://127.0.0.1:{DEFAULT_PORT}")


def ensure_home() -> None:
    HOME.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def read_config() -> dict:
    if not CONFIG_PATH.exists():
        return {}
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def write_config(cfg: dict) -> None:
    ensure_home()
    CONFIG_PATH.write_text(
        json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n"
    )
    try:
        os.chmod(CONFIG_PATH, 0o600)
    except OSError:
        pass
