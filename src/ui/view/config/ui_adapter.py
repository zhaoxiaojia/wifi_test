from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Mapping

from PyQt5.QtCore import QObject, QSortFilterProxyModel
from PyQt5.QtWidgets import QWidget
from qfluentwidgets import ComboBox as FluentComboBox


@dataclass(frozen=True)
class UiEvent:
    """Lightweight, structured UI event produced by the adapter layer."""

    kind: str
    source: str
    payload: Dict[str, Any]


EmitCallback = Callable[[UiEvent], None]


class UiAdapter(QObject):
    """Bridge between PyQt widgets and controller-facing UiEvent stream.

    The adapter is owned by :class:`CaseConfigPage` and is responsible for:

    - binding Qt signals on the page's widgets,
    - translating interactions into :class:`UiEvent` instances, and
    - forwarding them upstream via a simple callable ``emit(event)``.

    All logic in this module is intentionally written in English so that
    controller code and logs remain consistent and easy to maintain.
    """

    def __init__(self, page: QWidget, emit: EmitCallback) -> None:
        super().__init__(page)
        self._page = page
        self._emit = emit

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def bind_all(self) -> None:
        """Bind all known widget groups to the unified UiEvent pipeline."""
        self._bind_field_changes()
        self._bind_case_tree()
        self._bind_csv_combo()
        self._bind_run_buttons()
        self._bind_tabs()

    # ------------------------------------------------------------------
    # Event helpers
    # ------------------------------------------------------------------

    def _emit_event(self, kind: str, source: str, **payload: Any) -> None:
        event = UiEvent(kind=str(kind), source=str(source), payload=dict(payload))
        self._emit(event)

    # ------------------------------------------------------------------
    # Field-change binding
    # ------------------------------------------------------------------

    def _iter_field_widgets(self) -> Mapping[str, QWidget]:
        """Return the page's field widget map."""
        return self._page.field_widgets

    def _bind_field_changes(self) -> None:
        """Bind generic field-change signals to ``field.change`` events.

        This replaces scattered autosave bindings and ensures that all
        config widgets share a single, predictable signal → event path.
        """
        for field_id, widget in self._iter_field_widgets().items():

            def _handler(fid: str = field_id) -> None:
                value = self._extract_widget_value(widget)
                self._emit_event("field.change", fid, field=fid, value=value)

            if hasattr(widget, "entriesChanged"):
                widget.entriesChanged.connect(_handler)  # type: ignore[union-attr]
                continue

            if isinstance(widget, FluentComboBox):
                if hasattr(widget, "currentIndexChanged"):
                    widget.currentIndexChanged.connect(lambda _idx, cb=_handler: cb())
                if hasattr(widget, "currentTextChanged"):
                    widget.currentTextChanged.connect(lambda _txt, cb=_handler: cb())
                continue

            # Standard widgets: prefer high-level change notifications.
            if hasattr(widget, "toggled"):
                widget.toggled.connect(lambda _checked, cb=_handler: cb())
                continue
            if hasattr(widget, "currentIndexChanged"):
                widget.currentIndexChanged.connect(lambda _idx, cb=_handler: cb())
                continue
            if hasattr(widget, "valueChanged") and not hasattr(widget, "currentText"):
                widget.valueChanged.connect(lambda _val, cb=_handler: cb())
                continue
            if hasattr(widget, "textChanged"):
                widget.textChanged.connect(lambda _txt, cb=_handler: cb())
                continue

    @staticmethod
    def _extract_widget_value(widget: QWidget) -> Any:
        """Best-effort extraction of a widget's current value."""
        if hasattr(widget, "isChecked"):
            return bool(widget.isChecked())  # type: ignore[arg-type]
        if hasattr(widget, "value") and not hasattr(widget, "currentText"):
            return widget.value()  # type: ignore[call-arg]
        if hasattr(widget, "currentText"):
            return str(widget.currentText())  # type: ignore[call-arg]
        if hasattr(widget, "text"):
            return str(widget.text())  # type: ignore[call-arg]
        return None

    # ------------------------------------------------------------------
    # Case tree binding
    # ------------------------------------------------------------------

    def _bind_case_tree(self) -> None:
        tree = self._page.case_tree

        def _on_clicked(proxy_idx) -> None:
            model = tree.model()
            if isinstance(model, QSortFilterProxyModel):
                source_idx = model.mapToSource(proxy_idx)
            else:
                source_idx = proxy_idx

            fs_model = self._page.fs_model
            path = fs_model.filePath(source_idx)
            ctl = self._page.config_ctl
            base = Path(ctl.get_application_base())
            display_path = Path(path).relative_to(base).as_posix()

            if Path(path).is_dir():
                self._emit_event(
                    "case.dir.click",
                    source="case_tree",
                    fs_path=path,
                    display_path=display_path,
                )
                return

            self._emit_event(
                "case.select",
                source="case_tree",
                case_path=path,
                display_path=display_path,
            )

        tree.clicked.connect(_on_clicked)

    # ------------------------------------------------------------------
    # CSV combo binding
    # ------------------------------------------------------------------

    def _bind_csv_combo(self) -> None:
        csv_combo = self._page.csv_combo

        def _on_activated(index: int) -> None:
            self._emit_event(
                "csv.select",
                source="csv_combo",
                index=index,
                force=True,
            )

        csv_combo.activated.connect(_on_activated)
        csv_combo.currentIndexChanged.connect(
            lambda idx: self._emit_event(
                "csv.select",
                source="csv_combo",
                index=idx,
                force=False,
            )
        )

    # ------------------------------------------------------------------
    # Run buttons binding
    # ------------------------------------------------------------------

    def _bind_run_buttons(self) -> None:
        for btn in self._page._run_buttons:
            def _handler(_checked: bool = False, button=btn) -> None:
                object_name = button.objectName() or "run_button"
                self._emit_event(
                    "action.run",
                    source=object_name,
                    button_id=object_name,
                )

            btn.clicked.connect(_handler)

    # ------------------------------------------------------------------
    # Settings tabs binding
    # ------------------------------------------------------------------

    def _bind_tabs(self) -> None:
        for key, lbl in self._page._page_buttons.items():
            def _on_clicked(page_key: str = key) -> None:
                self._emit_event(
                    "tab.switch",
                    source="settings_tab",
                    key=page_key,
                )

            lbl.clicked.connect(_on_clicked)


__all__ = ["UiEvent", "UiAdapter"]
