# Architecture checklist (live)

**Role:** the live, ordered checklist distilled from the one-time
[Architecture Audit of 6 Nov 2026](../Audits/Architecture_Audit_2026-11-06.md) after a second reviewer verified every
finding against the source on `8328a6d2` (7 Nov). The audit stays as evidence; this file is the work list.
`Current_Plan.md` owns admission and sequence: it links here and promotes items; an item that lands is deleted here
and its durable contract moves to its owner (`Spec.md`, `Docs/Contracts.md`, the focused doc). Nothing below is
authority over a contract; every fix must keep the "must stay true" lines.

**How to read an item:** severity (what breaks or is blocked today), reward (what the product gains), effort
(S ≤ half a day, M ≤ two days, L a multi-day slice). The owning boundary is where the fix goes; fixing a symptom
elsewhere is not accepted. Each item has a regression bar that fails when the defect returns, and dependencies.

**Verification key:** Confirmed = the code reads exactly as the audit says (7 Nov). Needs measurement = the mechanism
is confirmed but the cost or trigger is not, and the exact measurement is named. Refuted items are only in the
appendix.

---

## Tier 1: land before the application-wide work (prerequisites for SMP and full display)

These are the audit's readiness blockers (A-03, A-02, A-01). The SMP plan and the Expanded Visualizer plan
list them as prerequisite phases with the milestone each must precede. Order here is by effort and by when each is
first needed. AC-01 (the Settings tab registry with profile gating, A-12 and A-14) landed on 7 Nov; its contract is in
`Docs/Architecture/Settings_Bucket_Persistence_Contract.md` ("Tabs and pills: one registry").

- [ ] **AC-02 The Visualizer gets a host-neutral binding; Media docking becomes a declared placement policy** (A-02).
  Severity high, reward high, effort L. **Confirmed.** Lands before Expanded Visualizer M2 (the takeover transaction
  binds to this owner) and before SMP M7 (dock / Pop Out hosts).
  - **Boundary:** `engine/display_manager.py` (5952 lines). The single owner is built in
    `_construct_quick_visualizer_owner_on` (`:3245-3560`; the one construction site `:3389`; a second is rejected at
    `:3258-3263`), which also wires double-click/middle-click admissions and the volume wheel (`:3529-3550`), and
    resolves the card style itself (`:3355-3386`). Ordinary placement docks to Media through
    `_resolve_quick_visualizer_base_authored_origin` / `_resolve_quick_visualizer_authored_layout` (`:3038-3110`),
    the Media-geometry observer (`:3222-3242`) and `rendering/visualizer_media_adjacency.py`. Arrange resolves the
    Visualizer on its own path too (`ui/onboarding/arrange_model.py::_visualizer_outer_size`). Ordinary widgets go
    through `WidgetRuntimeManager` / `family_binder`; the Visualizer does not, although it is a catalog member
    (`core/settings/widget_family_catalog.py:96`).
  - **Fix:** extract `widgets/spotify_visualizer/visualizer_host_binding.py` (name illustrative) owning construct,
    bind, transfer, retire, input admissions and authored layout for one host unit; `DisplayManager` keeps only the
    "which unit" decision and calls the binding. Express Media docking as one placement policy in the canonical
    layout descriptor vocabulary (`docked_to: media | none`), resolved by the binding and read by Arrange through the
    same function, so both layout authorities become one. Keep the one-owner rejection at the binding boundary. The
    card style comes from the family binder's resolver (AC-09).
  - **Must stay true:** exactly one Visualizer owner per process across construct → transfer → retire
    (`Spec.md` → Visualizer display routing); CUSTOM authority (committed geometry wins outside Edit, override wins
    while editing); the admissions cleared on route release (`display_manager.py:2215-2217, 3838-3840`); the
    transactional cross-display transfer (`_transfer_quick_visualizer_unit`); the Edit/Arrange parity harness maps
    (`tests/test_arrange_saver_geometry_parity.py`) identical; the operator-protected QSG/clip optimisations
    untouched.
  - **Regression bar:** one owner across construct → transfer → retire with today's unit and a stub second host;
    moving Media leaves a Visualizer with `docked_to: none` in place and moves one with `docked_to: media`; the
    parity harness maps are byte-identical before and after; `DisplayManager` no longer imports
    `QuickDisplayVisualizerOwner`.
  - **Depends on:** AC-09 (border width resolver) is a convenient first step. **Unblocks:** Expanded Visualizer M2,
    SMP docked Visualizer and Pop Out, the Expanded Media milestone.

- [ ] **AC-03 An application-service tier above display generations** (A-01). Severity high (for SMP), reward high,
  effort L. **Confirmed:** `engine/engine_handlers.py:355` `engine.stop(exit_app=False, reason="settings")` owns the
  complete teardown, `:509` `dialog.exec()` is a nested modal loop, `:600` `dialog_barrier.seal()` precedes
  replacement, and `:362` exits the whole application (`QCoreApplication.exit(1)`) when teardown fails. Lands before
  SMP M2 (`LibraryRepository`) and M3 (`PlaybackService`); the Expanded Visualizer does not need it (its intent is a
  settings value re-evaluated by the next generation).
  - **Boundary:** `engine/screensaver_engine.py` (owner of `initialize` / `stop` / `cleanup`), with
    `engine/engine_handlers.py::on_settings_requested` as the consumer.
  - **Fix:** one `ApplicationServices` registry on the engine (`core/application_services.py`, name illustrative):
    `register(name, factory)`, `get(name)`, `retire(name)`, created in `initialize`, excluded from
    `stop(reason="settings")`, retired in terminal `cleanup` after the display teardown and before the ThreadManager
    shutdown (the network admission fence closes first, as today). Consumers are generation-fenced: a display
    generation leases a service and the lease is what retires with the generation, never the service. Members are
    created lazily by the first lease and only when their capability is active, so Standard SRPSS without SMP creates
    nothing. `DisplayPowerAuthority` (already process-scoped, engine-owned) is the model, not a second tier. Decide
    explicitly what a Settings-teardown failure does to live services (today: process exit; with playback live the
    answer must be recorded in `Spec.md` → Lifecycle).
  - **Must stay true:** the display teardown, destruction barrier and modal Settings stay exactly as they are for
    SRPSS and MC; "SMP live Settings" is a separate application policy (SMP plan §9); no process-global singleton
    that survives `cleanup`; the Settings dialog's generation cancellation (`cancel_scheduled_single_shots`) still
    covers everything the dialog scheduled.
  - **Regression bar:** a test opens and closes Settings through `on_settings_requested` with a stub service
    registered: the service instance is identical before and after, the destruction-barrier watch list is empty
    (no display-generation object survives), a stale generation's lease cannot reach the service, and terminal
    `cleanup` retires it exactly once. A Standard-profile start with no capability registers no service.
  - **Depends on:** nothing. **Unblocks:** SMP M2, M3, M5.

## Tier 2: defects to fix soon (small, real)

- [ ] **AC-04 A failing inactive-renderer release blacks out the active mode** (A-11). Severity medium, reward medium,
  effort S. **Confirmed by reading** `rendering/quick/visualizer/render_host.py`: `:182-183` calls
  `release_inactive_implementations` when `mode_changed or len(self._implementations) > 1`, **before** the active
  implementation renders (`:258`); `:304-329` keeps a renderer whose `release_resources` raised and then raises
  `RuntimeError`, so every following frame re-enters (the cache still holds two), raises again, and
  `rendering/quick/visualizer/node.py:394-397` records it through `RenderFailureLog` without drawing. The docstring
  promise "a later legal render can retry it" is false in effect: the card stays black until teardown. No release
  failure has been seen in logs (trigger unobserved).
  - **Fix (owning boundary: `render_host.py`):** render the active implementation first; attempt inactive release
    after it, catch its error, record it once through the lifecycle note and the failure log, and retry only at the
    next mode boundary or at `release_resources`, never per frame. Keep the current-context check and the "a failed
    release stays accounted" rule.
  - **Must stay true:** release happens on the render thread with a current context; a retired mode's resources are
    never silently dropped from the ownership snapshot; mode-boundary telemetry still advances once per switch.
  - **Regression bar:** a renderer whose `release_resources` raises, then a switch to mode B: B's `render` runs on
    every frame, the failure is recorded once (not once per frame), and the next boundary retries the release.

- [ ] **AC-05 One beat-engine authority: delete the module global and the in-tick fallback** (A-07 + A-08). Severity
  medium, reward medium, effort S. **Confirmed:** `widgets/spotify_visualizer/beat_engine.py:1973-1988`
  `get_shared_spotify_beat_engine` writes `_global_beat_engine`, which `BeatEngineRegistry.clear()` (`:1952-1969`)
  never clears and `set_engine` (`:1944-1950`) never updates; `engine/engine_lifecycle.py:292-295` force-stops
  through the global first. `widgets/spotify_visualizer/tick_pipeline.py:965-969` binds the process engine when
  `widget._engine is None`, bypassing `runtime_controller.ensure_engine()` / `_engine_factory` and the owner lease
  (`quick_display_visualizer_owner.py:1505-1530`). No production trigger of the fallback was found; a Studio or
  offline controller built without its engine would silently take the live capture engine.
  - **Fix:** `get_shared_spotify_beat_engine` returns `BeatEngineRegistry.get_instance().get_engine(bar_count)` and
    the global is deleted; `engine_lifecycle` calls only the registry's `clear()`; the tick uses
    `controller.ensure_engine()` and raises when the controller has neither an engine nor a factory. The tick must
    never resolve a process service.
  - **Must stay true:** exactly one production `_SpotifyBeatEngine` (`Docs/Contracts.md` → Transition / visualizer);
    `clear()` retains the engine while native capture ownership drains; Studio/offline paths inject through
    `engine_factory` only.
  - **Regression bar:** after `clear()` a `weakref` to the engine dies once the test drops its own reference with gc
    disabled; `set_engine(x)` then terminal stop force-stops `x`; a tick on a controller with `engine_factory=stub`
    and `engine=None` uses the stub, a tick with neither raises, and neither touches `BeatEngineRegistry`.

- [ ] **AC-06 Studio memory and GUI-thread work: bounded clip caches, off-thread clip parsing** (A-04 + A-10).
  Severity medium, reward medium, effort S. **Confirmed:** class-level `_clip_cache: dict = {}` in
  `ui/studio/waveform_adapter.py:1209`, `extruded_bubble_adapter.py:760`, `bubble_adapter.py:653`,
  `sphere_adapter.py:591`, written on every analysed clip and never evicted (keys include analysis values, so each
  Audio Analysis change is a new entry), while `ui/studio/engine_answers.py:586-597` caps its store at
  `ANALYSED_LIMIT = 24`. `ui/studio/waveform_recorded_inputs.py:262-273` parses the worker's JSON and converts it on
  the GUI thread inside `QProcess.finished`. Entry size and parse cost are **Needs measurement**: `tracemalloc`
  around `to_inputs` for one Waveform entry, and `tools/studio_drag_profile.py`-style timing of a clip switch with
  the preview rendering.
  - **Fix (owner: `ui/studio`):** route the four adapters through `engine_answers.remember/analysed` (or one shared
    `analysed_cache(mode_id)` with the same limit and the same eviction) and delete the class dicts. Do the parse and
    `_convert` on a ThreadManager IO task and publish the finished `RecordedInputs` through the existing
    `run_on_ui_thread`, fenced on the job's cancelled flag; or have the worker write the binary sidecar the
    Oscilloscope capture history already uses (`Docs/Reference/Visualizer_Studio.md` §3).
  - **Must stay true:** the Studio owns no settings, clock, engine or desktop-visualizer resources; the worker runs
    in its kill-on-close Job Object; the newest analysis wins.
  - **Regression bar:** `ANALYSED_LIMIT + 5` distinct keys through each adapter's `start_clip_load` with a stub loader
    never exceed the limit and keep the newest entries; `_on_finished` returns without calling `json.loads` on the
    GUI thread (stub worker output).
  - **Depends on:** the Studio controller leak item in `Current_Plan.md` (same owner; the leak keeps these caches
    reachable). Route both to the Studio agent.

- [ ] **AC-07 Unchanged settings writes still publish** (A-13). Severity low, reward medium, effort S. **Confirmed
  (code):** `core/settings/json_store.py:332-333` drops an unchanged write, but `SettingsManager.set`
  (`core/settings/settings_manager.py:1099-1172`) always calls `sync()` and `_publish_store_change`, which fans out to
  the Qt signal, every handler and the EventSystem bridge; `ScreensaverEngine._on_settings_changed` rebuilds
  sources on any `sources*` key. **Needs measurement** for impact: count `settings_changed` publications per
  Settings close and per preset re-application in a log before and after.
  - **Fix (owner: `SettingsManager`):** `_set_structured_value_locked` and the store's `setValue` report "changed";
    `set()` skips publication when nothing changed, except explicit migrations and `'*'` resets, which must publish.
  - **Must stay true:** a first write of an explicit `None` is a change (the store's own comment at `:329-331`);
    display-section writes stay one transaction published after coherence.
  - **Regression bar:** `set(k, v)` twice emits `settings_changed` once; setting `sources.folders` to its current
    value does not call `_on_sources_changed`; seeding a nullable default to `None` still publishes once.
  - **Why it matters for SMP:** live Settings (SMP plan §9) and the SMP tab will re-save whole groups; publication
    must mean change.

- [ ] **AC-08 One GL state-query helper; the bench sees the production node path** (A-05 + unrelated defect 2 +
  A-23). Severity low, reward medium (about 0.2 ms of GIL-held render-thread Python per Visualizer frame back, no
  pixel change), effort S. **Confirmed** code sites; cost measured offscreen by the audit (PyOpenGL
  `glGetIntegerv` 14.4 µs vs `gl_query.get_int` 3.6 µs): `rendering/quick/visualizer/clip_host.py:57` `_int_state`
  with 14 getters plus the scissor box on every clip begin (`:211-231`, `:518-519`, `:603-605`);
  `rendering/quick/render/background_node.py:145` on every background draw; `rendering/quick/visualizer/render_host.py:30`;
  `rendering/quick/scene3d/waveform.py:536-537` (`GL_DRAW_FRAMEBUFFER_BINDING`, `GL_VIEWPORT` per frame in the floor
  pass) and `scene3d/ribbon.py:356,474` (`GL_VIEWPORT`). `rendering/quick/gl_query.py` already exists for exactly this
  and `rendering/quick/visualizer/gl_state.py:30-43` is a second private copy. `tools/overhead_baseline.py` drives the
  render host only, so none of these fences are in its call counts.
  - **Fix:** replace every `_int_state` / `glGetIntegerv` on a per-frame path with `gl_query.get_int/get_ints`,
    keeping the **exact query order** (`clip_host.py:199-201` requires it; CHK25/CHK26 lineage is
    operator-protected); fold `visualizer/gl_state.py` into `gl_query`; add a `node_path` bench case that drives
    `VisualizerClipHost.begin/end` and `BackgroundNode._draw_base` around one mode.
  - **Must stay true:** no steady-frame driver queries beyond those already made; pixel output identical on the
    clip-smoke fixtures; production never re-tuned to satisfy a pixel oracle.
  - **Regression bar:** a test records the sequence of `glGet*` names in `capture()` before and after (identical);
    the bench's node-path GL and Python call counts appear in the baseline JSON and do not rise.

- [ ] **AC-09 Card border width resolved once** (A-09). Severity low, reward low, effort S. **Confirmed:** the clamp
  lives in `rendering/quick/widgets/family_binder.py:84-96` and is re-implemented in `engine/display_manager.py:3363-3370`,
  `rendering/quick/widgets/games_you_follow.py:202-203`, `rendering/quick/widgets/system_audio_osd.py:98-111`, while
  `rendering/widget_descriptors.py:3048` declares the key `"int"`.
  - **Fix:** export `resolve_card_border_width_px(widgets_config) -> float` from the defaults-helper module the
    family binder already imports, call it from all four consumers, and correct the descriptor type to the admitted
    one (float if fractional widths are admitted, else clamp to int everywhere).
  - **Regression bar:** a parametrised test feeds NaN, inf, -1, 12.5, "x" and a missing key to every consumer path
    and gets the same value from each.
  - **Depends on:** nothing; a convenient first step of AC-02.

- [ ] **AC-10 The Visualizer owner's mode-transition deadline joins the single-shot registry** (A-19). Severity low,
  reward low, effort S. **Confirmed:** `widgets/spotify_visualizer/quick_display_visualizer_owner.py:1010-1013` uses
  raw `QTimer.singleShot` (weakref and serial fenced, but `cancel_scheduled_single_shots` cannot cancel it). The
  other raw sites are 0 ms deferrals (`ui/widgets/control_shadow.py:1152`, `ui/studio/waveform_recorded_inputs.py:252`)
  and `main.py` CLI/auto-accept timers; no QML `Timer` exists; the OS-volume write debounce
  (`widgets/media_volume_runtime.py:92,415`) is token-fenced. The timer inventory is otherwise clean.
  - **Fix:** route the deadline through `ThreadManager.single_shot` with a bound slot tagged with the owner's
    generation. Record the volume write debounce in `Spec.md` as an accepted coalescing exception (it coalesces OS
    writes; it is not a cadence timer), or replace it with an edge.
  - **Regression bar:** run a mode switch, then `cancel_scheduled_single_shots(generation)`: the deadline callback
    never runs.

## Tier 3: product decision first (operator)

- [ ] **AC-11 One 3D camera control contract across every orbiting mode** (A-06). Severity medium (2D/3D consistency),
  reward medium, effort M after the decision. **Confirmed:** `engine/display_manager.py:838-841` enables Reset Camera
  and framed flight only when `spec_for_mode(mode)` exists; in `core/settings/visualizer_mode_registry.py` only Neon
  Lake (`:368`), Extruded Bubble (`:407`) and Waveform (`:436`) declare `framed_camera`; Sphere (`:298-300`) and
  Extruded Spectrum (`:332-333`) orbit with no Reset Camera and no framed flight; inertia is on for Sphere and
  Waveform only (`:300`, `:434`); turn wrap is off for Neon Lake and Waveform (`:366`, `:434`).
  - **Decision for the operator:** (a) give Sphere and Extruded Spectrum a framed-camera spec (Reset Camera to the
    preset home; they join the shared standard, `core/settings/framed_camera.py`), or (b) a camera-reset contract
    that does not need a physical camera (reset turn/tilt to the preset's authored values). Then inertia and wrap
    become declared per-mode choices with a reason in `Docs/Reference/Visualizer_Reference.md` → Live view pose.
  - **Must stay true:** the framed-camera standard is the one shared camera (memory: never per-mode cameras); a
    landscape keeps wrap off on purpose; the queued Reset Camera double-click defect (`Current_Plan.md`) is fixed at
    the in-card control, not here.
  - **Regression bar:** a registry test lists every mode with `view_orbit_settings`: each declares a reset path
    (framed spec or explicit `camera_reset: none` with a reason) and its inertia/wrap matches the reference table.
  - **Must land before** a second mode opts into the Expanded Visualizer (where the card is large and orbiting
    likely).

## Tier 4: hygiene (batch when a nearby owner is open)

- [ ] **AC-12 The Visualizer's authored clock becomes monotonic** (A-15). Severity low, reward medium, effort M.
  **Confirmed:** `widgets/spotify_visualizer/tick_pipeline.py:1412` `now_ts = time.time()` drives every mode's step
  and `beat_engine.py` uses `time.time()` at nine sites (smoothing, play ramp, keepalive), while deadlines use
  `perf_counter` (`logical_runtime.py:53-60`) and `produced_ts` defaults to `time.monotonic()` (`:204`). A clock
  step (time sync, manual change) injects a dt jump or a negative dt; only partial guards exist (`beat_engine.py:88`).
  - **Fix:** the logical runtime exposes one monotonic authored clock (`perf_counter`); the tick and the engine's
    smoothing/ramp/keepalive read it; recordings that store wall timestamps convert at their boundary.
  - **Must stay true:** Bubble Temporal Fidelity (no retune; a monotonic clock changes nothing at steady state);
    replay harnesses keep byte-identical output on recorded clips.
  - **Regression bar:** a tick test patches `time.time` to jump −5 s and +60 s between ticks: every mode's published
    frame stays finite and its simulation dt stays bounded; recorded-clip digests unchanged.
  - **Depends on:** the Waveform logical tick cut (same files; land after it to avoid a merge fight).

- [ ] **AC-13 ThreadManager and worker hygiene** (A-20 + A-22 + A-21 + unrelated defects 5 and 6). Severity low,
  reward low, effort S-M. **Confirmed:** `core/threading/manager.py:638-639` sizes COMPUTE at `cpu_count - 1` (23 on
  the operator's machine) against two real submitters and a two-lane cap; `_ui_diagnostics["delivered_by_generation"]`
  (`:48, 303, 323`) gains an entry per generation and is never pruned; `core/process/workers/base.py:94,171` wakes
  idle IMAGE / IMAGE_PREFETCH workers 10x/s (`POLL_TIMEOUT_S = 0.1`) and `core/process/supervisor.py:281` the listener
  4x/s, displays off included; `engine/display_manager.py:5923` schedules the one untagged, owner-less lambda (MC
  Reddit flush). Cancellation note: `_prune_cancelled_single_shot_generation` (`manager.py:125-133`) forgets a
  cancelled generation once its timers drain, and Settings cancels only single-shots (`engine_handlers.py:572`); a
  late single-shot from a closed Settings generation is admitted unless it is parented to the dialog (today they are,
  through `_schedule_runtime_single_shot`). AC-03's service tier must state its cancellation rule against this.
  - **Fix:** size COMPUTE from the real need (`min(4, displays * 2)`, documented in `Spec.md`); prune
    `delivered_by_generation` with the queued/scheduled counters once a cancelled generation is idle; workers wait on
    `multiprocessing.connection.wait([queue._reader, parent.sentinel])` with no timeout; tag the Reddit flush lambda.
  - **Regression bar:** the pool limit is bounded with `os.cpu_count` monkeypatched to 64; after N cancelled idle
    generations `len(delivered_by_generation)` stays bounded; a worker idle for 2 s loops ≤ 2 times (about 20 today).

- [ ] **AC-14 Dead code and dead settings sweep** (A-16 + A-17 + A-18 + unrelated defect 4). Severity low, reward low,
  effort S. **Confirmed by a production-import scan (7 Nov):** no production module imports `core/lifecycle.py`,
  `core/threading/thread_stall_detector.py`, `core/windows/media_key_rawinput.py`, `ui/widgets/edit_history.py`,
  `utils/image_loader.py`, `utils/profiler.py`, `utils/text_utils.py` (only tests/tools or nothing). The
  tests-or-tools-only group and the `python -m` workers are as the audit lists. `core/resources/manager.py`'s GL-handle
  registration and QImage pool APIs (`:503-640`, `:962-1031`) have only `tests/test_resource_manager.py` as a caller;
  the `register_gl_handle` docstring misleads about where GL lifetime is accounted (render-thread owners).
  `core/settings/default_settings.py:275` declares `ui.visualizer_bucket_states` leaves for retired builder buckets,
  read only as an existence check (`spec_mode_builder.py:68-69`; `normalize_single_open_bucket_states` keeps old
  profiles loading).
  - **Fix:** delete the dead group (check whether the operator runs `verify_compile.py` by hand first); move true
    fixtures (`core/steam/mock_backend.py`) under `tests/`; delete the rest with their tests on caller proof
    (`Docs/Guides/Documentation_Maintenance.md`); keep the tool infrastructure; delete the ResourceManager APIs and
    state in `Docs/Reference/Scene3D_Resources.md` that render-thread owners own and account for GL; drop the
    retired bucket leaves from the canonical default (check `Docs/Architecture/Persisted_Input_Compatibility.md`
    first). The frozen build includes whole packages (`tools/build_layout.ps1:970-972`), so dead modules ship until
    deleted.
  - **Regression bar:** a test runs the reachability scan (entry points plus `python -m` workers, string edges
    included) with an explicit tool-infrastructure allowlist and fails on a new production module reachable from
    nothing; canonical `visualizer_bucket_states` keys equal the buckets a live builder constructs, derived from the
    registry.

- [ ] **AC-15 Bench hygiene** (unrelated defect 1). Severity low, reward low, effort S. **Confirmed:**
  `tools/overhead_baseline.py:285` defaults to `--size 1920x1080` while every stored baseline is 2560x1440, so a
  default `--compare` always prints "different size or GPU" (`:228`) without saying which; a fresh worktree fails
  every Visualizer case until `tools/regen_qrc.py` runs and `Docs/Reference/Benchmarks.md` does not say so.
  - **Fix:** default the size to the stored baseline's, name the differing field in the warning, and document the
    resource-pack prerequisite in Benchmarks.md.

- [ ] **AC-16 Needs measurement: the flat-ribbon packet copy per frame** (unrelated defect 3).
  `rendering/quick/scene3d/waveform.py:591-596` `_flat_ribbons` copies the whole packet
  (`np.frombuffer(...).copy()`) and rebuilds a packet object each call; it runs inside the `flat` pass at `:393` on
  every frame that pass draws. **Measurement:** on the offscreen Waveform harness at the live card size, time
  `_flat_ribbons` (perf_counter around the call) and count allocations for P2 (four ribbons, strands on) over 300
  frames; act only if the median exceeds 0.1 ms or it shows in `tracemalloc` as render-thread churn. If it does, keep
  one preallocated flat buffer per packet shape and rewrite colours in place.

---

## Tier S: Settings single sources of truth (from the 7 Nov Settings SSOT audit)

Source: [Settings SSOT Audit, 7 Nov 2026](../Audits/Settings_SSOT_Audit_2026-11-07.md). The audit holds the full
evidence, fix and regression bar for each item. The lead re-checked the key lines in source and every item survived.

**Binding:** the visualizer and transition spec systems stay the single owners
(`core/settings/visualizer_mode_settings.py`, `rendering/transition_settings.py`). Every item here folds a bypass
into them.

- [ ] **AC-17 (SS-01) A theme pair's surface material lives in two places, so a "[Glass]" theme gives Normal
  cards.** P0, effort M.
  - **Cause:** `tools/generate_widget_theme_mirrors.py` deliberately drops the Settings theme's backdrop material
    from its linked Widget mirror.
  - **Fix:** project it once in `widget_counterpart_for_settings_theme`, and fill existing mirrors with that one
    key (never regenerate them: ten mirrors carry hand-edited colours).
  - **Waits on the operator's choice:** the default pair would then draw Glass cards on fresh profiles. The
    alternative is linking the 15 material themes and labelling "[Glass]" as window-only.
- [ ] **AC-18 (SS-02) Fold the audio-analysis Technical controls into each mode's spec.** P1, effort M-L.
  - Today they are declared in five places with disagreeing ranges (manual floor: 0.05 vs 0.0).
  - The settings model does not clamp them (a bar count of 500 stays 500).
  - The preset completeness check and repair fill cannot see them.
  - The registry keeps membership; the spec gains range and presentation, and a single mode filter folds in.
- [ ] **AC-20 (SS-04) The Particle, Blinds and Burn pages go through the transition spec.** P2, effort M.
  - Particle's default radius of 7 always runs as 8. Its gloss offers 10–200 where 16–128 is admitted.
  - The Particle save overwrites four fields it doesn't show with literals.
  - **Radius decision (lead):** keep what users already see, so admit a minimum of 8 and make the default 8.
- [ ] **AC-21 (SS-05) The shared Bar Appearance and Rainbow families join the spec.** P2, effort M.
  - This finishes A-12: the page builds no hidden value-owner widget.
  - One range per value: the rainbow speed range is restated in four places today.
  - The preset completeness check covers them.
  - Uses AC-18's shared-entries pattern.
- [ ] **AC-23 (SS-07) AC-01 residue.** P3, effort S. Folds into AC-14 and follows AC-18.
  - Delete about 600 dead lines of Technical widget code and the dead Advanced plumbing
    (`_auto_switch_preset_to_custom` never fires).
  - Delete a dead copy of the preset rule that wrongly admits `monitor` as a global key.
  - Retire the three bucket-state schemas through the bridge procedure.

Addenda from the same audit:
- **AC-09:** the Studio's `card_style` and the General page's integer spin also restate the border clamp.
- **AC-07:** AC-19 (landed) reuses the dialog's reset/import reload edge, never a store subscription.

---

## Where the rest of the audit went

- **Healthy** (checked, no item): one Visualizer owner and one beat engine (apart from AC-05's handle); render
  resources released at the mode boundary behind a context check (apart from AC-04); card materials dormant when
  Normal; timers weak-ref + token fenced; Settings destruction barrier; supervisor per-role locks; Studio workers in
  Job Objects; GC policy-owned; steady publications early-return; no environment-variable flags; bounded image,
  exact-replay, engine-answer and DevCurve caches; every QML file and every `tools/*.py` referenced.
- **Known elsewhere, not re-listed:** the Studio controller leak and 18 s post-Studio stall, Reset Camera reaching
  the double-click mode cycle, the Waveform logical tick starving the render thread, the 15 s usage-sample hitch, the
  Bubble `max_disp *= 0.72` side defect, the Studio exact-replay frame budget: all live in `Current_Plan.md`.

## Appendix: challenged and why

Every finding was re-read against the source; none was refuted. Changes of weight:

- **A-05 downgraded from medium to low severity.** Cost is real but about 0.2 ms per Visualizer frame of
  GIL-held Python; the measured live bottleneck is the Waveform logical tick at 8.5 ms (`Current_Plan.md` §4). Kept
  as a mechanical, pixel-identical win and merged with the per-frame waveform/ribbon getters and the bench gap.
- **A-07 and A-08 merged** (one SSOT item, same files, same bar). A-08's trigger is still unobserved in production;
  the item is kept because the SMP PCM source will add a second engine input and the fail-open path would then bind
  the wrong engine silently.
- **A-04 and A-10 merged** into one Studio item and routed to the Studio agent, who owns the controller leak that
  keeps the caches reachable. Sizes marked Needs measurement with the exact measurements.
- **A-12 and A-14 folded into AC-01.** Both are Settings-architecture facts a new SMP tab would inherit; fixing them
  in the registry slice is cheaper than three slices. A-12's docstring at `spec_mode_builder.py:64-66` contradicts
  its own behaviour and is called out.
- **A-13 kept but impact marked Needs measurement** (the count of publications per Settings close); the code fact is
  confirmed.
- **A-15 kept low** (no clock step observed; guards exist) and sequenced after the Waveform tick cut.
- **A-19 reduced to one fix**: the only timer outside the registry with a cancellation gap; the rest of the
  inventory is confirmed clean.
- **A-16/17/18 and unrelated 4 merged** into one sweep with one reachability bar.
- **A-20/21/22 and unrelated 5, 6 merged** into one ThreadManager/worker hygiene item; the cancellation note (6) is
  a design constraint for AC-03, not a defect today.
- **A-23 merged into AC-08** (the bench must see the fences the fix touches).
- **Unrelated 1 kept** as AC-15; **unrelated 3** as AC-16 (measurement, not a fix).
- **A-11 severity kept medium** although unobserved: it is a fail-closed black card with no recovery, contrary to the
  docstring, and the fix is small.
- **Added under the operator's lenses:** AC-03 now records that `on_settings_requested` exits the process when
  teardown fails (`engine_handlers.py:362`), which the service tier must decide for live playback; AC-02 records
  Arrange's separate Visualizer resolution (`arrange_model.py::_visualizer_outer_size`) as the second layout
  authority to fold; AC-01 records that product identity is answered by scattered `is_mc_build()` calls with no
  Settings declaration point, which the SMP plan's `--smp` gate and SMP-only build need.
- **Not added:** nothing nasty surfaced. No finding breaks today's product or corrupts data; the Tier 1 items are the
  real cost of the application-wide work, and they are bounded.
