"""Windows Core Audio callback transport for the one shared audio owner.

Everything COM-owned is created, used and retired on one GUI/COM apartment.
The callbacks only copy scalar notifications and queue a device handover;
they never query/rebind the endpoint or invoke GUI/QML themselves.
"""
from __future__ import annotations

import threading
import weakref
from typing import Callable


class CoreAudioCallbackProbe:
    """One shared endpoint subscription; never instantiate per display/OSD."""

    def __init__(self, *, on_volume: Callable[[float, bool], None],
                 on_default_device: Callable[[], None]) -> None:
        self._thread = threading.get_ident()
        self._on_volume = on_volume
        self._on_device = on_default_device
        self._endpoint = None
        self._volume_callback = None
        self._enumerator = None
        self._device_callback = None
        self._binding_token = 0
        self._active = False

    def _assert_owner(self) -> None:
        if threading.get_ident() != self._thread:
            raise RuntimeError("Core Audio registration/teardown require owning COM apartment")

    def start(self) -> bool:
        self._assert_owner()
        if self._device_callback is not None:
            return True
        # Dependencies are deliberately imported only upon explicit B0 start.
        from comtypes import CLSCTX_ALL, COMObject
        from pycaw.pycaw import (AudioUtilities, IAudioEndpointVolume,
                                 IAudioEndpointVolumeCallback, IMMNotificationClient)

        parent_ref = weakref.ref(self)
        binding_token = self._binding_token + 1

        class VolumeCallback(COMObject):
            _com_interfaces_ = [IAudioEndpointVolumeCallback]

            def OnNotify(self, notification):
                parent = parent_ref()
                if parent is None:
                    return 0
                data = notification.contents
                if parent._active and binding_token == parent._binding_token:
                    try:
                        parent._on_volume(float(data.fMasterVolume), bool(data.bMuted))
                    except Exception:
                        pass  # No Python exception may escape into the COM caller.
                return 0

        class DeviceCallback(COMObject):
            _com_interfaces_ = [IMMNotificationClient]

            def OnDefaultDeviceChanged(self, flow, role, device_id):
                parent = parent_ref()
                if parent is None:
                    return 0
                # GetSpeakers selects the default multimedia *render* endpoint.
                if (parent._active and binding_token == parent._binding_token
                        and int(flow) == 0 and int(role) == 1):
                    try:
                        parent._on_device()
                    except Exception:
                        pass
                return 0

            def OnDeviceStateChanged(self, device_id, state):
                return 0

            def OnDeviceAdded(self, device_id):
                return 0

            def OnDeviceRemoved(self, device_id):
                return 0

            def OnPropertyValueChanged(self, device_id, property_key):
                return 0

        try:
            enumerator = AudioUtilities.GetDeviceEnumerator()
            if enumerator is None:
                return False
            device_callback = DeviceCallback()
            enumerator.RegisterEndpointNotificationCallback(device_callback)
            self._enumerator = enumerator
            self._device_callback = device_callback
            # Admit device changes immediately after registration, before
            # querying the current speaker. A switch during endpoint acquire
            # must queue a new-generation handover rather than leave us on the
            # old speaker until an unrelated future notification.
            self._binding_token = binding_token
            self._active = True
            # Keep the *device* subscription alive even when output is absent.
            # A subsequent default-output event can restore the endpoint with
            # no state poll or background retry chain.
            devices = AudioUtilities.GetSpeakers()
            if devices is not None:
                interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                # QueryInterface, never ctypes.cast: cast shares the raw COM
                # pointer without AddRef and ties the source into a ctypes
                # reference cycle, so dropping the endpoint freed the object and
                # a later GC released it again (access violation on retire/rebind).
                endpoint = interface.QueryInterface(IAudioEndpointVolume)
                del interface
                volume_callback = VolumeCallback()
                endpoint.RegisterControlChangeNotify(volume_callback)
                self._endpoint = endpoint
                self._volume_callback = volume_callback
            return True
        except Exception:
            self.stop()
            raise

    def snapshot(self) -> tuple[float, bool] | None:
        self._assert_owner()
        if self._endpoint is None:
            return None
        return (float(self._endpoint.GetMasterVolumeLevelScalar()),
                bool(self._endpoint.GetMute()))

    def set_mute(self, muted: bool) -> bool:
        """One explicit user action on the owning COM apartment; no callback write-back."""
        self._assert_owner()
        if not self._active or self._endpoint is None:
            return False
        self._endpoint.SetMute(int(bool(muted)), None)
        return True

    def set_volume(self, level: float) -> bool:
        """Set bounded master volume on the retained endpoint, never on a stale one."""
        self._assert_owner()
        if not self._active or self._endpoint is None:
            return False
        target = float(level)
        if not 0.0 <= target <= 1.0:
            raise ValueError("master volume must be in [0.0, 1.0]")
        self._endpoint.SetMasterVolumeLevelScalar(target, None)
        return True

    def rebind(self) -> bool:
        self._assert_owner()
        self.stop()
        return self.start()

    def stop(self) -> None:
        self._assert_owner()
        self._active = False
        self._binding_token += 1
        endpoint, volume_callback = self._endpoint, self._volume_callback
        enumerator, device_callback = self._enumerator, self._device_callback
        # Disable admission before deregistration, allowing late callbacks to
        # reach only the generation-fenced mailbox rather than touching COM.
        self._endpoint = self._volume_callback = None
        self._enumerator = self._device_callback = None
        try:
            if endpoint is not None and volume_callback is not None:
                endpoint.UnregisterControlChangeNotify(volume_callback)
        finally:
            if enumerator is not None and device_callback is not None:
                enumerator.UnregisterEndpointNotificationCallback(device_callback)
