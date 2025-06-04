#!/usr/bin/env python 
# -*- coding: utf-8 -*- 


"""
# File       : serial_tool.py
# Time       ：2023/6/30 16:48
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""

import logging
import re
import signal
import time
from time import sleep

import pytest
import serial


class serial_tool:
    '''
    serial command control
    Attributes:
        serial_port : serial port
        baud : baud
        ser : serial.Serial instance
        ethernet_ip : ip address
        status : serial statuc
    '''

    def __init__(self, serial_port='', baud=''):
        self.serial_port = serial_port or pytest.config_yaml.get_note('serial_port')['port']
        self.baud = baud or pytest.config_yaml.get_note('serial_port')['baud']
        logging.info(f'port {self.serial_port} baud {self.baud}')
        self.ethernet_ip = ''
        self.uboot_time = 0
        try:
            self.ser = serial.Serial(self.serial_port, self.baud,
                                     bytesize=serial.EIGHTBITS,
                                     parity=serial.PARITY_NONE,
                                     stopbits=serial.STOPBITS_ONE,
                                     xonxoff=False,
                                     rtscts=False,
                                     dsrdtr=False,
                                     timeout=1)
            logging.info('*' * 80)
            logging.info(f'* Serial  {self.serial_port}-{self.baud} is opened  ')
            logging.info('*' * 80)
            # self.ser.write(chr(0x03))
            # self.write('setprop persist.sys.usb.debugging y')
            # self.write('setprop service.adb.tcp.port 5555')
        except serial.serialutil.SerialException as e:
            logging.info(f'not found serial:{e}')
        if isinstance(self.ser, serial.Serial):
            self.status = self.ser.isOpen()
        else:
            self.status = False
        if self.ethernet_ip:
            logging.info('get ip ：%s' % self.ethernet_ip)
        logging.info('the status of serial port is {}'.format(self.status))

    def get_ip_address(self, inet='wlan0', count=10):

        '''

        get ip address

        @param inet: network interface (default: wlan0)

        @param count: maximum retry attempts

        @return: IP address string or None if not found

        '''

        for attempt in range(count, 0, -1):

            try:

                # Clear serial buffer before sending command
                self.ser.reset_input_buffer()
                self.write('\x1A')
                self.write('bg')
                # Send command
                self.write(f'ifconfig {inet}')
                # Wait briefly for response
                time.sleep(1)
                # Read with timeout
                ipInfo = ''
                start_time = time.time()
                while time.time() - start_time < 5:  # 5 second timeout
                    if self.ser.in_waiting:
                        ipInfo += self.ser.read(self.ser.in_waiting).decode('utf-8', errors='ignore')
                        if 'TX bytes:' in ipInfo:
                            break  # Stop reading if we see the marker
                    time.sleep(0.1)
                # Extract IP address
                ipInfo = ipInfo.split('TX bytes:')[0]
                ipaddress = re.findall(r'inet addr:(\d+\.\d+\.\d+\.\d+)', ipInfo)
                if ipaddress:
                    logging.info(f'IP address: {ipaddress[0]}')
                    return ipaddress[0]
            except Exception as e:
                logging.warning(f'Error getting IP address: {str(e)}')
            if attempt > 1:
                logging.debug(f'Retrying... attempts left: {attempt - 1}')
                time.sleep(2 if attempt % 2 == 0 else 1)  # Vary sleep time
        logging.error('Failed to get IP address after maximum attempts')
        return None

    def write_pipe(self, command):
        '''
        execute the command , get feecback
        @param command: command
        @return: feedback
        '''
        self.ser.write(bytes(command + '\r', encoding='utf-8'))
        logging.info(f'=> {command}')
        sleep(0.1)
        data = self.recv()
        logging.debug(data.strip())
        return data

    def enter_uboot(self):
        '''
        enter in uboot
        @return: uboot status : boolean
        '''
        self.write('reboot')
        start = time.time()
        info = ''
        while time.time() - start < 30:
            logging.debug(f'uboot {self.ser.read(100)}')
            try:
                info = self.ser.read(100).decode('utf-8')
                logging.info(info)
            except UnicodeDecodeError as e:
                logging.warning(e)
            if 'gxl_p211_v1#' in info:
                logging.info('the device is in uboot')
                # self.write('reset')
                return True
            if 'sc2_ah212#' or 's4_ap222#' in info:
                logging.info('OTT is in uboot')
                return True
            else:
                self.write('\n\n')
        logging.info('no uboot info printed,please confirm manually')

    def enter_kernel(self):
        '''
        enter in kernel
        @return: kernel status : boolean
        '''
        self.write('reset')
        self.ser.readlines()
        sleep(2)
        start = time.time()
        info = ''
        while time.time() - start < 60:
            try:
                info = self.ser.read(10000).decode('utf-8')
                logging.info(info)
            except UnicodeDecodeError as e:
                logging.warning(e)
            if 'uboot time:' in info:
                self.uboot_time = re.findall(".*uboot time: (.*) us.*", info, re.S)[0]
            if 'Starting kernel ...' in info:
                self.write('\n\n')
            if 'console:/ $' in info:
                logging.info('now is in kernel')
                return True
        logging.info('no kernel message captured,please confirm manually')

    def write(self, command):
        '''
        enter in kernel
        @param command: command
        @return:
        '''
        self.ser.write(bytes(command + '\r', encoding='utf-8'))
        logging.info(f'=> {command}')
        sleep(0.1)

    def recv(self):
        '''
        get feedback from buffer
        @return: feedback
        '''
        while True:
            data = self.ser.read_all()
            time.sleep(5)
            if data == '':
                continue
            else:
                break
        return data.decode('utf-8')

    def recv_until_pattern(self, pattern=b'', timeout=60):
        '''
        keep get feedback from buffer until pattern has been catched
        @param pattern: pattern
        @param timeout: timeout
        @return: contains the printing of keywords
        '''
        start = time.time()
        result = []
        while True:
            if time.time() - start > timeout:
                if pattern:
                    raise TimeoutError('Time Out')
                return result
            log = self.ser.readline()
            if not log:
                continue
            # logging.info(log)
            result.append(log)
            if pattern and pattern in log:
                return result

    def receive_file_via_serial(self, output_file):
        try:
            # 打开输出文件以写入数据
            with open(output_file, 'wb') as file:
                while True:
                    # 从串口读取数据
                    data = self.ser.read(1024)
                    if not data:
                        break
                    # 将数据写入输出文件
                    file.write(data)
            print("文件传输完成")
        except serial.SerialException as e:
            print("串口连接错误:", str(e))
        except Exception as e:
            print("发生错误:", str(e))

    def __del__(self):
        try:
            self.ser.close()
            logging.info('close serial port %s' % self.ser)
        except AttributeError as e:
            logging.info('failed to open serial port,not need to close')
