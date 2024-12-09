import subprocess
import os
import re
import time

from tools.yamlTool import yamlTool
from subprocess import check_output


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

    def checkoutput(self, cmd):
        try:
            info = subprocess.check_output(cmd, shell=True, encoding='utf-8')
        except Exception as e:
            return None
        else:
            return info

    def checkoutput_root(self, cmd):
        cmd = f'echo {self.passwd}|sudo -S {cmd}'
        return self.checkoutput(cmd)

    def get_ipaddress(self, net_card=''):
        info = self.checkoutput(f'ifconfig {net_card}')
        info = re.findall(r'inet\s+(\d+\.\d+\.\d+\.\d+)', info, re.S)
        if info:
            return info[0]

    def dynamic_flush_network_card(self, net_card=''):
        self.checkoutput_root(f'dhclient -r {net_card}')
        for i in range(30):
            time.sleep(2)
            self.checkoutput_root(f'dhclient {net_card}')
            if self.get_ipaddress(net_card):
                return self.get_ipaddress(net_card)
            time.sleep(6)

# host = host_os()
# host.dynamic_flush_network_card()
