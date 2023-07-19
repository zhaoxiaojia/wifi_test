import pytest
import os

if __name__ == '__main__':
    pytest.main(['-v', '-sq', '--html=report_temp.html', 'test/base/test_70_hot_spot_blank_passwd.py'])
    # os.system("allure generate -c results/ -o allure-report/")
