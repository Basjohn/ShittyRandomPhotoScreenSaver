# SRPSS | Current Plan

Live, ordered work only. `[ ]` work remains; `[~]` a candidate exists but is unaccepted (awaiting validation, never an
implicit pass). When an item lands, delete it: completed work lives in source control and its durable contract in
`Spec.md` / `Docs/` (Reference, Architecture, Guardrails, Guides); rejected mechanisms in `Docs/Historical_Bugs/`. This
is not a changelog. Deferred, unadmitted ideas live in `Future_Work.md`.

## 0. Scope and rules

**Accepted baseline (not live work):** original Bubble, Extruded Bubble, Neon Lake (`shockwave_grid`),
Oscilloscope, Spectrum/Rainbow Ghost, Voxel Sphere (`sphere`), source routing, transitions and Foundry launch buttons. Reopen an accepted
area only for a concrete new defect; deferred or unadmitted work belongs in `Future_Work.md`. Historical recovery
IDs, completed gates and rejected mechanisms belong in source control or their focused historical/investigation docs,
not in this working plan.

**Rules:** one Settings/capability/CUSTOM/render/lifecycle owner and the sole Visualizer logical clock. No new
floor, capture/DSP, renderer-side simulation, timers/polling or camera-following replacement populations. Preserve
authored presets (mutable, never test-pinned), BTF, accepted timings, parallel work and strict retirement barriers.
CLI/sidecars, never environment-variable configuration. Smallest meaningful focused test per change; the isolated
chunked suite only at milestones; no build/installer unless requested. Visual work is judged on rendered pixels against
its target (`Docs/Guides/Visualizer_Visual_Tuning.md`), and any claim of "fixed" needs the failure reproduced first.

**Linux compatibility** runs as a separate operator-requested plan, `Linux_Plan.md`; it does not reorder this plan.
New platform-facing work (power, display, input) still ships a basic Linux path or an explicit inert one alongside
the Windows path, so it never needs its own Linux audit later (operator, 5 Nov).

**Architecture checklist:** `Docs/Reference/Architecture_Checklist.md` (the 6 Nov audit, verified against source on
7 Nov: 16 items with severity, reward, effort, owning boundary, fix, regression bar). Its Tier 1 (AC-01 Settings tab
registry, AC-02 Visualizer host binding, AC-03 application-service tier) is the prerequisite work for step 7 below;
AC-01 landed 7 Nov (contract: `Docs/Architecture/Settings_Bucket_Persistence_Contract.md`, "Tabs and pills: one
registry"). The items promoted to run soon are in §3. Nothing else in it is admitted until it appears here.

## 1. Order of work (strict)

Live checklist: every open step is its own box, ticked boxes are deleted, and a landed item leaves only its `[~]`
validation steps and open side defects. **Load runs:** game60 at most 10 minutes in total, started by the lead only
after the operator's yes on a question card; agents never run load (invisible checks without load, at most 3 min).

**Now (in flight):**

### Item 0. Operator defects of 11 Nov: section 1B, in its own order, ahead of everything below

### Item 1. Operator-reported defects first

- [ ] Material density, composed-stack readability and Studio surfaces: section 1A, item 1.7 (with 1.7a, 1.7b).
- [ ] Native Settings corners: section 1A, item 1.9. Keep their acceptance and reversible checkpoints separate.
- [ ] Studio stall, clip selection and sidecar log (contract: `Docs/Reference/Visualizer_Studio.md`; the control-hints
  test runs on a never-shown window), D1 run (1B.14 harness) with the lead's checks:
  - [ ] Edit Reaction Mode while Waveform plays (the Studio keeps responding; the sidecar log shows the replay).
  - [ ] Pick Human once (the clip selection lands once, with its sidecar log line).

### Item 2. §7.1 Waveform Ribbon reactivity (operator, 7 Nov night: "Adaptivity is the enemy")

Contract: `Docs/Guides/Visualizer_Reactivity_Authoring.md` (§2B, §2C, §13D). Evidence:
`.artifacts/evidence/visualizers/waveform_ribbon/memoryless_reactivity/` (`20261107_lead/`, `20261107_bands/`) and
`.artifacts/webp/visualizers/waveform_ribbon/memoryless_reactivity/`.

- [ ] Lead review on a rendered showcase WebP on recorded music: Frozen Past (Preset 5), live.
- [ ] Lead review on rendered Studio frames (D1 run, 1B.14 harness): Pulse Count, Pulse Falloff and Freeze Deflate in
  the Studio.
- [ ] Vocals first, remainder: a kick inside sustained bass raises the swell 21% less (median .058 -> .046; those
  kicks also reach Kick Accent now); check it on the operator's look before tuning Pulse Strength's mid-led routing
  further.
- [ ] Breathing as a swell and release with proper motion (operator: 2D Bubble's breathing is the reference; guide
  §13A). Breathing is now only a faster release in soft passages.
- [ ] The onset reward is still sized by the bus's adaptive flux threshold (about 1 s of context: the same kick right
  after a dense passage scores .22 against .61); size it on the fixed scale.
- [ ] Group Wave still reads close to Travelling Pulse on rendered strips (it keeps the summed travelling field; its
  sets need their own pass), and its Pulse Width is not yet the band core the other two modes use (operator: "a
  relatively small horizontal width and the full vertical width").
- [ ] Pulse bands' colour edges read crisp at Pulse Falloff below ~1 on wide bands (Preset 5's vertical colour
  columns); judge on the operator's look whether the light's falloff should follow the geometry's broader envelope.

### Item 3. Expanded Visualizer M2 onward (plan 01; operator's M1 amendment: a mode switch never re-expands)

Contract and phase ladder: `Docs/Future_Work/Expanded_Visualizer/01_Expanded_Visualizer_Implementation_Plan.md`
(§0.6 capable modes, cycling and inset; §G overlays; M3c Fullscreen Edit). Next: M2b, then M3 and M3b/M3c follow-ups.

- [ ] M2b, Spectrum's width-scaled bar count (operator, 8 Nov: "20% more if fullscreen and horizontal"): the display
  rule is built (`widgets/spotify_visualizer/spectrum_display_bar_count.py`, round(1.2 x) bars, cap 64, resampled
  by the renderer); the width-ratio DSP recompute of plan 01 M2b stays open and needs the hidden activation
  transaction (an engine bar-count change bumps its generation). Spectrum's own edge fade is part of it.
- [ ] Expanded Visualizer on D1 (1B.14 harness), lead review of grabbed frames: the expanded card's inset (operator,
  7 Nov night: "Don't reach nearly close enough to the screen borders") and the ordinary widgets and their shadows
  fading out with it (operator: "Don't really hide/disable the widgets underneath"; 14 logical px at 2560 x 1440
  was 30). Complex transitions under the takeover are M4.
- [ ] Bright-area text switch (operator's long-term item, plan 01 §G): overlay text white with a soft shadow should
  switch to black over a bright Visualizer area; cheap means no per-frame CPU readback (a `ShaderEffect` on the text
  sampling the already-rendered frame, or a tiny luminance probe only while an overlay shows). Not built.
- [ ] Now Playing on D1 (1B.14 harness), drag and hover driven by messages, lead review of the frame trace and
  grabbed frames: Show On Hover (`now_playing.hover_reveal`, on main since 0eda39c4) and Now Playing's parts as the
  block's children in Fullscreen Edit (`now_playing.child_geometry`, 2100fdc2): the child lock, a part drag and the
  hover re-fade on the real display.
- [ ] Side defect (8 Nov): `tests/test_qtquick_system_audio_osd.py::test_osd_colour_inheritance_respects_active_widget_
  theme_and_authored_overrides` fails when run after `tests/test_visualizers_fullscreen_mode_pill.py` in one
  process (passes alone; reproduced on the base): Widget Theme state leaks between the files.
- [ ] M4 (plan 01 `02_E0_Covered_Display_Admission.md`): the GPU/render-thread measurement with photo changes on the
  other display.
- [ ] M4: the two-monitor look, as a D1 run (1B.14 harness, Expanded Visualizer on D1 with a hidden D0-side owner);
  what truly needs both displays visible is listed in that report, not assumed.

**Next (admitted, in this order):**

### Item 4. Settings round-trip native residual

- [ ] About 2.5-6 MB of native heap per open/close, and the Studio's about 1-2 MB per session (measurements and the
  next step: section 3, "Settings round-trip memory growth").

### Item 5. Card/theme legibility beyond item 1.7 (details at section 4)

- [ ] Rerun `tools/theme_legibility.py` against final composed surfaces.
- [ ] Retain concrete failing palette roles.
- [ ] Fix light-theme shadows.
- [ ] Raw linked widget mirrors remain an authoring concern; runtime ink correction does not make raw exports pass.

### Item 6. Hygiene

- [ ] The hidden cross-test `tmp_path` dependency (section 3).
- [ ] The AC-13 remainder (`Docs/Reference/Architecture_Checklist.md`).
- [ ] AC-14, AC-15 and AC-16 (same checklist).

### Item 7. One measurement session of at most 10 minutes under game60, only after the operator's yes

Approved by the operator on 11 Nov ("The machine will not get quieter"). The lead runs it at the first gap in
which no agent is running tests (a measured run beside agents' GL tests is void by its own conditions), with a
fixed run list, no reruns, the conditions recorded. Baselines and evidence paths: section 3, "Lead, the quiet
machine".

- [ ] First reveal on the engine worker against in process under load (closes the Watchlist's latency entry).
- [ ] A second clean Waveform tick-cut round.
- [ ] A clean Waveform P4 GC run, and the long run with Settings round trips.
- [ ] A Settings round-trip run.
- [ ] The alternated Glass/Normal card-materials pair.
- [ ] The two-monitor canonical game60 outlier (48.6 fps, never repeated).

### Item 8. §8 Accepted-mode follow-ups

- [ ] The brief Bubble performance-parity check.

**Then (decided 5 Nov, `Docs/Future_Work/Graphics_Backend_Decision_2026-11-05.md`):**

### Item 8b. Universal visualizer performance architecture (operator, 7 Nov; the Decision's addendum)

Started once the current set of fixes and optimisations lands. P1 is accepted
(`Docs/Future_Work/Native_Core_P1_Spike.md`); P2 contracts: `Spec.md`, `Docs/Contracts.md`,
`Docs/Future_Work/Native_Core_P2_Engine_Design.md`; phase-boundary audit:
`Docs/Future_Work/Native_Core_P2_Phase_Boundary_Audit.md` (H1/H2 reviewed; the operator admitted audit repairs
alongside the 9 Nov miscellaneous work). Triggers 2 (render-thread starvation) and nearly 1 (EB at display size
over 8 ms) are met; Expanded Visualizer M2-M5 continue meanwhile; M6 (4K acceptance) waits for P2 and the first
P3 ports.

**P2 remaining checks outside the ordered audit repairs:**

- [ ] Frozen check, the lead's at the next GitHub Remote build (`tools/github_remote_build.py`): from the built
  artifact, the engine worker's import closure is QtCore only and the image worker's Qt dependencies are the
  expected ones (the same oracle as `tests/test_visualizer_engine_import_weight.py`, run against the frozen
  manifest), icons unchanged. What needs the frozen product running (flat worker memory over one Settings round
  trip; the first Neon Lake activation logging a cold link or a cache hit) is 1B.14's frozen run.
- The real-endpoint capture test and the no-load first-reveal comparison are 1B.14's; only latency under load
  is a Watchlist entry. None of them holds P2 open.
- [ ] Make the framed-view negative control independent of presentation timing
  (`test_visualizer_owner_engine_worker.py::test_the_framed_view_the_worker_tick_reads_follows_the_owners_controller`).
- [ ] Decide bounded reconstruction for a target that never reveals, including stopping a failed owner's runtime on
  refused reload; the existing loop can retry every six seconds.
- [ ] Bubble owner: define Random Group Drift's guarantee before retuning or asserting alignment;
  `test_bubble_reactivity.py::test_group_drift_aligns_non_swirl_bubble_motion[random-x]` depends on the draw.

**Remaining sequence (one Opus slot, in this order; it reports at each numbered boundary for the lead's
audit; focused proof for each).** Steps 1 and 2 of the 10 Nov sequence (M4 rendered parity, M5, L2-L5, the POSIX
transfer lifetime) merged 11 Nov with R-184 and R-185; records: the phase-boundary audit's "11 Nov" section, the
design and closeout docs.

Attribution merged 11 Nov (382ae139; baseline `tools/baselines/overhead/2026-11-11_4658981b.json`; record in the
phase-boundary audit and `Docs/Reference/Benchmarks.md`; evidence `.artifacts/evidence/native_core/20261111_attribution/`).
What it left open:

- [ ] Extruded Bubble still runs 4 imports inside per-frame functions (about 2.3 us each through PySide's import
  hook; older than the 7 Nov baseline): move them to module level, then sweep the other modes' and transitions'
  per-frame paths for the same pattern; proof by the overhead baseline's call counts.
- [ ] Neon Lake's driver memory at its first draw (`private_other`, about +280 MB committed, mostly not
  resident) is not attributed: read GPU allocations around the first draw before P3 sizes anything for it.
- [ ] Neon Lake against the new baseline: GL calls 354 -> 361 and relative GPU time 1.14 -> 1.44 ms since the land
  work (33912e5a); the refinement round reports which change accounts for it (1B.6).
- [ ] Waveform Ribbon hard-codes 4 samples (`rendering/quick/scene3d/waveform.py:378`); route it through the
  scene's sampling owner.
- [ ] `tools/artifact_paths.py` sends a worktree's evidence to the main checkout's `.artifacts`; give it the
  running checkout's root so worktree agents need no redirect.
- [ ] Multisampled scene targets are not reproducible draw to draw on this GPU (the parity gate judges
  single-sampled targets and reports product sampling beside the path's own repeat); attributed only as far as
  "the mode's own passes".
- [ ] P2-C1 remainder (closeout doc section 2): a failed high-water admission preserves the last good frame
  without silently changing the worker path; the load part only after the operator's yes.
- [ ] P2-C2 remainder: leases and holds release exactly once across Settings, mode switches, worker death, a
  failed reload and a Visualizer-off run; one worker/mapping at most and zero worker cost while disabled.
- [ ] M5 remainder: the Studios and the post-failure fallback were not measured separately (the in-process and
  worker laps show a first-visit GPU high-water step, not growth).
- [ ] L3 remainder: `collect_ms` with displays on and under load (the one live reading, 13.5-21 ms over four
  processes, was taken with the displays asleep and the Visualizer parked).
- [ ] L4 residual: a blocked cadence thread now fails its session closed at the worker's heartbeat, but the
  blocked thread itself stays in the worker until it returns.
- [ ] D1 run (1B.14 harness), lead review of grabbed frames: a mode switch on the engine worker no longer leaves a
  faint ghost of the outgoing mode after its fade-out (R-184: Sphere, Extruded Spectrum, Waveform Ribbon switches).

3. H3, the Linux worker default: the source flip merged 11 Nov (6c2039b3; `visualizer_engine_worker_platform_
   default` returns the worker on every platform; `--viz-in-process` still chooses in process; a worker that
   cannot start or configure falls back in process with a logged reason). Nothing of it has run on Linux
   (`Linux_Plan.md` Phase 4 says exactly what is unverified):
   Linux is best effort (operator, 11 Nov): no Linux environment exists, so the flip stands on code quality and
   the tests that run on Windows, and H3 is closed. What a first Linux run would show is the Watchlist entry
   "Linux engine worker".
   - [ ] `Docs/Guardrails/Linux_Compatibility.md` section 7 forbids a Linux-branch test in a shared file; the
     platform-injected `[False]` case in `tests/test_platform_selection.py` is the only negative control that
     runs on Windows: record it there as the admitted exception or move it.
   - [ ] The `[PLATFORM]` branch of `_note_in_process_path` (`quick_display_visualizer_owner.py`) can no longer
     fire; keep it only if a platform may be taken off the worker again, otherwise delete it with its test.
4. P3's four decisions and first native rendering substrate (order: D1/D2 with the drop edge, then D4, then D3;
   the substrate is built against the single-sample parity gate, `tools/visualizer_replay/owner_render_parity.py`):
   - [ ] D1: the native reader vs the GUI thread closing the mapping mid-copy; liveness is per stream, not per
     process.
   - [ ] D2: a single consumer and a non-consuming head read for the Python owner; a reader that retains a frame
     needs an explicit drop edge (R-184).
   - [ ] D3: EB geometry once per revision, not per frame. The worker's +34 MB at the first Waveform Ribbon is
     not geometry: 32 MB is the buffer numpy's OpenBLAS reserves on the first matrix-matrix product in a process
     (committed, not resident, never freed), so D3 sizes nothing against it.
   - [ ] D4: EB's fp64 drift solver on Vulkan, at equal quality (operator, 11 Nov: Vulkan is the front, strong,
     stable face of the product, never the fallback; OpenGL is the fallback). Direction to prove, not yet decided:
     (a) keep 64-bit floats where the device has them: `shaderFloat64` is a queryable Vulkan device feature
     through the native handles a C++ core holds (QRhi's own API has no query, which is why the Python path could
     not ask); (b) for devices and backends without it, the same solver in double-single arithmetic (two 32-bit
     floats per value, error-free sums and products) or a camera-relative reformulation that keeps the error
     below the fp64 oracle's visible threshold, judged against the fp64 result on recorded drift; (c) or the
     drift integrated in the worker in float64 and sent once per revision, if D3's geometry rule makes that
     natural. Pick by measured error and cost; the shader-readiness check must discover compute sources instead
     of a fixed module list.
     Inventory (Sonnet, 11 Nov): `D:\Temp\Scratch\SRPSS\research\20261111\eb_fp64_drift_inventory.md`. Facts
     the decision starts from: the doubles live only inside two compute programs (`CHAIN_COMPUTE`,
     `CLOUD_COMPUTE`: step log, chain geometry, per-chain shift and phase; add, multiply, divide, `floor`, `mod`
     only); every output the draw shaders read is already fp32; only chains carry exact fp64 state across frames
     (the cloud's phase, span and seed are float32); the recorded reason is that a float32 span/carry moved a
     chain's knot step one tick early against the CPU, plus 2 pi reduction of ever-growing phase; a complete
     float64 CPU oracle exists (`MaterialDriftReference`, tests only, 1e-4, at most about 4 s of simulated time).
   - [ ] D4 input: nothing detects fp64 today (OpenGL 4.6 Core implies it; a failed context raises "no renderer
     fallback"); the native core needs an explicit capability read and a stated behaviour without it.
   - [ ] D4 input: both drift shaders are on the `LEGACY_GL_ONLY` list because they fail `qsb` on loose uniforms,
     so "qsb compiles fp64 SPIR-V" (phase-boundary audit) is not shown for them: restructure the uniforms into a
     block and compile them, or correct the audit's claim.
   - [ ] D4 input: the oracle comparison runs 150 to 240 ticks; extend it to a long horizon (hours of simulated
     time, the saver's real session length) before any 32-bit formulation is judged, and state the visible
     threshold of drift error.
   - [ ] D4 input: option (c) would send about 3.99 MB per revision at full population (240 chains x 128 knots,
     2500 snow, 216000 specks, 16 B each); measure the worker's CPU cost for it.
   - [ ] The solver docstring says the CPU reference keeps positions in fp32; it keeps float64 and narrows only
     when packing. Correct the docstring; the phase-boundary audit cites the doubles at `SOLVER:39-92`, they run
     to line 210.
   - [ ] Transport rule for the substrate: nothing through the resource sharer; a name on POSIX, an exact-process
     handle on Windows.

**P3 and P4 (nothing built yet; decomposition and decision inputs:
`Docs/Future_Work/Native_Core_P2_Closeout_and_P3_Entry_2026-11-09.md` section 3; backend decision:
`Docs/Future_Work/Graphics_Backend_Decision_2026-11-05.md`; SMP seam:
`Docs/Future_Work/ShittyMusicPlayer/03_PCM_Source_and_Native_Core_Seams_2026-11-09.md`).** P3 is one C++/QRhi
native core for all custom drawing, rolled out in this order; each stage retires its raw-Python GL renderer only
after parity, never leaving a second permanent renderer:

- [ ] P3.0 The four decisions above (D1-D4) and the transport rule written as contracts, seen by the lead and the
  operator, before any C++.
- [ ] P3.1 Native QRhi substrate: exact Qt/PySide6 ABI, the frozen MSVC DLL guard, resource ownership, the native
  packet reader with its quiescence barrier and drop edge, capture/clip parity. `native/spike_p1` stays evidence,
  never a shipped renderer.
- [ ] P3.2 Spectrum first: pixel parity against the single-sample gate
  (`tools/visualizer_replay/owner_render_parity.py`), frame trace and CPU/GIL measurements, inside the same
  scene (no second compositor).
- [ ] P3.3 Transitions' shared fullscreen pass, then the specialised ones (Crumble, Particle, 3D Block Spins),
  keeping timing, image ownership, covered-display admission, protected clipping, shader identity and GPU
  resource accounting.
- [ ] P3.4 Waveform Ribbon, Extruded Bubble, the remaining Visualizers, the image presenter/background and the
  Scene3D nodes.
- [ ] P3.5 Switch the whole Qt Quick window's backend once every raw-GL dependency has retired: Vulkan as the
  default, OpenGL through the same core as the selectable fallback (D3D where supported); never a Python OpenGL
  node inside a Vulkan window.
- [ ] P4 Mixed-resolution soft layers in the same core; thin emissive lines, dots, rims, particles and UI stay
  full resolution; no per-mode extra renderer or backend.
- [ ] Expanded Visualizer M6 (4K acceptance) waits for the first P3 ports (plan 01); P2 holds nothing.

### Item 9. SMP & Full Display

Port-readiness rules bind all new GPU code from now. The production Vulkan backend is not yet enabled: P2 is the
Windows-default supervised Python worker; P3 is the planned C++/QRhi native renderer and Vulkan-default migration
(with OpenGL fallback), informed by measured cost and the operator's explicit modernization goal.

- [ ] Expanded Visualizer first (`Docs/Future_Work/Expanded_Visualizer/01_Expanded_Visualizer_Implementation_Plan.md`,
  EB only; its §0 holds the phase ladder and the 4K budgets).
- [ ] Then ShittyMusicPlayer (`Docs/Future_Work/ShittyMusicPlayer/02_ShittyMusicPlayer_Implementation_Plan.md`,
  gated behind `--smp` until its Gate M9; its §0A holds the prerequisite phases and §13-16 the operator's audio,
  Settings-tab, icon/artwork and rearrangement targets; §16A holds the operator's fullscreen arrangement: a
  tiling tree with choose, swap, resize and split/remove, no dead sections, SMP fullscreen remembered, Settings ->
  Layout pills Widgets and SMP).

### Item 10. §6 Shared 3D architecture and §7 Visualizer modes

- [ ] Resume after Expanded Visualizer acceptance and its full-display measurements, under the port-readiness
  rules: Reactive Liquid / Melt Pool -> Concrete Rain -> Usu Moonscape, lab-first per §7.0. If a trigger fires
  first, the native Vulkan core precedes them.

## 1B. Operator defects and requests (11 Nov; run first, in this order)

Live checklist: every open step is its own box, ticked boxes are deleted, and a landed item leaves only its
`[~]` validation steps and open side defects. Order: the Edit/exit defects, the Studio work, the fullscreen
overlay contract, window material and corners, presets last. Every fix reproduces its failure first; the lead
judges visual items on rendered pixels and audits each branch against the pre-fix code before merging.
**Nothing in this section waits on the operator** (operator, 11 Nov: checks are the lead's work; a remaining
question without a simple test is a Watchlist item, never an open phase). What needs the real product on real
hardware is proven by the lead's harnesses in 1B.14, and behaviour that changed is listed once in section 2
("Changed on 11 Nov").

### 1B.1 Edit edits the display it was entered on (merged 46129166; contract: plan 01 M3c "Edit beside the view")

- [ ] Side defect (unreproduced): in an ordinary global Edit, closing the Visualizer and then switching mode makes
  `activate_edit_visualizer_profile` return False (`rendering/quick/custom_layout_owner.py`, the `visible is None`
  branch), which looks like a forced runtime reload. Reproduce in a test or rule out.

### 1B.2 Cursor keeps its changed shape after exit until a click (merged 0f8f4836; R-183; proof owed in 1B.14)

The retire owner now gives Windows the arrow natively. The native harness reproduced the stuck shape only with
Qt's pointer tracking cleared artificially, so the operator's real exit path is unproven.

- [ ] Side defect: when a hovered QML item is destroyed or left, the saver window can keep the hand or arrow
  instead of the Halo until the Halo next re-applies it.

### 1B.4 Shape instrument for Spectrum and Neon Lake (merged; contract: Visualizer_Studio.md)

One instrument in Spectrum, Extruded Spectrum, Neon Lake's Frequency Response and its Reaction Shaper; the old
shape widget is retired; shape drags are in the churn guard; Studio tooltips wrap inside the window.

- [ ] `fft_to_bars` gained two helper calls per tick (`shape_bar_profile`, `lane_sample_positions`); re-record
  the Spectrum overhead baseline so the +2 calls are attributed (with section 1 item 8b's attribution box).
- [ ] Admitted later if wanted (operator's call): a pop-out larger canvas; Spline Curve's layer nodes and Voxel
  Sphere's zone boundaries on the same instrument; Shift axis lock, snapping, double-click reset.

### 1B.5 Neon Lake: all visible land is brush-editable (merged 33912e5ae; refinement round in flight, Opus High)

A stroke past the grid grows the authored grid under it invisibly (grown cells are an overlay on the generated
landscape; an authored origin keeps horizon, detail and glow; shipped presets' terrain loads byte-identical;
one commit and one undo per stroke; a refused state at the 257 cap). Contract: `Docs/Reference/Neon_Lake_Basin.md`.

- [ ] Painted growth cost: the mesh refines under one bounding box of painted cells (two far corners refine
  everything between; a fully painted 257 grid costs 5.65 ms against 1.95 ms at 65). Refine in tiles holding
  painted cells only, crack-free; report one corner, two corners and the whole grid; distance-based density if
  it holds without aliasing the smallest brush.
- [ ] Brush Radius is now a share of the basin (stable across growth): rescale its default and range so the
  default footprint on each shipped preset is about what it was (0.57x on Presets 1 and 2 today).
- [ ] Off-screen PNG of the refused state at the cap (struck-through footprint and notice).

### 1B.6 Neon Lake: smooth land reaction, Growth and Indents (merged 33912e5ae; refinement round in flight)

The reaction reshapes the land smoothly (lanes cross-fade along the height, cubic tables and elevation, an eased
floor, a shore fade); Growth (mounds to spires by Growth Shape) and Indents are optional, default off, authored
neutral into the three presets; drives are memoryless on the fixed scale. Under music the existing presets do
change: the tears are gone and the reaction is a little weaker on banks and very low land.

- [ ] Indents are barely visible at full drive on Preset 1: a depth law that clearly sinks visible land on all
  three presets' default views, smooth, never below the water-boundary contract; staged-drive sheet and a WebP.
- [ ] `tools/overhead_baseline.py` for Neon Lake against the stored baseline, with system usage.
- [ ] Logical-tick cost of the lane, Growth and Indents drives, before and after.
- [ ] GPU before/after alternated in one session, control-relative, including React To Music off (the +5-12%
  reaction cost so far comes from separate sessions).
- [ ] Continuous play across two songs back to back on the music-response trace: mid-song kicks read, no state
  across the song boundary.
- [ ] Off-screen PNG of the Neon Lake Studio's Reaction workspace with the Growth, Growth Shape and Indents rows.
- [ ] Growth Density (site cell size) and a Growth region bias (far land only / by elevation through the shaper):
  canonical spec entries with Studio rows, authored neutral into every preset, dormant when neutral.
- [ ] Lead pixel review of the refinement round; merge; then tell the preset agent Neon Lake is ready.

### 1B.7 Fullscreen Now Playing: one geometry contract with the Media widget (merged 189fbd36c; plan 01 M3c)

Now Playing and the toast are edited by ordinary Edit's handlers; the Media seek bar is one component
(`MediaSeekBar.qml`) and Now Playing has it as an option (Fullscreen Mode -> Now Playing -> Seek Bar, default
off). What stays overlay-specific, with its reason, is listed in plan 01. Old profiles' artwork factors load
through a bridge (`Docs/Architecture/Persisted_Input_Compatibility.md`).

- [ ] The safe-area edge guides are no longer drawn in Fullscreen Edit (as in ordinary Edit); confirm that is
  wanted or restore them through the ordinary guide owner.
- [ ] Evidence gap: no side-by-side render of the Media widget's own Edit beside Fullscreen Edit (it needs an
  off-screen harness that drives ordinary Edit on a Media card); build it beside
  `tools/expanded_visualizer_evidence.py`.
- [ ] A raw old profile file on disk with the retired artwork factors is covered only by the normaliser test
  (the round-trip test writes through the settings manager, which normalises on write): add a fixture file.
- [ ] Side defect: `tests/test_qtquick_media_presentation.py:429` pins a default colour
  (`app_volume_fill_color`) and fails when run after the Visualizer test files in one process (passes alone).

### 1B.8 Light themes are practically opaque in the saver (M1 merged 4674e801; M2 in flight, Opus High)

**Material track (operator, 11 Nov: proper transparency on light themes, no inset while keeping the material on
all themes, border materials). One agent, one shader, in this order, each its own reviewed checkpoint.** Contract:
`Docs/Architecture/Card_Surface_Materials.md` ("M1 dark-ink rule"); evidence
`.artifacts/evidence/materials/20261111_m1/` (open `OPEN_FIRST_overview_main.png`).

M1 landed: dark ink's panel is bounded at the card's Settings-variant shell density (`SurfaceContrast.panelCeiling`,
shader uniform `panelCeiling`), faint runs correct their own ink (`legibleInk`), and a run faded by item opacity
takes a text-local plate. Wallpaper swing inside light cards went from 0.0 to 0.08-0.25; dark themes identical.

- [ ] M2. No inset on any theme: the `plateInset` rim box of 1.7b (section 1A): the material face reaches the
  inside of the real border, dark and light, content padding unchanged; before/after renders of every material
  on one dark and one light theme, and text still passes on the composed pixels with M1's ink rule.
- [ ] M2. The ink plate behind faded runs (the pill behind "PLAYING" on Polished Chrome, Mica) re-checked at 1x
  and 3x on the three light themes once the inset is gone; softened or tightened if it reads as a sticker.
- [ ] M2. Dark-identity comparison that separates "inset gone" from any other change on dark themes.
- [ ] M3. Widget border material: the remaining boxes of 1.7b (ring shading from the same backdrop, Border
  Material and Border Opacity Adjust in Style Overrides, Normal/Flat pixel-identical).
- [ ] M4. Window border material: 1B.9's box (the Settings/Studio border ring takes the same rule).
- [ ] Each step: `.qsb` regenerated, the SURFACE block kept identical across its three shader files, one focused
  GPU before/after, lead pixel review on the operator's two wallpapers.
- [ ] Known dark-theme shortfalls measured in M1, written into `Card_Surface_Materials.md` with their numbers
  (Default Dark on the bright wallpaper 3.9-4.3; Midnight Cobalt accent 3.42), and whether M2 moves them.
- [ ] Card shell bound (about 0.73-0.76) against the real Settings window (0.63-0.72): recorded in
  `Card_Surface_Materials.md` with the reason cards do not read the linked Settings theme at runtime (lead, 11
  Nov: a card must not depend on Settings window state).
- [ ] Linked button red test (1B.11's side defect) fixed as its own commit before M2: a state ink may flip
  polarity in `ui/settings_surface_composition.py` `_correct_ink` when neither more alpha nor its own pole can
  reach the ratio; ordinary semantic inks keep their polarity; stills before and after; R-NNN entry if it was a
  silent long-lived red.
- [ ] Feature requests from the agent recorded here as their own boxes when admitted.

### 1B.9 Settings and Studio window corners bleed (see-through corners merged a89ce123; continues 1.9)

Both windows now end at their rounded border: nothing is painted outside it (alpha 1/255 there, so a layered
window keeps those pixels for drag and resize), and the opaque corner caps, the backing stroke and its near-white
inner line are gone. Thicker borders (they square the corner) and a pre-Accent region (staircase) are rejected;
measurements and rules: `Docs/Architecture/Settings_Theme_Architecture.md`. Residue no layered window can remove:
a few pixels of blurred wallpaper outside the arc (worst difference 41-86 levels, was 72-251).

- [ ] Studio resize areas have no test for their geometry; add one beside `tests/test_studio_chrome.py`.
- [ ] Close or rewrite 1.9 (section 1A) to point here.
- [ ] Side defect: the Studio window shows only blur (no title bar or content) in native captures by
  `tools/settings_native_corners.py --window studio`; find whether it is the capture setup or the Studio.
- [ ] Side defect (red on main before this work): `tests/test_waveform_studio_theme.py::
  test_every_theme_yields_readable_studio_chrome[Matte Graphite [Single]]`, accent-text contrast 2.12 against 4.5.
- [ ] `tools/settings_native_corners.py --qt-scale-factor` sets Qt's `QT_SCALE_FACTOR` inside the tool process to
  emulate 100% and 200%: decide whether that tool-only use stands under the no-environment-variables rule.
- [ ] If the operator still sees escape: the Windows 11 DWM corner preference on a non-layered variant
  (Microsoft's guidance excludes layered windows and windows with a region from system rounding; cost check:
  shadow ownership, translucency, the layered-window repaint path of section 9's freeze fix), then a
  composition-host clip. Whichever clips needs input, resize, snap/maximise, DPI change, activation and
  Studio-over-Settings modality proven on the real `SettingsDialog` and Studio window.
- [ ] Window border material: the border ring takes 1.7b's border-material treatment (one rule for cards and
  windows), inside the +2 px budget (unused: the border stays 4 px).

### 1B.10 Presets (in flight: one Fable Medium agent, the operator's exception to the Opus roster)

Supersedes the lead's Spectrum presets 2-15 of 7 Nov (section 3). Every preset must read as unique and visually
impressive; the agent may ask the lead for a feature or architecture a better look needs, if it is not wasteful.
Order: Spectrum, then Extruded Bubble, then Neon Lake once 1B.6's refinement round has merged; the agent reports
after each mode for the lead's pixel review.

Spectrum round 1 merged 11 Nov (b9a9a4a3; evidence `.artifacts/evidence/visualizers/spectrum/presets/20261111/`).
Operator, 11 Nov: presets 5 (Tube Lights), 6 (Quicksilver), 8 (Blueprint), 9 (Afterglow) and 10 (Frost) "are all
ghastly ugly"; 2 Aurora, 3 Lanterns, 4 Dot Matrix and 7 Prism stand. Lead's reading: wide glossy, chrome, capsule,
grid-on-block and dark-fill looks fail; fine luminous gradients pass. Fewer good presets beat a full slot count.

- [ ] Spectrum round 2 (in flight): the five rejected presets replaced by new ideas, not re-skins; slots
  contiguous; the whole set judged together on the peak and quiet sheets; lead pixel review before the operator
  sees them.
- [ ] Bar gap control (0 to about 4 px), admitted: one canonical spec entry, authored into every Spectrum preset at
  2 px by the repair fill, shown through the spec in Settings and the Studio, a structural test, the Visualizer
  Reference updated. Built in round 2 only if a new look needs it; otherwise it stays this open box.
- [ ] `tools/visualizer_preset_author.py` refuses the shape keys (`spectrum_lane_strengths_linear has no Settings
  control`): admit them through the spec's own admission and the Studio shape rules, as the agent's script did.
- [ ] Side defect: Bar Count is admitted to 96 by the spec but `spectrum.py` clamps to 64 (`_MAX_BARS`, lines 28,
  102, 199): a higher count would draw only the first 64 bars. One owner for the maximum; render one frame at 96.
- [ ] Side defect: the segment border ring is lopsided (`spectrum.frag:914`: `<=` on one side, `>=` on the
  other): two border rows at the bottom and left against one at the top and right at card scale, and the fill
  share changes with scale. Make it symmetric; before/after at 1x and 3x on Dot Matrix.
- [ ] Side defect: the kick lane in mirrored layouts boosts the first bars and their mirror, which are the edge
  bars, wherever the Bass lane sits (`bar_computation.py:422-432`). It should follow the Bass lane's position.
- [ ] Side defect: Rim Glow measures distance to the square edge (`spectrum.frag:783-785`), so it facets at
  rounded tops.
- [ ] Side defect: `tools/release_media.py:69` binds `load_scenes(paths=USU_SCENES)` at definition, so
  `test_release_media.py::test_source_change_during_capture_discards_media` ignores its monkeypatch in a
  worktree without the `assets/usu/scenes` originals; resolve the default at call time.
- [ ] Side defect: seven `test_release_media.py` tests fail with `missing authored preset path: spectrum:1` when
  run in one process after the preset and Studio preset tests (order pollution; the file passes alone and on
  main after the merge): find the test that leaves the preset tree redirected and make it restore.
- [ ] Extruded Bubble: one arctic-themed preset.
- [ ] Neon Lake: three unique presets (using the shape instrument, far-land brush and the new land reactivity).
- [ ] Every preset authored through the Studio's Save To path, complete for every control (completeness guard).
- [ ] One showcase WebP per preset (`release_media.py`), reviewed by the lead before the operator sees them.
- [ ] Feature requests from the agent recorded here as their own boxes when admitted.

### 1B.11 Theme filter in the Linked row (merged d401b3c2; contract: Settings_Theme_Architecture.md "Theme filter")

- [ ] The theme list's and the popup's scrollbars render as the native black/white bar in off-screen captures;
  confirm on a real display and theme them through `shared_styles` if they are native there too.
- [ ] Side defect (red on main): `tests/test_surface_opacity_adjust.py::test_real_link_button_uses_state_ink_for_
  checked_text_and_lock_icon_offscreen` fails (worst contrast 1.58 against 4.5): the Linked button's checked
  text/lock ink. Fix with 1B.8's ink correction or at the link button's style owner.

### 1B.12 Fullscreen glyphs relative to the Visualizer's display (merged 9bb4e806c; contract: plan 01 M3c)

Up arrow: full display on the Visualizer's own display; diagonal up-left / up-right: on the display to its left or
right by physical arrangement (`core/display_neighbours.py`: a display counts as beside only if it does not
overlap horizontally, so a vertical stack offers no side arrows); only applicable arrows show; while expanded the
current display's glyph is a Down arrow and the diagonals move the view. The owner request stays "expand on
display N" (`expand_on_display`, the shape SMP will reuse).

- [ ] Two left/right rules: Edit's display-hop arrows (`QuickCustomLayoutOwner._adjacent_binding_for_identity`,
  `rendering/quick/custom_layout_owner.py`) compare centre x and offer a hop between two vertically stacked
  displays of different widths, where the glyphs offer none. Move Edit's hop onto `core.display_neighbours`.
- [ ] A display arrangement changing while the saver runs is covered only by re-admission in tests; check it on
  the topology-replacement path.
- [ ] The Reset Camera glyph (a font character) shows coloured edge fringes in off-screen crops; confirm on a
  real display and paint it as a path like the arrows if it does there too.
- [ ] Record the QML trap where QML authors will see it (there is no QML authoring guide; add a short section to
  `Docs/Guardrails/Presentation_Change_Preflight.md`): a property named `left` on a `Text` (colliding with
  Item's built-in `left`) hangs the hidden-scene load silently instead of raising.

### 1B.13 Hold right-click to pan the live Visualizer (merged 21da6fbc; contract: Spec.md / Contracts.md input)

Over a pan-capable card a right press arms a pending pan; travel past the drag distance pans (no menu for that
press); a still release opens the menu at the release point; every other right press opens on press as before.
Measured: press-to-menu on the untouched path 300-308 us before, 311-314 us after (run-to-run noise 300-426).

- [ ] Native pointer capture on a real foreground window is unproven (tests use a stand-in capture): add the
  pan to the opt-in native harness pattern of R-183 or verify with the operator's check above.

### 1B.14 Lead verification harnesses (operator, 11 Nov: "why can you not make tests that exercise these?")

The lead's lapse: these were filed as operator checks. They are testable: a frozen build through GitHub, the
real product run on Display 1 (the second monitor) for diagnostics, and real audio endpoints. **Permissions
(operator, 11 Nov):** bounded runs on Display 1 are permitted; Display 0 is never taken without permission;
builds run only through GitHub's workflows, never on this machine's resources. Lead-run only (agents build the
harnesses and prove them hidden; the lead runs the visible part); each visible run is short, bounded, fails
closed and always tears down. Queued for the next free Opus High slot.

- [ ] A CLI flag that tells the saver which display to use (operator: better than editing diagnostics settings),
  RUN-only like the existing `--exit-after <seconds>` self-exit flag, which bounds every run. One owner for the
  display choice; with the flag absent nothing changes; a Linux path or an explicit inert one.
- [ ] D1 run harness: start the real saver from source on Display 1 only (that flag), with diagnostic flags,
  recorded music and `--exit-after`, driven by messages posted to the saver's own windows (never global input);
  collect its logs, frame trace and grabbed frames; a watchdog ends it if the self-exit does not. A tool under
  `tools/`, opt-in, zero product cost.
- [ ] Cursor after exit (R-183) on D1 with `tools/cursor_exit_observer.py`: key, click, mouse-move, link click
  (browser launch stubbed), Settings and Media Center exits, the pointer placed over the saver on D1 for the
  run and put back after; a verdict per path. Then R-183 is accepted, or the failing path is fixed at the
  retire owner and re-run.
- [ ] Held-right pan on D1: real pointer capture on a foreground window (press, drag, release; a click still
  opens the menu on release; focus loss mid-pan releases the capture).
- [ ] Expanded Visualizer on D1: expand, collapse, the fullscreen arrows offered for the real arrangement, the
  move toward D1 from a hidden D0-side owner where that can be driven without showing anything on D0; frames
  grabbed and reviewed by the lead. What truly needs both displays visible is listed in the report, not assumed.
- [ ] Now Playing on D1: Fullscreen Edit handles and the seek bar against a real player session (fill follows
  the timeline, a seek lands).
- [ ] Settings and Studio windows on D1: corner drag and resize from each corner by messages (the alpha-1 corner
  pixels keep input); the Studio's corners captured natively; the theme list and autocomplete scrollbars
  captured (theme them through `shared_styles` if they are native bars there).
- [ ] Frozen build: `tools/github_remote_build.py` on the pushed commit (the lead's standing permission); from
  the artifact, the engine worker's import closure and the image worker's Qt dependencies; then the frozen
  product run on D1 with diagnostic flags: worker memory flat across a Settings round trip, the first Neon Lake
  activation logging a cold link or a cache hit and never an activation-failure reload, the second run a cache hit.
- [ ] Real audio endpoints: a test that opens real WASAPI loopback in the engine worker and drives the product's
  own device-change path with real endpoint ids: with two or more active render endpoints, a default-device
  change to the other endpoint (the notification delivered with its real id; no system setting changed) and
  capture resuming on it; with one, invalidate-and-reopen on the same endpoint; endpoint removal by its
  notification. In-process path too. Skips cleanly with a stated reason where the machine has no second endpoint.
- [ ] First reveal, worker against in process, without load on D1: the time from activation to the first drawn
  frame for each mode on both paths.

### 1B.15 Housekeeping the lead decided (11 Nov; engineering choices, not operator decisions)

- [ ] Preset rollback recovery copies: `core/visualizer_preset_tree.py` writes the before-images of a failed
  preset-replacement rollback to `tempfile.mkdtemp(prefix='srpss_preset_recovery_')` (`%TEMP%`, which Windows
  Storage Sense may empty). Move them under the data root beside the preset tree (one owner for the path, the
  folder named in the error as now, the newest few kept and older ones pruned on the next successful replace);
  the test keeps redirecting to `tmp_path`.
- [ ] Extruded Bubble evidence root: move `Docs/Reference/Extruded_Bubble/Evidence/2026-10-20/` (ignored media,
  referenced by `Investigation.md`) to `.artifacts/evidence/visualizers/extruded_bubble/20261020/` and repoint the
  references; nothing deleted.

## 1A. Miscellaneous repair slices (operator, 9 Nov)

These repairs run alongside the existing audit/native-worker work above; they do not replace or reorder it. Live
checklist: one box per open step. Each confirmed slice gets its own reviewed checkpoint; keep material changes
(1.7) in a separate checkpoint.

### 1.0 Rotate in ordinary and fullscreen Edit

Focused proof exists for renderer pixels at non-square extents, prepared Scene3D resources, per-mode Save/Cancel and
all Studio frame builders; the physical stage and camera remain fixed. Extruded Spectrum retains its frameless
overflow policy.

- [ ] Lead review of rendered frames (off-screen for ordinary Edit, D1 run of 1B.14 for fullscreen Edit): Rotate in
  every mode except Sphere, in ordinary and in fullscreen Edit.
- [ ] Lead review of zoomed glyph crops: the rectangle/quarter-turn glyph against Reset Camera.

### 1.0b Studio Rotate control

Off-screen proofs cover non-square production pixels, input transforms, preparation barriers and canonical saves.
Preview orientation is per-open state, separate from camera/artwork and desktop CUSTOM orientation; Copy Frame
captures it.

- [ ] Studio run (D1, 1B.14 harness), lead review of grabbed frames: Studio's Rotate control in every mode except
  Sphere.
- [ ] Same run: upright handle labels.
- [ ] Same run, drags posted by messages: rotated brush/drag feel (the drag lands where the pointer is).

### 1.1 Mode switch with no direct cause (Awaiting Logs)

- [ ] No direct mode-switch cause in the supplied archive. On recurrence, correlate the reported time, prior/result
  mode, selected preset and runtime generation with the existing mode-transition owner and frame trace.
- [ ] Distinguish explicit selection, enabled-mode normalization and Settings restoration first.

### 1.4-1.5 Remaining fullscreen visual acceptance

Existing Settings/input/text-layout/Edit checks are green; actual Windows full-layout acceptance is still owed.

- [ ] Fullscreen run on D1 (1B.14 harness), lead review of grabbed frames: Media Bar and Floating Glyphs styles.
- [ ] Same run: long metadata fitting.
- [ ] Same run: multiline Edit boxes and optional album, including Save/Cancel.

### 1.6 Achievement Pulse child placement

The enabled-row regression is green; other families' extent floors are static.

- [ ] D1 run (1B.14 harness) with `--geo`: check child placement after Settings/fullscreen return (replaying the
  saved payload on Edit entry must not change the canvas; disabled provider fields must not count as painted capsule
  rows).

### 1.7a Studio legibility follow-up

- [ ] Resolve the intended density once (the panel guard raises broad light surfaces nearly opaque to carry
  accent/focus marks).
- [ ] Minimally correct runtime semantic ink against its actual composed locations; retain authored/scene colours.
- [ ] Prove controls/traces on final off-screen wallpaper renders.

### 1.7 Material density (separate reversible slice)

Contracts and evidence: `Docs/Architecture/Card_Surface_Materials.md`,
`Docs/Architecture/Settings_Theme_Architecture.md`, `Docs/Reference/Visualizer_Studio.md`. Final native Settings
checks use both exact operator wallpapers under `C:\Users\Basjohn\Documents\[4] WALLPAPERS\PERSONALSET`; final
Studio renders are never-shown alpha compositions, without native DWM proof. Native rounded corners remain open at
1.9; material transmission is not a clipping fix.

- [ ] Lead review of side-by-side renders (the supplied widget material screenshots beside current cards, both
  operator wallpapers): especially the good Glass/Frosted volume surfaces, Glass inset/distortion, and Studio
  panels/tabs/headers/wells.
- [ ] D1 run (1B.14 harness), lead review of grabbed frames: exercise Settings Opacity Adjust and Widget Opacity
  Adjust in Style Overrides (-1..1, neutral 0).
- [ ] Studio run on D1 (1B.14 harness): live Studio material switching, snap and resize, driven by messages.
- [ ] The remaining unsampled control/delegate inks.
- [ ] Small isolated GPU checks show an active increase (largest raw whole-frame rise about 0.020 ms for Glass):
  that is not performance neutrality or load acceptance; the load measurement is §1 item 7 (card materials).

### 1.7b Material-aware widget border (near-term, independent material slice; 10 Nov)

Contract: `Docs/Architecture/Card_Surface_Materials.md` §3.2.1.

- [ ] Extend the existing shared card `MaterialSurface` shader's rounded SDF to shade the **border ring** using the
  same display-local blurred backdrop already sampled by the fill; never create a second capture/blur, extra
  material pass, timer or per-frame Python owner.
- [ ] A material-enabled card inherits its surface material for the border **by default**. In
  `Widgets -> General -> Style Overrides` add **Border Material:** Inherit Surface (default) / Flat / Acrylic /
  Glass / Frosted / Mica / Smoked (explicit overrides). An explicit different border material still samples the same
  shared backdrop and draws through the same card shader (ring-local parameters only; no independent material item).
- [ ] Add **Border Opacity Adjust** (-1..+1, persisted neutral 0), following the existing
  `core/settings/surface_opacity.py` adjustment semantics and save/flush path. Zero is exactly the authored
  material/theme baseline, not an always-on override; nonzero adjusts border density independently of `Widget
  Opacity Adjust` and the existing family border-opacity controls.
- [ ] Retain the authored theme border colour/contrast as the ring's tint/edge authority and border width/radius as
  its geometric authority.
- [ ] On Normal or Flat, retain today's Rectangle border **pixel-identically**; on active material, remove overdraw
  by that Rectangle only for the ring.
- [ ] The shader currently still has `plateInset = borderWidth + 2.5/3 px`, creating the contrasting interior rim
  the operator asked to eliminate; coordinate this same-pass geometry cleanup with the new border-ring treatment.
  Extend the existing material face to the inside of the real border, without changing content padding or
  inventing a separate plate system.
- [ ] Must remain clear against the fill, including on Glass and bright wallpapers; validate stroke AA, translucent
  corners, 100/150/200% DPR, normal/material switching, card opacity/theme inheritance and Style Overrides reset.
- [ ] One focused GPU before/after on busy cards.
- [ ] Include the existing framed Visualizer card if its surface is active, using its own border authority; material
  children/Context Menu do not inherit this automatically where their independent stroke semantics differ.
- [ ] Preserve older themes and settings via neutral defaults.
- [ ] Regenerate the bundled `.qsb` from the shader source using the existing Qt toolchain; do not ship uncompiled
  GLSL changes or assume every QRhi backend accepts an untested shader variant.

### 1.8 Gmail and Reddit/Reddit2 column gestures

Retained-QML proof covers transformed opposite-edge stability, all-row updates, collision policy, Save/Cancel, Undo,
slots and fresh-profile hydration.

- [ ] D1 run (1B.14 harness), gestures posted by messages: top grips reorder.
- [ ] Same run: solid-span endpoints change start/width and truncation.

### 1.9 Settings native corner clipping (next step is 1B.9: the operator's +2 px border allowance)

Reproducer and evidence: `tools/settings_native_corners.py`; `Docs/Architecture/Settings_Theme_Architecture.md`. Both
Qt and post-Accent native regions were rejected and reverted: all four native dark/light theme/background
combinations retain outside-radius material pixels at 150% DPI, on both operator wallpapers. An inset native-child
blur candidate was rejected by Windows before pixels; no candidate product edge/child code ships.

- [ ] Find a composition treatment that actually clips Accent material at the rounded silhouette: a viable rounded
  composition host, with input, resize/DPI, activation and lifetime proof (material transparency alone cannot
  close it).
- [ ] Keep it a separate reversible fix.
- [ ] Repeat the four-case corner/border/shadow gate before claiming improvement.

### Side defect: Build Runner's environment variables

- [ ] `tools/build_runner.py:3346` still reads `SRPSS_BUILD_RUNNER_DEBUG` (the Inno override is now `--iscc PATH`);
  replace it with a CLI argument.
- [ ] Two reds in `tests/test_github_remote_build.py`: `test_the_github_tab_offers_the_remote_products_and_local_
  steps` (an extra `linux_mc` job) and `test_the_linux_dispatch_sends_inputs_only_for_a_pinned_commit`
  (`scripts/linux/build_from_windows.ps1` no longer matches); not checked against the base commit.

### Awaiting Validation after the focused proofs

- [ ] Lead review of zoomed glyph crops (D1 grabbed frames): the changed glyphs.
- [ ] Frozen run (1B.14): saves in the frozen build.
- [ ] D1 run (1B.14 harness): camera/child placement round trips.
- [ ] D1 run (1B.14 harness), lead review of grabbed frames: long fullscreen metadata and controls.
- [ ] D1 run (1B.14 harness), native frames grabbed: material comparisons on native pixels.

## 2. Awaiting the operator (decisions only; details stay at the item)

One line each; the detail and evidence live in the section named. Nothing here holds a phase open, and nothing here
is an operator look: looks, listens and feels are the lead's proofs (1B.14), and what has no simple test is a
Watchlist entry (operator, 11 Nov).

- **Framed aperture on the saver card (8 Nov, decision):** the writer is fixed (R-181: the Visualizer's uniform-scale
  minimum is absolute, and settings load lifts stored cards to it). That alone does not restore the saver card's 45°
  look: the repaired 592x592 card holds a 1480x1480 world (0.4 px per world unit, aperture 5.29), still at the 90° x
  90° cap and visually the same as before (`.artifacts/evidence/architecture/framed_camera/20261108_scale_repair/`).
  45° on that card needs about 2.11 px per world unit (a 280-unit world). Decide: bound the framed aperture (or the
  vertical view) as well, or leave it to Edit (Restore Size, wheel up, side drag back to the wanted width).
- **§1 8b P2:** decide whether to size the frame-age gain with a matched-GPU repeat game60 pair; gates 3/4 and their
  measurement limits are in the design record. The Windows default and H1/H2 repairs are already integrated.
- **Decision, Waveform Preset 4 (the reference):** sign off the fixed-scale v7 trade-offs against main and the
  "floor first" lift (`TROUGH_LIFT_MAX` 1.5 -> 3: Preset 4's ribbon rides about .7 higher at p90 and stops dipping
  into the floor, operator: "rather it goes a bit higher when it has to than clips"), or ask for the tag's exact
  Preset 4 dynamics (numbers at 7.1, "Fixed-scale rework v7"; the lead accepted them on 6 Nov).
- **Decision, Waveform on a small 640x560 card:** Presets 5 and 6 cannot fit it either way: crests now graze the top
  on 14-47% of frames, against floor contact before (an authoring choice; no reaction was shrunk). Sign off, or ask
  for taller-body authoring.
- **Decision, expanded card's hover Edit lane (plan 01 M3c):** the lane (Restore Widget Size, the transfer arrows)
  stays withdrawn on the display-wide card outside Edit since M2, because each edits the ordinary card's layout,
  which that view does not draw (the rotate glyph is in Fullscreen Edit). Return it, and what should each do while
  expanded?
- **Decision, overlays on pause:** a pause does nothing to them (by the spec, not built): Now Playing is event-only
  and has already faded after its window; with Always Show it stays up by definition. Add a fade-out on pause?
- **Decision, Audio Analysis group in the Spline Curve and Oscilloscope Studios (section 9):** keep it or hide it?
  Every offered control moves the frame (Spline Curve's; Oscilloscope's Flare and Drive, and Tone for Bar Count, Block
  Size and Input Gain), though the Oscilloscope's trace itself is the raw capture.
- **Decision, Studio clip loops (section 9):** the clips now start and end mid-song at the chosen loop points (Human
  and Growing Pains on their groove) for a seamless wrap, not at the earlier quiet-to-hot windows. Keep the seam, or
  restore the quiet-to-hot arc?

- **Changed on 11 Nov (no action needed; say only if one should go back):**
  - Now Playing follows the Media widget's Edit rules: its side handles reflow the text box (they resized the
    artwork border, accepted 10 Nov); the block's orientation follows its anchor corner, set by the title's flip
    glyph or by ending a move in a corner (it flipped by screen side, accepted 10 Nov); a corner drag grows about
    the top centre and Restore Size keeps the top left; its artwork border takes the Media widget's artwork
    colour, stroke and Rounded Artwork option; the safe-area edge guides are not drawn.
  - Fullscreen glyphs: a single display shows the Up arrow (it showed up-right); tooltips are relative and
    ALL CAPS like the rest of the glyph row.
  - All three pans (Alt+right, held-right, the Studios) share the Studio's rule: a right drag moves the scene
    against the pointer, a down drag moves it with the pointer.
  - Studios: Waveform has Camera X and Z only (its camera fixes the eye height, so Camera Y never did anything);
    Extruded Bubble's Camera X/Y/Z span -2..2 (was -1..1); Sphere's View Turn / Tilt hold for the session and
    save through Save Camera.
  - Settings and Studio windows end at their rounded border: the near-white inner line on light themes is gone
    (it was backing showing through).
  - Neon Lake under music: the land no longer tears; the reaction is a little weaker on banks and very low
    land; paint past the old grid edge renders as far land (no shoreline line or wet fringe).
  - Brush Radius in the Neon Lake Studio is a share of the basin (its default is being rescaled).
- **Decisions the lead will put to the operator when their write-ups exist:** Neon Lake spire glow on hits;
  islands rising from the lake (needs the water-boundary contract decision).

## 3. Lead and agents: active, paused and queued work

**Agents (operator, 11 Nov; replaces the 11 Nov roster):** the lead (Fable) is orchestrator, auditor and final
reviewer; all agent results pass that review before acceptance, and the lead's audits (pixel review, regressions
re-run against the pre-change code, tests on the merge) are what keep the hand-overs sound. The other slots are
Opus 5.5: two Opus High (complex, architectural and visual work), two Opus Medium (simpler and brute-force
work), and one Sonnet 5.5 Medium for documents and research when needed. No Fable agents: the native-core
sequence (section 1 item 8b) and the material track (1B.8) run in these slots; presets (1B.10) alone go to one
Fable Medium agent (operator, 11 Nov: Opus does not handle preset visuals well). Agents run
only the tests related to what they changed, never `--isolated`, never take over a display (off-screen renders
and captures), and record side defects here instead of ignoring them. Wait for agent reports without status
polling. An interrupted agent's uncommitted work is preserved as a "WIP (handover)" commit on its branch and the
next agent merges that branch first.

Live checklist: every open step is its own box, ticked boxes are deleted, and a landed item leaves only its `[~]`
validation steps and open side defects. Landed slices live in `Docs/Reference/Architecture_Checklist.md` (AC-01
to AC-12, A-xx audit ids), `Docs/Audits/Settings_SSOT_Audit_2026-11-07.md` (AC-17 to AC-23),
`Docs/Reference/Benchmarks.md` ("Recorded sessions") and the Historical Bugs records.

- [ ] Post-close repaint remedy (1cd5d9c7, merged 7 Nov): open until a field log confirms (§9).

- [ ] **Learned levels still in other modes (lead audit, 7 Nov; operator: "Adaptivity is the enemy"):** move each to
  absolute audibility and fixed scales, mode by mode, with continuous-play evidence. The bus presence ratio
  (`musical_weight`, a 6 s running level) still gates:
  - [ ] Spline Curve (`devcurve_frame_runtime.py`); it also divides its body by a remembered peak
    (`devcurve_runtime.py`, 20 s memory, not opt-in), and its accents read a lane "above its own recent mean"
    (reactivity guide §13D, guide pass 8 Nov).
  - [ ] Extruded Bubble (`extruded_bubble_frame_runtime.py`).
  - [ ] Neon Lake (`logical_frame_capture.py`, `rendering/gl_programs/shockwave_grid_program.py`).
  - [ ] Oscilloscope.
  - [ ] Sphere.
  - [ ] `tools/labs/waveform_ribbon_recorded_input.py` still uses `musical_weight` and no longer matches production.
- [ ] **Vocal-band scorer into the music-response tool (8 Nov):** the PCM vocal-band (300-3400 Hz) series behind the
  mid-led routing evidence and guide §2C lives only in scratch (`lead_audit/vocal_band.py`); add it to
  `tools/visualizer_replay/waveform_music_response.py` as a lane so it survives scratch pruning.
- [ ] **Tool-output contract reds (found 8 Nov on `610e38c0`; the three listed there were fixed by `bed993a4`):**
  `tests/test_artifact_paths_contract.py`: route each through `tools/artifact_paths.py` and
  `tools/evidence_media.py`, or allowlist it there with its reason:
  - [ ] The further reds recorded at 1B.2 (literal `evidence_chest` paths, PNG writes, a `delete=False` temp file).
- [ ] **Side findings of the Waveform second tick cut (7 Nov, not fixed there):**
  - [ ] `capture_visualizer_logical_frame` refreezes the common style (`freeze_render_fields(_common_style(widget))`,
    logical_frame_capture.py) on every tick of every mode, ~0.02-0.04 ms; a FrozenFieldsMemo would remove it.
  - [ ] The logical-tick capture reads every Waveform control (~150 getattr) and compares the whole configuration
    dict every tick (~0.07 ms together); a settings-change token would make the no-change tick free.
  - [ ] overhead_baseline on main 4467759c counts gl 182 / py 7010 per Waveform preview frame against the 81959727
    baseline's 180 / 6987: an unattributed per-frame rise on main between those commits.
  - [ ] 11 of the 19 recordings in `logs/visualizer_recordings` lack native capture history, so the Waveform tick
    (PCM reanalysis) cannot replay them; identity proofs cover the other 8.
  - [ ] The Studio's step-state copy refuses NumPy dtype objects ("uncopyable Float64DType"); a dtype-keyed cache in
    a logical owner fails every Waveform Studio. Caught by `tests/test_waveform_studio_evaluator.py` and avoided in
    the cut (keyed by `dtype.str`); worth a line in the Studio's step-state contract.

**Active or paused (resume each with a message to the same agent, which keeps its context and worktree):**

- [ ] Repair the shared Achievement Pulse mock field IDs (`build_mock_steam_view_model`): it emits rarity/session,
  while the card accepts total/latest/playtime/previous/source/selected. Existing fixtures can test impossible rows.
- [ ] Isolate active Widget Theme state between scene/display tests: the combined 33-file run fails four tests that
  pass alone (Achievement Pulse config, Gmail actions, Media projection and baseline theme material).
- [ ] **D1 run (1B.14 harness), lead review of grabbed frames:** live Style Overrides/theme changes must reach
  Visualizer and Context Menu material in the current display generation (`_configure_quick_auxiliary`), including
  the new global opacity override.
- [ ] Extend actual faint-run pixel checks to light widget themes beyond the sampled Gmail/Media cards. Keep
  authoring-mirror failures separate from runtime material guards; contract:
  `Docs/Architecture/Card_Surface_Materials.md`.
- [ ] **Spectrum presets 2-15: re-authored by the lead (7 Nov); to be replaced under 1B.10 (operator, 11 Nov).** The
  features (flag sheets, hue-preserving gradients, rim glow cap, Bar Fill ghosts;
  `Docs/Reference/Visualizer_Reference.md`) stay; every preset carries Preset 1's reactivity unchanged (only look keys authored). Evidence:
  `.artifacts/evidence/visualizers/spectrum/presets/20261107_lead/` (contact sheets, motion strips, metrics, the
  authoring script) and `D:\Temp\Scratch\SRPSS\evidence\visualizers\spectrum\20261108_ghost_v2\` (`before/`,
  `after/`; falling instants beside Preset 1 with 2x ghost-top crops).
  - [ ] Lead review on contact sheets and motion strips (rendered): the re-authored presets (Silhouette is the
    plainest by concept).
  - [ ] Lead review on rendered falling instants beside Preset 1 (2x ghost-top crops) for the operator's 8 Nov
    verdict on v2: "Those ghosts are too solid and not blurred." The Bar Fill ghost must read like Preset 1's: soft,
    blurred, translucent (no crisp stripes or stars inside it), fading sooner, with no ~1 px dark seam where a
    transparent-border bar meets its ghost (merged as 092304dc; evidence `20261108_ghost_seam`). The same bar binds
    the replacement presets under 1B.10.
- [ ] **Waveform Ribbon, 7 Nov follow-ups** (evidence:
  `.artifacts/evidence/visualizers/waveform_ribbon/followups/20261107_followups/`; raw captures not kept; the Preset 4
  and 640x560 card sign-offs are decisions in section 2):
  - [ ] The game60 live check of the tick cut is owed on a quiet machine (see "Lead, the quiet machine").
- [ ] **AC-02 remainder:** what stays in `DisplayManager` until a second host needs it: the request and gesture
  routing that acts on the owner (mode/preset requests, view orbit, camera reset, Edit move/scale gestures,
  transfer glyphs) and the committed-CUSTOM profile resolver `_resolve_quick_visualizer_layout_profile`. Move any of
  these only when a second host needs them.
- [ ] **Settings round-trip memory growth (R-175; record `Docs/Historical_Bugs/R-175_*`):** the main cause is fixed;
  about 2.5-6 MB per round trip of unattributed native heap remains (against no-round-trip controls of the same
  build: Waveform +1.8 MB RSS a minute, Spectrum +0.3; round trips every 60 s still add ~2.5-4.5 MB RSS each on
  Waveform and ~3.5-6 on Spectrum; main ~19-20). Evidence:
  `.artifacts/evidence/memory/settings_roundtrip/20261107_settings_roundtrip/`.
  - [ ] Next: a heap-block histogram per reveal, or an offscreen render-control loop (the Studio saw 1-2 MB a
    session). The memory map puts the residual in the default native heap (+5-6 MB a round trip on both modes); it is
    not Python, retired wrappers, the Settings dialog (+0.1-0.25 MB each in isolation), the QML engine and its
    components, GL accounting, threads, handles or the driver's `private_other`. Left: the Quick window, its GL
    context and scene graph, and the Visualizer's GL programs per generation.
  - [ ] Gate 4 (8 Nov, 20 round trips, Spectrum P1): the same residual with the engine worker on and off (main
    +4.2 / +3.2 MB RSS, +7.0 / +6.1 MB private a trip); each trip also leaves ~1,700-1,800 tuples and as many
    weakrefs tracked (census, on and off), and the main process's pagefile-backed section views rose by 2 over the
    20 trips on both paths (106 -> 108 off). Attribute these.
  - [ ] The invisible Waveform live check grows with no round trips at all: +7.2 MB private a minute over a 600 s run
    (`wf_p4_no_roundtrip_fix`; ~3.8 MB a minute on the steady stretch between image steps; main
    `wf_p4_no_roundtrip_main`: +2.6 MB RSS a minute, branch +1.8). tracemalloc puts the Python share at ~1 MB a
    minute, mostly the harness's own per-frame lists (`tools/eb_live_phases.py` `_frames`, `_waveform_signals`,
    unbounded for the run) and the probe; the rest is native heap, unattributed. It bounds any round-trip slope from
    a 60 s schedule. Next: overnight, R-97 method.
  - [ ] The Spectrum P1 control (`sp_p1_no_roundtrip_fix`) kept RSS flat (+0.3 MB a minute) but private bytes jumped
    +476 MB at ~7 min, non-resident, and fell by 216 MB two minutes later: committed-not-touched memory, R-97/R-99
    territory.
  - [ ] One `QWidget` wrapper of every Settings dialog outlives it: the initial tab's placeholder
    (`ui/settings_dialog.py` `_build_tab_by_key`: `removeWidget` + `deleteLater`). Its C++ object is destroyed, no
    Python object refers to it, a full collection leaves it: shiboken keeps the wrapper. One small wrapper a trip.
  - [ ] The Settings dialog barrier's `destroyed` callbacks outlive it in the live run: tracemalloc shows 459
    `functools.partial` objects from `RuntimeDestructionBarrier.watch_qobject` (`engine/runtime_destruction.py:250`)
    added and kept every round trip (~36 KB; the dialog barrier watches 467 objects). Not reproduced with a bare
    dialog (298 watched, all released).
  - [ ] `QuickSceneFactory` is per display generation, not process-level as its docstring says, and its
    `QQmlComponent`s have no QObject parent: Python owns them, so they outlive their engine for as long as their
    wrappers do (until R-175's collection). Fix the docstring or the ownership.
- [ ] **GC freeze per generation (merged 7 Nov): the live check is owed (lead, quiet machine).** Evidence:
  `.artifacts/evidence/memory/gc_gen2/20261107_gc_gen2/` (`live_roundtrip_wf_p4_{main,pregc}/`).
  - [ ] Waveform P4 and Bubble, 600 s, game60, with `--frame-trace`, alternating main and branch; then
    `tools/frame_trace_report.py` for gen1/gen2 pauses per hour and the heap census at the reveal.
  - [ ] One long run with a few Settings round trips (`tools/visualizer_live_check.py --settings-roundtrip AT[,AT]`):
    a re-freeze after each reveal, no barrier timeouts, flat memory, and the `[GC_POLICY]` lines.
  - [ ] The live 64-152 ms spikes at Waveform preset switches are not yet attributed; the live trace will show
    whether they are collections.
- [ ] **Lead, the quiet machine, 7 Nov session (stopped early by the lead; evidence
  `.artifacts/evidence/performance/quiet_session/20261107_quiet_session/<task>/receipts.md`):** owed runs and the
  baselines they are judged against (overhead baseline `tools/baselines/overhead/2026-11-07_4bb2b775.json`):
  - [ ] M0 EB baseline (`2_m0_eb_baseline/`) gaps, never measured: GPU `TIME_ELAPSED` (the live check has none),
    p95/p99, lease/pool counts beyond the media leases, audio-to-photo freshness, and the unexplained two-monitor
    canonical game60 outlier (48.6 fps, never repeated). Reference: only the display-sized view moves; under game60
    its render mode is 8.2 ms against 4.4 at the card (over §0.7's 8 ms) and fps 64 against 73; tick (5.1 ms game60,
    2.7 idle) and GIL do not depend on size.
  - [ ] Waveform tick cut under game60 (`3_waveform_tick_cut/`): a second clean round (round 2 overlapped the lead's
    WebP job and is tainted). First clean round, main against `946e14b3^`: tick -5 to -10 %, fps +6-12 % on
    P1/P4/P7; indicative only, confounded by the other 193 commits. Waveform stays far over budget under game60
    (GIL >0.7, render 16-21 ms).
  - [ ] GC freeze steady check (`4_gc_freeze_steady/`): a clean Waveform P4 run (the run was tainted: no steady gen2,
    3 gen1 of 9-11 ms) and the long run with Settings round trips. Bubble P1, 600 s game60 was clean: no steady
    gen1/gen2, heap 180,685 frozen at reveal and 87 left.
  - [ ] Card materials (`5_card_materials/`): the alternated second Glass/Normal pair. First pair: Glass costs about
    +16 % of a core on the render thread (53.7 against 37.5), publish->swap +3 ms, hitches 2.46 against 2.05 a
    minute, at the same late %.

**Found while landing AC-01 (7 Nov; record, not yet admitted):**

- [ ] `tools/flicker_test.py`'s Widgets-tab `setup_ui_only_*` modes patch `widgets_tab_media.build_visualizers_ui`,
  which no longer exists anywhere (the Visualizer left the Widgets tab at V7), so those modes fail at `getattr`
  before measuring (its mode-body stub now targets `spec_mode_builder.build_mode_body`).
- [ ] SMP import scan vs the registry: `ui/settings_tabs.py` imports the existing tabs' modules at import time. The
  SMP plan's §14 bar ("no saver module is imported by opening Settings in the SMP profile") needs those imports
  moved into the builders when the SMP descriptor lands.
- [ ] Gate note: `tests/test_release_media.py::test_source_change_during_capture_discards_media` fails in any agent
  worktree (and in a fresh one on main) because the operator's Usu scene originals (`assets/usu/scenes/UsuScene*.png`)
  are untracked and exist only in the main checkout; environmental, not a product defect.

**Found while landing AC-03 (7 Nov; record, not yet admitted):**

- [ ] Production never calls `engine_lifecycle.cleanup`: the terminal path is `stop(exit_app=True)` and its barrier
  finalization (and the post-loop `finalize_after_event_loop` backstop); `cleanup()` is reached only by tests. AC-03
  retires the tier on both paths (idempotent); a change to one terminal path must check the other.

**Found while centralizing tool output (7 Nov; record, not yet admitted):**

- [ ] Hidden cross-test dependency on an earlier test's `tmp_path` (lead, 7 Nov): with pytest's
  `tmp_path_retention_policy = failed`, `test_3d_curated_preset_ownership.py::...promotes_missing_owned_temporal_
  and_profile_keys...[shockwave_grid]` (0.7 vs 0.23) and two or three `test_settings_dialog.py` tab-restore tests
  fail; each passes with the default retention, so something process-scoped keeps a path into an earlier test's
  `tmp_path` (a cached preset tree or storage root). The setting was reverted. Find the cache and give each test its
  own root; this may also hide state leaking between tests.
- [ ] Dead evidence references (the folders no longer exist; `tools/artifact_migration.py refs` lists them):
  `logs/evidence_chest/08_*` in Historical_Bugs R-53/56/57/58/59/60/62, `.artifacts/evidence/{ribbon_path,
  ribbon_frames,ribbon_strip,expanded_visualizer,oscilloscope}` and several `waveform_ribbon/wr*` folders in
  `Docs/Reference/Ribbon_Path.md`, `Waveform_Ribbon_Lab_Plan.md` and
  `Waveform_Ribbon_Mist_Failure_and_Replacement.md`. Left unchanged; prune or mark historical on review.

**Side defects (Studio stall / clip selection fix, 7 Nov):**

- [ ] Bubble, Sphere and Extruded Bubble replay a change in one GUI-thread evaluation (no frame budget). While
  playing, the pass restarts, so the replay is short. Paused, an edit 6 s into Human still costs one evaluation of
  about 1.5 s (Bubble), 0.3 s (Sphere) or 0.2 s (Extruded Bubble), measured 7 Nov without load. Give them the frame
  budget (`ExactReplay`) or accept the cost.
- [ ] A restart still replays the clip's 2 s analysis lead-in (`clip_loop.PREROLL_S`) under the 8 ms budget. That
  holds the preview for about 0.7 s (Waveform) or 1 s (DevCurve), shown as "Updating...". A larger budget for that
  one replay would shorten it.
- [ ] `tests/test_visualizer_control_hints.py::test_lazy_visualizer_root_retains_initial_hint_capability` still
  builds a `QuickDisplayWindow` (it is never shown), which the probe rule forbids. Move it to the render-control
  pattern.
- [ ] `tests/test_studio_exit_every_mode.py` still calls `shiboken6.delete(...)`. The plain-orbit file's two calls
  left Qt Quick's pointer state dangling, and the next Quick window's mouse event in the same process crashed (the
  control-hints access violation). Check whether this call is safe.

**Found while building Expanded Visualizer M2 (7 Nov; recorded, not yet admitted):**

- [ ] Extruded Bubble drift family revisions are process-global (`extruded_bubble_drift_log._REVISIONS`): two
  identical replays in one process publish different labels, so in-process digest comparisons of EB (and the
  Studio's packet-hash proofs, if they ever replay EB twice in one process) differ for no behavioural reason. The M2
  harness numbers each replay from 1 (`fresh_drift_revisions`). A per-runtime counter would remove the trap.
- [ ] A takeover fade completes on the publication edge only: like the activation fade it has no deadline, so with no
  logical publication (displays off, parked) an expand or collapse in flight waits and finishes when publications
  resume; the coordinator meanwhile refuses mode requests and transfers as busy. Watch for it at M5 (display power).
- [ ] Lead review of a rendered expanded-card frame (hidden host, then D1 grab): the expanded card shows the theme's
  surface material (the Visualizer card's `visualizerCardSurfaceMaterial` exists since 0b4abe04, so it is no longer
  a plain rectangle).

**Found while building Expanded Visualizer M3 (7 Nov night; recorded, not yet admitted):**

- [ ] An ordinary root's initial fade runs its family's own fade from QML's default: the host writes `fadeOpacity`
  before parenting (`OrdinaryWidgetPresentationHost._adopt_item`), but a family `Behavior on fadeOpacity` (the
  OSD's, 1150 ms) is already live, so the root animates 1 -> 0 instead of starting at 0, and a
  `set_fade_opacity(1.0)` in the same turn reads the not-yet-ticked 1.0 and is skipped
  (`RetainedOverlayWidget.set_fade_opacity` compares first), so that reveal is lost. Harmless today (the startup
  gate is closed while generations build, and a real OSD reveal arrives later), but a mid-generation root with an
  authored fade would show a brief fade-out. The M3 test waits it out. Fix at the host (project the initial fade
  with the Behavior bypassed) when admitted.
- [ ] The overhead baseline cannot see the QML scene: `tools/overhead_baseline.py` renders render nodes on a bare
  host, never `DisplayScene.qml`, so scene-level dormancy (M3's cover) is proven by the QObject census and the
  no-per-frame-work structure instead.

**Found while building Expanded Visualizer M3b (8 Nov; recorded, not yet admitted):**

- [ ] A Card on a material shows the wallpaper, not the Visualizer: the shared backdrop is the wallpaper layer only
  (`Docs/Architecture/Card_Surface_Materials.md` §3), so on Glass over an opaque mode (Extruded Bubble) the card is a
  blurred wallpaper the Visualizer hides everywhere else. It reads as a tinted panel (evidence still
  `extruded_bubble_06_card_glass.png`). Lead review on rendered stills (Glass over Extruded Bubble, then other
  modes): whether that is acceptable.
- [ ] Right-hand corners sit further in than left ones: they keep clear of the card's hover-revealed controls (about
  80 px from the top edge for the collapse glyph, its tip and the 3D hint; the bottom for Reset Camera, the preset
  steps and their tip). Fullscreen Edit (M3c) can move an overlay. Lead review on rendered expanded-card frames:
  revisit if the gap reads odd.
- [ ] Now Playing needs an admitted Media card somewhere: it reads the Media model the Visualizer already binds; with
  Media off on every display there is no source and nothing shows (by design: no second Media source).
- [ ] The hidden render host never waits for the GPU: `tools/expanded_visualizer_evidence.HiddenDisplayHost.render`
  queues unthrottled frames, so the next texture upload (a glyph, a layer) waits for the whole queue (40-390 ms
  measured on the M3b scene) and time-based QML animations jump past what a test samples. The M3b tests finish each
  frame (`glFinish`); other users sampling animations should too, or the host could finish its frames itself.
- [ ] The bright-area text switch is not built (see §1 item 3).

**Found while building Expanded Visualizer M3c (8 Nov; recorded, not yet admitted):**

- [ ] `tests/test_visualizer_preset_glyphs.py` opens a real window (offscreen QPA hangs it), so the glyph-row agent
  could not run its updated assertion (Edit's glyphs match the card's 26 px). Port it to the hidden production host
  (QQuickRenderControl, as `tests/test_visualizer_glyph_row.py` does) and run it.
- [ ] `tests/test_qtquick_context_menu.py` fails after `tests/test_qtquick_custom_layout_owner.py` in one process
  (the 1B.1 side defect); the same pairing also turns three `tests/test_visualizer_direct_gestures.py` tests red
  (Alt-wheel / Alt-drag gestures never begin; reproduced on e9bbd7a4 without the M3c single-axis/rotate changes,
  8 Nov), so it is the same leak.
- [ ] The overlays' Edit placeholders are fixed English words ("Preset Name", "Track Title", "Artist"), shown only in
  Fullscreen Edit when there is nothing to show yet.

**Lead only:** merges and merge gates; the game60 live checks (card surfaces with materials on; Waveform after the
tick cut); scheduling heavy load generators; promoting checklist items here.

## 4. Runtime side requests (operator, 5 Nov; run alongside the order above)

Live checklist: every open step is its own box, ticked boxes are deleted, and a landed item leaves only its `[~]`
validation steps and open side defects.

**Slow startup (operator, 6 Nov 10:30; owners fixed, awaiting the lead's cold start)**

Evidence `.artifacts/evidence/lifecycle/slow_startup/20261106_slow_startup/`; the held-lock rule is in
`Docs/Guardrails/Performance_Optimization_Contract.md` section 5, the optional-worker start in its appendix.

- [ ] D1 run (1B.14 harness): cold start with `--usage`, then the lead reads the log:
  - [ ] No `UI_CALLBACK` / `FEED_GUI_DELIVERY` line exceeds a frame. The 166-240 ms `FEED_GUI_DELIVERY` lines at
    10:30:40-42 were not reproduced offline (Feeds cache delivery including the NEWS card model is 0.1-15 ms per
    source at 18 publishers x 40 stories; `_complete` excludes QML) and are treated as the post-block backlog on a
    97-100% CPU machine.
  - [ ] The first `collect_ms` is small.
- [ ] Side defect: a prefetch batch asked for before the optional image_prefetch child is ready fails as "not
  running" (a logged `[PREFETCH]` error); that batch is not retried.

**Spline Curve (`devcurve`) "more alive while keeping the flow" (second cut 6 Nov; awaiting lead review)**

Contract: guide section 13D -> DevCurve. Evidence and before/after WebPs (loud end and a quiet passage, P1/P6):
`.artifacts/evidence/visualizers/devcurve/reactivity/20261105_reactivity/` (`PROGRESS.md`).

- [ ] Lead review of the second cut.
- [ ] Lead review on the rendered before/after WebPs (loud end and a quiet passage, P1/P6): the second cut reads
  more alive while keeping the flow.
- [ ] Open: the strongest preset's bass (Deep Blue) stays ~18% below pre-work main's loud RMS (a smooth wave cannot
  match a slope-limited triangle at the same slope).
- [ ] Open: the quiet-passage evidence is one recording's cold start (9 kicks).
- [ ] Open: a capped layer shows the swell less (it lives inside the body's share).

**Waveform logical tick starves the render thread under game load (quiet-machine game60, 6 Nov)**

This is the Graphics Backend Decision's "optimise the logical tick first" step before trigger 2 can be judged.
Evidence `.artifacts/evidence/performance/live_check/20261106_quiet/`. Baseline to beat (main, game60): Waveform
P1/P4 tick median 8.5/8.3 ms (p90 14.4/14.0), GIL held 73-75%, render-mode 16-17 ms, 41-44 fps; same session
P1/P4/P7 43.5/42.7/37.6 fps, tick 8.5-8.7 ms (p90 14-16), GIL 0.75, P7 64% late frames; under the same load Neon
Lake runs 89 fps, Spectrum 90, Bubble 63, Extruded Bubble 5.9 ms / GIL 0.53 / 55 fps.

- [ ] Profile the LIVE logical tick (offline the Waveform dynamics are ~1.3 ms and the whole tick replays in ~1.5 ms;
  the live cost is elsewhere: capture, packet build, field/strand/spark work). Offline ticks above ~16 ms are gen2
  GC (86-161 ms, about one per 5,500 ticks), not Waveform work.
- [ ] Record the logical thread's own CPU time (`time.thread_time`) beside the tick's wall time in the live check,
  so the wait share is a number. One invisible no-load P4 run (120 s, other processes' CPU 26%) measured a 7.49 ms
  tick median (duty/GIL share 0.67, 51.7 fps, render-mode 10.9 ms); about 6 ms of each live tick is spent waiting,
  most likely for the GIL held by the render/GUI threads' Python (each wait can last a 5 ms switch interval).
  Switch-interval tuning stays banned by the Performance Optimization Contract.
  Evidence `.artifacts/evidence/visualizers/waveform_ribbon/live_check/20261107_tick_cut2_p4_noload/` (main checkout).
- [ ] Cut what the profile names, with byte-identical output (Preset 4 bit-exact with tag
  `waveform-baseline-2026-11-05`).
- [ ] Live re-measure of Waveform after the two merged tick cuts (lead only, game60 after the operator's yes card).

**Frozen builds could not open a Studio (operator 6 Nov: "module QtQuick.Controls.Basic is not installed"); fixed
in source, confirm on the next build**

Contract: `Spec.md` (frozen QML package contract); `test_every_shipped_qml_import_survives_the_frozen_prune`.

- [ ] Frozen run (1B.14): open a Studio from the fresh frozen build (the GitHub Remote artifact), on D1.

**Widget/Settings material appearance: Awaiting Validation**

Active density/composition work and native evidence: section 1A, items 1.7/1.9. Durable owners:
`Docs/Architecture/Card_Surface_Materials.md` and `Docs/Architecture/Settings_Theme_Architecture.md`.

- [ ] D1 run (1B.14 harness), lead review of grabbed frames, in the running app:
  - [ ] The inner rim.
  - [ ] Transport, mute and volume.
  - [ ] Dark and light palettes.
  - [ ] Linked material choice.

**Widget theme legibility (open)**

- [ ] Theme the Weather detail asset icons: they remain white and become faint on pale cards.
- [ ] Re-author raw linked Widget Theme roles that fail `tools/theme_legibility.py`, especially widget.accent on
  widget.panel/header surfaces; do not equate runtime ink correction with a corrected raw mirror export.
- [ ] Fix light-theme widget shadows, then inspect actual faint text over the resulting cards; analytic panel
  contrast alone does not account for the shadow's effect.

**Extruded Bubble: a deep red ocean preset that truly matches the mock (operator 6 Nov, not urgent); second pass
done, awaiting the lead's review**

The mock is `Docs/Reference/Extruded_Bubble/Targets/Originals/Preset7Goal.png`. Preset 9 (Deep Red Ocean) only;
Presets 1-8 stay pixel-identical. Shared controls, each dormant at 0: Ember Grain, Ember Band (Water), Lit Glass
(Glass), Stream Lanes, Wake Tint (Bubbles), Hero Shell with Hero Across/Height (Lens). Details, numbers,
reactivity and cost: `Docs/Reference/Extruded_Bubble/Investigation.md` sections 72-73; evidence
`.artifacts/evidence/visualizers/extruded_bubble/deep_red_ocean_pass2/20261106_deep_red_ocean_pass2/`.

- [ ] Lead review of side-by-side sheets (mock | ours, full resolution plus crops) of Preset 9 against the mock.
- [ ] Shells are paler and smoother inside than the mock's copper, busy-interior glass, and too many crowd together.
- [ ] Embers are partly along-stream strokes rather than torn debris.
- [ ] The lower right is far too busy (the mock's band fades out there).
- [ ] The shaft corner lacks its bright glittering core.
- [ ] The Hero Shell reads as a soft ring rather than a shell full of bokeh discs.
- [ ] Faint surface ripples at the top.
- [ ] Side defect: the near (defocus) layer stair-steps the rim of a large near shell on some frames (seen with Lit
  Glass off as well).
- [ ] Side defect: `tools/release_media.py` cannot render Waveform Ribbon showcases: the replay raises "Raw musical
  replay requires current PCM reanalysis" because `replay_clip` never drives
  `tools/visualizer_replay/pcm_reanalysis.py`.

## 5. Watchlist (observe during normal use; reopen only on evidence)

Live checklist: every box is an observation or a fix owed on evidence; delete an item when its evidence closes it.

**Engine worker and platform (reopen only on evidence; no simple test exists)**

- [ ] First-reveal latency under load: if the Visualizer's first appearance is noticeably later on the worker
  than it was in process, size it in a load session (the no-load comparison is 1B.14's).
- [ ] A hot-plugged audio device: nothing in use is hot-plugged until SMP/Library exists; the real-endpoint
  reopen test of 1B.14 covers the capture path. Revisit with SMP.
- [ ] Linux engine worker (best effort, never run): the named wake pipe (FIFO), the worker's spawn under
  forkserver, the shared mapping's tracker, Pulse capture in the worker, the listener thread ending when the
  worker's writer closes, and a broken worker showing as a logged in-process fallback. `--viz-in-process` is
  the escape if a Linux user reports the Visualizer missing.

**Neon Lake (`shockwave_grid`) camera step on real music (found 6 Nov, pass 7, pre-existing at 0776da08)**

Preset 1 on 1985_loud1 between 42.054 s and 42.075 s: the whole land shifts ~8 px down in one frame and stays (mean
step 8.5/255 against ~1.3; replay parameters and presentation identical across the two frames, Terrain Reaction
bands smooth).

- [ ] Find the owner (camera floor / reaction normalisation) with `tools/neon_lake_capture.py --clip ... --start 41.9
  --duration 0.3 --fps 90 --all-frames`.

**Neon render tests load-sensitive under parallel runs (5-6 Nov)**

`test_neon_lake_renderer.py` (once, pass-5 merge gate) and `test_neon_scene_materials.py` (once, pass-5 branch) failed
under parallel load and passed alone; the re-run overwrote each log, so the failing test is unknown (most likely a QSG
clip probe timing out).

- [ ] Next time it fails, read `logs/pytest_isolated/<file>.under_load.log` (the isolated runner now keeps the
  parallel-run failure) and fix the probe's timeout or synchronisation rather than rerunning.

**4x MSAA repeat-render noise (driver, 5 Nov)**

Mechanism and the shared comparison helper `tests/_msaa_render_noise.py`: `Docs/TestSuite.md` ("4x MSAA repeat-render
noise").

- [ ] Reopen if a driver update or another GPU shows the noise gone or larger.

**Display Settings capacity (physical hotplug)**

- [ ] On a real monitor disconnect/return or explicit reauthoring, Settings' current-screen rows and
  selections/bindings stay coherent (focused checks pass; hidden form evidence
  `tmp/pytest_ux30_display/test_display_ui_rows_follow_to0/six_display_rows.png`).

**R38 hover display-transfer glyphs (physical topology)**

- [ ] Watch glyph hit/tooltip/fade and transfer on unequal-DPI screens and monitor unplug/return (equal-DPR pair
  passes; `tmp/ux30_actual_displays/receipt.json`).

**Steam Games You Follow images**

Many update entries lack images. A generic game cover existing is not proof an image is missing.

- [ ] On a report of missing images: audit URLs, redirects/statuses, cache keys, game IDs, fallbacks, dedupe and
  selection order (including artwork fetched but rejected downstream).
- [ ] Then prefer image-bearing updates without suppressing legitimate no-image entries.
- [ ] Instrument attrition and compare natively with Feeds (the lead's own comparison; no operator step).

**Steam artwork 404**

- [ ] Asset hash `9b4a68b51c5f` (23 Oct MC run, `logs/run_matrix/2026-10-23_idle_hint_shaft/`) and earlier
  `4b349d51e996` / `3f5b734df3c5`: decide stale metadata vs genuinely missing CDN asset before changing lookup.

**Monitor power/wake**

- [ ] Exercise: display off, > 30 s off, rapid off/on, reordered return, both selected displays absent; widgets keep
  physical assignments and CUSTOM geometry.
- [ ] On recurrence record timestamps, remaining screen, flavour, Interaction Mode and wake/exit input (history:
  R-79).

**Refresh contention**

- [ ] Correlate FEEDS/Gmail/Reddit queue/claim/publish/retire with transition delays in a natural dual-display trace
  (fairness, no post-transition stampede, retained last-good content).

**15 s usage-sample hitch (unexplained, not reproduced)**

31 Oct 19:28-19:33 MC run: a 95-121 ms freeze of the GUI, render and logical threads at every `--usage` sample (20 in
5 min, `gui_stall_stacks.log` and frame trace agree). Each sample took ~95 ms because the sampled tree held 7
processes / 233 threads (normal 3 / ~55, ~16-24 ms); the four extra descendants used the GPU (counters 17 -> 70),
existed from the first sample and are unidentified. The next MC run (19:47) and an invisible live check on current
code were normal. Not the Extruded Bubble chain fix (no processes, tick unchanged).

- [ ] On recurrence read the sampler's `[USAGE] topology added ... name= parent= threads=` lines (one per process
  entering the tree), identify the extra processes, then decide whether the sampler must exclude/outsource them.
- [ ] Seen again 8 Nov with a normal tree (P2 gate 3's game60 pair, design doc step 6 "Gate 3 record"): every sample
  in both runs stalled the render thread 71-106 ms in the scene render (13 of the worker path's 23 hitches, 14 of in
  process's 39); `collect_ms` ~13 ms per process walked at 87% system CPU (58 ms for 4-5 processes with the engine
  worker, 46 ms for 3-4 in process; 23 ms for 4 on an idle machine). Main-side on both paths; the engine worker adds
  one process to the walk.

**Cross-display Media shortcuts**

- [ ] Delivered once on the other display, when exercised.

**Music recorder**

- [ ] 60-second clip, signal/history, cancel and mixed-DPR UI, when recording is needed.

**Helper breadcrumb diagnostics unavailable**

Current native MC evidence logs no access to `C:\ProgramData\SRPSS\logs\scr_helper.log`. Separate from Waveform
rendering.

- [ ] Inspect the helper/log-path authority before relying on that diagnostic route; do not hide it behind a silent
  local fallback.

**GitHub Remote builds (8 Nov, proven end to end; moved from section 2)**

Build Runner's third tab and `tools/github_remote_build.py` compile Standard/Media Center on GitHub runners, validate
and publish them, and compile opted-in installers locally (`Docs/Guides/GitHub_Remote_Build.md`). Lead's headless run
from the Build Runner CLI on e9bbd7a4: both remote builds downloaded, validated (manifest + PE version) and
published, and both installers compiled locally (`release/installers/Setup_SRPSS.exe`,
`Setup_SRPSS_Media_Center.exe`). The run before it showed the installer gate refusing a Standard installer whose
presets had changed after the remote build. Installing a remote-built product on an ordinary user account is the
"Installed builds" entry below; the frozen run of 1B.14 covers the artifact.

- [ ] Since checkpoint audit 11 (8 Nov) the tab's Linux job runs beside the Windows runs on its own process owner
  (never holding their retrieval) and a stop cancels its run even before it was followed; tested with fakes only, so
  the next Remote run with Linux selected is its first real one: read its log and fix what it shows.

**Bubble / Extruded Bubble "terrible performance" reports (6 Nov log 10:32-10:35; moved from section 2)**

That log was our load (97-100% system CPU from the agents' game60 checks), not the product: on the quiet machine
Bubble P1 ran 65.9 fps, tick 1.47 ms, GIL 0.13, 3.9% late; Extruded Bubble 45-69 fps
(`.artifacts/evidence/performance/live_check/20261106_live/`). Heavy load-generator runs are scheduled by the lead
only.

- [ ] On a new report, read the log's system CPU first: a load-driven reading is not a product defect; otherwise
  reproduce on the quiet machine against those numbers.

**Displays off -> presentation pauses entirely, resumes clean (built 5 Nov; needs the machine's own screen timeout)**

Contract: `Docs/Architecture/Compositor_Architecture.md` -> Display power (hardware findings 6 Nov are recorded
there). Evidence `.artifacts/evidence/display/display_power/20261105_display_power/`.

- [ ] When a heavy preset (Waveform Ribbon (`waveform_ribbon`) Preset 1 or Neon Lake (`shockwave_grid`)) is left
  overnight and Windows' screen timeout turns both displays off (not the panels' own buttons: an HDMI panel that
  stays enumerated gives no signal and the TV rejects DDC/CI queries; operator decision 6 Nov: no Screens Off
  command, the burden stays off the user; they enabled the power plan's display timeout), notice the saver's CPU/GPU
  in Task Manager while dark, whether wake input reaches the saver, and the first seconds after wake (a stale frame,
  a jump or a hitch). Run with `--frame-trace --usage`; when something shows, read that trace and reopen here.

**Card materials under load**

- [ ] A transition-heavy material/Normal pair needs the separately approved measurement session (load is the
  operator's to approve; small off-screen GPU timings do not replace it). When a session is approved, the lead runs
  it with item 7's card-materials pair.

**Installed builds as an ordinary Windows user (no such account or fresh install exists to test on; moved from 1.2-1.3)**

Durable behaviour: `Docs/Reference/Visualizer_Studio.md`; evidence:
`Docs/Audits/Studio_Camera_And_Fullscreen_Overlay_Self_Audit_2026-11-09.md` and
`Docs/Historical_Bugs/R-182_Installed_Preset_Files_Lacked_User_Modify_Permission.md`. Source-level file/Qt checks do
not establish installed ACLs; the frozen run of 1B.14 covers the artifact, not an installed ProgramData tree.

- [ ] On a freshly installed Standard or MC build as an ordinary Windows user (when one is available): the
  installer grants Modify on the shared ProgramData Visualizer preset tree **and its existing files**; Save and Save
  Camera over a shipped preset work; Save As and reopen work; Save As New Preset's file dialog lands in the right
  folder in an installed build (ProgramData's shared preset tree). If one fails, fix the installer's ACL grant
  (R-182).

**Frozen release gate (operator scheduled)**

- [ ] Standard/Diagnostic from one compile.
- [ ] MC and Reddit Helper installed startup/exit.
- [ ] Settings/widgets/cache/audio and installer behaviour.
- [ ] Installer logs and obsolete-file removal in both curated theme/preset trees. Both sources declare whole-tree
  replacement; verify Diagnostic now reads that installed theme tree too.

**Conditional evidence only**

- [ ] Original Bubble tiny-radius judder (R-105) needs a new reproduction.
- [ ] Dual-display reboot recovery (R-134–R-145) needs a new reproduction.
- [ ] The 90 Hz versus 60 Hz investigation stays off limits.

## 6. Shared 3D architecture (one step, before the next mode; after Expanded Visualizer, under port-readiness rules)

The architecture planned for the dropped concepts (volumetric music chamber, audio aurora/ribbon volume, photo
fracture portal, voxel morph field, holographic depth slices, procedural storm, reactive particle field,
terrain/skyline/tunnel, deformable blob sphere) is worth having; the modes were not. Build shared primitives on the
existing Scene3D substrate (`Docs/Reference/Scene3D_Resources.md`): `MeshResources`, `SceneTarget`, depth-aware OIT,
probe, defocus, HDR intermediate, framed camera. Order follows which mode needs them first.

Rules for every slice below:

- [ ] Read the 3D foundation lessons in `Docs/Reference/Transitions.md` before each slice.
- [ ] Prove each primitive on its own offscreen harness with bounded, measured cost (TIME_ELAPSED, median/p90), lazy
  creation, zero dormant work and clean retirement.
- [ ] None waits for a consumer, and none becomes a second renderer, clock or camera.

**S3D-1 Ribbon / strip primitive** (consumers: Waveform Ribbon; trails anywhere)

- [ ] Finish the reusable camera-facing width variant.
- [ ] Shared defocus integration.
- [ ] Lifecycle/admission proof and bounded cost around the existing history/ring/oriented-strip substrate.
- [ ] Preserve a bounded history SSBO, centripetal Catmull-Rom placement by continuous index, OIT translucency,
  multi-ribbon support and fixed maximum history.

**S3D-2 Particle population extensions (G4)** (consumers: ribbon sparks, rain droplets/crowns, melt droplets)

- [ ] Inventory the existing compacted-population/sprite/streak helpers first.
- [ ] Add bounded lifetimes, emitters, transient bursts and indirect draws.
- [ ] Add compute-driven arrangement (morphing a fixed population between shapes, from the voxel morph concept).
- [ ] Deterministic admission/retirement.

**S3D-3 Static scene geometry and materials** (consumers: Melt Pool chamber, Concrete Rain street)

- [ ] Authored static meshes (slabs, curbs, walls, recesses, wells, simple skyline/tunnel slices) with their own
  roughness/bevel/contact shading, built once and retained.
- [ ] Photo-textured shells/planes with real depth (from the fracture portal and depth-slice concepts).

**S3D-4 Dynamic surface field** (consumers: Melt Pool body, Concrete Rain ripples/puddles)

- [ ] A bounded GPU height+velocity grid (compute or ping-pong) with impulse injection and damping/return.
- [ ] A displaced mesh with normals from the actual surface.
- [ ] An opt-in deformable sheet for shapes a heightfield cannot make (from the deformable blob sphere concept).

**S3D-5 Reflections and wet surfaces** (consumers: Waveform Ribbon floor (next: section 7.1), Melt Pool, Concrete
Rain)

- [ ] A bounded planar/probe reflection for floors and pools.
- [ ] Wet-surface and puddle masks over authored ground.
- [ ] Reflection-distortion sampling driven by a surface field.
- [ ] No screen-space trick that collapses under camera motion.

**S3D-6 Shared shadows (G2 / S25)**

Also Usu's S25; not a revival of the rejected Extruded cast shadows.

- [ ] One fitted directional depth map with bounded soft PCF/bias.
- [ ] Caster/receiver admission, resize/teardown/dormancy.
- [ ] Tier cost on a real test scene.

**S3D-7 Reduced-resolution volumes, then lightning (G5)** (consumers: chamber/street atmosphere)

- [ ] Prove the bounded static fog slice required by Waveform Ribbon first, with no audio reactivity.
- [ ] Then bounded procedural bolt geometry/light and fog/smoke volumes with advection/reprojection and no permanent
  extra targets or separate cadence.

## 7. Visualizer modes (one at a time, in this order)

### 7.0 Method: lab first, then production

Extruded Bubble's lab (`tools/labs/extruded_bubble_lab.py`) reached the mocks long before production did; production
then closed the gap by measuring against both. Do the same for every new mode:

- [ ] **Target first:** the mock/concept package and its low/high pair; write the mode's contract and hard gates (from
  its brief) into its focused doc before code.
- [ ] **Lab:** `tools/labs/<mode>_lab.py` composes the target scene by hand, offscreen, from the shared primitives,
  with free knobs and no Settings/preset plumbing.
  - [ ] Reuse the context/target and ownership contract in `Docs/Guides/Visualizer_Labs.md`.
  - [ ] Iterate on rendered stills (mock | lab sheets) until it is close.
- [ ] **Production through the shared substrate:** typed Settings, presets, the logical clock and lifecycle.
  - [ ] Diff the lab's effective knobs against production's key by key.
  - [ ] Judge with **mock | lab | ours** sheets per preset, the per-mode capture tool (`tools/<mode>_capture.py` on
    recorded real music) and measurements (regional colour, on-screen size bands, Range audits), as in
    `Docs/Guides/Visualizer_Visual_Tuning.md`.
- [ ] **The lab is a waypoint, not the goal:** keep going toward the mock; keep the lab (it costs the product nothing).
- [ ] **Same-scene low/high proof, measured cost, dormancy and retirement** before calling any stage done, including
  the live-shape check under the calibrated game load (`tools/visualizer_live_check.py --load game60`, budgets in
  `Docs/Guides/Visualizer_Change_Checklist.md` 1C); the operator gives final sign-off.

### 7.1 Waveform Ribbon (next)

This is the single live list of reported failures, proposed corrections and required evidence (Awaiting native
validation/operator judgement, 2 Nov; updated 3 Nov). Tests establish mechanisms, not visual acceptance. Work first on
body/audio/accents, then grounded camera/viewport and replacement atmosphere. Binding references:
`Docs/Guides/Visualizer_Reactivity_Authoring.md` sections 13A-13C; control/design ownership
`Docs/Reference/Waveform_Ribbon_Migration_Plan.md` (recorded measurements: its section 8); motion targets and recorded
bake-off `Docs/Reference/Waveform_Ribbon_Lab_Plan.md` section 5.1. Keep C-primary elastic response and A's accumulated
twisting.

**Reactivity milestone baseline (operator, 5 Nov): tag `waveform-baseline-2026-11-05` (= `e598155d`)**

Pulse and Centre Out "like night and day"; logical cadence survives heavy game load; **Preset 4 is the reference**
("let us not lose this"). Preset 4 keeps Breathing 0 (exactly the baseline dynamics).

- [ ] Every later dynamics change shows, on the recorded clips, that Preset 4 is unchanged against this tag (or names
  the improvement for operator sign-off).

**Operator-selected recovery baseline (3 Nov)**

`Docs/Reference/Images/Waveform_Ribbon_Material_Baseline_20261103.png` and its `.capture.json` preserve the exact
chosen image/settings/source; the baseline settings are applied to Preset 3.

- [ ] Use this material direction; do not darken the background or lower the floor's colour level. Retain this
  reference before further work.
- [ ] Floor brightness is provisionally approved, not the entire floor/atmosphere.
- [ ] Remaining lumps and reactive detail still need improvement.

**Fixed-scale rework v7 (accepted by the lead review 6 Nov, merged; operator sign-off on Preset 4 and the trade-offs)**

No adaptive memory (the Adaptive Response toggle is retired), Kick Accent bounded at 15% of the roll (Preset 4
ships 0), the floor lift bounded by the card's top edge. Lessons of the rejected v4:
`Docs/Guides/Visualizer_Reactivity_Authoring.md`; measurements: Migration Plan section 8.

Trade-offs against main, for the operator's sign-off or a request for the tag's exact Preset 4 dynamics (the decision
is in section 2; the lead accepted them on 6 Nov):

- Preset 4 visible amplitude p10/p50/p90 -4/+4/+5% and 3 s contrast +4.5% against the tag (inside the +-10% gate).
- Preset 7 roll 1.12x; P7 saturation higher on two songs (10.2% / 6.8% against 3.4%).
- Kick peaks 1.6-6.4% under main in 6 of 16 song-time bins (worst P7 0-15 s) and 6-11% over it in sustained loud
  bins.
- Quieter-after-loud kicks 8-27% under main by design (a quieter passage is no longer re-normalised up).
- Top-row spark density up to about 2x main.
- **Floor first (7 Nov, operator: "rather it goes a bit higher when it has to than clips"; supersedes top edge
  first): Preset 4 change for sign-off.** `TROUGH_LIFT_MAX` 1.5 -> 3, `TOP_GIVE_BACK` 1.5; Floor Give (P2) and Static
  Height keep 1.5. Preset 4's lift p50/p90 .75/1.48 -> 1.01/2.19 at 1282x1005 (the ribbon rides ~.7 world units higher
  at p90, at most 1.5 higher, in loud passages) and no longer dips into the floor (7.8% -> .1%).

- [ ] Lead review on the music-vs-response traces (`waveform_music_response.py`; chain7, every preset and Reaction
  Mode; 7 Nov):
  - [ ] Group Wave registers single kicks least: P7 as authored born rise .03-.06 per kick, P7 forced to Travelling
    Pulse .16-.30, and 46% of P7's kicks raise its born swell by under 1% of its range (Travelling Pulse 25%).
  - [ ] Whole Swell plateaus in flat loud songs (P6 song 2 saturated 20%, ws_P1 15%): the music's RMS is flat there and
    beats ripple the plateau, so it reads as sustained, not pinned.
  - [ ] Song 1's sparse intro (big isolated kicks in the PCM) barely moves any preset while the carry-over from song 0
    decays (re-scale gap .37-.50 on most presets).
- [ ] At the 640x560 card: P4 Anything's crest-clipped share is 6.2% against main's .4% (crests graze the top edge)
  and P4 Rag Doll 2.1% (.4%); crests above the top on .2-1.1% of ticks (main 0-.1%).
- [ ] P5 and P6 do not fit a 640x560 card with any setting (floor 32-43% and crests above the top 16-36% of ticks;
  rendered crest clipping 14-47% against main's 2-16%): authoring, their bodies are taller than that card.

**Preset 7 and the other reaction modes (operator log `logse7a84d332e.zip`, Rag Doll, 5 Nov; awaiting the lead's
review)**

Complaints: no decay/breathing in soft passages, sustained passages with changes read almost flat, a swell to full
power as the song got QUIETER. Preset 7 is Group Wave (song 31-123 s in the log; the recorded clip is song 70-130 s).
Evidence `reactivity_preset7/20261107_reactivity_preset7/`. The pulse-visibility WIP was dropped with its branch
(11 Nov): the operator accepted the pulse as is.

- [ ] Lead review on a rendered showcase WebP and the music-response trace of Preset 7 (bodies are smaller in loud
  passages now that the uniform inflation is gone: sustained-loud visible amplitude 6.4 -> 5.4).
- [ ] Lead review on rendered Whole Swell (Preset 6) strips: it sits at its soft bound in all music by design (one
  global level; de-saturating it barely changed the visible body, so it was left).

**Breathing + anchored history ends (merged; awaiting the lead's review)**

Evidence `.artifacts/evidence/visualizers/waveform_ribbon/breathing/20261105_breathing/`.

- [ ] Invisible run on recorded music and lead review of the animated WebP: soft passages let go between swells (0.7
  in every preset but 4) and a quieter passage after a loud one stays quieter.
- [ ] Lead review on a rendered side-angle WebP: the tail no longer staggers at side angles.

**Four-ribbon maximum and Preset 3 (Awaiting Validation)**

The candidate admits FOUR cards across authoring/runtime/clearance/accent/range paths, preserving Presets 1/2's three
active identities and old three-card state's values and count. The explicit operator maximum overrides the first
board's decorative count label; use four for Preset 3's paired target.

- [ ] Lead review on mock | ours sheets (full resolution plus crops): validate Preset 3 against
  `references/Preset3Goal1.png` and `references/Preset3ReactivityGoalExample.png`:
  - [ ] Teal/orange contrast.
  - [ ] Readable lattice/twist/strands/particles.
  - [ ] Continuous wet textured floor.
  - [ ] The large quiet-to-peak geometric change shown.
- [ ] Native low/high/recorded captures must reach that range without pinning or swapping scene/camera identity.
- [ ] The recorded draft still needs visual correction: white/rope-like overlaps, repeated continuation, weak/dark
  atmosphere and a poor floor/contact strip remain rejected.
- [ ] Do not equate source tests, particle/root counts or larger amplitude with reference fidelity.

**Reaction: travelling energy pulse + four Reaction Modes (5 Nov; awaiting the lead's review)**

Design: Migration Plan "Current reaction model"; decision record in the audit doc, decisions 7+; evidence
`.artifacts/evidence/visualizers/waveform_ribbon/studio_20261105/modes/`.

- [ ] Lead review on rendered strips and music-response traces: Travelling Pulse (default), Frozen Past, Whole Swell
  and Group Wave read right on recorded music (flow-rule and twitch tests exist for every mode).
- [ ] Group Wave still reads close to Travelling Pulse on rendered strips (it keeps the summed travelling field; its
  sets need their own pass), and its Pulse Width is not yet the band core the other two modes use (operator: "a
  relatively small horizontal width and the full vertical width").
- [ ] Pulse bands' colour edges read crisp at Pulse Falloff below ~1 on wide bands (Preset 5's vertical colour
  columns); judge on the operator's look whether the light's falloff should follow the geometry's broader envelope.

**Particles (5 Nov candidate)**

- [ ] Lead review on rendered crops and a WebP: crest-weighted, distributed births in each ribbon's colour, visible
  >=1 px cores with soft halos, gentle fade; swells gather particles (Pulse Particles).
- [ ] Open: still sparser than the high-react reference (admission-limited).

**Strands: rare, 3-5 seconds TOTAL life**

The latest operator correction supersedes the proposed 30-second fade.

- [ ] Lead review on a rendered strand WebP: preserve the approved non-flickering look and make appearances much
  rarer.
- [ ] Same review: use most of a configurable 3-5 second lifetime for a gentle tip-first fade.
- [ ] Same review: reactivation restores them smoothly, with glow and movement/growth (retain the approximate 20%
  repeat extension), without abrupt respawn or pulse reset.
- [ ] Prove quiet/peak lifetime handles, tip/root fade ordering, slow decay, partial-fade reactivation and
  direct/reflected appearance.
- [ ] Retain birth look during travel; finite history eviction must not cut off a visible unfinished fade.

**Colour, floor and mist (5 Nov candidates; awaiting the lead's review)**

Evidence `studio_20261105/floor4/`; measurements in Migration Plan section 8.

- [ ] Lead review on rendered sheets: lattice sheets (V3).
- [ ] Lead review on rendered strips: wet concrete with stable soft coloured reflection mass (no horizon line, no
  flicker-prone streaks; operator prefers smeared colour to streaks).
- [ ] Lead review on rendered sheets: one bounded night medium with a slight local ribbon tint (strong Local Light
  can no longer wash the frame).
- [ ] Wide sheets (P2) still graze the floor on ~60% of ticks: optional Floor Give (below) lets the wet floor dent
  under them instead.

**Fixed response, break-proof Breathing, Kick Accent (operator, 6 Nov: "when it went suddenly quiet everything become
more reactive ... Adaptive is a very problematic approach"; "many sustained kicks ignored"; awaiting the lead's review)**

Geometry drives are a fixed function of the real-music scale (the Adaptive Response toggle is retired). Preset 4
differs from the tag only through it, Kick Accent and the floor lift: compare against the tag with Kick Accent 0.
Range audit: `.artifacts/evidence/visualizers/waveform_ribbon/reactivity_preset7/20261107_reactivity_preset7/rangeaudit_*.txt`.

- [ ] Invisible run on recorded music and lead review of the music-response traces: the fixed response, Breathing
  and Kick Accent.
- [ ] Rotation's drive is never above .36 on any recording (its Peak handle is never reached).
- [ ] Light/Colour/Sparkle/Highlights, Width and Lift never reach .8 on three or four of five songs: those
  calibrations (not the response gain) are the remaining Range losses.
- [ ] The music's return after a break still dips for about a second while the shared passage level climbs back
  (return window 12-55% of the unbroken clip on every arm, main included).
- [ ] Preset 3's quieter-after-loud kicks are 4% under main's (every time bin is above).
- [ ] Soft passages swing less in absolute terms (3 s contrast .21 vs the adaptive gain's .30) and loud ones .11 vs
  .16.

**Floor Give (operator, 5 Nov: "the floor can deform inwards, allowing crests"; awaiting the lead's review)**

Opt-in Floor slider (default 0 = the rigid floor, pixel-identical); P2 authored 1.0. Perspective only. Evidence
`.artifacts/evidence/visualizers/waveform_ribbon/floor_deform/20261107_floor_deform/`; design in the Migration Plan's
Floor bucket.

- [ ] Lead review on rendered stills and a WebP: where a lower edge comes down onto the floor the wet floor yields in
  a soft dent, so troughs stay round and dip in instead of flattening: in the visible frame P2 reaches the floor
  only in the ragdoll loud end (about 49.5-52 s); P3 never does, so it is unchanged there.

**Pulse Rim (operator, 5 Nov: "where the pulse is that section of the ribbon's rim can be even brighter with
falloff"; awaiting the lead's review)**

Reaction-bucket slider (0 = today's rims, pixel-identical). Evidence
`.artifacts/evidence/visualizers/waveform_ribbon/pulse_rim/20261107_pulse_rim/`; design in the Migration Plan's
Reaction bucket.

- [ ] Lead review on rendered strips: the rims (line and rim glow) brighten on the pulse with the field's own smooth
  falloff, in every Reaction Mode and both Travel Directions.

**Swells reach the Preset camera already faded (Presets 1-3; awaiting the lead's review)**

Swells now born just beyond the camera's visible span and ageing only once seen; Preset 4 and Presets 5-7 byte-
identical. Evidence `reactivity_preset7/20261107_reactivity_preset7/` (`visibility_tag_vs_final.txt`,
`kicks4_table.txt`, `sheets/*_p1..3_*`).

- [ ] Lead review on the rendered sheets of Presets 1-3: edge swells arrive in view at strength.
- [ ] Open: on Presets 1/3 the rim's swell-to-elsewhere contrast (1.11/1.17) is still below Preset 4's (1.27).
- [ ] Open: the no-twitch probe's .02/.01 bounds only held because its swells never reached the cloth (in-view
  .028/.012).

**Travel Direction (operator, 5 Nov: "Travel Direction ... chosen in the studio ... an important basic need";
awaiting the lead's review)**

Flow-bucket Choice, Right To Left (default, unchanged) or Left To Right (the mirror image: history enters at the left;
pulses, held swells, Tilt Shift, sparks, strands and floor give follow; the world colour grade stays put). Leads the
Studio's Composition / Flow group. Evidence
`.artifacts/evidence/visualizers/waveform_ribbon/travel_direction/20261107_travel_direction/`; design in the Migration
Plan's Flow bucket.

- [ ] Lead review on a rendered WebP of a live change: it fades out, swaps while hidden and fades back (0.6 s each
  way).
- [ ] Lead review on rendered strips: Left To Right mirrors history, pulses, held swells, Tilt Shift, sparks,
  strands and floor give.

**Dense highlights, moving colour and rim glow**

- [ ] Playback still lacks rewarded high-energy density and glow: verify local crest/high-power colour, bright
  tunable rim/glow and denser highlights against actual music, including quiet/loud differences.
- [ ] Consumer reachability does not establish visible strength. Keep both range handles effective.

**Idle and first-play blackout**

- [ ] Keep subtle low-energy body motion and the same ready scene on first play; no blackout, re-priming or scene
  reset.
- [ ] Test cold playing-before-start, silence, pause/resume and source changes.
- [ ] Idle must not emit fake musical hits or particles.

**Dynamic Floor independence**

The operator found floor ON more responsive. Controlled full PCM now proves identical body/birth packets and typed
events OFF/ON on four clips.

- [ ] Prove lively OFF response by ear/eye against the guide's standard; raw parity alone does not establish musical
  response.
- [ ] Preserve the existing FFT/bus raw-reference policy, mode-switch/reset and stale-compute fences, plus accepted
  Bubble/EB behavior.

**Grounded camera, near-flat tilt and infinite view**

Perspective is the only projection (Orthographic removed 5 Nov 2026) and retains its positive clip contract. Native
geometry and persistence tests alone cannot establish feel or beauty across moving audio, view and viewport extremes.

- [ ] Stable eye height above the floor, approach/retreat and bounded left/right orbit, waveform always in view and no
  escape into ugly areas.
- [ ] Admit a genuinely near-flat tilt with visible floor.
- [ ] Keep eye/basis, navigation, editor markers and saved pose under the shared owner; preserve continuous/infinite
  body with no exposed ends and complete Edit scaffolding.
- [ ] Reproduce the new cut-to-black at one end and staggered entry at the opposite end against recorded wide/angled
  playback.
- [ ] Current visual route (operator delegates the choice): a restrained long-lens Perspective primary view,
  calibrated with a farther physical eye and narrow lens together; preserve stable height, bounded orbit and actual
  camera movement; no camera-dependent actor density or audio compensation.
- [ ] Judge colours, restrained reactive twisting, floor material and full-scene mist together against the references
  before acceptance.

**Floor coverage, collision, reflection and viewport changes**

- [ ] Lead review on rendered frames (D1 run, 1B.14 harness, for native pixels): the floor now intersects the same
  physical camera's pixel rays with the infinite world plane, covering foreground/far ground while actor clipping
  remains unchanged. Finish the unified atmosphere before visual judgment.
- [ ] After the strand slice, draw ground all the way through the foreground and beyond the waveform into heavy dark
  mist that GENTLY thickens until no horizon line is visible. A strip of reflections over black is rejected.
- [ ] Keep actors and physical floor contact correct, with smooth waveform collision rather than clipping.
- [ ] Compare identical snapshots at canonical/wide/tall/large sizes in Perspective; inspect reflection
  normalization/filtering separately.
- [ ] Preserve live reflectivity/tint/brightness and the shared resize contract; no audio-gain compensation. Columns
  remain secondary.
- [ ] Additional explicit rejection: material outside the core reflection is practically invisible. Validate readable
  dim texture across the foreground with reflection and atmosphere both OFF, then under the unified night medium;
  increasing reflection alone cannot satisfy this. The current candidate restores filtered concrete/roughness and
  ambient light.

**Unified atmosphere (5 Nov candidate)**

Replacement medium in place (old banks/fringe/floor haze removed); P3 density 0.06-0.09, P1/P2 0.055-0.075.

- [ ] Lead review on rendered sheets: the darker bounded haze with capped local tint.
- [ ] Open: the retained moving-body wake needs measurement.
- [ ] Open: the loaded fog cost gate (P2/game60 render median was over budget) needs measurement.

**Waveform Studio (replaces the rejected builder UI)**

In-process, reusable (mode registry + switcher; Extruded Bubble is a second real adapter) Qt Quick Studio per the
operator's design pack; Settings > Custom opens it. Contract: `Docs/Reference/Visualizer_Studio.md`.

- [ ] Remaining mock parity.
- [ ] Real-window checks on hardware: visible window; native Settings hide/restore; exit timing via `[STUDIO] retire`
  logs; per-monitor DPI.

**Live performance and truthful evidence**

Offline GPU at the live card size: P2 7.2-7.6 ms with strands, 6.0-6.6 without (strands ~1.1 ms); logical tick budget
2.5 ms (measured history: Migration Plan section 8).

- [ ] Run all three presets under matched recorded PCM/game60 and admitted camera extremes.
- [ ] Verify the ACTUAL applied configuration, audible input and rendered features before interpreting timings
  (requested CLI settings can be overwritten by curated activation).
- [ ] Profile logical preparation, birth admission, render stages and whole-frame tails; do not reduce artistic
  reaction strength to conceal cost.
- [ ] Preset 2 with persistent strands currently exceeds the render budget (~14 ms median under game60): reduce
  repeated submission/preparation and prove tails without weakening the approved strands.
- [ ] GPU re-measure now that Floor Give has landed, then the game60 live check.

**Chosen first: the smallest contained scene and the first consumer of S3D-1/S3D-2/S3D-5**

Brief and hard gates: `Docs/Future_Work/Waveform_Ribbon.md`. The detailed working checklist and visual target custody
live in `Docs/Reference/Waveform_Ribbon_Lab_Plan.md`; reference packages under `references/` are local/operator-owned
and intentionally absent from normal GODZIPs. The scene is world-first through the shared framed Perspective camera:
wet reflective concrete floor, waveform and full-scene night fog, with no visible horizon/sky/floor edge; the waveform
clears and softly lights the mist.

- [ ] Preset/control migration and recorded-audio calibration come only after the lab look is credible.

**WR-07/08 production candidate: finish admission**

The reaction is the travelling energy pulse with selectable modes (the C elastic body remains only for depth
sway/torsion); A's accumulated twist and the reactive axial roll stay, with musical vertical response applied after
the roll (roll-invariant).

- [ ] Lead review on rendered strips and a WebP: preserve constant history flow, no time-varying axial scaling,
  smooth curves, particles/free strands and fog clearance by the actual body.

**Full controls/editors, four-ribbon capacity and three presets: finish admission**

Candidate Preset 1/2 with the selected hybrid, shared framed 3D camera/navigation, technical profile, preset/Custom
and Edit/Arrange feature set exist.

- [ ] Lead review of rendered Studio frames: expose bend/torsion/stretch/twist/rotation and accent ranges,
  source/curve visual tuning, ribbon/gradient editors, and floor reflectivity/tint/brightness.
- [ ] Every reactive range needs actual quiet/peak consumer proof for both handles (the range audit, lead-run).
- [ ] Retain mutable authored presets and prove Save/Cancel/Restore and runtime source reachability (focused tests
  on the real SettingsDialog).

**Framing, timing and acceptance**

- [ ] Prove hidden ends/history bounds and body/head-to-visible delay across admitted sizes/camera poses.
- [ ] Replay real quiet/middle/hot/silence/hot-start windows with unshifted audio, inspect lab/production parity and
  audit range headroom.
- [ ] Close shared lifecycle/cost/dormancy gates and run `tools/visualizer_live_check.py --mode waveform_ribbon --load
  game60` before WR-09 acceptance.
- [ ] Lead visual/native judgement at WR-09 acceptance: rendered showcase WebPs and a D1 run (1B.14 harness); what
  neither can close, and has no simple test, becomes a Watchlist entry, never an open phase (operator, 11 Nov).
- [ ] The new unified atmosphere supersedes all old fog layers. Floor-column polish is secondary to continuous ground
  and response.

**Loaded render budget**

The prior run labelled fog-OFF rendered fog because preset activation overwrote its CLI values; it is a failed fog-ON
run, not an A/B.

- [ ] Repeat the corrected actual-config live check after current source/geometry changes.
- [ ] Verify packet lease/GPU envelope/culling retirement and finite-consumer parity.
- [ ] Measure current body/birth/floor cost with the rejected volume disabled. Keep CPU reduction as a test oracle; no
  readback or duplicate live preparation.
- [ ] The replacement atmosphere must earn its own measured budget.

### 7.2 Reactive Liquid / Audio Melt Pool

A heavy viscous molten body in a real concrete chamber; must never read as Neon Lake (`shockwave_grid`) water. Brief
and hard gates H01-H14: `Docs/Future_Work/Melt_Pool.md` (mock in
`references/Reactive_Liquid_Audio_Melt_Pool_Concept_and_Architecture.zip`). Uses S3D-3 (chamber), S3D-4 (surface
field), S3D-5 (reflections), S3D-2 (droplets).

- [ ] Stages with stop points:
  - [ ] Static chamber + framed camera.
  - [ ] Connected viscous surface.
  - [ ] Musical pressure and peaks (decide whether a deformable peak mesh is needed).
  - [ ] Material/environment interplay.
  - [ ] Droplets, Settings, acceptance.

### 7.3 Concrete Rain

Rain on a night street: music changes the pavement's water, never the street. Contract:
`Docs/Future_Work/Concrete_Rain.md` (reference `references/Low and High Reactivity Concrete Rain Comparison.png`, left
low / right high). Reuses S3D-3 (street), S3D-4 (ripples), S3D-5 (wet surface, reflections), S3D-2 (impacts, crowns,
droplets).

- [ ] Stages:
  - [ ] Wet surface and reflection.
  - [ ] Ripples and impact rings.
  - [ ] Splash crowns/droplets.
  - [ ] Music mapping (density, impact energy, ripple complexity, reflection disturbance).
  - [ ] Scene assembly and acceptance against the reference.

### 7.4 Usu Moonscape (eventual)

Long-horizon character/world vertical: `Docs/Future_Work/Usu_Moonscape.md` (Blender work:
`Docs/Future_Work/Usu_Blender_Work.md`). Not admitted until the foundations are proven; the static silhouette approval
stays a separate hard gate.

- [ ] Prove the character/world foundations S19-S27 listed there (asset bake, skinning, animation graph, secondary
  motion, felt/fuzz, world-view projection, sphere world/starscape) plus S3D-6.

## 8. Accepted Bubble: bounded performance gate and deferred control audit

The operator has **accepted the improved original Bubble normal-drift musical authority**: that task is closed, do not
reopen it as unfinished work or restore the pre-experiment drift response (approved motion, ambient, direction and
occlusion rules: `Docs/Guardrails/Bubble_Temporal_Fidelity.md` section 23). The performance gate below is
**explicitly admitted now** as a short exception to the section 7 mode sequence. The separate scalar-to-range audit
remains deferred until explicitly reprioritized (it is folded into section 9's adapters).

**Bubble post-ambient performance / exact-output check (short and bounded)**

Inspect hidden costs from the shared hero big-over-small shader loop (including decoration OFF), the opt-in
2048-capped ambient FBO, large glow sprite fill, and up-to-110-circle masking.

- [ ] Compare the **original handoff** to the **accepted Slice 13** under matched configuration for
  resource/performance attribution, then freeze **Slice 13 itself** as the behavioral and rendered-output oracle for
  any proposed optimization: original-vs-Slice-13 pixel bytes are *not* expected to match where the operator
  intentionally changed layering, motion or glow.
- [ ] Measure decoration OFF, representative decoration ON, and high-density/high-glow decoration ON, using matched
  real-music replay and canonical plus extreme-wide/tall/expanded sizes, with multiple repetitions on the operator's
  native Qt Quick/OpenGL runtime.
  - [ ] Report Bubble GPU/render p50/p95, CPU logical work, FPS/frame-pacing gaps, resource allocation/release and
    other-display contention.
  - [ ] Check that OFF really avoids the extra FBO, sprite and mask draws; the modified shared hero shader still
    warrants timing even with decorations OFF.
- [ ] Include the R-170 density growth: a card larger than the canonical one now draws up to 72 live heroes (up to 110
  with draining trails) instead of its authored ~31-68, and the hero loops are per fragment.
- [ ] For any **actual optimization**, compare deterministic logical packets/bit patterns exactly, and compare final
  captured RGBA bytes frame-by-frame on the **same GPU, driver, dimensions and fixed replay** when that capture path is
  deterministic.
  - [ ] Where bit identity is unavailable, disclose why and use exact geometry/response checks plus recorded
    pixel-diff and temporal parity evidence.
  - [ ] Do not claim byte-identical *performance*: throughput, GPU timing and latency require measurements.
- [ ] If cost is material, optimize only the measured offender and repeat the parity + native performance gate;
  preserve visual quality, all approved sinking/reversed-flow presets, reactivity/latency, BTF and mutable presets.
- [ ] If no material cost is measured, **close the item without redesigning Bubble**. No generic "lean out" campaign.

**R-170 lead review**

Evidence: `Docs/Historical_Bugs/R-170_Bubble_Shape_Dependent_Speed_And_Aspect_Modifiers.md`.

- [ ] Lead review on rendered WebPs at each card size: Bubble on a tall card, a wide card and the TV card moves and
  sizes like the canonical card, and is denser on large cards.

**Side defect (found during R-170, not fixed)**

- [ ] `_apply_bubble_collision_response` smooth mode multiplies `max_disp *= 0.72` inside the per-bubble loop, so the
  in-view correction cap compounds down the list (order-dependent). Fixing it changes canonical Bubble output, so it
  needs an explicit BTF behaviour-change decision first.

**Particle glow (merged; awaiting the lead's review)**

Emitted linear light with a hot core and a monotonic halo (no dark moat), no twinkle on drifting sub-pixel cores,
cheaper ambient CPU pass. Evidence `.artifacts/evidence/visualizers/bubble/particle_glow/20261107_particle_glow/`
(`before/` vs `after/` 4x crops, flicker strips).

- [ ] Lead review on the `before/` vs `after/` 4x crops and flicker strips (rendered): the particle glow.

## 9. Studio for every visualizer (replaces the builders)

Operator (5 Nov): instead of a Bubble UX sweep, every visualizer (Sine retired 2026-11-05) gets a version of the
reusable Studio (`ui/studio`, mode registry + adapters) that replaces its builder. The Waveform Studio is the first
adapter and the framework bar; each mode contributes only an adapter (typed schema from the canonical registry,
truthful evaluator on its production logical/render path, fixtures, scene objects, workspaces and instruments), never
a copied shell. The former Bubble scalar-to-range idea is folded in: each adapter picks the right instrument per
control under the design pack's control policy (quiet/peak A/B, real ranges only where a true interval exists), with
unchanged serialized data unless a migration is justified. Accepted looks/behaviour (BTF, presets, timings) must not
change.

- [ ] Finish Waveform Studio acceptance first (section 7.1), then extract any remaining Waveform-shaped assumptions.
- [ ] Adapters in order of authoring pain (Extruded Bubble, Bubble, Spectrum/Rainbow Ghost, Extruded Spectrum and Neon
  Lake (`shockwave_grid`) built, Spline Curve (`devcurve`) and Oscilloscope built below):
  - [ ] Neon Lake awaits the lead's acceptance review on its rendered Studio frames (evidence
    `.artifacts/evidence/visualizers/shockwave_grid/studio/20261107_studio/`, Presets 1 and 3): recorded engine
    answers like Spectrum, the shared framed camera, no wallpaper; its terrain is painted with the Studio's shared
    brush (evidence `.artifacts/evidence/studio/completion/20261106_completion/brush/`; the retired Settings editor's
    3/4 view Sun / Moon drag is now Position X / Y / Z only).
  - [ ] Extruded Spectrum awaits the lead's acceptance review on its rendered Studio frames (evidence
    `.artifacts/evidence/visualizers/extruded_spectrum/studio/20261107_studio/`); its cast-shadow rows stay out of the
    Studio while they are unavailable (`EXTRUDED_CAST_SHADOW_AVAILABLE`).
  - [ ] Spectrum awaits the lead's acceptance review on its rendered Studio frames (evidence
    `.artifacts/evidence/visualizers/spectrum/studio/20261105_studio/`).
  - [ ] Lead review of the rendered Settings pages (the real SettingsDialog, off-screen), one sentence per mode:
    every mode's Settings body is now the preset row and the Studio launcher (operator 6 Nov: migrate fully once
    parity+ is proven; `tests/test_visualizer_studio_parity.py`).

**Spline Curve Studio built (6 Nov), awaiting the lead's acceptance review**

`ui/studio/devcurve_adapter.py`, registered; Spline Curve's preset row shows Open Studio and no Edit Preset. Evidence
`.artifacts/evidence/visualizers/devcurve/studio/20261107_studio/` (Deep Blue on Rag Doll, Neon Skyline on Human: every
workspace with the live traces, plus the node rows).

- [ ] Lead review on the rendered Studio frames: the per-layer Body / Accent / Swell traces as the way to read the
  reworked reactivity.
- [ ] Lead review on the rendered Studio frames: the Layers workspace (one panel per layer).

Whether the Audio Analysis group earns its place is a decision in section 2: it is re-analysed from PCM through the
production DSP, every offered control moves Spline Curve's frame; AGC Strength and Output Lift read nothing and are
now hidden (`Docs/Reference/Visualizer_Reference.md` -> Audio Analysis controls per mode).

**Oscilloscope Studio built (6 Nov), awaiting the lead's acceptance review**

`ui/studio/oscilloscope_adapter.py`, registered. Evidence `.artifacts/evidence/oscilloscope/studio/` (Preset 1 Phosphor
on Human, Preset 3 Lissajous on Rag Doll: every workspace with the live traces). Recorded engine answers with the
capture history recorded by identity (binary sidecar; `Docs/Reference/Visualizer_Studio.md` section 3).

- [ ] Lead review on the rendered Studio frames: Level / Afterglow / Ghosts / Flare / Drive / Tone as the way to
  read the beam.
- [ ] Lead review on the rendered Studio frames: the three workspaces.

Whether the Audio Analysis group earns its place is a decision in section 2: it is re-analysed from PCM through the
production DSP, every offered control moves Flare and Drive, and Bar Count, Block Size and Input Gain also move Tone
(the trace itself is the raw capture, but the beam's reactions are not; `Docs/Reference/Visualizer_Reference.md` ->
Audio Analysis controls per mode).

**Edit Preset deleted (6 Nov)**

Every visualizer mode now has a Studio, so the preset row's Edit Preset button, `_open_preset_json` and its pop-up are
gone (`ui/tabs/media/preset_slider.py`); curated presets are authored with Open Studio and the Studio's confirmed Save
To <Preset> (`Docs/Reference/Visualizer_Studio.md` section 4). `tools/flicker_test.py` keeps its own historical mock of
the old row.

- [ ] Lead review on a render of the real SettingsDialog (off-screen): Open Studio's place in the preset row.
- [ ] Lead review on a render of the real SettingsDialog with its popup patched: the Save To flow.

**Operator side requests (6 Nov, "important eventually"; queue after the running work)**

- [ ] **Waveform travel speed:** History Speed (`flow_speed`, 0.8-2.4, Flow bucket) and Pulse Speed exist but the
  operator did not find them, and there is no travel-speed reactivity (after the adaptive rework; same owner).
  - [ ] Make them findable (name / workspace / tooltip).
  - [ ] Consider a quiet -> peak History Speed under the flow rule: music pushes history faster, smoothly; knot spacing
    and the anchored ends stay continuous.
- [ ] **Studio clips are seamless loops (6 Nov), awaiting the lead's review of the wrap.** The Studio plays no
  sound: the clips are the capture stream the analysis reads, so the check is the music-reactive picture across the
  wrap. Contract `Docs/Reference/Visualizer_Studio.md` section 3 "Studio clips"; evidence
  `.artifacts/evidence/studio/clip_loop/20261106_clip_loop/`. Lead:
  - [ ] Review a rendered loop WebP of each of the three clips across the wrap (end of the 13 s timeline): the
    preview should not jump, empty, or re-start its motion.
  - [ ] Rag Doll has no steady beat, so its seam is the least certain: judge it first.
  - [ ] The clips now start and end mid-song at the loop points chosen (Human and Growing Pains on their groove), not
    at the earlier quiet-to-hot windows. Whether the quiet-to-hot arc matters more than the seam is a decision in
    section 2.

**Studio chrome: Awaiting Validation**

Active material work is section 1A, item 1.7; rounded native corners remain open at item 1.9. Contract:
`Docs/Reference/Visualizer_Studio.md` (Chrome and theme). Off-screen Studio evidence cannot establish native DWM
composition; preview-overlay backing stays cheap and scene colours stay independent of chrome.

- [ ] Studio run on D1 (1B.14 harness), lead review of grabbed frames: the shared semantic material on panels,
  workspace tabs, section headers, tools and instrument wells.
- [ ] Same run, driven by messages: native snap/resize/maximise.
- [ ] Same run on a light theme: light-theme shadows.

**Studio drag lag fixed (6 Nov), awaiting the lead's drag check**

Drags preview once per frame and re-show only the dragged key (`Docs/Reference/Visualizer_Studio.md` "Drags are
batched"); evidence `.artifacts/evidence/studio/drag/20261106_drag/` (per move 56 ms -> 0.07 ms on Waveform).

- [ ] Studio run on D1 (1B.14 harness), drags posted by messages with `tools/studio_drag_profile.py`: the feel of
  drags (per move on the 0.07 ms scale of the evidence above).
- [ ] Side defect (not measured): Bubble's, Extruded Bubble's and Sphere's evaluators still replay exactly in one
  evaluation from the fixture start, without the frame budget and checkpoints Waveform and the engine-answer modes now
  share (`ui/studio/exact_replay.py`). Measure with `tools/studio_drag_profile.py` and move them onto `ExactReplay`
  where a release stalls.

**UI frozen after closing a Studio, recovered by itself (operator 6 Nov 21:56, Extruded Bubble, Wine Ice Acrylic):
owner found in source, awaiting a field log**

The close was clean (Settings revealed `visible enabled exposed`, native `(True, True)`, window destroyed after 77 ms),
then the GUI thread logged nothing for 18 s with the process idle (CPU 4.7 %, GPU 0.1 %) while the event-loop recorder
still delivered its 15 s summary on time at 21:56:48 (not a stall; its `period_samples=0` only means the lifecycle
window was open, as for all of Settings). Not reproducible offscreen. The cause and the 7 Nov remedy
(`WindowPresence.repaint_revealed`, the watch's `qt_exposed`) are recorded in `Docs/Reference/Visualizer_Studio.md`
section 4 ("Repaint at the reveal"). This is the third round of this defect.

- [ ] Open until a field log shows a paint right after the reveal and `first Paint after the first input` within a
  frame or two (the `[STUDIO] after reveal` lines, `presence.RevealWatch`, one-shot, removed at the first input to
  Settings, name which window Windows sent the clicks to and the state at each step; "repaint since reveal: none" is
  the takes-input-but-never-repaints signature).
- [ ] Acceptance needs the operator's field log plus a fix proven on the real SettingsDialog path, never a stand-in
  only. If the lines show another owner, fix that owner from them.

**Camera reset on every edit and the exit double flicker fixed (operator 8 Nov), awaiting the lead's D1 run**

On a curated preset (Include current camera view on, the default) each commit used to re-hydrate the framed camera
editor and drop the orbit committed into the draft (Neon Lake, Extruded Bubble, Waveform Ribbon); Settings now appears
beneath the Studio and comes forward once it is gone (`Docs/Reference/Visualizer_Studio.md` section 4 "One transition
out").

- [ ] Studio run on D1 (1B.14 harness), lead review of grabbed frames: orbit, then drag sliders (the view stays).
- [ ] Same run: close the Studio by every path (one clean change to Settings, no swap).

**Per-session memory growth in the Studio (side defect, 6 Nov; the clip caches ruled out 7 Nov)**

Process memory grows about 2-3 MB per offscreen Extruded Bubble session (private bytes and USS, 16 sessions), the same
with and without the controller-leak fix (`test_closed_studio_sessions_are_released_and_live_counts_stay_flat`). The
sessions measured load no recorded clip, so the clip caches cannot be the cause; they are bounded now anyway (AC-06: 60
Audio Analysis re-analyses grew 39.3 MB before, 15.5 MB after, flat at 120). Re-measured with `_sessions` (24 sessions,
private bytes after `gc.collect()` per session): the first 4 sessions add ~85 MB (warm-up), then ~1 MB per session that
flattens, but the series swings by +-70 MB run to run (main and branch alike), and tracemalloc sees only ~55 kB of
Python growth per session (QML chrome objects, settings normalisation copies). What grows is native (Qt Quick / GL
driver heaps), not Python.

- [ ] A native heap comparison (UMDH or VMMap) across 30 sessions; bar: a trend, not run-to-run noise, before any
  fix.

**Slider drags no longer let go mid-motion (operator 6 Nov), awaiting the lead's drag check**

The cause was the inspector's ScrollView stealing the press on a vertical wobble; every drag instrument in a scrolling
panel now sets `preventStealing: true` (`Docs/Reference/Visualizer_Studio.md` "Drags are batched";
`tests/test_studio_drag_coalescing.py`, with a negative control).

- [ ] Studio run on D1 (1B.14 harness), a drag with a vertical wobble posted by messages: a slider drag holds
  through a wobble on every mode.

**No automatic switch to Custom (operator 6 Nov), awaiting the lead's review**

A Studio edit on a curated preset is held, with nothing saved and the preset still selected; closing, switching preset
or switching mode asks *Unsaved Preset Changes* (spec: `Docs/Reference/Visualizer_Studio.md` section 4 "Canonical
save"; tests `tests/test_studio_preset_row_and_save_to_preset.py`).

- [ ] Lead review of a grabbed frame (D1 run, 1B.14 harness): the prompt's wording and buttons over a real Studio.

**Neon Lake: drag the Sun/Moon in the Studio preview**

- [ ] Retiring the Settings terrain section (6 Nov, Studio brush) removed its 3/4 view, where the Sun/Moon could be
  dragged; it is now placed with Position X/Y/Z only. Give the Studio preview a direct drag for it: the same pick
  through the production camera as the terrain brush, one undoable commit on release.

**Lead review: the Studio terrain brush**

Brush button or B in the viewport toolbar; Raise, Lower, Flatten, Water; left-drag paints, right/middle drag pans.
Evidence `.artifacts/evidence/studio/completion/20261106_completion/brush/`. Audio Analysis now moves the Spline
Curve, Oscilloscope, Neon Lake, Bubble, Extruded Bubble and Voxel Sphere previews on recorded clips (sensitivity sheet
`audio_analysis/`); Spline Curve normalises its body, so it barely shows, as live.

- [ ] Studio run on D1 (1B.14 harness), strokes posted by messages, lead review of grabbed frames: the terrain brush
  in the Studio.

## Operator execution and evidence rules

Keep details and evidence at their focused owner, this checklist actionable, and `Index.md` / `Spec.md` navigation current.
No memory updates without an explicit request.

####################
ADDITION & SIDE QUEST BOX
Never Remove This Box. Restore It If Removed. Only Remove Contents As you place them in the active plan as real live checklist targets.
####################

###################
