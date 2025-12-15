"""Controller for the AI chat tool.

This controller connects :class:`AiChatToolView` to an AI backend.  The
current implementation is a stub that can be extended to call a free
LLM based on the selected model.
"""

from __future__ import annotations

from typing import Optional

from PyQt5.QtCore import QUrl
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QFileDialog,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from src.ui.view.toolbar.tools_ai_chat import AiChatToolView
from src.ui.model.ai_chat_backend import (
    get_signup_url,
    list_models_for_ui,
    load_api_key,
    send_chat_completion,
    store_api_key,
)
from src.util.constants import load_config, save_config, TOOLBAR_SECTION_KEY


class AiChatToolController:
    """Behaviour for the AI chat tool."""

    def __init__(self, view: AiChatToolView, parent: Optional[QWidget] = None) -> None:
        self.view = view
        self.parent = parent or view
        self._current_model_id: str | None = None
        self._restoring_model = False

        models = list_models_for_ui()
        if models:
            self.view.model_combo.clear()
            for model_id, title in models:
                self.view.model_combo.addItem(title, userData=model_id)

        self.view.model_combo.currentIndexChanged.connect(self._on_model_index_changed)
        self._restore_toolbar_state()
        self._on_model_index_changed(self.view.model_combo.currentIndex())

        self.view.sendMessageRequested.connect(self._on_send_message)
        self.view.manageKeysRequested.connect(self._on_manage_keys_requested)
        self.view.attachFileRequested.connect(self._on_attach_file_requested)

    def _on_model_index_changed(self, index: int) -> None:
        model_id = self.view.model_combo.itemData(index)
        if isinstance(model_id, str):
            self._current_model_id = model_id
            if not self._restoring_model:
                self._persist_toolbar_state()

    def _persist_toolbar_state(self) -> None:
        """Persist toolbar field values into config_toolbar.yaml via save_config()."""
        config = load_config(refresh=True) or {}
        toolbar_section = dict(config.get(TOOLBAR_SECTION_KEY, {}) or {})
        ai_section = dict(toolbar_section.get("ai_chat", {}) or {})
        if self._current_model_id:
            ai_section["model_id"] = str(self._current_model_id)
        toolbar_section["ai_chat"] = ai_section
        config[TOOLBAR_SECTION_KEY] = toolbar_section
        save_config(config)

    def _restore_toolbar_state(self) -> None:
        """Restore toolbar field values from config_toolbar.yaml via load_config()."""
        config = load_config(refresh=True) or {}
        toolbar_section = config.get(TOOLBAR_SECTION_KEY, {}) or {}
        ai_section = toolbar_section.get("ai_chat", {}) if isinstance(toolbar_section, dict) else {}
        stored = ai_section.get("model_id") if isinstance(ai_section, dict) else None
        if not isinstance(stored, str) or not stored.strip():
            return
        target_id = stored.strip()
        for idx in range(self.view.model_combo.count()):
            item_id = self.view.model_combo.itemData(idx)
            if item_id == target_id:
                self._restoring_model = True
                try:
                    self.view.model_combo.setCurrentIndex(idx)
                    self._current_model_id = target_id
                finally:
                    self._restoring_model = False
                return

    def _on_send_message(self, text: str) -> None:
        """Handle a user message from the view."""
        self.view.append_message("user", text)
        self.view.clear_input()
        try:
            from src.ui.controller.ai.llm_yaml_mapper import (
                apply_updates_to_config,
                derive_performance_csv_updates,
                looks_like_run_request,
                map_request_with_llm,
                load_ai_catalog,
                validate_and_coerce_updates,
            )

            if looks_like_run_request(text):
                main_window = self.parent
                if not hasattr(main_window, "caseConfigPage"):
                    raise RuntimeError("Main window does not expose caseConfigPage; cannot run.")

                model_id = self._current_model_id
                if not model_id:
                    raise RuntimeError("No model is selected.")

                result = map_request_with_llm(model_id, text)
                print(
                    "[AI_DEBUG] Run intent resolved:",
                    "case_id=",
                    result.case_id,
                    "text_case=",
                    (result.updates or {}).get("text_case"),
                    "scenario=",
                    result.scenario,
                )
                if result.action != "run":
                    missing = ", ".join(result.missing) if result.missing else "unknown"
                    self.view.append_message(
                        "assistant",
                        "Not enough information to run.\n"
                        f"Missing: {missing}\n"
                        "Try adding the case name, e.g. 'peak', 'rvr', or 'rvo'.",
                    )
                    return

                catalog = load_ai_catalog()
                coerced, errors = validate_and_coerce_updates(catalog, result.updates)
                if errors:
                    self.view.append_message(
                        "assistant",
                        "Cannot apply requested updates:\n- " + "\n- ".join(errors),
                    )
                    return

                # Performance scenario selection lives in the CSV file used by performance tests.
                # If the user mentions Wi-Fi scenario attributes (e.g. HE + 20), generate an AI CSV
                # and point csv_path to it. Unmentioned YAML keys keep their historical values.
                from src.util.constants import load_config

                current_cfg = load_config(refresh=True) or {}
                derived_updates, derived_details = {}, {}
                try:
                    derived_updates, derived_details = derive_performance_csv_updates(
                        current_config=current_cfg,
                        case_id=result.case_id,
                        scenario=result.scenario,
                    )
                except Exception as exc:  # noqa: BLE001
                    print(f"[AI_DEBUG] Failed to derive performance CSV: {exc}")
                if derived_updates:
                    coerced = {**coerced, **derived_updates}

                preview_lines = self._format_run_preview(
                    user_text=text, updates=coerced, derived_details=derived_details
                )
                confirm = QMessageBox(main_window)
                confirm.setIcon(QMessageBox.Question)
                confirm.setWindowTitle("AI Run")
                confirm.setText("Confirm the test run?")
                confirm.setInformativeText(preview_lines)
                confirm.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                run_button = confirm.button(QMessageBox.Yes)
                cancel_button = confirm.button(QMessageBox.No)
                if run_button is not None:
                    run_button.setText("Run")
                if cancel_button is not None:
                    cancel_button.setText("Cancel")
                if confirm.exec_() != QMessageBox.Yes:
                    self.view.append_message("assistant", "Canceled.")
                    return

                apply_updates_to_config(coerced)

                # Refresh the Case page CSV view immediately when csv_path changed,
                # so the UI reflects the newly generated AI scenarios.
                if derived_details and derived_details.get("generated_csv"):
                    try:
                        csv_path = str(derived_details["generated_csv"])
                        main_window.caseConfigPage.config_ctl.set_selected_csv(csv_path, sync_combo=True)
                        main_window.caseConfigPage.csvFileChanged.emit(csv_path)
                        print(f"[AI_DEBUG] Emitted csvFileChanged for: {csv_path}")
                    except Exception as exc:  # noqa: BLE001
                        print(f"[AI_DEBUG] Failed to refresh Case CSV view: {exc}")

                main_window.caseConfigPage.config_ctl.on_run()
                self.view.append_message(
                    "assistant",
                    "OK. Updated config and started Run:\n" + preview_lines,
                )
                return

            model_id = self._current_model_id
            if not model_id:
                reply = "No model is selected."
            else:
                try:
                    reply = send_chat_completion(model_id, text)
                except RuntimeError as exc:
                    signup_url = get_signup_url(model_id)
                    self._prompt_for_signup(signup_url, str(exc))
                    reply = str(exc)
        except Exception as exc:  # noqa: BLE001
            reply = f"Error calling model: {exc}"
        self.view.append_message("assistant", reply)

    def _prompt_for_signup(self, url: str, message: str) -> None:
        box = QMessageBox(self.parent)
        box.setIcon(QMessageBox.Information)
        box.setWindowTitle("API key required")
        box.setText(message)
        box.setInformativeText(
            "Open the provider web site in your browser to create or view an API key?"
        )
        box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        result = box.exec_()
        if result == QMessageBox.Yes:
            QDesktopServices.openUrl(QUrl(url))

    def _on_manage_keys_requested(self) -> None:
        model_id = self._current_model_id
        if not model_id:
            box = QMessageBox(self.parent)
            box.setIcon(QMessageBox.Information)
            box.setWindowTitle("No model selected")
            box.setText("Select a model before editing API keys.")
            box.setStandardButtons(QMessageBox.Ok)
            box.exec_()
            return

        current_title = self.view.model_combo.currentText() or model_id
        existing_key = load_api_key(model_id)
        if not existing_key:
            signup_url = get_signup_url(model_id)
            QDesktopServices.openUrl(QUrl(signup_url))

        dialog = _ApiKeyDialog(self.parent, current_title, existing_key)
        if dialog.exec_() == QDialog.Accepted:
            api_key = dialog.api_key()
            if api_key:
                store_api_key(model_id, api_key)

    def _on_attach_file_requested(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self.parent, "Select file to attach", "", "All Files (*.*)"
        )
        if path:
            self.view.append_message("user", f"[Attached file] {path}")

    def _format_run_preview(
        self,
        *,
        user_text: str,
        updates: dict[str, object],
        derived_details: dict[str, object],
    ) -> str:
        return _format_run_preview_message(user_text, updates, derived_details)


class _ApiKeyDialog(QDialog):
    """Simple dialog to edit a single provider API key."""

    def __init__(self, parent: QWidget, model_title: str, api_key: str) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"{model_title} API Key")

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self._key_edit = QLineEdit(self)
        self._key_edit.setText(api_key)
        self._key_edit.setEchoMode(QLineEdit.Password)
        form.addRow("API Key:", self._key_edit)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def api_key(self) -> str:
        return self._key_edit.text().strip()

__all__ = ["AiChatToolController"]


def _try_read_csv_preview(path: str, *, max_rows: int = 6) -> list[dict[str, str]]:
    import csv
    from pathlib import Path

    p = Path(path)
    if not p.exists():
        return []
    with p.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        out: list[dict[str, str]] = []
        for row in reader:
            out.append({k: (v or "").strip() for k, v in (row or {}).items()})
            if len(out) >= max_rows:
                break
        return out


def _format_csv_rows(rows: list[dict[str, str]]) -> str:
    if not rows:
        return "(no rows)"
    lines: list[str] = []
    for idx, row in enumerate(rows, start=1):
        band = row.get("band", "")
        mode = row.get("wireless_mode", "")
        bw = row.get("bandwidth", "")
        sec = row.get("security_mode", "")
        ssid = row.get("ssid", "")
        tx = row.get("tx", "")
        rx = row.get("rx", "")
        lines.append(f"{idx}. {band} | {mode} | {bw} | {sec} | {ssid} | tx/rx={tx}/{rx}")
    return "\n".join(lines)


def _updates_summary(updates: dict) -> str:
    if not updates:
        return "(no config changes)"
    lines = []
    for key in ("text_case", "csv_path"):
        if key in updates:
            lines.append(f"- {key}: {updates[key]}")
    for key, value in updates.items():
        if key in {"text_case", "csv_path"}:
            continue
        lines.append(f"- {key}: {value}")
    return "\n".join(lines)


def _issues_text(details: dict) -> str:
    issues = details.get("issues") if isinstance(details, dict) else None
    if not isinstance(issues, list) or not issues:
        return ""
    bullets = "\n".join(f"- {str(x)}" for x in issues if str(x).strip())
    if not bullets:
        return ""
    return (
        "\n\nNotes:\n"
        f"{bullets}\n"
        "\nIf this isn't what you want, click Cancel and rephrase, e.g.:\n"
        "- '只测5G HE 80 peak'\n"
        "- 'HE 40 peak (2.4G+5G)'\n"
    )


def _scenario_text(details: dict) -> str:
    if not details:
        return ""
    gen = details.get("generated_csv")
    if not isinstance(gen, str) or not gen:
        return ""
    rows = _try_read_csv_preview(gen)
    preview = _format_csv_rows(rows)
    return f"\n\nScenario Preview ({gen}):\n{preview}"


def _request_text(user_text: str) -> str:
    req = (user_text or "").strip()
    if not req:
        return ""
    return f"Request:\n{req}\n"


def _case_hint(updates: dict) -> str:
    text_case = str(updates.get("text_case") or "").strip()
    if not text_case:
        return ""
    # Only show filename for readability.
    name = text_case.replace("\\", "/").split("/")[-1]
    return f"Case:\n{name}\n"


def _csv_hint(updates: dict) -> str:
    csv_path = str(updates.get("csv_path") or "").strip()
    if not csv_path:
        return ""
    name = csv_path.replace("\\", "/").split("/")[-1]
    return f"CSV:\n{name}\n"


def _header_block(user_text: str, updates: dict) -> str:
    blocks = [_request_text(user_text), _case_hint(updates), _csv_hint(updates)]
    blocks = [b for b in blocks if b]
    return "\n".join(blocks).strip()


def _format_run_preview_message(
    user_text: str,
    updates: dict[str, object],
    derived_details: dict[str, object],
) -> str:
    header = _header_block(user_text, updates)
    changes = _updates_summary(updates)
    scenario = _scenario_text(derived_details)
    notes = _issues_text(derived_details)
    if header:
        header += "\n"
    return f"{header}\nPlanned config changes:\n{changes}{scenario}{notes}"
