import pytest
import os

if __name__ == '__main__':
    # retry '--reruns=3', '--reruns-delay=3',
    pytest.main(['-v', '-sq', '--html=report_temp.html', 'test/base'])
    # pytest.main(['-v', '-sq', '--html=report_temp.html', 'test/base/test_63_hot_spot_control.py'])
    # os.system("allure generate -c results/ -o allure-report/")
