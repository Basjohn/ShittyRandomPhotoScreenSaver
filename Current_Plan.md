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
  - a further serializer split is now in place: `to_dict()` delegates core/osc-blob/spectrum/sine/bubble/blob-shape groupings to dedicated helpers, so future mode-owned setting changes do not require editing one giant flat save dict.
  - the shared constructor payload is now being reduced the same way: `_build_visualizer_model_kwargs(...)` delegates core/osc-blob/spectrum/sine/bubble/blob-shape/devcurve groupings to dedicated builders, so future ingestion changes can stay mode-local instead of re-editing one giant mixed constructor map.

2. `widgets/spotify_visualizer_widget.py` coordinator residue reduction — second major code task.
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
  - progress note:
  - the startup-staging-through-coordinator guard is now in `tests/test_widget_manager.py`, and the fresh-frame / waveform / crossover gating guards in `tests/test_spotify_visualizer_widget.py` now target the real reset-generation contract instead of stale pre-split monkeypatch assumptions.
  - the runtime technical-config bridge has now been extracted into `widgets/spotify_visualizer/technical_config.py`, reducing widget-coordinator residue without touching startup ownership, fresh-frame gating, or GL first-frame behavior.
  - resolved activation/replay ownership is now partly extracted into `widgets/spotify_visualizer/activation_runtime.py`, so settings-model apply and canonical activation-payload replay are no longer embedded entirely in the widget coordinator.
  - shared engine/runtime config forwarding is now partly extracted into `widgets/spotify_visualizer/runtime_config.py`, covering thread/process propagation, floor/sensitivity/energy/input/AGC pushes, audio block-size forwarding, runtime bar-state clearing, and beat-engine bar-count reconfiguration without entering the GL first-frame authority path.
  - a concrete live-runtime regression was also identified and fixed here: mode-owned audio block-size changes were reaching the worker config path but not the live capture stream, so `devcurve -> spectrum` could keep running on the stale negotiated block size until a settings-dialog restart. `SpotifyVisualizerAudioWorker.set_audio_block_size()` now restarts capture when the preferred block changes while running.

3. `widgets/spotify_bars_gl_overlay.py` structural hardening — now active under explicit first-frame/bleed guardrails.
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
- Progress note:
  - the first active slice is now in place: overlay mode-reset scheduling, per-mode cold-reset bookkeeping, activation/generation/frame metadata capture, floor snapshot handoff, invisible-frame early return, and border-width storage now flow through `widgets/spotify_visualizer/overlay_state.py`, while `widgets/spotify_bars_gl_overlay.py` keeps the same public entrypoints as thin wrappers.
  - regression coverage now includes a real stale activation/generation rejection test in `tests/test_spotify_visualizer_mode_transition.py` and explicit manual overlay-reset bookkeeping checks in `tests/test_ghost_isolation.py`.
  - the next render-side slice is now in place too: painted-card stencil setup/teardown and rounded-rect mask uniform generation are no longer inlined entirely inside `paintGL()`. `widgets/spotify_visualizer/overlay_mask.py` now owns the mask uniform math, while `widgets/spotify_bars_gl_overlay.py` keeps explicit begin/draw/end stencil helpers around the same geometry contract.
  - next recommended slice inside this task: extract the non-shader first-frame authority / overlay-frame commit seam into a dedicated helper while preserving generation+activation gating, then validate with the existing synthetic bleed-family tests plus post-change log review.

4. Visualizer perf / latency follow-up — now an explicit near-term task, not just a watch item.
Core value: the remaining user-visible risk is no longer stale block-size carryover; it is runtime hot-path cost and misleading diagnostics during heavy swaps / overlay recreation.
- Scope:
  - keep the recently fixed live block-size renegotiation path intact,
  - investigate overlay recreation / shader recompile churn during mode switches and restarts,
  - investigate the remaining real 48–110ms tick spikes under load,
  - improve log signal so hot-path issues are parseable without drowning the vis log in per-frame chatter.
- Implementation guardrails:
  - do not weaken first-frame / fresh-generation / activation gates for the sake of throughput,
  - do not solve perf by removing visual features, fades, glow, or overlays,
  - prefer throttling / summarizing diagnostics over deleting the high-value probes we rely on for bleed and first-frame regressions.
- Immediate evidence:
  - fresh logs confirm the old stale capture block-size mismatch is fixed,
  - fresh logs still show repeated tick spikes and repeat full overlay shader setup after recreation,
  - the vis log remains too noisy in hot paths unless diagnostic emitters are tightened.

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
- Fresh logs do not show a new first-bar / bleed / stale-generation failure. The remaining visualizer risk is performance/observability: repeated tick spikes, overlay recreation cost, and log volume in hot paths.

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
