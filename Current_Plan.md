# Current Plan

Last updated: 2026-05-24

This file tracks active work only. Ongoing architecture truth belongs in the relevant reference docs, while dated severe/complex bug narratives belong in `Docs/Historical_Bugs.md`.

## Guardrails
- Keep this aligned with `Spec.md`, `Index.md`, `Docs/Guardrails.md`, and `Docs/Historical_Bugs.md`.
- Prune validated work aggressively. Once a milestone is materially landed and no longer driving active decisions, collapse it instead of letting this plan become a changelog.
- Keep harnesses/probes intact unless explicitly asked to retire them.
- Treat `presets/visualizer_modes/` as authored content. Tests may validate schema/index/repair behavior, but must not force exact preset names, slots, or creative numeric values.
- Do not close visual/runtime bugs from tests alone when symptoms are user-visible.
- Avoid broad focus, window-flag, compositor, widget-shadow, visualizer, or Qt effect rewrites unless the current task directly requires them.

## Active Tasks

- Stabilize recreated-display input/startup regressions from the latest CUSTOM/settings runtime reload path.
  - Trace active repros with the CLI-sidecar logging set instead of broad env-driven noise:
    - `--geo` for z-order, grid, menu, CUSTOM layout, and display-stack issues
    - `--life` for widget/worker/engine lifecycle and rebuild order issues
    - `--set` when a repro appears to involve restore/import/settings mutation drift
  - Verify stale pointer events cannot hit newly recreated fullscreen displays after save/revert/settings entry.
  - Verify first-image startup on cold/recreated displays uses bounded immediate retry instead of leaving a display blank until the long rotation timer.
  - Consolidate edit-mode stack ownership so background clicks, shell context-menu requests, and menu show/hide all use one deferred session-level restack contract instead of overlapping immediate raise/popup layers.
  - Verify edit-mode restack/menu paths do not force-show or force-update overlays/shells in ways that flash the grid or flicker widgets, draw the grid above the context menu, or let the menu appear under a compositor/display.
  - Expected outcome:
    - revert/settings reload returns all displays/compositors cleanly,
    - left-click/double-click cannot destroy or hide freshly recreated displays,
    - right-click no longer flashes the grid or broad-flickers widgets,
    - moved shells remain visible across cross-display edit interactions.

- Audit and fix duplicate widget lifecycle/setup activation during display rebuilds.
  - Trace the current duplicate-init path with `--life` from `rendering/widget_setup_all.py`, `rendering/display_setup.py`, and any follow-on lifecycle entry hooks.
  - Confirm which layer is authoritative for widget `initialize()` / `activate()` during ordinary startup, settings rebuild, and CUSTOM runtime reload.
  - Remove the second initialization/activation pass instead of suppressing the log symptom.
  - Verify rebuilt displays no longer log `Cannot initialize ... from state ACTIVE` for widgets already started by the canonical setup seam.
  - Expected outcome:
    - one clear lifecycle authority during display setup,
    - cleaner rebuild traces,
    - less churn around fade/startup/edit-mode reload interactions.

- Audit whether overlay-effect/shadow cache invalidation paths still provide real value after the painted-shadow migration.
  - Inventory every production caller of overlay/effect invalidation and separate painted-shadow-era compatibility code from still-needed runtime cache refresh paths.
  - Confirm whether any current environment still benefits from the all-display menu/open invalidation behavior, or whether it is now just flicker/churn risk.
  - Keep valid non-shadow cache refresh paths if they still solve real Qt/runtime issues; remove only the obsolete corruption-era invalidation behavior.
  - Validate against settings entry, context-menu open/close, edit mode, and cross-display interactions so we do not regress legitimate cache refresh needs.
  - Expected outcome:
    - no stale shadow-corruption cargo-cult behavior,
    - less visual churn during menus/edit-mode,
    - a documented distinction between real effect-cache maintenance and obsolete shadow-fix invalidation.

## Watchlist
- Keep visualizer preset/settings drift in view during later audits:
  - preserve CLEAR-then-APPLY semantics,
  - do not reintroduce a second post-overlay merge phase,
  - do not reintroduce entry-point-specific fallback behavior for visualizer settings.
- Visualizer first-frame / first-bar authority remains a cold watch item, not active implementation work, unless one of the audits above exposes a concrete regression path touching it.

## Deferred / Not Active
- Parallelism policy stays profiling-driven if performance work is reopened:
  - profile first and identify a real hotspot before changing thread/process counts,
  - prefer isolated pure-compute kernels or process-safe workloads, not Qt/UI/OpenGL ownership paths,
  - treat visualizer mode work as eligible for more off-thread compute only when it can be expressed as snapshot-in / result-out without thread-affinity side effects,
  - treat another process as more likely than another generic Python thread if a future hotspot is both heavy and sufficiently isolated.
- Imgur raise-path cleanup/testing is not active work while Imgur remains inactive. Revisit only if the widget is reactivated or if a shared overlay-system change would otherwise leave the dormant path stale.



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
