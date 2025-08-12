from functools import lru_cache
from src.util.constants import get_config_base
import yaml


@lru_cache()
def load_config():
    """加载 config.yaml 并缓存结果。"""
    config_path = get_config_base() / "config.yaml"
    with config_path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)
