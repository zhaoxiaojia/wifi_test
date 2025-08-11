from functools import lru_cache
from pathlib import Path
import yaml


@lru_cache()
def load_config():
    """加载 config.yaml 并缓存结果。"""
    config_path = Path(__file__).resolve().parents[2] / "config" / "config.yaml"
    with config_path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)
