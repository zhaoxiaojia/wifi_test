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
import threading

import pytest
import serial
from queue import Queue, Empty


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

    def __init__(self, serial_port='', baud='', log_file="kernel_log.txt", enable_log=True):
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

        self.status = self.ser.isOpen() if isinstance(self.ser, serial.Serial) else False
        logging.info('the status of serial port is {}'.format(self.status))

        # 日志文件和线程设置
        self.log_file = log_file
        self.keyword_flags = {}  # 存储关键字检测标志
        self.keyword_flags_lock = threading.Lock()  # 用于线程安全

        # # 启动后台线程保存日志并检测关键字
        self._rx_queue = Queue()  # <- 新增：线程安全缓冲
        self._stop_flag = threading.Event()
        if enable_log:
            self.log_thread = threading.Thread(
                target=self._save_and_detect_log, daemon=True)
            self.log_thread.start()

    def _save_and_detect_log(self):
        '''在保存日志的同时检测关键字'''
        # try:
        with open(self.log_file, 'w',encoding='utf-8',errors="ignore") as file:
            while not self._stop_flag.is_set():
                data = self.ser.read(1024)  # 不再立刻decode
                if not data:
                    continue
                file.write(data.decode('utf-8', errors='ignore').strip())
                self._rx_queue.put(data)  # <-- 喂给业务线程
                # 检查是否有关键字需要检测
                with self.keyword_flags_lock:
                    for kw in list(self.keyword_flags):
                        if kw.encode() in data:
                            self.keyword_flags[kw] = True

        # except Exception as e:
        #     logging.error(f"Logging thread error: {e}")

    def start_keyword_detection(self, keyword):
        '''开始检测指定关键字'''
        with self.keyword_flags_lock:
            self.keyword_flags[keyword] = False

    def is_keyword_detected(self, keyword):
        '''检查关键字是否被检测到'''
        with self.keyword_flags_lock:
            print(f'get {keyword} : {self.keyword_flags.get(keyword)} ')
            return self.keyword_flags.get(keyword, False)

    def clear_keyword(self, keyword):
        '''清除关键字检测状态'''
        with self.keyword_flags_lock:
            if keyword in self.keyword_flags:
                del self.keyword_flags[keyword]

    def get_ip_address(self, inet='wlan0', count=20):

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
                time.sleep(10)
                # Send command
                self.write(f'ifconfig {inet}')
                ipInfo = ''
                start_time = time.time()
                while time.time() - start_time < 10:  # 5 second timeout
                    if self.ser.in_waiting:
                        self.write(f'ifconfig {inet}')
                        time.sleep(1)
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
        print(f'=> {command}')
        sleep(0.1)

    def recv(self, timeout=5, until_newline=False):
        """
        从内部队列取数据
        :param timeout:   最长等待秒数
        :param until_newline:  True -> 读到换行就返回
        """
        deadline = time.time() + timeout
        buf = bytearray()

        while time.time() < deadline:
            try:
                chunk = self._rx_queue.get(timeout=deadline - time.time())
                buf.extend(chunk)
                if until_newline and b'\n' in chunk:
                    break
            except Empty:
                break  # 超时
        return buf.decode('utf-8', errors='ignore')

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

    def start_saving_kernel_log(self):
        try:
            with open(self.log_file, 'wb') as file:
                while True:
                    data = self.ser.read(1024)
                    if data:
                        file.write(data)
                        file.flush()  # 强制刷新缓冲区
        except serial.SerialException as e:
            print("串口连接错误:", str(e))
        except Exception as e:
            print("发生错误:", str(e))

    def search_keyword_in_log(self, keyword):
        try:
            with open(self.log_file, 'rb') as file:
                file.seek(self.log_file_position)  # 从上次记录的位置开始读取
                for line in file:
                    if keyword.encode() in line:
                        return True
                self.log_file_position = file.tell()  # 更新读取位置
            return False
        except Exception as e:
            print("发生错误:", str(e))
            return False

    def close(self):
        """安全关闭线程和串口"""
        self._stop_flag.set()
        if hasattr(self, 'log_thread') and self.log_thread.is_alive():
            self.log_thread.join(timeout=1)
        if getattr(self, 'ser', None):
            self.ser.close()

    def __del__(self):
        try:
            self.close()
            logging.info('close serial port %s' % self.ser)
        except AttributeError as e:
            logging.info('failed to open serial port,not need to close')
