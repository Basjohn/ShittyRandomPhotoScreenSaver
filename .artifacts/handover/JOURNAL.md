# N5.2h The switch: GL_INVALID_ENUM side defect + delete sub-box (agent ac5eb8a969947d272)

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
