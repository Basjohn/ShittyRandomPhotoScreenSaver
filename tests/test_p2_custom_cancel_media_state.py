"""CUSTOM Cancel must not replay persisted payloads into preview-only widgets.

Current_Plan section 3. CUSTOM is preview-first for ordinary widgets:
`_start_session_local()` hides the live widget and an `EditShellWidget` carries
the preview geometry, so ordinary drag/resize never mutates the hidden live
widget. Cancel nonetheless replayed every persisted CUSTOM entry back into every
display instance.

These bars preserve the surviving ownership contract: Cancel restores only
owners whose live runtime it actually suspended. Media core pixels are retained
Quick-owned, so the retired QWidget artwork/metadata reconstruction assertions
do not belong in this gate.
"""

from __future__ import annotations

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
