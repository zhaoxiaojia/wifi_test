from src.tools.router_tool.RouterControl import RouterTools


class AsusBaseControl(RouterTools):
    """华硕路由器通用控制基类

    提供标准字段到设备实际取值的映射，以减少各型号间的重复代码。
    """

    SECURITY_MODE_MAP = {
        "Open System": "Open System",
        "WPA2-Personal": "WPA2-Personal",
        # "WPA3-Personal": "WPA3-Personal",
        # "WPA/WPA2-Personal": "WPA/WPA2-Personal",
        # "WPA2/WPA3-Personal": "WPA2/WPA3-Personal",
    }

    WIRELESS_MODE_MAP = {
        "Auto": "自动",
        "Legacy": "Legacy",
        "N only": "N only",
        "AX only": "AX only",
        "N/AC/AX mixed": "N/AC/AX mixed",
        # "11a": "11a",
        # "11ac": "11ac",
        # "11ax": "11ax",
        # "11b": "11b",
        # "11g": "11g",
        # "11n": "11n",
    }
