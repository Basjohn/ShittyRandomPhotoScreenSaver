# SRPSS Guardrails

Last updated: 2026-04-25

Policy rules to keep architecture coherent and prevent repeat regressions.

## 1. Documentation Boundaries
- `Spec.md` for architecture contracts.
- `Index.md` for module ownership map.
- `Current_Plan.md` for active work only.
- `Docs/Historical_Bugs.md` for dated bug narratives.
- `Docs/Visualizer_Change_Checklist.md` for visualizer setting changes.

## 2. Centralized Ownership
- Threading through `ThreadManager`.
- Qt lifecycle through `ResourceManager`.
- Settings through `SettingsManager`.
- Animation through `AnimationManager`.

No shadow frameworks or parallel ownership paths.

## 3. Settings Safety
- Canonical defaults are single-source.
- Section/root writes must invalidate descendant cache entries.
- Reset/import preserve behavior uses one shared preservation contract.
- Retired global preset schema keys stay retired.

## 4. Visualizer Safety
- Mode identity and labels come from the mode registry.
- Internal ids remain stable even when user-facing labels change.
- Shared seams stay explicit and neutral.
- Reindex logic is index/filename normalization, not creative payload rewriting.

## 5. UI/UX Safety
- Do not remove custom styling to hide runtime issues.
- Fix startup/focus/visibility bugs at root cause.
- Respect staged startup contracts for dependent overlay widgets.

## 6. Testing and Validation
- Add automated regression coverage for changed contracts.
- Do not treat tests alone as sufficient for visual/timing-sensitive bug closure.
- Preserve useful harnesses/probes that materially improve diagnosis quality.

## 7. Focus and Shadow Cache Safety (U-05 Lessons)

### 7.1 Focus Policy Manipulation
- **Never manipulate focus policies on large widget trees at runtime.**
- Recursive `setFocusPolicy()` on dozens of widgets destabilizes Qt's focus tree, causing `focusInEvent`/`focusOutEvent` cascades. Runtime widget shadows must stay on the painter-owned card/text/header paths; do not reintroduce `QGraphicsDropShadowEffect` for overlay shadows.
- If focus policy changes are required, apply them at widget construction time only.

### 7.2 Dead Code Verification
- **Always verify a new function is actually wired into a call chain before declaring a fix complete.**
- A function that "looks correct" but is never invoked is a regression waiting to happen. Use `grep` to confirm all new helpers have ≥1 caller in production code (excluding tests).

### 7.3 Multi-Top-Level Window Z-Order
- **When restoring focus/activation to a top-level window that has separate top-level overlays (halo, tooltips), always re-raise the overlays after raising the main window.**
- `widget.raise_()` on a top-level window changes its position in the desktop stack, which can push separate top-level overlay windows behind it even if they have `WindowStaysOnTopHint`.
- Re-raising overlays with `overlay.raise_()` after focus restoration preserves visual layering without affecting keyboard focus (overlays should have `WindowDoesNotAcceptFocus`).

### 7.4 Graphics Effect Recreation During Active Animations
- **Never recreate or replace a `QGraphicsEffect` (opacity, shadow, etc.) while a `QVariantAnimation` is actively driving it.**
- `_recreate_effect()` in `widget_effects.py` replaces effects to bust Qt's internal cache. If called mid-animation, the old animation's `valueChanged` callbacks continue manipulating the DETACHED old effect, while the new effect stays frozen at its initial value.
- Result: widget becomes permanently invisible (opacity=0.0) or shows incorrect shadow because the animation never updates the new effect.
- **Prevention**: Before recreating an effect, check for an active `_fade_anim` or `_shadowfade_anim` on the widget. Skip recreation if an animation is in-flight, OR reconnect the animation to the new effect.
