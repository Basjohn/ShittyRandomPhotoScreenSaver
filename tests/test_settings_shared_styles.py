import weakref

from PySide6.QtCore import Qt

from ui.tabs import shared_styles


class _FakeShiboken:
    invalid_ids: set[int] = set()

    @classmethod
    def isValid(cls, obj) -> bool:
        return id(obj) not in cls.invalid_ids


def test_no_wheel_slider_skips_stale_last_moved_wrapper(qt_app):
    previous = shared_styles.NoWheelSlider(Qt.Orientation.Horizontal)
    current = shared_styles.NoWheelSlider(Qt.Orientation.Horizontal)
    original_shiboken = shared_styles.Shiboken
    original_last_moved = shared_styles._last_moved_slider
    try:
        shared_styles.Shiboken = _FakeShiboken
        _FakeShiboken.invalid_ids = {id(previous)}
        shared_styles._last_moved_slider = weakref.ref(previous)

        current._mark_last_moved()

        assert current.property("lastMoved") is True
        assert shared_styles._last_moved_slider is not None
        assert shared_styles._last_moved_slider() is current
    finally:
        shared_styles.Shiboken = original_shiboken
        shared_styles._last_moved_slider = original_last_moved
        previous.deleteLater()
        current.deleteLater()


def test_no_wheel_slider_does_not_store_invalid_current_slider(qt_app):
    current = shared_styles.NoWheelSlider(Qt.Orientation.Horizontal)
    original_shiboken = shared_styles.Shiboken
    original_last_moved = shared_styles._last_moved_slider
    try:
        shared_styles.Shiboken = _FakeShiboken
        _FakeShiboken.invalid_ids = {id(current)}
        shared_styles._last_moved_slider = weakref.ref(current)

        current._mark_last_moved()

        assert shared_styles._last_moved_slider is None
    finally:
        shared_styles.Shiboken = original_shiboken
        shared_styles._last_moved_slider = original_last_moved
        current.deleteLater()
