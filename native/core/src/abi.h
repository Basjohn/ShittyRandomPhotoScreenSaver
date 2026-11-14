// The contract between this module and its one Python importer, rendering/native/ (D5.7).
//
// SRPSS_NATIVE_CORE_ABI is the version of everything the Python face calls or reads: the module's functions, their
// arguments, the keys of runtime_info(). It is raised whenever any of those changes, together with EXPECTED_ABI in
// rendering/native/loader.py (tests/test_native_core_loader.py fails while the two differ), so a module built from
// another commit is refused at load with one reason instead of failing somewhere later.
//
// 2 (N2.2): the host adapter and the frame driver (host_attach returns a handle; host_*, vulkan_instance_*,
// process_counters).
// 3 (N2.4): the composite (composite_create/set/state/destroy, composite_live); the hidden host's device pixel ratio
// (host_attach's sixth argument, host_set_dpr) and Qt Quick's target read back (host_read).
// 4 (N2.6): the GPU timer (host_gpu_timer, host_gpu_samples, gpu_timer_live), the known-cost pass (host_load), the
// hidden host's QRhi timestamps (host_attach's seventh argument).
// 5 (N2.3): the packet reader (packet_reader_open/read/head/frame/drop/retire/release/state/close, packet_reader_live)
// and the compiled-in frame schemas (frame_schemas).
// 6 (N2.5): Spectrum on a composite (composite_spectrum_bind/unbind/present/drop/head/state/wait_paused/resume,
// composite_update, spectrum_block, spectrum_block_layout; composite_live's Spectrum counts), the packet reader's
// pause_in_copy hook (packet_reader_wait_paused/resume) and its post-copy retiring check.
#pragma once

#define SRPSS_NATIVE_CORE_ABI 6
