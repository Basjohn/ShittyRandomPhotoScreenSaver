# 05 — Lifecycle, GC, Durability and Diagnostic Oracles

Owners audited: `engine/{runtime_destruction,engine_lifecycle,screensaver_engine,display_manager}.py`,
`core/performance/{gc_policy,event_loop_recorder}.py`, `core/threading/manager.py`, `main.py`,
`rendering/quick/{runtime,context_menu}.py`, `core/settings/{defaults,default_contract}.py`,
`core/animation/animator.py`, `utils/lockfree/*`.

**Binding:** R-53 (destruction barrier; no `gc.collect`, no event pumping), R-59, R-77 (retire residue as a
whole import/caller transaction), R-30 (timer ownership at exit), R-80 (reset telemetry epochs), R-84 (handle
churn gate + context-menu tails), R-27 (never answer pressure with more UI work).

## Verified healthy (do not re-audit)

- `RuntimeDestructionBarrier` is fail-closed, never pumps events or collects garbage; its 25 ms recheck exists
  only while a retiring generation still owns resources (`engine/runtime_destruction.py:421-458`).
- Visualizer wake/retire ordering: wake detached and closed before the authored runtime is joined
  (`quick_display_visualizer_owner.py:1050-1083`); a publication racing retire sees `_closed`.
- Feed/Games-You-Follow deadline handles are cleared when they fire, so no stop-after-delete race.
- `int(self._runtime_generation or 0)` coercions keep generation 0 valid.
- Context-menu model keeps separate `entriesChanged` / `anchorChanged` / `visibilityChanged`
  (`rendering/quick/context_menu.py:320-415`); the row Repeater binds only `entries` (`ContextMenu.qml:127-131`).
  The R-84 single-notify repair is intact.

---

## LC-06 — Canonical defaults are recomputed (~5.5 ms) on every runtime call · P1 · R2 · Risk Low

**Evidence (measured).** `get_default_settings()` (`core/settings/defaults.py:70-86`) rebuilds the raw defaults and
re-normalizes the whole visualizer section on every call: **≈5.5 ms** (idle dev machine), dominated by ~600
`require_canonical_default` lookups with deep copies inside `normalize_visualizer_section_mapping`. The result is
constant per profile (a copy is already computed at import as `CANONICAL_DEFAULTS`, `:89`). Runtime GUI-thread
callers:

| Caller | When | Cost |
| --- | --- | --- |
| `DisplayManager._quick_context_transition_state` (`display_manager.py:839, 849`) | every context-menu open | 2 calls ≈ **11 ms** |
| `resolve_quick_transition_spec` (`transitions/request_resolution.py:147`) | every image batch | ≈5.5 ms |
| `_canonical_monitor_value_for_widget` (`rendering/widget_descriptors.py:1434-1438`) via `widget_route_admits_screen` (`family_binder.py:281`) | every enabled widget × display at every runtime construction (startup, Settings, topology, slot load) | ≈5.5 ms each → tens of ms per generation |
| visualizer construction/routing (`display_manager.py:2480`, `widget_descriptors.py:2586, 2669`) | construction/CUSTOM | ≈5.5 ms each |

**Why P1.** R-84's final exit gate still requires "Context Menu open/dismiss no longer produces the prior 50+ ms
event-loop tails", and CHK21 recorded a subjective "context menu slightly less responsive" watch item. Two full
default rebuilds per open are a concrete, owner-local contributor with no visible-output role.

**Proposal.** Memoize the resolved defaults per profile (immutable/read-only tree, like
`_canonical_defaults_readonly` in `default_contract.py`) and return `deepcopy` of the cached tree (≈0.6 ms) to keep
the mutable-result contract; switch hot callers to section reads (`get_canonical_default("transitions")`,
`"display.hw_accel"`, `"widgets.<section>.monitor"`), which copy only the leaf/subtree.

**Must remain true.** Defaults authority (Defaults_Guide; `tests/test_defaults_schema_authority.py`); MC profile
overrides resolved per profile; callers that mutate get a private copy.

- [ ] Memoized + section reads; defaults-authority, context-menu and transition-resolution tests green.
- [ ] Physical: context-menu open/close responsiveness; Settings round-trip construction time in `[LIFECYCLE]`
      logs.

---

## LC-05 — Context-menu entries refresh after the menu is shown; operator's "2 QImage tasks" note · P3 · R1 · Risk Low

**Evidence.** `QuickDisplayRuntime` connects `context_menu_requested` to its own `_on_context_menu_requested` (opens
the model) **before** re-emitting it to `DisplayManager` (`rendering/quick/runtime.py:228-231`), whose handler rebuilds
entries (`display_manager.py:1348-1352` → `_refresh_quick_context_menu` `:876-940`). When entries changed since the last
open (transition/visualizer/dimming/edit state), the row Repeater rebuilds while the menu is already visible.

**Proposal.** Refresh before opening (reverse the emit order, or refresh on the edges that change entries). LC-06
removes most of the per-open cost.

**Operator note (2026-09-22): "every time the context menu is opened 2 new QImage tasks occur in the logs."**
Not reproduced from the local 2026-09-22 dev logs:

- the menu-open code path creates no images (`ContextMenu.qml` has no `Image`; entries are dicts; the halo/arrow
  cursor pixmaps are cached per shape/DPR/fade step, `cursor_controller.py:245-261`);
- the only "QImage" text in the logs is `FILL(QImage)` from `rendering/image_processor_async.py` (image processing);
  in this run those lines follow transitions/prefetch, not menu opens;
- Media `Thumbnail stream` reads landed 1–2 s after two menu opens but also occur every 4–13 s regardless (PW-01).

- [ ] Operator: capture the exact log file + lines (or a run with `--cache --perf`) showing the two tasks around a
      menu open; then classify (prefetch resume, media refresh, or a real menu-triggered image path).

---

## LC-01 — GC freeze protects only generation 0 · P2 · R2 (estimate) · Risk Medium

**Evidence (source).** `main.py:676` schedules one `gc.freeze()` 45 s after startup; `RuntimeGCPolicy`
(`core/performance/gc_policy.py:123-172`) documents that later generations are *not* frozen and that the retired
generation-0 cyclic graph stays pinned until `gc.unfreeze()` at exit ("bounded one-generation offset"). Therefore
after the first Settings/CUSTOM-slot/topology replacement, the replacement generation's long-lived set is back in
gen-2 scans — the ~28–142 ms stall class `freeze_stable_generation` was introduced to remove. The local run froze
142,875 objects and saw zero gen-2 collections in 8 minutes, but contained no replacement.

**Evidence step (no new instrumentation, no extra operator run).** The pending R-84 exit gate already asks for
3–5 Settings cycles with `--perf`: grep `[PERF][GC_POLICY] generation=2 duration_ms=` (always logged ≥10 ms) before vs
after each replacement.

**Candidate repair if confirmed.** At a replacement boundary after the destruction barrier completes:
`gc.unfreeze()` (retired gen-0 cycles become collectable by the normal cadence), then one-shot re-freeze after the new
generation warms. No `gc.collect()`, no threshold tuning (Performance contract §P2), no periodic work.

- [ ] Evidence classified from the R-84 run.
- [ ] If implemented: `tests/test_gc_freeze_lifetime.py` extended for re-freeze; RSS/USS plateau across 3–5 cycles.

---

## LC-02 — Caller-dead multi-display transition sync with a GUI-thread sleep loop · P2 · R1 · Risk Low

`DisplayManager.enable_transition_sync`, `_on_display_transition_ready` and `wait_for_all_displays_ready`
(`engine/display_manager.py:4495-4577`) have no production caller (only `tests/test_multidisplay_sync.py`). The wait
spins with `time.sleep(0.001)` for up to 1 s on the GUI thread — a forbidden "GUI sleep" pattern kept alive only by a
test. `utils/lockfree/{spsc_queue,triple_buffer}.py` have no other production user.

- [ ] Remove the three methods, the `_transition_ready_queue`/`_sync_enabled` fields, the SPSC import and
      `utils/lockfree` (after a repo-wide caller check), and the museum test, in one commit with startup/import
      closure (R-77).

---

## LC-03 — Caller-dead engine app-shared `AnimationManager` · P3 · R1 · Risk Low

`ScreensaverEngine` constructs and registers an app-shared `AnimationManager` (`engine/screensaver_engine.py:436-442`)
that no production code reads (`AnimationManager.get_app_shared` has no production caller; Settings creates its own
per dialog, `engine_handlers.py:423`). It is QWidget-era residue from the era when transitions and the visualizer
shared it (R-27).

- [ ] Remove construction/registration/cleanup (`engine_lifecycle.py:621-626`) with caller proof and tests.

---

## LC-04 — Recurring-timer gap oracle ignores rebase/restart and names retired owners · P3 · R1 · Risk Low

**Evidence.** `ThreadManager.schedule_recurring` keeps `_last_invoke_ts` in the wrapper closure
(`core/threading/manager.py:1671-1715`). `ScreensaverEngine._rebase_rotation_timer` (`screensaver_engine.py:1521-1544`)
restarts the countdown on every manual next/previous without resetting that timestamp, so repeated manual rotations
produce huge "gaps" on the next natural fire — matching R-87's unexplained `_on_rotation_timer` 172,987 ms /
152,734 ms warnings "around manual/image-transition/timer-reset activity". The classifier
(`manager.py:236-362`) still looks for `MediaWidget`, AnimationManager hand-off and `get_transition_snapshot`, none of
which exist in the Quick runtime, so every such gap is labelled `unknown_ui_thread_stall`.

- [ ] Give `schedule_recurring` timers an epoch reset used by restart/rebase (perf-gated diagnostic only; R-80 rule);
      delete the retired-owner classifier branches and their tests; keep the warning for genuine gaps.

---

## Durability notes (no action unless evidence appears)

- Replacement barrier timeout exits the app (`runtime_destruction.py:592-594`) — intended fail-closed contract.
- Settings persistence is an ordered background writer with coalescing (`json_store.py:217-255`); TX-02 is the only
  runtime path found writing Settings on a steady cadence.
