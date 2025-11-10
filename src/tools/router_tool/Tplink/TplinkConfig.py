"""
Tplink config

This module is part of the AsusRouter package.
"""

from src.tools.router_tool.RouterControl import RouterTools


class TplinkRotuerConfig(RouterTools):
    """
        Tplink rotuer config
            Parameters
            ----------
            None
                This class is instantiated without additional parameters.
            Returns
            -------
            None
                Classes return instances implicitly when constructed.
    """

    def __init__(self):
        """
            Init
                Parameters
                ----------
                None
                    This function does not accept any parameters beyond the implicit context.
                Returns
                -------
                None
                    This function does not return a value.
        """
        super(TplinkRotuerConfig, self).__init__()

    CHANNEL_2_DICT = {
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


class TplinkAx6000Config(TplinkRotuerConfig):
    """
        Tplink ax6000 config
            Parameters
            ----------
            None
                This class is instantiated without additional parameters.
            Returns
            -------
            None
                Classes return instances implicitly when constructed.
    """

    def __init__(self):
        """
            Init
                Parameters
                ----------
                None
                    This function does not accept any parameters beyond the implicit context.
                Returns
                -------
                None
                    This function does not return a value.
        """
        super(TplinkAx6000Config, self).__init__()

    AUTHENTICATION_METHOD_DICT = {
        'WPA-PSK/WPA2-PSK': '1',
        'WPA2-PSK/WPA3-SAE': '2'
    }

    CHANNEL_5_DICT = {
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
        '165': '14',
    }

    WIRELESS_MODE_2G_DICT = {
        '11bgn/ax mixed': '1',
        '11bgn mixed': '2',
        '11bg mixed': '3',
        '11n only': '4',
        '11g only': '5',
        '11b only': '6'
    }

    WIRELESS_MODE_5G_DICT = {
        '11a/n/ac/ax mixed': '1',
        '11a/n/ac mixed': '2',
        '11a/n mixed': '3'
    }

    BANDWIDTH_2_DICT = {
        '40MHz/20MHz自动': '1',
        '20MHz': '2'
    }

    BANDWIDTH_5_DICT = {
        '160MHz/80MHz/40MHz/20MHz自动': '1',
        '40MHz/20MHz自动': '2',
        '20MHz': '3',
        '40MHz': '4',
        '80MHz': '5'
    }


class TplinkWr842Config(TplinkRotuerConfig):
    """
        Tplink wr842 config
            Parameters
            ----------
            None
                This class is instantiated without additional parameters.
            Returns
            -------
            None
                Classes return instances implicitly when constructed.
    """

    def __init__(self):
        """
            Init
                Parameters
                ----------
                None
                    This function does not accept any parameters beyond the implicit context.
                Returns
                -------
                None
                    This function does not return a value.
        """
        super().__init__()

    AUTHENTICATION_METHOD_LIST = ['WPA-PSK/WPA2-PSK', 'WPA/WPA2', 'WEP', 'WPA-PSK', 'WPA2-PSK', 'WPA', 'WPA2', '自动',
                                  '开放系统', '共享秘钥', 'OPEN']

    PSK_DICT = {
        '自动': '1',
        'WPA-PSK': '2',
        'WPA2-PSK': '3'
    }
    WPA_DICT = {
        '自动': '1',
        'WPA': '2',
        'WPA2': '3'
    }
    WPA_ENCRYPT = {
        '自动': '1',
        'TKIP': '2',
        'AES': '3'
    }
    WEP_DICT = {
        '自动': '1',
        '开放系统': '2',
        '共享秘钥': '3'
    }
    WEP_ENCRUPT = {
        '十六进制': '1',
        'ASCII码': '2'
    }

    WIRELESS_MODE_2G_DICT = {
        '11b only': '1',
        '11g only': '2',
        '11n only': '3',
        '11bg mixed': '4',
        '11bgn mixed': '5'
    }

    BANDWIDTH_2_DICT = {
        '自动': '1',
        '20MHz': '1',
        '40MHz': '2'
    }
