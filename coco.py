# !/usr/bin/env python
# -*-coding:utf-8 -*-

"""
# File       : coco.py
# Time       ：2023/7/26 13:51
# Author     ：chao.li
# version    ：python 3.9
# Description：
"""
import logging

COMMANDS = {
    # Standard Keys
    "home": "Home",
    "reverse": "Rev",
    "forward": "Fwd",
    "play": "Play",
    "select": "Select",
    "left": "Left",
    "right": "Right",
    "down": "Down",
    "up": "Up",
    "back": "Back",
    "replay": "InstantReplay",
    "info": "Info",
    "backspace": "Backspace",
    "search": "Search",
    "enter": "Enter",
    "literal": "Lit",
    # For devices that support "Find Remote"
    "find_remote": "FindRemote",
    # For Roku TV
    "volume_down": "VolumeDown",
    "volume_up": "VolumeUp",
    "volume_mute": "VolumeMute",
    # For Roku TV while on TV tuner channel
    "channel_up": "ChannelUp",
    "channel_down": "ChannelDown",
    # For Roku TV current input
    "input_tuner": "InputTuner",
    "input_hdmi1": "InputHDMI1",
    "input_hdmi2": "InputHDMI2",
    "input_hdmi3": "InputHDMI3",
    "input_hdmi4": "InputHDMI4",
    "input_av1": "InputAV1",
    # For devices that support being turned on/off
    "power": "Power",
    "poweroff": "PowerOff",
    "poweron": "PowerOn",
}

from roku import Roku

co = Roku("192.168.31.21")
co.home()

def remote(button_list):
    button_dict = {'h':'home','p':'play','s':'select','l':'left','r':'right','d':'down','u':'up','b':'back','i':'info'}
    for i in button_list:
        if i in COMMANDS:
            getattr(co,button_dict[i])()
        else:
            logging.info(f'{i} not in button_dict .pls check again')


remote(['h','d'])