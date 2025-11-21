
# UI Architecture (MVC)

All new UI work in this package must follow the **Model / View / Controller**
structure described here. Before adding or changing any UI code, **read this
document first**.

The goals are:

- Clear separation of data description (Model), widgets/layout (View), and
  behaviour / I/O (Controller).
- Consistent development flow for new features.
- Simple, predictable layering so code is easy to reason about and reuse.

The rules below apply to all UI modules in `src/ui`.

---

## 1. Layers and Responsibilities

### 1.1 Model

- Location: `src/ui/model/`
- Purpose: describe *what* can be configured and how fields are grouped.
- Typical files:
  - `config_dut_ui.yaml`
  - `config_execution_ui.yaml`
  - `config_stability_ui.yaml`
- Additional configuration lives under `src/util/constants.py` and other
  non-UI modules (e.g. router maps, debug flags).

Model files must not contain any Qt code or UI layout logic.

### 1.2 View

- Location: `src/ui/view/`
- Purpose: create widgets, layouts and visual effects. No business logic,
  no I/O, no direct pytest calls.
- Typical modules:
  - `view/account.py` – `AccountView`, `CompanyLoginPage`
  - `view/config/page.py` – `ConfigView`, `CaseConfigPage`
  - `view/case.py` – `CaseView`, `RvrWifiConfigPage`
  - `view/run.py` – `RunView`, `RunPage`
  - `view/report.py` – `ReportView`
  - `view/about.py` – `AboutView`
  - `view/common.py` – shared widgets, animations, helpers
  - `view/builder.py` – schema-driven Config UI builder

Each page has one primary view module that owns its visual skeleton. When a
“page” class exists (e.g. `RunPage`, `CompanyLoginPage`), it also lives in
the view package and is responsible for:

- Composing the pure view (e.g. `RunView`) via `attach_view_to_page(...)`.
- Wiring signals/slots **inside the page** (e.g. button clicks, timers).
- Delegating non-trivial logic and I/O to the controller layer.

Views may use animations and styling helpers from `view/common.py` and
`view/theme.py`, but must not:

- Read or write config files directly.
- Talk to routers, databases, pytest, or external tools.
- Perform heavy computation or multi-process/multi-thread orchestration.

### 1.3 Controller

- Location: `src/ui/controller/`
- Purpose: own all non-trivial behaviour and I/O for UI pages.
- Typical modules:
  - `controller/account_ctl.py` – LDAP helpers and login worker
  - `controller/config_ctl.py` – Config lifecycle, case tree, stability helpers
  - `controller/case_ctl.py` – RvR Wi‑Fi CSV helpers and switch‑Wi‑Fi plumbing
  - `controller/run_ctl.py` – pytest orchestration, run workers and logging
  - `controller/report_ctl.py` – report directory scanning and chart rendering
  - `controller/about_ctl.py` – About page actions and metadata wiring

Controllers operate on **view instances** passed in from the caller. They
may:

- Read and write YAML / JSON / CSV / logs.
- Call pytest, router tools, or other business modules.
- Connect signals from view widgets to slots implemented in the controller.
- Update the view via its public attributes and helper methods.

Controllers must not:

- Instantiate top-level windows or perform application‑wide navigation
  (that is owned by `main.py`).
- Create their own ad-hoc layouts or widgets; always use the view layer.

---

## 2. Config Page Flow (YAML → UI → Behaviour)

Most configuration-related development follows the pipeline below:

1. **Describe fields in YAML**  
   - Add or update entries in `src/ui/model/config/config_*_ui.yaml`.  
   - Use the existing structure under `dut`, `execution`, `stability`, and
     `stability.cases.*` for script-specific sections.

2. **Generate widgets via the builder**  
   - The builder in `src/ui/view/builder.py` is the **only place** that
     creates `QGroupBox`es and field widgets for the Config page. Example:

     ```python
     from src.ui.view.builder import load_ui_schema, build_groups_from_schema

     dut_schema = load_ui_schema("dut")
     build_groups_from_schema(page, config, dut_schema, panel_key="dut")
     ```

   - The builder populates:
     - `page._page_panels[...]` with `ConfigGroupPanel` containers.
     - `page.field_widgets[...]` mapping field keys to widgets.

3. **UI rules and actions**  
   - Visual rules and small UI reactions live in
     `src/ui/view/config/actions.py`. Examples:
     - Enabling/disabling widgets by field key.
     - Showing script-specific group boxes.
     - Responding to simple value changes in the Config UI.

4. **Controller behaviour**  
   - Non-trivial behaviour lives in `ConfigController`
     (`src/ui/controller/config_ctl.py`):
     - Loading/saving the combined config via `load_page_config` /
       `save_page_config` (from `src/ui/__init__.py`).
     - Computing editable fields per case.
     - Normalising stability and FPGA sections.
     - Managing the case tree.
   - Shared helpers for RvR Wi‑Fi CSV / switch‑Wi‑Fi live in
     `src/ui/controller/case_ctl.py` and are called from the controller
     and/or view.

5. **Main window wiring**  
   - `main.py` composes high‑level pages (Account, Config, Run, Report,
     About) and attaches controllers where needed:
     - `AboutController(self.about_page)`
     - `ReportController(self.report_view)`
     - `ConfigController(self.caseConfigPage)` (via `CaseConfigPage`)

If you need a new Config field, **do not** hand‑craft widgets in controllers.
Always extend the YAML schema and let the builder create the view.

---

## 3. Typical Development Workflows

### 3.1 Adding a new config field

1. Update the appropriate `config_*_ui.yaml` under `src/ui/model/config`.
2. Ensure the builder is invoked for the panel (`dut`, `execution`,
   `stability`) via `view/builder.py`.
3. Use `page.field_widgets[...]` in `view/config/actions.py` or the
   relevant controller to read/write values or apply rules.
4. Persist new values through `ConfigController.save_config()` only.

### 3.2 Adding a new sidebar page

1. **Model (optional)**  
   - If the page is driven by structured config, add a model module or
     extend existing YAML under `src/ui/model/` or `src/util/constants.py`.

2. **View**  
   - Create `src/ui/view/<page>.py` with:
     - A pure view class (e.g. `FooView`) that builds the layout.
     - A thin page class (e.g. `FooPage`) that:
       - Composes the view with `attach_view_to_page(...)`.
       - Exposes a small surface area for the controller and `main.py`.

3. **Controller**  
   - Add `src/ui/controller/<page>_ctl.py` with a controller class that:
     - Accepts the view/page in its constructor.
     - Connects signals and implements all non-trivial behaviour and I/O.

4. **Main window**  
   - Import and instantiate the view/page and controller in `main.py`.
   - Attach the page to the FluentWindow navigation via `_create_sidebar_button(...)`.

### 3.3 Extending RvR Wi‑Fi case behaviour

- UI-only changes (labels, layout, new buttons):
  - Update `CaseView` / `RvrWifiConfigPage` in `src/ui/view/case.py`.
- CSV discovery, path normalisation, switch‑Wi‑Fi preview:
  - Extend helpers in `src/ui/controller/case_ctl.py`.

---

## 4. Coding Style and Constraints

These rules apply to all new code in `src/ui`:

### 4.1 Language

- **Do not use Chinese** in identifiers, comments, or log messages.
- User‑visible strings must be English or loaded from resources intended for
  localisation (if added in the future).

### 4.2 Layering and Encapsulation

- Respect the MVC layers:
  - Model: no Qt, no UI.
  - View: widgets and visuals only; minimal logic; no heavy I/O.
  - Controller: I/O, long‑running work, cross‑module orchestration.
- When you encapsulate logic, decide clearly:
  - Which layer it belongs to.
  - Which modules are allowed to call it.
- Do not bypass the layering by calling deep controller helpers from random
  modules. Instead, expose small, explicit controller methods or higher‑level
  helpers in the appropriate module.

### 4.3 Defensive Programming

Avoid “defensive by default” patterns that make code hard to follow:

- Do **not** wrap large blocks in broad `try/except Exception` just to
  silence errors. Catch specific exceptions where necessary and log them.
- Avoid `getattr(obj, "attr", None)` as the primary way to discover state.
  Prefer explicit attributes and clear types. Use `TYPE_CHECKING` and type
  hints instead of runtime guessing.
- Do not use `hasattr(...)` / `getattr(...)` chains to probe for behaviour
  that a layer is not supposed to support. Instead, refactor the API so the
  caller passes what it needs.

It is acceptable to use `with suppress(...)` or small `try/except` blocks
for shutdown/cleanup paths where failures are non‑critical and explicitly
documented.

### 4.4 General Style

- Keep controller methods focused and testable. If a method grows beyond a
  clear responsibility, split it.
- Use explicit names for pages and views (`RunView`, `RunPage`,
  `RvrWifiConfigPage`, `ReportView`, etc.).
+- Reuse helpers from `view/common.py` and controllers instead of copying
  logic.
- Keep logging messages short, in English, and relevant to the action.

---

## 5. Before You Start Coding

For any new UI work, follow this checklist **in order**:

1. Read this `src/ui/README.md` to refresh the architecture.
2. Identify which layer(s) your change touches: Model, View, Controller.
3. Update or add YAML / model entries if needed.
4. Extend or create view modules under `src/ui/view/`.
5. Add or update controller modules under `src/ui/controller/`.
6. Wire the page/controller into `main.py` only at the top level.
7. Verify that layering is respected and that no new defensive patterns
   (broad `try/except`, heavy `getattr`, etc.) are introduced.

Following this process keeps the UI predictable and maintainable as the
application grows.
