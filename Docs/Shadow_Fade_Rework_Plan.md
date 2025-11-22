# Shadow Fade Rework Plan

Design and implementation plan for the next iteration of **widget shadow fade behaviour**.

This document is planning-only; no changes are active until explicitly implemented.

---

## 1. Goals

- **Unify** how drop shadows are applied to overlay widgets (Clock/Weather/Media/Reddit).
- **Replace** all per-widget ad-hoc fade logic with a **single global shadow fade profile** shared by every widget.
- Ensure **flicker-free** first appearance: widgets fade in using the same opacity animation (duration/easing) and then attach a stable shadow with no popping or double-effects.
- Respect the existing overlay fade coordination in `DisplayWidget` so that all widgets on a display fade in together.

### Non-Goals

- No change to GL transition behaviour or image compositing.
- No change to theming palette or widget colours beyond what `widgets.shadows.*` already controls.
- No new runtime dependencies.

---

## 2. Current Behaviour (Summary)

### 2.1 Global configuration

- `Settings['widgets']['shadows']` is a dict storing global shadow options (currently primarily an `enabled` flag, with defaults provided by `SettingsManager`).
- `DisplayWidget._setup_widgets` reads this config and passes it into widgets via:
  - `widget.set_shadow_config(shadows_config)` when available, **or**
  - `apply_widget_shadow(widget, shadows_config, has_background_frame=...)` as a direct helper.

### 2.2 Per-widget fade and shadow application

- **Clock widgets**: may attach shadows directly or via `set_shadow_config`, and coordinate first-show via `request_overlay_fade_sync` where supported.
- **Weather/Media/Reddit**:
  - Perform a first-time fade-in using a temporary `QGraphicsOpacityEffect`.
  - After the fade completes, they remove the opacity effect and call `apply_widget_shadow(...)` with the shared config.
  - They register with `DisplayWidget.request_overlay_fade_sync(overlay_name, starter)` so that fades across Weather/Media/Reddit (and clocks) start in sync per display.

Pain points:

- Shadow behaviour is partly duplicated across widgets.
- Fade vs. shadow responsibilities are blurred between `DisplayWidget`, `apply_widget_shadow`, and each widget class.
- There is no explicit configuration for **shadow fade characteristics** (duration, easing, when to re-apply after style changes).

---

## 3. Proposed Design

### 3.1 Single global shadow fade profile

Define a single, hard-coded shadow fade profile in `widgets/shadow_utils.py`:

- Duration: e.g. `1500ms`.
- Easing: `InOutCubic`.

This profile is **not configurable via settings** for now; if we ever want to expose controls, they will be added in a future iteration. The only setting we honour today is `widgets.shadows.enabled` as the master on/off switch for shadows.

### 3.2 Central helper: `ShadowFadeProfile`

Implement a small helper in `widgets/shadow_utils.py` that encapsulates **shadow-specific** behaviour using the single global profile:

- `ShadowFadeProfile()` – lightweight object or namespace with:
  - `attach_shadow(widget, shadows_config, has_background_frame: bool)` – apply a drop shadow immediately (no fade), using `apply_widget_shadow` internally when shadows are enabled.
  - `start_fade_in(widget, shadows_config, has_background_frame: bool)` –
    - Temporarily installs a `QGraphicsOpacityEffect` on the widget to drive a coordinated card opacity fade 0.0 → 1.0 with the global duration/easing.
    - Once the card fade completes, tears down the opacity effect and starts a **second animation** that fades the drop shadow's colour alpha from 0 to the configured value over the same duration/easing. The shadow effect is applied via `QGraphicsDropShadowEffect` and respects the existing `widgets.shadows.*` colour/offset/blur and text/frame opacity multipliers.
    - Log failures via the widget/logger without raising.

`DisplayWidget` continues to drive high-level overlay fade sync via `request_overlay_fade_sync`. Widgets call `ShadowFadeProfile.start_fade_in(...)` from their registered starter callbacks so that **all widgets on a display perform the card fade in lockstep**, and then each widget's shadow performs a matching-duration fade using the same profile. The visible effect is a smooth two-stage startup where cards and their slightly enlarged shadows feel like a single, unified animation.

### 3.3 Widget integration plan

For each overlay widget that currently performs its own fade + shadow logic:

1. **WeatherWidget**
   - Replace local opacity-effect+shadow code with calls to `ShadowFadeProfile.start_fade_in(...)` using the shared config passed from `DisplayWidget`.
   - Honour `apply_on_first_data_only` so subsequent refreshes only update text, not re-fade the card.

2. **MediaWidget**
   - Same pattern as WeatherWidget; ensure header frame and background state are respected when deciding `has_background_frame`.

3. **RedditWidget**
   - Replace the inline fade logic in `_start_widget_fade_in` with `ShadowFadeProfile.start_fade_in(...)`.
   - Continue to request overlay fade sync via `parent.request_overlay_fade_sync("reddit", starter)`; the starter will now delegate to `ShadowFadeProfile`.

4. **Clock widgets**
   - Where opacity effects are used, migrate to `ShadowFadeProfile` for consistency.
   - Where clocks only need an immediate shadow (no fade), call `attach_shadow` instead.

All of the above continue to receive `shadows_config` from `DisplayWidget._setup_widgets`, so the existing single source of truth remains intact.

### 3.4 Diagnostics

- Add targeted debug logging around the helper:
  - `[SHADOW_FADE] start_fade_in widget=%s duration=%sms easing=%s`.
  - `[SHADOW_FADE] attach_shadow widget=%s enabled=%s`.
- Ensure verbose logs surface any failures to create or apply `QGraphicsOpacityEffect` or shadow effects, without affecting runtime behaviour.

---

## 4. Rollout Strategy

Perform the rework as a **single coordinated change** across all overlay widgets to preserve fade sync and avoid mixed behaviours:

1. Implement `ShadowFadeProfile` in `widgets/shadow_utils.py` with the global duration/easing profile.
2. Update **all overlay widgets** (Weather, Media, Reddit, Clock 1/2/3) to:
   - Hand off their initial fade/shadow behaviour to `ShadowFadeProfile.start_fade_in(...)` from their `request_overlay_fade_sync` starter callbacks (or equivalent first-show paths).
   - Use `ShadowFadeProfile.attach_shadow(...)` for non-faded cases where an immediate shadow is required.
3. Validate on multi-monitor setups that:
   - All widgets on the same display fade and receive shadows in sync with the existing overlay fade coordinator.
   - There are no regressions in flicker or Z-order relative to the GL compositor.
4. Once validated, update `Spec.md`, `Index.md`, and roadmap/audit docs to reference the new unified shadow fade path.

---

## 5. Risks & Open Questions

- **Qt/Platform differences**: behaviour of `QGraphicsOpacityEffect` and `QGraphicsDropShadowEffect` may differ slightly across platforms; testing must cover at least Windows+DPI scaling.
- **Transition interplay**: ensure that GL transitions and overlay fade sync remain independent; shadow fades must not interfere with transition timing.
- **Performance**: additional effects should be negligible, but we should watch for any regressions when multiple widgets fade simultaneously on high-DPI, multi-monitor setups.

Open questions to resolve before implementation:

- Do we want per-widget overrides for shadow fade duration, or is a single global profile sufficient?
- Should the Settings dialog surface any of the new `widgets.shadows` fade options, or remain an expert-only configuration in the settings file?
