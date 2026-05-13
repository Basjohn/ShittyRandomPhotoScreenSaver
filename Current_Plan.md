# Current Plan

Last updated: 2026-05-13

This file tracks active work only. Completed implementation details belong in `Docs/Historical_Bugs.md` or the relevant reference docs, not here.

## Guardrails
- Keep this aligned with `Spec.md`, `Index.md`, `Docs/Guardrails.md`, and `Docs/Historical_Bugs.md`.
- Keep harnesses/probes intact unless explicitly asked to retire them.
- Treat `presets/visualizer_modes/` as authored content. Tests may validate schema/index/repair behavior, but must not force exact preset names, slots, or creative numeric values.
- Do not close visual/runtime bugs from tests alone when symptoms are user-visible.
- Avoid broad focus, window-flag, compositor, widget-shadow, visualizer, or Qt effect rewrites unless the current task directly requires them.

## Active Tasks

1. `V-04` — Add the deleted-widget validity guard to `widgets/media_layout.py` deferred position nudge.
Core value: small bounded closure/stability fix for a classic post-destruction timer callback hazard.

2. `V-03` — Register the remaining `MediaWidget` raw `QTimer(self)` fallback with `ResourceManager`, or prove the current parent-owned path is intentionally exempt and safe.
Core value: lifecycle/closure correctness with low implementation risk.

3. `T-05` / `V-01` follow-through — add/finish lifecycle coverage for Weather retry timer cleanup and Gmail fallback timer teardown behavior.
Core value: converts timer-heavy widget cleanup from assumption to regression signal without broad runtime rewrites.

4. `V-11` — Review `MediaWidget` synchronous `repaint()` calls and downgrade to `update()` only if runtime responsiveness remains acceptable.
Core value: modest performance/input-path improvement, but only if it does not reduce visible feedback quality.

5. `T-01` / Imgur raise workaround — add the missing regression test first, then investigate whether the explicit `raise_()` workaround can be normalized back through overlay-manager ownership without reopening focus/Z-order regressions.
Core value: expandability and overlay-system correctness.

6. Structural follow-through — last priority only, and only after the lower-risk items above.
Core value: long-term expandability/maintainability, not near-term stability.
- This item is already partially complete and the older audit wording is stale:
  - `core/settings/models.py` has already been split into the `core/settings/models/` package.
  - `widgets/spotify_visualizer_widget.py` already offloaded meaningful seams into `widgets/spotify_visualizer/startup_staging.py`, `startup_contract.py`, `card_paint.py`, `media_bridge.py`, and `engine_lifecycle.py`.
- Remaining real work, if ever chosen, is the harder residue:
  - further reducing `core/settings/models/_spotify_visualizer.py`,
  - further shrinking `widgets/spotify_visualizer_widget.py`,
  - and only then considering any deeper structural work around `widgets/spotify_bars_gl_overlay.py`.
- `widgets/spotify_bars_gl_overlay.py` prewarm `repaint()` review (`V-12`) is explicitly barred from accidental implementation. Treat it as dangerous by default because it risks reopening the first-bar / prewarm visualizer bug family.

## Watchlist
- Mute button fade-in reliability under startup event pressure.
- Transition random mode actual distribution vs expected uniform over long runtime.
- Settings destructive-flow checks: reset/import when touching settings architecture.
- Settings cache stale-read behavior after section/root writes.

## Deferred / Not Active
- `card_height.py` centralization is not active work. Revisit only if a focused sizing bug justifies it.
- Reassessing residual opacity-effect invalidation is not active work. Revisit only if a concrete shadow/effect corruption issue resurfaces.

## Documentation Rule
- Architecture: `Spec.md`
- Module map: `Index.md`
- Policy: `Docs/Guardrails.md`
- Dated regressions: `Docs/Historical_Bugs.md`
- Drift-check routine: `Docs/Documentation_Maintenance.md`
- Harness reference: `Docs/Harness_Index.md`

#######
### User Task Box: NEVER remove this box/section, only integrate its tasks into the active plan and then remove the text BELOW prompting the tasks.
----
----
######
