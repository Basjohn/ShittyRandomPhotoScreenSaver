# Widget Creation and Runtime Presentation Guide

Last updated: 2026-08-24

Canonical guide for adding or deeply refactoring a non-visualizer runtime widget during the Quick
migration.

## Core split

```text
provider / model / settings / actions / cadence
+
runtime pixel presentation
```

The migration changes runtime pixels, not business ownership.

Do not move provider/network/cache/auth/persistence/refresh logic into QML.

## Destination

```text
presentation-neutral Python state/model
-> retained family QML
-> shared OverlayWidget / OverlayCard / ShadowedText
-> display's one QQuickWindow
```

No extra accelerated widget window. No `QQuickWidget`.

## Presentation state

Prefer:

- explicit scalar properties;
- stable bounded list models;
- stable image identities;
- semantic action IDs.

Do not expose:

- `SettingsManager`;
- provider/controller QObjects;
- QWidget;
- arbitrary mutable backend dictionaries.

## Geometry

Outer geometry is Python/session-owned.

Family QML lays out inside assigned rect.

Support variants where shape genuinely differs:

```text
Clock:
  digital
  analog
```

Never repeatedly derive one variant geometry from the other and accumulate drift.

## Shadows

Ordinary card -> retained cached `RectangularShadow`.

Ordinary text -> duplicate retained glyph at signed offset.

No ordinary Text Blur.

One global direction (`NW/N/NE/W/E/SW/S/SE`, default `SE`) resolves in Python.

Current user buckets:

```text
Card: frame_opacity, blur_radius, frame_extra_offset
Text: text_opacity, text_extra_offset
```

No Intense mode. No `widgets.shadows.offset`. No `shadowtuning.json`.

### Family-authored reference rule

During a family port, preserve old visual behavior that the family itself authored independently.

Do **not** relabel old global tuning as family-authored merely because a widget used it.

The retired sidecar's generic card/text/header/icon/control/volume-slider numbers are not family-owned
reference authority.

Clock analogue bespoke hard-shadow geometry is family-authored and reference-protected through F1.

## Fade/effects

Do not port `ShadowFadeProfile`, `QGraphicsOpacityEffect`, dummy effect carriers or staged
widget-vs-shadow fades.

Destination ordinary whole-widget fade = one outer retained root opacity.

An intermediate Quick `Item` needs a real layout/transform/clip/z/input/lifecycle role.

## Provider/runtime lifecycle

Presentation recreation must not recreate a provider unless the provider is genuinely
per-presentation by contract.

Stale generations cannot update replacement presentation.

Activation differs from ordinary enabled state.

## Dynamic images

Use stable identity and one earned shared image-delivery seam.

No QPixmap worker transport, base64 churn, tempfiles per update or unchanged-image reupload.

Do not prebuild dynamic artwork during Clock.

## Actions

QML emits semantic actions; Python executes/persists them.

## Family retirement

For every ordinary family:

```text
inspect old pixels as reference
-> port
-> tests + eyes-on
-> independent GREEN
-> caller proof
-> delete old family pixels/presentation-only tests
```

Git is historical reference after deletion.

Shared old helpers remain only while another unported family genuinely needs them.

## Performance

Static retained widgets must not:

- create Python physical-frame callbacks;
- run provider refresh via QML Timer;
- rebuild stable trees for unchanged state;
- keep hidden continuous animation;
- multiply provider/timer/thread cardinality;
- keep custom-GL frame demand alive merely by existing.

Measure whole-scene cost with several real widgets.

## Steam family

The old 2026-07 Steam implementation plan contains useful product/data/privacy/visual history but obsolete
QWidget/painter architecture.

Read the current wrapper at `Docs/SRPSS_Steam_Widget_Family_Implementation_Plan.md`; use current neutral
Steam models/runtime and Phase-F Quick contracts for implementation.
