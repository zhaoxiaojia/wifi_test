# UI Modularisation Overview

This directory hosts the Qt-based desktop client. UI configuration is now organised around *sections* to keep
widgets isolated per functional area (Wi-Fi parameters, router tooling, RF setup, etc.).

## Adding a New Section
1. Create a module under `src/ui/sections/` implementing `ConfigSection` and register it via `@register_section`.
2. Describe form fields with `FieldSchema` and render them with `FormBuilder` when possible to avoid repetitive layout code.
3. Register fields using `register_field` so `CaseConfigPage` can manage enable/disable logic and persistence.
4. Update `sections/__init__.py` (if necessary) to ensure the module is imported for registration.
5. Map the section to relevant case types using `register_case_sections`.

## Updating Case-Type Mapping
*Case types* correspond to the stem of the selected test script (e.g. `switch_wifi`). Use `register_case_sections`
to assign sections, and `register_section_tags` for fine-grained visibility keyed by tags.

## Form Builder Quick Start
```
from src.ui.forms import FieldSchema, FormBuilder
builder = FormBuilder(parent)
form, widgets = builder.build_form(QFormLayout(), [
    FieldSchema(name="example.field", label="Example", placeholder="enter value"),
])
```
Attach the `form` widget into a layout and keep references from `widgets` for later reads.

## Development Workflow
- Prefer adding reusable helpers to `src/ui/forms/` or `src/ui/sections/base.py`.
- Keep interactions with existing proxies (`group_proxy`, `rvrwifi_proxy`, etc.) rather than duplicating logic.
- Run `python main.py` to manually verify layout changes.
