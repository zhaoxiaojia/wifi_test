import logging
import os
import re
import subprocess
import time
from subprocess import check_output

from src.tools.yamlTool import yamlTool


class LocalOS:
    def __new__(cls, *args, **kwargs):
        if not hasattr(LocalOS, "_instance"):
            LocalOS._instance = object.__new__(cls)
        return LocalOS._instance

    def __init__(self):
        self.ip = ''

    def checkoutput(self, cmd):
        try:
            info = subprocess.check_output(
                cmd,
                shell=True,
                encoding='utf-8',
                errors='ignore'
            )
        except Exception:
            return None
        else:
            return info

    def checkoutput_root(self, cmd):
        return self.checkoutput(cmd)

    def get_ipaddress(self, net_card=''):
        info = self.checkoutput('ipconfig')
        if not info:
            return None

        lines = info.splitlines()
        blocks = []
        current_header = None
        current_lines = []

        for line in lines:
            if line.strip() == '':
                if current_header is not None:
                    blocks.append((current_header, current_lines))
                    current_header = None
                    current_lines = []
                continue

            if not line.startswith(' ') and line.strip().endswith(':'):
                if current_header is not None:
                    blocks.append((current_header, current_lines))
                current_header = line.strip()
                current_lines = [line]
            else:
                if current_header is not None:
                    current_lines.append(line)

        if current_header is not None:
            blocks.append((current_header, current_lines))

        if net_card:
            target_block = None
            key = net_card.lower()
            for header, content in blocks:
                if key in header.lower():
                    target_block = '\n'.join(content)
                    break

            if target_block:
                ipv4_list = re.findall(r'IPv4[^\n:]*:\s*([\d\.]+)', target_block, re.S)
                for ip in ipv4_list:
                    if not ip.startswith('127.'):
                        return ip

                generic_list = re.findall(r'(\d+\.\d+\.\d+\.\d+)', target_block, re.S)
                for ip in generic_list:
                    if not ip.startswith('127.'):
                        return ip

        ipv4_list = re.findall(r'IPv4[^\n:]*:\s*([\d\.]+)', info, re.S)
        for ip in ipv4_list:
            if not ip.startswith('127.'):
                return ip

        generic_list = re.findall(r'(\d+\.\d+\.\d+\.\d+)', info, re.S)
        for ip in generic_list:
            if not ip.startswith('127.'):
                return ip

        return None

    def dynamic_flush_network_card(self, net_card=''):
        if net_card:
            cmd = f'ipconfig /renew "{net_card}"'
        else:
            cmd = 'ipconfig /renew'

        self.checkoutput_root(cmd)

        for _ in range(30):
            time.sleep(15)
            ip = self.get_ipaddress(net_card)
            if ip:
                self.ip = ip
                return self.ip
