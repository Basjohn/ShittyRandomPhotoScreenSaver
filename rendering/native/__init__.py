"""The native core's Python face (D5.7): the only importer of ``_srpss_native_core`` and the host adapter's Python
side (D5.1). ``load()`` checks the module's Qt version and ABI and fails in one place with one reason
(``NativeCoreUnavailable``); ``NativeCore.attach_host`` and ``NativeCore.hidden_host`` give the hosts
(``rendering.native.hosts``). Nothing in the product calls it yet (Current_Plan.md item 8b; N2.7 adds the backend
owner)."""
from rendering.native.hosts import PROBE_OPTIONS, HiddenHost, Host, ProbeReadback, WindowHost
from rendering.native.loader import (
    EXPECTED_ABI,
    HOST_KINDS,
    MODULE_NAME,
    NativeCore,
    NativeCoreUnavailable,
    load,
)

__all__ = ["EXPECTED_ABI", "HOST_KINDS", "MODULE_NAME", "PROBE_OPTIONS", "HiddenHost", "Host", "NativeCore",
           "NativeCoreUnavailable", "ProbeReadback", "WindowHost", "load"]
