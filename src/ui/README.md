# UI Architecture and Config Flow (MVC + Rules)

All new UI work under `src/ui` must follow the **Model / View / Controller**
structure described here. Before you touch any UI code, **read this file
first**.

The goals are:

- Keep data description (Model), widgets/layout (View), and behaviour/I/O
  (Controller) clearly separated.
- Drive as much UI behaviour as possible from **YAML + rules**, not ad‑hoc
  Python in the view layer.
- Make the signal/slot wiring predictable so future changes are easy to
  reason about.

---

## 1. Layers and Responsibilities

### 1.1 Model

- Location: `src/ui/model/`
- Purpose: describe *what* can be configured and how fields are grouped.
- Typical files:
  - `config_dut.yaml`, `config_execution.yaml`, `config_stability.yaml`  
    (persisted config values)
  - `config_dut_ui.yaml`, `config_execution_ui.yaml`, `config_stability_ui.yaml`  
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
  - `view/common.py` – shared widgets, `EditableInfo`, animations

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
  - `controller/config_ctl.py` – Config lifecycle, case tree, stability helpers
  - `controller/case_ctl.py` – RvR Wi‑Fi CSV helpers and switch‑Wi‑Fi plumbing
  - `controller/run_ctl.py` – pytest orchestration and logging
  - `controller/report_ctl.py` – report discovery and plotting
  - `controller/account_ctl.py`, `controller/about_ctl.py` – login/about

Controllers operate on view instances passed from the caller. They may:

- Load and save YAML/JSON/CSV/log files.
- Call pytest or router tools.
- Connect view signals to controller slots.
- Push data back into the view via its public API.

Controllers must not create their own ad‑hoc layouts or windows.

---

## 2. Config Page End‑to‑End Flow

This section describes the **exact pipeline** for the Config page (DUT,
Execution, Stability) from YAML to widgets to rule‑driven behaviour.

### 2.1 Config YAML (values)

Persisted configuration is stored under `src/ui/model/config/`:

- `config_dut.yaml`
- `config_execution.yaml`
- `config_stability.yaml`
- `config_tool.yaml`

Loading and saving is handled by helpers in `src/ui/__init__.py` and
`ConfigController`:

- `ConfigController.load_initial_config()`
  - Calls `load_page_config(page)` to populate `page.config`.
  - Normalises sections (connect_type / fpga / stability).
- `ConfigController.save_config()`
  - Collects current values from the view and writes YAML back to disk.

### 2.2 UI schema YAML (layout)

The *structure* of the Config page is described in:

- `config_dut_ui.yaml`
- `config_execution_ui.yaml`
- `config_stability_ui.yaml`

Each schema file defines:

- `panels.dut.sections[].fields[]`
- `panels.execution.sections[].fields[]`
- `panels.stability.sections[].fields[]`

Fields specify:

- `key`: dotted config key (e.g. `connect_type.type`)
- `widget`: widget type (`line_edit`, `combo_box`, `checkbox`, `spin`, `custom`)
- `label`: user‑visible label
- `placeholder`, `minimum`, `maximum`, `choices`: extra hints

The **schema never contains Qt code**. It only describes layout and field
metadata.

### 2.3 Builder (schema → widgets)

The builder in `src/ui/view/builder.py` is the only place that turns schema
into widgets:

- `load_ui_schema(section: str)`
  - Chooses `config_dut_ui.yaml`, `config_execution_ui.yaml` or
    `config_stability_ui.yaml` and loads it.
- `build_groups_from_schema(page, config, ui_schema, panel_key, parent)`
  - For each section in the schema:
    - Creates a `QGroupBox` and `QFormLayout`.
    - For each field, creates the appropriate widget (`LineEdit`, `ComboBox`,
      `QCheckBox`, `QSpinBox`, `SwitchWifiManualEditor`, etc.).
    - Uses `get_field_choices(field_key)` from `options.py` when the schema
      does not specify static `choices`.
    - Populates initial widget values from `config`.
    - Registers the widget in `page.field_widgets[field_key]`.
    - Optionally registers a logical ID in `page.config_controls`.

`CaseConfigPage.__init__` calls `refresh_config_page_controls(self)`
(`actions.py`), which:

1. Normalises `page.config` via `ConfigController` helpers.
2. Loads and builds the DUT / Execution / Stability panels using the builder.
3. Sets `page.field_widgets` on the page.

At this point we have **all widgets created and mapped by field key**, but
no dynamic behaviour yet.

### 2.4 Rule model (`rules.py`)

`src/ui/model/rules.py` centralises all declarative UI rules and helpers:

- `CUSTOM_SIMPLE_UI_RULES: list[SimpleRuleSpec]`
  - New per‑field rules expressed as:
    ```python
    SimpleRuleSpec(
        trigger_field="rvr.tool",
        effects=[SimpleFieldEffect(...), ...],
    )
    ```
  - Drive attribute changes such as show/hide/enable/disable/set_value and
    set_options for individual fields.
- `compute_editable_info(page, case_path) -> EditableInfo`
  - Computes which fields are editable for a given test case (performance,
    RvR, RvO, stability, script‑specific cases).
  - Used by `ConfigController.get_editable_fields`.
- `apply_rules(trigger_field, values, ui_adapter)`
  - Executes all matching `SimpleRuleSpec` entries on a **UIAdapter** object
    (the view implements `show/hide/enable/disable/set_value/set_options`).
- `evaluate_all_rules(page, trigger_field=None)`
  - Unified entry point:
    - Collects current field values from widgets.
    - If `trigger_field` is provided, evaluates `CUSTOM_SIMPLE_UI_RULES`
      only for that field via `apply_rules`.
    - If `trigger_field` is `None`, evaluates rules for all trigger fields
      using the current values.

All rule interpretation now lives in `rules.py`; the view layer only calls
these functions.

### 2.5 View wiring (`CaseConfigPage`)

`src/ui/view/config/page.py` owns the Config page view:

- After building the panels, it sets:
  - `self.field_widgets` (from the builder)
  - `self._field_map` (alias used by rules)
  - `self.config_ctl = ConfigController(self)`
  - `self._last_editable_info: EditableInfo | None`
- `_connect_simple_rules()`:
  - Imports `CUSTOM_SIMPLE_UI_RULES` from `rules.py`.
  - For each `SimpleRuleSpec.trigger_field`, finds the widget in
    `self._field_map` and connects an appropriate Qt signal to
    `self.on_field_changed(field_id, value)`:
    - `currentTextChanged` for combos
    - `toggled` for checkboxes
    - `textChanged` for line edits
  - Immediately evaluates each rule once using the current widget value so
    the initial UI state matches the underlying config.
- `on_field_changed(field_id, value)`:
  - Delegates to `evaluate_all_rules(self, field_id)`.
  - This applies the relevant `SimpleRuleSpec` entries for that field.
- UIAdapter methods (`show`, `hide`, `enable`, `disable`, `set_value`,
  `set_options`):
  - Implement the interface expected by `apply_rules`.
  - Work with `QFormLayout` to hide/show labels together with fields.

### 2.6 Actions layer (`actions.py`)

`src/ui/view/config/actions.py` provides **wiring helpers** and complex view
glue. It does *not* contain new low‑level show/hide/enable/disable logic;
that is handled by rules.

Key responsibilities:

- `refresh_config_page_controls(page)`:
  - Normalises `page.config` (connect_type / fpga / stability sections).
  - Invokes the builder for each panel (`dut`, `execution`, `stability`).
  - Binds common actions:
    - `init_fpga_dropdowns`, `init_connect_type_actions`,
      `init_system_version_actions`, `init_stability_actions`,
      `init_switch_wifi_actions`, `_bind_turntable_actions`,
      `_bind_case_tree_actions`, `_bind_csv_actions`, `_bind_run_actions`.
    - Calls `bind_view_events(page, "config", handle_config_event)` so that
      simple field events (connect type, third-party, serial, RF model, RvR
      tool, router name/address, basic stability toggles) are wired via the
      declarative event table defined in `src/ui/model/view_events.yaml`.
  - `handle_config_event(page, event, **payload)`:
    - Single dispatcher for Config events (case clicked, connect type changed,
      serial status changed, RF model change, RvR tool change, CSV selection,
      stability toggles, etc.). Most field events are declared in the view
      event table and routed here via `bind_view_events`.
  - For `"case_clicked"`:
    - Updates the selected test case display.
    - Calls `config_ctl.get_editable_fields(case_path)` to compute an
      `EditableInfo` snapshot via `rules.compute_editable_info`.
    - Optionally switches to the Execution or Stability tab.
    - Calls `evaluate_all_rules(page, None)` to re‑apply case‑type rules.
- Stability script helpers:
  - `update_script_config_ui`, `load_script_config_into_widgets` handle
    script‑specific layouts (e.g. `test_str`, `test_switch_wifi`) and call
    `apply_config_ui_rules`/`evaluate_all_rules` after updates.
- Run lock helpers:
  - `apply_run_lock_ui_state` disables all field widgets during a run and
    restores them afterwards using the controller.

In summary, **actions.py wires Qt signals to controllers and to
`evaluate_all_rules`**, and hosts complex view‑only behaviour that is hard
to express as a simple field rule.

### 2.7 Controller interaction

`ConfigController` (`src/ui/controller/config_ctl.py`) uses the rule model
and view wiring as follows:

- `get_editable_fields(case_path) -> EditableInfo`:
  - Calls `compute_editable_info(self.page, case_path)` from `rules.py`.
  - Applies the result to internal flags and to the view
    (`set_fields_editable` + `_last_editable_info`).
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
application grows.*** End Patch```】【。assistanturetat to=functions.apply_patch(serializers={"json": true}) ***!
