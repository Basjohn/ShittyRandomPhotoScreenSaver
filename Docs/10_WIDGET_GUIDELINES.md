# Widget Creation and Runtime Presentation Guide

Last updated: 2026-08-24

Canonical guide for adding or deeply refactoring a non-visualizer widget during the Qt Quick migration.

For sequencing read `Current_Plan.md`. For retained shell/shadow architecture read
`Docs/QtQuick_Migration/04_Widget_Runtime_Presentation.md`; for models/actions/assets read
`09_Widget_Quick_Presentation_Bridge.md`; for family-port detail read
`10_Widget_Family_Port_Decomposition.md`.

---

## 1. Split runtime logic from pixels

Understand every widget as:

```text
provider / model / settings / actions / cadence
                    +
runtime pixel presentation
```

The migration changes the second side.

Do not rewrite providers, persistence, authentication, cache or refresh policy into QML.

---

## 2. Activation and enabled state differ

```text
family activated/deactivated
    = may the capability resolve runtime/presentation ownership?

instance enabled/disabled
    = ordinary configuration inside an activated family
```

E1 runtime ownership is closed. E3/F work must not move provider/service lifetime back into
presentation.

A deactivated family ultimately owns no family-exclusive provider/model/process/poll/timer/presentation
resource. Shared infrastructure may remain while another valid consumer requires it.

---

## 3. Settings remain separate

The Settings UI may remain QWidget-based.

Opening Settings must not:

- start runtime providers merely to hydrate controls;
- construct every family section eagerly;
- perform network work;
- create Quick presentation resources for a family the user did not activate/open.

Application-level deactivation preserves detailed saved configuration.

---

## 4. Runtime presentation destination

```text
presentation-neutral Python owner/model
        ↓
compact explicit presentation state
        ↓
retained family QML inside ordinaryWidgetHost
        ↓
the display's one QQuickWindow
```

No extra accelerated widget window. No `QQuickWidget`.

---

## 5. Landed E3 substrate

Use the existing:

```text
OrdinaryWidgetPresentationHost
OverlayWidget.qml
OverlayCard.qml
ShadowedText.qml
Separator.qml
```

Do not replace them with a generic QWidget-like Quick base god-object.

The first family may establish a small static family-component registry/cache using the existing
process-level Quick engine.

---

## 6. Presentation model

Expose only state required by pixels/actions.

Good:

```text
explicit scalar properties
bounded stable list model
stable image identity
semantic action IDs
```

Bad:

```text
SettingsManager
provider/controller QObject
WidgetManager
QWidget
arbitrary mutable backend dict tree
```

Current state may coalesce. Exactly-once business events remain runtime-owned.

---

## 7. Geometry

Outer geometry is not family-QML persistence.

Python/session owners resolve:

- display;
- default anchor/stacking;
- outer rect;
- pixel shift;
- CUSTOM;
- DPR.

Family QML lays out inside that rect.

### Geometry variants

A widget may have more than one durable shape. Do not force all families into one-rect persistence.

Known required case:

```text
Clock digital
Clock analog
```

Each mode may have its own exact committed CUSTOM rect per display. Switching modes restores the target
variant instead of recursively deriving from the current mode and accumulating drift.

Phase F establishes family variant semantics. Phase G owns final CUSTOM Save/Cancel/edit persistence.

---

## 8. Styling and shadows

Preserve authored SRPSS visual language while removing obsolete implementation.

### Card shadow

Use retained Quick `RectangularShadow`.

Ordinary static card policy:

- cached by default;
- signed offsets;
- no clipping;
- root fade does not animate blur/spread/direction.

Do not build a parallel Python shadow pixmap cache around it.

### Ordinary text/header shadow

Exact legacy ordinary text shadow is:

```text
duplicate glyph
+ offset
+ alpha/color
+ size-dependent magnitude
```

There is no authored ordinary-text blur setting.

Destination text shadow should therefore be the retained duplicate-glyph pass. Do not use
MultiEffect/layer capture merely to make it look more sophisticated.

A future deliberate blurred-text feature may use an appropriate effect after evidence/measurement; this
guide does not ban MultiEffect universally.

### Global direction

E4 owns one global eight-direction orientation:

```text
NW N NE W E SW S SE
```

Default `SE`.

Direction changes signs/axis only. Magnitudes/alpha/blur/spread remain class-specific.

---

## 9. Performance

A migrated widget must not:

- create a second accelerated surface;
- keep a Python physical-frame callback for static content;
- run provider refresh through QML Timer;
- rebuild stable component trees for unchanged data;
- use layer/MultiEffect capture for simple offset text shadow;
- decode/upload unchanged images;
- multiply provider/timer/thread cardinality;
- force whole-scene rebuild for tiny changes.

Retained static effects should exploit the scene graph's retained/cached behavior where appropriate.

Measure whole-scene GPU/frame impact with multiple real widgets, not only local callback time.

---

## 10. Clock family authoring rules

Clock is first Phase-F family after F0.

Preserve the shared Python ticker/timezone logic.

Intentional Quick-port visual improvements:

- separator thickness: 2 logical px;
- separator target width: ~0.77 of available inner width;
- one symmetric separator gap above/below;
- separator applies in analogue mode too when selected;
- calendar/day/date shadow uses the same ordinary-text shadow style as timezone;
- no text blur/MultiEffect for Clock text;
- digital/analogue are geometry variants with exact round-trip restoration.

Do not let a one-second clock tick rebuild static face decoration every physical frame.

---

## 11. Dynamic images

Use stable identity/cache keys.

Preferred:

```text
worker/provider
-> bytes or decoded QImage + identity
-> shared presentation image seam
-> retained Quick image
```

Avoid:

- QPixmap worker ownership;
- base64/data URI churn;
- tempfiles per update;
- per-family image bridge when one shared seam fits;
- upload when identity is unchanged.

Do not invent the full dynamic-artwork seam during Clock. Let the first real image consumer earn it.

---

## 12. Input/actions

Quick owns visual hit areas; Python owns semantic action execution/persistence.

Examples:

```text
toggle_clock_mode
open_item(id)
refresh
play_pause
set_volume(value)
toggle_mute
```

Do not call providers or write Settings directly from QML.

---

## 13. Lifecycle

Presentation item recreation must not recreate providers unless the provider is genuinely
per-presentation by contract.

On retirement:

- state admission closes;
- stale results cannot publish into replacement generation;
- presentation detaches/retires;
- family-exclusive runtime resources retire through their actual owner;
- shared owners survive only while valid consumers exist.

---

## 14. CUSTOM

Edit the real retained Quick item where practical.

Save persists current session intent. Cancel restores baseline without provider/model reconstruction.

Support geometry variants; never assume one permanent rect per widget id.

See `05_Custom_Layout_Input_Interaction.md`.

---

## 15. Deprecated Imgur

Imgur is removed in F0, not migrated.

Do not create a Quick Imgur component or repair its old presentation path merely to preserve migration
symmetry.

---

## 16. Testing

Test at the owner appropriate to the claim:

- capability/activation;
- provider/model;
- presentation mapping;
- retained QML;
- shadow direction/cache;
- model/item recreation;
- actions;
- geometry variants;
- CUSTOM;
- multi-display/DPR;
- installed visual parity.

Before retiring an old QWidget test, prove its surviving behavior through the destination owner.
