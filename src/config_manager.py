from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


DEFAULT_CONFIG_PATH = Path.home() / ".codescan" / "config.json"


def ensure_user_config(example_path: Path, config_path: Path = DEFAULT_CONFIG_PATH) -> Path:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    if not config_path.exists():
        config_path.write_text(example_path.read_text(encoding="utf-8"), encoding="utf-8")
    return config_path


def load_config(config_path: Path = DEFAULT_CONFIG_PATH) -> Dict[str, Any]:
    with config_path.open("r", encoding="utf-8") as f:
        return json.load(f)
