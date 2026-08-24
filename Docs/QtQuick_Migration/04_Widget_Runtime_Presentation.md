# 04 — Retained Quick Runtime Widgets

Status: **Phase-F current architecture/style authority**  
Last updated: 2026-08-24

## Core rule

```text
provider / runtime / model / settings / actions
-> presentation state
-> retained Quick family pixels
```

Do not rewrite the widget ecosystem as QML business logic.

## Landed host

```text
QuickSceneController
-> ordinaryWidgetHost
-> OrdinaryWidgetPresentationHost
-> OverlayWidget
   -> OverlayCard
   -> family content
```

Shared primitives:

```text
OverlayWidget.qml
OverlayCard.qml
ShadowedText.qml
Separator.qml
```

One process Quick engine/component cache; no engine/window per widget.

## Ownership

Presentation host owns:

- retained item creation/retirement;
- display rect application;
- root fade;
- shell/card/style projection;
- family content attachment.

It does not own:

- providers;
- persistence;
- SettingsManager;
- network;
- provider refresh cadence;
- global business side effects.

## Geometry

Outer geometry remains Python/session-owned.

Family QML owns layout inside assigned rect.

Support stable variants for materially different shapes:

```text
Clock + display:
  digital -> rect A
  analog  -> rect B
```

## Fade

Whole ordinary-widget fade:

```text
OverlayWidget root opacity
-> whole subtree
```

Do not port QWidget effect carriers, dummy shadow widgets or staged `QGraphicsOpacityEffect`/
`ShadowFadeProfile` choreography.

## Card shadow

Destination ordinary card:

```text
OverlayCard
-> RectangularShadow
```

Default `cached: true` for ordinary static cards.

Style/geometry/direction changes naturally invalidate the Qt cache. Root fade does not churn blur/spread.

No Python/QPixmap shadow cache around it.

## Text shadow

Destination ordinary text:

```text
shadow Text at signed offset
+ visible Text
```

No ordinary text blur.
No MultiEffect/layer capture merely for parity.

## Canonical global shadow user state

```text
Card:
  enabled
  frame_opacity
  blur_radius
  frame_extra_offset

Text:
  text_enabled
  text_opacity
  text_extra_offset

Header:
  header_enabled

All:
  direction = NW/N/NE/W/E/SW/S/SE
```

Old `widgets.shadows.offset` is retired.
No Intense mode.
No `shadowtuning.json`.

Python resolves final signed offset/style before QML.

## Family-authored reference definition

Do not confuse a historical shared-tuning consumer with a family-authored visual rule.

A relationship is family-authored only when the family independently defined/owned it.

Examples:

- Clock analogue ring/marker/numeral/hand geometry: family-authored.
- old sidecar `card/text/text_large/header/icon/control/volume_slider` values: global tuning, not
  family-authored.

F0.5 audit correction removes copied generic sidecar profiles.

## Destination base magnitudes

F1 Clock establishes the first deliberate ordinary Quick card/text base-distance policy.

Do not derive that policy mechanically from deleted painter-sidecar numbers.

Later families reuse/extend the destination style policy only when their actual visual semantics require
a distinction.

## Family lifecycle

A presentation item can recreate/rebind current model state without provider recreation.

Stale generation state cannot update replacement presentation.

After a family is GREEN, caller-proof and delete its old QWidget pixels promptly.

## Update cost

Do not introduce:

- Python callback per physical frame for static content;
- QML provider/network timers;
- always-running hidden animations;
- full component rebuild for ordinary property changes;
- unchanged-image upload;
- static widgets keeping custom-GL frame demand active.

One-second Clock updates are authored state, not permission for physical-frame work.
