"""Friendly 60-second loopback clip recorder. Run: python tools/music_recorder.py"""
from __future__ import annotations

import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QPointF, Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QApplication, QHBoxLayout, QLabel, QLineEdit, QListWidget, QMessageBox,
    QProgressBar, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from tools.visualizer_replay import record
from ui.settings_theme_runtime import get_active_settings_theme


def _color(token):
    return QColor(*get_active_settings_theme().color(token).as_tuple())


class SignalView(QWidget):
    """A bounded peak envelope drawn in Qt logical pixels, with no animation timer."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.peaks = ()
        self.setMinimumHeight(110)
        self.setAccessibleName("Recorded audio signal")

    def set_samples(self, samples):
        step = max(1, len(samples) // 100)
        self.peaks = tuple(min(1.0, max(abs(float(v)) for v in samples[i:i + step]))
                           for i in range(0, len(samples), step))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(_color("control.input.surface"))
        painter.drawRoundedRect(self.rect(), 12, 12)
        middle = self.height() / 2
        if self.peaks:
            painter.setPen(QPen(_color("text.tertiary"), 1))
            painter.drawLine(QPointF(16, middle), QPointF(self.width() - 16, middle))
            painter.setPen(QPen(_color("text.primary"), 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            width = self.width() - 32
            for i, peak in enumerate(self.peaks):
                x = 16 + width * i / max(1, len(self.peaks) - 1)
                height = max(1, peak * (middle - 16))
                painter.drawLine(QPointF(x, middle - height), QPointF(x, middle + height))
        else:
            painter.setPen(_color("text.secondary"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Your signal will appear here while recording")


class MusicRecorder(QWidget):
    def __init__(self):
        super().__init__()
        self.session = None
        self.setWindowTitle("SRPSS · Music clip recorder")
        self.resize(660, 730)
        self.setMinimumWidth(400)
        self._apply_style()
        shell = QVBoxLayout(self)
        shell.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        content = QWidget()
        scroll.setWidget(content)
        shell.addWidget(scroll)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(14)
        title = QLabel("Music clip recorder")
        title_font = QFont(self.font())
        title_font.setPointSizeF(23)
        title_font.setWeight(QFont.Weight.DemiBold)
        title.setFont(title_font)
        layout.addWidget(title)
        helper = QLabel("Play a track on your computer, name your clip, then record.\n"
                        "A full minute of system audio and visualizer events is saved automatically.")
        helper.setWordWrap(True)
        helper.setObjectName("secondary")
        layout.addWidget(helper)
        label = QLabel("Clip name")
        self.name = QLineEdit()
        label.setBuddy(self.name)
        self.name.setPlaceholderText("e.g. Quiet piano intro")
        self.name.setClearButtonEnabled(True)
        self.name.setMaxLength(140)
        layout.addWidget(label)
        layout.addWidget(self.name)
        self.destination = QLabel()
        self.destination.setObjectName("secondary")
        self.destination.setWordWrap(True)
        layout.addWidget(self.destination)
        self.signal = SignalView()
        layout.addWidget(self.signal)
        row = QHBoxLayout()
        self.status = QLabel("Ready when you are")
        self.status.setWordWrap(True)
        self.remaining = QLabel("01:00")
        clock_font = QFont(self.font())
        clock_font.setPointSizeF(22)
        self.remaining.setFont(clock_font)
        row.addWidget(self.status, 1)
        row.addWidget(self.remaining)
        layout.addLayout(row)
        self.progress = QProgressBar()
        self.progress.setRange(0, 60_000)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        layout.addWidget(self.progress)
        self.details = QLabel("60 seconds · Full waveform history · Energy, spectrum & musical events")
        self.details.setWordWrap(True)
        self.details.setObjectName("secondary")
        layout.addWidget(self.details)
        buttons = QHBoxLayout()
        self.start_button = QPushButton("Record 60-second clip")
        self.start_button.setObjectName("primary")
        self.start_button.clicked.connect(self.start_recording)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self.cancel_recording)
        buttons.addWidget(self.start_button, 1)
        buttons.addWidget(self.cancel_button)
        layout.addLayout(buttons)
        library_row = QHBoxLayout()
        library_row.addWidget(QLabel("Your clips"), 1)
        open_button = QPushButton("Open folder")
        open_button.clicked.connect(self.open_folder)
        library_row.addWidget(open_button)
        layout.addLayout(library_row)
        self.library = QListWidget()
        self.library.setMinimumHeight(95)
        self.library.setMaximumHeight(140)
        self.library.setAccessibleName("Saved music clips")
        layout.addWidget(self.library, 1)
        self.name.textChanged.connect(self._name_changed)
        self.name.returnPressed.connect(self.start_recording)
        self._refresh_library()
        self._name_changed()

    def _apply_style(self):
        def css(token):
            return _color(token).name()

        self.setStyleSheet(f"""
            QWidget {{ background: {css('bucket.open.surface')}; color: {css('text.primary')}; }}
            QLabel#secondary {{ color: {css('text.secondary')}; }}
            QLineEdit, QListWidget {{ background: {css('control.input.surface')};
                border: 1px solid {css('bucket.closed.border')}; border-radius: 8px; padding: 9px; }}
            QLineEdit:focus {{ border-color: {css('control.input.border')}; }}
            QPushButton {{ background: {css('bucket.closed.surface')}; border: 1px solid {css('bucket.closed.border')};
                border-radius: 8px; padding: 10px 16px; }}
            QPushButton:hover {{ background: {css('bucket.closed.hover_surface')}; }}
            QPushButton#primary {{ background: {css('text.primary')}; color: {css('bucket.open.surface')}; font-weight: 600; }}
            QPushButton:disabled {{ background: {css('control.input.surface')}; color: {css('text.disabled')}; }}
            QPushButton#primary:disabled {{ background: {css('bucket.closed.surface')}; color: {css('text.disabled')}; }}
            QProgressBar {{ border: none; border-radius: 4px; background: {css('control.input.surface')}; max-height: 8px; }}
            QProgressBar::chunk {{ border-radius: 4px; background: {css('text.primary')}; }}
            QListWidget::item {{ padding: 4px; }}
            QScrollBar:vertical {{ background: {css('control.input.surface')}; width: 10px; margin: 0; }}
            QScrollBar::handle:vertical {{ background: {css('bucket.closed.hover_border')}; min-height: 28px; border-radius: 5px; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
        """)

    def _name_changed(self):
        try:
            name = record.clip_name(self.name.text())
            path = record.OUTPUT / f"{name}.jsonl"
            exists = path.exists()
            self.destination.setText(f"Already exists — choose another name: {path.name}" if exists
                                     else f"Saves as logs/visualizer_recordings/{path.name}")
            valid = not exists
        except ValueError as exc:
            self.destination.setText(str(exc) if self.name.text() else "Saved beside your other music clips")
            valid = False
        self.start_button.setEnabled(valid and not (self.session and self.session.active))

    def _refresh_library(self):
        self.library.clear()
        for path in sorted(record.OUTPUT.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True):
            self.library.addItem(f"{path.stem}    ·    {path.stat().st_size / (1024 * 1024):.1f} MB")

    def open_folder(self):
        record.OUTPUT.mkdir(parents=True, exist_ok=True)
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(record.OUTPUT))):
            self.status.setText(f"Could not open folder: {record.OUTPUT}")

    def start_recording(self):
        if not self.start_button.isEnabled():
            return
        self.progress.setValue(0)
        self.remaining.setText("01:00")
        self.signal.peaks = ()
        self.signal.update()
        self.status.setText("Connecting to system audio…")
        self.name.setEnabled(False)
        self.start_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        try:
            self.session = record.RecorderSession(self.name.text(), on_progress=self._progress,
                                                   on_finished=self._finished)
            self.session.start()
        except Exception as exc:
            self.status.setText(f"Could not start: {exc}")
            self.name.setEnabled(True)
            self.cancel_button.setEnabled(False)
            self._name_changed()

    def _progress(self, elapsed, samples, session):
        left = max(0, math.ceil(session.seconds - elapsed))
        self.remaining.setText(f"{left // 60:02d}:{left % 60:02d}")
        self.progress.setValue(min(60_000, round(elapsed * 1000)))
        self.signal.set_samples(samples)
        peak = max(abs(float(v)) for v in samples)
        self.status.setText("Recording · signal detected" if peak > 0.0001 else "Recording silence · check your music is playing")
        self.details.setText(f"{len(samples):,} samples/frame · {session._history.sample_rate:,} Hz · "
                             f"{session.frame_count:,} frames · {session.event_count + session.onset_count:,} events")

    def _finished(self, session):
        self.name.setEnabled(True)
        self.cancel_button.setEnabled(False)
        if session.error:
            self.status.setText(f"Recording failed: {session.error}")
        elif session.saved:
            self.status.setText(f"Saved {session.path.name}")
            self.progress.setValue(60_000)
            self.remaining.setText("00:00")
            self.details.setText(f"{session.frame_count:,} frames · {session.event_count:,} typed events · "
                                 f"{session.onset_count:,} onsets · longest frame gap {session.max_gap_s * 1000:.0f} ms")
            self._refresh_library()
        else:
            self.status.setText("Cancelled · no clip saved")
        self._name_changed()

    def cancel_recording(self):
        if self.session and self.session.active:
            self.session.cancel()

    def closeEvent(self, event):
        if self.session and self.session.active:
            answer = QMessageBox.question(self, "Discard this recording?",
                                          "Closing now discards the unfinished clip.",
                                          QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                                          QMessageBox.StandardButton.Cancel)
            if answer != QMessageBox.StandardButton.Discard:
                event.ignore()
                return
            self.session.cancel()
        event.accept()


def main():
    # Qt 6 handles per-monitor DPR; geometry and painter coordinates stay logical.
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    font = app.font()
    font.setPointSizeF(10)
    app.setFont(font)
    window = MusicRecorder()
    available = window.screen().availableGeometry()
    window.resize(min(window.width(), available.width() - 40), min(window.height(), available.height() - 64))
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
