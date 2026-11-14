# SRPSS | Current Plan

Live, ordered work only. `[ ]` work remains; `[~]` a candidate exists but is unaccepted (awaiting validation, never an
implicit pass). When an item lands, delete it: completed work lives in source control and its durable contract in
`Spec.md` / `Docs/` (Reference, Architecture, Guardrails, Guides); rejected mechanisms in `Docs/Historical_Bugs/`. This
is not a changelog. Deferred, unadmitted ideas live in `Future_Work.md`.

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

**Now (in flight):** N2.5 (High); 1D.13, then N1.6 Extruded Spectrum and Sphere (Medium).

**Next, by slot.** Picks come from the native ladder, active defects and side defects; operator requests are done
at the size asked.
- High:
  1. N2.5 (Spectrum at parity; the reader's first user), then N2.8; N2.3's and N2.7's leftovers
     ride with the next fitting dispatch.
  2. 1D.6 (design note first), then the 1C.2 Save stall and 1C.10, as defects between N steps.
- Medium:
  1. 1D.13 (a test process dies at exit 127 in a larger file set), then N1.6's Extruded Spectrum and Sphere, one
     per commit where it stays bit-identical at the widened run set; a program that cannot converts at its port.
  2. 1D.14 (Spectrum's rim glow), once N2.5 has merged.
  3. 1B.10.
- Docs (Sonnet): only when a step needs a document.
- Audit: an Opus High behind each merge, scaled to its risk.

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
- Group Wave's separation from Travelling Pulse and the pulse bands' colour edges: their boxes are in section
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

Evidence: `.artifacts/evidence/visualizers/waveform_ribbon/live_check/20261111_load_r1_*`, `..._r2_*`,
`.artifacts/evidence/visualizers/spectrum/live_check/20261111_load_r3_*`, `..._r4_*`; receipts
`.artifacts/evidence/performance/load_session/20261111_load_session/driver_receipts.json`.

- [ ] Waveform Preset 4 is still over the 8 ms render budget under game60 on the worker (10.4 ms median,
  `reflection` 1.7 and `ribbons` 1.9 ms the largest stages): a P3 input (item 8b, N5.4), not a P2 fault.
- [ ] Side defect, `tools/visualizer_live_check.py`: on the worker run with a Settings round trip the age chain's
  medians are nonsense (`publish_to_swap_ms` and `consumed_age_at_sync_ms` medians about -48,500 ms, p90 sane):
  records from before and after the round trip (a new worker generation, a different clock origin) are mixed.
  Report ages per generation, or only for the steady window before the first round trip as the help text says.
- What the ten minutes did not cover is in the Watchlist ("Load runs the 11 Nov session did not cover").

### Item 8. §8 Accepted-mode follow-ups

- The brief Bubble performance-parity check: its boxes are in section 8.

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
  on the native core only (was N1.5).
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

**State, 14 Nov (audit):** N0's contracts are decided, and N0.3, N0.6 and N0.7 are proved (D6 and D9 accepted). N1.6
is merged to ratchet 24 (Neon Lake, Extruded Spectrum and Sphere open). N2.1 (the product module's build), N2.2 (hosts
and frame driver), N2.4 (the composite node) and N2.6 (the GPU timer) are merged and proved (the D3D window rounds with
the displays on); N2.3 (Spectrum's native schema and the C++ packet reader) is merged and proved at module ABI 5. N2.7
and its first leftovers are merged; N2.8's pre-check on Display 1 is done; N2.5 is in flight.

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
- [ ] N0.6 D6's proof (harness rounds 1 to 6 merged 12 Nov; the record is D6's "As proved" in the decisions document;
  evidence `.artifacts/evidence/native_core/n06/`): our instance and device (Qt's feature set, API 1.2) host Qt Quick
  pixel-identical to Qt's own device; teardown order, resize and the second queue in Qt's family proved over cycles;
  the driver keeps 3 handles per VkDevice (ours add none); a translucent Vulkan window gets PRE_MULTIPLIED on NVIDIA
  with alpha intact in Qt's grab. Owed:
  - Validation layer installed 12 Nov with the operator's yes: Khronos's Windows build from the nightly release of
    KhronosGroup/Vulkan-ValidationLayers (`Validation_Layers_Windows_64.zip`, 6,367,674 bytes, sha256
    1d65db0662b448af422c756609b472274a96998bc473a44bf514e353956da95d, published 12 Nov 08:09 UTC; the tagged SDK releases
    carry Android binaries only), in `D:/Temp/Scratch/SRPSS/native_spike/validation_layers/extracted/`, given to the
    harness process alone with `--layer-path` (no registry entry, nothing persistent).
  - Validation clean 12 Nov (N0.7 build round 4, 7750374e: device, lifecycle and jobs rounds PASS with the layer;
    translucent, retire and rest PASS in round 3) apart from Qt 6.12.0's own defects, each excused only by its id,
    text and Qt caller (`run_n06.py` `QT_DEFECTS`; owners and sources in `Native_Core_N06_N07_Qt_Facts.md` section I):
    A (`QVkTexture::create` PREINITIALIZED with optimal tiling), B (`createOffscreenRenderPass` without an external
    dependency, only with non-preserving targets), D (Qt Quick's `grabWindow` on Vulkan, grab phases only). C
    (`toVkAccess(TexColorOutput)` write-only) is avoided by priming targets at creation and after every readback and
    is never excused.
  - [ ] The A excuse is removed when the project takes the next Qt 6.12 patch release (the branch head already uses
    `UNDEFINED`): the upgrade's rerun deletes A from `QT_DEFECTS` and every round is clean without it.
  - [ ] The harness fails closed: `run_n06.py` and `run_n07.py` take `--require-validation`, the lead's default from
    now on; a round whose layer did not load is a FAIL, never a PASS with "owed". `VK_ADD_LAYER_PATH` is admitted
    by name only when `--layer-path` is given.
  - [ ] Decisions document: D6's "no environment variable is used" names the layer path as the one exception,
    harness only.
  - [ ] Harness first (13 Nov: `run_n06.py` has no visible mode): a bounded visible translucent round on a named
    display, then the lead's run below.
  - [ ] Lead, Display 1 visible and bounded, when two displays are connected: a real translucent window on the
    module's device: see-through to the desktop (D7 point 8's first route; the hidden runs cannot read the composed
    alpha), with the DWM system backdrop and the project's glass, then the swapchain under resize, DPI change and
    sleep and wake. If it is not see-through, D7's second route (DirectComposition) is tried next.
- N0.3's three scenes: proved 12 Nov on Vulkan (our device, validated), OpenGL, D3D11 and D3D12 (run 2, harness
  29816002, `N03 VERDICT PASS`; the record and the decided F1 to F4 are the decisions document's N0.3 "As proved"
  sections; evidence `.artifacts/evidence/native_core/n0_3/`). The clip-NDC flip through the core's own block writer
  on D3D11 and D3D12 was proved by N2.2's probe (13 Nov, `native_core/n2_2/20261113_n22_hosts`: the probe passes and
  its `clip_ndc_flip_inverted` control fails on both). Owed:
  - [ ] Metal: the three scenes on Metal (Watchlist; no Metal machine).
- N0.7 D9's proof: proved in the harness and accepted 12 Nov (the verdict, jobs for compute on this vendor and
  uploads, is D9's "Accepted by the lead"). Owed, with the Qt 6.12 checks filed here:
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
    - Colour and card edges on Qt 6.12, lead's D1 run 12 Nov (`20261112_qt612_card_edge` against 6.11.2's
      `20261112_devcurve_card_edge_whole_logical`): every card edge still 8 solid border pixels, nothing blended, and
      the authored border colour exactly `#d2b2ff` in both (no ICC remap of an authored colour on this display).
    - [ ] Text: DirectWrite now reads a font's GASP table to choose antialiasing. Compare text crops (a widget title
      and body text, the Settings dialog via the offscreen render route) before and after; a visible change in
      weight or crispness is recorded and judged by the lead.
    - [ ] QML required properties now fail instead of building silently: grep every run's log for "required
      property" and QML component errors after the bump (the next D1 run and the next hidden-window test run);
      each hit is fixed at its component.

**N1. Every shader portable, in the existing OpenGL renderer (no C++; can start now)**

- D4 landed (D4.1 to D4.8 merged 12 Nov, evidence `.artifacts/evidence/native_core/20261112_d4/`): no 64-bit type
  in either drift program; exact Dekker products instead of `fma` (`qsb` turns `fma` into HLSL `mad`, which may round
  twice); baked for SPIR-V, GLSL 430, HLSL 5.0 and MSL 1.2; the readiness check discovers compute sources
  and bakes every target (`LEGACY_GL_ONLY` now 16); full specks 0.279 to 0.050 ms GPU and 3.89 to 0.34 ms CPU
  submit; the worst 4K difference 1.4 px at the near plane (the old `double` path 1.3 px; both keep float32
  displacement); the stream ring sized to the chain count; a warm-up self-check of the pair arithmetic.
- [ ] The beads at the near plane: D4.4's 1.4 px bound is geometric; check the bead shader's near culling and the
  near layer's defocus before the bound is quoted as visible error.
- [ ] Verify the drift programs through fxc/dxc and the Vulkan backend when the native core first runs them
  (D4.7's self-check reports a compiler that breaks the pairs). Other vendors are best effort, never tested.
- [ ] Side defect: `tools/gl_object_ledger.py:84` records only names a create call returns; objects created through
  out-parameters (`glCreateBuffers(1, arr)` in `scene3d/stream.py`, `population.py`, the defocus targets) are
  invisible to the lifecycle tests: record those too, with a test.
- [ ] Side defect: `waveform_ribbon.py:54` (`0.5*(clip.z/clip.w+1.0)`) and `scene3d_spheres.py:197` assume OpenGL's
  -1..1 depth: route both through `viewDepthFromDepthTexture`/the include before matrices are corrected at upload.
- [ ] N1.4's remainder (the include and its use across the substrate, Waveform and Extruded Bubble landed, above):
  - [ ] Per-pixel hash seeds still read raw `gl_FragCoord` (`gl_programs/fog_volume.py:165,289`,
    `reflection.py:84`, `extruded_bubble_program.py:545`): through `fragPixel`, so the dither is the same texel on
    every backend and a port's Vulkan record is not compared across two noise patterns. Bit-identical in OpenGL.
  - [ ] Extruded Spectrum's and Sphere's backdrop uv (`extruded_spectrum_program.py:415`, `sphere_voxel.py:658`)
    and the four 2D shaders (`gl_FragCoord.xy - u_viewport_origin_px`), each with its N1.6 group. Spectrum's group
    merged without it (`spectrum.frag:521` still reads raw `gl_FragCoord`): Spectrum's is owed before N2.5.
  - The eight scene composites in `scene3d/target.py:125-286` (and their oriented forms) keep raw `gl_FragCoord`
    and are never converted: D5.2 replaces them with a texture node.
- [ ] N1.6 Loose uniforms into blocks across the renderer (838 `glUniform*` call sites; `qsb` needs blocks), each
  group pixel-identical in OpenGL before and after and with GL calls per frame recorded before and after (fewer
  calls is a gain today); `.qsb` baked for every backend, not `--glsl 460` only; each group leaves the readiness
  ratchet in the same change. A group whose conversion is not pixel-identical inside one dispatch is converted at
  its port instead. Order: by first consumer on the ladder, not N5's order. Merged 12 Nov (ratchet 197 to 95): the
  substrate step, Spectrum, the seven fullscreen transitions, the item-quad transition families, the Quick hosts and
  Waveform Ribbon; 13 Nov (ratchet 95 to 40): the motion and trail family and its transitions, `bind_frame`'s loose
  branch deleted, Waveform's fog, and the 2D modes (the substrate was already done on 12 Nov); 13 Nov (ratchet 40 to
  24, a5648806): Extruded Bubble's defocus layer, probe prefilter, fullscreen passes, particles and wake trails.
  Open (this is the one home of the remainder; ratchet 24):
  - The coverage gap is closed (14 Nov): `conventions_identity` records variants `a` and `b` and, with `--offers`,
    every Choice offer (129 runs for all modes; `tests/test_conventions_identity_runs.py`); every N1.6 merge
    (611ae065, 1d1816d8, 0a508242, 580cedc1, a5648806) re-proved ALL IDENTICAL at that set, first parent against
    merge (`.artifacts/evidence/native_core/n16_reprove/20261114/`). New conversions and ports prove at that set.
  - [ ] Extruded Spectrum, then Sphere (Medium). Neon Lake merged 14 Nov (114bfbcd, ratchet 24 to 17); its basin
    (`NEON_VERTEX_SOURCE`/`NEON_FRAGMENT_SOURCE`, one 8-bit level on 2-6 pixels with Glass on its block) and
    Extruded Bubble's traced glass convert at their ports (`NEON_BLOCK` is kept as the basin's layout).
  - `rendering/gl_programs/lighting.py` belongs to N4.m: it is not a product shader (no `#version`; only its test
    draws it), and a program that includes it converts it (a 3088-byte block, about 3 KB of resources).
- [ ] D5.3's formats service, its one listed use: the scene target's multisampled velocity attachment
  (`scene3d/target.py`, RG16F kept; RGBA16F would add 127.5 MiB per 4K display at 4x, 255 MiB at 8x). Built with the
  substrate when the scene target ports (N3), or reconsidered if N1.8's resolve-first rule removes the multisampled
  velocity.
- [ ] D5.6 row 13's control was not run: fill the widened targets' unused channels with non-zero values in a test, so
  a consumer that reads them fails (the scan and source checks show only `.rg`/`.xy`/`.rgb` reads today).
- [ ] Side defect: `rendering/quick/visualizer/implementations/bubble_ambient_gl.py:421` restores the caller's program
  unconditionally; a program deleted while current makes the restore raise `GL_INVALID_VALUE` (hit by the harness;
  production's Quick program is live): restore only a live program, with a test.
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

- [ ] N2.2 leftovers (N2.2 proved 12-13 Nov: `native/core/python/host_check.py`, N22 VERDICT PASS on all four
  backends; lifecycle facts J1 to J4 in `Native_Core_N06_N07_Qt_Facts.md`):
  - [ ] An OpenGL hidden host is created once and kept (Qt's threaded render control keeps 2 handles and 1 USER
    object per create and destroy, J1). The N2.7 backend owner and every hidden-host user hold this rule, with a
    test that counts creations.
  - [ ] The hidden host's Qt Quick target keeps its contents between frames (defect B). A hidden host with
    transparent content must clear what Qt Quick does not cover; decide that when the first such host exists.
  - [ ] The `QT_DEFECTS` rule is copied in `native/core/python/vk_validation.py` and the spike's `run_n06.py`:
    one source, or both edited when defect A's excuse goes at the next Qt patch.
- [ ] N2.3 leftovers (N2.3 proved 14 Nov: N23 VERDICT PASS on the GitHub-built ABI-5 module,
  `native/core/python/packet_reader_check.py`; evidence `.artifacts/evidence/native_core/n2_3/20261114_n23_reader/`):
  - [ ] A refused payload takes the normal failure path (reconfigure once, then in process for the run), but
    retrying cannot cure a refusal (writer and reader disagree on the contract). Fail it closed for the run, as the
    capacity violation does, with a test.
  - [ ] Side defect: `PacketMailbox.peek` caches the frame it peeked (`packet_mailbox.py` `_read`, about :285), so
    peek, publish, take hands out the older frame once; the in-process mailbox hands out the newest. Fix with a
    test that fails on the old code.
  - [ ] D1's "close during copy" with a paused copy has no test hook (the view's pinning is shown instead). Add the
    hook with N2.5's render-thread retire job, which is the reader's first user.
  - [ ] Audit 14 Nov lows (`Docs/Future_Work/Audit_2026-11-14.md`): the x86-64 guard also admits ARM64EC (weakly
    ordered: refuse it); `skip_seqlock` drops three guards at once, so split it so one control isolates the
    re-read after the copy; D1's "retiring: no copy starts" gets a negative control; the drop's own watermark is
    redundant with the accepted sequence (delete it, or show a case only it catches).
- [ ] N2.4 leftovers (N2.4 proved 13 Nov: `native/core/python/composite_check.py`, N24 VERDICT PASS on all four
  backends):
  - [ ] The Glass card material on the native composite; its contract read once Glass's own native path exists.

Order inside N2 (the numbers stay stable for the documents that cite them): N2.1 to N2.4, then N2.6, N2.7, then
N2.5 (built), then N2.8, whose rehearsal closes N2.5's rule (f) and releases the Python renderer's retirement.

- [ ] N2.7 leftovers (N2.7 merged 14 Nov: `--graphics-backend=vulkan`, the owner in `rendering/quick/bootstrap.py`,
  `renderer_backends` in the registries, the remembered failed start; D10 "As built"):
  - [ ] Exits that bypass the stop: the bare `QCoreApplication.exit(1)` routes (the barrier timeout, Settings
    failures) still end the loop without waiting for the Quick windows, so on Vulkan they may still crash at exit
    (R-207 fixed every exiting stop). Prove it per route first (hidden Vulkan run); then each route releases its
    Quick windows before the loop ends (the barrier timeout cannot wait on its own barrier), with a test per route.
    Same box (audit 14 Nov): a second exiting stop during the terminal drain cancels it and quits before the
    windows retire.
  - [ ] `rendering/quick/qml/shaders/surface_material.frag:178` takes the card grain from raw `gl_FragCoord`,
    whose origin differs by backend: Vulkan and OpenGL differ by up to 8/255 inside the material card. Apply
    N1.4's `gl_FragCoord` rule, bake with `tools/regen_qrc.py --shaders`, OpenGL pixels unchanged.
- [ ] N2.5 Spectrum at parity on both backends (the port rule above; scheduled after N2.6 and N2.7, which its rule
  needs: (e) GPU time per pass is N2.6's timer, (f) the bounded Vulkan rehearsal is N2.7's path and N2.8's run).
  The Python renderer retires only after N2.8 passes. N1.6's Spectrum group is merged (`spectrum.frag` bakes);
  N1.4's raw `gl_FragCoord` in it is not. Bar coverage keeps R-197's rule: one continuous coordinate from the
  target's own pixel (`fragPixel`), and the diagonal-seam test runs on the native item. Boxes (one High dispatch;
  C++ goes through the lead's build rounds):
  - Route (agent, 14 Nov; branch `worktree-agent-ac07545e5cda02f94` until merge): N2.4's composite draws a
    `SpectrumContent` (`native/core/src/spectrum.*`) on the card's whole-device-pixel rect, recorded at
    `beforeRendering` only on an accepted or dropped frame or a card change (nothing at rest), bracketed by N2.6's
    timer; the product's `spectrum.frag` is the one fragment source. The N2.3 reader is opened on the GUI thread,
    read only at the item's sync on the render thread (D2's accept edge), marked Retiring on unbind or destruction
    and released by the render-thread retire job (D1). D10: Spectrum's `renderer_backends` gains `"vulkan"` only
    once rules (a) to (e) pass; the scene then attaches `NativeVisualizerRoute` on Vulkan. OpenGL keeps the Python
    renderer until N2.8. Built and proved at module rounds 1 and 2: `spectrum.frag` through the conventions include
    (18 runs identical), the item's contract on both backends, the seam test on the native item, rule (c), box 7's
    route, box 9 (a refused payload fails closed), the audit's reader lifetime, Studio switcher and
    foreign-before-schema.
  - [ ] Rule (a): pixel parity on OpenGL against the Python renderer at the widened run set (Spectrum: both
    variants plus 16 Choice offers). Round 2: segment mode within 1 level; bars mode up to 196 levels, with full-height
    columns at the outermost bars' outer edges and peak caps one device row off (worst frame input 328, with and
    without the mapping control). Lead decision 14 Nov: bit-exact, not a tolerance. The shader rebuilds the window
    coordinate (the item passes its target's origin in window device pixels and Python's own float32 map), so
    nothing moves at the switch. Round 3 carries it with the fine derivative. Steady frames reach at most 1 level;
    fade frames are reported apart for the lead's decision.
  - [ ] Rule (b): the same runs on Vulkan in the hidden host against native OpenGL, within a stated tolerance.
  - [ ] Rule (c): frame trace and render-thread figures beside the Python path's; zero calls holding a Python
    thread state.
  - [ ] Rule (d): Settings, Studio and engine-worker parity; Spectrum's own tests green; the diagonal-seam test on
    the native item.
  - [ ] Rule (e): GPU time per pass through N2.6's timer; nothing per frame at rest (`tools/overhead_baseline.py`).
  - [ ] N2.3's refusal leftover rides here if the item's route touches it (a refused payload fails closed).
  - [ ] Audit 14 Nov, fix-soon 3: the reader is never deleted or unmapped before the render-thread retire job ran
    (`packet_reader.cpp:239-247` unmaps in the destructor; `packet_reader_close` deletes on the caller's thread,
    safe only under the GIL). A GUI close marks Retiring and hands ownership to the retire job; a test races a GUI
    close with a render-thread read.
  - [ ] Audit 14 Nov, fix-soon 2: the Studio's mode switcher (`ui/studio/settings_link.py:620-624`) lists modes
    with no renderer on the running backend; picking one raises at `ui/tabs/visualizers_tab.py:443`. Filter it as
    the Visualizers tab does, with a test.
  - [ ] Lead decision 14 Nov (audit decision 1): a slot of another stream identity is counted foreign before its
    schema is checked, in both readers, so a stale slot never fails a native stream; a test per reader.
  - The Python renderer is deleted only once N2.8 (rule (f)) passes, in the same change as the switch.
- [ ] N2.8 Lead, Display 1: the first rehearsal (cards and Spectrum on Vulkan; no wallpaper yet).
  - Pre-check done 14 Nov (`.artifacts/evidence/display/d1_run/20261114_n27_vulkan_visible/`, displays on):
    the saver on Vulkan revealed on its first presented frame, every card drew with its material and text, and
    it exited 0 through the terminal barrier.
  - [ ] `d1_run.py`'s `grab` step reads back through OpenGL ("no current OpenGL context in afterRendering") and
    fails on Vulkan; `screen` steps work. N2.8 needs a backend-neutral grab (the window's own readback on its
    render thread through QRhi), with a test on both backends.
  - [ ] With no admitted mode renderable on the backend (before N2.5), the Visualizer card shows as a thin empty
    purple frame beside Spotify. Find its owner and decide: a card with nothing to draw fades out, never sits as
    an empty frame. OpenGL unchanged.

**N2b. The background layer, natively, and the first full rehearsal**

- [ ] Side defect: the legacy program classes' `render()` and `cache_uniforms()` in
  `rendering/gl_programs/{blinds,burn,crossfade,particle,raindrops,slide,warp,wipe}` are unused and now read
  block sources; delete them (grep first) with the readiness ratchet unchanged.
- [ ] N4.a The fullscreen pass and image sampling as a primitive.
- [ ] N3.8 The async job service (D9), built to N0.7's verdict: the job thread, self-contained jobs, the latch,
  the in-frame form; first job: a photo's upload and mips.
  - [ ] D8 row 3's gate (the contention measurement under a heavy Visualizer frame, the one limit of N0.7's proof,
    D9 point 2): p99 frame time and late frames across image changes with a Visualizer running, async against
    in-frame (Vulkan only; OpenGL runs in-frame).
  - [ ] D9 point 2, consumer (b), the warm-up class: warm-up jobs run on this service, scheduled with N3.6's
    gradual warm-up (one unit per spaced frame). Transition preparation (consumer (a)) is N5.2g's.
- [ ] N5.7a The image presenter and background as the core's background layer (D7 point 1): image ownership,
  covered-display admission and timing kept; the photo textures are the core's (the wrapped-texture bridge is
  OpenGL only and retires with the Python presenter); at rest nothing is drawn again. Proved in the hidden host
  on both backends against the Python presenter's frames, and measured against the protected retained-background
  path. It runs in the rehearsal only; production on OpenGL keeps the Python presenter until N5.2h.
- [ ] N5.7b The native backdrop pyramid (D7 points 2 to 6): from the background layer, only when it changed, only
  while demand is above zero; the full chain of levels; a texture provider `MaterialSurface` samples unchanged;
  fail closed to Normal. Cost against D7's budgets at 2560 x 1440 and 4K; stills of each material beside today's.
- [ ] N5.2a The seven transitions on the shared fullscreen pass (Crossfade, Burn, Particle, Ripple, Slide, Warp,
  Wipe) at parity on both backends.
- [ ] N5.7c Lead, Display 1: the first full rehearsal (wallpaper, a transition, cards on each material, Spectrum,
  a Settings round trip, exit, sleep and wake).

**N3. The 3D substrate core (C++; harness scenes, no mode yet)**

Numbering kept stable for the documents that cite it: N3.5 (per-pass GPU timing) moved to N2.6, and N3.8 (the job
service) is built in N2b, where its first job (a photo's upload) is needed.

- [ ] N3.1 Scene targets: colour, depth and the HDR intermediate with fixed allocations per size, resize and
  retirement; a sampled depth texture and the background capture (Extruded Bubble); a small extra target with a
  second light attachment (Bubble); single-sampled first (the parity gate), then one sampling-policy owner for
  the 3D Detail tier and a transition's own request (2x to 8x), clamped to what the device supports.
- [ ] N3.2 Mesh and buffer resources: static meshes built once and kept, dynamic buffers with dynamic offsets,
  instancing, pre-built resource bindings per ring slot (no allocation per frame), instanced quads in place of
  point sprites (Bubble, Neon Lake's marks, Waveform's sparks use `gl_PointSize`).
  - [ ] The stream ring: QRhi dynamic buffers against the persistent-mapped pair (D5.3) at the product's ring
    sizes on both backends; the pair is built only if it wins by 0.05 ms or more (D8 plus 8).
- [ ] N3.3 Compute passes: dispatch only when there is new work, storage buffers shared with draws, barriers from
  the binding access types, no readback in the product.
- [ ] N3.4 Transparency and post-processing as shared stages, each opt-in and absent from a mode that does not use
  it: depth-aware order-independent transparency, bloom and the HDR resolve, the defocus layer.
- [ ] N3.6 Lifetime: lazy creation on first use, release at retirement and at a mode switch, device loss rebuilt
  from the last packet, every state combination a pipeline built ahead and warmed gradually (Qt's pipeline cache
  file on Qt's pipelines; the core's own cache for raw ones); the working-set and GPU-memory readings of the P2
  audit rerun on it. On a lost device the Vulkan backend's `VK_EXT_device_fault` detail (vendor fault codes and
  addresses, Qt 6.12) is logged once, so a lost device on a user's machine is diagnosable.
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
- [ ] N4.e Heightfields and refined terrain meshes (the authored heightfield resource; Neon Lake's tile-refined
  basin; the grid a dynamic surface field will share).
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
- [ ] N4.i Motion blur and trails (a velocity attachment, the tile-max compute, trails and motion uniforms): five
  transitions.
- [ ] N4.j Photo and backdrop environments (`PhotoEnvironment`: ten transitions; `BackdropEnvironment`: Extruded
  Spectrum and Sphere's wallpaper reflection).
- [ ] N4.k Light shafts: the shared owner (Neon Lake today) and Extruded Bubble's own second implementation
  merged onto it, one owner (high potential); ported with Extruded Bubble, then used by Neon Lake.
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

- [ ] N5.1 Spline Curve (a fullscreen strip only).
- [ ] N5.1 Oscilloscope (a single-sampled overlay target, bloom, a ring, instanced quads).
- [ ] N5.1 Bubble (its extra target with a light attachment; instanced quads for its point sprites).
- [ ] N5.4 Waveform Ribbon (N4.b, N4.d's planar reflection, N4.f1's fog volume, its five compute passes and three
  rings, floor and pulse-rim textures; not populations): the mode over its render budget under load, measured
  against the 11 Nov load session (item 7).
- [ ] N5.6 Extruded Bubble (the drift compute of D4, transparency, HDR, the depth texture and background
  capture, the probe and defocus, N4.k, N4.g's impostors and optics; not populations).
- [ ] N4.f2 (the reduced-resolution layers; Waveform and Extruded Bubble are native), then Expanded Visualizer M6
  (4K acceptance, plan 01) may run.
- [ ] N5.5 Neon Lake (N4.e, N4.k, instanced quads for its marks, its own analytic water reflection; its reaction
  and growth are uniform arrays).
- [ ] N5.3 Extruded Spectrum, then Sphere (meshes, lighting, N4.j's backdrop environment, N4.l's silhouette
  shadows; neither uses bloom; no compute).

**N5, background track (one High slot; transitions grouped by what they share; needs are in the matrix,
section 2)**

Slots (lead, 12 Nov): N5.2a, the first group on the shared fullscreen pass, goes to Opus High, and so does each group
whose primitive is ported with it (N4.c, N4.g, N4.i, N4.j, N4.l). After that, a group whose primitive is already
native goes to Opus Medium, under the same parity proof and audit as the modes track.

- [ ] N5.2b The six with their own item-quad programs: Beam, Chromatic Shear, Liquid Lens, Melt Drip, Surface
  Tension, VHS.
- [ ] N5.2c Scene target and photo environment only (N4.j): Blinds, Cube Turn, Depth Cascade, Jigsaw.
- [ ] N5.2d Motion blur and trails (N4.i): 3D Block Spins, Crumble, Glass Shatter, Pixel Accretion.
- [ ] N5.2e Membrane, Page Curl, Exploding Tiles (N4.l).
- [ ] N5.2f Disintegrate, Volumetric Dissolve (N4.c).
- [ ] N5.2g Edge Bloom, Capillary Bloom (N4.g); their fields are the first transition preparation run as an async
  job (D9, consumer class a).
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

- [ ] After the flip, SMP's foundations first (operator, 12 Nov: "SMP foundations first after native parity, as
  you suggest"): the library, the playlists and a playback service that meets the measured audio bar
  (`Docs/Future_Work/ShittyMusicPlayer/02_ShittyMusicPlayer_Implementation_Plan.md`, gated behind `--smp` until
  its Gate M9; section 0A the prerequisite phases, 13 to 16A the operator's audio, Settings-tab, artwork,
  rearrangement and fullscreen-arrangement targets); then the question of how far to go before returning to
  modes. Reasons on record: that work closes reliably without visual sign-off, gives the Visualizer decoded
  audio with look-ahead instead of a loopback capture, and proves "one Visualizer owner, any surface". The visual
  track meanwhile finishes what is open and stays on the primitives track of item 8b.
- [ ] New modes (Reactive Liquid / Melt Pool, Concrete Rain, Usu Moonscape; section 7, lab first) are built on
  the native core only, after it.

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

The harness reproduced the stuck shape only with Qt's pointer tracking cleared artificially: the real exit path is
unproven.

- [ ] Side defect: when a hovered QML item is destroyed or left, the saver window can keep the hand or arrow
  instead of the Halo until the Halo next re-applies it.

### 1B.4 Shape instrument for Spectrum and Neon Lake (merged; contract: Visualizer_Studio.md)

- [~] `fft_to_bars` gained two helper calls per tick (`shape_bar_profile`, `lane_sample_positions`). The overhead
  baseline was re-recorded after 1B.4 merged (`tools/baselines/overhead/2026-11-11_4658981b.json`, with a Spectrum
  case): the lead confirms the two calls are in it, then deletes this box.
- [ ] Admitted later if wanted (operator's call): a pop-out larger canvas; Spline Curve's layer nodes and Voxel
  Sphere's zone boundaries on the same instrument; Shift axis lock, snapping, double-click reset.

### 1B.5 Neon Lake: all visible land is brush-editable (merged 33912e5ae; refinement round merged 11 Nov)

Contract: `Docs/Reference/Neon_Lake_Basin.md`.

- [ ] Distance-based mesh density was not built (the mesh does not know the eye, and a camera-dependent mesh
  would rebuild and pop): no render shows whether the smallest brush aliases on far land seen up close; render
  it once, and only then decide whether anything is owed.

### 1B.6 Neon Lake: smooth land reaction, Growth and Indents (merged 33912e5ae; refinement round merged 11 Nov)

Contract and measurements: `Docs/Reference/Neon_Lake_Basin.md`. The lead decides when the reactivity is good enough
(operator, 11 Nov).

- [~] Lead's reactivity verdict: watch `indents_p1_heavy1.webp` and one driven showcase per preset with Growth
  and Indents on, beside the music envelope (`tools/visualizer_replay/neon_lake_music_response.py --continuous`);
  write the verdict here (good enough, or the one thing that is still weak) before any further reaction work.
- [ ] Side defect: `tools/visualizer_replay/waveform_music_response.py:63` silently skips recordings without PCM
  (heavy1, quiet_intro*, balanced*) and the report drops those songs without saying so: name them in the report.
- [ ] Side defect: the cost probe does not count GL or Python calls inside modules loaded under alias names, so
  one-session comparisons against an old renderer have meaningless call counts: count by module object.

### 1B.7 Fullscreen Now Playing: one geometry contract with the Media widget (merged 189fbd36c; plan 01 M3c)

Contract: plan 01 M3c (what stays overlay-specific, with its reason); the old artwork-factor bridge is in
`Docs/Architecture/Persisted_Input_Compatibility.md`.

- [ ] The safe-area edge guides are no longer drawn in Fullscreen Edit (as in ordinary Edit); confirm that is
  wanted or restore them through the ordinary guide owner.
- [ ] Evidence gap: no side-by-side render of the Media widget's own Edit beside Fullscreen Edit (it needs an
  off-screen harness that drives ordinary Edit on a Media card); build it beside
  `tools/expanded_visualizer_evidence.py`.

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
- [ ] Each step: `.qsb` regenerated, the SURFACE block kept identical across its three shader files, one focused
  GPU before/after, lead pixel review on the operator's two wallpapers.

### 1B.9 Settings and Studio window corners bleed (see-through corners merged a89ce123; continues 1.9)

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

- [ ] Side defect (same cause as R-197, unchecked): Oscilloscope (`widgets/spotify_visualizer/shaders/oscilloscope.frag`
  about :352), Spline Curve (`devcurve.frag` about :262) and Bubble (`bubble.frag` about :121) threshold the
  interpolated `v_uv * u_resolution` too: render each at 840x560 and compare coverage across the quad's diagonal; fix
  any that steps with the same affine map (one helper, not three copies).
- [ ] Side defect: the presets round's `render_spectrum_evidence.py` sets `ROOT = HERE.parents[5]`, which under the
  evidence junction resolves to `D:\TEMP\Scratch\SRPSS`, not the repo: kept evidence scripts take the repository root
  from `tools/artifact_paths.py` (or an explicit argument), never from their own location.
- [ ] Round 2 was never reported: check the Bar Gap control end to end (Settings and Studio rows through the
  spec, authored into every Spectrum preset by the repair fill, the Visualizer Reference) and the whole-song
  reactivity table for the round's new presets (`response.json` in
  `.artifacts/evidence/visualizers/spectrum/presets/20261111_round2/`).
- [ ] Bar Fill ghosts read as the default look's do (operator, 8 Nov: "Those ghosts are too solid and not
  blurred."): soft, blurred, translucent, no crisp stripes or stars inside, fading sooner, and no ~1 px dark seam
  where a transparent-border bar meets its ghost (merged as 092304dc; evidence `20261108_ghost_seam`). This binds
  every Spectrum preset.
- [~] Showcase WebPs for the round's new presets exist only as the interrupted agent's drafts: re-render after
  the two looks are fixed; lead review before the operator sees them.
- [ ] Extruded Bubble: one arctic-themed preset, light and depth, not a glossy object.
- [ ] Neon Lake: three unique presets (using the shape instrument, the far-land brush and the land reactivity).
- [ ] Every preset authored through the Studio's Save To path, complete for every control (the completeness
  guard).
- [ ] One showcase WebP per preset (`release_media.py`), reviewed by the lead before the operator sees them.
- [ ] Side defect: Bar Count is admitted to 96 by the spec but `spectrum.py` clamps to 64 (`_MAX_BARS`, lines 28,
  105, 205): a higher count would draw only the first 64 bars. One owner for the maximum; render one frame at 96.
- [ ] Side defect: the segment border ring is lopsided (`spectrum.frag:914`: `<=` on one side, `>=` on the
  other): two border rows at the bottom and left against one at the top and right at card scale, and the fill
  share changes with scale. Make it symmetric; before/after at 1x and 3x on a segmented look.
- [ ] Side defect: the kick lane in mirrored layouts boosts the first bars and their mirror, which are the edge
  bars, wherever the Bass lane sits (`bar_computation.py:422-432`). It should follow the Bass lane's position.
- [ ] Side defect: Rim Glow measures distance to the square edge (`spectrum.frag:783-785`), so it facets at
  rounded tops.

### 1B.11 Theme filter in the Linked row (merged d401b3c2; contract: Settings_Theme_Architecture.md "Theme filter")

- The theme list's and the popup's scrollbars (native black/white bars in off-screen captures): 1B.14's Settings
  and Studio box.

### 1B.12 Fullscreen glyphs relative to the Visualizer's display (merged 9bb4e806c; contract: plan 01 M3c)

- [ ] A display arrangement changing while the saver runs is covered only by re-admission in tests; check it on
  the topology-replacement path.
- [ ] The Reset Camera glyph (a font character) shows coloured edge fringes in off-screen crops; confirm on a
  real display and paint it as a path like the arrows if it does there too.

### 1B.13 Hold right-click to pan the live Visualizer (merged 21da6fbc; contract: Spec.md / Contracts.md input)

- Native pointer capture on a real foreground window (tests use a stand-in capture): 1B.14's held-right pan
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
- [~] Carried from section 1A's former "Awaiting Validation" list, in the D1 sessions: the changed glyphs as
  zoomed crops; camera and child placement round trips; long fullscreen metadata and controls; material
  comparisons on native pixels.

### 1B.16 Tooling (Docs/Reference/Tooling.md, merged 12 Nov)

- [ ] Candidates to retire (Tooling.md's table; the operator keeps useful tools, so the lead judges each and deletes
  only what is dead and superseded, recording the reason): high confidence `verify_compile.py` (repo root) and
  `.github/tools/linux_smoke_dist.py` (a stale copy no workflow runs); the medium and low rows stay unless a caller
  check proves them dead.

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

### 1C.2 Display moves retarget the live Visualizer (merged d14559e9, R-194; proved with both displays visible 13 Nov)

Operator: "we do not want teardowns and rebuilds unless absolutely needed. They are a last resort." Landed: every
glyph move rebuilt the whole runtime (its chrome-less Save refused and reloaded, R-194); now the move attaches its
session to both scenes and commits in place, the owner, controller, runtime, engine worker session and revision
counter survive both directions, one fade crosses the two displays with the target prepared first (bounded 1.5 s),
and Extruded Bubble's drift history is handed over behind a GPU fence (the windows share one GL context group,
proved; a non-sharing target refuses with one error and the history restarts there). Decision in plan 01 M3c; rule
in `Docs/Guardrails/Presentation_Change_Preflight.md` ("Retarget before rebuild"); evidence
`.artifacts/evidence/visualizers/expanded/20261112_1c2_root_cause/`. Teardown remains only for a display
arrangement change, a display added or removed, the owning display lost, Settings, and corrupted-object recovery.

- Lead's two-display runs, 12 Nov (Extruded Bubble, display-wide on the MSI, the up-right glyph to the TV; the
  operator allowed Display 0 for this test; its window stayed invisible): the move works with no rebuild (the session
  commits in place, "Display move landed screen=1"; the view ends display-wide on Display 1 and the MSI shows its
  wallpaper). Evidence `.artifacts/evidence/display/d1_run/20261112_1c2_move_hidden/` and `20261112_1c2_move_visible/`.
  The recipe needs a profile whose `monitor_bindings.spotify_visualizer.screen` names the MSI (an identity binding
  outranks `monitor`; `d1_run.py --setting` cannot set it): the lead's copy is `D:/Temp/Scratch/SRPSS/profile_move/`.
- [ ] Defect: the hop's cross-display Save stalls the GUI thread 102-132 ms at the fade's midpoint (no window renders;
  the fade-in waits): `custom_layout_owner.py:954` -> `SettingsManager.set_widgets_map` ->
  `core/settings/settings_manager.py:542-552`, which re-normalises the whole Visualizer section on every widgets write
  (15-27 ms alone). Reproduce: hidden run plus `--diag gui-stall-stacks` (`20261112_1c2_move_hidden_stalls`).
  - [ ] Root cause with each part timed; the Save off the fade's critical path or made cheap at its owner (no timer
    deferral); before/after on the hidden run.
- [ ] Defect (tool): `d1_run.py:440-475` reads 4K frames back and copies them on the render thread, costing the other
  display one 57-92 ms frame per 4K grab; move the copies off the render thread (the read-back itself stays).
- Visible move confirmed with both displays visible, 13 Nov (`d1_run.py --second-display-visible`): Extruded
  Bubble expanded TV -> MSI -> TV, each landed about 2 s after the press; the hop's Save measured 64-89 ms of GUI
  stall with both displays visible (the defect above). Evidence `display/d1_run/20261113_1c2_move_both_visible/`.
- [ ] The 1.5 s preparation bound on a cold shader cache (34 units land at 1.22-1.28 s warm, close to the bound).
- [ ] A prepared neighbour redraws for as long as the pointer rests on an arrow: every published frame calls
  `feed_visualizer_prewarm` (`quick_display_visualizer_owner.py:585-588`), and `feed_prewarm` calls `update()`
  (`rendering/quick/visualizer/item.py:344-354`), also after the renderer reported prepared, so a display at rest
  renders at the Visualizer's rate with no bound.
  - [ ] Measure on two hidden hosts: frames rendered by the prepared display per second while the hover is held,
    before and after its renderer is prepared.
  - [ ] Stop feeding at the "prepared" edge (the renderer is kept, nothing is redrawn until the hop or the release);
    guard: zero updates of the prepared item across steady frames once prepared (negative control: today's feed).
- [ ] Side defect: `tests/test_visualizer_hover_transfer_native.py:61` pins UI wording (`activeTip == "MOVE TO NEXT
  DISPLAY"`): assert the tip's structure (non-empty, from the glyph's own source), never the wording.
- [ ] Side defect: `tests/test_settings_undo.py:63` and `:132`: four tests skip ("no steppable NoWheelSlider on the
  page", "no colour swatch on the page"), so they prove nothing: give them a page that has the controls.
- [ ] PyOpenGL's `GL_TIMEOUT_IGNORED` has the wrong value (`glWaitSync` rejects it): the move uses the GL spec's
  value; record it where GL constants are shared so nothing else takes PyOpenGL's.

### 1C.3 Fullscreen Now Playing: one Edit contract with the Media widget (merged 426ec4aa, R-189; accepted by the operator 12 Nov)

Contract: plan 01 M3c; evidence `.artifacts/evidence/visualizers/shared/expanded_now_playing/20261112_1c3_after/`.

- [ ] Side defect (watch): `tests/test_visualizers_fullscreen_mode_pill.py` crashed once with an access violation
  when run after overlay_settings, fullscreen_edit and overlays in one process (not reproduced with two files).

### 1C.4 Spline Curve's white lines show about one pixel into the card border (fixed and proved on Display 1, 12 Nov; R-191, R-192)

Records: R-188, R-191, R-192 (`Docs/Historical_Bugs/`), with the Display 1 and Display 0 evidence.

- [ ] The tests that open windows were not run on the merge (`test_qtquick_visualizer_clip_smoke.py`, Neon Lake's
  `actual_neon_qsg_pixels`): run them hidden at the next milestone run.

### 1C.5 Volume child control: its drop shadow was cut off sharply (fixed and merged 12 Nov, R-187; one check left)

Record: R-187 (`Docs/Historical_Bugs/`, cause, guard and evidence).

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


### 1C.8 Neon Lake: the water's edge and face lines can be hidden completely (merged 290b039b, 12 Nov)

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

### 1C.9 Sources: RSS Pools shows which pools are active and valid (rows and restyle merged 12 Nov)

Contract: `Docs/Architecture/Settings_Theme_Architecture.md` (the shared list style and the Sources pool rows).

- [ ] The marks seen with real stored health once (a D1 or frozen run of 1B.14 after a real fetch), lead review.
- [ ] Not rendered: a Mica theme; the onboarding lists keep their own style (decide whether they join the shared
  one when onboarding is next touched).
- The Sources list's scrollbars (unthemed black native bars in off-screen renders; the Themes list too): 1B.14's
  Settings and Studio box.

## 1D. Operator requests (12 Nov, evening; after the current agents pass audit)

### 1D.10 Audit of 13 Nov: what is left after its merge (14 Nov)

- [ ] C++, with the next native build round: excuse `vulkan_context.cpp:205-207`'s two messages only when Qt6Gui
  is the caller; prune `surfaces.cpp`'s window registry (`:51-54`, `:295-305`). Then the lead runs host_check, which
  also proves the new `front_face_fixed_cw` control and the Qt-only cycle verdict on the GPU.
- [ ] `tools/build_runner.py:2272`, `:2285` (`_fit_initial_window`): on a work area shorter than the content, the
  fit clamps Tk's client height without counting the native frame, so the window's bottom passes the work area by
  about 25 px. This only affects short screens; the operator's 732 px stays. Count the frame in the clamp.
  `tests/test_build_foundry_window_layout.py -k keeps_the_whole_window` is a strict expected failure until then.
- [ ] GODZIP's close joins a read-only worker for up to 10 s on the GUI thread (audit low 5). Bound the join tighter,
  or detach the result safely.

### 1D.11 Extruded Bubble side defects from N1.6 (14 Nov; Opus Medium)

- [ ] Port note (N5.6): the beads program puts its probe sampler and its `EbMaterialDrift` storage buffer
  (`extruded_bubble_program.py:1441`) both at binding 6. That collides on Vulkan's single binding namespace;
  renumber at the port.
- The traced glass converts at its port (N5.6): converted alone it differs by one 8-bit level on 1-2 pixels in
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

### 1D.14 Spectrum's rim glow: a left-side bias, and Placement and Sharpness controls (operator, 14 Nov; Opus Medium, after N2.5 merges)

The operator sees bars glow, or show a gap, on their left side, and most looks glow too softly (Organs is right).
`spectrum_rim_alpha` (`widgets/spotify_visualizer/shaders/spectrum.frag:455`) takes one `side_dist_px` (the nearer
side) and a fixed core/falloff shape (`core_end = spread * 0.35`, smoothstep feathers widened by `fwidth`). Timed
after N2.5's merge so its parity target does not move mid-port; N2.5 makes a settings-only `spectrum.frag` change
need no native build round.
- [ ] Root cause first: render bars at several bar widths and both backends, measure the rim on each side of a bar
  (left against right, in device pixels), and say whether the left bias is the shader (the side distance, the
  `fwidth` feather, a half-pixel bar origin) or the bar layout (gaps). A defect is fixed at its cause with a test
  and a historical bug entry.
- [ ] Two controls in the spec (`visualizer_mode_settings.py`, the appearance bucket, under Enable Rim Glow):
  Rim Placement (Left, Right, Both) and Rim Sharpness (a slider over the core/falloff shape). Their defaults
  reproduce today's look exactly (pixel-identical at the widened run set with the defaults); every preset gets them
  by the repair fill. Studio shows them through the spec.
- [ ] Renders for the lead: each placement and three sharpness values on real wallpapers.

### 1D.13 A pytest process dies with exit 127 in larger file sets (14 Nov; Opus Medium)

- [ ] Seen twice on 14 Nov, both before and after Neon Lake's merge (the agent reproduced it on cfbdb129):
  - the lead's 8-file run (`test_qtquick_shockwave_grid`, `test_neon_lake_renderer`, `test_neon_scene_materials`,
    `test_vulkan_shader_readiness`, `test_qtquick_visualizer_all_modes`, `test_visualizer_prepared_reveal`,
    `test_scene3d_quality_settings`, `test_conventions_identity_runs`) dies right after
    `test_a_transition_request_carries_the_tier_resolved_from_the_3d_settings`, inside or at
    `test_the_tab_writes_only_its_own_level_and_shows_what_resolves` (a `Scene3DTab`);
  - a 31-file Neon run dies in `tests/test_scene3d_target.py` after `test_the_composite_respects_an_inherited_scissor`.
  - Each file passes alone, and the quality-settings file passes beside either of its two neighbours.
  Find the object or GL state that outlives its owner (R-208's class: a slot or callback keeping a dead object,
  a context or window left current), fix it at the owner if product, else in the tests; both runs exit 0, three
  times. A historical bug entry if a product path is at fault.

### 1D.9 Linux credential encryption, port from the archived branch (Opus Medium, low priority; Linux is best effort)

- [ ] The Linux branch was deleted on 13 Nov and archived as tag `archive/linux-branch-2026-11-05`. Its one unported
  piece: Linux credentials through a per-user key in the Secret Service keyring (`core/secret_service_key.py`,
  the `core/windows/dpapi.py` rework, no plaintext fallback). Port it onto today's `dpapi.py` without changing
  Windows behaviour, with its tests and the `Linux_Plan.md` row updated.

### 1D.2 Fullscreen Visualizer display styles (merged and proved on Display 1, 12 Nov)

- Watchlist: R-192's enclosed axis. A monitor with no exterior edge on an axis whose extent is not whole at its
  DPR (the middle of three in a row; the centre of a 3 x 3 grid) keeps Qt Quick's stretch there, and Borders To
  Edge's frame shows it. `test_the_enclosed_axis_stretch_is_recorded_not_hidden` records it.

### 1.0 Rotate in ordinary and fullscreen Edit

Focused proof exists for renderer pixels at non-square extents, prepared Scene3D resources, per-mode Save/Cancel and
all Studio frame builders; the physical stage and camera remain fixed. Extruded Spectrum retains its frameless
overflow policy.

- [~] Lead review of rendered frames (off-screen for ordinary Edit, D1 run of 1B.14 for fullscreen Edit): Rotate in
  every mode except Sphere, in ordinary and in fullscreen Edit.
- [~] Lead review of zoomed glyph crops: the rectangle/quarter-turn glyph against Reset Camera.

### 1.0b Studio Rotate control

Off-screen proofs cover non-square production pixels, input transforms, preparation barriers and canonical saves.
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

Existing Settings/input/text-layout/Edit checks are green; actual Windows full-layout acceptance is still owed.

- [~] Fullscreen run on D1 (1B.14 harness), lead review of grabbed frames: Media Bar and Floating Glyphs styles.
- [~] Same run: long metadata fitting.
- [~] Same run: multiline Edit boxes and optional album, including Save/Cancel.

### 1.6 Achievement Pulse child placement

The enabled-row regression is green; other families' extent floors are static.

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
  which that view does not draw (since 1D.7 its Rotate glyph turns the expanded card outside Edit and saves at
  once). Return it, and what should each do while expanded?
- **Decision, overlays on pause:** a pause does nothing to them (by the spec, not built): Now Playing is event-only
  and has already faded after its window; with Always Show it stays up by definition. Add a fade-out on pause?
- **Decision, Audio Analysis group in the Spline Curve and Oscilloscope Studios (section 9):** keep it or hide it?
  Every offered control moves the frame (Spline Curve's; Oscilloscope's Flare and Drive, and Tone for Bar Count, Block
  Size and Input Gain), though the Oscilloscope's trace itself is the raw capture.
- **Decision, Studio clip loops (section 9):** the clips now start and end mid-song at the chosen loop points (Human
  and Growing Pains on their groove) for a seamless wrap, not at the earlier quiet-to-hot windows. Keep the seam, or
  restore the quiet-to-hot arc?

- **Changed on 11 Nov (no action needed; say only if one should go back):**
  - Now Playing (corrected 12 Nov): side handles give or take the block's size and the artwork follows on X and
    Y, as accepted on 10 Nov and as the Media widget does; the block flips with the half of the display it lies
    on, as accepted on 10 Nov; title, artist and album move as one text group with one handle; a corner drag
    grows about the top centre and Restore Size keeps the top left; its artwork border takes the Media widget's
    artwork colour, stroke and Rounded Artwork option; the safe-area edge guides are not drawn.
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
  - Widget cards on every theme: no inset panel inside the border any more (the material face reaches the
    border); on light themes the dark hairline just inside the border is gone too, and the wallpaper shows
    through the card again.
  - Settings, Linked button: on Ghost, Monochrome Frost and Smoke Quartz the checked text switched to the
    opposite pole so it reads on its pill (2.48, 3.79, 2.86 to about 5.1); the other 197 state inks are
    unchanged.
  - Spectrum presets 2 to 15 of 7 Nov are replaced (1B.10).
  - Dark themes on material cards (12 Nov): text that was under 4.5:1 is now lighter (58 themes; on Royal
    Orchard and Smoke Quartz the accent-coloured text ends up close to the plain text colour). Bars, dividers
    and icons in the accent colour are unchanged.
  - Settings lists (12 Nov): the Themes, Folders and online lists share one style (12 pt, 32 px rows); the
    Sources list's heading reads "Pools and Custom Feeds"; the window's resize grip is three solid lines.
## 3. Lead and agents: active, paused and queued work

**Agents and slots:** `Docs/Guides/Orchestrator_Handbook.md` section 1 is the one source (the lead is Opus 5.5
High; Fable 5.2 High only as a rare one-off audit at a major milestone, last used on 12 Nov for the native core's
direction; since 12 Nov evening one Opus 5.5 High for complex work, one Opus 5.5 High for audits, one Opus 5.5
Medium and one Sonnet 5.5 Medium for documents and research). The plan
holds every task in detail before dispatch: a brief is its plan item, and a report is checked against the item's
boxes (operator, 11 Nov evening). Closing before opening (operator, 12 Nov: "We do need to focus on closing tasks
with real successes ... and thus opening work chances"; on the native core having no agent: "it is
disappointing"): a slot takes no new work while its last report is unreviewed or unmerged, and a dispatch is
sized to finish inside a usage window. Which item is in flight is written at the item, never here; the native
core's state and tracks are in item 8b ("State" and "Order").

Live checklist: every open step is its own box, ticked boxes are deleted, and a landed item leaves only its `[~]`
validation steps and open side defects. Landed slices live in `Docs/Reference/Architecture_Checklist.md` (AC-01
to AC-12, A-xx audit ids), `Docs/Audits/Settings_SSOT_Audit_2026-11-07.md` (AC-17 to AC-23),
`Docs/Reference/Benchmarks.md` ("Recorded sessions") and the Historical Bugs records.

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

**Active or paused (resume each with a message to the same agent, which keeps its context and worktree):**

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
- Waveform Ribbon, 7 Nov follow-ups: the Preset 4 and 640x560 card sign-offs are decisions in section 2 (evidence
  `.artifacts/evidence/visualizers/waveform_ribbon/followups/20261107_followups/`; raw captures not kept).
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

Live checklist: every open step is its own box, ticked boxes are deleted, and a landed item leaves only its `[~]`
validation steps and open side defects.

**Slow startup (operator, 6 Nov 10:30; owners fixed, awaiting the lead's cold start)**

Evidence `.artifacts/evidence/lifecycle/slow_startup/20261106_slow_startup/`; the held-lock rule is in
`Docs/Guardrails/Performance_Optimization_Contract.md` section 5, the optional-worker start in its appendix.

- [~] D1 run (1B.14 harness): cold start with `--usage`, then the lead reads the log:
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

- [~] Lead review of the second cut.
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
  so the wait share is a number. One invisible no-load P4 run (120 s, other processes' CPU 26%) measured a 7.49 ms
  tick median (duty/GIL share 0.67, 51.7 fps, render-mode 10.9 ms); about 6 ms of each live tick is spent waiting,
  most likely for the GIL held by the render/GUI threads' Python (each wait can last a 5 ms switch interval).
  Switch-interval tuning stays banned by the Performance Optimization Contract.
  Evidence `.artifacts/evidence/visualizers/waveform_ribbon/live_check/20261107_tick_cut2_p4_noload/` (main checkout).
- [ ] Cut what the profile names, with byte-identical output (Preset 4 bit-exact with tag
  `waveform-baseline-2026-11-05`).
- The game60 re-measure of the two tick cuts is superseded on the default path: the tick runs in the engine
  worker (P2), and the 11 Nov load session measured it there (item 7). The boxes above matter for
  `--viz-in-process` only; the lead decides whether they still pay.

**Widget/Settings material appearance: Awaiting Validation**

Active density/composition work and native evidence: section 1A, items 1.7/1.9. Durable owners:
`Docs/Architecture/Card_Surface_Materials.md` and `Docs/Architecture/Settings_Theme_Architecture.md`.

- [~] D1 run (1B.14 harness), lead review of grabbed frames, in the running app:
  - [ ] The inner rim.
  - [ ] Transport, mute and volume.
  - [ ] Dark and light palettes.
  - [ ] Linked material choice.

**Widget theme legibility (open)**

- [ ] Theme the Weather detail asset icons: they remain white and become faint on pale cards.

**Extruded Bubble: a deep red ocean preset that truly matches the mock (operator 6 Nov, not urgent); second pass
done, awaiting the lead's review**

The mock is `Docs/Reference/Extruded_Bubble/Targets/Originals/Preset7Goal.png`. One preset only; the shared
controls are each dormant at 0, so no other look changes: Ember Grain, Ember Band (Water), Lit Glass
(Glass), Stream Lanes, Wake Tint (Bubbles), Hero Shell with Hero Across/Height (Lens). Details, numbers,
reactivity and cost: `Docs/Reference/Extruded_Bubble/Investigation.md` sections 72-73; evidence
`.artifacts/evidence/visualizers/extruded_bubble/deep_red_ocean_pass2/20261106_deep_red_ocean_pass2/`.

- [~] Lead review of side-by-side sheets (mock | ours, full resolution plus crops) of Preset 9 against the mock.
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

## 7. Visualizer modes (one at a time, in this order)

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
and intentionally absent from normal GODZIPs. The scene is world-first through the shared framed Perspective camera:
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

- [~] Lead review on rendered WebPs at each card size: Bubble on a tall card, a wide card and the TV card moves and
  sizes like the canonical card, and is denser on large cards.

**Side defect (found during R-170, not fixed)**

- [ ] `_apply_bubble_collision_response` smooth mode multiplies `max_disp *= 0.72` inside the per-bubble loop, so the
  in-view correction cap compounds down the list (order-dependent). Fixing it changes canonical Bubble output, so it
  needs an explicit BTF behaviour-change decision first.

**Particle glow (merged; awaiting the lead's review)**

Emitted linear light with a hot core and a monotonic halo (no dark moat), no twinkle on drifting sub-pixel cores,
cheaper ambient CPU pass. Evidence `.artifacts/evidence/visualizers/bubble/particle_glow/20261107_particle_glow/`
(`before/` vs `after/` 4x crops, flicker strips).

- [~] Lead review on the `before/` vs `after/` 4x crops and flicker strips (rendered): the particle glow.

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

Drags preview once per frame and re-show only the dragged key (`Docs/Reference/Visualizer_Studio.md` "Drags are
batched"); evidence `.artifacts/evidence/studio/drag/20261106_drag/` (per move 56 ms -> 0.07 ms on Waveform).

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
Evidence `.artifacts/evidence/studio/completion/20261106_completion/brush/`. Audio Analysis now moves the Spline
Curve, Oscilloscope, Neon Lake, Bubble, Extruded Bubble and Voxel Sphere previews on recorded clips (sensitivity sheet
`audio_analysis/`); Spline Curve normalises its body, so it barely shows, as live.

- [~] Studio run on D1 (1B.14 harness), strokes posted by messages, lead review of grabbed frames: the terrain brush
  in the Studio.

## Operator execution and evidence rules

Keep details and evidence at their focused owner, this checklist actionable, and `Index.md` / `Spec.md` navigation current.
No memory updates without an explicit request.

####################
ADDITION & SIDE QUEST BOX
Never Remove This Box. Restore It If Removed. Only Remove Contents As you place them in the active plan as real live checklist targets.
####################

###################
