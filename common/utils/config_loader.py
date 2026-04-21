import os
from pathlib import Path

try:
    import yaml  # type: ignore
except ModuleNotFoundError:
    yaml = None


def load_env_config() -> dict:
    env_name = os.getenv("TEST_ENV", "dev")
    config_path = Path(__file__).resolve().parents[2] / "config" / f"{env_name}.yaml"
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    text = config_path.read_text(encoding="utf-8")
    if yaml is not None:
        data = yaml.safe_load(text) or {}
        # 清理可能存在的 BOM
        cleaned = {}
        for k, v in data.items():
            if isinstance(k, str):
                cleaned[k.lstrip("\ufeff")] = v
            else:
                cleaned[k] = v
        return cleaned

    # 兜底：不依赖 PyYAML 的极简 YAML 解析（仅支持 key: value）
    result: dict = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        # 兼容 BOM：有些编辑器会在文件首行引入 \ufeff，导致 key 变成奇怪字符
        key = k.strip().lstrip("\ufeff").strip()
        val = v.strip()
        if val.startswith('"') and val.endswith('"'):
            val = val[1:-1]
        elif val.startswith("'") and val.endswith("'"):
            val = val[1:-1]
        low = val.lower()
        if low == "true":
            parsed = True
        elif low == "false":
            parsed = False
        else:
            # int（例如 timeout: 15）
            if val.isdigit():
                parsed = int(val)
            else:
                # 兜底为字符串（例如 token/URL）
                parsed = val
        result[key] = parsed
    # 清理可能存在的 BOM（兜底解析路径）
    cleaned = {}
    for k, v in result.items():
        if isinstance(k, str):
            cleaned[k.lstrip("\ufeff")] = v
        else:
            cleaned[k] = v
    return cleaned
