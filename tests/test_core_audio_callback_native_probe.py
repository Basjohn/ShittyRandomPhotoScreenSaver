"""Read-only, explicit opt-in Windows registration gate for pinned pycaw.

Run explicitly via pytest on Windows. Never sets volume/mute,
changes default output, or starts a background poll. A passing test proves
registration/snapshot/unregistration on the test apartment, NOT yet the full
end-to-end device-switch or callback-thread latency contract.
"""
from __future__ import annotations

import sys

import pytest


@pytest.mark.skipif(sys.platform != "win32", reason="Windows Core Audio only")
def test_pinned_core_audio_callbacks_register_snapshot_and_retire_without_writes():
    from core.media.core_audio_callback_probe import CoreAudioCallbackProbe

    values = []
    device_changes = []
    source = CoreAudioCallbackProbe(
        on_volume=lambda volume, muted: values.append((volume, muted)),
        on_default_device=lambda: device_changes.append(True))
    try:
        assert source.start(), "No default speakers or Core Audio enumerator"
        initial = source.snapshot()
        if initial is None:
            pytest.skip("Device notifications registered but no active speakers")
        volume, muted = initial
        assert 0.0 <= volume <= 1.0 and isinstance(muted, bool)
    finally:
        source.stop()
    # Ambient hardware volume/device events can arrive during this read-only
    # test. Never require the user's live audio system to remain silent.
    assert all(0.0 <= v <= 1.0 and isinstance(m, bool) for v, m in values)
