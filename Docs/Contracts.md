# Contracts — Current Owner Map

Last updated: 2026-08-29

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
| Settings theme semantics/backdrop contract | `Docs/Settings_Theme_Architecture.md`; `SettingsThemeSpec` + Settings renderers + `core/windows/dwm_blur.py` |

`QQuickWidget`, selectable old-presenter fallback and a second accelerated runtime surface are prohibited.
Migration scaffolding may still reference legacy `DisplayWidget` before the production cutover. That is never a
destination contract or a reason to preserve a compatibility presenter.

## Settings theme ownership

```text
SettingsThemeSpec / strict .srtheme
-> ui/settings_theme_runtime.py
-> QWidget semantic renderers
-> ui/settings_dialog.py shell/native-mode ownership
-> core/windows/dwm_blur.py AccentPolicy adapter
```

On the current frameless translucent Settings HWND, Acrylic and Glass deliberately share the AccentPolicy composition
family. Acrylic = state 4 with theme native tint. Glass = untinted state 3; semantic Qt RGBA surfaces own its visible
colour/opacity. Off = state 0. Do not conflate AccentPolicy state 3 with the documented `DwmEnableBlurBehindWindow` API.

`themes/dark.qss` is legacy base-stylesheet residue, not visual authority. Its audited retirement is owned by
`Future_Cleanup.md`; do not alter native backdrop or forged-edge geometry merely to delete it.

## Production runtime chain

The destination connects exactly once:

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

Engine image processing consumes ordered immutable `DisplayProcessingDescriptor` values from `DisplayManager` and publishes
GUI-materialized results back through a screen-identity-keyed manager/display-unit operation. It does not retain or inspect
concrete QWidget/Quick presenter objects, compositor internals or private DPR fields.

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

Visualizer logical/source/presentation ownership is bounded and single-instance at product level:

```text
canonical enabled/activation + requested monitor
-> participating-display admission (exactly one visualizer owner)
-> VisualizerRuntimeController
-> controller-owned VisualizerLogicalTickState + all-five resolved logical/runtime config
-> one VisualizerLogicalRuntime authored clock
-> mode logical runtime
-> latest immutable VisualizerLogicalFrame
-> one GUI/Quick presentation synchronization owner
-> complete ResolvedVisualizerPresentation + VisualizerRenderSnapshot
-> existing VisualizerSnapshotBridge
-> retained visualizer render node on the admitted display
```

The logical runtime step advances against controller-owned state, never a live QWidget. Configuration ownership follows the
**actual consumer**, not the Settings subsection or historical widget field that supplied it. In particular, the canonical
resolved "technical" cache is not one ownership bucket:

```text
engine/DSP technical inputs
-> controller-owned shared BeatEngine / audio-worker boundary

technical-origin values consumed by authored logical evolution
-> controller-owned VisualizerLogicalTickState

renderer/style/chrome values
-> presentation state
```

Bar-count reconfiguration must leave controller authority, the shared engine generation and the controller-owned logical
display-bar mirror/freshness state coherent. Legacy overlay-only mirrors get no Quick successor unless an exact retained
consumer exists. Do not move every legacy widget field into the logical controller merely because the widget historically
stored several ownership classes together.

Binding or directly draining a render bridge is not delivery proof. The synchronization owner must populate it with a complete,
identity-fenced snapshot **and the retained visualizer item/node must actually admit that snapshot**. A failed authored-runtime
join blocks visualizer/display generation retirement. Retained visualizer double-click is semantic mode-cycle input and must be
admitted before the display-level next-image fallback. Retained visualizer middle-click is semantic same-mode preset-cycle
input: it advances one preset with wraparound, preserves mode identity, snapshots/restores the user-owned Custom slot, and
persists only `widgets.spotify_visualizer`. It must not become a whole-widget refresh, second visualizer owner, or disguised
cross-mode request.

Visualizer geometry has two independent persisted dimensions of intent:

```text
uniform_visual_scale     # wheel/corners
viewport_extent          # left/right width; top/bottom height
```

All five current modes must support viewport extent and the core capability policy is now all-five-mode capable. Bubble is
not a destination exception and must not be re-gated to hide a defect. Preserve focused BTF/reflow proof.

Viewport configuration has two precedence levels, not two persistence owners: ordinary committed extent is runtime truth;
an active CUSTOM session may provide a temporary working override. Save promotes the new value into committed truth, Cancel
restores the old committed value, and ending CUSTOM removes only the override. Inactive CUSTOM does not imply canonical
`(420,280)`.

## Geometry / CUSTOM

`CustomLayoutSession` owns working geometry/state independent of QWidget. Geometry keys include display identity and
variant. Save/Cancel and layout slots preserve ordinary ON/OFF semantics without crossing capability activation.
Cross-display transfer has one live retained pixel owner and preserves logical runtime/model identity.
