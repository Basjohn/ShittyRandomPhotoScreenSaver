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
- Runtime painted shadows are the default widget shadow system. `widgets.shadows.enabled` controls framed-card shadows, `widgets.shadows.text_enabled` controls painter text shadows, and `widgets.shadows.header_enabled` controls header-frame shadows. Runtime card shadows avoid persistent `QGraphicsDropShadowEffect`, explicitly clear transparent backing stores before painting, and use cached DPR-aware painter output.
- Shadow tuning loads from `shadowtuning.json` (in `%APPDATA%/SRPSS/`) via `core/settings/shadow_tuning.py`. Canonical sections are `card`, `volume_slider`, `text`, and `header`; missing or corrupt files regenerate from canonical defaults.
- Settings dialog creation flicker is fixed in live use; keep R-18 guardrails active for future settings work.

Critical Blockers:
- [FIXED 2026-05-04] Media control bar shift: `MediaWidget._update_stylesheet()` now sets transparent background/no border when `uses_painted_frame_shadow()` is True, preventing double-painting of card background that caused visual shift. Validated.
- [FIXED 2026-05-04 — U-07] Visualizer GL modes escape card boundary under painted-card shadows. Fixed via rounded-rect **stencil mask** in `paintGL()` with extra `border_width/2` inset to avoid bleeding over the centred card pen stroke. Validated across all modes; `test_stencil_mask_alignment.py` proves zero bleed.
- [FIXED 2026-05-04] Volume slider shadow: `SpotifyVolumeWidget` now has its own painted frame shadow system using `VOLUME_SLIDER_SHADOW_TUNING` from `shadowtuning.json`. Validated.
An Image example of ALL 3 Blockers: "F:\Programming\Apps\ShittyRandomPhotoScreenSaver\temp\blockers.png"

Near-term targets:
- Runtime-validate the latest Gmail/Reddit refresh contention fix from fresh `/logs`: in-flight refresh + manual transition should suspend spinner repaint and defer apply until transition idle.
- Runtime-validate painted shadows on all framed widgets in MC multi-monitor: Display 1 click into app, then Display 0 click. Confirm Gmail/Weather/Reddit/Media/Visualizer do not double outside-card shadows.
- Tune `PAINTED_FRAME_SHADOW_TUNING` for family-wide fidelity only if visual validation shows mismatch. Do not make widget-card backdrop shadows generally more intense by default; the painted-card baseline is already tuned heavy.
- Rebuild/inspect final normal and MC artifacts for envelope/action icons, optional refresh visual, and regression-check Gmail logo/sound packaging.
- Run a concise Gmail defaults/security/build audit after packaging changes: no credentials or OAuth local secrets tracked or bundled.
- Runtime-check display polish only where screenshots still show issues: header/logo alignment, unread/read envelope distinction at 16px, date modes at practical widths, sender/subject column alignment.

Deferred Gmail targets:
- Thread grouping/conversation display remains default-off until researched. Prefer `X-GM-THRID`, split read/unread groups, and decide collapsed-row action semantics before implementing.
- Archive should stay hidden for IMAP unless a source-backed finding or small diagnostic harness proves a reliable accepted command.
- Low-priority shared stretch: open Gmail/Reddit links on monitor index `0` when cleanly possible, with fallback to current behavior.

### Visualizer
Current status:
- Spotify visualizer card GL escape under painted-card shadows is fixed via **rounded-rect stencil mask** in `SpotifyBarsGLOverlay.paintGL()`. Mask shader draws the visible card shape (including rounded corners) into the stencil buffer; visualizer only renders where stencil == 1. No content scale/behavior changes. Needs runtime validation across Spectrum, Sine, Blob, Bubble, DevCurve, Oscilloscope.

Guardrails:
- Do not touch visualizer timing/mitigation paths as a side effect of widget performance work.
- Keep preset tooling/schema and runtime behavior aligned as visualizer modes evolve.
- For visualizer painted-card clipping, do not solve escape by changing visualizer mode size/content, preset geometry, curve amplitude, waveform math, or authored mode behavior. The required fix is visibility/clipping/masking to the card boundary only.

Near-term targets:
- [DONE] Stencil mask validated: `test_stencil_mask_alignment.py` passes (zero bleed, correct corner rounding, zero-radius rectangle parity).
- [DONE 2026-05-04] Removed dead `_render_with_qpainter` fallback from `SpotifyBarsGLOverlay`. GL is the only active rendering path.
- Remove invalid widget painting outside `paintEvent` if it reappears. Recent logs showed `QWidget::paintEngine: Should no longer be called` / `QPainter::begin: Paint device returned engine == 0`, caused by painting a widget from `resizeEvent`; this class of fix should stay paint-event-only.
- Preset repair/reindex round-trip checks after visualizer schema changes.
- Assess `card_height.py` and whether a centralized sizing contract can replace scattered multipliers without bleed or visual regressions.
- Assess and document whether any remaining opacity-effect invalidation is still needed now that runtime card shadows are painted.


### Runtime Painted Shadow System
Current status:
- `widgets.shadows.enabled`, `widgets.shadows.text_enabled`, and `widgets.shadows.header_enabled` are the runtime controls for card, text, and header shadows.
- Intense shadow settings and Qt drop-shadow runtime branches are retired. Clock analog keeps the former intense painter look as its normal analog face-shadow appearance.
- Settings dialog chrome remains separate and may keep its own dialog-only effects.

Near-term targets:
- Runtime validate independent card/text/header toggles with Gmail, Weather, Reddit, Media, Visualizer, and Spotify volume visible.
- Update targeted tests around defaults cleanup, Widgets tab save/load, Gmail/Spotify painted shadows, and no runtime Qt drop-shadow construction.

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
