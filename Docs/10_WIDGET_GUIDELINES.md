# Ordinary Widget Authoring Guide

Last updated: 2026-08-26

Canonical guide for adding or deeply refactoring a **non-Visualizer runtime widget** in the accepted Qt
Quick architecture. This guide is based on landed/proven patterns from Clock, Weather, Media and Reddit.
Gmail is the current partial family and is an active example, not closure authority.

`Current_Plan.md` owns which family may be changed now.

## 1. Start with ownership, not pixels

Classify the concern first:

```text
application capability
ordinary instance enabled state
provider/backend/runtime state
presentation model/state
retained pixels
```

Family activation/deactivation is application-level. Ordinary `enabled=False` is the casual per-instance
off state inside an activated family. Do not collapse them.

Before adding `FooRuntimeService`, answer:

1. Does meaningful non-pixel lifetime/state need a new owner?
2. Is there already a correct neutral owner?
3. What is the real cardinality: process/shared, runtime-generation shared, per-display or per-instance?
4. What recurring work/provider/cache/action authority exists before and after?
5. What retires it and fences stale completion?

Do not add a service merely for naming symmetry.

## 2. Destination chain

```text
canonical capability/settings
-> WidgetRuntimeManager or existing neutral owner
-> coherent accepted runtime state
-> stable presentation model / bounded list model
-> Retained<Family>Presentation wrapper
-> OrdinaryWidgetPresentationHost
-> family QML
-> OverlayWidget / OverlayCard / ShadowedText
-> display's one QQuickWindow
```

The presentation host creates/retires retained items and applies outer geometry, root fade and card style.
It is not a provider, SettingsManager, cache owner or business controller.

No extra accelerated widget window. No `QQuickWidget`.

## 3. Proven ownership patterns

### Clock

```text
GlobalClockTicker
-> stable ClockPresentationModel per logical instance
-> retained ClockPresentation.qml
```

Ticker was already neutral. No Clock runtime service was invented.

### Weather

```text
WidgetRuntimeManager
-> WeatherRuntimeService
-> WeatherPresentationModel
-> retained WeatherPresentation.qml
```

Provider/network/cache/cadence/retry/request generation remain runtime-owned.

### Media

```text
runtime-generation shared Media owner
-> per-display MediaRuntimeService lease
-> one retained MediaPresentationModel/item

separate shared app-volume owner -> narrow lease
separate shared system-mute owner -> narrow lease
```

Dynamic artwork uses one process-engine image provider with stable runtime-owned identity and bounded
retention. Presentation does not become playback/controller truth.

### Reddit / Reddit2

Each configured member keeps independent feed/config/runtime identity through a per-member
`RedditRuntimeService` and stable retained model. Shared family rate-limit/policy infrastructure remains
shared; Reddit2 is not a second provider architecture.

### Gmail

The runtime-generation shared Gmail owner and process `GmailBackend.instance()` remain the backend/cache/
cadence/action/notification/sound authority. The retained port projects that owner; do not create another
backend abstraction.

### Steam cards

Use current neutral Steam models/runtime/cache/privacy/provenance seams. Do not manufacture Quick ports for
unfinished Steam Journey/Progress or Friend Pulse scaffolds.

## 4. Import dormancy is architecture

Forbidden:

```text
import common Quick scene/host
-> import every family presentation module
-> import inactive family runtime/backend/provider tree
```

Rules:

- common `rendering.quick.widgets` infrastructure stays light;
- family implementation imports at actual family caller/activation boundary;
- static presentation-only family metadata may remain in a light registry;
- annotation-only runtime types use `TYPE_CHECKING` where appropriate;
- importing common Quick host constructs/bootstraps no provider/controller/runtime/backend singleton.

Fresh-process dormancy tests cover the destination Quick host, not only legacy QWidget imports.

## 5. Presentation model design

Prefer stable explicit Python models:

- immutable/bounded config record;
- immutable/bounded style record;
- coherent accepted runtime revision;
- explicit scalar properties;
- stable `QAbstractListModel` for rows;
- stable semantic row/item IDs;
- stable image identities;
- explicit action capability flags.

Do not expose to QML: `SettingsManager`, QWidget, business provider/backend objects, arbitrary mutable backend
dicts, raw CUSTOM persistence, or provider refresh timers.

Identical effective state should be a no-op where practical. Normal setting/style/state changes mutate the
existing retained item/model/list model instead of recreating item/model/runtime/engine/window.

## 6. Coherent state / stale fencing

Publish one coherent accepted revision. Avoid mixed state such as new metadata with old artwork or new
provider with old capability flags.

A worker completion is legal only if relevant identities still match, e.g. runtime generation, owner/service
generation, request generation, account/location/feed/provider identity, activation identity.

Stale work may physically finish; it becomes a fenced no-op. Model retirement makes later callbacks harmless.

## 7. Lists

Reddit/Gmail/Steam-style rows use bounded stable semantic IDs and coherent update transactions. A simple
bounded reset is fine when correct; do not invent a universal diff engine without need.

Delegate index is presentation position, not semantic identity. Transient popup/menu UI is not row geometry
authority.

## 8. Actions

```text
QML semantic signal
-> Python presentation/action admission
-> neutral runtime/business owner
-> side effect
-> accepted current state
-> presentation update
```

QML does not directly persist settings, own auth, perform network I/O, decide cache policy, call backend
APIs as business authority, or mutate accepted playback/message/provider truth.

Purely visual press/flash/menu-open state may be QML-owned. Interaction admission is shared runtime input
policy, not separately invented per family.

## 9. Dynamic images

Proven Media pattern:

```text
runtime owns decoded QImage + stable key
-> process-engine MediaArtworkImageProvider
-> image:// stable identity
-> retained Image
```

No QPixmap worker transport, base64 churn, tempfile per update, unchanged-image reupload, or unearned
per-widget provider duplication. Static packaged icons can use stable packaged file identities.

## 10. Geometry / dynamic height

Outer geometry is Python/session-owned. QML lays out inside assigned rect.

Materially different shapes may have stable variants:

```text
(widget_id, display_identity, geometry_variant)
```

Clock digital/analogue is the first proven case. Never repeatedly derive one saved variant from the other
and accumulate drift.

Content-driven natural height may derive from accepted state. Keep it separate from transient overlays.
Opening Gmail's three-dot menu must not rewrite Gmail's committed CUSTOM height.

## 11. Shared edit-mode X

Every adjustable card gets X in edit mode. This is shared CUSTOM/session behavior, not a family business
command:

- duplicate -> remove duplicate from working layout;
- singleton -> ordinary widget OFF, same meaning as its normal Settings checkbox;
- never map X to family/capability deactivation;
- do not persist or destroy committed provider/runtime state on click.

Context-menu Save or Enter commits. Cancel restores geometry, duplicate set and ordinary enabled state.
Family QML does not persist this itself.

## 12. Card / text / header style

Ordinary card:

```text
OverlayCard -> cached RectangularShadow
```

Ordinary text:

```text
shadow glyph at signed offset
+ visible glyph
```

No ordinary text blur or MultiEffect/layer capture for parity. Canonical direction resolves in Python.
Current ordinary base distances live in the retained widget host. Card/frame **Extra Offset grows only the selected far edge(s)** while preserving opposite-edge coverage; Text Extra Offset remains glyph displacement. Canonical direction resolves in Python.

A family owns a visual exception only if it independently authored that relationship. Retired
`shadowtuning.json` card/text/header/icon/control/volume values are not family-authored because a widget once
consumed them.

Family header geometry remains family content, but colours/opacity come from the correct style authority,
not an unrelated value such as a row separator colour.

## 13. Fade / animation

Whole ordinary-widget fade:

```text
OverlayWidget.fadeOpacity -> root Item.opacity -> whole subtree
```

Do not port `ShadowFadeProfile`, `QGraphicsOpacityEffect` choreography, dummy/effect carriers or separate
shadow fade timelines.

A retained intermediate `Item` needs a real layout/transform/clip/z/input/lifecycle purpose.
Presentation-only animation may be retained Quick animation but must not become provider cadence or logical
simulation authority.

## 14. Family fidelity rule

Migration preserves working family-specific product behavior unless a deliberate product change is requested.
Preserve content hierarchy, meaningful layout relationships, interaction/menu/action semantics, family-specific
geometry, authored animation and independently-authored visual relationships.

Do not preserve obsolete QPainter caches, QWidget hit rectangles, QGraphics effects or retired global tuning
merely for mechanical parity. A retained replacement is not an excuse for unrelated UI redesign.

## 15. Lifecycle / retirement

```text
construct inert model/wrapper
-> inject real neutral service/lease
-> activate after admission
-> consume current accepted state
-> retire presentation
-> detach/stop lease according to real cardinality
-> fence stale completion
```

Presentation destruction does not automatically mean backend destruction. Shared owners retire only when
real consumer set is empty.

After family GREEN under current audit policy + caller proof, delete old QWidget/QPainter pixels and
presentation-only tests. Do not keep an old selectable/fallback presenter for safety.

## 16. Performance / resource rules

Static retained widgets must not create Python callbacks per physical frame, run provider refresh through
QML `Timer`, rebuild stable trees for unchanged state, keep hidden continuous animation alive, multiply
provider/controller/timer/thread/subscription cardinality, keep custom-GL frame demand active merely by
existing, or load inactive family backends through common imports.

Measure whole-scene cost with several real widgets, not only isolated component cost.

## 17. Validation checklist

Deterministic/model as applicable:
- config/default/style projection;
- stable IDs/list model;
- coherent revision/state mapping;
- stale rejection;
- semantic action admission;
- no-op mutation.

Ownership/runtime:
- real `WidgetRuntimeManager` or existing neutral owner injection;
- cardinality preserved/reduced;
- activation vs ordinary enabled distinction;
- one consumer retirement does not kill surviving shared consumers;
- stale async fenced;
- capability/common-import dormancy.

Retained Quick:
- one existing process engine/window path;
- stable item/model/list-model identity;
- geometry/fade/style changes in place;
- no QWidget/effect/business object in QML;
- no extra accelerated surface.

Eyes-on:
- normal/empty/loading/error/cached states where relevant;
- card on/off;
- realistic long/short content;
- practical DPRs/sizes;
- interactions/transient menus/controls;
- busy background where readability/shadows matter.

Then caller-proof and retire old pixels.

## 18. Visualizer exception

Spotify Visualizer is not an ordinary widget-family presentation. Its authored logical runtime and inline
custom-GL render-node contracts are governed by visualizer docs/guardrails. Do not force it through ordinary
widget abstractions merely for consistency.
