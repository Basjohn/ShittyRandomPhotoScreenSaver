# 09 — Ordinary Widget Qt Quick Presentation State Bridge

Status: **Phase-F technical bridge; E3 substrate landed/closed; E4 shadow normalization active next**  
Last updated: 2026-08-24  
Reviewed source basis: `1f25a791a2af822aff707f1e64ff836d0fc6f070`

Cross-links:

- active sequence: `Current_Plan.md`
- widget architecture/style: `Docs/QtQuick_Migration/04_Widget_Runtime_Presentation.md`
- runtime ownership/threading: `Docs/QtQuick_Migration/08_Widget_Runtime_Ownership_Threading.md`
- detailed family sequence: `Docs/QtQuick_Migration/10_Widget_Family_Port_Decomposition.md`
- host lifecycle: `Docs/QtQuick_Migration/01_Runtime_Host_Lifecycle.md`
- CUSTOM/input: `Docs/QtQuick_Migration/05_Custom_Layout_Input_Interaction.md`
- runtime efficiency: `Docs/Guardrails/Runtime_Efficiency.md`

This document defines the state/model/action/asset boundary used when ordinary widget pixels move into
the retained Quick scene. It does not own phase sequencing.

---

## 1. Landed presentation substrate

E3 is no longer hypothetical.

```text
QuickSceneFactory
    -> one process-level engine/component cache

QuickSceneController (per display)
    -> ordinaryWidgetHost

OrdinaryWidgetPresentationHost
    -> creates/retires OverlayWidget roots

OverlayWidget
    -> display rect + root fade
    -> OverlayCard
    -> family content area
```

The first Phase-F family should build on this seam, not replace it with another generic host.

---

## 2. Core family destination

```text
provider/backend/runtime owner
        ↓
normalized current family state
        ↓
stable presentation model
        ↓
family Quick component
        ↓
shared retained shell/primitives
```

Quick consumes presentation state and emits semantic actions.

Quick does not own:

- credentials/authentication;
- provider/network calls;
- cache policy;
- refresh cadence;
- SettingsManager;
- persistence;
- business side effects;
- background worker lifetime;
- general runtime generation.

---

## 3. Small static family registry

The first family may establish one static presentation descriptor/registry.

Its job is only to answer stable presentation questions such as:

```text
widget/family id
QML component path
expected presentation model kind/type
optional presentation capabilities
```

It is not a plugin framework.

The process-level Quick factory may compile/cache the family component using the existing engine.
Per-display creation happens in the current display context.

Do not put family dispatch into:

```text
DisplayScene.qml
QuickSceneController
WidgetRuntimeManager
```

A generic registry lookup is acceptable; central family-specific branching is not.

---

## 4. Stable scalar presentation models

Clock/Weather/Media summary state should use a stable explicit presentation object rather than exposing
a backend or rebuilding arbitrary object graphs.

A model should publish coherent state changes and avoid replacing itself for every ordinary update.

Example conceptual Clock surface:

```text
ClockPresentationModel
    timeText
    calendarText / calendarLines
    timezoneText
    displayMode
    hourAngle
    minuteAngle
    secondAngle
    showNumerals
    showSeparator
    separatorStyle
    style
    geometryVariant
```

Exact names remain source-owned. The contract is explicit, presentation-oriented state.

---

## 5. Repeating rows/cards

Reddit, Gmail and some Steam surfaces need deterministic row identity.

Use a bounded list model (`QAbstractListModel` or an equally clear proven seam) when appropriate.

Required:

- stable semantic row IDs;
- bounded item count;
- one coherent update transaction;
- no stale row action target;
- current-generation fencing;
- no raw backend object references in delegates.

Incremental diffing is optional when lists are small/infrequent. Correct bounded resets are acceptable.

---

## 6. State publication and atomicity

A runtime owner prepares one coherent next presentation state.

Avoid half-state such as:

```text
new media title
old artwork
new playback state
old provider identity
```

Possible bounded techniques:

- immutable state snapshot applied into a stable model;
- batch properties then emit one revision;
- bounded list reset/diff.

Do not add a heavyweight transaction framework to ordinary UI.

Identical state should be a no-op where practical.

---

## 7. Latest state vs events

Ordinary presentation is usually latest/current state:

```text
clock time
weather state
media metadata/progress
reddit rows
gmail rows
steam cards
```

Newer current state may replace older unread presentation state.

Business events such as notification sounds or provider-side exactly-once actions remain runtime-owned.
They must not depend on whether QML sampled a revision.

---

## 8. Semantic action boundary

Quick emits actions such as:

```text
toggle_clock_mode
open_item(id)
refresh
media_previous
media_play_pause
media_next
set_volume(value)
toggle_mute
archive_message(id)
open_message(id)
```

Routing:

```text
Quick handler
-> semantic action signal/router
-> presentation-neutral runtime/business owner
-> external action
-> new current state
-> presentation model
```

QML does not persist settings or call providers directly.

For Clock mode changes, the action owner changes canonical display mode and requests the target geometry
variant. QML itself does not write mode geometry.

---

## 9. Dynamic images/artwork

Static packaged assets should use package/QML resource paths.

For dynamic/provider images:

```text
provider/worker
-> bytes or decoded QImage + stable image identity
-> presentation image broker/model
-> one proven Quick image-delivery mechanism
-> retained Image/item
```

Do not:

- use QPixmap in general worker threads;
- build base64/data URIs every refresh;
- create tempfiles per update;
- decode/upload unchanged identities;
- invent one image bridge per family without a demonstrated need.

Do not build the dynamic-artwork seam during Clock. Weather may use static/identity-based assets. Media is
the likely first family that genuinely requires the shared dynamic-artwork path.

---

## 10. Geometry and geometry variants

Global outer geometry stays Python/session-owned.

Family QML lays itself out inside the assigned outer rect.

A widget may declare a stable presentation geometry variant when modes have materially different shapes.
This does not give QML persistence authority.

Known case:

```text
Clock:
  digital
  analog
```

The geometry owner must be able to answer:

```text
get committed rect(widget_id, display, variant)
set committed rect(widget_id, display, variant, rect)
```

without overwriting another variant.

Phase F establishes the semantic interface. Phase G implements final CUSTOM edit/session persistence.

---

## 11. Shared style bridge

Presentation style should distinguish:

- root fade opacity;
- card/background alpha;
- border alpha;
- card-shadow alpha;
- ordinary text alpha;
- ordinary text-shadow alpha;
- header shadow if distinct.

### Card shadows

`RectangularShadow` is the retained card primitive and is cached by default for ordinary static cards.
Direction/style/size changes rebuild the cache; root fade must not churn the shadow properties.

### Ordinary text shadows

Exact legacy source uses an offset duplicate text pass with alpha and size-sensitive magnitude. No
authored ordinary-text blur exists.

Destination `ShadowedText` therefore stays two retained glyph layers with signed offsets. Do not use
MultiEffect/layer capture to reproduce ordinary text parity.

Global shadow direction is resolved before QML and changes only the signs/axis of each authored shadow
magnitude.

---

## 12. Clock-specific text-shadow rule

Clock calendar/day/date and timezone are the same class of ordinary secondary text.

Destination rule:

- both consume the same resolved ordinary-text shadow style;
- no separate calendar shadow-distance authority;
- no mode-specific accidental extra offset;
- the current good timezone appearance is the visual reference for day/date;
- digital and analogue secondary text should agree unless a deliberate authored exception is later
  specified.

The main time/numerals may legitimately resolve through large-text tuning if the canonical text-shadow
resolver selects it by font size. That is different from inventing blur.

---

## 13. Update cost

Retained widgets should be event/state driven.

Forbidden unless separately earned:

- per-physical-frame Python callbacks for static UI;
- provider/network QML Timers;
- hidden continuous animations;
- rebuilding family component for unchanged data;
- large mutable map rebinding every tick;
- layer/MultiEffect capture for simple offset text shadow;
- image source changes when image identity is unchanged;
- static UI keeping a custom-GL pacer active.

Clock's one-second authored ticker may update time/angles once per second. Its static face/decorations
should not be rebuilt simply because the hand angle changed.

---

## 14. Lifecycle

Presentation lifecycle is not service lifecycle.

```text
runtime/model survives
        ↓
display scene/presentation item recreated
        ↓
new item binds current model state
```

Likewise, terminal runtime retirement closes publication and retires presentation without a retained QML
reference keeping a provider alive.

Required family tests should cover:

- item recreate/rebind without provider recreate;
- stale generation cannot update replacement item;
- host/display retirement releases family content;
- family deactivation does not leave family-exclusive presentation resources;
- cross-monitor transfer preserves logical model owner.

---

## 15. Family port inventory template

Before implementing each family, record:

### Runtime/business

- providers/backends;
- cache;
- cadence/timers;
- async request identity;
- shared/per-instance owners;
- actions and side effects.

### Presentation state

Every value actually required by pixels.

### Presentation features

- card/background/border;
- text/header shadows;
- artwork/icons;
- rows;
- progress/controls;
- fade;
- family-specific decoration;
- sizing and geometry variants;
- CUSTOM behavior.

### Actions

Every click/gesture/control -> semantic action.

### Assets

```text
static packaged
dynamic provider image
generated presentation image
custom GL
```

### Geometry

- default placement;
- stack footprint;
- variant identities;
- CUSTOM size/position semantics;
- min/max/aspect;
- display/DPR behavior.

### Final owner map

Every old QWidget responsibility gets one destination owner or explicit authorized retirement.

---

## 16. Completion tests

A family is not complete merely because QML loads.

Prove, as applicable:

- model mapping;
- stable row IDs/actions;
- stale generation fencing;
- no provider reconstruction on presentation recreation;
- static state causes no recurring presentation work;
- image identity/cache behavior;
- legal image thread ownership;
- action routing;
- settings/detail visual mapping;
- stacking/monitor geometry;
- geometry-variant round trips;
- retained shell/shadow semantics;
- no QWidget/backend dependency in final Quick component;
- visual parity plus any explicitly authorized product improvements.

Use synthetic/offline model data for a Quick widget gallery where provider access is irrelevant.

---

## 17. Anti-patterns

Do not land:

```text
raw SettingsManager in QML
provider/controller objects in QML
family if/elif dispatcher in scene/controller
one engine per widget
QML provider refresh timers
frame-driven Python ordinary widgets
arbitrary mutable dict tree as permanent family API
QPixmap worker transport
per-family image bridge without need
global stacking in QML
QWidget screenshot final presentation
QuickBaseOverlayWidget god-object
MultiEffect for ordinary offset-only text shadow
one persisted rect that silently overwrites another Clock mode variant
```
