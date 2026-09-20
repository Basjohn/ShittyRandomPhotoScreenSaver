"""Pure-Python retained-session tests; no Qt/COM or system-audio writes."""
from __future__ import annotations

import threading

import pytest

from core.media.audio_event_mailbox import AudioEventMailbox
from core.media.audio_event_session import CoreAudioEventSession


class _Bridge:
    def __init__(self, deliver):
        self.wakes = []
        self.mailbox = AudioEventMailbox(post_wake=lambda: self.wakes.append(1) or True,
                                          deliver=deliver)
        self.closed = False
        self.delete_later_calls = 0

    def deleteLater(self):
        self.delete_later_calls += 1

    def close(self):
        self.closed = True
        self.mailbox.retire()

    def flush(self):
        while self.wakes:
            self.wakes.pop(0)
            self.mailbox.drain()


class _Probe:
    def __init__(self, on_volume, on_default_device, snapshot):
        self.on_volume = on_volume
        self.on_default_device = on_default_device
        self.current = snapshot
        self.stops = 0
        self.starts = 0

    def start(self):
        self.starts += 1
        return True

    def stop(self):
        self.stops += 1

    def snapshot(self):
        return self.current

    def set_mute(self, muted):
        if self.current is None:
            return False
        self.current = (self.current[0], bool(muted))
        self.on_volume(*self.current)
        return True

    def set_volume(self, level):
        if self.current is None:
            return False
        self.current = (float(level), self.current[1])
        self.on_volume(*self.current)
        return True


def _setup(snapshots):
    output, bridges, probes = [], [], []

    def bridge_factory(deliver):
        result = _Bridge(deliver)
        bridges.append(result)
        return result

    def probe_factory(*, on_volume, on_default_device):
        result = _Probe(on_volume, on_default_device, snapshots[len(probes)])
        probes.append(result)
        return result

    session = CoreAudioEventSession(publish=output.append,
                                    bridge_factory=bridge_factory,
                                    probe_factory=probe_factory)
    return session, output, bridges, probes


def test_retained_session_no_poll_one_subscription_and_latest_only_burst():
    session, output, bridges, probes = _setup([(0.4, False)])
    assert session.start() and session.start()
    assert len(bridges) == len(probes) == 1
    bridge, probe = bridges[0], probes[0]
    assert bridge.wakes == [1]
    bridge.flush()
    assert len(output) == 1 and output[-1].volume == 0.4

    def cb():
        for i in range(1000):
            probe.on_volume(i / 999, bool(i % 2))
    worker = threading.Thread(target=cb)
    worker.start(); worker.join()
    assert bridge.wakes == [1]
    bridge.flush()
    assert len(output) == 2 and output[-1].volume == 1.0
    assert output[-1].muted is True
    probe.on_volume(1.0, True)
    bridge.flush()
    assert len(output) == 2  # Equal effective state cannot fan out again.
    assert bridge.wakes == []  # And must not queue an unnecessary GUI wake.
    session.retire()
    assert probe.stops == 1 and bridge.closed and bridge.delete_later_calls == 1


def test_device_swap_fences_old_transport_and_restores_on_new_endpoint():
    session, output, bridges, probes = _setup([(0.3, False), (0.8, True)])
    assert session.start()
    bridge = bridges[0]
    bridge.flush()
    old = probes[0]
    old.on_volume(0.6, False)
    old.on_default_device()
    # A callback-thread handover fences UI actions before the next Qt wake;
    # none may write through the now-stale original endpoint.
    assert session.toggle_mute() is None
    assert session.step_volume(0.05) is None
    assert session.request_snapshot() is False
    old.on_volume(0.7, False)
    assert bridge.wakes == [1]
    bridge.flush()
    assert len(probes) == 2 and old.stops == 1
    assert [(s.available, s.endpoint_token) for s in output] == [
        (True, 0), (False, 1), (True, 1)]
    assert output[-1].volume == 0.8 and output[-1].muted
    old.on_volume(0.9, False)  # Simulate already-queued old COM callback.
    bridge.flush()
    assert output[-1].volume == 0.8
    probes[1].on_volume(0.1, False)
    bridge.flush()
    assert output[-1].volume == 0.1 and output[-1].endpoint_token == 1
    session.retire()
    assert probes[1].stops == 1
    old.on_default_device()
    bridge.flush()
    assert len(probes) == 2


def test_missing_endpoint_remains_watchable_and_device_event_rebinds():
    session, output, bridges, probes = _setup([None, (0.6, False)])
    assert session.start()
    bridges[0].flush()
    assert len(output) == 1 and not output[-1].available
    probes[0].on_default_device()
    bridges[0].flush()
    assert len(probes) == 2 and output[-1].available
    assert output[-1].volume == 0.6
    session.retire()


def test_retirement_fences_all_callbacks_and_cross_thread_owner_calls():
    session, output, bridges, probes = _setup([(0.3, False)])
    assert session.start()
    errors = []

    def invalid_thread():
        for operation in (session.start, session.retire):
            try:
                operation()
            except RuntimeError as exc:
                errors.append(str(exc))

    worker = threading.Thread(target=invalid_thread)
    worker.start(); worker.join()
    assert len(errors) == 2
    session.retire()
    probes[0].on_volume(0.2, True)
    probes[0].on_default_device()
    bridges[0].flush()
    assert output == []  # No delivery from a retired generation.


def test_system_actions_share_one_session_and_coalesce_with_callback_echo():
    session, output, bridges, probes = _setup([(0.4, False)])
    assert session.start()
    bridge = bridges[0]
    bridge.flush()
    probe = probes[0]
    assert session.toggle_mute() is True
    assert session.step_volume(0.2) == pytest.approx(0.6)
    assert len(bridge.wakes) == 1
    bridge.flush()
    assert output[-1].volume == pytest.approx(0.6) and output[-1].muted is True
    count = len(output)
    probe.on_volume(probe.current[0], True)
    bridge.flush()
    assert len(output) == count
    assert session.request_snapshot()
    assert bridge.wakes == []  # Equal effective value does not post a fresh wake.
    session.retire()
    assert session.toggle_mute() is None
    assert session.step_volume(0.1) is None
    assert session.request_snapshot() is False


def test_actions_while_output_absent_never_write_or_queue_retries():
    session, output, bridges, probes = _setup([None])
    assert session.start()
    bridges[0].flush()
    assert session.toggle_mute() is None
    assert session.step_volume(0.2) is None
    assert session.request_snapshot() is False
    assert bridges[0].wakes == []
    session.retire()


def test_com_float_jitter_does_not_trigger_redundant_ui_delivery():
    session, output, bridges, probes = _setup([(0.6, False)])
    assert session.start()
    bridge = bridges[0]
    bridge.flush()
    count = len(output)
    for volume in (0.60000000001, 0.59999999999, 0.6000000002):
        probes[0].on_volume(volume, False)
    assert bridge.wakes == []
    bridge.flush()
    assert len(output) == count
    probes[0].on_volume(0.60001, False)
    assert bridge.wakes == [1]
    bridge.flush()
    assert output[-1].volume == pytest.approx(0.60001)
    session.retire()
