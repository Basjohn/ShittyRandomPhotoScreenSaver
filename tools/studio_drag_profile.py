"""Profile one slider drag in a hidden Studio: the cost of each mouse move and of each frame.

Opens a registered Studio (``--mode``) on an in-memory store through the hidden ``OffscreenStudioSurface`` (no
window is ever shown), finds the Value Slider of ``--key`` (any registered property id; by default the first
slider of the first workspace), and drags it with real mouse events delivered to the Quick window:
``--moves-per-frame`` moves between rendered frames, ``--frames`` frames. It reports the per-move handler time
(the QML handler, the bridge slot and whatever it triggers synchronously), the per-frame time (evaluation and
render), and what ran: session previews applied, values-map rebuilds, evaluations and analysis jobs started
during the drag and after release. Nothing is saved.

    .venv/Scripts/python.exe tools/studio_drag_profile.py --mode waveform_ribbon
    .venv/Scripts/python.exe tools/studio_drag_profile.py --mode spectrum --key <property id>
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path
import sys as _sys  # noqa: E402
from pathlib import Path as _Path  # noqa: E402
if str(_Path(__file__).resolve().parents[1]) not in _sys.path:
    _sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
from tools import artifact_paths  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class _Store:
    def __init__(self, mode):
        from core.settings.visualizer_mode_settings import mode_settings
        from core.settings.visualizer_presets import resolve_visualizer_activation_payload
        self.values = dict(resolve_visualizer_activation_payload({"mode": mode, f"preset_{mode}": 0},
                                                                 mode=mode).resolved_config)
        spec = mode_settings(mode)
        if mode != "waveform_ribbon" and spec is not None:
            self.values.update({c.key: c.admit(self.values[c.key], self.values[c.key])
                                for c in spec.controls if c.key in self.values})
        self.commits = 0

    def snapshot(self):
        return dict(self.values)

    def commit(self, values, changed):
        self.commits += 1
        self.values.update(values)
        return dict(self.values)

    def preset_label(self):
        return "Preset"


class _Presence:
    concealed = False

    def conceal(self):
        pass

    def reveal(self):
        pass


def _named(root, name):
    stack, found = [root], []
    while stack:
        item = stack.pop()
        if item.objectName() == name:
            found.append(item)
        stack.extend(reversed(item.childItems()))
    return found


def _visible(item) -> bool:
    while item is not None:
        if not item.isVisible() or item.opacity() <= 0.0:
            return False
        item = item.parentItem()
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--mode", default="waveform_ribbon")
    parser.add_argument("--key", default="", help="Property id of the slider to drag (default: the first one)")
    parser.add_argument("--frames", type=int, default=30)
    parser.add_argument("--moves-per-frame", type=int, default=4)
    parser.add_argument("--json", type=artifact_paths.evidence_arg, default=None, help="Also write the record here")
    args = parser.parse_args()

    from rendering.quick.bootstrap import configure_quick_graphics
    configure_quick_graphics(reason="studio-drag-profile")
    from PySide6.QtCore import QCoreApplication, QEvent, QPointF, Qt
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    from rendering.gl_error_policy import disable_per_call_gl_error_checking
    disable_per_call_gl_error_checking()
    from ui.studio.controller import StudioBridge, StudioController
    from ui.studio.registry import create_adapter
    from ui.studio.surface import OffscreenStudioSurface
    from ui.studio.theme import studio_theme

    adapter = create_adapter(args.mode)
    adapter.recorded_clips = lambda: ()
    surfaces = []

    def factory(controller):
        surfaces.append(OffscreenStudioSurface(controller, size=(1600, 900), present_on_show=False))
        return surfaces[0]

    store = _Store(args.mode)
    controller = StudioController(adapter, store, _Presence(), factory, theme_provider=studio_theme)
    if not controller.open():
        raise SystemExit("Studio did not open")
    surface = surfaces[0]
    bridge = controller.bridge
    evaluator = controller.evaluator

    def settle(limit=3000):
        for _ in range(limit):
            surface.pump()
            if bridge.viewportStatus != "preparing" and not getattr(evaluator, "analysing", False) \
                    and not getattr(evaluator, "converging", False):
                return
            time.sleep(0.005)

    settle()
    if args.key:
        bridge.revealProperty(args.key, 0)
        surface.pump(3)
    root = surface.host.root
    sliders = [s for s in _named(root, "valueSlider") if _visible(s) and (not args.key or s.property("propId") == args.key)]
    if not sliders:
        shown = sorted({s.property("propId") for s in _named(root, "valueSlider") if _visible(s)})
        raise SystemExit(f"No visible slider for {args.key or 'the first workspace'}; visible: {shown}")
    slider = sliders[0]
    key = slider.property("propId")
    # Bring the slider into the window (the inspector scrolls).
    for _ in range(4):
        y = slider.mapToScene(QPointF(0, 0)).y()
        if 40 <= y <= 860:
            break
        for scroll in _named(root, "inspectorScroll"):
            flick = scroll.property("contentItem")
            flick.setProperty("contentY", max(0.0, flick.property("contentY") + y - 450))
        surface.pump(2)

    counts = {"rebuilds": 0, "previews": 0, "jobs": 0}
    original_rebuild = StudioBridge._rebuild_values

    def counting_rebuild(self):
        counts["rebuilds"] += 1
        start = time.perf_counter()
        try:
            return original_rebuild(self)
        finally:
            rebuild_ms.append((time.perf_counter() - start) * 1000.0)
    rebuild_ms: list[float] = []
    StudioBridge._rebuild_values = counting_rebuild
    session = controller.session
    original_preview = session.preview

    def counting_preview(*a, **k):
        counts["previews"] += 1
        return original_preview(*a, **k)
    session.preview = counting_preview
    analyse = getattr(evaluator, "_analyse", None)
    if callable(analyse):
        def counting_analyse(values, wanted):
            if evaluator._job_key != wanted and wanted not in evaluator.errors:
                counts["jobs"] += 1
            return analyse(values, wanted)
        evaluator._analyse = counting_analyse

    evaluate_ms: list[float] = []
    original_evaluate = evaluator.evaluate

    def timed_evaluate(*a, **k):
        start = time.perf_counter()
        try:
            return original_evaluate(*a, **k)
        finally:
            evaluate_ms.append((time.perf_counter() - start) * 1000.0)
    evaluator.evaluate = timed_evaluate
    window = surface.window
    width = slider.width()

    clock = [1000]

    def send(kind, x):
        scene = slider.mapToScene(QPointF(x, slider.height() / 2.0))
        buttons = Qt.MouseButton.NoButton if kind == QEvent.Type.MouseButtonRelease else Qt.MouseButton.LeftButton
        event = QMouseEvent(kind, scene, scene, scene, Qt.MouseButton.LeftButton if kind != QEvent.Type.MouseMove
                            else Qt.MouseButton.NoButton, buttons, Qt.KeyboardModifier.NoModifier)
        clock[0] += 4
        event.setTimestamp(clock[0])
        start = time.perf_counter()
        QCoreApplication.sendEvent(window, event)
        return (time.perf_counter() - start) * 1000.0

    def frame():
        start = time.perf_counter()
        surface.pump()
        return (time.perf_counter() - start) * 1000.0

    evaluations0 = controller.evaluations
    commits0 = session.commit_count
    undo0 = len(session._undo)
    move_ms, frame_ms = [], []
    press_ms = send(QEvent.Type.MouseButtonPress, width * 0.3)
    total = args.frames * args.moves_per_frame
    for index in range(total):
        x = width * (0.3 + 0.4 * (index + 1) / total)
        move_ms.append(send(QEvent.Type.MouseMove, x))
        if (index + 1) % args.moves_per_frame == 0:
            frame_ms.append(frame())
    during = dict(counts, evaluations=controller.evaluations - evaluations0)
    drag_evaluate_ms = list(evaluate_ms)
    evaluate_ms.clear()
    release_ms = send(QEvent.Type.MouseButtonRelease, width * 0.7)
    release_frame_ms = frame()
    settle()
    record = {
        "mode": args.mode, "key": key, "frames": args.frames, "moves_per_frame": args.moves_per_frame,
        "move_ms": {"median": round(statistics.median(move_ms), 3), "p90": round(sorted(move_ms)[int(len(move_ms) * .9)], 3),
                    "max": round(max(move_ms), 3)},
        "frame_ms": {"median": round(statistics.median(frame_ms), 3), "p90": round(sorted(frame_ms)[int(len(frame_ms) * .9)], 3),
                     "max": round(max(frame_ms), 3)},
        "press_ms": round(press_ms, 3), "release_ms": round(release_ms, 3), "release_frame_ms": round(release_frame_ms, 3),
        "rebuild_ms_median (values map + presets + QML notify)": round(statistics.median(rebuild_ms), 3) if rebuild_ms else None,
        "evaluate_ms_during_drag": {"median": round(statistics.median(drag_evaluate_ms), 3) if drag_evaluate_ms else None,
                                    "max": round(max(drag_evaluate_ms), 3) if drag_evaluate_ms else None},
        "evaluate_ms_after_release": [round(v, 1) for v in evaluate_ms[:6]],
        "during_drag": during,
        "after_release": {k: counts[k] - during[k] for k in counts},
        "commits": session.commit_count - commits0, "undo_entries": len(session._undo) - undo0,
        "store_commits": store.commits,
    }
    StudioBridge._rebuild_values = original_rebuild
    text = json.dumps(record, indent=1)
    print(text)
    if args.json is not None:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(text, encoding="utf-8")
    controller.close()
    del app
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
