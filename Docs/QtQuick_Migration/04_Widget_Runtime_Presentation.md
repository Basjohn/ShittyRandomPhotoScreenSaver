# 04 — Runtime Widgets, Retained Quick Presentation, Shadows and Full Customization

Status: technical decomposition only
Last updated: 2026-08-20

Cross-links:

- `Current_Plan.md`
- `Docs/10_WIDGET_GUIDELINES.md`
- `Docs/Custom_Style_Implementation.md`
- `Future_Cleanup.md`

## 1. Core rule

Do not rewrite the widget ecosystem as QML business logic.

Split:

```text
provider / model / settings / refresh / actions
                    from
runtime pixel presentation
```

Keep the first side in Python.

Move the second side into the display's retained Quick scene.

## 2. Current overload

`WidgetManager` currently owns a dictionary of QWidget instances and mixes:

- creation;
- provider/model lifecycle;
- positioning;
- stacking;
- visibility;
- fades;
- effect invalidation;
- compositor readiness;
- Spotify secondary staging;
- live settings application.

`BaseOverlayWidget` also mixes:

- QWidget lifecycle;
- common style data;
- painter shadow caches;
- geometry;
- stack offset;
- pixel shift;
- card painting.

Do not recreate these as one giant Python Quick base class.

## 3. Presentation-neutral descriptor authority

Refactor canonical widget metadata so it is not defined by a QWidget factory.

Canonical descriptor should own things like:

```text
widget_id
settings_key
family_id
startup_stage
default position
monitor-routing keys
CUSTOM participation
base/inheritance keys
service requirements
```

Old QWidget factory creation metadata may remain in the old factory module until cutover.

Quick presentation registry maps family ids to retained Quick components.

After cutover, old factory-only metadata is deleted.

## 4. Future manager split

### `WidgetRuntimeManager`

Owns:

- model/provider lifetime;
- enabled/visible intent;
- monitor participation;
- settings updates;
- stacking inputs;
- action routing;
- runtime generation;
- presentation model registration.

It does not own QWidget instances.

### Quick widget presentation host

Owned by each `QuickSceneController`.

Creates/destroys retained Quick components for models assigned to that display.

It owns:

- QQuickItem instance;
- current geometry;
- z order;
- opacity/fade;
- edit overlay participation.

## 5. Widget model contract

Each family exposes only the state its visual needs.

Examples:

### Clock model

```text
formatted time/date strings
analog hand angles if analog
timezone label
display mode
style/config
```

Keep shared clock ticker/timezone computation in Python.

### Weather model

```text
location label
condition
temperature
forecast rows
icon source
style/config
```

Keep weather retrieval/cache/provider in Python.

### Media model

```text
title/artist/album
artwork image
playback state
progress
volume/mute
control availability
provider identity
style/config
```

Keep GSMTC/provider/control command logic in Python.

### Reddit/Gmail/Steam

Expose normalized rows/cards/actions; keep retrieval/filter/cache/ranking logic in Python.

## 6. Shared Quick visual primitives

Build small components rather than a base-god-object.

Suggested:

```text
OverlayRoot.qml
OverlayCard.qml
CardShadow.qml
ShadowedText.qml
HeaderRow.qml
Artwork.qml
Separator.qml
ProgressBar.qml
IconButton.qml
```

These components bind to explicit model/style properties.

## 7. Full style state

Create a presentation-neutral common style structure, e.g. `WidgetVisualStyle`.

It must represent current controls:

```text
font family
font size
text color/alpha
show background
background color/alpha
border width
border color/alpha
corner radius
margin/padding
card shadow enable/color/opacity/blur/offset/spread
text shadow enable/color/opacity/blur/offset
header shadow if distinct
overall widget opacity/fade
```

Family-specific style remains family-specific.

Do not collapse controls merely because Quick offers fewer convenient properties.

## 8. Shadow history and Quick rule

Historical bug:

```text
Docs/Historical_Bugs/U-06_MC_Shadow_Cache_Corruption.md
Docs/Historical_Bugs/R-24_Retired_Overlay_Effect_Cache_Busting.md
```

The old failure class involved QWidget `QGraphicsEffect`/cache/focus behaviour. Painter-owned card/text
shadows removed that dependency.

Qt Quick does not use that QWidget effect path, but the migration must still avoid fragile/general
effect churn.

### Card shadows

Preferred final representation on pinned Qt 6.9.1:

- a dedicated retained `ShaderEffect`/custom shadow item for rounded rectangular cards;
- parameters for radius, blur, spread, offset, color, opacity;
- draw behind the card;
- no source-item snapshot required;
- no effect topology toggling during fade.

This is conceptually equivalent to a mathematical rectangular shadow and avoids general full-source
blur cost.

### Arbitrary-shape shadows

Use `MultiEffect` only when genuinely required by an arbitrary shaped visual.

Rules:

- source bounds tight;
- do not apply to whole display;
- do not animate shader-topology properties;
- keep blur bounds explicit;
- disable rendering when not visible.

### Text/header shadows

Use the smallest representation that matches current appearance:

- retained shadow text/effect item;
- bounded effect source if blur is required;
- exact current offsets/opacity/color.

No global `QGraphicsEffect` cache-busting equivalent should exist.

## 9. Required old-corruption regression gate

The Quick widget gallery must repeatedly exercise:

```text
two displays
MC/interaction mode where available
focus display A
focus/click display B
context menu open/close
widget click
hide/show
Settings open/recreate
CUSTOM enter/cancel/save
monitor topology recreate
```

Visually inspect:

- card shadow;
- text/header shadow;
- opacity;
- clipping;
- stale texture;
- disappeared shadow;
- corrupted blur.

A corruption failure blocks the affected shared primitive, not the whole architecture.

## 10. Opacity/fades

Distinguish:

- content/background alpha;
- border alpha;
- shadow alpha;
- whole-widget fade opacity.

Use parent/root Quick `opacity` for authored fade when appropriate.

Do not animate by repeatedly enabling/disabling shadow/effect nodes.

## 11. Stacking

Keep current stacking policy/math in Python.

Quick scene consumes resolved geometry/z order.

Do not make QML anchors a second stacking algorithm.

CUSTOM position overrides authored stack placement according to existing contract.

## 12. Pixel shift

Keep pixel-shift scheduling/intent outside QML if already product-owned.

Apply resulting offset as a retained transform/property on the presentation item/root.

Do not rebuild widget content for pixel shift.

## 13. Family migration matrix

### Clock / Clock2 / Clock3

Preserve:

- digital/analog modes;
- seconds;
- timezone;
- day/date;
- calendar layout;
- analog numerals/face shadow;
- inherited secondary-clock styling;
- monitor-specific display-mode overrides.

This is the first ordinary-widget canary.

### Weather

Preserve:

- condition icon/alignment/size;
- forecast/details;
- font/margin;
- card style/shadows.

### Media

Preserve:

- artwork;
- rounded artwork;
- metadata;
- header frame;
- controls;
- Spotify volume;
- mute;
- playback progress;
- progress shadow/glow;
- live provider updates;
- click/control actions.

### Reddit / Reddit2

Preserve:

- header/logo;
- rows/items;
- separators;
- refresh indication;
- click/exit behaviour;
- inherited second-instance style/settings.

### Gmail

Preserve all current configured presentation switches:

- sender/subject;
- envelope/three-dot/refresh indicators;
- unread;
- header;
- timestamp/date mode;
- grouping;
- separators;
- desaturation;
- background/border;
- sound behaviour remains Python-owned.

### Steam family

Preserve each card's current:

- artwork;
- selection state;
- accent;
- capsules;
- desaturation;
- metadata rows;
- current dev gates.

### Imgur/dev families

If still canonical/enabled when reached, port them or deliberately retire them as a separate product
decision before cutover. Do not silently lose them because the migration ignored dev-gated runtime.

## 14. No screenshot-wrapper final implementation

A temporary development capture can be used for visual comparison.

Do not ship:

```text
old QWidget -> grab() -> texture -> Quick
```

as the final widget presenter.

## 15. Tests

Per family:

- model tests;
- settings-to-model mapping;
- style mapping;
- Quick component instantiation;
- geometry;
- CUSTOM;
- click/action routes;
- hide/show;
- DPR;
- visual capture/golden where robust;
- lifecycle.

Shared primitives receive stronger regression tests because every widget depends on them.

## 16. Commit cadence

Push:

- descriptor-neutralization;
- manager model/presentation split;
- common style/shadow primitives;
- each widget family;
- shared visual regression corrections.

Do not batch every widget into one commit.
