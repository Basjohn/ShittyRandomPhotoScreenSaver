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
// composite_live's stage_records_timed and stage_record_ns; a defocus read level past defocusReadLevelCap is refused;
// stage_control's time_defocus_draws and composite_live's stage_defocus_timed, stage_gather_gpu_ns, stage_sprites_gpu_ns
// and stage_defocus_time_skipped (the defocus cost's diagnosis).
#pragma once

// 21 (N3.1c L3): scene_target_control (placement, one-pixel allocation bucket, bounded allocation steps) and
// host_invalidate_scene_graph (hidden-host harness; actual render-thread QQuickRenderControl invalidation).
// 22: scene-target scissor controls and stage_control's flush_defocus_draws (same boundaries without queries).
// 23: isolate the three flush_defocus_* sites; composite_live's stage_defocus_flushes proves which boundaries ran.
// 24: complete mip readbacks with level-relative content; bounded stage allocation/build fault controls and counters.
// 25: OpenGL declaration-only and compute-tracker-only defocus diagnostics, with counters of actual controlled flags.
// 26 (N5.1, the Oscilloscope): a program's "unread", the record's fields it reads nowhere (a stage it leaves out reads
// them: the Glow 0 program's bloom strength); each must be a field of the record that no pass, draw or stream reads, any
// other record field no pass reads is refused as before. The program's layout JSON carries "unread". Backward
// compatible for every earlier program (no "unread": ABI 25's check).
// 27 (N5.1, the lead's decision 21 Nov: Python's SceneTarget is the oracle): the core member u_scene_item (the item's
// cover in the target's pixels, from the card: mode_core_members, mode_core_values); the composite step's forms read it
// (their texel, glow and dither from the item's own pixel, discarded outside the item) and a bloom step's first
// downsample starts from the item's own pixel in a surface-sized source; stage_control's bloom_at_target_origin (its
// negative control). A new stream's first sync clears the old stream's frame whatever that read is (an admission-
// rejected first frame left the previous mode's frame shown). Unchanged for an item that covers its target.
// 28 (checkpoint audit 10; the lead's decisions, 21 Nov): H1, a surface-sized scene target of a program with a composite
// step takes Python's SceneTarget geometry (sceneAnchor: the item's pixel at its content's bottom left, the content the
// 64-pixel bucket of the item's cover), so it holds the light past the item's right and top edges that Python's
// allocation slack holds; the composite forms read the scene at the item's texel. M2, the card's optional "scene_item"
// (Python's item_pixel_rect in the target's pixels) is the core's one source of the item's rect (u_scene_item; no
// re-derivation). M3, a bloom or composite step under a turned card is refused (its anchoring is unturned only).
// 29 (N5.1, turned-card anchoring; checkpoint audit 10 M3): a composite step may declare "scene_frame": "window" (the
// mode's Python scene drawn through Quick's window, unturned: the Oscilloscope turns at the vertex). Under a turned card
// such a program's surface-sized scene target takes Python's SceneTarget geometry in the window's frame (sceneAnchor:
// the item's window rect, from scene_item through window_from_target, its bucket the content), and the composite forms
// read the scene, glow and dither key at Python's texel through the core members u_scene_from_target_x/_y (the surface's
// pixel to the scene's texel; the surface's own, as at ABI 28, for an unturned card). A turned card's bloom or composite
// without the declaration is still refused. stage_control's scene_frame_surface (the negative control: the turned scene
// anchored in the surface's frame). Unchanged for an unturned card.
// 30 (N3.6, lifetime: the device loss): host_force_device_lost (harness: the hidden host's next frame takes the lost
// path, swap_device False its control); the host states' device_losses and lost_device_alive, the hidden host's
// loss_forced_pending and vulkan_live_devices, the device facts' device_fault. A window host replaces a lost Vulkan
// device itself (no call). Backward compatible for every earlier caller. Within 30 (N3.6's pipeline cache, the same
// unbuilt round): pipeline_cache_self_test (GPU-free) and pipeline_cache_directory (the harness's directory of the
// core's file); the job service's stop record's pipeline_cache_load and pipeline_cache_save. Within 30 (N3.6's release
// timing): host_detach's at_frame_edge (harness, a hidden host), raw_vulkan_counts, the frame driver state's
// raw_vulkan_released and no_frame_finishes, the GPU timer state's deferred_releases; every QRhi resource is retired by
// deleteLater (rhi_owned.h), the GPU timer's pool retired inside a frame goes to the device's deferred queue.
// 31 (N3.6, checkpoint audit 11): host_inject_device_lost (harness, Vulkan: Qt's queue answers its next submit, or
// every one with sticky, with VK_ERROR_DEVICE_LOST, so Qt's own QRhi reports the loss; M1), vulkan_device_create_failures
// (harness: forced device creation failures, and the injection's counts; M2), rhi_owned_counts (L1). The hidden host
// retries a replacement device it could not make at each next frame (its frames fail with the reason until then) and its
// state's replacement_pending, device_lost_marked and core_wrappers_live; a loss record's replacement_attempts,
// replacement_failures, device_already_lost, replacement_pending, retried_at_frame, core_wrappers_live_before and
// core_wrappers_live_after_invalidation; the hidden host's close record's core_wrappers_live_after_invalidation; the job
// service's stop record's told_device_lost and device_lost and its self-test's device_was_lost step (L2). RhiOwned is a
// class (rhi_owned.h). Backward compatible for every earlier caller.
// 32 (the lead's decision, 21 Nov: Spline Curve's long-take residuals fixed at the source): a mode's own pass reading
// v_uv on the surface draws over the card's own quad (mode_content.cpp cardQuad: Python's item quad, its strip's two
// triangles, exact corner uv turned as Python's vertex stage turns it), not the full triangle; scene-target passes, the
// core's steps, vUv passes and a card-less content are unchanged. stage_control's card_triangle (harness: the full
// triangle again, its negative control). Every generic mode's native frames may change (regression guards on the branch's ABI 31 build: every generic
// mode's harness on both APIs, Bubble variant a on one take).
// 33 (N5.4, Waveform's five C++ boxes): a target's "allocation": "exact" (the content's exact
// size, no bucket) and a drawable mipped target (a mipped target no defocus step reads: a depth and an explicit size
// allowed; a sampler reading an RGBA16F attachment's levels with "mips", whose chain the core's box kernel makes after
// each run on it, shaders/mip_box.comp, never generateMips; the layout JSON's targets carry "self_mips" and
// "allocation", their attachments "mips_read"; composite_live's scene_target_mips); composite_mode_texture's
// seventh argument half_float (an RGBA16F item texture, its chain generated on the GPU; the textures' state "format");
// kMaxModePasses 28 (16 before) and kMaxStorageImages 9 (8 before); compute_control's no_float32_linear (harness: a
// device without linear filtering of 32-bit floats), the device facts' linear_filter_formats (Vulkan's
// SAMPLED_IMAGE_FILTER_LINEAR_BIT per storage format) and the compute facts' linear_filter_formats and
// float32_linear_control; a linear sampler over a storage image this device does not filter linearly fails the
// content with its reason. Backward compatible for every earlier program and caller.
// 34: retired unused (N5.2c moved to 36).
// 35 (N5.4, the Waveform port's two core gaps): (1) an item texture with mips has its chain made by the core's box kernel
// (the lead's decision of 21 Nov: every level chain a sampler reads), shaders/mip_box.comp (RGBA16F) and
// shaders/mip_box_rgba8.comp (RGBA8), the texts rendering/gl_programs/mip_chain.py gives the Python renderer, on both
// upload routes (in the frame; a job uploads level 0 and the render thread makes the chain after the import), never
// generateMips; one kernel owner for the textures and the self-mipped targets (mip_chain.h); a device without compute
// refuses such a texture with its reason; composite_live's mode_texture_chains. (2) A composite step's "scene_frame":
// "oriented" (Python's orient_visualizer_scene_frame: Waveform's scene drawn in the content's orientation): under a turned
// card the scene target is Python's SceneTarget of the oriented frame and the composite reads Python's sceneTexel; the
// card's optional scene_oriented (the item's rect in the oriented viewport) and scene_from_window (the window's pixel to
// that viewport's), both or neither; a turned card of such a program without them is refused. Item textures with mips
// may draw differently where a level is made from an odd size (no product mode samples them before Waveform);
// backward compatible for every other program and caller.
// 36 (N5.2c with N4.j): a program's environment step ({"name", "environment": an item texture, "size": [w, h]}: N4.j's
// photo environment, post_stages.h; its copy "<step>.environment", its chain made by the core's box kernel (mip_chain.h,
// never generateMips), read with mips), the composite form "opaque" (no glow), composite_live's stage_environments and
// stage_environment_copies, and the lost edge's "mesh:<name>" (a mesh a content made again has nothing to upload from:
// the owner sends it again). Backward compatible for every earlier program (no program declares either; an owner without
// a mesh listener ignores the name).
// 37 (N4.i motion blur and trails, with N5.2d): a compute entry's "trigger": "draw" (dispatched at every record that
// draws the program's passes: a still's only compute trigger, the motion blur's tile max over this record's velocity);
// the target format "r8" (the trails' ghost buffer); an attachment a pass masks ("write": false) may be left unwritten
// by its shader; a setting scoped to one pass ("<member>@<pass>": the trails' ghosts, one pass a ghost from one pack);
// a pass's "viewport": "allocation" (the core's triangle over a scene target's whole allocation: the trails' edges);
// the item texture format rgba32f (composite_mode_texture's eighth argument full_float, no mips: Crumble's motion
// table). Backward compatible for every earlier program and caller (none declares any of them).
// 39 (black flicker at a transition's start on Vulkan): a content waiting for its textures or meshes keeps the frame its
// target holds (as a refused build does, M4) instead of recording no pass over a cleared target; composite_mode_state's
// waiting_kept counts those records. Backward compatible for every caller (only a waiting content's frame changes).
// 40 (N5.4, the Waveform port's own-camera scene): a record's f64 field fills a vec2, vec3, vec4 or mat4 member (its
// numbers the member's components times its elements, columns first) and its u32 field an int vector under a range
// rule at most 2147483647 (program_blocks.cpp recordFieldFits); the conventions block's w is 1 where the target's clip
// depth runs 0 to 1 (QRhi::isClipDepthZeroToOne: Vulkan, D3D, Metal; it was a reserved 0), read by
// rendering/gl_programs/conventions.py SRPSS_TARGET_CLIP_GLSL; a graphics pass's samplers take their declared wrap on W
// too (QRhi's default Repeat blended a 3D image's first and last slices; 2D samplers unchanged). Backward compatible
// for every earlier program (no shader before Waveform reads w or samples a 3D image in a graphics pass). And a
// composite step's "scene_rows": "up" (overlay_glow only): the scene holds OpenGL's rows (its bottom row at the
// target's memory row 0, Python's SceneTarget memory), read there by the composite through the new core member
// u_scene_rows_up (0 for every other program: their composites read as before). Waveform draws its scene so: drawn
// flipped, its anti-aliased edges met the multisample pattern mirrored and differed from Python's (the bloom carried
// them; one sample a pixel drew alike).
// 41 (N5.2f with N4.c): the storage state's device facts draw_indirect and draw_indirect_multi (QRhi::DrawIndirect and
// DrawIndirectMulti, compute_passes.cpp computeDeviceFacts) and mesh_buffer_control's hide_draw_indirect, the harness
// control under which an indirect pass is refused with its reason, both facts read false and the draw-parameters forms
// fall back to one draw a batch (mesh_buffers.h drawIndirectAvailable: the one answer every reader takes). Backward
// compatible for every program and caller (the facts are new keys; the control is off unless set).
// 42 (N5.6, Extruded Bubble's core boxes; reserved by the lead, 22 Nov): (1) the scene probe (scene_targets.h,
// cube_prefilter.h): a target's "cube": true (an explicit square size, one rgba16f attachment, one sample, exact; a
// D32F depth shared by its faces), a pass's "face": 0..5 into it (one render target per face, cleared per face, drawn
// in OpenGL's cube-map rows: the cube triangle's flipped uv and the uMatrix's extra Y flip; no culling), a prefilter
// step ({"name", "prefilter": <cube>}, an empty pack: probe.py's 32-tap cone filter per level and face into a stage
// cube, copied into the cube's level), a samplerCube reading "<cube>.<attachment>" with mips; the readback's
// "<target>.<attachment>#<face>@<level>"; composite_live's scene_cube_face_runs, scene_cube_prefilters and
// scene_cube_level_copies. (2) Geometry once per key (D3, geometry_arena.h): a storage buffer's {"name", "geometry":
// {"family", "key"}} form (read only; its key the record's u32 array of 8 words), composite_mode_geometry_arena(handle,
// name) naming the activation's arena, "<name>@previous" bindable by a compute entry (the rebase record), and
// composite_live's geometry_resident, _uploads, _failed, _released, _waits, _arenas, _reads_found and _reads_torn.
// (3) The drift pair check's readback: a compute trigger "once" (the entry's first record with its storage) and an
// entry's "readback": <a buffer it writes> (one a program, at most 4096 bytes), read once after its dispatch, taken
// at a later record and reported once (the content's state "check": floats and hex; one log line); composite_live's
// check_readbacks, check_readback_bytes and check_reports. (4) The limits: kMaxModePasses 28 to 48 (the missing-mesh
// mask one bit a pass) and kMaxSceneTargets 4 to 6 (the probe cube among them); the face's MAX_PASSES and MAX_TARGETS.
// (5) A pass's "when": a record u32 scalar; at a record where it is 0 a draw pass draws nothing and a defocus step makes
// none of its passes (never on a compute entry, capture, cube face, prefilter, bloom or environment step);
// composite_live's mode_entries_skipped.
// Backward compatible for every earlier program (none declares a cube or a geometry buffer).
// 43 (N5.2g with N4.g; reserved by the lead, 22 Nov): field recipes (field_recipe.h): composite_mode_field(handle,
// recipe_json, packs, blocks, pixels=None, (w, h), in_frame, deadline_ms) makes an item's field outputs (Edge Bloom's
// edge fields, Capillary Bloom's arrival and extent) from a flat list of compute dispatches over the recipe's images,
// recorded by one recorder in two forms (D9 point 5): a field job on the device's job service (the input photo uploaded
// by the job from `pixels`; its outputs published together under consecutive ids) or in the frame at the commit over the
// input's front (OpenGL, no service, a failed job, in_frame, and the core's deadline: a job past deadline_ms gives way
// at the next record); the outputs commit with the item's other textures. The mode texture format r32f (a field's
// output, never with mips). composite_mode_on_ready(handle, callable): the owner's ready edge, once per record that
// committed textures, with their names (the transition's start). field_recipe_check (GPU-free admission) and
// field_counts; the content state's "fields" and textures_ready_edges / _delivered; the job self-test's submit_field.
// Backward compatible for every earlier program and caller (no texture is a field's output unless sent so; the ready
// edge only calls a listener that is set).
// 44 (N5.6, Extruded Bubble drift): the program can declare up to 16 storage buffers, including geometry buffers.
// The existing limit of 8 storage bindings per compute entry still applies. Earlier programs remain valid.
// 45 (N5.6): reflected column-major mat3 members, including arrays, take nine numbers per matrix in settings and
// f64 record fields. Columns use the qsb matrix stride.
// 46 (N5.6, Extruded Bubble's record and route; reserved by the lead, 27 Nov): a compute entry binding a geometry
// buffer is dispatched only at a record whose key for it is resident (ModeContent::geometryKeysResident); a held entry
// keeps its trigger, so u_srpss_compute's last-dispatch value names the last step it applied and the next record
// dispatches the window's suffix after it; composite_live's compute_geometry_holds. Backward compatible for every
// earlier program (an entry binding no geometry buffer is never held).
// 47 (N5.6, Extruded Bubble's program; awaiting the lead's reservation): a pass between a transparency target's first
// pass and its resolve may sample the owner's capture (<owner>.capture_colour / capture_depth: its own texture, copied
// before the first pass, which no capture of the owner follows there); the owner's attachments stay refused. Backward
// compatible for every earlier program (it only admits more).
#define SRPSS_NATIVE_CORE_ABI 47
