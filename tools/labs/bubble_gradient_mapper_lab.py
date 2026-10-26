"""Two-endpoint Bubble gradient lab using the production renderer and shader.

Explicit immutable endpoints vary one renderer input; no Settings/preset writes,
mocked modules, extra clock or duplicated drawing. --capture writes the control
and wide/narrow/shifted production-shader fixtures, then retires all resources.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from core.gradient_geometry import project_linear_gradient
from core.settings.default_contract import require_canonical_default
from rendering.quick.visualizer.implementations.bubble import QuickBubbleRenderer
from rendering.quick.visualizer.render_host import QuickVisualizerRenderHost
from tools.labs.render_target import OffscreenRenderTarget
from tools.onboarding_preview_foundry import _build_spectrum_preview_snapshot
from ui.font_registration import ensure_custom_fonts
from ui.settings_theme import load_theme
from ui.widgets.visual_controls import GradientMapper


class _EndpointBubbleRenderer(QuickBubbleRenderer):
    endpoints = (.2, .8, .8, .2)
    content_aspect = 2.

    def _gradient_parameters(self, parameters, layout):
        self.content_aspect = layout.aspect_ratio
        return (*project_linear_gradient(self.endpoints, self.content_aspect), 0.)


class BubbleGradientMapperLab(QWidget):
    def __init__(self):
        super().__init__()
        self._target = self._host = None
        self.setWindowTitle("Bubble — two-node gradient prototype")
        config = dict(require_canonical_default("widgets.spotify_visualizer"))
        config["bubble_gradient_direction"] = "top_right"
        self._snapshot = _build_spectrum_preview_snapshot(width=720, height=360, mode="bubble", settings=config)
        self._renderer = renderer = _EndpointBubbleRenderer()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.addWidget(QLabel("Original Bubble — Dark / Light gradient endpoints"))
        intro = QLabel("Drag either node: the line sets direction; their separation sets the blend span.\n"
                       "Close nodes give a tighter transition. Moving both shifts the gradient.\n"
                       "Tab selects the other node; arrows move it; Shift makes fine adjustments.")
        intro.setWordWrap(True)
        layout.addWidget(intro)
        row = QHBoxLayout()
        self.mapper = GradientMapper()
        self.mapper.setToolTip("Drag Dark and Light independently. Their line sets direction and distance sets blend span.")
        row.addWidget(self.mapper)
        self.value_label = QLabel()
        row.addWidget(self.value_label)
        row.addStretch()
        layout.addLayout(row)
        self.preview = QLabel()
        self.preview.setFixedSize(720, 360)
        layout.addWidget(self.preview)
        self.mapper.valueChanged.connect(self._describe)
        self.mapper.valueCommitted.connect(self._on_commit)
        load_theme(self)
        try:
            self._target = OffscreenRenderTarget(720, 360, label="bubble-gradient-lab")
            self._host = QuickVisualizerRenderHost(renderer_factory=lambda _mode: renderer)
            self._describe(self.mapper.value())
            self._render(self.mapper.value())
        except Exception:
            self._retire()
            raise

    def _describe(self, value):
        dx, dy, lx, ly = value
        text = f"Dark: {dx:.2f}, {dy:.2f}\nLight: {lx:.2f}, {ly:.2f}"
        self.value_label.setText(text)
        self.mapper.setAccessibleDescription(text.replace("\n", ", "))

    def _render(self, value):
        self._renderer.endpoints = tuple(value)
        target = self._target
        width, height = target.width, target.height
        with target.current():
            target.bind()
            matrix = (2/width, 0, 0, 0, 0, -2/height, 0, 0, 0, 0, 1, 0, -1, 1, 0, 1)
            mode = self._host.render(snapshot=self._snapshot, viewport=(0, 0, width, height),
                                     logical_size=(float(width), float(height)), matrix_values=matrix)
            if mode != "bubble":
                raise RuntimeError("Production Bubble renderer was not admitted")
            pixels = target.read_rgba()
        image = QImage(pixels.data, width, height, width * 4, QImage.Format.Format_RGBA8888_Premultiplied).copy()
        self.preview.setPixmap(QPixmap.fromImage(image))
        self.mapper.setAspectRatio(self._renderer.content_aspect)

    def _on_commit(self, value):
        try:
            self._render(value)
        except Exception:
            self.preview.clear()
            self.mapper.setEnabled(False)
            self._retire()
            raise

    def _retire(self):
        if self._target is None or self._target.closed:
            return
        try:
            if self._host is not None:
                with self._target.current():
                    self._host.release_resources()
                self._host = None
        finally:
            self._target.close()

    def closeEvent(self, event):
        self._retire()
        super().closeEvent(event)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", type=Path)
    args = parser.parse_args()
    app = QApplication([])
    ensure_custom_fonts()
    lab = BubbleGradientMapperLab()
    try:
        lab.adjustSize()
        if args.capture:
            args.capture.parent.mkdir(parents=True, exist_ok=True)
            for name, endpoints in (("wide", (.1, .9, .9, .1)), ("narrow", (.4, .6, .6, .4)),
                                    ("shifted", (.05, .65, .45, .25))):
                lab.mapper.setValue(endpoints)
                lab._describe(endpoints)
                lab._render(endpoints)
                if not lab.preview.pixmap().save(str(args.capture.with_name(name + ".png"))):
                    raise RuntimeError("Gradient fixture capture failed")
            lab.mapper.setValue((.2, .8, .8, .2))
            lab._describe(lab.mapper.value())
            lab._render(lab.mapper.value())
            lab.ensurePolished()
            for widget in reversed([lab, *lab.findChildren(QWidget)]):
                if widget.layout() is not None:
                    widget.layout().activate()
            app.processEvents()
            if not lab.grab().save(str(args.capture)):
                raise RuntimeError("Gradient control capture failed")
            print("GRADIENT_LAB_CAPTURE", args.capture, flush=True)
            return 0
        lab.show()
        return app.exec()
    finally:
        lab.close()


if __name__ == "__main__":
    raise SystemExit(main())
