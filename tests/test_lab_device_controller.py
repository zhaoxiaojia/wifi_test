import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.tools.connect_tool.lab_device_controller import LabDeviceController


def test_execute_rf_cmd_handles_multiple_ports(monkeypatch):
    config = {
        'rf_solution': {
            'model': 'LDA-908V-8',
            'LDA-908V-8': {
                'ports': '1,3-4',
            },
        }
    }
    monkeypatch.setattr(pytest, 'config', config, raising=False)

    calls = []

    def fake_run(self, endpoint, params):
        calls.append((endpoint, dict(params)))
        return 'attn=10'

    monkeypatch.setattr(LabDeviceController, '_run_curl_command', fake_run, raising=False)

    controller = LabDeviceController('192.168.0.1')

    controller.execute_rf_cmd(10)

    setup_calls = [call for call in calls if call[0] == 'setup.cgi']
    assert [call[1]['chnl'] for call in setup_calls] == [1, 3, 4]

    values = controller.get_rf_current_value()

    status_calls = [call for call in calls if call[0] == 'status.shtm']
    assert [call[1]['chnl'] for call in status_calls] == [1, 3, 4]
    assert values == {1: 10, 3: 10, 4: 10}
