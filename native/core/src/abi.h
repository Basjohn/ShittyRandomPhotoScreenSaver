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
// 10 (N2.9 round 2, audit 14 Nov N29): the generic pass in the product 2D shaders' shape (one block of its own filled
// by name from the core's conventions, the settings and the record; v_uv); composite_mode_card, mode_core_members;
// mode_blocks takes the card and the target and returns one block per pass; composite_window_pixels (Qt's own
// framebuffer, L1); the composite's fade_ms option (M1) and its shown/shown_opacity/fading state; a Spectrum call on an
// item that draws a mode is refused (L3), composite_spectrum_present included; the states' refused_frames,
// last_refusal, content_failures (M2, M4).
// 11 (N4.a, the fullscreen pass and image sampling): a pass's samplers bound by name in its program's declaration
// (samplers: [{name, texture, filter, wrap, mips}]); its location-0 input named v_uv or vUv (mode_program_layout's "uv"
// is that name); composite_mode_texture and composite_mode_texture_remove; composite_live's mode_texture counts;
// composite_mode_state's textures, texture_uploads, textures_resident, textures_lost.
// 12 (N2.9 round 2's audit): v_uv is the item's oriented uv from the card (M6; vUv unchanged); composite_content_status
// (M4, M5: draws, failures, refused_run, failing); the surface clears a target its content never wrote (M4; the
// state's surface clears); composite_window_pixels only from the item's last sync, invalid when stale (L1, M3);
// an unbound stream keeps its last frame (L3); the content latch keyed on the target's generation, the program and the
// settings, not the card, with a bounded retry (L4); mode_core_values (L6); the states' content_failing, refused_run
// and the reader live JSON's state_json_off_gui_thread (L2).
// 13 (N2.8, R-NEW: the Vulkan card's diagonal break): the composite's vertex stage puts the item's quad on whole pixels
// of its render target wherever the item is placed (the block's viewport member); composite_state's origin_shift (the
// last draw's shift of the item's origin, per axis, in target pixels).
// 14 (N3.8, D9's job service): the Vulkan device's second queue and job service; composite_mode_texture's in_frame
// control; composite_mode_on_lost (the lost edge); job_counts, job_services_state, job_services_wait_idle and
// job_service_self_test; composite_mode_state's texture_jobs, image_changes and textures_lost_edges; the host state's
// device queues and job_service; the frame driver state's retired_outputs_released and window_edges.
// 15 (N5.7a, the background layer; the N3.8 audit): composite_mode_still (a generic mode drawn with no stream);
// composite_set's layer (content, background: recorded first) and opaque (Qt's opaque pass); composite_state's surface
// kept_records and layer, its sync's material_blending and layer; composite_mode_state's still, still_kept and
// textures_lost_listener (cleared by composite_mode_retire, L4); the frame driver state's window_retire_frame_requests
// and window_retiring (M2); window edges counted once per frame (M1; window_edges_self_test); the job service's device-loss, thread-start and
// briefJson rules (L1-L3), its self-test's lose_device, fail_thread_start and running_state; the commit's two phases (L5).
// 16 (N5.7b, the backdrop pyramid; backdrop.h): backdrop_create/set/build/levels/state/destroy and
// backdrop_pyramid_sizes; composite_live's backdrop_items, backdrop_pyramids, backdrop_resources and backdrop_builds;
// the GPU timer's pass kind 4 (backdrop); the frame driver state's backdrop_builds and window_backdrops. Backward
// compatible for every earlier caller: the surface's drawn generation and window placement and the frame driver's
// backdrop step after the background layer are additions; primeForLoad transitions every mip level (one for every
// single-level target, as before).
// 17 (N3.1, scene targets; D14, scene_targets.h): a program's "targets" and a pass's "target", "attachments", "depth"
// and capture steps ({"name", "capture"} with an empty pack); samplers naming "<target>.<attachment>"; the blend
// "additive" (ONE, ONE: emitted light, Bubble's ambient light); at most 16
// passes (8 before); composite_mode_target_size, composite_mode_target_read and composite_mode_target_pixels (harness);
// scene_sample_counts_control (the clamp's control); scene_depth_prime_control (build round 2: rule C for depth's
// control) and composite_live's scene_target_depth_primes (still 17: round 2 of the same unmerged N3.1); round 3 (D14
// point 10, still 17): an attachment's "resolve" ("average" or "nearest"), the core's nearest resolve in place of
// QRhi's depth resolve, scene_nearest_first_sample_control (its control), composite_live's
// scene_target_nearest_resolves and the readback's "<target>.depth" when multisampled; audit 2 (still 17):
// scene_resolve_prime_control and composite_live's scene_target_resolve_primes; R-223 (still 17): gpu_timer_ring_simulation
// (GPU-free), the timer state's abandoned_slots, the OpenGL hidden host's frames finished; scene_target_next_allocation, scene_target_viewport and
// scene_target_clamp (GPU-free); composite_live's scene_targets, scene_target_textures, scene_target_bytes,
// scene_target_allocations, scene_target_steps and scene_target_readbacks; composite_mode_state's scene_targets,
// target_reads_requested and target_readback_pending; a program's layout JSON carries targets and each pass's target,
// capture, attachments, depth and frag_depth. Backward compatible for every earlier program (no targets: N2.9's passes).
// 18 (N3.2, meshes and buffers; D15, mesh_buffers.h): a pass's "vertex" (its vertex pack after its fragment's; a batched
// pass's draw-parameters pack after that) and geometry ("topology", "vertices", "instances", "first_vertex", "mesh",
// "instance_from", "storage", "cull", "front_face", "indirect", "draw_count", "batches", "batch_count"); a blend as a
// full declaration; a program's "streams"; the record's f32 field kind (frame_abi_generated.h); composite_mode_mesh and
// composite_mode_mesh_remove; the core member uMatrix filled for a pass with its own vertex stage and u_srpss_batch;
// the conventions block's z (clipTopDown); every block in one arena given by dynamic offsets (N2.9 and N3.1's passes
// too, their outputs unchanged); mesh_buffer_control (harness), mesh_buffer_arena_layout (GPU-free) and
// vulkan_device_facts; composite_live's mesh_buffers_* counts; composite_mode_state's meshes and mesh_buffers.
// Backward compatible for every earlier program. Within 18 (before its first use, the lead, 15 Nov): an f32 stream's
// "used" (a u32 field under an at_most rule within its count; only the used bytes are written), mode_blocks' optional
// clip correction, and composite_live's mesh_buffers_records_timed, _record_ns and _stream_write_ns. Within 18 after
// checkpoint audit 4 (the lead, 15 Nov; no consumer yet): an instance stream is drawn exactly its used records (another
// instance count refuses the draw), the draws' counts are checked against their buffers at the record (a count past
// one refuses the draw), mesh_buffer_control's instances_past_used, composite_live's mesh_buffers_draws_refused and
// the mesh-buffer state's draws_refused.
// 19 (N3.3, compute passes; D16, compute_passes.h): a program's "buffers" and "images"; a compute entry in the pass list
// ({"name", "compute": true, "trigger", "groups", "bindings", "samplers"}, one compute pack); the core member
// u_srpss_compute (a uvec4); a draw's "storage", "instance_from" and "indirect" naming a storage buffer, and its samplers
// a storage image (sampler3D for a 3D one); a mesh declaration's "storage"; the lost edge's "state:<resource>" names;
// composite_mode_image_size, composite_mode_storage_read and composite_mode_storage_data (harness), compute_control
// (harness); composite_live's compute_* counts; composite_mode_state's storage, storage_reads_requested,
// storage_readback_pending and storage_held; vulkan_device_facts' queue_family_compute,
// shader_storage_image_extended_formats, max_compute_work_group_count_x, max_compute_work_group_invocations and
// storage_image_formats. Backward compatible for every earlier program (no compute: N3.2's passes).
// 20 (N3.4, transparency and post-processing as shared stages; D17, post_stages.h): a target's "transparency" ({"of",
// "borrow"}) and "mips"; a transparent pass's sorted pack ("sorted": true, the pack after its others); the steps
// {"transparency_resolve", "alpha"}, {"bloom"}, {"defocus", "onto"} and {"composite", "scene", "glow"} (an empty pack
// each); a sampler naming "<bloom step>.glow"; stage_control (harness); composite_live's stage_* counts; the targets'
// state's transparency_fallbacks and each target's transparency_of, borrow and mips; composite_mode_target_pixels'
// "level" (a mipped target's every level read back); vulkan_device_facts' independent_blend, sample_rate_shading and
// color_attachment_blend. N3.1's check of differing attachment states reads the core's device facts (independentBlend on
// Vulkan), never QRhi's PerRenderTargetBlending. Backward compatible for every earlier program (no stage: N3.3's).
// Within 20 (the proof's findings, before any consumer, the lead, 15 Nov): stage_control's skip_read_chain;
// composite_live's stage_records_timed and stage_record_ns; a defocus read level past defocusReadLevelCap is refused.
#pragma once

#define SRPSS_NATIVE_CORE_ABI 20
