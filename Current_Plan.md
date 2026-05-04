# Current Plan

Last updated: 2026-05-04

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

Current status:
- Gmail is a normal feature, not dev-gated.
- IMAP/app-password is the primary supported backend; OAuth/REST remains optional/advanced.
- Normal and MC Gmail link opening works.
- Mark Read/Unread, Spam, and Delete work in runtime reports.
- Archive is hidden for IMAP after repeated runtime failures; code remains for OAuth/future diagnostics.
- Gmail refresh/paint has first-pass caching and transition contention mitigation. Recent fix also covers refreshes already in flight when a transition is requested.
- `--shadowfix` now gates the shared painted-frame-shadow experiment for framed overlay cards. It avoids persistent `QGraphicsDropShadowEffect` for framed widgets, explicitly clears the transparent backing store before painting, and uses cached DPR-aware painter output instead.
- Shadow tuning now loaded from `shadowtuning.json` (in `%APPDATA%/SRPSS/`) via `core/settings/shadow_tuning.py`. Card tuning is re-exported as `PAINTED_FRAME_SHADOW_TUNING` from `widgets/base_overlay_widget.py` for compatibility. Volume slider has its own `VOLUME_SLIDER_SHADOW_TUNING` section. Hardcoded fallbacks used when file is missing or corrupt. Gmail's older `GMAIL_SHADOWFIX_TUNING` remains only as diagnostic/local comparison.
- Settings dialog creation flicker is fixed in live use; keep R-18 guardrails active for future settings work.

Critical Blockers:
- [FIXED 2026-05-04] Media control bar shift: `MediaWidget._update_stylesheet()` now sets transparent background/no border when `uses_painted_frame_shadow()` is True, preventing double-painting of card background that caused visual shift. Needs runtime validation.
- [FIXED 2026-05-04 — U-07] Visualizer GL modes escape card boundary under `--shadowfix`. Fixed via rounded-rect **stencil mask** in `paintGL()` — mask pass writes `1` to stencil inside the visible card boundary (including rounded corners), then visualizer only draws where stencil == 1. No content scale or behavior changes. Needs runtime validation across all modes.
- [FIXED 2026-05-04] Volume slider shadow: `SpotifyVolumeWidget` now has its own painted frame shadow system using `VOLUME_SLIDER_SHADOW_TUNING` from `shadowtuning.json`. Needs runtime validation.
An Image example of ALL 3 Blockers: "F:\Programming\Apps\ShittyRandomPhotoScreenSaver\temp\blockers.png"

Near-term targets:
- Runtime-validate the latest Gmail/Reddit refresh contention fix from fresh `/logs`: in-flight refresh + manual transition should suspend spinner repaint and defer apply until transition idle.
- Runtime A/B `--shadowfix` on all framed widgets in MC multi-monitor: Display 1 click into app, then Display 0 click. Compare whether Gmail/Weather/Reddit/Media stop doubling outside-card shadows.
- Watch logs for `[GMAIL_SHADOWFIX] Unexpected persistent graphics effect`; if it appears, there is still an effect in the stack despite the gated painted-shadow path.
- Tune `PAINTED_FRAME_SHADOW_TUNING` for family-wide fidelity only if visual validation shows mismatch. Do not make the widget-card backdrop shadows generally more intense by default; current `--shadowfix` card shadows are already tuned heavy.
- Rebuild/inspect final normal and MC artifacts for envelope/action icons, optional refresh visual, and regression-check Gmail logo/sound packaging.
- Run a concise Gmail defaults/security/build audit after packaging changes: no credentials or OAuth local secrets tracked or bundled.
- Runtime-check display polish only where screenshots still show issues: header/logo alignment, unread/read envelope distinction at 16px, date modes at practical widths, sender/subject column alignment.

Deferred Gmail targets:
- Thread grouping/conversation display remains default-off until researched. Prefer `X-GM-THRID`, split read/unread groups, and decide collapsed-row action semantics before implementing.
- Archive should stay hidden for IMAP unless a source-backed finding or small diagnostic harness proves a reliable accepted command.
- Low-priority shared stretch: open Gmail/Reddit links on monitor index `0` when cleanly possible, with fallback to current behavior.

### Visualizer
Current status:
- Spotify visualizer card `--shadowfix` GL escape fixed via **rounded-rect stencil mask** in `SpotifyBarsGLOverlay.paintGL()`. Mask shader draws the visible card shape (including rounded corners) into the stencil buffer; visualizer only renders where stencil == 1. No content scale/behavior changes. Needs runtime validation across Spectrum, Sine, Blob, Bubble, DevCurve, Oscilloscope.

Guardrails:
- Do not touch visualizer timing/mitigation paths as a side effect of widget performance work.
- Keep preset tooling/schema and runtime behavior aligned as visualizer modes evolve.
- For visualizer `--shadowfix`, do not solve escape by changing visualizer mode size/content, preset geometry, curve amplitude, waveform math, or authored mode behavior. The required fix is visibility/clipping/masking to the card boundary only, matching non-`--shadowfix` behavior.

Near-term targets:
- Runtime-validate stencil mask clipping across all visualizer modes under `--shadowfix`. Confirm no bleed at rounded corners, no content distortion, no stencil artifacts after mode switches.
- [DONE 2026-05-04] Remove dead `_render_with_qpainter` fallback from `SpotifyBarsGLOverlay`. Removed unused imports: `QPainter`, `QRectF`, `compute_bar_layout`. GL is the only active rendering path.
- Remove invalid widget painting outside `paintEvent` if it reappears. Recent logs showed `QWidget::paintEngine: Should no longer be called` / `QPainter::begin: Paint device returned engine == 0`, caused by painting a widget from `resizeEvent`; this class of fix should stay paint-event-only.
- Preset repair/reindex round-trip checks after visualizer schema changes.
- Assess `card_height.py` and whether a centralized sizing contract can replace scattered multipliers without bleed or visual regressions.
- Assess & Document need for extensive shadow cache invalidation systems post-shadowfix gate removal. Other sources of corruption? Performance cost?


### Shadow System / `--shadowfix`
Current status:
- HIGH PRIORITY: multi-monitor MC shadow/shadow-cache corruption now appears frequently after focus loss/cross-display clicks. Preserve the MC focus restore/key fix while validating the permanent mitigation.
- Current theory: stale transparent backing-store pixels and/or widget-level `QGraphicsDropShadowEffect` on translucent background frames are the corruptible primitives. `--shadowfix` tests cached painted outer-frame shadows across framed overlay cards.
- `Intense Shadows` currently remains a user-facing setting, but under painted-frame shadows it is at best ignored and at worst a path back toward mixed shadow methodologies.
- The existing `--shadowfix` framed-card backdrop shadow should not be made generally heavier as part of intense-shadow cleanup. It is already tuned heavy; the goal is simplification, safety, and consistency, not stronger card backdrop shadows.

Recommended intense-shadow migration path:
- Remove `intense_shadow` as a user-facing setting after the painted shadow baseline validates. The painted shadow path currently does not meaningfully branch on it, so keeping the toggle risks a setting that appears active but does nothing under `--shadowfix`.
- Remove `_intense_shadow` as an internal framed-widget control once the migration is live. The goal is one centralized shadow system, not a normal/intense fork.
- Remove `INTENSE_SHADOW_BLUR_MULTIPLIER`, `INTENSE_SHADOW_OPACITY_MULTIPLIER`, and `INTENSE_SHADOW_OFFSET_MULTIPLIER` from `widgets/shadow_utils.py` once the legacy `QGraphicsDropShadowEffect` path is retired or limited to non-framed/text-only cases.
- Keep `apply_widget_shadow` only for the non-`--shadowfix` legacy path until migration is complete, then strip the `intense` parameter when no framed widget depends on it.
- Avoid double painting. A framed widget should never have both a persistent `QGraphicsDropShadowEffect` and a painted-frame shadow. `uses_painted_frame_shadow()` should continue to clear/skip `QGraphicsDropShadowEffect` before returning.
- Avoid shadow cache corruption by making the painted frame shadow the sole framed-card implementation. The old intense path triples blur radius, boosts opacity, and doubles offset inside Qt's graphics-effect pipeline, increasing exactly the kind of large translucent cached effect surface suspected in U-06.
- Preserve visual strength by keeping the validated painted-shadow baseline strong enough without a second user-facing intense mode. Do not increase the current `--shadowfix` widget-card backdrop shadow unless a specific visual mismatch is identified.
- If any non-card/text-only shadow still needs more presence after migration, handle it through a safe painted/text-shadow strategy or another centralized non-`QGraphicsDropShadowEffect` mechanism, not by reviving per-widget intense `QGraphicsDropShadowEffect` multipliers.

Near-term targets:
- Runtime A/B `--shadowfix` on all framed widgets in MC multi-monitor after the visualizer escape is fixed: Display 1 click into app, then Display 0 click. Compare whether Gmail/Weather/Reddit/Media/Visualizer stop doubling outside-card shadows.
- Audit settings UI and defaults for `intense_shadow` references before removal. This includes widget tabs, settings models, defaults, tests, and migration behavior.
- Update `Docs/Historical_Bugs.md` after validation with the final status of U-06 and the adopted shadow architecture.

### General Runtime
Open watchlist:
- Mute button fade-in reliability under startup event pressure.
- Transition random mode actual distribution vs expected uniform over 50+ rotations.
- Settings destructive-flow checks: reset/import when touching settings architecture.
- Settings cache stale-read behavior after section/root writes.

## Historical Ledger
- U-05 MC Keyboard Focus / Ctrl Halo Runtime Input Family resolved on 2026-04-25 by wiring `_restore_mc_input_focus` into click routing. User validated media keys, `C`, and `S` after manual click in MC mode.
- Cursor halo side effect from focus restore was fixed by re-raising the halo after `DisplayWidget` focus restoration.
- MuteButtonWidget fade-in race was fixed by replacing bespoke opacity animation with `ShadowFadeProfile`; keep the pattern documented in `Docs/Historical_Bugs.md`.
- Gmail foundation, settings UI, defaults, sound packaging guardrails, row/link routing, menu ownership, date modes, text cleanup, cache ordering, header parity start, stable-content cache, and transition-aware refresh deferral have been implemented.
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
