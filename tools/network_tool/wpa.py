import logging
import re
import subprocess
import time

from pandas.core.window.doc import window_agg_numba_parameters

from tools.connect_tool.host_os import host_os


class cmd_wpa:
    '''
    wpa_supplicant for linux
    '''
    def __init__(self, host=None, dut=None):
        self.host_control = host
        # if self.host_control:
        #     self.host_control.checkoutput_root('su')
        self.dut_control = dut
        self.interface = 'wlp0s20f3'

    def send_cmd(self, cmd, target):
        if target == 'host':
            assert self.host_control, "Can't find any host control"
            logging.info(cmd)
            return self.host_control.checkoutput_root(cmd)
        elif target == 'dut':
            assert self.dut_control, "Can't find any dut control"
            logging.info(cmd)
            return self.dut.checkoutput(cmd)

    def  flush_wlan(self, target):
        if not self.send_cmd(f'ifconfig {self.interface} |egrep -o "inet [^ ]*"|cut -d " " -f 2', target):
            self.send_cmd(f'dhclient {self.interface}', target)
            time.sleep(5)

    def clear_wlan(self, target):
        if self.send_cmd(f'ifconfig {self.interface} |egrep -o "inet [^ ]*"|cut -d " " -f 2', target):
            self.send_cmd(f'dhclient -r {self.interface}', target)
            time.sleep(5)

    def associate_wifi(self, target, **kwargs):
        """
        Build Wi-Fi connection for endpoint
        Usage:
            wifi_connect(ssid='TIGO_1123334', psk='123244353')
        Args:
            N/A
        Kwargs:
            timeout: time to wait command response
            retry: retry times to build connection
            interface: data interface
            radio: wpa_supplicant para
            ssid: wpa_supplicant para
            psk: wpa_supplicant para
            configs: full configuration text
            wpa_conf: full configuration file
            ap_scan: wpa_supplicant para ap_scan, 0 or 1
            p2p_disabled: wpa_supplicant para
            ctrl_interface: wpa_supplicant para
            ctrl_interface_group: wpa_supplicant para
            pairwise: 6G radio wpa_supplicant para
            security: wpa_supplicant para
            bssid: wpa_supplicant para
            rad_identity: raduis server login usuername
            rad_password: raduis server login password
            eap: wpa_supplicant para
            phase2: wpa_supplicant para
            proto: wpa_supplicant para
        Return:
            True or False
        """
        timeout = kwargs.get('timeout', 60)
        retry = 3
        interface = kwargs.get('interface', self.interface)
        radio = kwargs.get('radio', '2.4G')
        ssid = kwargs.get('ssid', None)
        psk = kwargs.get('psk', None)
        key_mgmt = kwargs.get('key_mgmt', None)
        configs = kwargs.get('configs', None)
        wpa_conf = kwargs.get('wpa_conf', None)
        ap_scan = kwargs.get('ap_scan', 1)
        p2p_disabled = kwargs.get('p2p_disabled', 1)
        ctrl_interface = kwargs.get('ctrl_interface', '/var/run/wpa_supplicant')
        ctrl_interface_group = kwargs.get('ctrl_interface_group', 0)
        pairwise = kwargs.get('pairwise', None)
        security = kwargs.get('security', None)
        bssid = kwargs.get('bssid', None)
        # rad_identity = kwargs.get('rad_identity', None)
        # rad_password = kwargs.get('rad_password', None)
        eap = kwargs.get('eap', None)
        phase2 = kwargs.get('phase2', None)
        proto = kwargs.get('proto', None)
        scan_ssid = kwargs.get('scan_ssid', None)
        # self.send_cmd('killall wpa_suplicant', target)
        current_status = self.send_cmd('wpa_cli status', target)
        if current_status:
            if ssid in current_status:
                logging.info('already associate')
                return True
            if 'wpa_state=COMPLETED' in current_status:
                logging.info('forget first')
                self.forget_wifi(target, **kwargs)
        wpa_supplicant_conf = '/etc/wpa_supplicant.conf'
        # c.send_cmd(f'dhclient -r {interface}', '# ', timeout=timeout)
        # # c.send_cmd(f'killall dhclient', '# ', timeout=timeout)
        # c.send_cmd(f'ip -4 addr flush {interface}', '# ', timeout=timeout)
        # c.send_cmd(f'ip -6 addr flush {interface}', '# ', timeout=timeout)
        # c.send_cmd(f'sed -i -n \"1p\" /var/lib/dhcp/dhclient6.leases', '# ', timeout=timeout)
        # self.send_cmd(
        #     "if [ -f /etc/wpa_supplicant.conf ];then yes|cp -f /etc/wpa_supplicant.conf /etc/wpa_supplicant_bk; fi",
        #     target)
        # self.send_cmd(f'rm -f /etc/wpa_supplicant.conf', target)

        if not configs:
            configs = f'ap_scan={ap_scan}\np2p_disabled={p2p_disabled}\nctrl_interface={ctrl_interface}\nctrl_interface_group={ctrl_interface_group}\n'

            if radio == '6G':
                configs += 'pmf=2\n'
                configs += 'sae_pwe=2\n'

            configs += 'network={\n'

            if isinstance(security, str) and key_mgmt is None:
                if security == 'None':
                    key_mgmt = 'NONE'
                elif re.search(f'Enterprise', security, re.I):
                    key_mgmt = 'WPA-EAP'
                elif re.search(f'WPA3-Personal', security, re.I):
                    key_mgmt = 'SAE'
                else:
                    key_mgmt = 'WPA-PSK'

            if isinstance(security, str) and proto is None and re.search(f'WPA', security, re.I):
                proto = 'WPA RSN'

            for var in ['ssid', 'psk', 'wep_key0', 'wep_key1', 'wep_key2', 'wep_key3', 'identity', 'password',
                        'phase1', 'phase2']:
                if var in locals().keys() and locals()[var] != None:
                    if key_mgmt == 'NONE' and var == 'psk':
                        # Skip psk when key_mgmt is NONE
                        continue
                    configs += f'{var}=\\"{locals()[var]}\\"\n'
            for var in ['proto', 'key_mgmt', 'wep_tx_keyidx', 'pairwise', 'group', 'priority', 'scan_freq',
                        'filter_ssids',
                        'scan_ssid', 'frequency', 'freq_list', 'mode', 'eap', 'ht40_intolerant', 'bssid', 'ieee80211w']:
                if var in locals().keys() and locals()[var] != None:
                    configs += f'{var}={locals()[var]}\n'

            if isinstance(pairwise, str) and radio == '6G':
                configs += 'pairwise=CCMP\n'

            if key_mgmt == 'SAE':
                configs += 'ieee80211w=2\n'
            configs += '}'

        if wpa_conf is None:
            self.host_control.checkoutput(f'echo "{configs}" > /etc/wpa_supplicant.conf')
        else:
            tmp_conf = '/tmp/wpa_supplicant.conf'
            wpa_supplicant_conf = tmp_conf
            with open(tmp_conf, 'w') as conf:
                conf.write(wpa_conf)
            # scp wpa_supplicant.conf file to avoid complicated escaping
            # os.system(f"sshpass -p '{self.autouser_passwd}' scp {tmp_conf} autouser@{self.access_ip}:{wpa_supplicant_conf}")

        rsp = self.send_cmd(f'cat {wpa_supplicant_conf}', target)
        # log.debug(f'Show configs in wpa_supplicant.conf:  {rsp}')
        #
        # log.info(f'Running wpa_supplicant on {interface} @ {self.access_ip} .....')

        for i in range(retry):
            self.send_cmd(f'killall wpa_supplicant', target)
            # c.send_cmd(f'rm -f /var/run/wpa_supplicant/{interface}', '# ', timeout=timeout)
            # c.send_cmd(f'ifconfig {interface} down; ifconfig {interface} up', '# ', timeout=timeout)
            # time.sleep(5)
            self.send_cmd(f'wpa_supplicant -B -i {interface} -c /etc/wpa_supplicant.conf', target)
            time.sleep(5)

            for j in range(3):
                # conn_info = self.get_wifi_conn_info(access_ip)
                rsp = self.send_cmd(f'wpa_cli status', target)
                if rsp and ('wpa_state=COMPLETED' in rsp):
                    return True
                else:
                    if isinstance(radio, str) and radio == '6G':
                        time.sleep(30)
                    else:
                        time.sleep(5)
            else:
                return False

    def disassociate_wifi(self, target, **kwargs):
        """
        Disconnect Wi-Fi connection for endpoint
        Usage:
            wifi_disconnect(ssid='TIGO_1123334', psk='123244353')
        Args:
            N/A
        Kwargs:
            timeout: time to wait command response
        Return:
            True or False
        """
        timeout = kwargs.get('timeout', 20)

        self.send_cmd(f'wpa_cli disconnect', target)
        # c.send_cmd(f'killall wpa_supplicant', '# ', timeout=timeout)

    def connect_wifi(self, target, **kwargs):
        self.associate_wifi(target, **kwargs)
        self.flush_wlan(target)

    def forget_wifi(self, target, **kwargs):
        self.disassociate_wifi(target, **kwargs)
        self.clear_wlan(target)

    def get_wifi_conn_info(self, target, **kwargs):
        """
        Get wi-fi endpoint connection information
        Usage:
            get_wifi_conn_info()
        Args:
            N/A
        Kwargs:
            timeout: time to wait command response
            interface: data interface
        Return:
            Connection info dictionary
        """
        conn_info = {}
        timeout = kwargs.get('timeout', 20)
        interface = kwargs.get('interface', self.interface)

        rsp = self.send_cmd(f'wpa_cli status', target)
        # log.info(f'Get wpa_cli response: \n {rsp}')
        rsp_line = rsp.splitlines()
        for index, line in enumerate(rsp_line):
            reg_rsp = re.findall('([^=]*)=([^\n]*)', line, re.I | re.M)
            if reg_rsp:
                conn_info[reg_rsp[0][0]] = reg_rsp[0][1]

        rsp = self.send_cmd(f'iwconfig {interface}', target)

        # Get AP MAC address
        reg_rsp = re.findall('Access Point: (([0-9A-F]{2}:){5}[0-9A-F]{2})', rsp, re.I | re.M)
        if reg_rsp:
            conn_info['access_point'] = reg_rsp[0][0]

        # Get bit rate
        reg_rsp = re.findall('Bit Rate=([0-9]{1,3})', rsp, re.I | re.M)
        if reg_rsp:
            conn_info['bit_rate'] = reg_rsp[0]

        # Get bit rate
        reg_rsp = re.findall('Bit Rate:(.*) [M|G]b/s', rsp, re.I)
        if reg_rsp:
            conn_info['bit_rate'] = reg_rsp[0]

        # Get AP SSID
        reg_rsp = re.findall('ESSID:\"(.*)\"', rsp, re.I)
        if reg_rsp:
            conn_info['ssid'] = reg_rsp[0]

        # Get connection frequency
        reg_rsp = re.findall('Frequency:([0-9]+.[0-9]+) GHz', rsp, re.I)
        if reg_rsp:
            conn_info['frequency'] = reg_rsp[0]

        return conn_info

    def scan_aps(self, target, **kwargs):
        """
        Scan APs from Wi-Fi endpoint
        Usage:
            scan_aps(interface='wlan0')
        Args:
            N/A
        Kwargs:
            timeout: time to wait command response
            interface: data interface
            ap: specified ap(bssid, ssid...)
            retry: scan retry times
        Return:
            Scan result
        """
        timeout = kwargs.get('timeout', 20)
        interface = kwargs.get('interface', self.interface)
        retry = kwargs.get('retry', 5)
        ap = kwargs.get('ap', None)
        rsp = ""

        scan_result = False
        self.send_cmd(f'killall wpa_supplicant', target)
        for i in range(retry):
            try:
                rsp = self.send_cmd(f'iw dev {interface} scan', target)
            except Exception as error:
                # log.error(f'Exception log during iw dev{ interface} scan: {error}')
                scan_result = False
            if ap:
                re1 = re.compile(r"{}(\b|\(|\n)".format(ap), re.I)
                if re1.search(rsp, re.I):
                    # log.info(f'successfully get {ap}')
                    scan_result = True
                    break
                else:
                    # log.warning(f'Failed to scan {ap}')
                    scan_result = False
                    time.sleep(2)
            else:
                if re.search('busy|unavailable|No scan result', rsp, re.I):
                    # log.warning(f'Failed to scan APs: {rsp}')
                    scan_result = False
                    time.sleep(2)
                else:
                    break

        # log.debug(f'Scan result on {interface} @ {self.access_ip}: {rsp}')
        return scan_result


# host = host_os()
# wpa = cmd_wpa(host=host)
# wpa.connect_wifi('host', ssid='sunshine', psk='Home1357')
# print(wpa.send_cmd('ifconfig wlp0s20f3', 'host'))
# wpa.forget_wifi('host')
# print(wpa.send_cmd('ifconfig wlp0s20f3', 'host'))
