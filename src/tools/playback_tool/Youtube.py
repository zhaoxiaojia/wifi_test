# !/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2024/8/19 10:35
# @Author  : chao.li
# @File    : Youtube.py



import logging
import time

import pytest

from src.tools.playback_tool.OnlinePlayback import Online


class Youtube(Online):
    '''
    Youtube video playback

    Attributes:
        PLAYERACTIVITY_REGU : player command regular
        AMAZON_YOUTUBE_PACKAGENAME : amazon youtube package name
        PLAYTYPE : playback type
        DECODE_TAG : logcat tag
        GOOGLE_YOUTUBE_PACKAGENAME : google youtube package name
        YOUTUBE_DECODE_TAG : logcat tag
        VIDEO_INFO : video info
        VIDEO_TAG_LIST : play video info list [dict]

    '''

    PLAYERACTIVITY_REGU = 'am start -n com.google.android.youtube.tv/com.google.android.apps.youtube.tv.activity.ShellActivity -d https://www.youtube.com/watch?v={}'
    AMAZON_YOUTUBE_PACKAGENAME = 'com.amazon.firetv.youtube'
    PLAYTYPE = 'youtube'
    DECODE_TAG = 'AmlogicVideoDecoderAwesome2'
    GOOGLE_YOUTUBE_PACKAGENAME = 'com.google.android.youtube.tv'
    CURRENT_FOCUS = 'dumpsys window | grep -i mCurrentFocus'
    YOUTUBE_DECODE_TAG = 'C2VDAComponent'
    VIDEO_INFO = []

    VIDEO_TAG_LIST = [
        {'link': 'vX2vsvdq8nw', 'name': '4K HDR 60FPS Sniper Will Smith'},  # 4k hrd 60 fps
        # {'link': '9Auq9mYxFEE', 'name': 'Sky Live'},
        {'link': '-ZMVjKT3-5A', 'name': 'NBC News (vp9)'},  # vp9
        {'link': 'LXb3EKWsInQ', 'name': 'COSTA RICA IN 4K 60fps HDR (ULTRA HD) (vp9)'},  # vp9
        {'link': 'b6fzbyPoNXY', 'name': 'Las Vegas Strip at Night in 4k UHD HLG HDR (vp9)'},  # vp9
        {'link': 'AtZrf_TWmSc', 'name': 'How to Convert,Import,and Edit AVCHD Files for Premiere (H264)'},  # H264
        {'link': 'LXb3EKWsInQ', 'name': 'COSTA RICA IN 4K 60fps HDR(ultra hd) (4k 60fps)'},  # 4k 60fps
        {'link': 'NVhmq-pB_cs', 'name': 'Mr Bean 720 25fps (720 25fps)'},
        {'link': 'bcOgjyHb_5Y', 'name': 'paid video'},
        {'link': 'rf7ft8-nUQQ', 'name': 'stress video'}
        # {'link': 'hNAbQYU0wpg', 'name': 'VR 360 Video of Top 5 Roller (360)'}  # 360
    ]

    def __init__(self,):
        super().__init__()

    def youtube_playback(self, playback_format, repeat_time=0, seekcheck=False, switch_able=False, home_able=False):
        '''
        playback video from VIDEO_TAG_LIST
        @param seekcheck: seek check fun contril : boolean
        @return: None
        '''
        for i in self.VIDEO_TAG_LIST:
            if playback_format == "VP9":
                if i['link'] == "-ZMVjKT3-5A":
                    # playerCheck.reset()
                    logging.info(f"Start playing Youtube - {i['name']}")
                    self.playback(self.PLAYERACTIVITY_REGU, i['link'])
                    assert self.check_playback_status(), 'playback not success'
                    time.sleep(30)
                    # playerCheck.check_secure()
                    # assert playerCheck.run_check_main_thread(30), f'play_error: {i}'
                    break
                else:
                    continue
            elif playback_format == "AV1":
                if i['link'] == "NVhmq-pB_cs":
                    # playerCheck.reset()
                    logging.info(f"Start playing Youtube - {i['name']}")
                    self.playback(self.PLAYERACTIVITY_REGU, i['link'])
                    assert self.check_playback_status(), 'playback not success'
                    time.sleep(30)
                    # playerCheck.check_secure()
                    # assert playerCheck.run_check_main_thread(30), f'play_error: {i}'
                    break
                else:
                    continue
            elif playback_format == "paid_video":
                if i['link'] == "bcOgjyHb_5Y":
                    # playerCheck.reset()
                    logging.info(f"Start playing Youtube - {i['name']}")
                    self.playback(self.PLAYERACTIVITY_REGU, i['link'])
                    assert self.check_playback_status(), 'playback not success'
                    time.sleep(30)
                    # playerCheck.check_secure()
                    # assert playerCheck.run_check_main_thread(30), f'play_error: {i}'
                    break
                else:
                    continue
            elif playback_format == "VP9 and AV1":
                if i['link'] == "NVhmq-pB_cs":
                    switch_able = not switch_able
                    # playerCheck.reset()
                    logging.info(f"Start playing Youtube - {i['name']}")
                    self.playback(self.PLAYERACTIVITY_REGU, i['link'])
                    assert self.check_playback_status(), 'playback not success'
                    time.sleep(30)
                    # playerCheck.check_secure()
                    # assert playerCheck.run_check_main_thread(30), f'play_error: {i}'
                    if not switch_able:
                        logging.info("switch successful")
                        return True
                elif i['link'] == "-ZMVjKT3-5A":
                    switch_able = not switch_able
                    # playerCheck.reset()
                    logging.info(f"Start playing Youtube - {i['name']}")
                    self.playback(self.PLAYERACTIVITY_REGU, i['link'])
                    assert self.check_playback_status(), 'playback not success'
                    time.sleep(30)
                    # playerCheck.check_secure()
                    # assert playerCheck.run_check_main_thread(30), f'play_error: {i}'
                    if not switch_able:
                        logging.info("switch successful")
                        return True
                else:
                    continue
            elif playback_format is None and seekcheck:
                if i['link'] == "-ZMVjKT3-5A":
                    # playerCheck.reset()
                    logging.info(f"Start playing Youtube - {i['name']}")
                    self.playback(self.PLAYERACTIVITY_REGU, i['link'])
                    assert self.check_playback_status(), 'playback not success'
                    time.sleep(10)
                    # playerCheck.check_secure()
                    pytest.dut.keyevent("KEYCODE_DPAD_CENTER")
                    time.sleep(2)
                    pytest.dut.keyevent("KEYCODE_DPAD_RIGHT")
                    time.sleep(2)
                    pytest.dut.keyevent("KEYCODE_DPAD_CENTER")
                    time.sleep(30)
                    # return playerCheck.check_seek()
                else:
                    continue
            elif playback_format is None and home_able:
                if i['link'] == "-ZMVjKT3-5A":
                    # playerCheck.reset()
                    logging.info(f"Start playing Youtube - {i['name']}")
                    self.playback(self.PLAYERACTIVITY_REGU, i['link'])
                    assert self.check_playback_status(), 'playback not success'
                    time.sleep(10)
                    # playerCheck.check_secure()
                    pytest.dut.keyevent("KEYCODE_HOME")
                    time.sleep(2)
                    pytest.dut.checkoutput(f'monkey -p {self.GOOGLE_YOUTUBE_PACKAGENAME} 1')
                    time.sleep(2)
                    # return playerCheck.check_home_play()
                else:
                    continue
            elif playback_format == "stress":
                if i['link'] == "rf7ft8-nUQQ":
                    # playerCheck.reset()
                    logging.info(f"Start playing Youtube - {i['name']}")
                    self.playback(self.PLAYERACTIVITY_REGU, i['link'])
                    assert self.check_playback_status(), 'playback not success'
                    time.sleep(10)
                    # playerCheck.check_secure()
                    # assert playerCheck.run_check_main_thread(repeat_time), f'play_error: {i}'
                    break
                else:
                    continue
            else:
                # playerCheck.reset()
                logging.info(f"Start playing Youtube - {i['name']}")
                self.playback(self.PLAYERACTIVITY_REGU, i['link'])
                assert self.check_playback_status(), 'playback not success'
                time.sleep(30)
                # playerCheck.check_secure()
                if i['name'] == '4K HDR 60FPS Sniper Will Smith':
                    ...
                    # logging.info(playerCheck.check_frame_rate())
                    # assert playerCheck.check_frame_rate() == '59', 'frame rate error'
                # assert playerCheck.run_check_main_thread(30), f'play_error: {i}'
                if seekcheck == "True":
                    pytest.dut.keyevent("KEYCODE_DPAD_CENTER")
                    time.sleep(5)
                    # TODO seek_check not found
                    # playerCheck.seek_check()
                # self.home()

    def check_Youtube_exist(self):
        return True if self.GOOGLE_YOUTUBE_PACKAGENAME in self.checkoutput('pm list packages') else False

    def time_out(self):
        logging.warning('Time over!')
        # if hasattr(self, 'logcat') and isinstance(self.logcat, subprocess.Popen):
        #     os.kill(self.logcat.pid, signal.SIGTERM)
        #     self.logcat.terminate()
        # self.clear_logcat()

    def check_current_window(self):
        current_window = pytest.dut.checkoutput(self.CURRENT_FOCUS)[1]
        return current_window

    def stop_youtube(self):
        pytest.dut.checkoutput("am force-stop com.google.android.youtube.tv")
        time.sleep(2)
        count = 0
        while True:
            if self.GOOGLE_YOUTUBE_PACKAGENAME not in self.check_current_window():
                logging.info("youtube is closed successfully")
                break
            else:
                time.sleep(1)
                count = count + 1
            if count >= 5:
                pytest.dut.checkoutput("am force-stop com.google.android.youtube.tv")
                if self.GOOGLE_YOUTUBE_PACKAGENAME not in self.check_current_window():
                    logging.info("youtube is closed successfully")
                    break
                else:
                    raise ValueError("apk hasn't exited yet")
            else:
                logging.debug("continue check")
        pytest.dut.kill_logcat_pid()
        pytest.dut.checkoutput("logcat -c")



# class YoutubeFunc(WifiTestApk):
#
#     YOUTUBE_PACKAGE = 'com.google.android.youtube.tv'
#     YOUTUBE_APK = ''
#     PLAY_COMMAND = "am start -n com.google.android.youtube.tv/com.google.android.apps.youtube.tv.activity.ShellActivity -d/' https://www.youtube.com/watch?v=DYptgVvkVLQ&list=RDMM8DvsTnWz3mo&index=3 /' "
#     STOP_COMMAND = 'am force-stop com.google.android.youtube.tv'
#
#     def __init__(self):
#         super(YoutubeFunc, self).__init__()
#
#     def check_Youtube_exist(self):
#         return True if self.YOUTUBE_PACKAGE in self.checkoutput('pm list packages') else False
#
#     def youtube_setup(self):
#         if not self.check_Youtube_exist():
#             assert self.install_apk("apk/" + self.YOUTUBE_APK)
#         self.get_permissions()
#         self.push_config()
#         self.clear_logcat()
#
#     def start_youtube(self):
#         playerCheck.reset()
#         name = "check_stuck_avsync_audio.txt"
#         if os.path.exists(os.path.join(self.logdir, name)):
#             os.remove(os.path.join(self.logdir, name))
#         if not self.check_Youtube_exist():
#             assert self.install_apk("apk/" + self.YOUTUBE_APK)
#         self.run_shell_cmd(self.PLAY_COMMAND)
#         time.sleep(60)
#         playerCheck.check_secure()
#         assert playerCheck.run_check_main_thread(30), 'play_error'
#         logging.info("youtube is start successfully")
#
#     def stop_youtube(self):
#         self.run_shell_cmd(self.STOP_COMMAND)
#         logging.info("youtube is closed successfully")
#
#     def connect_speed(self):
#         self.clear_logcat()
#         time.sleep(2)
#         cmd_speed = 'Online_Playback'
#         logging.info(f"{cmd_speed}")
#         name = 'wifi_speed.log'
#         log, logcat_file = self.save_logcat(name, 'WifiTest')
#         self.run_shell_cmd(self.wifi_cmd.format(cmd_speed))
#         self.stop_save_logcat(log, logcat_file)
#         with open(logcat_file.name, 'r+') as f:
#             for i in f.readlines():
#                 if 'Mbps' in i:
#                     logging.info(f"Now the wifi speed is {i}")
