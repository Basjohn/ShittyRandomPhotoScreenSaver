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
- [~] Studio stall, clip selection and sidecar log (contract: `Docs/Reference/Visualizer_Studio.md`; the control-hints
  test runs on a never-shown window), operator checks:
  - [~] Edit Reaction Mode while Waveform plays.
  - [~] Pick Human once.

### Item 2. §7.1 Waveform Ribbon reactivity (operator, 7 Nov night: "Adaptivity is the enemy")

Contract: `Docs/Guides/Visualizer_Reactivity_Authoring.md` (§2B, §2C, §13D). Evidence:
`.artifacts/evidence/visualizers/waveform_ribbon/memoryless_reactivity/` (`20261107_lead/`, `20261107_bands/`) and
`.artifacts/webp/visualizers/waveform_ribbon/memoryless_reactivity/`.

- [~] Frozen Past (Preset 5) live.
- [~] Pulse Count, Pulse Falloff and Freeze Deflate in the Studio.
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
- [~] Operator's physical look at the expanded card's inset (operator, 7 Nov night: "Don't reach nearly close enough
  to the screen borders") and at the ordinary widgets and their shadows fading out with it (operator: "Don't really
  hide/disable the widgets underneath"; 14 logical px at 2560 x 1440 was 30). Complex transitions under the takeover
  are M4.
- [ ] Bright-area text switch (operator's long-term item, plan 01 §G): overlay text white with a soft shadow should
  switch to black over a bright Visualizer area; cheap means no per-frame CPU readback (a `ShaderEffect` on the text
  sampling the already-rendered frame, or a tiny luminance probe only while an overlay shows). Not built.
- [ ] Agent branch (plan 01 M3c "Now Playing's parts" and §G "Show On Hover"): lead audit and merge of (a) Show On
  Hover (`now_playing.hover_reveal`; no timer or polling; nothing under Fullscreen Edit) and (b) Now Playing's parts
  as the block's children in Fullscreen Edit (`now_playing.child_geometry`).
- [~] Operator's live look at that branch: the feel of the child lock, a part drag and the hover re-fade on the real
  display.
- [ ] Side defect (8 Nov): `tests/test_qtquick_system_audio_osd.py::test_osd_colour_inheritance_respects_active_widget_
  theme_and_authored_overrides` fails when run after `tests/test_visualizers_fullscreen_mode_pill.py` in one
  process (passes alone; reproduced on the base): Widget Theme state leaks between the files.
- [ ] M4 (plan 01 `02_E0_Covered_Display_Admission.md`): the GPU/render-thread measurement with photo changes on the
  other display.
- [~] M4: the operator's two-monitor look.

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

Pick the most valuable runs that fit; baselines and evidence paths are in section 3, "Lead, the quiet machine".

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

- [~] Awaiting Validation, frozen: next requested build: QtCore-only engine workers, expected image-worker Qt
  dependencies, flat worker memory, unchanged icons and one Settings round trip. First Neon Lake activation: logged
  cold link with live progress or cache hit, never an activation-failure reload; second run: cache hit.
- [~] Awaiting Validation, audio devices (design 5.3): default switch, pinned player, USB/Bluetooth or sole output
  unplug, silent/remote playback and another player masking the old endpoint; include in-process control and time
  capture reopen against cadence. No device/load run without the operator.
- [~] Awaiting Validation, M2 latency: size first reveal against in process in a separately approved load session.
  The cold configure bound remains six seconds; later owners skip it after a deadline miss this run.
- [ ] After device checks, decide whether the in-process owner should use the existing worker delivery watch to
  recover stale loopback streams; it currently waits for a later playback/activation edge.
- [ ] Make the framed-view negative control independent of presentation timing
  (`test_visualizer_owner_engine_worker.py::test_the_framed_view_the_worker_tick_reads_follows_the_owners_controller`).
- [ ] Decide bounded reconstruction for a target that never reveals, including stopping a failed owner's runtime on
  refused reload; the existing loop can retry every six seconds.
- [ ] Bubble owner: define Random Group Drift's guarantee before retuning or asserting alignment;
  `test_bubble_reactivity.py::test_group_drift_aligns_non_swirl_bubble_motion[random-x]` depends on the draw.

**Remaining sequence (dedicated Fable High, in this order; it reports at each numbered boundary for the lead's
audit; focused proof for each):**

1. M4 non-default production-owner parity (dynamic capacity, high-water and non-default packet tests are already
   implemented; do not reopen them):
   - [ ] Non-default worker/in-process **rendered** parity.
   - [ ] The gate-2 rendered no-visual-change record.
2. M5, L2-L5 and the POSIX Connection lifetime repair (which must own a bounded descriptor retirement before the
   Linux worker default can depend on that transport):
   - [ ] M5: the in-process mode-cycling memory growth (gate 4 side finding) still hits the fallback and the Studios.
   - [ ] L2: gate 3's "GIL share" fields are wall time, not GIL hold; "revisions waiting 0/0" is zero by
     construction on the worker path; the worker's audio feed differs from a real device.
   - [ ] L3: `--usage` costs ~13 ms more per 15 s sample with the worker (see section 5's usage-sample hitch).
   - [ ] L4: the wake listener takes the GIL every frame (unmeasured); presentation inputs holding a Qt type are not
     forwarded silently; a blocked tick thread whose loop still answers heartbeats freezes undetected.
   - [ ] L5: reconcile remaining historical qualification: gate 4's worker memory predates R-179; the earlier "next
     frozen build" wording is already answered by frozen check 2; audit the remaining writer overstatement.
   - [ ] POSIX transfer lifetime: design bounded ownership for an accepted Connection never decoded because its
     worker dies. The inherited stdlib sharer can retain one sender descriptor; synchronous serialization creates it
     earlier. Do not cancel accepted registrations through the private cache or block GUI on a sharer handshake.
     Boundary/source evidence: phase-boundary audit L1. Linux runtime remains unverified; this is a source repair
     task, separate from the operator-waived Linux proving step.
3. H3 Linux worker-default source flip and focused tests (the operator waived **physical** Linux validation, not
   source correctness; do not claim Pulse/forkserver runtime was tested):
   - [ ] H3: worker path has no native Linux runtime evidence (forkserver, POSIX wake, Pulse capture). After the
     source POSIX-lifetime repair, flip Linux default and update `Linux_Plan.md`; the operator's hardware waiver
     does not turn untested runtime behaviour into a green gate.
4. P3's four decisions and first native rendering substrate:
   - [ ] The native reader vs the GUI thread closing the mapping mid-copy.
   - [ ] A single consumer and a non-consuming head read for the Python owner.
   - [ ] EB geometry once per revision, not per frame.
   - [ ] EB's fp64 drift solver (optional on Vulkan, not queryable through QRhi; the shader-readiness check scans a
     fixed module list and cannot see it).

**P3 and P4:**

- [ ] P3: one C++/QRhi native core for all custom drawing, one staged ownership plan: substrate, Spectrum parity,
  shared fullscreen transition passes, Waveform/Extruded Bubble, specialised transitions, the remaining
  Visualizers and image/background/Scene3D ports. Switch the whole window to Vulkan only when raw-GL nodes have
  retired; retain OpenGL through that same QRhi core.
- [ ] P4: mixed-resolution soft layers in the core.

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

### 1B.1 Edit edits the display it was entered on (merged 46129166; contract: plan 01 M3c "Edit beside the view")

- [~] Operator, two physical monitors, Visualizer expanded on one:
  - [~] Edit from the other display (context menu, then double-right): its widgets edit, the expanded view keeps
    animating, no Edit chrome on the expanded display.
  - [~] Edit from the expanded display: Fullscreen Edit of the overlays only.
  - [~] Save and Cancel from each; a collapse press while Edit is open beside the view waits for Save/Cancel.
- [ ] Side defect: `tests/test_qtquick_custom_layout_owner.py` then `tests/test_qtquick_context_menu.py` in one
  process fails the menu tests (`menuVisible` False); suspect the 700 ms right-click suppression armed by an
  earlier test's Save/Cancel leaking across tests. Reset it per test at its owner.
- [ ] Side defect (unreproduced): in an ordinary global Edit, closing the Visualizer and then switching mode makes
  `activate_edit_visualizer_profile` return False (`rendering/quick/custom_layout_owner.py`, the `visible is None`
  branch), which looks like a forced runtime reload. Reproduce in a test or rule out.

### 1B.2 Cursor keeps its changed shape after exit until a click (merged 0f8f4836; R-183; NOT accepted)

The retire owner now gives Windows the arrow natively. The native harness reproduced the stuck shape only with
Qt's pointer tracking cleared artificially, so the operator's real exit path is unproven.

- [~] Operator: run `.venv\Scripts\python.exe tools\cursor_exit_observer.py --label <name>`, start the saver, and
  keep the mouse still two seconds after each exit:
  - [~] key exit
  - [~] click exit
  - [~] mouse-move exit
  - [~] link click (browser opens)
  - [~] Settings opened from the saver
  - [~] Media Center mode exit
  - [~] exit with the pointer on the second display
- [ ] Read the observer log (`.artifacts/evidence/input/cursor_exit/`): any path printing `only after click`
  names the event that clears Qt's pointer tracking; reproduce that path in `tools/cursor_exit_native_harness.py`
  and fix it at the retire owner.
- [ ] Update R-183 with the operator's result (accepted, or the failing path and its fix).
- [ ] Side defect: when a hovered QML item is destroyed or left, the saver window can keep the hand or arrow
  instead of the Halo until the Halo next re-applies it.
- [ ] Side defect: `tests/test_artifact_paths_contract.py` fails on literal `evidence_chest` paths
  (`tools/godzip_foundry.py` 2579, 2632, 3386; `tools/godzip_logzip_retention.py` 22, 38), PNG writes outside
  `tools/evidence_media.py` (`tools/settings_native_corners.py`, `srpss_border_core.py`, `srpss_border_studio.py`)
  and a `delete=False` temp file (`tools/visualizer_capture_core.py:215`). Fix with section 3's "Tool-output
  contract reds".

### 1B.3 Studio slider save churn (audit and its two camera side defects landed; contract: Visualizer_Studio.md)

- [ ] The Studio's orbit notice says the orbit "saves only with the preset's camera checkbox"; Sphere and
  Extruded Spectrum have no checkbox and save through Save Camera. Make the notice follow the mode's policy.
- [~] Operator: Sphere Studio, drag View Turn / View Tilt (holds for the session), Save Camera, reopen.
- [~] Operator: Waveform Studio has Camera X and Z only (its grounded orbit fixes the eye height, so Camera Y
  never did anything); say if a real eye-height control is wanted.
- [~] Operator: Extruded Bubble Studio Camera X/Y/Z now span -2..2 (the eye's whole admitted box), was -1..1.

### 1B.4 Shape instrument for Spectrum and Neon Lake (design regression: sliders replaced the shape control)

Built and merged (one instrument in Spectrum, Extruded Spectrum, Neon Lake's Frequency Response and its Reaction
Shaper; contract: `Docs/Reference/Visualizer_Studio.md`; capture tool `tools/studio_shape_capture.py`). The lead
passed its off-screen pixels (dark and light themes).

- [~] Operator look at the instrument in the Spectrum and Neon Lake Studios: drag feel, cursor shapes and
  tooltips on a real window; over a material theme on the real desktop.
- [ ] `tests/test_studio_drag_io_churn.py`: its drag plans skip the SHAPE instrument; fold the shape drags in so
  the one churn guard covers it (today only `tests/test_studio_shape_instrument.py` proves no write per move).
- [ ] Side defect: long row tooltips do not wrap and run off the window (`RowLabel` in
  `ui/studio/qml/StudioShell.qml`).
- [ ] Side defect: a lane-strength diamond exactly under a curve node cannot be grabbed (reachable only through
  its tag, the field or keys); give the nearer-to-pointer element the press or offset the hit areas.
- [ ] `ui/tabs/media/spectrum_shape_editor.py` now only owns the node-limit constants and is a test subject:
  move the constants to the shape rule owner and retire the widget with its tests.
- [ ] `fft_to_bars` gained two helper calls per tick (`shape_bar_profile`, `lane_sample_positions`); re-record
  the Spectrum overhead baseline so the +2 calls are attributed, not read as drift.
- [ ] Admitted later if wanted (operator's call): a pop-out larger canvas; Spline Curve's layer nodes and Voxel
  Sphere's zone boundaries on the same instrument; Shift axis lock, snapping, double-click reset.

### 1B.5 Neon Lake: all visible land is brush-editable (reproduced; fix decided, operator agreed 11 Nov)

Cause: land past the authored grid is generated landscape with no stored cells, so `pick_terrain` refuses it
(26% of on-screen land on Preset 3; 13-20% on Presets 1-2 dollied back). Queued for Fable High after 1B.4.

- [ ] A stroke past the grid grows the authored grid through the existing extend owner
  (`rendering/gl_programs/neon_terrain_extent.py`, cap 257).
- [ ] Growth is invisible: new cells take the generated landscape's own heights (`scene_surface`), and the
  far-land curvature keeps its authored origin, so horizon, detail and glow do not shift. Prove with a
  before/after render of an un-painted growth (pixel-equal within MSAA jitter).
- [ ] Existing cells stay exactly as stored: every shipped preset's terrain loads byte-identical.
- [ ] The stroke re-maps its coordinates across a mid-stroke growth; one undoable step per stroke including
  the growth.
- [ ] At the 257 cap the brush shows a clear refused state (cursor + one-line notice), never a silent no-op.
- [ ] `tests/test_neon_lake_brush_reach.py`: the strict xfail "every visible land point is paintable" becomes a
  pass and the xfail marker is removed.
- [ ] Texture/mesh cost of the largest grown grid measured against today's (control-relative GPU).
- [ ] Docs: `Docs/Reference/Neon_Lake_Basin.md`, `Docs/Reference/Visualizer_Studio.md` (brush).
- [~] Operator: paint far land in the Studio.

### 1B.6 Neon Lake: land reactivity pass for smooth deformation (queued for Fable High with 1B.5)

- [ ] Reproduce the tearing/jagged edges first: stills and one animated WebP at high reactivity on recorded
  music, with the mesh density and the reaction path that produce them named.
- [ ] Smooth deformation at every reactivity: continuous normals and silhouette at the production mesh density
  (no cracks between cells, no stair-stepped ridges, no shading pops).
- [ ] Optional growth (default off, a preset-authored control): spires, mounds and land that is not visible at
  low reactivity rise with the music.
- [ ] Optional indents (default off, a preset-authored control): land that is visible sinks with the music.
- [ ] Fixed scales only (no learned levels, no `musical_weight` gate); everything ramps and fades in and out.
- [ ] One simulation owner: the existing terrain reaction path, no second population, no renderer-side sim.
- [ ] Each new control: canonical spec entry, Studio row, authored into every Neon Lake preset (repair fill +
  completeness guard), Settings/Studio parity test.
- [ ] Continuous-play evidence over whole songs (`neon_lake_music_response.py`): mid-song kicks still read.
- [ ] Per-frame cost before/after on the logical tick and the render (`tools/overhead_baseline.py`).
- [ ] Lead pixel review on showcase WebP; then merge.
- [~] Operator look.

### 1B.7 Fullscreen Now Playing: one geometry contract with the Media widget (not started)

Already shared: child editor, descriptor type, child-geometry normaliser, transport bar, metadata fit. Each slice
is its own reviewed checkpoint, in this order; the Media card stays pixel-identical after every one.

- [ ] a. Extract the Media seekbar from `MediaPresentation.qml` into one component with a look carrier (no
  behaviour change; before/after Media card renders identical at 100% and 150%).
- [ ] b. Parent geometry through the shared owner: the overlay block's move, corner scale, per-axis resize and
  Restore Size use the ordinary Edit handlers; delete the parallel code in `fullscreen_overlay_edit.py` and its
  tests.
- [ ] c. Alignment as declared roles: `alignment_flip` / `semantic_corner_anchor` on the overlay's roles replace
  the position-based mirroring in `ExpandedVisualizerOverlays.qml`.
- [ ] d. Artwork: one size carrier; the parent handles act as Media's do; border and shape follow the Media
  widget's artwork settings, not the Visualizer card chrome.
- [ ] d1. The four reds in `tests/test_visualizer_expansion_fullscreen_edit.py` are green or rewritten to the
  new contract (`test_parent_axes_resize_the_artwork_border_not_the_metadata_text_box`,
  `test_entering_fullscreen_edit_does_not_refade_already_visible_now_playing_content`,
  `test_now_playings_parts_move_and_size_inside_the_block_through_the_child_editor[False/True]`).
- [ ] e. Snap and guides: display edges, centre lines and the other overlay through the ordinary guide owner.
- [ ] f. Storage: the key `widgets.spotify_visualizer.fullscreen_overlays` stays; its records take the ordinary
  child-geometry schema and normaliser; any shape change gets its load bridge in
  `Docs/Architecture/Persisted_Input_Compatibility.md`.
- [ ] g. Optional seekbar (default off): Fullscreen Mode option, a child part in Fullscreen Edit, the Media
  card's seek route and double-click ownership, authored into the defaults; no timer for position.
- [ ] h. A saved profile's overlays render to the same pixels before and after (a user who never opens
  Fullscreen Edit sees no change).
- [ ] i. No overlay-only geometry maths left: grep-level audit listed in the report.
- [~] Operator: Fullscreen Edit of Now Playing beside the Media widget's Edit; the seekbar.

### 1B.8 Light themes are practically opaque in the saver (not started; cause found in research)

Cause (arithmetic, not yet pixels): `SurfaceContrast.js` cannot reach its 4.8:1 target for dark ink at 55% alpha
even on white, so it saturates and `surface_material.frag` fills the card interior white. The Settings variant
corrects the ink and keeps the surface at its calibrated density (about .63-.72).

- [ ] a. Before set: off-screen card renders of Platinum Workstation, Polished Chrome, Pearl Blush and two good
  dark themes over one dark and one bright PERSONALSET wallpaper (`tools/surface_material_capture.py`), with
  the surviving wallpaper swing inside the card measured per theme.
- [ ] b. Bounded surface for dark ink: the panel moves toward the anchor only as far as the theme's
  Settings-variant shell density; the solver's unreachable case resolves to "bounded surface + corrected ink",
  never limit 1.0.
- [ ] c. Correct the ink, not the panel: darken semantic ink toward its theme anchor where it misses the ratio
  (the 1.7a runtime ink correction); judge faint ink at its real alpha, not a fixed 55%.
- [ ] d. Text-local plate (`TextLegibilityPlate` / `text_legibility.frag`) only where a run still fails over a
  busy backdrop; never a whole-card lift.
- [ ] e. Dark themes pixel-identical before and after.
- [ ] f. The SURFACE block identical across `surface_material.frag`, `text_legibility.frag`,
  `text_legibility.vert` (`tests/test_surface_materials.py`); `.qsb` files regenerated with the Qt toolchain.
- [ ] g. One focused GPU before/after on a busy card; no extra pass, capture or per-frame Python.
- [ ] h. After set + lead pixel review, light beside dark; `tools/theme_legibility.py` rerun on the composed
  surfaces.
- [ ] i. Docs: `Docs/Architecture/Card_Surface_Materials.md`; closes 1.7a's density question (update it there).
- [~] Operator look on the three light themes.

### 1B.9 Settings and Studio window corners bleed (not started; continues 1.9 with the +2 px allowance)

Both windows are rectangular layered HWNDs with Accent blur over the whole rectangle; `paint_forged_window_edge`
forges the rounded look (radius 6.5, 4 px border). Model estimate: +2 px leaves about 1 px at 150% and 3 of 8 at
200% by squaring the corner. A small native window is unavoidable here: Settings-sized, brief, never fullscreen.

- [ ] a. `tools/settings_native_corners.py` gains a Studio case and a border-width argument.
- [ ] b. Measure today, +1 px and +2 px at 100/150/200%, four theme/background cases each; crops kept.
- [ ] c. Tell the operator plainly whether thicker borders solve it; adopt a width only if it removes the
  escape rather than squaring the corner.
- [ ] d. If not: a region applied before the Accent call.
- [ ] e. If not: the Windows 11 DWM corner preference on a non-layered variant (cost check: shadow ownership,
  translucency, the layered-window repaint path of §9's freeze fix).
- [ ] f. If not: a composition-host clip.
- [ ] g. Whichever clips: input, resize, snap/maximise, DPI change, activation and Studio-over-Settings
  modality proven on the real `SettingsDialog` and Studio window.
- [ ] h. Window border material: the forged border ring takes 1.7b's border-material treatment (one rule for
  cards and windows), inside the +2 px budget.
- [ ] i. Docs: `Docs/Architecture/Settings_Theme_Architecture.md`; close or rewrite 1.9.
- [~] Operator look at Settings and Studio corners on both wallpapers.

### 1B.10 Presets (only after 1B.3-1B.6 land; one Fable 5.2 Medium agent above the roster cap, this task only)

Supersedes the lead's Spectrum presets 2-15 of 7 Nov (section 3). Every preset must read as unique and visually
impressive; the agent may ask the lead for a feature or architecture a better look needs, if it is not wasteful.

- [ ] Gate: 1B.3 side defects, 1B.4, 1B.5 and 1B.6 merged.
- [ ] Spectrum: presets 2 and up replaced with the best and most novel looks the mode can make (ghosts soft and
  blurred like Preset 1's; no seam where a transparent-border bar meets its ghost).
- [ ] Extruded Bubble: one arctic-themed preset.
- [ ] Neon Lake: three unique presets (using the shape instrument, far-land brush and the new land reactivity).
- [ ] Every preset authored through the Studio's Save To path, complete for every control (completeness guard).
- [ ] One showcase WebP per preset (`release_media.py`), reviewed by the lead before the operator sees them.
- [ ] Feature requests from the agent recorded here as their own boxes when admitted.
- [~] Operator look.

### 1B.11 Theme filter in the Linked row (operator request; built on an agent branch, in its refinement round)

Built: the shared term derivation, the filter on both pages, autocomplete, hidden-row rules, view-state only,
real-dialog tests. The lead's pixel review sent three things back (in flight, Opus Medium):

- [ ] Colour terms discriminate: the accent always counts, the surface only when clearly coloured ("Blue" listed
  almost every dark theme); a per-term distribution table for both catalogs, no family above about a third.
- [ ] Names match by word start, not any substring ("Red" found "Weathered Iron").
- [ ] The autocomplete popup is opaque (the list behind bled through its text in light themes), with a pixel test.
- [ ] Lead pixel review of the re-rendered set, audit (tests fail on pre-change code), merge.
- [ ] Side defect (red on main): `tests/test_surface_opacity_adjust.py::test_real_link_button_uses_state_ink_for_
  checked_text_and_lock_icon_offscreen` fails (worst contrast 1.58 against 4.5): the Linked button's checked
  text/lock ink. Fix with 1B.8's ink correction or at the link button's style owner.
- [ ] Side defect: the Weather location autocomplete (`ui/widgets/geocode_completer.py:52-69`) uses Qt's default
  popup (unthemed); give it the theme filter's popup.
- [ ] Side defect: `ui/tabs/widgets_tab_weather.py:157` hard-codes `#4CAF50` instead of a theme role.
- [~] Operator look on a real display (popup placement, scrollbar).

### 1B.12 Two fullscreen glyphs, one per display (operator; in flight, Opus High)

For the Expanded Visualizer now and SMP later: the target is a display, not "the Visualizer's display".

- [ ] A second glyph (diagonal arrow up-left) beside the existing up-right one, painted in the glyph row's
  style (no seams, strokes >= 1.5 px), Title Case tooltips.
- [ ] More than one display: both show; up-left expands onto Display 0, up-right onto Display 1, from whichever
  display the card is on, through the existing transfer + expand transaction (no second path).
- [ ] One display: the single existing glyph exactly as today (operator: "Keep it").
- [ ] V still expands on the display the Visualizer is on; displays beyond the first two are reached with V.
- [ ] While expanded: the expanded display's glyph collapses; the other moves the expanded view there; the
  Edit holds of 1B.1 still refuse a transfer.
- [ ] The glyphs fade in and out when the display count changes.
- [ ] The owner request is "expand on display N" (the shape SMP will reuse).
- [ ] Off-screen PNG evidence at 100% and 150% with 2x crops (one display, two displays, expanded); lead pixel
  review.
- [ ] Lead audit, merge; plan 01 updated.
- [~] Operator look on two monitors.

### 1B.13 Hold right-click to pan the live Visualizer (operator; queued behind 1B.12, same agent)

The context menu's reliability and speed rank above this feature. Design: menu on button-up, only over a
pan-capable Visualizer card; everywhere else the menu opens on press exactly as today, untouched.

- [ ] Baseline first: press-to-menu-visible timing on the untouched path recorded.
- [ ] Over a pan-capable card (not in Edit, not exiting, no menu open, mode has `scene_transform_settings`) a
  right press opens nothing and arms a pending pan.
- [ ] Travel past the system drag distance while held becomes the pan (the existing pan baseline
  `_quick_scene_view_gesture` and the one pointer-capture owner); no menu for that press;
  `context_menu_active` never true.
- [ ] Release ends the pan through the live view-pose owner's existing save rule (no new persistence rule).
- [ ] Release without that travel opens the retained menu at the release point through
  `context_menu_requested`.
- [ ] Pan feel (direction, scale per pixel, limits) matches the Studios (`ui/studio/viewport.py`).
- [ ] No timer or hold delay; no menu flash-and-dismiss.
- [ ] The pan cursor goes through the cursor owner and ends on R-183's retire path.
- [ ] Existing context-menu, R39 hover-handoff, double-right Edit and single-menu-per-display tests pass
  unchanged.
- [ ] New tests: click (menu once, on release); drag (pan, no menu); press on the card, release off it; second
  right press with the menu open; double-right over the card; focus loss, mode switch, exit and display loss
  mid-pan; the expanded card; Media Center mode.
- [ ] After: press-to-menu-visible on the untouched path equal to the baseline; release-to-menu-visible on the
  card reported.
- [ ] Docs: `Spec.md` / `Docs/Contracts.md` input routing.
- [~] Operator feel check.

## 1A. Miscellaneous repair slices (operator, 9 Nov)

These repairs run alongside the existing audit/native-worker work above; they do not replace or reorder it. Live
checklist: one box per open step. Each confirmed slice gets its own reviewed checkpoint; keep material changes
(1.7) in a separate checkpoint.

### 1.0 Rotate in ordinary and fullscreen Edit

Focused proof exists for renderer pixels at non-square extents, prepared Scene3D resources, per-mode Save/Cancel and
all Studio frame builders; the physical stage and camera remain fixed. Extruded Spectrum retains its frameless
overflow policy.

- [~] Operator: check Rotate in every mode except Sphere, in ordinary and in fullscreen Edit.
- [~] Operator: check the rectangle/quarter-turn glyph against Reset Camera.

### 1.0b Studio Rotate control

Off-screen proofs cover non-square production pixels, input transforms, preparation barriers and canonical saves.
Preview orientation is per-open state, separate from camera/artwork and desktop CUSTOM orientation; Copy Frame
captures it.

- [~] Operator: check Studio's Rotate control in every mode except Sphere.
- [~] Operator: check upright handle labels.
- [~] Operator: check rotated brush/drag feel.

### 1.1 Mode switch with no direct cause (Awaiting Logs)

- [ ] No direct mode-switch cause in the supplied archive. On recurrence, correlate the reported time, prior/result
  mode, selected preset and runtime generation with the existing mode-transition owner and frame trace.
- [ ] Distinguish explicit selection, enabled-mode normalization and Settings restoration first.

### 1.2-1.3 Frozen-install validation only

Durable behaviour: `Docs/Reference/Visualizer_Studio.md`; evidence:
`Docs/Audits/Studio_Camera_And_Fullscreen_Overlay_Self_Audit_2026-11-09.md` and
`Docs/Historical_Bugs/R-182_Installed_Preset_Files_Lacked_User_Modify_Permission.md`.

- [~] On freshly installed Standard and MC builds as an ordinary Windows user: confirm the installer grants Modify
  on the shared ProgramData Visualizer preset tree **and its existing files**.
- [~] Save and Save Camera over a shipped preset.
- [~] Save As and reopen. Source-level file/Qt checks do not establish installed ACLs.

### 1.4-1.5 Remaining fullscreen visual acceptance

Existing Settings/input/text-layout/Edit checks are green; actual Windows full-layout acceptance is still owed.

- [~] Operator: Media Bar and Floating Glyphs styles.
- [~] Operator: long metadata fitting.
- [~] Operator: multiline Edit boxes and optional album, including Save/Cancel.

### 1.6 Achievement Pulse child placement

The enabled-row regression is green; other families' extent floors are static.

- [~] Check child placement after Settings/fullscreen return with `--geo` (replaying the saved payload on Edit
  entry must not change the canvas; disabled provider fields must not count as painted capsule rows).

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

- [~] Operator: compare the supplied widget material screenshots with current cards, especially the good
  Glass/Frosted volume surfaces, Glass inset/distortion, and Studio panels/tabs/headers/wells.
- [~] Operator: exercise Settings Opacity Adjust and Widget Opacity Adjust in Style Overrides (-1..1, neutral 0).
- [~] Operator: live Studio material switching, snap and resize.
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

- [~] Operator: top grips reorder.
- [~] Operator: solid-span endpoints change start/width and truncation.

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

### Side defect: Build Runner's Inno discovery

- [ ] Build Runner's Inno discovery still reads `SRPSS_ISCC_PATH` (`tools/build_runner.py:1012`) and a test requires
  it. Replace that tool override with explicit CLI/sidecar admission when opening its owner.

### Awaiting Validation after the focused proofs

- [~] Operator: the changed glyphs.
- [~] Operator: saves in the frozen build.
- [~] Operator: camera/child placement round trips.
- [~] Operator: long fullscreen metadata and controls.
- [~] Operator: material comparisons on native pixels.

## 2. Awaiting the operator (eyes, ears, hardware, decisions; details stay at the item)

One line each; the detail and evidence live in the section named. Nothing here needs an agent until the operator
answers.

- **GitHub Remote builds (8 Nov, proven end to end):** Build Runner's third tab and
  `tools/github_remote_build.py` compile Standard/Media Center on GitHub runners, validate and publish them, and
  compile opted-in installers locally (`Docs/Guides/GitHub_Remote_Build.md`). Lead's headless run from the Build
  Runner CLI on e9bbd7a4: both remote builds downloaded, validated (manifest + PE version) and published, and both
  installers compiled locally (`release/installers/Setup_SRPSS.exe`, `Setup_SRPSS_Media_Center.exe`). The run before
  it showed the installer gate refusing a Standard installer whose presets had changed after the remote build.
  Open: the operator installing a remote-built product. Since checkpoint audit 11 (8 Nov) the tab's Linux job runs
  beside the Windows runs on its own process owner (never holding their retrieval) and a stop cancels its run even
  before it was followed; tested with fakes only, so the next Remote run with Linux selected is its first real one.
- **Read:** Bubble / Extruded Bubble "terrible performance" (6 Nov log 10:32-10:35) was our load (97-100% system CPU
  from the agents' game60 checks), not the product: on the quiet machine Bubble P1 ran 65.9 fps, tick 1.47 ms, GIL
  0.13, 3.9% late; Extruded Bubble 45-69 fps (`.artifacts/evidence/performance/live_check/20261106_live/`). Heavy load-generator runs are
  scheduled by the lead only.
- **§4 Slow startup:** a cold start with `--usage` (no `UI_CALLBACK` / `FEED_GUI_DELIVERY` line over a frame).
- **§4 Displays off:** the overnight check with the power plan's display timeout (`--frame-trace --usage`).
- **§4 Spline Curve (`devcurve`) "more alive":** eyes after the lead's review.
- **§4 Frozen builds:** open a Studio from a fresh build.
- **Materials/Studio:** native operator comparison at section 1A, item 1.7; Settings corners remain open at item 1.9.
- **§4 Extruded Bubble Deep Red Ocean (Preset 9):** eyes on the second pass.
- **Framed aperture on the saver card (8 Nov, decision):** the writer is fixed (R-181: the Visualizer's uniform-scale
  minimum is absolute, and settings load lifts stored cards to it). That alone does not restore the saver card's 45°
  look: the repaired 592x592 card holds a 1480x1480 world (0.4 px per world unit, aperture 5.29), still at the 90° x
  90° cap and visually the same as before (`.artifacts/evidence/architecture/framed_camera/20261108_scale_repair/`).
  45° on that card needs about 2.11 px per world unit (a 280-unit world). Decide: bound the framed aperture (or the
  vertical view) as well, or leave it to Edit (Restore Size, wheel up, side drag back to the wanted width).
- **§1 8b P2:** decide whether to size the frame-age gain with a matched-GPU repeat game60 pair; gates 3/4 and their
  measurement limits are in the design record. The Windows default and H1/H2 repairs are already integrated.
- **§7.1 Waveform:** Preset 4 trade-offs of the fixed-scale v7 (sign off or ask for the tag's exact dynamics);
  Preset 7 and the Reaction Modes; Breathing; four-ribbon Preset 3; Particles; Strands; Colour/floor/mist; Fixed
  response; Floor Give; Pulse Rim; swell visibility; Travel Direction; Unified atmosphere.
- **§8 Bubble:** R-170 eyes-on (tall, wide and TV cards); Particle glow.
- **§9 Studios:** Neon Lake (`shockwave_grid`), Extruded Spectrum, Spectrum, Spline Curve and Oscilloscope Studios; the migrated Settings
  pages; Open Studio in the preset row and the Save To flow; the seamless clip loops; the chrome; the drag feel; the
  terrain brush.
- **§5 Frozen release gate:** operator-run builds and installer checks.

## 3. Lead and agents: active, paused and queued work

**Agents (operator, 11 Nov; replaces the 9 Nov roster):** the lead is orchestrator, auditor and final reviewer;
all agent results pass that review before acceptance. At most one Fable High (complex/architectural/visual), one
Opus 5.5 High (general high-quality work), one Opus 5.5 Medium (simpler/brute force) and one Sonnet Medium
(documents and research only); reuse a loaded agent for related slices. Above that cap (operator, 11 Nov): one
dedicated Fable High for the native-core sequence (§1 8b, "Remaining sequence", in its order; it reports at each
numbered boundary for the lead's audit), and one Fable 5.2 Medium for 1B.10's presets. Agents run only the tests related to what
they changed, never `--isolated`, never take over a display (off-screen renders and captures), and record side
defects here instead of ignoring them. Wait for agent reports without status polling.

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
  - [ ] Neon Lake (`logical_frame_capture.py`, `shockwave_frame_runtime.py`).
  - [ ] Oscilloscope.
  - [ ] Sphere.
  - [ ] `tools/labs/waveform_ribbon_recorded_input.py` still uses `musical_weight` and no longer matches production.
- [ ] **Vocal-band scorer into the music-response tool (8 Nov):** the PCM vocal-band (300-3400 Hz) series behind the
  mid-led routing evidence and guide §2C lives only in scratch (`lead_audit/vocal_band.py`); add it to
  `tools/visualizer_replay/waveform_music_response.py` as a lane so it survives scratch pruning.
- [ ] **Tool-output contract reds (found 8 Nov on `610e38c0`, not fixed there):**
  `tests/test_artifact_paths_contract.py` fails 3 tests. Route each through `tools/artifact_paths.py` and
  `tools/evidence_media.py`, or allowlist it there with its reason:
  - [ ] `tools/github_remote_build.py` hard-codes `logs/` (lines 200, 249, 703).
  - [ ] `--out` / `--json` bypass `tools/artifact_paths.py` in `github_remote_build.py`, `theme_legibility.py`,
    `vulkan_shader_readiness.py` and `visualizer_replay/{engine_main_cost,engine_worker_gate,live_engine_cost,
    live_engine_gate,owner_production_replay,owner_worker_gate}.py`.
  - [ ] `owner_worker_gate.py` writes PNG without `tools/evidence_media.py`.
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
- [~] **Awaiting Validation:** live Style Overrides/theme changes must reach Visualizer and Context Menu material
  in the current display generation (`_configure_quick_auxiliary`), including the new global opacity override.
- [ ] Extend actual faint-run pixel checks to light widget themes beyond the sampled Gmail/Media cards. Keep
  authoring-mirror failures separate from runtime material guards; contract:
  `Docs/Architecture/Card_Surface_Materials.md`.
- [ ] **Spectrum presets 2-15: re-authored by the lead (7 Nov); to be replaced under 1B.10 (operator, 11 Nov).** The
  features (flag sheets, hue-preserving gradients, rim glow cap, Bar Fill ghosts;
  `Docs/Reference/Visualizer_Reference.md`) stay; every preset carries Preset 1's reactivity unchanged (only look keys authored). Evidence:
  `.artifacts/evidence/visualizers/spectrum/presets/20261107_lead/` (contact sheets, motion strips, metrics, the
  authoring script) and `D:\Temp\Scratch\SRPSS\evidence\visualizers\spectrum\20261108_ghost_v2\` (`before/`,
  `after/`; falling instants beside Preset 1 with 2x ghost-top crops).
  - [~] Operator's eyes on the re-authored presets (Silhouette is the plainest by concept).
  - [~] Operator's eyes on the ghost fix for his 8 Nov verdict on v2: "Those ghosts are too solid and not blurred."
    The Bar Fill ghost must read like Preset 1's: soft, blurred, translucent (no crisp stripes or stars inside it),
    fading sooner, with no ~1 px dark seam where a transparent-border bar meets its ghost (merged as 092304dc;
    evidence `20261108_ghost_seam`). The same bar binds the replacement presets under 1B.10.
- [~] **Waveform agent (Opus medium, worktree `agent-af0eb2492e1e318d7`, branch
  `worktree-agent-af0eb2492e1e318d7`), operator decisions from the 7 Nov follow-ups** (evidence:
  `.artifacts/evidence/visualizers/waveform_ribbon/followups/20261107_followups/`; raw captures not kept):
  - [~] Preset 4 rides about .7 higher at p90 and stops dipping into the floor: sign off.
  - [~] On a small 640x560 card, P5 and P6 cannot fit either way: crests now graze the top on 14-47% of frames,
    against floor contact before. An authoring choice; no reaction was shrunk: sign off.
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
- [ ] Lead audit of the Gmail IMAP interruptible-session fix (branch `worktree-agent-ab77df54c8fe5d4a6`, merged as
  64950529; the plan recorded it as awaiting the lead's audit; contract `Docs/Contracts.md` Network transports).

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

- [~] Preset rollback recovery copies go to `%TEMP%`: `core/visualizer_preset_tree.py` writes the before-images of a
  failed preset-replacement rollback to `tempfile.mkdtemp(prefix='srpss_preset_recovery_')` and names the folder in
  the error. It is user-facing recovery data in a folder Windows Storage Sense may empty and nothing ever removes; a
  location beside the preset tree (or the data root) may be intended. Product behaviour unchanged pending the
  operator's call (the test redirects it to `tmp_path`).
- [ ] Hidden cross-test dependency on an earlier test's `tmp_path` (lead, 7 Nov): with pytest's
  `tmp_path_retention_policy = failed`, `test_3d_curated_preset_ownership.py::...promotes_missing_owned_temporal_
  and_profile_keys...[shockwave_grid]` (0.7 vs 0.23) and two or three `test_settings_dialog.py` tab-restore tests
  fail; each passes with the default retention, so something process-scoped keeps a path into an earlier test's
  `tmp_path` (a cached preset tree or storage root). The setting was reverted. Find the cache and give each test its
  own root; this may also hide state leaking between tests.
- [~] A third evidence root lives in `Docs/`: `Docs/Reference/Extruded_Bubble/Evidence/2026-10-20/` (ignored media,
  referenced by `Docs/Reference/Extruded_Bubble/Investigation.md`). Not part of the 7 Nov migration mapping; move it
  into the layout (`visualizers/extruded_bubble/...`) on the operator's word.
- [ ] Dead evidence references (the folders no longer exist; `tools/artifact_migration.py refs` lists them):
  `logs/evidence_chest/08_*` in Historical_Bugs R-53/56/57/58/59/60/62, `.artifacts/evidence/{ribbon_path,
  ribbon_frames,ribbon_strip,expanded_visualizer,oscilloscope}` and several `waveform_ribbon/wr*` folders in
  `Docs/Reference/Ribbon_Path.md`, `Waveform_Ribbon_Lab_Plan.md` and
  `Waveform_Ribbon_Mist_Failure_and_Replacement.md`. Left unchanged; prune or mark historical on review.

**Naming follow-ups (naming-audit agent, 7 Nov; `Docs/Reference/Naming.md` is generated and test-guarded):**

- [~] Operator's call: Neon Lake vs Neon Lake (edit only the registry `display_name`, then run
  `tools/naming_reference.py --write`).
- [ ] The "Spotify Visualizer" widget label and Spline Curve's Ghost tooltip ("for debug visibility") are audit #6,
  not done.

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
- [ ] The expanded card inherits the Visualizer card's surface material (it was a plain rectangle): confirm the
  expanded card shows the theme's material with no M2 change now that cards have materials.

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

- [~] A Card on a material shows the wallpaper, not the Visualizer: the shared backdrop is the wallpaper layer only
  (`Docs/Architecture/Card_Surface_Materials.md` §3), so on Glass over an opaque mode (Extruded Bubble) the card is a
  blurred wallpaper the Visualizer hides everywhere else. It reads as a tinted panel (evidence still
  `extruded_bubble_06_card_glass.png`); the operator's look decides whether that is acceptable.
- [~] Right-hand corners sit further in than left ones: they keep clear of the card's hover-revealed controls (about
  80 px from the top edge for the collapse glyph, its tip and the 3D hint; the bottom for Reset Camera, the preset
  steps and their tip). Fullscreen Edit (M3c) can move an overlay; revisit if the operator finds the gap odd.
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
- [~] The expanded card's hover Edit lane stays withdrawn (operator's call if wanted back). The rotate glyph the
  operator missed is now on the expanded card in Fullscreen Edit (plan 01 M3c, "Rotate Widget Content"); the
  ordinary Visualizer's hover lane never offered rotate. What the display-wide card still does not show outside Edit
  is that lane (Restore Widget Size, the transfer arrows), withdrawn since M2 because each edits the ordinary card's
  layout, which the display-wide view does not draw (Restore would resize a hidden card, transfers are M5).
  Returning it needs a decision on what each does while expanded.
- [~] A pause does nothing to the overlays (by the spec, not built): Now Playing is event-only and has already faded
  after its window; with Always Show it stays up by definition. A fade-out on pause would need the operator's word.
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

**Slow startup (operator, 6 Nov 10:30; owners fixed, awaiting the operator's cold start)**

Evidence `.artifacts/evidence/lifecycle/slow_startup/20261106_slow_startup/`; the held-lock rule is in
`Docs/Guardrails/Performance_Optimization_Contract.md` section 5, the optional-worker start in its appendix.

- [~] Operator: cold start with `--usage`, then read the log:
  - [~] No `UI_CALLBACK` / `FEED_GUI_DELIVERY` line exceeds a frame. The 166-240 ms `FEED_GUI_DELIVERY` lines at
    10:30:40-42 were not reproduced offline (Feeds cache delivery including the NEWS card model is 0.1-15 ms per
    source at 18 publishers x 40 stories; `_complete` excludes QML) and are treated as the post-block backlog on a
    97-100% CPU machine.
  - [~] The first `collect_ms` is small.
- [ ] Side defect: a prefetch batch asked for before the optional image_prefetch child is ready fails as "not
  running" (a logged `[PREFETCH]` error); that batch is not retried.

**Displays off -> presentation pauses entirely, resumes clean (built 5 Nov; awaiting the operator's overnight check)**

Contract: `Docs/Architecture/Compositor_Architecture.md` -> Display power (hardware findings 6 Nov are recorded
there). Evidence `.artifacts/evidence/display/display_power/20261105_display_power/`.

- [~] Operator: leave a heavy preset (Waveform Ribbon (`waveform_ribbon`) Preset 1 or Neon Lake (`shockwave_grid`))
  overnight and let Windows' screen timeout turn both displays off (not the panels' own buttons: an HDMI panel that
  stays enumerated gives no signal and the TV rejects DDC/CI queries; operator decision 6 Nov: no Screens Off
  command, the burden stays off the user; they enabled the power plan's display timeout and will report how SRPSS
  handles it). Run with `--frame-trace --usage`, then check:
  - [~] Task Manager CPU/GPU for the saver while dark.
  - [~] Wake input reaches the saver.
  - [~] The first seconds after wake: no stale frame, jump or hitch.

**Spline Curve (`devcurve`) "more alive while keeping the flow" (second cut 6 Nov; awaiting lead review, then
operator eyes)**

Contract: guide section 13D -> DevCurve. Evidence and before/after WebPs (loud end and a quiet passage, P1/P6):
`.artifacts/evidence/visualizers/devcurve/reactivity/20261105_reactivity/` (`PROGRESS.md`).

- [ ] Lead review of the second cut.
- [~] Operator eyes on the second cut.
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

- [~] Operator: open a Studio from a fresh build.

**Widget/Settings material appearance: Awaiting Validation**

Active density/composition work and native evidence: section 1A, items 1.7/1.9. Durable owners:
`Docs/Architecture/Card_Surface_Materials.md` and `Docs/Architecture/Settings_Theme_Architecture.md`.

- [~] Operator, in the running app:
  - [~] The inner rim.
  - [~] Transport, mute and volume.
  - [~] Dark and light palettes.
  - [~] Linked material choice.

**Awaiting Validation, material cost under load**

- [~] A lead-scheduled transition-heavy material/Normal pair, only within the separately approved measurement
  session. Small off-screen GPU timings do not replace it.

**Widget theme legibility (open)**

- [ ] Theme the Weather detail asset icons: they remain white and become faint on pale cards.
- [ ] Re-author raw linked Widget Theme roles that fail `tools/theme_legibility.py`, especially widget.accent on
  widget.panel/header surfaces; do not equate runtime ink correction with a corrected raw mirror export.
- [ ] Fix light-theme widget shadows, then inspect actual faint text over the resulting cards; analytic panel
  contrast alone does not account for the shadow's effect.

**Extruded Bubble: a deep red ocean preset that truly matches the mock (operator 6 Nov, not urgent); second pass
done, awaiting operator eyes**

The mock is `Docs/Reference/Extruded_Bubble/Targets/Originals/Preset7Goal.png`. Preset 9 (Deep Red Ocean) only;
Presets 1-8 stay pixel-identical. Shared controls, each dormant at 0: Ember Grain, Ember Band (Water), Lit Glass
(Glass), Stream Lanes, Wake Tint (Bubbles), Hero Shell with Hero Across/Height (Lens). Details, numbers,
reactivity and cost: `Docs/Reference/Extruded_Bubble/Investigation.md` sections 72-73; evidence
`.artifacts/evidence/visualizers/extruded_bubble/deep_red_ocean_pass2/20261106_deep_red_ocean_pass2/`.

- [~] Operator eyes on Preset 9 against the mock.
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

- [ ] **Neon Lake (`shockwave_grid`) camera step on real music (found 6 Nov, pass 7, pre-existing at 0776da08):** Preset 1 on
  1985_loud1 between 42.054 s and 42.075 s the whole land shifts ~8 px down in one frame and stays (mean step 8.5/255
  against ~1.3; replay parameters and presentation identical across the two frames, Terrain Reaction bands smooth).
  Find the owner (camera floor / reaction normalisation) with `tools/neon_lake_capture.py --clip ... --start 41.9
  --duration 0.3 --fps 90 --all-frames`.

- [ ] **Neon render tests load-sensitive under parallel runs (5-6 Nov):** `test_neon_lake_renderer.py` (once, pass-5
  merge gate) and `test_neon_scene_materials.py` (once, pass-5 branch) failed under parallel load and passed alone; the
  re-run overwrote each log, so the failing test is unknown (most likely a QSG clip probe timing out). The isolated
  runner now keeps the parallel-run failure as `logs/pytest_isolated/<file>.under_load.log`; next time, read it and
  fix the probe's timeout or synchronisation rather than rerunning.
- [ ] **4x MSAA repeat-render noise (driver, 5 Nov; was "Floor Give run-to-run noise"):** the same frame rendered
  again through a 4x scene target differs by 1 level (rarely 2-3) on a pixel or two in Waveform (more often with Floor
  Give and mist) and on ~0.7% of pixels in Neon Lake. Not renderer state: packet, uniforms, every vertex position,
  fields, fog volumes, reflection and all four depth samples are bit-identical, single-sample renders are exact
  (`test_floor_give_repeat_renders_are_renderer_deterministic`), and no barrier/finish/stream pinning changes it; the
  multisampled colour itself flips up to 3/255 per sample. Per-sample Waveform floor shading removes it there but costs
  +1.2 ms (give off) / +2.0 ms (give on) at 1080p, so it was not taken. Tests compare such renders with
  `tests/_msaa_render_noise.py`. Reopen if a driver update or another GPU shows it gone or larger.

- [ ] **Display Settings capacity (physical hotplug):** on a real monitor disconnect/return or explicit reauthoring,
  Settings' current-screen rows and selections/bindings stay coherent (focused checks pass; hidden form evidence
  `tmp/pytest_ux30_display/test_display_ui_rows_follow_to0/six_display_rows.png`).
- [ ] **R38 hover display-transfer glyphs (physical topology):** watch glyph hit/tooltip/fade and transfer on
  unequal-DPI screens and monitor unplug/return (equal-DPR pair passes; `tmp/ux30_actual_displays/receipt.json`).
- [~] **Steam Games You Follow images:** many update entries lack images. Audit URLs, redirects/statuses, cache keys,
  game IDs, fallbacks, dedupe and selection order (including artwork fetched but rejected downstream); prefer
  image-bearing updates without suppressing legitimate no-image entries; instrument attrition, compare natively with
  Feeds. A generic game cover existing is not proof an image is missing.
- [ ] **Steam artwork 404** for asset hash `9b4a68b51c5f` (23 Oct MC run, `logs/run_matrix/2026-10-23_idle_hint_shaft/`)
  and earlier `4b349d51e996` / `3f5b734df3c5`: stale metadata vs genuinely missing CDN asset, before changing lookup.
- [ ] **Monitor power/wake:** display off, > 30 s off, rapid off/on, reordered return, both selected displays absent:
  widgets keep physical assignments and CUSTOM geometry. On recurrence record timestamps, remaining screen, flavour,
  Interaction Mode and wake/exit input (history: R-79).
- [ ] **Refresh contention:** correlate FEEDS/Gmail/Reddit queue/claim/publish/retire with transition delays in a natural
  dual-display trace (fairness, no post-transition stampede, retained last-good content).
- [ ] **15 s usage-sample hitch (unexplained, not reproduced):** 31 Oct 19:28-19:33 MC run, a 95-121 ms freeze of the
  GUI, render and logical threads at every `--usage` sample (20 in 5 min, `gui_stall_stacks.log` and frame trace
  agree). Each sample took ~95 ms because the sampled tree held 7 processes / 233 threads (normal 3 / ~55, ~16-24 ms);
  the four extra descendants used the GPU (counters 17 → 70), existed from the first sample and are unidentified.
  The next MC run (19:47) and an invisible live check on current code were normal. On recurrence the sampler now
  logs `[USAGE] topology added ... name= parent= threads=` for every process entering the tree: identify them, then
  decide whether the sampler must exclude/outsource them. Not the Extruded Bubble chain fix (no processes, tick unchanged).
  Seen again 8 Nov with a normal tree (P2 gate 3's game60 pair, design doc step 6 "Gate 3 record"): every sample in both
  runs stalled the render thread 71-106 ms in the scene render (13 of the worker path's 23 hitches, 14 of in process's
  39); `collect_ms` ~13 ms per process walked at 87% system CPU (58 ms for 4-5 processes with the engine worker, 46 ms
  for 3-4 in process; 23 ms for 4 on an idle machine). Main-side on both paths; the engine worker adds one process to
  the walk.
- [ ] **Cross-display Media shortcuts** delivered once on the other display, when exercised.
- [ ] **Music recorder** 60-second clip, signal/history, cancel and mixed-DPR UI, when recording is needed.
- [ ] **Helper breadcrumb diagnostics unavailable:** current native MC evidence logs no access to
  `C:\ProgramData\SRPSS\logs\scr_helper.log`. Inspect the helper/log-path authority before relying on that
  diagnostic route; do not hide it behind a silent local fallback. Separate from Waveform rendering.
- [ ] **Frozen release gate (operator scheduled):** Standard/Diagnostic from one compile, MC and Reddit Helper installed
  startup/exit, Settings/widgets/cache/audio and installer behaviour.
  Check installer logs and obsolete-file removal in both curated theme/preset trees. Both sources declare whole-tree
  replacement; verify Diagnostic now reads that installed theme tree too.
- [ ] **Conditional evidence only:** original Bubble tiny-radius judder (R-105) and dual-display reboot recovery
  (R-134–R-145) need new reproductions. The 90 Hz versus 60 Hz investigation stays off limits.

## 6. Shared 3D architecture (one step, before the next mode; after Expanded Visualizer, under port-readiness rules)

The architecture planned for the dropped concepts (volumetric music chamber, audio aurora/ribbon volume, photo
fracture portal, voxel morph field, holographic depth slices, procedural storm, reactive particle field,
terrain/skyline/tunnel, deformable blob sphere) is worth having; the modes were not. Build it here as shared primitives
on the existing Scene3D substrate (`Docs/Reference/Scene3D_Resources.md`): `MeshResources`, `SceneTarget`, depth-aware
OIT, probe, defocus, HDR intermediate, framed camera. Each primitive is proven on **its own offscreen harness** with
bounded, measured cost (TIME_ELAPSED, median/p90), lazy creation, zero dormant work and clean retirement; none waits for a
consumer, and none becomes a second renderer, clock or camera. Read the 3D foundation lessons in
`Docs/Reference/Transitions.md` before each slice. Order follows which mode needs them first.

- [ ] **S3D-1 Ribbon / strip primitive:** finish the reusable camera-facing width variant, shared defocus integration,
  lifecycle/admission proof and bounded cost around the existing history/ring/oriented-strip substrate. Preserve a bounded
  history SSBO, centripetal Catmull-Rom placement by continuous index, OIT translucency, multi-ribbon support and fixed
  maximum history. *Consumers: Waveform Ribbon; trails anywhere.*
- [ ] **S3D-2 Particle population extensions (G4):** inventory the existing compacted-population/sprite/streak
  helpers first; add bounded lifetimes, emitters, transient bursts, indirect draws and compute-driven arrangement
  (morphing a fixed population between shapes, from the voxel morph concept). Deterministic admission/retirement.
  *Consumers: ribbon sparks, rain droplets/crowns, melt droplets.*
- [ ] **S3D-3 Static scene geometry and materials:** authored static meshes (slabs, curbs, walls, recesses, wells,
  simple skyline/tunnel slices) with their own roughness/bevel/contact shading, built once and retained; photo-textured
  shells/planes with real depth (from the fracture portal and depth-slice concepts). *Consumers: Melt Pool chamber,
  Concrete Rain street.*
- [ ] **S3D-4 Dynamic surface field:** a bounded GPU height+velocity grid (compute or ping-pong), impulse injection,
  damping/return, a displaced mesh with normals from the actual surface, and an opt-in deformable sheet for shapes a
  heightfield cannot make (from the deformable blob sphere concept). *Consumers: Melt Pool body, Concrete Rain
  ripples/puddles.*
- [ ] **S3D-5 Reflections and wet surfaces:** a bounded planar/probe reflection for floors and pools, wet-surface and
  puddle masks over authored ground, and reflection-distortion sampling driven by a surface field. No screen-space trick
  that collapses under camera motion. *Consumers: Waveform Ribbon floor (next: §7.1), Melt Pool, Concrete Rain.*
- [ ] **S3D-6 Shared shadows (G2 / S25):** one fitted directional depth map, bounded soft PCF/bias, caster/receiver
  admission, resize/teardown/dormancy and tier cost on a real test scene (also Usu's S25; not a revival of the rejected
  Extruded cast shadows).
- [ ] **S3D-7 Reduced-resolution volumes, then lightning (G5):** prove the bounded static fog slice required by Waveform
  Ribbon first, with no audio reactivity. Then add bounded procedural bolt geometry/light and fog/smoke volumes with
  advection/reprojection and no permanent extra targets or separate cadence. *Consumers: chamber/street atmosphere.*

## 7. Visualizer modes (one at a time, in this order)

### 7.0 Method: lab first, then production

Extruded Bubble's lab (`tools/labs/extruded_bubble_lab.py`) reached the mocks long before production did; production
then closed the gap by measuring against both. Do the same for every new mode:

1. **Target first:** the mock/concept package and its low/high pair; write the mode's contract and hard gates (from its
   brief) into its focused doc before code.
2. **Lab:** `tools/labs/<mode>_lab.py` composes the target scene by hand, offscreen, from the shared primitives, with
   free knobs and no Settings/preset plumbing. Reuse the context/target and ownership contract in
   `Docs/Guides/Visualizer_Labs.md`. Iterate on rendered stills (mock | lab sheets) until it is close.
3. **Production through the shared substrate:** typed Settings, presets, the logical clock and lifecycle. Diff the lab's
   effective knobs against production's key by key; judge with **mock | lab | ours** sheets per preset, the per-mode
   capture tool (`tools/<mode>_capture.py` on recorded real music) and measurements (regional colour, on-screen size
   bands, Range audits), as in `Docs/Guides/Visualizer_Visual_Tuning.md`.
4. **The lab is a waypoint, not the goal:** keep going toward the mock; keep the lab (it costs the product nothing).
5. **Same-scene low/high proof, measured cost, dormancy and retirement** before calling any stage done, including the
   live-shape check under the calibrated game load (`tools/visualizer_live_check.py --load game60`, budgets in
   `Docs/Guides/Visualizer_Change_Checklist.md` 1C); the operator gives final sign-off.

### 7.1 Waveform Ribbon (next)

**Live rejection checklist - Awaiting native validation/operator judgement (2 Nov).** This is the single live
list of reported failures, proposed corrections and required evidence (updated 3 Nov). Tests establish mechanisms, not visual acceptance.
Work first on body/audio/accents, then grounded camera/viewport and replacement atmosphere. Binding references:
`Docs/Guides/Visualizer_Reactivity_Authoring.md` sections 13A-13C; control/design ownership in
`Docs/Reference/Waveform_Ribbon_Migration_Plan.md`; motion targets and recorded bake-off in
`Docs/Reference/Waveform_Ribbon_Lab_Plan.md` section 5.1. Keep C-primary elastic response and A's accumulated twisting.

**Reactivity milestone baseline (operator, 5 Nov): tag `waveform-baseline-2026-11-05` (= `e598155d`).** Pulse and
Centre Out "like night and day"; logical cadence survives heavy game load; **Preset 4 is the reference** ("let us not
lose this"). Every later dynamics change shows, on the recorded clips, that Preset 4 is unchanged against this tag
(or names the improvement for operator sign-off). Preset 4 keeps Breathing 0 (exactly the baseline dynamics).

- [~] **Fixed-scale rework v7: accepted by the lead review 6 Nov (merged 840bd935); operator sign-off on Preset 4 and
  the trade-offs.** No adaptive memory (Adaptive Response toggle, off in every preset), fixed response fitted to main's
  visible behaviour, phrases widened about a heard-only 3 s mean, Kick Accent bounded at 15% of the roll (Preset 4 ships
  0), the floor lift bounded by the card's top edge (top edge first), the phrase mean catching up after real silence.
  The rejected v4's lessons (top edge first, fixed calibration fitted to what the replaced path visibly did, bounded
  kick channels) are in `Docs/Guides/Visualizer_Reactivity_Authoring.md`.
  Lead's own review on whole recordings against main (`tmp/waveform_review_20261106/`, gitignored: v7 frames in
  `branch/`, frame sheets, music-vs-response traces, `drift_*`, `chain7.npy`, `scripts/`; the agent's curated evidence
  in `.artifacts/evidence/visualizers/waveform_ribbon/reactivity_preset7/20261107_reactivity_preset7/`, PROGRESS.md):
  - crests clipped by the card's top: P7 Anything 66% (v4) -> 5.8% raw (main 2.9%), and the residual is sparks drifting
    into the top rows, not crests (crest clipping <= main in 8 of 10 recordings); frame sheets of P4 and P7 show main's
    dynamics, slightly fuller; music-vs-response at parity; no drift on a song replayed after 7 min; P4 roll identical.
  - every reaction mode (Centre Out, both Travelling Pulse directions, Group Wave, Whole Swell, Frozen Past's newly
    born swell; `modes/summary.txt`): correlation with loudness/RMS/bass at or above main (+0..+.04), saturation
    +0..+1.9 points (Group Wave's born swell 5.1% against 3.2%); Breathing adds +.01..+.02 correlation.
  - **Trade-offs for the operator:** Preset 4 visible amplitude p10/p50/p90 -4/+4/+5% and 3 s contrast +4.5% against
    the tag (inside the +-10% gate; sign off, or ask for the tag's exact dynamics); Preset 7 roll 1.12x; P7 saturation
    higher on two songs (10.2% / 6.8% against 3.4%); kick peaks 1.6-6.4% under main in 6 of 16 song-time bins (worst
    P7 0-15 s) and 6-11% over it in sustained loud bins; quieter-after-loud kicks 8-27% under main by design (a quieter
    passage is no longer re-normalised up); top-row spark density up to about 2x main.
  - Still open from the Range audit (item below): Rotation's drive never passes .36.
  - **Music-vs-response on main, every preset and Reaction Mode (7 Nov, after the tick cut).** chain7 (7 recordings
    back to back, continuous play), `waveform_music_response.py`, born swell for travelling/frozen modes; 16 runs (P1-7
    as authored; P1/P4/P7 forced to Frozen Past, Whole Swell, Group Wave/Travelling Pulse). Means over songs: correlation
    with loudness/RMS/bass +.34..+.49, saturated 2.2-8.2%, dead 3.7-10.6%, spurious 2.0-4.4%, re-scale gap .11-.25
    (P1 = the v7 numbers exactly). Mid-song kicks are not muted: the median born-swell rise per kick in every later
    15 s bin is 0.95-2.5x the first bin's (the first bin holds the intros). Findings worth the operator's eye:
    (1) Group Wave registers single kicks least: P7 as authored born rise .03-.06 per kick, P7 forced to Travelling
    Pulse .16-.30, and 46% of P7's kicks raise its born swell by under 1% of its range (Travelling Pulse 25%);
    (2) Whole Swell plateaus in flat loud songs (P6 song 2 saturated 20%, ws_P1 15%): the music's RMS is flat there and
    beats ripple the plateau, so it reads as sustained, not pinned; (3) song 1's sparse intro (big isolated kicks in
    the PCM) barely moves any preset while the carry-over from song 0 decays (re-scale gap .37-.50 on most presets);
    (4) the floor lift sits at its 1.5 cap for whole loud songs (P2 song 0, P6 song 2): the floor clipping item.
    Evidence `.artifacts/evidence/visualizers/waveform_ribbon/followups/20261107_followups/music/` (summary.txt, kicks.txt, report_*/ traces).
  - **Floor first (7 Nov, operator: "rather it goes a bit higher when it has to than clips"; supersedes top edge
    first): Preset 4 change for sign-off.** `TROUGH_LIFT_MAX` 1.5 -> 3; the card's top may take back at most 1.5 of the
    lift (`TOP_GIVE_BACK`, swept .3/.6/1.0/1.5); Floor Give (P2) and Static Height keep 1.5. Visible lower edge through
    the floor, chain7 continuous play, main -> now: 1282x1005 P1 21.0 -> .9%, P3 16.7 -> .3%, P4 7.8 -> .1%, P5 49.3 ->
    2.2%, P6 47.6 -> .2%, P7 7.3 -> 0% with no crest above the top on any preset; 640x560 P1 21.4 -> 3.9%, P3 16.4 ->
    5.0%, P4 7.3 -> 1.6%, P7 2.2 -> .2% with crests above the top on .2-1.1% of ticks (main 0-.1%). Rendered 640x560
    frames (the lead's v7 windows, crest-clipped share): P1/P3/P7 0-2.5% (main 0-.4%), P4 Anything 6.2% (main .4%:
    crests graze the top edge), P4 Rag Doll 2.1% (.4%). P5 and P6 do not fit a 640x560 card with any setting (floor
    32-43% and crests above the top 16-36% of ticks; rendered crest clipping 14-47% against main's 2-16%): authoring,
    their bodies are taller than that card. P2 (Floor Give) unchanged (72% contact is its yielding floor). Preset 4 for
    the operator: lift p50/p90 .75/1.48 -> 1.01/2.19 at 1282x1005 (the ribbon rides ~.7 world units higher at p90,
    at most 1.5 higher, in loud passages) and no longer dips into the floor (7.8% -> .1%). Evidence `.artifacts/evidence/visualizers/waveform_ribbon/followups/20261107_followups/`
    (floor/table_main_vs_final.txt, floor/sweep_640.txt, topclip_crest_640.txt, clipsheet_*.png, captures/).
- [~] **Preset 7 and the other reaction modes (operator log `logse7a84d332e.zip`, Rag Doll, 5 Nov) - awaiting
  operator eyes:** no decay/breathing in soft passages, sustained passages with changes read almost flat, and a swell to
  full power as the song got QUIETER. Preset 7 is Group Wave (song 31-123 s in the log; the recorded clip is song
  70-130 s). Causes: Group Wave's set envelope was built from the long-fade field with a peak-keeping blur, so the swell
  sat at its soft bound over the visible span (median/max .98) and the whole body inflated with Pulse Strength (bass);
  and the adaptive gain's 30 s memory re-normalised a quieter passage to loud reach. Fixed: Group Wave follows the fresh
  field (as Travelling Pulse); Breathing holds the gain memory through a quieter passage only, keyed to the slow
  passage level, never beat gaps (Preset 4, Breathing 0, is bit-exact with the tag).
  Evidence and per-passage tables: `.artifacts/evidence/visualizers/waveform_ribbon/reactivity_preset7/20261107_reactivity_preset7/`. Open: operator review of
  Preset 7 (bodies are smaller in loud passages now that the uniform inflation is gone: sustained-loud visible
  amplitude 6.4 -> 5.4); Whole Swell (Preset 6) sits at its soft bound in all music by design (one global level;
  de-saturating it barely changed the visible body, so it was left). Pulse-visibility WIP (branch
  `worktree-agent-a470c20ffe5fe8b02`) stays parked: the operator accepted the pulse as is.
- [~] **Breathing + anchored history ends (merged b1806449) — awaiting operator ears/eyes:** soft passages let go
  between swells (0.7 in every preset but 4) and, since the Preset 7 fix, a quieter passage after a loud one stays
  quieter (gain memory held); the tail no longer staggers at side angles. Evidence
  `.artifacts/evidence/visualizers/waveform_ribbon/breathing/20261105_breathing/`.

**Operator-selected recovery baseline (3 Nov):**
`Docs/Reference/Images/Waveform_Ribbon_Material_Baseline_20261103.png` and its `.capture.json` preserve the exact
chosen image/settings/source. Use this material direction; do not darken the background or lower the floor's colour
level. Floor brightness is provisionally approved, not the entire floor/atmosphere. Remaining lumps and reactive
detail still need improvement. Baseline settings are applied to Preset 3; retain this reference before further work.

- [~] **Four-ribbon maximum and Preset 3 — Awaiting Validation:** the candidate now admits FOUR cards across
  authoring/runtime/clearance/accent/range paths, preserving Presets 1/2's three active identities. Validate Preset 3 against
  `references/Preset3Goal1.png` and `references/Preset3ReactivityGoalExample.png`: teal/orange contrast, readable
  lattice/twist/strands/particles, continuous wet textured floor, and the large quiet-to-peak geometric change shown.
  The explicit operator maximum overrides the first board's decorative count label; use four for Preset 3's paired
  target. Native low/high/recorded captures must reach that range without pinning or swapping scene/camera identity.
  Four-card forward migration and a first Teal/Ember Preset 3 are implemented; preserve original three-card values
  and count in old state. The recorded draft still needs visual correction: white/rope-like overlaps, repeated
  continuation, weak/dark atmosphere and a poor floor/contact strip remain rejected. Do not equate source tests,
  particle/root counts or larger amplitude with reference fidelity.
- [~] **Reaction: travelling energy pulse + four Reaction Modes (5 Nov) — awaiting operator eyes/ears:** the R1/R2
  elastic motion was rejected as fundamentally wrong (sideways bursts from the retired axial stretch; standing bends).
  Beats launch swells that travel along the waveform and amplify its OWN crests/troughs through a broad envelope
  whose slope is capped so a swell never bends a curve inward; points slide along their own curve (shape-preserving,
  rate-limited); a narrower travelling light/colour/saturation band and gathered particles show where the energy is.
  Modes: Travelling Pulse (default), Frozen Past, Whole Swell, Group Wave; flow-rule and twitch tests for every mode.
  Dense music (5 Nov probe, ragdoll loud end): the light reads as one coherent front travelling at the authored speed
  with no standing glow at the emitter; a packetised release was measured (emitter share .41 -> .40) and rejected as
  machinery without a visible gain. 8 s strips (5 Nov, `modes_long/`): Frozen Past is distinct (held crests stay
  raised when the passage quiets); Group Wave was indistinguishable, so a swell now arrives as a SET (envelope 3.5
  carrier wavelengths, light across the set, stronger forward lean) and reviewed frame by frame. Audit doc decisions 7+; evidence `.artifacts/evidence/visualizers/waveform_ribbon/
  studio_20261105/modes/`.
- [~] **Particles (5 Nov candidate):** crest-weighted, distributed births in each ribbon's colour, visible
  >=1 px cores with soft halos, gentle fade; swells gather particles (Pulse Particles). Hot passages hold ~3.4x quiet.
  Pulse births only fill the cohort headroom left after the authored Spark Count, so they never mask it.
  Open: still sparser than the high-react reference (admission-limited).
- [~] **Strands: rare, 3-5 seconds TOTAL life.** Latest operator correction supersedes the proposed 30-second fade.
  Preserve the approved non-flickering look, make appearances much rarer, and use most of a configurable 3-5 second
  lifetime for a gentle tip-first fade. Reactivation restores them smoothly,
  with glow and movement/growth (retain the approximate 20% repeat extension), without abrupt respawn or pulse reset.
  Prove quiet/peak lifetime handles, tip/root fade ordering, slow decay, partial-fade reactivation and direct/reflected
  appearance. Retain birth look during travel; finite history eviction must not cut off a visible unfinished fade.
- [~] **Colour, floor and mist (5 Nov candidates):** lattice sheets (V3); wet concrete with stable soft coloured
  reflection mass (no horizon line, no flicker-prone streaks; operator prefers smeared colour to streaks); one bounded
  night medium with a slight local ribbon tint (strong Local Light can no longer wash the frame). 5 Nov vs `Preset3Goal1`:
  the grey base was the far concrete level and surface brightness, and Reflection Colour was not the hue drift (lower
  read pastel). All presets darker far surface (.2) and brightness (1.2); P3 stronger, wider-smeared reflection
  masses (lit saturation .60 vs reference .59, current .54). Consecutive frames smooth (flicker .0068 -> .0105, from
  brighter moving masses, no column popping); evidence `studio_20261105/floor4/`.
  Floor collision (operator, 5 Nov): a ribbon whose lower edge nears the floor lifts as a WHOLE (shape-exact, two-stage
  eased, up to 3 units since 6 Nov, when in-view swells needed more; Floor Give keeps 1.5); per-knot trough limits
  were rejected as boxy. Residual visible contact (lift still easing up, lift-only, recorded continuous play +-16):
  P1 1.3%, P3 .75%, P4 .19%, P7 .13% of music ticks (main 27/16/7/7%); a faster attack clears more but moves the lift
  harder (TROUGH_ATTACK .1: P1 .45%, lift acceleration p99 x1.3) -- not adopted. Wide sheets (P2) still graze ~60% of ticks:
  optional Floor Give (below) lets the wet floor dent under them instead.
- [~] **Fixed response, break-proof Breathing, Kick Accent (operator, 6 Nov: "when it went suddenly quiet everything
  become more reactive ... Adaptive is a very problematic approach"; "many sustained kicks ignored") — awaiting
  operator eyes:** geometry drives are a fixed function of the real-music scale (Adaptive Response toggle, off in every
  preset; Preset 4 differs from the tag only through it, Kick Accent and the floor lift — set Adaptive Response on and
  Kick Accent 0 to compare). Open: the Range audit (`.artifacts/evidence/visualizers/waveform_ribbon/reactivity_preset7/20261107_reactivity_preset7/
  rangeaudit_*.txt`) shows Rotation's drive never above .36 on any recording (its Peak handle is never reached), and
  Light/Colour/Sparkle/Highlights, Width and Lift never reach .8 on three or four of five songs: those calibrations (not
  the response gain) are the remaining Range losses; the music's return after a break still dips for about a second
  while the shared passage level climbs back (return window 12-55% of the unbroken clip on every arm, main included);
  Preset 3's quieter-after-loud kicks are 4% under main's (every time bin is above); soft passages swing less in
  absolute terms (3 s contrast .21 vs the adaptive gain's .30) and loud ones .11 vs .16.
- [~] **Floor Give (operator, 5 Nov: "the floor can deform inwards, allowing crests") — awaiting operator eyes:**
  opt-in Floor slider (default 0 = the rigid floor, pixel-identical); P2 authored 1.0. Where a lower edge comes down
  onto the floor the wet floor yields in a soft dent (one surface for the floor's ray hit, its shading/reflection and
  the ribbons' contact), so troughs stay round and dip in instead of flattening. Perspective only. In the visible
  frame P2 reaches the floor only in the ragdoll loud end (about 49.5-52 s); P3 never does, so it is unchanged there.
  Evidence `.artifacts/evidence/visualizers/waveform_ribbon/floor_deform/20261107_floor_deform/`; design in the Migration Plan's Floor bucket.
- [~] **Pulse Rim (operator, 5 Nov: "where the pulse is that section of the ribbon's rim can be even brighter with
  falloff") — awaiting operator eyes:** Reaction-bucket slider (0 = today's rims, pixel-identical). The rims (line and
  rim glow) brighten by the square of the published pulse field over a reference level, softly capped, sampled at
  each fragment's history x (direct and reflected light), so every Reaction Mode and both Travel Directions put it
  exactly on the pulse; the field's own smooth shape is the falloff. Evidence
  `.artifacts/evidence/visualizers/waveform_ribbon/pulse_rim/20261107_pulse_rim/`; design in the Migration Plan's Reaction bucket.
- [~] **Swells reach the Preset camera already faded (Presets 1-3) - awaiting operator eyes:** the card's camera shows
  about ±16 of the scene axis at 1282x1005 (±5 at the canonical card), but edge swells were born at `PULSE_ORIGIN` 44,
  so Head To Tail swells arrived ~2 s late at 5% strength (in-view swell p50 .13-.30 against Preset 4's 1.39). Now the
  capture and the Studio pass the camera's visible span; Travelling Pulse edge swells are born just beyond it and age
  only once seen (p50 .81-.99 at ±16; the peak visible swell after each kick is 1.7-5.6x main at every time in song).
  Preset 4 and Presets 5-7 are byte-identical. Evidence `.artifacts/evidence/visualizers/waveform_ribbon/reactivity_preset7/20261107_reactivity_preset7/`
  (`visibility_tag_vs_final.txt`, `kicks4_table.txt`, `sheets/*_p1..3_*`). Follow-ups (6 Nov): an edge swell now
  publishes half its level for Pulse Rim, as a Centre Out swell carries half the injection (rims at their ceiling over
  43% of the view -> 0-1%; rim pixels at 255 4.3% -> 3.6% P1, 3.2% -> 2.5% P3; Preset 4 pixel-identical); the floor
  lift reads the card's visible span plus 5 envelope sigmas within ±32 (identical at a 1282x1005 card, lower lift for
  unseen troughs at the canonical card with unchanged contact). Open: on Presets 1/3 the rim's swell-to-elsewhere
  contrast (1.11/1.17) is still below Preset 4's (1.27); the no-twitch probe's .02/.01 bounds only held because its
  swells never reached the cloth (in-view .028/.012).
- [~] **Travel Direction (operator, 5 Nov: "Travel Direction ... chosen in the studio ... an important basic need") —
  awaiting operator eyes:** Flow-bucket Choice, Right To Left (default, unchanged) or Left To Right (the mirror image:
  history enters at the left; pulses, held swells, Tilt Shift, sparks, strands and floor give follow; the world colour
  grade stays put). A live change fades out, swaps while hidden and fades back (0.6 s each way). Leads the Studio's
  Composition / Flow group. Evidence `.artifacts/evidence/visualizers/waveform_ribbon/travel_direction/20261107_travel_direction/`; design in the Migration
  Plan's Flow bucket.
- [ ] **Dense highlights, moving colour and rim glow:** playback still lacks rewarded high-energy density and glow.
  Verify local crest/high-power colour, bright tunable rim/glow and denser highlights against actual music, including
  quiet/loud differences. Consumer reachability does not establish visible strength. Keep both range handles effective.
- [ ] **Idle and first-play blackout:** keep subtle low-energy body motion and the same ready scene on first play;
  no blackout, re-priming or scene reset. Test cold playing-before-start, silence, pause/resume and source changes.
  Idle must not emit fake musical hits or particles.
- [ ] **Dynamic Floor independence:** the operator found floor ON more responsive. Controlled full PCM now proves
  identical body/birth packets and typed events OFF/ON on four clips. Preserve the existing FFT/bus raw-reference
  policy, mode-switch/reset and stale-compute fences, plus accepted Bubble/EB behavior. Prove lively OFF response by
  ear/eye against the guide's standard; raw parity alone does not establish musical response.
- [ ] **Grounded camera, near-flat tilt and infinite view:** stable eye height above the floor, approach/retreat and
  bounded left/right orbit, waveform always in view and no escape into ugly areas. Admit a genuinely near-flat tilt
  with visible floor. Keep eye/basis, navigation, editor markers and saved pose under the shared
  owner; preserve continuous/infinite body with no exposed ends and complete Edit scaffolding. Native geometry and
  persistence tests alone cannot establish feel or beauty across moving audio, view and viewport extremes. Reproduce
  the new cut-to-black at one end and staggered entry at the opposite end against recorded wide/angled playback.
  Perspective (the only projection; Orthographic removed 5 Nov 2026) retains its positive clip contract.
  **Current visual route:** operator delegates the choice; use a restrained long-lens Perspective primary view,
  calibrated with a farther physical eye and narrow lens together. Preserve stable height,
  bounded orbit and actual camera movement; no camera-dependent actor density or audio compensation. Judge colours,
  restrained reactive twisting, floor material and full-scene mist together against the references before acceptance.
- [ ] **Floor coverage, collision, reflection and viewport changes:** after the strand slice, draw ground all the
  way through the foreground and beyond the waveform into heavy dark mist that GENTLY thickens until no horizon
  line is visible. A strip of reflections over black is rejected. **Awaiting native visual validation:** the floor now
  intersects the same physical camera's pixel rays with the infinite world plane, covering foreground/far ground
  while actor clipping remains unchanged. Focused native tests cover complete coverage,
  world coordinates, floor occlusion and capped reflection. Finish the unified atmosphere before visual judgment. Keep actors and
  physical floor contact correct, with smooth waveform collision rather than clipping. Compare identical snapshots at
  canonical/wide/tall/large sizes and both projections; inspect reflection normalization/filtering separately. Preserve
  live reflectivity/tint/brightness and the shared resize contract; no audio-gain compensation. Columns remain secondary.
  **Additional explicit rejection:** material outside the core reflection is practically invisible. Validate readable
  dim texture across the foreground with reflection and atmosphere both OFF, then under the unified night medium;
  increasing reflection alone cannot satisfy this. Current candidate restores filtered concrete/roughness and ambient light.
- [~] **Unified atmosphere (5 Nov candidate):** replacement medium in place (old banks/fringe/floor haze removed);
  darker bounded haze with capped local tint; P3 density 0.06-0.09, P1/P2 0.055-0.075. Open: retained moving-body
  wake and the loaded fog cost gate (P2/game60 render median was over budget) still need measurement.
- [ ] **Waveform Studio (replaces the rejected builder UI):** in-process, reusable (mode registry + switcher;
  Extruded Bubble is a second real adapter) Qt Quick Studio per the operator's design pack; Settings > Custom opens it; production
  framing on the real card; camera navigation; theme-token chrome; full registry coverage; Energy Pulse/Reaction Mode
  first in Reactivity; target-first response tuner. Opens on the live card's world (Fill framing; 34f65cb1) with the
  mock's viewport toolbar, ribbon arrows and curve tiles. Open: remaining mock parity; real-window checks on hardware (visible window,
  native Settings hide/restore, exit timing via `[STUDIO] retire` logs, per-monitor DPI). The old builder buckets are
  already retired (Custom shows only the preset row and the Studio launcher); contract in
  `Docs/Reference/Visualizer_Studio.md`.
- [ ] **Live performance and truthful evidence:** run all three presets under matched recorded PCM/game60 and admitted
  camera extremes. Verify ACTUAL applied configuration, audible input and rendered features before interpreting
  timings. Profile logical preparation, birth admission, render stages and whole-frame tails; do not reduce artistic
  reaction strength to conceal cost. Preset 2 with persistent strands currently exceeds the render budget (~14 ms
  median under game60); reduce repeated submission/preparation and prove tails without weakening the approved strands.
  Requested CLI settings can be overwritten by curated activation.
  5 Nov: the logical tick (Waveform dynamics) was 2.2-3.2 ms median offline (live ~1.4x, budget 2.5 ms) after the
  reaction work; the along-curve surge and per-card colouring now run as rows (byte-identical packets proven per tick
  on real replays; paired -0.33 and -0.18 ms), quiet-machine median 1.32-1.35 ms all presets. Offline GPU at the
  live card size: P2 7.2-7.6 ms with strands, 6.0-6.6 without (strands ~1.1 ms). 5 Nov (late): the no-twitch/pulse
  work added no tick cost vs 5b69d6d8 (same machine, human_heavy: advance median 2.45 ms both) and the closed-form
  flow-rule share took it to 2.30 ms. Next: GPU re-measure once Floor Give lands, then the game60 live check.

Chosen first: the smallest contained scene and the first consumer of S3D-1/S3D-2/S3D-5. Brief and hard gates:
`Docs/Future_Work/Waveform_Ribbon.md`. The detailed working checklist and visual target custody live in
`Docs/Reference/Waveform_Ribbon_Lab_Plan.md`; reference packages under `references/` are local/operator-owned and are
intentionally absent from normal GODZIPs.

The scene is world-first through the shared framed Perspective camera: wet reflective concrete floor,
waveform and full-scene night fog, with no visible horizon/sky/floor edge. The waveform clears and softly lights
the mist. Preset/control migration and recorded-audio calibration come only after the lab look is credible.

- [~] **WR-07/08 production candidate — finish admission:** the reaction is the travelling energy pulse with
  selectable modes (the C elastic body remains only for depth sway/torsion); A's accumulated twist and the reactive
  axial roll stay, with musical vertical response applied after the roll (roll-invariant). Preserve constant history
  flow, no time-varying axial scaling, smooth curves, particles/free strands and fog clearance by the actual body.
- [~] **Full controls/editors, four-ribbon capacity and three presets — finish admission:** primary/alternate examples now have
  candidate Preset 1/2 with the
  selected hybrid, shared framed 3D camera/navigation, technical profile, preset/Custom and Edit/Arrange feature set.
  Expose bend/torsion/stretch/twist/rotation and accent ranges, source/curve visual tuning, ribbon/gradient editors,
  and floor reflectivity/tint/brightness. Every reactive range needs actual quiet/peak consumer proof for both handles;
  retain mutable authored presets and prove Save/Cancel/Restore and runtime source reachability.
- [ ] **Framing, timing and acceptance:** prove hidden ends/history bounds and body/head-to-visible delay across admitted
  sizes/camera poses; replay real quiet/middle/hot/silence/hot-start windows with unshifted audio, inspect lab/production
  parity and audit range headroom. Close shared lifecycle/cost/dormancy gates and run
  `tools/visualizer_live_check.py --mode waveform_ribbon --load game60` before WR-09 acceptance. Operator visual/native
  judgement remains explicit where automation cannot close it. The new unified atmosphere supersedes all old fog
  layers. Floor-column polish is secondary to continuous ground and response.
- [ ] **Loaded render budget:** repeat the corrected actual-config live check after current source/geometry
  changes. The prior run labelled fog-OFF rendered fog because preset activation overwrote its CLI values; it is a
  failed fog-ON run, not an A/B. Verify packet lease/GPU envelope/culling retirement and finite-consumer parity, then
  measure current body/birth/floor cost with the rejected volume disabled. Keep CPU reduction as a test oracle; no
  readback or duplicate live preparation. Replacement atmosphere must earn its own measured budget.

### 7.2 Reactive Liquid / Audio Melt Pool

A heavy viscous molten body in a real concrete chamber; must never read as Neon Lake (`shockwave_grid`) water. Brief and hard gates
H01–H14: `Docs/Future_Work/Melt_Pool.md` (mock in `references/Reactive_Liquid_Audio_Melt_Pool_Concept_and_Architecture.zip`).
Uses S3D-3 (chamber), S3D-4 (surface field), S3D-5 (reflections), S3D-2 (droplets).

- [ ] Stages with stop points: static chamber + framed camera → connected viscous surface → musical pressure and peaks
  (decide whether a deformable peak mesh is needed) → material/environment interplay → droplets, Settings, acceptance.

### 7.3 Concrete Rain

Rain on a night street: music changes the pavement's water, never the street. Contract: `Docs/Future_Work/Concrete_Rain.md`
(reference `references/Low and High Reactivity Concrete Rain Comparison.png`, left low / right high). Reuses S3D-3
(street), S3D-4 (ripples), S3D-5 (wet surface, reflections), S3D-2 (impacts, crowns, droplets).

- [ ] Stages: wet surface and reflection → ripples and impact rings → splash crowns/droplets → music mapping (density,
  impact energy, ripple complexity, reflection disturbance) → scene assembly and acceptance against the reference.

### 7.4 Usu Moonscape (eventual)

Long-horizon character/world vertical: `Docs/Future_Work/Usu_Moonscape.md` (Blender work:
`Docs/Future_Work/Usu_Blender_Work.md`). Needs the character/world foundations S19–S27 listed there (asset bake,
skinning, animation graph, secondary motion, felt/fuzz, world-view projection, sphere world/starscape) plus S3D-6.
Not admitted until those foundations are proven; the static silhouette approval stays a separate hard gate.

## 8. Accepted Bubble: bounded performance gate and deferred control audit

The operator has **accepted the improved original Bubble normal-drift musical authority**. That task is closed;
do not reopen it as unfinished work or restore the pre-experiment drift response. The durable approved motion,
ambient, direction and occlusion rules are in `Docs/Guardrails/Bubble_Temporal_Fidelity.md` §23. The following
performance gate is **explicitly admitted now** as a short exception to the §7 mode sequence. The separate
scalar-to-range audit remains deferred until explicitly reprioritized.

- [ ] **Bubble post-ambient performance / exact-output check (short and bounded):** inspect hidden costs from the
  shared hero big-over-small shader loop (including decoration OFF), opt-in 2048-capped ambient FBO, large glow
  sprite fill, and up-to-110-circle masking. Compare the **original handoff** to the **accepted Slice 13** under
  matched configuration for resource/performance attribution, then freeze **Slice 13 itself** as the behavioral and
  rendered-output oracle for any proposed optimization: original-vs-Slice-13 pixel bytes are *not* expected to match
  where the operator intentionally changed layering, motion or glow.
  - [ ] Measure decoration OFF, representative decoration ON, and high-density/high-glow decoration ON, using matched
    real-music replay and canonical plus extreme-wide/tall/expanded sizes, with multiple repetitions on the operator's
    native Qt Quick/OpenGL runtime. Report Bubble GPU/render p50/p95, CPU logical work, FPS/frame-pacing gaps,
    resource allocation/release and other-display contention. Check that OFF really avoids the extra FBO, sprite
    and mask draws; the modified shared hero shader still warrants timing even with decorations OFF.
  - [ ] For any **actual optimization**, compare deterministic logical packets/bit patterns exactly, and compare
    final captured RGBA bytes frame-by-frame on the **same GPU, driver, dimensions and fixed replay** when that
    capture path is deterministic. Where bit identity is unavailable, disclose why and use exact geometry/response
    checks plus recorded pixel-diff and temporal parity evidence. Do not claim byte-identical *performance*:
    throughput, GPU timing and latency require measurements.
  - [ ] If cost is material, optimize only the measured offender and repeat the parity + native performance gate;
    preserve visual quality, all approved sinking/reversed-flow presets, reactivity/latency, BTF and mutable presets.
    If no material cost is measured, **close the item without redesigning Bubble**. No generic "lean out" campaign.
  - [ ] Include the R-170 density growth: a card larger than the canonical one now draws up to 72 live heroes
    (up to 110 with draining trails) instead of its authored ~31-68, and the hero loops are per fragment.
- [~] **R-170 operator eyes-on:**Bubble on a tall, a wide and the TV card should move and size like the canonical
  card, denser on large cards. Evidence: `Docs/Historical_Bugs/R-170_Bubble_Shape_Dependent_Speed_And_Aspect_Modifiers.md`.
- [ ] **Side defect (found during R-170, not fixed):** `_apply_bubble_collision_response` smooth mode multiplies
  `max_disp *= 0.72` inside the per-bubble loop, so the in-view correction cap compounds down the list (order-dependent).
  Fixing it changes canonical Bubble output, so it needs an explicit BTF behaviour-change decision first.
- [~] **Particle glow (merged 059e8ccb) — awaiting operator eyes:** emitted linear light with a hot core and a
  monotonic halo (no dark moat), no twinkle on drifting sub-pixel cores, cheaper ambient CPU pass. Evidence
  `.artifacts/evidence/visualizers/bubble/particle_glow/20261107_particle_glow/` (`before/` vs `after/` 4x crops, flicker strips).

## 9. Studio for every visualizer (replaces the builders)

Operator (5 Nov): instead of a Bubble UX sweep, every visualizer (Sine retired 2026-11-05) gets a version of the reusable
Studio (`ui/studio`, mode registry + adapters) that replaces its builder. The Waveform Studio is the first adapter and
the framework bar; each mode contributes only an adapter (typed schema from the canonical registry, truthful evaluator
on its production logical/render path, fixtures, scene objects, workspaces and instruments), never a copied shell.
The former Bubble scalar-to-range idea is folded in: each adapter picks the right instrument per control under the
design pack's control policy (quiet/peak A/B, real ranges only where a true interval exists), with unchanged
serialized data unless a migration is justified. Accepted looks/behaviour (BTF, presets, timings) must not change.

- [ ] Finish Waveform Studio acceptance first (§7.1), then extract any remaining Waveform-shaped assumptions.
- [ ] Adapters in order of authoring pain (Extruded Bubble, Bubble, Spectrum/Rainbow Ghost, Extruded Spectrum and
  Neon Lake (`shockwave_grid`) built, Spline Curve (`devcurve`) and Oscilloscope built (below); Voxel Sphere in progress). Neon Lake awaits operator acceptance
  (evidence `.artifacts/evidence/visualizers/shockwave_grid/studio/20261107_studio/`, Presets 1 and 3): recorded engine answers like Spectrum, the
  shared framed camera, no wallpaper; its terrain is painted with the Studio's shared brush (6 Nov; evidence
  `.artifacts/evidence/studio/completion/20261106_completion/brush/`; the retired Settings editor's 3/4 view Sun / Moon drag is
  now Position X / Y / Z only). Extruded Spectrum awaits operator acceptance
  (evidence `.artifacts/evidence/visualizers/extruded_spectrum/studio/20261107_studio/`); its cast-shadow rows stay out of the Studio while
  they are unavailable (`EXTRUDED_CAST_SHADOW_AVAILABLE`). Spectrum awaits operator acceptance (evidence
  `.artifacts/evidence/visualizers/spectrum/studio/20261105_studio/`). Every mode's Settings body is now the preset row and the Studio
  launcher (operator 6 Nov: migrate fully once parity+ is proven; `tests/test_visualizer_studio_parity.py`). Operator
  look pending on the migrated Settings pages (one sentence per mode) and on the terrain brush in the Studio.
- [~] **Spline Curve Studio built (6 Nov), awaiting operator acceptance**(`ui/studio/devcurve_adapter.py`, registered;
  so Spline Curve's preset row now shows Open Studio and no Edit Preset). Evidence `.artifacts/evidence/visualizers/devcurve/studio/20261107_studio/`
  (Deep Blue on Rag Doll, Neon Skyline on Human: every workspace with the live traces, plus the node rows). Operator
  to judge: the per-layer Body / Accent / Swell traces as the way to read the reworked reactivity, the Layers
  workspace (one panel per layer), and whether the Audio Analysis group earns its place (re-analysed from PCM through the
  production DSP, every offered control moves Spline Curve's frame; AGC Strength and Output Lift read nothing and are now
  hidden: `Docs/Reference/Visualizer_Reference.md` → Audio Analysis controls per mode).
- [~] **Oscilloscope Studio built (6 Nov), awaiting operator acceptance**(`ui/studio/oscilloscope_adapter.py`,
  registered). Evidence `.artifacts/evidence/oscilloscope/studio/` (Preset 1 Phosphor on Human, Preset 3 Lissajous on
  Rag Doll: every workspace with the live traces). Recorded engine answers with the capture history recorded by
  identity (binary sidecar; `Docs/Reference/Visualizer_Studio.md` §3). Operator to judge: Level / Afterglow / Ghosts /
  Flare / Drive / Tone as the way to read the beam, the three workspaces, and whether the Audio Analysis group earns
  its place (re-analysed from PCM through the production DSP, every offered control moves Flare and Drive, and Bar Count,
  Block Size and Input Gain also move Tone: the trace itself is the raw capture, but the beam's reactions are not;
  `Docs/Reference/Visualizer_Reference.md` → Audio Analysis controls per mode).
- [~] **Edit Preset deleted (6 Nov)**: every visualizer mode now has a Studio, so the preset row's Edit Preset button,
  `_open_preset_json` and its pop-up are gone (`ui/tabs/media/preset_slider.py`); curated presets are authored with
  Open Studio and the Studio's confirmed Save To <Preset> (`Docs/Reference/Visualizer_Studio.md` §4).
  `tools/flicker_test.py` keeps its own historical mock of the old row. Operator look pending: Open Studio's place in
  the preset row and the Save To flow.
- [ ] **Operator side requests (6 Nov, "important eventually"; queue after the running work):**
  - **Waveform travel speed:** History Speed (`flow_speed`, 0.8-2.4, Flow bucket) and Pulse Speed exist but the
    operator did not find them; there is no travel-speed reactivity. Make them findable (name / workspace / tooltip)
    and consider a quiet -> peak History Speed under the flow rule (music pushes history faster, smoothly; knot spacing
    and the anchored ends stay continuous). After the adaptive rework (same owner).
  - **Studio clips are seamless loops (6 Nov), awaiting the operator's listen and look.** Built: the three clips are
    12.6-13.2 s loops (0.86-1.01 MB each) with searched loop points and a 1 s equal-power crossfade baked into the
    capture stream, and every Studio's evaluator plays on through the wrap with its state carried (no restart at
    `t = 0`); workers prime on the loop's last 2 s. 30 s clips were measured and not chosen (size and re-analysis
    grow, the seam does not improve): `Docs/Reference/Visualizer_Studio.md` §3 "Studio clips", evidence
    `.artifacts/evidence/studio/clip_loop/20261106_clip_loop/`. Note the Studio plays no sound: the clips are the capture
    stream the analysis reads, so "listen" means the music-reactive picture across the wrap. Operator: (1) let any
    Studio loop on each of the three clips and watch the wrap (end of the 13 s timeline): the preview should not
    jump, empty, or re-start its motion; (2) Rag Doll has no steady beat, so its seam is the least certain: judge it
    first; (3) the clips now start and end mid-song at the loop points chosen (Human and Growing Pains on their
    groove), not at the earlier quiet-to-hot windows; say if the quiet-to-hot arc matters more than the seam.
- [~] **Studio chrome: Awaiting Validation.** Operator-check the shared semantic material on panels, workspace
  tabs, section headers, tools and instrument wells, plus native snap/resize/maximise and light-theme shadows.
  Active material work is section 1A, item 1.7; rounded native corners remain open at item 1.9. Contract:
  `Docs/Reference/Visualizer_Studio.md` (Chrome and theme). Off-screen Studio evidence cannot establish native DWM
  composition; preview-overlay backing stays cheap and scene colours stay independent of chrome.
- [~] **Studio drag lag fixed (6 Nov), awaiting the operator's feel check.**Drags preview once per frame and
  re-show only the dragged key (Visualizer_Studio.md "Drags are batched"); evidence
  `.artifacts/evidence/studio/drag/20261106_drag/` (per move 56 ms -> 0.07 ms on Waveform). Side defect (not measured): Bubble's,
  Extruded Bubble's and Sphere's evaluators still replay exactly in one evaluation from the fixture start, without the
  frame budget and checkpoints Waveform and the engine-answer modes now share (`ui/studio/exact_replay.py`); measure
  with `tools/studio_drag_profile.py` and move them onto `ExactReplay` where a release stalls.
- [ ] **UI frozen after closing a Studio, recovered by itself (operator 6 Nov 21:56, Extruded Bubble, Wine Ice
  Acrylic): owner not found yet, instrumented.**
  - What the log shows: the close was clean. Settings was revealed `visible enabled exposed`, native `(True, True)`,
    and the window was destroyed after 77 ms. Then the GUI thread logged nothing for 18 s while the process was
    idle (CPU 4.7 %, GPU 0.1 %).
  - The event-loop recorder still delivered its 15 s summary on time at 21:56:48, so the loop was running and this
    was not a stall. Its `period_samples=0` only means the lifecycle window was open, as it is for all of Settings.
  - Not reproducible offscreen: in an offscreen-QPA probe with a real application-modal `StudioWindowSurface` closed
    by its Close button, Settings ends up active, unblocked and taking clicks.
  - Read from Qt's source (6.11): hiding the modal window unblocks Settings before the native hide. While Settings
    is still blocked, focus given to it is handed to the modal window (`handleFocusEvent`), and a blocked window is
    natively `WS_DISABLED`. So the suspect is native activation or enable state at the reveal, which happens while
    the modal Studio is still shown.
  - Next field run: the `[STUDIO] after reveal` lines (`presence.RevealWatch`, one-shot, removed at the first input
    to Settings) name which window Windows sent the clicks to, and the state at each step. Fix the owner from them.
  - Lead fix audit (7 Nov): this is the third round. 5 Nov (da1b86fb) fixed a real deadlock with real-Studio
    tests. 6 Nov (583401bd, "re-expose so the layered window repaints") was proven only on a bare stand-in
    window, and the freeze returned that night. The watch now also records Settings' first Expose, UpdateRequest
    and Paint after the reveal, and the first-input line reports them ("repaint since reveal: none" is the
    takes-input-but-never-repaints signature). Acceptance needs the operator's field log plus a fix proven on the
    real SettingsDialog path, never a stand-in only.
  - Field log 7 Nov (operator's source run): the 02:00:08 close (Neon Lake) shows Settings revealed, active,
    enabled and exposed, the first click delivered to Settings at +853 ms, and **no Expose, UpdateRequest or Paint
    since the reveal**. The 01:56:26 close painted at +80 ms. Cause: Settings is a layered window, so the 6 Nov
    `RedrawWindow` re-expose produces no WM_PAINT, and when nothing else dirtied Settings Qt scheduled no repaint;
    the screen kept the pre-Studio picture while clicks changed state underneath. Remedy (7 Nov, lead):
    `WindowPresence.repaint_revealed` asks Qt itself to repaint Settings at the reveal and again when the Studio window
    is destroyed. The watch now stays armed until Settings' first Paint after the first input and logs `qt_exposed`.
    **Open until a field log** shows a paint right after the reveal and `first Paint after the first input` within a
    frame or two.
- [~] **Camera reset on every edit and the exit double flicker fixed (operator 8 Nov), awaiting the operator's look.**
  Camera: on a curated preset (Include current camera view on, the default) each commit re-hydrated the framed camera
  editor and dropped the orbit committed into the draft, so the preview snapped back to the preset's view (Neon Lake,
  Extruded Bubble, Waveform Ribbon). Exit: Settings was raised and activated over the still-shown modal Studio, Qt
  handed its activation back to the Studio, then the Studio hid: Settings now appears beneath the Studio and comes
  forward once it is gone (`Docs/Reference/Visualizer_Studio.md` §4 "One transition out"). Operator to check on screen:
  orbit, then drag sliders (the view stays); close the Studio by every path (one clean change to Settings, no swap).
- [ ] **Per-session memory growth in the Studio (side defect, 6 Nov; the clip caches ruled out 7 Nov).** Process
  memory grows about 2-3 MB per offscreen Extruded Bubble session (private bytes and USS, 16 sessions), the same with
  and without the controller-leak fix (`test_closed_studio_sessions_are_released_and_live_counts_stay_flat`). The
  sessions measured load no recorded clip, so the clip caches cannot be the cause; they are bounded now anyway
  (AC-06 landed: 60 Audio Analysis re-analyses grew 39.3 MB before, 15.5 MB after, flat at 120). Re-measured with
  `_sessions` (24 sessions, private bytes after `gc.collect()` per session): the first 4 sessions add ~85 MB (warm-up),
  then ~1 MB per session that flattens, but the series swings by ±70 MB run to run (main and branch alike), and
  tracemalloc sees only ~55 kB of Python growth per session (QML chrome objects, settings normalisation copies). What
  grows is native (Qt Quick / GL driver heaps), not Python. Next: a native heap comparison (UMDH or VMMap) across 30
  sessions; bar: a trend, not run-to-run noise, before any fix.
- [ ] **Slider drags no longer let go mid-motion (operator 6 Nov), awaiting the operator's feel check.** The cause
  was the inspector's ScrollView: a vertical wobble past the drag threshold stole the press, on every mode at the
  first wobble. Every drag instrument in a scrolling panel now sets `preventStealing: true`
  (`Docs/Reference/Visualizer_Studio.md` "Drags are batched"). `tests/test_studio_drag_coalescing.py` covers it,
  with a negative control.
- [ ] **No automatic switch to Custom (operator 6 Nov), awaiting the operator's look.** A Studio edit on a curated
  preset is now held, with nothing saved and the preset still selected.
  - Closing the Studio yourself, switching preset or switching mode asks *Unsaved Preset Changes* with four
    choices: Overwrite <Preset> (not offered on a read-only file), Save As New Preset (Settings' own Save Preset
    As, then the new preset is selected), Place In Custom, Discard. Closing the prompt stays in the Studio.
  - Quit, Settings going away and other closes nobody can answer keep the edits in Custom.
  - Spec: `Docs/Reference/Visualizer_Studio.md` §4 "Canonical save". Tests:
    `tests/test_studio_preset_row_and_save_to_preset.py` (every choice, read-only, edits returned to the preset,
    unanswerable closes, and a Custom negative control).
  - Operator to check: the prompt's wording and buttons over a real Studio, and that Save As New Preset's file
    dialog lands in the right folder in an installed build (ProgramData's shared preset tree).
- [ ] **Neon Lake: drag the Sun/Moon in the Studio preview.** Retiring the Settings terrain section (6 Nov, Studio brush)
  removed its 3/4 view, where the Sun/Moon could be dragged; it is now placed with Position X/Y/Z only. Give the Studio
  preview a direct drag for it: the same pick through the production camera as the terrain brush, one undoable commit
  on release.
- [~] **Operator look: the Studio terrain brush**(brush button or B in the viewport toolbar; Raise, Lower, Flatten,
  Water; left-drag paints, right/middle drag pans). Evidence `.artifacts/evidence/studio/completion/20261106_completion/brush/`.
  Audio Analysis now moves the Spline Curve, Oscilloscope, Neon Lake, Bubble, Extruded Bubble and Voxel Sphere previews on
  recorded clips. Sensitivity sheet: `audio_analysis/`. Spline Curve normalises its body, so it barely shows, as live.

## Operator execution and evidence rules

Keep details and evidence at their focused owner, this checklist actionable, and `Index.md` / `Spec.md` navigation current.
No memory updates without an explicit request.

####################
ADDITION & SIDE QUEST BOX
Never Remove This Box. Restore It If Removed. Only Remove Contents As you place them in the active plan as real live checklist targets.
####################




###################
