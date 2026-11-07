# SRPSS | Current Plan

Live, ordered work only. `[ ]` work remains; `[~]` a candidate exists but is unaccepted (awaiting validation, never an
implicit pass). When an item lands, delete it: completed work lives in source control and its durable contract in
`Spec.md` / `Docs/` (Reference, Architecture, Guardrails, Guides); rejected mechanisms in `Docs/Historical_Bugs/`. This
is not a changelog. Deferred, unadmitted ideas live in `Future_Work.md`.

## 0. Scope and rules

**Accepted baseline (not live work):** original Bubble, Extruded Bubble, Neon Lake, Oscilloscope,
Spectrum/Rainbow Ghost, Sphere, source routing, transitions and Foundry launch buttons. Reopen an accepted
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
registry, AC-02 Visualizer host binding, AC-03 application-service tier) is the prerequisite work for step 4 below;
the items promoted to run soon are in §3. Nothing else in it is admitted until it appears here.

## 1. Order of work (strict)

**Now (in flight):**

1. **Data-corruption fix** (§3, the Studio agent's top priority): a Neon Lake preset file was rewritten with Bubble
   values. Nothing outranks a user-data write bug.
2. **§7.1 Waveform Ribbon**: finish acceptance (already built; the only 3D mode in flight), including the logical
   tick cut (§4) and the operator sign-offs listed in §2.
3. **§9 Studio for every visualizer** (operator, 5 Nov): the controller leak, the close freeze, the close prompt,
   then the remaining operator looks.
4. **§4 runtime side requests** run alongside, and the small queued fixes in §3 fill free slots.

**Next (admitted, waits for the above):**

5. **§8 Accepted-mode follow-ups**: the brief Bubble performance-parity check is operator-admitted.
6. **Architecture prerequisites, in this order: AC-01 → AC-02 → AC-03** (`Docs/Reference/Architecture_Checklist.md`
   Tier 1). AC-01 may start at the next free high slot once the Studio leak lands (it pays off for every existing
   Settings tab now); AC-02 lands before Expanded Visualizer M2; AC-03 before SMP M2.

**Then (decided 5 Nov, `Docs/Future_Work/Graphics_Backend_Decision_2026-11-05.md`):**

7. **SMP & Full Display:** Expanded Visualizer first
   (`Docs/Future_Work/Expanded_Visualizer/01_Expanded_Visualizer_Implementation_Plan.md`, EB only; its §0 holds the
   phase ladder and the 4K budgets), then ShittyMusicPlayer
   (`Docs/Future_Work/ShittyMusicPlayer/02_ShittyMusicPlayer_Implementation_Plan.md`, gated behind `--smp` until its
   Gate M9; its §0A holds the prerequisite phases and §13-16 the operator's audio, Settings-tab, icon/artwork and
   rearrangement targets). No Vulkan backend now: the eventual backend is a native render core on Qt Quick's Vulkan
   RHI, started only when a recorded trigger fires (full-display 4K GPU budget, render-thread GIL starvation, a
   needed capability, a platform blocker). Port-readiness rules bind all new GPU code from now.
8. **§6 Shared 3D architecture** and **§7 Visualizer modes** (Reactive Liquid / Melt Pool → Concrete Rain → Usu
   Moonscape, lab-first per §7.0) resume after Expanded Visualizer acceptance and its full-display measurements, under
   the port-readiness rules; if a trigger fires first, the native Vulkan core precedes them.

## 2. Awaiting the operator (eyes, ears, hardware, decisions; details stay at the item)

One line each; the detail and evidence live in the section named. Nothing here needs an agent until the operator
answers.

- **Read:** Bubble / Extruded Bubble "terrible performance" (6 Nov log 10:32-10:35) was our load (97-100% system CPU
  from the agents' game60 checks), not the product: on the quiet machine Bubble P1 ran 65.9 fps, tick 1.47 ms, GIL
  0.13, 3.9% late; Extruded Bubble 45-69 fps (`.artifacts/evidence/live_20261106/`). Heavy load-generator runs are
  scheduled by the lead only.
- **§4 Slow startup:** a cold start with `--usage` (no `UI_CALLBACK` / `FEED_GUI_DELIVERY` line over a frame).
- **§4 Displays off:** the overnight check with the power plan's display timeout (`--frame-trace --usage`).
- **§4 DevCurve "more alive":** eyes after the lead's review.
- **§4 Frozen builds:** open a Studio from a fresh build.
- **§4 Widget card surfaces:** eyes on the rows, the inner rim, the mute position and the 15 material themes.
- **§4 Extruded Bubble Deep Red Ocean (Preset 9):** eyes on the second pass.
- **§7.1 Waveform:** Preset 4 trade-offs of the fixed-scale v7 (sign off or ask for the tag's exact dynamics);
  Preset 7 and the Reaction Modes; Breathing; four-ribbon Preset 3; Particles; Strands; Colour/floor/mist; Fixed
  response; Floor Give; Pulse Rim; swell visibility; Travel Direction; Unified atmosphere.
- **§8 Bubble:** R-170 eyes-on (tall, wide and TV cards); Particle glow.
- **§9 Studios:** Neon Lake, Extruded Spectrum, Spectrum, DevCurve and Oscilloscope Studios; the migrated Settings
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
"uncopyable WindowsPath" start failure (fab141f0), and the post-close repaint remedy (4e423fe6; open until a field
log confirms, §9). Card surfaces, the style pass and the 15 material themes are merged; their open items are in §4.

**Active or paused (resume each with a message to the same agent, which keeps its context and worktree):**
- **AC-01 Settings tab registry** (Opus high, started 7 Nov): checklist AC-01 with A-12 and A-14, proven on the real
  SettingsDialog; side defects and conflicts reported.
  **Next in this slot (operator 7 Nov): a Settings system and SSOT audit, once AC-01 is merged.** Read-only audit of
  the post-registry code. Scope:
  - schema, defaults and persistence: one owner per key; defaults that leak into widgets, QML or presets;
  - typed settings versus raw key strings;
  - presets and Studio-owned values; profile gating (MC/SMP);
  - import, export, reset and cache; change signals and the control-to-key binding;
  - dead or orphan keys, and compatibility bridges;
  - values duplicated between 2D and 3D or between runtime and Settings.
  It produces a ranked, actionable checklist (priority, reward, the fix) that the lead challenges and promotes into
  `Docs/Reference/Architecture_Checklist.md`. Defects it finds go to this plan.
  **Binding (operator, 7 Nov):** the spec systems are the canonical owners and stay:
  - each visualizer mode's Settings are declared once in `core/settings/visualizer_mode_settings.py`;
  - each transition's Settings are declared once in `rendering/transition_settings.py`.

  The audit finds what bypasses or duplicates them and proposes folding it into them; it never proposes replacing
  them. One known straggler to judge: the audio-analysis Technical controls are still declared separately in
  `ui/tabs/media/technical_controls.py`.
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

  All carry Preset 1's reactivity unchanged (only look keys authored), with ghosts off and caps carrying the peak.
  Evidence: `.artifacts/evidence/spectrum_presets_lead_20261107/` (contact sheets, motion strips, metrics, the
  authoring script). Open: the operator's eyes. Silhouette is the plainest by concept.
- **Waveform agent** (Opus medium, worktree `agent-af0eb2492e1e318d7`, branch `worktree-agent-af0eb2492e1e318d7`).
  **The tick cut is merged (7 Nov).** Lead audit: three realistic mutations are each caught by
  `tests/test_waveform_logical_tick_exactness.py` (a Gaussian cache key ignoring the width, one shifted grid shared
  by both directions, and a 1e-6 spring-term change). 43/43 Waveform files pass isolated on main. The game60 live
  check is owed on a quiet machine.
  Now on the follow-ups:
  - a music-vs-response check of every preset and Reaction Mode;
  - the floor clipping the operator sees: raise the lift limit (the operator prefers a little more height to floor
    clipping, which partly supersedes "top edge first");
  - checklist **AC-12** (the monotonic authored clock).

  Its live tick spikes around preset switches are gen2 GC, now queue item 1 below.
**Queued, next free medium slot, in this order (small, bounded):**
0. **Checklist AC-06** (left by the Studio agent): the four Studio adapters' unbounded class-level clip caches and
   the GUI-thread clip parse. Repeated offscreen Extruded Bubble sessions still grow about 2-3 MB each after the
   controller-leak fix; these caches are the first suspect.
1. **Gen2 garbage collection stalls the logical thread for 86–161 ms about once a minute, in every mode (found by
   the Waveform cut, 7 Nov).** Offline, every tick over ~16 ms in both builds was exactly one gen2 collection: about
   one per 5,500 ticks, roughly every 60 s at 90 Hz. Allocation bursts (preset switches, Studio sessions) bring
   collections forward. That fits the live 64–152 ms spikes around Waveform preset switches. A pause that long is a
   visible hitch.
   - **Measure first:** record gen2 collections live with `gc.callbacks` timestamps on the existing opt-in frame
     trace (no recurring work at rest), on two modes in the live check.
   - **Then fix at the process owner:** `gc.freeze()` once the startup warm-up ends (the long-lived startup heap
     leaves the scanned generations), plus tuned thresholds if still needed. Name the work that disappears.
   - **Prove:** gen2 pauses are rare and short live, there is no memory growth over a long run (overhead baseline),
     and lifecycle and teardown are unchanged.
2. **Two clicks on Reset Camera count as the card's double-click, which cycles the Visualizer mode** (operator 6 Nov
   ~22:00; `logs/screensaver*.log` 22:04:34-36). Two presses each ran a reset ("[VIS_ORBIT] Camera reset to preset
   home" x2). The pair also reached the visualizer region's double-click admission
   (`QuickVisualizerDoubleClickAdmission`, `cycle_mode=self._cycle_quick_visualizer_mode`,
   `engine/display_manager.py` ~3529). That cycled to the next mode in `mode_activation` (after Extruded Bubble comes
   Waveform) and wrote `widgets.spotify_visualizer.mode` (~1939). The one-Visualizer contract held: EB's last tick was
   22:04:34 and Waveform's first was 22:04:36, never overlapping. Fix at the owner: the camera hint buttons (Reset
   Camera and any other in-card control) consume their presses, including the second press of a double-click, so no
   in-card control press reaches mode cycling. Regression bar: a double-click on Reset Camera resets once or twice but
   never cycles; a double-click on the card's empty area still cycles.
3. **Checklist AC-04:** a failing inactive-renderer release blacks out the active mode on every frame
   (`rendering/quick/visualizer/render_host.py:182-183, 304-329`); render the active mode first, record the failure
   once, retry at the next boundary.
4. **Checklist AC-05:** one beat-engine authority (delete `_global_beat_engine`; the tick uses
   `controller.ensure_engine()` or raises). Lands before any SMP PCM source.
5. **Checklist AC-09 and AC-08 together** (one card border width resolver; one GL state-query helper on the per-frame
   fences with the query order preserved, plus the bench node-path case). Mechanical, pixel-identical.
6. **Checklist AC-11, decided (operator 7 Nov): "don't ruin the bordered 3D cameras so adjust the freeform Sphere
   but ideally in a way that does not ruin its look/capabilities".** The framed (bordered) 3D cameras of Extruded
   Bubble, Neon Lake and Waveform stay exactly as they are. Sphere (freeform) gains a Reset Camera to its preset home
   and declared inertia/wrap, without changing its look, framing or orbit freedom; Extruded Spectrum gets the same
   treatment where it applies. Prove it pixel-identical at the preset home and identical under orbit before and after.
   The in-card Reset Camera button must consume its own presses (item 2).
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
  `.artifacts/evidence/slow_startup_20261106/`.
- [~] **Displays off -> presentation pauses entirely, resumes clean (built 5 Nov; awaiting the operator's physical
  overnight check):** `core.display_power` pauses rotation, transitions, the Visualizer (parked, capture released) and
  the clock while the console displays are off (`Docs/Architecture/Compositor_Architecture.md` → Display power).
  Injected through the real window procedure, a heavy preset went from ~142% of a core / ~10% GPU / 51 swaps/s to ~4% /
  ~0% / ~0.6 swaps/s while off, and resumed with no publish or swap hole (`.artifacts/evidence/display_power/`). Still
  needs real hardware: leave a heavy preset (Waveform Preset 1 or Neon Lake) overnight with both displays turned off
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
- [~] **DevCurve "more alive while keeping the flow" (second cut 6 Nov; awaiting lead review, then operator eyes):**
  loud body owns most of the drawn ceiling (big, smooth: carrier blends to its broad component instead of limiter
  triangles), kicks ride linear headroom, quiet passages take the band share's rise, swell inside the body's share,
  tick vectorised (guide §13D → DevCurve). Evidence and before/after WebPs (loud end and a quiet passage, P1/P6) in
  `.artifacts/evidence/devcurve/reactivity_20261105/` (`PROGRESS.md`). Open: the strongest preset's bass (Deep Blue)
  stays ~18% below pre-work main's loud RMS (a smooth wave cannot match a slope-limited triangle at the same slope);
  the quiet-passage evidence is one recording's cold start (9 kicks); a capped layer shows the swell less (it lives
  inside the body's share).
- [ ] **Waveform logical tick starves the render thread under game load (quiet-machine game60, 6 Nov):** Waveform
  P1/P4 logical tick median 8.5/8.3 ms (p90 14.4/14.0) holding the GIL 73-75% of the time, so render-mode time is
  16-17 ms and frames drop to 41-44 fps (Neon Lake 89 fps, Spectrum 90, Bubble 63 under the same load; Extruded Bubble
  5.9 ms / GIL 0.53 / 55 fps is the second case). Offline the Waveform dynamics alone are ~1.3 ms, so the live tick's
  cost is mostly elsewhere (capture, packet build, field/strand/spark work): profile the LIVE logical tick, then cut
  it with byte-identical output (Preset 4 bit-exact with the tag). This is the Graphics Backend Decision's "optimise
  the logical tick first" step before trigger 2 can be judged. Evidence `.artifacts/evidence/live_check_quiet_20261106/`.
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
    simulation. Evidence `.artifacts/evidence/live_20261106/` and `.artifacts/evidence/eb_logical_tick/`.
  - **Waveform, same session (main):** P1 / P4 / P7 run at 43.5 / 42.7 / 37.6 fps, tick 8.5-8.7 ms (p90 14-16), GIL
    0.75, P7 64% late frames. Waveform is now the slowest live mode.
    **Tick cut (7 Nov, cc493199, byte-identical; live re-measure owed).** Profile: the tick is ~1.8 ms of many small
    NumPy/Python calls (snapshot ~1.0, surge ~0.37, pulse transport ~0.2, scene ~0.1, burst admission 2-4 ms on
    admitting ticks only); no steady GIL-held C call above ~2.5 ms. Cuts: shared spring terms, cached source Gaussians
    and shifted grid, direct surge gathers, one float32 fade column, uniform_gradient for Group Wave, scene and capture
    reads resolved once per configuration/spec, RibbonMaterial's check without astuple. Identity: 31 recorded replays
    (169,136 frames, every preset and Reaction Mode, P4 included) match main frame by frame;
    `tests/test_waveform_logical_tick_exactness.py` compares against the pre-cut forms with an fp64-fade negative
    control. Offline the gain is small (P4 min-of-3 median 3.01 -> 2.94 ms on a loaded machine; quiet-machine phase
    savings ~0.1-0.2 ms). Every tick above ~16 ms offline, in both builds, is one gen2 GC (86-161 ms, about one per
    5,500 ticks): the remaining live spikes are GC, not Waveform work. Merged 7 Nov after the lead's mutation audit
    (§3). Evidence: `.artifacts/evidence/waveform_logical_tick/` in the main checkout (local, git-ignored).
- [~] **Frozen builds could not open a Studio (operator 6 Nov: "module QtQuick.Controls.Basic is not installed"): fixed
  in source (e5005ffa), confirm on the next build.** The QML prune removed QtQuick/Controls, Templates and Shapes, and
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
  `.artifacts/evidence/widget_surfaces_20261106/` and `.artifacts/evidence/widget_surfaces_style_20261106/`
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
     - **The theme's material doesn't reach the cards.** With a material theme selected and Style Override left
       at **Theme**, the cards are opaque; forcing Glass in Style Overrides works. The theme's `surface_material`
       is lost somewhere between the selected theme and the running cards. Trace that chain in the running app
       (theme selection → resolved style → per-card material → `SurfaceBackdropSource`), not on a stand-in.
       Regression bar: select a material theme with the override on Theme, and the running card draws that
       material.
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
  `.artifacts/evidence/extruded_bubble/deep_red_ocean_pass2_20261106/`.
- [ ] **Side defects found in the deep red ocean pass (6 Nov):** the near (defocus) layer stair-steps the rim of a
  large near shell on some frames (seen with Lit Glass off as well). Also `tools/release_media.py` cannot render
  Waveform Ribbon showcases: the replay raises "Raw musical replay requires current PCM reanalysis" because
  `replay_clip` never drives `tools/visualizer_replay/pcm_reanalysis.py`.

## 5. Watchlist (observe during normal use; reopen only on evidence)

- [ ] **Neon Lake camera step on real music (found 6 Nov, pass 7, pre-existing at a372f106):** Preset 1 on
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

**Reactivity milestone baseline (operator, 5 Nov): tag `waveform-baseline-2026-11-05` (= `e7a84d33`).** Pulse and
Centre Out "like night and day"; logical cadence survives heavy game load; **Preset 4 is the reference** ("let us not
lose this"). Every later dynamics change shows, on the recorded clips, that Preset 4 is unchanged against this tag
(or names the improvement for operator sign-off). Preset 4 keeps Breathing 0 (exactly the baseline dynamics).

- [~] **Fixed-scale rework v7: accepted by the lead review 6 Nov (merged b76dc269); operator sign-off on Preset 4 and
  the trade-offs.** No adaptive memory (Adaptive Response toggle, off in every preset), fixed response fitted to main's
  visible behaviour, phrases widened about a heard-only 3 s mean, Kick Accent bounded at 15% of the roll (Preset 4 ships
  0), the floor lift bounded by the card's top edge (top edge first), the phrase mean catching up after real silence.
  The rejected v4's lessons (top edge first, fixed calibration fitted to what the replaced path visibly did, bounded
  kick channels) are in `Docs/Guides/Visualizer_Reactivity_Authoring.md`.
  Lead's own review on whole recordings against main (`tmp/waveform_review_20261106/`, gitignored: v7 frames in
  `branch/`, frame sheets, music-vs-response traces, `drift_*`, `chain7.npy`, `scripts/`; the agent's curated evidence
  in `.artifacts/evidence/waveform_ribbon/reactivity_preset7/`, PROGRESS.md):
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
- [~] **Preset 7 and the other reaction modes (operator log `logse7a84d332e.zip`, Rag Doll, 5 Nov) - awaiting
  operator eyes:** no decay/breathing in soft passages, sustained passages with changes read almost flat, and a swell to
  full power as the song got QUIETER. Preset 7 is Group Wave (song 31-123 s in the log; the recorded clip is song
  70-130 s). Causes: Group Wave's set envelope was built from the long-fade field with a peak-keeping blur, so the swell
  sat at its soft bound over the visible span (median/max .98) and the whole body inflated with Pulse Strength (bass);
  and the adaptive gain's 30 s memory re-normalised a quieter passage to loud reach. Fixed: Group Wave follows the fresh
  field (as Travelling Pulse); Breathing holds the gain memory through a quieter passage only, keyed to the slow
  passage level, never beat gaps (Preset 4, Breathing 0, is bit-exact with the tag).
  Evidence and per-passage tables: `.artifacts/evidence/waveform_ribbon/reactivity_preset7/`. Open: operator review of
  Preset 7 (bodies are smaller in loud passages now that the uniform inflation is gone: sustained-loud visible
  amplitude 6.4 -> 5.4); Whole Swell (Preset 6) sits at its soft bound in all music by design (one global level;
  de-saturating it barely changed the visible body, so it was left). Pulse-visibility WIP (branch
  `worktree-agent-a470c20ffe5fe8b02`) stays parked: the operator accepted the pulse as is.
- [~] **Breathing + anchored history ends (merged b0ddc041) — awaiting operator ears/eyes:** soft passages let go
  between swells (0.7 in every preset but 4) and, since the Preset 7 fix, a quieter passage after a loud one stays
  quieter (gain memory held); the tail no longer staggers at side angles. Evidence
  `.artifacts/evidence/waveform_ribbon/breathing_20261105/`.

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
  carrier wavelengths, light across the set, stronger forward lean) and reviewed frame by frame. Audit doc decisions 7+; evidence `.artifacts/evidence/waveform_ribbon/
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
  Kick Accent 0 to compare). Open: the Range audit (`.artifacts/evidence/waveform_ribbon/reactivity_preset7/
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
  Evidence `.artifacts/evidence/waveform_ribbon/floor_deform/`; design in the Migration Plan's Floor bucket.
- [~] **Pulse Rim (operator, 5 Nov: "where the pulse is that section of the ribbon's rim can be even brighter with
  falloff") — awaiting operator eyes:** Reaction-bucket slider (0 = today's rims, pixel-identical). The rims (line and
  rim glow) brighten by the square of the published pulse field over a reference level, softly capped, sampled at
  each fragment's history x (direct and reflected light), so every Reaction Mode and both Travel Directions put it
  exactly on the pulse; the field's own smooth shape is the falloff. Evidence
  `.artifacts/evidence/waveform_ribbon/pulse_rim/`; design in the Migration Plan's Reaction bucket.
- [~] **Swells reach the Preset camera already faded (Presets 1-3) - awaiting operator eyes:** the card's camera shows
  about ±16 of the scene axis at 1282x1005 (±5 at the canonical card), but edge swells were born at `PULSE_ORIGIN` 44,
  so Head To Tail swells arrived ~2 s late at 5% strength (in-view swell p50 .13-.30 against Preset 4's 1.39). Now the
  capture and the Studio pass the camera's visible span; Travelling Pulse edge swells are born just beyond it and age
  only once seen (p50 .81-.99 at ±16; the peak visible swell after each kick is 1.7-5.6x main at every time in song).
  Preset 4 and Presets 5-7 are byte-identical. Evidence `.artifacts/evidence/waveform_ribbon/reactivity_preset7/`
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
  Composition / Flow group. Evidence `.artifacts/evidence/waveform_ribbon/travel_direction/`; design in the Migration
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
  first in Reactivity; target-first response tuner. Opens on the live card's world (Fill framing; 1493e246) with the
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
  work added no tick cost vs a21a2b0c (same machine, human_heavy: advance median 2.45 ms both) and the closed-form
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

A heavy viscous molten body in a real concrete chamber; must never read as Neon Lake water. Brief and hard gates
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
- [~] **Particle glow (merged f441bd99) — awaiting operator eyes:** emitted linear light with a hot core and a
  monotonic halo (no dark moat), no twinkle on drifting sub-pixel cores, cheaper ambient CPU pass. Evidence
  `.artifacts/evidence/bubble/particle_glow/` (`before/` vs `after/` 4x crops, flicker strips).

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
  Neon Lake built, DevCurve and Oscilloscope built (below); Sphere in progress). Neon Lake (Shockwave Grid) awaits operator acceptance
  (evidence `.artifacts/evidence/neon_lake/studio/`, Presets 1 and 3): recorded engine answers like Spectrum, the
  shared framed camera, no wallpaper; its terrain is painted with the Studio's shared brush (6 Nov; evidence
  `.artifacts/evidence/studio_completion_20261106/brush/`; the retired Settings editor's 3/4 view Sun / Moon drag is
  now Position X / Y / Z only). Extruded Spectrum awaits operator acceptance
  (evidence `.artifacts/evidence/extruded_spectrum/studio/`); its cast-shadow rows stay out of the Studio while
  they are unavailable (`EXTRUDED_CAST_SHADOW_AVAILABLE`). Spectrum awaits operator acceptance (evidence
  `.artifacts/evidence/spectrum/studio_20261105/`). Every mode's Settings body is now the preset row and the Studio
  launcher (operator 6 Nov: migrate fully once parity+ is proven; `tests/test_visualizer_studio_parity.py`). Operator
  look pending on the migrated Settings pages (one sentence per mode) and on the terrain brush in the Studio.
- [~] **DevCurve Studio built (6 Nov), awaiting operator acceptance**(`ui/studio/devcurve_adapter.py`, registered;
  so DevCurve's preset row now shows Open Studio and no Edit Preset). Evidence `.artifacts/evidence/devcurve/studio/`
  (Deep Blue on Rag Doll, Neon Skyline on Human: every workspace with the live traces, plus the node rows). Operator
  to judge: the per-layer Body / Accent / Swell traces as the way to read the reworked reactivity, the Layers
  workspace (one panel per layer), and whether the Audio Analysis group earns its place (re-analysed from PCM through the
  production DSP, every offered control moves DevCurve's frame; AGC Strength and Output Lift read nothing and are now
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
    `.artifacts/evidence/studio_clip_loop_20261106/`. Note the Studio plays no sound: the clips are the capture
    stream the analysis reads, so "listen" means the music-reactive picture across the wrap. Operator: (1) let any
    Studio loop on each of the three clips and watch the wrap (end of the 13 s timeline): the preview should not
    jump, empty, or re-start its motion; (2) Rag Doll has no steady beat, so its seam is the least certain: judge it
    first; (3) the clips now start and end mid-song at the loop points chosen (Human and Growing Pains on their
    groove), not at the earlier quiet-to-hot windows; say if the quiet-to-hot arc matters more than the seam.
- [~] **Studio chrome matches Settings (6 Nov), awaiting the operator's look**(all Studios: one shell;
  `Docs/Reference/Visualizer_Studio.md` "Chrome and theme"). Frameless window with Settings' title bar and forged
  rounded edge, the theme's Glass/Acrylic material, 1.5 px one-path card borders, Settings' panel casts at half
  offset, viewport corners rounded over the scene. Hidden-render evidence `.artifacts/evidence/studio_chrome/`
  (before/after, Default Dark Acrylic, Matte Graphite Normal, Pearl Blush light Glass; 8x crops). Operator to check
  on screen: the live Glass/Acrylic composition of the Qt Quick window (first use of the AccentPolicy material on an
  alpha OpenGL window; the evidence only simulates the blur), snap/resize/maximise by hand, and the panel opacity
  floor (0.88) and shadow strength on light themes. Light-theme instrument wells (trace cards, response curve,
  transport bar) now sit on the theme's input surface (evidence `.artifacts/evidence/studio_followups/legibility/`,
  Pearl Blush and Default Dark, before/after): operator look pending. Operator (6 Nov, not urgent): the material is
  missing from most Studio areas (workspace tabs, the panels under the preview, their section headers). Apply the
  theme's Glass/Acrylic to them with a slightly darker layer behind every control so it stays legible. Controls laid
  over the preview (transport chips, aspect chips, the source notice) keep a translucent dark solid: blurring the live
  scene behind them would cost GPU time every frame and skew what the preview shows about performance.
- [~] **Studio drag lag fixed (6 Nov), awaiting the operator's feel check.**Drags preview once per frame and
  re-show only the dragged key (Visualizer_Studio.md "Drags are batched"); evidence
  `.artifacts/evidence/studio_drag/` (per move 56 ms -> 0.07 ms on Waveform). Side defect (not measured): Bubble's,
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
  - Lead fix audit (7 Nov): this is the third round. 5 Nov (a4a6978d) fixed a real deadlock with real-Studio
    tests. 6 Nov (2a3626f0, "re-expose so the layered window repaints") was proven only on a bare stand-in
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
- [ ] **Per-session memory growth in the Studio (side defect, 6 Nov).** Process memory grows about 2-3 MB per
  offscreen Extruded Bubble session (private bytes and USS, 16 sessions). The growth is the same with and without the
  controller-leak fix, which `test_closed_studio_sessions_are_released_and_live_counts_stay_flat` guards: closed
  sessions are now collected and live Studio object counts stay flat. So something other than the controller grows.
  Find it with tracemalloc plus a native heap comparison. Same owner: checklist AC-06
  (`Docs/Reference/Architecture_Checklist.md`), the four adapters' unbounded class-level `_clip_cache` dicts and the
  GUI-thread clip parse in `waveform_recorded_inputs.py:262-273`. These are the first suspects for the growth.
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
  Water; left-drag paints, right/middle drag pans). Evidence `.artifacts/evidence/studio_completion_20261106/brush/`.
  Audio Analysis now moves the DevCurve, Oscilloscope, Neon Lake, Bubble, Extruded Bubble and Sphere previews on
  recorded clips. Sensitivity sheet: `audio_analysis/`. DevCurve normalises its body, so it barely shows, as live.

## Operator execution and evidence rules

Keep details and evidence at their focused owner, this checklist actionable, and `Index.md` / `Spec.md` navigation current.
No memory updates without an explicit request.

####################
ADDITION & SIDE QUEST BOX
Never Remove This Box. Restore It If Removed. Only Remove Contents As you place them in the active plan as real live checklist targets.
####################




###################