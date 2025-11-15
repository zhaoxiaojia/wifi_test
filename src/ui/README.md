# UI Architecture (MVC-oriented)

This package is being refactored towards a clear **Model / View / Controller** split.

At a high level:

- **Model** lives under `src/ui/model/` (YAML config + UI schema) and other
  config files in the repository. It describes *what* can be configured.
- **View** lives under `src/ui/view/` and is responsible for all widget
  creation, layouts and visual effects.
- **Controller / Logic** lives in the existing page classes (e.g.
  `CaseConfigPage`, `RunPage`, `ReportPage`), which wire views to models,
  apply rules, and handle IO.

This document focuses on the **View** layer.

## View layer rules

The current rules for view implementation are:

1. **Each page owns its visual skeleton**

   - For each sidebar page there is a dedicated view module:

     - `view/account.py` → `AccountView`
     - `view/config/page.py` → `ConfigView`
     - `view/case.py` → `CaseView`
     - `view/run.py` → `RunView`
     - `view/report.py` → `ReportView`
     - `view/about.py` → `AboutView`

   - The page class (`CompanyLoginPage`, `CaseConfigPage`, `RvrWifiConfigPage`,
     `RunPage`, `ReportPage`, `AboutPage`) composes its view in `__init__`,
     but does **not** build layouts or widgets directly. It only:

     - Instantiates the view (e.g. `self.view = RunView(self)`).
     - Calls `attach_view_to_page(...)` from `view/common.py` to attach it.
     - Keeps references to important widgets for business logic.

2. **Config page fields are schema-driven**

   - All fields under `dut`, `execution`, and `stability` are rendered from
     UI schema YAMLs in `src/ui/model/config`:

     - `config_dut_ui.yaml`
     - `config_execution_ui.yaml`
     - `config_stability_ui.yaml`

   - The builder in `view/builder.py` is the **only place** that creates
     `QGroupBox`es and field widgets for the Config page:

     ```python
     from src.ui.view.builder import load_ui_schema, build_groups_from_schema

     dut_schema = load_ui_schema("dut")
     build_groups_from_schema(page, config, dut_schema, panel_key="dut")
     ```

   - `CaseConfigPage` now only:

     - Normalises config data (e.g. `connect_type`, `fpga`, `stability`).
     - Calls the builder for each panel (`dut`, `execution`, `stability`).
     - Maps widgets into `field_widgets`/`config_controls`.
     - Applies `model.rules.CONFIG_UI_RULES` to enable/disable/show/hide fields.

   - Script-specific stability sections (e.g. `test_str`, `test_switch_wifi`)
     are also described in `config_stability_ui.yaml` as fields under
     `stability.cases.*`. The controller builds `ScriptConfigEntry` objects
     by **discovering** widgets created by the builder; it does not create
     any new group boxes or layouts.

3. **Shared view utilities live in `view/common.py`**

   - `view/common.py` contains reusable view-only helpers:

     - `ConfigGroupPanel` – three-column animated panel layout for config groups.
     - `AnimatedTreeView` – `TreeView` with expand/collapse animations.
     - `TestFileFilterModel`, `_StepSwitcher` – helpers for the config wizard tree.
     - `attach_view_to_page(page, view, ...)` – attaches a single view widget to a page with a simple box layout.
     - `animate_progress_fill(fill_frame, container, percent, ...)` – animates the Run page progress bar.

   - Any future animations or shared layout tricks should be implemented
     here, then called from controllers, instead of duplicating UI code.

4. **Controllers must not hand-craft config UI**

   - `CaseConfigPage` and other controllers **must not**:

     - Create `QGroupBox` instances for config fields.
     - Manually build form layouts for config sections.
     - Add/remove config widgets from layouts.

   - If a new config field needs to appear in the UI:

     1. Add the field to the appropriate YAML (`config_*_ui.yaml`).
     2. Let `build_groups_from_schema(...)` create the widget.
     3. Use `field_widgets[...]` and rules to control behaviour.

   - The only acceptable UI work in controllers is:

     - Wiring signals/slots (e.g. reacting to value changes).
     - Switching between panels or pages.
     - Showing InfoBars / dialogs based on business events.

This separation ensures that future UI growth (especially in the Config
page) can be achieved by editing schema files and view modules, without
spreading layout code across controllers.
