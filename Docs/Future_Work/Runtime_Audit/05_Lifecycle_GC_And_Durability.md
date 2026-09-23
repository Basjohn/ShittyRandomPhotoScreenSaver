# 05 — Lifecycle, GC, Durability and Diagnostic Oracles

Owners audited: `engine/{runtime_destruction,engine_lifecycle,screensaver_engine,display_manager}.py`,
`core/performance/{gc_policy,event_loop_recorder}.py` (LC-01 closed: 06 §Considered and rejected),
`core/threading/manager.py`, `main.py`,
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

## LC-06 — Canonical defaults were recomputed (~5.5 ms) on every runtime call · P1 · R2 · Risk Low · `[~]`

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

- [x] Memoized (`_resolved_defaults_readonly`, built once per profile; full copy now ≈0.86 ms) + resolved section
      reads (`get_default_setting`, 3–96 µs) on the context-menu, transition-batch and widget-routing paths;
      `tests/test_defaults_memoization.py`, defaults-authority, context-menu and transition-resolution tests green.
- [ ] Physical: context-menu open/close responsiveness; Settings round-trip construction time in `[LIFECYCLE]`
      logs.

---

## LC-05 — Context-menu entries refresh after the menu is shown · P3 · R1 · Risk Low · `[~]`

**Evidence.** `QuickDisplayRuntime` connects `context_menu_requested` to its own `_on_context_menu_requested` (opens
the model) **before** re-emitting it to `DisplayManager` (`rendering/quick/runtime.py:228-231`), whose handler rebuilds
entries (`display_manager.py:1348-1352` → `_refresh_quick_context_menu`). When entries changed since the last open
(transition/visualizer/dimming/edit state), the row Repeater rebuilds while the menu is already visible. Measured
2026-09-23: 6.6 ms median (15.5 ms first) per refresh after LC-06.

**Decision (operator 2026-09-23): Do.** Make the refresh of the retained menu entries complete before `open_at()` with
the smallest ordering change. `QuickContextMenuModel.replace_entries()` already returns early on an unchanged tuple
(`rendering/quick/context_menu.py:375`) and stays the only "entries unchanged" authority: no competing equality cache,
no new menu-state owner.

- [x] Refresh-before-show: `QuickDisplayRuntime` now connects the relay to `DisplayManager` before its own
      `_on_context_menu_requested`, so the product refresh completes before `open_at()` (the only open path).
      Single-menu enforcement (driven by `visibilityChanged`), focus/Ctrl semantics and action admission unchanged.
      Bar: `test_qtquick_h_cutover.py::test_context_menu_entries_are_refreshed_before_the_menu_becomes_visible`
      (fails with the old order); context-menu, input and runtime-purity suites green.
- [ ] Physical: open the menu after Next / a transition change / dimming toggle — no visible row rebuild.

**Resolved operator note — "2 QImage tasks per context-menu open".** The 2026-09-22 22:53–22:59 run shows every
`FILL(QImage)` pair (one line per display, `rendering/image_processor_async.py`) lands 5–11 s after an image change —
the prefetcher pre-scaling the next images — whether or not a menu is open. The observed workflow (Next, then open the
menu to pick a transition) puts that pair inside the menu window; menu opens without a recent rotation show none. The
menu path creates no images.

---

## Durability notes (no action unless evidence appears)

- Replacement barrier timeout exits the app (`runtime_destruction.py:592-594`) — intended fail-closed contract.
- Settings persistence is an ordered background writer with coalescing (`json_store.py:217-255`); TX-02 is the only
  runtime path found writing Settings on a steady cadence.
