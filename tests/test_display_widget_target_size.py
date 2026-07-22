from __future__ import annotations

from PySide6.QtCore import QRect, QSize

from rendering.display_widget import DisplayWidget


class _Screen:
    def __init__(self, width: int, height: int, dpr: float) -> None:
        self._geometry = QRect(0, 0, width, height)
        self._dpr = dpr

    def geometry(self) -> QRect:
        return self._geometry

    def devicePixelRatio(self) -> float:
        return self._dpr


class _Display:
    def __init__(self, logical_size: QSize, screen: _Screen, dpr: float = 1.0) -> None:
        self._logical_size = logical_size
        self._screen = screen
        self._device_pixel_ratio = dpr

    def size(self) -> QSize:
        return self._logical_size

    _set_device_pixel_ratio = DisplayWidget._set_device_pixel_ratio


class _Presenter:
    def __init__(self, dpr: float) -> None:
        self.device_pixel_ratio = dpr


def test_get_target_size_uses_screen_geometry_before_fullscreen_resize():
    display = _Display(QSize(640, 480), _Screen(2560, 1440, 1.5))
    display._image_presenter = _Presenter(1.0)

    target = DisplayWidget.get_target_size(display)

    assert target == QSize(3840, 2158)
    assert display._device_pixel_ratio == 1.5
    assert display._image_presenter.device_pixel_ratio == 1.5


def test_get_target_size_preserves_established_fullscreen_geometry():
    display = _Display(QSize(1707, 959), _Screen(1707, 960, 1.5), dpr=1.5)

    target = DisplayWidget.get_target_size(display)

    assert target == QSize(2560, 1438)


def test_shared_dpr_authority_rejects_invalid_values_and_updates_presenter():
    display = _Display(QSize(1920, 1080), _Screen(1920, 1080, 1.0))
    display._image_presenter = _Presenter(1.0)

    assert display._set_device_pixel_ratio(1.5) == 1.5
    assert display._device_pixel_ratio == 1.5
    assert display._image_presenter.device_pixel_ratio == 1.5

    assert display._set_device_pixel_ratio(float("nan")) == 1.5
    assert display._image_presenter.device_pixel_ratio == 1.5
