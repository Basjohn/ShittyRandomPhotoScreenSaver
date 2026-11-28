# N5.2h switch audit fixes (items 1-6 + lows), agent aeba3f08a60b6a572

started 2026-11-28. Merged worktree-agent-aa3b364fd31f5d860. Module c9b9f0a6 copied.
Order: 1 reveal waits for first wallpaper; 2 hidden-host owner guard; 3 fullscreen_pass_check TransitionCapture;
4 owner tests; 5 exit routes on OpenGL; 6 per-window degrade; lows (PhotoEnvironment deletion stays backlog);
7 (lead, added mid-task): warm the next transition's native GL pipelines one unit per rendered frame (first-frame hitch).
- Item 1 DONE cc8464553: QuickSceneReadiness.background_drawn (layer.photo_drawn = content draws>0, core counts a draw
  only with textures in; degraded node sync) published at swap; _startup_reveal_admits needs it + the authoritative first
  image. Control seen failing (old code: is_started True on a black presented frame, both backends): evidence
  native_core/n5_2h/20261128_audit_item1_reveal/negative_control.log. Scratch runner .artifacts/scratch/audit_fixes/control.py.
- Item 2 DONE (commit after cc8464553): native_hidden_host(timestamps=) so surface_material_capture's timed host goes
  through the owner (closed via close_native_hidden_host). eb_core_check/waveform_check STAY allowlisted (validated
  Vulkan instance per child + per-round sizes the kept host cannot give) with the reason in the test: deviation to report.
  Control: old bootstrap+capture fail both owner tests (evidence 20261128_audit_item2_hidden_host). 91 passed / 8 files.
- Item 3 DONE: round_shape reads block values GL-free (_values/_run_without_gl). TransitionCapture import guard
  (DELETED_NAMES in test_python_route_deleted; marker lines excepted). Decision: record-only Python GL code
  (draw_python_frames, product_capture, _product_python, _python_stages, hold_python_clock) kept marked but it is
  DEAD (TransitionCapture gone, record on an old checkout runs that checkout's tools): report as backlog deletion.
  Control: old fsc fails the guard (evidence 20261128_audit_item3_round_shape).
- Item 4 DONE: old_stop control back (judges order quit-before-window_destroyed; unshown window dies either way),
  real driver edges via the kept hidden host (2 edges, 0 Python) in the rehearsal + new native-OpenGL-after-instance-
  failure test (control: degrade branch fails it). 24/24 owner file. Evidence 20261128_audit_item4_owner_tests.
  Side note: the exit probe's stop hits a LIFECYCLE_BARRIER timeout (QuickDisplayRuntime 1 live, the probe's own
  global `runtime` ref) before finalizing.
- Item 5 DONE: exit routes parametrized on api (vulkan+opengl, 28 cases; bare control holds on OpenGL: window alive,
  host 1); docstrings (probe + test, bare = counts not crash; R-260 symptom line). test_quit_request_render_thread_gil
  retargeted: Python updatePaintNode on the kept hidden host's render thread (painted_off_main), quit requested, exits,
  both APIs. NO failing control on Windows: the synchronous app.quit() contrast also exits (the wedge was Linux/Xvfb
  only; the original test had no Windows control either) - log 20261128_audit_item5_exit_routes.
- Item 6 DONE: per-window degrade (owner.unhosted_windows WeakSet, window_hosted(window); attach_native_background
  refuses an unhosted window's item; core kept for other windows; one error per window) + one-way: a started process
  with no core never reloads one for a hidden host. Controls: HEAD files fail both new tests; behavioural (old
  _degrade branch) fails (evidence 20261128_audit_item6_per_window_degrade). Residual: backdrop + Visualizer on an
  unhosted window still take the core (native_backdrop_core/attach_native_route have no window check): draw nothing.

---- previous agent's journal (aa3b364) is in git history of .artifacts/handover/JOURNAL.md ----
