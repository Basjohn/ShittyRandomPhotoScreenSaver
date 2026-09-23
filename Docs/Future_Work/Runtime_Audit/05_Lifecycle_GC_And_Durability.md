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

## Durability notes (no action unless evidence appears)

- Replacement barrier timeout exits the app (`runtime_destruction.py:592-594`) — intended fail-closed contract.
- Settings persistence is an ordered background writer with coalescing (`json_store.py:217-255`); TX-02 is the only
  runtime path found writing Settings on a steady cadence.
