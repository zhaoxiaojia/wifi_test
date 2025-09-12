from src.tools.router_tool.RouterControl import RouterTools


class XiaomiBaseControl(RouterTools):
    """小米路由器通用控制基类

    汇总各型号共享的常量和映射，避免重复定义。
    """

    BAND_2 = '2.4G'
    BAND_5 = '5G'

    CHANNEL_2 = {
        '自动': '1',
        '1': '2',
        '2': '3',
        '3': '4',
        '4': '5',
        '5': '6',
        '6': '7',
        '7': '8',
        '8': '9',
        '9': '10',
        '10': '11',
        '11': '12',
        '12': '13',
        '13': '14',
    }

    CHANNEL_5 = {
        '自动': '1',
        '36': '2',
        '40': '3',
        '44': '4',
        '48': '5',
        '52': '6',
        '56': '7',
        '60': '8',
        '64': '9',
        '149': '10',
        '153': '11',
        '157': '12',
        '161': '13',
        '165': '14'
    }

    AUTHENTICATION_METHOD = {
        '超强加密(WPA3个人版)': '1',
        '强混合加密(WPA3/WPA2个人版)': '2',
        '强加密(WPA2个人版)': '3',
        '混合加密(WPA/WPA2个人版)': '4',
        '无加密(允许所有人连接)': '5'
    }

    SECURITY_MODE_MAP = {
        "Open System": "无加密(允许所有人连接)",
        "WPA2-Personal": "强加密(WPA2个人版)",
        "WPA3-Personal": "超强加密(WPA3个人版)",
        "WPA/WPA2-Personal": "混合加密(WPA/WPA2个人版)",
        "WPA2/WPA3-Personal": "强混合加密(WPA3/WPA2个人版)",
    }

    WIRELESS_MODE_MAP = {
        "11ax": "11ax",
        "11ac": "11ac",
        "11n": "11n",
    }

    BANDWIDTH_5 = {
        '160/80/40/20MHz': '1',
        '20MHz': '2',
        '40MHz': '3',
        '80MHz': '4'
    }

    BANDWIDTH_2 = {
        '40/20MHz': '1',
        '20MHz': '2',
        '40MHz': '3'
    }

    WIRELESS_2 = ['11n', '11ax']
    WIRELESS_5 = ['11ac', '11ax']
