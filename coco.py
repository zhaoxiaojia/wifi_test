# !/usr/bin/env python
# -*-coding:utf-8 -*-

"""
# File       : coco.py
# Time       ：2023/7/26 13:51
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""
from tools.router_tool.Router import Router

test_results = [
    {'test_scan': {'result': 'PASSED', 'return_value': None, 'fixtures': {'power_setting': ('192.168.200.1', '1'),
                                                                          'router_setting': Router(serial=None,
                                                                                                   band='2.4G',
                                                                                                   ssid='coco is handsome',
                                                                                                   wireless_mode='11AX',
                                                                                                   channel='default',
                                                                                                   bandwidth='40Mhz',
                                                                                                   authentication_method='Open System',
                                                                                                   wpa_passwd=None,
                                                                                                   test_type=None,
                                                                                                   protocol_type=None,
                                                                                                   data_row=None,
                                                                                                   expected_rate='0 0')}}},
    {'test_conn': {'result': 'PASSED', 'return_value': None, 'fixtures': {'power_setting': ('192.168.200.1', '1'),
                                                                          'router_setting': Router(serial=None,
                                                                                                   band='2.4G',
                                                                                                   ssid='coco is handsome',
                                                                                                   wireless_mode='11AX',
                                                                                                   channel='default',
                                                                                                   bandwidth='40Mhz',
                                                                                                   authentication_method='Open System',
                                                                                                   wpa_passwd=None,
                                                                                                   test_type=None,
                                                                                                   protocol_type=None,
                                                                                                   data_row=None,
                                                                                                   expected_rate='0 0')}}},
    {'test_multi_throughtput_tx': {'result': 'PASSED', 'return_value': None,
                                   'fixtures': {'power_setting': ('192.168.200.1', '1'),
                                                'router_setting': Router(serial=None, band='2.4G',
                                                                         ssid='coco is handsome',
                                                                         wireless_mode='11AX', channel='default',
                                                                         bandwidth='40Mhz',
                                                                         authentication_method='Open System',
                                                                         wpa_passwd=None, test_type=None,
                                                                         protocol_type=None, data_row=None,
                                                                         expected_rate='0 0')}}}, {
        'test_multi_throughtput_rx': {'result': 'PASSED', 'return_value': None,
                                      'fixtures': {'power_setting': ('192.168.200.1', '1'),
                                                   'router_setting': Router(serial=None, band='2.4G',
                                                                            ssid='coco is handsome',
                                                                            wireless_mode='11AX', channel='default',
                                                                            bandwidth='40Mhz',
                                                                            authentication_method='Open System',
                                                                            wpa_passwd=None, test_type=None,
                                                                            protocol_type=None, data_row=None,
                                                                            expected_rate='0 0')}}}, {
        'test_scan': {'result': 'PASSED', 'return_value': None,
                      'fixtures': {'power_setting': ('192.168.200.1', '1'),
                                   'router_setting': Router(serial=None, band='2.4G', ssid='coco is handsome',
                                                            wireless_mode='11AX', channel='default',
                                                            bandwidth='40Mhz', authentication_method='Open System',
                                                            wpa_passwd=None, test_type=None, protocol_type=None,
                                                            data_row=None, expected_rate='0 0')}}}, {
        'test_conn': {'result': 'PASSED', 'return_value': None,
                      'fixtures': {'power_setting': ('192.168.200.1', '1'),
                                   'router_setting': Router(serial=None, band='2.4G', ssid='coco is handsome',
                                                            wireless_mode='11AX', channel='default',
                                                            bandwidth='40Mhz', authentication_method='Open System',
                                                            wpa_passwd=None, test_type=None, protocol_type=None,
                                                            data_row=None, expected_rate='0 0')}}}, {
        'test_multi_throughtput_tx': {'result': 'PASSED', 'return_value': None,
                                      'fixtures': {'power_setting': ('192.168.200.1', '1'),
                                                   'router_setting': Router(serial=None, band='2.4G',
                                                                            ssid='coco is handsome',
                                                                            wireless_mode='11AX', channel='default',
                                                                            bandwidth='40Mhz',
                                                                            authentication_method='Open System',
                                                                            wpa_passwd=None, test_type=None,
                                                                            protocol_type=None, data_row=None,
                                                                            expected_rate='0 0')}}}, {
        'test_multi_throughtput_rx': {'result': 'PASSED', 'return_value': None,
                                      'fixtures': {'power_setting': ('192.168.200.1', '1'),
                                                   'router_setting': Router(serial=None, band='2.4G',
                                                                            ssid='coco is handsome',
                                                                            wireless_mode='11AX', channel='default',
                                                                            bandwidth='40Mhz',
                                                                            authentication_method='Open System',
                                                                            wpa_passwd=None, test_type=None,
                                                                            protocol_type=None, data_row=None,
                                                                            expected_rate='0 0')}}}, {
        'test_scan': {'result': 'PASSED', 'return_value': None,
                      'fixtures': {'power_setting': ('192.168.200.3', '3'),
                                   'router_setting': Router(serial=None, band='2.4G', ssid='coco is handsome',
                                                            wireless_mode='11AX', channel='default',
                                                            bandwidth='40Mhz', authentication_method='Open System',
                                                            wpa_passwd=None, test_type=None, protocol_type=None,
                                                            data_row=None, expected_rate='0 0')}}}, {
        'test_conn': {'result': 'PASSED', 'return_value': None,
                      'fixtures': {'power_setting': ('192.168.200.3', '3'),
                                   'router_setting': Router(serial=None, band='2.4G', ssid='coco is handsome',
                                                            wireless_mode='11AX', channel='default',
                                                            bandwidth='40Mhz', authentication_method='Open System',
                                                            wpa_passwd=None, test_type=None, protocol_type=None,
                                                            data_row=None, expected_rate='0 0')}}}, {
        'test_multi_throughtput_tx': {'result': 'PASSED', 'return_value': None,
                                      'fixtures': {'power_setting': ('192.168.200.3', '3'),
                                                   'router_setting': Router(serial=None, band='2.4G',
                                                                            ssid='coco is handsome',
                                                                            wireless_mode='11AX', channel='default',
                                                                            bandwidth='40Mhz',
                                                                            authentication_method='Open System',
                                                                            wpa_passwd=None, test_type=None,
                                                                            protocol_type=None, data_row=None,
                                                                            expected_rate='0 0')}}}, {
        'test_multi_throughtput_rx': {'result': 'PASSED', 'return_value': None,
                                      'fixtures': {'power_setting': ('192.168.200.3', '3'),
                                                   'router_setting': Router(serial=None, band='2.4G',
                                                                            ssid='coco is handsome',
                                                                            wireless_mode='11AX', channel='default',
                                                                            bandwidth='40Mhz',
                                                                            authentication_method='Open System',
                                                                            wpa_passwd=None, test_type=None,
                                                                            protocol_type=None, data_row=None,
                                                                            expected_rate='0 0')}}}, {
        'test_scan': {'result': 'PASSED', 'return_value': None,
                      'fixtures': {'power_setting': ('192.168.200.3', '3'),
                                   'router_setting': Router(serial=None, band='2.4G', ssid='coco is handsome',
                                                            wireless_mode='11AX', channel='default',
                                                            bandwidth='40Mhz', authentication_method='Open System',
                                                            wpa_passwd=None, test_type=None, protocol_type=None,
                                                            data_row=None, expected_rate='0 0')}}}, {
        'test_conn': {'result': 'PASSED', 'return_value': None,
                      'fixtures': {'power_setting': ('192.168.200.3', '3'),
                                   'router_setting': Router(serial=None, band='2.4G', ssid='coco is handsome',
                                                            wireless_mode='11AX', channel='default',
                                                            bandwidth='40Mhz', authentication_method='Open System',
                                                            wpa_passwd=None, test_type=None, protocol_type=None,
                                                            data_row=None, expected_rate='0 0')}}}, {
        'test_multi_throughtput_tx': {'result': 'PASSED', 'return_value': None,
                                      'fixtures': {'power_setting': ('192.168.200.3', '3'),
                                                   'router_setting': Router(serial=None, band='2.4G',
                                                                            ssid='coco is handsome',
                                                                            wireless_mode='11AX', channel='default',
                                                                            bandwidth='40Mhz',
                                                                            authentication_method='Open System',
                                                                            wpa_passwd=None, test_type=None,
                                                                            protocol_type=None, data_row=None,
                                                                            expected_rate='0 0')}}}, {
        'test_multi_throughtput_rx': {'result': 'PASSED', 'return_value': None,
                                      'fixtures': {'power_setting': ('192.168.200.3', '3'),
                                                   'router_setting': Router(serial=None, band='2.4G',
                                                                            ssid='coco is handsome',
                                                                            wireless_mode='11AX', channel='default',
                                                                            bandwidth='40Mhz',
                                                                            authentication_method='Open System',
                                                                            wpa_passwd=None, test_type=None,
                                                                            protocol_type=None, data_row=None,
                                                                            expected_rate='0 0')}}}]
row_data = []
for test_result in test_results:
    test_name = sorted(test_result.keys())[0]
    if test_name in row_data:
        print('-> ', row_data)
        row_data.clear()
    data = test_result[test_name]
    keys = sorted(data['fixtures'].keys())
    if data['fixtures'][keys[0]] not in row_data:
        for j in keys:
            row_data.append(data['fixtures'][j])
    row_data.append(test_name)
    row_data.append(data['result'])
    row_data.append(data['return_value'])
print(row_data)