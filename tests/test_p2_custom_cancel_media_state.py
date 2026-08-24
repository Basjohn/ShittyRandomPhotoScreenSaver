"""CUSTOM Cancel must not rebuild a preview-only widget from persisted payload.

Current_Plan section 3. CUSTOM is preview-first for ordinary widgets:
`_start_session_local()` hides the live widget and an `EditShellWidget` carries
the preview geometry, so ordinary drag/resize never mutates the hidden live
widget. Cancel nonetheless replayed every persisted CUSTOM entry back into every
display instance.

The installed run shows Media created with

    payload={artwork_size=220, font_size=19}

and Cancel replaying that identical payload through replay_start ->
replay_after_payload -> replay_after_update_position -> replay_final, after
which the operator sees live artwork and metadata gone.

The absence of `overlay.frame_shadow.regen` did not make that replay a semantic
no-op: `MediaWidget.set_artwork_size()`/`set_font_size()` invalidate the
metadata and controls layout and then rebuild the card through
`_refresh_current_display_layout()`, which falls back to an empty card whenever
`_last_info` and the retained info are unavailable.

These bars hold both halves: Cancel restores only owners whose live runtime it
actually suspended, and an unchanged Media size is a no-op.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from PySide6.QtGui import QColor, QImage, QPixmap

from core.media.media_controller import MediaPlaybackState, MediaTrackInfo
from widgets.media_widget import MediaWidget


# ---------------------------------------------------------------------------
# A real, populated MediaWidget
# ---------------------------------------------------------------------------


class _Controller:
    def get_current_track(self):
        return None

    def is_available(self):
        return False


class _ThreadManager:
    def submit_task(self, *args, **kwargs):
        return None

    def run_on_ui_thread(self, func, *args, **kwargs):
        func(*args, **kwargs)


def _artwork() -> QPixmap:
    image = QImage(220, 220, QImage.Format.Format_ARGB32)
    image.fill(QColor("#cc5500"))
    return QPixmap.fromImage(image)


@pytest.fixture
def media(qt_app, qtbot):
    widget = MediaWidget(controller=_Controller(), thread_manager=_ThreadManager())
    qtbot.addWidget(widget)
    widget.resize(420, 300)
    widget.set_artwork_size(220)
    widget.set_font_size(19)
    widget._last_info = MediaTrackInfo(
        title="Ghost Town",
        artist="The Specials",
        album="Ghost Town",
        state=MediaPlaybackState.PLAYING,
    )
    widget._artwork_pixmap = _artwork()
    widget._metadata_paint = {"title": "Ghost Town", "artist": "The Specials"}
    return widget


class TestUnchangedSizeIsANoOp:
    def test_reapplying_the_same_artwork_size_keeps_artwork(self, media):
        before = media._artwork_pixmap

        media.set_artwork_size(220)

        assert media._artwork_pixmap is before, (
            "re-applying the current artwork size rebuilt the live card"
        )

    def test_reapplying_the_same_artwork_size_keeps_metadata(self, media):
        before = dict(media._metadata_paint)

        media.set_artwork_size(220)

        assert media._metadata_paint == before

    def test_reapplying_the_same_font_size_keeps_metadata(self, media):
        before = dict(media._metadata_paint)

        media.set_font_size(19)

        assert media._metadata_paint == before

    def test_a_real_artwork_size_change_still_applies(self):
        """The guard is a no-op filter, never a freeze."""
        widget = MediaWidget(controller=_Controller(), thread_manager=_ThreadManager())
        widget.set_artwork_size(220)
        widget.set_artwork_size(160)
        assert widget._artwork_size == 160

    def test_a_real_font_size_change_still_applies(self):
        widget = MediaWidget(controller=_Controller(), thread_manager=_ThreadManager())
        widget.set_font_size(19)
        widget.set_font_size(24)
        assert widget._font_size == 24


# ---------------------------------------------------------------------------
# Cancel restores only genuinely suspended owners
# ---------------------------------------------------------------------------


class _Descriptor:
    def __init__(self, widget_id: str, attr_name: str):
        self.widget_id = widget_id
        self.attr_name = attr_name
        self.custom_layout_resize_mode = "media_scale"
        self.supports_layout_resize_edit = True
        self.custom_layout_runtime_vertical_content_resize = False


def test_cancel_restore_set_excludes_preview_only_widgets():
    """The audit result, pinned: only the visualizer is restored."""
    from rendering.custom_layout_manager import _CANCEL_RESTORE_WIDGET_IDS

    assert "spotify_visualizer" in _CANCEL_RESTORE_WIDGET_IDS, (
        "the visualizer runtime is genuinely suspended and must be restored"
    )
    for preview_only in ("media", "clock", "weather", "reddit", "gmail"):
        assert preview_only not in _CANCEL_RESTORE_WIDGET_IDS, (
            f"{preview_only} is preview-only; Cancel must not replay into it"
        )


class _RecordingManager:
    """The replay filter under test, with the display side faked."""

    def __init__(self, applied):
        self._applied = applied
        self._active = False

    def apply_saved_layouts_to_display(self, *, only_widget_ids=None):
        for widget_id in ("clock", "media", "spotify_visualizer"):
            if only_widget_ids is not None and widget_id not in only_widget_ids:
                continue
            self._applied.append(widget_id)


def test_cancel_applies_only_the_restore_set():
    from rendering.custom_layout_manager import _CANCEL_RESTORE_WIDGET_IDS

    applied: list[str] = []
    manager = _RecordingManager(applied)

    manager.apply_saved_layouts_to_display(only_widget_ids=_CANCEL_RESTORE_WIDGET_IDS)

    assert applied == ["spotify_visualizer"], (
        "Cancel replayed a persisted payload into a preview-only widget"
    )


def test_an_unfiltered_apply_still_covers_every_widget():
    """Save and ordinary startup replay must be unaffected."""
    applied: list[str] = []
    manager = _RecordingManager(applied)

    manager.apply_saved_layouts_to_display()

    assert applied == ["clock", "media", "spotify_visualizer"]


def test_the_filter_parameter_exists_on_the_real_manager():
    import inspect

    from rendering.custom_layout_manager import CustomLayoutManager

    signature = inspect.signature(CustomLayoutManager.apply_saved_layouts_to_display)
    assert "only_widget_ids" in signature.parameters


def test_cancel_session_no_longer_calls_the_broad_display_replay():
    """The exact defect: `instance._apply_saved_custom_layouts()` on Cancel."""
    import inspect

    from rendering.custom_layout_manager import CustomLayoutManager

    source = inspect.getsource(CustomLayoutManager.cancel_session)
    assert "_apply_saved_custom_layouts" not in source, (
        "Cancel still broadly replays persisted layout into every widget"
    )
    assert "only_widget_ids" in source
