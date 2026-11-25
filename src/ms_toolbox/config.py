from pathlib import Path
from platformdirs import user_config_path
from ruamel.yaml import YAML

APP_NAME = "ms-toolbox"
CONFIG_DIR: Path = user_config_path(APP_NAME, appauthor=False)
CONFIG_YAML: Path = CONFIG_DIR / "config.yaml"

DEFAULT_CONFIG_YAML = """
tipo_worker_python_exe:
"""

yaml = YAML()
yaml.preserve_quotes = True
yaml.indent(mapping=2, sequence=4, offset=2)


def sync_defaults(current: dict, default: dict) -> bool:
    """递归检查并补齐缺失的配置项，返回是否有新增"""
    updated = False
    for key, val in default.items():
        if key not in current:
            current[key] = val
            updated = True
        elif isinstance(val, dict) and isinstance(current[key], dict):
            if sync_defaults(current[key], val):
                updated = True
    return updated


def get_config() -> dict:
    default_cfg = yaml.load(DEFAULT_CONFIG_YAML.strip())

    if not CONFIG_YAML.exists():
        CONFIG_YAML.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_YAML.write_text(DEFAULT_CONFIG_YAML.strip(), encoding="utf-8")
        return default_cfg

    with CONFIG_YAML.open("r", encoding="utf-8") as f:
        cfg = yaml.load(f)

    if sync_defaults(cfg, default_cfg):
        with CONFIG_YAML.open("w", encoding="utf-8") as f:
            yaml.dump(cfg, f)

    return cfg
