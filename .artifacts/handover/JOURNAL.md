# N5.2h "Switch-caused and NOT fixed" (proof run 28 Nov), agent aa3b364fd31f5d860

2026-11-28. Merged worktree-agent-aa7af460a1382fb30 (9744222bb). Module f9d4399e copied into release/native_module.
- Item 1 (card-material pixel tests) DONE: tools/surface_material_capture.NativeHiddenScene (the scene root as the
  kept hidden native host's content; timestamps=True owns a timed host for --cost), MaterialScene.settle_background
  (upload jobs + wall-time fade), measure_cost on the host's QRhi frame timer; expanded_visualizer_evidence
  HiddenDisplayHost attaches bootstrap.host_quick_window + set_wallpaper (the clip contract's glass cases need a photo
  to build the backdrop from); test_hidden_scene_retirement retargeted to the core's live counts (negative controls:
  no DeferredDelete delivery -> nothing destroyed in close(); no sync frame -> backdrop pyramid/resources held).
  54 + 57 pass. Evidence rendering/n52h_card_material_native/20261128_retarget.
- Item 1 commit 9f4a5b731.
- Item 3 DONE 87c0063f5: discovery evaluates composer calls nested in composers (population_packs, propagation_sources)
  and local-import parts; forwarded sites count as covered when every part is covered. 13 pass, 1 predating red (4 raw
  module-level fragments disintegrate/volumetric; fixing changes the baked packs -> needs a build). Evidence
  native_core/n52h_shader_readiness/20261128_native_pack_discovery.
- Exit-crash attribution DONE 418d137ce (comment in test_quick_exit_routes; by reading f12427a2e: BackgroundRenderItem's
  direct sceneGraphInvalidated slot ran Python on the render thread in the exit sweep). Control unchanged.
- Item 2 NOT DONE: tools/qtquick_render_node_smoke.py has 124 reads of the deleted node's telemetry (pixel samples,
  midpoint colours, GL init/release/upload counts, hide/show polls) and runs QuickDisplayRuntime on physical screens,
  which this agent may not run; an unverifiable rewrite was not committed. Decomposition in the report.
- Side note: the core's composite handle table keeps a null entry when a layer item dies with its root (close_native_layer skipped).

---- previous agent's journal ----
# N5.2h switch side defect: Qt GL sets sampler state on multisampled textures (GL_INVALID_ENUM), agent ad3b55

2026-11-28. Merged worktree-agent-a6b16aeef142dc895 (7dc955488). Module 163d41b8 copied into release/native_module.
- Box 1 done: synchronous logger probe (.artifacts/scratch/gl_ms_sampler/probe_bind.py) shows ONE error per multisampled
  texture at its creation (eb_4x textures 3,5,7,11,12: RGBA16F x3, D32F, R16F; tiles_4x one RGBA8), program 31 (Quick's,
  no core sampler on the unit). Cause: QGles2Texture::create() ends with glTexParameteri(target, MIN_FILTER, LINEAR)
  for every uncompressed texture. Not bindCombinedSampler (that would be 5 calls on one texture). Advisor refuted.
- Box 2: createTexture() in gl_sampler_state.cpp (GL + MS: glGenTextures, createFrom, glTexStorage2DMultisample, owns=true);
  scene_targets.cpp make lambda uses it. Source test test_every_multisampled_texture_is_created_without_sampler_state
  (failed before the C++ change at scene_targets.cpp:1141). Not built (lead builds). Commit 158531ad9.
- Box 3 done 123cf29d0: fragment 'no mips' -> 'reads mips of'. Evidence native_core/n5_2h/20261128_gl_ms_create_attribution.

---- previous agent's journal ----
# N5.2h switch delete sub-box, successor (agent a6b16aeef142dc895)

started 2026-11-28. Merged ac5eb + main; release/native_module copied (f475358aa).

2026-11-28 successor progress (uncommitted until round 2 finishes):
- bootstrap.close_native_hidden_host() public (used by atexit in native_transition_capture and the quit edge; the capture re-makes the host at another size).
- NativeTransitionCapture.run() added (direction/parameters overrides). ~25 tests/test_qtquick_<transition>*.py retargeted by swapping the class; tests that used capture.host/frame/fbo/vao/textures (Python draw pins) deleted via .artifacts/scratch/switch/delete_pins.py. First native pass: all pass but melt seams (deleted: pinned Python shader), volumetric mist unit 3 (deleted).
- deleted tests: test_qtquick_transition_state_fence, test_transition_upload_types, test_scene3d_environment (PhotoEnvironment Python copy; dead after deletion: SIDE DEFECT follow-up, Python PhotoEnvironment/mist etc may now be dead code), env/lifecycle test renamed test_visualizer_lifecycle_contract (transition parts deleted).
- tools: transition_contact_sheet (TransitionCapture + quick_smoke removed; native), release_media (visualizer branch uses OffscreenRenderTarget), visualizer_cost_probe/bubble_particle_glow (OffscreenRenderTarget), bench_stability.crossfade_control (self-owned GL control), overhead_baseline transitions (native, wall ms relative to native crossfade control; rows native_rel), conventions_identity (native hashes only).
- item 6 DONE: background_item uses the shared _WindowEdge (visualizer/native_route) instead of afterRendering.connect; prohibited-surface test passes.
- DONE (commit e7cafe96b): rendering/quick/transitions/render_host.py deleted; every implementation class's GL draw (render, warm, park, release_resources, _initialize, _draw*, resources) stripped by .artifacts/scratch/switch/strip.py (classes stay value owners; edge_bloom/exploding_tiles/liquid_lens keep a small __init__ for their value caches); FullscreenPassRenderer GL removed; registry check now 'value contract' (block_values or scene_values), QuickTransitionRenderer protocol is transition_id only; SHARED_RENDERER_MODULES re-derived (the warm-unit test pins one rendering module per unit); guard list has render_host with the negative control (a temp importer in tools/ failed the guard, removed).
- Stale/pinning tests deleted or trimmed in round 4: test_qtquick_transition_uniform_wiring (fake-GL render pin, deleted), test_idle_transition_preparation_contract (render-thread job tests were already stale: replaced by one _WindowEdge test), crumble failed-instance deletion, pixel accretion draw-source asserts, block_spins draw-source asserts, melt has_resources, native_fullscreen_pass render source assertion, transition_controller (background_node path -> native_background).
- test_native_scene_targets::test_the_admission_refuses_with_its_reasons is RED and not mine: the f475358aa module's refusal wording differs from the test (side defect).
- qtquick_render_node_smoke windows tests: the 5 test_script_smoke_* in tests/test_qtquick_render_node.py deleted (judged the Python node's pixels); tools/qtquick_render_node_smoke.py itself untouched.
- STILL TO DO / record: reference checks both APIs (running), release_media + onboarding scratch capture, tool smoke runs (overhead_baseline transitions, conventions_identity), dead Python Scene3D code (PhotoEnvironment, MotionTrails, SceneTarget, trails etc. no longer imported by any transition class) is a follow-up.

## Final status (switch)
- Reference checks (4) pass on OpenGL and Vulkan from the cache; release_media crossfade, onboarding crossfade, overhead_baseline crossfade and conventions_identity record (transitions crossfade, 12 distinct of 12) smokes all ran.
- Scratch removed. Known red, not from this work: tests/test_native_scene_targets.py::test_the_admission_refuses_with_its_reasons (wording vs f475358aa module).
2026-11-28: started. Merged a5767, ac12, main. release/native_module copied from a5767 (f475358aa, ABI 45).
Box 1 DONE e06691e3e (C++, READY FOR BUILD): cause = Qt 6.12.0 QRhiGles2::bindCombinedSampler sets glTexParameteri on
a texture's first bind after create() (cached samplerState != sampler); on GL_TEXTURE_2D_MULTISAMPLE = INVALID_ENUM. Qt
fixed it after 6.12.0 (isMultisampleTextureTarget in 6.12 branch). Sites: TransparencyResolve (accum+coverage MS) and
nearest resolve (MS depth). Fix: gl_sampler_state.cpp adoptMultisampleSamplerState (private qrhigles2_p.h, sets
QGles2Texture::samplerState = sampler d) called at both records. Test: test_native_core_module::
test_a_validation_on_opengl_frame_logs_no_gl_errors (post_stage_check --rounds gl_errors, debug context, hidden host
threaded=False, QOpenGLDebugLogger log) FAILS on f475358aa module (eb_4x frame 0 INVALID_ENUM) = control seen.
Evidence n5_2h/20261128_gl_invalid_enum. Old "Watch: one GL_INVALID_ENUM on first 4x frame" = same cause.
Order: 1 GL_INVALID_ENUM (C++ fix + validation-on GL frame test); 2 delete sub-box + retargets + import guard test.
Box 2 slice 1 DONE 3b9938b5b (Python only): deleted background_image_node, background_node, image_textures,
native_texture_bridge, surface_backdrop + BACKGROUND_FAMILY_BACKENDS/background_family_available_on_backend,
scene_controller._publishes_frame_presented (frame_presented now always published once). background_item lost the GL
NoStage warm job, retirement, proof progress. Tests pinning the Python route deleted (8 files) or trimmed (12 files).
Reference checks: backdrop_pyramid_check/transition_route_check touch the Python route only in record mode
(trc.hold_python_clock, "# record mode only" import marker); route round uses backdrop="owner" (was a native crash
0xC0000005 after the blit import failed mid-scene). overhead_baseline: surfaces + node_path cases removed (they measured
the deleted blit/node). qtquick_render_node_smoke: dense axis count local. Guard: tests/test_python_route_deleted.py
(negative control seen: 3 failed before deletion, log in evidence n5_2h/20261128_delete_sub_box).
REMAINING (box 2):
- transitions/render_host.py NOT deleted: TransitionCapture (tools/transition_contact_sheet.py:107, ~54 callers incl.
  overhead_baseline transitions/crossfade_control, release_media non-transition cases, many tests) draws through it.
  Retarget TransitionCapture callers to NativeTransitionCapture (or delete Python-only ones), then delete render_host and
  the transitions' render/warm/_initialize/release GL code (classes stay value owners), add it to the guard's DELETED.
- bench_stability.crossfade_control -> native crossfade control; overhead_baseline transitions to native; conventions_identity.
- native_transition_capture.py:61 atexit.register(bootstrap._on_about_to_quit) -> public close.
- qtquick_render_node_smoke script_smoke tests (open windows; not run) pin Python node pixels: retarget or delete.
- Docs refs to deleted modules (Docs/Reference/*.md; product docstrings fixed in the follow-up commit).
Side defect (pre-existing on HEAD): test_qtquick_render_node::test_quick_render_node_path_has_no_prohibited_surface_or_
compatibility_owner fails: background_item's GUI warm uses window.afterRendering.connect (forbidden list).
Four reference checks from cache on module f475358aa, OpenGL+Vulkan, after slice 1: background_layer, fullscreen_pass, backdrop_pyramid, transition_route all VERDICT PASS (logs evidence n5_2h/20261128_delete_sub_box). Stopped here at the context limit.
Box 1 follow-up aab60aa9e (C++, READY FOR BUILD): lead's build of e06691e3e (manifest 7df944fb) still logged eb_4x 5, eb_band_4x 5, tiles_4x 1 on frame 0 (evidence n3_4/20261128_lead_gle). Now every pipeline set (26) goes through set*PipelineAdopting and every explicit setShaderResources(srb) (11) follows adoptMultisampleSamplerState; test_native_post_stages::test_every_pipeline_set_and_shader_resource_bind_adopts_the_multisample_sampler_state (controls: a bare set and a dropped adopt are caught). Positive gl_errors run needs the build. Remaining edge: a texture create() recorded after its bind in the same frame would still reset the cache.
