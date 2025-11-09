import pytest

from rendering.display_widget import DisplayWidget
from rendering.display_modes import DisplayMode


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

    # Trigger show + prewarm
    w.show_on_screen()

    # Allow time for prewarm loop to complete
    qtbot.wait(800)

    # Verify persistent overlays exist and are ready
    overlay_attrs = [
        '_srpss_gl_xfade_overlay',
        '_srpss_gl_slide_overlay',
        '_srpss_gl_wipe_overlay',
        '_srpss_gl_diffuse_overlay',
        '_srpss_gl_blockflip_overlay',
    ]

    for attr in overlay_attrs:
        overlay = getattr(w, attr, None)
        assert overlay is not None, f"Missing overlay: {attr}"
        ready = True
        if hasattr(overlay, 'is_ready_for_display'):
            try:
                ready = bool(overlay.is_ready_for_display())
            except Exception:
                ready = False
        assert ready, f"Overlay not ready: {attr}"

    # Cleanup
    w.close()
