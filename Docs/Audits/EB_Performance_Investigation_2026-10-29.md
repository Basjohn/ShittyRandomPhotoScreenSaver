# Extruded Bubble — performance and GPU-contention investigation

**Read-only source audit:** GODZIP `d2b0a73b06`, 2026-10-29 13:00 snapshot.  
**Status:** Investigation checklist; no implementation approved or attempted.  
**Operator observations:** EB remains visually and musically accepted. Under moderate/heavy competing GPU load, EB frame delivery collapses while ordinary Bubble and other visualizers remain stable. EB alone reportedly consumes ~25% GPU versus ~2–10% for Bubble. Enabling all drift controls versus an otherwise comparable setup approximately doubles the reported frame delay. The supplied underwater image shows that spiralling/clockwise microbubble drift is a valuable visual feature to **preserve**, not a setting to switch off.


## New evidence: 2026-10-29 performance / frame-trace capture

**Repository evidence:** `\logs\evidence_chest\logsd2b0a73b062.zip` (user-retained location). The uploaded archive contains four rolling `screensaver_frame_trace*.bin` segments, `screensaver_perf.log`, `screensaver_usage.log`, `screensaver_handles.log`, `gui_stall_stacks.log`, and related diagnostic logs. Cross-correlated using the GODZIP's own trace record format and existing reporter definitions. Clock times below are **Johannesburg local** on 2026-10-29. Frame-trace records total **3,692,808** across four segments; **76,332** render-mode and swap observations for screen 1. This trace spans approximately 13:09:44–13:29:18; some startup/teardown and transient lifecycle gaps exist, so use stable comparison windows.

### Measured transition and interpretation

| Same captured EB run | 13:24 (pre-collapse) | 13:27 (sustained collapse) |
|---|---:|---:|
| HUD median EB draw FPS (roughly 1-second reports) | 80.0 | 30.8 |
| HUD median frame age | 35.0 ms | 92.7 ms |
| Binary-trace median `render_mode_begin→render_mode_ready` | 8.38 ms | 20.76 ms |
| Binary-trace p99 EB render-mode duration | 11.87 ms | 39.77 ms |
| Binary-trace median Qt `before_render_pass_recording→after_render_pass_recording` | 10.94 ms | 26.71 ms |
| Binary-trace median swap spacing | 12.08 ms | 31.89 ms |
| Process-scoped Windows GPU-engine `gpu_busy_pct`, 15-second samples | 24.4–26.1% | approximately 6.9–11.7% |

- [x] **Collapse is real and timestamped:** HUD deterioration starts around **13:25:19** and persists through exit. At 13:25:28, HUD hits **3.69 FPS**, **550.57 ms frame age**; the binary trace records render-mode excursions of **455.30 ms** and **419.40 ms** near the same second. Early in the run the HUD is generally ~70–80 FPS; sustained 13:26–13:28 is ~30–34 FPS. The comparison is observational, not a controlled equal-settings experiment, so inspect the resolved snapshot parameters and external workload when retesting.
- [x] **The render path measurably slows under the collapse:** at 13:27, the EB mode interval median is ~**2.48×** the 13:24 median, and total Qt pass recording ~**2.44×**. The clip-begin median is comparatively similar (~**1.03 ms** at 13:24 versus ~**1.22 ms** at 13:27), so the sustained increase is not explained solely by clip-state capture; the EB mode region is the largest measured change. These durations are **CPU-observed wall time spanning Python/GL calls and potential driver waits**, **not hardware GPU pass durations**.
- [x] **Logical capture suffers simultaneous major stalls:** `screensaver_perf.log` at 13:25:28 reports logical `_on_tick` **441.15 ms**, with **440.85 ms** in the `publish` phase; another tick is **468.10 ms**. Source cross-check: `tick_pipeline.py` `publish` calls `_publish_logical_state()` → `capture_visualizer_logical_frame()` → `_capture_extruded_bubble()` → EB `runtime.advance()` plus frozen-frame/parameter construction. Thus the label **does not mean just mailbox insertion**. The traceback samples frequently locate the logical worker in `extruded_bubble_material_paths.py`, `extruded_bubble_drift.py`, `extruded_bubble_wake.py`, NumPy arrays/comparisons and render-state conversion. The GUI-stall sampler preferentially samples *stalls*, so these are localization clues, not unbiased percentages of CPU time.
- [x] **SRPSS-owned GPU usage drops as EB slows:** `WindowsGpuUsageCollector` (`core/performance/usage_sampler.py`) uses **process-scoped** Windows GPU Engine PDH counters, not total-card utilisation. It reads ~25% before the collapse, **17.4% at 13:25:20**, **11.6% at 13:25:35**, and ~6–8% later, despite lower FPS. This makes a simple “EB reaches 100% overall GPU occupancy” explanation untenable; it remains compatible with another process occupying the relevant engine, CPU-side underfeeding, driver serialization, GPU scheduling, VRAM/bandwidth contention or several interacting constraints. These logs **do not measure the external application's GPU usage or total GPU engines**, and cannot prove GPU starvation or a particular GL bottleneck.
- [x] **Handle attribution is not an obvious runaway:** sampled main-process handles move roughly **1,590–1,640** across the change, without monotonically exploding; `screensaver_handles.log` captures changes and several thread-count increases but does not establish a handle leak as the cause. The occasional diagnostic/runtime UI callbacks and collection are not a sufficient account for multi-minute sustained mode slowdown. The unusually heavy `--frame-trace --gui-stall-stacks --handle-attribution` instrumentation is a possible observer cost; compare an otherwise identical run without the diagnostic modes after the targeted evidence is obtained.
- [ ] **Match actual on-device workload** around 13:25:19: what external GPU task started/changed, GPU clocks/power, per-engine busy time, VRAM committed/resident allocation and allocation eviction/page-fault counters. The application-owned GPU percent is insufficient. Confirm no coincident EB preset, viewport-size, quality or sound-source changes; current log contains no obvious lifecycle transition explaining the sustained shift.

### New targeted measurement / diagnosis checklist prompted by this capture

- [x] (Offline, 2026-10-30 baselines; `tools/eb_logical_cost_probe.py`.) **First instrument EB `publish_ms` subphases:** effective configuration/readback; EB `runtime.advance`; chain-path definition generation, equality/identity checks and 30,720-node history; snow; speck/216k offset history; wake generation; bytes/payload freezing; `ExtrudedBubbleFrame` construction and parameter deep-copy/validation; mailbox insertion. Report median, p90, p99, allocation bytes and total tick budget for solo vs external GPU activity. Source-confirmed coarse `publish_ms` cannot distinguish these.
- [ ] **Test whether logical and GL render slowdowns share a resource bottleneck:** correlate per-frame EB capture interval, QQuick render-mode interval, CPU scheduling, GIL ownership/NumPy call duration, driver-call time, per-engine GPU queue, upload stalls and OS process CPU quotas/priority. Use same wall clock/frame revision where possible. Avoid treating `publish` spikes as proof the original logical drift algorithm suddenly doubled its intrinsic arithmetic cost.
- [ ] **Sample GPU hardware time around identical EB passes:** probe six faces + filtering, procedural particle draw, near begin/composite, OIT/MSAA, shafts and resolves using deferred nonblocking timer queries, combined with ETW/Nsight system scheduling. If hardware GPU time stays steady but GL call wall time doubles, prioritize driver/queue/fence/VRAM or CPU contention; if GPU times also double, prioritize actual GPU resource competition and pass reduction.
- [ ] **Investigate 13:25:27–13:25:30 outliers directly:** align `render_mode_begin`→`ready` (455/419 ms), logical `publish` (440/468 ms), GUI stack captures, GPU memory snapshots and OS workload transitions. Determine whether one blocked resource triggers cascading missed logical and presentation deadlines rather than independent slow paths.
- [ ] **Re-run with diagnostic controls:** same effective mutable settings, display extent/DPR and audio workload, first solo/contended with light diagnostics, then opt-in full trace; record instrumentation overhead and whether the severe collapse survives. Keep the accepted visualizer and pacing unchanged.

**Implication for rank:** Promote **EB logical capture/material-path drift and snapshot allocation** into the top priority alongside the previously suspected **GL driver submission/synchronization** issue. Empty-near optimization, cubemap refresh strategy and repeated per-speck vertex work remain valuable **source-proven candidates**, but the existing trace does not provide their individual GPU costs or justify blaming any one of them yet.

## 2026-10-30 offline baselines (headless, real recordings)

**Tools:** `tools/eb_logical_cost_probe.py` (new). It replays the production logical tick from a real recording at 91 Hz and splits the `publish` phase with tool-only timers. `tools/extruded_bubble_capture.py` gives whole-frame and `--passes` GPU time. A scratch GIL experiment ran the production render host on the main thread while a paced logical thread ticked.
**Conditions:** RTX 4090, run while the operator's heavy external GPU workload was active the whole time (card 50–99% busy; other processes 25–60% CPU). Absolute milliseconds move with machine CPU load, so compare rows within one table.
**Workloads:** preset 1 (all three drift families, Clockwise; the same drift values as the 2026-10-29 Custom run) and preset 3 (no free drift), on `anything_mixed2` and `heavy1`.

**Logical tick, median / p99 ms (budget 11.0 ms at 91 Hz)**

| Workload | anything_mixed2 | heavy1 |
|---|---:|---:|
| Preset 3 | 1.9 / 3.6 | 1.8 / 4.4 |
| Preset 1, free drift off | 6.4 / 10.4 | 6.9 / 11.0 |
| Preset 1, specks only | 8.0 / 13.1 | 8.3 / 12.3 |
| Preset 1, chains only | 13.7 / 20.6 | 14.5 / 20.1 |
| Preset 1, all drift (live workload) | 19.2 / 27.7 (others 48% CPU) | 14.5 / 25.4 (others 30% CPU) |
| Preset 1, all drift, Particles 0.85–1.0 | 165 / 207 | 152 / 209 |

**Phase split, preset 1 all drift (heavy1, median ms):**

| Phase | ms |
|---|---:|
| Chain material paths | 6.1 |
| Specks | 0.7 |
| Snow | 0.3 |
| Drift packing / `tobytes` | 0.5 |
| Per-bubble simulation (own time) | 2.1 |
| Collisions | 0.9 |
| Wakes | 1.0 |
| `ExtrudedBubbleFrame` validation | 1.4 |
| Settings read, controls and render parameters | 0.5 |
| Mailbox | 0.01 |

Frame validation is a Python `_finite` per float over about 7,000 wake/bubble floats, plus `np.isfinite` over the payloads.

- [x] **The live workload's logical capture overruns the 11 ms budget under moderate machine CPU load.** Chain material paths are the largest single item, at about 6–7.7 ms and fixed in size. All 240×128 knots are solved every tick. The renderer can draw at most `bead_chains_high × 12 × detail share` chains: 120 for preset 1.
- [x] **Specks scale with musical emission × Particles, in power-of-two capacity steps.** Preset 1 has 2,048–4,096 specks, costing about 1 ms. Particles 0.85–1.0 gives 216,000 specks at 134–146 ms per tick, about 13× the budget.
- [x] **Allocation:** preset 1 allocates a 6.2 MB transient peak every tick (about 570 MB/s). With free drift off the peak is 0.19 MB.
- [x] **GIL coupling reproduced** (scratch experiment, 1672×941):

  | Render-thread EB submit | Wall median | Wall p90 | Render thread's own CPU |
  |---|---:|---:|---:|
  | Solo | 9.2–9.7 ms | 11.3–11.8 ms | 9.3–9.7 ms |
  | + preset 3 logical thread (2.5 ms ticks) | 12.5–12.8 ms | 16.8–17.8 ms | 9.2–9.4 ms |
  | + preset 1 logical thread (19.6–20.0 ms ticks) | 20.6 ms | 24.9 ms | 12.3 ms |

  The render thread's own CPU hardly changes, so the extra wall time is spent waiting for the GIL, not on GPU work. This matches the collapse: Qt pass recording grew 2.44×, and revisions ran at about 48–55 Hz from 13:26 to 13:29, which corresponds to 18–21 ms per logical tick.
- **Interpretation:** the 13:25 collapse can be explained without GPU contention.
  1. Extra CPU demand pushes EB's logical tick past 11 ms. The external workload here also used 25–60% CPU.
  2. The logical thread then runs back-to-back and holds the GIL for most of the time.
  3. The render thread's ~9 ms of PyOpenGL submission stretches to more than 20 ms.

  SRPSS's own GPU use falls because the GPU is underfed. Other visualizers don't collapse because their logical ticks use a fraction of the budget.
- [ ] **Confirm on the live runtime:** one MC run, preset 1, with and without the external load. Read the HUD `viz_revision_hz` and the frame trace's `render_mode` interval.

**GPU (offscreen, production host, with the external load running)**

| ms | 1672×941 | 2560×1440 |
|---|---:|---:|
| Preset 1, whole frame median / p90 | 6.2 / 13.0 | 6.6 / 8.1 |
| Preset 3, whole frame median / p90 | 5.1 / 8.6 | 7.0 / 8.4 |
| Preset 1, sum of draw calls | 1.5 | 2.6 |
| Preset 3, sum of draw calls | 1.6 | 3.5 |

- Largest draws for preset 1 at 2560×1440: near-layer defocus 0.42, shells 0.40, shafts 0.34, backdrop 0.31, beads 0.31, probe prefilter 0.29 ms.
- About 3–4 ms per frame is not yet attributed (whole frame minus draws). It is non-draw GPU work (mip generation, clears, the per-frame `glNamedBufferSubData` drift upload) plus idle time inside the query while the GPU waits on CPU submission. These have not been separated yet.
- `visualizer_cost_probe` (preview snapshot, 2560×1440): EB costs 778 Crossfade frames of GPU against Bubble's 1.24. EB's CPU submit is 4.4 ms against Bubble's 0.2 ms.
- On this card, draw work is small next to the CPU work. The §3–5 GPU candidates remain valid but rank below the CPU items.

**Re-ranked by measured milliseconds**

1. **Chain material paths, 6–8 ms per tick.** Lossless candidates:
   - Solve only the chains the authored Bead Chains range can ever draw (`high × 12`: 120 of 240 for preset 1). A raised range would start the newly admitted chains with fresh history.
   - When the cached geometry object is unchanged, skip `array_equal` and the 737 KB definition copy.
   - Use fewer NumPy temporaries.
2. **Speck offsets at high Particles, 134–146 ms per tick at 216k.** This is already NumPy-batched, so it needs an order-of-magnitude change: in-place buffers or per-mote work, or the §1 GPU-resident design. Measure before choosing.
3. **Frame validation, 1.2–2.1 ms per tick:** Python per-float finiteness checks over the wake and bubble records.
4. **Render-thread CPU submit, about 9 ms per EB frame** (Bubble: 0.2 ms). Cut GL call count. Move the drift upload to the existing `StreamRing` (3D foundation lesson S14).
5. **GPU passes** (near layer, shells, shafts, backdrop, probe): 0.3–0.4 ms each at 2560×1440.

### Landed (2026-10-31): lossless, bit- or pixel-identical

| Commit | Change | Proof |
|---|---|---|
| `573a799d` | Solve only the chains the Bead Chains Range can draw (`min(240, high × 12)`); skip the definition compare and copy when the cached geometry is unchanged | Drawn rows bit-identical per tick against `850b1c37` |
| `129a8983` | Validation checks floats in C-level loops. Probe: face rotations are prebuilt C arrays, uniform locations are cached, face completeness is checked once at allocation. Defocus caches uniform locations. EB matrix uniforms upload from C arrays. | 12 frames pixel-identical against `850b1c37`; Python calls per frame 10,288 → 8,128 |
| `f6bd6c5a` | The swirl field skips the on-axis fallback when no record is on the axis. Chains shift history only for the paths that moved. Clouds reuse last tick's progress. Both integrate per component in place. | Bit-identical per tick against `850b1c37` (preset 1 Clockwise, mid Particles, Wander) |

**Results:**
- **Preset 1 logical tick on heavy1, single-threaded:** 14.5 → 6.6 ms median. Chains went from 6.1 to 1.5 ms, specks from 0.7 to 0.34 ms, and validation from 1.4 to 0.35 ms. Machine CPU load was 30% before and 23% after.
- **216k specks:** 152 → 80 ms per tick, still about 7× the budget.
- **GIL experiment, rerun:** with the render loop running, preset 1's logical tick stretches to 10–14 ms, and render submit is still 13.5–22 ms, against 5.5–8 ms solo. The machine was under 53% outside CPU load. Both Python threads together still need about a core of GIL time per second.

### Landed (2026-10-31, continued)

| Commit | Change | Proof |
|---|---|---|
| `a053189d` | Raw getters for the per-frame write-mask, depth-mask, framebuffer and viewport reads (shafts, scene target, defocus) | Same values; Python calls per frame 8,128 → 7,789 |
| `12144ffa` | The scalar drift field is written out per component in the generator/`sum()` evaluation order. Collisions test distance first among side-effect-free rejections. | Bit-identical per tick against `a053189d` (Clockwise, Wander, Left, Random) |
| `63e336d3` | **GPU drift solver (§1).** The logical tick publishes a float64 step log and per-family geometry. `DriftSolver` integrates it with compute into the unchanged `ebMaterialDrift` layout. | Log + CPU reference = previous live payloads bit for bit per tick. GPU = reference to float32 precision for all nine directions, multi-step frames, a geometry edit and capacity changes (`tests/test_extruded_bubble_drift_solver.py`). Frames differ only in isolated sparkle pixels (about 0.13% of pixels, 9–58 above 2 levels). |

**Measured after the solver:**
- **Logical tick, preset 1 on heavy1:** 3.0 ms median (14.5 at baseline). Free drift now costs 0.05 ms per tick. At 216k specks it's also 3.0 ms (was 152).
- **GIL experiment:** render submit is 7.0 ms with the preset-1 logical thread running and 4.2 ms solo, a 1.7× ratio (was 3.7×). The contended logical tick is 3.8 ms.
- **Live MC run (2026-10-31, 90 s):**

  | | Collapse (2026-10-29) | 2026-10-31, before the solver, heavy GPU load | 2026-10-31, after the solver |
  |---|---|---|---|
  | Draw rate | about 30 fps | 38–55 fps | 90.0 fps median (p10 89.8) |
  | Logical revisions | about 48 Hz | 88–91 Hz | 90.0 Hz |
  | Frame age | about 93 ms | 42–70 ms | 18 ms |

  The external GPU load had mostly stopped during the "after" run (41% → 3%). Repeat it under the same heavy load before calling the collapse closed.

**Behaviour change:** a free-drift family now retires once every knot or mote has recycled after its signed drift reaches zero. It used to retire when displacement fell below 1e-7, which happens at the same recycling.

### 2026-10-31, after the operator's heavy-load MC run

**The live run:**

| | Value |
|---|---|
| Draw rate | about 59–64 fps (median 58.8) |
| Logical revisions | 90 Hz |
| Frame age | about 40–42 ms |

Screen 1 is the 4K panel at **60 Hz**. Steady swaps sat at the refresh rate (16.65 ms), with 4% of frames missing a vblank. In the low-load MC run, EB drew every revision (90 fps) at 18 ms age, so the 40 ms comes from the render cycle stretching past the 11 ms revision interval under contention. Live EB render-mode time was 10.4 ms under load, against 4–5 ms offline.

**Offline findings** (`tools/eb_gpu_stage_cost.py`, `tools/gpu_load_generator.py`):

- **EB's GPU frame, truly idle, at 1662×888:** 2.32 ms. The probe prefilter took 1.07 ms of that, as 48 dependent tiny draws with GPU pipeline drains between them. Next were the near-layer composite (about 0.44 ms) and shafts (about 0.3 ms).
- **`8a67a808`:** the prefilter now does one layered draw per level (geometry-shader `gl_Layer`), at 0.68 ms. The whole frame is 1.93 ms, pixel-identical.
- **Under a 60% game-like competing load:** submit-to-completion is about 9.1 ms both before and after that change. EB waits behind the other process's in-flight GPU packets, and the wait barely depends on how much work EB submits. So trimming EB's GPU work alone will not halve the frame age under load.
- **Rejected, measured:**
  - *Prefilter tap table:* the arithmetic was not the cost.
  - *GL calls holding the GIL:* no reliable gain, and blocking calls would freeze the logical thread.
  - *A CPU near-layer skip gate:* a near bubble was present in 600 of 600 frames.
- **Measurement traps:**
  - `GL_TIME_ELAPSED` timers inside a frame charge the previous stage's draining work to the next stage. Use skip variants instead.
  - Stray load generators must be stopped by PID; killing the shell launcher leaves the Python child running.
- **Vanishing streams:** the GPU solver reproduces the pre-solver frames over 900 consecutive frames (at most 30 differing pixels per frame, never clustered). The cut-off mechanism was SCENE's two-radius wall cut, which predates this work. `68515506` fades drifted motes before the wall instead.

**Next candidates for the frame age under load:**
- Fewer separate GPU submissions per frame, so EB queues behind fewer competitor packets.
- Render-cycle phase and latency inside Qt's loop.
- The near-layer composite region of interest.

All of these need measuring against the 60% reference load (submit-to-completion latency, not idle GPU time).

**Remaining, ranked:**
1. **Heavy-load confirmation:** one MC run on preset 1 under the operator's external GPU load, compared with the 38–55 fps run.
2. **Render thread:** about 4.2 ms solo submit, still Python-heavy (7,789 calls per frame, about 750 GL calls). Each remaining item is small: uniform handling 0.4 ms, probe 0.7 ms, about 69 state queries.
3. **Logical simulation:** per-bubble Python 1.2 ms, collisions 0.6 ms, wakes 0.5 ms, frame validation 0.3 ms.

## Absolute acceptance rules

- [ ] Preserve existing EB appearance, underwater scattering, glass, highlights, blur, reflections, motion history, composition, musical response, breathing, identity, continuity, fade, and frame pacing. No reduced simulation precision/rate, particle counts, sample counts, resolution or quality as a *claimed* optimization. Such reductions may be used temporarily as diagnostic ablations only; restore them.
- [ ] **Lossless implementation improvements are unconditional implementation work, not user-facing quality knobs.** If the accepted result can be produced more cheaply with no meaningful fidelity/reactivity loss, make that the implementation and measure it; do not hide it behind a new setting.
- [ ] **Fidelity/performance controls are a secondary deliverable, never an optimization escape hatch.** First exhaust and measure no-visible-loss improvements for the affected subsystem. Adding or planning a quality control does **not** close that subsystem's performance investigation; the accepted High/reference path must still be optimized independently.
- [ ] Any measured, worthwhile fidelity/performance trade-off that the operator chooses to expose belongs in **Settings → 3D Visualizers** under that visualizer's **Custom** quality option. Keep Auto/High/Balanced/Performance uncluttered; show subordinate controls conditionally only when Custom is selected (or within an equivalent compact per-visualizer reveal), so future 3D visualizers do not turn the tab into a permanent wall of controls. Preserve one Settings/capability/CUSTOM ownership path rather than adding EB-local UI authority.
- [ ] Never use subjective/current operator-authored preset values as fixed test expectations. Preset 1 and preset 3 can be compared as **operator-chosen live workload examples**, with exact resolved effective parameters captured alongside results. Use independently specified test-owned values for automated semantic/integrity checks.
- [ ] Keep the single existing logical/snapshot authority, Qt Quick presentation contract, and dormancy; no extra animation clock, polling, unsanctioned workers, blocking GL readback or synchronous fallback.
- [ ] Prove performance changes under **both solo and contention** load. Profile logical CPU, snapshot creation/copy, render-thread CPU submission, GPU pass times, GPU queue latency and presentation independently. A sub-100% whole-GPU reading does **not** rule out a saturated engine, bandwidth or driver queue.
- [ ] Attribute every claimed saving to an actual measured bottleneck; provide before/after reproducible measurements (median, p90/p99, frame pacing) and pixel/behaviour comparisons across quiet, loud, drift, camera movement, near crossings, scene/beam, and projection modes.
- [ ] Do not turn all unchecked hypotheses into a blanket implementation batch. Investigate/rank first, prototype smallest safe changes second, operator accepts visible results last.

## 0. Reproducible measurement and instrumentation [highest priority]

- [ ] Confirm the operator's “ms delay doubles”: identify whether this refers to the QQuick HUD frame interval, render-thread CPU duration, actual GPU duration, or presentation age. Screenshot HUD `draw 78.0 fps`, `rev 79.0/s`, `age 39ms` is **not** a per-pass GPU timing breakdown.
- [ ] Collect paired traces for: original Bubble; EB without free drift; chain-only, snow-only, speck-only, and all-three drift; clockwise/anticlockwise swirl; and the same scenarios with another steady GPU workload. Fix window sizes/DPR, refresh, effective 3D quality, capture input and time-in-scene, and measure both idle and demanding music. Preserve operator settings rather than substituting supposed curated defaults.
- [x] Inspect supplied frame-trace/performance/usage/handle logs in `\logs\evidence_chest\logsd2b0a73b062.zip` and correlate the 13:25:19 onward collapse with logged EB render wall-time and `publish` spikes. [ ] Still need **external GPU workload / OS engine timing** and measured per-pass GPU timings; the supplied capture records application-scoped counters only.
- [ ] Add opt-in, low-observer-effect scopes/counters *only when implementation is authorized*: CPU `advance`/`_advance_free_drift` per family; geometry regeneration; packing/tobytes; snapshot publication; `material_payload` join; GL buffer uploads; probe face capture/prefilter; shafts; scene/background resolve; OIT; near begin/composite; bloom/end; Qt Quick delivery. Use deferred GPU timer queries with bounded in-flight query sets and never block on results.
- [ ] Compare **live simulation + renderer** with a **fixed-snapshot renderer-only** benchmark. `tools/visualizer_cost_probe.py` reuses a frozen snapshot: good for draw/driver cost but **cannot establish CPU drift integration cost**. Use its paired Crossfade/GPU-control methodology where suitable, rather than treating static replay as an end-to-end result.
- [ ] Measure active counts, submitted counts, viewport-visible counts, rendered pixels/overdraw, material-path payload bytes, GL call count, target bytes/bandwidth and GPU busy engines. Log effective settings without asserting that their values are canonical.

## 1. Drift: retain the spiralling microbubble field

**Evidence:** `widgets/spotify_visualizer/extruded_bubble_simulation.py:1097–1147`; `extruded_bubble_material_paths.py`; `extruded_bubble_drift.py`; `rendering/quick/visualizer/implementations/extruded_bubble.py:438–450`; `rendering/gl_programs/extruded_bubble_program.py` (`_SPECK_GLSL`, `BEAD_VERTEX`).

- [x] Confirmed architecture: physical drift is integrated into persistent material history on the logical side. The vertex shader consumes frozen displacement/progress; simply replacing swirl with a shared procedural spin would change trails, inlet recycling and path history.
- [x] Confirmed scale: at maximum population, specks have **216,000** displacement records (`216000 × 16 = 3,456,000` bytes). The fixed chain field is **240 × 128 = 30,720** vec4 records (491,520 bytes), and snow can have 2,500 (40,000 bytes). Together, the three maximum payloads are approximately **3.99 MB per logical snapshot**, before Python/NumPy temporary arrays and downstream copies. Actual population depends on current *effective*, mutable settings and emission state.
- [x] Confirmed: `ProceduralOffsets.advance()` is NumPy-batched, not a Python per-speck object loop; however it creates fresh arrays for base/progress/world, drift velocity, masks and `packed`, and publishes `packed.tobytes()` every update. The simulation may choose power-of-two population capacities, not necessarily exactly the rendered count.
- [x] Confirmed: `MaterialPaths.advance()` regenerates node-base/world/velocity arrays for all chain knots, compares full definitions, reindexes history as needed, and stores copies. Chain paths are solved regardless of the exact active number of drawn chains while the family remains active.
- [x] (2026-10-30 baselines: chains 6–8 ms, specks 0.7–1.3 ms at preset 1 and 134–146 ms at 216k, snow 0.3–1.2 ms.) **Measure CPU per family** on full input ticks, including operations independent of GPU draw and their peak allocation rates. Attribute the reported factor-of-two to family/phase rather than assuming every drift flavour has the same cost.
- [ ] Evaluate in-place scratch-buffer reuse, fewer NumPy temporaries, reusing unchanged geometry/definitions, cached path invariants, and avoiding repeated `array_equal`/whole-array copies when immutable geometry keys already prove equality. Maintain ownership so published snapshots never alias mutable next-frame arrays.
- [ ] For modes whose velocity depends only on chain identity, phase and time, calculate velocity **once per chain** and broadcast over nodes (only where mathematically exact); keep position-dependent per-node steering for swirl. Verify bitwise/controlled-tolerance trajectories and inlet carry.
- [ ] For swirls, reuse per-record intermediate vector terms (stream-axis dot, radial vector, normalization, tangent, phase carrier) and calculate one result per actual logical mote, not separately for its four GPU billboard corners. Compare CPU vectorization vs a single authoritative GPU integration design (see below).
- [ ] Audit whether the GPU's four vertices per speck redundantly redo hash, random, clouds, stream basis, trig, `cloudMaterial`, and world displacement. Evaluate precomputed instance attributes, mesh/compute preparation, or vertex/instance-stage strategies; weigh saved ALU against new memory traffic and synchronization. At 216,000 quads there are up to **864,000 vertex invocations** for this pass; that is an upper bound, not a measured execution count.
- [ ] Evaluate a GPU-resident, batched drift solver **only** if measurements show CPU/history serialization dominates. It must retain continuous integrated history, stable identities, deterministic recycling and snapshot semantics, no second independent motion clock, and zero blocking GPU→CPU readbacks. Plan pause/resume, resizing, preset changes, device recovery and multimonitor behaviour before suggesting it.
- [ ] Avoid treating particle-share reduction or skipping offscreen motes as a free CPU fix: those motes can enter the view and must retain continuity. Investigate sparse/visibility-aware representation only with a proven, exact history-preservation scheme.
- [ ] Check the GPU drift SSBO fetch (`cloudMaterial`) per billboard vertex: four vertex invocations may fetch the same drift vec4 and repeat identical procedural setup for one particle. Measure cache behaviour and alternative shared-per-instance preparation without allocating a second motion authority.
- [ ] Measure upload behavior with current `glNamedBufferSubData` after `b''.join(...)` and `np.frombuffer(...).reshape(-1,4)`: look for needless reserialization, transient ~4 MB allocations and **implicit buffer read/write stalls**. Compare bounded ring-buffer/suballocation or persistent mapping/fences only after locating a stall, using nonblocking retirement.

## 2. Why are 150 small bubbles not visible? Occlusion, residency and culling

**Evidence:** `extruded_bubble_simulation.py:688–765`; `extruded_bubble_scene.py:288–348`; `extruded_bubble.py:430–449, 584–620`; `extruded_bubble_program.py:593–645, 977–1029`; `scene3d/target.py:618–668`.

- [x] `MAX_BUBBLES` is **192** combined ordinary physical bubbles, **not** 192 per family. Small-count settings are quiet/loud occupancy targets, not guaranteed simultaneous on-screen counts: musical population follower, shared cap, inlet throughput (up to 12 admissions/s per family), collisions/fusion, retirement, fades, 3D world distribution, camera frustum and close-lens fading all affect occupancy/appearance.
- [x] `bubble_instances` filters non-ordinary/fused records and nonpositive opacity, **but performs no camera-frustum culling**. `cluster_instances` and glint-proxy packing also have no camera-frustum reduction. All eligible shell records are uploaded and passed to the GPU; vertex shader rejects some behind-camera or wrong near-layer instances and the rasterizer clips offscreen primitives.
- [x] The transparent pass uses weighted blended **order-independent transparency** with `glDepthMask(GL_FALSE)`. This is not a general per-bubble depth-writing occlusion system. Do **not** claim that fully overlapped, translucent, refracting bubbles are safely eliminated by the depth buffer. Early raster clipping and depth testing against background are different matters.
- [ ] During matching live frames instrument: requested count by family; active/live/leaving; fused members; packed shell count; cluster count; front-of-camera count; coarse frustum-intersection count; near-route count; actual pixels/overdraw. Compare those with the operator's visual impression before calling bubbles missing.
- [ ] Add conservative **draw-only view-frustum culling** candidate for ordinary shells/clusters with bounds including physical radius, breathing, lens blur/near spread, camera projection and border. Do not drop them from the simulation, collision field, wake history or identity. Check orthographic, near-plane intersections, offscreen giants, camera movement and high-DPI.
- [ ] Keep probe glint visibility **separate**: offscreen real bubbles can legitimately be reflected by on-screen glass in a 360° environment; blindly reusing camera-culling results for the cubemap would change reflections. Measure importance and pursue probe-specific policies only if the operator accepts them.
- [ ] Test whether OIT overdraw/fragment shader cost rather than vertex submission is the problem; use nonblocking pipeline statistics or GPU pixel/overdraw inspection. Do not equate `150 configured` with `150 expensive on-screen fragment passes`.

## 3. Near-field eligibility: what was implemented, and what remains

**Evidence:** `extruded_bubble.py:631–646`; `tests/test_extruded_bubble_empty_near.py`; `extruded_bubble_program.py:593–645, 977–1029`; `scene3d/defocus.py`.

- [x] Existing Sol optimization is **real but narrow**: `if shell_count or cluster_count:` skips the entire near layer only when *both* counts are zero. Its test checks empty-population skip and stale-target safety; it does not verify the common **populated-but-no-actual-near-bubbles** case.
- [x] The near/ordinary decision currently happens **inside vertex shaders** (`ebLens`, circle-of-confusion `> 1.5`). The CPU does not decide whether any ordinary shell or cluster actually occupies the near layer. Thus a populated scene can clear both near attachments, execute two instance draws, generate both texture mip chains, clip, full-screen gather and per-read-texel highlight-sprite submission with **zero surviving near geometry**.
- [x] Shared gather can perform **64 wide + 32 fine taps per output pixel** (conditional source reads skip many), and the highlight stage instantiates one four-vertex quad per texel at its selected read level. This is a substantial candidate at large card sizes. **This is not yet an observed GPU-time cost.**
- [ ] Implement/prototype conservative CPU near-eligibility using the **same lens/near-surface mathematical contract** and clip guards, including clusters; false positives are acceptable, false negatives are not. If none qualify, skip `begin`, `end`, mip generation, `composite` and sprite draw entirely. Compare shader/CPU decisions at transitions and close-lens cases without visual reliance on authored presets.
- [ ] Investigate a bounded near ROI (projected near object union expanded by maximum circle radius, highlight footprint and filter reach), not simply a zero/nonzero gate. Scissor/ROI output can reduce full-screen fragment shading; full texture mip generation and full-grid instancing remain unless explicitly redesigned. Measure options from cheap scissor guard to sparse tiles/atlas without introducing per-frame texture churn.
- [ ] Profile **near with active bokeh** separately from near-empty. Evaluate shared gather/clip/sprite passes, sampling reuse, tile occupancy and band-specific work while preserving light conservation, circular highlights and exact accepted blur (including extremely bright source spots).
- [ ] Compare high-fidelity candidate outputs in native and high-DPI sizes with camera crossings, large intersecting bubbles, border clipping, transparent layer ordering, projected clusters and silent/music transitions. Don't merely reduce `DEFOCUS_TAPS`, `_FINE_TAPS` or radius and call it an optimization.

## 4. Reflection-probe cost: favour light/colour, relax other-bubble freshness

**Evidence:** `extruded_bubble.py:685–711`; `scene3d/probe.py:30–246`; `extruded_bubble_scene.py:331–348`; reflection sampling in `extruded_bubble_program.py`.

- [x] The current probe captures **six 256×256 faces at High** and prefilters **eight additional mip levels × six faces = 48 further draws**. The prefilter's 32-tap fragment loop entails roughly **4.19 million cube texture tap iterations per full 256-pixel prefilter** (geometric mip-count sum), plus base-face water/backdrop drawing and bubble glint proxies. This is arithmetic from shader structure, not a GPU measurement.
- [x] The six-face probe includes expensive dynamic water/light background and per-bubble glint proxy draws. Camera-hidden bubbles may legitimately influence the reflection. Cubemap/pre-filter recomputation currently happens every rendered EB frame.
- [ ] Time separately: six-face backdrop, proxies, each prefilter level, state restoration and all GPU synchronization. **Important separation:** removing six glint-proxy draws alone does not remove the six backdrop draws or 48 mip-filter draws; to materially cheapen the probe, measure and address the capture/prefilter work itself. Check whether all mip levels are actually sampled in representative shell/roughness situations before removing any. Check `glCheckNamedFramebufferStatus` per face and per-pass uniform-location/GL-state queries as secondary driver overhead.
- [ ] Prototype **light/colour-first** reflection architecture: retain directional lighting, water hue, smooth highlights and surface detail at accepted quality; make the less-important **other-bubble proxy** component cheaper through representation/complexity/resolution or analytical glints while keeping bubble position/motion response current every rendered frame. Do not freeze full water lighting blindly: the water surface itself is time-varying.
- [ ] Treat temporal throttling of dynamic bubble reflections as a **later, measured trade-off**, not the first optimization. First exhaust cheaper full-rate representations. If retained/progressive/staggered probe work is still worth testing, require coherent interpolation/update with no visible teleporting, highlight popping, ghosting or stale cubemap seams under fast bubble motion and camera movement; no new timer.
- [ ] Investigate cheaper mathematically equivalent prefilter / sample reuse / compute reduction before any quality lowering. Confirm no cross-frame read/write hazard or stale face seams; test GPU contention and multimonitor.
- [ ] Record exactly which reflection degradation, if any, the operator accepts. Lower-priority **other-bubble reflection detail/quality** may be tunable if it produces a meaningful measured saving, but weaker glass, dimmer light, loss of environmental colour, or visibly stale/teleporting reflected motion is not an implicit acceptance.

## 5. Shared render target, MSAA, shafts, full-screen effects

**Evidence:** `extruded_bubble.py:568–669`; `scene3d/target.py:537–615, 618–714, 798–1060`; `extruded_bubble_program.py` shafts.

- [x] EB's target includes HDR, bloom, weighted OIT, sampled depth, multisample variants and a mid-frame background capture. For High the EB `_scene_samples` function currently resolves four overlay samples from the broad 3D Detail tier.
- [x] `SceneTarget.background()` fills both full-resolution background colour and background **depth** attachments. EB binds only the returned colour (`background, _depth = ...`); investigate whether another consumer/contract actually requires the depth output for this path. No cheapness assumption until resource/write and depth-testing semantics are verified.
- [ ] Profile the colour/depth capture, MSAA resolve, OIT resolve, bloom and final composition as separate GPU passes. Check allocation area (64 px buckets vs actual viewport), bandwidth and redundant attachment clears/writes. Prototype an explicit *colour-only background capture* contract for consumers that do not need the depth texture, without breaking the shared SceneTarget API.
- [ ] Check whether EB really requires a **sampleable** scene depth texture, or only a depth test attachment, in this exact path; optimize only with equivalent depth-test results and no effects regressions.
- [ ] Measure rays at half-resolution (40 ray-marching steps per pixel in its shader) plus two blurs separately; look for shared/reused lighting results rather than reducing rays, contrast, or sample counts.
- [ ] Cache safe invariant program bindings and uniform locations; trim unnecessary repeated framebuffer-state queries and bindings only within the Qt Quick state ownership rules. Some queries are correctly needed to restore the host.
- [ ] After profiling and no-visible-loss work, identify which remaining expensive effects have a **real, measured quality/performance continuum** worth exposing (possible examples: AA/MSAA, near-field defocus quality, reflection detail, volumetric/ray quality). These controls are a secondary operator feature, not a substitute for optimizing the High/reference path. Put accepted controls behind the per-visualizer **Custom** option in the existing 3D Visualizers tab, using a compact conditional reveal rather than permanent rows for every present/future visualizer. Reuse existing Settings/CUSTOM authority and inspect existing transition-specific AA infrastructure before designing parallel controls.

## 6. Presentation and contention-specific collapse

- [ ] Use GPUView/ETW, Nsight Systems/Graphics or an equivalent nonblocking capture to identify 3D/compute/copy-engine occupancy, driver submission time, waits, present/flip queue depth and residency/page faults. Contrast solo and competing-load states, despite global GPU utilization remaining <100%.
- [ ] Inspect `glNamedBufferSubData` on live/busy buffers; mid-frame background texture reads after writes; probe face→mip dependencies; texture mip generation; MSAA/OIT resolve transitions; and buffered Qt Quick render-target handoff for implicit stalls.
- [ ] Identify whether the collapse is a **GPU throughput** problem, driver serialization, VRAM residency/bandwidth, CPU/GIL + memory churn, or frame presentation starvation. A GPU-heavy visualizer can trigger a cliff without any individual operation being catastrophically expensive in isolation.
- [ ] Compare fixed-snapshot GPU costs with live scene on same machine, same card size and monitor arrangement. Preserve currently established latest-wins publication, display staggering and transition gating; do not reintroduce periodic polling or synchronous image paths.

## 7. Priority, decision gates and final sign-off

**Investigate first:** (1) live drift family CPU/copy/upload split; (2) near-populated-but-empty pass; (3) cube capture/prefilter; (4) GPU under-load stalls; (5) frustum/occlusion counters. These can be instrumented together, but **rank by measured milliseconds**, not audit rhetoric.

- [ ] Produce a before/after table covering solo & competing GPU load, at least two actual display sizes, drift off / full swirl, empty / populated near, and bubble/cluster density, with CPU logical, render-thread, GPU and frame-age statistics explicitly separated.
- [ ] Rank **source-proven waste** separately from **measured time** and **speculative redesign**; report confidence and quantified tradeoffs for each. Include why rejected candidates would not help.
- [ ] Land only the best verified, minimal-risk changes. Revalidate stable ID trails, no event/tick changes, per-display Qt Quick lifecycle, display re-entry and zero-music/quiet behaviour.
- [ ] Do not make completing the Waveform Ribbon primitive a prerequisite. `S3D-1` ribbon geometry does not directly solve speck drift, optics or cubemap load; shared particle/compute improvements (`S3D-2`) may become relevant **after** confirming the bottleneck and parity requirements.
- [ ] Final visual acceptance remains with the operator. Do not silently degrade accepted EB appearance or mark partial/candidate work complete solely because benchmarks improve.

### Audit boundary

The 2026-10-29 runtime archive `\logs\evidence_chest\logsd2b0a73b062.zip` **is now available and analysed** (including rolling binary frame traces, perf, process-scoped GPU usage, handle attribution and GUI-stall samples). No external process GPU metrics, hardware per-pass GPU execution timing, controlled same-settings A/B capture or on-device GPU profiler data was supplied. The trace **measures a severe dual render/logical slowdown** but does not prove its root cause. No repository content, code, tests or existing plans were modified; this remains a standalone investigation file.
