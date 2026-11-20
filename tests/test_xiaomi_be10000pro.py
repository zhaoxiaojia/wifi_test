import pytest
from PyQt5.QtWidgets import QApplication

from src.tools.router_tool.Router import Router
from src.tools.router_tool.RouterControl import ConfigError
from src.tools.router_tool.router_factory import get_router
from src.ui.view import RouterConfigForm


MODEL = "Xiaomi BE 10000 Pro"


@pytest.mark.parametrize("band,form", [
    ("2.4G", "wifiset24"), ("5G", "wifiset50"), ("5G Game", "wifiset5g2"),
])
def test_radio_mapping(band, form):
    control = get_router(MODEL)
    assert control.RADIOS[band] == form
    assert control._changes(Router(band=band), {}) == {}


def test_game_channel_uses_firmware_choices():
    control = get_router(MODEL)
    choices = {"channel": ["0", "36", "40"], "bandwidth": ["0", "20", "40", "80"]}
    assert control._changes(Router(band="5G Game", channel=40, bandwidth="80 MHz"),
                            choices) == {"channel": "40", "bandwidth": "80"}
    with pytest.raises(ConfigError):
        control._changes(Router(band="5G Game", channel=149), choices)
    with pytest.raises(ConfigError):
        control._changes(Router(band="5G Game", wireless_mode="11be"), choices)


@pytest.fixture(scope="module")
def qt_app():
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("QT_QPA_PLATFORM", "offscreen")
        yield QApplication.instance() or QApplication([])


@pytest.mark.parametrize("model", ["Xiaomi AX3600", "Xiaomi AX7000", "ASUS-AX86U"])
def test_form_round_trip(model, qt_app):
    dual = get_router(model)
    form = RouterConfigForm(dual)
    def items(box):
        return [box.itemText(i) for i in range(box.count())]
    assert items(form.band_combo) == ["2.4G", "5G"]
    form.band_combo.setCurrentText("5G")
    form.set_router(get_router(MODEL))
    assert items(form.band_combo) == ["2.4G", "5G", "5G Game"]
    assert form.band_combo.currentText() == "5G"
    combos = (form.wireless_combo, form.channel_combo, form.bandwidth_combo)
    options = [items(box) for box in combos]
    form.load_row({"band": "5G Game"})
    assert form.current_row_data()["band"] == "5G Game"
    assert items(form.channel_combo) == ["auto", "36", "40", "44", "48", "52", "56", "60", "64"]
    assert items(form.wireless_combo) == options[0]
    assert items(form.bandwidth_combo) == options[2]
    form.band_combo.setCurrentText("5G")
    assert items(form.channel_combo) == options[1]
    form.band_combo.setCurrentText("5G Game")
    form.set_router(dual)
    form.load_row({"band": "5G Game"})
    assert items(form.band_combo) == ["2.4G", "5G"]
    assert form.band_combo.currentText() == "2.4G"
    assert items(form.channel_combo) == list(dual.CHANNEL_2)
    form.close()

def test_failed_save_preserves_non_target_payload(monkeypatch):
    from unittest.mock import MagicMock

    control = get_router(MODEL)
    control.driver = MagicMock()
    monkeypatch.setattr(control, "login", lambda: None)
    state = {}
    for index, radio in enumerate(control.RADIOS.values(), 1):
        state[radio] = {
            "fields": {"on": "1", "ssid": f"radio{index}", "encryption": "none",
                       "channel": "36", "bandwidth": "80", "hidden": "0",
                       "txpwr": "max", "pwd": ""},
            "choices": {},
        }
    monkeypatch.setattr(control, "_settings", lambda: state)
    control.driver.execute_async_script.return_value = 1
    with pytest.raises(ConfigError):
        control.change_setting(Router(band="5G Game", ssid="changed"))
    payload = control.driver.execute_async_script.call_args.args[1]
    for index, radio in enumerate(control.RADIOS.values(), 1):
        for name, original in state[radio]["fields"].items():
            expected = "changed" if index == 3 and name == "ssid" else original
            assert payload[f"{name}{index}"] == expected
    control.driver.refresh.assert_not_called()
    control.driver.quit.assert_called_once()

def test_be_frontend_only_offers_supported_settings(qt_app):
    control = get_router(MODEL)
    form = RouterConfigForm(control)
    for band in control.BAND_LIST:
        form.band_combo.setCurrentText(band)
        assert [form.wireless_combo.itemText(i) for i in range(form.wireless_combo.count())] == (['auto', '11n', '11ax'] if band == '2.4G' else ['auto', '11ac', '11ax'])
        control._changes(Router(**{k:v for k,v in form.current_row_data().items() if k in Router._fields}), {})
    form.band_combo.setCurrentText('5G')
    assert [form.channel_combo.itemText(i) for i in range(form.channel_combo.count())] == ['auto','149','153','157','161','165']
    form.close()

def test_form_can_clear_router(qt_app):
    form = RouterConfigForm(get_router(MODEL))
    form.set_router(None)
    assert form.band_combo.count() == 0
    assert form.wireless_combo.count() == 0
    form.close()


@pytest.mark.parametrize("mode,before,after,ax", [("11ac", "0", "1", "0"), ("11ax", "1", "0", "1")])
def test_global_compatibility_mode_is_saved_even_without_radio_changes(monkeypatch, mode, before, after, ax):
    from unittest.mock import MagicMock
    control = get_router(MODEL)
    control.driver = MagicMock()
    monkeypatch.setattr(control, "login", lambda: None)
    state = {radio: {"fields": {"on": "1", "ssid": radio, "encryption": "none",
             "channel": "36", "bandwidth": "80", "hidden": "0", "txpwr": "max", "pwd": ""},
             "choices": {}} for radio in control.RADIOS.values()}
    monkeypatch.setattr(control, "_settings", lambda: state)
    control.driver.execute_script.side_effect = [before, after]
    control.driver.execute_async_script.return_value = 0
    assert control.change_setting(Router(band="5G Game", wireless_mode=mode)) is True
    assert control.driver.execute_async_script.call_count == 1
    script, payload = control.driver.execute_async_script.call_args.args
    assert "set_wifi_ax" in script
    assert payload == {"ax": ax, "isDFS": 0}
    control.driver.refresh.assert_called()
    control.driver.quit.assert_called_once()
