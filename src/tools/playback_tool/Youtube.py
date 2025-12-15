import logging
import time

import pytest

from src.tools.playback_tool.OnlinePlayback import Online


class Youtube(Online):
    """
    YouTube

    Parameters
    ----------
    None
        This class is instantiated without additional parameters.

    Returns
    -------
    None
        Classes return instances implicitly when constructed.
    """
    PLAYERACTIVITY_REGU = 'am start -n com.google.android.youtube.tv/com.google.android.apps.youtube.tv.activity.ShellActivity -d https://www.youtube.com/watch?v={}'
    AMAZON_YOUTUBE_PACKAGENAME = 'com.amazon.firetv.youtube'
    PLAYTYPE = 'youtube'
    DECODE_TAG = 'AmlogicVideoDecoderAwesome2'
    GOOGLE_YOUTUBE_PACKAGENAME = 'com.google.android.youtube.tv'
    CURRENT_FOCUS = 'dumpsys window | grep -i mCurrentFocus'
    YOUTUBE_DECODE_TAG = 'C2VDAComponent'
    VIDEO_INFO = []

    VIDEO_TAG_LIST = [
        {'link': 'vX2vsvdq8nw', 'name': '4K HDR 60FPS Sniper Will Smith'},

        {'link': '-ZMVjKT3-5A', 'name': 'NBC News (vp9)'},
        {'link': 'LXb3EKWsInQ', 'name': 'COSTA RICA IN 4K 60fps HDR (ULTRA HD) (vp9)'},
        {'link': 'b6fzbyPoNXY', 'name': 'Las Vegas Strip at Night in 4k UHD HLG HDR (vp9)'},
        {'link': 'AtZrf_TWmSc', 'name': 'How to Convert,Import,and Edit AVCHD Files for Premiere (H264)'},
        {'link': 'LXb3EKWsInQ', 'name': 'COSTA RICA IN 4K 60fps HDR(ultra hd) (4k 60fps)'},
        {'link': 'NVhmq-pB_cs', 'name': 'Mr Bean 720 25fps (720 25fps)'},
        {'link': 'bcOgjyHb_5Y', 'name': 'paid video'},
        {'link': 'rf7ft8-nUQQ', 'name': 'stress video'}

    ]

    def __init__(self, ):
        """
        Init

        Parameters
        ----------
        None
            This function does not accept any parameters beyond the implicit context.

        Returns
        -------
        None
            This function does not return a value.
        """
        super().__init__()

    def youtube_playback(self, playback_format, repeat_time=0, seekcheck=False, switch_able=False, home_able=False):
        """
        YouTube playback

        Sends shell commands to the host or device and returns the output.
        Waits for a specified duration to allow asynchronous operations to complete.
        Interacts with the DUT via pytest to issue commands or key events.
        Sends key events to the device to control its user interface.
        Asserts conditions to verify the success of operations.
        Logs informational or warning messages for debugging and status reporting.

        Parameters
        ----------
        playback_format : object
            Codec or file format used for video playback.
        repeat_time : object
            Number of times to repeat an operation for stress testing.
        seekcheck : object
            Flag controlling whether to perform seek operations during playback.
        switch_able : object
            Toggle indicating whether switching between videos is enabled.
        home_able : object
            Toggle indicating whether returning to the home screen is allowed.

        Returns
        -------
        object
            Description of the returned value.
        """
        for i in self.VIDEO_TAG_LIST:
            if playback_format == "VP9":
                if i['link'] == "-ZMVjKT3-5A":

                    logging.info(f"Start playing Youtube - {i['name']}")
                    self.playback(self.PLAYERACTIVITY_REGU, i['link'])
                    assert self.check_playback_status(), 'playback not success'
                    time.sleep(30)

                    break
                else:
                    continue
            elif playback_format == "AV1":
                if i['link'] == "NVhmq-pB_cs":

                    logging.info(f"Start playing Youtube - {i['name']}")
                    self.playback(self.PLAYERACTIVITY_REGU, i['link'])
                    assert self.check_playback_status(), 'playback not success'
                    time.sleep(30)

                    break
                else:
                    continue
            elif playback_format == "paid_video":
                if i['link'] == "bcOgjyHb_5Y":

                    logging.info(f"Start playing Youtube - {i['name']}")
                    self.playback(self.PLAYERACTIVITY_REGU, i['link'])
                    assert self.check_playback_status(), 'playback not success'
                    time.sleep(30)

                    break
                else:
                    continue
            elif playback_format == "VP9 and AV1":
                if i['link'] == "NVhmq-pB_cs":
                    switch_able = not switch_able

                    logging.info(f"Start playing Youtube - {i['name']}")
                    self.playback(self.PLAYERACTIVITY_REGU, i['link'])
                    assert self.check_playback_status(), 'playback not success'
                    time.sleep(30)

                    if not switch_able:
                        logging.info("switch successful")
                        return True
                elif i['link'] == "-ZMVjKT3-5A":
                    switch_able = not switch_able

                    logging.info(f"Start playing Youtube - {i['name']}")
                    self.playback(self.PLAYERACTIVITY_REGU, i['link'])
                    assert self.check_playback_status(), 'playback not success'
                    time.sleep(30)

                    if not switch_able:
                        logging.info("switch successful")
                        return True
                else:
                    continue
            elif playback_format is None and seekcheck:
                if i['link'] == "-ZMVjKT3-5A":

                    logging.info(f"Start playing Youtube - {i['name']}")
                    self.playback(self.PLAYERACTIVITY_REGU, i['link'])
                    assert self.check_playback_status(), 'playback not success'
                    time.sleep(10)

                    pytest.dut.keyevent("KEYCODE_DPAD_CENTER")
                    time.sleep(2)
                    pytest.dut.keyevent("KEYCODE_DPAD_RIGHT")
                    time.sleep(2)
                    pytest.dut.keyevent("KEYCODE_DPAD_CENTER")
                    time.sleep(30)

                else:
                    continue
            elif playback_format is None and home_able:
                if i['link'] == "-ZMVjKT3-5A":

                    logging.info(f"Start playing Youtube - {i['name']}")
                    self.playback(self.PLAYERACTIVITY_REGU, i['link'])
                    assert self.check_playback_status(), 'playback not success'
                    time.sleep(10)

                    pytest.dut.keyevent("KEYCODE_HOME")
                    time.sleep(2)
                    pytest.dut.checkoutput(f'monkey -p {self.GOOGLE_YOUTUBE_PACKAGENAME} 1')
                    time.sleep(2)

                else:
                    continue
            elif playback_format == "stress":
                if i['link'] == "rf7ft8-nUQQ":

                    logging.info(f"Start playing Youtube - {i['name']}")
                    self.playback(self.PLAYERACTIVITY_REGU, i['link'])
                    assert self.check_playback_status(), 'playback not success'
                    time.sleep(10)

                    break
                else:
                    continue
            else:

                logging.info(f"Start playing Youtube - {i['name']}")
                self.playback(self.PLAYERACTIVITY_REGU, i['link'])
                assert self.check_playback_status(), 'playback not success'
                time.sleep(30)

                if i['name'] == '4K HDR 60FPS Sniper Will Smith':
                    ...

                if seekcheck == "True":
                    pytest.dut.keyevent("KEYCODE_DPAD_CENTER")
                    time.sleep(5)

    def check_Youtube_exist(self):
        """
        Check YouTube exist

        Sends shell commands to the host or device and returns the output.

        Parameters
        ----------
        None
            This function does not accept any parameters beyond the implicit context.

        Returns
        -------
        object
            Description of the returned value.
        """
        return True if self.GOOGLE_YOUTUBE_PACKAGENAME in self.checkoutput('pm list packages') else False

    def time_out(self):
        """
        Time out

        Logs informational or warning messages for debugging and status reporting.

        Parameters
        ----------
        None
            This function does not accept any parameters beyond the implicit context.

        Returns
        -------
        None
            This function does not return a value.
        """
        logging.warning('Time over!')

    def check_current_window(self):
        """
        Check current window

        Sends shell commands to the host or device and returns the output.
        Interacts with the DUT via pytest to issue commands or key events.

        Parameters
        ----------
        None
            This function does not accept any parameters beyond the implicit context.

        Returns
        -------
        object
            Description of the returned value.
        """
        current_window = pytest.dut.checkoutput(self.CURRENT_FOCUS)[1]
        return current_window

    def stop_youtube(self):
        """
        Stop YouTube

        Sends shell commands to the host or device and returns the output.
        Waits for a specified duration to allow asynchronous operations to complete.
        Interacts with the DUT via pytest to issue commands or key events.
        Logs informational or warning messages for debugging and status reporting.

        Parameters
        ----------
        None
            This function does not accept any parameters beyond the implicit context.

        Returns
        -------
        None
            This function does not return a value.
        """
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
