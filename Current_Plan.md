# Current Plan

Last updated: 2026-05-07

This file tracks active work and near-term validation. Completed implementation detail belongs in a compact ledger, not as the main working surface.

## Guardrails
- Keep this aligned with `Spec.md`, `Index.md`, `Docs/Guardrails.md`, `Docs/Historical_Bugs.md`, and `Docs/Gmail_Widget_Plan.md`.
- Keep harnesses/probes intact unless explicitly asked to retire them.
- Treat `presets/visualizer_modes/` as authored content. Tests may validate schema/index/repair behavior, but must not force exact preset names, slots, or creative numeric values.
- Do not close visual/runtime bugs from tests alone when symptoms are user-visible.
- Avoid broad focus, window-flag, compositor, visualizer, or Qt effect/shadow rewrites unless the current task directly requires them.

## Active Priorities

### Gmail Widget
Primary plan: `Docs/Gmail_Widget_Plan.md`.

Status: Foundation complete. Gmail is a normal feature with IMAP (primary) and OAuth (advanced) backends. All core functionality implemented and validated.

Deferred targets (when needed):
- Thread grouping/conversation display remains default-off until researched. Prefer `X-GM-THRID`, split read/unread groups, and decide collapsed-row action semantics before implementing.
- Archive should stay hidden for IMAP unless a source-backed finding or small diagnostic harness proves a reliable accepted command.
- Low-priority shared stretch: open Gmail/Reddit links on monitor index `0` when cleanly possible, with fallback to current behavior.

### Visualizer
Current status:
- Active visualizer settings work is redesigning technical ownership so runtime/save/load/preset paths all use per-mode technical keys only. Shared/global technical keys remain legacy migration inputs for normalization/repair, not live runtime state.
- Canonical visualizer activation now routes through `resolve_visualizer_activation_payload(...)` so startup create, settings refresh, and runtime switches can share one resolved mode/preset payload instead of rebuilding technical state through parallel paths.
- Preset-varying runtime visuals now follow the same ownership rule: bar fill/border styling and legacy ghost controls are being normalized to per-mode payloads so preset switches cannot overwrite another mode's render state through shared keys.

Guardrails:
- Do not touch visualizer timing/mitigation paths as a side effect of widget performance work.
- Keep preset tooling/schema and runtime behavior aligned as visualizer modes evolve.
- For visualizer painted-card clipping, do not solve escape by changing visualizer mode size/content, preset geometry, curve amplitude, waveform math, or authored mode behavior. The required fix is visibility/clipping/masking to the card boundary only.

Near-term targets:
- Align all visualizer settings/model/tests/tooling/docs with canonical per-mode technical ownership; remove active-mode save paths that rewrite shared technical keys and keep diagnostics mode-resolved.
- Keep preset/custom/runtime normalization using all stable mode ids, not only currently active descriptor gates. Blob preset ownership was previously being dropped during normalization when blob was dev-gated, which let hot activation fall back to curated preset 1 instead of the stored target preset/custom payload.
- Keep live activation diagnostics comparing resolved preset identity with actual worker/widget-applied technical state; do not trust raw settings logs alone for bleed closure.
- Remove invalid widget painting outside `paintEvent` if it reappears. Recent logs showed `QWidget::paintEngine: Should no longer be called` / `QPainter::begin: Paint device returned engine == 0`, caused by painting a widget from `resizeEvent`; this class of fix should stay paint-event-only.
- Preset repair/reindex round-trip checks after visualizer schema changes.
- Assess `card_height.py` and whether a centralized sizing contract can replace scattered multipliers without bleed or visual regressions.
- Assess and document whether any remaining opacity-effect invalidation is still needed now that runtime card shadows are painted.

### General Runtime
Open watchlist:
- Mute button fade-in reliability under startup event pressure.
- Transition random mode actual distribution vs expected uniform over 50+ rotations.
- Settings destructive-flow checks: reset/import when touching settings architecture.
- Settings cache stale-read behavior after section/root writes.

## Historical Ledger
- Gmail widget completed on 2026-05-07: Full IMAP (primary) and OAuth (advanced) backend implementation with normal/MC link opening, Mark Read/Unread/Spam/Delete actions, refresh/paint caching with transition contention mitigation, settings UI with non-blocking IMAP Save & Test, action menu with active-backend support, envelope/action icons, optional refresh control, date modes, sender/subject cleanup, cache ordering, header parity, stable-content cache, and transition-aware refresh deferral. Archive hidden for IMAP after runtime failures.
- Runtime painted shadow system completed on 2026-05-07: `widgets.shadows.enabled`, `widgets.shadows.text_enabled`, and `widgets.shadows.header_enabled` control card/text/header shadows via cached DPR-aware painter output. Shadow tuning loads from `shadowtuning.json` via `core/settings/shadow_tuning.py`. Intense shadow settings and Qt drop-shadow runtime branches retired. Media control bar shift fixed via transparent background when using painted frame shadow. Volume slider shadow implemented with `VOLUME_SLIDER_SHADOW_TUNING`.
- Visualizer GL escape fix completed on 2026-05-07: Rounded-rect stencil mask in `SpotifyBarsGLOverlay.paintGL()` with extra `border_width/2` inset prevents bleed under painted-card shadows. Validated across all modes via `test_stencil_mask_alignment.py`. Dead `_render_with_qpainter` fallback removed; GL is the only active rendering path.
- U-05 MC Keyboard Focus / Ctrl Halo Runtime Input Family resolved on 2026-04-25 by wiring `_restore_mc_input_focus` into click routing. User validated media keys, `C`, and `S` after manual click in MC mode.
- Cursor halo side effect from focus restore was fixed by re-raising the halo after `DisplayWidget` focus restoration.
- MuteButtonWidget fade-in race was fixed by replacing bespoke opacity animation with `ShadowFadeProfile`; keep the pattern documented in `Docs/Historical_Bugs.md`.
- Reddit refresh control click classification and guarded refresh path have been implemented.

## Latent Focus Architecture Risks
These remain risky and should be handled only when a focused task justifies them:
- Assess/fix general focus policies on overlay widgets.
- Assess GL compositor focus policy.
- Assess focus-restore reason consistency.
- Assess global Raw Input registration vs per-window.
- Assess halo focus interactions.
- Assess activation-refresh contract.
- Audit post-show `setWindowFlag()` calls.

## Documentation Rule
- Architecture: `Spec.md`
- Module map: `Index.md`
- Policy: `Docs/Guardrails.md`
- Dated regressions: `Docs/Historical_Bugs.md`
- Gmail implementation plan: `Docs/Gmail_Widget_Plan.md`

## Idea Box/Problem Box
1. Add a lightweight doc-drift check for stale references between `Spec.md`, `Index.md`, `Current_Plan.md`, and `Docs/Gmail_Widget_Plan.md`.

2. Add a small harness smoke command list for recurring investigations.

3. Add a transition-distribution logger that reports session skew at shutdown.

4. Archive button still appears in the triple dot menu when using Imap despite being disabled.
