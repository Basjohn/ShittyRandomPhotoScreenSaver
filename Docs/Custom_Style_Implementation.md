# Custom Style Implementation

Last updated: 2026-08-24

Guidance for SRPSS Settings UI and runtime visual styling during the Qt Quick migration.

## 1. Goals

- preserve SRPSS custom chrome and dark settings language;
- preserve runtime customization unless the migration explicitly retires a presentation-era control;
- keep shared style decisions in shared owners;
- fix focus/startup/visibility/render bugs at their owner rather than deleting visuals;
- distinguish QWidget Settings styling from runtime-pixel styling that is migrating to Quick.

## 2. Settings UI sources — PRESERVE

Settings remains QWidget-based unless a separate product decision changes that.

Current Settings style sources remain:

- `ui/settings_dialog.py`
- `ui/settings_theme.py`
- `ui/tabs/shared_styles.py`
- `ui/styled_popup.py`
- `ui/widgets/`

These are **LANDED / PRESERVE** for Settings UI. Do not rewrite them merely because runtime
presentation migrates to Quick.

## 3. Runtime presentation architecture

Runtime widget pixels migrate to the display's retained Qt Quick scene.

Read:

- `Current_Plan.md`
- `Docs/QtQuick_Migration/04_Widget_Runtime_Presentation.md`
- `Docs/Contracts.md`

Keep provider/model/settings authority in Python.

### 3.1 Current-legacy runtime style owners

The following may still have real callers before family/cutover deletion, but are
**CURRENT-LEGACY — WILL BE OBSOLETE / REHOMED through E3/E4/F/I**:

- `BaseOverlayWidget` runtime card/pixel ownership;
- QWidget/QPainter runtime card drawing;
- painted-frame/shadow caches used only by runtime widgets;
- QWidget runtime `QGraphicsEffect` opacity/shadow machinery;
- old compositor/overlay fade/style application that exists only for the pre-Quick presenter.

Do not expand those paths because they still run today. Preserve the **visual/style contract**, then
move that contract to retained Quick owners and delete caller-proven legacy machinery.

Transient QWidget control styling for Settings/context controls is not automatically obsolete merely
because a similarly named runtime helper is.

## 4. Runtime style contract — PRESERVE / REHOME

Quick runtime must preserve, as applicable:

- font family/size;
- text color/opacity;
- background show/color/opacity;
- border width/color/opacity;
- corner radius;
- margin/padding;
- card shadows;
- text/header shadows;
- per-widget/global opacity/fade;
- artwork/progress/special family styling;
- one global eight-direction shadow orientation in General, defaulting to SE.

The direction setting rotates each shadow type's existing authored magnitude rather than replacing its
blur/spread/opacity/color or forcing every shadow to the same offset.

Do not remove a user-facing visual control merely because its QWidget implementation disappears,
unless `Current_Plan.md` explicitly retires that **control/behavior itself**. The known exception is
presentation-era state deliberately retired by the migration, such as the old per-mode visualizer
card-height/growth controls.

### 4.1 Widgets → General shadow-direction picker — REQUIRED F0.5 UI

E4 landed the canonical `widgets.shadows.direction` setting/runtime authority but intentionally did not
add its user-facing Settings control. F0.5 supplies that editor before the first retained family port.

Location:

```text
Settings
  -> Widgets
      -> General
          -> Shadow Direction
```

Use a **compact custom-styled 3×3 arrow-picker box** rather than a combo box or a vertical bank of eight
radio buttons:

```text
┌─────────────┐
│ ↖   ↑   ↗  │
│ ←       →  │
│ ↙   ↓   ↘  │
└─────────────┘
```

The eight selectable cells map to the existing canonical tokens:

```text
NW  N  NE
 W     E
SW  S  SE
```

The center cell is deliberately empty/inert. There is no center, none, automatic, or zero-offset
shadow-direction mode. Do not add a ninth semantic merely because the control uses a 3×3 layout.

Style/UX requirements:

- match existing SRPSS dark custom Settings chrome and spacing;
- remain compact enough to sit naturally inside Widgets → General rather than becoming a large panel;
- arrows/icons are the primary presentation, not `NW`/`SE` text labels;
- selected direction is immediately obvious without requiring focus;
- provide normal hover and pressed feedback consistent with nearby custom controls;
- keyboard focus/navigation must remain usable;
- expose tooltip/accessibility names such as `North West`, `North`, `South East`;
- fresh profile / Reset to Defaults selects `SE`;
- loading an invalid persisted token displays the canonical E4 fallback (`SE`) rather than inventing a
  separate UI repair policy.

Authority requirements:

- read/write the existing canonical `widgets.shadows.direction` value;
- reuse the E4 canonical token vocabulary/resolution policy; do not define a second direction enum or
  independent mapping table with different semantics;
- Settings remains QWidget; this control does not justify QML Settings UI;
- do not expose `SettingsManager` to runtime QML;
- do not directly reach into a retained family item from the picker. Use the normal Settings
  apply/save/recreate/update path used by shared visual settings;
- the picker controls **orientation only**. It does not alter card/text/header magnitude, blur, spread,
  opacity, color, or enabled state.

Focused F0.5 tests should cover all eight choices, center-cell inertness, canonical persistence/reload,
Reset to Defaults => `SE`, invalid-token fallback display, and normal Widgets → General lazy-page/save
behavior. F0.5 does not port Clock or another runtime widget family.

## 5. Shadow history and Phase E4 destination

Historical multi-monitor shadow corruption involved QWidget `QGraphicsEffect`/effect-cache behaviour.

Relevant records:

- `Docs/Historical_Bugs/U-06_MC_Shadow_Cache_Corruption.md`
- `Docs/Historical_Bugs/R-24_Retired_Overlay_Effect_Cache_Busting.md`

Painter-owned shadows were a QWidget-era correction, not the final Quick implementation.

Qt Quick runtime must **not** reintroduce `QGraphicsDropShadowEffect`/broad QWidget effect-cache
ownership.

For the Quick runtime:

- use one canonical `ShadowDirection` (`NW/N/NE/W/E/SW/S/SE`) and signed-offset resolver;
- preserve each surface's authored shadow magnitude;
- reserve four-sided visual padding so top/left directions cannot clip;
- prefer retained bounded mathematical/shader card shadows for rounded cards;
- use bounded Quick effects only where an arbitrary-shaped source genuinely requires them;
- do not use broad focus/menu/display cache-busting;
- do not toggle effect topology to animate fade;
- stress multi-monitor focus/context/hide/recreate.

E4 owns the global direction authority. Old runtime shadow implementations remain only until their
family/presenter callers are removed.

## 6. Settings styling safety

Continue to avoid:

- broad visibility/focus recursion;
- constructing every settings section at startup;
- styling work that triggers provider/network activity;
- changing Settings chrome as a workaround for runtime rendering issues;
- coupling family activation to eager page construction.

## 7. Change process

Shared runtime style change:

1. identify the surviving style contract and current owner;
2. if the owner is current-legacy, update/rehome the destination owner rather than deepening it;
3. update affected retained Quick components;
4. update `Docs/TestSuite.md` when test ownership/retirement changes;
5. run shared style/shadow gallery tests;
6. run focused family tests;
7. check focus/context/Settings/CUSTOM;
8. commit + push the landed slice.

No visual-fidelity downgrade as a performance fix.
