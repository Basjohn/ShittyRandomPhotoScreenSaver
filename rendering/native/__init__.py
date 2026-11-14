"""The native core's Python face (D5.7): the only importer of ``_srpss_native_core`` and the host adapter's Python
side (D5.1). ``load()`` checks the module's Qt version and ABI and fails in one place with one reason
(``NativeCoreUnavailable``); ``NativeCore.attach_host`` and ``NativeCore.hidden_host`` give the hosts
(``rendering.native.hosts``); ``NativeCore.composite`` the composite item, placed from a presentation record by
``rendering.native.composite`` (N2.4); ``rendering.native.gpu_timing`` the per-pass GPU timer's samples and their
frame-trace records (N2.6). The product's one caller is the backend owner, ``rendering.quick.bootstrap`` (Current_Plan.md
item 8b N2.7), and only on the Vulkan rehearsal path or for its one kept hidden host."""
from rendering.native.composite import (
    COMPOSITE_OPTIONS,
    SURFACE_PATTERNS,
    CompositeGeometry,
    CompositeItem,
    composite_geometry,
)
from rendering.native.gpu_timing import GPU_PASS_KINDS, GpuSample, write_to_frame_trace
from rendering.native.hosts import PROBE_OPTIONS, HiddenHost, Host, ProbeReadback, QuickFrame, WindowHost
from rendering.native.loader import (
    EXPECTED_ABI,
    HOST_KINDS,
    MODULE_NAME,
    NativeCore,
    NativeCoreUnavailable,
    load,
)
from rendering.native.mode import MODE_CORE_MEMBERS, PASS_BLENDS, ModePass, NativeMode, mode_card, schema_table_entry
from rendering.native.packet_reader import (
    READ_RESULTS,
    READER_CONTROLS,
    NativeFrame,
    PacketReader,
    SchemaTableMismatch,
)
from rendering.native.spectrum import SPECTRUM_PRESENTATION_KEYS, NativeSpectrum, spectrum_presentation

__all__ = ["COMPOSITE_OPTIONS", "CompositeGeometry", "CompositeItem", "EXPECTED_ABI", "GPU_PASS_KINDS", "GpuSample",
           "HOST_KINDS", "MODE_CORE_MEMBERS", "MODULE_NAME", "ModePass", "NativeFrame", "NativeMode", "NativeSpectrum",
           "PASS_BLENDS", "PROBE_OPTIONS", "PacketReader", "mode_card", "schema_table_entry",
           "READER_CONTROLS", "READ_RESULTS", "HiddenHost", "Host", "NativeCore", "NativeCoreUnavailable",
           "ProbeReadback", "QuickFrame", "SPECTRUM_PRESENTATION_KEYS", "SURFACE_PATTERNS", "SchemaTableMismatch",
           "WindowHost", "composite_geometry", "load", "spectrum_presentation", "write_to_frame_trace"]
