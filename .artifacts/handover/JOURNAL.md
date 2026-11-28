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

---- previous agent's journal (aa3b364) is in git history of .artifacts/handover/JOURNAL.md ----
