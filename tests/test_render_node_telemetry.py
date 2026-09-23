"""Background render-node telemetry keeps per-frame notes allocation-free (PR-03)."""

from __future__ import annotations

import rendering.quick.render.telemetry as telemetry_module
from rendering.quick.render.telemetry import RenderNodeSnapshot, RenderNodeTelemetry


def test_hot_path_notes_do_not_compose_snapshots(monkeypatch) -> None:
    telemetry = RenderNodeTelemetry(gui_thread_id=7)
    built: list[int] = []
    real = telemetry_module.RenderNodeSnapshot

    def _counting(**values):
        built.append(1)
        return real(**values)

    monkeypatch.setattr(telemetry_module, "RenderNodeSnapshot", _counting)
    for _ in range(50):
        telemetry.note_sync(logical_size=(2560.0, 1440.0), device_pixel_ratio=1.25)
        telemetry.note_render(render_thread_id=3, viewport=(0, 0, 3200, 1800), render_target_size=(3200, 1800))
        telemetry.note_transition_drawn(transition_id="crossfade")
    assert built == []

    first = telemetry.snapshot()
    assert built == [1]
    assert telemetry.snapshot() is first
    assert built == [1]


def test_snapshot_reflects_every_note_and_changes_identity_only_on_change() -> None:
    telemetry = RenderNodeTelemetry(gui_thread_id=7)
    initial = telemetry.snapshot()
    assert isinstance(initial, RenderNodeSnapshot)
    assert initial == RenderNodeSnapshot(gui_thread_id=7)

    telemetry.note_sync(logical_size=(1920.0, 1080.0), device_pixel_ratio=1.0)
    telemetry.note_render(render_thread_id=3, viewport=(0, 0, 1920, 1080), render_target_size=(1920, 1080))
    telemetry.note_image_uploaded(identity="a", active_identity="a", byte_count=100, pending_release_count=1)
    telemetry.note_custom_background_active()
    telemetry.note_error("boom")

    current = telemetry.snapshot()
    assert current is not initial
    assert (current.sync_count, current.render_count) == (1, 1)
    assert current.logical_size == (1920.0, 1080.0)
    assert current.viewport == (0, 0, 1920, 1080)
    assert (current.image_upload_count, current.image_upload_bytes) == (1, 100)
    assert current.active_image_identity == "a"
    assert current.error == "boom"
    assert telemetry.snapshot() is current
