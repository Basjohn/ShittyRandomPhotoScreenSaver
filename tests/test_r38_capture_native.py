"""Narrow native key/capture gate; no build, runtime or environment mutation."""
from pathlib import Path

from PySide6.QtCore import QEvent, QPoint, QRect, Qt
from PySide6.QtGui import QImage, QKeyEvent

from rendering.quick.input_controller import QuickInputController
from rendering.quick import diagnostic_capture as captures


def test_backslash_is_one_edge_and_never_repeats(qt_app, monkeypatch):
    # Source/diagnostic only. A compiled release must not intercept this key.
    monkeypatch.setattr(captures, 'capture_allowed', lambda: True)
    ctrl = QuickInputController(screen_index=0, runtime_generation=11)
    edges = []
    ctrl.diagnostic_capture_requested.connect(lambda: edges.append(True))
    event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Backslash,
                      Qt.KeyboardModifier.NoModifier, '\\')
    repeat = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Backslash,
                       Qt.KeyboardModifier.NoModifier, '\\', True, 2)
    try:
        assert ctrl.handle_key_press(event)
        assert ctrl.handle_key_press(repeat)
        assert len(edges) == 1
        monkeypatch.setattr(captures, 'capture_allowed', lambda: False)
        # Interaction mode means the release-build backslash is ordinary input.
        ctrl.set_interaction_mode_enabled(True)
        assert not ctrl.handle_key_press(event)
        assert len(edges) == 1
        ctrl.close_input()
        assert ctrl.handle_key_press(event)
        assert len(edges) == 1
    finally:
        ctrl.deleteLater()


def test_one_shot_widget_region_and_full_display_fallback(qt_app, tmp_path, monkeypatch):
    fake_frame = QImage(1800, 900, QImage.Format.Format_ARGB32)
    fake_frame.fill(Qt.GlobalColor.blue)
    output = []
    monkeypatch.setattr(captures, 'capture_allowed', lambda: True)
    monkeypatch.setattr(captures, 'capture_directory', lambda: tmp_path/'captures')
    monkeypatch.setattr(captures, 'capture_cursor_position', lambda: QPoint(1100, 100))

    class Screen:
        def geometry(self): return QRect(1000, 0, 1200, 600)
        def grabWindow(self, window_id):
            assert window_id == 0
            from PySide6.QtGui import QPixmap
            return QPixmap.fromImage(fake_frame)

    class Window:
        def isVisible(self): return True
        def screen(self): return Screen()
        def mapFromGlobal(self, point): return QPoint(point.x()-1000, point.y())

    class Scene:
        def diagnostic_capture_target_at(self, point):
            return ('media', (1050, 30, 100, 100))

    class InstantThread:
        def __init__(self, *, target, args, **kwargs): self.target, self.args = target, args
        def start(self):
            image, destination = self.args
            output.append((image.width(), image.height(), destination))
            self.target(*self.args)

    monkeypatch.setattr(captures, 'Thread', InstantThread)
    monkeypatch.setattr(captures, '_save_detached', lambda image, destination: None)
    candidate = captures.capture_key_edge(window=Window(), scene=Scene(), screen_index=1)
    assert output[0][0:2] == (150, 150)
    assert candidate.parent == tmp_path/'captures'
    assert candidate.name.endswith('.png')
    output.clear()
    class EmptyScene:
        def diagnostic_capture_target_at(self, point): return None
    captures.capture_key_edge(window=Window(), scene=EmptyScene(), screen_index=1)
    assert output[0][0:2] == (1800, 900)
