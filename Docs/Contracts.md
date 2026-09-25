# Contracts — Current Owner Map

`Current_Plan.md` owns work admission. This file owns fast current-owner routing.

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
| Settings theme semantics/backdrop contract | `Docs/Architecture/Settings_Theme_Architecture.md`; `SettingsThemeSpec` + Settings renderers + `core/windows/dwm_blur.py` |

`QQuickWidget`, selectable old-presenter fallback and a second accelerated runtime surface are prohibited.
The Qt Quick cutover is complete: deleted `DisplayWidget`/old-presenter paths are history, not compatibility architecture.
Do not preserve or recreate a presenter facade merely because a stale test/comment once referenced it.

## Winlogon URL handoff authority

Ordinary screensaver Reddit, FEEDS, Gmail and Steam link actions do **not** launch a browser or spawn a helper from the saver desktop, regardless of whether the saver holds a SYSTEM or user token or Windows reports `SESSIONNAME=Console`. `core/windows/secure_url_launcher.py` durably queues the accepted HTTP/S target in the existing ProgramData handoff and requests the canonical `SRPSS_RedditHelper` **interactive-only scheduled task** through `core/windows/reddit_helper_runtime.py`. **Successful queue admission owns handoff success and normal saver exit; helper heartbeat/task-wake confirmation must never gate teardown.** A missing/unwritable queue fails closed without falling through to Qt or `webbrowser` on Winlogon. MC/diagnostic and explicitly interactive Settings links retain their separate direct route. Gmail authorization requested from the saver routes to interactive Settings rather than starting OAuth on the saver desktop.

The existing user-desktop helper consumes only admitted queue work, waits for the session ticket to clear **and**, for `scr_click_` or Winlogon/Services URL entries with a known sender PID, for that saver process to exit before calling `os.startfile`. A present Explorer window is not evidence that the saver has exited. This is a finite defer in the existing helper queue loop, not an additional timer, per-widget launch owner, resident browser agent or a reason to restore retired task aliases/direct saver-child fallback. The shipped ProgramData helper executable must be rebuilt/deployed for changes in `helpers/reddit_helper_worker.py` to affect installed screensavers. The historical launch-authority record is `Docs/Historical_Bugs/R-02_Reddit_Helper_Link_Handoff.md`.

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

`themes/dark.qss` is physically deleted and is not a supported asset. Production Settings/tray code has no loader or
reference for it: permanent narrow renderers own the surviving structure and `SettingsThemeSpec` remains the visual
authority. The installed file-absent Windows/PySide acceptance matrix is complete. Do not restore a loader, duplicate
the old monolith into another file/string, alter native backdrop/forged-edge geometry, or weaken theme failure semantics.

Runtime Widget Themes are a separate semantic colour authority over retained Widget/runtime-overlay appearance. Theme identity and Settings-window backdrop material are deliberately separate:

```text
Widget Theme (.srwtheme schema v3)
    -> stable Widget theme identity
    -> explicit linked Settings-theme identity
    -> semantic runtime colours
```

Runtime cards are ordinary RGBA Quick surfaces. There is no Widget Theme material recommendation, Surface Style override, card-material Loader/capture path, or Settings-HWND backdrop reuse in the screensaver scene. Settings Glass/Acrylic remains owned exclusively by the Settings theme/native-window stack above.

### Settings collapsible-bucket contract

Canonical defaults enumerate collapsible bucket identities, but persistence does **not** store one boolean per bucket.
`ui.gmail_bucket_states`, `ui.widget_bucket_states`, `ui.visualizer_bucket_states` and
`ui.visualizer_tech_bucket_states` are sparse mappings whose missing members mean closed. Opening a bucket synchronously closes checked peers in the same local accordion scope
before revealing the new body; no timer, polling loop, animation owner or second persistence coordinator is permitted.

Scope follows actual layout ownership: ordinary Widget pages coordinate their peer buckets; nested Steam card buckets
coordinate with sibling Layout/Appearance/Content buckets without collapsing their parent card; Visualizer Custom
buckets coordinate per mode even when lazy construction places some buckets in Normal and others in Advanced. Stable
Visualizer Custom accessories use the same shared accordion contract. Technical's AGC/Transient leaf sections use the
same per-mode accordion rule. The outer Visualizer `Advanced` and `Technical` disclosures are **parents**, not leaf
buckets: they retain independent disclosure state so opening a child can never close the container required to reach it.
Canonical defaults remain the identity/schema registry, so unknown bucket keys stay fail-loud even though persisted maps
are sparse. Legacy full boolean maps normalize
to one open winner per local scope and are rewritten sparsely on the next bucket interaction, not during Settings startup.

**Lazy Settings-section lifetime:** family body retirement invalidates queued/coalesced UI callbacks admitted by the old
section generation and drops retained references to child QObjects before `deleteLater()`. Generic follow-up UI refreshes
must validate the underlying C++ QObject before dereference and prune stale wrappers. Never keep hidden bodies alive, pump
the event loop, add a retry timer, or special-case a family to avoid deleted-object failures.

**Widget Theme palette precedence:** Widget Theme colours are the ordinary shared baseline. Explicit surviving specialized `widgets.<family>.*` colour values remain higher-precedence only where a genuine family-level authoring contract still exists; they are not silently reclassified as theme state. Branded Header Fill/Text/Border are **not** such family contracts anymore: Media/Gmail/Reddit/Steam resolve them through shared `header.*` semantics, with Header Fill exposed once in `Widgets -> General -> Style Overrides`. The Context Menu has no family override layer and takes Widget Theme palette values directly. A surviving specialized family swatch edit therefore does not create Widget Theme `Custom`; editing a Widget-Theme-owned shared value does.

**Semantic visual-role contract (schema v3):** specialized decorative roles are sparse and inherit through one Qt-free resolver: intentional family override -> exact theme role -> shared semantic parent -> caller-supplied `local.*` current semantic value -> preserved current fallback. `local.*` tokens are runtime/presentation context only and must never serialize into `.srwtheme`, Custom or Settings. Default-valued compatibility fields act as implicit Inherit; only a genuinely changed *surviving specialized* family value is an explicit family override. Adding a role is therefore not permission to recolour Default Dark or to add a permanent visible Settings swatch. The ordinary shared authoring surface is `Widgets -> General -> Style Overrides`: Card Surface, Card Border and Header Fill edit Widget Theme state; Reset All Colours to Theme explicitly normalizes ordinary family colour/card-alpha compatibility overrides; Card Border Width is global geometry. Media Seek/Volume are examples of family controls that may remain because they are genuinely specialized. Do not recreate a Header Appearance palette or another Media/Steam/family-local theme cascade. Visualizer's specialised line/presentation system remains exempt from the generic decorative-stroke theme projection.

Manual editing of any Widget Theme-owned visual value has one separate deterministic contract: snapshot the complete
currently resolved named Widget Theme into user-owned `Custom`, apply the edit to that snapshot, select `Custom`, and turn
`Keep Synced` OFF. The installed/shipped `.srwtheme` remains immutable and all unedited resolved values survive the
transition. `Custom` is serialized in normal SRPSS Settings persistence rather than emitted as a `.srwtheme` file, so
ordinary customization never needs write access to `%ProgramData%\SRPSS\themes\widgets`. Exporting/saving a real Widget
Theme file is a separate explicit authoring operation. Do not create hidden per-property override inheritance. Re-enabling
Keep Synced may reselect the linked named Widget Theme but must not destroy the saved Custom snapshot.

`Keep Synced` defaults ON and links each Settings theme to an explicit mirrored Widget Theme; sync OFF permits
independent GUI/runtime theme combinations. Matching names may help author theme packs, but runtime links use stable
metadata/IDs rather than display-name heuristics. Widget catalogue display labels remove trailing Settings-only
`[Glass]` / `[Acrylic]` tags from Widget display names and Widget filenames while stable IDs and explicit Settings link IDs remain unchanged.

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

The retained Context Menu follows the selected Widget Theme palette because it lives in the Quick display scene; it never consumes the Settings QWidget theme/AccentPolicy backdrop directly. Its palette is projected once per display generation (alongside its global Card-shadow snapshot), not read on menu-open or per frame. Default Dark's context roles deliberately reproduce the accepted retained QML pixels before semantic replacement; optional indicator/arrow roles may inherit when sparser themes omit them.

## Production runtime chain

The production runtime connects exactly once:

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

## Retired presentation owners

The cutover sequence is history; current code is governed by present ownership and explicit cleanup horizons.

| Retired/superseded owner | Current rule |
| --- | --- |
| ordinary QWidget family pixels | retired; do not restore |
| shared old widget pixel helpers | remove when exact caller proof shows residue; never preserve for pixel compatibility |
| old transition/visualizer pixel owners | retired except for explicitly retained neutral logic/data contracts |
| old CUSTOM/edit/auxiliary pixel owners | retired; current Quick/session geometry owners are authoritative |
| old physical presenter/backend/software fallback | retired and absent; not rollback architecture |
| aliases/compatibility adapters | keep only while a named supported import/profile horizon requires them; horizon-gated per `Docs/Architecture/Persisted_Input_Compatibility.md` |

Historical code is not reference-protected merely because the product once needed it during cutover.

## Tooling authority

Production runtime emits evidence; operator tooling consumes that evidence out of process unless a focused harness must explicitly construct a current owner. Production Python must not import `tools`/`scripts` analysis modules, and operator tooling must not restore deleted QWidget/GL/compositor/replay owners simply to preserve an old benchmark or parser. `tests/run_chunked.py` is the single test-profile authority; no secondary test-runner facade is retained.

Built-in PERF/usage/QML instrumentation is the primary runtime performance evidence. Retain an external parser/harness only when it answers a bounded question that current instrumentation/tests cannot answer more directly. Resource counters never authorize weakening Visualizer cadence, newest-state freshness, R-69 authored response, Media event ownership or R-63 black-flash protection.

Current tool disposition and deletion routing live in `Docs/Reference/Harness_Index.md`; production/tool boundary history is R-72.

## Capability / ordinary enabled

Canonical family authority: `core/settings/widget_family_catalog.py` +
`core/settings/capability_activation.py`.

```text
family activated/deactivated != ordinary widget ON/OFF
```

CUSTOM X and layout-slot replay operate only on ordinary ON/OFF. They never activate a fully deactivated capability
or replace provider/account/source settings.

## Network transports

Every network request on the ThreadManager IO lane resolves its connection host through `core/network` before connecting: `bounded_request` (requests), `bounded_urlopen` (urllib), or `resolve_bounded` ahead of a raw socket client (Gmail IMAP). `socket.getaddrinfo` ignores socket timeouts and cannot be interrupted, so the lookup runs on a short-lived daemon thread with a 4 s deadline, at most eight in progress, cancelled by the family's own retirement fence (FEEDS job event, Reddit `shutdown_event`, Weather service/request fence, Gmail `should_cancel`, geocode pending query, wallpaper RSS shutdown check) and by the one-way process exit fence `close_network_admission()`, which the engine closes immediately before its thread-manager shutdown and `main` closes at process end. Steam requests are shared through request coordinators, so no single widget retirement cancels them; their deadline and the exit fence bound them. Redirects are followed one bounded hop at a time with the library's own semantics, a proxy's host is resolved when one applies, and a failed lookup surfaces as the library's own connection error. Without this, one stalled lookup pinned a worker of the four-worker lane, held the engine's 5 s exit wait and then kept the process alive (ThreadPoolExecutor workers are joined by the interpreter; the OS does not kill them). Direct-socket TLS (`bounded_urlopen`, the artwork transport's `http.client`, Gmail `imaplib`) uses the single verified process context `core.network.tls.verified_client_context()`. Without it, `imaplib` is unverified, and urllib builds a trust-store context per connection, which on Windows holds the GIL while it enumerates the certificate stores (R-98). `requests` keeps its library-owned context. Headless bars: `tests/test_network_bounded_http.py`, `tests/test_network_dns_stall_families.py`, `tests/test_feed_dns_stall.py`, `tests/test_network_tls_context.py`.

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
| Friend Pulse | runtime-generation shared FriendList/PlayerSummaries/cache/avatar owner + display leases | retained Grid/Rows model/QML |
| System Stats | runtime-generation shared low-priority CPU/Memory/Uptime/Network sampler + display leases | retained model/QML |

Presentation destruction does not automatically mean backend destruction; shared owners use real consumer cardinality.

**Scene-local accessory lane:** an ordinary retained widget may reserve presentation width beside its card through `OverlayWidget.rightAccessoryExtent/rightAccessoryContent` without creating a second retained root or geometry/lifecycle owner. The card occupies `authoredRoot.width - rightAccessoryExtent`; the accessory remains in the same root, display route and startup/family fades. Corner/wheel CUSTOM resize scales the whole root uniformly. A family-owned shared `content_extent` may reflow the card logical box without promoting the accessory into an independent widget; Media horizontal extent therefore leaves app-volume width unchanged, while vertical extent changes the common presentation height and the anchored volume-track length. The ordinary display-level card shadow binds the card-only visual width, not the accessory lane. Accessory content may own its own hit target and visual shadow, but not a second provider/model/poller/service or independent monitor. If a future accessory needs independently movable CUSTOM geometry, that requires an explicit new child-geometry contract rather than silently promoting this lane.

### Ordinary CUSTOM geometry / normalization

`ordinary_uniform` is the default new-family contract: one authored outer rectangle, one session-owned uniform transform,
shared 40% whole-card normalization floor and no family-local geometry persistence. Families with a proven presentation
benefit may opt into the shared `content_extent_axes` descriptor/session/owner path. Side handles then mutate one logical content axis at constant uniform scale; an optional selected-parent diagonal corner may mutate both admitted content axes through the same owner; **square** corners/wheel remain whole-card uniform. Family models/QML may reflow presentation
inside that box and may declare bounded logical direct-axis floors through shared policy, but may not create another
placement solver, timer/debounce, Settings-backed geometry value or payload owner.

Restore Size is shared edit infrastructure, not `restore_baseline()`: authored preferred geometry is retained separately
from effective/committed CUSTOM geometry before CUSTOM payload hydration. Restore clears content extent, keeps current
X/Y/display, stays in CUSTOM and bypasses stacking/ordinary auto-fit/shrink. Only an authored rectangle that physically
cannot fit the owning display may receive uniform emergency reduction. CUSTOM side reflow must never overwrite the
authored restore target.

**Edit-only controls and bounded three-action undo:** the existing shared `CustomLayoutSession` remains the sole working parent/child geometry and payload owner. The retained edit overlay owns only selected-frame transient, default-locked child-handle visibility. Plain `L` during Edit and the existing 22 px lock glyph invoke the same toggle. Locking cancels any held child gesture before hiding handles; neither control changes the parent edit controls, child paint, ordinary widget enabled state, Settings, or the saved layout. The child-role observer remains alive while the chrome is locked.

`Ctrl+Z` while Edit is active consumes one of **up to three completed Edit actions**, newest first, across all widgets in the shared Edit session. A drag counts once at release, not per pointer sample; an admitted wheel step, child flip, reset, or other discrete editor change counts once. Only state-changing completed actions enter the bounded history; the fourth-previous action is evicted. Each snapshot records values of the existing item, not a competing state model. Undo republishes through the shared session, never writes Settings, has no redo stack, and is disabled outside Edit and during an active pointer gesture. The entire history is cleared at Edit teardown. Plain `Z` retains its normal previous-image behaviour outside Edit. The lock toggle changes transient QML chrome only, so it is not an undoable geometry action. No extra polling, timer, per-frame work, persisted schema, or input owner is introduced.

**Grouped repeated-child paint and Edit parity:** A representative Edit target for repeated content must match the painted geometry that its semantic role promises. Friend Pulse's representative row/avatar/name targets follow the first actual painted instance. System Stats has a deliberately different user-visible unit: one entire metric stack (all enabled cards and their gaps), plus its header and top separator. Its single group target must enclose the union of every enabled painted panel, not only the first card; each real card consumes the same `metric_panels` normalized geometry. Metric label/detail/value/accent/track positions and header-driven left/right orientation remain authored within each painted panel and have no overlapping Edit handles. Disabled metrics do not create an Edit role or a phantom stack. This grouping avoids per-row/per-metric Edit or persistence owners. Other families may retain first-instance representatives where that is the actual semantic user interaction. Stable roles do not disappear solely because content is temporarily hidden; readiness gates selected chrome. Qt scene gates must independently map the real painted target and selected Edit proxy after resize, flip, geometry edits and Edit teardown. Avoid normal-runtime scene scans, polling and new publication paths.

**Live normalization without semantic-role churn:** A `customEditableChildRoles` array describes semantic identity and retained paint targets only. It must not read content-driven authored/preferred width or height, provider availability or any moving child property: a new role array retires QML Repeater delegates and can sever an in-progress pointer gesture. For a dimension that genuinely varies, put the retained family object in `normalizationTarget` and read its bindable `childNormalizationWidth`/`childNormalizationHeight` on the selected Edit delegate. If a role deliberately uses a different axis baseline (Media's external volume), name the existing family-owned property via `normalizationWidthProperty`; never add a second offset or outer-layout authority. Clock's face-specific roles use its existing `preferredContentWidth`/`preferredContentHeight` through explicit read-property names, without subscribing the role list to changing text dimensions. Dense authored-baseline families (Friend Pulse, Achievement Pulse and Abandonment Issues) similarly use their existing `baseAuthoredWidth`/`baseAuthoredHeight` through named properties; Weather and System Stats expose their existing `childNormalizationWidth`/`childNormalizationHeight`. All of these values are read only on retained selected Edit delegates, never by the descriptor array. A Weather location/icon hide or a Steam roster/content change can temporarily disable a painted target but must not remove the semantic role itself. Existing explicit numeric normalization still works for static/test descriptors. Read fallback preferred extent only when there is no live family baseline. No normal-render listener, timer, model JSON stringify, scene scan, additional Settings write or sub-widget persistence is admitted. Retained Qt tests must check numeric normalization, *same delegate identity*, exact painted-target bounds and zero non-bindable/binding-loop warnings while live baselines change repeatedly.

**Selected Edit painted-target geometry and semantic role identity:** A declared child role is a stable semantic identity even if its actual target has not yet loaded, becomes hidden, or switches among explicitly paired paint targets. Declare static roles unconditionally; resolve dynamic Repeater rows and alternate paint items only inside the retained selected Edit delegate. Readiness determines visible/editable chrome, not whether a role exists. Selected Edit bounds are derived from actual four-corner QQuickItem mapping through inherited item and QML transforms, ancestor clipping and visibility. QQuickItem.transform is a non-bindable list: never enumerate it in an active mapping binding. Instead, any family using QML Scale/Translate/Rotation on an Edit target or its ancestors declares a cheap bindable `customEditMappingDependency` on the transformed QQuickItem, derived from the **applied transform object properties** (such as a named `Translate.x/y` or `Scale.xScale/yScale`), not merely their input/model values. Source inputs can notify before the QML transform has updated, otherwise leaving Edit paint projection one change behind. The shared selected-Edit mapper observes that marker on the retained ancestor chain and continues to project the actual paint with `mapToItem()`. Clock's digital text and footer roles and its analogue face/footer roles use that same contract on their own applied transforms. The analogue face role keeps its centred transparent carrier, including its applied Scale origin, while actual face paint and mode-specific roles remain family-owned. Clock digital text remains unwrapped and uses a derived, uniform paint-only fit of its natural content stack when the existing owner supplies a compact X/Y outer rect; the intrinsic authored layout keeps scale 1 at or above natural size, so a narrow text item must never mask overwide ink or desynchronize its selected Edit proxy. This fit changes neither the persisted font-size/variant payload nor the analogue centre-owned face. The selected-Edit loader is the only observer of these signatures; the Clock ticker does not acquire an Edit subscriber. Inherited ordinary x/y/size/scale/rotation/visibility/clip remain observed directly; do not substitute a status label for a missing saved-role target. Intentionally transparent geometry carriers that represent separately painted content remain legal and must not be rejected solely by opacity. Family QML owns normal paint/reflow and independent child X/Y rails; the existing session owns edits, Undo, slots and Save. No second layout owner, generic scene scans, per-frame observer, polling, or per-pointer Settings writes.

**Ordinary child containment and two-axis reflow:** Parent CUSTOM size/extent is
controlled by the outer resize controls only; moving/resizing a child never
grows the parent. The shared Edit admission clamps its actual occupied painted
bounds to the legal card or separately declared accessory surface regardless of
sibling-collision setting. Saved child X/Y are independent deltas from live
family rails: customizing one axis cannot suppress the other's parent reflow.
Flipped layouts retain the same compact-height, Save/reopen and Edit geometry
contracts and may not alter text/image pixels or hide essential active-track
controls. Authored size is a Restore target, not child-growth permission.

**Dense Steam parent-growth negative control:** Achievement Pulse and Abandonment Issues intentionally expose `customEditableChildRequirementTarget: null`; their retired `customChildRequirement` QML object must not be restored to satisfy older tests. A user-authored parent `content_extent` may reposition an *unedited* child on its live right rail, but that movement does not create another outer-size request or alter `baseAuthoredWidth/Height`. Native regression tests must measure the current model's committed outer extent, actual painted child coordinates, and their stability across repeated event-loop settlement; inspecting a nonexistent child-requirement property is not a valid oracle. Test-owned QQuickItems attached to retained presentation hosts must be detached before host retirement or allowed to die with the host, never dereferenced after the parent is destroyed.

**Retained refresh and inner-shadow parity:** A widget with an explicit refresh control (Games You Follow, Reddit/Reddit2, Gmail, or FEEDS Custom 1) uses the existing bounded glyph target as its whole pointer/tap hitbox, semantic colour for its resting family identity, and a restrained bright-white active-hover cue plus pointing-hand cursor only while refresh is admitted and CUSTOM input is not capturing gestures. A family may use its existing outline or a small neutral-white surface wash; the affordance must not paint through adjacent text. This paint treatment may not alter the control's authored width/height, font size, header position, Edit target or network refresh ownership. Widgets with only a double-click-to-refresh gesture do not gain a new glyph. Ordinary card/header shadow ownership remains global. Small inner image/row/avatar contact shadows follow signed card-shadow offsets and enablement without new blurred image layers, shader passes, schedulers, or independent shadow settings; `ShadowedText` remains the signed text-shadow owner. A contact shadow is a subdued offset silhouette, not a second blurred card shadow.

**Clickable-affordance parity:** Single-click surfaces advertise the same interaction fact without replacing resting family semantics. Resting borders/separators keep their semantic theme colour at its authored opacity; an active clickable border, separator or emphasized text becomes **bright white** on hover so one widget family does not use accent-colour hover while another uses white. Text-dense Reddit, Gmail and FEEDS List rows use a restrained inset neutral foreground surface wash plus pointing-hand cursor and deliberately have **no row hover stroke**, because a compact row border can cross timestamp/title rails and read as content decoration; Reddit/Gmail separators and primary text brighten white instead. Grid/story/card surfaces may use their boundary outline, with FEEDS retaining full semantic colour at rest and white on hover. Friend Pulse exposes the same white hover cue on the exact clickable avatar/name or game text instead of pretending the whole row is one action. Achievement Pulse and Abandonment Issues artwork use the same full white hover outline while their resting artwork borders remain semantic. Control-strip gestures, especially Media seek, previous/play-pause/next, mute and volume, advertise clickability with pointer/opacity/scale/surface feedback only: do **not** add hover borders around seek or transport controls. All hover affordance is paint/input-event driven only and may not schedule source/cache/network work, publish geometry, create a timer/poll/thread, or acquire another interaction owner.

**Rounded artwork frames:** Qt Quick `clip` is rectangular and ignores `radius`, so a rounded artwork/avatar frame never relies on it. The image is inset by the frame's outline stroke on a concentric `MultiEffect` mask (frame radius minus the inset) and the outline paints on top, so neither the image nor a thicker hover stroke can escape the frame or cover its outline (Achievement Pulse, Abandonment Issues, Media, Friend Pulse avatars, Games You Follow story/inline art, FEEDS art). `tests/test_qtquick_artwork_frame_containment.py` renders each and measures image pixels against the ideal rounded frame.

**Widget line weight (not Visualizer):** every inner border, rule and separator goes through `OverlayWidget`'s scale-aware stroke helpers. An authored line under 2 px gains +0.5 px (0.5 px and finer) rising linearly to +1.5 px just under 2 px; 2 px and heavier keep their weight. Enlarging the card adds up to +2.5 px more (headers 1.25x that); shrinking never goes below the boosted baseline or 1 px. A child CUSTOM enlarges by geometry uses `scaleAwareChildStrokeWidth` with min(width scale, height scale). The outer card border (Card Border Width) and user-set Clock separator thickness scale directly, and icon glyph strokes scale with their icon.

**Family-local live rails:** Friend Pulse's unedited separator follows its existing live `authoredWidth`/content extent, while an explicitly edited `width_scale` multiplies that live span. The separator's own geometry cannot demand parent growth. Flipped Reddit reads `post title | age value (e.g. 01HR) | AGO`, with a compact title/time gap and no mirrored text or independently persisted post-row geometry. These are projections of existing family and normalized child values, not new ownership systems.

### Last-good cache / freshness

For durable provider caches, freshness controls refresh admission and cached/stale labeling only. A coherent successful
cache record remains usable indefinitely and is the preferred fallback after network/private/rate-limit/provider failure.
Failed, malformed or stale-generation responses never overwrite/freshen last-good evidence. Deletion requires explicit
user/account/cache reset, schema rejection/corruption, or a proven identity change. Do not substitute semantically
different data simply because the intended source is stale; Games You Follow must not replace stale follows
with owned/recent/wishlist games.

### User-requested cache maintenance

Widgets → General → Cache Maintenance deletes disk content from explicit, inspectable family targets, not currently retained presentation/model snapshots. The normal profile Steam target is the entire account-scoped `steam/cache/` subtree (including Games You Follow article/name metadata, general assets and `assets/news_inline`), **excluding user-authored Friend Pulse pin state** (`friend_pulse_pins.json` and its pending atomic write) even though that state lives inside the cache subtree. Steam credentials and credential metadata reside outside the cache target. RSS image files, repository-local Reddit post snapshots, FEEDS last-good snapshots, Weather provider/last-visible responses and Gmail message cache each have separate, narrow targets; settings, credentials, Reddit startup-gate markers and user-authored configuration are not part of those targets. The Settings control shows the resolved disk targets and reports *no matching files at those locations* instead of claiming visible/runtime caches are empty. A running owner can retain its data and write new cache files after a disk clear; stop the screensaver before requesting a durable disk reset, then restart the widgets. Do not add a second cache owner, synchronous widget-wide invalidation or provider rescan merely to make content disappear immediately on a still-live display.

### Startup composition

**Physical status:** accepted in the current Quick runtime. The desktop -> first-wallpaper crossfade and coordinated Visualizer/widget startup reveal were physically validated after the startup-fade correction; later Settings/runtime replacement generations deliberately skip desktop recapture while retaining the independent startup gate. Preserve R-63 non-exact-cover/1 px overscan geometry throughout startup.

Cold application startup (runtime generation 0) has one ordered retained presentation contract:

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

**Multi-display reveal ownership.** A display is reveal-ready once its own first authored wallpaper has finished presenting and its Quick readiness is `ready_for_reveal`. The shared reveal waits for every selected display whose readiness has not failed. If at least one display is ready and another is not, one generation-fenced 6 s one-shot bounds the wait, loudly (`[STARTUP_REVEAL][FALLBACK]`). The shared 1800 ms fade drives only the displays that were ready when it started, which is all of them on an ordinary startup. A display outside that cohort, stalled or failed, keeps its widget and Visualizer gates at 0. When it becomes ready on its own it gets its own one-shot 1800 ms reveal from the same coordinator type, scoped to its gate. That reveal does not restart the shared fade or publish a second `startup_reveal_completed`, which belongs to the shared cohort. Late reveals retire with their generation; there is no poll or recurring timer. Bars: `tests/test_startup_reveal_stalled_display.py`.

### Runtime replacement and monitor topology

Settings, CUSTOM Edit and monitor-topology replacements share one construction path: `engine_handlers._construct_and_start_replacement_runtime`. Its all-thread stack-dump window (`hang_watchdog`, label `replacement_to_reveal:<event>:generation=<n>`, 20 s) stays armed until the generation's coordinated reveal completes. It is closed by that reveal, by generation retirement, by construction failure, when the queue has no image, or when the first-image retry is exhausted. A stale edge cannot close a newer window, because disarm checks the label.

A replacement generation has exactly one first-image admission owner. A monitor-topology rebuild replays the current image through the ordinary image-change owner, and `start(show_first_image=False)` schedules no parallel startup retry. Only a rejected replay hands the first image to the bounded startup retry, and it says so loudly (`[DISPLAY][FALLBACK]`). A work-area-only change (taskbar or app-bar) is not a topology change: the monitor signature excludes `availableGeometry`, and each window re-applies its bound screen geometry on that edge. Adding a monitor still rebuilds the whole generation, because screen indices shift and routing, Visualizer ownership and CUSTOM layout are generation-wide (R-96). Every application quit is queued through `engine.runtime_destruction.request_application_quit(reason)` (Guardrails § Lifecycle). Bars: `tests/test_monitor_replay_admission.py`, `tests/test_replacement_hang_window.py`, `tests/test_qtquick_monitor_wake_reconcile.py`, `tests/test_quit_request_render_thread_gil.py`.

### Current feature admission and selected-Edit churn boundary

- The implemented, independently enabled `system_audio_osd` (on by canonical default) consumes the shared GUI-apartment Core Audio source, not another endpoint, poll or Qt window. Media and OSD retain independent display admission; endpoint lifetime follows the combined live consumer count. One event-owned hide deadline/fade belongs to each active OSD presentation. See `Docs/Reference/System_Volume_OSD.md`.
- The implemented default-off Games You Follow family retains the `steam_progress` identity. Only linked-account `GetGamesFollowed/v1` supplies membership; bounded per-game news is ranked newest-first from validated discovered results and kept in a profile-private last-good per-app cache. Initial complete coverage persists; ordinary maintenance advances a saved cursor by at most eight apps per session instead of redoing the full sweep. One generation-shared source/deadline serves displays, with a retained Qt model and stable grouped CUSTOM roles. A separate profile-private AppID metadata cache resolves followed-but-not-owned game names once from local caches or bounded worker-only Store lookups, preserving verified names indefinitely; each article inherits the associated game name independently of its headline. Missing or corrupt art must not suppress other valid art; one retained source admission projects valid local images and the Quick card uses a uniform image rail/placeholder for mixed availability. News-body Steam Clan image macros are parsed as up to three optional article thumbnails, with all recognized image-path tokens stripped from preview text, locally warmed in the existing source worker and projected only as local images. The private article action retains the validated Steam-supplied URL independently of the news GID; it never synthesizes a Store `/view/<GID>` route. App-bound Store/Community articles and Steam-owned source-supplied `/news/externalpost/<feed>/<GID>` redirects for syndicated news are admitted through narrow host/path/identity checks, not by accepting arbitrary publisher links. For a missing or unsupported article URL, the same accepted story remains clickable via its safe, explicitly app-bound Steam news index; neither the UI nor the backend invents a `/view/<GID>` article URL. The final action boundary revalidates the selected route. Steam managed asset and news-thumbnail caches have distinct per-profile count/byte budgets enforced on successful writes; no global app-wide cache ceiling is established. See `Docs/Reference/Steam_Games_You_Follow.md`.
- The FEEDS family uses four fixed CUSTOM identities with only `feeds_custom_1` currently admitted. Custom 1 uses the shared `BrandedHeader` and established semantic header palette; publisher metadata is a separate small per-slot optional subtitle below the pill. Header alignment is the one widget-wide semantic orientation intent, so header/corner, refresh rail, Grid order, List artwork/text/age rails and overflow alignment mirror together without mirroring image pixels. Its configured-name monogram is rasterized once per semantic config through a cached antialiased QPainter wireframe/segment renderer and supplied to QML as an immutable local data URI; there is no emoji/font-glyph, Canvas repaint, timer or file-cache owner. Feed documents are fetched through explicit timeout/byte/redirect limits (a website address resolves to its verified feed by bounded standards-based discovery, never per-site rules, stored beside the endpoint's last-good state), normalized from RSS/Atom/JSON Feed/JF2/h-feed documents into one model, and stored as atomic versioned last-good snapshots with persisted failure backoff. Image absence never invalidates an item. CUSTOM acquisition identity is the endpoint fingerprint, so identical active endpoints share one cache/source/cadence while each card keeps independent presentation; changing endpoints cannot display the prior endpoint's cache. One generation-scoped Feed family owner owns earliest-due scheduling, active leases and source-specific cancellation; cache-only admission does not construct network transport until refresh is actually due. Optional artwork is one event-admitted, bounded local-cache batch on that existing source lane, not a second cadence. Feed-contained media candidates are deduplicated across stories by canonical URL identity and normalized image content before presentation; List and Grid admit local artwork per stable story identity while an image-less story uses its authored text-only row/card, and Compact remains text-only. Retained QML owns no timer, network or remote image source. Max Items is a ceiling and presentation paints only complete rows/cells that fit. Custom 1 participates in the shared independent X/Y `content_extent` Edit contract and the shared stable CUSTOM-child geometry contract (`header`, `refresh`, `articles` group, repeated `artwork`, `overflow`); volatile article IDs are never child persistence keys. The one `artwork` role supplies common freeform geometry to repeated List/Grid image paint and its Edit proxy targets the first actually admitted local image, avoiding per-story persistence churn. Hover/reflow/child editing perform no feed/image I/O. `--feeds` owns focused diagnostic INFO/DEBUG in `screensaver_feeds.log`. Custom 2–4 and NEWS remain unadmitted until their later gates; see `Docs/Reference/Feeds.md` and `Docs/Future_Work/Feeds.md`.
- A selected child role is stable identity, not an array of changing normalization/visibility facts. Its selected-only delegate observes named live family normalization and applied QML transform dependencies; it compares **actual clipped paint** to Edit bounds without non-bindable transform-list reads. Child snap guides are retained per axis. Parent extent cannot be republished by child occupancy. See the authoring guide and historical R-88 for failure modes and test-oracle cautions.

## Actions / images

Widget interaction glow: `InputSettings` -> `DisplayManager._configure_quick_auxiliary` resolves the shared optional
colour through `ui.widget_glow_style` (`card.border` inheritance) plus the canonical 0-100% intensity scalar -> existing
Quick input snapshot/scene-generation gate -> ordinary host -> `OverlayWidget`/`WidgetInteractionGlow`. The input owner
observes discrete presses without intercepting family actions; the host turns each admitted press into one last-clicked
ordinary-card boolean target (or clears it on empty space), while the shell observes hover edges. Hover/click fade toward
their state on entry/selection and remain settled until that state changes, at which point they fade gently out.
`cardShellEnabled` is the common eligibility gate: shell-less ordinary widgets and frameless Visualizer modes are not
hover/click glow targets and cannot emit Jedi Mode through this interaction feature; removing a shell clears click state.
One lazy shader and finite edge-triggered animations own pixels only; no recurring cadence exists.

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
Abandonment Issues use the shared retained `ArtworkFadeImage.qml` two-buffer primitive; both buffers are hard-clipped to
the caller-assigned artwork rectangle, while each family owns its rounded mask and keeps the image inset beneath the
scale-aware border so enlarged artwork cannot bleed past rough frame edges. Future dynamic artwork must reuse the same
contract or an explicitly superior retained equivalent. On replacement, the currently displayed texture remains visible
until the incoming `Image` reports `Ready`; the incoming buffer then fades over it for the shared **520 ms `InOutSine`**
baseline and the old texture is released only after coverage is complete. An explicit empty source fades the displayed
texture out over **280 ms**. The inactive buffer's source is cleared at idle, so the contract does not retain a second
artwork texture indefinitely. These are bounded event-driven QML animations only while artwork changes; no recurring
timer/poller/cadence owner is permitted. Media metadata follows the same ownership principle: provider/model
Title/Artist/Album truth updates immediately, while `MediaMetadataColumn.qml` may retain only outgoing rendered strings
for one bounded presentation crossfade. Animation must never become data authority, alter alignment/layout authority or
delay fresh metadata.

### Wallpaper image cache and prefetch

The decoded image cache (`utils/image_cache.py`, bounded by `cache.max_items`/`cache.max_memory_mb`) holds speculative lookahead only:
- a raw decode stays until its display-ready derivative exists;
- a derivative stays until a display consumes it.

Once a display captures a derivative into its `PresentationImage`, the presentation owns the pixels and the derivative leaves the cache. ImageWorker results are not cached. Exact reuse happens per batch (`processed_by_transform`), never through the cache. A consumed derivative left at the LRU's recent end displaced the nearer lookahead and doubled the decode/scale work (R-99). The parked transition render node keeps its warm GL programs but no run or frame references. Numpy's OpenBLAS runs one thread in every process (`core/native_threads.py`, R-99).

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

The expanded transition catalog and Slide Perspective Push are described in `Docs/Reference/Transitions.md`. Shared mesh primitives are lazy, context-local and clock-free; per-effect geometry/material/state remain local. The new effects do not change Sphere, Bubble, Visualizer cadence or the single-surface presentation contract.

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

All six current modes must support viewport extent and the core capability policy is now all-six-mode capable. Bubble is
not an exception and must not be re-gated to hide a defect. Preserve focused BTF/reflow proof, including equal
renderer-content stream/drift head/trail travel for the same consume-once transient at canonical, wide and tall extents.
Bubble presentation now uses `sqrt(content_width * content_height / 1.5)` as its response-height reference,
following the operator rejection of height-only aspect coupling. The full logical radius waveform remains
unchanged; same-area reshaping preserves pixel response and large views continue to grow.
Sine/Oscilloscope Gaussian halo distance is measured normal to the curve in logical pixels; its width follows
the visible content area's square-root scale against 420x280. DPR and whole-widget scaling remain physical
projection concerns. Authored-world encoding must not compress the halo; line-core AA and musical amplitude
remain separate contracts.
R-69 remains binding for optimization: viewport adaptation must not add a second compressor to Bubble head radius, Ghost/history displacement, or another mode's authored musical response/freshness. Performance-motivated changes at this seam must pass `Docs/Guardrails/Performance_Optimization_Contract.md`; lower GC/FPS/CPU counters never override this contract.

Viewport configuration has two precedence levels, not two persistence owners: ordinary committed extent is runtime truth;
an active CUSTOM session may provide a temporary working override. Save promotes the new value into committed truth, Cancel
restores the old committed value, and ending CUSTOM removes only the override. Inactive CUSTOM does not imply canonical
`(420,280)`.

Sphere is an opt-in descriptor with FRAMELESS + VIEWPORT_RECT policy. Its compact configure-owned parameters and
activation-relative time share the existing visualizer clock; only current playing source energy/transients drive
deformation, size pulse and reactive bump. A static body mesh uses aspect-correct perspective and material-local
bump/lighting; Magma/Water may lazily allocate bounded static effect geometry. Renderer resources belong to
their Quick window/context and retire through one-shot render events on admission changes, independently of whether
the replacement mode obtains a frame. Sync and pointer movement create no cleanup polling or repeated frame requests.

## Geometry / CUSTOM

Non-CUSTOM stacking first attempts full authored sizes, then bounded whole-card
shrink/re-stack trials down to the shared 40% whole-card floor only when placement remains unresolved.
The bounded search samples 5% bands and refines the first fitting band in 1% steps;
it proves accepted fits without claiming exhaustive or globally optimal packing. Each
accepted scale carries its freshly solved placement and 10px clearance; growth
restores authored size as space returns. Clock and fixed Media/Visualizer obstacles
are excluded from shrink. No-fit remains an explicit overfull diagnostic. Global
CUSTOM disables this derived planner; first Edit preserves the visible footprint.


`CustomLayoutSession` owns working geometry/state independent of QWidget. Geometry keys include display identity and
variant. Save/Cancel and layout slots preserve ordinary ON/OFF semantics without crossing capability activation. Clock
keeps behavior and geometry separate: `display_mode` plus per-display `display_mode_overrides` are visible Clock state,
while digital/analogue rects remain variant geometry. A numbered slot must round-trip both layers and restore mode state
before the fenced rebuild; an empty saved override map clears later overrides rather than inheriting them. Legacy slots that
never recorded overrides replay their saved shared baseline. Cross-display transfer has one live retained pixel owner and
preserves logical runtime/model identity.
Healthy Edit Save transfers ordinary family/binding/service retirement records to that target without
reconstruction, reinjection or provider restart. Clock variant/action context follows the receiving display owner.
A geometry display crossing alone never requires generation replacement; slot-load and proven-corruption
repair boundaries remain explicit.

CUSTOM layout admission is global. As soon as any effective family route is `Custom`, or the live Edit Layout
transaction starts, generic authored stacking and the stronger ordinary Media/Visualizer adjacency owner are dormant
for the whole retained layout. Number-key layout-slot loads quiesce the same subsystem before their fenced runtime
rebuild. No CUSTOM family participates as a movable card *or* obstacle because the planner is not invoked at all in
that mode. Live Edit captures existing visible rectangles without resetting their stacked/adjacent positions.
A newly constructed uncommitted Visualizer uses Media's plain authored anchor; adjacency is restored
only after returning to a globally non-CUSTOM generation/session. This switch is event-bound and must never gain a
recurring timer, polling loop, render callback, or worker.

CUSTOM wheel resize remains free uniform scaling: it may publish the same nearby peer-alignment guides as drag resize, but it must never apply the guide resolver's suggested snap scale. Authored peer/centre/safe-gutter guide strokes are one pixel thicker than their former baseline; the generic edit grid remains 1 px.

The selected child editor retains one vertical and one horizontal snap-guide QQuickItem for the active parent. Pointer samples update their bindable position, semantic style and visible state only when the values change; they never rebuild an array-model Repeater or a new guide delegate. Guide hiding preserves the last coordinate but not visibility, so a new gesture paints its new coordinate before reveal. Both guides are transient Edit-only chrome: the ordinary render path, geometry/persistence owner and snap/collision decision logic are unchanged. The outer peer/centre guide channel is separate and keeps its existing per-value publication guard.

Ordinary uniform CUSTOM scale is absolute against stable authored/preferred geometry with a shared 40% floor; re-entering CUSTOM must not compound shrink. New ordinary cards default to the `ordinary_uniform` descriptor mode and whole-card scaling remains the stable outer transform even for families that additionally opt into shared side-axis `content_extent`. Every current resizable ordinary non-Clock family now uses admitted content-extent reflow: Weather, Media, Reddit/Reddit2, Gmail, Achievement Pulse, Abandonment Issues, Friend Pulse, System Stats and FEEDS Custom 1. Dense authored families may resolve their side-axis logical floor against the live authored reference once at edit admission so working/persisted geometry cannot become smaller than the canvas QML actually renders. Clock alone retains variant-aware per-value sizing. Older current-format per-value payloads are inert for normalized families, and genuine product Settings remain authoritative. Media's preferred width may include a scene-local accessory extent; that extent scales as part of the same authored root while horizontal content extent reflows only the card lane, so external app volume does not become a second geometry owner. Gmail model width is already outer width; its row-derived preferred height alone receives shell inset. Weather may reveal its retained five-day forecast only when a CUSTOM vertical content extent has enough room for the compact card plus the extra section; the provider supplies those rows through the existing request/cadence rather than a second fetch owner. Visualizer is intentionally separate: `uniform_visual_scale` and `viewport_extent` remain independent intents.


### Edit-mode hit targeting and semantic timestamp rails (2026-09-19)

The shared edit parent MouseArea covers its entire parent footprint; only explicit higher-z chrome owns a restricted hit target. An entire top-strip exclusion is not a close-button collision solution. The child-alignment flip glyph may have a larger invisible event target than its painted disc, but both must route through the same child flip method, above the child move/resize target, without introducing a second alignment or geometry authority. Locked child handles must not disable selection of their parent.

Reddit/Reddit2 flipped rows use a single bounded trailing age rail, with title before age value before AGO and explicit compact gaps; title text elides before reaching that rail. Timestamp X must not depend on a headline's intrinsic width. Real QQuickWindow pointer-delivery and real retained-item geometry tests are required to assert these behaviours; green source-string checks alone cannot establish them.

### CUSTOM semantic repeated-list columns

The existing CUSTOM layout `size_payload` may contain one `column_rails` list
for Reddit/Reddit2 (`age`, `ago`, `title`) or Gmail (`timestamp`, `sender`,
`subject`). It is accepted only as an exact three-item permutation of that
family's stable IDs. Missing/invalid data falls back to the normal header-flip
order; it cannot mutate saved user content during hydration. One release in
selected/unlocked Edit commits a whole-list swap as one Undo action. The model emits a dedicated column-order change event so an unrelated child
geometry sample never rebinds every repeated-row column. Retained
per-row items use the same order, preserve their identity, and never become
independent position owners. Normal render has no edit-rail descriptor scan.
