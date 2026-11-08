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

Rewritten 7 Nov (evening) after the data-corruption fix (R-174), the Studio leak/close fixes, AC-01..AC-03, AC-17
and Expanded Visualizer M1 all landed. **Load runs:** game60 at most 10 minutes in total, started by the lead only
after the operator's yes on a question card; agents never run load (invisible checks without load, at most 3 min).

**Now (in flight):**

1. **Operator-reported defects first:**
   - Card surfaces (operator screenshot, 7 Nov): the Visualizer card takes the theme's material (Spectrum, Spline
     Curve, Oscilloscope); one rounded legibility panel per card (2.5 px inset, radius-following, 7:1 floor so
     faint runs keep 4.5:1); Media's transport bar, volume and mute on the material; vector transport glyphs.
     Lead-audited; merged after its gate.
   - **Studio stall, clip selection and sidecar log (merged 7 Nov after lead review):** while playing, a change whose
     replay would chase the moving instant restarts the pass (`exact_replay.PassRestart`, every Studio-backed mode),
     and the transport waits for a converging replay ("Updating…"). A clip pick names itself "analysing" at once and
     retires every other analysis (latest wins). `logs/screensaver_studio.log` records selections, analysis jobs,
     replays after a change and preview gaps. The control-hints test runs on a never-shown window (its access
     violation came from `shiboken6.delete` in the plain-orbit tests). A Sphere <-> Extruded Spectrum switch ends a
     held orbit. Operator check: edit Reaction Mode while Waveform plays; pick Human once.
2. **§7.1 Waveform Ribbon reactivity (lead, 7 Nov night; operator: "Adaptivity is the enemy").** Landed: the response
   is memoryless (no phrase-mean widening, learn gate, Breathing contrast about a mean or presence-ratio gate;
   Adaptive Response retired as a setting); the body lets go within the authored Decay (`CASCADE_SHARE`), and the raw
   path takes a fixed pre-FFT gain instead of the block peak normaliser. Travelling Pulse and Frozen Past travel as
   discrete pulse bands (operator: "a relatively small horizontal width and the full vertical width"), with Pulse
   Count (1-3 at once) and Pulse Falloff in Settings and the Studio; Frozen Past holds everything that moves the cloth
   on cloth-fixed cells, so each part stays frozen until a pulse reaches it (Preset 5 on Human: motion outside the
   pulses .002 against .46 world units/s inside); a kick the pulses cannot show goes to Kick Accent (roll, twist,
   sparks, strands); optional Freeze Deflate. Measured on eight recordings back to back against the songs' own PCM
   (Presets 1/4/5/6/7): view-amplitude correlation with loudness up against main in every mode that follows the music.
   Evidence: `.artifacts/evidence/visualizers/waveform_ribbon/memoryless_reactivity/` (`20261107_lead/`,
   `20261107_bands/`) and `.artifacts/webp/visualizers/waveform_ribbon/memoryless_reactivity/`. Operator check:
   Frozen Past (Preset 5) live, and Pulse Count / Pulse Falloff / Freeze Deflate in the Studio. Next, in order:
   - **Vocals first, remainder.** Pulse Strength is routed mid-led in every preset (operator yes, 7 Nov night; set
     through the Studio's response tuner and Save To Preset: Bass gain .5, Mids gain .8, both curve 1.3). On the
     eight recordings: Pulse Strength vs the PCM vocal band +.50 -> +.66 (Don't You See -.58 -> +.18, Rag Doll
     +.71 -> +.57), loudness tracking P1 +.45 -> +.48, P5 born swell +.50 -> +.56. Open: a kick inside sustained bass
     raises the swell 21% less (median .058 -> .046; those kicks also reach Kick Accent now); check it on the
     operator's look before tuning further.
   - **Breathing as a swell and release with proper motion** (operator: 2D Bubble's breathing is the reference;
     guide §13A). Breathing is now only a faster release in soft passages.
   - The onset reward is still sized by the bus's adaptive flux threshold (about 1 s of context: the same kick right
     after a dense passage scores .22 against .61); size it on the fixed scale.
   - Group Wave still reads close to Travelling Pulse on rendered strips (it keeps the summed travelling field; its
     sets need their own pass), and its Pulse Width is not yet the band core the other two modes use.
   - Pulse bands' colour edges read crisp at Pulse Falloff below ~1 on wide bands (Preset 5's vertical colour columns);
     judge on the operator's look whether the light's falloff should follow the geometry's broader envelope.
3. **Expanded Visualizer M2** (plan 01; merged 7 Nov, 884f5a50, after the lead's Gate 2 audit;
   next: M2b, Spectrum's width-scaled bar count, then M3), with the operator's M1 amendment: a mode switch never
   re-expands; Expanded is only ever the user's explicit request. Operator, 7 Nov evening:
   - "Full display" is the Visualizer card placed near the display extents with its border and surface kept, never
     edge-to-edge (R-63 overscan).
   - Capable modes: every mode except Sphere and Extruded Spectrum (Extruded Bubble, Spectrum, Oscilloscope, Spline
     Curve, Bubble, Neon Lake, Waveform Ribbon). Waveform Ribbon's full-display cost is recorded at M6.
   - Double-click cycling while expanded skips incapable enabled modes and stays expanded; an explicit selection of
     an incapable mode collapses.
   - Spectrum gains bars in proportion to the extra width (its own milestone after M2, with a fade at the edges).
     Operator, 8 Nov: "20% more if fullscreen and horizontal". Landed (agent branch): the expanded, horizontal card
     draws round(1.2 x) the authored bars (cap 64), resampled from the same logical frame by the renderer; the rule's
     one owner is `widgets/spotify_visualizer/spectrum_display_bar_count.py`, read from the display-wide record
     (`expanded_display`), so it switches at the fade-through's invisible midpoint. A quarter turn, the ordinary card
     and Extruded Spectrum (not expansion-capable) keep the authored count. The width-ratio DSP recompute of plan 01
     M2b stays open; it needs the hidden activation transaction (an engine bar-count change bumps its generation).
   - Operator, 7 Nov night: "Don't reach nearly close enough to the screen borders" and "Don't really hide/disable
     the widgets underneath". Landed 8 Nov (agent branch, lead-audited): the expanded card is inset only by its own
     chrome plus 2 px (14 logical px at 2560 x 1440 with canonical chrome, was 30) and draws the card's own shadow;
     the display's ordinary widgets and their shadows fade out with the card and stay hidden (one display-local cover,
     nothing retired). The operator's physical look at both is owed. Complex transitions under the takeover are M4.
   - Overlays (operator, 8 Nov; plan 01 §G/M3b, after M3): a top-left preset-name toast in Title Case and a bottom-left
     Artist/Song/Artwork now-playing, both fading very gently on change; artwork with the themed border, white text
     with a customizable font; later, cheap bright-area detection to switch the text to black. No volume rail.
     Options: any corner per overlay, Always Show, Media Controls with the now-playing (default off), an optional card
     border + theme surface (default off); all in a new Visualizers pill "Fullscreen Mode", first after Setup.
   - Fullscreen Edit (operator, 8 Nov; plan 01 M3c): merged 8 Nov (with single-axis handles and Rotate Widget
     Content). Edit entered while expanded stays expanded and edits the overlays (the toast and Now Playing's block)
     through the one Edit session; Save writes their value (and the Visualizer's turn to CUSTOM),
     other displays keep running without Edit chrome, and an unsaved draft holds Settings. Also there: Now Playing
     reveals when playback resumes (paused -> playing).
     The operator's live defects (8 Nov), merged c5cf132e (plan 01 M3c "Live defects"): Now Playing's rows fill a
     set box (the artist follows the side handles); the Volume OSD is a Fullscreen Edit part, its placement over the
     expanded card `fullscreen_overlays.volume_osd` (its ordinary placement untouched); Now Playing's controls are a
     small Media card control bar (one shared `MediaTransportBar.qml`).
     The operator's two requests (8 Nov) are built on an agent branch (plan 01 M3c "Now Playing's parts" and §G
     "Show On Hover"): (a) **Show On Hover** (Fullscreen Mode, default off, `now_playing.hover_reveal`): the pointer
     resting where Now Playing is placed fades it back in and holds it; leaving runs the reveal's own hold and
     fade-out (one passive HoverHandler's edges, no timer or polling; nothing under Fullscreen Edit). (b) **Now
     Playing's parts** (artwork, title, artist, the Media Controls bar) are its block's children in Fullscreen Edit,
     moved and sized one by one through ordinary Edit's child editor (select the block, open its child lock), stored
     in `now_playing.child_geometry`; the block is its whole overlay (the separate artwork item is gone); with a
     Card the parts stay editable inside it. The parts move within the block: it is as large as its content until
     its own side handles make room. The operator's live look is owed (the feel of the lock, a part drag and the
     hover re-fade on the real display).
     Side defect (8 Nov): `tests/test_qtquick_system_audio_osd.py::test_osd_colour_inheritance_respects_active_widget_
     theme_and_authored_overrides` fails when run after `tests/test_visualizers_fullscreen_mode_pill.py` in one
     process (passes alone; reproduced on the base): Widget Theme state leaks between the files.
   - M4 (plan 01 `02_E0_Covered_Display_Admission.md`): built 8 Nov, a covered display that already shows an image
     is left out of image batches at admission (no queue advance, decode, upload, transition or material refresh; the
     batch still closes; every display covered = edges are no-ops). Open: the GPU/render-thread measurement with
     photo changes on the other display, and the operator's two-monitor look.

**Next (admitted, in this order):**

4. Settings round-trip native residual (about 2.5-6 MB per open/close) and the Studio's about 1-2 MB per session.
5. Card legibility: 40 untouched linked mirrors below 4.5:1 (`widget.accent` on the card surfaces), and light-theme
   shadows. Theme legibility: 59 untouched dark Glass/Acrylic Settings themes fall under 4.5:1 over a bright
   wallpaper (`python tools/theme_legibility.py` lists both; details at §4 Widget card surfaces).
6. Hygiene: the hidden cross-test `tmp_path` dependency (§3), the AC-13 remainder and AC-14..AC-16.
7. One measurement session of at most 10 minutes under game60, only after the operator's yes. Owed: a second
   Waveform round, a clean Waveform P4 GC run, a Settings round-trip run, the alternated Glass/Normal pair, and the
   two-monitor outlier. Pick the most valuable runs that fit.
8. **§8 Accepted-mode follow-ups:** the brief Bubble performance-parity check.

**Then (decided 5 Nov, `Docs/Future_Work/Graphics_Backend_Decision_2026-11-05.md`):**

8b. **Universal visualizer performance architecture** (operator, 7 Nov; the Decision's addendum), started once the
   current set of fixes and optimisations lands:
   - P1: GO with conditions (7 Nov, `Docs/Future_Work/Native_Core_P1_Spike.md`, sources `native/spike_p1/`): a
     native abi3 module built against Qt 6.11.2 draws through QRhi on D3D11/D3D12/Vulkan/OpenGL standalone and
     inside Qt Quick's frame, bound to PySide6's Qt DLLs; a native render thread is unaffected by a GIL-holding Python
     thread. Part B (a C++ `QSGRenderNode` + QML type on a separate render thread) verified 8 Nov on all four
     backends. The Nuitka standalone probe passed 8 Nov on every part and backend, pixel-identical to the unfrozen
     runs (P1 doc). P1 has no open condition left besides the MSVC-runtime build guard for the production core.
   - P2: an out-of-process visualizer engine for every mode (byte-identical packets; the logical tick leaves the main
     process's GIL). Designed 7 Nov (`Docs/Future_Work/Native_Core_P2_Engine_Design.md`): P2a moves the tick and mode
     runtimes into one `WorkerType.VISUALIZER` per generation (capture and DSP stay until measured), frames cross a
     versioned C-readable seqlock triple buffer in shared memory that P3 reads directly. Landed: the packet ABI and
     the exact frame codec (work orders 1-2; every mode's production frames round-trip byte-identically; main-thread
     decode at most ~.4 ms per frame) and the in-process loopback (3: `PacketMailbox`, the logical mailbox over the
     ABI; the production owner delivers identical frames for every mode through it; the tick side imports QtCore
     only) and the worker (4: `WorkerType.VISUALIZER` under `ProcessSupervisor`; fed recorded post-DSP inputs it ticks
     frames identical to the in-process owner for all nine modes, and on every recording: 160/160 replayable pairs,
     291k frames; P2a's live input, the lossless engine snapshot, was deleted in 5.6 once P2b's live input replaced
     it; the cross-process wake and per-session label namespaces are built). Independent Fable audit, 8 Nov
     (`Docs/Future_Work/Native_Core_P2_Audit.md`): its two critical findings (a lost cross-process wake that froze the
     display; the seqlock reader accepting torn slots) and H3a/H4/H6/M2 are fixed with failing-first tests. Next, in
     order (design doc work orders): 4c measured 8 Nov: the snapshot path saves nothing for Spectrum, Oscilloscope,
     Sphere, Extruded Spectrum and Neon Lake (its capture + pickle + take cost about their whole tick) and ~1.0-1.3 ms
     for the four heavy modes, while moving DSP too would save ~.7-2.2 ms for every mode, so **P2b goes first**: the
     worker owns audio capture, DSP and the tick, the snapshot layer is deleted. Built 8 Nov: P2b slice 1 (the live
     engine on recorded PCM through its own capture callback, identical in process and in the worker) and slice 2
     (pause/resume, warm re-entry and in-session mode switch in production read order, 126 pairs, 0 mismatching;
     `VIS_SET_MODE` / `VIS_SET_DISPLAY_POWER`; per-slot identity under the seqlock, ABI 2), each audited. The Vulkan
     core's needs are in the design doc (4V); compute shaders are SPIR-V-gated by test. Work order 5 (production
     wiring): 5.1 (the worker paces its own ticks) and 5.2 with 5.3's core built 8 Nov: the production owner runs its
     Visualizer on the worker behind the code-level admission `--viz-engine-worker` (default off; off is today's path),
     the worker opens the loopback device itself, and the owner's frames on the worker equal its in-process frames for
     every mode through configure, play/pause, park/unpark and a mode switch (first gate-3 data point: the main
     process's CPU per step 0.7-1.2 ms on the worker vs 1.7-5.0 ms in process; the GUI's take+decode per presentation
     rises .2-.6 ms). 5.5 built 8 Nov with checkpoint audit 7's failure items: no control edge waits on the worker
     (replies are events; the spawn is off the GUI thread; a hung worker's edges cost 0.2 ms instead of 21.9 s), a dead
     or hung worker reaches the failure path by an event (the pipe's end, the supervisor's heartbeat), the recovery is
     bounded (one fallback in process, then faded out with requests admitted), a full wake pipe never blocks the tick,
     a device that fails to open no longer counts as a worker failure. 5.4 built 8 Nov with audit 7's A7-M1/A7-M2: the
     presentation inputs the capture reads (view records, the mode's presentation-only controls) reach the worker with
     the framed view, the reflected wallpaper completes the frames on the main side, the Fullscreen Edit envelopes
     work on the worker, and every activation in the worker loads QtCore only; the view gate is identical for the
     five 3D modes with a photograph, an orbit and a preset's Auto Rotate. 5.6 built 8 Nov: the snapshot layer is
     deleted and Bubble's spawn draws from its simulation's own generator (seeded per controller by gates and
     replays, never the process RNG; identical frames to the process-RNG version seeded alike). 5.7 built 8 Nov with
     checkpoint audit 9's A9-L1..L3: the worker process lives while an owner leases it (retired at the end of the GUI
     turn that released the last lease; held across a CUSTOM commit or a monitor change until the replacement adopts
     it; parked it costs ~0 CPU), the link is the role's one starter (the heartbeat only retires, fenced by identity),
     a session whose steps keep failing fails closed into the recovery, the supervisor reaches the display manager
     before the Visualizer is admitted, `--usage` labels the worker's CPU/RSS/threads, and every build family
     compiles the worker's package. Checkpoint audit 10's findings are fixed (8 Nov): every worker role (image workers
     included) skips `main.py`'s application imports, so a spawn from the production entry is ready in 0.29 s with
     32 MB RSS (was 1.6 s / 112 MB, Qt GUI stack loaded). Next: 5.3's rest (device changes), then 6 (gate 3).
     Operator checks for 6: a frozen build with `--viz-engine-worker` (the Visualizer on the worker), its cold spawn
     against the first configure's 6 s bound, and the worker's RSS in `--usage`. Open for 6: gate 4's open/close and
     switch counts.
     Side finding (audit 10 fixes): the negative-control half of
     `test_visualizer_owner_engine_worker.py::test_the_framed_view_the_worker_tick_reads_follows_the_owners_controller`
     (`run(False)`) failed once in a combined run of the four owner suites and passed alone and in its own file (not
     investigated; probably a presentation landing during `rig.settle()` forwards the view through `_forward_view`
     even with the metrics observer off). Make the control independent of presentation timing.
     General follow-up (checkpoint audit 9, A9-L3; not a P2b item): a reconstruction that never reveals reloads about
     every 6 s with no cap, and a refused reload leaves the owner `failed` at fade 0 with its runtime running (both as
     in process): decide a per-run reconstruction cap, or a `failed` owner that stops its runtime when its reload is
     refused.
     Side finding (5.6): `test_bubble_reactivity.py::test_group_drift_aligns_non_swirl_bubble_motion[random-x]`
     holds for only ~61% of Random Group Drift draws (2,000 seeds; Diagonal for all); it had passed on the process-RNG
     state earlier tests left behind and is seeded now. Open for Bubble's owner: what Random Group Drift should
     guarantee (an aligned axis, or none), then assert that; no retune under Bubble Temporal Fidelity without it.
   - P3: the native render core, Spectrum first as the parity proof, then Waveform Ribbon, Extruded Bubble and the rest.
   - P4: mixed-resolution soft layers in the core.

   Triggers 2 (render-thread starvation) and nearly 1 (EB at display size over 8 ms) are met. Expanded Visualizer
   M2-M5 continue meanwhile; M6 (4K acceptance) waits for P2 and the first P3 ports.

9. **SMP & Full Display:** Expanded Visualizer first
   (`Docs/Future_Work/Expanded_Visualizer/01_Expanded_Visualizer_Implementation_Plan.md`, EB only; its §0 holds the
   phase ladder and the 4K budgets), then ShittyMusicPlayer
   (`Docs/Future_Work/ShittyMusicPlayer/02_ShittyMusicPlayer_Implementation_Plan.md`, gated behind `--smp` until its
   Gate M9; its §0A holds the prerequisite phases and §13-16 the operator's audio, Settings-tab, icon/artwork and
   rearrangement targets; §16A holds the operator's fullscreen arrangement: a tiling tree with choose, swap, resize
   and split/remove, no dead sections, SMP fullscreen remembered, Settings → Layout pills Widgets and SMP). No
   Vulkan backend now: the eventual backend is a native render core on Qt Quick's Vulkan
   RHI, started only when a recorded trigger fires (full-display 4K GPU budget, render-thread GIL starvation, a
   needed capability, a platform blocker). Port-readiness rules bind all new GPU code from now.
10. **§6 Shared 3D architecture** and **§7 Visualizer modes** (Reactive Liquid / Melt Pool → Concrete Rain → Usu
   Moonscape, lab-first per §7.0) resume after Expanded Visualizer acceptance and its full-display measurements, under
   the port-readiness rules; if a trigger fires first, the native Vulkan core precedes them.

## 2. Awaiting the operator (eyes, ears, hardware, decisions; details stay at the item)

One line each; the detail and evidence live in the section named. Nothing here needs an agent until the operator
answers.

- **GitHub Remote builds (8 Nov, proven end to end):** Build Runner's third tab and
  `tools/github_remote_build.py` compile Standard/Media Center on GitHub runners, validate and publish them, and
  compile opted-in installers locally (`Docs/Guides/GitHub_Remote_Build.md`). Lead's headless run from the Build
  Runner CLI on e9bbd7a4: both remote builds downloaded, validated (manifest + PE version) and published, and both
  installers compiled locally (`release/installers/Setup_SRPSS.exe`, `Setup_SRPSS_Media_Center.exe`). The run before
  it showed the installer gate refusing a Standard installer whose presets had changed after the remote build.
  Open: the operator installing a remote-built product.
- **Read:** Bubble / Extruded Bubble "terrible performance" (6 Nov log 10:32-10:35) was our load (97-100% system CPU
  from the agents' game60 checks), not the product: on the quiet machine Bubble P1 ran 65.9 fps, tick 1.47 ms, GIL
  0.13, 3.9% late; Extruded Bubble 45-69 fps (`.artifacts/evidence/performance/live_check/20261106_live/`). Heavy load-generator runs are
  scheduled by the lead only.
- **§4 Slow startup:** a cold start with `--usage` (no `UI_CALLBACK` / `FEED_GUI_DELIVERY` line over a frame).
- **§4 Displays off:** the overnight check with the power plan's display timeout (`--frame-trace --usage`).
- **§4 Spline Curve (`devcurve`) "more alive":** eyes after the lead's review.
- **§4 Frozen builds:** open a Studio from a fresh build.
- **§4 Widget card surfaces:** eyes on the rows, the inner rim, the mute position and the 15 material themes.
- **§4 Theme materials (8 Nov):** eyes on the Settings window under the new Frosted / Mica / Smoked themes (41
  pairs, all 7 light themes reworked) and on the light themes' forged corners over a dark desktop.
- **§4 Extruded Bubble Deep Red Ocean (Preset 9):** eyes on the second pass.
- **§7.1 Waveform:** Preset 4 trade-offs of the fixed-scale v7 (sign off or ask for the tag's exact dynamics);
  Preset 7 and the Reaction Modes; Breathing; four-ribbon Preset 3; Particles; Strands; Colour/floor/mist; Fixed
  response; Floor Give; Pulse Rim; swell visibility; Travel Direction; Unified atmosphere.
- **§8 Bubble:** R-170 eyes-on (tall, wide and TV cards); Particle glow.
- **§9 Studios:** Neon Lake (`shockwave_grid`), Extruded Spectrum, Spectrum, Spline Curve and Oscilloscope Studios; the migrated Settings
  pages; Open Studio in the preset row and the Save To flow; the seamless clip loops; the chrome; the drag feel; the
  terrain brush.
- **§5 Frozen release gate:** operator-run builds and installer checks.

## 3. Lead and agents: active, paused and queued work

**Agents (operator, 6 Nov evening):** at most one Opus 5.5 high and one Opus 5.5 medium subagent at once, with the
lead as reviewer/orchestrator. Agents that already hold unfinished work may exceed this until they finish (their
context is valuable). Slots need not always be full: when the right agent is not free, queue the item here. The
one-time audit and review agents (6-7 Nov) are done; the cap applies again once no existing agent holds loaded work.

**Merged 7 Nov (lead fix audit: every regression bar fails on its pre-fix code for the reported reason):** R-174
cross-mode preset write (fails closed and logs every preset-file write), the Studio controller leak, drag controls
holding their press, the Unsaved Preset Changes prompt, R-172/R-173 teardown order, the engine-answer Studios'
"uncopyable WindowsPath" start failure (7eb09032), and the post-close repaint remedy (1cd5d9c7; open until a field
log confirms, §9). Card surfaces, the style pass and the 15 material themes are merged; their open items are in §4.

- [ ] **Learned levels still in other modes (lead audit, 7 Nov; operator: "Adaptivity is the enemy"):** the bus presence
  ratio (`musical_weight`, a 6 s running level) still gates Spline Curve (`devcurve_frame_runtime.py`), Extruded Bubble
  (`extruded_bubble_frame_runtime.py`), Neon Lake (`logical_frame_capture.py`, `shockwave_frame_runtime.py`),
  Oscilloscope and Sphere; Spline Curve divides its body by a remembered peak (`devcurve_runtime.py`, 20 s memory,
  not opt-in). Move each to absolute audibility and fixed scales, mode by mode, with continuous-play evidence.
  `tools/labs/waveform_ribbon_recorded_input.py` still uses `musical_weight` and no longer matches production.
  Also (guide pass, 8 Nov): Spline Curve's accents read a lane "above its own recent mean" (reactivity guide
  §13D), another learned-level sizing to move to a fixed scale with the rest.
- [ ] **Vocal-band scorer into the music-response tool (8 Nov):** the PCM vocal-band (300-3400 Hz) series behind the
  mid-led routing evidence and guide §2C lives only in scratch (`lead_audit/vocal_band.py`); add it to
  `tools/visualizer_replay/waveform_music_response.py` as a lane so it survives scratch pruning.
- [ ] **Side findings of the Waveform second tick cut (7 Nov, not fixed there):**
  - `capture_visualizer_logical_frame` refreezes the common style (`freeze_render_fields(_common_style(widget))`,
    logical_frame_capture.py) on every tick of every mode, ~0.02-0.04 ms; a FrozenFieldsMemo would remove it.
  - The logical-tick capture reads every Waveform control (~150 getattr) and compares the whole configuration dict
    every tick (~0.07 ms together); a settings-change token would make the no-change tick free.
  - overhead_baseline on main 4467759c counts gl 182 / py 7010 per Waveform preview frame against the 81959727
    baseline's 180 / 6987: an unattributed per-frame rise on main between those commits.
  - 11 of the 19 recordings in `logs/visualizer_recordings` lack native capture history, so the Waveform tick (PCM
    reanalysis) cannot replay them; identity proofs cover the other 8.
  - The Studio's step-state copy refuses NumPy dtype objects ("uncopyable Float64DType"); a dtype-keyed cache in a
    logical owner fails every Waveform Studio. Caught by `tests/test_waveform_studio_evaluator.py` and avoided in
    the cut (keyed by `dtype.str`); worth a line in the Studio's step-state contract.

**Active or paused (resume each with a message to the same agent, which keeps its context and worktree):**
- **AC-01 Settings tab registry: merged 7 Nov (a7f1853c).** Lead audit: its tests, copied onto main, fail there for
  the stated defects (the hidden value holder; technical values missing from the cache; the Gmail job not requeued).
  9/9 focused files pass on the merge. The branch's impact gate passed 724/726; the two failures fail on main too.
  Its side defects are recorded below and in the checklist. The rest of A-12 (the page-level Bar Appearance and
  Rainbow hidden rows) is folded into the spec by the Settings SSOT fold (AC-21).
- **Settings system and SSOT audit: done 7 Nov.** It is at `Docs/Audits/Settings_SSOT_Audit_2026-11-07.md`. The
  lead re-checked its key lines in source, and all 7 items survived; they are promoted to the checklist as Tier S,
  AC-17 to AC-23. All seven are built (AC-17 last, below).
- **Settings SSOT fold: merged 7 Nov (bd625f28).** Six items landed, each its own commit:
  - **AC-19:** Reset and Import re-derive the active Settings and Widget themes, and the Themes tab reloads.
  - **AC-22:** one MC predicate decides whether interaction is forced.
  - **AC-18:** the Technical controls are spec entries. 3090 preset fields are identical and 27/27 replay digests
    match; `technical_controls.py` is deleted.
  - **AC-21:** the shared Bar Appearance and Rainbow families are spec entries; the hidden holder and
    `shared_appearance_controls.py` are gone.
  - **AC-23:** the dead residue is removed and three disclosure schemas are retired through the bridge.
  - **AC-20:** the Particle, Blinds and Burn pages read their ranges from the transition spec.

  **Lead audit:**
  - Two of the new test files, copied onto main, fail there (30 failures, behavioural).
  - Nothing imports the deleted modules.
  - A 211-file Settings, Studio, transition, preset and lifecycle gate on the merge passed 210. The one failure was
    a source-text test left stale by AC-01 (it sits outside the registry gate's import graph); it is fixed in
    e3b28e93.

  **Visible changes for the operator:**
  - Neon Lake's (`shockwave_grid`) Kick Lane Gain is now offered: the renderer always read it.
  - The Particle radius default is 8, which is what always ran.
  - Particle Gloss Size offers 16–128, which is what the resolver admits.
  - Manual Floor's low is 0.0 everywhere.
  - Technical tooltips use the registry names.

- **Card surface acceptance pass: merged 7 Nov (afcb022a).**
  Rule: `Docs/Architecture/Card_Surface_Materials.md` 3.3 and 3.4. Each card's one legibility panel is the
  material's inner panel (2.5 px inside the border, the card's own radius less the inset, never under 2 px, floor
  7:1, which holds faint runs at 4.5:1); card-level rows and per-run plates are gone; rows stay only inside
  tiles/capsules/stats panels (2 px inside, concentric). The Visualizer card takes the baseline material with its
  Fill as tint; Media's transport bar, mute button (no inner rim) and a more transparent volume track take the card's
  material; the transport glyphs are vectors. Achievement Pulse's canvas reserves a rail for every capsule shown.
  Evidence: `.artifacts/evidence/widgets/card_surfaces/20261107_sheets/` and `20261107_controls_sheets/`.
  Side defects found (not fixed here):
  - The shared Steam mock (`build_mock_steam_view_model("achievement_pulse")`) uses field ids the card does not
    define (rarity, session); the real ids are total, latest, playtime, previous, source, selected. Fixtures built
    on it exercise capsules the runtime never emits.
  - Order pollution: run together, the 33 scene/display test files fail 4 tests (Achievement Pulse config, Gmail
    semantic actions, Media config projection, `test_baseline_follows_the_theme...`: an active theme leaks to
    'glass'); each passes alone, and main fails the same 4 in the same run.
  - The Visualizer's and the Context Menu's material are projected once per display generation
    (`_configure_quick_auxiliary`); check whether a live Style Overrides or theme change reaches them before the
    next generation as it reaches the ordinary cards.
  - The faint-run measurement covered the dark theme only; light themes (dark text, the floor lightens) are unmeasured.
- **AC-17 (theme material): landed 7 Nov (cc5b61f0).** Operator's
  choice: cards follow the theme. A linked Widget mirror now carries its Settings theme's backdrop material
  (`widget_counterpart_for_settings_theme` projects it; 98 shipped mirrors got the one key by a fill, nothing else
  changed). Visible change: every profile on a linked "[Glass]"/"[Acrylic]" pair with Style Overrides on Theme,
  fresh profiles included, now draws that material; the Themes tab tags Widget theme names with their material.
  Rule: `Docs/Architecture/Card_Surface_Materials.md` section 4.
- [~] **Spectrum presets 2-15: re-authored by the lead (7 Nov), awaiting the operator's eyes.** The first agent
  round failed the fidelity gate (operator: "awful"). Its looks were opaque clip-art blocks, its per-bar patterns
  turned to checkerboard and tartan, its ghost trails read as soot, and Union Jack read as tartan. That round is not
  merged; its evidence tool fix is.
  New in Spectrum:
  - **Flag sheets** in the Pattern choice: USA, Japan, UK, Jamaica, Brazil. Each is one flag over the whole field,
    revealed by the bars, with gentle cloth folds.
  - **Hue-preserving gradients:** green to red passes through yellow.
  - **Rim glow** capped at 30% of a bar's width.
  - Each has a behavioural test in `tests/test_spectrum_decor.py` with a negative control against the old rule.

  Presets:
  - **Flags:** Old Glory, Rising Sun, Union Jack, Yard (Jamaica), Ordem (Brazil).
  - **2000s apps:** Llama Whipper (the classic MP3 player's LED analyser), Bliss (XP), Lickable (Aqua),
    Glass Player (WMP11), Butterfly Buddies (MSN), Silhouette (iPod posters), Away Message (AIM).
  - **Novel:** Holo Foil, Afterburner.

  All carry Preset 1's reactivity unchanged (only look keys authored).
  Evidence: `.artifacts/evidence/visualizers/spectrum/presets/20261107_lead/` (contact sheets, motion strips, metrics, the
  authoring script). Open: the operator's eyes. Silhouette is the plainest by concept.

  **Operator, 8 Nov (twice):** first none of them ghosted; then the flat-colour ghosts under caps were "horsepiss":
  a solid line on every ghost's top, no blend, and bad colours on 2 and 6. Cause: Peak Caps draw an opaque line
  right on each ghost's faintest row, and a flat Custom colour cannot continue flag, gradient or patterned bars.
  Now (v2): caps off on 2-15, and a new Ghost Colour source **Bar Fill** makes each ghost a fading copy of its own
  bar (fill, gradient, flag or pattern, outline), as Preset 1's Rainbow Ghost continues its rainbow borders. Glass
  Player ghosts in its cyan Bar Colour, Holo Foil keeps its Rainbow Ghost; opacities sit near Preset 1's.
  Evidence (falling instants, each preset beside Preset 1 with 2x ghost-top crops):
  `D:\Temp\Scratch\SRPSS\evidence\visualizers\spectrum\20261108_ghost_v2\` (`before/`, `after/`).
  **Open (operator, 8 Nov, on v2): "Those ghosts are too solid and not blurred."** The Bar Fill ghost must read like
  Preset 1's: soft, blurred, translucent (no crisp stripes or stars inside it), fading sooner. Also a ~1 px dark
  seam where a transparent-border bar meets its ghost. Both assigned to the ghost seam/blur agent (evidence
  `20261108_ghost_seam`).
- **Waveform agent** (Opus medium, worktree `agent-af0eb2492e1e318d7`, branch `worktree-agent-af0eb2492e1e318d7`).
  **The tick cut is merged (7 Nov).** Lead audit: three realistic mutations are each caught by
  `tests/test_waveform_logical_tick_exactness.py` (a Gaussian cache key ignoring the width, one shifted grid shared
  by both directions, and a 1e-6 spring-term change). 43/43 Waveform files pass isolated on main. The game60 live
  check is owed on a quiet machine.
  **Follow-ups merged 7 Nov:**
  - **Music-vs-response check:** no mid-song kicks are muted. Group Wave shows single kicks least, and Whole Swell
    plateaus on flat loud songs, which reads as sustained.
  - **Floor first:** the lift limit is now 3 (from 1.5), and the top takes back at most 1.5. Floor contact at
    1282x1005 falls from 7–49% to 0–2.2%, with no crest above the top.

  **For the operator:**
  - Preset 4 rides about .7 higher at p90 and stops dipping into the floor.
  - On a small 640x560 card, P5 and P6 cannot fit either way: crests now graze the top on 14–47% of frames,
    against floor contact before. That is an authoring choice; no reaction was shrunk.

  Evidence: `.artifacts/evidence/visualizers/waveform_ribbon/followups/20261107_followups/` (tables, clip sheets, music traces; raw captures not kept).
  **AC-12 merged 7 Nov.** The authored clock is monotonic: `core/authored_clock.py`, with every visualizer-path
  `time.time()` converted. 88/88 replays across all nine modes are byte-identical to main.
  `tests/test_visualizer_authored_clock.py` fails on main; the lead re-ran it there for three modes. No external
  wall-clock timestamp reaches the clock path. The rule is in the visualizer change checklist §2.
  **Now on queue item 1 (the gen2 GC stalls),** which it found itself.
- **AC-09 and AC-02: merged 7 Nov (f85d84b7).**
  - **AC-09:** one card border width resolver (`core/settings/default_contract.py`) that every card and the General
    page read.
  - **AC-02:** `VisualizerHostBinding` owns construct, bind, transfer and retire, the click admissions and authored
    placement. `DisplayManager` keeps only the "which unit" decision and no longer imports the owner. Media docking
    is the descriptor's `docked_to` policy, resolved by one function for the saver and Arrange.

  **Lead audit:**
  - The new tests, copied onto main, fail there (AC-09's on behaviour; AC-02's structurally). The one-owner
    preservation test passes on both, by design.
  - 324 Arrange cases are byte-identical.
  - No file from the protected QSG/clip lineage is touched.
  - 52/52 routing, layout, parity and lifecycle files pass on the merge.

  **Left in `DisplayManager`, until a second host needs them:** the request and gesture routing that acts on the
  owner.
- **AC-03, the application-service tier: merged 7 Nov (83a4b839).** `core/application_services.py`:
  - a registry that lives across Settings and retires exactly once at terminal finalization;
  - generation leases revoked at every teardown and at the dialog's cancellation edge;
  - nothing created in Standard SRPSS;
  - a failed Settings teardown retires the services before the process exits.

  It broke each guarantee on purpose and showed each check catches it. 17/17 lifecycle, destruction, Settings and
  thread files pass on the merge. **All three SMP and Expanded Visualizer prerequisites (AC-01, AC-02, AC-03) have
  landed.**
- **Expanded Visualizer M1: merged 7 Nov (4cadce49) after the M0 receipts** (`quiet_session_20261107/2_m0_eb_baseline/`;
  862 M1, defaults-schema and capability tests pass on the merge). Next is M2 (plan 01).
  - **Capability:** `supports_expanded_display`, Extruded Bubble only; `resolve_expanded_display_capable()`.
  - **Intent:** `expanded_display_requested`, with no mode prefix, so presets and Custom never carry it.
  - **Reducer:** the pure takeover state machine in `core/expanded_visualizer_takeover.py`; its state/event table
    is in plan 01's M1 section.

  **Gate 1:**
  - 119 persistence and capability tests fail on main; the reducer tests fail on main (the module is absent).
  - Six reducer mutations each turn the tests red.
  - The import scan is clean.
  - 0 call-count differences against main across 38 overhead cases.
  - The impacted gate passed 734/735 (the Usu assets, environmental).

  **Amended by the operator (7 Nov), built on the M2 branch:** a mode switch never re-expands. Switching to an
  incapable mode clears the saved "expanded" intent once the collapse has committed (also a held intent, and a
  generation that starts on an incapable mode chosen in Settings), so a capable mode reached afterwards starts
  ordinary. The intent still survives a Settings round trip and a restart while the capable mode stays selected.
  **Overhead drift (attributed by the lead, 7 Nov): not a regression.** The +46 Python calls per Visualizer frame
  (Spectrum 757 → 803, Extruded Spectrum 1179 → 1225) arrive exactly at efea1304: AC-08's `rendering/quick/gl_query.py`.
  - AC-12 adds none: 757 before and after it.
  - Each wrapper call replaces a PyOpenGL checked getter (~2.7 µs against ~13 µs a query).
  - Control-relative render CPU fell: Spectrum 2.04 → 1.26 cf, Extruded Spectrum 3.29 → 2.12 cf.
  - The baseline is re-recorded at M0.
- **Expanded Visualizer inset amendment + M3 widget cover: merged 8 Nov after the lead's audit; the
  operator's physical look is owed** (plan 01 §0.6 and M2/M3 notes).
  - **Inset:** the expanded card sits only its own chrome inside the display (AC-09 border width + the shadow's
    displaced body + 2 px): 14 logical px at 2560 x 1440 (21 device px at 150 %), was the 30 px edge margin; its
    shadow is drawn as the card draws it (it had been magnified about five times).
  - **M3 widgets:** the expanded display's ordinary cards and their shadows fade out with the card's first half and
    are hidden (no paint, input or hover); they return exactly on collapse. Visual policy only: no family, provider
    or lease is retired, so Media's Visualizer truth and every shared backend keep their consumers; the OSD lane and
    other displays are untouched. 20 cycles: 0 lifecycle calls, QObject tree flat, no Qt warnings.
  - **Open:** the operator's look on the real display (both corrections). The now-playing HUD is its own slice after
    M3 merges (operator's respecified plan 01 §G, lead).
- **Settings round-trip memory growth (R-175): main cause merged 7 Nov (6b289cdc).** The lead audited the timing:
  the collection runs in the replacement's construction, the barrier's continuation, and with real Qt roots that
  continuation is queued on the barrier's completion timer. So it never runs inside a `destroyed` emission. 15/15 GC,
  lifecycle, destruction and Settings files pass on the merge. Still open: about 2.5–6 MB per round trip of
  unattributed native heap. Classified with the live check's new opt-in `--roundtrip-memory census[,collect][,tracemalloc][,map]`:
  - **Cause:** every round trip left its retired display generation and Settings dialog in Python reference cycles
    (wrappers of destroyed QObjects, 15 Python-owned `QQmlComponent`s, an ~11 MB heap block): ~5,200 objects and 11 MB
    a round trip, plus heap/arena growth. The RUN GC thresholds never run a deep collection (0 in 10 minutes, on main and
    before the GC change), and each reveal re-froze the garbage. Native QObject trees, GL accounting, threads, handles
    and the driver heap were flat.
  - **Fix:** `RuntimeGCPolicy.collect_retired_generations()`, once per replacement, in
    `_construct_and_start_replacement_runtime`, after the barrier(s) completed (60–90 ms, ~5,200 objects).
  - **Waveform P4, plain live check, 9 round trips:** main +22.4 MB RSS / +23.0 MB private a round trip; fix +6.3 /
    +6.9. Spectrum P1 (census): main +19.1 / +22.7; fix +6.5 / +9.1. No barrier timeouts; every reveal re-froze.
  - **Not flat yet: a smaller native residual remains, open.** Against no-round-trip controls of the same build
    (Waveform +1.8 MB RSS a minute, ~3.8 on its steady stretch, main +2.6; Spectrum +0.3), round trips every 60 s
    still add ~2.5–4.5 MB RSS each on Waveform and ~3.5–6 on Spectrum (main: ~19–20). The memory map puts it in the default native heap (+5–6 MB
    a round trip on both modes, before and after the fix); it is not Python (tracemalloc ~1 MB a round, mostly the
    harness and the probe), not retired wrappers (none survive but one dialog placeholder), not the Settings dialog
    (built and retired 12 times in isolation: +0.1–0.25 MB each), not the QML engine and its components
    (`QuickSceneFactory` 14 times: flat), and not GL accounting, threads, handles or the driver's `private_other`.
    Left: the Quick window, its GL context and scene graph, and the Visualizer's GL programs per generation. Next:
    a heap-block histogram per reveal, or an offscreen render-control loop (the Studio saw 1–2 MB a session).
  - **Test:** `tests/test_settings_roundtrip_retired_generations.py` fails on main (3 retired display generations and
    3 dialogs still reachable) and passes on the fix.
  - Evidence: `.artifacts/evidence/memory/settings_roundtrip/20261107_settings_roundtrip/`.
- **Lead, the quiet machine, 7 Nov session (stopped early by the lead; evidence
  `.artifacts/evidence/performance/quiet_session/20261107_quiet_session/<task>/receipts.md`):**
  - **Overhead baseline: done** (`tools/baselines/overhead/2026-11-07_4bb2b775.json`, 3bd18337). Against 123e1209,
    every Visualizer gains +46 Python calls a frame (AC-08), and GL calls and control-relative CPU are flat.
    Burn's +14 Python calls a frame (AC-20's per-frame spec lookup) are fixed in 0b3048b6 (407 again).
  - **M0 EB baseline: done for Gate 0's numbers** (`2_m0_eb_baseline/`). Four views (canonical, wide, tall, display)
    × idle/game60 on one monitor, plus canonical and display on two monitors. Only the display-sized view moves:
    under game60 its render mode is 8.2 ms against 4.4 at the card (over §0.7's 8 ms) and fps 64 against 73. Tick
    (5.1 ms game60, 2.7 idle) and GIL do not depend on size. Not covered: GPU `TIME_ELAPSED` (the live check has
    none), p95/p99, lease/pool counts beyond the media leases, audio-to-photo freshness, and an unexplained
    two-monitor canonical game60 outlier (48.6 fps) that was never repeated.
  - **Waveform tick cut under game60: one clean round** (`3_waveform_tick_cut/`). Round 2 overlapped the lead's WebP
    job and is tainted. Main against `946e14b3^`: tick −5 to −10 %, fps +6-12 % on P1/P4/P7. Indicative only, and
    confounded by the other 193 commits. Waveform stays far over budget under game60 (GIL >0.7, render 16-21 ms).
    Owed: a second clean round.
  - **GC freeze steady check: Bubble clean, Waveform tainted** (`4_gc_freeze_steady/`). Bubble P1, 600 s game60: no
    steady gen1/gen2, heap 180,685 frozen at reveal and 87 left. Waveform P4 (tainted): no steady gen2, 3 gen1 of
    9-11 ms. Owed: a clean Waveform P4 run, and the long run with Settings round trips.
  - **Card materials: incomplete, one Glass/Normal pair** (`5_card_materials/`). Glass costs about +16 % of a core
    on the render thread (53.7 against 37.5), with publish→swap +3 ms and hitches 2.46 against 2.05 a minute, at
    the same late %. Owed: the alternated second pair.
- **Small-defects agent (Opus medium): its first four items were merged 7 Nov (b3801f46):**
  - **AC-06:** the Studio's clip caches are bounded, and the clip parse runs off the GUI thread.
  - **Reset Camera:** in-card controls own their double-click, so it never cycles the mode.
  - **AC-04:** the active mode draws first, and a failed release is recorded once and retried at the next boundary.
  - **AC-05:** one beat-engine authority; 94 replays are byte-identical.

  **Lead audit:** the new tests, copied onto main, fail there for the stated reasons. 13/13 cross-merge files pass.
  The Studio's remaining 2–3 MB per session is native, not these caches (side defect below).
  **Second round merged 7 Nov (efea1304):**
  - **The s_hotkey exit hang:** the lead's own display-window guard caused it. Its `pytest.skip` escaped production's
    show-failure path and abandoned a running logical runtime. The guard now raises an ordinary error that
    production retires after, and still reports the test as skipped. The file exits in 9 s instead of 900.
  - **ThreadManager:** only the terminal owner's shutdown cancels every single-shot; a helper cancels only its own
    work. This is one slice of AC-13.
  - **AC-08:** one GL state-query helper on every per-frame fence, in the same order. On the node path, Python
    calls fall from 1609 to 1216 and render-thread CPU from 0.68 to 0.51 ms. Clip smoke and the render-node pixel
    tests pass, and the protected lineage is untouched.

  **Lead audit:** 10/10 guard, GL, thread and lifecycle files and 4/4 pixel files pass on the merge.
  **Third round merged 7 Nov (3a908db8):**
  - **AC-11:** Sphere and Extruded Spectrum reset to their preset home through the in-card glyph and the R key.
    Every orbiting mode now declares its reset path, inertia and wrap in `Docs/Reference/Visualizer_Reference.md`.
    The framed cameras are untouched. Home and orbit renders are byte-identical before and after (single-sample).
  - The worktree-only `test_run_matrix_harness.py` check is fixed.
  - The one-pixel `test_waveform_floor_give.py` flake is fixed: it was MSAA rasterisation noise, so the test now
    renders single-sample, and 20/20 runs pass.

  **Lead:** 35/35 camera and orbit files pass on the merge. Operator (7 Nov): Extruded Spectrum does not coast; a
  released drag stops dead (inertia stays off).
- **Settings round-trip live harness + lifecycle hygiene: merged 7 Nov (1e92abf6).**
  1. `tools/visualizer_live_check.py --settings-roundtrip AT,...` drives the real Settings path invisibly. Per
     round trip it records barrier times, generations, memory and GC thaw/re-freeze, and fails the run on a barrier
     timeout or a missing re-freeze.
  2. **Fatal-exit backstop:** terminal retirement runs once, even after a bare `exit(1)`.
  3. **AC-10:** the mode-transition deadline joins the single-shot registry.
  4. **AC-07:** unchanged writes no longer publish. Two no-edit saves drop from 38 publications to 2.

  The new tests fail on main for the stated reasons. 16/16 lifecycle and Settings files pass on the merge, and Tier 2
  of the checklist is complete.
  **Side defect found here (Gmail IMAP `LOGIN` held the Settings barrier 6.2 s): fixed on branch
  `worktree-agent-ab77df54c8fe5d4a6`, awaiting the lead's audit** (interruptible raw-socket sessions;
  `Docs/Contracts.md` Network transports).
**Queued, next free medium slot, in this order (small, bounded):**
1. **GC freeze per generation: merged 7 Nov; the live check is owed (lead, quiet machine).** The minute-ly 86–161 ms
   gen2 stalls came from the replay driver: it kept every frame under the interpreter's thresholds.
   - **The live defect:** a one-shot 45 s timer froze the startup heap once, and the first Settings visit thawed it
     for the rest of the RUN. Every later gen2 then scanned about 186k objects (37-44 ms).
   - **The fix:** every display generation is frozen at its coordinated reveal and thawed at every teardown, with
     no sweep. The barrier stays strict, judging by reference counting as for an unfrozen generation, and the timer
     is gone.
   - **Lead audit:** `tests/test_gc_freeze_per_generation.py` fails on main 3 of 4, as claimed. 16/16 GC, lifecycle,
     destruction and Settings files pass on the merge. A stale docstring that still promised a sweep is fixed.
   - **Live check:** Waveform P4 and Bubble, 600 s, game60, with `--frame-trace`, alternating main and branch. Then
     `tools/frame_trace_report.py` for gen1/gen2 pauses per hour and the heap census at the reveal. Plus one long
     run with a few Settings round trips: a re-freeze after each reveal, no barrier timeouts, flat memory, and the
     `[GC_POLICY]` lines. Commands in the agent's report; evidence `.artifacts/evidence/memory/gc_gen2/20261107_gc_gen2/`.
     The round trips now run inside the live check itself: `tools/visualizer_live_check.py --settings-roundtrip
     AT[,AT]` (real Settings path, dialog never shown) fails the run on a barrier timeout, a reveal without a
     re-freeze or an early exit. Smoke (Bubble, 40 s, no load, 10,25): both re-froze, no timeout.
   - The live 64–152 ms spikes at Waveform preset switches are not yet attributed. The live trace will show whether
     they are collections.
   - **Settings round-trip live check (lead, 7 Nov):** Waveform P4, 600 s, load none, 9 round trips.
     - **Correct:** every round trip completed with thaw and re-freeze, and no barrier timed out.
     - **But memory grows per Settings round trip, and it predates the GC change.** Rounds 2–8, measured before
       each teardown:

       | Build | RSS | Private bytes |
       |---|---|---|
       | Before the GC change (137e6587, harness adapted) | +17 MB per round trip | +19 MB |
       | Main | +24 MB | +25 MB |

     - The GC change may add a few MB through uncollected retired cycles. That is unproven and close to noise.
       (Classified since: uncollected retired cycles on both builds, R-175; fixed on the agent's branch.)
     - Evidence: `.artifacts/evidence/memory/gc_gen2/20261107_gc_gen2/live_roundtrip_wf_p4_{main,pregc}/`. Investigation: §3, the
       Settings round-trip memory agent.

**Found while landing AC-01 (7 Nov; record, not yet admitted):**
- **Dead after A-12: removed by the Settings SSOT fold (AC-18, AC-23).** Still open from that note:
  Pre-existing: `tools/flicker_test.py`'s Widgets-tab `setup_ui_only_*` modes patch
  `widgets_tab_media.build_visualizers_ui`, which no longer exists anywhere (the Visualizer left the Widgets tab at
  V7), so those modes fail at `getattr` before measuring (its mode-body stub now targets
  `spec_mode_builder.build_mode_body`, where the builders look it up).
- **SMP import scan vs the registry:** `ui/settings_tabs.py` imports the existing tabs' modules at import time (as
  the dialog did). The SMP plan's §14 bar ("no saver module is imported by opening Settings in the SMP profile")
  needs those imports moved into the builders when the SMP descriptor lands.
- **Gate note:** `tests/test_release_media.py::test_source_change_during_capture_discards_media` fails in any agent
  worktree because the operator's Usu scene originals (`assets/usu/scenes/*.png`) are untracked and exist only in
  the main checkout; environmental, not a product defect.

**Found while landing AC-09 and AC-02 (7 Nov; fixed there or recorded):**
- **Card border consumers disagreed on malformed values (fixed in AC-09).** Games You Follow drew 12 px for a stored
  NaN/inf (0 for -inf) instead of the canonical width; the Studio's live `card_style` returned nothing for a malformed
  `widgets.global`; the General page showed the canonical width for numeric text ("3.5") the cards drew. Fractional
  stored widths are still drawn as stored and shown truncated in the integer spin; a Settings save then writes the
  whole pixels (unchanged behaviour, now owned by the resolver).
- **An oversized authored Visualizer reported an off-display origin (fixed in AC-02).** With no Media card and a
  Visualizer as large as the display, the saver projected its origin and stacking obstacle at the margin (30 px off
  the display) while the presentation drew it clamped at 0. The shared placement clamps, as Arrange always did.
  Drawn pixels are unchanged; only that obstacle moves to where the card is.
- **The owner and its click admissions held DisplayManager strongly (changed in AC-02).** The owner's layout-profile
  resolver, transition-failure callback and the double/middle-click and wheel admissions were bound methods or
  closures of the manager; they now reach it through the binding's weak services and ignore a late click once it is
  gone.
- **Still in `DisplayManager` after AC-02 (not the binding's scope):** the Visualizer request and gesture routing
  that acts on the one owner (mode/preset requests, view orbit, camera reset, Edit move/scale gestures, transfer
  glyphs) and the committed-CUSTOM profile resolver `_resolve_quick_visualizer_layout_profile`. Expanded Visualizer
  M2's takeover coordinator sits beside the binding; move any of these only when a second host needs them.

**Found during the Settings SSOT fold (7 Nov; fixed or recorded by that agent):**
- **Neon Lake's Kick Lane Gain moves its frame but was never offered (fixed in AC-18).** The old Technical
  definitions' mode filter (`_KICK_GAIN_MODES`) hid it from Settings and the Studio although
  `tools/visualizer_replay/analysis_controls_audit.py` shows it moves the published frame (onset waves). Folding the
  filter into `technical_hidden_suffixes` made the audit test fail, so Neon Lake now offers it; the stored values and
  presets were always authored, so no value changes.

**Found while landing AC-03 (7 Nov; record, not yet admitted):**
- **Production never calls `engine_lifecycle.cleanup`.** The terminal path is `stop(exit_app=True)` and its barrier
  finalization (and the post-loop `finalize_after_event_loop` backstop); `cleanup()` is reached only by tests. AC-03
  retires the tier on both paths (idempotent); a change to one terminal path must check the other.

**Found while centralizing tool output (7 Nov; record, not yet admitted):**
- **Preset rollback recovery copies go to `%TEMP%`.** `core/visualizer_preset_tree.py` writes the before-images of a
  failed preset-replacement rollback to `tempfile.mkdtemp(prefix='srpss_preset_recovery_')` and names the folder in
  the error. It is user-facing recovery data in a folder Windows Storage Sense may empty and nothing ever removes;
  a location beside the preset tree (or the data root) may be intended. Product behaviour unchanged pending the
  operator's call (the test redirects it to `tmp_path`).
- **Hidden cross-test dependency on an earlier test's `tmp_path` (lead, 7 Nov):** with pytest's
  `tmp_path_retention_policy = failed` (a passing test's folder removed at its teardown),
  `test_3d_curated_preset_ownership.py::...promotes_missing_owned_temporal_and_profile_keys...[shockwave_grid]`
  (0.7 vs 0.23) and two or three `test_settings_dialog.py` tab-restore tests fail. Each passes with the default
  retention, so something process-scoped keeps a path into an earlier test's `tmp_path` (a cached preset tree or
  storage root). The setting was reverted. Find the cache and give each test its own root; this may also hide state
  leaking between tests.
- **A third evidence root lives in `Docs/`:** `Docs/Reference/Extruded_Bubble/Evidence/2026-10-20/` (ignored media,
  referenced by `Docs/Reference/Extruded_Bubble/Investigation.md`). Not part of the 7 Nov migration mapping; move it
  into the layout (`visualizers/extruded_bubble/...`) on the operator's word.
- **Dead evidence references** (the folders no longer exist; `tools/artifact_migration.py refs` lists them):
  `logs/evidence_chest/08_*` in Historical_Bugs R-53/56/57/58/59/60/62, `.artifacts/evidence/{ribbon_path,
  ribbon_frames,ribbon_strip,expanded_visualizer,oscilloscope}` and several `waveform_ribbon/wr*` folders in
  `Docs/Reference/Ribbon_Path.md`, `Waveform_Ribbon_Lab_Plan.md` and `Waveform_Ribbon_Mist_Failure_and_Replacement.md`.
  Left unchanged; prune or mark historical on review.

**Found while fixing the Settings round-trip memory growth (7 Nov; record, not yet admitted):**
- **The invisible Waveform live check grows with no round trips at all:** +7.2 MB private a minute over a 600 s run
  (fix branch, `wf_p4_no_roundtrip_fix`; ~3.8 MB a minute on the steady stretch between image steps). tracemalloc
  puts the Python share at ~1 MB a minute, mostly the harness's own per-frame lists (`tools/eb_live_phases.py`
  `_frames`, `_waveform_signals`, unbounded for the run) and the probe; the rest is native heap, unattributed. It
  bounds any round-trip slope from a 60 s schedule. Main does the same (`wf_p4_no_roundtrip_main`: +2.6 MB RSS a
  minute; branch +1.8). Next: overnight, R-97 method. The
  Spectrum P1 control (`sp_p1_no_roundtrip_fix`) kept RSS flat (+0.3 MB a minute) but private bytes jumped +476 MB
  at ~7 min, non-resident, and fell by 216 MB two minutes later: committed-not-touched memory, R-97/R-99 territory.
- **One `QWidget` wrapper of every Settings dialog outlives it:** the initial tab's placeholder
  (`ui/settings_dialog.py` `_build_tab_by_key`: `removeWidget` + `deleteLater`). Its C++ object is destroyed, no
  Python object refers to it, a full collection leaves it: shiboken keeps the wrapper. One small wrapper a round trip.
- **The Settings dialog barrier's `destroyed` callbacks outlive it in the live run:** tracemalloc shows 459
  `functools.partial` objects from `RuntimeDestructionBarrier.watch_qobject` (`engine/runtime_destruction.py:250`)
  added and kept every round trip (~36 KB; the dialog barrier watches 467 objects). Not reproduced with a bare dialog
  (298 watched, all released).
- **`QuickSceneFactory` is per display generation, not process-level as its docstring says,** and its
  `QQmlComponent`s have no QObject parent: Python owns them, so they outlive their engine for as long as their
  wrappers do (until R-175's collection).

**Naming follow-ups (naming-audit agent, 7 Nov; `Docs/Reference/Naming.md` is now generated and test-guarded):**
- **Operator's call:** Neon Lake vs Neon Lake (edit only the registry `display_name`, then run
  `tools/naming_reference.py --write`); the "Spotify Visualizer" widget label and Spline Curve's Ghost tooltip
  ("for debug visibility") are audit #6, not done.
- `tests/test_release_media.py::test_source_change_during_capture_discards_media` fails in any fresh worktree (main
  too): it needs the untracked operator originals `assets/usu/scenes/UsuScene*.png`.

**Side defects (Studio stall / clip selection fix, 7 Nov):**
- Bubble, Sphere and Extruded Bubble replay a change in one GUI-thread evaluation (no frame budget). While playing,
  the pass now restarts, so the replay is short. Paused, an edit 6 s into Human still costs one evaluation of about
  1.5 s (Bubble), 0.3 s (Sphere) or 0.2 s (Extruded Bubble), measured 7 Nov without load. Give them the frame budget
  (`ExactReplay`) or accept the cost.
- A restart still replays the clip's 2 s analysis lead-in (`clip_loop.PREROLL_S`) under the 8 ms budget. That holds
  the preview for about 0.7 s (Waveform) or 1 s (DevCurve), shown as "Updating…". A larger budget for that one
  replay would shorten it.
- `tests/test_visualizer_control_hints.py::test_lazy_visualizer_root_retains_initial_hint_capability` still builds a
  `QuickDisplayWindow` (it is never shown), which the probe rule forbids. Move it to the render-control pattern.
- `tests/test_studio_exit_every_mode.py` still calls `shiboken6.delete(...)`. The plain-orbit file's two calls left
  Qt Quick's pointer state dangling, and the next Quick window's mouse event in the same process crashed (the
  control-hints access violation). Check whether this call is safe.

**Found while building Expanded Visualizer M2 (7 Nov; recorded, not yet admitted):**
- **The engine generation cannot fence a takeover.** M1's notes said every takeover event carries the engine
  generation, but `BeatEngine._commit_activation_generation` advances generation and activation together on every
  preset and mode activation, so a preset step would have made every later takeover event stale. The coordinator
  uses its own owner-admission serial (plan 01 M2 notes). Nothing else relies on that note.
- **Extruded Bubble drift family revisions are process-global** (`extruded_bubble_drift_log._REVISIONS`): two
  identical replays in one process publish different labels, so in-process digest comparisons of EB (and the
  Studio's packet-hash proofs, if they ever replay EB twice in one process) differ for no behavioural reason. The M2
  harness numbers each replay from 1 (`fresh_drift_revisions`). A per-runtime counter would remove the trap.
- **A takeover fade completes on the publication edge only.** Like the activation fade it has no deadline: with no
  logical publication (displays off, parked) an expand or collapse in flight waits and finishes when publications
  resume. The coordinator meanwhile refuses mode requests and transfers as busy. Watch for it at M5 (display power).
- **The expanded card inherits the Visualizer card's missing surface material** (§1 item 1: the card draws a plain
  rectangle). Once the card gets the theme's material, the expanded card shows it with no M2 change.
- **Display-wide renders reach 4K device pixels per scene target** (3840 x 2160 at 150 %); M0 already measured EB's
  render-mode median over 8 ms at display size under game60. Per-mode full-display budgets stay with M6 (§0.7).

**Found while building Expanded Visualizer M3 (7 Nov night; recorded, not yet admitted):**
- **An ordinary root's initial fade runs its family's own fade from QML's default.** The host writes `fadeOpacity`
  before parenting (`OrdinaryWidgetPresentationHost._adopt_item`), but a family `Behavior on fadeOpacity` (the OSD's,
  1150 ms) is already live, so the root animates 1 -> 0 instead of starting at 0, and a `set_fade_opacity(1.0)` in
  the same turn reads the not-yet-ticked 1.0 and is skipped (`RetainedOverlayWidget.set_fade_opacity` compares
  first), so that reveal is lost. Harmless today (the startup gate is closed while generations build, and a real
  OSD reveal arrives later), but a mid-generation root with an authored fade would show a brief fade-out. The M3
  test waits it out. Fix at the host (project the initial fade with the Behavior bypassed) when admitted.
- **The overhead baseline cannot see the QML scene:** `tools/overhead_baseline.py` renders render nodes on a bare
  host, never `DisplayScene.qml`, so scene-level dormancy (M3's cover) is proven by the QObject census and the
  no-per-frame-work structure instead.

**Found while building Expanded Visualizer M3b (8 Nov; recorded, not yet admitted):**
- **Bright-area text switch (operator's long-term item, plan 01 §G):** the overlays' text is white with a soft
  shadow; over a bright Visualizer area it should switch to black. Cheap means no per-frame CPU readback (a
  `ShaderEffect` on the text sampling the already-rendered frame, or a tiny luminance probe only while an overlay
  shows). Not built.
- **A Card on a material shows the wallpaper, not the Visualizer:** the shared backdrop is the wallpaper layer only
  (`Docs/Architecture/Card_Surface_Materials.md` §3), so on Glass over an opaque mode (Extruded Bubble) the card is a
  blurred wallpaper the Visualizer hides everywhere else. It reads as a tinted panel (evidence still
  `extruded_bubble_06_card_glass.png`); the operator's look decides whether that is acceptable.
- **Right-hand corners sit further in than left ones:** they keep clear of the card's hover-revealed controls (about
  80 px from the top edge for the collapse glyph, its tip and the 3D hint; the bottom for Reset Camera, the preset
  steps and their tip). Fullscreen Edit (M3c) can move an overlay; revisit if the operator finds the gap odd.
- **Now Playing needs an admitted Media card somewhere:** it reads the Media model the Visualizer already binds;
  with Media off on every display there is no source and nothing shows (by design: no second Media source).
- **The hidden render host never waits for the GPU:** `tools/expanded_visualizer_evidence.HiddenDisplayHost.render`
  queues unthrottled frames, so the next texture upload (a glyph, a layer) waits for the whole queue (40-390 ms
  measured on the M3b scene) and time-based QML animations jump past what a test samples. The M3b tests finish each
  frame (`glFinish`); other users sampling animations should too, or the host could finish its frames itself.

**Found while building Expanded Visualizer M3c (8 Nov; recorded, not yet admitted):**
- `tests/test_visualizer_preset_glyphs.py` opens a real window (offscreen QPA hangs it), so the glyph-row agent
  could not run its updated assertion (Edit's glyphs match the card's 26 px). Port it to the hidden production host
  (QQuickRenderControl, as `tests/test_visualizer_glyph_row.py` does) and run it.
- **The expanded card's hover Edit lane stays withdrawn (operator's call if wanted back).** The rotate glyph the
  operator missed is now on the expanded card in Fullscreen Edit (plan 01 M3c, "Rotate Widget Content"); the
  ordinary Visualizer's hover lane never offered rotate. What the display-wide card still does not show outside Edit
  is that lane (Restore Widget Size, the transfer arrows), withdrawn since M2 because each edits the ordinary card's
  layout, which the display-wide view does not draw (Restore would resize a hidden card, transfers are M5).
  Returning it needs a decision on what each does while expanded.
- **A pause does nothing to the overlays (by the spec, not built):** Now Playing is event-only and has already faded
  after its window; with Always Show it stays up by definition. A fade-out on pause would need the operator's word.
- **`tests/test_qtquick_context_menu.py` fails after `tests/test_qtquick_custom_layout_owner.py` in one process**
  (two right-click tests; each file passes alone; identical on the M3c base without its changes). Likely a
  process-wide pointer-suppression deadline or input state one file leaves for the next. Not investigated further.
  The same pairing turns three `tests/test_visualizer_direct_gestures.py` tests red (Alt-wheel / Alt-drag gestures
  never begin; reproduced on e9bbd7a4 without the M3c single-axis/rotate changes, 8 Nov), so it is the same leak.
- **The overlays' Edit placeholders are fixed English words** ("Preset Name", "Track Title", "Artist"), shown only in
  Fullscreen Edit when there is nothing to show yet.

**Lead only:** merges and merge gates; the game60 live checks (card surfaces with materials on; Waveform after the
tick cut); scheduling heavy load generators; promoting checklist items here.

## 4. Runtime side requests (operator, 5 Nov; run alongside the order above)

- [~] **Slow startup (operator, 6 Nov 10:30; owners found and fixed, awaiting the operator's cold start):**the 7 s
  GUI "Feeds delivery" and the sampler's 7.2 s first sample were one `ProcessSupervisor` state lock held across a
  stuck optional child's stop/start; fixed (lock for dictionary work only, per-role lifecycle lock, a role mid-transition
  reports "not available"; `tests/test_process_supervisor_availability.py`). The engine init thread no longer waits up
  to 10 s for the OPTIONAL image_prefetch child's ready signal (10:30:10 to :20): `_start_optional_worker` queues that
  start on a ThreadManager IO worker (the required IMAGE worker keeps its inline ready wait; supervisor `shutdown()`
  aborts the wait and the engine stops the supervisor before the ThreadManager; `tests/test_optional_worker_startup.py`).
  Offline, Feeds cache delivery including the NEWS card model is 0.1-15 ms per source at 18 publishers x 40 stories, so
  the 166-240 ms `FEED_GUI_DELIVERY` lines at 10:30:40-42 are not reproduced (`_complete` excludes QML) and are treated
  as the post-block backlog on a 97-100% CPU machine. Open: confirm on the operator's next cold start with `--usage`
  that no `UI_CALLBACK` / `FEED_GUI_DELIVERY` line exceeds a frame and the first `collect_ms` is small; a prefetch
  batch asked for before the child is ready fails as "not running" (a logged `[PREFETCH]` error; no retry of that batch). Evidence
  `.artifacts/evidence/lifecycle/slow_startup/20261106_slow_startup/`.
- [~] **Displays off -> presentation pauses entirely, resumes clean (built 5 Nov; awaiting the operator's physical
  overnight check):** `core.display_power` pauses rotation, transitions, the Visualizer (parked, capture released) and
  the clock while the console displays are off (`Docs/Architecture/Compositor_Architecture.md` → Display power).
  Injected through the real window procedure, a heavy preset went from ~142% of a core / ~10% GPU / 51 swaps/s to ~4% /
  ~0% / ~0.6 swaps/s while off, and resumed with no publish or swap hole (`.artifacts/evidence/display/display_power/20261105_display_power/`). Still
  needs real hardware: leave a heavy preset (Waveform Ribbon (`waveform_ribbon`) Preset 1 or Neon Lake (`shockwave_grid`)) overnight with both displays turned off
  by the power plan, then check Task Manager CPU/GPU for the saver while dark, that wake input reaches the saver, and
  the first seconds after wake (no stale frame, jump or hitch; run with `--frame-trace --usage`). Per-monitor power is
  not observable on Windows: an HDMI panel switched off at its own button that stays enumerated keeps running.
  Confirmed on the operator's hardware 6 Nov (diagnostic log 15:06-17:14, both screens switched off at their buttons):
  no console display-off event in any SRPSS log on this machine. The MSI (DisplayPort) left the topology while off
  and was handled; the LG TV (HDMI) stayed enumerated, so screen 0 rendered at 90 fps with transitions and the
  Visualizer for ~2 h (32-37% of a core). The TV rejects DDC/CI power queries even while on, so there is no signal to
  read; the overnight check must let Windows' screen timeout turn the displays off. Operator decision 6 Nov: no
  Screens Off command (it would put the burden on the user); they enabled the power plan's display timeout and will
  report how SRPSS handles it.
- [~] **Spline Curve (`devcurve`) "more alive while keeping the flow" (second cut 6 Nov; awaiting lead review, then operator eyes):**
  loud body owns most of the drawn ceiling (big, smooth: carrier blends to its broad component instead of limiter
  triangles), kicks ride linear headroom, quiet passages take the band share's rise, swell inside the body's share,
  tick vectorised (guide §13D → DevCurve). Evidence and before/after WebPs (loud end and a quiet passage, P1/P6) in
  `.artifacts/evidence/visualizers/devcurve/reactivity/20261105_reactivity/` (`PROGRESS.md`). Open: the strongest preset's bass (Deep Blue)
  stays ~18% below pre-work main's loud RMS (a smooth wave cannot match a slope-limited triangle at the same slope);
  the quiet-passage evidence is one recording's cold start (9 kicks); a capped layer shows the swell less (it lives
  inside the body's share).
- [ ] **Waveform logical tick starves the render thread under game load (quiet-machine game60, 6 Nov):** Waveform
  P1/P4 logical tick median 8.5/8.3 ms (p90 14.4/14.0) holding the GIL 73-75% of the time, so render-mode time is
  16-17 ms and frames drop to 41-44 fps (Neon Lake 89 fps, Spectrum 90, Bubble 63 under the same load; Extruded Bubble
  5.9 ms / GIL 0.53 / 55 fps is the second case). Offline the Waveform dynamics alone are ~1.3 ms, so the live tick's
  cost is mostly elsewhere (capture, packet build, field/strand/spark work): profile the LIVE logical tick, then cut
  it with byte-identical output (Preset 4 bit-exact with the tag). This is the Graphics Backend Decision's "optimise
  the logical tick first" step before trigger 2 can be judged. Evidence `.artifacts/evidence/performance/live_check/20261106_quiet/`.
  - **Extruded Bubble part (built 6 Nov; offline proven, live re-measure open):** byte-identical cuts at the owners.
    These are the contact discovery and far-pair skip, the cluster motion and layout, the cached phase terms, steer
    with no closure, the wake fast path, the snapshot records, controls re-resolved only on a read value's change,
    a strict-equality memo for the renderer parameters, struct-packed wake floats and presentation attrs resolved
    once per spec. Every published frame matches main on 4 recordings x 6 cases (24 replays, 130,926 frames, per-frame
    digests). `tests/test_extruded_bubble_logical_tick_exactness.py` compares the output against the straightforward
    forms. The offline P1 tick (`tools/eb_logical_cost_probe.py`, paired with main) went from 2.50 to 2.13 ms median
    (p90 3.25 to 2.78), about 15%. The tick is now spread thin: contacts 0.38, wakes 0.42 (NumPy flow 0.2), the
    rest of the simulation 0.62, capture 0.45. A NumPy contact sweep measured slower in situ and was dropped.
    **Live, confirmed (lead, quiet machine, game60, before/after alternated, 2 rounds, 6 Nov 14:00):**
    | Preset | fps (r1 / r2) | late frames (r1 / r2) |
    |---|---|---|
    | P1 | 44.9 -> 45.5 / 57.3 -> 63.8 | 32 -> 24.5% / 6.0 -> 2.0% |
    | P5 | 42.3 -> 52.9 / 62.9 -> 69.2 | 36 -> 8.2% / 2.3 -> 1.5% |

    Better in every pair. The live tick is only 2-4% lower (5.3-5.6 ms, GIL ~0.5): most of it lies outside the
    simulation. Evidence `.artifacts/evidence/performance/live_check/20261106_live/` and `.artifacts/evidence/visualizers/extruded_bubble/logical_tick/20261106_logical_tick/`.
  - **Waveform, same session (main):** P1 / P4 / P7 run at 43.5 / 42.7 / 37.6 fps, tick 8.5-8.7 ms (p90 14-16), GIL
    0.75, P7 64% late frames. Waveform is now the slowest live mode.
    **Tick cut (7 Nov, 946e14b3, byte-identical; live re-measure owed).** Profile: the tick is ~1.8 ms of many small
    NumPy/Python calls (snapshot ~1.0, surge ~0.37, pulse transport ~0.2, scene ~0.1, burst admission 2-4 ms on
    admitting ticks only); no steady GIL-held C call above ~2.5 ms. Cuts: shared spring terms, cached source Gaussians
    and shifted grid, direct surge gathers, one float32 fade column, uniform_gradient for Group Wave, scene and capture
    reads resolved once per configuration/spec, RibbonMaterial's check without astuple. Identity: 31 recorded replays
    (169,136 frames, every preset and Reaction Mode, P4 included) match main frame by frame;
    `tests/test_waveform_logical_tick_exactness.py` compares against the pre-cut forms with an fp64-fade negative
    control. Offline the gain is small (P4 min-of-3 median 3.01 -> 2.94 ms on a loaded machine; quiet-machine phase
    savings ~0.1-0.2 ms). Every tick above ~16 ms offline, in both builds, is one gen2 GC (86-161 ms, about one per
    5,500 ticks): the remaining live spikes are GC, not Waveform work. Merged 7 Nov after the lead's mutation audit
    (§3). Evidence: `.artifacts/evidence/visualizers/waveform_ribbon/logical_tick/20261107_logical_tick/` in the main checkout (local, git-ignored).
    **Second tick cut (7 Nov, c31350eb, byte-identical; on its branch for the lead's audit).** Profile (sys.monitoring
    per-line, P4 replay): snapshot ~0.7 ms (packet-only terms rebuilt every tick, the HSV `%` remainders ~0.08 ms,
    the surge's broadcast gathers ~0.1 ms), capture ~0.3 ms (scene ~0.1, camera re-admission ~0.05, camera refreeze
    ~0.04, per-tick validation imports ~0.025), burst admission ~2.3 ms per admitting tick (the emitter's cloth
    evaluation continued an empty side on every in-anchor call), routing clamped every source per target. Cuts: the
    packet-only terms and surge windows once per packet (~6 Hz), crest/weight and HSV columns once per card set, exact
    remainder forms (`unit_remainder`, `sector_remainder`), take/put surge gathers, no empty-side continuation,
    sources clamped once, a camera-admission memo and FrozenFieldsMemo on the runtime, the frame's imports resolved
    once. Identity: 24 recorded replays (8 recordings with native capture history x P1/P4/P7, 130,944 frames) match
    main frame by frame; the other 11 recordings cannot be replayed by the Waveform tick on either tree. Offline
    (alternated pairs, anything_mixed2): tick median -13..-16% in the cleanest pair (P1 1.70 -> 1.45, P4 1.75 -> 1.48,
    P7 1.74 -> 1.50 ms; p90 -6..-9%), every pair faster; calls per tick 3,137 -> 2,848. overhead_baseline (preview
    render path, not the tick): branch = main (gl 182, py 7010). **Live, the tick is not its own cost:** one invisible
    no-load P4 run (branch, 120 s, other processes' CPU 26%) measured a 7.49 ms tick median (duty/GIL share 0.67,
    51.7 fps, render-mode 10.9 ms) for a tick that replays offline in ~1.5 ms. About 6 ms of each live tick is spent
    waiting, most likely for the GIL held by the render/GUI threads' Python (each wait can last a 5 ms switch
    interval). Next step (measure, not tune): record the logical thread's own CPU time (`time.thread_time`) beside the
    tick's wall time in the live check, so the wait share is a number; switch-interval tuning stays banned by the
    Performance Optimization Contract. Evidence: `.artifacts/evidence/visualizers/waveform_ribbon/logical_tick/20261107_tick_cut2/`
    and `.artifacts/evidence/visualizers/waveform_ribbon/live_check/20261107_tick_cut2_p4_noload/` (main checkout).
- [~] **Frozen builds could not open a Studio (operator 6 Nov: "module QtQuick.Controls.Basic is not installed"): fixed
  in source (6058dc7b), confirm on the next build.** The QML prune removed QtQuick/Controls, Templates and Shapes, and
  the import allowlist scanned only the saver's QML, never `ui/studio/qml`. The build now keeps the Basic style's
  closure and prunes only the other Controls styles. `test_every_shipped_qml_import_survives_the_frozen_prune` walks
  every shipped import's module and DLL closure against the prune. Open: open a Studio from a fresh build.
- [~] **Widget card surfaces: Acrylic, Glass, Frosted, Mica, Smoked (operator 6 Nov) - built and merged, awaiting the
  live check and the operator's eyes.** Design, failure analysis, invariants, cost tables and the 6 Nov style pass
  (inner legibility panel 2.5 px inside the border, full rounded rows on every list card, the Media bar's shadow and
  mute position, light-theme legibility 4.5:1+ on every material, Widget Themes naming a `surface_material` with
  Style Overrides defaulting to **Theme**, 15 new material themes): `Docs/Architecture/Card_Surface_Materials.md`
  (sections 1-6). `Widgets -> General -> Style Overrides -> Surface Material` (Normal default; all-Normal creates
  nothing; the Visualizer card and the System Volume OSD stay Normal). Evidence
  `.artifacts/evidence/widgets/surfaces/20261106_surfaces/` and `.artifacts/evidence/widgets/surfaces_style/20261106_surfaces_style/`
  (before/after crops, theme contact sheets `theme_sheet_*.png`).
  Left:
  1. **Live check under the lead-scheduled game load**, materials on, a transition-heavy run, and Normal as the
     control.
  2. **Operator's eyes:** the rows (light themes draw them as lighter bands, dark themes mostly nothing), the inner
     panel's thin rim, the mute position, the 15 new themes (contact sheets `theme_sheet_*.png`). Normal changes
     only where intended: the Media bar/artwork shadows, the mute button and Friend Pulse on light themes.
  3. **Side defect found (not caused here):** light themes keep the weather detail icons white (asset images),
     faint on pale cards; a themed icon tint would fix it. (The `tests/test_surface_materials.py` access violation
     found in the same pass is fixed: R-173, the hidden scene's GL context freed before its render control.)
  4. **Field defects (operator 7 Nov, not high priority):**
     - **The theme's material doesn't reach the cards: root cause fixed by AC-17 (on its branch).** The chain
       never lost the value: a linked "[Glass]" pair's Widget mirror named no material. Mirrors now carry it
       (binder-level bar: `tests/test_theme_pair_surface_material.py`). Left: confirm it in the running app
       during live check 1 (a "[Glass]" pair, Keep Synced, override on Theme, and the running card draws Glass).
     - **Side defect (found by AC-17, not caused by it):** 18 of the 98 linked material mirrors sit under the
       4.5:1 authoring bar the 15 material themes meet, mostly `widget.accent` on `widget.panel` (3 are the header
       label on its fill). Their colours are unchanged; only their material is new. Judge them on the live
       renders, and re-author the ones that read badly on Glass/Acrylic.
     - **Theme materials and light themes (8 Nov, agent branch, awaiting the lead's merge and the operator's
       eyes).** The Settings forged edge now paints over the content (light themes' shell covered it: square pale
       corners, no border). Settings takes Frosted, Mica and Smoked (AccentPolicy Acrylic with a derived tint; the
       DWM system backdrop stays rejected); a pair keeps one material. 41 pairs moved: all 7 light themes to
       Frosted (4) or Mica (3) with a translucent shell, 26 dark to Mica, 8 dark to Smoked; every text role of
       those holds 4.5:1 / 3:1 on its material over any wallpaper (`tests/test_theme_material_legibility_contract.py`).
       Left: a native look at Frosted/Mica/Smoked on the real HWND (offscreen renders model the blur and tint
       only), and the light themes' corner caps: they take the opaque pale title-bar colour, which shows as a
       small pale corner speck over a dark desktop (the documented camouflage rule; dark themes show the mirror
       case over a bright one). Side defects recorded at item 5 of §1: 59 untouched dark Glass/Acrylic themes
       under 4.5:1 over a bright wallpaper, 40 untouched mirrors' `widget.accent` under 4.5:1 on the card.
     - **Light themes:** the widget shadows still make widgets largely unreadable. The 4.5:1 legibility check
       measured text against its panel but not the shadow's effect. Fix the shadows, then judge the result on
       live renders.
- [~] **Extruded Bubble: a deep red ocean preset that truly matches the mock (operator 6 Nov, not urgent) - second
  pass done, awaiting operator eyes:** the mock is `Docs/Reference/Extruded_Bubble/Targets/Originals/Preset7Goal.png`.
  Preset 9 (Deep Red Ocean) only; Presets 1-8 pixel-identical. Shared work, each dormant at 0: **Ember Grain**,
  **Ember Band** (Water), **Lit Glass** (Glass), **Stream Lanes**, **Wake Tint** (Bubbles), **Hero Shell** with Hero
  Across/Height (Lens). Shells now read as lit glass, micro-bubbles as glass beads in lanes, the band runs where the
  mock's does and the top-middle is dark. Still short: shells paler and smoother inside than the mock's copper,
  busy-interior glass, and too many crowded together; embers partly along-stream strokes rather than torn debris; the
  lower right far too busy (the mock's band fades out there); the shaft corner lacks its bright glittering core; the
  Hero Shell reads as a soft ring rather than a shell full of bokeh discs; faint surface ripples at the top. Details,
  numbers, reactivity and cost: Extruded_Bubble/Investigation.md §72-73; evidence
  `.artifacts/evidence/visualizers/extruded_bubble/deep_red_ocean_pass2/20261106_deep_red_ocean_pass2/`.
- [ ] **Side defects found in the deep red ocean pass (6 Nov):** the near (defocus) layer stair-steps the rim of a
  large near shell on some frames (seen with Lit Glass off as well). Also `tools/release_media.py` cannot render
  Waveform Ribbon showcases: the replay raises "Raw musical replay requires current PCM reanalysis" because
  `replay_clip` never drives `tools/visualizer_replay/pcm_reanalysis.py`.

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
- [~] **Studio chrome matches Settings (6 Nov), awaiting the operator's look**(all Studios: one shell;
  `Docs/Reference/Visualizer_Studio.md` "Chrome and theme"). Frameless window with Settings' title bar and forged
  rounded edge, the theme's Glass/Acrylic material, 1.5 px one-path card borders, Settings' panel casts at half
  offset, viewport corners rounded over the scene. Hidden-render evidence `.artifacts/evidence/studio/chrome/20261107_chrome/`
  (before/after, Default Dark Acrylic, Matte Graphite Normal, Pearl Blush light Glass; 8x crops). Operator to check
  on screen: the live Glass/Acrylic composition of the Qt Quick window (first use of the AccentPolicy material on an
  alpha OpenGL window; the evidence only simulates the blur), snap/resize/maximise by hand, and the panel opacity
  floor (0.88) and shadow strength on light themes. Light-theme instrument wells (trace cards, response curve,
  transport bar) now sit on the theme's input surface (evidence `.artifacts/evidence/studio/followups/20261107_followups/legibility/`,
  Pearl Blush and Default Dark, before/after): operator look pending. Operator (6 Nov, not urgent): the material is
  missing from most Studio areas (workspace tabs, the panels under the preview, their section headers). Apply the
  theme's Glass/Acrylic to them with a slightly darker layer behind every control so it stays legible. Controls laid
  over the preview (transport chips, aspect chips, the source notice) keep a translucent dark solid: blurring the live
  scene behind them would cost GPU time every frame and skew what the preview shows about performance.
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