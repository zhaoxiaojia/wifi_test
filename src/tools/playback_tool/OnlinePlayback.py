import logging
import pytest
from src.util.decorators import set_timeout


class Online():
    """
    Online

    Parameters
    ----------
    None
        This class is instantiated without additional parameters.

    Returns
    -------
    None
        Classes return instances implicitly when constructed.
    """
    DECODE_TAG = 'AmlogicVideoDecoderAwesome'
    DECODE_TAG_AndroidS = 'VDA'
    PLAYER_PACKAGE_TUPLE = '', ''

    def __init__(self):
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
        ...

    def playback(self, activity, link):
        """
        Playback

        Sends shell commands to the host or device and returns the output.
        Interacts with the DUT via pytest to issue commands or key events.
        Logs informational or warning messages for debugging and status reporting.

        Parameters
        ----------
        activity : object
            Activity component name used to launch an Android application.
        link : object
            Video identifier or URL used for media playback.

        Returns
        -------
        None
            This function does not return a value.
        """
        logging.info(activity.format(link))
        pytest.dut.checkoutput(activity.format(link))

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

    @set_timeout(300)
    def check_playback_status(self):
        """
        Check playback status

        Parameters
        ----------
        None
            This function does not accept any parameters beyond the implicit context.

        Returns
        -------
        object
            Description of the returned value.
        """
        return True

    def check_apk_exist(self):
        """
        Check apk exist

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
        return True if self.PLAYER_PACKAGE_TUPLE[0] in pytest.dut.checkoutput('ls /data/data/') else False
