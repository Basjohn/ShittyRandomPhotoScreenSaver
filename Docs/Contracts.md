# Contracts — Current Owner Map

Last updated: 2026-08-27

`Current_Plan.md` owns work admission. This file owns fast current/destination owner routing.

## Physical presentation

| Concern | Destination owner |
| --- | --- |
| one display runtime | `QuickDisplayRuntime` |
| physical window | one standalone `QQuickWindow` |
| retained scene | `QuickSceneController` + retained Quick items |
| ordinary widget presentation | per-display `OrdinaryWidgetPresentationHost` |
| custom transition pixels | inline display `QSGRenderNode` |
| custom visualizer pixels | inline visualizer `QSGRenderNode` |
| Settings UI | existing QWidget/settings owners |

`QQuickWidget`, selectable old-presenter fallback and second accelerated runtime surface are prohibited.
Normal production startup remains old `DisplayWidget` until H; H replaces it rather than creating permanent
dual presentation.

## H production runtime chain

Before cutover:

```text
QuickDisplayRuntime
-> one display-owned WidgetRuntimeManager
-> canonical capability / instance admission
-> existing neutral runtime/service lease(s)
-> stable presentation model(s)
-> QuickSceneController
-> retained family item(s)
```

`QuickSceneController` is sole runtime Quick-item creator/destructor for that display. Shared `QQmlEngine`
is component/cache infrastructure, not runtime-generation owner.

## Retirement timing

| Current-legacy owner | Retirement |
| --- | --- |
| ordinary QWidget family pixels | family GREEN under current audit policy + caller proof |
| shared old widget pixel helper | last real old-pixel consumer disappears |
| old transition-only pixels | caller-proof early; H maximum if physical-host bound |
| old visualizer-only pixels/card/overlay | caller-proof early; H maximum if physical-host bound |
| old CUSTOM/edit pixels | G replacement GREEN |
| old physical presenter/backend/software fallback | H |
| residue/aliases/expired adapters | I |

Historical code is not automatically reference-protected.

## Capability / ordinary enabled

Canonical family authority: `core/settings/widget_family_catalog.py` +
`core/settings/capability_activation.py`.

```text
family activated/deactivated != ordinary widget enabled/disabled
```

Visualizers requires Media but keeps its special visualizer runtime/render ownership outside ordinary
Phase-F family presentation.

## Import dormancy

Common capability metadata and common Quick scene/host imports must not resolve inactive family business/
runtime/backend trees. Static presentation-only registry metadata may load; family implementation resolves
at caller/activation. Common Quick import must not bootstrap provider/controller/backend/runtime singleton.

## Ordinary widgets

```text
provider/backend/runtime owner
-> coherent accepted current state
-> stable presentation model/list model
-> retained family component
-> OrdinaryWidgetPresentationHost
-> OverlayWidget shell
```

Host owns item creation/retirement, display rect, root fade and card style; not provider, persistence,
SettingsManager, network or cadence.

| Family | Neutral/runtime owner | Presentation |
| --- | --- | --- |
| Clock | shared `GlobalClockTicker`; no invented service | stable per-instance Clock model/QML |
| Weather | manager-owned `WeatherRuntimeService` | stable Weather model/QML |
| Media | runtime-generation shared Media + display lease; separate shared volume/mute | one Media model/QML + process-engine artwork provider |
| Reddit/Reddit2 | independent configured `RedditRuntimeService` per member | separate stable models, one family QML |
| Gmail | runtime-generation shared Gmail + `GmailBackend.instance()` + display lease | retained model/QML; old QWidget presenter retired |
| Achievement Pulse | existing neutral Steam runtime/preparation/cache/selection owners | retained model/QML; old QWidget presenter retired |
| Abandonment Issues | existing neutral Steam runtime/data/cache/rotation owners | retained model/QML; old QWidget presenter retired |

Presentation destruction does not automatically mean backend destruction; shared owners use real consumer
cardinality.

## Actions / images

```text
QML semantic action -> Python admission/action owner -> business side effect -> accepted state -> presentation
```

QML does not directly own URLs/backend calls, persistence, provider/cache policy or refresh cadence.

Dynamic image precedent is process-engine `MediaArtworkImageProvider` over runtime-owned decoded `QImage`
with stable identity/bounded retention. No QPixmap worker transport, base64/tempfile churn or unchanged
reupload.

## Shadow authority

Canonical includes direction, Card enabled/opacity/blur/extra offset, Text enabled/opacity/extra offset,
and Header enabled. No `widgets.shadows.offset`, Intense mode, Text Blur or `shadowtuning.json` replacement.
Python resolves direction to signed offsets before QML.

A value is family-authored only when family independently owns it. Clock analogue special geometry is the
permanent explicit exception.

## Transition / visualizer

Transitions: canonical registry/settings -> activation/admission -> immutable request/run -> lazy Quick
implementation -> display render node. Old compositor transition pixels are debris after caller proof.

Visualizer: Beat/source owners -> `VisualizerLogicalRuntime` -> mode logical runtime -> immutable/latest
render state -> Quick sync -> visualizer render node. One authored logical clock; preserve destination-used
adapters regardless of filename.

## Geometry / CUSTOM

Outer geometry is Python/session-owned; key supports `(widget_id, display_identity, geometry_variant)`.
Clock has digital/analogue variants.

Edit-mode X: duplicate removes working duplicate; singleton maps to ordinary enabled OFF; never capability
deactivation; persist on Save/Enter only; Cancel restores prior state.

## Lifecycle / documentation

Generation 0 is valid. Old admission closes before replacement authority. Stale generation/request results
cannot update replacement. Render resources retire on legal owner.

Authority order: exact source for implementation fact -> `Current_Plan.md` for sequence -> `Spec.md` and
focused current docs for durable contract -> tests/evidence for claim. Historical plans cannot override.
