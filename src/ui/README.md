# UI Architecture and Config Flow (MVC + Rules)

All new UI work under `src/ui` must follow the **Model / View / Controller**
structure described here. Before you touch any UI code, **read this file
first**.

Goals:

- Keep data description (Model), widgets/layout (View), and behaviour/I/O
  (Controller) clearly separated.
- Drive as much UI behaviour as possible from **YAML + rules**, not ad‑hoc
  Python in the view layer.
- Make signal/slot wiring predictable so future changes are easy to reason
  about.

---

## 1. Layers and Responsibilities

### 1.1 Model

- Location: `src/ui/model/`
- Purpose: describe *what* can be configured and how fields are grouped.
- Typical files:
  - `config_basic.yaml`, `config_performance.yaml`, `config_stability.yaml`
    (persisted config values)
  - `config_basic_ui.yaml`, `config_performance_ui.yaml`, `config_stability_ui.yaml`
    (UI schema: panels/sections/fields)
  - `options.py` (dynamic choice lists for comboboxes)
  - `rules.py` (declarative UI rules and helpers)

Model modules must not contain any Qt widget or layout code. They are pure
data and rule definitions.

### 1.2 View

- Location: `src/ui/view/`
- Purpose: build widgets, layouts, and visual effects. No business logic, no
  I/O, no direct pytest calls.
- Important modules for the Config page:
  - `view/config/page.py` – `ConfigView`, `CaseConfigPage`
  - `view/builder.py` – schema‑driven widget builder
  - `view/config/actions.py` – wiring helpers and complex view glue
  - `view/common.py` – shared widgets (`EditableInfo`, `RfStepSegmentsWidget`, etc.).

Other pages (`account.py`, `run.py`, `case.py`, `report.py`, `about.py`,
`main_window.py`) follow the same pattern: the view owns geometry and
appearance only.

Views must not:

- Read or write config files.
- Talk to routers, databases, pytest, or other external tools.
- Perform heavy computation or spawn workers directly.

### 1.3 Controller

- Location: `src/ui/controller/`
- Purpose: own non‑trivial behaviour and I/O for each page.
- Important modules:
  - `controller/config_ctl.py` – Config lifecycle, case tree, stability helpers.
  - `controller/case_ctl.py` – RvR Wi‑Fi CSV helpers and switch‑Wi‑Fi plumbing.
  - `controller/run_ctl.py` – pytest orchestration and logging.
  - `controller/report_ctl.py` – report discovery and plotting.
  - `controller/account_ctl.py`, `controller/about_ctl.py` – login/about.

Controllers operate on view instances passed from the caller. They may:

- Load and save YAML/JSON/CSV/log files.
- Call pytest or router tools.
- Connect view signals to controller slots.
- Push data back into the view via its public API.

Controllers must not create their own ad‑hoc layouts or windows.

---

## 2. Config Page End‑to‑End Flow

This section describes the **exact pipeline** for the Config page (Basic,
Performance, Stability) from YAML to widgets to rule‑driven behaviour.

### 2.1 Config YAML (values)

Persisted configuration is stored under `src/ui/model/config/`:

- `config_basic.yaml`
- `config_performance.yaml`
- `config_stability.yaml`
- `config_tool.yaml`

Loading and saving is handled by helpers in `src/ui/__init__.py` and
`ConfigController`:

- `ConfigController.load_initial_config()`
  - Calls `load_page_config(page)` to populate `page.config`.
  - Normalises sections (connect_type / project / stability).
- `ConfigController.save_config()`
  - Collects current values from the view (`sync_widgets_to_config`) and
    writes YAML back to disk.

### 2.2 UI schema YAML (layout)

The *structure* of the Config page is described in:

- `config_basic_ui.yaml`
- `config_performance_ui.yaml`
- `config_stability_ui.yaml`

Each schema file defines panels and sections:

- `panels.basic.sections[].fields[]`
- `panels.execution.sections[].fields[]`
- `panels.stability.sections[].fields[]`

Fields specify:

- `key`: dotted config key (e.g. `connect_type.type`).
- `widget`: widget type (`line_edit`, `combo_box`, `checkbox`, `spin`, `custom`).
- `label`: user‑visible label.
- `placeholder`, `minimum`, `maximum`, `choices`: extra hints.

The **schema never contains Qt code**. It only describes layout and field
metadata.

### 2.3 Builder (schema → widgets)

The builder in `src/ui/view/builder.py` is the only place that turns schema
into widgets:

- `load_ui_schema(section: str)` chooses the appropriate UI schema file.
- `build_groups_from_schema(page, config, ui_schema, panel_key, parent)`:
  - For each section:
    - Creates a `QGroupBox` and `QFormLayout`.
    - For each field, creates the appropriate widget (`LineEdit`, `ComboBox`,
      `QCheckBox`, `QSpinBox`, `SwitchWifiConfigPage`, etc.).
    - Uses `get_field_choices(field_key)` from `options.py` when the schema
      does not specify static `choices`.
    - Populates initial widget values from `config`.
    - Registers widgets into `page.field_widgets[key]` for later use.

### 2.4 Options (dynamic choices)

`src/ui/model/options.py` centralises combobox choices and complex option
sources. The builder or rules use:

- `get_field_choices(field_key)` – return choices for a given `field_key`.
- Helper functions for project/customer/product lines, RF models, etc.

If a field’s choices depend on other config values, put that logic here.

### 2.5 Rules (behaviour)

`src/ui/model/rules.py` contains the rule engine:

- `CUSTOM_SIMPLE_UI_RULES` – declarative rules for enabling/disabling/
  hiding fields, setting values, etc.
- `compute_editable_info(page, case_path) -> EditableInfo` – computes which
  sections/fields are editable for a given `text_case`.
- `evaluate_all_rules(page, controller)` – recompute derived UI state after
  field changes.

Rules operate on generic *field adapters* (see `view/common.py`) rather
than raw Qt widgets, so they are easy to test and extend.

### 2.6 Actions (signal wiring)

`src/ui/view/config/actions.py` is where widgets are connected to the
controller and rule engine. Typical responsibilities:

- Bind field change signals (`toggled`, `currentIndexChanged`, etc.) to
  `handle_config_event(page, event, **payload)`.
- Use `autosave_config` (see `src/ui/model/autosave.py`) to auto‑save YAML
  when certain events occur (`field_changed`, `csv_index_changed`, etc.).
- Apply rule evaluation after relevant events.

In summary, **actions.py wires Qt signals to controllers and to
`evaluate_all_rules`**, and hosts complex view‑only behaviour that is hard
to express as a simple field rule.

### 2.7 Controller interaction

`ConfigController` (`src/ui/controller/config_ctl.py`) uses the rule model
and view wiring as follows:

- `get_editable_fields(case_path) -> EditableInfo`:
  - Calls `compute_editable_info(self.page, case_path)` from `rules.py`.
  - Applies the result to internal flags and to the view.
- `apply_editable_info(info)`:
  - Stores the snapshot on the page, then calls `evaluate_all_rules` so that
    rule‑based enable/disable respects the new editable set.

The controller never pokes individual widget attributes directly; it passes
through the rule + adapter layers.

---

## 3. Typical Development Workflow (Config Page)

When you add or change behaviour on the Config page, follow this order:

1. **Update model / schema**  
   - Add fields to `config_*_ui.yaml` under `src/ui/model/config/`.  
   - If needed, extend `options.py` to provide dynamic `choices` lists.
2. **Let the builder create widgets**  
   - Ensure `refresh_config_page_controls` calls
     `build_groups_from_schema` for the relevant panel.
   - Access widgets via `page.field_widgets["section.key"]` if necessary.
3. **Describe behaviour in rules**  
   - Prefer `CUSTOM_SIMPLE_UI_RULES` with `SimpleRuleSpec` for
     show/hide/enable/disable/set_value/set_options behaviour.
   - For case‑type behaviour (performance / stability / RvR / RvO), extend
     `CUSTOM_SIMPLE_UI_RULES` or adjust `evaluate_all_rules` as needed.
4. **Wire signals, not logic, in actions**  
   - Use `handle_config_event` and the `_bind_*_actions` helpers to connect
     widgets to controller methods and to `evaluate_all_rules`.
   - Avoid adding new `if/else` chains in actions for simple attribute
     changes; push those into `rules.py` instead.
5. **Keep controllers focused on I/O and orchestration**  
   - Let controllers call `compute_editable_info`, `evaluate_all_rules`,
     and view helpers instead of mutating widgets directly.

---

## 4. Coding Style and Constraints

These rules apply to all new code in `src/ui`:

### 4.1 Language

- **Do not use Chinese** in identifiers, comments, or log messages.
- User‑visible strings must be English or loaded from a dedicated resource
  layer (if added in the future).

### 4.2 Layering and Encapsulation

- Respect MVC boundaries:
  - Model: configuration, options, rules; no Qt.
  - View: widgets/layout/animations; minimal logic; no heavy I/O.
  - Controller: I/O, long‑running work, orchestration.
- When you encapsulate logic, decide clearly:
  - Which layer it belongs to.
  - Which modules are allowed to call it.
- Do not bypass the layering by reaching into deep controller internals from
  random modules. Expose small, explicit methods instead.

### 4.3 Defensive Programming

Avoid “defensive by default” patterns that make code hard to follow:

- Do **not** wrap large blocks in broad `try/except Exception` just to
  silence errors. Catch specific exceptions and log them.
- Avoid `getattr(obj, "attr", None)` as the default way to discover state.
  Prefer explicit attributes and type hints.
- Do not chain `hasattr`/`getattr` to probe behaviour that a layer should
  not even know about. Refactor the API instead.

Small, targeted `try/except` blocks or `contextlib.suppress` are acceptable
for shutdown/cleanup paths where failures are expected and harmless.

### 4.4 General Style

- Keep controller methods focused and testable; split when responsibilities
  grow too large.
- Use explicit names for pages and views (`RunView`, `RunPage`,
  `RvrWifiConfigPage`, `ReportView`, etc.).
- Reuse helpers from `view/common.py`, `rules.py`, and controllers instead
  of copying logic.
- Keep logging messages short, English, and relevant.

---

## 5. Checklist Before Coding

For any new UI work, follow this checklist **in order**:

1. Read this `src/ui/README.md` to refresh the architecture and config flow.
2. Decide which layer(s) your change touches: Model, View, Controller.
3. Update or add YAML / model entries if needed.
4. Extend or create view modules under `src/ui/view/`.
5. Add or update controller modules under `src/ui/controller/`.
6. Use the builder and rule engine instead of hand‑crafting widgets or
   enable/disable logic.
7. Wire the page/controller into `main.py` only at the top level.
8. Re‑check that no new defensive patterns (broad `try/except`,
   heavy `getattr`, etc.) were introduced.

Following this process keeps the UI predictable and maintainable as the
application grows.

---

## 6. Developing New Test Cases (end‑to‑end)

This section explains how a *pytest test module* fits into the MVC
architecture and which pieces you normally touch when adding a new case.

### 6.1 High‑level data flow

For performance / RVR / RVO style tests the pipeline is:

1. **Performance config YAML** (`src/ui/model/config/config_performance.yaml`)
   - Stores `text_case` (test module path) and `csv_path` (per‑scenario CSV).
2. **Config Performance panel** (View + Controller + Rules)
   - `config_performance_ui.yaml` describes the “Selected Test Case”, RF
     Solution, RVR section, etc.
   - `ConfigController` loads/saves `config_performance.yaml` and auto‑saves
     on every field change (see `autosave.py` and the bindings in
     `view/config/actions.py`).
3. **Case page** (RVR Wi‑Fi CSV editor)
   - `RvrWifiConfigPage` renders the CSV rows as a form + table and keeps
     its internal `rows` list in sync with the table; any change in the
     form updates the table and writes back to CSV.
   - `case_ctl.py` keeps `csv_path` in sync between Config and Case pages
     and exposes helpers for other CSV‑driven case UIs.
4. **Run page / pytest**
   - `RunController` reads the latest config (including `text_case` and
     `csv_path`), builds a pytest command line and spawns a worker process.
   - The test module (`src/test/...`) imports `load_config()` or
     `get_testdata()` to read YAML/CSV and execute the real test steps.

### 6.2 Steps for a new performance / RVR‑like test

When you add a new test that follows the same pattern (Config → optional
CSV → pytest), use this checklist:

1. **Create the pytest module**
   - Place it under `src/test/performance/` or `src/test/stability/`.
   - Reuse helpers from `src/test/performance/__init__.py` where possible
     (`init_router`, `init_rf`, `scenario_group`, `wait_connect`, etc.).
   - If the test is CSV‑driven, either:
     - reuse the `Router` namedtuple + `get_testdata()` (same CSV schema as
       RvR), or
     - implement a dedicated CSV loader in the test package.
2. **Expose the test from Performance config**
   - In `config_performance.yaml`, set a default for `text_case` (e.g.
     `test/performance/test_wifi_<name>.py` relative to `src/test`).
   - The “Selected Test Case” group in `config_performance_ui.yaml` already
     maps to `text_case`, so the file‑dialog selection and auto‑save logic
     will just work.
3. **Decide whether the Case page needs content**
   - If the test uses the **same CSV schema** as RvR, reuse
     `RvrWifiConfigPage`:
     - `ConfigController._apply_editable_ui_state` calls
       `set_case_content_visible(enable_rvr_wifi)` so that the RvR Wi‑Fi
       page is only shown for cases that enable this feature via rules.
     - In `rules.py` / `CUSTOM_SIMPLE_UI_RULES`, set
       `enable_rvr_wifi=True` for the relevant `text_case` values.
   - If the test needs a *different* per‑scenario editor:
     - Create a new view under `src/ui/view/` (similar to
       `RvrWifiConfigPage`) and keep it UI‑only.
     - Add a small controller helper in `case_ctl.py` if you reuse CSV
       discovery or combo synchronisation.
     - Extend `MainWindow` to host the new Case page and expose a
       `set_case_content_visible(...)` method on it.
     - In `ConfigController._apply_editable_ui_state`, call the new Case
       page when rules indicate that this test type is active.
4. **Wire autosave / config usage**
   - For Performance / DUT / Stability panels, continue to rely on the
     central autosave decorator in `src/ui/model/autosave.py` instead of
     hand‑calling `save_config` from random slots.
   - For CSV‑driven Case pages, keep auto‑save inside the page:
     - Update the in‑memory `rows` list when widgets change.
     - Write back to CSV through a single helper (like
       `RvrWifiConfigPage._save_csv()`).
   - In the pytest module, read only from YAML/CSV (never from Qt widgets)
     so tests stay decoupled from the UI.
5. **Classify the test for reporting**
   - If the new case should be treated as RVR/RVO/PERFORMANCE in reports,
     update the detection logic in `src/conftest.py` (see
     `pytest_collection_finish`) so that `pytest.selected_test_types`
     contains the correct labels.
   - For project‑style reports, ensure the test’s CSV layout matches the
     expectations of `src/tools/reporting/project_report.py` or extend it
     accordingly.
