import time
import pytest
from PySide6.QtWidgets import QApplication

# Ensure a QApplication exists
@pytest.fixture(scope="module")
def app():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app

class _StubOverlay:
    def __init__(self, *args, **kwargs):
        self._visible = False
    def setGeometry(self, *args, **kwargs):
        pass
    def show(self):
        self._visible = True
    def hide(self):
        self._visible = False
    def makeCurrent(self):
        pass
    def repaint(self):
        pass
    def is_ready_for_display(self):
        return True

@pytest.mark.timeout(5)
def test_prewarm_no_deadlock(monkeypatch, app):
    # Patch GL overlay widget classes to stub overlays that are always ready
    import transitions.gl_crossfade_transition as gl_xfade
    import transitions.gl_slide_transition as gl_slide
    import transitions.gl_wipe_transition as gl_wipe
    import transitions.gl_diffuse_transition as gl_diff
    import transitions.gl_block_puzzle_flip_transition as gl_block

    monkeypatch.setattr(gl_xfade, "_GLFadeWidget", _StubOverlay, raising=False)
    monkeypatch.setattr(gl_slide, "_GLSlideWidget", _StubOverlay, raising=False)
    monkeypatch.setattr(gl_wipe, "_GLWipeWidget", _StubOverlay, raising=False)
    monkeypatch.setattr(gl_diff, "_GLDiffuseWidget", _StubOverlay, raising=False)
    monkeypatch.setattr(gl_block, "_GLBlockFlipWidget", _StubOverlay, raising=False)

    # Import DisplayWidget and call prewarm directly
    from rendering.display_widget import DisplayWidget

    w = DisplayWidget(screen_index=0, settings_manager=None)
    try:
        start = time.time()
        w._prewarm_gl_contexts()  # Should return quickly with stubs
        elapsed = time.time() - start
        assert elapsed < 2.0
    finally:
        try:
            w.close()
        except Exception:
            pass
