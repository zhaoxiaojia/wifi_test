import pytest

import src.test.performance as performance
from src.util.constants import (
    _normalize_config_keys_for_save,
    merge_config_sections,
    split_config_data,
)


@pytest.mark.parametrize('source', [
    {'24g_target_rssi': '-60,-70', '5g_target_rssi': '-65,-75'},
    {'2.4G Target RSSI': '-60,-70', '5G Target RSSI': '-65,-75'},
])
def test_band_rssi_survives_save_reload_and_case_read(monkeypatch, source):
    config = merge_config_sections({}, {'Turntable': source})
    section = config['Turntable']
    assert section.get('24g_target_rssi') == '-60,-70'
    assert section.get('5g_target_rssi') == '-65,-75'

    saved = _normalize_config_keys_for_save(config)
    assert saved['Turntable']['2.4G Target RSSI'] == '-60,-70'
    assert saved['Turntable']['5G Target RSSI'] == '-65,-75'
    assert '24g_target_rssi' not in saved['Turntable']
    assert '5g_target_rssi' not in saved['Turntable']
    _, execution, *_ = split_config_data(saved)
    reloaded = merge_config_sections({}, execution)
    monkeypatch.setattr(performance, 'get_cfg', lambda: reloaded)
    performance.get_rvo_target_rssi_list.cache_clear()
    try:
        assert performance.get_rvo_target_rssi_list('2.4G') == [-60, -70]
        assert performance.get_rvo_target_rssi_list('5G') == [-65, -75]
    finally:
        performance.get_rvo_target_rssi_list.cache_clear()


def test_clearing_ui_rssi_overrides_saved_display_value():
    config = merge_config_sections({}, {'Turntable': {
        '24g_target_rssi': '', '2.4G Target RSSI': '-60',
        '5g_target_rssi': '-75', '5G Target RSSI': '-65',
    }})
    saved = _normalize_config_keys_for_save(config)['Turntable']
    assert saved['2.4G Target RSSI'] == ''
    assert saved['5G Target RSSI'] == '-75'


def test_empty_band_rssi_does_not_use_legacy_shared_value(monkeypatch):
    config = merge_config_sections({}, {'Turntable': {'Target RSSI': '-60'}})
    monkeypatch.setattr(performance, 'get_cfg', lambda: config)
    performance.get_rvo_target_rssi_list.cache_clear()
    try:
        assert performance.get_rvo_target_rssi_list('2.4G') == []
        assert performance.get_rvo_target_rssi_list('5G') == []
    finally:
        performance.get_rvo_target_rssi_list.cache_clear()
