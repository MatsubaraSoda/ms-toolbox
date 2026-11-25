import os

from ms_toolbox.config import CONFIG_DIR, sync_defaults, yaml

# Harness 专属配置与会话数据目录：%LOCALAPPDATA%/ms-toolbox/harness/
HARNESS_DIR = CONFIG_DIR / "harness"
HARNESS_CONFIG_YAML = HARNESS_DIR / "config.yaml"
PRESETS_YAML = HARNESS_DIR / "presets.yaml"
SESSIONS_DIR = HARNESS_DIR / "sessions"
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_HARNESS_CONFIG_YAML = """
port: 8000
max_steps: 5
stream: true
workspace_dir:
api_key: sk-xx
url: https://openrouter.ai/api/v1/chat/completions
model:
provider:
tools:
  - base
web_provider: tavily
web_api_key:
system_prompt:
"""

TEXT_KEYS = ["workspace_dir", "model", "provider", "system_prompt"]


def get_harness_config() -> dict:
    """读取 harness/config.yaml，不存在时自动生成默认文件并补齐缺失键"""
    default_cfg = yaml.load(DEFAULT_HARNESS_CONFIG_YAML.strip())

    if not HARNESS_CONFIG_YAML.exists():
        HARNESS_DIR.mkdir(parents=True, exist_ok=True)
        HARNESS_CONFIG_YAML.write_text(DEFAULT_HARNESS_CONFIG_YAML.strip(), encoding="utf-8")
        return default_cfg

    with HARNESS_CONFIG_YAML.open("r", encoding="utf-8") as f:
        cfg = yaml.load(f)

    if sync_defaults(cfg, default_cfg):
        with HARNESS_CONFIG_YAML.open("w", encoding="utf-8") as f:
            yaml.dump(cfg, f)

    return cfg


def _format_preset(name: str, data: dict) -> dict:
    """将预设字典标准化（None 转为空字符串或空列表）"""
    preset = {"name": str(name)}
    for key in TEXT_KEYS:
        preset[key] = "" if data[key] is None else str(data[key])
    preset["tools"] = list(data["tools"] or [])
    return preset


def get_presets() -> list[dict]:
    """读取 default 与 presets.yaml 组装完整预设列表（缺位继承 default，留空转为 "" 或 []）"""
    default_preset = _format_preset("default", get_harness_config())
    presets = [default_preset]

    if not PRESETS_YAML.exists():
        HARNESS_DIR.mkdir(parents=True, exist_ok=True)
        PRESETS_YAML.write_text("", encoding="utf-8")
        return presets

    with PRESETS_YAML.open("r", encoding="utf-8") as f:
        items = yaml.load(f) or []

    for item in items:
        if not item or not item.get("name"):
            continue

        merged = default_preset.copy()
        merged.update(item)
        presets.append(_format_preset(item["name"], merged))

    return presets


def open_config():
    """确保 harness/config.yaml 存在并使用系统默认程序打开"""
    get_harness_config()
    os.startfile(HARNESS_CONFIG_YAML)


def open_presets():
    """确保 harness/presets.yaml 存在并使用系统默认程序打开"""
    get_presets()
    os.startfile(PRESETS_YAML)
