import logging
import os
import re
import subprocess
import time
from subprocess import check_output

from tools.yamlTool import yamlTool


class host_os:
    def __new__(cls, *args, **kwargs):
        if not hasattr(host_os, "_instance"):
            host_os._instance = object.__new__(cls)
        return host_os._instance

    def __init__(self):
        self.config = yamlTool(os.getcwd() + '/config/config.yaml')
        self.host = self.config.get_note('host_os')
        self.user = self.host['user']
        self.passwd = self.host['password']
        self.ip = ''

    def checkoutput(self, cmd):
        try:
            info = subprocess.check_output(cmd, shell=True, encoding='utf-8')
        except Exception as e:
            return ""
        else:
            return info

    def checkoutput_root(self, cmd):
        cmd = f'echo {self.passwd}|sudo -S {cmd}'
        return self.checkoutput(cmd)

    def get_ipaddress(self, net_card=''):
        info = self.checkoutput(f'ifconfig {net_card}')
        logging.info(f' ifconfig :{info}')
        info = re.findall(r'inet\s+(\d+\.\d+\.\d+\.\d+)', info, re.S)
        if info :
            return info[0]

    def dynamic_flush_network_card(self, net_card=''):
        self.checkoutput_root(f'netplan apply')
        for i in range(30):
            time.sleep(15)
            if self.get_ipaddress(net_card):
                self.ip = self.get_ipaddress(net_card)
                logging.info(f'get pc ip {self.ip}')
                return self.ip

# host = host_os()
# host.dynamic_flush_network_card()
