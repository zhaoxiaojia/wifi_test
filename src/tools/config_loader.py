from functools import lru_cache
from src.util.constants import get_config_base
import yaml


@lru_cache()
def _cached_load_config():
    """实际读取 config.yaml 并缓存结果。"""
    config_path = get_config_base() / "config.yaml"
    with config_path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_config(refresh: bool = False):
    """加载 config.yaml。

    默认返回缓存内容；当 ``refresh=True`` 时清除缓存并重新读取文件。
    """
    config_path = get_config_base() / "config.yaml"
    if refresh:
        load_config.cache_clear()
        print(f"配置缓存已清理，重新加载: {config_path}")
    else:
        print(f"加载配置文件（缓存未清理）: {config_path}")
    return _cached_load_config()


# 兼容外部直接调用 ``load_config.cache_clear``
load_config.cache_clear = _cached_load_config.cache_clear
