"""Import-free B0 source checks: bounded callback admission, no Qt or COM."""
from __future__ import annotations

import threading

import pytest

from core.media.audio_event_mailbox import AudioEventMailbox, AudioNotification


def _mailbox():
    wakes = []
    outputs = []
    box = AudioEventMailbox(post_wake=lambda: wakes.append("wake") or True,
                            deliver=outputs.append)
    return box, wakes, outputs


def test_burst_coalesces_to_one_pending_wake_and_last_snapshot():
    box, wakes, outputs = _mailbox()
    def burst():
        for i in range(500):
            assert box.push_volume(0, i / 499, bool(i % 2))
    thread = threading.Thread(target=burst)
    thread.start(); thread.join()
    assert wakes == ["wake"]
    assert outputs == []
    assert box.drain() is True
    assert outputs == [AudioNotification("volume", 0, 1.0, True)]
    assert box.drain() is False


def test_duplicate_pending_value_no_extra_wake():
    box, wakes, outputs = _mailbox()
    assert box.push_volume(0, 0.4, False)
    for _ in range(50):
        assert box.push_volume(0, 0.4, False)
    assert wakes == ["wake"]
    assert box.drain()
    assert outputs[-1].volume == pytest.approx(0.4)


def test_duplicate_consumed_value_does_not_rewake_but_real_changes_and_rebind_do():
    box, wakes, outputs = _mailbox()
    assert box.push_volume(0, 0.4, False)
    assert box.drain()
    for _ in range(1000):
        assert box.push_volume(0, 0.4, False)
    assert wakes == ["wake"]
    assert outputs == [AudioNotification("volume", 0, 0.4, False)]
    assert not box.drain()

    # Mute is an effective state change even at an identical scalar level.
    assert box.push_volume(0, 0.4, True)
    assert wakes == ["wake", "wake"]
    assert box.drain()
    assert outputs[-1] == AudioNotification("volume", 0, 0.4, True)

    assert box.push_device_change()
    assert box.drain()
    assert outputs[-1] == AudioNotification("device", 1)
    assert box.finish_handover(1)
    # The same volume/mute values on the NEW endpoint must be delivered.
    assert box.push_volume(1, 0.4, True)
    assert box.drain()
    assert outputs[-1] == AudioNotification("volume", 1, 0.4, True)
    assert wakes == ["wake"] * 4


def test_reentrant_duplicate_state_does_not_schedule_followup_wake():
    wakes, outputs = [], []
    box = None

    def consume(item):
        outputs.append(item)
        assert box is not None
        assert box.push_volume(item.endpoint_token, item.volume, item.muted)

    box = AudioEventMailbox(post_wake=lambda: wakes.append(1) or True,
                            deliver=consume)
    assert box.push_volume(0, 0.55, True)
    assert box.drain()
    assert wakes == [1] and len(outputs) == 1
    assert not box.drain()


def test_device_handover_preempts_old_endpoint_and_requires_gui_rebind():
    box, wakes, outputs = _mailbox()
    assert box.push_volume(0, 0.2, False)
    assert box.push_device_change()
    assert box.push_device_change()
    assert not box.push_volume(0, 0.8, True)
    assert not box.push_volume(1, 0.8, True)
    assert wakes == ["wake"]
    assert box.drain()
    assert outputs == [AudioNotification("device", 1)]
    assert box.finish_handover(0) is False
    assert box.finish_handover(1) is True
    assert box.push_volume(1, 0.9, True)
    assert wakes == ["wake", "wake"]
    assert box.drain() and outputs[-1].volume == pytest.approx(0.9)
    assert not box.push_volume(0, 0.3, False)


def test_late_callback_after_retirement_and_queued_wake_are_inert():
    box, wakes, outputs = _mailbox()
    assert box.push_volume(0, 0.6, False)
    box.retire()
    assert not box.push_volume(0, 0.2, True)
    assert not box.push_device_change()
    assert box.drain() is False
    assert outputs == [] and wakes == ["wake"]


def test_reentrant_notification_during_ui_delivery_gets_one_followup_wake():
    wakes = []
    delivered = []
    box = None

    def consume(item):
        delivered.append(item)
        assert box is not None
        if len(delivered) == 1:
            box.push_volume(0, 0.75, True)

    box = AudioEventMailbox(post_wake=lambda: wakes.append(1) or True,
                            deliver=consume)
    assert box.push_volume(0, 0.25, False)
    assert box.drain()
    assert wakes == [1, 1] and len(delivered) == 1
    assert box.drain() and delivered[-1].volume == pytest.approx(0.75)
    assert box.drain() is False


def test_no_cross_thread_draining_or_rebind():
    box, wakes, outputs = _mailbox()
    errors = []

    def callback_thread():
        try:
            box.drain()
        except RuntimeError as exc:
            errors.append(str(exc))
        try:
            box.finish_handover(0)
        except RuntimeError as exc:
            errors.append(str(exc))
    t = threading.Thread(target=callback_thread)
    t.start(); t.join()
    assert len(errors) == 2
    assert not wakes and not outputs


def test_no_retry_or_spin_after_bridge_rejects_wake():
    delivered = []
    calls = []
    box = AudioEventMailbox(post_wake=lambda: calls.append(1) or False,
                            deliver=delivered.append)
    assert not box.push_volume(0, 0.2, False)
    assert len(calls) == 1 and not box.drain() and delivered == []
    assert not box.push_device_change()
    assert len(calls) == 2 and not box.drain()


def test_invalid_level_does_not_publish_or_wake():
    box, wakes, outputs = _mailbox()
    for value in (-0.1, 1.1, float('nan'), float('inf')):
        assert box.push_volume(0, value, True) is False
    assert not wakes and not outputs


def test_disabled_source_module_import_does_not_load_pycaw_or_qt():
    import json
    from pathlib import Path
    import subprocess
    import sys
    code = (
        "import sys, json; "
        "import core.media.audio_event_mailbox; "
        "import core.media.core_audio_callback_probe; "
        "print(json.dumps(sorted(set(sys.modules) & "
        "{'pycaw', 'comtypes', 'PySide6', 'widgets.system_mute_runtime'})))"
    )
    result = subprocess.run([sys.executable, '-c', code],
                            capture_output=True, text=True, cwd=Path.cwd())
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout.strip()) == []
