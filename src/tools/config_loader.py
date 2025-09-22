from functools import lru_cache
from src.util.constants import get_config_base
import yaml
import logging


@lru_cache()
def _cached_load_config():
    """实际读取 config.yaml 并缓存结果。"""
    config_path = get_config_base() / "config.yaml"
    with config_path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
        return data or {}


def load_config(refresh: bool = False):
    """加载 config.yaml。

    默认返回缓存内容；当 ``refresh=True`` 时清除缓存并重新读取文件。
    """
    config_path = get_config_base() / "config.yaml"
    if refresh:
        load_config.cache_clear()
        logging.debug("Cache cleared, reloading %s", config_path)
    else:
        logging.debug("Loading config file without clearing cache: %s", config_path)

    config = _cached_load_config() or {}

    if refresh:
        try:
            logging.debug("config_path: %s", config_path)
            logging.debug("rf_solution['step']: %s", config['rf_solution']['step'])
        except Exception as e:
            logging.warning("Failed to get rf_solution['step']: %s", e)
        try:
            with open(config_path, encoding="utf-8") as f:
                logging.debug("Config file content:\n%s", f.read())
        except Exception as e:
            logging.warning("Failed to read config file content: %s", e)

    return config


# 兼容外部直接调用 ``load_config.cache_clear``
load_config.cache_clear = _cached_load_config.cache_clear
