import time
import pytest
from PySide6.QtWidgets import QApplication
from core.animation.animator import AnimationManager
from core.animation.types import EasingCurve

@pytest.fixture(scope="module")
def app():
    app = QApplication.instance() or QApplication([])
    return app

@pytest.mark.timeout(3)
def test_set_target_fps_updates_timer_interval(app):
    am = AnimationManager(fps=60)
    try:
        # Initial assumptions
        assert am.fps == 60
        before_interval = am._timer.interval()
        assert before_interval in (16, 17)  # ms
        # Change FPS
        am.set_target_fps(120)
        assert am.fps == 120
        after_interval = am._timer.interval()
        assert after_interval in (8, 9)
        # Start a tiny animation and make sure manager starts/stops cleanly
        am.animate_custom(
            duration=0.05,
            easing=EasingCurve.LINEAR,
            update_callback=lambda p: None,
        )
        # Allow updates for a short time
        start = time.time()
        while am.get_active_count() > 0 and (time.time() - start) < 1.0:
            app.processEvents()
            time.sleep(0.005)
        assert am.get_active_count() == 0
    finally:
        am.cleanup()
