# Contracts — Current Owner Map

Last updated: 2026-08-28

`Current_Plan.md` owns work admission. This file owns fast current/destination owner routing.

## Physical presentation

| Concern | Destination owner |
| --- | --- |
| one display runtime | `QuickDisplayRuntime` |
| physical window | one standalone `QQuickWindow` |
| retained scene | `QuickSceneController` + retained Quick items |
| ordinary widget presentation | per-display `OrdinaryWidgetPresentationHost` |
| CUSTOM edit scene | neutral `CustomLayoutSession` + retained Quick overlay/model |
| context menu | retained Quick context-menu model/QML; Python semantic action authority |
| dimming / pixel shift / cursor halo | generation-scoped retained Quick auxiliary controller/state + same display scene |
| custom transition pixels | inline display `QSGRenderNode` |
| custom visualizer pixels | inline visualizer `QSGRenderNode` |
| Settings UI | existing QWidget/settings owners |

`QQuickWidget`, selectable old-presenter fallback and a second accelerated runtime surface are prohibited.
Engine startup may still reference legacy `DisplayWidget` until H; that is a temporary routing fact, not a requirement
that the legacy half-migrated runtime remain functional.

## H production runtime chain

H connects the already-landed destination exactly once:

```text
QuickDisplayRuntime
-> one display-owned WidgetRuntimeManager
-> canonical capability / ordinary-instance admission
-> existing neutral runtime/service lease(s)
-> stable presentation model(s)
-> QuickSceneController
-> retained family item(s)
```

`QuickSceneController` is sole runtime Quick-item creator/destructor for that display. Shared `QQmlEngine` is
component/cache infrastructure, not runtime-generation owner. Do not run old and Quick production runtime managers in
parallel.

## Retirement timing

| Legacy/migration owner | Retirement |
| --- | --- |
| ordinary QWidget family pixels | already retired family-by-family in F |
| shared old widget pixel helper | when last live old-pixel caller disappears |
| old transition/visualizer-only pixels | caller-proof immediately; H only for inseparable physical-host edges |
| old CUSTOM/edit/auxiliary pixels | caller-proof during G; no compatibility preservation for temporary continuity |
| remaining old physical presenter/backend/software fallback | H |
| residue/aliases/expired adapters | I |

Historical code is not reference-protected merely because the half-migrated product once needed it to run.

## Capability / ordinary enabled

Canonical family authority: `core/settings/widget_family_catalog.py` +
`core/settings/capability_activation.py`.

```text
family activated/deactivated != ordinary widget ON/OFF
```

CUSTOM X and layout-slot replay operate only on ordinary ON/OFF. They never activate a fully deactivated capability
or replace provider/account/source settings.

## Import dormancy

Common capability metadata and common Quick scene/host imports must not resolve inactive family business/runtime/
backend trees. Static presentation-only registry metadata may load; family implementation resolves at caller/
activation. Common Quick import must not bootstrap provider/controller/backend/runtime singleton.

## Ordinary widgets

```text
provider/backend/runtime owner
-> coherent accepted current state
-> stable presentation model/list model
-> retained family component
-> OrdinaryWidgetPresentationHost
-> OverlayWidget shell
```

Host owns item creation/retirement, display rect, root fade and card style; not provider, persistence, SettingsManager,
network or cadence.

| Family | Neutral/runtime owner | Presentation |
| --- | --- | --- |
| Clock | shared `GlobalClockTicker`; no invented service | stable per-instance Clock model/QML |
| Weather | manager-owned `WeatherRuntimeService` | stable Weather model/QML |
| Media | runtime-generation shared Media + display lease; separate shared volume/mute | one Media model/QML + process-engine artwork provider |
| Reddit/Reddit2 | independent configured `RedditRuntimeService` per member | separate stable models, one family QML |
| Gmail | runtime-generation shared Gmail + `GmailBackend.instance()` + display lease | retained model/QML |
| Achievement Pulse | neutral Steam runtime/preparation/cache/selection owners | retained model/QML |
| Abandonment Issues | neutral Steam runtime/data/cache/rotation owners | retained model/QML |

Presentation destruction does not automatically mean backend destruction; shared owners use real consumer cardinality.

## Actions / images

```text
QML semantic action -> Python admission/action owner -> business side effect -> accepted state -> presentation
```

QML does not directly own URLs/backend calls, persistence, provider/cache policy or refresh cadence.

Dynamic image precedent is process-engine `MediaArtworkImageProvider` over runtime-owned decoded `QImage` with stable
identity/bounded retention. No QPixmap worker transport, base64/tempfile churn or unchanged reupload.

## Shadow authority

Canonical includes direction, Card enabled/opacity/blur/extra offset, Text enabled/opacity/extra offset, and Header
enabled. No `widgets.shadows.offset`, Intense mode, Text Blur or `shadowtuning.json` replacement. Python resolves
direction to signed offsets before QML. Clock analogue geometry is the permanent explicit family exception.

## Transition / visualizer

Transitions: canonical registry/settings -> activation/admission -> immutable request/run -> lazy Quick implementation
-> display render node. Old compositor transition pixels are debris after caller proof.

Visualizer: Beat/source owners -> `VisualizerLogicalRuntime` -> mode logical runtime -> immutable/latest render state ->
Quick sync -> visualizer render node. One authored logical clock.

Visualizer geometry has two independent persisted dimensions of intent:

```text
uniform_visual_scale     # wheel/corners
viewport_extent          # left/right width; top/bottom height
```

All five current modes must support viewport extent. Bubble is not a destination exception; current false capability
gating is migration debt and must be removed with focused BTF/reflow proof.

## Geometry / CUSTOM

`CustomLayoutSession` owns working geometry/state independent of QWidget. Geometry keys include display identity and
variant. Save/Cancel and layout slots preserve ordinary ON/OFF semantics without crossing capability activation.
Cross-display transfer has one live retained pixel owner and preserves logical runtime/model identity.
