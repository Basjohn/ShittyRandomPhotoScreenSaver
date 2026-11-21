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

**Temporary test-failure handoff (19 Nov):** `Docs/testfailures20261119.md` records the
three oversized-chunk timeouts, four earlier file-isolated timeouts, Settings foreground,
Glass clipping and absent-policy-test investigation. Preserve native-worker dormancy;
remove this pointer when the documented failures are resolved/accepted.

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
4. Ports, each under the guide from its first brief: the Oscilloscope (N5.1), then Waveform (N5.4) once the fast
   proof's coverage selection has passed its method proof on Bubble, then Extruded Bubble (N5.6), Neon Lake (N5.5),
   Extruded Spectrum and Sphere (N5.3).

5. Everything else in this plan is backlog: operator defects (Item 1, sections 1B, 1C, 1D, 1A), hygiene, Studio and
   later mode work. A slot takes from it only when no native step above can use that slot (operator, 15 Nov:
   native core first in every slot). Within a backlog section, its own internal order holds. No other heading in
   this plan sets a global order.

**Resume here (lead, 21 Nov, usage cut):**
- [ ] The fast-proof tools are merged (6055b0f97). Agent a6257c36aeee45f10 is running the held heavy runs: the
  Bubble method proof (it decides whether coverage windows become the default), and the rule (a) reruns of
  human_heavy1 and nightsolong. The Oscilloscope partner control follows the Oscilloscope merge.
- [ ] The Oscilloscope at ABI 28 is merged (audit 10's H1, M1-M4 and L2 fixed; Trace, Ring and Phase pass rule (a)
  on both APIs). Open before its 60 s takes, layer T and registration, agent a652d2d5a77e690ff (details under the
  N5.1 H1 box): audio block sizes 0 and 3 exceed rule (a)'s 10 ties (12-21, at most 2 levels); graticule 0 input 167;
  L1 (576 x 384 on OpenGL); the owner run's Bubble frames after the switch must be judged under Bubble's bounds (main's
  partner-bounds judge, now on the branch). Lead: the ABI 28 build of main, then the quiet cost round and layer T.

**Next, by slot** (operator, 20 Nov: Opus High only where it genuinely pays, otherwise a second Medium; audits at
the level the risk needs; Sonnet as a cheap workhorse, researcher and documenter alongside; no Fable unless asked).
- [ ] High (Opus High): the Oscilloscope port (step 4), then N3.6. Defects between N steps: 1D.6 (design note
  first), then 1C.10.
- [ ] Medium (Opus Medium): the fast-proof tools (step 1), then Bubble's L, T and long-take rule (b), then step 3.
- [ ] Second Medium (Opus Medium, while the High slot audits): step 2's scene-fade fix.
- [ ] Audit (Opus Medium; Opus High only for core C++ with real risk): each merge (the Bubble landing is audit 8).
- [ ] Sonnet Medium: profile the owner replay (the fast proof's first box), then cheap audits and docs of open avenues,
  hygiene item 6's closed-report cleanup, and the low-risk section 1E items.

### Item 0. Operator defects of 11 Nov: section 1B (backlog; its own internal order; see Order point 5)

### Item 1. Operator-reported defects first

- [ ] Foundry UX (operator, 14 Nov): `Docs/Future_Work/Foundry_UX_Audit_2026-11-14.md`; open from it, for the operator's
  pick: its remaining high and medium findings and the Build Foundry's port from Tkinter to PySide6.
- [~] Defect (operator, 14 Nov): a Studio window's taskbar icon in frozen builds is Windows' default box. The static
  cause is unproven (likely an icon Qt could not decode). Lead: check the next GitHub frozen build's `[ICON]` startup
  line, any no-icon warning for a shown Studio window, and the taskbar.
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

- [ ] N2.2 leftovers (proved; `native/core/python/host_check.py`; lifecycle facts J1 to J4 in
  `Native_Core_N06_N07_Qt_Facts.md`):
  - [ ] The hidden host's Qt Quick target keeps its contents between frames (defect B). A hidden host with
    transparent content must clear what Qt Quick does not cover; decide that when the first such host exists.
- [ ] N2.4 leftovers (proved; `native/core/python/composite_check.py`):
  - [ ] The Glass card material on the native composite; its contract read once Glass's own native path exists.
    When the card material moves to the core, its grain takes an integer hash exact on every backend (today 2 frosted
    pixels sit 12 levels apart on Vulkan where the float hash's `fract` wraps near 1.0; accepted 14 Nov).

Order inside N2 (the numbers stay stable for the documents that cite them): N2.1 to N2.4, N2.6, N2.7, N2.5, then
N2.8, whose rehearsal closes N2.5's rule (f) and releases the Python renderer's retirement.

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

**N2b. The background layer, natively, and the first full rehearsal**

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
- [ ] N3.6 Lifetime: lazy creation on first use, release at retirement and at a mode switch, device loss rebuilt
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
- [ ] N4.j Photo and backdrop environments (`PhotoEnvironment`: ten transitions; `BackdropEnvironment`: Extruded
  Spectrum and Sphere's wallpaper reflection).
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
identity harnesses. A difference that is not byte for byte goes back to the lead to judge. An Opus High audit
reruns every port's parity proof and its negative controls before merge.

Rule for every port here (Qt 6.12): where a mode's small instanced batches (bars, specks, snow, sprite families)
are measured above a handful per frame, one pipeline and one indirect call with `QRhi::ShaderDrawParameters`
(`gl_DrawID`, `gl_BaseInstance`, `gl_BaseVertex`) replaces a draw per batch; the port records which backends report
the feature (D3D11 is not stated).

- [ ] N5.1 Spline Curve leftover: its Studio is not offered on Vulkan (`STUDIO_PREVIEW_BACKENDS`), the same open
  item as Spectrum's; both close with N5.8.
- [ ] N5.1 Oscilloscope (Opus High: N3.4 bloom's first consumer; agent a652d2d5a77e690ff, 20 Nov).
  - [ ] Next (lead, 21 Nov; 5-hour window at 95 %, so after the reset): an Opus High audit of branch
    `worktree-agent-a652d2d5a77e690ff` before merge. Its ABI 26/27 C++ touches core code every bloom consumer will use:
    `u_scene_item`, the item-anchored bloom triangle, the three composites, and `StreamSource::syncStream` clearing an
    old stream's frame. Then merge, build main at ABI 27, run the quiet-machine cost round (the lead), and layer T
    (the lead). The owner smoke's remaining failure is the replay judging Bubble's partner frames under the
    Oscilloscope's bounds, a tool fix routed to the fast-proof agent. The stale-stream fix gets an R number at merge. Python oracle:
  `rendering/quick/visualizer/implementations/oscilloscope.py`. It is one instanced pass reading a segment array from
  the stream ring (binding 3) into a single-sample overlay `SceneTarget`. Each segment is a quad. Light goes into the
  overlay's emission attachment, and the target's bloom spreads it into the glow. Glow 0 allocates no emission or
  bloom. The glow light is `_GLOW_LIGHT` and the strength is per frame. Shapes and reaction rules:
  `rendering/gl_programs/oscilloscope_program.py`. Follow `Docs/Guides/Native_Port_Playbook.md` (checklist; E3, E4/E19
  bloom, the stream-ring section) and prove it under `Docs/Guides/Native_Parity_And_Timing_Proof.md` from the first
  brief.
  - [ ] Source reading first: the record each frame carries (segments, glow strength, settings), what is per frame and
    what is per settings change, the ring's size rule, and which N3.4 stages it needs (overlay target, bloom from
    emission, composite with glow). Confirm in writing that nothing the port needs is missing from ABI 25. Anything
    missing is a C++ box here, with its build.
    Read (Opus High, 20 Nov, at d9b5c4505; ABI 25). *Per frame, from the logical frame alone* (the record): the traces'
    points (float32 x, y, every trace back to back, at most 16 x 384; a storage stream with its used length), each
    trace's alpha (16, zero past the count), the points per trace (always 384 from the runtime; the frame admits 2 to
    384), the segment count (the instanced draw's instances: traces x (points - 1)), the flare's beam widening
    (1 + 0.9 flare x Flare), the brightness, the white-hot centre, the beam colour (the tone's tint under Spectral) and
    the bloom strength (Glow x (0.55 + 0.3 Pulse drive + 0.45 flare)); whether the graticule draws (its style and a
    frame with traces). *Per Settings or card change* (the settings): the content rect, the oriented size and quarter
    turns, one device pixel, the beam's base half width (half Beam Width x visual scale), the layout (the Trace's half
    extent past the centre, the vertical scale, the Ring's and Phase's radius and length), the glow colour, the glow
    light (`_GLOW_LIGHT`), Analog Beam, the Phase centre fade and the graticule's whole block. The flare-dependent
    reach, the Trace's horizontal scale (it runs past the item by the reach) and the focus length mix the two, so the
    converted beam shader derives them from the base values and the record's widening (checklist 16: the Python
    renderer draws the converted files). *The ring's size rule*: the record's points field is the whole capacity,
    49,152 bytes, only the used floats written; the slot is the record in whole 4096-byte steps (53,248).
    *The N3.4 stages*: a surface-sized single-sample overlay target (RGBA8 colour, RGBA16F emission), both passes
    blended MAX on both attachments, a bloom step from `scene.emission`, the `overlay_glow` composite (`u_bloom_strength`
    from the record, `u_hdr_exposure` 0 from the settings); with Glow 0 a target of colour alone and the `overlay`
    composite, so the beam and graticule each ship a fragment without the emission output (the core requires one output
    per attachment). *ABI 25 has all of it but one thing*: a record field no pass of the program reads is refused
    (`ModeProgram::check`), so the Glow 0 program, which has no composite reading `u_bloom_strength`, cannot read the
    one record. Neither a second schema per program nor an unused member is acceptable (D12 rejects silent unused
    fields). C++ box below.
  - [ ] C++ (ABI 26, needs a GitHub build): a program may name the record fields it reads nowhere (`"unread"`: a stage
    it leaves out reads them; each must be a field of the record and read by no pass, draw or stream), so a stage
    turned off at the Settings edge keeps the mode's one record. The Python face's `program_json` and
    `NativeMode.program` take `unread`. Proof: the Glow 0 program admitted with it and refused without it (GPU-free
    `mode_blocks`), a name the record lacks refused, a read field named unread refused.
  - [ ] The record schema and shared Settings and frame-value functions, which the Python renderer also calls (as
    Bubble did), proved byte-identical by a GPU-free test.
  - [ ] The route's program: the target, the stream ring, the instanced pass, the bloom stage and the composite step,
    declared as data (D12 to D17). The target size is sent only when it changes.
  - [ ] Layer P, rule (a): owner rule (a) over three 60 s recorded takes at the display placement, every Choice setting
    at both placements as a smoke check (the 5.5 s replay), and the run's judged counts stated. Rule (b):
    `native/core/python/oscilloscope_check.py` built on the shared rounds (as `bubble_check.py` reuses
    `devcurve_check.py`), with its negative controls run and seen failing.
  - [ ] Layer L: the per-frame record compared byte for byte with the Python renderer's values, once the fast proof's
    L tool exists (the "Build the fast long-clip proof" box). Until then, state that L is indirect.
  - [ ] Layer T: the live run on Vulkan and native OpenGL against the pre-flip Oscilloscope row (lead runs it on
    Display 1). Layer C: per pass at 2560 x 1440 and 4K, the glow-off path included.
  - [ ] Registration last (playbook checklist 18), then docs (D12 "As built: Oscilloscope", Primitives, README).
  - [ ] Blocking finding for owner rule (a) (Opus High, 21 Nov; `n5_1_oscilloscope/20261121_owner_variant_a/`): at the
    owner level the native glow differs from the Python renderer's by up to 4 to 5 levels in steady frames (variant a,
    5.5 s replay: 547 of 549 inputs, about 11,000 pixels a frame past one level, the scope's whole glow), though every
    setting and record value is the Python renderer's (probe: no member differs) and the harness's rule (a), with the
    target on the item's own rect, passes. Cause: the bloom chain's texel grid is anchored at the target's origin. The
    route's surface is quad-aligned (`composite_geometry(quad_aligned=True)`: 632 x 422 device pixels from window pixel
    44 for a 630 x 420 card at 45), so the native content sits one pixel into its target, while Python's `SceneTarget`
    allocation starts at the item's own pixel (and counts rows from the bottom); each 2 x 2 downsample pairs other
    pixels, and the glow moves by several levels. Python's frame at a fade input (360) also draws nothing where the
    native one draws its fading scope (10 levels). Decide one of: (a) C++: a scene target anchored at the item's own
    device-pixel origin inside the quad-aligned surface (the bloom grid as Python's; the beam's derivatives keep the
    surface's quads), with its harness; (b) Python's `SceneTarget` aligns its allocation as the native target does
    (changes the frozen Python pictures of every scene-target mode); (c) a measured tolerance class for the bloom
    grid's phase. The three 60 s takes and the offers smoke were stopped at this finding (each failing the same way).
    - [ ] Lead's decision (21 Nov): (a). C++ (ABI 27, needs a GitHub build): the core member `u_scene_item`, every
      composite form reading from the item's own pixel, the bloom's first downsample from it (`bloomTriangle`), the
      `bloom_at_target_origin` control; proof `oscilloscope_check.py --rounds block item pixels offsets` (odd and even
      offsets in each axis) and `--control old_origin` seen failing; then owner rule (a) on the 5.5 s replay. Input 360's
      cause (a new stream's admission-rejected first frame left the previous mode's record and frame) is fixed in the
      same build (`StreamSource::syncStream`). The three 60 s takes and the full Choice-offer runs wait for the fast-proof
      tools (operator, 21 Nov: no long-take proofing before them).
      Run on the ABI 27 build (21 Nov, `n5_1_oscilloscope/20261121_n51_oscilloscope_abi27/`, `20261121_owner_abi27/`):
      the harness passes on both APIs with validation clean, offsets included (4 placements x dpr 1 and 1.5 x 16
      frames: at most 2 levels from the item's own rect, rule (a) against Python on every placement). `old_origin`
      failed as expected at all 8 (3 to 6 levels, about 33,000 to 56,000 masked pixels a frame). Owner smoke: the
      Oscilloscope's inputs 0 to 336 pass rule (a) in both halves (at most 2 levels, at most 3 ties), and input 360 is
      0. The run fails only on Bubble's frames after the switch (inputs 390 to 418, 11 to 12 ties) judged under the
      Oscilloscope's tolerance (`owner_render_parity` judges the partner's frames under the run's mode: that tool's
      owner decides). Glow 0 set (`..._abi27_glow_off/`, `..._abi27_item_glow_off/`): block, item, pixels and rule (b)
      pass on both APIs (36 samples, at most 1 level). The item round needed two harness fixes: `item_key`, and a beam
      width change at Glow 0.
  - [ ] Layer C cost on a quiet machine (lead): `python native/core/python/oscilloscope_check.py --module-dir
    release/native_module --require-validation --layer-path <layers> --label n51_oscilloscope_cost --rounds cost`. A
    first round ran 21 Nov under concurrent load from two other agents' heavy runs (CPU 57 %), so its figures are not
    clean (`..._abi27_cost/`). Median whole surface on Vulkan: 0.142 ms at 1440p and 0.249 ms at 4K. On OpenGL:
    0.186 ms and 0.300 ms. The clear, bloom and composite take about 70 % of it. "4K" is capped at dpr 8 (3360 x 2240,
    7.5 M pixels).
  - [ ] Side defect (found 20 Nov by the port): the legacy `widgets/spotify_visualizer/shaders/oscilloscope.frag` (and
    its `.qsb`) is drawn by no renderer (its own header says so; the beam files are the mode's shaders now), yet it is
    still the mode's registered fragment (`shaders._ALL_SHADER_FILES["oscilloscope"]`): `preload_fragment_shaders`
    composes it at startup, the route's `_ModeContent.load` reads its pack at every Oscilloscope bind (the program
    ignores it), and `generic_mode_check.py`'s product-pack round admits it as "the Oscilloscope's" pack. Retire it with
    its registry entry once the route no longer reads a mode's pack for a mode with its own program, and move the
    harness's admission check to the beam's packs.
  - [ ] Audit 10 H1 (blocks registration; `Docs/Future_Work/Checkpoint_Audits_Nov21.md`, checkpoint audit 10): the
    Trace display fails owner rule (a) on ABI 27 (5.5 s, `--offers --runs oscilloscope:osc_display=0`: 429 of 546
    frames, at most 8 levels, a glow wedge along the card's right edge). Python's `SceneTarget` keeps the beam's overrun
    right of and above the item in its allocation's slack and cuts it left of and below; the native surface-sized target
    holds 1 to 2 pixels of it on every side; the bloom spreads the difference into the item. Lead decides: (a) C++ ABI
    28, the target is Python's own (origin the item's pixel, allocation the bucket of its rect, grow-only, drawn through
    the window's viewport), or (b) Python's `SceneTarget` scissors its passes to its rect and the core scissors to
    `u_scene_item`. Then: owner rule (a) for every display (`--offers`, 5.5 s), the offsets round over every sampled
    frame, audit 10 L1's 64-multiple case rerun, and D12's bucket sentence corrected.
    Lead chose (a); built as ABI 28 (eb3aabb30), run 21 Nov:
    - Harness `n51_oscilloscope_abi28`: passes on both APIs. Rule (a) holds over 63 samples a ratio from all 7 runs
      (Trace, Ring and Phase included), at most 2 levels, at most 4 ties. The offsets round's placements are
      bit-identical to the item's own rect. `old_origin` failed at all 8 placements.
    - `generic_mode_check` (M4 case): passes on both APIs.
    - Owner `--offers` (`20261121_owner_offers_abi28/`): the Oscilloscope's shown inputs pass rule (a) in both halves
      for Ring, Trace, Phase and audio block size 2.
      - Every run but Phase fails on Bubble's frames after the switch (inputs 390 to 418), judged under the
        Oscilloscope's tolerance (the owner tool's judging, its owner decides).
      - Open: audio block sizes 0 and 3 exceed rule (a)'s tie count in the shown span (12 to 21 ties a frame at
        2 levels, 52 + 28 and 42 + 28 frames); Graticule 0 fails one frame (167: 3 ties not isolated). Not the
        overrun (placement-independent); cause not isolated.
    - L1 rerun (`20261121_n51_audit10_edge_abi28/`): at 48/35 (a 576 x 384 item, whole buckets) rule (a) still fails
      on OpenGL (13 to 14 ties, 2,260 masked one-level pixels a frame) and rule (b) one frame (2 ties not isolated);
      32/35 passes rule (a). Cause not isolated; it was there at ABI 27 too.
  - [ ] Audit 10 M1: `oscilloscope_check.py`'s offsets round places only the first 16 samples (Ring and Phase), and its
    Python reference is drawn through a viewport the item's size (all overrun cut, unlike the product). Place every
    sampled frame; draw the reference as the product does or state it is not the edge's oracle; run the box's owner
    smoke with `--offers`. Control: the Trace owner run fails on ABI 27 (`20261121_audit10_owner_trace/`).
  - [ ] Audit 10 M2: one owner of the item's pixel rect. `sceneItemRect` snaps at a fixed 1e-3 with no viewport clamp;
    `item_pixel_rect` snaps within its float32 matrix's rounding and clamps. They disagree within about 1e-4 to 1e-3 of a
    whole pixel (`snap_probe.py`: six of eight fractions), a one-pixel phase error. The core applies Python's rule
    exactly, its test deriving every expectation from `item_pixel_rect` over near-integer fractions (or the card carries
    one Python computation).
  - [ ] Audit 10 M3 (before the first turned bloom consumer: Waveform Ribbon, Extruded Bubble, Neon Lake, Extruded
    Spectrum): `u_scene_item`, `bloomTriangle` and the composite forms anchor in physical pixels, Python's turned scenes
    in the turned frame (`_ORIENTED_COMPOSITES`' `sceneTexel`). Take the turn as Python does, or refuse a bloom or
    composite program on a turned card until then; prove at quarters 1 to 3 with odd item sides.
  - [ ] Audit 10 M4: a regression test for ABI 27's stale-stream fix: a new stream whose first frame the admission
    rejects shows nothing of the old stream (`generic_mode_check.py` case or a module test, `stale_stream_probe.py`'s
    steps), its negative control seen failing; the R number at merge.
  - [ ] Turned-card anchoring for the Oscilloscope (from audit 10 M3, the lead 21 Nov): ABI 28 refuses a bloom or
    composite step under a turned card (fail closed, the refusal's reason in the item's state), because a turned card's
    native surface is turned against Python's physical `SceneTarget`, so its bloom pairs and its composite's texel and
    dither key would be rotated. The Oscilloscope on a turned display is therefore refused (the route fades it out)
    until this is built: the scene target in physical pixels (or the composite and first downsample taking the turn as
    Python's `sceneTexel` does), proved at quarters 1 to 3 with odd item sides against the Python renderer. Required
    before registration only if a turned display is offered.
- [ ] N5.1 Bubble (its extra target with a light attachment; instanced quads for its point sprites).
  Registered on the route and offered on Vulkan (rule (b) passes: `native/core/python/bubble_check.py`, D12 "As built:
  Bubble"). Owner rule (a) passes on the 5.5 s replay; on the four 60 s recorded takes, rejudged 21 Nov under today's
  rule (a), two takes fail three steady frames on the narrowed isolation clause (the box below). `Docs/Future_Work/Native_Bubble_Parity_Investigation.md` owns detailed statistics,
  eliminated suspicions and evidence; the diagnostics tools are `tools/visualizer_replay/bubble_native_diagnostics.py`
  (`Docs/Guides/Native_Bubble_Diagnostics.md`). Follow the Native Port Playbook; no further tolerance widening.
  Order: checkpoint audit 8's M1, M2 and lows (boxes below); the fast proof's L and P tools (their own box); layer L directly; layer T; rule (b)
  over the four takes; the 2560 x 1440 cost; the D1 rehearsal. Proved so far
  (`Docs/Guides/Native_Parity_And_Timing_Proof.md` layers): P on OpenGL over the four 60 s takes; P on Vulkan over the
  5.5 s replay only; L indirectly (the simulation is untouched and 21,107 matching frames); C at 4K. Not proved: T.
  - [ ] Layer T on Vulkan, first runs done (lead, 20 Nov, Display 1, quiet GPU; evidence
    `.artifacts/evidence/visualizers/{bubble,spectrum}/live_check/20261120_*`). Bubble on native Vulkan matches the
    Python OpenGL control in median and p90 (11.07/12.30-12.47 ms) and in tick-to-publish. Its render-thread
    recording is 10 times cheaper (0.15 ms median against 1.52). But its tail is heavier: frames over 16.7 ms were
    27, 39 and 27 against 11, 16 and 18, with p99 about 1 ms worse. Spectrum on Vulkan sits near parity (11 and 14
    against 7 and 9), so the tail is Bubble's own. In every late frame, the time is after rendering ends and before the
    next frame begins (median about 17 ms, up to 85 ms): not sync, not recording.
    - [ ] Root cause, two candidates, neither proved (agent aac773583ad93e2ab, 21 Nov; trace events 79 and 80, merge
      6020d2977). (1) The PERF HUD's once-a-second text write, from the 20 Nov traces below. (2) The GPU clock: the one
      clean 21 Nov run, with no game running, showed no once-a-second pattern (15 of 115 clusters). Vulkan had 79 late
      frames against OpenGL's 8, at 675 MHz median against 1553, so the native path's lighter GPU load may let the
      card downclock. The A/B adds clock sampling. The 20 Nov reading:
      Qt begins frames on the visualizer's present requests through its 5 ms update-request timer. About once a
      second another update source starts that timer early, so the next frame waits for the next publication, at
      about 6 ms and then 15-17 ms. Bubble's Vulkan late frames that follow such an early frame are 14, 21, 20 and 13
      per run; the rest, 13, 18, 7 and 7, are in OpenGL's range. Vulkan's frame ends about 0.5 ms after it begins, so
      the early timer expires just as Bubble's request lands: the publish arrives about 4 ms in, and the route sync
      takes 1.5-1.9 ms against OpenGL's 0.35. The likely source is the PERF HUD's text rewrite from a queued
      `frameSwapped` handler (`_update_perf_hud_on_swap`, `rendering/quick/scene_controller.py`), on in every live
      check (`--perf`), at 1000 + 0-12 ms. Ruled out by measurement: GPU time, acquire and present blocking, and the
      route re-running on an `afterRendering` edge (0 in 7,686 syncs). Evidence:
      `.artifacts/evidence/visualizers/bubble/live_check/20261121_layer_t_root_cause/figures.txt`.
      - [ ] One-variable proof: the HUD's text writes off against on, three Vulkan and three OpenGL runs, alternating
        back to back, with conditions recorded. If the HUD is the source, Vulkan's late frames after an early frame
        fall to OpenGL's range.
    - [ ] Fix, if proved: with a visualizer active, hold the HUD's once-a-second text and write it in
      `request_visualizer_present` just before `item.update()`, so both share one Qt timer. With no visualizer active,
      keep writing on swap. Separately, trim Bubble's per-frame route sync on the GUI thread (1.5-1.9 ms against
      0.35 for OpenGL).
    - [ ] Fix at the owner if it is ours, then rerun three Vulkan runs and three OpenGL controls back to back. Accept
      when frames over 16.7 ms on Vulkan fall within the control's spread. If it is the driver's or Qt's, record it
      in D12 "As built: Bubble" with the figures, and ask the operator.
    - [ ] Then Bubble's own T tools (its diagnostics guide).

  - [ ] Rule (b) over the four 60 s takes, once the owner replay gains `--api vulkan` (the fast-proof box). Today
    rule (b) has run over the 5.5 s replay's 684 sampled frames only.
    The tool exists (21 Nov): `native_record_identity.py --deliveries` then `native_stream_player.py`, about 9
    minutes a take on an idle machine; ragdoll and human_heavy1 ran and fail (the 60 s box below).
  - [ ] Layer L directly: the per-frame packed record byte-compared with the values the Python renderer uses, over the
    four takes (the fast-proof box's L tool; `engine_worker_gate.py` is the precedent).
    Ran 20 Nov (`native_record_identity.py`, variant a, display placement): identical on all four takes, 2,645 of 2,645
    and 2,646 of 2,646 inputs judged per half each (5,313 compared frames a take with the switch fade; all three passes
    and both ambient streams compared); Spectrum and Spline Curve on `nightsolong_acousticsoft1` identical with the
    same counts. Evidence `.artifacts/evidence/native_core/fast_proof/20261120_l_<mode>_<take>/`.
  - [ ] Checkpoint audit 8 M1, what is left (ties joined into groups, the 16 x 16 density bound of 26 for rule (a) and
    the split-line and dithered-patch controls landed 21 Nov, c432c1359; D12's Bubble line):
    - [ ] The audit's line split by two exact pixels (65 one-level pixels in a straight line, groups of 22) still
      passes: a straight line puts 16 pixels in a 16 x 16 window, under the bound. Decide whether it needs its own rule.
    - [ ] Rule (b)'s density bound: not set. Measured densest window 12 and 13 on the ragdoll and human_heavy1 60 s
      takes (`fast_proof/20261121_rule_b_60s_*`), 9 on the 5.5 s stream; rule (b)'s own count and tie bounds fail
      on the long takes (the box below), so the bound waits for that decision.
    - [ ] Rerun the offers and rule (b)'s 684 frames under the fix. Any newly failing frame is classified, never
      admitted by a wider bound.
  - [ ] Bubble's 60 s takes under today's rules (audit 8 M2's rejudge, 20 and 21 Nov; D12's Bubble line;
    `fast_proof/20261120_m2_rule_a_60s_*`, `20261121_m2_rule_a_60s_*`, `20261121_rule_b_60s_*`). Classify and decide;
    no bound raised.
    - [ ] Rule (a): human_heavy1 inputs 2182 and 2223 and nightsolong input 2128 fail, each a lone 2-level tie off a
      content edge (reference 3x3 range 31, 15 and 23) with 3 or more scatter pixels in its 3x3: the narrowed isolation
      clause of 17 Nov, which the stored reports predate. nightsolong input 22 as accepted. ragdoll and anything_mixed2
      pass.
    - [ ] Rule (b) on 60 s (`native_stream_player.py`): ragdoll 18 and human_heavy1 12 of 5,313 frames fail the
      5.5 s-measured bound (32 scatter, groups of 11, no tie): scatter up to 237 a frame but spread (groups at most
      11, densest window 13), 2-level ties in 6 frames, all steady (content fade 1), 8 of ragdoll's in inputs 74-197
      (the reveal and the synthesised pause). anything_mixed2 and nightsolong not run yet (their streams are in
      `D:\Temp\Scratch\SRPSS\fast_proof\deliveries\`).
  - [x] Class-word upload and portable unsigned-vector admission proved on both APIs; unchanged wire record (R-238).
  - [ ] Non-blocking contract follow-up, now with a measured case: non-unit inherited scene opacity. During the cold
    reveal (scene fade 0.8648 at input 0 to 1.0 by input 30, content fade 1, identical on both paths) Python folds it
    into the shader fade while native composites it afterward; the operator-accepted input-22 pair (D12 Bubble line)
    sits in that window, as do Spline Curve's cold-start failures (see the Spectrum and Spline Curve box). Prove with
    the scene fade forced to 1 on both paths, then one owner applies it for both. Probe:
    `.artifacts/evidence/native_core/n5_1_bubble/20261117_reveal_values_bubble_nightsolong/`.
  - [ ] Tracked exceptions of the scene-fade double-rounding class (lead, 17 Nov; no bound or class change; D12's
    Bubble line), to disappear when the scene-fade fix lands (the Spectrum and Spline Curve box): the operator-accepted
    `nightsolong_acousticsoft1` input 22 pair, and the offer runs `stream_direction=2` and `=6` at input 337 (the mode
    switch), adjacent 2-level ties on the mask off a content edge (`n5_1_bubble/20261117_offers/`,
    `20261117_offer_tie_classes/`). The other 38 runs pass (variants a and b at both placements, the Choice offers at the
    display placement only; scatter worst 41, group worst 15;
    the three steady tie frames pass under the lead's narrowed isolation rule, rerun `20261117_offers_steady_rerun/`).
  - [ ] GPU median and p90 per pass at 2560 x 1440 against the Python renderer's (checklist 11): still open. 4K is
    measured (D12 "As built: Bubble", cost).
  - [ ] Check the 4K cost's ambience-off surface reading higher than ambience-on (0.299 against 0.236 ms on OpenGL at
    840 x 560; 4.23 against 3.10 ms at the 4K frame): the columns are not swapped in `bubble_check.py` (`COST_RUNS`:
    on = variant a's frame, off = variant b's), but variant b differs from variant a in many settings beyond the
    ambience, so the two frames are not a like-for-like ambience toggle. Measure one frame with only the ambience
    switched.
  - [ ] For the Bubble GPU optimisation item: native OpenGL is about 5 % slower than the Python renderer at the full
    4K frame (3.10 against 2.94 ms ambience on, 4.23 against 4.08 ms off; at 840 x 560 0.236 against 0.230 ms).
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
- [ ] Build the fast long-clip proof (Opus Medium agent a6257c36aeee45f10, 20 Nov; method and rules: `Docs/Guides/Native_Parity_And_Timing_Proof.md`, its
  section 7; step 1 of the order: Bubble's layer L and long-take rule (b) need it, and so do every later port). Steps, each with a test:
  - [ ] Layer L: the per-frame record compared byte for byte between paths, CPU only (`engine_worker_gate.py` is the
    precedent).
    Built (20 Nov, commit e0275205c): `tools/visualizer_replay/native_record_identity.py` (`--mode --recording
    --seconds 60 --out`), test `tests/test_native_record_identity.py` (one-ulp record and dropped-frame controls seen
    failing at their input). One owner tick; the product's route on the owner's own item with a recording core; per
    frame record bytes, settings by name and the module's GPU-free blocks against the Python renderer on a null GL.
    Outside L by declaration: positional members (uMatrix, u_target_px, Spectrum's window maps) and the inherited scene
    opacity. A take runs in 24 to 39 s. Evidence `.artifacts/evidence/native_core/fast_proof/20261120_l_*`.
  - [ ] Layer T on native paths (guide section 7): the live check reads presentation cadence from Qt Quick's frame
    cycles when the native core draws (today it reports `frames_per_s 0` on Vulkan), and the native per-pass GPU
    time from `--gpu-pass-timing`. `tools/quick_frame_cadence.py` (frame-cycle intervals outside lifecycle windows) is the
    reference; prove it gives the same figures as the Python path's swap gaps on an OpenGL run.
  - [ ] Layer P: cached Python references; a native-only, hash-only compare with `--api opengl|vulkan`; every failing
    frame recorded (not the first eight); progress written during a run.
    Built (20 to 21 Nov), in the profile's order, each with a test, evidence `fast_proof/20261120_*`:
    (1) ddb3dc8b2 the judge reads content edges only at ties and flips, and one pass per frame shares one decompress
    and one delta (same verdicts on synthetic frames and on the 5.5 s replay of all three modes; judge 10 to 13 s
    against 58 to 61 s); (2) ec0bf3feb no lit mean on native, reference or mask runs, and the console says
    "not bit-identical ... PASS under tolerance"; (3) 12a688e57 `owner_render_parity --native --references` caches
    the Python run and its masks (`tools/visualizer_replay/python_references.py`, default
    `D:\Temp\Scratch\SRPSS\fast_proof\references`, about 2 GB a 60 s take; keyed by the run and the Python drawing
    code's sources, re-drawn when the native run's logical digests differ); (4a) d0b2e8095 the reference first, then
    each native frame judged as it is drawn with a progress line, every failing frame kept with its pixels, and
    `--native-only --against <report>` (no Python, hashes only, every changed frame listed); (4b) 29fc590c0 the
    Vulkan side is not the owner replay (its hidden host is OpenGL) but the take's delivery stream
    (`native_record_identity.py --deliveries`) drawn by `native_stream_player.py` on OpenGL and Vulkan: rule (b) per
    frame under the mode's `VULKAN_RULE_B`, and each API's hashes against an earlier run; generic modes only, Spectrum's
    own item is not played yet; (5) d0b2e8095 `--judge-workers N`, the same result as one process.
  - [ ] Checkpoint audit 9 M1 (`Docs/Future_Work/Checkpoint_Audits_Nov21.md`): the cached reference's key
    (`python_references._source_files`) misses `rendering/gl_programs/conventions.py` (spliced into every composed
    shader), the composer `widgets/spotify_visualizer/shaders/__init__.py`, `rendering/gl_programs/*`, the QML shaders
    and the mask and capture code (`rule_a_masks`, `content_backdrop`, `SceneMirror`,
    `pixel_tolerance.translucent_by_backgrounds`). Key on the composed sources of every shader the renderer compiles,
    a declared module list and the mask code; the conventions change (seen not changing the key) becomes the test's
    control.
  - [ ] Checkpoint audit 9 M2: the stale-reference path dies on Windows (WinError 32: `store` removes the folder whose
    `frames.bin` the loaded `StoredFrames` still holds open), leaving the stale reference so every later run dies
    too. Close the stored frames (or store aside and swap), rewrite the progress file from the rejudge with the
    run's `--judge-workers`, and test the stale path end to end.
  - [ ] Coverage selection with its coverage report (guide section 3), warm-up per mode (guide section 5).
    Built (21 Nov, b4cd47802): `tools/visualizer_replay/coverage_windows.py` selects from the take's continuous
    delivery stream (cold start, switch, a late window in the last 15 s, loudest, quietest, each record field's
    extremes); warm-up 0 for the landed modes (no GPU history); `native_record_identity.run(window=...)` is
    byte-identical to the full run's slice and its restart control is caught (`tests/test_coverage_windows.py`);
    `native_stream_player.py --windows` and `owner_render_parity.py --windows` draw only the windows. Bubble's four
    takes: 11, 10, 12 and 8 windows, 972, 954, 1,143 and 856 of 5,313 inputs drawn, late windows at 45.1, 43.8,
    50.6 and 57.1 s, all 14 fields covered (`fast_proof/20261121_coverage_bubble_<take>/`).
  - [ ] Method proof on Bubble: the selected set catches input 22, the two offer fade frames, a one-level shift and a
    one-ulp shader change.
    Controls built (WIP 503784340): `owner_render_parity --native-control shift`, `native_stream_player
    --shader-control ulp_gradient`. Not run yet (held for the layer T agent's quiet CPU). The runs: nightsolong
    `--references --windows` (input 22 in the cold-start window); the 5.5 s offers `stream_direction=2` and `=6` with
    5.5 s windows (input 337); one take with `--native-control shift`; the player `--windows --shader-control
    ulp_gradient --apis opengl --against` a full-run report.
  - [ ] Rule (a) reruns of human_heavy1 and nightsolong under today's rule (isolation clause retired 270313a62): the
    M2 frames 2182, 2223 and 2128 must pass and input 22 still fail; store their references (`--references`).
  - [ ] The partner-bounds control on real frames: the Oscilloscope 5.5 s smoke's Bubble frames (inputs 390-418) pass
    under Bubble's bounds (5608f58db) and fail under the Oscilloscope's.
- [ ] N5.4 Waveform Ribbon (N4.b, N4.d's planar reflection, N4.f1's fog volume, its five compute passes and three
  rings, floor and pulse-rim textures; not populations): the mode over its render budget under load, measured
  against the 11 Nov load session (item 7).
  - [ ] Port decision: Waveform clears its scene colour every frame to a backdrop from its recipe
    (`rendering/quick/scene3d/waveform.py:387`), while a native target's clear value is fixed in its declaration
    (D14; D17 point 9). Decide the port's form (a clear value filled by a setting, or a first pass that writes the
    backdrop) and prove it against the Python renderer under the port rule.
- [ ] N5.6 Extruded Bubble (the drift compute of D4, transparency, HDR, the depth texture and background
  capture, the probe and defocus, N4.k, N4.g's impostors and optics; not populations).
- [ ] N4.f2 (the reduced-resolution layers; Waveform and Extruded Bubble are native), then Expanded Visualizer M6
  (4K acceptance, plan 01) may run.
- [ ] N5.5 Neon Lake (N4.e, N4.k, instanced quads for its marks, its own analytic water reflection; its reaction
  and growth are uniform arrays).
- [ ] N5.3 Extruded Spectrum, then Sphere (meshes, lighting, N4.j's backdrop environment, N4.l's silhouette
  shadows; neither uses bloom; no compute).
- [ ] Spectrum and Spline Curve long-take residuals (ACCEPTED by the operator, 17 Nov, with Bubble; non-blocking: the
  scene-fade double-rounding fix, then a rerun as their control). Opus Medium agent a9931705e23b026a7 (21 Nov) on the scene-fade fix. Their landed parity was proved only on the 5.5 s Studio clip, which the owner
  replay switched away from at 4.2 s. Neither mode is retuned and no D12 bound is changed while this is open.
  - Sources: `tools/visualizer_replay/owner_render_parity.py` with `--recording <take> --seconds 60` (recorded-take
    support from Bubble's branch, commits b2486b333, 673377683, 770fee01e; per-half reporting 4c0b1474b and the
    first-eight-failing-frames record 92c721fc9 land with N5.1). Bounds: D12 "The pixel tolerance"
    (`Docs/Future_Work/Native_Core_P3_Decisions.md`) via `tools/pixel_tolerance.py` (composite: 1 level on the mask,
    10 ties at 3 levels, ties isolated or on a content edge, no flips). Module: ABI 25 (c53e3fe27). Evidence:
    `.artifacts/evidence/native_core/longclip_recheck/20261117_{spectrum,devcurve}_nightsolong_display[_framelist]/`
    (owner report, both paths' frame hashes, `frame_verdicts.json`). Take: `nightsolong_acousticsoft1`, display
    placement, 5,503 inputs (the mode switch at input 5291, about 58 s; inputs 0-2750 first half, 2751-5290 second).
  - Three more takes, variant a, display placement, 60 s (5,503 inputs, switch 5291, halves 0-2645 / 2645-5291), module
    ABI 25, frozen settings, cold start. Evidence under `.artifacts/evidence/native_core/longclip_recheck/20261117_<mode>_<take>_display/`
    (`native_render_parity.json` with both paths' frame hashes; `failed_frames` is capped at the first 8, so failures
    past the 8th are counted per half but not listed). Ties / scatter / max level are the worst single frame. Runtime
    in parentheses.
    - spectrum ragdoll_quiet_intro_loud_end1 (1361 s): PASS, 0 failed; ties 2, scatter 0, max level 1; first half 2 /
      0 / 1, second half 1 / 0 / 1.
    - spectrum human_heavy1 (1223 s): 1 failed, input 5311 (mode-switch fade, not cold start; 3 ties not isolated); ties 3,
      scatter 0, max level 1; first half 2 / 0 / 1, second half 0 / 0 / 1; steady 0 pixels past 1 level.
    - spectrum anything_mixed2 (1000 s): 2 failed, inputs 5311 (25 ties) and 5312 (105 ties), both mode-switch fade, none
      in 0-30; ties 105, scatter 0, max level 1; first half 2 / 0 / 1, second half 0 / 0 / 1; steady 0 pixels past 1
      level.
    - devcurve ragdoll_quiet_intro_loud_end1 (1504 s): 22 failed (first half 22, second half 0); listed 0-3, 5, 6, 7, 10
      (all cold start; 224 ties at input 10); the other 14 of the first half are not listed; ties 224, scatter 0, max
      level 3; first half 224 / 0 / 2, second half 9 / 0 / 3.
    - devcurve human_heavy1 (1033 s): 22 failed (first half 21, second half 1); listed 0-3, 5, 6, 7, 8 (cold start; 1343
      ties at input 8); the other 13 first-half failures and the one second-half failure (input unknown) are not listed;
      ties 1343, scatter 0, max level 3; first half 1343 / 0 / 3, second half 9 / 0 / 3.
    - devcurve anything_mixed2 (1160 s): 25 failed (first half 24, second half 1); listed 0-7 (cold start; 1329 ties
      within the first half, 158 at input 1); the other 16 first-half failures and the one second-half failure are not
      listed; ties 1329, scatter 0, max level 2; first half 1329 / 0 / 2, second half 9 / 0 / 2.
    - Pattern: scatter 0 and flips 0 in all six; Spectrum's only failures are the mode-switch fade frames 5311-5312
      (a replay artefact, as on nightsolong); Spline Curve fails on every take in the first half, at inputs 0-10 for the
      listed ones (inputs 0-2 fail on every take with the same 35 / 114-158 / 134-152 tie counts), with 0-1 failures in
      the second half (second-half ties never above 9 in any take; the one failing frame's reason is not recorded).
  - Lead for the cold-start frames (Bubble's probe, 17 Nov, same take and window): during the reveal both paths read
    the SAME values, content fade 1 and scene fade rising 0.8648 (input 0), 0.9422 (10), 0.9942 (22) to 1.0 by input
    30, but apply the scene fade at different places. Python folds the inherited scene opacity into the shader's fade
    (one rounding, `VisualizerRenderNode._inherited_scene_opacity`); native draws at card content fade 1 into its RGBA8
    surface and the scene fade is applied by the composite afterward (two roundings). Bubble's only long-clip failure
    (input 22) and 20 of Spline Curve's 27 (inputs 0-25) fall exactly in this window. Next: prove it by comparing a
    frame with the scene fade forced to 1 on both paths, then fix at the owner (one place applies the scene fade for
    both), not by a bound. Probe and values: `.artifacts/evidence/native_core/n5_1_bubble/20261117_reveal_values_bubble_nightsolong/`
    (`reveal_values.json`, probe `reveal_probe.py`); the existing Bubble box's "non-unit inherited scene opacity"
    follow-up is the same question.
  - [ ] Spline Curve (`devcurve`), variant a: 27 failed frames, all ties over the 10-a-frame bound, not isolated and
    not on a content edge; max 3 levels, no scatter, no flips. 20 are inputs 0-25 (cold start: worst input 10, 162 ties
    at 2 levels), 2 at inputs 728 and 829, 5 in the second half (2991, 3170, 3385, 3446, 4042; 1-9 ties). Root cause
    first: (1) the cold-start frames: compare the first 26 inputs' logical state Python vs native (warm-up order, the
    first record's settings, the Dynamic Floor's first value) before treating them as a class; (2) the steady
    failures: classify their pixels with the 3x3 reference range (curve edges vs flat interior) and test whether one
    source (the adaptive normaliser's float path, a uniform's precision, the line raster) explains every one. Fix at
    the owner; if they prove to be a D12 class, the bound is a lead decision with the measured worst stated.
  - [ ] Spectrum, variant a: steady passes the whole take (0 failures, 0 ties, 0 scatter, both halves); 3 failed
    frames (5310-5312) in the fade after the replay's mode switch, 69 ties at 1 level, not isolated. Variant b passes.
    Root cause first: the fade class (the composite's translucent mask during a mode switch). Check whether the mask
    from the reference's two-background draw covers fading pixels; if the mask misses them, the judge is wrong, not
    the port.
  - [ ] After both are settled: the remaining three takes for each mode at the display placement, frame hashes kept
    as their reference (the operator's half-size recheck: display placement only).
  - [ ] When the scene-fade fix lands (one place applies the scene fade): rerun Bubble's offers
    (`owner_render_parity.py --native --mode bubble --offers`, both placements) and `nightsolong_acousticsoft1` input 22;
    Bubble's tracked exceptions (input 22, and `stream_direction=2` / `=6` at input 337) must disappear.
  - Tool gaps found (fix with or before this box): no Vulkan path in the owner replay (no rule (b) or Vulkan hashes);
    output only at the end of a run (a killed run loses everything); about 3 GB per run; 28 min per one-variant run.
- [ ] Bubble GPU optimisation, after N5.1 lands (operator, 17 Nov: Bubble about 50 % GPU at 4K and Extruded Bubble
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
  - [ ] Extruded Bubble gets the same treatment after N5.6, with its own three-clip before-state.

**N5, background track (one High slot; transitions grouped by what they share; needs are in the matrix,
section 2)**

Slots (lead, 12 Nov): N5.2a, the first group on the shared fullscreen pass, goes to Opus High, and so does each group
whose primitive is ported with it (N4.c, N4.g, N4.i, N4.j, N4.l). After that, a group whose primitive is already
native goes to Opus Medium, under the same parity proof and audit as the modes track.

- [ ] N5.2b leftover: Beam. Its sparks are a second pass of their own geometry (900 instanced additive streaks from
  their own vertex stage), which the core's full-card fragment passes cannot draw; it stays Crossfade on Vulkan.
  Port it with the instanced-quad primitive the Oscilloscope's beam and Bubble's sprites need (N5.1), under the same
  proof in `transition_route_check.py`.
- [ ] N5.2c Scene target and photo environment only (N4.j): Blinds, Cube Turn, Depth Cascade, Jigsaw.
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
  and reuse of Studio Qt Quick bounce/hover transitions with reduced-motion policy. **Pre-SMP 1B.8 M4 unifies Settings and Widget themes immediately after M3 material borders; SMP M0/M1 adds scoped ZIP skin support.** The full visual Theme & Skin Studio comes after the first usable SMP release at M10. Design and boundaries: plan 02 §8.2B and document 05.
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

- [ ] **Idle parent bubbles occasionally teleport their wake bubbles (operator, 19 Nov):** this persists in Extruded Bubble with wakes enabled, less noticeably for small parent bubbles and more noticeably for larger parents. Reproduce on steady idle motion at contrasting parent radii with stable bubble/wake identity traces, world-space positions and successive frames; determine whether the cause is wrapping, spawn/expiry, parent-relative transform, interpolation or a GPU/CPU lifetime mismatch. Correct the owner, not by fading out the symptom; preserve authored wake motion and the already-required stable-world/camera contracts in `Docs/Reference/Extruded_Bubble/Target.md`. Cover Normal/paused/idle audio, large/small bubbles and camera motion with focused tests and real visual evidence. **Schedule after the relevant native Extruded Bubble port/validation, before SMP M0; do not detour N5.6 or ongoing native work.**
- [ ] **Preset 9 (Deep Red Ocean): rapidly flickering bubble-star/circle at the default camera (post-port):** at the authored default view, which is otherwise good at fullscreen 4K, a very fast flickering circular/star-like arrangement of bubble lines is briefly visible and difficult to capture in screenshots. Investigate whether an emission source or spawn geometry is leaking into view; gather high-frame-rate footage or captured successive frames, verify emitter culling and view transforms, and hide the source without hiding the legitimate emitted bubbles. Treat this as a shared Extruded Bubble system issue unless evidence isolates a preset defect.
- [ ] **Existing regular bubbles not consistently accelerated by music (post-port):** confirm that all eligible *already-living parent bubbles*, not only newly emitted bubbles, respond to music-driven acceleration. Exclude microbubbles and particles. Compare old/new bubble identity and velocity under the same audio, checking pinning, age-dependent logic, lifetime state, spawn-time-only parameter propagation and native buffer updates. Preserve intentional pinned motion if explicitly authored, but correct accidental non-reactivity at its owner. Reproduce on Preset 9 and another preset, with paired real-audio and idle tests. **Both Preset 9 issues are after N5.6 and its validation, before SMP M0.**

### 1B.11 Theme filter in the Linked row (contract: Settings_Theme_Architecture.md "Theme filter")

- [~] The theme list's and the popup's scrollbars (native black/white bars in off-screen captures): 1B.14's Settings
  and Studio box.

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

## 1E. Operator requests (20 Nov; backlog under section 1's Order, point 5)

Each item reproduces its failure first. The lead judges pixels on the operator's two wallpapers. Opus Medium or Sonnet
by risk; none takes a slot native work can use.

- [ ] **Gmail's faint runs on a light Mica card sit under 4.5:1 now that Gmail takes the shared panel.** Measured with
  `tools/surface_material_capture.py --card-set lists --legibility` (Polished Chrome, Usu_Underwater_Lab): sender,
  date and menu runs 4.14 to 4.45 (they were 5.1 or more with Gmail's own ink); every other material and the dark
  theme are unchanged. The run solver keeps a run that reads at the 4.5 floor over the poles byte for byte, and the
  composed Mica pixels land below it. Fix in the shared solver or Mica's light recipe, never a Gmail exception.
  Media still supplies its own playback-state ink (`MediaPresentation.qml:7`) and so still differs from Feeds and
  Reddit (glass 0.80 against 0.88 on Default Dark): decide whether Media's too goes to the shared path.
- [ ] **Widget opacity baseline:** the current -0.35 becomes the new 0 (Base). The operator checked that every theme
  stays legible at -0.35.
  - [ ] Root cause first: where the baseline is defined (the canonical default and the Style Override offset), and
    what the legibility guard does at that value. The guard must not raise opacity back: tell it the new base is
    intended (a theme-authored floor, not a new exception).
  - [ ] Persisted values: follow `Docs/Architecture/Persisted_Input_Compatibility.md`. A stored user offset keeps its
    visual result (stored + 0.35), and an unset value takes the new base. Test both. Never pin the default's number in
    a test; derive it from the canonical default.
- [ ] **Style Overrides: a "Borderless" button.** (Sonnet agent a491af36afbc01b8e, 20 Nov.) It goes below "Reset Colours To Theme", on the same row as Card Border
  Width, right-aligned, in the same style. It latches pressed and sets every border element of the widget UIs to 0 or
  invisible. Reset Colours, editing the border width, or changing the surface choice in Style Overrides each un-latches
  it. It persists like the other overrides. Test: latch, each un-latch path, and a reload.
- [ ] **The ordinary Visualizer card offers its Rotate glyph on hover** (operator report): UI-3 of `Docs/Future_Work/Studio_Corners_Card_Rim_and_Visualizer_Rotate_2026-11-09.md`, its
  live checklist. Today `rendering/quick/qml/VisualizerPresentation.qml:1049` still passes `canRotate: false`.

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

## Operator execution and evidence rules

Keep details and evidence at their focused owner, this checklist actionable, and `Index.md` / `Spec.md` navigation current.
No memory updates without an explicit request.

####################
ADDITION & SIDE QUEST BOX
Never Remove This Box. Restore It If Removed. Only Remove Contents As you place them in the active plan as real live checklist targets.
####################
Reactivity Issues:
1. WaveForm - Travel Direction for the overall mesh has no reactivity option to control its speed. It should have a range slider controlling speed from min-max depending on overall instensity. Quick Attack, Slow Decay but adding these as options is best. There also might be missing a overall base speed and idle speed of the mesh setting. Check, add what's missing and audit these controls so they don't conflict but complement each other. Default setting in all presets will be what it currently is as is our usual methodology.
2. Neon Lake. Generally very much improved and still has work in plan but there is a lot of sharp movement on terrain currently. Sudden massive judder up or down that feels sharp blocklike instead of smooth. This is likely a visual issue not a design one. Preset 1 shows this easily, especially on terrain closer to the camera. Needs to be smoothed without smoothing the audio or deadening reactivity. Same peaks and bottoms but we get there less sharply.
General Issues:
Clicking a link in MC profiles/mode completely kills the cursor halo now.
###################
