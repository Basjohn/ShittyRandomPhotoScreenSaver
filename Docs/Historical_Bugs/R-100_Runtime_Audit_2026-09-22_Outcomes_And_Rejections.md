# R-100 — Runtime Audit 2026-09-22: Outcomes, Rejections and Closure

**Status:** CLOSED (historicalised 2026-09-27). The admitted queue was accepted on 2026-09-23 (operator run
19:29–19:35 with `--frame-trace`, earlier physical runs and automated bars) and PR-04's native texture handoff on
2026-09-24 (operator run 23:47 plus a frozen-build probe). On 2026-09-27 the operator ruled that items the audit left
watched or parked are **rejected**, not deferred: do not re-propose them without new evidence.

The audit audited `main` at `2ba9e15d` against CHK26 / `a0bf70932c`. Its full body (register, per-area detail,
historical cross-audit and evidence research) is in source control under the retired
`Docs/Future_Work/Runtime_Audit/` folder (last present at the commit before this record). Durable rules it produced
live at their owners (Guardrails §Wallpaper pixel opacity and §Presentation texture ownership, Spec §Media lane,
`mode_capabilities.consumes_waveform_samples`) and the defects it found are R-89, R-90, R-91, R-92, R-93 and R-95.

## Protected invariants the audit held every change to

- Visualizer fidelity/reactivity, BTF, R-69; ~90 Hz authored logical cadence; newest-state semantics.
- Latency: source/snapshot age, state→paint, publication→draw (CHK26 GOLDEN references in R-87).
- Visible functionality and fidelity (pixels, authored transitions, fades, CUSTOM behaviour).
- Visualizer fps/cadence on 60 Hz and high-refresh displays; mixed-refresh behaviour.
- R-63 non-exact-cover geometry; `swapInterval=0`; one QQuickWindow per display; no Python display pacer; no
  `frameSwapped → requestUpdate()` loop; no env flags; diagnostics strictly opt-in.


## Accepted and implemented

Each row keeps only what traces a future issue back to the change.

| ID | Change | Commits | Durable home / bar | Closing evidence |
| --- | --- | --- | --- | --- |
| TX-01 | Fracture geometry prepared on COMPUTE; a render thread takes the in-flight preparation instead of rebuilding it; vectorised prism builder | `da2de88e`, `50f38551` | `tests/test_transition_run_geometry.py` | 19:29 trace exposed duplicate builds (Glass first frames 102–134 ms / 40–60 ms); fixed with a bar that fails on the old path; Tiles run clean. The 23:47 trace showed the preparation never matched in production (R-95: monitor-rect vs R-63 window aspect); fixed 2026-09-24 |
| TX-02 | Random rotation is session memory, never a Settings write | `e3c6ce82` | R-92; `tests/test_transition_distribution.py` | run: Random rotations with no Settings writes |
| LC-05 | Context-menu entries refresh before the menu opens | `ca86367c` | context-menu entry test | run: six context-menu actions |
| LC-06 | Canonical defaults built once per profile | `f84439f2` | defaults tests | run: two Settings replacements, three generations |
| PR-01 | Steady equal publications skip the QML shell projection | `3598c8fb` | publication tests | run: mode switches, startup/replacement fades; operator: no regression |
| PR-03 | Background telemetry notes without dataclass `replace()` | `e80336c9` | telemetry tests | trace: background render normal |
| PR-04 A | Opaque wallpaper pixels at both processing owners; premultiplied native label | `8541cb82` | Guardrails §Wallpaper pixel opacity; `tests/test_wallpaper_opaque_pixels.py` | operator: no black flash; transparent sources are an automated contract |
| PR-04 B | Native `QImage` wraps the presentation bytes (no deep copy) | `48b11565` | `tests/test_qtquick_native_image_lifetime.py` | trace: first post-transition sync 0.33–1.53 ms (was ≈4.6 ms) |
| PR-04 native | The retained background adopts the transition's destination GL texture through Qt's exported `QSGOpenGLTexture::fromNative` (ctypes on the loaded `Qt6Quick`; no PySide release binds it, no compiled helper); the texture host stays the only owner/deleter (lend/reclaim) and the next run reuses it as its source | `e744d119` | Guardrails §Presentation texture ownership; `tests/test_qtquick_native_texture_handoff.py`, `tests/test_qtquick_native_texture_handoff_gl.py` (real GL; six reintroduced ownership faults each caught) | 23:47 trace: first cycle after a transition end on the 4K Visualizer display 3.3–11.1 ms (median ≈7; was median 19.3), 26 of 26 completed runs adopted, no fallback; frozen Nuitka probe: adoption, deletion by identity, pixel parity with Stage B, GL state untouched, one `qt6quick.dll` |
| PW-01 | Timeline-only Media refreshes reuse the held artwork | `aa57c284` | Media refresh tests | run: `artwork_reused` 43 of 47 event refreshes, track changes |
| PW-02 | Media refresh and commands on a dedicated `media` lane | `a8e38012`, `468ec0cc` | Spec §Media lane; R-93 | operator offline/network-stress run |
| PW-03 Clock | Clock ticks notify only the time epoch | `e8ef729c` | clock presentation tests | run: clock on screen throughout |
| PW-05 | `single_shot` returns a cancellation handle; Feed/Games-You-Follow deadlines in the generation registry | `1f60f0c8` | `tests/test_single_shot_handle.py` (incl. a due deadline firing once) | automated |
| VZ-01 | Paused idle waveform synthesized only for Oscilloscope | `ccb9c615` | `tests/test_visualizer_idle_waveform_demand.py` (all six modes) | automated |
| VZ-03 | Tick phase recording only under `--perf` | `17fc2276` | `tests/test_visualizer_tick_phase_diagnostics.py` | automated |
| VZ-04 | Waveform samples only for sample-consuming modes | `a9878340` | `mode_capabilities.consumes_waveform_samples`; payload tests | BTF Layer 4 PASS (Bubble, Oscilloscope, Spectrum, Dev Curve, Voxel Sphere); Sine's quieter-level pulse accepted as authored behaviour |
| VZ-05 | Render fields frozen once per tick | `99a94a21` | tick tests | soak |

Defects this audit found are recorded as R-89 (cross-file native abort), R-90 (Core Audio double release), R-91
(orphaned workers), R-92 (TX-02), R-93 (PW-02) and R-95 (TX-01's prepared geometry never matched under R-63 overscan; found in the 23:47 trace).


## Left open by the audit, rejected by the operator (2026-09-27)

| ID | Finding | Pri | Reward | Risk | Decision / status | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| PW-04 | `FeedRowsModel.replace_rows` resets the whole list when one row changes | P3 | R1 | Low | **Watch** — FEEDS Custom 2–4 | source + soak |
| PR-02 | Ordinary runtime connects `frameSwapped` to a queued per-frame GUI Python callback (≈0.5 ms/s) | P2 | R1 | Low–Med | **Park** (with DC-04) | source + soak |
| PR-01 memo | Presentation re-resolve per publication (47.6 µs) | P3 | R1 | Low | **Park** | measured |
| PR-07 | `QuickSceneFactory` compiles every family QML component at startup (≈0.2–0.3 s dev) | P3 | R1 | Low | **Park** | measured |
| ST-01/02 | `DisplayManager` 4.9k-line owner; very large files | P3 | R1 | Medium | **Park** (move-only on a touched seam) | source |
| VZ-05 cache | Epoch cache for config-static render extras (17–117 µs/tick left) | P3 | R1 | Medium | **Park** | soak |
| VZ-07 | Logical runtime sleeps in 4 ms slices | P3 | R1 | Low | **Park** | source |
| DC-04 | Guardrail vs source conflict: per-frame `frameSwapped` Python callback (PR-02) | P3 | R1 | Low | documented; fixed only when PR-02 reopens | source |

## Considered and rejected during the audit (do not re-propose without new evidence)

| Idea | Why rejected |
| --- | --- |
| Raise IO pool size to relieve PW-02 | hides the ownership problem; more concurrent network work; fix the owner lane instead |
| `swapInterval=1` / VSync-driven pacing | R-86 installed A/B materially worse |
| Python display-refresh timer or `frameSwapped → requestUpdate()` | R-87 forbidden regressions |
| Global GIL switch interval change | CHK18 worse, operator felt worse |
| Remove/merge inherited GL/clip state fences | CHK24–26 closed; protected optimizations |
| Bubble renderer micro-optimization | CHK29 closed; reactive work, not waste |
| Render-thread priority boost | CHK16: not runnable starvation |
| Coalesce or defer visualizer `update()` requests | R-62/R-61B/R-27: late, flatter Bubble |
| Skip visualizer draws on non-revision frames without an offscreen cache | impossible in Qt Quick (scene redraws fully); only PR-05's architecture route could |
| Lower visualizer cadence while paused | paused idle animation is authored product behaviour (Visualizer_Presentation §10) |
| GC threshold tuning / periodic `gc.collect()` | Performance contract §P2, R-53, R-71 |
| Remove the 200 ms display transition stagger | authored visible behaviour; needs product decision |
| A parallel "last applied presentation" cache for PR-01 | U-09/R-68 single geometry authority; use the retained item's own record |
| Lazy-construct `CustomLayoutOverlay` only in Edit | already dormant (`visible: editActive`, model-driven Repeaters); R-23/R-88 Edit risk for startup-only gain |
| Replace `DisplayScene.qml` per-tick transition counters | run only during transitions and feed PERF_HUD |
| Unslice the authored-clock sleep (VZ-07) | small unmeasured gain on the protected BTF clock; parked |
| LC-01: re-freeze GC after each runtime replacement | closed 2026-09-23 (08): after a real replacement gen-2 takes 1.2 ms (11,692 unfrozen objects); the freeze pins 748 retired objects, 0 MB; the D1 soak had no gen-2 stall. Scope is only the feared post-replacement gen-2 stall — the soak did record one 19.53 ms gen-1 collection |
| PR-05: offscreen-cache the visualizer to skip repeat draws | closed 2026-09-23: 2.81% of draws in the D1 soak (1,803 of 64,150), ≈5.8 ms/s idle; would change the selected custom-render composition (Compositor_Architecture §6) |
| PW-06: persistent supervisor heartbeat thread | closed 2026-09-23: 0.31 ms per 3 s ≈ 0.1 ms/s, OS timer handles steady at ≈13–14 through the soak; replacement risks R-30 exit behaviour |
| Treat the 22:58:31 prefetch "double batch" as a defect | closed 2026-09-23: `requested=2 retained=1` near-future keys — benign lookahead catch-up |
| PR-04: move the native upload earlier in the transition | relocates the stall into the transition or stacks it on the costly start frame |
| PR-04: make every `capture_qimage` output opaque | `capture_qimage` is a generic boundary; the opacity guarantee belongs at the background processing boundary (FILL perfect-fit) |
| PW-02: run Media queries/commands on the WinRT observation lane | teardown waits 2 s on that worker; a stuck WinRT await would fail the R-53 barrier. Use a separate Media-only lane |
| PW-03: one notify signal per property across every family | churn without evidence; a few semantic epochs, Clock first, Media only if measured material |
| PW-03: split Media's notify | measured 2026-09-23: 0.5 ms per emit at ≈0.25 refreshes/s ≈ 0.13 ms/s — not material |

## Lesson

Measure the exact function on the audited tree and cross-check it against the historical bugs before recommending a
change; most apparent waste was either authored behaviour (paused idle animation, the display stagger), protected
optimisation, or too small to matter (PW-03 Media 0.13 ms/s, PR-05 2.8% of draws). The items that paid off removed
whole stalls at their owner (TX-01 duplicate geometry builds, PR-04 background upload, PW-02 Media starvation).
