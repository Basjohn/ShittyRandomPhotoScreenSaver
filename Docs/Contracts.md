# Contracts — Current Owner Map

Last updated: 2026-09-02

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
| dimming / pixel shift / cursor halo | `QuickAuxiliaryController` owns low-rate semantic admission/shape; dimming + pixel shift project into the retained scene, while Cursor Halo presentation is a generation-scoped native `QCursor` owned by `QuickCursorController` and never moves a retained QML item |
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

Future runtime Widget Themes are a separate visual bundle authority over widget/runtime-overlay appearance. Theme identity
and surface material are intentionally orthogonal:

```text
Widget Theme (.srwtheme)
    -> semantic runtime palette / proven visual-only values
    -> default_card_material_mode = normal | glass | acrylic

user Surface Style
    -> card_material_override = theme | normal | glass | acrylic

resolver
    -> effective_card_material_mode
```

`Theme Default` is the default/no-override state. An explicit Normal/Glass/Acrylic selection overrides material only and
retains the selected Widget Theme's colours; it does not mutate/dirty the theme or alter `Keep Synced`.

**Widget Theme palette precedence:** Widget Theme card colours are global/default baseline values. Explicit existing `widgets.<family>.card.*` values remain higher-precedence family overrides; they are not silently reclassified as theme state. The Context Menu has no family override layer and takes Widget Theme palette values directly. A per-family swatch edit therefore does not create Widget Theme `Custom`; editing a Widget-Theme-owned baseline value does.

**Semantic visual-role contract (schema v2):** specialized decorative roles are sparse and inherit through one Qt-free resolver: intentional family override -> exact theme role -> shared semantic parent -> caller-supplied `local.*` current semantic value -> preserved current fallback. `local.*` tokens are runtime/presentation context only and must never serialize into `.srwtheme`, Custom or Settings. Default-valued legacy family swatches act as implicit Inherit; only a genuinely changed stored value is an explicit family override. Adding a role is therefore not permission to recolour Default Dark or to add a permanent visible Settings swatch. A bounded high-value family override **may** be exposed when users genuinely author it; such controls belong in collapsed semantic Settings buckets and still use default-valued = Inherit semantics. Slice 9 Media is the reference: `Header Appearance`, `Seek Bar`, and `Volume Control` expose the useful family overrides while lower-level transport/mute/panel/icon roles remain inherited. New retained widgets must consume this resolver rather than implement another Media/Steam/family-local theme cascade. Visualizer's specialised line/presentation system remains exempt from the generic decorative-stroke migration.

Manual editing of any Widget Theme-owned visual value has one separate deterministic contract: snapshot the complete
currently resolved named Widget Theme into user-owned `Custom`, apply the edit to that snapshot, select `Custom`, and turn
`Keep Synced` OFF. The installed/shipped `.srwtheme` remains immutable and all unedited resolved values survive the
transition. `Custom` is serialized in normal SRPSS Settings persistence rather than emitted as a `.srwtheme` file, so
ordinary customization never needs write access to `%ProgramData%\SRPSS\themes\widgets`. Exporting/saving a real Widget
Theme file is a separate explicit authoring operation. Do not create hidden per-property override inheritance. Re-enabling
Keep Synced may reselect the linked named Widget Theme but must not destroy the saved Custom snapshot.

Future `Keep Synced` defaults ON and links each Settings theme to an explicit mirrored Widget Theme; sync OFF permits
independent GUI/runtime theme combinations, and sync changes never erase an explicit surface override. Matching names may
help author theme packs, but runtime links must use stable metadata/IDs rather than display-name heuristics.

Theme storage uses one resolved root with a Widget child:

```text
installed/frozen: %ProgramData%\SRPSS\themes        -> .srtheme
                  %ProgramData%\SRPSS\themes\widgets -> .srwtheme

source/dev:       <repo-root>\themes
                  <repo-root>\themes\widgets
```

Path resolution belongs to startup/build authority. Catalogues receive the resolved directory; they do not encode install
paths into theme identity. Source/dev reads `<repo-root>/themes`; frozen/installed runtime reads only
`%ProgramData%\SRPSS\themes`, with Widget Themes under its `widgets/` child. The normal and Media Center installers own
seeding/clean-replacing that curated ProgramData tree, just as they do the shared visualizer preset tree. Do not merge
ProgramData and repository/onefile/app-local theme roots into one live catalogue or add a runtime bootstrap fallback.
ProgramData theme files are catalogue assets, not the persistence location for automatic Custom state; `Custom` belongs
to Settings persistence.

The retained Context Menu follows the selected Widget Theme palette plus the same resolved **effective** runtime material
because it lives in the Quick display scene; it never consumes the Settings QWidget theme/AccentPolicy backdrop directly.
Its palette is projected once per display generation (alongside its global Card-shadow snapshot), not read on menu-open or per frame. Default Dark's context roles deliberately reproduce the accepted retained QML pixels before semantic replacement; optional indicator/arrow roles may inherit when older/sparser themes omit them. Glass/Acrylic remain scene-local Quick materials, not Settings HWND effects.

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

## Tooling authority

Production runtime emits evidence; operator tooling consumes that evidence out of process unless a focused harness must explicitly construct a current owner. Production Python must not import `tools`/`scripts` analysis modules, and operator tooling must not restore deleted QWidget/GL/compositor/replay owners simply to preserve an old benchmark or parser. `tests/run_chunked.py` is the single test-profile authority; `tools/run_tests.py` is convenience delegation only.

Built-in PERF/usage/QML instrumentation is the primary destination performance evidence. Retain an external parser/harness only when it answers a bounded question that current instrumentation/tests cannot answer more directly. Resource counters never authorize weakening Visualizer cadence, newest-state freshness, R-69 authored response, Media event ownership or R-63 black-flash protection.

Current tool disposition and deletion routing live in `Docs/Tooling_Audit_2026-09-01.md`; production/tool boundary history is R-72.

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

Host owns item creation/retirement, display rect, family-authored root fade, independent generation startup gate and card style; not provider, persistence, SettingsManager, network or cadence. Family-local `fadeOpacity` is multiplied by `startupRevealOpacity`, so a lifecycle publication cannot bypass startup staging.

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

**Scene-local accessory lane:** an ordinary retained widget may reserve presentation width beside its card through `OverlayWidget.rightAccessoryExtent/rightAccessoryContent` without creating a second retained root or geometry/lifecycle owner. The card occupies `authoredRoot.width - rightAccessoryExtent`; the accessory remains in the same root, display route, startup/family fades and uniform CUSTOM transform. The ordinary display-level card shadow binds the card-only visual width, not the accessory lane. Media app-volume is the canonical first consumer. Accessory content may own its own hit target and visual shadow, but not a second provider/model/poller/service or independent monitor. If a future accessory needs independently movable CUSTOM geometry, that requires an explicit new child-geometry contract rather than silently promoting this lane.

### Startup composition

**Physical status 2026-09-01:** the attempted implementation below failed operator validation: the desktop -> first-wallpaper crossfade was not visible and the same Steam-family startup flashes remained. Treat this as the intended contract pending repair, not accepted behavior. The repair must preserve R-63 non-exact-cover/1 px overscan geometry throughout startup.

Cold application startup (runtime generation 0) is intended to have one ordered retained presentation contract:

```text
hidden selected QScreen
-> one pre-show desktop snapshot captured into PresentationImage staging state
-> same retained Quick window shows that snapshot
-> fixed retained 1300 ms Crossfade into first processed wallpaper
-> transition finalization publishes first-wallpaper authority/readiness
-> one existing 1800 ms QuickStartupRevealCoordinator scalar opens
   ordinary startupRevealOpacity + Visualizer startupRevealOpacity together
```

The desktop snapshot is never queue/history/current-image semantic truth and is released by first-image finalization. Desktop staging is application-session-only: later Settings/runtime replacement generations must skip desktop recapture/crossfade, while the independent startup gate may still protect replacement presentation from early family content. The startup gate is independent of family/Visualizer authored fades. Ordinary-host startup-gate state is retained and applied before every newly created root joins the scene; any explicit initial family fade value is also projected before parenting, so a late/Steam-style root cannot flash at either QML default. Immediately before the synchronized reveal begins the coordinator re-projects the closed gate and refreshes its target count, covering roots completed during the desktop crossfade. Visualizer startup-gate state is likewise retained by its scene owner. Desktop capture is opt-in at the manager boundary and enabled only by the cold engine generation. Startup adds no recurring timer/pacer, transparent-window opacity ramp, cover surface, second scene, or repaint loop. A desktop-capture failure is loud and uses the explicit no-seed first-image path; it never creates a hidden fallback presenter.

## Actions / images

```text
QML semantic action -> Python admission/action owner -> business side effect -> accepted state -> presentation
```

QML does not directly own URLs/backend calls, persistence, provider/cache policy or refresh cadence.

Media action ingress stays non-blocking, but worker submission is only admission.
The existing shared Media owner consumes the real GSMTC Boolean/exception result
and then reconciles accepted state; no presenter or second command owner may
infer success from queueing. Canonical Play/Pause/Toggle capabilities drive both
glyph admission and the exact provider method. Seek uses absolute 100 ns ticks.

Dynamic image precedent is process-engine `MediaArtworkImageProvider` over runtime-owned decoded `QImage` with stable
identity/bounded retention. No QPixmap worker transport, base64/tempfile churn or unchanged reupload.

Dynamic artwork presentation invariant: **every changing artwork surface fades**. Media, Achievement Pulse and
Abandonment Issues use the shared retained `ArtworkFadeImage.qml` fade-through primitive; future dynamic artwork must
reuse the same contract or an explicitly superior retained equivalent. Source changes never become visible as an instant
texture swap: old art fades to zero, the new source waits for `Image.Ready`, then fades in. Slice 8's shared gentle baseline is `200 ms` out / `340 ms` in (family lifecycle choreography may explicitly shorten a fade that is already fully hidden). These are bounded event-driven QML animations only while artwork changes; no recurring timer/poller/cadence owner is permitted for artwork fading. Media metadata follows the same ownership principle: provider/model Title/Artist/Album truth updates immediately, while `MediaMetadataColumn.qml` may retain only the outgoing rendered strings for one bounded presentation crossfade (`240 ms` out / `340 ms` in). Animation must never become data authority or delay fresh metadata.

## Shadow authority

Canonical includes direction, Card enabled/opacity/blur/extra offset, Text enabled/opacity/extra offset, and Header
enabled. No `widgets.shadows.offset`, Intense mode, Text Blur or `shadowtuning.json` replacement. Python resolves
direction to signed offsets before QML. Card/frame Extra Offset is directional one-sided geometry with zero Qt
effect translation; ordinary production card shadows are composed in one display-level underlay beneath every
ordinary card so a later sibling shadow cannot overpaint earlier widget content. The retained Context Menu consumes
the same global Card shadow direction/opacity/blur/Extra Offset contract at generation admission, but its shadow lives in
the menu overlay plane so it may cast over runtime content while remaining below the menu surface itself. Text shadows
remain retained duplicate glyphs with signed displacement, not MultiEffect blur. Clock analogue geometry is the permanent
explicit family exception.

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

The logical runtime step advances against controller-owned state, never a live QWidget. Audio analysis is one persistent serial `visualizer.audio_analysis` lane with one in-flight + newest pending source, retained detached DSP state across ordinary frames, explicit config/activation/reset epoch invalidation, and no generic Future/task fallback. Configuration ownership follows the
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
not a destination exception and must not be re-gated to hide a defect. Preserve focused BTF/reflow proof, including equal
renderer-content stream/drift head/trail travel for the same consume-once transient at canonical, wide and tall extents.
R-69 is binding: viewport adaptation must not add a second compressor to Bubble head radius, Ghost/history displacement, or another mode's authored musical response/freshness. Performance-motivated changes at this seam must pass `Docs/Guardrails/Performance_Optimization_Contract.md`; lower GC/FPS/CPU counters never override this contract.

Viewport configuration has two precedence levels, not two persistence owners: ordinary committed extent is runtime truth;
an active CUSTOM session may provide a temporary working override. Save promotes the new value into committed truth, Cancel
restores the old committed value, and ending CUSTOM removes only the override. Inactive CUSTOM does not imply canonical
`(420,280)`.

## Geometry / CUSTOM

`CustomLayoutSession` owns working geometry/state independent of QWidget. Geometry keys include display identity and
variant. Save/Cancel and layout slots preserve ordinary ON/OFF semantics without crossing capability activation.
Cross-display transfer has one live retained pixel owner and preserves logical runtime/model identity.

CUSTOM layout admission is global. As soon as any effective family route is `Custom`, or the live Edit Layout
transaction starts, generic authored stacking and the stronger ordinary Media/Visualizer adjacency owner are dormant
for the whole retained layout. Number-key layout-slot loads quiesce the same subsystem before their fenced runtime
rebuild. No CUSTOM family participates as a movable card *or* obstacle because the planner is not invoked at all in
that mode. An uncommitted Visualizer falls back to Media's plain authored anchor while dormant; adjacency is restored
only after returning to a globally non-CUSTOM generation/session. This switch is event-bound and must never gain a
recurring timer, polling loop, render callback, or worker.

Ordinary uniform CUSTOM scale is absolute against stable authored/preferred geometry with a shared 40% floor; re-entering CUSTOM must not compound shrink. Reddit/Reddit2, Media and Gmail use whole-card retained uniform scaling. Media's preferred width may include a scene-local accessory extent; that extent scales as part of the same authored root while the card keeps its own authored width, so external app volume does not become a second geometry owner. Gmail model width is already outer width; its row-derived preferred height alone receives shell inset. Visualizer is intentionally separate: `uniform_visual_scale` and `viewport_extent` remain independent intents.
