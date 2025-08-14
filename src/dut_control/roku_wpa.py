#!/usr/bin/env python 
# encoding: utf-8 
'''
@author: chao.li
@contact: chao.li@amlogic.com
@software: pycharm
@file: roku_wpa.py 
@time: 2025/6/30 20:01 
@desc: 
'''

import time
import re


class roku_wpa:
    def __init__(self, executor, ui_signature=None, script_signature=None):
        """
        executor: 提供 .run(cmd:str, timeout:float=1.0) -> str 的接口
        可以是你的 pytest.dut.roku.ser，也可以是你自定义的执行器对象
        """
        self.executor = executor
        self.ui_signature = ui_signature or '/etc/wpa-supp.conf'  # 默认UI用的conf路径
        self.script_signature = script_signature or '/tmp/wpa_supplicant.conf'
        self.process_list = []  # 保存所有wpa_supplicant进程信息

    def refresh_process_list(self):
        """查找当前所有wpa_supplicant进程，并保存"""
        self.executor.write(f"ps -A -o pid,cmd | grep 'wpa_supplicant'")
        ps_out = self.executor.recv()
        for line in ps_out.splitlines():
            line = line.strip()
            if not line or "grep" in line:
                continue
            parts = line.split(None, 1)
            if len(parts) == 2:
                pid, cmdline = parts
                # 识别类型
                if self.ui_signature and self.ui_signature in cmdline:
                    proc_type = "ui"
                elif self.script_signature and self.script_signature in cmdline:
                    proc_type = "script"
                else:
                    proc_type = "unknown"
                self.process_list.append({"pid": pid, "cmdline": cmdline, "type": proc_type})

    def kill_by_type(self, proc_type):
        """批量kill指定类型的wpa_supplicant（ui/script/unknown）"""
        self.refresh_process_list()
        killed = []
        for proc in self.process_list:
            if proc["type"] == proc_type:
                self.executor.write(f"kill {proc['pid']}")
                killed.append(proc)
                # print(f"[KILL] {proc_type}: PID={proc['pid']} CMD={proc['cmdline']}")
                time.sleep(0.5)
        if not killed:
            # print(f"[INFO] 没有需要kill的 {proc_type} wpa_supplicant")

    def restart_ui_wpa(self, proc_type):
        """重启指定类型的wpa_supplicant（只启动之前查到的命令）"""
        # kill同类型所有
        self.kill_by_type('script')
        # 恢复（以后台方式重启所有）
        for proc in self.process_list:
            if proc["type"] == proc_type:
                cmd = proc["cmdline"]
                self.executor.write(cmd + " &")
                # print(f"[RESTART] {proc_type}: {cmd}")
                time.sleep(1)

    def restart_interface(self, iface='wlan0'):
        self.executor.write(f"ip link set {iface} down")
        time.sleep(0.5)
        self.executor.write(f"ip link set {iface} up")
        time.sleep(1)

    def make_ctrl_dir(self, path='/tmp/wpa_supplicant'):
        self.executor.write(f"mkdir -p {path}")

    def create_conf(self, ssid, auth_type="WPA2-PSK", psk=None, eap=None, identity=None, password=None,
                    key_mgmt=None, proto=None, ieee80211w=None, pairwise=None, group=None, pmf=None,
                    priority=None, conf_path='/tmp/wpa_supplicant.conf'):
        """
        支持 WPA/WPA2/WPA3/Open/Enterprise 配置，避免重复字段，支持 priority
        """
        network_lines = [f'    ssid="{ssid}"']

        # Open
        if auth_type.upper() in ["OPEN", "NONE"]:
            network_lines.append('    key_mgmt=NONE')

        # WPA-PSK/WPA2-PSK
        elif auth_type.upper() in ["WPA-PSK", "WPA2-PSK"]:
            network_lines.append(f'    psk="{psk}"')
            network_lines.append('    key_mgmt=WPA-PSK')
            if ieee80211w is not None:
                network_lines.append(f'    ieee80211w={ieee80211w}')
            if pmf:
                network_lines.append(f'    pmf={pmf}')

        # WPA3-SAE
        elif auth_type.upper() == "WPA3-SAE":
            network_lines.append(f'    psk="{psk}"')
            network_lines.append('    key_mgmt=SAE')
            network_lines.append('    ieee80211w=2')  # 强制开启管理帧保护
            if pmf:
                network_lines.append(f'    pmf={pmf}')

        # WPA-EAP
        elif auth_type.upper() == "WPA-EAP":
            network_lines.append('    key_mgmt=WPA-EAP')
            if eap:
                network_lines.append(f'    eap={eap}')
            if identity:
                network_lines.append(f'    identity="{identity}"')
            if password:
                network_lines.append(f'    password="{password}"')
            if ieee80211w is not None:
                network_lines.append(f'    ieee80211w={ieee80211w}')
            if pmf:
                network_lines.append(f'    pmf={pmf}')

        # 通用扩展字段（避免重复）
        if key_mgmt and f'key_mgmt={key_mgmt}' not in network_lines:
            network_lines.append(f'    key_mgmt={key_mgmt}')
        if proto:
            network_lines.append(f'    proto={proto}')
        if pairwise:
            network_lines.append(f'    pairwise={pairwise}')
        if group:
            network_lines.append(f'    group={group}')
        if priority is not None:
            network_lines.append(f'    priority={priority}')

        network_block = "network={\n" + "\n".join(network_lines) + "\n}"

        conf = f"""ctrl_interface=/tmp/wpa_supplicant
update_config=1

{network_block}
    """
        cmd = f"cat > {conf_path} <<EOF\n{conf}\nEOF"
        self.executor.write(cmd)

    def start_wpa_supplicant(self, iface='wlan0', conf='/tmp/wpa_supplicant.conf', debug=False):
        log_opt = "-d" if debug else ""
        self.executor.write(f"wpa_supplicant -i {iface} -c {conf} -B {log_opt} ")

    def run_udhcpc(self, iface='wlan0'):
        self.executor.write(f"udhcpc -i {iface}")

    def set_static_ip(self, iface, ip, mask='255.255.255.0'):
        self.executor.write(f"ifconfig {iface} {ip} netmask {mask} up")

    def status_check(self, iface='wlan0'):
        return self.executor.write(f"wpa_cli -i {iface} -p /tmp/wpa_supplicant status")

    def scan_network(self, iface='wlan0'):
        self.executor.write(f"wpa_cli -i {iface} -p /tmp/wpa_supplicant scan")
        time.sleep(3)
        return self.executor.write(f"wpa_cli -i {iface} -p /tmp/wpa_supplicant scan_results")

    def get_ip(self, iface='wlan0'):
        return self.executor.write(f"ifconfig {iface}")

    def ping_test(self, target='8.8.8.8', count=4):
        return self.executor.write(f"ping -c {count} {target}")

    def cleanup(self):
        self.kill_wifi_process()
        self.executor.write("rm -f /tmp/wpa_supplicant.conf")
        self.executor.write("rm -rf /tmp/wpa_supplicant")

    def disconnect(self, iface='wlan0'):
        """断开当前连接"""
        self.executor.write(f"wpa_cli -i {iface} -p /tmp/wpa_supplicant disconnect")

    def reconnect(self, iface='wlan0'):
        """重新连接"""
        self.executor.write(f"wpa_cli -i {iface} -p /tmp/wpa_supplicant reconnect")

    def list_networks(self, iface='wlan0'):
        """列出所有网络配置"""
        return self.executor.write(f"wpa_cli -i {iface} -p /tmp/wpa_supplicant list_networks")

    def forget(self, iface='wlan0', net_id=None):
        """
        删除指定 network（forget）
        - net_id: 网络ID，如None则删除所有配置
        """
        if net_id is None:
            self.executor.write(f"wpa_cli -i {iface} -p /tmp/wpa_supplicant remove_network all")
        else:
            self.executor.write(f"wpa_cli -i {iface} -p /tmp/wpa_supplicant remove_network {net_id}")
        self.executor.write(f"wpa_cli -i {iface} -p /tmp/wpa_supplicant save_config")

    def select_network(self, iface='wlan0', net_id=0):
        """选择某个network连接"""
        self.executor.write(f"wpa_cli -i {iface} -p /tmp/wpa_supplicant select_network {net_id}")

    def set_default_route(self, gw='192.168.1.1', iface='wlan0'):
        """
        设置默认网关
        :param gw: 网关地址
        :param iface: 网卡名
        """
        # 删除现有默认路由（防止冲突，可选）
        self.executor.write(f"ip route del default dev {iface}")
        # 添加新的默认路由
        self.executor.write(f"ip route add default via {gw} dev {iface}")

    def wait_for_state(self, iface='wlan0', target_state='COMPLETED', timeout=75, interval=5):
        """
        轮询 wpa_cli status，直到 wpa_state=target_state 或超时
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            self.executor.write(f"wpa_cli -i {iface} -p /tmp/wpa_supplicant status")
            status = self.executor.recv()
            m = re.search(r'wpa_state=(\w+)', status)
            if m:
                curr = m.group(1)
                if curr == target_state:
                    # print(f"[INFO] 连接状态已到达 {target_state}")
                    return True
                else:
                    # print(f"[INFO] 当前状态：{curr}，等待中...")
            else:
                # print("[WARN] 未检测到状态字段，等待中...")
            time.sleep(interval)
        # print(f"[ERROR] 等待 {target_state} 超时！")
        return False

    def is_ip_in_use(self, ip, iface='wlan0'):
        # 只要能通，就说明有主机在线
        self.executor.write(f"ping -c 1 -w 2 -I {iface} {ip}")
        result = self.executor.recv()
        return "1 received" in result or "bytes from" in result

    def set_available_static_ip(self, iface='wlan0', ip_pool=None, mask='255.255.255.0', gw='192.168.1.1'):
        """
        自动选择未被占用的静态IP并设置
        :param ip_pool: 静态IP候选列表，如 ['192.168.1.200', '192.168.1.201', ...]
        """
        ip_pool = ip_pool or [f"192.168.1.{i}" for i in range(200, 251)]
        for ip in ip_pool:
            if not self.is_ip_in_use(ip, iface=iface):
                self.set_static_ip(iface, ip, mask)
                self.set_default_route(gw=gw, iface=iface)
                # print(f"[INFO] 设置静态IP成功: {ip}")
                return ip
            else:
                # print(f"[WARN] IP {ip} 已被占用，尝试下一个...")
        # print("[ERROR] 没有可用的静态IP，请检查路由器分配策略。")
        return None

    def connect(self, ssid, auth_type="WPA2-PSK", psk=None, eap=None, identity=None, password=None,
                key_mgmt=None, proto=None, ieee80211w=None, pairwise=None, group=None, pmf=None,
                gw=None, mask='255.255.255.0', dhcp=False, iface='wlan0', priority=None,
                max_retry=3, wait_connect=5, state_timeout=75, retry_interval=2):
        """
        一键连接并带有重试机制、连接等待、状态检查
        - max_retry: 最大重试次数
        - wait_connect: 启动wpa_supplicant后的首次等待（秒）
        - state_timeout: 单次连接状态等待超时（秒）
        - retry_interval: 每次重试之间等待时间（秒）
        """
        for attempt in range(1, max_retry + 1):
            # print(f"\n[INFO] 第 {attempt} 次尝试连接 {ssid} ...")
            self.kill_by_type("ui")
            self.make_ctrl_dir()
            self.create_conf(ssid, auth_type, psk, eap, identity, password,
                             key_mgmt, proto, ieee80211w, pairwise, group, pmf, priority)
            self.start_wpa_supplicant(iface=iface, debug=False)
            time.sleep(wait_connect)
            ok = self.wait_for_state(iface=iface, target_state='COMPLETED', timeout=state_timeout)
            if ok:
                if dhcp:
                    self.run_udhcpc(iface=iface)
                else:
                    self.set_available_static_ip()
                    self.set_default_route(gw=gw)
                # print(f"[SUCCESS] 第 {attempt} 次连接成功！")
                time.sleep(3)
                self.restart_ui_wpa('ui')
                return self.status_check(iface=iface)
            else:
                # print(f"[WARN] 第 {attempt} 次连接失败，{retry_interval} 秒后重试...")
                time.sleep(retry_interval)
                self.kill_by_type("script")
        # print(f"[ERROR] 多次尝试后，连接 {ssid} 仍失败。")
        time.sleep(3)
        self.restart_ui_wpa('ui')
        return None


if __name__ == '__main__':
    from src.tools import serial_tool

    ser = serial_tool("COM4", 115200)
    wpa = roku_wpa(ser)
    wpa.connect("_coco", psk='12345678', priority=1, gw='192.168.1.1')
