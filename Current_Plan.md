# Current Plan

Last updated: 2026-05-14

This file tracks active work only. Completed implementation details belong in `Docs/Historical_Bugs.md` or the relevant reference docs, not here.

## Guardrails
- Keep this aligned with `Spec.md`, `Index.md`, `Docs/Guardrails.md`, and `Docs/Historical_Bugs.md`.
- Keep harnesses/probes intact unless explicitly asked to retire them.
- Treat `presets/visualizer_modes/` as authored content. Tests may validate schema/index/repair behavior, but must not force exact preset names, slots, or creative numeric values.
- Do not close visual/runtime bugs from tests alone when symptoms are user-visible.
- Avoid broad focus, window-flag, compositor, widget-shadow, visualizer, or Qt effect rewrites unless the current task directly requires them.

## Active Tasks

1. `core/settings/models/_spotify_visualizer.py` residue reduction — current highest-value implementation target.
Core value: best long-term payoff-to-risk ratio among the remaining structural items.
- Why this is now first:
  - it improves the settings/preset seam that every future visualizer change touches,
  - the recent startup/perf/first-frame triage is healthy enough that we can move back to long-value structural work,
  - it reduces the chance that future expandability work keeps paying a serialization/preset-activation tax.
- Implementation guardrails:
  - preserve `from_settings()`, `from_mapping()`, and `to_dict()` as one coherent contract,
  - preserve CLEAR-then-APPLY preset semantics; do not introduce a second merge phase,
  - keep `normalize_visualizer_section_mapping(...)` reaching the full canonical model path,
  - prefer extracting tightly-scoped helpers/data groupings over renaming or API churn.
- Detailed next slices:
  - keep the landed shared constructor-state helper intact so `from_settings()` and `from_mapping()` no longer carry separate active-mode/preset assembly logic,
  - keep the landed shared per-mode technical serialization/resolution maps intact so mode technical additions do not need separate serializer and resolver edits,
  - keep the landed shared default-list maps plus core/blob-shape/transient serializer helpers intact so small settings-group changes stop being hand-maintained in multiple spots,
  - keep the landed osc/blob, spectrum, sine, and bubble serializer maps intact so the major non-devcurve serializer groups no longer drift independently,
  - keep the landed devcurve build/default/serializer consolidation intact so the last major handwritten mode family does not silently diverge from the shared settings-model contract,
  - keep the landed osc/blob, sine, and blob-shape build maps intact so more of the ingestion path now follows shared data-driven field specs instead of bespoke `read_value(...)` dicts,
  - keep the landed core, spectrum, and bubble build maps intact so the remaining high-traffic ingestion families follow the same shared field-spec path while preserving their legacy fallback semantics,
  - keep the landed ordered grouped constructor/persistence merges intact so `from_settings()`, `from_mapping()`, and `to_dict()` stop carrying subtly separate field group sequencing knowledge,
  - consolidate the remaining split serializer/build paths so grouped field families, defaults, and merge order stay single-source instead of drifting between entry points,
  - isolate mode-family data groups explicitly:
    - spectrum/osc/blob,
    - sine,
    - bubble,
    - Spline Curve (`devcurve`),
    - per-mode technical settings,
    - preset indices and transient mixes,
  - remove remaining one-off fallback logic where the same field family still resolves differently depending on which entry point touched it first,
  - keep canonical default-mode resolution flowing through `core/settings/visualizer_mode_registry.py` and canonical defaults rather than hidden local fallback assumptions,
  - add regression coverage exactly where helper extraction changes contract risk, not broad smoke-only additions.
- Progress note:
  - the grouped field-spec/default/build/serialize path is now in much healthier shape across the major mode families and ordered constructor/persistence merges. Treat Task 1 as nearing completion; prefer only small targeted follow-throughs here before shifting real effort into Task 2.
- Required validation:
  - run `tests/test_settings_schema.py`,
  - run the relevant visualizer sections of `tests/test_visualizer_settings_plumbing.py`,
  - keep `tests/test_settings_manager.py` normalization-idempotency coverage green.

2. `widgets/spotify_visualizer_widget.py` coordinator residue reduction — next structural follow-through after Task 1.
Core value: reduces future startup/mode-switch/activation churn while keeping the GL overlay authority boundaries explicit.
- This is already partially complete:
  - startup staging, startup contract, card paint, media bridge, and engine lifecycle have already been extracted.
- Remaining work should target only the coordinator residue that is still clearly separable.
- Implementation guardrails:
  - do not reintroduce display-local secondary-stage scheduling,
  - preserve `_waiting_for_fresh_engine_frame` and activation/source-generation protections,
  - preserve Sine paused-idle behavior and the existing startup ownership contract,
  - keep preset/runtime activation flow unified through the current resolved payload path.
- Detailed next slices:
  - extract remaining activation/config replay helpers that are still mixed into the coordinator without touching GL authority or mode-owned render math,
  - make startup and settings-refresh application order explicit in one place so thread-manager hookup, activation payload, and technical replay cannot silently drift again,
  - reduce direct coordinator knowledge of per-mode technical settings in favor of the existing extracted helpers,
  - only touch first-frame/overlay authority code if logs or tests make it necessary again.
- Required validation:
  - targeted `tests/test_spotify_visualizer_widget.py` startup/activation/first-frame subsets,
  - `tests/test_spotify_visualizer_mode_transition.py`,
  - synthetic bleed-family subset when a change touches reset/replay ordering,
  - post-change vis log review only if the slice affects startup or mode-switch authority.

3. `widgets/spotify_bars_gl_overlay.py` structural split planning / bounded execution — highest-value risky visualizer architecture move once Tasks 1 and 2 are healthier.
Core value: biggest long-term fragility reduction inside the visualizer stack, but only after the surrounding seams are cleaner.
- Why this is third, not first:
  - it is the highest-value risky move in the visualizer architecture,
  - but it has the highest regression potential and should follow the lower-risk settings/coordinator cleanup first,
  - it becomes safer once the model and coordinator seams carry less hidden drift.
- Implementation guardrails:
  - preserve first-bar / first-frame authority protections,
  - preserve settings/preset application truth through the existing resolved payload path,
  - keep `set_state(...)` and overlay activation/generation storage fully covered,
  - split only with targeted guard tests already in place or added first.

4. Expandability groundwork — highest cross-project future payoff after the main visualizer residue tracks are healthier.
Core value: best architecture payoff outside the fragile visualizer runtime itself.
- Recommended order from the audited architecture queue:
  1. widget descriptor/registry system,
  2. shared async/service-backed widget contract,
  3. descriptor-driven widget settings composition,
  4. stronger transition registry/descriptor layer,
  5. extension-path contract tests.
- Why this stays explicit:
  - these are not weak cleanup items,
  - they are the best non-visualizer future-value targets once the current visualizer seams are safer.

5. Visualizer test maintainability follow-through — do this alongside or immediately after Tasks 1–3 where it directly improves refactor safety.
Core value: makes the future architecture work cheaper instead of letting the biggest test files become their own blocker.
- Scope:
  - split `tests/test_visualizer_settings_plumbing.py` by subsystem/mode,
  - audit `tests/test_spotify_visualizer_widget.py` for duplicate setup and extract helpers where justified,
  - add rationale comments where raw `threading.Thread()` remains intentionally used in tests.
- Rule:
  - this is not busywork cleanup; only do the split when it directly improves refactor safety or runability for the structural tasks above.
- Progress note:
  - the first worthwhile maintainability slice is now in place: `tests/test_spotify_visualizer_widget.py` has a shared engine-patching helper that patches both the widget-local and extracted beat-engine seams, and the full file is green again after the architecture split.

## Watchlist
- While any visualizer work remains active, first-bar / first-frame authority and settings/preset drift stay on the watchlist by default. Do not remove them from active watch coverage until the visualizer track is fully complete.
- Gmail/OAuth is not an active blocker for planning purposes. The threading/test seam is closed enough; do not hold the larger architecture queue on manual Gmail validation.
- The stale live capture block-size regression is fixed and confirmed in logs: live mode switches renegotiate `128` for `spectrum` and `256` for `devcurve` without waiting for a settings-dialog restart.
- Recent long-run logs do not show a new first-bar / bleed / stale-generation failure. Visualizer performance looks good enough to leave as watch work rather than the active priority, provided later runs do not show persistent settled-runtime drift.
- The curated/custom preset drift family stays a standing watch item during settings-model refactors: preserve CLEAR-then-APPLY semantics and do not reintroduce a second post-overlay merge phase or entry-point-specific fallback path.
- Startup mode truth and shader warmup are now aligned around the resolved startup mode. Keep watching for any reappearance of cold-start replay misses or legacy `spectrum` assumptions in logs.
- The overlay cold-reset path should preserve guardrails even if the GL object is reused. If a reused overlay ever reintroduces stale activation/generation state, the first-frame guard warning should make that visible immediately in logs.

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
