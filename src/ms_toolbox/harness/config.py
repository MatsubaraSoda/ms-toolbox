import os

from ms_toolbox.config import CONFIG_YAML, get_config


def get_harness_config() -> dict:
    """读取 config.yaml 中的 harness 配置项"""
    return get_config()["harness"]


def get_default_config() -> dict:
    """每次新建对话时读取最新的 config.yaml 默认配置"""
    raw = get_harness_config()
    return {
        "workspace_dir": raw["workspace_dir"],
        "system_prompt": raw["system_prompt"],
        "model": raw["model"],
        "provider": raw["provider"]["order"][0],
    }


def open_config():
    """确保配置文件存在并使用系统默认程序打开"""
    get_config()
    os.startfile(CONFIG_YAML)
