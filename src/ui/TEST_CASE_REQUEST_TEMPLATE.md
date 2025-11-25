# Test Case Development Request Template

This document is a **template** for describing new Wi‑Fi test case
requirements. It is designed to match the MVC flow explained in
`src/ui/README.md` (especially sections 2 and 6).  When you request a new
test case, copy this template and fill in the sections.

> Tip: keep code identifiers / log messages in English as required by
> `README.md`; you can describe requirements in Chinese if you prefer.

---

## A. Basic information

1. **Test name / purpose**
   - e.g. “5G peak throughput”, “RVR with special RF profile”.
2. **Test type**
   - One of: `PERFORMANCE`, `RVR`, `RVO`, `STABILITY`, `OTHER`.
3. **Pytest module path**
   - Target file under `src/test/...`, e.g.
     `src/test/performance/test_wifi_<name>.py`.
4. **Expected input source**
   - `YAML only` (Performance/DUT/Stability panels), or  
   - `YAML + CSV` (per‑scenario rows, like RvR), or  
   - other (describe).

---

## B. Performance page requirements (Config → Performance panel)

This corresponds to the Performance panel described in `README.md` §2.1–2.3.

1. **Selected Test Case**
   - Default `text_case` value (relative to `src/test`, e.g.
     `test/performance/test_wifi_<name>.py`).  
   - Does this case need any special validation before running?
2. **New or changed fields in `config_performance.yaml`**
   - For each field:
     - YAML key (e.g. `rvr.repeat`, `rf_solution.step`).
     - Widget type (`line_edit`, `combo_box`, `checkbox`, `spin`, etc.).
     - Default value.
     - Options source:
       - Static list, or
       - From `options.py` (specify helper), or
       - New dynamic rule (describe).
3. **Rule behaviour**
   - When should these fields be enabled/disabled/visible?
   - Do any fields depend on the selected `text_case` or `test type`?
   - Any auto‑fill logic (e.g. when X changes, Y is recomputed)?

---

## C. Case page requirements (RvrWifiConfigPage or new page)

This corresponds to `README.md` §6.1–6.2.

1. **Does this test reuse the existing RvR Wi‑Fi CSV schema?**
   - If **yes**:
     - CSV path pattern under `config/performance_test_csv/` (e.g.
       `rvr_wifi_setup_<router>.csv`).
     - Which columns are actually used by the test (band, ssid,
       wireless_mode, channel, bandwidth, security_mode, password, tx, rx).
   - If **no**:
     - Describe the CSV columns and their meaning.
     - For each column, indicate:
       - Data type (string / int / choice).
       - Whether it should be editable in the Case page.
2. **Case page UI behaviour**
   - Should we **reuse `RvrWifiConfigPage`** (form + table) with minimal
     tweaks, or design a **new Case page view**?
   - When the user selects a row:
     - What fields should be shown in the form?
     - How should edits sync back to the table / CSV?
   - Any special validation or constraints (e.g. at least one of `tx`/`rx`
     must be enabled)?
3. **When to show the Case page**
   - Which `text_case` values should enable this Case page?
   - If multiple test modules share the same Case UI, list all of them.

---

## D. Test logic and data mapping (pytest side)

This helps connect YAML/CSV fields to the pytest implementation.

1. **Per‑row parameters**
   - For each CSV column or YAML field, specify how the test uses it:
     - e.g. `band` → router band, `ssid` → Wi‑Fi SSID, `tx`/`rx` →
       throughput direction flags, etc.
2. **RF / turntable behaviour**
   - Which config keys control RF steps / corner rotation
     (e.g. `rf_solution.step`, `Turntable.Step`)?
   - Does this test follow the existing `get_rf_step_list()` /
     `get_corner_step_list()` conventions, or need a new pattern?
3. **Repeat / profiling requirements**
   - Should this test support `rvr.repeat`‑style extra throughput columns
     (handled in `TestResult`), or is one run per point enough?
4. **Expected reporting classification**
   - How should this test be tagged in `pytest.selected_test_types`?
     (`PERFORMANCE`, `RVR`, `RVO`, etc.).
   - Does it contribute to the project report (`project_report.py`)?  If
     yes, specify how its CSV output should look.

---

## E. Miscellaneous

1. **Constraints / assumptions**
   - e.g. specific router models, DUT OS type, lab devices.
2. **Priority and scope**
   - Must‑have vs nice‑to‑have, minimal viable version, future extensions.
3. **Anything else Codex should know**
   - Links to existing tests with similar behaviour.
   - Known pitfalls from previous versions.
