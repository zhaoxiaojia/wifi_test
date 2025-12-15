"""
This module implements serial tool functionality for the ``connect_tool`` package.

It provides a ``serial_tool`` class which wraps low‑level ``pyserial`` primitives
to manage a serial connection, read and write data, and collect logs from a
device under test.  The module defines helper methods for connection recovery,
log saving, keyword detection and other convenience operations used by the
test harness.  All methods expose docstrings to describe their purpose and
parameters in English.
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
from typing import Annotated


class serial_tool:
    """
    Serial tool.

    -------------------------
    It logs information for debugging or monitoring purposes.
    It introduces delays to allow the device to process commands.

    -------------------------
    Returns
    -------------------------
    None
        This class does not return a value.
    """

    def __init__(self, serial_port='', baud='', log_file="kernel_log.txt", enable_log=True):
        """
        Init.

        -------------------------
        It logs information for debugging or monitoring purposes.

        -------------------------
        Parameters
        -------------------------
        serial_port : Any
            The ``serial_port`` parameter.
        baud : Any
            The ``baud`` parameter.
        log_file : Any
            The ``log_file`` parameter.
        enable_log : Any
            The ``enable_log`` parameter.

        -------------------------
        Returns
        -------------------------
        None
            This method does not return a value.
        """
        self.serial_port = serial_port or pytest.config.get('serial_port')['port']
        self.baud = baud or pytest.config.get('serial_port')['baud']
        logging.info(f'port {self.serial_port} baud {self.baud}')
        self.ethernet_ip = ''
        self.uboot_time = 0
        self.ser = None
        self._open_serial()
        self.status = self._is_serial_open()
        logging.info('Serial port open status: %s', self.status)

        self.log_file = log_file
        self.keyword_flags = {}  # Dictionary storing detection flags for keywords
        self.keyword_flags_lock = threading.Lock()  # Lock used for thread safety

        self._rx_queue = Queue()  # Thread‑safe receive buffer
        self._stop_flag = threading.Event()
        if enable_log:
            self.log_thread = threading.Thread(
                target=self._save_and_detect_log, daemon=True)
            self.log_thread.start()

    def _open_serial(self):
        """
        Open serial.

        -------------------------
        It logs information for debugging or monitoring purposes.

        -------------------------
        Returns
        -------------------------
        None
            This method does not return a value.
        """
        try:
            self.ser = serial.Serial(self.serial_port, self.baud,
                                     bytesize=serial.EIGHTBITS,
                                     parity=serial.PARITY_NONE,
                                     stopbits=serial.STOPBITS_ONE,
                                     xonxoff=False,
                                     rtscts=False,
                                     dsrdtr=False,
                                     timeout=1)
            logging.info('Serial port %s-%s opened', self.serial_port, self.baud)
        except serial.serialutil.SerialException as e:
            logging.error('Failed to open serial port %s-%s: %s',
                          self.serial_port, self.baud, e)
            self.ser = None

    def _is_serial_open(self):
        """
        Is serial open.

        -------------------------
        Returns
        -------------------------
        Any
            The result produced by the function.
        """
        if not self.ser:
            return False
        attr = getattr(self.ser, 'is_open', None)
        if isinstance(attr, bool):
            return attr
        if callable(attr):
            try:
                return bool(attr())
            except Exception:
                return False
        legacy = getattr(self.ser, 'isOpen', None)
        if callable(legacy):
            try:
                return bool(legacy())
            except Exception:
                return False
        return False

    def _ensure_connection(self, retries=3, interval=2):
        """
        Ensure connection.

        -------------------------
        It logs information for debugging or monitoring purposes.

        -------------------------
        Parameters
        -------------------------
        retries : Any
            The ``retries`` parameter.
        interval : Any
            The ``interval`` parameter.

        -------------------------
        Returns
        -------------------------
        Any
            The result produced by the function.
        """
        if self._is_serial_open():
            self.status = True
            return True

        for attempt in range(1, retries + 1):
            logging.warning('Serial connection lost, retrying to connect (%s/%s)',
                            attempt, retries)
            if self.ser:
                try:
                    self.ser.close()
                except serial.serialutil.SerialException as e:
                    logging.debug('Error closing serial during reconnect: %s', e)
                finally:
                    self.ser = None
            self._open_serial()
            if self._is_serial_open():
                self.status = True
                logging.info('Serial reconnected successfully')
                return True
            sleep(interval)

        self.status = False
        raise RuntimeError('Failed to reconnect serial port after multiple attempts')

    def _save_and_detect_log(self):
        """
        Save and detect log.

        -------------------------
        It introduces delays to allow the device to process commands.

        -------------------------
        Returns
        -------------------------
        None
            This method does not return a value.
        """
        with open(self.log_file, 'w', encoding='utf-8', errors="ignore") as file:
            while not self._stop_flag.is_set():
                if not self._is_serial_open():
                    time.sleep(0.5)
                    continue
                data = self.ser.read(1024)  # Do not decode immediately
                if not data:
                    continue
                chunk = data.decode("utf-8", errors="ignore")
                chunk = chunk.replace("\r\n", "\n").replace("\r", "\n")
                file.write(chunk)
                self._rx_queue.put(data)  # Feed data to the business thread
                with self.keyword_flags_lock:
                    for kw in list(self.keyword_flags):
                        if kw.encode() in data:
                            self.keyword_flags[kw] = True

    def start_keyword_detection(self, keyword):
        """
        Start keyword detection.

        -------------------------
        Parameters
        -------------------------
        keyword : Any
            The ``keyword`` parameter.

        -------------------------
        Returns
        -------------------------
        None
            This method does not return a value.
        """
        with self.keyword_flags_lock:
            self.keyword_flags[keyword] = False

    def is_keyword_detected(self, keyword):
        """
        Is keyword detected.

        -------------------------
        It logs information for debugging or monitoring purposes.

        -------------------------
        Parameters
        -------------------------
        keyword : Any
            The ``keyword`` parameter.

        -------------------------
        Returns
        -------------------------
        Any
            The result produced by the function.
        """
        with self.keyword_flags_lock:
            logging.debug("get %s : %s", keyword, self.keyword_flags.get(keyword))
            return self.keyword_flags.get(keyword, False)

    def clear_keyword(self, keyword):
        """
        Clear keyword.

        -------------------------
        Parameters
        -------------------------
        keyword : Any
            The ``keyword`` parameter.

        -------------------------
        Returns
        -------------------------
        None
            This method does not return a value.
        """
        with self.keyword_flags_lock:
            if keyword in self.keyword_flags:
                del self.keyword_flags[keyword]

    def get_ip_address(self, inet='wlan0', count=20):
        """
        Retrieve ip address.

        -------------------------
        It logs information for debugging or monitoring purposes.
        It introduces delays to allow the device to process commands.

        -------------------------
        Parameters
        -------------------------
        inet : Any
            The ``inet`` parameter.
        count : Any
            The ``count`` parameter.

        -------------------------
        Returns
        -------------------------
        Any
            The result produced by the function.
        """

        for attempt in range(count, 0, -1):
            try:
                self.ser.reset_input_buffer()
                self.write('\x1A')
                self.write('bg')
                time.sleep(10)
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
        """
        Write pipe.

        -------------------------
        It logs information for debugging or monitoring purposes.

        -------------------------
        Parameters
        -------------------------
        command : Any
            The ``command`` parameter.

        -------------------------
        Returns
        -------------------------
        Any
            The result produced by the function.
        """
        try:
            self.ser.write(bytes(command + '\r', encoding='utf-8'))
        except (serial.serialutil.SerialException, AttributeError, OSError) as err:
            logging.error('Serial write failed for command %s: %s', command, err)
            self._ensure_connection()
            self.ser.write(bytes(command + '\r', encoding='utf-8'))
        logging.info(f'=> {command}')
        sleep(0.1)
        data = self.recv()
        logging.debug(data.strip())
        return data

    def enter_uboot(self):
        """
        Enter uboot.

        -------------------------
        It logs information for debugging or monitoring purposes.

        -------------------------
        Returns
        -------------------------
        Any
            The result produced by the function.
        """
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
                return True
            if 'sc2_ah212#' or 's4_ap222#' in info:
                logging.info('OTT is in uboot')
                return True
            else:
                self.write('\n\n')
        logging.info('no uboot info printed,please confirm manually')

    def enter_kernel(self):
        """
        Enter kernel.

        -------------------------
        It logs information for debugging or monitoring purposes.

        -------------------------
        Returns
        -------------------------
        Any
            The result produced by the function.
        """
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
        """
        Write.

        -------------------------
        It logs information for debugging or monitoring purposes.

        -------------------------
        Parameters
        -------------------------
        command : Any
            The ``command`` parameter.

        -------------------------
        Returns
        -------------------------
        None
            This method does not return a value.
        """
        try:
            self.ser.write(bytes(command + '\r', encoding='utf-8'))
        except (serial.serialutil.SerialException, AttributeError, OSError) as err:
            logging.error('Serial write failed for command %s: %s', command, err)
            self._ensure_connection()
            self.ser.write(bytes(command + '\r', encoding='utf-8'))
        logging.info(f'=> {command}')
        sleep(0.1)

    def recv(self, timeout=5, until_newline=False):
        """
        Recv.

        -------------------------
        Parameters
        -------------------------
        timeout : Any
            Timeout in seconds for waiting or connection operations.
        until_newline : Any
            The ``until_newline`` parameter.

        -------------------------
        Returns
        -------------------------
        Any
            The result produced by the function.
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
                break  # Timeout
        return buf.decode('utf-8', errors='ignore')

    def recv_until_pattern(self, pattern=b'', timeout=60):
        """
        Recv until pattern.

        -------------------------
        It logs information for debugging or monitoring purposes.

        -------------------------
        Parameters
        -------------------------
        pattern : Any
            The ``pattern`` parameter.
        timeout : Any
            Timeout in seconds for waiting or connection operations.

        -------------------------
        Returns
        -------------------------
        Any
            The result produced by the function.
        """
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
            result.append(log)
            if pattern and pattern in log:
                return result

    def receive_file_via_serial(self, output_file):
        """
        Receive file via serial.

        -------------------------
        It logs information for debugging or monitoring purposes.

        -------------------------
        Parameters
        -------------------------
        output_file : Any
            The ``output_file`` parameter.

        -------------------------
        Returns
        -------------------------
        None
            This method does not return a value.
        """
        try:
            with open(output_file, 'wb') as file:
                while True:
                    data = self.ser.read(1024)
                    if not data:
                        break
                    file.write(data)
            logging.info("File transfer completed")
        except serial.SerialException as e:
            logging.error("Serial connection error: %s", str(e))
        except Exception as e:
            logging.error("An error occurred: %s", str(e))

    def start_saving_kernel_log(self):
        """
        Start saving kernel log.

        -------------------------
        It logs information for debugging or monitoring purposes.

        -------------------------
        Returns
        -------------------------
        None
            This method does not return a value.
        """
        try:
            with open(self.log_file, 'wb') as file:
                while True:
                    data = self.ser.read(1024)
                    if data:
                        file.write(data)
                        file.flush()  # Force flush the buffer
        except serial.SerialException as e:
            logging.error("Serial connection error: %s", str(e))
        except Exception as e:
            logging.error("An error occurred: %s", str(e))

    def search_keyword_in_log(self, keyword):
        """
        Search keyword in log.

        -------------------------
        It logs information for debugging or monitoring purposes.

        -------------------------
        Parameters
        -------------------------
        keyword : Any
            The ``keyword`` parameter.

        -------------------------
        Returns
        -------------------------
        Any
            The result produced by the function.
        """
        try:
            with open(self.log_file, 'rb') as file:
                file.seek(self.log_file_position)  # Start reading from the last recorded position
                for line in file:
                    if keyword.encode() in line:
                        return True
                self.log_file_position = file.tell()  # Update read position
            return False
        except Exception as e:
            logging.error("An error occurred: %s", str(e))
            return False

    def close(self):
        """
        Close.

        -------------------------
        Returns
        -------------------------
        None
            This method does not return a value.
        """
        self._stop_flag.set()
        if hasattr(self, 'log_thread') and self.log_thread.is_alive():
            self.log_thread.join(timeout=1)
        if getattr(self, 'ser', None):
            self.ser.close()

    def __del__(self):
        """
        Del.

        -------------------------
        It logs information for debugging or monitoring purposes.

        -------------------------
        Returns
        -------------------------
        None
            This method does not return a value.
        """
        try:
            self.close()
            logging.info('close serial port %s' % self.ser)
        except AttributeError as e:
            logging.info('failed to open serial port,not need to close')
