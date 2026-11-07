# Architecture Audit, 6 Nov 2026 (one-time, read-only)

**Status:** dated audit snapshot (evidence, not authority; `Index.md` → Directory roles). Reviewed 7 Nov against
`8328a6d2`: every finding confirmed, merged and re-weighted into the live work list
[`Docs/Reference/Architecture_Checklist.md`](../Reference/Architecture_Checklist.md), which `Current_Plan.md` links
and promotes from. Nothing here is fixed; `file:line` references below are as of 6 Nov. **Source:** branch
`worktree-agent-ae7baee1b36deb171`, written on
`0a4fba7e` and rechecked after `git merge main` (fast-forward to `d84dceff`; that merge touched only
`Current_Plan.md`, so every `file:line` below is valid on `d84dceff`).

**Scope:** thread manager, resource/GL ownership, lifecycles, dead code, churn, GIL contention, memory, dormancy,
plus the lenses SSOT, 2D/3D consistency, performance and readiness for SMP and full visual rearrangement.

**Method:**
- **Static:** ripgrep over production source; an AST import-reachability scan from `main`, `main_mc`,
  `main_diagnostic`, `helpers.reddit_helper_worker` and `versioning`. Dotted string literals count as edges, so
  string hooks and `python -m` workers stay reachable and "dead" is under-reported, never over-reported. A
  settings-key scan tokenised production `.py/.qml/.js` against every leaf of `DEFAULT_SETTINGS`.
- **Cheap probes, offscreen and in my own process:**
  - `tools/overhead_baseline.py`: transitions, surfaces and visualizers;
  - a GL state-query micro-probe on a `QOffscreenSurface`, with PyOpenGL per-call checking off as in production.

  No app launch, no visible window, no load generator. The machine was shared with other agents (other processes'
  CPU was 55-63%), so GPU and wall times here are not comparable. Call counts and thread CPU are.
- **Evidence:** `.artifacts/evidence/architecture/audit/20261106_audit/` in this worktree. It holds both baseline JSONs (moved
  out of `tools/baselines/overhead/`, not committed) and both run logs. Copy it before the worktree is removed.

**Known items that are not re-reported** (cross-references only):
- the closed `StudioController` leak and the 18 s UI stall after a Studio closes (`Current_Plan.md` §0 "Paused",
  §9 R-172 follow-ups; the Studio agent owns them);
- Reset Camera's two clicks cycling the mode (`Current_Plan.md` §0 "Queued");
- the Waveform logical tick starving the render thread (`Current_Plan.md` §4);
- the 15 s usage-sample hitch (`Current_Plan.md` §5);
- the Bubble `max_disp *= 0.72` side defect (§8);
- the Studio exact-replay frame-budget side defect (§9 "Studio drag lag").

No **critical** defect was found: nothing breaks today's product or corrupts data. The highest items are readiness
blockers for SMP and full rearrangement, plus a handful of SSOT duplicates and bounded performance wins.

---

## Summary (sorted by severity, then reward)

| ID | Area | Finding (one line) | State | Sev | Reward | Effort |
|---|---|---|---|---|---|---|
| A-01 | Lifecycle / SMP | Opening Settings tears down the whole runtime and runs a modal `exec()`. Playback or any long-lived service cannot survive it. | Confirmed | high | high | L |
| A-02 | Layout / SMP | The Visualizer is a `DisplayManager` special case: its own owner, Media docking, input admissions and CUSTOM hooks. It is not a descriptor/family member. | Confirmed | high | high | L |
| A-03 | Settings / SMP | Settings tabs and pills are hard-coded: two parallel tab lists, a pill derivation copied twice and per-tab view-state schemas. | Confirmed | medium | high | M |
| A-04 | Memory | Four Studio adapters keep analysed clips in unbounded class-level dicts for the process lifetime. The engine-answer path caps its store at 24. | Confirmed | medium | medium | S |
| A-05 | GIL / perf | Per-frame render-thread GL state fences use PyOpenGL getters (14.4 µs each) beside the repo's own ctypes helper (3.6 µs). That is about 0.2 ms of GIL-held time per Visualizer frame. | Confirmed (cost measured) | medium | medium | S |
| A-06 | 3D consistency | Reset Camera and framed flight exist only for modes with a framed-camera spec. Sphere and Extruded Spectrum orbit without them, and inertia and wrap differ per mode. | Confirmed | medium | medium | M |
| A-07 | SSOT / beat engine | A module-global `_global_beat_engine` mirrors the registry's engine. It outlives `BeatEngineRegistry.clear()` and can disagree with `set_engine`. | Confirmed | medium | medium | S |
| A-08 | SSOT / beat engine | `consume_engine_bars` lazily binds the process engine when `_engine` is None. It bypasses the controller's factory and `acquire()`. | Confirmed (code); trigger Suspected | medium | medium | S |
| A-09 | SSOT / defaults | The card border width is resolved and clamped in five places. One of them declares it `int`. | Confirmed | medium | low | S |
| A-10 | GIL / Studio | `ClipLoadJob` parses the worker's JSON and builds the recorded inputs on the GUI thread. | Confirmed (code); cost Suspected | medium | medium | S |
| A-11 | Render lifecycle | One failing inactive-renderer release raises before the active mode renders, on every frame from then on. | Suspected | medium | medium | S |
| A-12 | Settings / SMP | Studio-owned mode bodies still build hidden value-owner widgets next to a lazy value dict, so each value has two owners. | Confirmed (code); cost Suspected | low | medium | M |
| A-13 | Churn | `SettingsManager.set` publishes a change even when the store discarded an unchanged value. Engine handlers rebuild sources on any `sources*` publication. | Confirmed (code); impact Suspected | low | medium | S |
| A-14 | Threading / SSOT | Standalone Settings (CONFIG) creates up to eight private helper ThreadManagers through copy-pasted factories. | Confirmed | low | low | S |
| A-15 | Clock SSOT | Visualizer authored time is the wall clock (`time.time()`), while deadlines use `perf_counter`. A system clock step injects dt. | Suspected | low | medium | M |
| A-16 | Dead code | 17 production modules are unreachable from every entry point; 15 of them are used only by tests or tools. | Confirmed | low | low | S |
| A-17 | Dead code | ResourceManager's GL-handle registration and QImage pool APIs have no production caller. | Confirmed | low | low | S |
| A-18 | Dead settings | The `ui.visualizer_bucket_states` leaf keys of Studio-owned modes are read only as an existence check. | Confirmed | low | low | S |
| A-19 | Timers | A few raw `QTimer.singleShot` calls bypass the ThreadManager registry, and one write path uses a debounce. All are fenced; the inventory is below. | Confirmed | low | low | S |
| A-20 | Threading | The COMPUTE pool is sized `cpu_count - 1` (23 on this machine), far above the real concurrency. | Confirmed | low | low | S |
| A-21 | Polling | Idle worker processes wake 10x/s and the supervisor listener 4x/s. | Confirmed | low | low | M |
| A-22 | Memory | Per-generation diagnostic maps in the ThreadManager grow for the whole process. | Confirmed | low | low | S |
| A-23 | Bench coverage | `overhead_baseline` never runs the production clip and background fences, so A-05-class costs are invisible to it. | Confirmed | low | medium | S |

---

## Findings

### A-01: Settings is a full runtime teardown (SMP blocker)

- **Area:** lifecycle, Settings, SMP readiness. **Confirmed.**
- **Evidence:**
  - `engine/engine_handlers.py:355`: `engine.stop(exit_app=False, reason="settings")` owns the complete display/GL
    teardown;
  - `:509`: `dialog.exec()` is a nested modal loop;
  - `:600`: `dialog_barrier.seal()`, after which replacement continues;
  - `Spec.md` → Lifecycle.

  The SMP plan's own §0 table already says a long-lived music service "must be owned above the MC display
  generation".
- **Impact:** today this is the contract, so nothing is broken. Every future application-scoped service (SMP
  playback and queue, library DB, the Expanded Visualizer's takeover state) either dies with each Settings visit or
  has to invent its own exemption from the barrier. Settings can never be live (non-modal) while the saver presents.
- **Reward:** a defined application tier above display generations, which plans 01 and 02 both need.
- **Suggested fix (owning boundary):** in `ScreensaverEngine`, add one explicit application-service tier: a
  registry with create/retire and consumers fenced by generation. Its members are excluded from `stop(reason=
  "settings")` but retired at terminal `cleanup`. Keep the display teardown exactly as it is. Settings stays modal
  for SRPSS. SMP's "live Settings" becomes a separate application policy, as plan 02 §1 already says.
- **Regression bar:** a test that opens and closes Settings through `on_settings_requested` with a stub application
  service. It asserts that the service instance is identical before and after, that no display-generation object
  survives (destruction-barrier watch list empty), and that terminal cleanup retires the service.

### A-02: The Visualizer is a DisplayManager special case (full-rearrangement and SMP blocker)

- **Area:** layout, ownership, SSOT, SMP readiness. **Confirmed.**
- **Evidence:**
  - `engine/display_manager.py` is 5952 lines. The single Visualizer owner is built in
    `_construct_quick_visualizer_owner_on` (`:3245-3560`; one construction site at `:3389`; a second is rejected at
    `:3258-3263`). The same method wires the double-click/middle-click admissions and the volume wheel (`:3529-3550`).
  - Ordinary placement docks to Media: `_resolve_quick_visualizer_base_authored_origin` /
    `_resolve_quick_visualizer_authored_layout` (`:3038-3110`), the Media-geometry observer (`:3222-3242`) and
    `rendering/visualizer_media_adjacency.py`.
  - The Visualizer's card style is resolved here too, not by the family binder (`:3355-3386`, see A-09).
  - Ordinary widgets go through `WidgetRuntimeManager` / `family_binder`. The Visualizer does not.
- **Impact:**
  - "Full visual rearrangement of every widget and panel" has two layout authorities: ordinary families, and the
    Visualizer through Media docking. Moving Media moves an uncommitted Visualizer.
  - SMP's docked Visualizer / Pop Out (plan 02 §8.3) and the Expanded Visualizer (plan 01 §D) would need a third
    host path inside the same 6k-line owner.
  - Every Visualizer change touches the class that also owns topology, idle warm-up, Reddit URL flush, display power
    and startup reveal.
- **Reward:** one host-neutral Visualizer presentation owner that both the display runtime and a future SMP or pop-out
  host can bind. Docking becomes an explicit, removable placement policy, not hidden coupling.
- **Suggested fix:** extract a `VisualizerHostBinding` from `DisplayManager` that owns construct, bind, retire,
  admissions and authored layout for one display unit. `DisplayManager` keeps only the "which unit" decision.
  Express Media docking as one placement policy, `docked_to: media | none`, inside the canonical layout descriptor
  vocabulary. Keep the one-owner rejection (`:3258`) at the binding boundary.
- **Regression bar:**
  - one Visualizer owner per process across construct → transfer → retire, both today's unit and a stub second host;
  - moving Media leaves a Visualizer with `docked_to: none` in place;
  - the existing Edit/Arrange parity harness maps stay identical.

### A-03: Settings tabs and pills are hard-coded (SMP-tab blocker)

- **Area:** Settings architecture, SSOT, SMP readiness. **Confirmed.**
- **Evidence:**
  - `ui/settings_dialog.py:709` hard-codes the `_tab_keys` list. `:1088-1110` keeps a parallel `_tab_builders` dict.
  - The editing-path pill is derived twice with the same if/elif chain: `:735-745` (initial) and `:1821-1829`
    (reload). Each tab names its pill differently (`subtab_id`, `mode_id` + `page == "mode"`,
    `transition_bucket_section(pill)`).
  - `core/settings/ui_bucket_state.project_settings_bucket_context` consumes the result
    (`Docs/Architecture/Settings_Bucket_Persistence_Contract.md`).
- **Impact:** an SMP tab with pills (the operator's request, box at the end of `Current_Plan.md`) needs edits in at
  least four places. Its pill persistence has to be added to both copies of the chain. Profile-conditional tabs (SMP
  only when the Library widget is on, hidden in an SMP-only build) have no declaration point. A forgotten branch
  silently drops the remembered pill.
- **Reward:** adding a tab is one descriptor. Pill persistence and profile gating come for free and match the
  existing ones.
- **Suggested fix:** one `SettingsTabDescriptor` registry in `ui/` holding key, label, builder, `pill_of(view_state)`
  and `available(profile, capabilities)`. `_tab_keys`, `_tab_builders` and both pill chains derive from it. Migrate
  the existing tabs without changing their persisted view-state.
- **Regression bar:** a test that walks the registry and proves the following for every tab: initial and reload pill
  derivation agree, each round-trips through `project_settings_bucket_context`, and a tab declared unavailable is
  absent from the button row and the persisted index mapping.

### A-04: Unbounded Studio clip caches

- **Area:** memory. **Confirmed.**
- **Evidence:** class-level `_clip_cache: dict = {}`, written on every successful clip analysis and never evicted:
  - `ui/studio/waveform_adapter.py:1209,1223-1231`;
  - `ui/studio/extruded_bubble_adapter.py:760,780-787`;
  - `ui/studio/bubble_adapter.py:653,665-672`;
  - `ui/studio/sphere_adapter.py:591,603-610`.

  Keys include the analysis (non-authored) values, so each analysis-value change is a new entry
  (`waveform_adapter.py:1211-1216`). The shared engine-answer store, by contrast, caps at `ANALYSED_LIMIT = 24`
  (`ui/studio/engine_answers.py:584-597`). A Waveform entry is a tuple of `AdvanceInput` records, one per tick (90 Hz)
  over a 13 s loop plus its prime (`ui/studio/waveform_recorded_inputs.py:146-157`).
- **Impact:** Studio sessions that move Audio Analysis controls grow the Settings process without limit. They are
  also what the known controller leak keeps reachable. Size per entry is Suspected; measure with `tracemalloc`
  around `to_inputs`.
- **Reward:** bounded Studio memory, and one cache policy instead of five.
- **Suggested fix:** route all four adapters through `engine_answers.remember/analysed`, or a shared
  `analysed_cache(mode_id)` with the same limit. Delete the class dicts.
- **Regression bar:** a test that feeds `ANALYSED_LIMIT + 5` distinct keys through each adapter's `start_clip_load`
  with a stub loader. It asserts that the cache length never exceeds the limit and that the newest entries survive.

### A-05: PyOpenGL state getters in per-frame render-thread fences

- **Area:** GIL contention, render thread, SSOT. **Confirmed;** cost measured offscreen.
- **Evidence:**
  - `rendering/quick/gl_query.py` exists for exactly this. Its docstring cites PyOpenGL getters at about 13 µs and
    raw ctypes at 2.7 µs.
  - A parallel private ctypes helper lives in `rendering/quick/visualizer/gl_state.py:30-43`.
  - PyOpenGL `_int_state` copies remain on per-frame paths:
    - `rendering/quick/visualizer/clip_host.py:57`, with 14 getters plus `GL_SCISSOR_BOX` per
      `_InheritedClipState.capture` (`:193-240`, called on every clip begin `:327-330`);
    - `rendering/quick/render/background_node.py:145`, with `_draw_base` at `:599-613` on every background draw;
    - `rendering/quick/visualizer/render_host.py:30,370-371`;
    - `rendering/quick/render/image_textures.py:27`, upload only.
  - The micro-probe ran with per-call checking off as in production, under about 55% outside CPU load. PyOpenGL
    `glGetIntegerv(int)` took 14.38 µs against 3.64 µs for `gl_query.get_int`, and the `GL_VIEWPORT` tuple 18.68
    against 7.60 µs. `glIsEnabled` showed no difference (1.73 against 1.59 µs).
- **Impact:** about 15 × 10.7 µs ≈ 0.16 ms per Visualizer frame in the clip fence, plus about 0.06 ms per
  background draw. That is GIL-held render-thread Python per display at 90 Hz (about 2% of a core). It competes
  directly with the logical tick, which is the project's tick-dt-spike mechanism.
- **Reward:** about 0.2 ms per frame back, with no pixel change. One GL-query helper instead of three.
- **Suggested fix:**
  - replace `_int_state` in `clip_host`, `background_node` and `render_host` with `gl_query.get_int/get_ints`,
    keeping the **exact query order** (`clip_host.py:199-201` says to preserve it; CHK25/CHK26 lineage is
    operator-protected);
  - fold `visualizer/gl_state.py`'s private entry points into `gl_query`.

  The ordering constraint makes this a mechanical swap, not a retune.
- **Regression bar:** a GL-call-order test that records the sequence of `glGet*` names in `capture()` before and
  after. Bench call counts must not rise (A-23 makes the bench see these paths). Pixel output stays identical on
  the clip-smoke fixtures.

### A-06: 3D camera contract diverges by mode (2D/3D consistency)

- **Area:** 2D/3D behavioural consistency. **Confirmed.**
- **Evidence:**
  - `engine/display_manager.py:835-842` enables `set_visualizer_camera_reset_available` and framed flight only when
    `spec_for_mode(mode)` exists.
  - In `core/settings/visualizer_mode_registry.py`, only Neon Lake/Shockwave Grid (`:368`), Extruded Bubble
    (`:407`) and Waveform (`:436`) declare `framed_camera`.
  - Sphere (`:298-300`) and Extruded Spectrum (`:332-333`) orbit with W/A/S/D but get no Reset Camera and no framed
    flight.
  - Inertia is on for Sphere and Waveform only (`:300`, `:434`). Turn wrap is off for Neon Lake and Waveform
    (`:366`, `:434`).
- **Impact:** the same gestures behave differently across the 3D modes. Sphere and Extruded Spectrum can be orbited
  away with no in-card way back. A drag coasts in two modes and stops dead in three. This contradicts the shared
  framed-camera standard (`core/settings/framed_camera.py`; `Docs/Reference/Visualizer_Reference.md` → Live view
  pose) for every mode that orbits. Some divergence is authored on purpose (a landscape has no back, so no wrap).
- **Reward:** one predictable 3D control contract for Expanded Visualizer and SMP, where the card is large and
  orbiting is more likely.
- **Suggested fix:** product decision first (operator). Choose between giving Sphere and Extruded Spectrum a
  framed-camera spec (Reset Camera to preset home), or a camera-reset contract that does not need a physical camera.
  Then make inertia a declared, documented per-mode choice with a reason, not an accident.
- **Regression bar:** a registry test listing every mode with `view_orbit_settings`. Each must declare a reset path
  (framed spec or explicit `camera_reset: none` with a reason), and its inertia/wrap must match a table in
  `Visualizer_Reference.md`.

### A-07: Duplicate beat-engine handle (`_global_beat_engine`)

- **Area:** SSOT, one-beat-engine contract. **Confirmed.**
- **Evidence:**
  - `widgets/spotify_visualizer/beat_engine.py:1973-1987`: `get_shared_spotify_beat_engine` stores the registry's
    engine in a module global. `BeatEngineRegistry.clear()` (`:1952-1969`) never clears it, and `set_engine`
    (`:1944-1950`) never updates it.
  - `engine/engine_lifecycle.py:292-295` force-stops through the module global first, then through the registry.
- **Impact:**
  - After `clear()` the engine object (a QObject with its audio worker) stays reachable through the module global
    until process exit.
  - With an injected engine, terminal stop force-stops the stale one.
  - When SMP adds an internal PCM source to this engine, two handles make "which engine is live" ambiguous at
    retirement.

  This is not a second engine: the "exactly one" contract holds (see Healthy).
- **Reward:** one authority for the one engine.
- **Suggested fix:** delete `_global_beat_engine`. `get_shared_spotify_beat_engine` returns
  `BeatEngineRegistry.get_instance().get_engine(...)`, and `engine_lifecycle` calls only the registry's `clear()`.
- **Regression bar:** after `BeatEngineRegistry.clear()`, a `weakref` to the engine dies once the test drops its
  own reference, with gc disabled (this proves the module retains nothing). `set_engine(x)`, then terminal stop,
  force-stops `x`.

### A-08: Lazy engine fallback inside the tick

- **Area:** SSOT, lifecycle (engine lease). **Confirmed** in code; production trigger **Suspected** (none found).
- **Evidence:**
  - `widgets/spotify_visualizer/tick_pipeline.py:965-969`: when `widget._engine is None`, the tick calls
    `get_shared_spotify_beat_engine(...)` and writes it back to `_engine`.
  - `_engine` delegates to the controller (`logical_tick_state.py:37,90-95`).
  - The controller's own resolution is `ensure_engine()` with `_engine_factory`
    (`runtime_controller.py:313-328`). The owner's lease is `acquire()`/`release()`
    (`quick_display_visualizer_owner.py:1505-1530`, `:179-221`).
- **Impact:** a fail-open second resolution path. A Studio or offline controller built without its engine would
  silently bind the live capture engine: it ignores the factory, takes no lease and can reconfigure the live bar
  count. Today every caller sets the engine first, so it is latent.
- **Suggested fix:** use `controller.ensure_engine()`, or raise. The tick must never resolve a process service.
- **Regression bar:** a tick on a controller with `engine_factory=stub` and `engine=None` uses the stub. A tick with
  neither raises. Neither touches `BeatEngineRegistry`.

### A-09: Card border width resolved five times

- **Area:** SSOT, defaults. **Confirmed.**
- **Evidence:**
  - "the one ... authority" exists: `rendering/quick/widgets/family_binder.py:84-96` (float, finite, clamp 0-12);
  - re-implemented in `engine/display_manager.py:3356-3370` (the Visualizer's card);
  - `rendering/quick/widgets/games_you_follow.py:202-203`;
  - `rendering/quick/widgets/system_audio_osd.py:98-110`;
  - `rendering/widget_descriptors.py:3048` declares the same key as `"int"`.
- **Impact:** a change to range, type or rounding lands in one place and not the others. The Visualizer, OSD and
  Games You Follow then draw a different border from every other card. This matters for themes and materials.
- **Suggested fix:** export `resolve_card_border_width_px(widgets_config)` from one module (where the defaults
  helpers live) and call it from all five. Correct the descriptor type to float if fractional widths are admitted.
- **Regression bar:** a parametrised test feeding NaN, inf, -1, 12.5, "x" and a missing key to every consumer path.
  All return the same value.

### A-10: Studio clip results parsed on the GUI thread

- **Area:** GIL, GUI responsiveness. **Confirmed** (code); cost **Suspected**.
- **Evidence:** `ui/studio/waveform_recorded_inputs.py:262-270`. In `QProcess.finished`, on the GUI thread, the job
  calls `json.loads(self._output_path.read_text())` and then `self._convert(data, fixture)`. For Waveform that is
  `to_inputs`, which builds one `AdvanceInput` with onsets per tick (`:146-157`). The shared engine-answer workers
  use the same `ClipLoadJob` (`engine_answers.py:604-612`).
- **Impact:** one GIL-held C parse plus pure-Python construction per clip load and per analysis-value change, while
  the Studio preview renders. Size is Suspected. Confirm with `--frame-trace` / the GUI stall sampler around a clip
  switch.
- **Suggested fix:** do the parse and conversion on a ThreadManager IO task. Publish the finished `RecordedInputs`
  to the GUI through the existing `run_on_ui_thread`, fenced on the job's cancelled flag. Or have the worker write a
  binary sidecar, as Oscilloscope's capture history already does (`Docs/Reference/Visualizer_Studio.md` §3).
- **Regression bar:** a test with a stub worker output asserting that `_on_finished` returns without calling
  `json.loads` on the GUI thread, plus a `tools/studio_drag_profile.py`-style timing of a clip switch.

### A-11: A failing inactive-renderer release blacks out the active mode

- **Area:** render-resource lifecycle. **Suspected:** no release failure has been seen in logs; the logic is
  confirmed.
- **Evidence:** `rendering/quick/visualizer/render_host.py:182-183` calls `release_inactive_implementations` when
  `mode_changed or len(self._implementations) > 1`, **before** the active mode renders. `:276-329`: a failed
  release keeps the renderer cached and then raises `RuntimeError`. So once a release fails, every following frame
  re-enters, fails and raises before `implementation.render(frame)` at `:258`.
- **Impact:** one stuck release in a retired mode stops the new mode drawing until teardown. This is a fail-closed
  black card, where the docstring promises "a later legal render ... can retry it".
- **Suggested fix:** render the active implementation first, or catch the inactive-release error and record it
  through the node's `RenderFailureLog` without aborting the frame. Retry release on a bounded schedule (next mode
  boundary or teardown), not on every frame.
- **Regression bar:** a test with a renderer whose `release_resources` raises, then a switch to mode B. B's
  `render` is called every frame, and the failure is recorded once, not once per frame.

### A-12: Hidden value-owner widgets in Studio-owned mode bodies

- **Area:** Settings, SSOT, memory and startup cost. **Confirmed** (code); cost **Suspected**.
- **Evidence:** `ui/tabs/media/spec_mode_builder.py:64-93`. `build_studio_owned_mode_ui` still builds the full
  scaffold (normal widget, advanced host, technical controls, shared Bar Appearance/Rainbow rows) and parks it in a
  hidden `holder` (`:86-92`). It also creates `_<prefix>_lazy_values` (`:93`). Values then have two owners: the
  lazy dict and the hidden widgets. The docstring says the parked controls are "the value owners inside".
- **Impact:** every visited mode body constructs and styles QWidgets that are never shown. An SMP tab copying this
  pattern would inherit two value owners.
- **Suggested fix:** make the lazy value cache the only owner for Studio-owned modes. Build no technical or shared
  widgets for them, and have `collect_spec_mode_settings` read the cache.
- **Regression bar:** for every Studio-owned mode, opening its body creates no `QWidget` named for technical/shared
  rows (`findChildren`), and save round-trips every `body_keys(mode_id)` value unchanged.

### A-13: Unchanged settings writes still publish

- **Area:** churn. **Confirmed** (code); impact **Suspected**.
- **Evidence:** `core/settings/json_store.py:332-333` drops a write whose value is unchanged. But
  `SettingsManager.set` (`core/settings/settings_manager.py:1158-1177`) always calls `sync()` and
  `_publish_store_change`: the Qt signal, every handler and the EventSystem bridge (`engine/screensaver_engine.py:
  620-624`). `ScreensaverEngine._on_settings_changed` (`:2382-2399`) rebuilds sources on any `sources*` key.
- **Impact:** re-saving the same value (Settings save-all paths, preset re-application, CUSTOM commits) triggers
  handlers and rebuilds that change nothing. Which callers re-save unchanged values in practice is Suspected; count
  `settings_changed` emissions per Settings close in a log.
- **Suggested fix:** `_set_structured_value_locked` / `setValue` report "changed". `set()` skips publication when
  nothing changed, except explicit migrations that must publish.
- **Regression bar:** `set(k, v)` twice emits `settings_changed` once. Setting `sources.folders` to its current value
  does not call `_on_sources_changed`.

### A-14: Copy-pasted helper ThreadManagers in standalone Settings

- **Area:** threading, SSOT. **Confirmed.**
- **Evidence:** CONFIG mode (`main.py:834-866`) never registers an app-shared ThreadManager (only
  `engine/screensaver_engine.py:584-585` does). Each of these creates and owns a private
  `create_helper_manager()` (2 IO + 1 COMPUTE):
  - `ui/tabs/widgets_tab_defaults.py:292-308`;
  - `ui/tabs/widgets_tab_feeds.py:114-129`;
  - `ui/tabs/widgets_tab_gmail.py:173-188`;
  - `ui/tabs/widgets_tab_steam.py:283-299`;
  - `ui/widgets/geocode_completer.py:66-78`;
  - `ui/onboarding/setup_page.py:55-59`;
  - `core/gmail/gmail_backend.py:104`;
  - `core/gmail/gmail_oauth.py:446`.

  Each copy has its own `destroyed`-lambda shutdown.
- **Impact:** up to 24 lazily created threads. Eight copies of ownership code where one service would do. Every new
  Settings feature (SMP tab) adds another.
- **Suggested fix:** the Settings dialog, in CONFIG mode, owns one helper ThreadManager registered as app-shared for
  its lifetime and shut down when it is destroyed. Delete the per-tab factories.
- **Regression bar:** in a CONFIG-mode Settings test, `ThreadManager.create_helper_manager` is called at most once;
  after the dialog is destroyed, `get_app_shared()` is None.

### A-15: The Visualizer's authored clock is wall time

- **Area:** clock SSOT. **Suspected:** no clock step has been observed.
- **Evidence:**
  - `widgets/spotify_visualizer/tick_pipeline.py:1412`: `now_ts = time.time()` drives every mode's step;
  - the beat engine uses `time.time()` at 9 sites (smoothing, play ramp, keepalive);
  - deadlines use `perf_counter` (`logical_runtime.py:53-60`);
  - `produced_ts` defaults to `time.monotonic()` (`:204`).

  Partial guards exist (`beat_engine.py:88`: dt > 2 or ≤ 0 resets smoothing).
- **Impact:** a Windows time sync that steps the clock, or a manual time change, puts a dt jump or a negative dt into
  every simulation. Mode clamps differ.
- **Suggested fix:** move authored time to one monotonic source (`perf_counter` or the logical runtime's deadline
  clock), exposed by the logical runtime. Recordings that store wall timestamps keep converting at their boundary.
- **Regression bar:** a tick test patching `time.time` to jump −5 s and +60 s between ticks. Every mode's published
  frame stays finite and its simulation dt stays bounded.

### A-16: Unreachable production modules

- **Area:** dead code. **Confirmed** by the import scan; string-reference edges were included, so this under-reports.
- **Dead (no production, test or tool user):**
  - `core/lifecycle.py`;
  - `core/threading/thread_stall_detector.py`;
  - `core/windows/media_key_rawinput.py`;
  - `ui/widgets/edit_history.py`;
  - `utils/image_loader.py`;
  - `utils/profiler.py`;
  - `utils/text_utils.py`;
  - `verify_compile.py`: a root script; check whether the operator runs it by hand before deleting.
- **Used only by tests or tools** (production-dead):
  - `core/presentation_image_coherence.py`, `core/process/tuning.py`, `core/steam/events.py`,
    `core/utils/decorators.py` and `widgets/spotify_visualizer/startup_contract.py`: tests only;
  - `rendering/dwm_timing.py`: tests only; its paint-boundary sampler has no caller;
  - `rendering/gl_programs/photo_surface.py` and `vortex_flow.py`: tests only; retired transitions, see
    `Docs/Reference/Transitions.md:98`;
  - `rendering/gl_programs/lighting.py`: a test and `tools/labs/ribbon_lighting.py`;
  - `core/steam/mock_backend.py`: a test fixture, documented in `Docs/Reference/Steam_Source_Contracts.md`;
  - `core/steam/games_followed_news_probe.py`: a test and `tools/steam_followed_g0_probe.py`;
  - `ui/settings_dialog_cache.py`: a test and `tools/flicker_test.py`;
  - `ui/tabs/settings_binding.py`: 2 tests;
  - `ui/widgets/waveform_ribbon_preview.py`: 2 tests; superseded by the Studio (`Current_Plan.md` §7.1, "the old
    builder buckets are already retired").
- **Tool infrastructure** (not dead; production-unreachable by design): `core/build_qml_contract.py`,
  `core/settings/defaults_authority_audit.py`, `core/settings/defaults_snapshot_builder.py`.
- **Live through `python -m` workers** (keep): `ui/studio/{devcurve,extruded_spectrum,spectrum}_recorded_inputs.py`
  (`engine_answers.py:343`).
- **Shipped anyway:** `tools/build_layout.ps1:970-972` includes whole packages (`rendering.quick`,
  `widgets.spotify_visualizer`, `rendering.gl_programs`). Dead modules in them ship in the frozen build.
- **Cross-check:** no unreachable module is listed in `Index.md` or `Docs/Reference/Harness_Index.md`.
  `Docs/TestSuite.md` mentions only the retired programs' tests.
- **Reward:** less to read and ship. Removes false leads such as a "stall detector" or "media keys" that never run.
- **Suggested fix:** delete the dead group. For the test-only group, move true fixtures (`mock_backend`) under
  `tests/` and delete the rest together with their tests, using caller proof (`Docs/Guides/Documentation_
  Maintenance.md`). Keep the tool infrastructure.
- **Regression bar:** a test running the same reachability scan (entry points plus `python -m` workers) that fails
  on a new production module reachable from nothing, with an explicit allowlist for tool infrastructure.

### A-17: Dead ResourceManager APIs

- **Area:** dead code, resource ownership clarity. **Confirmed.**
- **Evidence:** `core/resources/manager.py`: `register_gl_handle/program/vao/vbo/texture` and `get_gl_stats`
  (`:503-640`), `acquire_image/release_image/clear_pools/get_pool_stats` (`:962-1031`). Only
  `tests/test_resource_manager.py` calls them. The `register_gl_handle` docstring says GL handles "must be
  registered immediately after creation", but no GL owner does: GL lifetime lives with the render-thread owners
  (`render_host.py:276-363`, `scene3d/*`).
- **Impact:** misleading guidance for SMP and Expanded Visualizer authors about where GL ownership is accounted.
- **Suggested fix:** delete them, and state in `Docs/Reference/Scene3D_Resources.md` that render-thread owners own
  and account for GL.
- **Regression bar:** the A-16 scan, plus deleting the corresponding tests.

### A-18: Vestigial Visualizer bucket-state keys

- **Area:** dead settings. **Confirmed.**
- **Evidence:** `core/settings/default_settings.py:275` declares `ui.visualizer_bucket_states` leaves for every
  retired builder bucket (`waveform_ribbon:ribbons` ... `bubble:reactivity` and the rest).
  `spec_mode_builder.py:68-69` reads each one only so that a missing key raises; no bucket is built.
  `bar_appearance` and `rainbow` stay live (`ui/tabs/visualizers_tab.py:482,489`).
- **Other settings keys:** the scan found no other unread leaf. Every other candidate was a dynamically built key:
  mode-prefixed `waveform_ribbon_*`, `show_<field>`, `<mode>_detail`, or transition names with spaces.
- **Suggested fix:** drop the retired leaves from the canonical default. Keep the existing tolerant normalisation of
  stored profiles (`normalize_single_open_bucket_states`), so old profiles load. Check
  `Docs/Architecture/Persisted_Input_Compatibility.md` first.
- **Regression bar:** canonical `visualizer_bucket_states` keys equal the set of buckets that a live builder
  actually constructs, derived from the registry, not pinned.

### A-19: Timer inventory

- **Area:** timers (`Spec.md`: the idle GL warm-up is the only named accepted exception). **Confirmed.**
- **Every production `ThreadManager.single_shot`** (38 sites) was checked. Each is either:
  - a bound method of a QObject owner, so it is parented and cancelled with the owner: geocode completer, styled
    popup, the Visualizers/Widgets tab save coalescers, the idle warm-up `display_manager.py:4767-4772`; or
  - a closure tagged `_srpss_runtime_generation` that holds only a weakref plus a token, so it is cancellable and
    inert when stale: weather, Reddit, Media, system stats, image pipeline, display stagger/reveal/reconcile, engine
    retry.

  Two are `partial`s whose payload re-validates its intent (`engine_handlers.py:250,802`). One unfenced lambda holds
  only a URL (`display_manager.py:5923`, the MC Reddit foreground). **No owner-less leak was found.**
- **Raw `QTimer.singleShot`, outside the registry:**
  - `widgets/spotify_visualizer/quick_display_visualizer_owner.py:1010-1013`: the mode-transition deadline. Weakref
    and serial fenced, but `cancel_scheduled_single_shots` cannot cancel it.
  - `ui/widgets/control_shadow.py:1152` and `ui/studio/waveform_recorded_inputs.py:252`: 0 ms deferrals.
  - `main.py:223` (CLI exit-after), `:617,636` (10 s auto-accept message boxes), `:680` (the opt-in ABC driver).
- **Debounce:** `widgets/media_volume_runtime.py:405-415` uses a write debounce (`_WRITE_DEBOUNCE_MS`). It coalesces
  OS volume writes and is token fenced.
- **QML:** no QML `Timer` exists anywhere.
- **Recurring timers:** rotation, RSS, usage sampler, overlay timers, clock ticker and Reddit-helper keepalive, all
  through `schedule_recurring`, with callbacks released on `deleteLater` (`core/threading/manager.py:427-467`).
- **Suggested fix:** route the visualizer-owner deadline through `ThreadManager.single_shot` with a bound slot, so a
  generation retire cancels it. Record the volume debounce in `Spec.md` as an accepted coalescing exception, or
  replace it with an edge.
- **Regression bar:** a test that runs a mode switch, then `cancel_scheduled_single_shots(generation)`, and asserts
  that the deadline callback never runs.

### A-20: COMPUTE pool sizing

- **Area:** thread pools. **Confirmed.**
- **Evidence:** `core/threading/manager.py:638-643`: `COMPUTE = max(1, cpu_count - 1)`, which is 23 workers on this
  24-thread machine. IO is a fixed 4. Real submitters are few: `engine/image_pipeline.py:1884,2092` and
  `engine/display_manager.py:4838`. Compute lanes cap at 2 (`:1003-1009`). Background work is one serial demoted lane
  (`background_tasks.py`).
- **Impact:** threads spawn lazily, so the cost is a bound, not a constant. A burst can still create many
  GIL-sharing threads, and each keeps per-thread GL-driver state for life (R-97: about 70 KB each on NVIDIA).
- **Suggested fix:** size COMPUTE from the real concurrency need, for example `min(4, displays * 2)`, and document
  the sizing in `Spec.md`.
- **Regression bar:** a test asserting the pool limit is bounded independently of `os.cpu_count()` (monkeypatched to
  64).

### A-21: Idle polling in worker processes

- **Area:** polling at rest. **Confirmed.**
- **Evidence:**
  - `core/process/workers/base.py:94,166-176`: each worker blocks on `get(timeout=0.1)` to check the parent's
    liveness, 10 wake-ups/s per idle worker (IMAGE and IMAGE_PREFETCH);
  - `core/process/supervisor.py:281`: the response listener uses `get(timeout=0.25)`;
  - plus the heartbeat thread.
- **Impact:** small, constant CPU wake-ups while the saver rests, displays off included.
- **Suggested fix:** wait on the parent's process handle together with the queue's reader handle
  (`multiprocessing.connection.wait([queue._reader, parent.sentinel])`), with no timeout.
- **Regression bar:** a worker test counting loop iterations over 2 s idle. It must be ≤ 2, against about 20 today.

### A-22: Per-generation diagnostic maps grow for the whole process

- **Area:** memory. **Confirmed;** small.
- **Evidence:** `core/threading/manager.py:31-49`: `_cancelled_ui_generations` grows by design (stale callbacks must
  stay rejected), and `_ui_diagnostics["delivered_by_generation"]` gains one entry per generation (`:303-304,
  323-324`) and is never pruned.
- **Impact:** a few bytes per Settings visit or topology change. It matters only for a multi-week SMP process.
- **Suggested fix:** prune `delivered_by_generation` together with the queued and scheduled counters once a cancelled
  generation is idle.
- **Regression bar:** after N cancelled, idle generations, `len(delivered_by_generation)` stays bounded.

### A-23: The overhead bench misses the production node fences

- **Area:** dormancy and performance evidence. **Confirmed.**
- **Evidence:** in `.artifacts/evidence/architecture/audit/20261106_audit/overhead_visualizers_run.txt`, 2D modes record
  17 GL calls per frame. That covers the render host only, not `clip_host`'s 17 state reads (A-05) or the
  background node.
- **Impact:** costs on the real QSG node path (fences, clip, background) are invisible to the tool the project uses
  to prove "no added per-frame work".
- **Suggested fix:** add a `node_path` case that drives `VisualizerClipHost.begin/end` and `BackgroundNode._draw_base`
  around one mode.
- **Regression bar:** the new case's GL and Python call counts appear in the baseline JSON and are compared.

---

## SMP and full-display readiness (summary of the blockers)

1. **The application service tier** (A-01). Nothing may outlive a display generation except process singletons;
   SMP playback, library and queue need an explicit tier.
2. **The Visualizer host** (A-02). It is bound to `DisplayManager` and docked to Media. SMP's docked Visualizer,
   Pop Out and the Expanded Visualizer need a host-neutral binding with exactly one live renderer.
   The one-owner and one-engine contracts themselves are sound (Healthy).
3. **Settings tabs and pills** (A-03). There is no tab registry and no profile gating, and the pill logic is
   duplicated. An SMP tab with pills, hidden in non-SMP builds, has no declaration point.
4. **One widget id per retained presentation** (plan 02 §3.1's own audit; `family_binder`,
   `WidgetRuntimeManager`). A two-pane Library/Playlists widget needs two member ids under one family, which the
   catalog supports (`widget_family_catalog`). Settings must group them as one entry: this lands on A-03's registry.
5. **Value ownership in Settings** (A-12). Do not copy the hidden-widget value owner into new tabs.
6. **Layout vocabulary.** Arrange and runtime Edit already share one session and commit
   (`ui/onboarding/arrange_model.py:1-12`, `rendering/custom_layout_commit.py`). This is healthy and the right base
   for "rearrange everything". The missing piece is A-02's docking policy, not a new layout engine.

## What is healthy (checked and found sound)

**Exactly one Visualizer and one beat engine**
- There is one production construction site for `QuickDisplayVisualizerOwner` (`display_manager.py:3389`). A second
  admission is rejected (`:3258-3263`). The owner is registered only after a successful start (`:3504-3505`), and
  retired on failure (`:3553-3560`).
- There is one production `_SpotifyBeatEngine` (`beat_engine.py:1936-1940`, through the registry). Studio and offline
  replays inject `ReplayBeatEngine` or recorded answers through `engine_factory` (`waveform_recorded_inputs.py:117-121`,
  run in a worker process; `engine_answers.py`), never the capture engine. `tools/visualizer_replay/record.py:80` is
  tool-only.
- Leases are symmetrical: acquire at start (`quick_display_visualizer_owner.py:1505-1530`); release and re-acquire on
  display power (`:179-221`).
- The scene-controller admissions are cleared on route release (`display_manager.py:2215-2217, 3838-3840`).

**Render resources**
- Inactive renderers are released on the render thread at the mode boundary, behind a current-context check
  (`render_host.py:276-363`), except for A-11's per-frame retry.
- Card surface materials: an all-Normal card creates nothing. The `Loader` is inactive when Normal
  (`OverlayCard.qml:99-106`), and the backdrop owner is lazy and parks (`surface_backdrop_owner.py`).
- Bench evidence: transition GL and Python call counts are identical from pre-materials `90f65ee9` to now, and the
  Visualizer counts are identical to `e61647f5` (`overhead_*_run.txt`). The size differed from the stored 2560x1440
  baselines, so the GPU deltas are not comparable; the counts are.

**Timers and threads**
- `single_shot` uses weak methods, owner parenting, generation registries and synchronous payload release
  (`manager.py:1561-1717`). `schedule_recurring` releases its callback before `deleteLater` (`:427-467`).
- Callers consistently use a weakref plus a token (A-19).

**Lifecycles**
- The Settings dialog has `WA_DeleteOnClose`, a destruction barrier watching the dialog and all its children, and its
  single-shots cancelled per generation (`engine_handlers.py:457-600`).
- `ProcessSupervisor` uses per-role lifecycle locks (`supervisor.py:76-95`). Workers watch the parent
  (`base.py:162-176`) and are daemon children with an atexit shutdown.
- Studio clip workers run in kill-on-close Job Objects (`ui/studio/worker_lifetime.py`).
- The reveal fence and display-power park/resume rebase clocks and arm the fresh-frame fence
  (`quick_display_visualizer_owner.py:210-228`; `Docs/Architecture/Compositor_Architecture.md` → Display power).
- GC is policy-owned (`core/performance/gc_policy.py`).

**Churn and dormancy**
- Steady Visualizer publications return early with no QML writes (`scene_controller.py:2159-2177`).
- The cross-thread wake is coalesced to one pending event (`quick_presentation_sync.py:57-117`).
- The usage sampler is opt-in (`main.py:698-729`), and the Windows Toolhelp path avoids the GIL-held psutil tree
  calls (`usage_sampler.py:22-27,170-246`).
- No environment-variable feature flags: the only `os.environ` writes are Qt bootstrap and BLAS threads
  (`rendering/quick/bootstrap.py:333`, `core/native_threads.py:48`).
- No `ui.studio` import outside `ui/studio` at module scope.

**Memory bounds**
- The image cache is bounded (`utils/image_cache.py:56-72`).
- Studio exact-replay checkpoints are bounded (`exact_replay.py:42,153-167`), as are the engine-answer stores and
  kwargs (`engine_answers.py:584-597, 875-876`) and the DevCurve profile cache (`devcurve_runtime.py:280-294`).

**Docs and payload**
- Every QML file under `rendering/quick/qml` and `ui/studio/qml` is referenced.
- Every `tools/*.py` is referenced by a doc, a test or another tool.
- The build's QML payload lists name only live files.

## Unrelated defects noticed (do not drop)

1. `tools/overhead_baseline.py`:
   - its default `--size 1920x1080` (`:285`) differs from every stored baseline (2560x1440), so a default
     `--compare` always prints "different size or GPU" and GPU deltas are meaningless; the warning does not say
     which of the two differs (`:227-228`);
   - in a fresh worktree every Visualizer case fails with "Qt resource pack is missing" until `tools/regen_qrc.py`
     runs; `Docs/Reference/Benchmarks.md` does not say so.
2. `rendering/quick/scene3d/waveform.py:536-537`: per frame, at large card sizes, the floor pass reads
   `GL_DRAW_FRAMEBUFFER_BINDING` and `GL_VIEWPORT` through PyOpenGL (A-05's cost class). `scene3d/ribbon.py:356,474`
   read `GL_VIEWPORT` the same way.
3. `rendering/quick/scene3d/waveform.py:593`: `_flat_ribbons` copies the whole packet with `np.frombuffer(...).copy()`
   each time it draws. Check whether it runs per frame in the reflection or flat pass before acting (allocation
   churn on the render thread).
4. `ui/tabs/media/spec_mode_builder.py:68-69` reads bucket state only so that a missing key raises (see A-18). A
   profile without those keys would make the mode page fail, unless normalisation already filled them.
5. The MC Reddit flush (`display_manager.py:5923-5930`) schedules an untagged lambda. Harmless, but it is the one
   `single_shot` caller with neither an owner nor a generation tag.
6. ThreadManager cancellation semantics: `_prune_cancelled_single_shot_generation` (`manager.py:125-133`) forgets a
   cancelled generation once its timers drain. Settings cancels only single-shots, never queued UI callbacks
   (`engine_handlers.py:572`). A late single-shot from a closed Settings generation is then admitted, unless it is
   parented to the dialog (today they are, through `_schedule_runtime_single_shot`).
