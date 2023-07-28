import pytest
import os

if __name__ == '__main__':
    # retry '--reruns=3', '--reruns-delay=3',
    pytest.main(['-v', '-s', '--reruns=3', '--reruns-delay=3',
                 '--html=report_temp.html', 'test/base/test_15_connect_open.py'])
    # pytest.main(['-v', '-s','--html=report_temp.html', 'test/full/test_check_5g_saved_status.py'])
    # os.system("allure generate -c results/ -o allure-report/")
