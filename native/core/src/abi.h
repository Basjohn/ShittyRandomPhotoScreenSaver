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
// pause_in_copy hook (packet_reader_wait_paused/resume) and its post-copy retiring check; a reader handle owned by its
// references (packet_reader_close never deletes under a read; packet_reader_live's "closing"); the identity checked before
// the schema.
// 7 (N2.5 rule (a)): the Spectrum card's window maps (window_from_target, item_from_window replace item_from_target):
// the target's pixel is rebuilt as the window's and mapped by the Python renderer's own float32 rows.
// 8 (N2.5 round 4, the standing port rule): the Spectrum program (composite_spectrum_program: the fragment pack loaded
// at run time; composite_spectrum_settings: Settings-derived members by name, packed by program_blocks.h);
// spectrum_block takes the pack and the settings; spectrum_block_layout takes a pack; the composite's surface_format
// option (rgba8, rgba16f; N2.5 rule (a)). Round 4 never compiled (limited-API macros): round 5 is ABI 8's first build.
// 9 (N2.3 leftovers, audit 14 Nov lows): the packet reader's controls split (skip_seqlock is now skip_head_seqlock and
// skip_copy_reread) and copy_while_retiring added; packet_reader_state no longer has dropped_through. The N2.5 audit's
// fixes: the composite's pixel_ratio option (the window's own logical-to-framebuffer ratio per axis, H1); a Spectrum
// content that failed to build reports content_failed/content_failures once and is not rebuilt every frame (M2).
// Also 9 (N2.9, generic mode content, built in the same round): composite_mode_bind/unbind/program/settings/drop/head/
// state/retire, mode_blocks, mode_program_layout, program_block_pack; packet_reader_open's schema argument;
// composite_live's mode counts; the Spectrum program refused when it does not take the current settings (audit L4).
#pragma once

#define SRPSS_NATIVE_CORE_ABI 9
