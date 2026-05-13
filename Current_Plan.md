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

1. Structural follow-through — last priority only, and only after the lower-risk items above.
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
- No immediate watchlist items. Next non-urgent value work is structural follow-through only.

## Deferred / Not Active
- Imgur raise-path cleanup/testing is not active work while Imgur remains inactive. Revisit only if the widget is reactivated or if a shared overlay-system change would otherwise leave the dormant path stale.
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
