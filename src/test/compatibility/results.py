import csv
import json
import os

from src.util.constants import load_config
from src.tools.router_tool.Router import Router


def _iter_compatibility_relays():
    """
    Yield (ip, port) tuples for all configured compatibility relays.
    """
    config = load_config(refresh=True)
    compat = config["compatibility"]
    power_cfg = compat["power_ctrl"]
    relays = power_cfg["relays"]
    for relay in relays:
        ip = str(relay["ip"]).strip()
        for port in relay["ports"]:
            yield ip, int(port)


def _load_router_table():
    """
    Return a mapping (ip, port) -> router definition loaded from
    config/compatibility_router.json.
    """
    path = os.path.join(os.getcwd(), "config", "compatibility_router.json")
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    table = {}
    for entry in data:
        ip = str(entry["ip"]).strip()
        port = int(str(entry["port"]).strip())
        table[(ip, port)] = entry
    return table


def write_compatibility_results(test_results, csv_file: str) -> None:
    """
    Persist compatibility summary rows into a CSV file.

    When test_results is empty, two rows per configured (ip, port) are
    written (for 2.4G and 5G) with the Scan column set to "Error". Router
    brand/model and per-band configuration are taken from
    config/compatibility_router.json when available. Otherwise the collected
    test_results are flattened into rows as before.
    """
    title_row = [
        "PDU IP",
        "PDU Port",
        "AP Brand",
        "Band",
        "Ssid",
        "WiFi Mode",
        "Bandwidth",
        "Security",
        "Scan",
        "Connect",
        "TX Result",
        "Channel",
        "RSSI",
        "TX Criteria",
        "TX Throughtput(Mbps)",
        "RX Result",
        "Channel",
        "RSSI",
        "RX Criteria",
        "RX Throughtput(Mbps)",
    ]

    with open(csv_file, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file, quotechar=" ")
        writer.writerow(title_row)

    if not test_results:
        router_table = _load_router_table()
        bands = ["2.4G", "5G"]
        with open(csv_file, mode="a", newline="", encoding="utf-8") as file:
            writer = csv.writer(file, quotechar=" ")
            for ip, port in _iter_compatibility_relays():
                router_def = router_table.get((ip, port))
                brand_model = ""
                if router_def is not None:
                    brand_model = f"{router_def['brand']} {router_def['model']}"
                for band in bands:
                    mode = ""
                    bandwidth = ""
                    security = ""
                    if router_def is not None and band in router_def:
                        band_cfg = router_def[band]
                        mode = str(band_cfg.get("mode", "")).upper()
                        bandwidth = str(band_cfg.get("bandwidth", ""))
                        security = str(
                            band_cfg.get("security_mode", band_cfg.get("authentication", ""))
                        ).upper()
                    row = [
                        ip,
                        port,
                        brand_model,
                        band,
                        "",
                        mode,
                        bandwidth,
                        security,
                        "Error",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                    ]
                    writer.writerow(row)
        return

    row_data = []
    temp_data = []
    for test_result in test_results:
        test_name = sorted(test_result.keys())[0]
        if test_name in temp_data:
            with open(csv_file, mode="a", newline="", encoding="utf-8") as file:
                writer = csv.writer(file, quotechar=" ")
                writer.writerow(row_data)
            row_data.clear()
            temp_data.clear()
        data = test_result[test_name]
        keys = sorted(data["fixtures"].keys())
        if data["fixtures"][keys[0]][0] not in row_data:
            for name in keys:
                fixture_value = data["fixtures"][name]
                if isinstance(fixture_value, dict):
                    if fixture_value.get("ip") and fixture_value["ip"] not in row_data:
                        row_data.append(fixture_value["ip"])
                    if fixture_value.get("port") and fixture_value["port"] not in row_data:
                        row_data.append(fixture_value["port"])
                    if fixture_value.get("brand"):
                        brand_model = f"{fixture_value['brand']} {fixture_value['model']}"
                        if brand_model not in row_data:
                            row_data.append(brand_model)
                elif isinstance(fixture_value, Router):
                    router_desc = str(fixture_value).replace("default,", "")
                    if router_desc not in row_data:
                        row_data.append(router_desc)
        temp_data.append(test_name)
        # For throughput tests, prefer the explicit comparison result so that
        # the test case itself can pass while still reporting PASS/FAIL.
        compare_result = data.get("compat_compare")
        if compare_result:
            row_data.append(compare_result)
        elif data["result"]:
            row_data.append(data["result"])
        if data["return_value"]:
            row_data.extend([*data["return_value"]])

    with open(csv_file, mode="a", newline="", encoding="utf-8") as file:
        writer = csv.writer(file, quotechar=" ")
        writer.writerow(row_data)
