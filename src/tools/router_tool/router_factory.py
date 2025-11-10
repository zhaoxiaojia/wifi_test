"""
Router factory

This module is part of the AsusRouter package.
"""

from src.tools.router_tool.AsusRouter.Asusax86uControl import Asusax86uControl
from src.tools.router_tool.AsusRouter.Asusax88uControl import Asusax88uControl
from src.tools.router_tool.AsusRouter.Asusax88uProControl import Asusax88uProControl
from src.tools.router_tool.AsusRouter.Asusax5400Control import Asusax5400Control
from src.tools.router_tool.AsusRouter.Asusax6700Control import Asusax6700Control
from src.tools.router_tool.Xiaomi.Xiaomiax3600Control import Xiaomiax3600Control
from src.tools.router_tool.Xiaomi.XiaomiBe7000Control import XiaomiBe7000Control
from src.tools.config_loader import load_config

router_list = {
    'asusax86u': Asusax86uControl,
    'asusax88u': Asusax88uControl,
    'asusax88upro': Asusax88uProControl,

    'xiaomibe7000': XiaomiBe7000Control,
    'xiaomiax3600': Xiaomiax3600Control,
}


def get_router(router_name: str, address: str | None = None):
    """
        Get router
            Parameters
            ----------
            router_name : object
                Description of parameter 'router_name'.
            address : object
                The router's login address or IP address; if None, a default is used.
            Returns
            -------
            object
                Description of the returned value.
    """
    if router_name not in router_list:
        raise ValueError("Doesn't support this router")

    if address is None:
        try:
            cfg = load_config(refresh=True)
            cfg_router = cfg.get('router', {})
            if cfg_router.get('name') == router_name:
                address = cfg_router.get('address')
        except Exception:
            address = None

    return router_list[router_name](address)
