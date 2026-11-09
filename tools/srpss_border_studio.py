"""SRPSS Border Studio: Windows-friendly, per-monitor-DPI-aware drag/drop GUI."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal, QSize
from PySide6.QtGui import QPixmap, QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QCheckBox, QComboBox, QFileDialog, QGridLayout, QGroupBox,
    QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMainWindow, QMessageBox,
    QPlainTextEdit, QProgressBar, QPushButton, QSizePolicy, QScrollArea, QFrame, QSpinBox, QSplitter,
    QVBoxLayout, QWidget,
)

from srpss_border_core import (
    AssetError,
    Cancelled,
    Settings,
    SlideshowSettings,
    inspect_source,
    process_asset,
    process_slideshow,
    SUPPORTED_SUFFIXES,
)


def configure_windows_dpi():
    """Ask Windows for Per Monitor v2; Qt 6 scales widgets automatically."""
    if sys.platform != "win32":
        return
    import ctypes
    try:
        # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except Exception:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            pass  # Qt6 handles HiDPI even when OS policy prohibits changing this


class DropList(QListWidget):
    pathsDropped = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        # Accept external file drops AND genuine internal drag-reordering.
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.setDragEnabled(True)
        self.setDropIndicatorShown(True)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setAlternatingRowColors(True)
        self.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.setToolTip("Drop images to add them; drag an existing row to change playback order. Alt+Up/Down also moves a row.")

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.source() is self:
            super().dragEnterEvent(event)
            return
        if event.mimeData().hasUrls() and any(
            u.isLocalFile() and Path(u.toLocalFile()).suffix.lower() in SUPPORTED_SUFFIXES | {".zip"}
            for u in event.mimeData().urls()
        ):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.source() is self:
            super().dragMoveEvent(event)
            return
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent):
        if event.source() is self:
            # Qt moves QListWidgetItems with their UserRole (full source path) intact.
            super().dropEvent(event)
            return
        paths = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
        self.pathsDropped.emit(paths)
        event.acceptProposedAction()

    def keyPressEvent(self, event):
        if event.modifiers() == Qt.KeyboardModifier.AltModifier and event.key() in (
            Qt.Key.Key_Up, Qt.Key.Key_Down
        ):
            row = self.currentRow()
            dest = row + (-1 if event.key() == Qt.Key.Key_Up else 1)
            if 0 <= row < self.count() and 0 <= dest < self.count():
                moved = self.takeItem(row)
                self.insertItem(dest, moved)
                self.setCurrentRow(dest)
            event.accept()
            return
        super().keyPressEvent(event)


class Processor(QThread):
    logMessage = Signal(str)
    assetFinished = Signal(dict)
    failed = Signal(str)
    batchDone = Signal(int, int, bool)

    def __init__(self, sources: list[str], output_dir: str, settings: Settings,
                 slideshow: SlideshowSettings | None = None):
        super().__init__()
        self.sources = sources
        self.output_dir = output_dir
        self.settings = settings
        self.slideshow = slideshow or SlideshowSettings(enabled=False)
        self.stop_requested = False

    def cancel(self):
        self.stop_requested = True

    def run(self):
        successes = 0
        failures = 0
        if self.slideshow.enabled:
            self.logMessage.emit(f"\n[queue slideshow] {len(self.sources)} source image(s)")
            try:
                result = process_slideshow(
                    self.sources,
                    self.output_dir,
                    self.settings,
                    self.slideshow,
                    notify=self.logMessage.emit,
                    cancelled=lambda: self.stop_requested,
                )
                successes = 1
                self.assetFinished.emit(result)
            except Cancelled:
                pass
            except Exception as exc:
                failures = 1
                self.failed.emit(str(exc))
            self.batchDone.emit(successes, failures, self.stop_requested)
            return

        for index, source in enumerate(self.sources, 1):
            if self.stop_requested:
                break
            self.logMessage.emit(f"\n[{index}/{len(self.sources)}] {Path(source).name}")
            try:
                result = process_asset(
                    source, self.output_dir, self.settings,
                    notify=self.logMessage.emit,
                    cancelled=lambda: self.stop_requested,
                )
                successes += 1
                self.assetFinished.emit(result)
            except Cancelled:
                break
            except Exception as exc:
                failures += 1
                self.failed.emit(f"{Path(source).name}: {exc}")
        self.batchDone.emit(successes, failures, self.stop_requested)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SRPSS Border Studio  |  Frame Preservation First")
        # Use available horizontal space instead of forcing tall, compressed forms.
        # Keep the window inside the current monitor's logical (DPI-scaled) desktop.
        screen = QApplication.primaryScreen()
        if screen is not None:
            available = screen.availableGeometry()
            self.resize(min(1430, max(900, available.width() - 70)),
                        min(900, max(640, available.height() - 70)))
        else:
            self.resize(1330, 860)
        self.setMinimumSize(QSize(900, 640))
        self.setAcceptDrops(True)
        self.worker: Processor | None = None
        self.last_output: str | None = None
        self._make_ui()
        self._set_style()

    def _make_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(18, 16, 18, 16)
        outer.setSpacing(10)

        heading = QLabel("SRPSS BORDER STUDIO")
        heading.setObjectName("heading")
        outer.addWidget(heading)
        explainer = QLabel(
            "Drop source images or a ZIP containing one image. Animate WebP/GIF without guessing frame timing. "
            "Still-image queues can also be assembled into one bordered crossfade WebP. Outputs are published only after validation."
        )
        explainer.setWordWrap(True)
        explainer.setObjectName("intro")
        outer.addWidget(explainer)

        content = QSplitter(Qt.Orientation.Horizontal)
        outer.addWidget(content, 1)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 8, 0)
        left_layout.setSpacing(10)
        content.addWidget(left)

        queue_group = QGroupBox("1  ·  SOURCE QUEUE")
        queue_layout = QVBoxLayout(queue_group)
        self.queue = DropList()
        self.queue.pathsDropped.connect(self.add_paths)
        self.queue.currentItemChanged.connect(self.show_source_preview)
        queue_layout.addWidget(self.queue, 1)
        actions = QHBoxLayout()
        self.add_btn = QPushButton("Add files…")
        self.remove_btn = QPushButton("Remove selected")
        self.clear_btn = QPushButton("Clear")
        self.add_btn.clicked.connect(self.pick_sources)
        self.remove_btn.clicked.connect(self.remove_selected)
        self.clear_btn.clicked.connect(self.queue.clear)
        actions.addWidget(self.add_btn)
        actions.addWidget(self.remove_btn)
        actions.addWidget(self.clear_btn)
        queue_layout.addLayout(actions)
        queue_hint = QLabel("Drag rows to reorder · Top → bottom is slideshow playback order · Alt+↑/↓ also works")
        queue_hint.setObjectName("muted")
        queue_hint.setWordWrap(True)
        queue_layout.addWidget(queue_hint)
        left_layout.addWidget(queue_group, 2)

        output_group = QGroupBox("2  ·  OUTPUT")
        output_layout = QVBoxLayout(output_group)
        folder_row = QHBoxLayout()
        self.folder_label = QLabel(str(Path(__file__).resolve().parents[1] / "assets" / "temp"))
        self.folder_label.setWordWrap(True)
        self.folder_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        folder_row.addWidget(self.folder_label, 1)
        self.folder_btn = QPushButton("Browse…")
        self.folder_btn.clicked.connect(self.pick_output_folder)
        folder_row.addWidget(self.folder_btn)
        self.open_btn = QPushButton("Open folder")
        self.open_btn.clicked.connect(self.open_output_folder)
        folder_row.addWidget(self.open_btn)
        output_layout.addLayout(folder_row)
        self.make_zip = QCheckBox("Create ZIP with WebP/PNG and processing report")
        self.make_zip.setChecked(True)
        output_layout.addWidget(self.make_zip)
        left_layout.addWidget(output_group)

        preview_group = QGroupBox("SELECTED SOURCE / LAST RESULT")
        preview_layout = QVBoxLayout(preview_group)
        self.preview = QLabel("Image preview")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumHeight(128)
        self.preview.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.preview.setStyleSheet("border: 1px dashed #566077; background: #11151e; border-radius: 6px;")
        preview_layout.addWidget(self.preview, 1)
        self.preview_details = QLabel("No source selected")
        self.preview_details.setWordWrap(True)
        self.preview_details.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        preview_layout.addWidget(self.preview_details)
        left_layout.addWidget(preview_group, 2)

        # Make settings scroll rather than crush controls when the window is short
        # or a 1440p monitor is running at 150-200% DPI scaling.
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(8, 0, 10, 0)
        right_layout.setSpacing(10)
        right_scroll = QScrollArea()
        right_scroll.setFrameShape(QFrame.Shape.NoFrame)
        right_scroll.setWidgetResizable(True)
        right_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        right_scroll.setWidget(right)
        content.addWidget(right_scroll)
        content.setStretchFactor(0, 5)
        content.setStretchFactor(1, 7)
        content.setSizes([570, 760])

        settings_group = QGroupBox("3  ·  PRESERVATION & COMPRESSION")
        grid = QGridLayout(settings_group)
        grid.setVerticalSpacing(9)
        grid.setHorizontalSpacing(12)

        self.scale_start = self._spin(10, 100, 90, "%")
        self.scale_min = self._spin(10, 100, 50, "%")
        self.scale_step = self._spin(1, 25, 5, "%")
        self.quality_pref = self._spin(50, 100, 96, "")
        self.quality_min = self._spin(50, 100, 90, "")
        self.limit = self._spin(1, 100, 10, " MB")

        # Two compact field columns instead of seven long rows. Crucially, each
        # editor has a fixed vertical size: QGridLayout cannot squash it to zero.
        fields = [
            ("Start at", self.scale_start),
            ("Minimum size", self.scale_min),
            ("Resize increment", self.scale_step),
            ("Preferred WebP quality", self.quality_pref),
            ("Minimum WebP quality", self.quality_min),
            ("Max file size", self.limit),
        ]
        for index, (label, editor) in enumerate(fields):
            self._add_setting_field(grid, label, editor, index // 2, index % 2)

        self.prefer_quality = QCheckBox("Prefer image quality; shrink dimensions before lowering quality")
        self.prefer_quality.setChecked(True)
        self.border_detect = QCheckBox("Replace existing SRPSS border (no double-border)")
        self.border_detect.setChecked(True)
        self.visual_check = QCheckBox("Verify decoded sample-frame quality")
        self.visual_check.setChecked(True)
        self.still_format = QComboBox()
        self.still_format.addItems(["PNG (lossless)", "WebP (high quality)"])
        self._add_setting_field(grid, "Still image output", self.still_format, 3, 0)
        grid.addWidget(self.prefer_quality, 4, 0, 1, 2)
        grid.addWidget(self.border_detect, 5, 0, 1, 2)
        grid.addWidget(self.visual_check, 6, 0, 1, 2)

        info = QLabel(
            "Existing animation frames and timing are never modified. "
            "If the size cap cannot be met above your minimum quality/scale, processing fails."
        )
        info.setWordWrap(True)
        info.setObjectName("muted")
        grid.addWidget(info, 7, 0, 1, 2)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        right_layout.addWidget(settings_group)

        slideshow_group = QGroupBox("4  ·  QUEUE SLIDESHOW")
        slide_grid = QGridLayout(slideshow_group)
        slide_grid.setVerticalSpacing(9)
        slide_grid.setHorizontalSpacing(12)
        self.assemble_queue = QCheckBox("Assemble the whole queue into one animated WebP")
        self.assemble_queue.toggled.connect(self.on_mode_changed)
        self.hold_ms = self._spin(0, 120000, 2000, " ms")
        self.fade_ms = self._spin(0, 60000, 400, " ms")
        self.slide_fps = self._spin(1, 60, 24, " fps")
        self.loop_back = QCheckBox("Crossfade the last image back into the first")
        self.loop_back.setChecked(True)
        slide_grid.addWidget(self.assemble_queue, 0, 0, 1, 2)
        self._add_setting_field(slide_grid, "Hold each still", self.hold_ms, 1, 0)
        self._add_setting_field(slide_grid, "Crossfade duration", self.fade_ms, 1, 1)
        self._add_setting_field(slide_grid, "Slideshow FPS", self.slide_fps, 2, 0)
        slide_grid.addWidget(self.loop_back, 3, 0, 1, 2)
        slide_note = QLabel(
            "Still-image queue only. Sources are normalized to the first image's content size "
            "without stretching, then bordered and crossfaded."
        )
        slide_note.setWordWrap(True)
        slide_note.setObjectName("muted")
        slide_grid.addWidget(slide_note, 4, 0, 1, 2)
        slide_grid.setColumnStretch(0, 1)
        slide_grid.setColumnStretch(1, 1)
        right_layout.addWidget(slideshow_group)

        log_group = QGroupBox("PROCESS LOG")
        log_layout = QVBoxLayout(log_group)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMinimumHeight(130)
        self.log.setMaximumHeight(210)
        self.log.setPlaceholderText("Source analysis and verification details will appear here.")
        log_layout.addWidget(self.log)
        right_layout.addWidget(log_group)
        right_layout.addStretch(1)

        bottom = QHBoxLayout()
        self.progress = QProgressBar()
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setMaximumHeight(13)
        bottom.addWidget(self.progress, 1)
        self.start_btn = QPushButton("Process queue")
        self.start_btn.setObjectName("primary")
        self.start_btn.clicked.connect(self.start_processing)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self.cancel_processing)
        bottom.addWidget(self.start_btn)
        bottom.addWidget(self.cancel_btn)
        outer.addLayout(bottom)
        self.output_dir: str | None = str(Path(__file__).resolve().parents[1] / "assets" / "temp")
        self._last_preview_pixmap = None
        self.on_mode_changed(False)
        self.statusBar().showMessage("Ready. 2 px transparent padding · 2 px black outline · 3 px radius")

    @staticmethod
    def _add_setting_field(layout: QGridLayout, label: str, editor: QWidget, row: int, column: int):
        field = QWidget()
        field_layout = QVBoxLayout(field)
        field_layout.setContentsMargins(0, 0, 0, 0)
        field_layout.setSpacing(4)
        field_label = QLabel(label)
        field_label.setObjectName("fieldLabel")
        field_layout.addWidget(field_label)
        editor.setMinimumHeight(36)
        editor.setMaximumHeight(40)
        editor.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        field_layout.addWidget(editor)
        layout.addWidget(field, row, column)

    @staticmethod
    def _spin(low, high, value, suffix):
        spin = QSpinBox()
        spin.setRange(low, high)
        spin.setValue(value)
        spin.setSuffix(suffix)
        spin.setMinimumHeight(36)
        spin.setMaximumHeight(40)
        spin.setMinimumWidth(110)
        return spin

    def _set_style(self):
        self.setStyleSheet("""
            QMainWindow, QWidget { background: #171b24; color: #e4e9f3; font-size: 12px; }
            #heading { color: #f2f5ff; font-size: 24px; font-weight: 800; }
            #intro, #muted { color: #a8b4c9; }
            #fieldLabel { color: #c4cee0; }
            QScrollArea { background: transparent; border: none; }
            QGroupBox { font-weight: 700; color: #b8c8e8; border: 1px solid #3e485b;
                margin-top: 13px; border-radius: 8px; padding: 10px; }
            QGroupBox::title { subcontrol-origin: margin; left: 13px; padding: 0 7px; }
            QPushButton { background: #303c54; color: #eaf0fb; border: 1px solid #647592;
                border-radius: 6px; padding: 7px 10px; }
            QPushButton:hover { background: #40516f; }
            QPushButton:disabled { background: #252b36; color: #727d8f; }
            #primary { background: #365b82; border: 1px solid #8ab5e5; font-weight: 700; }
            QSpinBox, QComboBox, QListWidget, QPlainTextEdit { background: #202836; color: #f0f4fa;
                border: 1px solid #4a5770; border-radius: 5px; padding: 5px; }
            QListWidget::item { padding: 6px; }
            QListWidget::item:selected { background: #486184; }
            QProgressBar { background: #242d3b; border: 1px solid #4a5770; border-radius: 5px; }
            QProgressBar::chunk { background: #73a7db; }
            QCheckBox { spacing: 8px; }
            QSplitter::handle { background: #2c3546; }
        """)

    def on_mode_changed(self, enabled: bool):
        # A 4K still-image slideshow has far more information than a single still.
        # Give slideshow batches a useful 25% floor while preserving the regular
        # tool's existing 50% floor and any manual edits in either mode.
        if not hasattr(self, "_scale_mode"):
            self._scale_mode = False
            self._min_scale_by_mode = {False: self.scale_min.value(), True: 25}
        if enabled != self._scale_mode:
            self._min_scale_by_mode[self._scale_mode] = self.scale_min.value()
            self.scale_min.setValue(self._min_scale_by_mode[enabled])
            self._scale_mode = enabled
        for widget in (self.hold_ms, self.fade_ms, self.slide_fps, self.loop_back):
            widget.setEnabled(enabled)
        self.still_format.setEnabled(not enabled)
        self.start_btn.setText("Build slideshow" if enabled else "Process queue")

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() and any(
            u.isLocalFile() and Path(u.toLocalFile()).suffix.lower() in SUPPORTED_SUFFIXES | {".zip"}
            for u in event.mimeData().urls()
        ):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            self.add_paths([u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()])
            event.acceptProposedAction()
        else:
            event.ignore()

    def add_paths(self, paths: list[str]):
        known = {self.queue.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.queue.count())}
        valid = []
        for p in paths:
            path = Path(p)
            if not path.is_file() or path.suffix.lower() not in SUPPORTED_SUFFIXES | {".zip"}:
                continue
            absolute = str(path.resolve())
            if absolute in known:
                continue
            known.add(absolute)
            item = QListWidgetItem(path.name)
            item.setData(Qt.ItemDataRole.UserRole, absolute)
            item.setToolTip(absolute)
            self.queue.addItem(item)
            valid.append(path)

        if self.queue.count() and not self.queue.currentItem():
            self.queue.setCurrentRow(0)
        if not valid:
            self.statusBar().showMessage("No new supported files added.")

    def pick_sources(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Add images / ZIPs", str(Path.home()),
            "Images and ZIPs (*.webp *.png *.gif *.jpg *.jpeg *.zip);;All Files (*)")
        self.add_paths(files)

    def pick_output_folder(self):
        path = QFileDialog.getExistingDirectory(self, "Choose output folder", self.output_dir or str(Path.home()))
        if path:
            self.output_dir = path
            self.folder_label.setText(path)

    def open_output_folder(self):
        if not self.output_dir:
            return
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        folder = Path(self.output_dir)
        folder.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder.resolve())))

    def remove_selected(self):
        for item in self.queue.selectedItems():
            self.queue.takeItem(self.queue.row(item))

    def _update_preview(self, img_path: str):
        pixmap = QPixmap(img_path)
        if pixmap.isNull():
            self.preview.setText("Preview unavailable")
            self._last_preview_pixmap = None
            return
        self._last_preview_pixmap = pixmap
        self._scale_preview()

    def _scale_preview(self):
        if self._last_preview_pixmap is None:
            return
        target = self.preview.size() - QSize(14, 14)
        if target.width() > 0 and target.height() > 0:
            self.preview.setPixmap(self._last_preview_pixmap.scaled(
                target, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._scale_preview()

    def show_source_preview(self, item: QListWidgetItem | None, old=None):
        if item is None:
            self.preview.setText("Drop images here")
            self.preview_details.setText("No source selected")
            return
        path = item.data(Qt.ItemDataRole.UserRole)
        try:
            info = inspect_source(path)
            from PIL import Image
            import io
            original = Image.open(io.BytesIO(info.payload))
            original.seek(0)
            rgba = original.convert("RGBA")
            rgba.thumbnail((1024, 512), Image.Resampling.LANCZOS)
            from PySide6.QtGui import QImage
            img_bytes = rgba.tobytes("raw", "RGBA")
            qimg = QImage(img_bytes, rgba.width, rgba.height, rgba.width * 4, QImage.Format.Format_RGBA8888)
            self._last_preview_pixmap = QPixmap.fromImage(qimg.copy())
            self._scale_preview()
            self.preview_details.setText(
                f"{info.name}  ·  {info.width}×{info.height}  ·  {info.frame_count} frame(s)  ·  "
                f"{info.duration_ms/1000:.3f}s  ·  {info.bytes_size:,} bytes  ·  "
                f"existing border: {'yes' if info.border_present else 'no'}"
            )
        except Exception as exc:
            self.preview.setText("Preview unavailable")
            self.preview_details.setText(str(exc))

    def current_settings(self) -> Settings:
        cfg = Settings(
            scale_percent=self.scale_start.value(),
            min_scale_percent=self.scale_min.value(),
            scale_step_percent=self.scale_step.value(),
            preferred_quality=self.quality_pref.value(),
            minimum_quality=self.quality_min.value(),
            max_bytes=self.limit.value() * 1_000_000,
            replace_existing_border=self.border_detect.isChecked(),
            prefer_quality_over_pixels=self.prefer_quality.isChecked(),
            strict_visual_check=self.visual_check.isChecked(),
            make_zip=self.make_zip.isChecked(),
            still_format="PNG" if self.still_format.currentIndex() == 0 else "WEBP",
        )
        cfg.validate()
        return cfg

    def current_slideshow_settings(self) -> SlideshowSettings:
        cfg = SlideshowSettings(
            enabled=self.assemble_queue.isChecked(),
            hold_ms=self.hold_ms.value(),
            fade_ms=self.fade_ms.value(),
            fps=self.slide_fps.value(),
            loop_back_to_first=self.loop_back.isChecked(),
        )
        cfg.validate()
        return cfg

    def start_processing(self):
        if self.worker and self.worker.isRunning():
            return
        sources = [self.queue.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.queue.count())]
        if not sources:
            QMessageBox.information(self, "No images", "Drop images into the source queue first.")
            return
        try:
            config = self.current_settings()
            slideshow = self.current_slideshow_settings()
            if slideshow.enabled and len(sources) < 2:
                raise AssetError("Queue slideshow mode requires at least two still-image sources.")
            if not self.output_dir:
                raise AssetError("Select an output folder first.")
            Path(self.output_dir).mkdir(parents=True, exist_ok=True)
        except (AssetError, OSError) as exc:
            QMessageBox.warning(self, "Settings error", str(exc))
            return
        self.log.clear()
        if slideshow.enabled:
            self.log.appendPlainText("Queue slideshow mode: ON. Still-image queue → one crossfade WebP.")
            self.log.appendPlainText("No silent fps guessing. Crossfade frames are generated explicitly and validated.")
        else:
            self.log.appendPlainText("Strict preservation mode: ON. No inferred FPS, no silent frame loss.")
        self.worker = Processor(sources, self.output_dir, config, slideshow)
        self.worker.logMessage.connect(self.log.appendPlainText)
        self.worker.assetFinished.connect(self.on_asset_finished)
        self.worker.failed.connect(self.on_failed)
        self.worker.batchDone.connect(self.on_done)
        self.start_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.progress.setRange(0, 0)
        self.statusBar().showMessage("Processing and validating...")
        self.worker.start()

    def cancel_processing(self):
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.cancel_btn.setEnabled(False)
            self.statusBar().showMessage("Cancelling at next safe boundary...")

    def on_asset_finished(self, report: dict):
        self.last_output = report.get("zip_path", report["output_path"])
        self._update_preview(report["output_path"])
        if report.get("mode") == "queue_slideshow":
            self.preview_details.setText(
                f"LAST OUTPUT: {report['output_file']} · {report['frame_count']} frames · "
                f"{report['duration_ms']/1000:.3f}s · {report['output_size_bytes']:,} bytes · queue slideshow"
            )
        else:
            self.preview_details.setText(
                f"LAST OUTPUT: {report['output_file']} · {report['frame_count']} frames · "
                f"{report['duration_ms']/1000:.3f}s · {report['output_size_bytes']:,} bytes"
            )
        self.log.appendPlainText(f"PASS → {self.last_output}")
        self.log.appendPlainText(
            f"  {report['output_size_bytes']:,} bytes | {report['frame_count']} frames | "
            f"{report['duration_ms']/1000:.3f}s"
        )

    def on_failed(self, error: str):
        self.log.appendPlainText("FAILED (no artifact published): " + error)

    def on_done(self, successes: int, failures: int, was_cancelled: bool):
        self.progress.setRange(0, 100)
        self.progress.setValue(100 if successes and not failures and not was_cancelled else 0)
        self.start_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        status = f"{successes} succeeded, {failures} failed" + (", cancelled" if was_cancelled else "")
        self.statusBar().showMessage(status)
        self.log.appendPlainText("\nFinished: " + status)
        if successes and self.last_output:
            self.log.appendPlainText("Output folder: " + str(Path(self.last_output).parent))

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            answer = QMessageBox.question(
                self,
                "Processing running",
                "Cancel processing and close? Existing successful exports will remain.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self.worker.cancel()
            if not self.worker.wait(3000):
                QMessageBox.warning(self, "Still processing", "A WebP encode is still finishing. Cancel again after it stops.")
                event.ignore()
                return
        event.accept()


def main():
    configure_windows_dpi()
    # Qt6 supports per-monitor HiDPI scaling by default; PassThrough avoids rounding
    # problems when moving between 100%, 125%, 150% and 200% displays.
    from PySide6.QtGui import QGuiApplication
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setApplicationName("SRPSS Border Studio")
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    if len(sys.argv) > 1:
        window.add_paths(sys.argv[1:])
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
