import os

import pytest

if __name__ == '__main__':
    # retry '--reruns=3', '--reruns-delay=3',
    pytest.main(['-v', '-s',
                 '--html=report_temp.html', 'test/iptv/test_ctcc_stress.py'])
    # pytest.main(['-v', '-s','--html=report_temp.html', 'test/full/test_check_5g_saved_status.py'])
    # os.system("allure generate -c results/ -o allure-report/")
