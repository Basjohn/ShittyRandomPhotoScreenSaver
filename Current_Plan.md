# SRPSS | Current Plan

Live, ordered work only. `[ ]` work remains; `[~]` a candidate exists but is unaccepted (awaiting validation, never an
implicit pass). Remove completed work; retain only extremely brief, useful native-core reference boxes. Durable contracts live in
`Spec.md` / `Docs/` (Reference, Architecture, Guardrails, Guides); rejected mechanisms in `Docs/Historical_Bugs/`. This
is not a changelog. Deferred, unadmitted ideas live in `Future_Work.md`.
All other work listed in this plan must be complete before SMP work can begin. SMP work should research and begin with a native audio core from the outset. You can remove this line if you place the instructions properly into the plan.

## 0. Scope and rules

**If you are the lead (orchestrator):** read `Docs/Guides/Orchestrator_Handbook.md` before anything else, and run `tools/agent_handover.py` to see every agent worktree, its journal and its unmerged work. Agents read `Docs/Guardrails/Agent_Worktree_Rules.md`, then their item here.

**Accepted baseline (not live work):** original Bubble, Extruded Bubble, Neon Lake (`shockwave_grid`),
Oscilloscope, Spectrum/Rainbow Ghost, Voxel Sphere (`sphere`), source routing, transitions and Foundry launch buttons. Reopen an accepted
area only for a concrete new defect; deferred or unadmitted work belongs in `Future_Work.md`. Historical recovery
IDs, completed gates and rejected mechanisms belong in source control or their focused historical/investigation docs,
not in this working plan.

**Rules:** one Settings/capability/CUSTOM/render/lifecycle owner and the sole Visualizer logical clock. No new
floor, capture/DSP, renderer-side simulation, timers/polling or camera-following replacement populations. Preserve
authored presets (mutable, never test-pinned), BTF, accepted timings, parallel work and strict retirement barriers.
CLI/sidecars, never environment-variable configuration. Smallest meaningful focused test per change; the
balanced, two-worker chunked suite only at milestones; file-isolated execution is opt-in diagnosis,
not a routine agent gate; no build/installer unless requested. Visual work is judged on rendered pixels against
its target (`Docs/Guides/Visualizer_Visual_Tuning.md`), and any claim of "fixed" needs the failure reproduced first.

**Linux compatibility** runs as a separate operator-requested plan, `Linux_Plan.md`; it does not reorder this plan.
New platform-facing work (power, display, input) still ships a basic Linux path or an explicit inert one alongside
the Windows path, so it never needs its own Linux audit later (operator, 5 Nov).

**Architecture checklist:** `Docs/Reference/Architecture_Checklist.md` (the 6 Nov audit, verified against source on
7 Nov: 16 items with severity, reward, effort, owning boundary, fix, regression bar). Its Tier 1 (AC-01 Settings tab
registry, AC-02 Visualizer host binding, AC-03 application-service tier) is the prerequisite work for step 7 below
(AC-01's contract: `Docs/Architecture/Settings_Bucket_Persistence_Contract.md`, "Tabs and pills: one registry"). The
items promoted to run soon are in §3. Nothing else in it is admitted until it appears here.

## 1. Order of work (strict)

Live checklist: every open step is its own box; landed boxes are deleted at merge; keep `[~]`
validation steps and open side defects. **Load runs:** game60 at most 10 minutes in total, started by the lead only
after the operator's yes on a question card; agents never run load (invisible checks without load, at most 3 min).

**State (17 Nov):** Spectrum, Spline Curve and Bubble are native and accepted (operator), and Bubble is offered on
Vulkan. ABI 25; N3.4 audited, its defocus investigation non-blocking. Every port and optimisation is proved by one
method, `Docs/Guides/Native_Parity_And_Timing_Proof.md` (layers L logic, P pixels, T timing, C cost); per-mode tools
are named in each mode's own guide (Bubble: `Docs/Guides/Native_Bubble_Diagnostics.md`).

**Order (lead and operator, 17 Nov):**
1. Close Bubble (the N5.1 Bubble box, in its order): checkpoint audit 8's fixes; build the fast long-clip proof's layer L and
   layer P tools (the "Build the fast long-clip proof" box); then Bubble's layer L directly, layer T on both backends,
   rule (b) over the four takes, the 2560 x 1440 cost, and the D1 rehearsal.
2. The scene-fade double-rounding fix (the "Spectrum and Spline Curve long-take residuals" box). Then rerun Bubble's
   tracked exceptions and the Spectrum and Spline Curve control.
3. Bubble GPU optimisation under the guide (its box), alongside step 4.
4. Ports, each under the guide from its first brief: the Oscilloscope (N5.1), then Waveform (N5.4) under the fast
   proof's split (the guide's section 7: full-take native-only runs against cached references; windows only for
   record and settings classes), then Extruded Bubble (N5.6), Neon Lake (N5.5),
   Extruded Spectrum and Sphere (N5.3).

5. Everything else in this plan is backlog: operator defects (Item 1, sections 1B, 1C, 1D, 1A), hygiene, Studio and
   later mode work. A slot takes from it only when no native step above can use that slot (operator, 15 Nov:
   native core first in every slot). Within a backlog section, its own internal order holds. No other heading in
   this plan sets a global order.

**Resume here (lead, 21 Nov ~16:30 UTC; main at ABI 33, built; weekly about 47 %):**
- [ ] Working rules (operator, 21 Nov; handbook 7a and section 3-4, proof guide section 3): critical path only; related
  work to the agent that holds it, unrelated to a fresh one; regression guards only after acceptance; unattended runs
  at once; briefs name the owning checklists, merges check the report bullet by bullet against the cited evidence;
  ABI numbers reserved at dispatch; main built once per batch of C++ merges.
- [ ] Modes track: the Waveform port (N5.4), agent a6688ad0cd2ae360a. Its branch holds 17a4bb9e0 (placement, bucket
  discard, row order; Python stills unchanged) and e3a84a443 (core C++, not compiled: record f64/u32 into vector and
  matrix members, the conventions `w` flag, the sampler W-wrap fix). Next: lead reserves ABI 38 (37 is N5.2d's), the
  agent renumbers, lead builds; rule (a) needs a measured Waveform bound (bloom rounding 13-29k px at 2-3 levels,
  edges 400-1,200 past 3) decided on the rerun after the W-wrap fix; then L, P, rule (b), C, T.
- [ ] Background track: N5.2d with N4.i (motion blur and trails), agent a52b367bbd9c11f5c (Opus Medium), ABI 37 reserved; N5.2c merged 21 Nov (ABI 36, main built).
- [ ] Black flicker at a transition's start on Vulkan (`--vulkan`, operator, 21 Nov): a visible black frame when a
  wallpaper transition begins. A serious class (fade, never vanish). Background track, the N5.2d agent's next box
  after its merge (it holds the background layer's run path), before any further transition batch. Reproduce on a
  live Vulkan run with `--frame-trace` (which transitions; first frame of the run: the destination upload, the slot
  swap, the photo environment's first copy, a target made at run start, a cleared frame presented before the first
  record); compare OpenGL native and Python. Fix at the owner so the first frame of every run shows the source or the
  run's own first frame, never black; a test whose control is the old path, and a trace-checked run on Display 1.
- [ ] Beam leftover: cost per pass at 1440p and 4K on both backends (`transition_route_check.py --cost --variants
  crossfade beam beam_sparks`). Its Vulkan hitch row, taken again 21 Nov with the run-gap tooling (the first one's
  "0 % late" counted Visualizer frames, of which there were none): gaps median 5.3 ms, max 9.6, first frame 9.2, none
  over 33 ms; render 0.43/0.69 ms; CPU 32.9 % of a core inside the run.
- [ ] Performance, parked until every port has landed (operator, 21 Nov: no optimising before then unless a port
  performs so poorly it cannot be considered stable, i.e. gaps over 33 ms inside runs, stalls or growth). Found 21 Nov (Jigsaw's GUI tick also about 1.25 ms against 0.5, its piece table packed every frame): inside a run, the saver's CPU on native Vulkan transitions is
  28-36 % of a core (Beam 32.9 %, the four 3D scenes 28-36 %, Jigsaw highest), while GPU render time halves against
  Python OpenGL. The earlier whole-row figures (Beam 16.5 % against 9.9, Crossfade 19.9 %) included idle time between
  runs; the first step is the same inside-run figure for Python OpenGL, so the ratio is like for like.
  Not one transition's own: it is the Vulkan path. Root cause (the present path, the frame driver, the trace and sampler on
  that path) before NF; evidence `tools/baselines/preflip/beam_*` and `crossfade_native_vulkan*`.
- [ ] `--perf` overlay on Vulkan (operator, 21 Nov): the Visualizer's overlay shows no fps, rev or age when the saver
  runs on Vulkan (`--vulkan`). Root-cause where the native path stops feeding the overlay's figures; fix at the owner
  so both backends feed it the same way, with a test. Before NF.
- [ ] The Oscilloscope: registered and documented; left only its two side defects and its backlog line.

**Next, by slot** (operator, 20 Nov: Opus High only where it genuinely pays, otherwise a second Medium; audits at
the level the risk needs; Sonnet as a cheap workhorse, researcher and documenter alongside; no Fable unless asked).
- [ ] High (Opus High): the Waveform port (N5.4) on the landed ABI 33 core (agent a6688ad0cd2ae360a; ABI 35 reserved). Defects between N steps: 1D.6 (design note first), then 1C.10.
- [ ] Bubble GPU optimisation step 3: the offline work is done (the hero and wake rejects halve the bubble pass at 4K);
  the lead's live Display 1 baseline remains.
- [ ] Audit (Opus Medium; Opus High only for core C++ with real risk): each merge (the Bubble landing is audit 8).
- [ ] Sonnet Medium: profile the owner replay (the fast proof's first box), then cheap audits and docs of open avenues,
  and hygiene (item 6).

### Item 0. Operator defects of 11 Nov: section 1B (backlog; its own internal order; see Order point 5)

### Item 1. Operator-reported defects first

- [ ] Foundry UX (operator, 14 Nov): `Docs/Future_Work/Foundry_UX_Audit_2026-11-14.md`; open from it, for the operator's
  pick: its remaining high and medium findings and the Build Foundry's port from Tkinter to PySide6.
- [~] Defect (operator, 14 Nov): a Studio window's taskbar icon in frozen builds is Windows' default box. The static
  cause is unproven (likely an icon Qt could not decode). Lead: check the next GitHub frozen build's `[ICON]` startup
  line, any no-icon warning for a shown Studio window, and the taskbar.
- [ ] Bubble breathing and reactivity weaker fullscreen than on a small card (agent ad98162c77b175a12, Opus Medium; operator, 21 Nov, after R-248 fixed the
  speed): R-248's check matched breathing as displayed/nominal radius in logical frames, yet on screen fullscreen
  breathes and reacts visibly less. Log: `logs/worker_visualizer.log` 21 Nov 20:19:17-20:21:24 fullscreen (world
  1.320x1.113), card after 20:21:25 (2.866x0.513, then resized). Root-cause where the drawn reaction depends on size
  (the capacity zoom, a pixel or world-unit cap or floor on pulse/breath amplitude, size-class thresholds that move
  with the zoom, the renderer's mapping), measured on drawn output not only logical ratios; fix at the owner so the
  visible reaction is size-independent, the small card's reaction being the target (fullscreen rises to it; the card
  never weakens toward fullscreen, proved by the card's figures unchanged); test at two sizes with a control on the old code; reaction check on a recorded
  take at card and fullscreen size with the take's envelope above.
- [ ] Defect (operator): in MC profiles mode, clicking a link kills the cursor halo completely. Root-cause and fix at
  the halo's owner, with a test.
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

- [~] Lead review on a rendered showcase WebP on recorded music: Frozen Past (Preset 5), live.
- [~] Lead review on rendered Studio frames (D1 run, 1B.14 harness): Pulse Count, Pulse Falloff and Freeze Deflate in
  the Studio.
- [ ] Vocals first, remainder: a kick inside sustained bass raises the swell 21% less (median .058 -> .046; those
  kicks also reach Kick Accent now); check it on the operator's look before tuning Pulse Strength's mid-led routing
  further.
- [ ] Breathing as a swell and release with proper motion (operator: 2D Bubble's breathing is the reference; guide
  §13A). Breathing is now only a faster release in soft passages.
- [ ] The onset reward is still sized by the bus's adaptive flux threshold (about 1 s of context: the same kick right
  after a dense passage scores .22 against .61); size it on the fixed scale.
- [ ] Group Wave's separation from Travelling Pulse and the pulse bands' colour edges: their boxes are in section
  7.1, "Reaction: travelling energy pulse".

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
- [ ] Re-author the raw linked Widget Theme roles that fail `tools/theme_legibility.py`, especially widget.accent on
  widget.panel and header surfaces, and keep the concrete failing roles listed in its report; runtime ink correction
  does not make a raw mirror export pass.
- [ ] Fix light-theme widget shadows, then inspect actual faint text over the resulting cards (analytic panel
  contrast alone does not account for the shadow's effect); 4x crops, lead review.

### Item 6. Hygiene

- [ ] Re-baseline after Qt 6.12.0 (admitted: doc sweep decision 9, 12 Nov; moved here from the 7 Nov "not yet
  admitted" list by the night audit's fix soon 6): `tools/overhead_baseline.py`'s stored baselines and the figures
  in `Docs/Reference/Benchmarks.md` predate the bump. Run it once on main (lead or Medium slot; no load), record
  new baselines with system usage before the next shared-path comparison. Today's merges (12 Nov: N2.3's changed
  Spectrum per-frame reads, N1.6's GL-call cuts) were measured on branches without a 6.12 baseline: compare
  Spectrum against the new one.
- [ ] Hidden cross-test dependency on an earlier test's `tmp_path` (lead, 7 Nov): with pytest's
  `tmp_path_retention_policy = failed`, `test_3d_curated_preset_ownership.py::...promotes_missing_owned_temporal_
  and_profile_keys...[shockwave_grid]` (0.7 vs 0.23) and two or three `test_settings_dialog.py` tab-restore tests
  fail; each passes with the default retention, so something process-scoped keeps a path into an earlier test's
  `tmp_path` (a cached preset tree or storage root). The setting was reverted. Find the cache and give each test its
  own root; this may also hide state leaking between tests.
- [ ] The AC-13 remainder (`Docs/Reference/Architecture_Checklist.md`).
- [ ] AC-14, AC-15 and AC-16 (same checklist).
- [ ] The rest of the plan staleness audit of 12 Nov
  (`D:\Temp\Scratch\SRPSS\research\20261112\plan_staleness_audit.md`; its line numbers predate the edits), Sonnet
  drafts and the lead decides:
  - [ ] One owner for the border material (1.7b, 1B.8's M3 and M4, 1B.9's last box) and for 1.9 against 1B.9.
  - [ ] One root-cause box for the state that leaks between test files in one process (item 3's side defect,
    section 3's "Isolate active Widget Theme state", the M3c context-menu and gesture reds, 1C.3's crash).
  - [ ] Section 3's "Found while ... (record, not yet admitted)" blocks: admit each or move it to
    `Future_Work.md`.
  - [ ] Findings written as boxes (the R-175 block, 7.1's "Open:" lines, 1B.8's theme-authoring numbers): one
    step each, the figures to their evidence document.
  - [ ] "Learned levels still in other modes" (section 3): per mode, the root-cause, contract, fix, guard and
    evidence steps.
  - [ ] 1.7a's first two boxes against M1, M2 and M2b: delete what those landed (1.7b's `plateInset` box went
    12 Nov).

### Item 7. Load session of 11 Nov (run; figures in `Docs/Reference/Benchmarks.md`, "Load session, 11 Nov")

Receipts: `.artifacts/evidence/performance/load_session/20261111_load_session/driver_receipts.json`.

- [ ] Waveform Preset 4 is still over the 8 ms render budget under game60 on the worker (10.4 ms median,
  `reflection` 1.7 and `ribbons` 1.9 ms the largest stages): a P3 input (item 8b, N5.4), not a P2 fault.
- [ ] Side defect, `tools/visualizer_live_check.py`: on the worker run with a Settings round trip the age chain's
  medians are nonsense (`publish_to_swap_ms` and `consumed_age_at_sync_ms` medians about -48,500 ms, p90 sane):
  records from before and after the round trip (a new worker generation, a different clock origin) are mixed.
  Report ages per generation, or only for the steady window before the first round trip as the help text says.
- [ ] Review the uncovered cases in the Watchlist ("Load runs the 11 Nov session did not cover") when admitted.

### Item 8. §8 Accepted-mode follow-ups

- [ ] Complete the Bubble performance-parity check in section 8.

**Then:**

### Item 8b. The native core: one C++ core for everything we draw; Vulkan the default, OpenGL selectable

Decisions with their reasons: `Docs/Future_Work/Native_Core_P3_Decisions.md` (D1 to D11 decided)
and `Docs/Future_Work/Graphics_Backend_Decision_2026-11-05.md` (its 12 Nov addendum says what is superseded).
Records: P1 `Native_Core_P1_Spike.md`; P2 `Native_Core_P2_Engine_Design.md`, `Native_Core_P2_Phase_Boundary_Audit.md`,
`Native_Core_P2_Closeout_and_P3_Entry_2026-11-09.md`; attribution baseline
`tools/baselines/overhead/2026-11-11_4658981b.json`; SMP seam
`Docs/Future_Work/ShittyMusicPlayer/03_PCM_Source_and_Native_Core_Seams_2026-11-09.md`. Research outside the
repository: `D:\Temp\Scratch\SRPSS\research\20261112\native_core_capability_matrix.md` (which mode uses what) and
`native_core_qrhi_gaps_and_conventions.md` (every OpenGL dependency with its routes; the conventions).

**Standing rules of this item (not boxes):**
- A port is done when it has (a) single-sampled pixel parity on OpenGL against the Python renderer it replaces
  (`tools/visualizer_replay/owner_render_parity.py`) at the widened run set (variants `a` and `b` and every Choice
  offer: `tools/conventions_identity.py` `mode_runs(mode, offers=True)`; never presets), (b) the same scene on Vulkan in the hidden host against the
  native OpenGL result, within a tolerance the port states, (c) the frame trace and render-thread figures beside
  the Python path's with zero calls holding a Python thread state, (d) Settings, Studio and engine-worker parity
  and the mode's own tests green, (e) GPU time per pass and nothing per frame at rest, (f) one bounded Vulkan
  rehearsal on Display 1 by the lead (D10), (g) no rebuild for Settings or Studio work (lead, 14 Nov, from the
  operator's question): the mode's fragment shaders load at runtime from the product's own `.qsb` (baked by
  `tools/regen_qrc.py --shaders`), every Settings-derived value is resolved in Python from the spec and packed by
  the core by reflected name (a settings block re-packed only on a Settings or card change), and C++ holds only
  per-frame and simulation arithmetic; a test adds a settings-only uniform and draws it with no module rebuild.
  N2.5 builds the shared piece (round 4); every later port uses it. Then the Python renderer and its shaders are
  deleted in the same change (a transition's at the background family's switch, N5.2h). Never two permanent
  renderers.
- Every primitive and service is proved on its own off-screen harness scene (GPU time median and p90, lazy
  creation, no work when dormant, clean retirement); none becomes a second renderer, clock or camera. Read the 3D
  foundation lessons (`Docs/Reference/Transitions.md`) before a 3D slice and append after it.
- A native route beside QRhi is one of D5.3's services, wins a measurement first and ships its OpenGL twin.
- No new 3D primitive is built in the Python OpenGL renderer unless an open defect needs it; new modes are built
  on the native core only (was N1.5), through its generic mode content (N2.9): a new mode is a Python simulation in
  the engine worker (off the render thread, publishing its frame record), its shaders loaded at runtime and its
  spec, with no C++ and no build round while it is iterated to its mock and reactivity goals. Hand-written C++
  for a mode is an optimisation admitted only after those goals are met and a measurement shows the hot path; a
  new GPU technique is a primitive, built and proved once in C++ and then used by every mode as data (lead,
  14 Nov, from the operator's question).
- High-potential primitives are built without a consumer, low-potential ones only when a consumer is admitted
  (operator, 12 Nov: "High potential primitives should be built regardless, low potential only when a consumer.
  We can always improve."). The lead classifies; the class is written at each item. When one lands it gets one
  showcase WebP and a "what this makes possible" note in `Docs/Reference/Primitives.md` (resource detail stays in
  `Docs/Reference/Scene3D_Resources.md`).
- The protected clip and background commits (ce07b991, 07486d83, 985b9d53) are not retuned while the Python path
  lives; the native background must measure no worse than them before it replaces them.
- The native module is compiled only by the GitHub workflow (operator, 12 Nov; handbook section 8; N0.9): an agent
  commits, the lead pushes its branch and runs the build, the agent never starts one. Frozen builds stay the
  lead's, on GitHub.
- The shared 3D architecture is inside this item, in order (operator, 12 Nov: "definitely put in the 3D work
  needed into the native work plan, in detail and order"): the port rewrites every renderer, so it is decided
  and built here, never afterwards and never twice. The old primitive ids: S3D-1 is N4.b, S3D-2 N4.c, S3D-3 N6.2
  (photo shells N6.4), S3D-4 N6.1, S3D-5 N4.d, S3D-6 N4.h, S3D-7 N4.f1 and N4.f2 with its smoke N6.3 and lightning N6.6.
  The old stage names: P3.1 and P3.2 are N2; P3.3 is N5.2; P3.4 is N5; P3.5 is NF; P4 is N4.f2 (N4.f1 is the fog volume port). What exists in
  the Python substrate and is therefore a port is listed in `Docs/Reference/Scene3D_Resources.md` ("Shared
  Scene3D capability inventory").

**Order.** N0 and N1 now. Then N2 (the substrate and Spectrum), N2b (the background layer and the first full
rehearsal), N3 (the 3D substrate). From there two ordered tracks, one High slot each: the **modes track** (N5.1,
N5.4, N5.6, N5.5, N5.3) and the **background track** (N5.2 a to h). Waveform Ribbon and Extruded Bubble go before
the modes with no measured need: they are the triggers, and Expanded Visualizer M6 waits on Extruded Bubble. The
**primitives track** (N4's unconsumed items, N6) runs whenever a High slot is free and never holds the flip. NF
(the flip) follows both tracks. After NF: SMP's foundations (item 9).

**P2 remainders (the worker is the default; none of these holds N0 to N2 open)**

- [ ] Make the framed-view negative control independent of presentation timing
  (`test_visualizer_owner_engine_worker.py::test_the_framed_view_the_worker_tick_reads_follows_the_owners_controller`).
- [ ] A target that never reveals: decide the bound (the existing loop can retry every six seconds), including
  stopping a failed owner's runtime on a refused reload.
  - [ ] Implement the bound at the owner.
  - [ ] Guard test with a negative control on today's loop.
- [ ] Bubble owner: define Random Group Drift's guarantee before retuning or asserting alignment
  (`test_bubble_reactivity.py::test_group_drift_aligns_non_swirl_bubble_motion[random-x]` depends on the draw).
- [ ] Neon Lake's driver memory at its first draw (`private_other`, about +280 MB committed, mostly not resident)
  is not attributed: read GPU allocations around the first draw before N5.5 sizes anything for it.
- [ ] P2-C1 remainder (closeout section 2): a failed high-water admission preserves the last good frame without
  silently changing the worker path; the load part only after the operator's yes.
- [ ] P2-C2 remainder: leases and holds release exactly once across Settings, mode switches, worker death, a
  failed reload and a Visualizer-off run; one worker and mapping at most, no worker cost while disabled.
- [ ] M5 remainder: measure the Studios and the post-failure fallback separately (the in-process and worker laps
  show a first-visit GPU high-water step, not growth).
- [ ] L3 remainder: `collect_ms` with the displays on and under load (the one live reading, 13.5-21 ms over four
  processes, was taken with the displays asleep and the Visualizer parked).
- [ ] L4 residual: a blocked cadence thread fails its session closed at the worker's heartbeat, but the thread
  itself stays in the worker until it returns.
- [~] D1 run (1B.14 harness), lead review of grabbed frames: a mode switch on the engine worker leaves no ghost
  of the outgoing mode after its fade-out (R-184: Sphere, Extruded Spectrum, Waveform Ribbon switches).

**N0. Decisions, contracts and proofs (design and harness only; can start now)**

- [ ] N0.4's remainder (D5.5 points 2 and 5), built with the first framed port (N5.4, then N5.6): the worker's tick
  calls `widgets/spotify_visualizer/framed_view_camera.py` (today only its test calls it) and publishes the
  finished camera in the mode's native schema; the renderer stops building one.
  - [ ] D5.5's test "one owner": no perspective or tangent construction in the native sources or schemas (negative
    control: `tan(fov / 2)` added to a core file).
  - [ ] D5.5's test "resize edge": the packet carries the extent its camera was built for; a frame whose stamp
    differs from the target holds the previous frame (negative control: ignore the stamp, a stretched frame).
  - [ ] Waveform's oracle in `tests/test_framed_view_camera.py` (`_renderer_waveform`) restates the renderer's
    expression: make the renderer and the test call one function, as Extruded Bubble's `parameter_camera` is.
- [ ] Offline Waveform hosts lost their pulse span with N0.4: a controller with no framed view gives `card_span`
  None and the fixed grid (`core/waveform_ribbon_dynamics.py:979,1057,1441`). The driver, the Studio and the foundry
  set one; these do not: `tools/visualizer_replay/waveform_ribbon_motion_audit.py`, `waveform_ribbon_signal_audit.py`,
  `waveform_ribbon_breathing_probe.py`, `tools/labs/waveform_ribbon_recorded_input.py`, `engine_worker_gate.py`,
  `live_engine_gate.py`, `live_engine_cost.py`. Before item 2's reactivity work uses them again:
  - [ ] One helper beside `configure_offline_controller` sets the framed view of the card a host models
    (`resolve_framed_view`); each host above calls it (the worker gates send it as `VIS_SET_VIEW`).
  - [ ] Guard: a Waveform tick in each of those hosts has a view span (negative control: today's hosts have none).
- [ ] N0.6 D6's proof (harness rounds 1 to 6 merged; the record is D6's "As proved" in the decisions document;
  - [~] The P1 desktop window's alpha, DPI and sleep/wake behaviour, validated by the lead on Display 1 (hidden-host
    results do not close it).
  evidence `.artifacts/evidence/native_core/n06/`). The validation layer (Khronos's Windows build in
  `D:/Temp/Scratch/SRPSS/native_spike/validation_layers/extracted/`) is given to the harness process alone with
  `--layer-path`: no registry entry, nothing persistent. Validation is clean apart from Qt 6.12.0's own defects, each
  excused only by its id, text and Qt caller (`run_n06.py` `QT_DEFECTS`; owners and sources in
  `Native_Core_N06_N07_Qt_Facts.md` section I): A (`QVkTexture::create` PREINITIALIZED with optimal tiling), B
  (`createOffscreenRenderPass` without an external dependency, only with non-preserving targets), D (Qt Quick's
  `grabWindow` on Vulkan, grab phases only). C (`toVkAccess(TexColorOutput)` write-only) is avoided by priming targets
  at creation and after every readback and is never excused. Owed:
  - [ ] **Qt 6.12.1 bump (lead; operator, 20 Nov: bump without asking).** Checked 20 Nov: PyPI still has PySide6
    6.12.0 only, and Qt's release plan moved 6.12.1 from 12 Nov to 23 Nov (wiki.qt.io/Qt_6.12_Release). When PySide6,
    PySide6_Addons, PySide6_Essentials and shiboken6 6.12.1 are on PyPI:
    - [ ] Pick a stage boundary (decision D11): no agent mid-build on `native/core`; agents merged or checkpointed.
    - [ ] Change the four pins in `requirements.txt`, then `pip install -r requirements.txt` with no venv process
      running (locked PySide6 DLLs make pip fail; restore a mixed set at once if it does).
    - [ ] Rebuild the native module on GitHub: the workflow reads Qt's version from that pin
      (`tools/native_sdk_fetch.py --print-qt-version`). Regenerate the `.qsb` packs if `regen_qrc --shaders --check`
      reports drift.
    - [ ] Rerun the native tests (`pytest tests -k native`), the N0.6 rounds without excuse A (the box below), and
      one Vulkan live check of a native mode on Display 1, then commit with the figures.
  - [ ] The A excuse is removed when the project takes the next Qt 6.12 patch release (the branch head already uses
    `UNDEFINED`): the upgrade's rerun deletes A from `QT_DEFECTS` and every round is clean without it.
  - [~] Awaiting Validation — lead, Display 1 visible and bounded, when two displays are connected: a real translucent window on the
    module's device: see-through to the desktop (D7 point 8's first route; the hidden runs cannot read the composed
    alpha), with the DWM system backdrop and the project's glass, then the swapchain under resize, DPI change and
    sleep and wake. If it is not see-through, D7's second route (DirectComposition) is tried next.
- [ ] N0.3: run the three scenes on Metal when a Metal machine is available (Watchlist).
- [ ] N0.7 remaining Qt 6.12 checks:
  - [ ] The handoff probe's inherited-state assertion was narrowed from Qt's whole sync to the item's
    `updatePaintNode` (`tests/test_qtquick_native_texture_handoff_gl.py:114-129`) on the statement that Qt 6.12's
    own sync resets the array-buffer binding; no control shows it. Add the control: a sync in which the adopting
    code does nothing, GL state read before and after. If the binding still changes, record it as Qt's; if not,
    restore the whole-sync assertion.
  - The rest of 6.12 is researched in `Docs/Future_Work/Qt_6_12_Gains.md` (merged 12 Nov; qtbase and qtdeclarative
    `changes-6.12.0` were unreachable, so the threaded render loop, layers, D3D12/DirectComposition and the Windows
    platform plugin are unread there). Placed: SMP's audio sink period and cover-art key in plan 02 section 4.1 and
    5.2; the SMP desktop window's backdrop call in N0.6. Checks on 6.12 (the venv moved on 12 Nov; Display 1 was
    off at the time, so the D1 part waits for it):
    - [ ] Text: DirectWrite now reads a font's GASP table to choose antialiasing. Compare text crops (a widget title
      and body text, the Settings dialog via the offscreen render route) before and after; a visible change in
      weight or crispness is recorded and judged by the lead.
    - [ ] QML required properties now fail instead of building silently: grep every run's log for "required
      property" and QML component errors after the bump (the next D1 run and the next hidden-window test run);
      each hit is fixed at its component.

**N1. Every shader portable, in the existing OpenGL renderer (no C++; can start now)**

- [ ] The beads at the near plane: D4.4's 1.4 px bound is geometric; check the bead shader's near culling and the
  near layer's defocus before the bound is quoted as visible error.
- [ ] Verify the drift programs through fxc/dxc and the Vulkan backend when the native core first runs them
  (D4.7's self-check reports a compiler that breaks the pairs). Other vendors are best effort, never tested.
- [ ] Side defect: `tools/gl_object_ledger.py:84` records only names a create call returns; objects created through
  out-parameters (`glCreateBuffers(1, arr)` in `scene3d/stream.py`, `population.py`, the defocus targets) are
  invisible to the lifecycle tests: record those too, with a test.
- [ ] Side defect: `waveform_ribbon.py:54` (`0.5*(clip.z/clip.w+1.0)`) and `scene3d_spheres.py:197` assume OpenGL's
  -1..1 depth: route both through `viewDepthFromDepthTexture`/the include before matrices are corrected at upload.
- [ ] Side defect (12 Nov evening audit, low): `tests/test_qrhi_texture_formats.py` scans `rendering/` only, by the
  enum's text, so a format QRhi lacks under `widgets/` (its shaders included) or reached through an alias passes.
  Scan `widgets/` too, with a control that plants an `rg16f` image layout there.
- N1.4's remainder: the eight scene composites in `scene3d/target.py:125-286` (and their oriented forms) keep raw
  `gl_FragCoord` and are never converted: D5.2 replaces them with a texture node.
- [ ] N1.6 Loose uniforms into blocks across the renderer (`qsb` needs blocks), each group pixel-identical in OpenGL
  before and after and with GL calls per frame recorded before and after (fewer calls is a gain today); `.qsb` baked
  for every backend, not `--glsl 460` only; each group leaves the readiness ratchet in the same change. A group whose
  conversion is not pixel-identical inside one dispatch is converted at its port instead. Order: by first consumer on
  the ladder, not N5's order. Remainder (ratchet 12; every other group is merged):
  - [ ] Prove new conversions and ports at the widened run set (variants `a` and `b` and, with `--offers`, every Choice
    offer: `tools/conventions_identity.py`, `tests/test_conventions_identity_runs.py`), first parent against merge.
  - [ ] Convert at its port, not here: Neon Lake's basin (`NEON_VERTEX_SOURCE`/`NEON_FRAGMENT_SOURCE`, one 8-bit level
    on 2-6 pixels with Glass on its block; `NEON_BLOCK` is kept as its layout) and Extruded Bubble's traced glass.
  - `rendering/gl_programs/lighting.py` belongs to N4.m: it is not a product shader (no `#version`; only its test
    draws it), and a program that includes it converts it (a 3088-byte block, about 3 KB of resources).
- [ ] D5.3's formats service, its one listed use: the scene target's multisampled velocity attachment
  (`scene3d/target.py`, RG16F kept; RGBA16F would add 127.5 MiB per 4K display at 4x, 255 MiB at 8x). Built with the
  substrate when the scene target ports (N3), or reconsidered if N1.8's resolve-first rule removes the multisampled
  velocity.
  Lead, 15 Nov (`Docs/Future_Work/Native_Core_QRhi_Research_N3.md` section 14): QRhi has no RG16F, so "RG16F kept" cannot be built natively. The native
  velocity is two R16F attachments, the same bytes as RG16F; RGBA16F only if the measurement shows two
  attachments cost more. A biased RG16 is refused: the single MRT clear value cannot encode zero velocity in it.
  The velocity resolve differs by backend (Vulkan averages, OpenGL blits nearest), so velocity resolves through
  the core's own per-sample pass (D14 point 10), nearest, on both.
- [ ] D5.6 row 13's control was not run: fill the widened targets' unused channels with non-zero values in a test, so
  a consumer that reads them fails (the scan and source checks show only `.rg`/`.xy`/`.rgb` reads today).
- [ ] N1.8 Per-sample multisample reads (`sampler2DMS`, `gl_SampleID`): each use resolves first and reads the
  resolve, with stills before and after; a use that cannot is listed for D5.3's per-sample service with the
  reason. The uses (D5.6 rows 7 and 15), one step each:
  - [ ] The composites' shader average over samples (`scene3d/target.py`, `_RESOLVE_GLSL`).
  - [ ] The per-sample OIT composite (`_OIT_RESOLVE_SAMPLES_FRAGMENT`, `gl_SampleID`).
  - [ ] The shaft source (`scene3d/shafts.py`, `_DOWNSAMPLE_SAMPLES_FRAGMENT`).
  - [ ] The background capture's nearest depth over samples (`_BACKGROUND_SAMPLES_FRAGMENT`; Extruded Bubble's
    refraction: the A/B of D5.6 answer 3).
- [ ] Waveform Ribbon hard-codes 4 samples (`rendering/quick/scene3d/waveform.py:381`) and the Oscilloscope 1:
  route both through the scene's sampling owner (N3.1 ports one owner, not three sources).

**N2. The substrate's 2D half and Spectrum (C++; `native/spike_p1` stays evidence, never a shipped renderer)**

- [ ] N2.2 leftovers (proved; `native/core/python/host_check.py`): one open item, the hidden host's stale Qt Quick contents; see Backlog.
- [ ] N2.4 leftovers (proved; `native/core/python/composite_check.py`): the Glass material on the native composite; see Backlog.

Order inside N2 (the numbers stay stable for the documents that cite them): N2.1 to N2.4, N2.6, N2.7, N2.5, then
N2.8, whose rehearsal closes N2.5's rule (f) and releases the Python renderer's retirement.

- [ ] N2.5 leftovers (merged 14 Nov at ABI 8): Studio on Vulkan, the two-block split, audit lows L6 and L8, an activation-deadline side defect; see Backlog.
- [ ] N2.9 leftovers (landed 14 Nov at ABI 10, decision D12): the sampler primitive (N4.a) and the Oscilloscope's primitives; see Backlog.
- [ ] N2.8 leftovers (Spectrum rehearsal passed 14 Nov): an empty Visualizer card frame with no renderable mode; see Backlog.

**N2b. The background layer, natively, and the first full rehearsal**

- [ ] N3.8 leftovers (landed 14 Nov at ABI 14, D9 "As built (N3.8)"): D8 row 3's contention gate and the warm-up job class; see Backlog.
- [ ] N5.7b leftovers (landed 14 Nov at ABI 16, D7 "as built (N5.7b)"): the slower-device fallback and glass over the live Visualizer; see Backlog.
- [ ] N5.2a leftovers (landed 14 Nov at ABI 15): first-frame pipeline and 4K cost, and a C++ side defect (a refused still draws black silently); see Backlog.
- [ ] N5.7c leftovers (D1 rehearsal on Vulkan, 15 Nov): real monitor sleep and wake, and the `[STARTUP_REVEAL]` gate for the native wallpaper; see Backlog.

**N3. The 3D substrate core (C++; harness scenes, no mode yet)**

Numbering kept stable for the documents that cite it: N3.5 (per-pass GPU timing) moved to N2.6, and N3.8 (the job
service) is built in N2b, where its first job (a photo's upload) is needed.

- [ ] N3.1b The four-sample capture cost on Vulkan (D14 point 13; settled before N5.6, Extruded Bubble, the first
  consumer of a four-sample capture). At 4K Vulkan's 4x minus 1x is 0.58 ms against the Python path's 0.41 (OpenGL
  0.45 is within noise, accepted); `cost_parts` puts about 0.5 ms of it in the capture step at four samples against
  0.08 ms single-sampled, and cannot split it further. The load-op fast clear is rejected (D14 point 12): do not retry it.
  - [ ] Per-run GPU timing inside a content: the GPU timer's scopes around each run of passes on a scene target, each
    core resolve (nearest, and QRhi's resolve at a run's end) and each capture, opt-in with the timer (no queries and
    no work when it is off: `core/diagnostics` rule), reported per scope in the content's state and the frame trace;
    a GPU-free test of the scope list and a harness check that the scopes sum to the surface's time within 5%.
  - [ ] Locate the capture step's 4x cost on Vulkan at 4K on a quiet GPU (`nvidia-smi` recorded with the figures),
    by scope: the nearest pass reading the multisampled D32F, the depth's layout switch (shader read to attachment,
    rule C's prime) before the second run, the second run's load of the multisampled attachments, the second colour
    resolve. Each candidate gets a harness control that removes it (with its pixels judged) before any fix.
  - [ ] Fix what the scopes show, if it brings Vulkan's 4K 4x minus 1x to the Python path's or below with parity
    exact and validation clean; otherwise the figure and its cause go to the lead with the operator's look question
    (4K defaulting to fewer samples).
- [ ] N3.3 leftovers: checkpoint audit 5's findings that D16's "As built after checkpoint audit 5" leaves to the plan
  (their boxes were lost in the 15 Nov merge 36faada69; still open in source, 20 Nov). Before the first compute consumer
  (N5.4, N5.6):
  - [ ] L2, a trigger consumed by a record that dispatches nothing: `ModeContent::decideDispatches` advances
    `lastTrigger`, `dispatches` and the fresh key before `recordCompute` may skip the entry (no pipeline, a group count
    of 0, groups past the device's limit). Decide the groups and the pipeline in `decideDispatches` and advance only an
    entry that dispatches; proof: a field-triggered stateful entry whose named group count is 0 for one record keeps
    that record's step for the next, control on the pre-change module.
  - [ ] L3, dispatch totals: only each dimension is bounded; the product of three admitted group counts is not (three
    record counts under at_most 65535 admit 2.8e14 groups, a TDR from an owner bug). Bound the product at admission and
    per record, refused at its edge as the per-dimension limit is; GPU-free test and a harness case refused with its
    reason.
  - [ ] L4, an image's zeros: `compute_passes.cpp` zeroes a storage image from one host `QByteArray` of a whole slice on
    the render thread (up to 256 MiB under `kMaxStorageImageBytes`). Upload them in bands of rows from one bounded block
    of zeros, proved by the copy round's zero reads on a 2D and a 3D image larger than one band; and decide whether
    `UsedAsTransferSource` (only the harness's readback needs it) stays on every storage image.
  - [ ] L5, the harness readback reaching the product: `NativeMode.read_storage` and `storage_data`
    (`rendering/native/mode.py`) are the harness's only; a test that no module under `rendering/`, `widgets/`, `core/` or
    `ui/` calls them, with its control.
  - [ ] M3's draw-side form: one render pass reading a storage buffer two ways (as `storage` and as `instance_from` or
    `indirect`, in one draw or two draws of a run) is admitted, and QRhi keeps one access a resource a pass. Refuse it
    at admission with the reason (or split the run), proved under validation with shader accesses on.
- [ ] N3.4 Transparency and post-processing (D17): source/proof complete; remaining investigation is non-blocking
  (operator, 16 Nov). Consumers retain their own parity, lifecycle and measured-cost requirements.
  - [ ] At Qt upgrades, recheck the private QRhi outside-pass `beginExternal`/`endExternal` contract against Qt source.
  - [ ] Non-blocking, deeper investigation by another agent: use R-232's retained timings, source/trace controls,
    failed avenues and unresolved hypotheses; choose one discriminating gather/control-flow or native-submission
    falsifier before running. Keep detailed evidence and machine conditions. Hardware counters are optional;
    profiler repair is not a prerequisite. No production barrier or tracking exception without proof. If a cause
    is established, verify the repair with both-backend `defocus_cost` and parity; this task does not hold consumers.
  - [ ] Awaiting Validation before a Waveform consumer: repeat `mesh_buffer_check.py --rounds stream_ring` on a quiet
    GPU, record load/clocks before and after, and review median margins plus the D5.3 tail watch. The available-GPU
    proof validates the harness, not quiet-GPU performance admission.
- [ ] N3.6 Lifetime (Opus High agent ab5da4c3c451f82c5, 21 Nov; built ABI 30 at e21923f1c, all three boxes pass on
  the build, branch head ebfe0944a; checkpoint audit by Opus High agent af5a9a2f30c88158c before merge): lazy creation on first use, release at retirement and at a mode switch, device loss rebuilt
  from the last packet, every state combination a pipeline built ahead and warmed gradually (Qt's pipeline cache
  file on Qt's pipelines; the core's own cache for raw ones); the working-set and GPU-memory readings of the P2
  audit rerun on it. On a lost device the Vulkan backend's `VK_EXT_device_fault` detail (vendor fault codes and
  addresses, Qt 6.12) is logged once, so a lost device on a user's machine is diagnosable.
  Decided by the lead, 15 Nov, from the research doc's sections 10 to 12:
  - [ ] Pipeline cache: pipelines the core builds on Qt's QRhi share Qt Quick's cache file, so they need nothing of
    their own. The job thread's QRhi and any raw Vulkan pipelines get one core file beside Qt's
    (`<CacheLocation>/qtpipelinecache-<abi>/srpss_core_<backend>`) with the same header check (driver version,
    vendor, device, cache UUID). A mismatch is a silent recompile. It is loaded at creation and saved at orderly
    shutdown, written to a temporary file and renamed, so two windows or processes never leave a torn file. The last
    writer wins, as with Qt's.
  - [ ] Device loss: the core owns the `VkDevice` Qt adopts, and Qt's recovery re-adopts the same device. So on
    `sceneGraphInvalidated` after a loss (`FrameOpDeviceLost` or `VK_ERROR_DEVICE_LOST`), the core destroys its dead
    device and hands the window a new one before Qt's next frame. Then it rebuilds every core object from the last
    packet. Settle the threading of `setGraphicsDevice` from that slot in the harness first. The proof is a
    harness-only module entry that forces the lost path (no env flag), on a hidden host, followed by a frame equal to
    one before the loss. On OpenGL the loss is detected only through a failed `makeCurrent`; the same rebuild
    applies.
  - [ ] Release timing: retirement calls `deleteLater` at once. The two-frame lag on Vulkan, and one frame on
    OpenGL, is accepted. Where no frame will follow (window retired, saver exit), the core calls `QRhi::finish()`
    at that edge, outside any frame; never mid-frame, which blanked Vulkan presentation in d1_run on 14 Nov.
    Raw Vulkan objects go to a deferred-delete queue keyed to their frame slot's fence, drained at device idle on
    teardown.
  Checkpoint audit 11 (21 Nov, `Docs/Future_Work/Checkpoint_Audits_Nov21.md`; N3.6 merged at ABI 30, b056a212c; M1-M3,
  L1-L4 with Opus High agent a8797a6d7c59d45af):
  - [ ] M1: a harness-only real loss: Qt's own QRhi must report `isDeviceLost()`. For example, the hidden host's
    device-function table answers `vkQueueSubmit` with `VK_ERROR_DEVICE_LOST` once, with no environment flag. Then rerun
    the rebuild round with `qrhi_lost` true and `faultReport` present. Or the lead records the window record's loss slots
    (Qt's threaded loop) as accepted unproven.
  - [ ] M2: a failed `vkCreateDevice` in `replaceDevice` is retried (for example, at the record's next frame edge or
    expose while `device_swapped` is false) instead of leaving the window black. Proof: M1's injection plus a forced
    create failure.
  - [ ] M3: the rebuild round also crosses a loss with a mode program that has storage, a scene target, bloom and
    meshes, with Spectrum, and with the background layer and a backdrop. Each frame after the loss equals the frame
    before it.
  - [ ] L1: `rhi_owned.h` states that a wrapper is retired before its QRhi, always: `deleteLater` on a never-created
    wrapper after its QRhi went is a use-after-free in Qt 6.12. `device_loss_check.py` proves that no core wrapper is
    live after `sceneGraphInvalidated`.
  - [ ] L2: a lost device's destruction tells its job service that the device was lost before `stop()`, so the job
    teardown never saves a lost device's cache (today it trusts the job thread's own observation).
  - [ ] L3: a failed cache-file commit is a reported skip, not red in `pipeline_cache_by_rule`, and the plan's "last
    writer wins" says "some writer wins". Run the real-blob round trip when the job QRhi's first pipeline, or the first
    raw `VkPipelineCache`, exists.
  - [ ] L4: `device_loss_check.py`'s release docstring drops the ABI 29 control it never ran; the OpenGL
    `no_wait_inside_the_frame` check is dropped or marked informational.
  - [ ] L5: at each Qt upgrade, recheck `QQuickRenderControlPrivate::resetRhi` against Qt source: its signature, and
    that `initialize()` reassigns `QQuickWindowPrivate::rhi`.
  - [ ] L6: the parent box's lazy creation, mode-switch release, pre-built and gradually warmed pipelines, and P2
    working-set/GPU-memory rerun are still open. They are not on the audited branch.
- [ ] N3.7 The orientation and quarter-turn contract (the scene frame's rotation in the composite) and the
  Expanded Visualizer's display-size targets at 4K (the M6 budget).
- [ ] N3.9 A display move keeps a mode's GPU-held history (1C.2, plan 01 M3c "Display moves retarget the live
  owner"): with one device per window (D6) nothing is shared, so the handoff is a copy through the job thread (D9)
  from the source device to the target's before the target integrates again; a test equal to an uninterrupted run
  (Extruded Bubble's drift first, N5.6).

**N4. Shared primitives, each against its Python harness, each ported just before its first consumer below
(the unconsumed ones on the primitives track)**

- [ ] N4.b Ribbon and strip (the bounded history buffer, centripetal placement by continuous index, the
  camera-facing width variant, multi-ribbon): Waveform Ribbon.
- [ ] N4.c Compacted populations (sprites and streaks, bounded lifetimes and emitters, compute-driven
  arrangement). Used today by the Disintegrate and Volumetric Dissolve transitions only. **High potential.**
  - [ ] The two transitions port 1:1 on QRhi's own indirect draw (Qt 6.12: `QRhiCommandBuffer::drawIndirect` for
    `scene3d/population.py`'s `glDrawArraysIndirect`; D5.3's indirect service is retired). "Draw the maximum, cull
    in the vertex shader" is built only as the path for a backend that does not report `QRhi::DrawIndirect`.
  - [ ] The port queries `DrawIndirect` and `DrawIndirectMulti` at runtime and records each backend's answer
    (`DrawIndirectMulti` is expected on Vulkan 1.1+, GL 4.3+ and D3D12 only; elsewhere Qt issues separate draws).
  - [ ] D8 plus 7, a QRhi-only build: the harness at one million sprites, the indirect draw against the cull path,
    same pixels, cost recorded.
- [ ] N4.d Planar reflections and rough receivers (Waveform's floor), the scene probe (Extruded Bubble),
  wet-surface masks (high potential). Neon Lake's water reflection is analytic in its own basin shader and needs
  none of this.
  Lead, 15 Nov (`Docs/Future_Work/Native_Core_QRhi_Research_N3.md` section 15): a cube renders as six passes, one render target per face (`setLayer`);
  multiview cannot render into a cube. Rough-receiver prefiltering is the core's own shader, never `generateMips`
  (a linear blit chain). The harness reads every face back on both backends first: face orientation may be
  mirrored between OpenGL and Vulkan.
- [ ] N4.e Heightfields and refined terrain meshes (the authored heightfield resource; Neon Lake's tile-refined
  basin; the grid a dynamic surface field will share).
  Lead, 15 Nov (`Docs/Future_Work/Native_Core_QRhi_Research_N3.md` section 16): vertex-stage sampling uses the binding's `VertexStage` flag with
  `textureLod`/`texelFetch` (QRhi has no feature flag for it); the heightfield is R16F or R32F read with
  `texelFetch`, so 32-bit float filtering is never required.
- [ ] N4.f1 The fog volume port (Waveform draws it today, so N5.4 cannot reach parity without it): ported just
  before its first consumer, N5.4, like every N4 item. The fog detail march (written and tested, runs nowhere in
  production: too costly at full size in the Python path) is the base of N6.3 and stays with N4.f2's reduced path.
- [ ] N4.f2 (placed after N5.6 and before Expanded Visualizer M6, see below) Reduced-resolution volumes and P4's
  mixed-resolution soft layers (D8 plus 4): bloom, reflection blur and wide glows at reduced resolution with
  depth-aware upsampling; lines, dots, rims, particles and UI stay at full resolution.
- [ ] N4.g Edge and propagation fields (the Edge Bloom and Capillary Bloom transitions only); sphere impostors,
  shared optics and underwater light (Extruded Bubble).
- [ ] N4.h Shared shadows (one fitted directional depth map, bounded soft filtering, caster and receiver
  admission, measured tiers). **High potential: built without a consumer**, proved on a harness scene; not a
  revival of the rejected Extruded cast shadows, and no mode turns it on without its own review.
  Lead, 15 Nov (`Docs/Future_Work/Native_Core_QRhi_Research_N3.md` section 13): comparison sampling through `QRhiSampler` compare ops on a depth-only
  pass (legal on both backends). The shader branches on `isClipDepthZeroToOne()`. Depth bias is tuned per backend
  and measured, never one shared number (the offset unit is implementation-defined, and Qt sets Vulkan's bias clamp
  to 0). Outside the light frustum is handled in the shader (no clamp-to-border in QRhi).
- [ ] N4.i Motion blur and trails (a velocity attachment, the tile-max compute, trails and motion uniforms): five
  transitions.
  Lead, 15 Nov (`Docs/Future_Work/Native_Core_QRhi_Research_N3.md` section 14): the velocity is the formats-service decision above (two R16F); the
  tile-max runs as compute over a storage image (D16) in a format the research lists as load-store on both
  backends.
- [ ] N4.j Backdrop environment (`BackdropEnvironment`: Extruded Spectrum and Sphere's wallpaper reflection), with N5.3;
  the photo half landed with N5.2c (ABI 36).
- [ ] N4.k Light shafts: the shared owner (Neon Lake today) and Extruded Bubble's own second implementation
  merged onto it, one owner (high potential); ported with Extruded Bubble, then used by Neon Lake.
  Lead, 15 Nov (`Docs/Future_Work/Native_Core_QRhi_Research_N3.md` section 17): volumes are written by compute (one pass, D16), never by per-slice
  rendering (one pass per slice, and Vulkan 1.1 instance API for slices).
- Topology rule for every N4 primitive (`Docs/Future_Work/Native_Core_QRhi_Research_N3.md` section 18): triangle lists or degenerate strips, never a restart
  index (OpenGL restarts every topology, Vulkan only strips); no wide lines (false on the OpenGL core profile);
  lines and points are instanced quads (D15).
- [ ] N4.l Silhouette shadows (Extruded Spectrum's directional silhouette and Sphere's own pass) as one shared
  primitive, distinct from N4.h; the bendable grid (Membrane, Page Curl); Exploding Tiles' planar shadows and
  particles.
- [ ] N4.m The soft-light array (up to 96 soft lights, `rendering/gl_programs/lighting.py`; written, tested, used
  by a lab only). **High potential: built without a consumer.**

**N5, modes track (one High slot; each box is one port under the port rule)**

Slots (lead, 12 Nov): the first port of each kind, and the heavy 3D ports (Waveform Ribbon, Extruded Bubble, Neon
Lake, Extruded Spectrum and Sphere), go to Opus High. Once Spectrum (N2.5) has proved the pattern, the simple modes
(Spline Curve, Oscilloscope, Bubble) go to Opus Medium, proved frame by frame against the Python renderer with the
identity harnesses. A difference that is not byte for byte goes back to the lead to judge. An audit reruns the port's
negative controls and one take per backend from the cited evidence; it never repeats the full parity sweep.

Rule for every port here (Qt 6.12): where a mode's small instanced batches (bars, specks, snow, sprite families)
are measured above a handful per frame, one pipeline and one indirect call with `QRhi::ShaderDrawParameters`
(`gl_DrawID`, `gl_BaseInstance`, `gl_BaseVertex`) replaces a draw per batch; the port records which backends report
the feature (D3D11 is not stated).

- [ ] N5.1 Spline Curve leftover: its Studio is not offered on Vulkan (`STUDIO_PREVIEW_BACKENDS`), the same open
  item as Spectrum's; both close with N5.8.
- [ ] N5.1 Oscilloscope (registered on the route and offered on Vulkan, 21 Nov; N3.4 bloom's first consumer). Python oracle:
  `rendering/quick/visualizer/implementations/oscilloscope.py`, `rendering/gl_programs/oscilloscope_program.py`; follow
  `Docs/Guides/Native_Port_Playbook.md`, proof under `Docs/Guides/Native_Parity_And_Timing_Proof.md` (section 7's split);
  harness `native/core/python/oscilloscope_check.py`. Built through ABI 29 (D12 "As built: Oscilloscope", "The pixel
  tolerance"); rule (a) passes all six 60 s takes and 14 of 15 offers, layer L identical, cost round passed
  (b8c6c3528). Evidence `n5_1_oscilloscope/` (`20261121_owner_offers_class/`, `20261121_n51_turned_abi29_band/`).
  Open parity and offer boxes: one line in the Backlog section (Oscilloscope parity and offers).
  - [ ] Side defect (found 20 Nov by the port): the legacy `widgets/spotify_visualizer/shaders/oscilloscope.frag` (and
    its `.qsb`) is drawn by no renderer (its own header says so; the beam files are the mode's shaders now), yet it is
    still the mode's registered fragment (`shaders._ALL_SHADER_FILES["oscilloscope"]`): `preload_fragment_shaders`
    composes it at startup, the route's `_ModeContent.load` reads its pack at every Oscilloscope bind (the program
    ignores it), and `generic_mode_check.py`'s product-pack round admits it as "the Oscilloscope's" pack. Retire it with
    its registry entry once the route no longer reads a mode's pack for a mode with its own program, and move the
    harness's admission check to the beam's packs.
  - [ ] Side defect (found 21 Nov by the turned-card agent): Python's `item_pixel_rect` (`rendering/quick/scene3d/
    frame.py`) gives the item one device pixel more than its size at some whole-pixel origins: a card 641 x 361 at
    (803, 517) in a 1920 x 1080 window at dpr 1 gets a SceneTarget rect 642 wide (at (801, 515) it is 641; at (800, 512)
    641 x 362), so its float32 snap misses an edge that is a whole pixel. It is the oracle the card's `scene_item` copies,
    so both renderers agree, but the SceneTarget is a pixel larger than the item. Reproduce: `_card` and
    `_pythons_scene_rect` of `tests/test_native_oscilloscope.py` with `viewport_extent=(641.0, 361.0)`,
    `outer_origin=(803.0, 517.0)`, dpr 1.
- [ ] N5.1 Bubble (registered on the route, offered on Vulkan; D12 "As built: Bubble"; statistics and eliminated
  suspicions `Docs/Future_Work/Native_Bubble_Parity_Investigation.md`; tools `Docs/Guides/Native_Bubble_Diagnostics.md`;
  follow the Native Port Playbook; no further tolerance widening). Proved: layer P on OpenGL over the four 60 s takes,
  on Vulkan over the 5.5 s replay only; L indirectly; C at 4K. Not proved: T. Rule (b) passes on the 5.5 s replay;
  owner rule (a) fails three steady frames on two of the four 60 s takes under today's rule. Remaining, in order:
  - [ ] Layer T on Vulkan (lead, Display 1): first runs 20 Nov match the Python OpenGL control in median and p90 and
    in tick-to-publish; the tail is heavier (frames over 16.7 ms 27, 39, 27 against 11, 16, 18), all of it after
    rendering ends, not sync or recording. Evidence `.artifacts/evidence/visualizers/{bubble,spectrum}/live_check/20261120_*`,
    `.../bubble/live_check/20261121_layer_t_root_cause/figures.txt` (agent aac773583ad93e2ab).
    - [ ] Root cause, two candidates, neither proved: (1) the PERF HUD's once-a-second text write from a queued
      `frameSwapped` handler (`_update_perf_hud_on_swap`, `rendering/quick/scene_controller.py`) starting Qt's update
      timer early; (2) the GPU downclocking under the lighter native load (the A/B adds clock sampling).
      - [ ] One-variable proof: the HUD's text writes off against on, three Vulkan and three OpenGL runs, alternating
        back to back, conditions recorded.
    - [ ] Fix, if proved: with a visualizer active, write the HUD text in `request_visualizer_present` just before
      `item.update()` so both share one Qt timer (keep writing on swap with none active); separately trim Bubble's
      per-frame route sync on the GUI thread.
    - [ ] Fix at the owner if it is ours, then three Vulkan runs and three OpenGL controls back to back; accept when
      Vulkan's late frames fall within the control's spread. If it is the driver's or Qt's, record it in D12 and ask
      the operator. Then Bubble's own T tools (its diagnostics guide).
  - [ ] Checkpoint audit 8 M1, what is left (D12's Bubble line):
    - [ ] A straight line of 65 one-level pixels (groups of 22) still passes the 16 x 16 density bound of 26: decide
      whether it needs its own rule.
    - [ ] Rule (b)'s density bound is not set (evidence `fast_proof/20261121_rule_b_60s_*`); it waits for the 60 s decision.
    - [ ] Rerun the offers and rule (b)'s 684 frames under the fix; classify any newly failing frame, never widen a bound.
  - [ ] Bubble's 60 s takes under today's rules (audit 8 M2; evidence `fast_proof/20261120_m2_rule_a_60s_*`,
    `20261121_m2_rule_a_60s_*`, `20261121_rule_b_60s_*`): classify and decide; no bound raised.
  - [ ] Tracked exceptions of the scene-fade double-rounding class (D12's Bubble line; no bound change): the
    `nightsolong_acousticsoft1` input 22 pair and the `stream_direction=2` and `=6` offer runs at input 337; they
    disappear when the scene-fade fix lands. Evidence `n5_1_bubble/20261117_offers/`, `20261117_offer_tie_classes/`.
  - [ ] GPU median and p90 per pass at 2560 x 1440 against the Python renderer's (checklist 11); 4K is measured (D12).
  - [ ] Ambience-off reads higher than ambience-on at 4K: variant b differs from variant a in many settings, so measure
    one frame with only the ambience switched (`bubble_check.py` `COST_RUNS`).
  - [ ] Native OpenGL is about 5 % slower than the Python renderer at the full 4K frame: input to the optimisation gate.
  - [ ] Conditional optimisation gate (operator, 16 Nov; after accepted parity and the per-pass cost check, before
    N5.4 and NF): name the measured Bubble-owned cost and its baseline first; a no-change result closes it. Full
    text (baseline, music matrix, exact-fidelity and speed proofs) in the Backlog section.
  - [ ] The D1 rehearsal (lead, rule (f), D10): one bounded Vulkan run on Display 1 through `tools/d1_run.py`, the
    Usu wallpaper and a recorded clip, ambience on and off. Deferred 17 Nov: Display 1 was off (`--list-displays`
    showed Display 0 only); run it when Display 1 is on.
- [ ] Non-blocking (does not hold the Bubble port): prove Bubble's rule-(a) scatter is the two-compiler case directly.
  Render Python's Bubble with the GLSL the qsb pack emits (the pack's GLSL variants in place of the composed source)
  over the `replay` recipe and show the steady residual collapses (from 2,430 one-level pixels, worst 34 a frame).
- [ ] Bubble optimisation proof gap: needs the fast long-clip proof's layer P tool (the box below) before the
  first Bubble optimisation; the rules are the guide's.
- [ ] Audit the fast-proof merge 79a5d1fe7 (Opus Medium audit agent a8810319889f3a218, 21 Nov): `tools/pixel_tolerance.py`'s M1 groups
  and density, the cheaper judge's equal-verdict proof, the reference cache key, the native-only and stream-player
  paths, and layer L's coverage of positional members.
- [ ] Build the fast long-clip proof (Opus Medium agent a6257c36aeee45f10, 20 Nov; method and rules:
  `Docs/Guides/Native_Parity_And_Timing_Proof.md` section 7):
  - [ ] Layer L built (e0275205c): `tools/visualizer_replay/native_record_identity.py`, test
    `tests/test_native_record_identity.py`; evidence `.artifacts/evidence/native_core/fast_proof/20261120_l_*`.
  - [ ] Layer T on native paths (open): the live check reads cadence from Qt Quick's frame cycles when the native core
    draws (`frames_per_s` is 0 on Vulkan today) and per-pass GPU time from `--gpu-pass-timing`;
    `tools/quick_frame_cadence.py` is the reference; prove it gives the Python path's swap-gap figures on an OpenGL run.
  - [ ] Layer P built (ddb3dc8b2, ec0bf3feb, 12a688e57, d0b2e8095, 29fc590c0): cached references
    (`tools/visualizer_replay/python_references.py`), native-only `--against`, `native_stream_player.py` for Vulkan
    (generic modes only; Spectrum's own item is not played yet), `--judge-workers`. Evidence `fast_proof/20261120_*`.
  - [ ] Coverage selection built (b4cd47802): `tools/visualizer_replay/coverage_windows.py`, test
    `tests/test_coverage_windows.py`; evidence `fast_proof/20261121_coverage_bubble_<take>/`.
- [ ] N5.4 Waveform Ribbon (N4.b, N4.d's planar reflection, N4.f1's fog volume, its five compute passes and three
  rings, floor and pulse-rim textures; not populations): the mode over its render budget under load, measured
  against the 11 Nov load session (item 7).
  - Reading (reference; Sonnet agent af6ce7875bfd45d8f, 21 Nov, merged), as the Oscilloscope's: the record each frame carries
    (what is per frame from the logical frame, what is per Settings or card change), each stream's size rule, every
    pass with its targets and attachments (the five compute passes, the three rings, the planar reflection, the fog
    volume, the floor and pulse-rim textures, bloom if any), how it turns (Waveform is a turned scene consumer: the
    Oscilloscope's turned-card anchoring box serves it), and its clear. Then confirm in writing, against the ABI 28 core
    (`native/core/src`, `Docs/Future_Work/Native_Core_P3_Decisions.md` D12-D17), what the port needs that the core
    lacks: one C++ box each here, with what its proof must show. Cite file and line for every claim.
    Reading (Sonnet, 21 Nov, no code touched). `waveform.py` is `rendering/quick/scene3d/waveform.py`; `parameters.py`
    is `widgets/spotify_visualizer/waveform_ribbon_parameters.py`; `D15` etc. are in `Native_Core_P3_Decisions.md`.
    - Per frame from the logical frame (`WaveformRibbonFrame`, `widgets/spotify_visualizer/render_state.py:835-854`,
      built at `widgets/spotify_visualizer/waveform_ribbon_capture.py:62-67`): the knot packet (instances, vertices,
      world and coordinate origin), time, travel, passage, zoom, the camera parameters, the event-spark births and
      their origin, the strand cohorts and their origin, the pulse field (385 floats, `core/waveform_ribbon_dynamics.py:55`).
      The Recipe is rebuilt every frame as well (`parameters.py:96-142`): material, fog density, displacement, height,
      softness, light, variation and drift, floor reflectivity, brightness, wetness, streak and column, sparks,
      strays, bloom and the published travel direction move with passage, sparkle and highlights. The world colour
      grade is evaluated per frame from passage (`waveform.py:69-80,277`).
    - Per frame in the renderer today, so for the worker to publish (D5.5, the N0.4 box above): view, projection, eye
      and lens (`rendering/quick/visualizer/implementations/waveform_ribbon.py:64-67`), the scroll `head_x - travel`
      (`waveform.py:258-259`), the history mirror (`:263-267`), the mirrored view (`:431`), the continuation span
      (`:269-276`) and the culled draw ranges of every ribbon draw (`rendering/quick/scene3d/ribbon.py:122-179,260-268`).
    - Per Settings or card change only: which stages exist (fog `waveform.py:245-247`, sparks `:243`, strays `:242`, floor
      give `:248-250`, Pulse Rim `:252-254`), the 4 samples (`:34`), the three floor maps (`:117-144`, loaded once), the
      fog grids (camera: min(128, ceil(w/cell)) x min(72, ceil(h/cell)) x 96/128/160 slices by quality, `waveform.py:338`,
      `parameters.py:79`; mirrored: cell 32, 96 slices, `core/waveform_ribbon_scene.py:46-47`), the reflection target
      size (`min(.5, 360/h)` of the item, `waveform.py:83-87,432`, `core/waveform_ribbon_scene.py:79-80`) and the floor's
      reduced pre-pass size (`waveform.py:528,534`; only past 1080 px tall, `core/waveform_ribbon_scene.py:81`).
    - Streams and size rules (a slot holds 1 MiB, `core/visualizer_engine/frame_capacity.py:9`; the four fields total at
      most 411,396 bytes): knot packet instances x 20,544 B (`core/ribbon_packet.py:11-16`; 4 ribbons,
      `core/waveform_ribbon_authoring.py:10`, so 82,176 B; checked `render_state.py:860`); strand cohorts instances x
      16,384 B or empty (`core/ribbon_strand_cohorts.py:8-9`, `render_state.py:873`); event sparks empty or exactly
      4,096 x 16 x 4 = 262,144 B (`core/ribbon_bursts.py:9-10`, `render_state.py:866`), bound twice a frame; pulse 1,540 B
      (`render_state.py:829`). The three rings are the three stream rings, each 3 slots of 4 binds: "ribbon knots"
      (`ribbon.py:243`), "ribbon strand cohorts" (`ribbon.py:500`), "ribbon event sparks"
      (`rendering/quick/scene3d/ribbon_bursts.py:52`). (If "three rings" meant ribbons: 4 here, 8 in the packet.)
    - Passes of a frame in order, fog, Floor Give and Pulse Rim on (`waveform.py:228-307`): packet upload (`:231`);
      compute: floor give sections and blur (`rendering/quick/scene3d/floor_give.py:80-88`), world field
      (`rendering/quick/scene3d/waveform_field.py:55`), fog inject and integrate for the camera and again for the
      mirrored camera (`waveform.py:298-300`, `rendering/quick/scene3d/fog_volume.py:155-167`): seven dispatches, five
      programs (D16). Reflection target (`waveform.py:428-466`): cleared to 0 and depth 1
      (`rendering/quick/scene3d/reflection.py:101-103`), reflected sky (`:441`), ribbon light (`:446`: its body draw
      and two continuation extension draws, `ribbon.py:380-391`), strays (`:453`), event sparks (`:460`), then its mip
      chain (`reflection.py:111`). Scene target (`waveform.py:379-425`: 4 samples, overlay, bloom, OIT, HDR at the
      exposure, `:382-383`): sky (`:392-395`, depth test off), floor (`:396`, `:469-559`; past 1080 px tall a reduced
      pre-pass into its own RGBA16F target first, `:528-557`), ribbon body in the transparency block (`:400-401`,
      resolved per sample on leaving it, `rendering/quick/scene3d/target.py:768-812`), ribbon light additive
      (`:402-407`), strays (`:413-419`), event sparks (`:420-423`), then the emission's bloom and the overlay composite
      (`target.py:937-975`).
    - Attachments and formats: the scene's colour is RGBA16F under HDR (`target.py:548-551`) beside the emission and a
      depth; the body writes accumulation, coverage and emission at location 2 (`rendering/gl_programs/ribbon.py:765`);
      light, floor and sky write colour and emission (`ribbon.py:800-801`, `rendering/gl_programs/waveform_ribbon.py:88-89`,
      `rendering/gl_programs/waveform_atmosphere.py:180`); the reflection is RGBA16F with a full chain and a D24 depth,
      alpha the weighted height, blend ONE, ONE (`reflection.py:59-74`, `waveform.py:435-438`); the fog volumes are 3D
      RGBA16F (inject, integrated) and R16F (steady) (`fog_volume.py:94-101`); the world field is RGBA32F 1024 x 8
      (`waveform_field.py:38`, `waveform_atmosphere.py:12`); floor give RGBA32F 1024 x 4 and 1024 x 3 (`floor_give.py:67`,
      `waveform_floor_give.py:19`); the pulse field R32F 385 x 1 (`rendering/quick/scene3d/pulse_rim.py:54`); the floor
      maps RGBA8 with mips and 8x anisotropy, the slope map RGBA16F with mips baked from the height map
      (`waveform.py:96-144`). The floor fragment binds 8 samplers, reads the packet as storage and writes
      `gl_FragDepth` (`rendering/gl_programs/waveform_ribbon.py:166,282-285`, `waveform_atmosphere.py:13-17,79,110`).
    - Turning: the frame is oriented before anything draws (`waveform_ribbon.py:27,60`, `rendering/quick/scene3d/frame.py:38-66`),
      the scene is drawn unturned at the oriented item size (the camera aspect comes from it, `waveform_ribbon.py:64-67`),
      and only the composite and the bloom's first samples are oriented (`target.py:939-941,980-1000`, programs
      `target.py:388-389`, `waveform_ribbon.py:39-40`). The core refuses a turned bloom or composite
      (`native/core/src/mode_content.h:445-447`, ABI 28), so Waveform is the turned-card box's second consumer.
    - Clear: `waveform.py:386-387` writes backdrop x .35, alpha 1, into colour 0 after the scope's own clear
      (`target.py:918-926`). The backdrop is the Recipe's default Environment (`core/waveform_ribbon_scene.py:22`) and
      Settings never set it (`parameters.py:37-40` builds the Recipe without one): a constant in production. With fog on
      the sky overwrites the clear everywhere (`waveform_atmosphere.py:182`, depth test off `waveform.py:393`), so it
      shows only with Mist off. A target's clear lives in its declaration, is written into the block arena once per build
      (`native/core/src/mode_content.cpp:6722-6730`) and is compared by `sameLayout` (`native/core/src/scene_targets.cpp:188-190`):
      a changed value rebuilds the target.
    - Found while reading, shapes the port:
      - Bloom is per frame and reaches 0: `bloom=pair(bloom, passage)` (`parameters.py:142`), range 0..1
        (`core/settings/visualizer_mode_settings.py:2167`; default 0.14 to 0.14, `core/settings/default_settings.py:983`).
        At exactly 0 Python draws the frame with no HDR, no emission and no bloom (`target.py:564-568`, `waveform.py:382-383`:
        a plain overlay, no tone map). D17 choice E assumed no consumer's strength reaches 0 (`Native_Core_P3_Decisions.md:2263-2266`).
      - The point-sprite sparks (`ribbon.py:408-444`, `gl_PointSize`) never draw in production: they run only without a
        burst payload (`waveform.py:408`) and the renderer always gives one (`waveform_ribbon.py:69-70`, `:32` prepares
        no spark program). The port draws the event sparks (instanced quads already, `ribbon_bursts.py:67-71`) and the strays.
      - Counts against the core: 7 compute entries and about 15 draws are 22 passes (28 if the three continuation draws of
        body, light and reflected light are separate passes) against `kMaxModePasses` 16 (`native/core/src/mode_content.h:187`,
        checked `mode_content.cpp:2152`); 9 storage images with Floor Give on (field 1, give 2, two fog volumes 3 each; 7
        off) against 8 (`compute_passes.h:55-57`, `mode_content.cpp:2241`); 4 scene targets (scene, transparency,
        reflection, pre-pass) of 4 (`scene_targets.h:69`), no headroom; the floor's 8 samplers of 8 (`mode_content.h:262`).
      - The continuation draws start at a vertex that varies per frame (`ribbon.py:380-391`) while `first_vertex` is a
        number (`mode_content.h:348`) and batches are instance ranges (D15 point 6, `Native_Core_P3_Decisions.md:1590-1592`):
        a vertex-shader offset or indirect commands from the record, decided at the port (shader work, no new C++).
      - The pulse field is a per-frame R32F texture (`pulse_rim.py:50-62`) and the core uploads textures from the GUI
        thread as RGBA8 only (`mode_content.h:35-37`): a storage stream and an in-shader linear read needs no C++, and
        the Python shader changes with it (one shader file for both renderers, `mode_content.h:3-4`).
      - Already in the plan: the quiet-GPU `stream_ring` recheck before a Waveform consumer (the N3.2 box "Awaiting
        Validation before a Waveform consumer"; D15's watch, `Native_Core_P3_Decisions.md:225`).
  - Core features landed (ABI 33, merged 21 Nov, proofs in the merge commit): exact-size drawable mipped targets,
    shader anisotropic taps, RGBA16F item textures with GPU mips, 28 passes and 9 storage images, linear-filter facts.
    Port decisions (lead, 21 Nov): the floor's anisotropy is the shared tap text (`rendering/gl_programs/anisotropic.py`)
    in both renderers; every level chain a sampler reads is the core's box kernel (`mip_box.comp`, Python's
    `rendering/gl_programs/mip_chain.py`), so Python's reflection and Waveform's own read item textures (the 1254 px maps)
    move to it at the port, by an opt-in flag (existing mipped item textures keep their path); the look change is judged on the port's showcase. Next: the port itself (records, streams,
    passes and the proof), Opus High.
  - [ ] Port decision: Waveform clears its scene colour every frame to a backdrop from its recipe
    (`rendering/quick/scene3d/waveform.py:387`), while a native target's clear value is fixed in its declaration
    (D14; D17 point 9). Decide the port's form (a clear value filled by a setting, or a first pass that writes the
    backdrop) and prove it against the Python renderer under the port rule.
    - Needs (Sonnet's reading, the lead decides). A clear value filled by a setting: C++ and an ABI bump: `clear`
      takes a setting name, the clear block is refilled when the setting changes (today once per build,
      `mode_content.cpp:6722-6730`) and `sameLayout` stops comparing it (`scene_targets.cpp:188-190`) so a change
      rebuilds nothing; proof: two backdrops against Python with no pipeline rebuild (control: the value changed in
      the declaration, which rebuilds). A first pass: data only, no module build: a surface-sized pass, blend replace,
      depth off, first in the list, colour 0 from a setting in its block and alpha 1; one of the pass budget and one
      more full-target 4-sample write a frame under the target's own clearing draw; proof: frames equal to
      Python's (control: the pass removed).
    - Recommendation: neither yet. The backdrop is a constant in production (the reading's Clear line), so declare
      `clear` once as backdrop x .35 when Python builds the program (a backdrop change is then a program change, the
      rule for every stage, D17 E), with no C++ and no pass. If Settings ever expose the backdrop, take the first pass:
      it is data and costs a pass of the budget, where the setting-filled clear costs C++ and an ABI bump for a
      value no other consumer varies.
    - Lead decision (21 Nov): the recommendation. `clear` is declared once as backdrop x .35 when Python builds the
      program; no C++ and no pass. Revisit only if Settings expose the backdrop (then the first pass).
- [ ] Waveform travel-speed reactivity (operator; after N5.4's acceptance, additive to its native record): the mesh's
  travel has no reactivity control for its speed. Add ONE range slider (two handles): its low end is the minimum
  speed at the least energy, its high end the maximum speed at the highest energy, and the speed between follows
  the overall music energy (wired to real energy, calibrated on recorded music, never pinned at either end). Attack
  is faster than decay and the decay is gentle (both exposed as options with those defaults). Check for a missing
  base speed and idle speed; audit these controls so they complement rather than conflict. Every preset's default stays exactly what it is now (Settings spec system,
  `core/settings/visualizer_mode_settings.py`); reaction check with `waveform_music_response.py`.
- [ ] N5.6 Extruded Bubble (the drift compute of D4, transparency, HDR, the depth texture and background
  capture, the probe and defocus, N4.k, N4.g's impostors and optics; not populations).
  - [ ] First, before any port reference is recorded (operator, 21 Nov): root-cause and fix on the Python side the three
    Extruded Bubble defects in section 1B (the wake-teleport box, Preset 9's flickering star of bubble lines, living
    bubbles not accelerated by music), so the port copies the fixed behaviour and its references are right the first
    time. Each fix gets its own tests and evidence as its box says; then the port's references are taken.
  - Reading (reference; Sonnet agent a531eca73061cfa21, 21 Nov, merged), as Waveform's reading above: the record per frame and
    per Settings or card change, each stream's size rule, every pass with its targets, formats and attachments (the
    drift compute, transparency/OIT, HDR, the depth texture and background capture, the probe, defocus, impostors and
    optics), how it turns, and its clear; then what the port needs that the ABI 28 core lacks beyond Waveform's six C++
    boxes (one box each, with what its proof must show), and which of Waveform's boxes it shares. File:line for every
    claim. Extruded Bubble is its own mode: never read the original Bubble as its oracle.
    Reading (Sonnet agent a531eca73061cfa21, 21 Nov, no code touched). `eb.py` is
    `rendering/quick/visualizer/implementations/extruded_bubble.py`; `prog.py` is `rendering/gl_programs/extruded_bubble_program.py`;
    `scene.py` is `rendering/gl_programs/extruded_bubble_scene.py`; `solver.py` is `.../implementations/extruded_bubble_drift_solver.py`;
    `log.py` is `widgets/spotify_visualizer/extruded_bubble_drift_log.py`; `target.py`, `probe.py`, `defocus.py` are in
    `rendering/quick/scene3d/`; `D4` etc. are in `Native_Core_P3_Decisions.md`.
    - Per frame from the logical frame (`ExtrudedBubbleFrame`, `widgets/spotify_visualizer/render_state.py:732-762`): the
      bubble records (8 floats), cluster records, time, level, flash, sustain, drift, emission, stream and its speed, travel,
      rays, shimmer, motion phase, passage, chain activity, chain drive, the wake records (50 floats each), the drift
      families, the step log and the knot decisions. The Settings parameters ride in the same frame as frozen fields.
    - Per frame in the renderer today, so for the worker to publish (D5.5, the N0.4 box): the compaction of live shells
      (`scene.py:289-291`), the cluster packing (`:310-325`), each shell's glint proxy (`:328-341`, `eb.py:559-562`), the
      four largest shells for the shafts (`eb.py:583-585`), the camera (`:535-536`, one assembly the logical side builds
      too), a deep light's direction from the eye (`:537-541`), the light's screen position (`:600`, `scene.py:351-358`),
      ray strength, flicker and reach (`eb.py:564-568`), the chain, snow, fizz and speck fills and the instance counts
      they give: beads x 160, snow, wakes x fizz-per-wake, specks (`:611-619,648-654`, `_BEADS_PER_CHAIN` `:94`).
    - Per Settings or card change only: the knots (`eb.py:514-516`, `scene.py:114-192`), the near layer's optical height
      (`eb.py:517-523`), the sample count and so the programs (`:131-133,430-435`; 4 at High, 2 at Balanced, 1 below,
      `rendering/gl_programs/scene3d.py:81-87`), the probe's face size (256, 256, 128, 64 by tier, `eb.py:86,421-428`),
      the shaft targets at half the card (`:149-170`), the near layer at the exact card size (`defocus.py:250-297`), the
      scene target (`eb.py:498-499`), bloom 0.55 and HDR exposure 1.0, both constants (`:87,684-685`).
    - Streams and size rules (a slot holds 1 MiB, `core/visualizer_engine/frame_capacity.py:9`): shells at most 192 x 32 B =
      6,144 (`eb.py:89,403`, `widgets/spotify_visualizer/extruded_bubble_simulation.py:49`), clusters 96 x 76 B = 7,296
      (`eb.py:90,406`, `scene.py:40`), proxies 192 x 32 B = 6,144 (`eb.py:407`), wakes 384 x 200 B = 76,800 (`eb.py:404`,
      `core/constants/extruded_bubble_world.py:34`), steps 128 x 30 float32 = 15,360 (`log.py:29-37`; the frame holds
      their float64 form, 30,720) and knots 128 x 240 chains x 12 B = 368,640 (`log.py:286-287`,
      `widgets/spotify_visualizer/extruded_bubble_material_paths.py:12-14,184-187`). Today the slot also carries the drift
      geometry at its maxima: chains 240 x 48 B, snow 2,500 x 32 B, specks 216,000 x 32 B = 6,912,000
      (`frame_capacity.py:12-42`, `core/constants/extruded_bubble_world.py:11-12`), 8,420,736 B in all. Python uploads only
      the steps newer than the last applied (`solver.py:728-743`); a storage stream uploads its used bytes whole each
      record (`mesh_buffers.h:12-15`),
      up to about 0.4 MB. Six streams (shells, clusters, proxies, wakes, steps, knots) of `kMaxModeStreams` 8
      (`mesh_buffers.h:55`).
    - The drift (`solver.py:680-875`), D4's solver: per family geometry once per revision, a state buffer of 16 B per knot
      or mote (chains 240 x 128 knots = 491,520 B; snow 40,000; specks 3,456,000), an aux buffer (`:817-843`) and one
      output of at most 262,144 vec4 = 4,194,304 B (`:650-678`). Three programs: chains (local size 128, one group a
      chain row, shared memory and `barrier()`, `:185-240`), snow and specks (local size 256, `:242-302`) and the pair
      check (`:308-319`), every dispatch only when a step is newer than the applied serial (`:716-717`), each with a
      64-byte block (`:67`). A geometry edit runs the old revision's pending steps on the old rows, copies the history onto
      the new geometry (the rebase reads both geometries, bindings 9 and 13, `:204-209,263-271,757-776`), then runs the new
      steps; a capacity growth keeps the prefix (`:834-839`); a render gap past 128 steps (about 1.4 s, `log.py:37`)
      restarts a family from zero (`solver.py:799-801`). The draws read the output as storage at binding 6
      (`prog.py:1454`) and the wakes at binding 7 (`:1397`).
    - Passes of a frame in order (`eb.py:679-767`). Probe (`:681,794-821`, `probe.py:264-304`): an RGBA16F cube with a full
      chain (`probe.py:162,192`), one D32F depth shared by the faces (`:206`), each face cleared to (0,0,0,1) and depth 1
      (`:284,289`); per face the backdrop in probe mode (`eb.py:799-806`, `prog.py:187-199`) and each shell's glint proxy,
      an instanced quad added ONE, ONE, depth write off (`eb.py:807-818`); then every level below the top filtered from
      the level above of the same cube, one draw a level, a geometry shader with six invocations writing `gl_Layer`
      (`probe.py:58-73,231-262`), 32 Gaussian taps over a cone (`:76-103`). Shafts (`eb.py:682,823-846`): the march at
      `max(1, w // 2)` into an R16F target (`:149-170`), then two separable blurs between two such targets. Scene target
      (`:684-685`: overlay with the card's fade, bloom, depth texture, OIT, HDR; colour RGBA16F beside the emission,
      cleared to 0): backdrop (`:696-701`), specks, instanced quads added to colour and emission, vertex-pulled over the
      drift output (`:702-713`), the capture (`:714`, `target.py:616-690`), the transparent block (`:717-746`,
      `target.py:692-740`: shells, clusters, one instanced beads-snow-fizz draw over the wakes and the drift output, the
      wake trails as a strip of 82 vertices a wake), resolved per sample on leaving (`target.py:768-812`). Near layer
      (`eb.py:747-764`): near shells and clusters into the `DefocusLayer` (RGBA16F colour and circle, full chains, the
      exact card size, cleared to 0, premultiplied over and MAX, no depth: `defocus.py:250-297,322-350`), then its
      composite: mips, clip, 64 plus 32 gather taps, highlight sprites (`:366-431`; read level 4 at 2160 px optical
      height, `:316-320`, `eb.py:88,99-101`); recorded only when a shell or cluster exists (`:751`). Leaving the scope:
      emission resolve, bloom chain, tone-mapped overlay composite (`target.py:937-975`, D17 "What the consumers do
      today"). Compute (`eb.py:549`) comes first in the frame.
    - Attachments and formats: scene colour and its capture RGBA16F, capture depth R32F nearest, colour linear
      (`target.py:672-690`); the transparent passes write accumulation (0), revealage (1) and emission (2)
      (`prog.py:1110,1257,1898`); the near passes write colour and circle (`:1112,1259`); the probe cube RGBA16F; the shaft
      targets R16F (`eb.py:159`). Samplers: the shafts, the captured colour and the probe (`prog.py:1997`); the shell
      fragment samples the cube with `samplerCube` and `textureSize` (`:718,950`) at the trilinear levels
      `sceneProbe` walks (`probe.py:111-118`).
    - Turning: the frame is oriented first (`eb.py:472,502`), everything draws unturned at the oriented item size, and
      only the composite and the bloom's first samples are oriented (`target.py:939-941,980-1000`). The core refuses a
      turned bloom or composite (`native/core/src/mode_content.h:445-447`, ABI 28), so Extruded Bubble is the turned-card
      anchoring box's third consumer (after the Oscilloscope and Waveform).
    - Clear: all constants. The scene's colour and emission clear to 0 and its depth to 1 (`target.py:923-926`), the OIT
      attachments to 0 and 1 (`:715-716`, the core's coverage stored inverted, D17 B), the near layer to 0
      (`defocus.py:341-342`), the probe faces to (0,0,0,1) with depth 1 (`probe.py:284,289`); the shaft targets are fully
      written. No port decision is open (Waveform's backdrop clear has no counterpart); the cube's alpha 1 is a clear
      value of its own declaration.
    - Found while reading, shapes the port:
      - The scene's depth is inert in production. The backdrop and specks draw with the depth test off (`eb.py:680,707-712`),
        the transparent block tests with the write mask off (`target.py:724-725`), the near layer has no depth
        (`defocus.py:343-344`), and the capture's depth is dropped (`eb.py:714`: `_depth` is never read). So the depth holds
        its clear of 1 all frame, and the `gl_FragDepth` writes (`prog.py:1048,1066,1217`) only reject a fragment at the
        far plane. Declaring the scene target without depth would save the multisampled D32F, the nearest resolve and the
        capture's R32F (D14 point 10 kept the nearest depth "as Python does", `Native_Core_P3_Decisions.md:1378-1379`), but
        the core refuses `gl_FragDepth` into a target without depth (`mode_content.cpp:688-691`) and Python's shader is
        the same file (`mode_content.h:3-4`): both renderers drop the writes together, proved by equal frames.
      - The core refuses what Python's shared programs do: a fragment output at a location past the target's attachments
        or an attachment left unwritten (`mode_content.cpp:664-683`; this answers Waveform's two-outputs question), and
        `gl_FragDepth` into the near target, which has none (`:688-691`). The backdrop's `Emission` output over the
        one-attachment cube face, and the near passes' `gl_FragDepth` (written outside the `NEAR_LAYER` guard,
        `prog.py:1048,1066,1217`) need fragment variants (a `#define`), the same file for both renderers.
      - The probe's backdrop declares the shafts sampler and reads it only outside probe mode (`prog.py:188,193-198`),
        and the shafts draw after the probe in a frame (`eb.py:681-682`): the probe variant drops the sampler (else the
        target would need `previous_frame`, `scene_targets.h:110`). The shell programs declare `uEnvironment`, bound
        nowhere (`prog.py:714,1997`), which the core refuses as unbound (`mode_content.cpp:619-624`). The traced glass
        keeps loose uniforms (`prog.py:2017-2019`): converted to blocks at the port (the plan's 1D.11 notes, with the
        binding-6 collision and the probe geometry shader's lack of HLSL).
      - The shaft and blur shaders address their targets by `fragUv(uFrameSize)` and `textureSize` (`prog.py:195,586`):
        with a bucketed allocation (`scene_targets.h:15-22`) `textureSize` is the allocation, and a bilinear read at the
        content's edge reads the slack (cleared 0) where Python clamps. Fixed in the shader (content from `u_target_px`,
        reads clamped inside the content) unless Waveform's exact-size box answers "exact" for every explicit target.
      - Counts against the core: 32 pass entries (3 compute, 12 probe draws, 1 prefilter, 3 shafts, 13 in the scene:
        backdrop, specks, capture, 4 transparent, resolve, 2 near, defocus, bloom, composite; 33 with the pair check)
        against `kMaxModePasses` 16 (`mode_content.h:187`, checked `mode_content.cpp:2152`), whose mesh mask holds 32
        (`:5040-5041`); 5 scene targets (scene, its transparency target, near, two shaft targets; 6 with the cube) of
        `kMaxSceneTargets` 4 (`scene_targets.h:69`); 7 storage buffers (state and aux per family and the output; 8 with the
        check's results) of 8 (`compute_passes.h:55`); 6 streams of 8; no storage image.
      - The near layer's read level must stay inside `defocusReadLevelCap` (`post_stages.h:163`, over the bucketed
        allocation, D17 H); the level is 4 at 2160 px optical height and grows with it, so the proof runs the largest
        framed aperture.
      - Revisions are 64-bit (`core/visualizer_engine/engine_worker.py:176`, `namespace << 32`) and a record trigger or
        member is a u32 (`compute_passes.h:24-29`): the record carries a small per-family epoch and a rebase flag, the
        worker's mapping (no C++).
      - A family that cannot advance fades its held drift out (`solver.py:491-517`); natively a device without the compute
        refuses the program (D16 point 6), so the fade has no counterpart.
      - Already in the plan: the four-sample capture cost on Vulkan (N3.1b, before this item), N3.3's L2 to L5 leftovers
        (before the first compute consumer), the display move's history copy with the drift as its first consumer (N3.9),
        the turned-card box, and the Light Shafts owner merged with Neon Lake's (N4.k, ported with this item).
  - [ ] C++: the scene probe (N4.d's EB half). The core has no cube: a sampler is `sampler2D`, or `sampler3D` for an image
    (`mode_content.h:28,282`), a scene target has no layers (`scene_targets.h:74-130`) and nothing in `native/core/src`
    mentions a cube or a layer write. Needed: a cube colour target (RGBA16F, exact size per tier, a full chain, its own
    clear value, one D32F shared by the six face passes, cleared per face), the face passes (a pass drawn per face with
    the face's block, or twelve entries: the pass budget decides), the core's own prefilter (N4.d's lead decision, the
    plan's N4.d box: six passes a face, never `generateMips`; no geometry-shader `gl_Layer`, which D3D lacks, the plan's
    1D.11 note), a `samplerCube` bound by name with a mip filter, seamless across faces, and the chain's rule under
    QRhi's whole-texture tracking (a level written from the level above of the same texture, D17 point 4's one texture a
    level: per-level cubes copied into the one mipped cube the shells read trilinearly, or another form; measured).
    Proof, both backends, each tier size: every face read back against Python's capture of the same scene (the face
    orientation per backend first, N4.d), every prefilter level against Python's, a lookup across a face edge (no seam),
    the shells' mirrored light inside rule (a) of D12 on recorded frames, the clear and the depth per face, objects
    released at retirement, the capture's cost against Python's. Negative controls: a swapped or mirrored face, a chain
    built by per-face box mips (the blurred lookups leave the bound), a non-seamless read.
  - [ ] C++: geometry once per key (D3). Decided (`Native_Core_P3_Decisions.md:2615-2647`), not built: the frame still
    carries the families' geometry (`frame_capacity.py:12-42`, 8.4 MB a slot at most), and the core's meshes are sent from
    the GUI thread (`mesh_buffers.h:4-11`), which does not hold the worker's bytes. Needed: the geometry arena (a second
    mapping, two banks a family, written before the frame that names its key), the reader uploading a key it first sees
    into a storage mesh, residency per key (requested, uploading, resident, failed, retiring), the old key kept until the
    new is resident and one frame used it, a failed swap keeping the old drawn, capacity growth as a new key with the
    history copied (the copy kernel, D16 C), and the previous key bound to the compute entry for the rebase record
    (`solver.py:263-271,757-776`). Proof: D3's four tests (two streams publishing one revision with different geometry;
    one upload a key and a frame size independent of capacity; an allocation failure injected, the old drawn, logged once;
    zero residencies after teardown, drop, mode switch, window destruction), and a drifted run through an edit and a
    capacity growth equal to `MaterialDriftReference` (`log.py:238-272`) and to the Python solver's output, both backends.
    Negative controls as D3's (the key on revision alone; delete before allocate; the retire job skipped).
  - [ ] C++: the drift pair check's readback, the one named exception. Only the harness reads storage back
    (`compute_passes.h:177-203`, `compute_passes.cpp:425-465`); the product's once-per-program check of D4's `precise`
    arithmetic (`solver.py:555-614`; `Docs/Guardrails/Performance_Optimization_Contract.md:450-465`) has no route. Needed:
    a check entry's one-shot result read through `readBackBuffer` at the program's first record, the completion taken at a
    later frame, never waited on, reported once in the content's state and the log. Proof: about 1 KB read once per program
    build on both backends, the readback counter flat over a steady minute, no frame waits on it, N3.3's L5 test (nothing
    else in the product reads storage) still green. Negative control: the check program compiled without `precise` is
    reported as inexact.
  - [ ] C++: Extruded Bubble's limits beyond Waveform's limits box. Targets: `kMaxSceneTargets` 4 to at least 5 (6 if the
    cube counts), Waveform's box leaving it at 4. Passes: Waveform's box raises 16 to 28; this mode needs 32 (33 with the
    check as a pass) and the mesh mask holds 32, so either the mask widens or the cube's faces and the check take
    fewer entries (the cube box decides); raise once for both. Storage buffers stay 8, at the limit with the check's results.
    Proof: the real program (every layer on, drift on, High tier) admitted on both backends with its warm-up counted
    (pipelines a step) and nothing at rest; one target or pass past the new limits refused with its reason; the targets'
    bytes at 4K recorded (`SceneTargetCounts`).
  - [ ] C++: a stage or pass entry skipped for a record with no work. A defocus step (its target's clear, mips, clip,
    gather and sprites) records on every accepted record (`mode_content.h:151-155`; D17 E, `Native_Core_P3_Decisions.md:2263-2266`,
    skips a stage only by program), where Python runs the whole near layer only when a shell or cluster exists
    (`eb.py:751`); an empty layer composites to nothing, so only the cost differs. Needed: a record u32 that skips an
    entry. Proof: frames equal with the skip taken and not taken, GPU time at zero shells no worse than Python's, no
    recorded work for the skipped entry (the stage counters). Negative control: the program-only form, whose zero-shell
    record still pays. If the lead judges the zero-shell cost immaterial, this box is dropped.
  - Shared with Waveform's boxes: the pass limit (its limits box, with this mode's higher count), and the exact-size,
    mipped, drawable target (its first box: the probe cube is the same rule across six faces, and the shaft targets
    follow its answer on exact sizes). Not shared: anisotropy (every sampler here is linear or trilinear), the half-float
    mode texture (no mode texture), 32-bit float image filtering (no storage image; the capture depth is read nearest),
    bloom and HDR off per record (bloom is the constant 0.55, never 0), the backdrop clear (every clear is a constant).
- [ ] N4.f2 (the reduced-resolution layers; Waveform and Extruded Bubble are native), then Expanded Visualizer M6
  (4K acceptance, plan 01) may run.
- [ ] N5.5 Neon Lake (N4.e, N4.k, instanced quads for its marks, its own analytic water reflection; its reaction
  and growth are uniform arrays).
  - [ ] First, before any port reference is recorded (operator, 21 Nov): the terrain's sharp, block-like judder. On
    Preset 1, terrain near the camera jumps up or down suddenly instead of moving smoothly. Likely visual, not design.
    Root-cause on the Python side (where the height steps: the published field, its interpolation between frames, the
    grid sampling), then smooth the motion there without smoothing the audio or deadening reactivity: the same peaks
    and troughs, reached less sharply. Prove it with `neon_lake_music_response.py` before and after on a recorded take
    (peak and trough heights kept, frame-to-frame height steps reduced) and a focused test with a control on the old
    code; then the port's references are taken.
  - Reading (reference; Sonnet agent ac4e1a1c9d1ad93c4, 21 Nov, merged), as Waveform's and Extruded Bubble's readings: the
    record per frame and per Settings or card change, stream size rules, every pass with its targets and formats, how
    it turns, its clear; then what the port needs that the ABI 29 core lacks beyond the Waveform and Extruded Bubble
    boxes (one C++ box each, with what its proof must show) and which of theirs it shares. File:line for every claim.
    Neon Lake's persisted id is `shockwave_grid`.
    Reading (Sonnet, 21 Nov, no code touched; sizes measured with a probe over the real mesh builders). `ng.py` is
    `rendering/quick/visualizer/implementations/shockwave_grid.py`; `basin.py` is `rendering/gl_programs/neon_lake_basin_program.py`;
    `target.py` and `shafts.py` are in `rendering/quick/scene3d/`; `mc.h` is `native/core/src/mode_content.h`; `D15` etc. are in
    `Native_Core_P3_Decisions.md`. Neon Lake has no compute, no storage image, no reflection target (its water reflection is the
    basin mesh drawn again mirrored, `ng.py:609-621`, `basin.py:507-511,694-706`), no depth texture, no HDR, no OIT.
    - Per frame from the logical frame (`ShockwaveGridFrame`, `widgets/spotify_visualizer/render_state.py:405-430`, on Spectrum's
      payload): the bars (at most 64, scaled by 0.55 at upload, `ng.py:388-389`, `rendering/quick/visualizer/implementations/spectrum.py:127-155`),
      peaks, the onset ring (age, x, z, strength; at most 48, `rendering/gl_programs/shockwave_grid_program.py:27`), the five terrain lane
      drives, their phase and the Growth and Indents drives, the animation time, the content fade. The Settings parameters ride
      frozen in the same frame.
    - Per frame in the renderer today, so for the worker to publish (D5.5, the N0.4 box): the newest 16 live events as records
      (`ng.py:390`, `shockwave_grid_program.py:23,191-196`), the mid-band mean (`ng.py:392-394`), the beat pulse (`:397-398`), the music
      drive (`:402`, `shockwave_grid_program.py:148-174`), the camera with its terrain-floor eye (`ng.py:200-209`, `basin.py:89-113`: it
      reads the terrain's cells round the eye, so the worker needs the terrain it already holds as a parameter), the Sun or
      Moon placement at infinity and its orbit (`ng.py:303-333`), the beat-star cells (up to 24 vec4, tested against the terrain
      and the body, `:438-452`, `rendering/gl_programs/neon_celestial.py:115`), the shaft light (`:718-727`), the halo light (`:730-735`),
      the cloud and nebula time terms (`:325-332`), the scroll, the idle swell and the wave terms (`:272-274,466`), the
      reaction-off flag when nothing drives the land (`:282-285`). The record is a few hundred bytes (events 16 x 16 B, 64 bars):
      no slot pressure.
    - Per Settings or card change only: the tier's samples, glow and mesh cells (`ng.py:94-104`; High 4 samples and 192 cells
      clamped to 180 x 120, Balanced 2 and 128, below single-sampled, `rendering/gl_programs/scene3d.py:81-92`,
      `shockwave_grid_program.py:29,54-58`), which stages exist (marks `ng.py:677`, sky `:710`, rays `:738`, glow), the three programs'
      blocks (about 100 uniforms: 5,488 B basin, 4,576 B skyline, 5,232 B sky; arrays `uBars` float[64] `basin.py:172`, the reaction
      lanes, bias and bands float[160], [32], [5] `rendering/gl_programs/neon_terrain_reaction.py:165-169`, the baked shaper
      tables `ng.py:681-699`), the terrain's adoption (`:167-176`), the mark diameter in pixels from the item's matrix
      (`basin_pixel_scale`, `ng.py:608`, `basin.py:36-44`: a card-derived value).
    - Meshes and textures (no per-frame bytes): the basin is non-indexed triangles of vec2 (`neon_lake_basin_mesh.py:97-154`), 385,320
      vertices = 3.08 MB at 180 x 120, 168,264 = 1.35 MB at 90 x 60, 78,864 = 0.63 MB at 40 x 27, keyed by the tier, the origin's
      reach and the painted tiles (`ng.py:136-154,664-669`); the marks are its unique vertices, 51,939 = 415 KB at 180 x 120, ten
      percent more with Wire Display's vertices (`ng.py:98-103`); the sky is a one-cell grid (`:242`). The terrain is a float32
      heightfield of at most 257 x 257 (`rendering/gl_programs/heightfield.py:16`): the stored cells RGBA32F (R height, G bank
      distance, B and A unwritten: 1.06 MB, `rendering/quick/scene3d/heightfield.py:59-62`; N1.7: QRhi has no RG32F) and, for a grown
      grid only, the overlay R32F (264 KB, `ng.py:132,182-185`), each uploaded once per data and released when the overlay goes
      (`heightfield.py:45-49`). The events are one std430 storage block at binding 3 (`ng.py:51,516`).
    - Passes of a frame in order (`ng.py:413-593`; one scene target, overlay, multisampled): 1 sky background (`:520-529`,
      depth test off, mask off); 2 depth-only prepass of the basin mesh, only with a Sun or a sky (`:531-540`, depth less, write on,
      blend ZERO, ONE_MINUS_SRC_ALPHA on colour and on emission, `:743-764`, to subtract the covered sky); 3 the mirrored basin,
      lines only, and 4 the mirrored marks, only with Reflection above 0 and the eye above the water (`:544,609-621`, depth always
      after a prepass, write off); 5 the surface (`:622-630`, depth less-or-equal, write on) and 6 the marks as `GL_POINTS`
      (`:631-633,640-645`); 7 the skyline, the basin mesh again with a displaced vertex stage (`:549-567`, `basin.py:1077-1190`, less-or-equal,
      write off); 8 the Sun or Moon body (`:568-577`, skyPass 2, `gl_FragDepth` 0.999999, `basin.py:1335`); 9 the shaft source (`:578-593`,
      skyPass 3, only while the body is in front of the camera, `gl_FragDepth` 1.0, `basin.py:1222`, written alone into attachment 2:
      `target.py:595-614`). On leaving the scope (`target.py:937-1013`): the shafts, a half-allocation downsample resolving the samples
      and two 16-tap radial gathers (`shafts.py:116-153`, three draws on two R16F targets), the emission's bloom chain
      (`target.py:966-968`, strength 1.4 x Glow, `ng.py:413`), and one composite of the scene with glow and shafts added
      (`target.py:228-277,1057-1104`). 14 entries (9 draws, 3 shafts, bloom, composite) against `kMaxModePasses` 16 (`mc.h:192`),
      3 scene targets (the scene and two shaft levels) of `kMaxSceneTargets` 4 (`scene_targets.h:69`), 1 storage buffer, 3 meshes of 8
      (`mesh_buffers.h:54`), at most 2 samplers a pass of 8 (`basin.py:1350`, `mc.h:277`): every limit fits, no limits box.
    - Attachments and formats: the scene's colour is RGBA8 (no HDR, `target.py:1202`); the emission RGBA16F only with Glow above 0
      (`:1207-1208`); the shaft source R16F only with rays admitted (`:1209-1210`), all multisampled at the tier's count; depth a D24
      renderbuffer, never sampled (`:1213-1220`), where the core's target depth is D32F (`scene_targets.h:9,102`). The fragments
      write `FragColor`, `Emission` at 1 and the sky also `ShaftSource` at 2 unconditionally (`basin.py:546,1158,1201-1202`); Python's
      shafts attachment is slot 2 even without emission, slot 1 draw-buffer NONE (`target.py:1222-1229`), and the core refuses an
      output past the target's attachments or an attachment left unwritten (`mode_content.cpp:664-683`, from Extruded Bubble's reading):
      fragment variants by attachment set (a `#define`, one file for both renderers, `mc.h:3-4`). Blends are Quick's inherited
      premultiplied over on colour, additive ONE, ONE on the emission (`target.py:585-588`) and off on the shafts (`:606`): with Glow
      above 0 every pass writes attachments of differing state, so the program needs the core's per-attachment blending
      (`mc.h:86-90`, device-gated: refused and Python's to log where it is not real).
    - Turning: the frame is oriented before anything (`ng.py:222,375`, `rendering/quick/scene3d/frame.py:38-66`), the scene draws unturned at the
      oriented size and only the composite and the bloom's first samples are oriented (`target.py:937-941,980-1000`); the core refuses
      a turned bloom or composite unless the scene is in the window's frame (`mc.h:150-155,445-447`, ABI 29), so Neon Lake is the
      turned-card anchoring box's fourth consumer (after the Oscilloscope, Waveform, Extruded Bubble). Suspected Python defect, not
      run: under a quarter turn `end` replaces `frame` by the physical output frame (`target.py:940-941`) before `_apply_shafts`
      maps the light's item point through its matrix (`:1042-1055`), while the shaft source was drawn in the oriented scene frame, so
      the rays' centre may be taken in the wrong frame for quarters 1 to 3. Reproduce: rays on, content quarter 1, compare the
      rays' centre with the Sun's drawn position; settle in Python before the port.
    - Clear: all constants. One `glClear` of every attachment to 0 (overlay: transparent, `target.py:918-926`) and depth 1; the
      emission and shafts attachments clear with it. No port decision is open. With the content fade at 0 or an empty content
      rect Python draws nothing at all (`ng.py:382-385`).
    - Found while reading, shapes the port:
      - The terrain is read with a hardware-filtered `textureLod` on RGBA32F (`rendering/gl_programs/heightfield_glsl.py:4-12`,
        `basin.py:260`) and its G channel's filtered value is compared to a threshold (`:411,443,596,848`), while the plan's N4.e
        decision reads the heightfield with `texelFetch` so that 32-bit float filtering is never required (plan N4.e, research
        section 16). R16F cannot hold the authored float32 heights. The shared shader either does a four-tap bilinear from
        `texelFetch` in both renderers (Python's pixels move by the hardware's quantised weights; rule (a) of D12) or the device
        proves linear RGBA32F (Waveform's box on 32-bit float filtering, for a mode texture instead of an image).
      - The basin deliberately keeps loose uniforms: on its pass block the Glass surfaces drew a few pixels one 8-bit level apart on
        OpenGL in 19 to 215 of 549 recorded frames (`basin.py:1365-1368`, the 14 Nov identity record), left "to its port". The
        port has no loose form, so that difference must be found and removed first, in Python, with the block form shown
        byte-identical on the Glass frames.
      - `uPass`, `uMarks`, `uDepthOnly`, `uSkyPass` are uniforms the renderer flips between draws of one program
        (`basin.py:233-235,1207`; `ng.py:525-592`). One rule fills each member from exactly one source (`mc.h:55-65`) and there is no
        per-pass constant, so each becomes a compile-time variant (a `#define`): about eight bakes of the large basin fragment,
        each with its own 5.5 KB block copy and pipeline, built a step at a time. Python's frames must stay byte-identical across
        the shader change.
      - The marks are `GL_POINTS` with `gl_PointSize` and `gl_PointCoord` (`basin.py:507-519,707-716`); the core refuses points
        (`mc.h:102`). Instanced quads on the primitive N5.1 builds (D15; the plan's N4 topology rule), the corner supplying the
        coverage, from the mesh's instance stream; one shader for both renderers.
      - The basin writes its clip depth by hand in GL's range after the matrix (`basin.py:193-202`), and the sky's `gl_FragDepth`
        constants 0.999999 and 1.0 assume GL's window depth; QRhi's correction covers x and y and a zero-to-one z on Vulkan
        (`native/core/src/conventions.h` rule 1; Waveform's floor maps `0.5 * (z / w + 1)`, `rendering/gl_programs/waveform_ribbon.py:55`).
        The body is depth-tested at 0.999999 against far land near the horizon, where D24 (Python) and D32F (core) quantise
        differently: the horizon frames are the proof.
      - Both renderers skip work per frame that the core records every time: everything at fade 0, the mirrored passes while the
        eye is at or below the water (`ng.py:544`: it moves with the orbit and the terrain floor; the shader would otherwise draw
        reflections from below, so this is parity, not only cost), and the shaft chain while the body is behind the camera
        (`:721-722`; a zero source gives zero rays, cost only). The record u32 that skips an entry is Extruded Bubble's box below.
      - A mesh change (tier, painted tiles, origin reach) uploads up to 3.1 MB in the record that first draws it
        (`mesh_buffers.h:4-11`), where Python warms it over not-ready steps (`ng.py:229-231,236-239`): the old mesh kept drawn until the
        new is resident is Extruded Bubble's geometry box's rule.
      - Shaft targets are half the allocation (`shafts.py:155-161`, the 64 px bucket of the item), so they need the exact explicit size
        Waveform's first box answers; the allocation's slack carries Python's own content under ABI 28's anchoring (`scene_targets.h:12-17`).
      - Already in the plan: N4.k's merged shafts owner (Extruded Bubble's port, then Neon Lake) decides whether the shafts keep
        the source attachment, the two gathers and a composite term, or become ordinary additive passes.
  - [ ] C++: a 32-bit float mode texture for the heightfield (N4.e's primitive). Mode textures are RGBA8 pixels from the GUI
    thread (`mc.h:35-37,488-500`, `setTexture` `:578`; Waveform's half-float box adds RGBA16F with mips, this is RGBA32F and R32F,
    no mips, one `format` member serving both). Needed: a declared format on a texture (RGBA32F, R32F), float bytes uploaded once
    per data and replaced in place at the same size (another size recreates), both stages reading it by name (`PassSampler.stages`,
    `mc.h:296`), `texelFetch` and `textureLod` at the base level, byte counts in `modeTextureCounts` (1.06 MB and 0.26 MB at
    257 x 257), the overlay removed when the grid is not grown, and the job-service route (`mc.h:46-53`) or its in-frame fallback
    for float bytes. Proof, both backends, sizes 2 to 257 including odd: every texel of both channels read back equal to Python's
    float32 bits (row order as Python's: the RGBA8 form is top-first); a vertex-stage `texelFetch` and `textureLod` of it
    (QRhi has no feature flag for vertex sampling, N4.e) reproducing Python's displaced surface; a replacement at the same and at
    another size mid-run without a pipeline rebuild; nothing uploaded at rest; zero textures after teardown; if the filtered
    read stays, Python's bilinear against the core's on the water classification and the bank-distance threshold, inside rule (a)
    of D12 (else the four-tap form in both renderers, same bound). Negative controls: R16F storage (heights and the water
    classification leave the bound), a flipped row order, the overlay left bound after the grid shrinks.
  - [ ] C++: the composite with light shafts, unless N4.k's merged owner draws its rays as ordinary additive passes. Core
    composites are overlay, overlay_glow and opaque_glow (`mc.h:147-155`, `native/core/shaders/composite_overlay_glow.frag:57-85`) and
    nothing under `native/core` mentions shafts. Python adds the half-size shaft texture, times the rays' colour and times the
    scene's coverage ("never the empty card around it"), into the glow before the dither test, bound in the glow's place when
    Glow is 0 (`target.py:259-277,1057-1104`). Needed: a composite input naming a shaft level (`"<target>.<attachment>"`, read
    at the glow's uv) and a three-component colour the record fills (the shafts' colour times strength, per frame), over both
    forms with and without bloom. Proof, both backends, every sample count: the composite against Python's
    `scene_overlay_shafts(_samples)` frame for frame, with bloom on, bloom off (the shafts alone), rays off and each tier; the
    dither where shafts alone clear its floor; a quarter turn (the fourth consumer of the anchoring box). Negative controls: the
    coverage factor left out (rays over the empty card), the dither keyed on bloom only, the glow read at the content size
    instead of the allocation's.
  - Shared with Waveform's and Extruded Bubble's boxes (not repeated): the turned-card anchoring box (fourth consumer); the exact-size
    explicit target (Waveform's first box: the two shaft levels, no mips); the record u32 that skips an entry (Extruded Bubble's
    box: fade 0, the mirrored passes while the eye is under the water, the shaft chain, with a proof frame at each; if the lead
    drops that box for Extruded Bubble these three cases argue to keep it); the geometry residency rule for a mesh swap
    (Extruded Bubble's geometry box, only its old-key-kept half); per-attachment blending (N3.4's gate); the fragment-variant rule
    for outputs; instanced quads (N5.1); the merged shafts owner (N4.k); Waveform's 32-bit float filtering box, only if the
    filtered terrain read stays. Not needed here: the pass, target and storage limits (all within the ABI 29 values), anisotropy,
    the half-float texture, the scene probe, the drift and geometry arena, the readback check, defocus, bloom off per record
    (Glow is a setting: a program change), the backdrop clear (every clear is a constant).
- [ ] N5.3 Extruded Spectrum, then Sphere (meshes, lighting, N4.j's backdrop environment, N4.l's silhouette
  shadows; neither uses bloom; no compute).
  - Reading (reference; Sonnet agent a32125875bef33af0, 21 Nov, merged), one reading per mode as the Waveform,
    Extruded Bubble and Neon Lake readings: the record, meshes and streams, every pass with its targets and formats, how
    each turns, the clear; then what each port needs that the ABI 29 core lacks beyond the earlier boxes (one C++ box
    each, with its proof) and which earlier boxes they share. File:line for every claim; any suspected Python defect is
    reported, not fixed. Sphere's persisted id is `sphere`.
    Reading (Sonnet agent a32125875bef33af0, 21 Nov, no code touched; sizes measured with a probe over the real mesh builders
    and block layouts). `es.py` is `rendering/quick/visualizer/implementations/extruded_spectrum.py`; `esp.py` is
    `rendering/gl_programs/extruded_spectrum_program.py`; `sv.py` is `.../implementations/sphere_voxel.py`; `svg.py` is
    `.../implementations/sphere_voxel_geometry.py`; `s3d.py` is `rendering/gl_programs/scene3d.py`; `env.py`, `target.py`,
    `frame.py` are in `rendering/quick/scene3d/`; `mc.h` is `native/core/src/mode_content.h`; `D12` etc. are in
    `Native_Core_P3_Decisions.md`. Both modes are one overlay `SceneTarget` (multisampled RGBA8 colour, a D24 renderbuffer
    depth, `target.py:1205,1217-1223`), a frameless card that may overflow it (`core/settings/visualizer_mode_registry.py:349-355,
    302-310,328,369`), drawn instanced from one small unit-cube mesh, and composited by the overlay composite with no bloom,
    no emission, no shafts, no compute, no reflection target, no OIT, no HDR, no depth texture. Neither uses `PhotoEnvironment`
    (ten transitions): N4.j for them is `BackdropEnvironment` only (`es.py:37,89`, `sv.py:26,730`).
    - **Extruded Spectrum, per frame** from the logical frame (`ExtrudedSpectrumFrame`, `widgets/spotify_visualizer/render_state.py:392-401`,
      Spectrum's payload and frame runtime unchanged): the bars (at most 64, `rendering/gl_programs/spectrum_options.py:13`),
      the peaks, the bar count and the animation time (`es.py:202-205,215-218`). The renderer turns the bars into the upload
      form per frame (`x 0.55`, `rendering/quick/visualizer/implementations/spectrum.py:127-148`) and the hue phase
      `animation_time x 0.15 x drift mod 1` (`es.py:75-77`, rate `esp.py:77`): for the worker to publish (D5.5, the N0.4 box), in
      the form Python packs (a double product rounded once to float32; a shader multiply would differ by an ulp). The bar
      record is 3 floats a bar, 768 B at 64 (`es.py:66-72`); no native schema exists yet for this mode (Spectrum's, Oscilloscope's,
      Bubble's and Spline Curve's do: `core/visualizer_engine/`), and the schema may carry f32 arrays or f64 fields filling a
      block's float arrays (`program_blocks.h:19`). The Settings parameters ride frozen in the same frame, with the wallpaper
      put in at the main side (`widgets/spotify_visualizer/backdrop.py:74-147`: 0.6 MB, so the record leaves it out).
    - **Extruded Spectrum, per Settings, card or view change only** (the view's Turn and Tilt are Settings, edited by drag):
      Spectrum's layout (`es.py:120-128`), depth, tilt, turn (`:133-136`), the fit `extruded_fit` (`:139-144`, `esp.py:133-149`),
      the painter's draw order of the translucent passes (`es.py:237-239`, `esp.py:115-123`: a permutation of up to 64 bars from
      the eye's x, so it is Settings-and-card data, not music), the multisampling (`es.py:54-63`: 4 at High, doubled to 8 by
      Smooth Edges, 2 and 4 at Balanced, 0 below, `s3d.py:81-88,115-127`), the colours, gloss, edge width in pixels, floor span
      (`es.py:214-226,265-277`), which passes exist (`:337-353`), the reach and so the target's frame (`:147-166`, `esp.py:152-175`;
      `frame.py:155-169` grows it in quarters of the item's height, never past the window), and the wallpaper maps (`es.py:279-291`).
      The pass block is 288 B (probed).
    - **Meshes**: the box is 36 vertices of position and normal, 864 B (`s3d.py:620-621`), drawn instanced once per bar,
      at most 64; the bars come from the record, never a second mesh.
    - **Passes of a frame in order** (`es.py:254-353`; one scene target, overlay, multisampled; every gate below is Settings,
      so each is a program variant, not a per-record choice): (1) the cast shadow (`es.py:301-335`, pass 4, MAX blend
      union) is never admitted: `EXTRUDED_CAST_SHADOW_AVAILABLE = False` (`core/settings/visualizer_mode_registry.py:15-17`, R-128;
      its settings are marked unavailable, `core/settings/visualizer_mode_settings.py:1390-1395`), so N4.l's Extruded half
      draws nothing in production; (2) the bars, pass 0, when the fill is opaque (`es.py:337-340`: depth test and write on) or,
      with a translucent fill or visible edges, pass 3 (`:341-348`: no depth, far-to-near by the records; the vertex stage moves
      the box faces turned away off the clip volume, `esp.py:344-349`); (3) the floor reflection, pass 2 (`es.py:350-351`, the
      row mirrored under the floor, discarded below the field, `esp.py:315-318,430-435`); (4) the ghost columns, pass 1
      (`es.py:352-353`, `esp.py:303-310,429`). Passes 1 to 3 are alpha blends with the depth mask off; one rule gives
      `uPass` no home in a block (`mc.h:55-65`), so each becomes a `#define` variant of one shader file (three or four bakes, each
      with its own 288 B block). On leaving the scope one overlay composite at the content fade (`target.py:980-1003,294-300`,
      `es.py:254`): up to 4 entries of `kMaxModePasses` 16 (`mc.h:192`), 1 scene target of 4 (`scene_targets.h:69`), 1 mesh of 8,
      at most 1 stream of 8 (`mesh_buffers.h:54-55`), 2 samplers of 8 (`mc.h:277`; `uBackdrop`, `uBackdropPrevious`,
      `esp.py:362,365,446-448`): every limit fits, no limits box. The blend of every pass is the core's `alpha` preset
      (colour SrcAlpha, OneMinusSrcAlpha; alpha One, OneMinusSrcAlpha: `mode_content.cpp:781-787`), the state the Python host leaves (`rendering/quick/visualizer/render_host.py:303-310`).
    - **Wallpaper (Mirror Faces)**: the two-slot `BackdropEnvironment` (`env.py:210-335`): an RGBA8 copy, longer side 512
      (`s3d.py:157`, `backdrop.py:27-31`), rows bottom first (`backdrop.py:20,46`), a full mip chain, linear mipmap filter,
      clamped (`env.py:287-299`); the new wallpaper goes into the other slot and the reflection crossfades over the bringing
      transition's duration or 2 s on the logical clock (`env.py:226,252-278`), the first one fading in from no reflection by
      `mirror x blend` (`es.py:243-252`); Mirror off holds nothing (`es.py:251-252`). The shader reads both with `textureLod` at the
      mirrored uv (`esp.py:416-426`). Native: two mode textures with mips already exist (`mc.h:35-44`, a same-size image replaces in
      place, another size recreates it; GPU mips). Gaps that are Python: the owner uploads on the edge it already has
      (`widgets/spotify_visualizer/quick_display_visualizer_owner.py:516-546`) instead of the frame carrying the pixels; the blend
      is per frame, so the worker publishes `mirror x blend` and the slot weights from the logical clock and the owner's
      (identity, duration) edge; a program whose texture is missing is not drawn (`mc.h:70-71`), so a 1 x 1 placeholder stays in both
      slots until the first wallpaper; the uv maps the fragment through `fragPixel(uTargetSize)` and `uBackdropMap`
      (`esp.py:363-364,418`), the allocation and the window's GL pixel, where the core's fragment row is top-first on every backend
      (`conventions.cpp:44`) and `u_target_px` is the content (`mode_content.cpp:230`): the shader maps the target pixel to the
      window's through `u_window_from_target_x/y` (`mode_content.cpp:228-229`) and the backdrop's row order once, in the one shared
      file, with Python's frames unchanged. Gaps that are C++: the crossfade's start (the owner's edge precedes the texture
      commit, `mc.h:46-53`), and the mip chain per backend: see the boxes.
    - **Turning**: the frame is oriented before anything (`es.py:172,195`, `frame.py:38-66`), the scene draws unturned at the oriented
      size, the reach stays in the oriented frame and clips to the physical window (`Docs/Reference/Scene3D_Resources.md:12`), and
      only the composite is turned (`target.py:937-941,980-1003`). The core refuses a turned composite unless the scene is in the
      window's frame (`mc.h:150-155,461-465`, ABI 29), so Extruded Spectrum is the turned-card anchoring box's fifth consumer
      (Oscilloscope, Waveform, Extruded Bubble, Neon Lake before it), and the only one that also overflows: its composite
      rect is the reach rect (`rendering/native/composite.py:12-14,115-136`; only `native/core/python/composite_check.py:472-473`
      passes an `overflow_rect` today), so that box's proof includes a turned, overflowing card.
    - **Clear**: all constants. One clear of colour to transparent and depth to 1 at the scope's start (`target.py:918-926`).
      With the content fade at 0, or no bars, Python draws nothing (`es.py:203,207`).
    - **Found while reading, shapes the port**:
      - The hand-written clip depth is OpenGL's range: `clip.z = clamp(-screen.z / 6, -1, 1) x w` (`esp.py:284`). The view depth
        spans both signs (the row turns up to 180 degrees about its centre, `esp.py:56-57,252-260`), so on Vulkan, whose clip
        range is 0 to w, everything nearer than the pivot is clipped. The one shared shader maps it as Waveform's floor does
        (`rendering/gl_programs/waveform_ribbon.py:55`, `0.5 x (z / w + 1)`); Python's frames must stay byte-identical across
        the change (the order is monotone; only D24's quantisation moves). The proof frames are the extreme turns and tilts.
      - The target is the reach: up to the whole window, at 8 samples with Smooth Edges at High (8 x (RGBA8 + D32F) = 64 B a pixel,
        about 530 MB at 3840 x 2160 before the resolve; arithmetic, not measured): `SceneTargetCounts` at the largest reach goes
        in the port's record, and the sample clamp to the device (`kMaxSceneSamples` 8, `scene_targets.h:72`) is a proof size.
      - The composite's rect is Python's `item_pixel_rect` of the reach frame (`frame.py:92-136`) and the core's is a whole-device-pixel
        rect (`composite.py:115-136`); the card's `scene_item` carries Python's (ABI 28), and the two must agree at every reach step.
      - Scene opacity reaches Extruded Spectrum only as the content fade (`es.py:254`), which the core's composite reads as `u_fade`
        (`native/core/shaders/composite_overlay.frag:16,39`); `render_contract.scene_faded_snapshot` folds it in on both paths
        (`rendering/quick/visualizer/render_contract.py:70-86`), so nothing is added.
    - **Sphere, per frame** from the logical frame (`SphereFrame`, `render_state.py:473-` and the cohort at `:438-469`): the size
      pulse, the rotation phase, the tracer drive and phase, the eight section drives, the incoming drive, density, two sections
      and blend, and up to four particle cohorts (progress, strength, density, velocity accent, vocal bounce, section, lane,
      outtake) (`sv.py:813-864,779-811`); every value packed as Python packs it (clamps at `:910-916`, `:793-800`). Per frame in the
      renderer today, so for the worker to publish: the rainbow phase `fmod(logical time x speed, 1)` (`sv.py:959`), the shadow's
      offset `-light x radius x (0.34 + 0.55 x pulse) x distance` and alpha `colour alpha x (0.28 + min(0.16, 1.6 x pulse)) x
      opacity` (`:1079-1087`), whether any admitted cohort is an outtake (`:967`), and the fade `scene_fade x content_fade` (`:955`;
      see the defect below). 278 instances is what the shell builder makes (`svg.py:14-19,63-95`, probed): radius 5, thickness
      0.75, 5,560 B of centre, seed and polarity, one cube of 36 vertices (864 B, `svg.py:32-44`), 10,008 vertices a draw.
    - **Sphere, per Settings or card change only**: the geometry `(centre, radius = 0.215 x min(content))` (`sv.py:48,79-85`), the
      reach and so the target's frame (`:93-109,751-756`), the multisampling (`:121-123`: 4, 2, then 1 where the tier has none),
      Mirror Cubes' strength (`:112-118`), the light vector (`:873-879`), colours, gloss, edge weight, depth shading, toon,
      rainbow flags, spin mode, perspective, view pose, voxel variation, projection (`:813-866,940-966`), which layers exist (the
      shadow and its softness layer, `:1073-1088,1134-1145`), and the wallpaper as above (`:929-939`). The block is 1,024 B
      (probed; `:126-181`), one block for hero and shadow, patched per layer (`:1115-1121`).
    - **Passes of a frame in order** (`sv.py:976-1034`; one scene target, overlay 1.0, multisampled, depth LESS and write on):
      (1) with Soft Shadow above 0, the soft layer, the same vertex stage with the cubes grown by `1 + 0.12 x softness`, a flat
      fragment of the shadow colour, alpha x `0.32 x softness`, projected with the offset and scale of the shadow
      (`:1134-1141`; shader `:691-704`), then a depth clear (`:1142`); (2) the shadow's core silhouette, the same program at cube
      scale 1 (`:1144`); depth is used only as a mask so overlapping faces do not stack alpha (`:1062-1069`); (3) a depth clear
      before the hero (`:989-990`) so the shadow cannot occlude it; (4) the hero, the cubes lit and edged, culled back with the
      front face from the matrix's handedness and the backend (`:1002-1018`, `:62-65`, `rendering/gl_programs/conventions.py`
      `front_face_clockwise`); (5) with outtake cohorts, a second draw of each of the three layers with `uRenderPass = 1`, depth
      write off (`:1020-1032,1107,1128-1132`); then the overlay composite at fade 1.0 (`:976`) with the fade applied per
      fragment (`:684-687`). Up to 6 draws, 2 depth clears and the composite: 9 entries of `kMaxModePasses` 16, 1 scene target,
      1 mesh with its instance stream of 8 (`mesh_buffers.h:54`), no stream or storage (every value fills a block member
      from the record or the settings: `mc.h:55-65`), 2 samplers: every limit fits. `uRenderPass`, `uVoxelScale`, `uProjectionOffset`,
      `uProjectionScale`, `uLayerAlpha`, `uShadowColor` change between draws of one program (`:1115-1121,1025`) and the rule has no
      per-pass constant: one `#define` variant a draw, a block member name per variant (about six bakes of the vertex and
      fragment sources, `:184-704`; warm-up one build a step). All draws are `Alpha` blends.
    - **Sphere, how it turns**: it does not turn the content. Sphere is not content-rotation capable
      (`registry:302-310`, against Extruded Spectrum's `:354`), never orients its frame (no call in `sv.py`), and its turn and tilt
      are a view pose in the vertex stage (`:837,509`, `s3d.py:1266-1286`). The turned-card box does not touch it.
    - **Sphere, clear**: constants (colour transparent, depth 1, `target.py:918-926`) plus the two mid-frame depth clears above.
      With the fade at 0 Python still records every pass (alpha 0, `:684-687`); no early return but a zero target.
    - **Found while reading, shapes the port (Sphere)**:
      - The core clears a scene target's depth only with the target's clearing draw at its first run of a record
        (`mc.h:96-97`, `mode_content.cpp:5999`): nothing clears depth mid-frame. Sphere's silhouette mask depends on it twice
        (`sv.py:989-990,1142`). A data-only substitute exists: a full-target pass with colour writes off, depth test Always, write
        on and `gl_FragDepth = 1.0` (`mc.h:91-92`), at a full-target fragment cost twice a frame; the box below decides.
      - The overlay composite always multiplies by the card's content fade (`composite_overlay.frag:39`, `u_fade` a core member,
        `mode_content.cpp:223`), where Sphere composites at 1.0 and fades each fragment before blending (`sv.py:976,684-687`);
        fading after the blend instead is not the same pixels where fragments overlap (the shell's translucent fills and the
        shadow layers). The shader's own fade member (`uFade`) is a record or settings member, not the core's `u_fade`.
      - Culling and the front-face selector (`mc.h:107-108`, `mode_content.cpp:5360-5372`) are built (N3.2) and used by no ported
        mode yet: Sphere is the first consumer, so the proof includes each backend's winding and the negative control of the
        flipped one.
      - The depth is the Scene3D projection's own: `sceneProjectAt` writes `clip.z = sceneClipDepth(w)` after the matrix
        (`s3d.py:224-239`), about 0.93 to 0.96 over the shell: inside both backends' ranges, the compare monotone; D24 against D32F
        only moves ties between faces of one cube, the same class as Neon Lake's horizon note.
      - The wallpaper maps as Extruded Spectrum's (`sv.py:661,962-963`, `uTargetSize` `:1044-1045`).
    - **Suspected Python defect (Sphere), not run**: the scene fade may be applied twice. The node and the native route fold the
      authored scene opacity into the content fade (`rendering/quick/visualizer/node.py:264`,
      `rendering/quick/visualizer/native_route.py:626-657`, `render_contract.py:70-86`; the root's `sceneOpacity` is
      `presentation.scene_fade x reveal`, `scene_controller.py:2741`, `VisualizerPresentation.qml:256`), and Sphere then multiplies
      `presentation.scene_fade x presentation.content_fade` again (`sv.py:955`; the snapshot's `scene_fade` is untouched by the
      fold). At a scene fade of 0.5 the shader receives 0.25. Extruded Spectrum and every other renderer use the content fade
      alone, and `tests/test_qtquick_visualizer_fade_authority.py` names "test_visualizer_scene_fade_once" (`:77`) which
      does not exist in `tests/`. The term arrived with the voxel rework (49086dbf4), before the fold (d67d6aac3). Reproduce: take
      a Sphere snapshot whose presentation has `scene_fade = 0.5` and `content_fade = 1.0`, pass it through `scene_faded_snapshot(
      snapshot, 0.5)`, and read `values["uFade"]` at `sv.py:955` (0.25, where one application gives 0.5); then a hidden render at
      scene fade 0.5 against an Extruded Spectrum frame at the same fade shows Sphere's alpha squared. Settle in Python (one term,
      with the fade-in curve judged on the activation reveal) before the port, since the native route would copy it.
  - [ ] C++: a depth-only clear of a scene target between passes (Sphere's silhouette mask, two a frame with Soft Shadow, one
    without it, none with the shadow off). The core's only depth clear is the target's first-run clearing draw (`mc.h:96-97`).
    Needed: a pass entry that clears a named target's depth (the far value, the whole content viewport and every sample) with colour
    untouched, recorded in place between runs of draws on that target. If the lead prefers data only, the full-target
    frag-depth pass above is the alternative and its cost the proof. Proof, both backends, every sample count: Sphere's frames
    with the clears taken against Python's `glClear` frames (shadow on with and without Soft Shadow; the hero not occluded by
    shadow depth), the clear leaving colour and the other target alone, GPU time of the entry at 4K against the frag-depth
    pass. Negative controls: the clear left out (the hero loses the pixels the shadow's depth covers), the clear writing colour.
  - [ ] C++: the overlay composite at a declared fade. The composite step's fade is the card's `u_fade` only
    (`composite_overlay.frag:16,39`; `mc.h:147-155`). Needed: a composite option whose fade is a constant 1 (or a named member the
    record or settings fill), valid for the overlay and glow forms, leaving every existing program's frames unchanged. Proof, both
    backends, every sample count: Sphere's overlay composite at 1.0 against Python's `overlay=1.0` frames with the per-fragment fade
    at 1, 0.5 and 0 (a content fade that does not reach the composite), and an existing overlay program (Oscilloscope or Neon
    Lake) hash-identical before and after. Negative control: the card's `u_fade` at the composite and the shader fade both applied
    (the half-fade frames leave the bound).
  - [ ] C++: a mode texture's commit as something the record can read. The wallpaper crossfade starts when the new image is what the
    slot draws (Python: at its first `textures` call, `env.py:260-271`); here the owner's edge precedes the texture's commit,
    which is one record later in place on OpenGL and a job's completion on Vulkan (`mc.h:46-53`), and the state keeps only
    counts (`TextureReport`, `mc.h:514-530`). Needed: each texture's committed generation as a core member of the pass block
    (or an edge to the owner, as a lost texture is, `item_notifier.h`), so the worker's blend begins at the commit and the shader
    never mixes toward a slot still holding an older image. Proof, both backends: a wallpaper change at a known record, the blend's
    first frame and the weights across the change against `BackdropEnvironment.textures` frame for frame with the job route
    forced slow (the in_frame control) and not; mip levels 0 to 4 read back against `glGenerateTextureMipmap` for even sizes
    and for the odd sizes real wallpapers give (QRhi's Vulkan blit differs on odd levels, D17 G), the reflection inside rule (a)
    of D12 on the frames that read them (lod 0.4 to 3.6, `esp.py:420`; 1.8 to 3.6, `sv.py:664`). Negative controls: the blend
    started at the owner's edge (a few percent of a stale reflection in the first frames), the mips of the Vulkan blit on an odd
    size without the bound. If the measured commit lag is a frame or less on both routes the lead may judge this immaterial and
    drop the box; the evidence is the proof's first row.
  - Shared with the earlier boxes (not repeated): the turned-card anchoring box (Extruded Spectrum only, fifth consumer, with its
    overflow rect in the proof); the record u32 that skips an entry (Extruded Bubble's box, for Sphere's three outtake overlay
    draws, which otherwise run every frame with every fragment discarded, `sv.py:537,1020-1032`: cost only, so if the lead drops
    that box Sphere pays and records it); the fragment and vertex `#define` variant rule (Extruded Bubble's and Neon Lake's); N3.6's
    warm-up for the variants. The wallpaper environment, the silhouette pass and the depth are N4.j's and N4.l's whole content:
    N4.j is two mode textures plus the Python plumbing above and the commit box; N4.l's Extruded half is dead code
    (R-128) and its Sphere half is ordinary passes of one program (the depth clear above), not a shared primitive, so N4.l as
    written (one primitive for both) is not needed by either mode. Not needed here: the pass, target, stream and storage limits
    (every one within the ABI 29 values), per-attachment blending, anisotropy, half-float or 32-bit float textures, the exact-size
    or mipped target, the scene probe, drift and geometry arena, readback check, defocus, bloom or HDR, shafts, the backdrop
    clear (every clear is a constant), instanced quads (the cube is a mesh).
- [ ] Spectrum and Spline Curve long-take residuals (ACCEPTED by the operator, 17 Nov, with Bubble; non-blocking).
  Rerun 21 Nov after the scene-fade fix (R-242) on all four 60 s takes, both variants, display placement: full
  replays with the Python references drawn and cached (`D:\Temp\Scratch\SRPSS\fast_proof\references\`), every
  one of 5,313 shown frames judged a run, halves 0-2645 / 2645-5291, 620-800 s a take for both variants. Module ABI 28
  (1843914e8); Spectrum's nightsolong take and the probes ran on ABI 29 after main's merge, and every probe
  reproduces the ABI 28 run's native hash at each failing input. The cold start passes on every take and variant
  (R-242's class is gone from the long takes). Neither mode is retuned and no D12 bound is changed. Evidence:
  `native_core/longclip_recheck/20261121_<mode>_<take>_display_fix_rerun/` (report with both paths' frame hashes,
  the long-term reference of the guide's section 6; `classify_<run>/`: every pixel past its allowance at each
  failing input, with crops). Bubble variant b's four 60 s takes pass after the fix (0 failed frames each; first
  half scatter 55-62, groups 2, ties 2-4; second half scatter 9-12, ties 0; Bubble's own Python frames identical to
  the pre-fix run, native changed only at inputs 0-27; `fast_proof/20261121_rule_a_fix_rerun_60s_<take>/`).
  - [ ] Spline Curve (`devcurve`): steady and deterministic failures only (nightsolong variant a fails exactly 17
    Nov's seven steady inputs). Failed frames (first half / second half; worst ties per half):
    - ragdoll: a 1 (2570 / none; ties 10 / 9); b 1 (2460 / none; 11 / 10).
    - human_heavy1: a 1 (none / 3376; 10 / 9); b 4 (1176, 1394, 2495 / 4646; 11 / 10).
    - anything_mixed2: a 3 (643, 810 / 5091; 9 / 9); b 2 (2384 / 5015; 11 / 11).
    - nightsolong: a 7 (728, 829 / 2991, 3170, 3385, 3446, 4042; 10 / 9); b 4 (205 / 3174, 5088, 5204; 10 / 12).
    Two classes; scatter 0 and flips 0 everywhere. (A) "11-12 ties", variant b only (9 frames): 8-10 two-level
    pixels on the translucency mask at the curve's anti-aliased edges (3x3 reference range 30-208), each isolated,
    plus 1-3 one-level opaque pixels; the count is one or two over the bound of 10, the placement never fails.
    (B) "ties neither isolated nor on a content edge", both variants (14 frames: 12 of a, 2 of b): a touching pair
    of one-level pixels in the curve's bright core (mostly one channel at 255), the stray one's 3x3 range 10-31,
    under the edge contrast of 32; at 728 the pair is two-level and on the mask (range 11-13). Not proved: the
    source of each (candidates: the line raster's coverage rounding for A, the core colour's float path for B).
    Next: compare the uniforms and the per-fragment colour of one A and one B frame Python against native; fix at
    the owner; if either proves a D12 class, the bound is a lead decision with the measured worst stated (A: 12
    ties; B: a touching pair at range 10).
    - Fixed at the source by the card quad (ABI 32, merged 21 Nov): failed frames 23 -> 6, class A gone. The 6 left
      (class B, one-level touching pairs, also seen in Python against itself) are backlog: human_heavy1 a 2358, 4200;
      nightsolong a 941, 4194, b 4836; anything_mixed2 a 2151.
  - [ ] When the scene-fade fix lands (one place applies the scene fade): rerun Bubble's offers
    (`owner_render_parity.py --native --mode bubble --offers`, both placements) and `nightsolong_acousticsoft1` input 22;
    Bubble's tracked exceptions (input 22, and `stream_direction=2` / `=6` at input 337) must disappear.
  - Tool gaps found (fix with or before this box): no Vulkan path in the owner replay (no rule (b) or Vulkan hashes);
    output only at the end of a run (a killed run loses everything); about 3 GB per run; 28 min per one-variant run.
- [ ] Bubble GPU optimisation (Opus Medium agent ae6c6e5974266bad5, 21 Nov; the live Display 1 baseline is the lead's)
  (operator, 17 Nov: Bubble about 50 % GPU at 4K and Extruded Bubble
  about 55 %, on a stale build; "all guarded gains are valuable"). Every candidate passes
  `Docs/Guides/Native_Parity_And_Timing_Proof.md` for what it touches (its change-type table).
  - [ ] Baseline in the operator's case first: Bubble fullscreen (expanded) at 4K on Display 1, where Python OpenGL
    reaches about 50 % of a 4090 for 2D vector work, and Extruded Bubble about 55 %. Use live runs on Python OpenGL
    and native Vulkan with `--app-arg=--gpu-pass-timing`, and record `nvidia-smi` utilisation and clocks with the
    figures. The card-sized cost measured at the port is not this case.
  - [ ] Measure per-pass GPU time at 4K on both backends first. The port's figures put nearly all the cost in the main
    `bubble` pass (about 3 ms at full 4K area; native OpenGL about 5 % slower than Python).
  - [ ] Measure with decoration off, representative decoration on, and high-density, high-glow decoration on, at the
    canonical card and at extreme wide, tall and expanded sizes. Include R-170's density growth: a larger card draws
    up to 72 live heroes (110 with draining trails), and the hero loops run per fragment. Confirm that decoration off
    really skips the ambient target's draws.
  - [ ] Byte-identical candidates first. Anything that cannot hold byte identity goes to the operator as tier 2.
  - [ ] Optimise only a measured offender. If no material cost is found, close the item without redesigning Bubble.
  - Built (Opus Medium agent abbcd68ea9219da70, 21 Nov): the wake loop's per-bubble reject (c8d1ea916), hash-identical
    on all four 60 s takes on both APIs, -22 % OpenGL and -21 % Vulkan for the expanded 4K bubble pass. The ghost loop
    has no candidate that pays after it (5ba190a5f keeps the three in `bubble_cost_matrix.py`). The pass's largest
    stages are now the wake (0.90 ms OpenGL, 0.66 Vulkan) and, on Vulkan, the ghost (0.66).
  - [ ] Extruded Bubble gets the same treatment after N5.6, with its own three-clip before-state.

**N5, background track (one High slot; transitions grouped by what they share; needs are in the matrix,
section 2)**

Slots (lead, 12 Nov): N5.2a, the first group on the shared fullscreen pass, goes to Opus High, and so does each group
whose primitive is ported with it (N4.c, N4.g, N4.i, N4.j, N4.l). After that, a group whose primitive is already
native goes to Opus Medium, under the same parity proof and audit as the modes track.

- [ ] N5.2d Motion blur and trails (N4.i): 3D Block Spins, Crumble, Glass Shatter, Pixel Accretion.
- [ ] N5.2e Membrane, Page Curl, Exploding Tiles (N4.l).
- [ ] N5.2f Disintegrate, Volumetric Dissolve (N4.c).
- [ ] N5.2g Edge Bloom, Capillary Bloom (N4.g); their fields are the first transition preparation run as an async
  job (D9, consumer class a).
- [ ] Pre-flip reference pack (operator, 15 Nov: "measure the gain instead of just telling ourselves it is good"):
  captured while the Python renderers are still the product, and **before N5.2h deletes them** (after that the
  "before" side cannot be measured). One script (extending `tools/visualizer_live_check.py` and
  `tools/overhead_baseline.py`, not a new system) runs the same matrix before and after the flip:
  - [ ] Every Visualizer mode (its default preset) and every transition, on Display 1 at 3840 x 2160 and on Display 0's
    size at 2560 x 1440, invisible saver, recorded music (`anything_mixed2`) over the Usu wallpaper: fps, render time
    median/p90, swap gap, late %, hitches a minute, saver CPU % of a core, GPU ms per frame, RSS and private memory,
    first-2-seconds frames.
  - [ ] Idle and loaded. game60 is only with the operator's yes on the day, 10 minutes at most, lead only.
  - The 15 Nov capture is done: every mode and the five-transition load set, idle and game60, on Display 1
    (`Benchmarks.md`, `tools/baselines/preflip/`); one size only (the saver takes its display's resolution).
  - [ ] Stored as a named baseline (`tools/baselines/preflip/`) and summarised in `Docs/Reference/Benchmarks.md`; the
    flip's acceptance reruns the same matrix on Vulkan and on native OpenGL and reports the gain per row.
- [ ] N5.2h The background family switches on OpenGL (D10 point 4): presenter, backdrop and all 28 transitions
  native in production; the native backdrop compared with the blit on the same frames; the Python presenter, the
  Python transitions, the blit backdrop and the wrapped-texture bridge deleted in that change.
- [ ] N5.9 True glass over the Visualizer (D7 point 7; D8 plus 5): after the Visualizer layer and the backdrop
  are both native; `Docs/Architecture/Card_Surface_Materials.md` section 2 invariant 6 amended for the native
  core in the same change.

**NF. The flip (P3.5): Vulkan the default, OpenGL selectable**

- [ ] N5.8 The Studio's preview host and window, and the release-media and capture tools, render through the
  same core; no Python OpenGL node is left in any Qt Quick surface of the process.
- [ ] The translucent-window question settled from N0.6 (the Studio's window: see-through if Vulkan can, else an
  opaque window with the system's rounded corners; the SMP build's window by D7 point 8's route, the artwork
  backdrop only where no route works).
- [ ] The flip gate of D10, item by item, as a record in the decisions document; then the backend setting in
  Settings (Vulkan by default; OpenGL the fallback, with the automatic start on OpenGL and its stated reason).
- [ ] A frozen GitHub build on Vulkan on Display 1; one load session after the operator's yes, Vulkan against
  OpenGL.

**N6. Primitives planned but never built: native only, on the primitives track**

- [ ] N6.1 Dynamic surface field. **High potential** (water, ripples, pools, melt, any reactive surface; Neon
  Lake's water and SMP surfaces could use it): a bounded GPU height and velocity grid with impulse injection and
  damping, a displaced mesh with true normals, reflection distortion driven by it (with N4.d).
- [ ] N6.2 Static scene geometry and materials. **High potential** (what turns a mode into a place: floors,
  walls, wells, simple skyline and tunnel slices, with roughness, bevel and contact shading, built once and
  kept).
- [ ] N6.3 Advected smoke and haze on the volume primitive. **High potential** (atmosphere for every 3D scene;
  shares N4.f2's reduced-resolution path).
- [ ] N6.4 Photo-textured shells and planes with real depth. **Low potential until a consumer** (a transition
  or a mode built round the user's photos).
- [ ] N6.5 The opt-in deformable sheet. **Low potential until a consumer.**
- [ ] N6.6 Lightning: procedural bolt geometry and its light. **Low potential until a consumer** (one effect).

- [ ] N6.8 Frost and ice (operator, 20 Nov). **Consumer known:** Extruded Bubble's icy-water look, which reads nothing
  like ice today. A surface treatment: a rime or frost layer (a procedural frost normal and scatter, crystalline
  sparkle), refraction through ice (on N4.d's rough receivers and the scene probe), and an ice-to-water edge on N6.1's
  dynamic surface field. Research first: which parts are new and which are compositions of N4.d, N4.j and N6.1. Then
  its harness proof like the other primitives, then the consumer.
- [ ] N6.7 Dense geometry route (operator, 13 Nov: mesh shaders for fidelity on the high-end modes). It is a
  measured candidate, admitted by evidence, not by a consumer. Mesh shaders (`VK_EXT_mesh_shader`) are recorded
  as raw Vulkan on the core's own device (D6) inside Qt's frame, with a compute-cull plus indirect-draw twin
  (Qt 6.12 `drawIndirect`) for OpenGL and any device without the extension: the fast path, never the only path.
  - Admitted when N2.6's per-pass timers show a ported mode's geometry pass is primitive-bound, or when a
    fidelity target needs more geometry than the current path can feed. Candidates: Extruded Bubble's beads and
    bubbles as real meshes, Neon Lake's terrain level of detail and culling, Waveform's ribbons, N6.2's scene
    geometry, N6.3's smoke.
  - Proof: the same picture as the twin; GPU time against the twin on the candidate's pass, median and p90;
    validation clean; the twin exact on OpenGL.

### Item 9. After the native core: SMP foundations, then modes

Port-readiness rules bind all new GPU code now (the backend decision). Expanded Visualizer continues meanwhile
(item 3; plan 01, whose section 0 holds the phase ladder and the 4K budgets).

- [ ] Oscilloscope legibility (operator, 21 Nov; after the flip, with the other mode tweaks): a setting that slows
  the trace's apparent noise while it stays reactive and busy. Today every preset moves so fast the trace reads as
  static to the eye. Research first: which motion carries the speed (sample window, refresh of the trace, jitter
  from noise), and how to slow what the eye sees without lagging the reaction. For example, temporal smoothing of the
  displayed trace shape against the reaction envelope, or persistence. Judge it with the music-response traces and
  live rendered motion, never twitch.

- [ ] After the flip, SMP's foundations first (operator, 12 Nov: "SMP foundations first after native parity, as
  you suggest"): the library, the playlists and a playback service that meets the measured audio bar
  (`Docs/Future_Work/ShittyMusicPlayer/02_ShittyMusicPlayer_Implementation_Plan.md`, gated behind `--smp` until
  its Gate M9; section 0A the prerequisite phases, 13 to 16A the operator's audio, Settings-tab, artwork,
  rearrangement and fullscreen-arrangement targets); then the question of how far to go before returning to
  modes. Reasons on record: that work closes reliably without visual sign-off, gives the Visualizer decoded
  audio with look-ahead instead of a loopback capture, and proves "one Visualizer owner, any surface". The visual
  track meanwhile finishes what is open and stays on the primitives track of item 8b.
  **Audio implementation decision (operator, 16 Nov):** M3 begins with one native C++ SMP audio engine
  (FFmpeg native decoding, own PCM/DSP scheduling, event-driven WASAPI shared/exclusive), not a Qt
  Multimedia playback prototype or a later backend migration. Native audio shares core tooling and
  engineering contracts with the QRhi Native Core, but never its GPU/GUI thread, clock or lifetime;
  Python retains application policy, not real-time sample delivery. Plan 02 §4/§13 and PCM seam 03 bind.
  **SMP visual/library foundations (operator, 16 Nov):** M0/M1 must define/consume versioned semantic shape,
  surface, type and motion tokens before building the panes, including full sharp-to-pill radii, inner junctions,
  and reuse of Studio Qt Quick bounce/hover transitions with reduced-motion policy. **Pre-SMP 1B.8 M4 unifies Settings and Widget themes immediately after M3 material borders; SMP M0/M1 adds scoped ZIP skin support.** The Theme Studio (visual authoring of the unified theme) is pre-SMP, after the native core, the flip and M4 (operator, 21 Nov; the 1B.8 box below); SMP M10 only extends that same Studio with skin authoring. Design and boundaries: plan 02 §8.2B and document 05.
  M2 keeps SQLite with mandatory FTS5, indexed virtualised pages, bounded edits and measured 50k/250k-track
  concurrency/recovery; no custom database core. Plan 02 §3.3 and §8.2A govern.
  **Pre-SMP admission (operator, 16 Nov):** NF (the native flip) is necessary but not sufficient: finish the
  *admitted* native-core, compositor and planned N4/N6 primitive work before entering SMP foundations, including
  the Context Menu backdrop-source defect, M3 material borders and M4 unified themes in 1B.8, and any chosen N5.9 material solution. Do not make hypothetical
  unadmitted future primitives an indefinite blocker.
- [ ] New modes (Reactive Liquid / Melt Pool, Concrete Rain, Usu Moonscape; section 7, lab first) are built on
  the native core only, after it.
- [ ] Very low priority, after the native core and its new primitives (operator, 14 Nov): Extruded Bubble's arctic
  look is flat, with "nothing icey about it": no ice, frost or anything inventive. Rework it once the native
  primitives give it real material tools (frost and ice surfaces, refraction, a sparkle field), not with today's
  parameters alone. Presets are authored content: the work is new EB capabilities, plus authoring that preset with
  them. The lead judges it on showcase WebPs over bright and dark wallpapers.

## 1B. Operator defects and requests (11 Nov; backlog under section 1's Order, in this internal order)

Live checklist: every open step is its own box; landed boxes are deleted at merge; keep
`[~]` validation steps and open side defects. Order: the Edit/exit defects, the Studio work, the fullscreen
overlay contract, window material and corners, presets last. Every fix reproduces its failure first; the lead
judges visual items on rendered pixels and audits each branch against the pre-fix code before merging.
**Nothing in this section waits on the operator** (operator, 11 Nov: checks are the lead's work; a remaining
question without a simple test is a Watchlist item, never an open phase). What needs the real product on real
hardware is proven by the lead's harnesses in 1B.14.

### 1B.1 Edit edits the display it was entered on (contract: plan 01 M3c)

- [ ] Side defect (unreproduced): in an ordinary global Edit, closing the Visualizer and then switching mode makes
  `activate_edit_visualizer_profile` return False (`rendering/quick/custom_layout_owner.py`, the `visible is None`
  branch), which looks like a forced runtime reload. Reproduce in a test or rule out.

### 1B.2 Cursor keeps its changed shape after exit until a click (R-183; proof in 1B.14)

The harness reproduced the stuck shape only with Qt's pointer tracking cleared artificially: the real exit path is
unproven.

- [ ] Side defect: when a hovered QML item is destroyed or left, the saver window can keep the hand or arrow
  instead of the Halo until the Halo next re-applies it.

### 1B.4 Shape instrument for Spectrum and Neon Lake (contract: Visualizer_Studio.md)

- [~] `fft_to_bars` gained two helper calls per tick (`shape_bar_profile`, `lane_sample_positions`). The overhead
  baseline was re-recorded after 1B.4 merged (`tools/baselines/overhead/2026-11-11_4658981b.json`, with a Spectrum
  case): the lead confirms the two calls are in it, then deletes this box.
- [ ] Admitted later if wanted (operator's call): a pop-out larger canvas; Spline Curve's layer nodes and Voxel
  Sphere's zone boundaries on the same instrument; Shift axis lock, snapping, double-click reset.

### 1B.5 Neon Lake: all visible land is brush-editable

Contract: `Docs/Reference/Neon_Lake_Basin.md`.

- [ ] Distance-based mesh density was not built (the mesh does not know the eye, and a camera-dependent mesh
  would rebuild and pop): no render shows whether the smallest brush aliases on far land seen up close; render
  it once, and only then decide whether anything is owed.

### 1B.6 Neon Lake: smooth land reaction, Growth and Indents

Contract and measurements: `Docs/Reference/Neon_Lake_Basin.md`. The lead decides when the reactivity is good enough
(operator, 11 Nov).

- [~] Lead's reactivity verdict: watch `indents_p1_heavy1.webp` and one driven showcase per preset with Growth
  and Indents on, beside the music envelope (`tools/visualizer_replay/neon_lake_music_response.py --continuous`);
  write the verdict here (good enough, or the one thing that is still weak) before any further reaction work.
- [ ] Side defect: `tools/visualizer_replay/waveform_music_response.py:63` silently skips recordings without PCM
  (heavy1, quiet_intro*, balanced*) and the report drops those songs without saying so: name them in the report.
- [ ] Side defect: the cost probe does not count GL or Python calls inside modules loaded under alias names, so
  one-session comparisons against an old renderer have meaningless call counts: count by module object.

### 1B.7 Fullscreen Now Playing: one geometry contract with the Media widget (plan 01 M3c)

Contract: plan 01 M3c (what stays overlay-specific, with its reason); the old artwork-factor bridge is in
`Docs/Architecture/Persisted_Input_Compatibility.md`.

- [ ] The safe-area edge guides are no longer drawn in Fullscreen Edit (as in ordinary Edit); confirm that is
  wanted or restore them through the ordinary guide owner.
- [ ] Evidence gap: no side-by-side render of the Media widget's own Edit beside Fullscreen Edit (it needs an
  off-screen harness that drives ordinary Edit on a Media card); build it beside
  `tools/expanded_visualizer_evidence.py`.
- [ ] **Now Playing app-mixer volume child (operator, 18 Nov; new request supersedes only the old "no volume rail" HUD design, not the OSD):** add a separate, independently editable volume child inside fullscreen Now Playing using the Media widget's existing volume child presentation, application-mixer volume authority, semantic colours and material surface. **The Volume OSD controls system volume; this new rail controls application mixer volume.** Never substitute one value/endpoint for the other, add a second volume owner/poller, or display a fabricated app level when the existing Media model cannot provide one.
  - [ ] Default placement follows Now Playing's artwork side: just **left of the artwork** when artwork is on the left, and just **right of the artwork** when artwork is on the right; orientation changes and Now Playing movement/resize move the authored default together. The rail remains its own adjustable/movable child under the existing Fullscreen Edit child-geometry, containment, guides, Undo, Save/Cancel and profile persistence rules; respect explicit child offsets rather than re-snapping them on every layout change.
  - [ ] Inherit the working Media volume child's tint, opacity/material, border and shadow semantics; verify surface rendering on bright/dark fullscreen Visualizers without demanding continuous Visualizer captures. Keep system OSD priority and separate OSD geometry unchanged. Test both alignment sides, missing app-volume capability, edit round trips, multiple displays/DPR and ordinary Media parity. Detail belongs to plan 01 M3c's existing Now Playing child contract, not a second fullscreen editor or a new native-core workstream.

### 1B.8 Light themes are practically opaque in the saver (M1, M2 and M2b merged; M3 waits behind the native core)

**Material track (operator, 11 Nov: proper transparency on light themes, no inset while keeping the material on
all themes, border materials). One agent, one shader, in this order, each its own reviewed checkpoint.** Contract:
`Docs/Architecture/Card_Surface_Materials.md` ("M1 dark-ink rule"; it also holds M1, M2, M2b and the 12 Nov
follow-ups with their evidence folders).

- [ ] Watch: the "three failures in one long run" were not reproduced in any order of that run's 21 files; the
  long run's other two failures may have been the engine worker gate (red since 438790f7, fixed 4a805fe6).

- [ ] Accents whose corrected text ink collapses toward the card text: Royal Orchard most (#3e4f2c to #97a08d,
  48 % of its colour kept) and Smoke Quartz; Slate Lavender, Tungsten Blues, Lantern Grove and Riviera Dusk keep
  61-70 % (`.artifacts/evidence/materials/20261111_m2b/ink_rule/accent_collapse_candidates_3x.png`). A theme-authoring matter: these six accents are too dark for a
  dark card; note it for the theme files, no solver change.
- [ ] The accent as a graphic (bars, dividers, icons; not recoloured) is under 3:1 on eight dark themes: Royal
  Orchard 1.44, Tungsten Blues 2.27, Lantern Grove 2.32, Slate Lavender 2.35, Smoke Quartz 2.59, Riviera Dusk
  2.67, Forest Rose 2.89, Nordic Signal 2.89. The same theme-authoring note.
- [ ] Mid-transition frames and a real display for M1, M2 and M2b: a D1 run (1B.14 harness), lead review.
- [ ] M3. With the inner hairline gone, the border stays clearly distinct from the face on the three light
  themes over a busy bright wallpaper and over a dark one (3x edge zooms); no second line inside the card.
- [ ] **Context Menu backdrop correctness (operator, 16 Nov; close before SMP):** its current `MaterialSurface` samples the shared wallpaper/dimming pyramid, even when right-clicked over another card or the fullscreen Visualizer. This distorts an image which is not actually behind the menu. The menu and its submenu must either sample the *real visible underlay* or render as straightforward theme-coloured translucent surfaces; never advertise a false glass result.
  - [ ] **Investigate first, bounded to the existing material/native compositor:** assess native QRhi's retained layer textures and N5.9's proposed overlap-limited Visualizer glass (D7 point 7; ≤0.3 ms). That source alone omits ordinary cards. Check whether a colour-accurate, correctly ordered *local* composited-underlay texture for the menu's rectangle can be obtained without a new fullscreen capture, CPU/GPU readback, synchronous right-click frame fence, duplicate blur chain, Visualizer-frame work while no menu is shown, or compositor rearchitecture. Test both menu and submenu as they move and overlap other surfaces. No risky new capture owner just to simulate glass.
  - [ ] **Decide by evidence, not the material label:** adopt true blurred/translucent glass only if its sampled colours and spatial details reflect the actually visible wallpaper/cards/Visualizer, its local cost is within N5.9's overlap budget where relevant, and opening, submenu reveal and frame p90 show no meaningful hitch or regression. **Otherwise choose Normal with theme-derived RGBA opacity/tint** (including existing ink-contrast, border, shadow, hover and opacity-adjust authority): a naturally transparent coloured menu with no special wallpaper sampling, fabricated distortion, capture or extra material pass. No new theme switch required.
  - [ ] **Proof and ordering:** compare right-click over bright/dark wallpaper, opaque/translucent cards and active fullscreen Visualizer, including while a wallpaper transition runs; check submenus, clipping, colour/alpha, light/dark themes and mixed DPR on both native OpenGL and Vulkan where supported. Capture pixel evidence plus GPU cost, input-to-menu latency, frame p90 and dormancy, with the Visualizer uninterrupted. Place final material behaviour in `Docs/Architecture/Card_Surface_Materials.md`; use focused Context Menu regressions. This is pre-SMP surface work, shared across Standard/MC/SMP, and must not create an SMP-only renderer.
  - [ ] **Fullscreen Now Playing vs Context Menu underlays (operator, 19 Nov):** the shared wallpaper/dimming material backdrop cannot represent the foreground of an active fullscreen Visualizer. The ordinary Media Control Bar's theme material is accepted and must not regress. **Now Playing is resolved independently:** its optional card and its shared transport bar use semantic **Normal** colour fills with alpha blending directly over the live Visualizer, never false material sampling. Visualizers → Fullscreen Mode → Now Playing has independent **Media Bar Fill Opacity** and **Card Fill Opacity** adjustments (-1..+1, zero = the currently resolved Normal widget-card alpha); those controls affect fills only, leaving outline, separators, glyphs, text, artwork, shadow and timing unchanged. Ordinary Media still uses its own independent material and opacity Style Overrides, including the volume-track-inspired treatment. Validate both fullscreen card on/off, bar/floating, bright/dark and fast-changing Visualizers, Custom positioning, mixed DPI, reset/reload, transitions and original OSD priority; no extra shader/capture or new Media controller.
  - [ ] **Context Menu retains its own evidence-based decision:** true composited-underlay material only if the preceding Context Menu gate proves correct pixels and its GPU/input budget; otherwise theme-semantic Normal RGBA transparency is the reliable fallback. It must not depend on Visualizer preset metadata, palette sampling, or Now Playing's local opacity adjustments. Keep the menu/submenu performance and appearance gates above unchanged.
  - [ ] **Seekbar track and progress-fill surface investigation (do not dismiss):** inspect the ordinary Media seekbar and fullscreen Now Playing seekbar separately for their semantic RGBA fill, alpha/composition and existing material-source availability. Compare a subtle inherited material where the true underlay is available with semantic Normal translucency where it is not; preserve separate track/fill roles, progress legibility, scrubbing hit targets and controls. Decide by screenshots and GPU timing rather than dismissing thin geometry or requiring a new blur pass.

- [ ] Each step: `.qsb` regenerated, the SURFACE block kept identical across its three shader files, one focused
  GPU before/after, lead pixel review on the operator's two wallpapers.

- [ ] **M4 Unified Appearance Theme (operator, 16 Nov):** after 1B.8 M3 / 1.7b material-border rendering and its proof, and **before SMP M0**. Consolidate the separately selected Settings and Widget themes into ONE typed, versioned Appearance Theme, one chosen ID and one global selector. Keep separate actual native Settings-HWND and Qt Quick rendering projections. Current linked pairs and mirror generation are transitional, not the desired permanent architecture.
  - [ ] Shared semantic roles with independently authored Settings / Widget / optional SMP scopes: surface colour/material, **surface transparency bias** (neutral 0), border-surface colour/material, **border transparency bias** (neutral 0), **border thickness** and **four-corner curvature** (correct concentric inner edge), plus typography/contrast. The skinning system does not own these global renderers. Neutral user Style Overrides inherit the authored theme value; nonzero user biases are relative adjustments applied once.
  - [ ] Retire roles left unused by the 22 Nov tile unification (System Stats' `metric_surface_color` and its theme role;
    tiles now take `tile_wash`) when the themes are regenerated here.
  - [ ] **Semantic completeness audit alongside unification (operator, 18 Nov):** inventory presently hardcoded colours, alpha, tint and *reasonably independent* material surfaces across Settings, ordinary widgets and fullscreen overlays; give missing eligible elements typed roles **where the element genuinely has an authored surface/ink purpose**, especially the Media Control Bar (distinct from the Media card), volume child, branded headers, seekbar track/fill and overlay controls. Seed every new role with the **effective visual value the element renders today**, including existing style overrides, so the default unified theme is visually unchanged unless the operator explicitly requests a change. Preserve fullscreen Now Playing’s two fill-opacity biases as neutral-zero adjustments on the resolved Normal semantic alpha, not new standalone colour authority or preset metadata. Preserve shared renderer/semantic ownership and per-element inheritance/Normal overrides; avoid indiscriminate material passes for decorative lines, tiny fills or already-correct surfaces. Prove baseline parity with before/after pixels before re-authoring aesthetics.
  - [ ] **Media application-volume child border thickness becomes semantic at M4 (operator, 19 Nov):** introduce an authored, typed `media.volume.outline.width` thickness role shared by both the vertical track and its filled-level outline, and use the current **2.5 logical px** as the unified-theme baseline. The Widgets → Media → Volume Control **Outline Width** setting, added before M4, must then become an explicit override of that role; an untouched/default value must inherit the theme instead of freezing all users at 2.5 px. Preserve non-default user-authored widths across migration, including zero (intentional no outline). Keep the material-border 20% alpha adjustment and the single-stroke clipping behavior independent of thickness. Confirm round-trip, theme switch/reset, DPI scaling, both alignment sides, Normal/material states and no new renderer or capture.
  - [ ] **Hierarchical sub-semantics (operator, 20 Nov), if architecture and cost allow.** Each role (for example
    border: colour, thickness, surface) has an overarching semantic, and each element (a widget's border, the volume
    child's outline) may carry an optional sub-semantic that takes authority for that element when provided.
    - [ ] Design check first: resolve the hierarchy once, at theme load and on change, into flat per-element values,
      so drawing reads one value with no per-frame lookup chain. Record the cost (zero recurring work) and the
      precedence: element sub-semantic, then role semantic, then theme default, then user Style Override where exposed.
    - [ ] Defaults: no sub-semantic is authored where today's look comes from the role. Where an element differs today,
      its sub-semantic reproduces that, so the regenerated themes render as now (pixel comparison per theme).
  - [ ] **Theme-authored legibility guard per eligible surface:** evaluate a typed semantic on/off (and inheritance precedence) for the guard/legibility panel, resolving theme default -> user Style Override if that component exposes one -> material child, with no duplicate shader or capture. Defaults mirror **current effective per-component states**: the ordinary Media card keeps its guard; the volume child and Media Control Bar do not have theirs restored by accident. Do not apply a global switch that disables guards on unrelated cards or sacrifices necessary contrast; prove light/dark/bright-scene ink accessibility and independently configurable card/child guards.
  - [ ] Regenerate curated themes semantically into the new format; preserving old bundled .srtheme/.srwtheme pairs byte-for-byte is not required. Retire the duplicate catalogues/mirror sync after accepted projection. Convert user-authored themes and Custom values in a bounded one-time importer where possible; otherwise back up the originals and report a safe fallback. No silent deletion of personal files.
  - [ ] Prove dark/light/material themes, Settings, Context Menu, Media and ordinary widgets; neutral and non-neutral surface/border bias, border width/curves, flat/material fallback, DPR 100/125/150/200%, real bright/dark backgrounds, hot selection, legibility and no extra underlay capture. The M3 material-border pass and native corner constraints remain independent renderer contracts. See SMP document 05.
- [ ] **Theme Studio (operator, 21 Nov; supersedes "Studio only at SMP M10"):** after the native core work, the flip
  (NF) and its follow-ups, and M4, and **before SMP M0**; not worth building before then. One visual editor for the
  unified Appearance Theme at the quality of the Visualizer Studios: live rendered previews of real Settings, ordinary
  widgets, Media, the Context Menu and fullscreen overlays on light and dark backdrops at real DPR; edits of every
  semantic role and sub-semantic (colours, materials, face and border transparency bias, border thickness, curvature,
  typography, legibility guard) with an inheritance inspector, one-click revert, undo and redo, Save and Cancel, and
  export and import through the production theme loader. It renders through the production theme renderer (no second
  renderer, no per-frame theme parsing) and edits appearance only. SMP M10 later adds skin authoring and the SMP
  Full/Compact previews to this same Studio. Design: `Docs/Future_Work/ShittyMusicPlayer/05_Theme_Skin_Studio.md` §5.

### 1B.9 Settings and Studio window corners bleed (continues 1.9)

- [ ] Studio's outer corners to match the visible Settings improvement: UI-1 of `Docs/Future_Work/Studio_Corners_Card_Rim_and_Visualizer_Rotate_2026-11-09.md` (its live checklist;
  UI-2 landed in 7cbc1d5b). Do it with this section's corner work, as one owner.

Measurements, rejected alternatives and the residue no layered window can remove:
`Docs/Architecture/Settings_Theme_Architecture.md` (native corners).

- [ ] Side defect: the Studio window shows only blur (no title bar or content) in native captures by
  `tools/settings_native_corners.py --window studio`; find whether it is the capture setup or the Studio.
- [ ] Side defect (red on main before this work): `tests/test_waveform_studio_theme.py::
  test_every_theme_yields_readable_studio_chrome[Matte Graphite [Single]]`, accent-text contrast 2.12 against 4.5.
- [ ] `tools/settings_native_corners.py --qt-scale-factor` sets Qt's `QT_SCALE_FACTOR` inside the tool process to
  emulate 100% and 200%: decide whether that tool-only use stands under the no-environment-variables rule.
- [ ] Window border material: the border ring takes 1.7b's border-material treatment (one rule for cards and
  windows), inside the +2 px budget (unused: the border stays 4 px).

### 1B.10 Presets (Opus Medium, low priority, when nothing more significant waits; the lead judges the pixels)

Every preset must read as unique and visually impressive; the agent may ask the lead for a feature or
architecture a better look needs, if it is not wasteful. Order: Spectrum, then Extruded Bubble, then Neon Lake;
the agent reports after each mode for the lead's pixel review. Presets are authored, mutable and exchangeable:
this item describes looks, and nothing here or anywhere names, counts or pins them.

The operator's taste for Spectrum (11 Nov, on five of round 1: "are all ghastly ugly"): wide glossy, chrome,
capsule, grid-on-block and dark-fill looks fail; fine luminous gradients pass; fewer good presets beat a full slot
count. The Spectrum features and the Bar Gap control are in `Docs/Reference/Visualizer_Reference.md`.

Every 3D look (operator, 14 Nov): never a near-lens blob (a defocused shell or bubble in front of the camera);
the lead rejects any still or showcase frame that shows one.

- [ ] Defect: growing a painted Neon Lake grid shifts the picture 0.055-0.11 of a level on average (allowance
  0.02); `tests/test_neon_terrain_growth.py` holds it as an expected failure. Cause not found (tile alignment,
  edge clipping and mound position ruled out). Root-cause it, with the far-land Water trench below if related.
- [ ] Defect: a river painted with the Water brush in Neon Lake's far land draws as a straight-walled trench, not
  along its path (reproduction: `render_neon_evidence.py stills --preset 1 --look
  .artifacts/evidence/visualizers/shockwave_grid/presets/20261114_round1/side_defect_far_water_trench/look_river.json`).
- [ ] Side defect: Rim Glow measures distance to the square edge (`spectrum.frag:783-785`), so it facets at
  rounded tops.

### 1B.10a Extruded Bubble idle wake continuity (deferred, before SMP)

- [ ] **Idle parent bubbles occasionally teleport their wake bubbles (operator, 19 Nov):** this persists in Extruded Bubble with wakes enabled, less noticeably for small parent bubbles and more noticeably for larger parents. Reproduce on steady idle motion at contrasting parent radii with stable bubble/wake identity traces, world-space positions and successive frames; determine whether the cause is wrapping, spawn/expiry, parent-relative transform, interpolation or a GPU/CPU lifetime mismatch. Correct the owner, not by fading out the symptom; preserve authored wake motion and the already-required stable-world/camera contracts in `Docs/Reference/Extruded_Bubble/Target.md`. Cover Normal/paused/idle audio, large/small bubbles and camera motion with focused tests and real visual evidence. **Scheduled as N5.6's first step, before the port records its references (operator, 21 Nov).**
- [ ] **Preset 9 (Deep Red Ocean): rapidly flickering bubble-star/circle at the default camera (N5.6's first step):** at the authored default view, which is otherwise good at fullscreen 4K, a very fast flickering circular/star-like arrangement of bubble lines is briefly visible and difficult to capture in screenshots. Investigate whether an emission source or spawn geometry is leaking into view; gather high-frame-rate footage or captured successive frames, verify emitter culling and view transforms, and hide the source without hiding the legitimate emitted bubbles. Treat this as a shared Extruded Bubble system issue unless evidence isolates a preset defect.
- [ ] **Existing regular bubbles not consistently accelerated by music (N5.6's first step):** confirm that all eligible *already-living parent bubbles*, not only newly emitted bubbles, respond to music-driven acceleration. Exclude microbubbles and particles. Compare old/new bubble identity and velocity under the same audio, checking pinning, age-dependent logic, lifetime state, spawn-time-only parameter propagation and native buffer updates. Preserve intentional pinned motion if explicitly authored, but correct accidental non-reactivity at its owner. Reproduce on Preset 9 and another preset, with paired real-audio and idle tests. **Both Preset 9 issues are N5.6's first step, fixed on the Python side before the port's references (operator, 21 Nov).**

### 1B.11 Theme filter in the Linked row (contract: Settings_Theme_Architecture.md "Theme filter")

- [~] Themed list scrollbars merged 21 Nov (the product drew the platform's bar too); a real Windows 11 hover in
  1B.14's Settings and Studio box (every Settings tab's scroll area now takes the same owner). The Studio's QML bars
  are 1B.14's.

### 1B.12 Fullscreen glyphs relative to the Visualizer's display (contract: plan 01 M3c)

- [ ] A display arrangement changing while the saver runs is covered only by re-admission in tests; check it on
  the topology-replacement path.
- [ ] The Reset Camera glyph (a font character) shows coloured edge fringes in off-screen crops; confirm on a
  real display and paint it as a path like the arrows if it does there too.

### 1B.13 Hold right-click to pan the live Visualizer (contract: Spec.md / Contracts.md input)

- [~] Native pointer capture on a real foreground window (tests use a stand-in capture): 1B.14's held-right pan
  box.

### 1B.14 Lead verification runs (operator, 11 Nov: "why can you not make tests that exercise these?")

Tools: `--only-display <index>` (RUN only, fails closed) and `tools/d1_run.py` (the real saver on one display,
bounded, frames read back from the saver's own window and from the desktop, crops, logs; refuses the primary
display; `--help` holds the recipes); both in `Docs/Reference/Harness_Index.md`. Permissions (operator, 11 Nov):
bounded runs on Display 1 are the lead's; Display 0 is rare (the lead only, through `--allow-primary`, never in a test, recipe or automated run; agents never take it); builds run only through GitHub's workflows.
Agents build harnesses and prove them hidden; each visible run is short, bounded, fails closed and tears down.
Every `[~]` box in this plan that says "D1 run", "Studio run on D1" or "Frozen run" is run in these sessions.

- [~] Cursor after exit (R-183) on D1 with `tools/cursor_exit_observer.py`: key, click, mouse-move, link click
  (browser launch stubbed), Settings and Media Center exits, the pointer placed over the saver on D1 for the
  run and put back after; a verdict per path. Then R-183 is accepted, or the failing path is fixed at the
  retire owner and re-run.
- [~] Held-right pan on D1: real pointer capture on a foreground window (press, drag, release; a click still
  opens the menu on release; focus loss mid-pan releases the capture).
- [~] Expanded Visualizer on D1: expand, collapse, the fullscreen arrows offered for the real arrangement, the
  move toward D1 from a hidden D0-side owner where that can be driven without showing anything on D0; frames
  grabbed and reviewed by the lead. What truly needs both displays visible is listed in the report, not assumed.
- [~] Settings and Studio windows on D1: corner drag and resize from each corner by messages (the alpha-1 corner
  pixels keep input); the Studio's corners captured natively; the scrollbars of the theme list, the theme
  filter's popup, the Sources list and autocomplete captured (theme them through `shared_styles` if they are
  native bars there; 1B.11, 1C.9).
- [ ] Frozen build: `tools/github_remote_build.py` on the pushed commit (the lead's standing permission).
  - [ ] From the artifact: the engine worker's import closure is QtCore only and the image worker's Qt
    dependencies are the expected ones (the oracle of `tests/test_visualizer_engine_import_weight.py`, run
    against the frozen manifest); icons unchanged.
  - [ ] The frozen product on D1 with diagnostic flags: worker memory flat across a Settings round trip; the
    first Neon Lake activation logs a cold link or a cache hit and never an activation-failure reload; the
    second run a cache hit.
  - [ ] In the same frozen run: saves work, and a Studio opens (the 6 Nov "QtQuick.Controls.Basic is not
    installed" fix; contract `Spec.md`, frozen QML package contract;
    `test_every_shipped_qml_import_survives_the_frozen_prune`).
- [ ] Real audio endpoints: a test that opens real WASAPI loopback in the engine worker and drives the product's
  own device-change path with real endpoint ids; it skips cleanly with a stated reason where the machine has no
  second endpoint.
  - [ ] Two or more active render endpoints: a default-device change to the other endpoint (the notification
    delivered with its real id; no system setting changed) and capture resuming on it.
  - [ ] One endpoint: invalidate and reopen on the same endpoint.
  - [ ] Endpoint removal by its notification.
  - [ ] The in-process path too.
- [ ] First reveal, worker against in process, without load on D1: the time from activation to the first drawn
  frame for each mode on both paths.
- [ ] `tools/d1_run.py` hands `screen.grabWindow(0)`, a `QPixmap`, to its writer thread (`_write_frame`; 12 Nov night
  audit, low 1). It works only because Windows' platform reports threaded pixmaps: convert with `.toImage()` on the
  GUI thread (one frame's copy) so the tool does not depend on it.
- [~] Carried from section 1A's former "Awaiting Validation" list, in the D1 sessions: the changed glyphs as
  zoomed crops; camera and child placement round trips; long fullscreen metadata and controls; material
  comparisons on native pixels.

### 1B.16 Tooling (Docs/Reference/Tooling.md, merged 12 Nov)

- [ ] Candidates to retire (Tooling.md's table; the operator keeps useful tools, so the lead judges each and deletes
  only what is dead and superseded, recording the reason): high confidence `verify_compile.py` (repo root) and
  `.github/tools/linux_smoke_dist.py` (a stale copy no workflow runs); the medium and low rows stay unless a caller
  check proves them dead.
- [ ] Workflow supply chain (12 Nov evening audit, low): `.github/workflows/native-module.yml` pins its actions by major
  tag (`actions/checkout@v4`, `setup-python@v5`, `cache@v4`, `upload-artifact@v4`); pin each by commit SHA with the tag
  in a comment. `tools/native_sdk_fetch.py` says Vulkan-Headers 1.4.341 is "the release it is built with" for Qt 6.12
  with no source: cite Qt's own build record, or say it is the loader's version on this machine.

### 1B.15 Housekeeping the lead decided (11 Nov; engineering choices, not operator decisions)

- [ ] Extruded Bubble evidence of 20 Oct: the references now point to
  `.artifacts/evidence/visualizers/extruded_bubble/20261020/` (`RELOCATED` in `tools/artifact_migration.py`),
  but neither that folder nor the old `Docs/Reference/Extruded_Bubble/Evidence/2026-10-20/` exists on disk any
  more: the media `Investigation.md` cites is gone. Say so in `Investigation.md` (one line under its evidence
  list) so nobody hunts for it; the 22 and 23 Oct folders are still referenced and still ignored by git.

## 1C. Operator's diagnostic run (11 Nov, evening; ahead of everything in 1B that is not already in flight)

The operator ran the product themselves and reported five defects ("do not rely on me for future runs"). Rule
for this section and from now on (operator, 11 Nov): the plan holds every task in detail before it is dispatched;
an agent's brief is its plan item, and its report is checked against the boxes, never taken on trust or kept only
in the lead's memory. Each item below starts with a root-cause box: the cause is established on the real product
path (an off-screen reproduction or a Display 1 run), with a negative control, before anything is changed.

### 1C.2 Display moves retarget the live Visualizer (R-194)

Operator: "we do not want teardowns and rebuilds unless absolutely needed. They are a last resort." A display move
attaches the session to both scenes and commits in place (decision: plan 01 M3c; rule:
`Docs/Guardrails/Presentation_Change_Preflight.md`, "Retarget before rebuild"). Teardown remains only for a display
arrangement change, a display added or removed, the owning display lost, Settings, and corrupted-object recovery.

- [ ] The 1.5 s preparation bound on a cold shader cache (34 units land at 1.22-1.28 s warm, close to the bound).
- [ ] PyOpenGL's `GL_TIMEOUT_IGNORED` has the wrong value (`glWaitSync` rejects it): the move uses the GL spec's
  value; record it where GL constants are shared so nothing else takes PyOpenGL's.

### 1C.3 Fullscreen Now Playing: one Edit contract with the Media widget (R-189)

Contract: plan 01 M3c; evidence `.artifacts/evidence/visualizers/shared/expanded_now_playing/20261112_1c3_after/`.

- [ ] Side defect (watch): `tests/test_visualizers_fullscreen_mode_pill.py` crashed once with an access violation
  when run after overlay_settings, fullscreen_edit and overlays in one process (not reproduced with two files).

### 1C.4 Spline Curve's white lines show about one pixel into the card border (R-191, R-192)

- [ ] The tests that open windows were not run on the merge (`test_qtquick_visualizer_clip_smoke.py`, Neon Lake's
  `actual_neon_qsg_pixels`): run them hidden at the next milestone run.

### 1C.5 Volume child control: its drop shadow was cut off sharply (R-187)

- [ ] The agent could not reproduce the cut at the operator's stored Media layout (no volume edits in their
  settings): a D1 run with a copy of the operator's profile (1B.14), a 4x crop of the volume bar, lead review.

### 1C.6 SMP full-player mock restored (operator, 11 Nov; `references/` is ignored by git)

The mock, its sixteen requirements (R1-R16), the lead's proposals and the operator's clarification are in
`Docs/Future_Work/ShittyMusicPlayer/04_Full_Player_Mock_2026-11-11.md` and plan 02; the mock files are
`references/` (ignored by git). SMP stays behind the native core, the open defects and the fullscreen Visualizer.

- [ ] Rules that keep SMP's doors open, to check at every audit until SMP starts (document 04 section 8, last
  list): the Media widget, Now Playing and the seek bar stay host-agnostic; the Visualizer stays one owner that can
  be retargeted between hosts and rendered at any aspect, strips included; Edit's handles, guides and snapping
  stay reusable components; the native core renders into whatever surface its host gives it.
- [ ] The operator's answers to the mock document's section 6 (what "CS" is; whether Lyrics and Artist Collage
  are in the first full-player milestone; whether the wider dock model is wanted) are recorded there when given.
  Nothing waits on them.

### 1C.8 Neon Lake: the water's edge and face lines can be hidden completely

Contract and evidence: `Docs/Reference/Neon_Lake_Basin.md` "Water Lines".

- [ ] The showcase WebP at Water Lines 0 was lost when its worktree was retired (the retire step copied only evidence;
  it now copies WebPs too): re-render it with `tools/release_media.py` (Preset 3 at 0 on the heavy recording) and
  review it.

### 1C.10 Neon Lake round 3 (operator, 11 Nov evening; one Opus High agent when a slot is free, in this order)

One agent, one mode (`shockwave_grid`), four features and two repairs, each its own reviewed checkpoint. Every
new control is a canonical spec entry in `core/settings/visualizer_mode_settings.py`, off or neutral by default,
authored neutral into every Neon Lake preset by the repair fill, shown in Settings and the Studio through the
spec, identical pixels and zero cost when off (a skipped branch, not a multiply by zero), Settings/Studio and
engine-worker parity rerun, `Docs/Reference/Neon_Lake_Basin.md` and the Visualizer Reference updated. Everything
ramps and fades; nothing pins at its ceiling on loud music and nothing mutes mid-song kicks in continuous play
(judge on whole songs with `tools/visualizer_replay/neon_lake_music_response.py --continuous`).

**a. Repairs first (they change what the rest is measured against)**

- [ ] 1B.5's dormancy fault: an ungrown grid with React To Music off pays for the terrain-overlay path; skip it
  (identical pixels, the pre-1B.5 cost), re-measured alternated in one session; the five unattributed GL calls.
- [ ] 1B.6's paused Studio preview: a paused seek shows the reaction the fixture has at that time.

**b. Water lines can be hidden: plan 1C.8, as written there.**

**c. Spire glow on hits (operator: "spires should glow an editible colour on hits. Completely optional in the
Studio. If you want a test colour just pick one of the dominant colours.")**

- [ ] The hit part of the Growth drive exposed on its own (today it is mixed into the drive): a frame-field
  value and one uniform, memoryless on the fixed scale like the other drives; nothing per frame when off.
- [ ] Growth's share of a vertex's height passed to the fragment shader; emission added into the bloom target
  in proportion to that share and the hit value, so only what grew glows, tallest most; mounds glow less than
  spires by the same rule (Growth Shape decides), no separate switch.
- [ ] Two spec controls in the Studio's Reaction workspace beside Growth: "Spire Glow" (amount, 0 = off and
  identical to today) and "Spire Glow Colour" (an editable colour). No test colour is shipped in presets: the
  presets are authored at 0; for evidence use each preset's dominant accent (Preset 1 its magenta ridge colour,
  Preset 3 its gold).
- [ ] The glow rises with the hit and decays over a few hundred milliseconds (a ramp, never a flash that
  strobes); on sustained loud passages it settles below its ceiling so the next hit still reads.
- [ ] Evidence: a staged sheet (hit value 0, 0.5, 1 on Presets 1 and 3), one driven WebP on `heavy1`, the
  music-response trace with the glow term beside the song's envelope; lead pixel review.

**d. Vertex trace (operator: "would a vertex trace reaction also be viable? When on and a colour is chosen
vertexes react to music by changing colour to the chosen colour and you could select 'Random', 'Left to Right',
'Back To Front', 'Front To Back' and 'Center Out' as their starting points. Their speed and colour deepness
effected by intensity, making sure not to pin.")** Viable and cheap: the land's vertex points are already drawn
by a vertex shader that knows each point's position, and the mode already carries a small ring of travelling
wave fronts from the tick to the shader.

- [ ] Design note first (half a page in `Neon_Lake_Basin.md`, seen by the lead before code): each vertex gets an
  order key in 0..1 from its position by the chosen start: Left To Right (basin x), Back To Front and Front To
  Back (depth from the saved camera's forward axis, so it reads the same from the default view), Center Out
  (distance from the lake's centre), Random (a stable hash of the cell, so it never shimmers frame to frame). A
  trace is a front that travels along the key; a vertex's colour moves toward the chosen colour as the front
  passes and relaxes back behind it over a set tail length.
- [ ] Fronts are launched by the music in the tick (a hit above the passage's own level launches one), kept in
  a small fixed ring (as the wave ring is), advanced on the logical tick, sent as one uniform array; the vertex
  shader does a few operations per vertex per live front and nothing when the ring is empty.
- [ ] Intensity drives two things, both through soft knees so neither pins: the front's speed (faster on
  louder passages, bounded so a front is always seen to travel) and the colour's depth (how far a vertex moves
  toward the chosen colour; never fully replacing the land's own colour unless the control asks for it).
- [ ] Spec controls in the Reaction workspace: "Vertex Trace" (amount, 0 = off), "Trace Colour" (editable),
  "Trace Start" (Random, Left To Right, Back To Front, Front To Back, Center Out; Title Case as written here),
  "Trace Length" (the tail). Whether land vertices only or the water's vertices too: the agent renders both
  and the lead picks.
- [ ] It composes with Growth, Indents and Spire Glow without double-brightening (the trace recolours the
  vertex; glow adds emission; together they stay under the bloom ceiling on `heavy1`).
- [ ] Evidence: one WebP per Trace Start on Preset 1 with a test colour from its dominant accents, the
  music-response trace showing launches against the song, a continuous-play run over three songs (launch
  counts per third, no starvation after loud passages), cost per frame against the overhead baseline; lead
  pixel review.

**e. Islands (operator: "land can grow out of water but only in exceptional music circumstances"; optional,
last because it touches the water's edge)**

- [ ] The standing rule changes for this one feature only, and the docs say so: the authored shoreline never
  moves; islands are extra land that may rise inside the lake while the feature is on.
- [ ] "Exceptional" defined on the music's own scale and proved on whole songs: an island rises only when the
  passage level has stayed in the top few percent of the session's own recent loudness for some seconds *and*
  a strong hit lands; a cooldown follows; a quiet or even song raises none. Calibrate by presence on the
  recorded songs (0 on `quiet_intro` until its loud end; 1 to 3 across `heavy1`), never by absolute levels.
- [ ] A few fixed island sites per preset (seeded from the terrain record, in open water away from the shore and
  the celestial reflection path), each a smooth mound; an island rises over seconds and sinks over seconds
  (fade, never vanish), and never breaches the camera floor's clearance.
- [ ] The island gets a real water's edge without recomputing the precomputed bank distance: its shoreline
  distance is analytic (distance to the island's current waterline circle), and the shore glow, wet fringe,
  wave taper and reflections read the smaller of the bank distance and the island distance. With no island up
  the term is skipped and the frame is identical to today.
- [ ] The camera floor's ripple allowance and the water reaction account for an island that is up; Growth,
  Indents, Spire Glow and Vertex Trace treat island land as land.
- [ ] One spec control, "Islands" (off by default), with at most one more for how rare; in the Studio the
  Peak fixture can force one for authoring.
- [ ] Evidence: rise and sink WebP on Presets 1 and 3 with 4x crops of the island's waterline (glow and fringe
  wrap it, no hard ring), the whole-song launch table, GPU cost with an island up and with none, alternated in
  one session; lead pixel review. If the analytic edge cannot be made to look right, stop and report with the
  renders rather than shipping rocks without a shoreline.

### 1C.9 Sources: RSS Pools shows which pools are active and valid

Contract: `Docs/Architecture/Settings_Theme_Architecture.md` (the shared list style and the Sources pool rows).

- [ ] The marks seen with real stored health once (a D1 or frozen run of 1B.14 after a real fetch), lead review.
- [ ] Not rendered: a Mica theme; the onboarding lists keep their own style (decide whether they join the shared
  one when onboarding is next touched).
- [~] The Sources list's scrollbars (unthemed black native bars in off-screen renders; the Themes list too): 1B.14's
  Settings and Studio box.

## 1D. Operator requests (12 Nov, evening; after the current agents pass audit)

### 1D.13 Side defects found at its merge (15 Nov; Opus Medium when a slot is free of native work)

- [ ] Two tests fail only inside one long same-process pytest run (2,413 tests over 14 minutes), and pass alone:
  `tests/test_waveform_pulse_rim.py::test_pulse_rim_off_is_pixel_identical_to_the_light_pass_without_it` and
  `tests/test_qtquick_ordinary_widget_host.py::test_refresh_transition_clock_coalesces_arbitrary_simultaneous_consumers`.
  A third, `tests/test_qtquick_startup_reveal.py::test_startup_reveal_primes_zero_then_completes_at_one_once`,
  failed the same way in the 1D.12 merge run (4,407 tests over 33 minutes). Find the leaked state or ordering they depend on, and make each test own its preconditions.
  The N5.1 merge run (4,529 tests, 44 minutes, one process) added twelve more of this kind; they pass alone.
- [ ] Watch for recurrence of the Oscilloscope reflow clip-smoke red; retain captures and owner-resolved vertical
  geometry before judging the thresholded lit-row oracle. Protected QSG/clip implementation stays unchanged.
- [ ] Lead, Display 1: confirm R-221 in the product, Fullscreen Hide Borders with pixel shift stepping, and check
  whether the operator's lavender edge colour came from the shift.
- [ ] Checkpoint audit 1 M1 (15 Nov, 1D.12 C; open, found by the 20 Nov closed-report triage): a display move back to a
  display whose Visualizer shell already exists replays the 3D control hint. The transfer reuses the retained root
  (`scene_controller.py` `transfer_visualizer_to`, `_adopt_visualizer_transfer`), and neither the host binding's
  `transfer` nor `_transfer_quick_visualizer_unit` re-projects `controlHintShown`
  (`_configure_quick_visualizer_input_admission` runs at bind and mode edges only). Case: A's hint on D1, move to D2,
  switch to B, hover on D2 (B joins the set), move back: D1's retained root still reads B as not shown and plays it
  again. Fix at the transfer edge (the adopting scene projects the session set); test with two hidden production hosts
  and the real `transfer_visualizer_to` (the audit's probe printed "display 1 root reused = True controlHintShown =
  False"; it is no longer on disk), negative control today's code.
  - [ ] Its L2: `tests/test_visualizer_control_hint_once_per_mode.py::test_display_manager_hands_every_display_the_sessions_one_set`
    compiles `_configure_quick_visualizer_input_admission` out of `display_manager.py` and drives `SimpleNamespace`
    stubs; rebuild it on `tests/_display_manager_doubles.py`, and replace the `_admit()` stand-in for a display move
    (the test says a move rebuilds the root; it does not).

### 1D.10 Audit of 13 Nov: what is left after its merge (14 Nov)

- [ ] C++, with the next native build round: excuse `vulkan_context.cpp:205-207`'s two messages only when Qt6Gui
  is the caller; prune `surfaces.cpp`'s window registry (`:51-54`, `:295-305`). Then the lead runs host_check, which
  also proves the new `front_face_fixed_cw` control and the Qt-only cycle verdict on the GPU.
- [ ] `tools/build_runner.py` `_fit_initial_window`: on a work area shorter than the content, the
  fit clamps Tk's client height without counting the native frame, so the window's bottom passes the work area by
  about 25 px. This only affects short screens; the operator's 732 px stays. Count the frame in the clamp.
  `tests/test_build_foundry_window_layout.py -k keeps_the_whole_window` is a strict expected failure until then.
- [ ] Archive Foundry's close joins a read-only worker for up to 10 s on the GUI thread (audit low 5). Bound the join tighter,
  or detach the result safely.

### 1D.11 Extruded Bubble side defects from N1.6 (14 Nov; Opus Medium)

- [ ] Port note (N5.6): the beads program puts its probe sampler and its `EbMaterialDrift` storage buffer
  (`extruded_bubble_program.py:1441`) both at binding 6. That collides on Vulkan's single binding namespace;
  renumber at the port.
- [ ] Convert the traced glass at its port (N5.6): converted alone it differs by one 8-bit level on 1-2 pixels in
  14-26 of 549 frames (compiler rounding). Its probe geometry shader also stays on the ratchet (no HLSL for its
  layered `gl_Layer` write).

### 1D.6 Leaving fullscreen on another display lands the card in a poor spot (operator, 13 Nov; Opus High, design first)

Case: the Visualizer sits at B2 on D1, is moved to A1 on D0, goes fullscreen and is moved to D1 (that move works),
then leaves fullscreen. It lands at a spot mapped from D0 instead of its own B2 on D1. Log
`logs/evidence_chest/logs2bec597a774.zip` (`screensaver_geometry.log`): every "Visualizer display move/hop" maps the
source rect over (D0 (51,38) became D1 (2760,143)). The one time it came back to D0's original spot (06:38:37) the
mapping only happened to match. Nothing remembers a display's own last ordinary placement. The log also shows
borderless fullscreen transfers working smoothly.
- [ ] Design note first (plan 01 M3c, beside "Display moves retarget"), for the lead's approval:
  - One authority: `rendering/quick/custom_layout_owner.py` stays the only owner of ordinary placement. A
    remembered per-display placement is a field of that owner's stored record, keyed by monitor identity (the
    `monitor_bindings` identity), never a second store or a renderer-side guess.
  - When it is written: only at a committed ordinary placement on that display (Edit commit, drag commit, a
    move's landing).
  - When it is read: on leaving fullscreen onto a display, and on an ordinary display move landing there.
  - Its validity rules: still on that display's current geometry and DPR, inside the safe area, no overlap
    breaking the existing collision rules. An invalid one falls back to today's mapping.
  - The interaction with Edit's draft, Restore Size, the shape (B2 is a position and a shape), presets of
    placement, and the R-63/R-192 whole-pixel rules.
- [ ] Build to the note; the move keeps "retarget before rebuild" and the fade.
- [ ] Tests: the operator's exact sequence (B2 on D1, move to A1 on D0, fullscreen, move to D1, leave fullscreen)
  lands at B2; an invalid remembered spot falls back; nothing else in the record changes (negative controls).
- [ ] Lead D1 run with both displays: the sequence above, edges read.

### 1D.9 Linux credential encryption, port from the archived branch (Opus Medium, low priority; Linux is best effort)

- [ ] The Linux branch was deleted on 13 Nov and archived as tag `archive/linux-branch-2026-11-05`. Its one unported
  piece: Linux credentials through a per-user key in the Secret Service keyring (`core/secret_service_key.py`,
  the `core/windows/dpapi.py` rework, no plaintext fallback). Port it onto today's `dpapi.py` without changing
  Windows behaviour, with its tests and the `Linux_Plan.md` row updated.

### 1D.2 Fullscreen Visualizer display styles

- [ ] Watch R-192's enclosed axis. A monitor with no exterior edge on an axis whose extent is not whole at its
  DPR (the middle of three in a row; the centre of a 3 x 3 grid) keeps Qt Quick's stretch there, and Borders To
  Edge's frame shows it. `test_the_enclosed_axis_stretch_is_recorded_not_hidden` records it.

## 1A. Fullscreen, Rotate, material and corner items (1.0 to 1.9)

### 1.0 Rotate in ordinary and fullscreen Edit

- [~] Lead review of rendered frames (off-screen for ordinary Edit, D1 run of 1B.14 for fullscreen Edit): Rotate in
  every mode except Sphere, in ordinary and in fullscreen Edit.
- [~] Lead review of zoomed glyph crops: the rectangle/quarter-turn glyph against Reset Camera.

### 1.0b Studio Rotate control

Preview orientation is per-open state, separate from camera/artwork and desktop CUSTOM orientation; Copy Frame
captures it.

- [~] Studio run (D1, 1B.14 harness), lead review of grabbed frames: Studio's Rotate control in every mode except
  Sphere.
- [~] Same run: upright handle labels.
- [~] Same run, drags posted by messages: rotated brush/drag feel (the drag lands where the pointer is).

### 1.1 Mode switch with no direct cause (Awaiting Logs)

- [ ] No direct mode-switch cause in the supplied archive. On recurrence, correlate the reported time, prior/result
  mode, selected preset and runtime generation with the existing mode-transition owner and frame trace.
- [ ] Distinguish explicit selection, enabled-mode normalization and Settings restoration first.

### 1.4-1.5 Remaining fullscreen visual acceptance

- [~] Fullscreen run on D1 (1B.14 harness), lead review of grabbed frames: Media Bar and Floating Glyphs styles.
- [~] Same run: long metadata fitting.
- [~] Same run: multiline Edit boxes and optional album, including Save/Cancel.

### 1.6 Achievement Pulse child placement

- [~] D1 run (1B.14 harness) with `--geo`: check child placement after Settings/fullscreen return (replaying the
  saved payload on Edit entry must not change the canvas; disabled provider fields must not count as painted capsule
  rows).

### 1.7a Studio legibility follow-up

- [ ] Resolve the intended density once (the panel guard raises broad light surfaces nearly opaque to carry
  accent/focus marks).
- [ ] Minimally correct runtime semantic ink against its actual composed locations; retain authored/scene colours.
- [ ] Prove controls/traces on final off-screen wallpaper renders.

### 1.7 Material density (separate reversible slice)

Contracts and evidence: `Docs/Architecture/Card_Surface_Materials.md`,
`Docs/Architecture/Settings_Theme_Architecture.md`, `Docs/Reference/Visualizer_Studio.md`. Final native checks use both
operator wallpapers under `C:\Users\Basjohn\Documents\[4] WALLPAPERS\PERSONALSET`; Studio renders have no DWM proof.

- [~] Lead review of side-by-side renders (the supplied widget material screenshots beside current cards, both
  operator wallpapers): especially the good Glass/Frosted volume surfaces, Glass inset/distortion, and Studio
  panels/tabs/headers/wells.
- [~] D1 run (1B.14 harness), lead review of grabbed frames: exercise Settings Opacity Adjust and Widget Opacity
  Adjust in Style Overrides (-1..1, neutral 0).
- [~] Studio run on D1 (1B.14 harness): live Studio material switching, snap and resize, driven by messages.
- [ ] The remaining unsampled control/delegate inks.

### 1.7b Material-aware widget border (near-term, independent material slice; 10 Nov)

**Source implementation candidate (19 Nov, awaiting compiled shader and operator validation):**
The shared `OverlayCard`/`MaterialSurface` path now carries one separate material ring, a global
Border Surface choice (Normal / Theme / Acrylic / Glass / Frosted / Mica / Smoked), and an
independent Border Opacity slider (neutral 0). The ring uses the existing display backdrop,
adds no QML layer/extra capture, and never applies a border legibility panel. Do not mark the
feature complete on source checks alone: the committed `.qsb` is not regenerated by this
handoff and must be rebuilt with the pinned Windows Qt toolchain before runtime testing.
The following unchecked items are **mandatory acceptance gates**, not deleted work.


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
- [ ] **No fixed minimum border-width rule (operator, 19 Nov):** admit material borders at every positive authored
  visible stroke width, including 1–2 logical px. Use proper continuous rounded-SDF coverage and device-pixel AA,
  not a 3 px eligibility gate that silently switches thin borders to Flat. At subpixel physical widths preserve
  sensible coverage and shape without inventing a thicker border. Verify 1/1.5/2/3/5 px at 100/125/150/200% DPR,
  with normal/material switching and all corner radii; let measured appearance decide future tuning.
- [ ] Retain the authored theme border colour/contrast as the ring's tint/edge authority and border width/radius as
  its geometric authority.
- [ ] On Normal or Flat, retain today's Rectangle border **pixel-identically**; on active material, remove overdraw
  by that Rectangle only for the ring.
- [ ] Must remain clear against the fill, including on Glass and bright wallpapers; validate stroke AA, translucent
  corners, 100/150/200% DPR, normal/material switching, card opacity/theme inheritance and Style Overrides reset.
- [ ] **Measure incremental material-border overhead, not accepted card-material cost (operator, 19 Nov):** take a
  comparable GPU/CPU/frame-time baseline with the *existing, accepted card materials* active, then enable the border
  ring alone. Compare one, several, and densely populated simultaneously visible ordinary widgets, plus existing
  material children/headers, over static wallpaper and during wallpaper transitions; include glass/acrylic/frosted/
  mica/smoked, normal/flat fallbacks, varied border widths and mixed DPR. Record GPU pass/sample counts where available,
  per-frame GPU cost, frame p90/p99, 90 Hz cadence impact, scene-graph item/node counts, memory changes and idle/dormant
  behaviour. The extra border must be in the SAME material shader/sampler invocation with no duplicate backdrop blur,
  capture, full-scene pass or per-border worker. Reject or optimise only a measured regression; do not re-open the
  already accepted card-material rendering or divert the native core work for cosmetic materials.
- [ ] Include the framed and expanded Visualizer frame using its own authored width, radius and colour, not the
  ordinary `OverlayCard` geometry. **Separate foreground path awaiting measurement (19 Nov):** the live Visualizer
  paints above its existing card-face shader, so the border-only material shader has to paint above those pixels;
  it cannot share the ordinary card's single face/border quad without covering the live content. Check 4K/90 Hz
  GPU/CPU frame-time impact of this *extra border-only draw*, static backdrop sampling, 1–2 px strokes and
  Native/Vulkan/OpenGL parity. Normal/zero-width/missing-backdrop must not instantiate a border shader, and no
  extra backdrop capture or work per frame beyond the existing conditional draw is permitted. If its measured cost
  is unacceptable, optimise/defer that Visualizer-specific material path, never the already accepted card surfaces.
  Material children/Context Menu keep their independent border semantics.
- [ ] **One-time cumulative material/UI/Steam audit (19 Nov):** use `Docs/Temporary_Material_Surface_Audit_2026-11-19.md` to audit the full handoff, run its focused and Qt/performance tests, fix confirmed issues in their existing owners, record outcomes, then delete the temporary document and remove this checklist line. Do not advance native-core scope for the audit.
- [ ] Preserve older themes and settings via neutral defaults.
- [ ] **Shader bake and binary admission (BLOCKING):** use the project's pinned `PySide6` toolchain to regenerate
  `surface_material.frag.qsb` from its changed GLSL source for the full shipped QRhi target matrix, and run
  `tools/regen_qrc.py --shaders --check`; test the generated pack on Windows Vulkan and OpenGL before shipping.
  Source-only shader changes paired with stale compiled `.qsb` files must not be treated as a working material-border release.
- [ ] **Disabled/compatibility proof:** Normal border and zero-width border must keep pixel-identical legacy
  outlines on both Normal and material card fills. Test Theme inheritance, explicit override while the parent
  card is Normal, older saved settings, switch on/off, opacity reset, backdrop first-frame fallback, missing
  backdrop and hot-switch failure modes; verify no leaks/scene-graph churn after multiple Settings edits.
- [ ] **Shader and visual proof:** confirm ring/face order and rounded-corner coverage at 1, 1.5, 2, 3 and 5 px
  across DPR 100/125/150/200%, Glass/Acrylic/Frosted/Mica/Smoked, light/dark themes, bright/dark wallpapers,
  shared-backdrop updates and transitions, multiple displays and scale-aware CUSTOM layouts. Confirm the border
  never inherits the card's legibility guard, and no flat outline overpaints active material borders.
- [ ] **Incremental cost and dormancy proof:** benchmark *border OFF vs border ON* with accepted card materials
  unchanged, single and crowded ordinary widgets, overlapping material headers/controls, and on both Vulkan and
  OpenGL where available. Capture per-pass GPU median/p90, frame p90/p99, 90 Hz missed cadence, CPU, resource and
  material node counts, GPU-memory delta and shared-backdrop dormancy. Regressions must be measured and resolved
  before marking complete; this cosmetic task must not displace native-core priorities.

### 1.8 Gmail and Reddit/Reddit2 column gestures

- [~] D1 run (1B.14 harness), gestures posted by messages: top grips reorder.
- [~] Same run: solid-span endpoints change start/width and truncation.

### 1.9 Settings native corner clipping (next step is 1B.9: the operator's +2 px border allowance)

Reproducer: `tools/settings_native_corners.py`; evidence and the rejected candidates (Qt and post-Accent regions, an
inset native-child blur): `Docs/Architecture/Settings_Theme_Architecture.md`. No candidate code ships.

- [ ] Find a composition treatment that actually clips Accent material at the rounded silhouette: a viable rounded
  composition host, with input, resize/DPI, activation and lifetime proof (material transparency alone cannot
  close it).
  - [ ] First candidate, if the operator still sees escape (from 1B.9): the Windows 11 DWM corner preference on a
    non-layered variant (Microsoft's guidance excludes layered windows and windows with a region from system
    rounding; cost check: shadow ownership, translucency, the layered-window repaint path of section 9's freeze
    fix), then a composition-host clip. Whichever clips needs input, resize, snap and maximise, DPI change,
    activation and Studio-over-Settings modality proven on the real `SettingsDialog` and Studio window.
- [ ] Keep it a separate reversible fix.
- [ ] Repeat the four-case corner/border/shadow gate before claiming improvement.

## 2. Awaiting the operator (decisions only; details stay at the item)

One line each; the detail and evidence live in the section named. Nothing here holds a phase open, and nothing here
is an operator look: looks, listens and feels are the lead's proofs (1B.14), and what has no simple test is a
Watchlist entry (operator, 11 Nov).

- [~] **Framed aperture on the saver card (8 Nov, decision):** the writer is fixed (R-181: the Visualizer's uniform-scale
  minimum is absolute, and settings load lifts stored cards to it). That alone does not restore the saver card's 45°
  look: the repaired 592x592 card holds a 1480x1480 world (0.4 px per world unit, aperture 5.29), still at the 90° x
  90° cap and visually the same as before (`.artifacts/evidence/architecture/framed_camera/20261108_scale_repair/`).
  45° on that card needs about 2.11 px per world unit (a 280-unit world). Decide: bound the framed aperture (or the
  vertical view) as well, or leave it to Edit (Restore Size, wheel up, side drag back to the wanted width).
- [~] **§1 8b P2:** decide whether to size the frame-age gain with a matched-GPU repeat game60 pair; gates 3/4 and their
  measurement limits are in the design record. The Windows default and H1/H2 repairs are already integrated.
- [~] **Decision, Waveform Preset 4 (the reference):** sign off the fixed-scale v7 trade-offs against main and the
  "floor first" lift (`TROUGH_LIFT_MAX` 1.5 -> 3: Preset 4's ribbon rides about .7 higher at p90 and stops dipping
  into the floor, operator: "rather it goes a bit higher when it has to than clips"), or ask for the tag's exact
  Preset 4 dynamics (numbers at 7.1, "Fixed-scale rework v7"; the lead accepted them on 6 Nov).
- [~] **Decision, Waveform on a small 640x560 card:** Presets 5 and 6 cannot fit it either way: crests now graze the top
  on 14-47% of frames, against floor contact before (an authoring choice; no reaction was shrunk). Sign off, or ask
  for taller-body authoring.
- [~] **Decision, expanded card's hover Edit lane (plan 01 M3c):** the lane (Restore Widget Size, the transfer arrows)
  stays withdrawn on the display-wide card outside Edit since M2, because each edits the ordinary card's layout,
  which that view does not draw (since 1D.7 its Rotate glyph turns the expanded card outside Edit and saves at
  once). Return it, and what should each do while expanded?
- [~] **Decision, overlays on pause:** a pause does nothing to them (by the spec, not built): Now Playing is event-only
  and has already faded after its window; with Always Show it stays up by definition. Add a fade-out on pause?
- [~] **Decision, Audio Analysis group in the Spline Curve and Oscilloscope Studios (section 9):** keep it or hide it?
  Every offered control moves the frame (Spline Curve's; Oscilloscope's Flare and Drive, and Tone for Bar Count, Block
  Size and Input Gain), though the Oscilloscope's trace itself is the raw capture.
- [~] **Decision, Studio clip loops (section 9):** the clips now start and end mid-song at the chosen loop points (Human
  and Growing Pains on their groove) for a seamless wrap, not at the earlier quiet-to-hot windows. Keep the seam, or
  restore the quiet-to-hot arc?

## 3. Lead and agents: active, paused and queued work

**Agents and slots:** `Docs/Guides/Orchestrator_Handbook.md` section 1 is the one source (roster, models, audits). The
plan holds every task in detail before dispatch: a brief is its plan item, and a report is checked against the item's
boxes (operator, 11 Nov evening). Closing before opening (operator, 12 Nov): a slot takes no new work while its last
report is unreviewed or unmerged, and a dispatch is sized to finish inside a usage window. The native core's state and
tracks are in item 8b ("Order").

Live checklist: every open step is its own box; landed boxes are deleted at merge; keep `[~]`
validation steps and open side defects. Landed slices live in `Docs/Reference/Architecture_Checklist.md` (AC-01 to
AC-12, A-xx audit ids), `Docs/Audits/Settings_SSOT_Audit_2026-11-07.md` (AC-17 to AC-23), `Docs/Reference/Benchmarks.md`
("Recorded sessions") and the Historical Bugs records.

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
- [ ] **Side findings of the Waveform second tick cut (7 Nov, not fixed there):**
  - [ ] `capture_visualizer_logical_frame` refreezes the common style (`freeze_render_fields(_common_style(widget))`,
    logical_frame_capture.py) on every tick of every mode, ~0.02-0.04 ms; a FrozenFieldsMemo would remove it.
  - [ ] The logical-tick capture reads every Waveform control (~150 getattr) and compares the whole configuration
    dict every tick (~0.07 ms together); a settings-change token would make the no-change tick free.
  - [~] overhead_baseline on main 4467759c counted gl 182 / py 7010 per Waveform preview frame against the
    81959727 baseline's 180 / 6987. The 11 Nov attribution (382ae139) found and fixed per-frame Python-call rises
    and re-recorded the baseline: the lead confirms the two GL calls are accounted for, then deletes this box.
  - [ ] 11 of the 19 recordings in `logs/visualizer_recordings` lack native capture history, so the Waveform tick
    (PCM reanalysis) cannot replay them; identity proofs cover the other 8.
  - [ ] The Studio's step-state copy refuses NumPy dtype objects ("uncopyable Float64DType"); a dtype-keyed cache in
    a logical owner fails every Waveform Studio. Caught by `tests/test_waveform_studio_evaluator.py` and avoided in
    the cut (keyed by `dtype.str`); worth a line in the Studio's step-state contract.

**Active or paused:**

- [ ] Repair the shared Achievement Pulse mock field IDs (`build_mock_steam_view_model`): it emits rarity/session,
  while the card accepts total/latest/playtime/previous/source/selected. Existing fixtures can test impossible rows.
- [ ] Isolate active Widget Theme state between scene/display tests: the combined 33-file run fails four tests that
  pass alone (Achievement Pulse config, Gmail actions, Media projection and baseline theme material).
- [~] **D1 run (1B.14 harness), lead review of grabbed frames:** live Style Overrides/theme changes must reach
  Visualizer and Context Menu material in the current display generation (`_configure_quick_auxiliary`), including
  the new global opacity override.
- [ ] Extend actual faint-run pixel checks to light widget themes beyond the sampled Gmail/Media cards. Keep
  authoring-mirror failures separate from runtime material guards; contract:
  `Docs/Architecture/Card_Surface_Materials.md`.
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
- [~] Lead review of a rendered expanded-card frame (hidden host, then D1 grab): the expanded card shows the theme's
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
  modes): whether that is acceptable. (For a surface that overlaps the Visualizer the native answer is decision
  D7 point 7, item 8b N5.9; the card's own material keeps the wallpaper.)
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

## 4. Runtime side requests (operator, 5 Nov; run alongside the order above)

Live checklist: every open step is its own box; landed boxes are deleted at merge; keep `[~]`
validation steps and open side defects.

**Slow startup (operator, 6 Nov 10:30; owners fixed, awaiting the lead's cold start)**

The held-lock rule is in `Docs/Guardrails/Performance_Optimization_Contract.md` section 5, the optional-worker start
in its appendix.

- [~] D1 run (1B.14 harness): cold start with `--usage`, then the lead reads the log:
  - [ ] No `UI_CALLBACK` / `FEED_GUI_DELIVERY` line exceeds a frame (the 166-240 ms lines of 6 Nov were not
    reproduced offline: 0.1-15 ms per source; treated as post-block backlog on a 97-100% CPU machine).
  - [ ] The first `collect_ms` is small.
- [ ] Side defect: a prefetch batch asked for before the optional image_prefetch child is ready fails as "not
  running" (a logged `[PREFETCH]` error); that batch is not retried.

**Spline Curve (`devcurve`) "more alive while keeping the flow" (second cut 6 Nov; awaiting lead review)**

Contract: guide section 13D -> DevCurve. Evidence: `.artifacts/evidence/visualizers/devcurve/reactivity/20261105_reactivity/`.

- [~] Lead review on the rendered before/after WebPs (loud end and a quiet passage, P1/P6): the second cut reads
  more alive while keeping the flow.
- [ ] Open: the strongest preset's bass stays ~18% below pre-work main's loud RMS (a smooth wave cannot
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
  so the wait share is a number (a no-load P4 run measured a 7.49 ms tick median; about 6 ms of each live tick is
  likely spent waiting for the GIL held by the render/GUI threads). Switch-interval tuning stays banned by the
  Performance Optimization Contract.
- [ ] Cut what the profile names, with byte-identical output (Preset 4 bit-exact with tag
  `waveform-baseline-2026-11-05`).
- The game60 re-measure of the two tick cuts is superseded on the default path: the tick runs in the engine
  worker (P2), and the 11 Nov load session measured it there (item 7). The boxes above matter for
  `--viz-in-process` only; the lead decides whether they still pay.

**Widget/Settings material appearance: Awaiting Validation**

Active work: section 1A, items 1.7/1.9. Owners: `Docs/Architecture/Card_Surface_Materials.md`,
`Docs/Architecture/Settings_Theme_Architecture.md`.

- [~] D1 run (1B.14 harness), lead review of grabbed frames, in the running app:
  - [ ] The inner rim.
  - [ ] Transport, mute and volume.
  - [ ] Dark and light palettes.
  - [ ] Linked material choice.

**Widget theme legibility (open)**

- [ ] Theme the Weather detail asset icons: they remain white and become faint on pale cards.

**Extruded Bubble: a deep red ocean preset that truly matches the mock (operator 6 Nov, not urgent)**

The mock is `Docs/Reference/Extruded_Bubble/Targets/Originals/Preset7Goal.png`. One preset only; the shared
controls (Ember Grain, Ember Band, Lit Glass, Stream Lanes, Wake Tint) are each dormant at 0, so no other look
changes. Details: `Docs/Reference/Extruded_Bubble/Investigation.md` sections 72-73.

- [~] Lead review of side-by-side sheets (mock | ours, full resolution plus crops) of Preset 9 against the mock.
- [ ] Shells are paler and smoother inside than the mock's copper, busy-interior glass, and too many crowd together.
- [ ] Embers are partly along-stream strokes rather than torn debris.
- [ ] The lower right is far too busy (the mock's band fades out there).
- [ ] The shaft corner lacks its bright glittering core.
- [ ] Faint surface ripples at the top.
- [ ] Side defect: the near (defocus) layer stair-steps the rim of a large near shell on some frames (seen with Lit
  Glass off as well).
- [ ] Side defect: `tools/release_media.py` cannot render Waveform Ribbon showcases: the replay raises "Raw musical
  replay requires current PCM reanalysis" because `replay_clip` never drives
  `tools/visualizer_replay/pcm_reanalysis.py`.

## 5. Watchlist (observe during normal use; reopen only on evidence)

Live checklist: every box is an observation or a fix owed on evidence; delete an item when its evidence closes it.

**Engine worker and platform (reopen only on evidence; no simple test exists)**

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
- Parity gates judge single-sampled targets and report product sampling beside the path's own repeat; the noise
  is attributed only as far as "the mode's own passes" (11 Nov attribution).

**Display Settings capacity (physical hotplug)**

- [ ] On a real monitor disconnect/return or explicit reauthoring, Settings' current-screen rows and
  selections/bindings stay coherent.

**R38 hover display-transfer glyphs (physical topology)**

- [ ] Watch glyph hit/tooltip/fade and transfer on unequal-DPI screens and monitor unplug/return (equal-DPR pair
  passes).

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

31 Oct MC run: a 95-121 ms freeze of the GUI, render and logical threads at every `--usage` sample, because the
sampled tree held 7 processes / 233 threads (normal 3 / ~55); the four extra descendants used the GPU and are
unidentified. The next MC run and an invisible live check were normal.

- [ ] On recurrence read the sampler's `[USAGE] topology added ... name= parent= threads=` lines (one per process
  entering the tree), identify the extra processes, then decide whether the sampler must exclude/outsource them.
- [ ] Seen again 8 Nov with a normal tree (design doc step 6 "Gate 3 record"): every sample stalled the render
  thread 71-106 ms; `collect_ms` ~13 ms per process walked at 87% system CPU (23 ms for 4 on an idle machine).
  Main-side on both paths; the engine worker adds one process to the walk.

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

`Docs/Guides/GitHub_Remote_Build.md`. Installing a remote-built product on an ordinary user account is the
"Installed builds" entry below; the frozen run of 1B.14 covers the artifact.

- [ ] Retire superseded native run43937313108 (`e15efeda1`, token20261116_211445_549725) when GitHub permits:
  REST reports queued/no jobs, while cancellation returns409 "not been queued yet" and token discovery cannot
  identify it. No local publisher is running. Do not redispatch that token or publish its older artifact over the
  validated c53e3fe27 module. This service-state cleanup is non-blocking.
- [ ] Since checkpoint audit 11 (8 Nov) the tab's Linux job runs beside the Windows runs on its own process owner
  (never holding their retrieval) and a stop cancels its run even before it was followed; tested with fakes only, so
  the next Remote run with Linux selected is its first real one: read its log and fix what it shows.

**Bubble / Extruded Bubble "terrible performance" reports (6 Nov log 10:32-10:35; moved from section 2)**

That log was our load (97-100% system CPU from game60 checks), not the product: on the quiet machine Bubble P1 ran
65.9 fps (tick 1.47 ms, GIL 0.13) and Extruded Bubble 45-69 fps. Heavy load runs are the lead's only.

- [ ] On a new report, read the log's system CPU first: a load-driven reading is not a product defect; otherwise
  reproduce on the quiet machine against those numbers.

**Displays off -> presentation pauses entirely, resumes clean (built 5 Nov; needs the machine's own screen timeout)**

Contract: `Docs/Architecture/Compositor_Architecture.md` -> Display power.

- [ ] When a heavy preset (Waveform Ribbon (`waveform_ribbon`) Preset 1 or Neon Lake (`shockwave_grid`)) is left
  overnight and Windows' screen timeout turns both displays off (not the panels' own buttons: an HDMI panel that
  stays enumerated gives no signal and the TV rejects DDC/CI queries; operator decision 6 Nov: no Screens Off
  command, the burden stays off the user; they enabled the power plan's display timeout), notice the saver's CPU/GPU
  in Task Manager while dark, whether wake input reaches the saver, and the first seconds after wake (a stale frame,
  a jump or a hitch). Run with `--frame-trace --usage`; when something shows, read that trace and reopen here.

**Load runs the 11 Nov session did not cover (reopen only on evidence)**

- [ ] The 600 s Waveform Preset 4 and Bubble GC runs with `--frame-trace` (gen1/gen2 pauses per hour) and a long
  run with several Settings round trips: one 85 s run with one round trip was clean (re-frozen, no barrier
  timeout); nothing has shown a steady collection since the GC freeze merged.
- [ ] The two-monitor canonical game60 outlier (48.6 fps once, 7 Nov, never repeated).
- The Waveform tick-cut A/B under load is superseded on the default path (the tick runs in the engine worker);
  it matters for `--viz-in-process` only.

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

## 6. Shared 3D architecture: now inside section 1, item 8b

Kept as the target of the documents that cite "Current_Plan §6". The shared 3D primitives (S3D-1 to S3D-7) are
stages N3, N4 and N6 of item 8b, where the old ids are mapped; there is nothing else here.

## 7. Visualizer modes (backlog; when admitted, one at a time in this order)

### 7.0 Method: lab first, then production

Extruded Bubble's lab (`tools/labs/extruded_bubble_lab.py`) reached the mocks long before production did; production
then closed the gap by measuring against both. Do the same for every new mode:

- [ ] **Target first:** the mock/concept package and its low/high pair; write the mode's contract and hard gates (from
  its brief) into its focused doc before code.
- [ ] **Lab:** `tools/labs/<mode>_lab.py` composes the target scene by hand, offscreen, from the shared primitives,
  with free knobs and no Settings/preset plumbing. From the native core on, a lab composes from the core's
  harness primitives (item 8b): no new Python OpenGL scene code.
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

- [~] Lead review on the music-vs-response traces (`waveform_music_response.py`; chain7, every preset and Reaction
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
Evidence `reactivity_preset7/20261107_reactivity_preset7/`.

- [~] Lead review on a rendered showcase WebP and the music-response trace of Preset 7 (bodies are smaller in loud
  passages now that the uniform inflation is gone: sustained-loud visible amplitude 6.4 -> 5.4).
- [~] Lead review on rendered Whole Swell (Preset 6) strips: it sits at its soft bound in all music by design (one
  global level; de-saturating it barely changed the visible body, so it was left).

**Breathing + anchored history ends (merged; awaiting the lead's review)**

Evidence `.artifacts/evidence/visualizers/waveform_ribbon/breathing/20261105_breathing/`.

- [~] Invisible run on recorded music and lead review of the animated WebP: soft passages let go between swells (0.7
  in every preset but 4) and a quieter passage after a loud one stays quieter.
- [~] Lead review on a rendered side-angle WebP: the tail no longer staggers at side angles.

**Four-ribbon maximum and Preset 3 (Awaiting Validation)**

The operator's maximum is four ribbons (it overrides the first board's decorative count label); Preset 3's paired
target uses four.

- [~] Lead review on mock | ours sheets (full resolution plus crops): validate Preset 3 against
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

- [~] Lead review on rendered strips and music-response traces: Travelling Pulse (default), Frozen Past, Whole Swell
  and Group Wave read right on recorded music (flow-rule and twitch tests exist for every mode).
- [ ] Group Wave still reads close to Travelling Pulse on rendered strips (it keeps the summed travelling field; its
  sets need their own pass), and its Pulse Width is not yet the band core the other two modes use (operator: "a
  relatively small horizontal width and the full vertical width").
- [ ] Pulse bands' colour edges read crisp at Pulse Falloff below ~1 on wide bands (Preset 5's vertical colour
  columns); judge on the operator's look whether the light's falloff should follow the geometry's broader envelope.

**Particles (5 Nov candidate)**

- [~] Lead review on rendered crops and a WebP: crest-weighted, distributed births in each ribbon's colour, visible
  >=1 px cores with soft halos, gentle fade; swells gather particles (Pulse Particles).
- [ ] Open: still sparser than the high-react reference (admission-limited).

**Strands: rare, 3-5 seconds TOTAL life**

The latest operator correction supersedes the proposed 30-second fade.

- [~] Lead review on a rendered strand WebP: preserve the approved non-flickering look and make appearances much
  rarer.
- [~] Same review: use most of a configurable 3-5 second lifetime for a gentle tip-first fade.
- [~] Same review: reactivation restores them smoothly, with glow and movement/growth (retain the approximate 20%
  repeat extension), without abrupt respawn or pulse reset.
- [ ] Prove quiet/peak lifetime handles, tip/root fade ordering, slow decay, partial-fade reactivation and
  direct/reflected appearance.
- [ ] Retain birth look during travel; finite history eviction must not cut off a visible unfinished fade.

**Colour, floor and mist (5 Nov candidates; awaiting the lead's review)**

Evidence `studio_20261105/floor4/`; measurements in Migration Plan section 8.

- [~] Lead review on rendered sheets: lattice sheets (V3).
- [~] Lead review on rendered strips: wet concrete with stable soft coloured reflection mass (no horizon line, no
  flicker-prone streaks; operator prefers smeared colour to streaks).
- [~] Lead review on rendered sheets: one bounded night medium with a slight local ribbon tint (strong Local Light
  can no longer wash the frame).
- [ ] Wide sheets (P2) still graze the floor on ~60% of ticks: optional Floor Give (below) lets the wet floor dent
  under them instead.

**Fixed response, break-proof Breathing, Kick Accent (operator, 6 Nov: "when it went suddenly quiet everything become
more reactive ... Adaptive is a very problematic approach"; "many sustained kicks ignored"; awaiting the lead's review)**

Geometry drives are a fixed function of the real-music scale (the Adaptive Response toggle is retired). Preset 4
differs from the tag only through it, Kick Accent and the floor lift: compare against the tag with Kick Accent 0.
Range audit: `.artifacts/evidence/visualizers/waveform_ribbon/reactivity_preset7/20261107_reactivity_preset7/rangeaudit_*.txt`.

- [~] Invisible run on recorded music and lead review of the music-response traces: the fixed response, Breathing
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

Evidence `.artifacts/evidence/visualizers/waveform_ribbon/floor_deform/20261107_floor_deform/`; design in the
Migration Plan's Floor bucket.

- [~] Lead review on rendered stills and a WebP: where a lower edge comes down onto the floor the wet floor yields in
  a soft dent, so troughs stay round and dip in instead of flattening: in the visible frame P2 reaches the floor
  only in the ragdoll loud end (about 49.5-52 s); P3 never does, so it is unchanged there.

**Pulse Rim (operator, 5 Nov: "where the pulse is that section of the ribbon's rim can be even brighter with
falloff"; awaiting the lead's review)**

Evidence `.artifacts/evidence/visualizers/waveform_ribbon/pulse_rim/20261107_pulse_rim/`; design in the Migration
Plan's Reaction bucket.

- [~] Lead review on rendered strips: the rims (line and rim glow) brighten on the pulse with the field's own smooth
  falloff, in every Reaction Mode and both Travel Directions.

**Swells reach the Preset camera already faded (Presets 1-3; awaiting the lead's review)**

Evidence `reactivity_preset7/20261107_reactivity_preset7/` (`visibility_tag_vs_final.txt`, `kicks4_table.txt`,
`sheets/*_p1..3_*`); design in the Migration Plan.

- [~] Lead review on the rendered sheets of Presets 1-3: edge swells arrive in view at strength.
- [ ] Open: on Presets 1/3 the rim's swell-to-elsewhere contrast (1.11/1.17) is still below Preset 4's (1.27).
- [ ] Open: the no-twitch probe's .02/.01 bounds only held because its swells never reached the cloth (in-view
  .028/.012).

**Travel Direction (operator, 5 Nov: "Travel Direction ... chosen in the studio ... an important basic need";
awaiting the lead's review)**

Evidence `.artifacts/evidence/visualizers/waveform_ribbon/travel_direction/20261107_travel_direction/`; design in the
Migration Plan's Flow bucket.

- [~] Lead review on a rendered WebP of a live change: it fades out, swaps while hidden and fades back (0.6 s each
  way).
- [~] Lead review on rendered strips: Left To Right mirrors history, pulses, held swells, Tilt Shift, sparks,
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

- [~] Lead review on rendered frames (D1 run, 1B.14 harness, for native pixels): the floor now intersects the same
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

- [~] Lead review on rendered sheets: the darker bounded haze with capped local tint.
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

**Chosen first: the smallest contained scene and the first consumer of S3D-1/S3D-5** (it uses no population, S3D-2)

Brief and hard gates: `Docs/Future_Work/Waveform_Ribbon.md`. The detailed working checklist and visual target custody
live in `Docs/Reference/Waveform_Ribbon_Lab_Plan.md`; reference packages under `references/` are local/operator-owned
and intentionally absent from ordinary source handoffs. The scene is world-first through the shared framed Perspective camera:
wet reflective concrete floor, waveform and full-scene night fog, with no visible horizon/sky/floor edge; the waveform
clears and softly lights the mist.

- [ ] Preset/control migration and recorded-audio calibration come only after the lab look is credible.

**WR-07/08 production candidate: finish admission**

Reaction design: Migration Plan "Current reaction model".

- [~] Lead review on rendered strips and a WebP: preserve constant history flow, no time-varying axial scaling,
  smooth curves, particles/free strands and fog clearance by the actual body.

**Full controls/editors, four-ribbon capacity and three presets: finish admission**

- [~] Lead review of rendered Studio frames: expose bend/torsion/stretch/twist/rotation and accent ranges,
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

## 8. Accepted Bubble: open reviews and side defect

- [ ] Side defect (agent aac773583ad93e2ab, 21 Nov, under the operator's game plus agents' runs, 77-96 % CPU): the
  live check's engine worker timed out on its first configure and the saver fell back to in-process. In the same
  conditions an OpenGL control drew 12 fps. Reproduce under a measured CPU load, then find the worker's configure
  deadline and why the in-process fallback runs so slowly. A slow but loaded machine must degrade gracefully, never
  fall to 12 fps.

- [ ] Side defect (lead, 20 Nov live control): Python OpenGL Bubble on Display 1 shows 1.44 hitches a minute (steady
  frames over 50 ms; `tools/frame_trace_cadence.py`: 6 gui_starved stalls, the worst a 88.5 ms swap-to-frame-begin
  gap with an 84.4 ms GUI wake gap). Native Vulkan Bubble's logical side shows the same worker gaps (10 over 16 ms,
  max 145.7 ms). Root cause first: attribute the GUI starvation and the worker's logical gaps (GIL-holding C calls,
  GC generation 2 at 36 ms, the usage sampler) on both paths, before any fix. Evidence:
  `.artifacts/evidence/visualizers/bubble/live_check/20261120_bubble_*`.

The operator accepted Bubble's drift, motion, ambient, direction and occlusion rules
(`Docs/Guardrails/Bubble_Temporal_Fidelity.md` section 23); do not reopen them. Bubble's performance work is the
native "Bubble GPU optimisation" box in item 8b (section 1's Order, step 3); the earlier Python-side gate here is
superseded, because the Python renderer is deleted at N5.2h.

**R-170 lead review**

Evidence: `Docs/Historical_Bugs/R-170_Bubble_Shape_Dependent_Speed_And_Aspect_Modifiers.md`.

- [~] Lead review on rendered WebPs at each card size: Bubble on a tall card, a wide card and the TV card moves and
  sizes like the canonical card, and is denser on large cards.

**Side defect (found during R-170, not fixed)**

- [ ] `_apply_bubble_collision_response` smooth mode multiplies `max_disp *= 0.72` inside the per-bubble loop, so the
  in-view correction cap compounds down the list (order-dependent). Fixing it changes canonical Bubble output, so it
  needs an explicit BTF behaviour-change decision first.

**Particle glow (merged; awaiting the lead's review)**

- [~] Lead review on the `before/` vs `after/` 4x crops and flicker strips of
  `.artifacts/evidence/visualizers/bubble/particle_glow/20261107_particle_glow/`: hot core, monotonic halo (no dark
  moat), no twinkle on drifting sub-pixel cores.

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
  - [~] Lead review of the rendered Settings pages (the real SettingsDialog, off-screen), one sentence per mode:
    every mode's Settings body is now the preset row and the Studio launcher (operator 6 Nov: migrate fully once
    parity+ is proven; `tests/test_visualizer_studio_parity.py`).

**Spline Curve Studio built (6 Nov), awaiting the lead's acceptance review**

`ui/studio/devcurve_adapter.py`, registered; Spline Curve's preset row shows Open Studio and no Edit Preset. Evidence
`.artifacts/evidence/visualizers/devcurve/studio/20261107_studio/` (two presets, on Rag Doll and on Human: every
workspace with the live traces, plus the node rows).

- [~] Lead review on the rendered Studio frames: the per-layer Body / Accent / Swell traces as the way to read the
  reworked reactivity.
- [~] Lead review on the rendered Studio frames: the Layers workspace (one panel per layer).

Whether the Audio Analysis group earns its place is a decision in section 2: it is re-analysed from PCM through the
production DSP, every offered control moves Spline Curve's frame; AGC Strength and Output Lift read nothing and are
now hidden (`Docs/Reference/Visualizer_Reference.md` -> Audio Analysis controls per mode).

**Oscilloscope Studio built (6 Nov), awaiting the lead's acceptance review**

`ui/studio/oscilloscope_adapter.py`, registered. Evidence `.artifacts/evidence/oscilloscope/studio/` (two presets, on
Human and on Rag Doll: every workspace with the live traces). Recorded engine answers with the
capture history recorded by identity (binary sidecar; `Docs/Reference/Visualizer_Studio.md` section 3).

- [~] Lead review on the rendered Studio frames: Level / Afterglow / Ghosts / Flare / Drive / Tone as the way to
  read the beam.
- [~] Lead review on the rendered Studio frames: the three workspaces.

Whether the Audio Analysis group earns its place is a decision in section 2: it is re-analysed from PCM through the
production DSP, every offered control moves Flare and Drive, and Bar Count, Block Size and Input Gain also move Tone
(the trace itself is the raw capture, but the beam's reactions are not; `Docs/Reference/Visualizer_Reference.md` ->
Audio Analysis controls per mode).

**Edit Preset deleted (6 Nov)**

Contract: `Docs/Reference/Visualizer_Studio.md` section 4 (Open Studio and the confirmed Save To <Preset>).

- [~] Lead review on a render of the real SettingsDialog (off-screen): Open Studio's place in the preset row.
- [~] Lead review on a render of the real SettingsDialog with its popup patched: the Save To flow.

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
  - [~] Review a rendered loop WebP of each of the three clips across the wrap (end of the 13 s timeline): the
    preview should not jump, empty, or re-start its motion.
  - [ ] Rag Doll has no steady beat, so its seam is the least certain: judge it first.
  - [ ] The clips now start and end mid-song at the loop points chosen (Human and Growing Pains on their groove), not
    at the earlier quiet-to-hot windows. Whether the quiet-to-hot arc matters more than the seam is a decision in
    section 2.

**Studio chrome: Awaiting Validation**

Active material work is section 1A, item 1.7; rounded native corners remain open at item 1.9. Contract:
`Docs/Reference/Visualizer_Studio.md` (Chrome and theme). Off-screen Studio evidence cannot establish native DWM
composition; preview-overlay backing stays cheap and scene colours stay independent of chrome.

- [~] Studio run on D1 (1B.14 harness), lead review of grabbed frames: the shared semantic material on panels,
  workspace tabs, section headers, tools and instrument wells.
- [~] Same run, driven by messages: native snap/resize/maximise.
- [~] Same run on a light theme: light-theme shadows.

**Studio drag lag fixed (6 Nov), awaiting the lead's drag check**

Contract: `Docs/Reference/Visualizer_Studio.md` "Drags are batched" (per move 56 ms -> 0.07 ms on Waveform).

- [~] Studio run on D1 (1B.14 harness), drags posted by messages with `tools/studio_drag_profile.py`: the feel of
  drags (per move on the 0.07 ms scale of the evidence above).

**UI frozen after closing a Studio, recovered by itself (operator 6 Nov 21:56, Extruded Bubble, Wine Ice Acrylic):
owner found in source, awaiting a field log**

Not reproducible offscreen. The incident, its cause and the 7 Nov remedy are in `Docs/Reference/Visualizer_Studio.md`
section 4 ("Repaint at the reveal").

- [ ] Open until a field log shows a paint right after the reveal and `first Paint after the first input` within a
  frame or two (the `[STUDIO] after reveal` lines, `presence.RevealWatch`, one-shot, removed at the first input to
  Settings, name which window Windows sent the clicks to and the state at each step; "repaint since reveal: none" is
  the takes-input-but-never-repaints signature).
- [ ] Acceptance needs the operator's field log plus a fix proven on the real SettingsDialog path, never a stand-in
  only. If the lines show another owner, fix that owner from them.

**Camera reset on every edit and the exit double flicker fixed (operator 8 Nov), awaiting the lead's D1 run**

Contract: `Docs/Reference/Visualizer_Studio.md` section 4 ("One transition out" and the camera round trip).

- [~] Studio run on D1 (1B.14 harness), lead review of grabbed frames: orbit, then drag sliders (the view stays).
- [~] Same run: close the Studio by every path (one clean change to Settings, no swap).

**Per-session memory growth in the Studio (side defect, 6 Nov; the clip caches ruled out 7 Nov)**

Process memory grows about 1-3 MB per offscreen Extruded Bubble session after an ~85 MB warm-up over the first 4
sessions, but the series swings by +-70 MB run to run (main and branch alike); tracemalloc sees only ~55 kB of Python
growth per session, and the clip caches are ruled out and bounded. What grows is native (Qt Quick / GL driver heaps).

- [ ] A native heap comparison (UMDH or VMMap) across 30 sessions; bar: a trend, not run-to-run noise, before any
  fix.

**Slider drags no longer let go mid-motion (operator 6 Nov), awaiting the lead's drag check**

Contract: `Docs/Reference/Visualizer_Studio.md` "Drags are batched"; guard `tests/test_studio_drag_coalescing.py`.

- [~] Studio run on D1 (1B.14 harness), a drag with a vertical wobble posted by messages: a slider drag holds
  through a wobble on every mode.

**No automatic switch to Custom (operator 6 Nov), awaiting the lead's review**

Spec: `Docs/Reference/Visualizer_Studio.md` section 4 "Canonical save"; tests
`tests/test_studio_preset_row_and_save_to_preset.py`.

- [~] Lead review of a grabbed frame (D1 run, 1B.14 harness): the prompt's wording and buttons over a real Studio.

**Neon Lake: drag the Sun/Moon in the Studio preview**

- [ ] Retiring the Settings terrain section (6 Nov, Studio brush) removed its 3/4 view, where the Sun/Moon could be
  dragged; it is now placed with Position X/Y/Z only. Give the Studio preview a direct drag for it: the same pick
  through the production camera as the terrain brush, one undoable commit on release.

**Lead review: the Studio terrain brush**

Brush button or B in the viewport toolbar; Raise, Lower, Flatten, Water; left-drag paints, right/middle drag pans.
Evidence `.artifacts/evidence/studio/completion/20261106_completion/brush/`.

- [~] Studio run on D1 (1B.14 harness), strokes posted by messages, lead review of grabbed frames: the terrain brush
  in the Studio.

## Backlog (parked text moved out of section 1 on 21 Nov; agents are not briefed on this section; the lead promotes an item back by plan box)

### Bubble conditional optimisation gate (moved verbatim from N5.1 Bubble; the plan box keeps a pointer)

  - [ ] **N5.1 Bubble conditional optimisation gate (operator, 16 Nov; AFTER accepted native OpenGL/Vulkan parity
    and the per-pass cost check above, BEFORE N5.4 and NF):** recorded music now allows controlled, bounded
    performance-only optimisation without assuming that Bubble's calculations are the cause of any observed GPU
    utilisation. First name the measured Bubble-owned GPU pass, CPU/GIL, transfer or allocation problem and its
    baseline; if nothing significant is attributable to Bubble, record a no-change result and close the gate.
    Do NOT speculatively optimise the old Python/OpenGL renderer being retired, retune motion or response, or
    rewrite the 110-body shader on theoretical complexity alone. The relevant owner is the accepted native path,
    or the surviving Python logical simulation where that owner is independently shown to be costly.
    - [ ] **Baseline before editing:** freeze two *fully resolved* independent settings cases from the accepted
      curated **Preset 1 (Deep Sea Abyss)** and **Preset 2 (Going Down)**. Keep the existing
      `tests/fixtures/visualizer_frozen_settings/bubble.json` and its consumers intact; it has Preset 1-like
      values but must be checked against the entire current resolved profile before being called exact.
      Create an immutable versioned Preset 2 fixture, with SHA-256 for both frozen files and resolved models.
      Preserve the pre-change acceptance and commit/fixture provenance. Never resolve from the mutable Studio
      state on each run or regenerate baselines from the candidate implementation.
    - [ ] **Music/event matrix:** normally replay ALL FOUR existing ~60-second schema-2 operator takes with PCM
      histories, typed events and onsets: `nightsolong_acousticsoft1`,
      `ragdoll_quiet_intro_loud_end1`, `human_heavy1`, `anything_mixed2`, under EACH frozen preset
      (eight full replay cases, approximately 43,200 ticks at 90 Hz). THREE full, distinct recordings
      are the absolute minimum only if one is unavailable and the lead explicitly accepts a documented
      reason. Validate file SHA-256, actual span and event/onset completeness rather than assuming a filename
      proves 60 seconds. Do not use a short excerpt, older schema-1 clip or synthetic input as a substitute.
      Extend existing `tools/visualizer_replay/bubble_parity.py` narrowly for two immutable profiles while
      retaining its four default clips, per-frame hashes, first difference, and negative controls.
      Use configured Bubble-band PCM reanalysis for an audio-analysis/input optimisation, not merely the
      recorder's Sphere-profile post-DSP bands.
    - [ ] **Exact logical fidelity:** pin seed/timebase/inputs/event consumption and compare the complete
      canonical bytes at EVERY frame: published logical frame, identity-preserving physics, reactive event
      consequences, Quick snapshot and renderer payload. Zero differing frames, timestamps, values or event
      order; even a float last-bit change rejects an output-preserving optimisation. A deliberately perturbed
      float and a late/missing one-shot event must fail the gate. Byte-parity is about computed results,
      not proof of on-monitor latency. If the change affects shaders/passes, also retain N5.1's approved
      Python/native OpenGL and Vulkan/OpenGL pixel oracles; same-device raw RGBA equality where repeatable,
      otherwise the existing D12 pixel bounds without silently widening tolerance.
    - [ ] **Independent speed and reactivity proof:** paired measurements of the named CPU/GIL owner or native
      GPU pass at 2560x1440 and 4K, ambience on/off, GPU median/p90, frame latency p95/p99, resource
      lifetime/dormancy, source/snapshot age, authored ~90 Hz cadence, event-to-visible attack, loud/quiet
      elasticity and motion/ghost/tail feel on the installed system (including mixed-display load).
      Retain the 240-frame ambience-off empty-pass control below. No slowdown, timing regression or
      fidelity alteration may be excused by matching offline hashes. Lead/operator acceptance or revert;
      one bounded candidate at a time, then return to the native migration ladder. BTF §24 binds.

### Oscilloscope parity and offers (moved from N5.1 Oscilloscope; operator 21 Nov: the mode is reworked after the flip, no 1:1 polish)

- [ ] Rule (a) for the Choice offers passes 14 of 15 runs; the one miss is nightsolong `oscilloscope_audio_block_size=0`
  input 1388 (two diagonally touching 2-level pixels in the beam's edge; the lead decides whether it is a class).
  Rule (b) over the three 60 s takes fails `VULKAN_RULE_B` on isolated edge pixels of 2-6 levels (shape A: saturated
  core or glow fringe, the composite's dither over float16 bloom; shape B: one pixel held for hundreds of frames,
  human_heavy1 a (370, 251) and nightsolong b (264, 208); a root cause of B is the open question); no bound is widened.
  Rule (b) for the offers is not run: the stream player's windows do not reproduce its continuous frames for the
  Oscilloscope (a window with warm-up 299 never converges; the player or publish-history state is suspect;
  `coverage_windows.WARMUP_INPUTS["oscilloscope"]` is 0, unproved). Repro: `native_stream_player.py --deliveries
  D:/Temp/Scratch/SRPSS/fast_proof/deliveries/oscilloscope_human_heavy1_a --apis opengl --windows <one window [300, 310],
  warmup_inputs 299> --against n5_1_oscilloscope/20261121_rule_b_60s_human_heavy1_a/native_stream_player.json`.
  Evidence: `n5_1_oscilloscope/20261121_owner_offers_<take>/`, `20261121_offer_windows/`,
  `20261121_rule_b_60s_<take>_<a|b>/` (`classify_rule_b.json`, crop sheets), `20261121_layer_p_summary/summary.json`,
  `20261121_warmup_probe_*`, `20261121_windows_against_full_human_heavy1_a/`. Figures per take are in those folders.

### Native core leftovers (moved verbatim from N2.2 to N5.7c; the plan keeps one verdict line each)

- [ ] N2.2 leftovers (proved; `native/core/python/host_check.py`; lifecycle facts J1 to J4 in
  `Native_Core_N06_N07_Qt_Facts.md`):
  - [ ] The hidden host's Qt Quick target keeps its contents between frames (defect B). A hidden host with
    transparent content must clear what Qt Quick does not cover; decide that when the first such host exists.
- [ ] N2.4 leftovers (proved; `native/core/python/composite_check.py`):
  - [ ] The Glass card material on the native composite; its contract read once Glass's own native path exists.
    When the card material moves to the core, its grain takes an integer hash exact on every backend (today 2 frosted
    pixels sit 12 levels apart on Vulkan where the float hash's `fract` wraps near 1.0; accepted 14 Nov).
- [ ] N2.5 leftovers (merged 14 Nov at ABI 8; the Python renderer retires only after N2.8 passes, in the switch
  change):
  - [ ] Studio on Vulkan: Spectrum's Studio preview is the Python renderer in an OpenGL node, so `has_studio` is
    OpenGL-only (`STUDIO_PREVIEW_BACKENDS`). A native Studio preview (the same native item in the Studio's scene)
    before the flip (NF) or before Vulkan becomes a default, whichever is first.
  - [ ] The two-block split (port rule (g)'s preferred shape): a settings block packed on change and a frame block
    per frame, removing the 980 to 995 Python calls a frame on the OpenGL path; OpenGL bit-identical at the
    widened run set. With audit M3: `spectrum_settings_values` and `QuickSpectrumRenderer.render` share one
    settings owner (today the guard compares one frozen setup).
  - [ ] Audit lows: L6 the native pipeline joins the gradual warm-up (`renderer_prepared` is True at once on the
    native route, `item.py:316-323`); L8 the destruction barrier sees the native objects.
  - [ ] Side defect (R-214's sibling, low): the activation deadline's fading-out phase has no slow-but-alive
    extension (cancels the switch after 6 s; only reached at about 270 ms a frame). Same rule as R-214 when the
    owner is next touched.
  - Surface format: RGBA8 (RGBA16F gave rule (a) no gain at twice the memory; quad alignment fixed it).
    `surface_format` stays a harness-only switch.
- [ ] N2.9 leftovers (generic mode content landed 14 Nov at ABI 10: a mode is a Python simulation, its product shader
  and its spec, with no build; README "How a new mode is built", decision D12):
  - [ ] Samplers are a primitive (N4.a): Bubble's `u_ambient_texture` (binding 0, the water-decoration underlay)
    and `u_ambient_light` (binding 1, the particles' linear light), both from Bubble's offscreen ambient render.
  - [ ] The Oscilloscope's port: its Quick renderer draws an instanced beam from a storage buffer with its own scene
    target and bloom, not `oscilloscope.frag`, so its N5 port needs those primitives (or returns to the 2D shader).
- [ ] N2.8 leftovers (the first rehearsal on Display 1 passed 14 Nov for Spectrum, rule (f); the Python renderer
  retires in the switch change):
  - [ ] With no admitted mode renderable on the backend (before N2.5), the Visualizer card shows as a thin empty
    purple frame beside Spotify. Find its owner and decide: a card with nothing to draw fades out, never sits as an
    empty frame. OpenGL unchanged.
- [ ] N3.8 leftovers (the async job service landed 14 Nov at ABI 14, D9 "As built (N3.8)"; OpenGL stays in-frame by
  design):
  - [ ] D8 row 3's gate (the contention measurement under a heavy Visualizer frame, the one limit of N0.7's proof,
    D9 point 2): p99 frame time and late frames across image changes with a Visualizer running, async against
    in-frame (Vulkan only; OpenGL runs in-frame).
  - [ ] D9 point 2, consumer (b), the warm-up class: warm-up jobs run on this service, scheduled with N3.6's
    gradual warm-up (one unit per spaced frame). Transition preparation (consumer (a)) is N5.2g's.
- [ ] N5.7b leftovers (the native backdrop pyramid landed 14 Nov at ABI 16, D7 "as built (N5.7b)"):
  - [ ] The slower-device fallback (D7 point 3's minimum build interval) is not built; Vulkan follows every layer frame.
  - [ ] D7 point 7 (glass over the live Visualizer) is not built.
- [ ] N5.2a leftovers (the seven transitions landed 14 Nov at ABI 15, each drawn on Vulkan from its own product
  fragment over the background layer):
  - [ ] The first frame's pipeline build cost when a run switches program, and the 4K cost (not measured).
  - [ ] Side defect (C++): the core refusing a still for "no card" draws black silently and `content_status`
    reports no failure, so the layer's fade-out on failure would not trigger; report it and fail closed.
- [ ] N5.7c leftovers (the D1 rehearsal on Vulkan, 15 Nov, covered wallpaper, cards on all five materials, Spectrum,
  live Settings changes, a transition and a clean exit):
  - [ ] Sleep and wake through Windows' console display state (`[DISPLAY_POWER]` off, then on). The operator's power
    cycle of the TV during the run raised no display-power event and rendering carried on; a real monitor sleep
    remains unexercised.
  - [ ] `[STARTUP_REVEAL]` still says "the vulkan backend has no background renderer, so no wallpaper frame is awaited
    (D10)". Since N5.7a, Vulkan draws the native wallpaper, so the reveal should wait for its first wallpaper frame as
    OpenGL does. Fix the reveal gate, or show that the first presented frame already holds the wallpaper.

### Test-failure triage (19 Nov; folded in from Docs/testfailures20261119.md, deleted)

Investigate on real Qt before changing anything; none is proof of a production defect or licence to retune visuals,
relax thresholds or wake the dormant native worker. The runner now balances 32 historical-duration batches, two
child processes, one GPU/Qt Quick lane; read the last `batch_NN.log` node name before blaming a test. A Windows
timeout dump (`.dmp`) can hold process memory: inspect before sharing. GPU scheduling is not a cross-worktree lock.

- [ ] `tests/test_settings_input_foreground.py`: both `test_input_roles_follow_current_semantics_across_live_theme_changes`
  cases fail; an explicit `control.input.text` colour does not reach `QPalette.Text` (a Qt stylesheet precedence issue is
  plausible; one QLineEdit has its own background-only stylesheet). Prove the displayed colour for QLineEdit, QSpinBox
  and QComboBox before touching shared theme code.
- [ ] `tests/test_visualizer_card_clip_contract.py`: `glass` cases fail at 1.0x and 1.25x (Spline Curve, Neon Lake,
  Extruded Bubble); it also timed out at `extruded_bubble-glass-1.25`. Check stale QSB binaries first
  (`tools/regen_qrc.py --shaders --check`), then compare captured pixels and clip ancestry; no shader or bound change
  without that proof.
- [ ] `tests/test_neon_lake_studio.py` (timeout in `test_engine_owned_edits_change_the_engine_answers_negative_control`),
  `tests/test_studio_drag_io_churn.py` (the `shockwave_grid` case of
  `test_no_drag_instrument_writes_while_moving_and_each_release_commits_once`) and
  `tests/test_visualizer_owner_render_parity.py` (the `extruded_spectrum` worker-path case): 160 s isolated timeouts,
  not proven deadlocks; collect the last-test log, faulthandler output and a dump, isolate the parametrization, no
  broad worker rewrite, native worker stays dormant.
- [ ] `tests/unit/test_policy_compliance.py::TestThreadingPolicyCompliance::test_no_raw_threading_in_production_code`
  flags the named daemon wake-listener thread at `core/visualizer_engine/packet_mailbox.py:472`; the test file was
  absent from the transferred archive. Decide whether it is a permitted dormant mailbox mechanism or a real policy
  violation; do not exempt or refactor it from the missing test alone.

## Operator execution and evidence rules

Keep details and evidence at their focused owner, this checklist actionable, and `Index.md` / `Spec.md` navigation current.
No memory updates without an explicit request.

####################
ADDITION & SIDE QUEST BOX
Never Remove This Box. Restore It If Removed. Only Remove Contents As you place them in the active plan as real live checklist targets.
####################
Reactivity Issues:
General Issues:
###################
