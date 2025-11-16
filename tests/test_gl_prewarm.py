import pytest

from rendering.display_widget import DisplayWidget
from rendering.display_modes import DisplayMode
from rendering.gl_compositor import GLCompositorWidget


class DummySettings:
    def __init__(self, data=None):
        self._data = data or {}

    def get(self, key, default=None):
        # Direct key first
        if key in self._data:
            return self._data[key]
        # Dot-notation fallback for tests
        if "." in key:
            cur = self._data
            for part in key.split("."):
                if isinstance(cur, dict) and part in cur:
                    cur = cur[part]
                else:
                    return default
            return cur
        return default


@pytest.mark.qt_no_exception_capture
def test_gl_prewarm_overlays_ready(qtbot):
    # Enable GL prewarm but disable widgets to avoid extra UI creation in test
    settings = DummySettings({
        'display.hw_accel': True,
        'widgets': {'clock': {'enabled': False}}
    })

    w = DisplayWidget(screen_index=0, display_mode=DisplayMode.FILL, settings_manager=settings)
    qtbot.addWidget(w)

    # Trigger show + prewarm (this now initializes the shared compositor
    # rather than per-transition GL overlays).
    w.show_on_screen()

    # Allow time for prewarm loop to complete
    qtbot.wait(800)

    # Verify a shared GL compositor exists and is usable
    comp = getattr(w, "_gl_compositor", None)
    assert isinstance(comp, GLCompositorWidget), "Missing GL compositor after prewarm"

    # If a GL context cannot be made current in this environment, skip rather
    # than failing the test outright.
    try:
        comp.makeCurrent()
    except Exception:
        pytest.skip("GL context not available for GLCompositorWidget prewarm")

    # Cleanup
    w.close()
