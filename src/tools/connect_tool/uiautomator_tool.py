import logging
import time
import uiautomator2 as u2


class UiautomatorTool:
    """
    Uiautomator tool.

    -------------------------
    It logs information for debugging or monitoring purposes.
    It introduces delays to allow the device to process commands.

    -------------------------
    Returns
    -------------------------
    None
        This class does not return a value.
    """

    def __init__(self, serialnumber, type="u2"):
        """
        Init.

        -------------------------
        Parameters
        -------------------------
        serialnumber : Any
            The ADB serial number identifying the target device.
        type : Any
            Type specifier for the UI automation tool (e.g., "u2").

        -------------------------
        Returns
        -------------------------
        None
            This method does not return a value.
        """
        if type == "u2":
            self.d2 = u2.connect(serialnumber)

    def __new__(cls, *args, **kwargs):
        """
        New.

        -------------------------
        Returns
        -------------------------
        Any
            The result produced by the function.
        """
        if not hasattr(UiautomatorTool, "_instance"):
            if not hasattr(UiautomatorTool, "_instance"):
                UiautomatorTool._instance = object.__new__(cls)
        return UiautomatorTool._instance

    def wait(self, text):
        """
        Wait for.

        -------------------------
        It logs information for debugging or monitoring purposes.
        It introduces delays to allow the device to process commands.

        -------------------------
        Parameters
        -------------------------
        text : Any
            Text to input into the device.

        -------------------------
        Returns
        -------------------------
        Any
            The result produced by the function.
        """
        logging.info(f'waiting for {text}')
        for _ in range(5):
            if self.d2.exists(text=text):
                self.d2(text=text).click()
                return 1
            time.sleep(1)
        logging.debug('not click')

    def wait_not_exist(self, text):
        """
        Wait for not exist.

        -------------------------
        It logs information for debugging or monitoring purposes.
        It introduces delays to allow the device to process commands.

        -------------------------
        Parameters
        -------------------------
        text : Any
            Text to input into the device.

        -------------------------
        Returns
        -------------------------
        Any
            The result produced by the function.
        """
        logging.info(f'waiting for {text} disappear')
        for _ in range(5):
            if not self.d2.exists(text=text):
                return 1
            time.sleep(1)
        logging.info('still exists')

    def send_keys(self, searchKey, attribute):
        """
        Send keys.

        -------------------------
        Parameters
        -------------------------
        searchKey : Any
            The ``searchKey`` parameter.
        attribute : Any
            The ``attribute`` parameter.

        -------------------------
        Returns
        -------------------------
        None
            This method does not return a value.
        """
        if self.d2.exists(resourceId=searchKey):
            self.d2(resourceId=searchKey).send_keys(attribute)
        if self.d2.exists(text=searchKey):
            self.d2(text=searchKey).send_keys(attribute)
