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

1. `core/settings/models/_spotify_visualizer.py` residue reduction — first major code task.
Core value: best long-term payoff-to-risk ratio among the remaining structural items.
- Why this before widget/runtime residue:
  - it improves the settings/preset seam that every future visualizer change touches,
  - it is less dangerous than runtime/GL coordinator work,
  - it reduces the chance that future expandability work keeps paying a serialization tax.
- Implementation guardrails:
  - preserve `from_settings()`, `from_mapping()`, and `to_dict()` as one coherent contract,
  - preserve CLEAR-then-APPLY preset semantics; do not introduce a second merge phase,
  - keep `normalize_visualizer_section_mapping(...)` reaching the full canonical model path,
  - prefer extracting tightly-scoped helpers/data groupings over renaming or API churn.
- Required validation:
  - run `tests/test_settings_schema.py`,
  - run the relevant visualizer sections of `tests/test_visualizer_settings_plumbing.py`,
  - keep `tests/test_settings_manager.py` normalization-idempotency coverage green.
- Progress note:
  - the first safe slice is already in place: `from_settings()` and `from_mapping()` now share one constructor-payload builder, and persisted `visualizers_enabled` no longer gets dropped on the `from_settings()` path.
  - the next residue slice is also in place: reader/preset-resolution branching is now pulled into dedicated helpers so future ingestion changes do not require re-editing both mapping/settings paths line-by-line.
  - the serialization side is now starting to match that cleanup: `to_dict()` offloaded its preset/per-mode/devcurve/transient-mix sub-blocks into dedicated helpers, which lowers the cost of future visualizer settings additions without changing saved keys.

2. `widgets/spotify_visualizer_widget.py` coordinator residue reduction — second major code task.
Core value: reduces future startup/mode-switch/activation churn without touching the dangerous GL overlay yet.
- This is already partially complete:
  - startup staging, startup contract, card paint, media bridge, and engine lifecycle have already been extracted.
- Remaining work should target only the coordinator residue that is still clearly separable.
- Implementation guardrails:
  - do not reintroduce display-local secondary-stage scheduling,
  - preserve `_waiting_for_fresh_engine_frame` and activation/source-generation protections,
  - preserve Sine paused-idle behavior and the existing startup ownership contract,
  - keep preset/runtime activation flow unified through the current resolved payload path.
- Required pre-work:
  - add the remaining regression guards from `Audit 09` before moving much logic:
    - startup staging still reveals through manager/coordinator ownership,
    - fresh-engine-frame gate still blocks stale post-reset pushes.
  - progress note:
    - the startup-staging-through-coordinator guard is now in `tests/test_widget_manager.py`, and the fresh-frame / waveform / crossover gating guards in `tests/test_spotify_visualizer_widget.py` now target the real reset-generation contract instead of stale pre-split monkeypatch assumptions.

3. Visualizer test maintainability follow-through — do this alongside or immediately after Tasks 1 and 2.
Core value: makes the future architecture work cheaper instead of letting the biggest test files become their own blocker.
- Scope:
  - split `tests/test_visualizer_settings_plumbing.py` by subsystem/mode,
  - audit `tests/test_spotify_visualizer_widget.py` for duplicate setup and extract helpers where justified,
  - add rationale comments where raw `threading.Thread()` remains intentionally used in tests.
- Rule:
  - this is not busywork cleanup; only do the split when it directly improves refactor safety or runability for the structural tasks above.
- Progress note:
  - the first worthwhile maintainability slice is now in place: `tests/test_spotify_visualizer_widget.py` has a shared engine-patching helper that patches both the widget-local and extracted beat-engine seams, and the full file is green again after the architecture split.

4. Expandability groundwork — start only after the two visualizer residue tracks are in a healthier state.
Core value: highest future feature payoff, especially for eventual new widgets/transitions.
- Recommended order from the audited architecture queue:
  1. widget descriptor/registry system,
  2. shared async/service-backed widget contract,
  3. descriptor-driven widget settings composition,
  4. stronger transition registry/descriptor layer,
  5. extension-path contract tests.
- Why this is not first:
  - it is the broadest architecture move left,
  - it will land more cleanly after the existing visualizer/settings residue is reduced.

## Watchlist
- Gmail/OAuth is not an active blocker for planning purposes. The threading/test seam is closed enough; do not hold the larger architecture queue on manual Gmail validation.
- `widgets/spotify_bars_gl_overlay.py` remains intentionally out of scope until the earlier residue work is done and the extra safety net in `Audit 09` exists.

## Deferred / Not Active
- Imgur raise-path cleanup/testing is not active work while Imgur remains inactive. Revisit only if the widget is reactivated or if a shared overlay-system change would otherwise leave the dormant path stale.
- `card_height.py` centralization is not active work. Revisit only if a focused sizing bug justifies it.
- Reassessing residual opacity-effect invalidation is not active work. Revisit only if a concrete shadow/effect corruption issue resurfaces.
- `widgets/spotify_bars_gl_overlay.py` structural work is deferred behind explicit caution. Do not "helpfully" pick it up while working nearby files.

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
