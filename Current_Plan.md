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

- [ ] 1. Audit `core/animation/animator.py`.
  - Why this is next:
    - it is central enough to affect fades, timers, and lifecycle behavior,
    - the higher-risk settings/descriptors/setup seams are now materially tightened,
    - it is the next best shared-timing/lifecycle authority to verify before future feature work stacks more behavior on top.
  - Audit checklist:
    - verify animation registration and cleanup ownership are centralized and consistent,
    - identify any widgets or helpers still bypassing the central animation/lifecycle seam in risky ways,
    - assess timer churn, cleanup behavior, and whether any fade/animation responsibilities have drifted outward.
  - Guardrails:
    - preserve current working visual/fade behavior unless the audit proves a contract violation.
  - Hopeful outcome:
    - cleaner animation ownership and lower long-term timing/leak risk.

- [ ] 2. Audit `core/process/supervisor.py`.
  - Why this follows animator:
    - it matters for startup/close reliability and any future performance/process work,
    - but it is less entangled with day-to-day widget-extension cost than the items above.
  - Audit checklist:
    - verify worker lifecycle ownership, restart/cleanup boundaries, and failure handling are explicit,
    - identify any quiet process ownership assumptions that could affect close reliability or future workload expansion,
    - assess whether image/rss/transition worker seams are still the right abstractions.
  - Guardrails:
    - no speculative concurrency expansion from this audit alone,
    - preserve current worker behavior unless a real lifecycle defect is found.
  - Hopeful outcome:
    - more confidence in startup/close/process cleanup behavior and a clearer basis for future perf/process decisions.

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
- Legacy widget stacking is still intentionally active for authored anchor-based layouts. It is not a general removal candidate yet; only its interaction with `Custom` remains disabled by contract.
- Imgur raise-path cleanup/testing is not active work while Imgur remains inactive. Revisit only if the widget is reactivated or if a shared overlay-system change would otherwise leave the dormant path stale.
- Reassessing residual opacity-effect invalidation is not active work. Revisit only if a concrete shadow/effect corruption issue resurfaces.
- Further visualizer residue reduction is deferred. Only reopen `_spotify_visualizer.py`, `spotify_visualizer_widget.py`, or deeper `spotify_bars_gl_overlay.py` work if a concrete regression appears or a clearly higher-value feature cannot proceed safely without it.

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
