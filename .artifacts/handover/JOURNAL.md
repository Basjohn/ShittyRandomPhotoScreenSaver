# N5.6 Extruded Bubble native port - P, T and C, then register (successor 3, module 8bf270aa7, ABI 47)

started 2026-11-28. Newest first.

- 28 Nov (5): noise floor on fresh 30 s delivery (n5_6/20261128_rule_b_noise_floor_30s): GL floor p50 0 max 3 px
  1 level; Vulkan self 2576/2586 frames past 1 level (p50 68 px, max 149); rule (b) p50 4,310 px max 150: FAIL.
  Refs: lane 1 done (hh1 60 + 30 x5 + 4 alternates, ragdoll block sizes, ns dd 6,7), lane 2 done but ns dd 0,2,3
  (running). P hh1 60 s vs new ref (n5_6/20261128_p_human_heavy1_60s): 5,500/5,503 differ, 21.6M px, max 168 at
  input 4022, on bright speck glints/highlight discs (crops look identical by eye): FAIL. L set not run (module not
  final: rule (a)/(b) fail). No C++ changed by me.

- 28 Nov (4): 7 deliveries regenerated, all IDENTICAL at L (D:/Temp/Scratch/SRPSS/n56_deliveries/l_*; logs
  n5_6/20261128_deliv_*/run.log): 3 base 60 s, light_type0 x3, ragdoll b. Scene depth: native-only control SAME as
  the smoke (n5_6/20261128_scene_depth_control); without depth the core refuses ("transparency target 'glass': its
  owner 'scene' is a surface-sized scene target with depth"; 20261128_scene_depth_no_depth) -> DECIDED keep the scene
  depth in both (omitting needs a C++ contract change for no gain: nothing writes scene depth before the glass, the
  sorted packs already drop gl_FragDepth). Running: lens shift 0.07,-0.05 3 s both placements (20261128_lens_shift),
  noise floor on l_human_heavy1_light_type0 (scratch/n56b_noise/hh1_light_type0_30s). Next: refs lanes.
  Lens shift (0.07,-0.05; n5_6/20261128_lens_shift): display 4,795,577 px max 39, overscan 4,795,390 max 39, vs zero
  shift 5,019,698 max 55: no added difference (rule (a) still FAILS as at zero shift, so not a strict proof).
  Aperture vs defocusReadLevelCap (scratch/n56b/aperture_cap.py, real functions): at aperture 1 the 4K expanded card
  (3800x2100 -> 3840x2112, cap 4) reads level 4 = cap, no margin; a world zoomed in (aperture <= ~0.54 there; level 5
  at optical >= 3862 device px) goes past the cap -> native refuses + fades out, Python draws. DEFECT for the lead.
  Turned card: no rotation run in owner_render_parity/native_stream_player (harness feature needed). N3.9: native
  drift header zeroed on re-creation -> fresh restart from the published history (reading only, no proof).
  Refs lane 1 running (bxq2jtg4a): hh1 60; hh1 30 x5; hh1 alternates; ragdoll block sizes; nightsolong dd 6,7.
  Lane 2 to start when the noise floor ends: nightsolong 60; ragdoll 60; nightsolong 30 x5; ragdoll 30 x5; ns dd 0,2,3.

- 28 Nov (3): smoke done (n5_6/20261128_rule_a_input0): input 0 drawn on all 4 runs (a: 187 px at 1 level;
  b: 73 px at 3; was 252,112 at 211). Rule (a) still FAILS: 372/404 EB frames (a), 369 (b); 2-3 level ties not on
  edges + pixels up to 55 (a) / 31 (b), speckled inside near-layer bubbles + scattered. R-258/R-256 committed.
  Music response (n5_6/20261128_music_response, 4 traces, route-independent sim): correlations below 22 Nov on
  human p1 (newborn 0.91 -> 0.73, 5-15 s 0.93 -> 0.85, older 0.81 -> 0.71), others close. NEXT, in order (2 procs):
  scene-depth native-only experiment (scratch/n56b/no_depth_run.py ... --native --native-only --against
  20261128_rule_a_input0/native_render_parity.json) BEFORE refs (a Python depth change re-keys refs); lens-shift
  run; noise floor on a fresh delivery; refs via scratch/n56b/refs_lane.py (jobs listed in the final report).
  C needs deliveries at 1440p/4K card sizes + a cost round in the player: not built.
- 28 Nov (2): rule (b) noise floor on smoke_hh1_8s (old delivery, 586 drawn; evidence
  n5_6/20261128_rule_b_noise_floor/): OpenGL floor tiny (gl1 vs gl2: p50 0, max 4 px, 1 level). Vulkan NOT
  self-identical: vk1 vs vk2 differ on 585/586 frames, p50 33 px (max 186), up to 147 levels, isolated pixels on
  specks/snow (look_*.png) -> a Vulkan determinism defect (drift/specks?), not root-caused. Rule (b) vk vs gl:
  p50 2,707 px (grows 1,271 -> 3,922 by third), max 145 levels: FAILS the 2x-floor rule. Scripts
  .artifacts/scratch/n56b/noise_floor.py, vk_self_look.py. Smoke rerun: display/b/overscan now draw all 594 (no
  serial errors). Deliveries lane A running (scratch/n56b/deliveries_lane.py; logs in 20261128_deliv_*/run.log).
- 28 Nov (1): merged ac0cda3c8 + main; copied release/native_module (8bf270aa7, ABI 47) and scratch n56key.
  Order: rule (a) smoke -> R-258 + R-256 note -> rule (b) noise floor -> 7 deliveries -> 18 refs + 12 alternates
  -> rest of P/T/C -> side defects -> L set last.
  Done: 9f08b7df8 wake listener on new core/threading/listener_threads.py (policy test green; HEAD control failed);
  e01f125b9 DRIFT projector per stream (label namespace) + test, HEAD control failed;
  4b5025f64 owner replay opens the in-process arena per planned run (the overscan run failed every frame with
  "drift serial went backwards" on the display run's projector) + test with control.
  First smoke (display run, before the harness fix): 594 drawn, 5,019,698 px, max 55 (was 211). Rerunning both
  placements -> evidence n5_6/20261128_rule_a_input0, log .artifacts/scratch/n56b/smoke_rule_a.log.
