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
    landscape keeps wrap off on purpose; an in-card control consumes its own double-click
    (`Docs/Guardrails/Visualizer_Presentation.md` §14A).
  - **Regression bar:** a registry test lists every mode with `view_orbit_settings`: each declares a reset path
    (framed spec or explicit `camera_reset: none` with a reason) and its inertia/wrap matches the reference table.
  - **Must land before** a second mode opts into the Expanded Visualizer (where the card is large and orbiting
    likely).

## Tier 4: hygiene (batch when a nearby owner is open)

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
  - **Landed 7 Nov (one slice):** only the terminal manager cancels every pending `single_shot`. `ThreadManager.shutdown`
    called the global `cancel_all_scheduled_single_shots()` for any manager, so a Settings/CONFIG helper manager's
    shutdown cancelled other owners' delayed callbacks. The runtime engine's manager is now `terminal_owner=True` and
    is the only one that does; a helper cancels only its own pools
    (`tests/test_thread_manager_shutdown_scope.py`, with the terminal negative control). The items above remain.

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

Addenda from the same audit:
- **AC-09:** the Studio's `card_style` and the General page's integer spin also restate the border clamp.
- **AC-07:** AC-19 (landed) reuses the dialog's reset/import reload edge, never a store subscription.

---

## Where the rest of the audit went

- **Healthy** (checked, no item): one Visualizer owner and one beat engine (one registry holder, controllers by factory); render
  resources released at the mode boundary behind a context check, after the active mode draws; card materials dormant when
  Normal; timers weak-ref + token fenced; Settings destruction barrier; supervisor per-role locks; Studio workers in
  Job Objects; GC policy-owned; steady publications early-return; no environment-variable flags; bounded image,
  exact-replay, engine-answer and DevCurve caches; every QML file and every `tools/*.py` referenced.
- **Known elsewhere, not re-listed:** the Studio controller leak and 18 s post-Studio stall, the Waveform logical tick starving the render thread, the 15 s usage-sample hitch, the
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
