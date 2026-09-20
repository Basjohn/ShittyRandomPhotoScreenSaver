"""Fake COM transport tests. No device, real COM or Qt is accessed here."""
from __future__ import annotations

import sys
import ctypes
import threading
from types import ModuleType, SimpleNamespace

import pytest

from core.media.core_audio_callback_probe import CoreAudioCallbackProbe


class Endpoint:
    def __init__(self):
        self.callbacks = []
        self.unregistered = []
        self.volume = 0.55
        self.muted = False

    def RegisterControlChangeNotify(self, callback):
        self.callbacks.append(callback)

    def UnregisterControlChangeNotify(self, callback):
        self.unregistered.append(callback)

    def GetMasterVolumeLevelScalar(self): return self.volume
    def GetMute(self): return self.muted

    def SetMasterVolumeLevelScalar(self, value, _context):
        self.volume = float(value)
        self.push(self.volume, self.muted)

    def SetMute(self, value, _context):
        self.muted = bool(value)
        self.push(self.volume, self.muted)

    def push(self, value, muted):
        for callback in list(self.callbacks):
            callback.OnNotify(SimpleNamespace(contents=SimpleNamespace(
                fMasterVolume=value, bMuted=muted)))


class Enumerator:
    def __init__(self):
        self.callbacks = []
        self.unregistered = []
        self.fail_registration = False

    def RegisterEndpointNotificationCallback(self, callback):
        if self.fail_registration:
            raise RuntimeError("endpoint notification registration failed")
        self.callbacks.append(callback)

    def UnregisterEndpointNotificationCallback(self, callback):
        self.unregistered.append(callback)


@pytest.fixture
def fake_core_audio(monkeypatch):
    endpoints = [Endpoint()]
    enumerator = Enumerator()

    class Speaker:
        def Activate(self, *_a): return endpoints[-1]

    class AudioUtilities:
        @staticmethod
        def GetSpeakers(): return Speaker()
        @staticmethod
        def GetDeviceEnumerator(): return enumerator

    comtypes = ModuleType("comtypes")
    comtypes.CLSCTX_ALL = 1
    comtypes.COMObject = type("COMObject", (), {})
    pycaw = ModuleType("pycaw")
    inner = ModuleType("pycaw.pycaw")
    inner.AudioUtilities = AudioUtilities
    inner.IAudioEndpointVolume = type("FakeEndpointInterface", (ctypes.Structure,),
                                       {"_fields_": [], "_iid_": "fake-endpoint"})
    inner.IAudioEndpointVolumeCallback = type("IAudioEndpointVolumeCallback", (), {})
    inner.IMMNotificationClient = type("IMMNotificationClient", (), {})
    monkeypatch.setitem(sys.modules, "comtypes", comtypes)
    monkeypatch.setitem(sys.modules, "pycaw", pycaw)
    monkeypatch.setitem(sys.modules, "pycaw.pycaw", inner)
    monkeypatch.setattr("ctypes.cast", lambda interface, pointer: interface)
    return endpoints, enumerator


def test_registration_rebind_late_callbacks_snapshot_and_stop(fake_core_audio):
    endpoints, enumerator = fake_core_audio
    values, device_changes = [], []
    source = CoreAudioCallbackProbe(on_volume=lambda v, m: values.append((v, m)),
                                    on_default_device=lambda: device_changes.append(True))
    assert source.start() and source.start()
    assert len(endpoints[0].callbacks) == 1
    assert len(enumerator.callbacks) == 1
    assert source.snapshot() == (0.55, False)
    endpoints[0].push(0.3, True)
    assert values == [(0.3, True)]
    prior_volume = endpoints[0].callbacks[0]
    prior_device = enumerator.callbacks[0]
    prior_device.OnDefaultDeviceChanged(1, 1, "capture")
    prior_device.OnDefaultDeviceChanged(0, 0, "console")
    assert device_changes == []
    prior_device.OnDefaultDeviceChanged(0, 1, "multimedia")
    assert device_changes == [True]
    endpoints.append(Endpoint())
    assert source.rebind()
    assert endpoints[0].unregistered == [prior_volume]
    assert enumerator.unregistered == [prior_device]
    prior_volume.OnNotify(SimpleNamespace(contents=SimpleNamespace(fMasterVolume=0.8, bMuted=False)))
    prior_device.OnDefaultDeviceChanged(0, 1, "late")
    assert values == [(0.3, True)] and device_changes == [True]
    endpoints[1].push(0.9, False)
    assert values == [(0.3, True), (0.9, False)]
    source.stop()
    assert source.snapshot() is None
    assert len(endpoints[1].unregistered) == 1
    assert len(enumerator.unregistered) == 2
    endpoints[1].push(0.1, True)
    assert len(values) == 2


def test_partial_registration_failure_cannot_leave_active_volume_callback(fake_core_audio):
    endpoints, enumerator = fake_core_audio
    enumerator.fail_registration = True
    source = CoreAudioCallbackProbe(on_volume=lambda *_: None,
                                    on_default_device=lambda: None)
    with pytest.raises(RuntimeError, match="registration failed"):
        source.start()
    assert endpoints[0].callbacks == []
    assert endpoints[0].unregistered == []
    assert source.snapshot() is None


def test_com_registration_and_retirement_require_same_thread(fake_core_audio):
    source = CoreAudioCallbackProbe(on_volume=lambda *_: None,
                                    on_default_device=lambda: None)
    assert source.start()
    errors = []

    def other_thread():
        for operation in (source.start, source.stop, source.snapshot, source.rebind):
            try:
                operation()
            except RuntimeError as exc:
                errors.append(str(exc))

    t = threading.Thread(target=other_thread)
    t.start(); t.join()
    assert len(errors) == 4 and all("COM apartment" in error for error in errors)
    source.stop()


def test_no_speakers_still_watches_default_device_and_can_rebind(fake_core_audio, monkeypatch):
    endpoints, enumerator = fake_core_audio
    from pycaw.pycaw import AudioUtilities
    original_speakers = AudioUtilities.GetSpeakers
    monkeypatch.setattr(AudioUtilities, 'GetSpeakers', staticmethod(lambda: None))
    events = []
    source = CoreAudioCallbackProbe(on_volume=lambda *_: None,
                                    on_default_device=lambda: events.append('device'))
    assert source.start() and source.snapshot() is None
    assert source.start() and len(enumerator.callbacks) == 1
    enumerator.callbacks[0].OnDefaultDeviceChanged(0, 1, 'new-device')
    assert events == ['device']
    monkeypatch.setattr(AudioUtilities, 'GetSpeakers', original_speakers)
    assert source.rebind() and source.snapshot() == (0.55, False)
    assert len(enumerator.unregistered) == 1 and len(endpoints[0].callbacks) == 1
    source.stop()


def test_actions_reuse_registered_endpoint_and_stop_after_retirement(fake_core_audio):
    endpoints, enumerator = fake_core_audio
    values = []
    source = CoreAudioCallbackProbe(
        on_volume=lambda volume, muted: values.append((volume, muted)),
        on_default_device=lambda: None,
    )
    assert source.start()
    assert source.set_mute(True)
    assert source.set_volume(0.25)
    assert source.snapshot() == (0.25, True)
    assert values == [(0.55, True), (0.25, True)]
    assert len(endpoints[0].callbacks) == 1 and len(enumerator.callbacks) == 1
    with pytest.raises(ValueError):
        source.set_volume(-0.1)
    source.stop()
    assert source.set_mute(False) is False
    assert source.set_volume(0.5) is False
    assert source.snapshot() is None


def test_actions_are_confined_to_owning_com_apartment(fake_core_audio):
    source = CoreAudioCallbackProbe(on_volume=lambda *_: None, on_default_device=lambda: None)
    assert source.start()
    errors = []
    def wrong_apartment():
        for action in (lambda: source.set_mute(True), lambda: source.set_volume(0.7)):
            try:
                action()
            except RuntimeError as exc:
                errors.append(str(exc))
    worker = threading.Thread(target=wrong_apartment)
    worker.start(); worker.join()
    assert len(errors) == 2 and all("COM apartment" in item for item in errors)
    source.stop()
