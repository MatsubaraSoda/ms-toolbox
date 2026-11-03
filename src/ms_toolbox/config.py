from pathlib import Path
import yaml
from platformdirs import user_config_path

APP_NAME = "ms-toolbox"
CONFIG_YAML: Path = user_config_path(APP_NAME, appauthor=False) / "config.yaml"

DEFAULT_CONFIG_YAML = """
tipo_worker_python_exe:
"""

def get_config() -> dict:
    if not CONFIG_YAML.exists():
        CONFIG_YAML.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_YAML.write_text(DEFAULT_CONFIG_YAML.strip(), encoding="utf-8")

    return yaml.safe_load(CONFIG_YAML.read_text(encoding="utf-8"))