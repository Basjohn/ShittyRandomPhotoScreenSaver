from __future__ import annotations

from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import QWidget

from rendering.display_modes import DisplayMode
from rendering.image_presenter import (
    ImagePresenter,
    ensure_pixmap_device_pixel_ratio,
)
from rendering.image_upload_payload import ImageUploadPayload


def test_pixmap_dpr_helper_preserves_identity_when_ratio_is_unchanged(qt_app):
    pixmap = QPixmap(32, 32)
    pixmap.fill(QColor("red"))
    assert ensure_pixmap_device_pixel_ratio(pixmap, 1.5) is True
    key = int(pixmap.cacheKey())

    assert ensure_pixmap_device_pixel_ratio(pixmap, 1.5) is False
    assert int(pixmap.cacheKey()) == key


def test_presenter_uses_display_dpr_without_detaching_prepared_pixmap(qt_app):
    parent = QWidget()
    presenter = ImagePresenter(parent, DisplayMode.FILL, 1.5)
    pixmap = QPixmap(32, 32)
    pixmap.fill(QColor("blue"))
    ensure_pixmap_device_pixel_ratio(pixmap, 1.5)
    key = int(pixmap.cacheKey())

    presenter.set_current(pixmap)
    presenter.complete_transition(pixmap)

    assert presenter.device_pixel_ratio == 1.5
    assert pixmap.devicePixelRatio() == 1.5
    assert int(pixmap.cacheKey()) == key


def test_presenter_keeps_payload_generation_with_transition_state(qt_app):
    parent = QWidget()
    presenter = ImagePresenter(parent, DisplayMode.FILL, 1.0)
    old_pixmap = QPixmap(2, 2)
    new_pixmap = QPixmap(2, 2)
    old_payload = ImageUploadPayload.from_rgba8(2, 2, b"\x01" * 16)
    new_payload = ImageUploadPayload.from_rgba8(2, 2, b"\x02" * 16)

    presenter.set_current(old_pixmap, upload_payload=old_payload)
    assert presenter.prepare_for_transition() is old_pixmap
    presenter.set_current(new_pixmap, upload_payload=new_payload)

    assert presenter.previous_upload_payload is old_payload
    assert presenter.current_upload_payload is new_payload

    presenter.complete_transition(new_pixmap, upload_payload=new_payload)

    assert presenter.current_upload_payload is new_payload
    assert presenter.seed_upload_payload is new_payload
    assert presenter.previous_upload_payload is None
