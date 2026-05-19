from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml


def read_yaml(path: str | Path) -> Any:
    file_path = Path(path)
    return yaml.safe_load(file_path.read_text(encoding="utf-8"))


def read_json(path: str | Path) -> Any:
    file_path = Path(path)
    return json.loads(file_path.read_text(encoding="utf-8"))
