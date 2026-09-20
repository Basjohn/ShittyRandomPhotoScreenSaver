"""Pure event, identity and dormancy gates for the optional system audio OSD."""
from dataclasses import dataclass

from core.media.system_audio_osd_policy import SystemAudioOSDPolicy


@dataclass(frozen=True)
class Snapshot:
    revision: int
    endpoint_token: int
    available: bool = True
    volume: float | None = 0.5
    muted: bool = False


def test_initial_seed_is_silent_and_effective_master_changes_reveal():
    policy = SystemAudioOSDPolicy()
    assert not policy.accept(Snapshot(1, 0)).reveal
    assert not policy.accept(Snapshot(2, 0)).reveal
    assert policy.accept(Snapshot(3, 0, volume=0.6)).reveal
    assert policy.accept(Snapshot(4, 0, volume=0.6, muted=True)).reveal
    assert not policy.accept(Snapshot(4, 0, volume=0.1)).accepted
    assert not policy.accept(Snapshot(5, 0, volume=0.6, muted=True)).reveal


def test_device_switch_fences_stale_audio_and_clears_readiness():
    policy = SystemAudioOSDPolicy()
    policy.accept(Snapshot(1, 0))
    unavailable = policy.accept(Snapshot(2, 1, available=False, volume=None))
    assert unavailable.accepted and not unavailable.reveal and not unavailable.available
    assert not policy.accept(Snapshot(999, 0, volume=0.9)).accepted
    rebound = policy.accept(Snapshot(3, 1, volume=0.3))
    assert not rebound.reveal and rebound.volume == 0.3
    assert policy.accept(Snapshot(4, 1, volume=0.4)).reveal
    policy.retire()
    assert not policy.accept(Snapshot(4, 1, volume=0.7)).accepted


def test_no_import_of_gui_com_or_audio_source_from_pure_policy():
    import sys
    import core.media.system_audio_osd_policy as policy

    assert not any(symbol in policy.__dict__ for symbol in (
        "QTimer", "QQuickItem", "CoreAudioCallbackProbe", "SharedCoreAudioBackend"
    ))
    assert "core.media.core_audio_callback_probe" not in policy.__dict__
