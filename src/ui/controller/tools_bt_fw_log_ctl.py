"""Controller for the BT FW log analysis tool.

This controller owns I/O and behaviour for :class:`BtFwLogToolView`,
leaving the view focused on widget layout only.

For now the implementation is a lightweight stub; actual serial and
log parsing logic can be integrated later.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PyQt5.QtCore import QThread, pyqtSignal, QObject
from PyQt5.QtWidgets import QFileDialog, QMessageBox, QWidget

from src.tools.bt_fw_log_analyzer import analyze_bt_fw_log, capture_serial_log
from src.ui.controller import list_serial_ports
from src.ui.view.tools_bt_fw_log import BtFwLogToolView


class BtFwLogToolController:
    """Behaviour for the BT FW log analysis tool."""

    def __init__(self, view: BtFwLogToolView, parent: Optional[QWidget] = None) -> None:
        self.view = view
        self.parent = parent or view

        self._worker_thread: QThread | None = None
        self._analyze_worker: QObject | None = None
        self._capture_thread: QThread | None = None
        self._capture_worker: QObject | None = None
        self._serial_port_map: dict[str, str] = {}

        self._init_serial_ui()

        self.view.browseFileRequested.connect(self._on_browse_file)
        self.view.analyzeRequested.connect(self._on_analyze_requested)
        self.view.captureRequested.connect(self._on_capture_requested)

    # ------------------------------------------------------------------
    # Serial configuration helpers
    # ------------------------------------------------------------------

    def _init_serial_ui(self) -> None:
        """Populate serial port and baud-rate combos using shared helpers."""
        self._refresh_serial_ports()
        self.view.set_baud_rates(["9600", "19200", "38400", "57600", "115200", "921600"])

    def _refresh_serial_ports(self) -> None:
        """Re-enumerate system serial ports and update the Port combo."""
        try:
            ports = list_serial_ports()
        except Exception:
            ports = []
        self._serial_port_map = {}
        labels: list[str] = []
        for device, label in ports:
            labels.append(label)
            self._serial_port_map[label] = device
        self.view.set_serial_ports(labels)

    def _on_browse_file(self) -> None:
        """Open a file dialog and update the view with the selected path."""
        path, _ = QFileDialog.getOpenFileName(
            self.parent, "Select BT FW log file", str(Path.home()), "Log files (*.log *.txt);;All files (*.*)"
        )
        if not path:
            return
        self.view.set_file_path(path)
        # Automatically start analysis when the user selects a local
        # file so that no extra Analyze button is required.
        self._on_analyze_requested()

    def _on_analyze_requested(self) -> None:
        """Run BT FW log analysis in a background thread and display the result."""
        # Debug: entry point for Analyze button.
        import sys as _sys

        debug_out = getattr(_sys, "__stdout__", None) or _sys.stdout
        print("[bt-fw-debug] _on_analyze_requested: invoked", file=debug_out, flush=True)
        path_text = self.view.file_path_edit.text().strip()
        if not path_text:
            QMessageBox.warning(self.parent, "BT FW Log", "Please select a log file first.")
            return
        log_path = Path(path_text)
        if not log_path.is_file():
            QMessageBox.warning(
                self.parent,
                "BT FW Log",
                f"Selected log file does not exist:\n{log_path}",
            )
            return

        if self._worker_thread is not None:
            # Avoid running multiple analyses simultaneously.
            QMessageBox.information(
                self.parent,
                "BT FW Log",
                "Analysis is already running. Please wait for it to finish.",
            )
            print("[bt-fw-debug] _on_analyze_requested: worker already running", file=debug_out, flush=True)
            return

        # Prevent concurrent runs and capture while analysing.
        self.view.set_busy(True)
        self.view.analyze_button.setEnabled(False)
        self.view.capture_button.setEnabled(False)
        self.view.append_result_text(f"Starting analysis for: {log_path}")
        print(f"[bt-fw-debug] _on_analyze_requested: creating worker for {log_path}", file=debug_out, flush=True)

        thread = QThread(self.parent)

        class _Worker(QObject):
            finished = pyqtSignal(str)
            error = pyqtSignal(str)
            progress = pyqtSignal(str)

            def __init__(self, src_path: Path) -> None:
                super().__init__()
                self._src_path = src_path

            def run(self) -> None:  # type: ignore[override]
                import sys as _sys_inner

                debug_out_inner = getattr(_sys_inner, "__stdout__", None) or _sys_inner.stdout
                print("[bt-fw-debug] _Worker.run: started", file=debug_out_inner, flush=True)
                try:
                    def _on_chunk(chunk: str) -> None:
                        self.progress.emit(chunk)

                    text = analyze_bt_fw_log(self._src_path, on_chunk=_on_chunk)
                except Exception as exc:  # pragma: no cover - defensive
                    self.error.emit(str(exc))
                    print(f"[bt-fw-debug] _Worker.run: error {exc}", file=debug_out_inner, flush=True)
                    return
                print("[bt-fw-debug] _Worker.run: finished, emitting result", file=debug_out_inner, flush=True)
                self.finished.emit(text)

        worker = _Worker(log_path)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)

        def _on_finished(text: str) -> None:
            # Always show some feedback so the user can see that
            # analysis has completed, even when the legacy parser
            # produces no decoded lines for the selected file.
            self.view.set_busy(False)
            if not text.strip():
                self.view.append_result_text(
                    "Analysis finished, but no BT FW entries were decoded.\n"
                    "Please ensure the file is a raw firmware log captured by the BT tool."
                )
            else:
                self.view.append_result_text(text)
            self.view.analyze_button.setEnabled(True)
            self.view.capture_button.setEnabled(True)
            thread.quit()
            self._worker_thread = None
            self._analyze_worker = None

        def _on_error(msg: str) -> None:
            QMessageBox.critical(self.parent, "BT FW Log", msg)
            self.view.set_busy(False)
            self.view.analyze_button.setEnabled(True)
            self.view.capture_button.setEnabled(True)
            thread.quit()
            self._worker_thread = None
            self._analyze_worker = None

        def _on_progress(chunk: str) -> None:
            if not chunk:
                return
            # The legacy parser prints many small fragments; coalesce
            # them visually by writing them as-is into the QTextEdit.
            import sys as _sys
            debug_out = getattr(_sys, "__stdout__", None) or _sys.stdout
            print(f"[bt-fw-debug] progress chunk len={len(chunk)}", file=debug_out, flush=True)
            self.view.result_view.moveCursor(self.view.result_view.textCursor().End)
            self.view.result_view.insertPlainText(chunk)
            self.view.result_view.ensureCursorVisible()

        worker.finished.connect(_on_finished)
        worker.error.connect(_on_error)
        worker.progress.connect(_on_progress)
        thread.finished.connect(thread.deleteLater)

        # Keep a reference so the worker is not garbage-collected
        # before the thread starts, which would silently prevent the
        # run() method from ever being invoked.
        self._analyze_worker = worker
        self._worker_thread = thread
        print("[bt-fw-debug] _on_analyze_requested: starting worker thread", file=debug_out, flush=True)
        thread.start()

    # ------------------------------------------------------------------
    # Serial capture
    # ------------------------------------------------------------------

    def _on_capture_requested(self, running: bool) -> None:
        """Start or stop serial capture and analysis."""
        if running:
            if self._capture_thread is not None:
                QMessageBox.information(
                    self.parent,
                    "BT FW Log",
                    "Capture is already running.",
                )
                self.view.set_capture_running(True)
                return

            # Refresh ports just before starting capture so that newly
            # plugged-in devices are visible without restarting the app.
            self._refresh_serial_ports()

            label = self.view.current_port_label()
            if not label:
                QMessageBox.warning(
                    self.parent,
                    "BT FW Log",
                    "No serial port is available or selected.",
                )
                self.view.set_capture_running(False)
                return

            device = self._serial_port_map.get(label, label)
            baud = self.view.current_baud_rate()

            # Worker that captures raw FW log and runs the analyzer.
            thread = QThread(self.parent)

            class _CaptureWorker(QObject):
                finished = pyqtSignal(str)
                error = pyqtSignal(str)
                progress = pyqtSignal(str)

                def __init__(self, port: str, baudrate: int) -> None:
                    super().__init__()
                    self._port = port
                    self._baudrate = baudrate
                    self._stop_requested = False

                def stop(self) -> None:
                    self._stop_requested = True

                def run(self) -> None:  # type: ignore[override]
                    try:
                        def _on_chunk(chunk: str) -> None:
                            self.progress.emit(chunk)

                        stop_cb = lambda: self._stop_requested
                        log_paths = capture_serial_log(
                            self._port,
                            self._baudrate,
                            on_raw_text=self.progress.emit,
                            stop_flag=stop_cb,
                        )

                        # Run the same analyzer used for local files and
                        # stream decoded output via the same progress signal.
                        all_text: list[str] = []
                        for path in log_paths:
                            text_chunk = analyze_bt_fw_log(str(path), on_chunk=_on_chunk)
                            if text_chunk:
                                all_text.append(text_chunk)
                        text = "".join(all_text)
                    except Exception as exc:  # pragma: no cover - defensive
                        self.error.emit(str(exc))
                        return
                    self.finished.emit(text)

            worker = _CaptureWorker(device, baud)
            worker.moveToThread(thread)
            thread.started.connect(worker.run)

            def _on_finished(text: str) -> None:
                self.view.append_result_text("Capture and analysis finished.")
                if text:
                    self.view.append_result_text(text)
                self.view.set_capture_running(False)
                self.view.analyze_button.setEnabled(True)
                thread.quit()
                self._capture_thread = None

            def _on_error(msg: str) -> None:
                QMessageBox.critical(self.parent, "BT FW Log", msg)
                self.view.set_capture_running(False)
                self.view.analyze_button.setEnabled(True)
                thread.quit()
                self._capture_thread = None

            def _on_progress(chunk: str) -> None:
                if chunk:
                    self.view.append_result_text(chunk.rstrip("\n"))

            worker.finished.connect(_on_finished)
            worker.error.connect(_on_error)
            worker.progress.connect(_on_progress)
            thread.finished.connect(thread.deleteLater)

            self._capture_thread = thread
            self._capture_worker = worker
            self.view.analyze_button.setEnabled(False)
            self.view.set_busy(True)
            thread.start()
        else:
            # Stop requested
            worker = self._capture_worker
            thread = self._capture_thread
            if worker is None or thread is None:
                self.view.set_capture_running(False)
                return
            if hasattr(worker, "stop"):
                worker.stop()  # type: ignore[call-arg]


__all__ = ["BtFwLogToolController"]
