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

1. Visualizer perf / latency follow-up — current active implementation priority.
Core value: the remaining user-visible risk is runtime hot-path cost and misleading diagnostics during heavy swaps / longer steady runs.
- Scope:
  - keep the fixed live block-size renegotiation path intact,
  - keep the tightened first-frame / fresh-generation guardrails intact,
  - keep the resolved transition-handoff/timer-cadence fixes intact,
  - separate settings-boundary stalls from true steady-runtime spikes,
  - keep log signal high enough that persistent jitter is easy to spot,
  - target real steady-state hot-path cost in active modes (`spectrum`, `sine_wave`, `bubble`, `devcurve`) rather than transition-only artifacts.
- Implementation guardrails:
  - do not lower visualizer FPS,
  - do not weaken first-frame / fresh-generation / activation gates for throughput,
  - do not solve perf by removing fades, glow, overlays, or authored mode behavior,
  - if a change would alter fidelity, accuracy, or reactivity, stop and confirm first.
- Required validation:
  - targeted `tests/test_spotify_visualizer_widget.py` perf/guard subsets,
  - `tests/test_spotify_visualizer_mode_transition.py`,
  - `tests/test_frame_timing_workload.py -k "slide_with_visualizer_load"`,
  - post-change vis log review for persistent spikes versus transition/settings-boundary spikes.
- Current focus:
  - keep the landed latency-readiness gate intact so startup-only pre-capture noise does not emit fake Bubble latency warnings,
  - keep the landed hot-diagnostic emit-only gates intact: `BARS`, `FLOOR`, `TRANSIENT`, `DEVCURVE`, and throttled `GLOW`,
  - keep the landed Spectrum pure-upgrade path intact: shared GPU extras dict reuse for steady-state `spectrum` pushes,
  - keep the landed startup warmup shape intact: transition GL startup compiles only the minimal subset first, while Spotify visualizer GL startup compiles the resolved startup mode first and warms the rest incrementally,
  - keep the landed resolved-startup-mode construction contract intact so widget/overlay cold construction does not leak legacy `spectrum` assumptions before activation,
  - investigate persistent non-transition `spectrum` spikes that remain after the timer/tick-source cleanup, Bubble dispatch-allocation reduction, and diagnostic-overhead cuts,
  - treat Bubble startup latency as an observability issue unless fresh logs show it persisting after the activation is audio-ready,
  - treat the transition handoff itself as green unless fresh logs show new first-frame or post-transition stalls.

2. `widgets/spotify_bars_gl_overlay.py` structural hardening — active under explicit first-frame/bleed guardrails.
Core value: highest-value remaining runtime-coordinator cleanup, because the GL overlay still carries a large mixed state/reset/render seam that future visualizer work will keep paying for.
- Implementation guardrails:
  - preserve the reset sequence described in `Docs/spotify_visualizer_bleed_first_frame_refactor_guardrails.md`,
  - preserve the fresh-generation / activation gate before display-bar authority returns,
  - preserve `paintGL()` stencil-mask geometry unless a change is directly justified and `tests/test_stencil_mask_alignment.py` stays green,
  - keep state/reset extraction work on the non-shader side unless a render-path change is explicitly required.
- Required validation:
  - `tests/test_ghost_isolation.py` overlay reset/isolation coverage,
  - `tests/test_spotify_visualizer_mode_transition.py`,
  - synthetic bleed-family subset from `tests/test_spotify_visualizer_widget.py`,
  - `tests/test_stencil_mask_alignment.py`,
  - post-change log review for `MODE_RESET_ASSERT`, `before_first_overlay_push`, `after_first_overlay_push`, `bleed`, `first frame`, `first bar`, `ERROR`, and `CRITICAL`.
- Current focus:
  - the next recommended slice is still the non-shader first-frame / overlay-frame commit seam,
  - this stays behind perf follow-up unless logs show the authority seam becoming suspicious again.

3. `core/settings/models/_spotify_visualizer.py` residue reduction — structural follow-through.
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

4. `widgets/spotify_visualizer_widget.py` coordinator residue reduction — structural follow-through.
Core value: reduces future startup/mode-switch/activation churn while keeping the GL overlay authority boundaries explicit.
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

5. Visualizer test maintainability follow-through — do this alongside or immediately after Tasks 1, 2, 3, and 4.
Core value: makes the future architecture work cheaper instead of letting the biggest test files become their own blocker.
- Scope:
  - split `tests/test_visualizer_settings_plumbing.py` by subsystem/mode,
  - audit `tests/test_spotify_visualizer_widget.py` for duplicate setup and extract helpers where justified,
  - add rationale comments where raw `threading.Thread()` remains intentionally used in tests.
- Rule:
  - this is not busywork cleanup; only do the split when it directly improves refactor safety or runability for the structural tasks above.
- Progress note:
  - the first worthwhile maintainability slice is now in place: `tests/test_spotify_visualizer_widget.py` has a shared engine-patching helper that patches both the widget-local and extracted beat-engine seams, and the full file is green again after the architecture split.

6. Expandability groundwork — start only after the visualizer residue tracks are in a healthier state.
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
- The stale live capture block-size regression is now fixed and confirmed in logs: live mode switches renegotiate `128` for `spectrum` and `256` for `devcurve` without waiting for a settings-dialog restart.
- Fresh logs do not show a new first-bar / bleed / stale-generation failure. The transition handoff/timer-cadence regression is resolved enough to move on. The remaining visualizer risk is performance/observability: repeated steady-runtime `spectrum`-leaning tick spikes plus some settings-boundary latency noise in logs.
- The overlay cold-reset path should preserve guardrails even if the GL object is reused. If a reused overlay ever reintroduces stale activation/generation state, the new first-frame guard warning should make that visible immediately in logs.

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
