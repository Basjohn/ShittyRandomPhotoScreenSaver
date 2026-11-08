"""SRPSS Visualizer Capture Studio: thin operator GUI for production offscreen release_media.

Select a canonical visualizer, preset and existing recorded-music window, then
render a WebP. Source rendering runs in SRPSS's own .venv child process. The
orchestrator publishes ONLY the verified WebP; all PNGs and manifests are scratch.
"""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal, QSize, QUrl
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout,
    QGridLayout, QGroupBox, QHBoxLayout, QLabel, QMainWindow, QMessageBox,
    QPlainTextEdit, QProgressBar, QPushButton, QScrollArea, QSizePolicy,
    QSpinBox, QSplitter, QVBoxLayout, QWidget,
)

from visualizer_capture_core import (
    CaptureCancelled, CaptureError, CaptureOptions, DEFAULT_OUTPUT,
    available_recordings, capture_webp, list_visualizer_cases,
)


def configure_windows_dpi() -> None:
    if sys.platform != "win32":
        return
    import ctypes
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except Exception:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            pass


class CatalogueLoader(QThread):
    loaded = Signal(list)
    failed = Signal(str)

    def run(self) -> None:
        try:
            self.loaded.emit(list_visualizer_cases())
        except Exception as exc:
            self.failed.emit(str(exc))


class CaptureWorker(QThread):
    log_line = Signal(str)
    finished_capture = Signal(dict)
    failed = Signal(str)
    cancelled_capture = Signal(str)

    def __init__(self, options: CaptureOptions):
        super().__init__()
        self.options = options
        self._cancel = False

    def cancel(self) -> None:
        self._cancel = True

    def run(self) -> None:
        try:
            result = capture_webp(
                self.options, notify=self.log_line.emit,
                cancelled=lambda: self._cancel,
            )
            self.finished_capture.emit(result)
        except CaptureCancelled as exc:
            self.cancelled_capture.emit(str(exc))
        except Exception as exc:
            self.failed.emit(str(exc))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SRPSS Visualizer Capture Studio  |  Offscreen Production Renderer")
        self.resize(1200, 790)
        self.setMinimumSize(QSize(960, 670))
        self._catalogue: list[dict] = []
        self._catalogue_worker: CatalogueLoader | None = None
        self._worker: CaptureWorker | None = None
        self._last_output: Path | None = None
        self._make_ui()
        self._set_style()
        self.refresh_recordings()
        self.refresh_catalogue()

    @staticmethod
    def _spin(minimum: int, maximum: int, value: int, suffix: str = "") -> QSpinBox:
        widget = QSpinBox()
        widget.setRange(minimum, maximum)
        widget.setValue(value)
        widget.setSuffix(suffix)
        widget.setMinimumHeight(34)
        widget.setMinimumWidth(134)
        widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        return widget

    @staticmethod
    def _seconds(minimum: float, maximum: float, value: float) -> QDoubleSpinBox:
        widget = QDoubleSpinBox()
        widget.setDecimals(2)
        widget.setSingleStep(0.25)
        widget.setRange(minimum, maximum)
        widget.setValue(value)
        widget.setSuffix(" s")
        widget.setMinimumHeight(34)
        widget.setMinimumWidth(134)
        widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        return widget

    def _make_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        heading = QLabel("SRPSS VISUALIZER CAPTURE STUDIO")
        heading.setObjectName("heading")
        layout.addWidget(heading)
        intro = QLabel(
            "Render the real SRPSS visualizers offscreen against recorded music. "
            "Select a curated preset and capture window. No live preview or normal screensaver window required."
        )
        intro.setObjectName("intro")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        layout.addWidget(splitter, 1)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 8, 0)
        left_layout.setSpacing(12)
        splitter.addWidget(left)

        source_group = QGroupBox("1  ·  VISUALIZER & RECORDING")
        sg = QGridLayout(source_group)
        sg.setHorizontalSpacing(12)
        sg.setVerticalSpacing(12)
        self.mode_combo = QComboBox()
        self.mode_combo.setMinimumHeight(36)
        self.mode_combo.currentIndexChanged.connect(self._fill_presets)
        self.preset_combo = QComboBox()
        self.preset_combo.setMinimumHeight(36)
        self.recording_combo = QComboBox()
        self.recording_combo.setMinimumHeight(36)
        self.recording_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.reload_catalogue_btn = QPushButton("Refresh modes")
        self.reload_catalogue_btn.clicked.connect(self.refresh_catalogue)
        self.reload_recordings_btn = QPushButton("Refresh clips")
        self.reload_recordings_btn.clicked.connect(self.refresh_recordings)
        sg.addWidget(QLabel("Visualizer"), 0, 0)
        sg.addWidget(self.mode_combo, 0, 1)
        sg.addWidget(self.reload_catalogue_btn, 0, 2)
        sg.addWidget(QLabel("Curated preset"), 1, 0)
        sg.addWidget(self.preset_combo, 1, 1, 1, 2)
        sg.addWidget(QLabel("Recorded music"), 2, 0)
        sg.addWidget(self.recording_combo, 2, 1)
        sg.addWidget(self.reload_recordings_btn, 2, 2)
        sg.setColumnStretch(1, 1)
        left_layout.addWidget(source_group)

        window_group = QGroupBox("2  ·  CAPTURE WINDOW")
        wg = QGridLayout(window_group)
        wg.setHorizontalSpacing(14)
        wg.setVerticalSpacing(11)
        self.start_seconds = self._seconds(0, 36000, 5)
        self.duration_seconds = self._seconds(0.25, 30, 4)
        wg.addWidget(QLabel("Start at"), 0, 0)
        wg.addWidget(self.start_seconds, 0, 1)
        wg.addWidget(QLabel("Duration"), 1, 0)
        wg.addWidget(self.duration_seconds, 1, 1)
        wg.setColumnStretch(1, 1)
        detail = QLabel("The replay includes the music preceding this window, so simulation state is warmed naturally.")
        detail.setObjectName("muted")
        detail.setWordWrap(True)
        wg.addWidget(detail, 2, 0, 1, 2)
        left_layout.addWidget(window_group)

        output_group = QGroupBox("3  ·  OUTPUT LOCATION")
        og = QVBoxLayout(output_group)
        self.output_folder = DEFAULT_OUTPUT
        self.output_path = QLabel(str(self.output_folder))
        self.output_path.setWordWrap(True)
        self.output_path.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        og.addWidget(self.output_path)
        folder_buttons = QHBoxLayout()
        self.choose_folder_btn = QPushButton("Browse…")
        self.choose_folder_btn.clicked.connect(self.choose_folder)
        self.open_folder_btn = QPushButton("Open folder")
        self.open_folder_btn.clicked.connect(self.open_folder)
        folder_buttons.addWidget(self.choose_folder_btn)
        folder_buttons.addWidget(self.open_folder_btn)
        folder_buttons.addStretch(1)
        og.addLayout(folder_buttons)
        left_layout.addWidget(output_group)
        left_layout.addStretch(1)

        right_outer = QWidget()
        right_layout = QVBoxLayout(right_outer)
        right_layout.setContentsMargins(8, 0, 0, 0)
        right_layout.setSpacing(12)
        splitter.addWidget(right_outer)
        splitter.setSizes([580, 580])

        options_group = QGroupBox("4  ·  WEBP EXPORT SETTINGS")
        opts = QGridLayout(options_group)
        opts.setHorizontalSpacing(16)
        opts.setVerticalSpacing(12)
        self.capture_width = self._spin(160, 3840, 1280, " px")
        self.output_width = self._spin(160, 3840, 960, " px")
        self.fps = self._spin(10, 60, 24, " fps")
        self.max_megabytes = self._spin(1, 1000, 10, " MB")
        for row, (label, field) in enumerate((
            ("Render width", self.capture_width),
            ("WebP width", self.output_width),
            ("Motion rate", self.fps),
            ("Maximum file size", self.max_megabytes),
        )):
            opts.addWidget(QLabel(label), row // 2 * 2, row % 2)
            opts.addWidget(field, row // 2 * 2 + 1, row % 2)
        self.allow_lower_fps = QCheckBox("Allow lowering FPS to meet the size limit")
        self.allow_lower_fps.setChecked(False)
        opts.addWidget(self.allow_lower_fps, 4, 0, 1, 2)
        opts.setColumnStretch(0, 1)
        opts.setColumnStretch(1, 1)
        right_layout.addWidget(options_group)

        policy_group = QGroupBox("CLEAN CAPTURE POLICY")
        policy_layout = QVBoxLayout(policy_group)
        policy = QLabel(
            "The existing release_media.py renderer owns the rendering, replay and WebP encoding. "
            "Each job uses disposable scratch under logs/. Only the finished, verified WebP is copied to "
            "the selected folder. PNG frames, release manifests, failures and temporary files are removed. "
            "Source recordings and presets are never edited."
        )
        policy.setObjectName("muted")
        policy.setWordWrap(True)
        policy_layout.addWidget(policy)
        right_layout.addWidget(policy_group)

        log_group = QGroupBox("CAPTURE LOG")
        log_layout = QVBoxLayout(log_group)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setPlaceholderText("Canonical mode catalogue loading…")
        log_layout.addWidget(self.log)
        right_layout.addWidget(log_group, 1)
        
        bottom = QHBoxLayout()
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setMaximumHeight(13)
        self.progress.setValue(0)
        self.capture_btn = QPushButton("Render WebP")
        self.capture_btn.setObjectName("primary")
        self.capture_btn.setEnabled(False)
        self.capture_btn.clicked.connect(self.start_capture)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self.cancel_capture)
        bottom.addWidget(self.progress, 1)
        bottom.addWidget(self.capture_btn)
        bottom.addWidget(self.cancel_btn)
        layout.addLayout(bottom)
        self.statusBar().showMessage("Reading canonical visualizer presets…")

    def _set_style(self) -> None:
        self.setStyleSheet("""
            QMainWindow, QWidget { background: #171b24; color: #e4e9f3; font-size: 12px; }
            #heading { color: #f2f5ff; font-size: 24px; font-weight: 800; }
            #intro, #muted { color: #a8b4c9; }
            QGroupBox { font-weight: 700; color: #b8c8e8; border: 1px solid #3e485b;
                margin-top: 13px; border-radius: 8px; padding: 11px; }
            QGroupBox::title { subcontrol-origin: margin; left: 13px; padding: 0 7px; }
            QPushButton { background: #303c54; color: #eaf0fb; border: 1px solid #647592;
                border-radius: 6px; padding: 7px 10px; min-height: 28px; }
            QPushButton:hover { background: #40516f; }
            QPushButton:disabled { background: #252b36; color: #727d8f; }
            #primary { background: #365b82; border: 1px solid #8ab5e5; font-weight: 700; }
            QSpinBox, QDoubleSpinBox, QComboBox, QPlainTextEdit {
                background: #202836; color: #f0f4fa; border: 1px solid #4a5770;
                border-radius: 5px; padding: 5px; min-height: 25px; }
            QComboBox::drop-down { border: none; width: 21px; }
            QComboBox QAbstractItemView { background: #202836; color: #f0f4fa; selection-background-color: #486184; }
            QProgressBar { background: #242d3b; border: 1px solid #4a5770; border-radius: 5px; }
            QProgressBar::chunk { background: #73a7db; }
            QCheckBox { spacing: 8px; }
            QSplitter::handle { background: #2c3546; }
        """)

    def _busy(self) -> bool:
        return self._worker is not None and self._worker.isRunning()

    def refresh_catalogue(self) -> None:
        if self._busy() or self._catalogue_worker and self._catalogue_worker.isRunning():
            return
        self.reload_catalogue_btn.setEnabled(False)
        self.capture_btn.setEnabled(False)
        self.log.appendPlainText("Reading visualizer modes and curated presets from release_media.py…")
        worker = CatalogueLoader()
        self._catalogue_worker = worker
        worker.loaded.connect(self._catalogue_ready)
        worker.failed.connect(self._catalogue_failed)
        worker.finished.connect(lambda: self.reload_catalogue_btn.setEnabled(True))
        worker.start()

    def _catalogue_ready(self, cases: list[dict]) -> None:
        previous_mode = self.mode_combo.currentData()
        previous_preset = self.preset_combo.currentData()
        self._catalogue = cases
        by_mode: dict[str, str] = {}
        for case in cases:
            by_mode.setdefault(case["identity"], case["identity"].replace("_", " ").title())
        self.mode_combo.blockSignals(True)
        self.mode_combo.clear()
        for mode, display in sorted(by_mode.items(), key=lambda item: item[1].casefold()):
            self.mode_combo.addItem(display, mode)
        if previous_mode:
            idx = self.mode_combo.findData(previous_mode)
            if idx >= 0:
                self.mode_combo.setCurrentIndex(idx)
        self.mode_combo.blockSignals(False)
        self._fill_presets()
        if previous_preset:
            idx = self.preset_combo.findData(previous_preset)
            if idx >= 0:
                self.preset_combo.setCurrentIndex(idx)
        self.capture_btn.setEnabled(bool(cases) and bool(self.recording_combo.count()) and not self._busy())
        self.log.appendPlainText(f"Found {len(by_mode)} visualizers and {len(cases)} curated presets.")
        self.statusBar().showMessage("Ready to render using the production offscreen renderer.")

    def _catalogue_failed(self, error: str) -> None:
        self._catalogue.clear()
        self.mode_combo.clear()
        self.preset_combo.clear()
        self.capture_btn.setEnabled(False)
        self.log.appendPlainText("MODE DISCOVERY FAILED: " + error)
        self.statusBar().showMessage("Could not load the canonical visualizer list.")

    def _fill_presets(self, *_args) -> None:
        mode = self.mode_combo.currentData()
        self.preset_combo.clear()
        for case in self._catalogue:
            if case["identity"] == mode:
                self.preset_combo.addItem(f"{case['label']}  ·  P{int(case['preset']) + 1}", case["variant"])

    def refresh_recordings(self) -> None:
        if self._busy():
            return
        prior = self.recording_combo.currentData()
        self.recording_combo.clear()
        for path in available_recordings():
            self.recording_combo.addItem(path.name, str(path))
            self.recording_combo.setItemData(self.recording_combo.count()-1, str(path), Qt.ItemDataRole.ToolTipRole)
        if prior:
            idx = self.recording_combo.findData(prior)
            if idx >= 0:
                self.recording_combo.setCurrentIndex(idx)
        if not self.recording_combo.count():
            self.recording_combo.addItem("No recordings found in logs/visualizer_recordings", None)
        self.capture_btn.setEnabled(bool(self._catalogue) and bool(self.recording_combo.currentData()) and not self._busy())

    def choose_folder(self) -> None:
        chosen = QFileDialog.getExistingDirectory(self, "Choose WebP output folder", str(self.output_folder))
        if chosen:
            self.output_folder = Path(chosen)
            self.output_path.setText(str(self.output_folder))

    def open_folder(self) -> None:
        self.output_folder.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.output_folder.resolve())))

    def start_capture(self) -> None:
        if self._busy():
            return
        mode = self.mode_combo.currentData()
        variant = self.preset_combo.currentData()
        recording_path = self.recording_combo.currentData()
        try:
            if not mode or not variant or not recording_path:
                raise CaptureError("Select a visualizer, curated preset and recorded music clip first.")
            options = CaptureOptions(
                identity=str(mode), variant=str(variant), recording=Path(recording_path),
                start_seconds=self.start_seconds.value(),
                duration_seconds=self.duration_seconds.value(),
                fps=self.fps.value(), capture_width=self.capture_width.value(),
                output_width=self.output_width.value(),
                max_bytes=self.max_megabytes.value() * 1_000_000,
                destination=self.output_folder,
                accept_reduced_fps=self.allow_lower_fps.isChecked(),
            )
            options.validate()
        except (CaptureError, ValueError, OSError) as exc:
            QMessageBox.warning(self, "Capture settings", str(exc))
            return
        self.log.clear()
        self.log.appendPlainText(
            f"{mode} / {variant} · {Path(recording_path).name}\n"
            f"Window: {options.start_seconds:.2f}–{options.start_seconds + options.duration_seconds:.2f}s · "
            f"requested {options.fps} fps · {options.output_width}px · cap {options.max_bytes:,} bytes\n"
            "Offscreen engine: release_media.py. No source settings changed.\n"
        )
        self.reload_catalogue_btn.setEnabled(False)
        self.reload_recordings_btn.setEnabled(False)
        self.capture_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.progress.setRange(0, 0)
        self.statusBar().showMessage("Rendering and validating…")
        self._worker = CaptureWorker(options)
        self._worker.log_line.connect(self.log.appendPlainText)
        self._worker.finished_capture.connect(self._capture_succeeded)
        self._worker.failed.connect(self._capture_failed)
        self._worker.cancelled_capture.connect(self._capture_cancelled)
        self._worker.finished.connect(self._capture_done)
        self._worker.start()

    def cancel_capture(self) -> None:
        if self._busy():
            self._worker.cancel()
            self.cancel_btn.setEnabled(False)
            self.statusBar().showMessage("Cancelling and cleaning scratch…")

    def _capture_succeeded(self, result: dict) -> None:
        self._last_output = Path(result["output_path"])
        self.log.appendPlainText(
            f"\nSUCCESS: {self._last_output}\n"
            f"{result['frames']} frames · {result['duration_ms'] / 1000:.3f}s · "
            f"{result['fps']} fps · {result['bytes']:,} bytes.\n"
            "All intermediate frames and manifests cleaned."
        )
        self.progress.setRange(0, 100)
        self.progress.setValue(100)
        self.statusBar().showMessage(f"WebP saved: {self._last_output.name}")

    def _capture_failed(self, message: str) -> None:
        self.log.appendPlainText("\nFAILED (no output published): " + message)
        self.statusBar().showMessage("Capture failed; temporary frame directory cleaned.")
        self.progress.setRange(0, 100)
        self.progress.setValue(0)

    def _capture_cancelled(self, message: str) -> None:
        self.log.appendPlainText("\nCANCELLED: " + message)
        self.statusBar().showMessage("Cancelled; temporary frame directory cleaned.")
        self.progress.setRange(0, 100)
        self.progress.setValue(0)

    def _capture_done(self) -> None:
        self.cancel_btn.setEnabled(False)
        self.reload_catalogue_btn.setEnabled(True)
        self.reload_recordings_btn.setEnabled(True)
        self.capture_btn.setEnabled(bool(self._catalogue) and bool(self.recording_combo.currentData()))

    def closeEvent(self, event) -> None:
        if self._busy():
            response = QMessageBox.question(
                self, "Capture running", "Cancel the capture and close? Temporary frames will be cleaned.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if response != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self._worker.cancel()
            if not self._worker.wait(8000):
                QMessageBox.warning(self, "Capture still closing", "The renderer has not finished stopping. Try again shortly.")
                event.ignore()
                return
        if self._catalogue_worker is not None and self._catalogue_worker.isRunning():
            self._catalogue_worker.wait(2000)
            if self._catalogue_worker.isRunning():
                event.ignore()
                return
        event.accept()


def main() -> int:
    configure_windows_dpi()
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName("SRPSS Visualizer Capture Studio")
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
