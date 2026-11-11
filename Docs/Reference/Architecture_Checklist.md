# Architecture checklist (live)

**Role:** the live, ordered checklist distilled from the one-time
[Architecture Audit of 6 Nov 2026](../Audits/Architecture_Audit_2026-11-06.md) after a second reviewer verified every
finding against the source on `a295697c` (7 Nov). The audit stays as evidence; this file is the work list.
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
`Docs/Architecture/Settings_Bucket_Persistence_Contract.md` ("Tabs and pills: one registry"). AC-02 (the host-neutral
Visualizer binding with Media docking as the declared `docked_to` placement policy, A-02) and AC-09 (one card border
width resolver, A-09) landed on 7 Nov; their contracts are in `Spec.md` ("Visualizer display routing", "Geometry /
CUSTOM", "Runtime Widget Themes") and the Visualizer change checklist §9A. AC-03 (the application-service tier
above display generations, A-01) landed on 7 Nov; its contract, including the Settings-teardown failure rule, is in
`Spec.md` → Lifecycle ("Application services") and `Docs/Contracts.md`, with `tests/test_application_services.py` as
its bar. Tier 1 is complete.

## Tier 2: defects to fix soon (small, real)

AC-10 (the Visualizer owner's mode-transition deadline joins the single-shot registry, A-19) landed 7 Nov; its rule,
with the Media volume write debounce recorded as an accepted coalescing exception, is in `Spec.md` ("Delayed runtime
callbacks join the single-shot registry").
AC-07 (unchanged settings writes no longer publish, A-13) landed 7 Nov; its rule is in `Docs/Contracts.md` ("A
settings publication means a change"). Tier 2 is complete.

## Tier 3: product decision first (operator)

None open (AC-11 landed 7 Nov: `Docs/Reference/Visualizer_Reference.md` → Live view pose).

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
  through `_schedule_runtime_single_shot`). The AC-03 service tier's rule (`Spec.md` → Lifecycle): a retired
  generation's leases are revoked at the same edge and it can never lease again, so such a late callback still cannot
  reach a service.
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

None open (AC-17, the last, landed 7 Nov: a theme pair's card material is owned by its Widget mirror,
`Docs/Architecture/Card_Surface_Materials.md` section 4).

Addenda from the same audit:
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

## Landed slice notes (moved from `Current_Plan.md`, 11 Nov 2026)

Facts of the 7-8 Nov landings that no contract doc carried; the contracts themselves stay where the sections above
point.

- **AC-02:** an oversized authored Visualizer (no Media card, as large as the display) reported an off-display origin
  (the saver projected its origin and stacking obstacle at the 30 px margin while the presentation drew it clamped at
  0); the shared placement now clamps, as Arrange always did (drawn pixels unchanged). The owner and its click
  admissions no longer hold `DisplayManager` strongly: the layout-profile resolver, transition-failure callback and
  the double/middle-click and wheel admissions reach it through the binding's weak services and ignore a late click
  once it is gone. 324 Arrange cases are byte-identical. Expanded Visualizer M1's takeover events cannot be fenced by
  the engine generation (`BeatEngine._commit_activation_generation` advances generation and activation together on
  every preset and mode activation), so the coordinator uses its own owner-admission serial.
- **AC-04, AC-05, AC-06:** the active mode draws first and a failed release is recorded once and retried at the next
  boundary (AC-04); one beat-engine authority, 94 replays byte-identical (AC-05); the Studio's clip caches are bounded
  and the clip parse runs off the GUI thread (AC-06). Reset Camera: in-card controls own their double-click, so it
  never cycles the mode.
- **AC-07, AC-10:** two no-edit saves drop from 38 publications to 2; the mode-transition deadline joins the
  single-shot registry.
- **AC-08:** one GL state-query helper on every per-frame fence, in the same order; on the node path Python calls fall
  1609 -> 1216 and render-thread CPU 0.68 -> 0.51 ms; clip smoke and the render-node pixel tests pass, protected
  lineage untouched.
- **AC-11:** Sphere and Extruded Spectrum reset to their preset home through the in-card glyph and the R key; home and
  orbit renders are byte-identical before and after (single-sample). Operator (7 Nov): Extruded Spectrum does not
  coast; a released drag stops dead (inertia stays off). The one-pixel `test_waveform_floor_give.py` flake was MSAA
  rasterisation noise, so the test renders single-sample.
- **AC-12:** the authored clock is monotonic (`core/authored_clock.py`), every visualizer-path `time.time()`
  converted; 88/88 replays across all nine modes are byte-identical to main; no external wall-clock timestamp reaches
  the clock path.
- **AC-13 slice:** only the terminal owner's shutdown cancels every single-shot; a helper cancels only its own work.
  The s_hotkey exit hang was the display-window guard's `pytest.skip` escaping production's show-failure path and
  abandoning a running logical runtime; the guard now raises an ordinary error that production retires after, and the
  file exits in 9 s instead of 900.
- **Lifecycle backstop and Settings round-trip harness:** terminal retirement runs once even after a bare `exit(1)`;
  `tools/visualizer_live_check.py --settings-roundtrip AT,...` drives the real Settings path invisibly and fails the
  run on a barrier timeout, a reveal without a re-freeze or an early exit.
