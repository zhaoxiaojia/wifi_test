from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
import csv
from pathlib import Path
from typing import Any, Mapping

import yaml

from src.util.constants import load_config, save_config
from src.ui.model.ai_chat_backend import send_chat_completion
from src.util.constants import get_config_base, get_src_base


@dataclass(frozen=True)
class LlmMappingResult:
    action: str
    updates: dict[str, Any]
    missing: list[str]
    case_id: str | None = None
    confidence: float | None = None
    scenario: dict[str, Any] | None = None
    raw: str | None = None


def _catalog_path() -> Path:
    base = Path(get_src_base()).resolve()
    return base / "ui" / "model" / "ai_catalog.yaml"


def load_ai_catalog() -> dict[str, Any]:
    path = _catalog_path()
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Invalid ai_catalog.yaml root type: {type(data)}")
    return data


def _extract_json_object(text: str) -> str:
    """Best-effort extraction of a JSON object from an LLM response."""
    raw = (text or "").strip()
    if raw.startswith("{") and raw.endswith("}"):
        return raw
    match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
    if not match:
        raise ValueError("LLM did not return a JSON object.")
    return match.group(0)


def _parse_first_json_object(text: str) -> tuple[dict[str, Any], str]:
    """Parse the first JSON object from a response, tolerating trailing text.

    Returns (obj, trailing_text). Raises ValueError on parse failures.
    """
    raw = (text or "").strip()
    start = raw.find("{")
    if start < 0:
        raise ValueError("LLM did not return a JSON object.")
    decoder = json.JSONDecoder()
    obj, end = decoder.raw_decode(raw[start:])
    if not isinstance(obj, dict):
        raise ValueError("LLM JSON is not an object.")
    trailing = raw[start + end :].strip()
    return obj, trailing


def _normalize_update_keys(updates: Mapping[str, Any], key_aliases: Mapping[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for key, value in updates.items():
        alias = key_aliases.get(key, key)
        normalized[str(alias)] = value
    return normalized


def _set_dotted(config: dict[str, Any], dotted_key: str, value: Any) -> None:
    parts = [p for p in str(dotted_key).split(".") if p]
    if not parts:
        raise ValueError("Empty config key.")
    cursor: dict[str, Any] = config
    for part in parts[:-1]:
        next_val = cursor.get(part)
        if not isinstance(next_val, dict):
            next_val = {}
            cursor[part] = next_val
        cursor = next_val
    cursor[parts[-1]] = value


def _validate_updates(catalog: Mapping[str, Any], updates: Mapping[str, Any]) -> tuple[dict[str, Any], list[str]]:
    allowed = set(catalog.get("allowed_update_keys") or [])
    key_aliases = catalog.get("key_aliases") or {}
    normalized = _normalize_update_keys(updates, key_aliases)

    invalid: list[str] = []
    filtered: dict[str, Any] = {}
    for key, value in normalized.items():
        if key not in allowed:
            invalid.append(key)
            continue
        filtered[key] = value
    return filtered, invalid


def _field_specs(catalog: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    specs: dict[str, dict[str, Any]] = {}
    for item in catalog.get("fields") or []:
        if not isinstance(item, dict):
            continue
        key = str(item.get("key") or "").strip()
        if not key:
            continue
        specs[key] = item
    return specs


def _coerce_value(spec: Mapping[str, Any], value: Any) -> Any:
    t = str(spec.get("type") or "string").strip().lower()
    if t in {"string", "str"}:
        return "" if value is None else str(value).strip()
    if t in {"number", "float"}:
        return float(value)
    if t in {"int", "integer"}:
        return int(value)
    if t in {"bool", "boolean"}:
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return bool(value)
    return value


def validate_and_coerce_updates(catalog: Mapping[str, Any], updates: Mapping[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Validate updates against catalog.fields (types/choices)."""
    specs = _field_specs(catalog)
    errors: list[str] = []
    coerced: dict[str, Any] = {}

    def build_choice_map(spec: Mapping[str, Any]) -> dict[str, str]:
        """Build a token->canonical choice mapping (case-insensitive)."""
        mapping: dict[str, str] = {}
        choices = spec.get("choices")
        if not isinstance(choices, list):
            return mapping
        for item in choices:
            if isinstance(item, dict):
                value = str(item.get("value") or "").strip()
                if not value:
                    continue
                mapping[value.lower()] = value
                syns = item.get("synonyms") or []
                if isinstance(syns, list):
                    for syn in syns:
                        syn_str = str(syn).strip()
                        if syn_str:
                            mapping[syn_str.lower()] = value
            else:
                value = str(item).strip()
                if value:
                    mapping[value.lower()] = value
        return mapping

    for key, value in updates.items():
        spec = specs.get(key)
        if spec is None:
            coerced[key] = value
            continue
        try:
            new_val = _coerce_value(spec, value)
        except Exception:
            errors.append(f"{key}: invalid type for {spec.get('type')}")
            continue
        choices = spec.get("choices")
        if isinstance(choices, list) and choices:
            choice_map = build_choice_map(spec)
            lowered = str(new_val).strip().lower()
            if lowered not in choice_map:
                errors.append(f"{key}: must be one of {choices}")
                continue
            new_val = choice_map[lowered]
        coerced[key] = new_val
    return coerced, errors


def _case_id_to_text_case(catalog: Mapping[str, Any], case_id: str | None) -> str | None:
    if not case_id:
        return None
    needle = case_id.strip()
    for item in catalog.get("cases") or []:
        if not isinstance(item, dict):
            continue
        if str(item.get("id") or "").strip() == needle:
            text_case = str(item.get("text_case") or "").strip()
            return text_case or None
    return None


def build_prompt(user_text: str, catalog: Mapping[str, Any], current_config: Mapping[str, Any]) -> str:
    """Build a single-turn prompt that instructs the LLM to output JSON only."""
    catalog_yaml = yaml.safe_dump(catalog, allow_unicode=True, sort_keys=False)
    # Keep the config minimal: only include allowed keys + a few common roots.
    allowed = set(catalog.get("allowed_update_keys") or [])
    snapshot: dict[str, Any] = {}
    for key in allowed:
        if "." in key:
            root = key.split(".", 1)[0]
            if root in current_config and root not in snapshot:
                snapshot[root] = current_config.get(root)
        else:
            if key in current_config:
                snapshot[key] = current_config.get(key)
    snapshot_yaml = yaml.safe_dump(snapshot, allow_unicode=True, sort_keys=False)

    return (
        "You are a YAML configuration mapping engine.\n"
        "Given:\n"
        "1) ai_catalog.yaml (available cases, allowed keys, aliases, field hints)\n"
        "2) current_config.yaml snapshot\n"
        "3) the user's natural language request\n"
        "\n"
        "Task: output ONLY one JSON object with this schema:\n"
        "{\n"
        '  "action": "run" | "unknown",\n'
        '  "case_id": string | null,\n'
        '  "scenario": {\n'
        '    "bands": ["2.4G","5G"] | ["5G"] | ["2.4G"] | null,\n'
        '    "wireless_mode": "11ax" | "11ac" | "11n" | null,\n'
        '    "bandwidth_mhz": 20 | 40 | 80 | 160 | null,\n'
        '    "security_mode": string | null,\n'
        '    "channel": string | null,\n'
        '    "tx": true | false | null,\n'
        '    "rx": true | false | null\n'
        '  } | null,\n'
        '  "updates": { "<yaml_key>": <value>, ... },\n'
        '  "missing": [ "<yaml_key>", ... ],\n'
        '  "confidence": number | null\n'
        "}\n"
        "\n"
        "Rules:\n"
        "- Only output JSON, no markdown.\n"
        "- Only put keys listed in ai_catalog.allowed_update_keys into updates.\n"
        "- You may use ai_catalog.key_aliases (e.g. case_path -> text_case).\n"
        "- Choose case_id when action=run.\n"
        "- Case selection priority: if the user request contains a case synonym verbatim (e.g. 'rvr', 'rvo', 'peak'),\n"
        "  select that case_id accordingly instead of keeping the previous case.\n"
        "- scenario is the extracted Wi-Fi scenario outline from the user's request.\n"
        "  Do NOT try to validate feasibility; the app will do it and may ask the user to уточнить.\n"
        "- Do NOT add defaults. If the user did not mention a YAML key, omit it from updates so the\n"
        "  existing YAML historical value remains unchanged.\n"
        "- If you cannot map confidently, set action=unknown and explain by listing missing keys.\n"
        "\n"
        "ai_catalog.yaml:\n"
        f"{catalog_yaml}\n"
        "\n"
        "current_config.yaml:\n"
        f"{snapshot_yaml}\n"
        "\n"
        "User request:\n"
        f"{user_text}\n"
    )


def map_request_with_llm(model_id: str, user_text: str) -> LlmMappingResult:
    catalog = load_ai_catalog()
    current = load_config(refresh=True) or {}
    prompt = build_prompt(user_text, catalog, current)
    raw = send_chat_completion(model_id, prompt)

    try:
        # Prefer tolerant parsing to avoid "Extra data: line ..." issues.
        data, trailing = _parse_first_json_object(raw)
        if trailing:
            print(f"[AI_DEBUG] LLM response had trailing non-JSON text: {trailing[:200]}")
    except Exception as exc:  # noqa: BLE001
        print(f"[AI_DEBUG] Failed to parse LLM JSON: {exc}")
        print(f"[AI_DEBUG] LLM raw (first 800 chars): {(raw or '')[:800]}")
        # Fallback to legacy extraction to aid debugging.
        payload_text = _extract_json_object(raw)
        print(f"[AI_DEBUG] Extracted JSON candidate (first 800 chars): {payload_text[:800]}")
        data = json.loads(payload_text)

    action = str(data.get("action") or "unknown").strip()
    updates_raw = data.get("updates") or {}
    missing_raw = data.get("missing") or []
    scenario_raw = data.get("scenario")
    if not isinstance(updates_raw, dict):
        raise ValueError("LLM JSON 'updates' must be an object.")
    if not isinstance(missing_raw, list):
        raise ValueError("LLM JSON 'missing' must be a list.")

    updates, invalid = _validate_updates(catalog, updates_raw)
    if invalid:
        logging.warning("LLM proposed invalid update keys: %s", invalid)

    case_id = data.get("case_id")
    case_id = str(case_id).strip() if isinstance(case_id, str) else None

    # Allow the LLM to specify case_id instead of text_case.
    if "text_case" not in updates:
        mapped_text_case = _case_id_to_text_case(catalog, case_id)
        if mapped_text_case:
            updates["text_case"] = mapped_text_case

    scenario: dict[str, Any] | None = None
    if isinstance(scenario_raw, dict):
        scenario = dict(scenario_raw)
    elif scenario_raw is None:
        scenario = None
    else:
        print(f"[AI_DEBUG] Ignoring invalid scenario type: {type(scenario_raw)}")

    # Debug: trace what the model returned to help diagnose misclassification (e.g. rvr -> peak).
    try:
        print("[AI_DEBUG] User request:", (user_text or "").strip())
        print("[AI_DEBUG] LLM action:", action)
        print("[AI_DEBUG] LLM case_id:", case_id)
        print("[AI_DEBUG] LLM updates keys:", sorted(list((updates or {}).keys())))
        print("[AI_DEBUG] LLM text_case:", updates.get("text_case"))
        print("[AI_DEBUG] LLM scenario:", scenario)
        if invalid:
            print("[AI_DEBUG] Dropped invalid update keys:", invalid)
    except Exception as exc:  # noqa: BLE001
        print(f"[AI_DEBUG] Failed to print mapping debug info: {exc}")

    if action == "run" and not case_id and "text_case" not in updates:
        action = "unknown"
        missing_raw = list(missing_raw) + ["case_id"]

    confidence = data.get("confidence")
    try:
        confidence_val = float(confidence) if confidence is not None else None
    except Exception:
        confidence_val = None

    return LlmMappingResult(
        action=action,
        updates=updates,
        missing=[str(x) for x in missing_raw if str(x).strip()],
        case_id=case_id,
        confidence=confidence_val,
        scenario=scenario,
        raw=raw,
    )


def apply_updates_to_config(updates: Mapping[str, Any]) -> dict[str, Any]:
    """Apply validated updates to the model config YAMLs via save_config()."""
    config = load_config(refresh=True) or {}
    merged = dict(config)
    for dotted_key, value in updates.items():
        if "." in str(dotted_key):
            _set_dotted(merged, str(dotted_key), value)
        else:
            merged[str(dotted_key)] = value
    save_config(merged)
    return merged


def looks_like_run_request(text: str) -> bool:
    normalized = re.sub(r"\s+", " ", (text or "").strip()).lower()
    return any(token in normalized for token in ("run", "运行", "跑", "执行", "开始测", "开始测试"))


def derive_performance_csv_updates(
    *,
    current_config: Mapping[str, Any],
    case_id: str | None,
    scenario: Mapping[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Derive CSV updates for performance scenario selection.

    Requirement:
    - Natural language extraction is done by the LLM.
    - This function normalises/validates the extracted scenario and generates a runnable CSV.
    - Write scenario changes into an AI-generated CSV and point config.csv_path to it.
    """
    normalized_scenario = _normalize_llm_scenario(scenario)
    if normalized_scenario is None:
        return {}, {}

    # Apply only when we are running a performance case (selected or current).
    text_case = str(current_config.get("text_case") or "").strip()
    if not _is_performance_case(text_case) and not (case_id or "").startswith("perf_"):
        return {}, {}

    config_base = get_config_base().resolve()

    # Choose a template CSV:
    # - prefer current csv_path if exists
    # - else fallback to rvr_wifi_setup_demo.csv
    # - else fallback to rvr_wifi_setup.csv
    template_csv = _resolve_csv_path(str(current_config.get("csv_path") or ""), config_base)
    if template_csv is None or not template_csv.exists():
        candidate = config_base / "performance_test_csv" / "rvr_wifi_setup_demo.csv"
        template_csv = candidate if candidate.exists() else None
    if template_csv is None or not template_csv.exists():
        template_csv = config_base / "performance_test_csv" / "rvr_wifi_setup.csv"

    out_name = "ai_wifi_scenarios.csv"
    out_path = config_base / "performance_test_csv" / out_name

    details = _write_ai_scenario_csv(template_csv, out_path, normalized_scenario)
    updates = {"csv_path": f"performance_test_csv/{out_name}"}
    return updates, details


def _is_performance_case(text_case: str) -> bool:
    normalized = (text_case or "").replace("\\", "/").strip()
    return normalized.startswith("test/performance/")


def _resolve_csv_path(raw_path: str, config_base: Path) -> Path | None:
    path = Path(str(raw_path or "").strip())
    if not raw_path:
        return None
    return path if path.is_absolute() else (config_base / path)


def _normalize_llm_scenario(scenario: Mapping[str, Any] | None) -> dict[str, Any] | None:
    """Convert LLM-provided scenario object into the internal CSV generator format."""
    if scenario is None or not isinstance(scenario, Mapping):
        return None

    wireless_mode = scenario.get("wireless_mode")
    wireless_mode = str(wireless_mode).strip() if wireless_mode not in (None, "") else None
    if wireless_mode:
        wl = wireless_mode.lower()
        if wl in {"he", "ax", "wifi6", "11ax"}:
            wireless_mode = "11ax"
        elif wl in {"ac", "wifi5", "11ac"}:
            wireless_mode = "11ac"
        elif wl in {"n", "11n"}:
            wireless_mode = "11n"

    bw = scenario.get("bandwidth_mhz")
    bandwidth_mhz: int | None = None
    try:
        if bw not in (None, ""):
            bandwidth_mhz = int(bw)
    except Exception:
        bandwidth_mhz = None

    bands_raw = scenario.get("bands")
    bands: list[str] | None = None
    if isinstance(bands_raw, list):
        cleaned: list[str] = []
        for b in bands_raw:
            b_str = str(b).strip()
            if not b_str:
                continue
            if b_str.lower() in {"5g", "5ghz"}:
                cleaned.append("5G")
            elif b_str.lower() in {"2.4g", "2g", "2.4ghz"}:
                cleaned.append("2.4G")
        if cleaned:
            seen: set[str] = set()
            bands = []
            for b in cleaned:
                if b not in seen:
                    seen.add(b)
                    bands.append(b)

    security_mode = scenario.get("security_mode")
    security_mode = str(security_mode).strip() if security_mode not in (None, "") else None
    channel = scenario.get("channel")
    channel = str(channel).strip() if channel not in (None, "") else None
    tx = scenario.get("tx")
    rx = scenario.get("rx")

    if not any([wireless_mode, bandwidth_mhz, bands, security_mode, channel, tx, rx]):
        return None

    normalized: dict[str, Any] = {"bands": bands}
    if wireless_mode:
        normalized["wireless_mode"] = wireless_mode
    if bandwidth_mhz:
        normalized["bandwidth"] = f"{bandwidth_mhz} MHz"
    if security_mode:
        normalized["security_mode"] = security_mode
    if channel:
        normalized["channel"] = channel
    if tx in (True, False):
        normalized["tx"] = bool(tx)
    if rx in (True, False):
        normalized["rx"] = bool(rx)
    return normalized


def _build_capability_matrix_from_csv(csv_path: Path) -> dict[str, dict[str, set[str]]]:
    """Return capabilities as {band: {field: {values}}} from a CSV file."""
    header, rows = _read_csv(csv_path)
    band_idx = _get_idx(header, "band")
    mode_idx = _get_idx(header, "wireless_mode")
    bw_idx = _get_idx(header, "bandwidth")
    sec_idx = _get_idx(header, "security_mode")
    caps: dict[str, dict[str, set[str]]] = {}
    for row in rows:
        band = row[band_idx].strip() or "unknown"
        entry = caps.setdefault(band, {})
        entry.setdefault("wireless_mode", set()).add(row[mode_idx].strip())
        entry.setdefault("bandwidth", set()).add(row[bw_idx].strip())
        entry.setdefault("security_mode", set()).add(row[sec_idx].strip())
    return caps


def _choose_feasible_bands(
    *,
    caps: dict[str, dict[str, set[str]]],
    requested_bands: list[str] | None,
    wireless_mode: str | None,
    bandwidth: str | None,
) -> tuple[list[str], list[str]]:
    """Choose feasible bands and return (bands, issues)."""
    issues: list[str] = []
    all_bands = sorted(caps.keys(), key=lambda x: (x != "5G", x))
    candidates = requested_bands[:] if requested_bands else all_bands

    def ok(band: str) -> bool:
        entry = caps.get(band) or {}
        if wireless_mode and wireless_mode not in (entry.get("wireless_mode") or set()):
            return False
        if bandwidth and bandwidth not in (entry.get("bandwidth") or set()):
            return False
        return True

    feasible = [b for b in candidates if ok(b)]
    if requested_bands:
        if not feasible:
            issues.append(
                "Requested band(s) do not support the requested scenario; please refine."
            )
        return feasible, issues

    # Band unspecified: prefer all feasible bands, but do not include bands
    # that cannot satisfy the requested bandwidth/mode.
    if bandwidth or wireless_mode:
        if not feasible:
            issues.append("No band supports the requested Wi‑Fi settings.")
            return [], issues
        if len(feasible) < len(candidates):
            missing = [b for b in candidates if b not in feasible]
            issues.append(
                f"Some bands do not support the requested settings and will be excluded: {', '.join(missing)}"
            )
        return feasible, issues

    # Nothing constrained: keep all bands.
    return candidates, issues


def _read_csv(path: Path) -> tuple[list[str], list[list[str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        rows = [r for r in reader if r]
    if not rows:
        raise ValueError(f"CSV is empty: {path}")
    header = [h.strip() for h in rows[0]]
    data = [[c.strip() for c in row] for row in rows[1:]]
    return header, data


def _write_csv(path: Path, header: list[str], rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)


def _get_idx(header: list[str], name: str) -> int:
    lowered = [h.strip().lower() for h in header]
    try:
        return lowered.index(name.strip().lower())
    except ValueError as exc:
        raise ValueError(f"CSV missing column: {name}") from exc


def _default_ssid_for_band(config_base: Path, band: str) -> str | None:
    ref = config_base / "performance_test_csv" / "rvr_wifi_setup.csv"
    if not ref.exists():
        return None
    header, rows = _read_csv(ref)
    band_idx = _get_idx(header, "band")
    ssid_idx = _get_idx(header, "ssid")
    for row in rows:
        if row[band_idx].strip().lower() == band.lower():
            ssid = row[ssid_idx].strip()
            if ssid:
                return ssid
    return None


def _write_ai_scenario_csv(template_csv: Path, out_csv: Path, scenario: Mapping[str, Any]) -> dict[str, Any]:
    header, rows = _read_csv(template_csv)
    if not rows:
        raise ValueError(f"Template CSV has no data rows: {template_csv}")

    config_base = get_config_base().resolve()
    band_idx = _get_idx(header, "band")
    ssid_idx = _get_idx(header, "ssid")
    mode_idx = _get_idx(header, "wireless_mode")
    bw_idx = _get_idx(header, "bandwidth")
    tx_idx = _get_idx(header, "tx")
    rx_idx = _get_idx(header, "rx")

    base_row = rows[0]
    requested_bands = scenario.get("bands")
    requested_bands = list(requested_bands) if isinstance(requested_bands, list) else None
    wireless_mode_req = str(scenario.get("wireless_mode") or "").strip() or None
    bandwidth_req = str(scenario.get("bandwidth") or "").strip() or None

    caps_ref = config_base / "performance_test_csv" / "rvr_wifi_setup.csv"
    caps_source = caps_ref if caps_ref.exists() else template_csv
    caps = _build_capability_matrix_from_csv(caps_source)
    bands, issues = _choose_feasible_bands(
        caps=caps,
        requested_bands=requested_bands,
        wireless_mode=wireless_mode_req,
        bandwidth=bandwidth_req,
    )
    if not bands:
        raise ValueError(
            "No feasible band found for the requested Wi‑Fi settings. "
            "Please specify a supported band or adjust bandwidth."
        )
    out_rows: list[list[str]] = []

    for band in bands:
        row = list(base_row)
        row[band_idx] = str(band)
        ssid = _default_ssid_for_band(config_base, str(band))
        if ssid:
            row[ssid_idx] = ssid
        if "wireless_mode" in scenario:
            row[mode_idx] = str(scenario["wireless_mode"])
        if "bandwidth" in scenario:
            row[bw_idx] = str(scenario["bandwidth"])
        row[tx_idx] = "1"
        row[rx_idx] = "1"
        out_rows.append(row)

    _write_csv(out_csv, header, out_rows)
    return {
        "template_csv": str(template_csv),
        "generated_csv": str(out_csv),
        "rows": len(out_rows),
        "scenario": dict(scenario),
        "selected_bands": bands,
        "issues": issues,
    }


def _detect_mentioned_keys(
    catalog: Mapping[str, Any],
    user_text: str,
    *,
    case_id: str | None,
) -> set[str]:
    """Detect which YAML keys are explicitly mentioned in the request.

    This is a heuristic-based guardrail: if the model proposes updates for keys
    that are not mentioned, they are dropped so historical YAML values remain.
    """
    text = (user_text or "").lower()
    mentioned: set[str] = set()

    def is_negated(token: str) -> bool:
        token_re = re.escape(token)
        # Chinese: "不/不要/别/无需/不用/不需要" within a short window before the token.
        if re.search(rf"(不|不要|别|无需|不用|不需要).{{0,4}}{token_re}", text):
            return True
        # Chinese: "默认/保持/历史" indicates no explicit change requested.
        if re.search(rf"(默认|保持|历史).{{0,4}}{token_re}", text) or re.search(
            rf"{token_re}.{{0,4}}(默认|保持|历史)", text
        ):
            return True
        # English: simple "don't/do not/no need/without" patterns.
        if re.search(rf"(don't|do not|no need|without).{{0,8}}{token_re}", text):
            return True
        # English: "keep/default" near token.
        if re.search(rf"(keep|default).{{0,8}}{token_re}", text) or re.search(
            rf"{token_re}.{{0,8}}(keep|default)", text
        ):
            return True
        return False

    # Field-level mentions: match on key name and configured synonyms.
    for item in catalog.get("fields") or []:
        if not isinstance(item, dict):
            continue
        key = str(item.get("key") or "").strip()
        if not key:
            continue
        tokens = {key.lower()}
        for syn in item.get("synonyms") or []:
            syn_str = str(syn).strip().lower()
            if syn_str:
                tokens.add(syn_str)
        positive_match = any(tok and tok in text and not is_negated(tok) for tok in tokens)
        if positive_match:
            mentioned.add(key)

    # Case mention: if the user referenced a known case by synonym (or the LLM selected case_id),
    # treat text_case as explicitly intended.
    for case in catalog.get("cases") or []:
        if not isinstance(case, dict):
            continue
        cid = str(case.get("id") or "").strip()
        if not cid:
            continue
        if case_id and cid == case_id:
            mentioned.add("text_case")
            break
        tokens = {cid.lower()}
        for syn in case.get("synonyms") or []:
            syn_str = str(syn).strip().lower()
            if syn_str:
                tokens.add(syn_str)
        if any(tok and tok in text for tok in tokens):
            mentioned.add("text_case")
            break

    return mentioned
