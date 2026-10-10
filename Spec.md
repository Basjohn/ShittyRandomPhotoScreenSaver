# SRPSS Specification

Canonical durable architecture and product-behavior contracts. `Current_Plan.md` owns sequence; durable regression/failed-method history belongs under `Docs/Historical_Bugs/`, while ordinary chronology belongs in source control.

Recurring service timer handles are terminal on stop: the owning handle stops and
defers Qt destruction, which releases callbacks and passive resource registration.
Gmail's retained family adapter carries the display generation into its shared
runtime lease, including generation 0; final lease retirement removes the shared
owner without shutting down the process-wide backend.

## Product priorities

1. visualizer fidelity/reactivity;
2. lifecycle/resource safety;
3. frame pacing/perceived continuity;
4. multi-display correctness;
5. bounded resources;
6. CPU/task efficiency;
7. average FPS;
8. elegance.

Do not improve counters by reducing authored cadence, visual quality, overlay behavior or topology support.

## Accepted runtime presentation

```text
Python / QWidget application shell
-> Settings / persistence / providers / media / orchestration
-> logical runtimes + models
-> bounded presentation state
-> one standalone threaded QQuickWindow per selected physical display
-> one retained Quick scene + inline QSGRenderNode custom GL
```

Hard: one accelerated runtime surface per selected display; standalone `QQuickWindow`, never `QQuickWidget`; threaded
Quick scene graph; Settings may remain QWidget; business/runtime ownership remains Python; transition+visualizer GL
remains inline in the one Quick scene; no permanent old/software presenter fallback.

The dependency floor is PySide6/Qt 6.11.2. Production requests OpenGL 4.6 Core and uses GLSL 460 core;
OpenGL is the sole production graphics API. The existing render-context initialization boundary records actual
GL/GLSL, vendor, renderer and required capabilities, and rejects unsupported contexts. Validation is scoped to
context lifetime, with no steady-frame driver queries. The accepted swap interval remains zero.
Maintained render/capture diagnostics reuse `rendering.quick.bootstrap`; owned offscreen shader contexts request
and validate the same floor.

Wallpaper lookahead uses bounded source batches in the supervised speculative image worker. The parent caches only
display-ready derivatives; requested images retain their separate foreground worker and authored quality settings.
The construction, generation and shared-memory ownership contract lives in `Docs/Contracts.md` → Wallpaper image cache and prefetch.
Display quality uses the canonical `display.resample_filter` choice (Smooth, Hamming or Lanczos) with independent
downscale sharpening. Every choice supports bounded lookahead with foreground-identical pixels. Processing,
one-way migration and quality/cost measurements live in `Docs/Reference/Image_Quality.md`.

## Build control and products

**Build execution owner:** Agents may edit/review build source and inspect reports, but **must not run any Nuitka, Build Runner, helper, installer or other frozen product build**. These are time-consuming **operator-executed gates**; the operator supplies logs, reports and physical acceptance. Do not auto-request a full four-chunk test suite alongside source corrections. `Docs/Guides/Python314_Cutover.md` owns current interpreter/toolchain details.


`tools/build_runner.py` owns sequential build execution. One active process owner places the Windows build root
in a kill-on-close Job Object before resuming it; Emergency Stop and runner shutdown cancel that tree and prevent
queued jobs from starting. Operator abort is distinct from compiler failure. A new run creates a fresh owner.
The Standard job compiles once and publishes the same binary twice: `release/screensaver/SRPSS.scr` and
`release/diagnostic/SRPSS_Diagnostic.scr` (checked byte-for-byte against the compiled binary). The published file's
name selects the diagnostic flavour at startup (`core/build_profile.py`: exactly `SRPSS_Diagnostic`, read from the
launched binary's long path), so there is no Diagnostic job or second compile (operator direction, 2026-10-10).
Builds compile without a console; the diagnostic flavour opens a terminal only with `--debug`, so installing it from
Explorer or running a soak never pops one. Only Standard and Media Center have installers. Build concurrency remains script-owned. Operator builds and installed acceptance do not block source work.
The canonical runtime dependency probe reads the four exact Qt pins from `requirements.txt` and checks both
distribution metadata and loaded PySide/Qt/shiboken versions before compilation, in Normal and Venv modes.
Build Runner owns the QRC prerequisite before any selected runtime-product jobs. It delegates deterministic
generation to `tools/regen_qrc.py` using the selected mode's interpreter; resource child processes share its existing
cancellation owner. Direct build scripts invoke the same prerequisite. A generation failure prevents compilation;
unchanged resources do not recompile for each job. Before any expensive PowerShell product compilation, Build Foundry
and the direct worker both clear that job's canonical `release/<product>` directory. A locked old artifact therefore
fails before compilation rather than after a full Nuitka run, and publication retains one bounded four-attempt retry for
a transient Windows handle race. Every Standard and Media Center runtime build also
writes a persistent Nuitka compilation report and a compact footprint JSON into `logs/`: artifact/published bytes,
file count, largest payload files/top-level buckets, and QRC source-vs-generated-module reference sizes. These reports
describe the current build only and exist to identify real package/dependency bloat before exclusions are added.
Themes and presets retain their loose editable packaging.

The frozen QML package contract is evidence-gated rather than `qml`-means-everything. Project-authored QML currently
imports only `QtQuick` and `QtQuick.Effects`; the shared build-layout authority rejects any new external QML namespace
until the package contract is deliberately reviewed. Nuitka's broad QML scan is therefore pruned for source-proven
unused families, including WebEngine, QML PDF and the `qpdf` image plugin, VirtualKeyboard, Qt3D/Quick3D, Controls
families, Charts/Graphs/DataVisualization and Location/Positioning. Standard, Media Center and their Venv workers use
the same exclusion authority; the diagnostic file is the Standard binary itself. Native Qt Multimedia remains
packaged because notification/Jedi playback uses `QMediaPlayer`/`QAudioOutput`; QtQuick/Qml/Effects, QtGui's OpenGL
context surface, NumPy/OpenBLAS and other currently owned runtime dependencies are not removed merely for size.
The PySide6 QtQuick binding has a binding-level dependency on `PySide6.QtOpenGL`, even though SRPSS application
source obtains `QOpenGLContext`/`QSurfaceFormat` from QtGui and uses PyOpenGL for renderer calls. Therefore
`PySide6.QtOpenGL` and the native `Qt6OpenGL` substrate are mandatory frozen dependencies and must not be pruned by
source-import reasoning alone. `Qt6OpenGLWidgets` remains outside the runtime contract because the QWidget/QOpenGLWidget
presentation path is retired. `opengl32sw.dll` is retained unless a frozen-runtime acceptance probe proves that this
particular PySide/Qt Windows package does not require the fallback loader path; hardware OpenGL 4.6 remains the actual
runtime floor, but that policy is not evidence that a Qt deployment support DLL is loader-safe to remove. Linked
framework DLLs belonging solely to QML namespaces rejected by the authored-import allowlist may be denied only when
the current frozen dependency graph and runtime acceptance both agree. WGL remains a valid Windows OpenGL platform
surface and must not be confused with WebGL. A new dependency cut requires a fresh current-build report plus runtime
acceptance of the affected surface.

Only Standard and Media Center have installers. Their two canonical `.iss` files are self-contained and each requires
Inno Setup 6.7.2 or newer, deletes the previous expected `Setup_*.exe` before compilation so failure cannot masquerade
as success, and owns the same fixed SRPSS installer visual language (`modern dark slate includetitlebar hidebevels` plus
a charcoal wizard surface). No third installer-visual include is an authority. This is an installer-specific VCL
presentation contract, not a second Settings Theme renderer and not a user-selectable theme. The existing transparent
`SRPSS.ico` is the single brand asset: `SetupIconFile` owns the executable/window icon while each installer loads that ICO
into Setup and Uninstall's small wizard bitmap plane with transparent background handling. The explicit ICO `[Files]`
entry is first so early extraction does not traverse the solid runtime payload. Build Foundry discovers Inno 7 before 6,
retains explicit override/PATH fallback, and removes stale expected installer output before invocation. Standard installers
must not resurrect immutable QRC-owned imagery as loose files; Media Center's recursive release wildcard is the one
app-payload copy. The obsolete `ui/assets/installer/LogoBMP.bmp` has no remaining installer or Build Foundry owner and is
retired rather than retained as dead source baggage.

For venv products, the Foundry first invokes the existing worker's preparation-only mode, which returns before
build-directory mutation or compilation.

## Retired presentation architecture

The legacy `DisplayWidget` / QRhiWidget / `GLCompositorWidget` physical path is retired. The accepted Quick runtime is the sole production presentation authority; the old path is not rollback architecture, a facade, test convenience or fallback. Caller-dead residue is cleanup debt and must not be rebuilt merely to satisfy stale tests.

## Settings themes / native backdrop

Settings remains a frameless translucent QWidget top-level. `SettingsThemeSpec` schema v6 is the semantic visual
authority and compiled Default Dark is the unconditional no-file fallback. Complete `.srtheme` files may request
`off`, `acrylic` or `glass` and must pass strict whole-theme validation.
Schema v6 owns `about.art.liquid`, the explicit Settings-only colour used to recolour only the masked liquid/background field in the two About artworks while preserving source shading, alpha and all unmasked artwork. Every shipped theme seeds this role from its own primary accent (`chrome.outer_border` RGB at full alpha); Nocturne Split therefore uses its pink-red primary accent while other themes use their own primary colour. Schema-v5 user themes migrate the new role from that same existing primary accent rather than failing whole-theme load.

The current Windows Settings top-level is a layered HWND. Both translucent product materials therefore stay on the
physically proven `SetWindowCompositionAttribute` AccentPolicy family:

```text
Acrylic -> ACCENT_ENABLE_ACRYLICBLURBEHIND (state 4) + theme native tint
Glass   -> ACCENT_ENABLE_BLURBEHIND        (state 3) + no native tint
Off     -> ACCENT_DISABLED                 (state 0)
```

Glass colour and opacity are owned by semantic Qt RGBA surfaces above the untinted native blur. AccentPolicy state 3 is
not the documented `DwmEnableBlurBehindWindow` API and must not be reasoned about as though those mechanisms were the
same.

DWM system-backdrop/redirection-bitmap experiments are not part of the current Settings contract. Reintroducing them
requires an intentional window/presentation architecture change and new physical proof, not a theme tweak. Native
activation is not repaired by timers, duplicate calls or QSS replay.

`themes/dark.qss` is retired and physically absent, not theme authority. Production Settings/tray code has severed
the loader/caller dependency; the surviving structure is owned by narrow renderers and semantic visual values remain
in `SettingsThemeSpec`. The file-absent runtime/build matrix is accepted. Do not restore a loader, copy the QSS
blob/literals elsewhere, use native-backdrop workarounds, or add a fail-open theme path. The complete permanent contract is
`Docs/Architecture/Settings_Theme_Architecture.md`.

## Guided Setup / Quick Start

Settings owns one no-source decision after show: Guided Setup unless `sources.guided_setup_silenced` selects the
existing popup. Manual Quick Start ignores Hide This From Now On. Both use normal Settings owners and shared source/account/theme
operations. Guided Setup edits a draft: nothing persists until Finish (or Keep Changes when leaving early).
Account setup requires the calling thread's interactive Default desktop. Arrange stages the canonical
CUSTOM session and shared commit, with content-sized anchored placements and Runtime Edit's own sizing functions
(one gesture saves one entry in either editor). It draws the saver's own geometry: sizes
measured through each family's QML on detached items, placement by the saver's anchor, stacking and Media-docking
functions; once anything is placed, Apply saves the whole canvas because CUSTOM is global. It admits no provider,
scene or audio runtime. Static previews are release assets, never live render work in
Settings. Product and ownership details: `Docs/Reference/Guided_Setup.md`.

## Runtime Widget Themes / semantic visuals

Runtime Widget Themes (`.srwtheme`) are separate from the Settings QWidget theme. They are **colour/semantic bundles only**. `Widgets -> General -> Style Overrides` contains Card Surface, Card Border, Header Fill and Card Border Width: the three colour edits fork a named Widget Theme into persisted `Custom`, while Border Width remains global geometry styling outside Widget Theme schema. Branded-header family colour swatches are retired; header Fill/Text/Border resolve through Widget Theme semantics instead of a Media/Gmail/Reddit/Steam Settings bucket. Existing non-header per-family colour swatches remain higher-precedence only when intentionally authored. `Reset All Colours to Theme` is an explicit operator normalization/cleanup action that normalizes ordinary Clock/Weather/Reddit/Gmail/Media/Steam family colour fields (and card alpha fields that make a colour explicit) back to canonical implicit-Inherit values; it never runs at startup and never changes the selected Widget Theme/Custom palette. Specialized optional visual roles are sparse and inherit through one resolver (`intentional family override -> exact role -> semantic parent -> local/current semantic value -> preserved fallback`); `local.*` roles are presentation context and never persistence. Visualizer-authored colours remain outside this generic reset/theme authority. The retained Context Menu has no family override and consumes the generation-scoped Widget Theme palette directly.

Settings-theme <-> Widget-theme linking is one persisted **bidirectional** stable-ID relationship. The same compact lock/unlock control appears on both theme catalogue pages. While locked, selecting either catalogue activates and persists the explicit paired theme on the other side; selection must never implicitly unlock. A theme without an available counterpart (including Widget `Custom`) requires Independent mode first. Display names are never a pairing authority. Theme Foundry may explicitly save a linked Widget counterpart only through the same deterministic Settings->Widget projection authority used by the curated mirror generator; the Settings theme must have a real stable catalogue identity first. Clock is semantic through shared `card.text` when its family swatch remains canonical. Abandonment Issues' archive/BACKLOG accent is the specialized `abandonment_issues.accent -> widget.accent` role; the block consumes that accent while its label consumes ordinary themed text for contrast.

Live Settings theme publication must distinguish Python wrapper lifetime from C++ QObject lifetime. Registries may use weak references for ownership, but before applying live QSS they must verify that the PySide wrapper still owns a valid C++ QObject and prune stale wrappers. A stale deleted wrapper is cleanup, not a renderer failure; an exception from a still-live renderer remains transaction-fatal and rolls the theme back.

Runtime cards remain the ordinary retained Qt Quick RGBA surface/border/shadow path. The rejected runtime Glass/Acrylic card experiment has no schema field, Surface Style override, card material Loader, background capture/layer, mask tree or cadence callback. The wallpaper/transition render node is directly composited under the display scene using the healthy pre-material topology, selectively restored while preserving the later Bidirectional theme/lifetime/C++ fixes. Settings-window Glass/Acrylic remains a separate native QWidget/HWND theme concern. The failed runtime-card experiments are preserved as negative-control history in `Docs/Contracts.md`.

The curated source pack currently contains 58 Settings themes and 58 deterministic colour-only Widget counterparts, including four deliberately light/white-adjacent themes and four silver/metal themes. Settings-theme filenames may legitimately retain `[Glass]`/`[Acrylic]` because those tags describe the Settings HWND. Widget counterpart display names and filenames omit those tags while preserving stable links back to the actual Settings-theme identity. Installed theme storage is the same machine-wide curated asset family as visualizer presets: source/dev reads `<repo-root>/themes`, while frozen/installed runtime reads `%ProgramData%\SRPSS\themes` and Widget Themes live under its `widgets/` child. Normal and Media Center installers seed/clean-replace that tree; Nuitka may bundle the source pack for build completeness, but frozen runtime does not merge the bundled extraction/app-local copy into the active catalogue.

Immutable application assets are Qt resources. Their canonical sources live under `ui/assets/`, grouped by ownership;
`ui/resources/assets.qrc` embeds ordinary fonts, UI icons, branding and widget imagery under `:/srpss/...`.
Qt image APIs use that path; QML uses `qrc:/srpss/...`. Consumers must not resolve install directories or extract
resources back to disk. Frozen products do not ship duplicate loose imagery.

Guided Setup previews have one separate `onboarding_assets.qrc`, registered on the first explicit asset request.
The split follows measured import cost of the consolidated resource family; importing Settings/onboarding helpers must
not register the preview pack. The selected pinned PySide toolchain compiles `assets.qrc` and
`onboarding_assets.qrc` to raw binary `assets.rcc` / `onboarding_assets.rcc` via `rcc -binary`. Build Foundry and the
standalone product workers own content-based regeneration and provenance. Runtime registers the ordinary binary pack
with `QResource` at the resource/UI boundary and registers the onboarding pack lazily. Existing `:/srpss/...` and
`qrc:/srpss/...` identities are invariant. Frozen products package the `.rcc` files as data and must not rely on
generated Python resource modules or loose-image fallbacks. Generated `.rcc` packs/provenance are reproducible build
products and stay opt-in for GODZIP transfer; the `.qrc` manifests plus canonical `ui/assets/` sources are handoff
authority. Legacy generated Python QRC modules are retired rather than retained as fallback. Themes, presets, user content,
caches, credentials and replaceable notification/Jedi sounds retain filesystem ownership. Installer artwork is a
compile-time Inno Setup input, not loose runtime imagery.

Clock named-zone authority is `PySide6.QtCore.QTimeZone`, already present through QtCore. SRPSS must not bundle
`pytz`, `tzdata`, or a loose world `zoneinfo` tree merely for Clock display. Local detection uses Qt's system timezone
identity rather than offset matching; the bounded Settings/Onboarding catalogue, explicitly persisted SRPSS aliases,
DST-aware current/future conversion and explicit `UTC±hh[:mm]` values remain supported. On Windows Qt maps the native
Windows zone through its built-in IANA/CLDR mapping; obscure historical-zone fidelity outside the SRPSS-authored
catalogue is not a reason to ship a second global timezone database.

## Capability / ordinary instance state

Family activation/deactivation is different from ordinary instance ON/OFF. Capability deactivation preserves detail
settings and suppresses family-exclusive ownership; ordinary `enabled=False` is the casual per-widget off state inside
an activated family.

CUSTOM X and layout-slot replay may change ordinary ON/OFF only. They never activate a deactivated capability/family.

## Import dormancy

Common Quick scene/host imports must not eagerly import inactive family business/runtime/backend trees. Family
implementation resolves at actual family caller/activation. Static presentation-only registry metadata is fine.
Common Quick import must not bootstrap provider/controller/runtime/backend singletons.

Lazy Settings family bodies follow the same lifetime discipline as runtime families. Before a section is retired or its
QObjects receive `deleteLater()`, invalidate queued/coalesced UI callbacks that were admitted under the old section
generation and remove retained references to its labels/combos/anchors/other child controls. Any later generic refresh
must validate the underlying C++ QObject (`shiboken6.isValid()` or equivalent) and fail closed on a stale wrapper. Do not
solve deleted-object failures with timers, event-loop pumping, leaked hidden sections or family-specific unload exceptions.

## Shared 3D rendering foundation / dormancy

Usu character authoring material lives in the local working checkout under `assets/usu/` (see its Windows-local `README.md`, not bundled in normal GODZIP handoffs).
The Blender source and review renders are authoring assets; they do not admit a
runtime Visualizer, rig, animation or engine export. Asset modelling and approval
notes stay in the Windows-local `assets/usu/README.md`; they do not belong in `Current_Plan.md`.

SRPSS already has a bounded **real-3D foundation inside the accepted Qt Quick scene**; future 3D work must inspect and
reuse/extend this foundation where appropriate rather than creating a second renderer stack.
Shared mesh, reflection and scene/post resource ownership, immutable storage, multi-bind and state restoration are
detailed in `Docs/Reference/Scene3D_Resources.md`.

**3D presentation is SDR-only.** Do not add an HDR swapchain, HDR metadata, HDR display/output mode, HDR Settings
surface or HDR-specific tone-mapping pipeline. Higher-precision internal render targets are admissible only when a
concrete effect needs numerical headroom; they remain an implementation detail and resolve into the canonical SDR
Qt Quick presentation path.

Current proof points:

- `rendering/quick/transitions/implementations/block_spins.py` is a lazy Quick renderer that owns real mesh geometry,
  context-local VAO/VBO/program resources, source/destination textures, depth-tested rendering and explicit
  `release_resources()` cleanup;
- `rendering/gl_programs/blockspin_program.py` is the OpenGL-free authored mesh/shader contract and already demonstrates
  3D positions/normals/UVs, transformed normals and bounded directional/specular treatment;
- `rendering/quick/visualizer/implementation_registry.py` resolves a mode renderer lazily from the canonical Visualizer
  descriptor and requires the `render()` + `release_resources()` implementation contract;
- `rendering/quick/visualizer/render_host.py` and `rendering/quick/visualizer/clip_host.py` provide the accepted Quick GL
  ownership/fence and preserve/restore relevant state including cull, depth and depth-write state around custom rendering;
- `core/settings/visualizer_mode_registry.py` already defines the presentation-policy vocabulary including
  `CARD / CARD_INTERIOR` and `FRAMELESS / VIEWPORT_RECT`; the frameless geometry/clip path is covered by
  `tests/test_qtquick_visualizer_geometry.py` and `tools/qtquick_visualizer_clip_smoke.py`;
- `rendering/quick/render/gl_resources.py` and the existing implementation modules are the starting point for bounded
  context-local shader/program resource ownership.

This is a **substrate**, not a general-purpose scene engine. Reusable low-level primitives may include static mesh/buffer
ownership, small aspect-correct projection/MVP helpers, GL resource lifetime helpers, safe depth-state composition and
presentation-neutral direction/light math. Feature semantics remain local: deformation fields, fracture logic, material
identities, audio mapping, per-effect physics/easing and authored visual behavior do not move into a generic 3D framework
merely because two features both contain Z coordinates. A shared primitive the roadmap plans to use (the Current_Plan
§4 S-slices, the Usu Moonscape foundations) may be built before any transition or mode consumes it: it is proved by its
own focused tests, offscreen renders and measurements, and costs nothing until something activates it. Never design or
ship an effect around a primitive merely to give it a consumer. What stays forbidden is abstraction nothing on the
roadmap needs.

3D work inherits the existing clock rule. `VisualizerLogicalRuntime` remains the mode-general authored Visualizer clock;
a mode-owned logical/frame runtime may produce compact 3D state, but render refresh never becomes simulation cadence.
Transitions similarly consume their one canonical monotonic run rather than creating an effect-local clock.

**3D dormancy is mandatory for meaningful cost.** If every admitted mode/effect that needs additional 3D machinery is
dormant, the project must not keep 3D-only shader programs compiled, meshes/VAOs/VBOs allocated, effect-specific GPU
resources retained, depth-specific per-frame work running, workers alive, or a separate 3D cadence ticking. Heavy
implementation modules resolve at the consuming renderer boundary and context-local assets retire with that renderer or
context. There is no background "3D subsystem" owner.

Cheap/import-safe pure math, immutable types, tiny contracts/helpers and canonical catalog metadata may remain shared or
eager when their cost is effectively nil and doing so prevents duplication. Dormancy protects meaningful work/resources;
it is not a requirement to hide zero-cost helpers behind artificial import machinery.

Future 3D modes/effects should therefore begin by inventorying the files above, then add the smallest missing substrate
needed by the real vertical feature. Do not cargo-cult Block Spins' transition-specific projection/math, and do not distort
an existing helper merely to claim reuse.

## Ordinary widgets

Ordinary CUSTOM semantics are divided between family-owned retained QML paint/reflow and the shared session-owned Edit/persistence path. A semantic child-role list declares stable identity and real paint targets, not live normalization values, visibility or provider snapshots. The selected Edit delegate resolves the current family-owned normalization and paints through the actual retained transform/clip chain; a change in size or readiness must not replace a selected role delegate. Repeated content exposes meaningful editing units, not overlapping per-primitive handles: System Stats uses header, top separator and one complete metric stack; Friend Pulse uses grouped row/grid representatives. No parallel geometry owner, polling, normal-render Edit observer or per-pointer Settings writes are allowed.

```text
provider/backend/runtime/cadence/actions
-> stable presentation model/state
-> retained Quick pixels
```

Current proven patterns are deliberately heterogeneous:

- Clock: shared `GlobalClockTicker` + stable models; no invented service;
- Weather: neutral manager-owned runtime service + retained model;
- Media: runtime-generation shared owner with display leases, separate narrow volume/mute owners and a process-engine
  artwork provider;
- Reddit/Reddit2: separate configured member runtime services/models using shared family policy;
- Gmail: runtime-generation shared Gmail owner/backend with per-display lease;
- Achievement Pulse: neutral Steam runtime/preparation/cache/selection ownership. `Progress Pulse` is a presentation of the existing Total field: the first numeric value establishes baseline, later numeric changes emit one presentation edge, and the 2 s build / 3 s decay is QML animation frame demand only—no second refresh, polling, worker, thread or application timer. `Shelf Style` is a presentation-only alternate for the supporting fields and reuses existing Steam metric/accent/text semantics;
- Abandonment Issues: neutral Steam runtime/data/cache/rotation ownership;
- Friend Pulse: one runtime-generation Steam friend/cache/avatar owner shared by display leases; cache-first FriendList + bounded PlayerSummaries, account-private pin persistence and retained Grid/Rows presentation. No Steam-chat/message-session backend is part of the product;
- System Stats: one runtime-generation low-priority sampler shared by display leases; CPU/Memory/Uptime/Network selection suppresses unused underlying observations inside that same owner rather than creating per-metric timers/services.
- FEEDS CUSTOM 1–4: one generation-scoped family owner with endpoint-deduplicated source leases, endpoint-isolated durable last-good state, retained List/Grid/Compact QML and event-admitted local artwork. It uses the ordinary shared `content_extent` and child-geometry/Edit owners; repeated article artwork shares one stable semantic geometry role rather than persisting article identities.
- FEEDS NEWS (World, US, Politics, Gaming, Tech, Anime): each card is one ordinary lease per selected publisher on that same family owner, merged newest first; no NEWS scheduler or downloader. Every Feeds card shares one family refresh cadence (`widgets.feeds.refresh_minutes`), and sources due close together share one wake-up.

Do not create services/managers merely for naming symmetry.

App volume is a Media-dependent scene-local accessory, not an independent widget-family capability. Its default
presentation is an **external right accessory lane inside the same retained `OverlayWidget` root** as the Media card.
`OverlayWidget.rightAccessoryExtent/rightAccessoryContent` reserves authored width beside the card; the card then keeps
its accepted ordinary content width while the accessory receives its own visible bounds/hit target and the whole Media
presentation still shares one outer geometry/session, lifecycle and display route. Corner/wheel CUSTOM resize applies the
one uniform transform to card + accessory. Media's shared horizontal `content_extent` changes only the card's logical
content width and does **not** widen the accessory lane; vertical extent changes the shared presentation height, so the
already top/bottom-anchored volume track length follows that height. The display-level ordinary-card shadow uses the
card-only visual width and therefore does not expand over the accessory lane. The lane exists only while Media plus
provider app-volume capability are effective and is default-enabled by the Media setting.
It consumes the existing Media presentation model plus its one `MediaVolumeRuntimeService` lease/action seam. It does
**not** persist an independent CUSTOM child rect, own an independent monitor, create another retained presentation root,
or gain its own model/controller/poller/service. A future independently movable volume child would require a separately
approved geometry contract rather than being inferred from this accessory lane. Moving volume back inside the card is
likewise an explicit presentation option/feature, not a parity fallback, and must not steal the reclaimed Media card
content width.

### Last-good cache / freshness policy

For network/provider features with a durable cache, **freshness is metadata, not expiry authority**. A coherent successful
cache record remains eligible for cache-first presentation regardless of age. Freshness decides whether a refresh is due
and whether presentation is marked cached/stale; a failed/private/rate-limited/malformed refresh must not overwrite,
freshen, or delete the last-good record. Cache removal requires an explicit user/account/cache reset, schema
rejection/corruption, or a proven semantic identity change. Do not improve nominal freshness by blanking useful stale
content. Friend Pulse, Games You Follow and FEEDS use this cache-first rule.

## State / actions

Ordinary widgets support optional **Widget Glow on Hover** and **Widget Glow on Click** under Display -> Interaction.
One shared swatch inherits the active Widget Theme's `card.border` semantic by default (`input.widget_glow_color=null`);
an explicit RGBA choice persists until **Use Theme** clears it. `input.widget_glow_intensity` is the canonical 0-100%
opacity scalar (default 100). `input.widget_glow_distance` is the canonical 6-48 px halo travel/spread scalar (default
14 px; the former analytical extent was fixed at 12 px). Both project once with the other immutable input options. Existing
interaction/Ctrl/context-menu admission gates the shared retained glow. Hover uses the existing passive hover edge: it
fades in, settles with no running animation while hovered, and only begins a gentle fade when hover ends. Admitted
discrete presses select the last-clicked ordinary card or retained Visualizer without consuming its semantic action;
that click glow remains settled until a later admitted press selects another target or empty space, then fades out.
The retained Visualizer uses the same primitive only while its real card/frame shell is rendered. `cardShellEnabled` is
the single glow-eligibility truth for ordinary widgets and the Visualizer: frameless presentations (including Sphere,
frameless Clock, Media, Reddit, Weather, or any future shell-less family) receive no hover glow, no click-glow target
and no Jedi Mode trigger. Losing the shell clears any retained click selection. Only state edges trigger finite Quick
animations; there is no new poller, timer, worker, independent frame loop or visualizer clock. Runtime theme colours
resolve with the existing generation configuration.

Producers integrate work then publish coherent accepted current state. Presentation consumes bounded latest state with
generation/request fencing. No producer wait for paint, paint acknowledgement, FIFO render backlog, catch-up replay or
display-rate division of authored cadence.

```text
QML semantic action
-> Python action owner
-> business side effect
-> accepted current state
-> presentation
```

QML does not persist settings or directly invoke providers/backends.

Context menu **Images → Save Image** (alongside Previous/Next Image) is always offered (checking each image's source per open would be extra work). The engine
copies the file it already has for the display that was right-clicked, byte for byte, with one I/O-worker `copy2`
(`core/sources/image_collection.py`): into the Sources "Save All RSS Images To Disk" folder when the user ever chose one, else
`Pictures/SRPSS Collections`. The first save there adds that folder to `sources.folders`; the engine marks this one
write as its own so the running sources and prefetch are not rebuilt (the image is already in rotation). No timer,
poll, extra size or cache change is involved.

A local source folder has one spelling. Every place that adds, shows, de-duplicates or removes `sources.folders`
entries (Sources tab, Guided Setup, the collection above) goes through `core/sources/folder_paths.py`: Windows
separators, case- and separator-insensitive identity, so Qt's `C:/…` picker result and a `C:\…` path are one folder.
Stored values are read as they are and never rewritten merely to change separators.

Retained Windows GSMTC event observation has a stricter ownership rule than ordinary burst IO. The manager, selected session and their subscription/remove tokens are created, rebound, detached and released only on one lazy ThreadManager-owned **affinity lane**. The general IO pool is not an apartment authority and the Qt UI thread must never clear retained WinRT wrappers. Native manager callbacks capture only a coarse edge and queue any session rebind back to that lane; session dirty callbacks remain presentation-neutral. Teardown fences the observation generation first, then synchronously executes detach/release on the affinity owner. This lane is Condition-driven and owns no polling cadence.

Media refresh queries (the Visualizer's play/pause truth) and transport commands run on a separate lane owned by the shared Media runtime owner: a ThreadManager-owned dedicated `media` worker (`create_affinity_lane(worker="media")`), created on first use, generation-tagged and stopped when the owner retires. They never run on the FIFO IO pool, where network work (unbounded DNS/connect stalls) could starve them, and never on the observation worker, whose teardown waits a bounded 2 s on that thread. The owner injects the lane into its controller (`set_work_executor`); one-in-flight/one-pending refresh, command de-duplication and event authority are unchanged, and there is no polling fallback.

Every native dirty edge still yields the one shared refresh (coalesced, never throttled by reason). A refresh caused only by timeline edges narrows its query scope: when the fresh snapshot has the same host/title/artist/album identity and that track's artwork is already held, the WinRT thumbnail stream is not re-read and the held payload is reused. Properties, playback, activation, reconcile, wake and command refreshes always read artwork, and a track without held artwork keeps reading so a lazily published thumbnail is picked up.

Source/developer runs and explicit debug/verbose runtime logging must persist recoverable native/SEH faulthandler output to `native_faults.log`; the dedicated diagnostic build uses `diagnostic_crash.log` and adds lifecycle breadcrumbs. Ordinary compiled non-diagnostic runs without explicit debug/verbose logging must not activate this native-fault companion. One-shot hang diagnostics may schedule `faulthandler.dump_traceback_later()` to their own file but may not call `faulthandler.enable()` or retarget the persistent native-fault stream.

Media transport is non-blocking at GUI ingress. Queue admission is not provider
success: GSMTC Play/Pause/Toggle/Previous/Next/seek publishes its asynchronous
Boolean or exception outcome to the single shared Media runtime owner, which
generation-fences it and then refreshes accepted state. Play/Pause capability is
the state-appropriate union of canonical GSMTC Play, Pause and Toggle controls;
seek position is an absolute 100 ns tick value.
Quick runtime Space/Home (play/pause), Left (previous) and Right (next) shortcuts route through `DisplayManager` to exactly one **live** Media presentation across all active displays, preferring the invoking display when it owns Media. Input focus on a display without Media must not drop the command. Retired display/generation units are ineligible. The canonical Media action names are `play`, `previous`, `next`; do not reintroduce `prev` at the Media boundary or emit commands on multiple displays.

## Dynamic images

Use stable identity and bounded presentation image ownership. Proven Media shape:

```text
runtime-owned decoded QImage + stable artwork key
-> retained artwork rectangle hard-clips dynamic image buffers; family mask/border owns rounded edge containment
-> process-engine image provider
-> retained Image source identity
```

No QPixmap worker transport, base64 churn, tempfile-per-update or unchanged-image reupload. Dynamic artwork uses the
shared readiness-gated `ArtworkFadeImage`: the displayed texture stays visible until the replacement reaches
`Image.Ready`, the incoming buffer fades over it for 520 ms with `InOutSine`, then the old texture is released; an explicit
empty source fades the current image out over 280 ms. This is finite event-driven frame demand only and retains no second
artwork texture at idle. Family-specific artwork QML may own geometry/mask/shadow, but not another swap cadence/transition
owner.

## Shadows / fade

Canonical direction is NW/N/NE/W/E/SW/S/SE, default SE, resolved in Python. No Text Blur, Intense mode,
`widgets.shadows.offset`, `shadowtuning.json`, or replacement hidden tuning. Ordinary card = cached retained
`RectangularShadow`; ordinary text = duplicate glyph + signed offset; whole-widget fade = one retained root opacity.
Clock analogue hard shadows are permanent family-authored exceptions under doc 11.

Settings-window theme/shadow ownership is separate from runtime overlay-widget shadow authority; see
`Docs/Architecture/Settings_Theme_Architecture.md` and `ui/widgets/control_shadow.py`.

## Geometry / CUSTOM

Runtime display identity, CUSTOM and Clock face overrides share `rendering/custom_layout_contract.py`.
Serial-backed keys use serial/model/name; Qt's manufacturer label is metadata and cannot move a saved layout.
Old manufacturer/geometry-qualified keys are accepted at the input boundary, with independent widget/face variants
merged and canonical/current-label entries winning conflicts. Explicit layout saves migrate them to one canonical
bucket without changing the geometry. Serial-less keys retain exact monitor facts and geometry; there is no
monitor-index or approximate-geometry replay.

Non-CUSTOM stacking first attempts full authored sizes, then bounded whole-card
shrink/re-stack trials down to the shared 40% whole-card floor only when placement remains unresolved.
The bounded search samples 5% bands and refines the first fitting band in 1% steps;
it proves accepted fits without claiming exhaustive or globally optimal packing. Each
accepted scale carries its freshly solved placement and 10px clearance; growth
restores authored size as space returns. Clock and fixed Media/Visualizer obstacles
are excluded from shrink. No-fit remains an explicit overfull diagnostic. Global
CUSTOM disables this derived planner; first Edit preserves the visible footprint.


Ordinary card CUSTOM resize starts with one retained whole-card transform, with Settings-authored baseline values
unchanged. A family may additionally opt into the **shared `content_extent` presentation-reflow contract** on selected side
axes. Side handles then change one logical family content axis at constant uniform scale; an optional selected-parent diagonal corner may change both admitted content axes through the same owner; existing square corners/wheel still resize the whole
retained presentation uniformly. The descriptor/session/owner is the sole persistence authority for that extent. Family
QML/models may consume it to reflow rows, spacing, metadata or artwork, but may not persist geometry, mutate product
Settings, create a placement solver, or add a resize timer/debounce/poller. Family-owned logical side-drag floors are
allowed only through the shared content-extent policy and must not replace the generic whole-card uniform shrink floor.

Restore Size is a separate shared edit action. It uses the canonical preferred geometry captured **before CUSTOM payload
hydration** and retained separately from effective/committed CUSTOM geometry. It restores only the selected widget's
authored size/shape, clears family `content_extent`, preserves current X/Y + display, remains in CUSTOM, and does not invoke
stacking or ordinary auto-fit/shrink. Uniform emergency reduction is allowed only when the authored rectangle itself
cannot fit the owning display. A live CUSTOM side resize must never redefine that authored restore target.

Wheel resize shows nearby peer-alignment guides but never snaps; the generic edit grid remains 1 px while authored
alignment/centre/gutter guides use the thicker guide treatment. Clock retains variant-aware sizing; Visualizer retains
separate viewport and visual-scale intents. New-widget implementation starts with the
[authoring checklist](Docs/Guides/10_WIDGET_GUIDELINES.md#whole-card-custom-resize-default).

Outer geometry is Python/session-owned. Variant key supports `(widget_id, display_identity, geometry_variant)`.
Clock digital/analogue are the first required example. **That existing variant axis is also the only admitted persistence seam
for Visualizer pose compatibility.** Visualizer descriptor `geometry_kind` selects mechanics (`planar` / `freeform_3d`) while
`layout_profile` selects the existing CUSTOM variant slot. Current profiles are `planar`, `3d:extruded_spectrum`,
`3d:shockwave_grid` and `3d:sphere`; future modes may share a profile only by explicit descriptor choice when their stage geometry
is compatible. The split remains inside the same `custom_layout` map, `CustomLayoutSession` and commit/hydration owner; it may
not introduce parallel 2D/3D roots, per-mode X/Y settings or a second geometry service. Hidden activation restores the target
layout profile without borrowing outgoing geometry. Turn/tilt/camera/material/preset values remain mode-presentation state and
are never serialized into layout profiles. Legacy `default` / `freeform_3d` variants are one-way interpretation input only.
Read-only projected 3D Edit envelope/cage paint and migration/transaction semantics are defined in `Docs/Contracts.md`'s CUSTOM
contract; The operator accepts implemented geometry/profile authoring; reopen from the specific R-111–R-113 incident only if new symptoms are reported.

Edit-mode X changes working session only: duplicate removal or singleton ordinary-enabled OFF. Never family capability
deactivation. Save/Enter commits; Cancel restores pre-edit geometry/instances/enabled state.

Layout slots save/load ordinary visible-layout state, including ordinary ON/OFF, but never capability activation or
provider/account/source settings. The Visualizer's active `mode` is part of visible layout/hot-swap state and is captured
with its geometry; per-mode tuning/preset fields are not. Clock is the other explicit stateful case: each Clock slot captures
its shared `display_mode` baseline **and** the complete per-display `display_mode_overrides` map, while `custom_layout`
continues to own the independent digital/analogue geometry variants. Slot replay applies that mode state before the fenced
runtime rebuild so the presentation selects the geometry belonging to the saved face. Empty override maps are meaningful
state; legacy payloads that predate override capture fall back deterministically to their saved shared baseline rather than
inheriting a newer runtime override. Number-key slot **load** then performs the existing fenced runtime rebuild so restored
visible state becomes runtime truth. Ordinary live Edit Save, including a successfully transferred cross-display Visualizer,
is not a slot-load boundary and must not gain teardown/reinit from this rule.

CUSTOM is a **global layout mode**. If any effective widget route is `Custom`, ordinary authored stacking and the
non-CUSTOM Media/Visualizer adjacency projection are disabled for the entire retained layout, not selectively per
widget. The same subsystem switch is asserted before live Edit Layout captures geometry and before number-key layout
slot loads rebuild the runtime. Live Edit preserves the currently visible stacked/adjacent rectangles when capturing
its initial session: disabling Follow Media or stacking changes authority without moving or resizing the cards.
A newly constructed uncommitted Visualizer in global CUSTOM uses Media's plain authored slot. Cancel restores
authored packing only when no effective route remains `Custom`. This boundary is event-driven and owns no cadence.

CUSTOM terminalization is one **shared all-display transaction**. Save/Cancel may not clear one display and then throw before
the others are released. Every display cleanup is attempted, shared coordinator/session/binding ownership is retired in a
`finally`-equivalent boundary, and repeated cleanup is safe. A Python retained-presentation wrapper must not outlive its C++
`QQuickItem`; unexpected Qt destruction is captured from the object's `destroyed` edge and pruned without polling. Healthy
geometry-only Save—including a coherent cross-display Visualizer transfer—still performs no teardown/reinit. If persistence
has committed but a dead retained Qt root or failed live promotion proves the current retained graph corrupt, finish the
shared Edit session first and then queue exactly one generation reconstruction from committed truth. That reconstruction is
an invariant-repair path, never the normal Save contract. Lifecycle/diagnostic snapshots are observational: encountering an
already-deleted Shiboken wrapper must be reported/fail-closed and can never abort runtime destruction.

## Visualizer geometry

`VisualizerLogicalRuntime` remains sole mode-general authored visualizer clock. Quick presentation does not own
simulation cadence.

Visualizer geometry is capability-driven. Modes using the shared reflowing card policy use the canonical 1.5 baseline aspect; every registered descriptor must explicitly declare how it supports the two CUSTOM operations:

```text
uniform_visual_scale
    wheel -> whole visualizer scales uniformly; viewport extent unchanged

viewport_extent
    left/right edge -> width only
    top/bottom edge -> height only
    corner -> width + height independently, opposite corner anchored
```

Viewport extent is world/layout playroom, not final-pixel X/Y stretch. Every registered mode must remain viewport-resize-capable through its descriptor policy and adapt its authored domain to wide/tall extents without anisotropic final-pixel stretch. Bubble's viewport bounds are spatial
configuration to its logical side; changing them must preserve round geometry, motion/collision semantics and BTF and
must not create another clock. Bubble position/trail coordinates normalize from that expanded world. Stream/drift deltas
are renderer-content-relative: each nonbaseline movement axis projects once onto the corresponding expanded domain axis,
and nonbaseline trail length/strength are solved in content coordinates before world storage. This preserves the same
visible fraction-of-viewport motion at canonical, wide and tall extents rather than losing `1 / domain_axis`; canonical
`1x1` takes the exact pre-projection path. Nonbaseline swirl tangent/radial geometry is likewise solved in content space and
its birth offset projects once per axis, so viewport aspect does not distort the authored orbit. Authored render radius
is projected through the equal-area canonical response height `sqrt(content_width * content_height / 1.5)`.
This operator-authorized mapping replaces the rejected actual-height coupling, preserves the complete radius
waveform across same-area shapes and grows naturally with visible area. Directional entry depth, refill-cluster spread,
surface exit/drain grace, contraction retirement margin, overlap-retry allowance/jitter and pre-entry prediction distance
are also renderer-content distances projected once per nonbaseline axis; otherwise lifecycle shape changes with viewport
size. None of these spatial projections changes random-draw order or adds a tick. Radius is not divided by viewport-domain
height. Collision/spawn policy remains in canonical normalized content coordinates and preserves exact canonical
behavior; it is authored separation rather than literal pixel packing. Any contact change needs a dedicated
rendered-overlap and event test under BTF. Bubble viewport presentation uses one **geometry-only cached gradient profile**:
resolve it when committed viewport geometry changes, cache it in the logical simulation and retained Quick layout, and do
not reclassify area/aspect every audio/render tick after Edit settles. The main-head outline uses a bounded physical-pixel
curve (about **1.6 px total canonical floor**, earlier gentle area/shape firmness, about **4.7 px total ceiling**) rather than
the retired late `bonus * effect_scale` acceleration or the retired -1px complete-outline subtraction. Extreme width eases
from no-op at roughly **2.5:1** physical aspect to at most +1 authored big bubble, +3 authored small bubbles and +20% stream
baseline/cap by roughly **5.0:1**; the +1 big modifier applies only when authored `bubble_big_count > 0`, and zero is a valid
authored count. Extreme vertical geometry eases from roughly **1.5:1 to 3.0:1 height:width** to at most -1 big bubble,
-1 small bubble and -30% stream **cap** while leaving baseline stream speed unchanged. Integer population deltas are necessarily
discrete; stroke and speed/cap factors are continuous. These profile adjustments may not alter drift, radius, Ghost/history
displacement, reaction amplitude or cadence.

Bubble consume-once kick/snare/vocal events may accent stream and drift motion only through the existing decaying
stream-burst state. They must not add a clock, mutate authored motion settings, replay an event, or leak into pulse/radius
authority. Motion diagnostics report renderer-normalized, pre-collision stream/drift contributions; final trajectory can
still be changed by the existing impulse and collision stages.

Registry-wide viewport capability is part of the destination contract and the core Bubble reflow path has landed.
Bubble's per-head specular mutation and light ellipse use the canonical content aspect at the current
uniform scale/inset; edge resizing changes playroom without stretching or rotating the local highlight.
Do not reintroduce a Bubble false capability gate to conceal a viewport ownership or spatial-domain defect. **R-69 is golden for optimization:** wide/tall geometry may not globally compress renderer-facing Bubble head radius, already-normalized Ghost/history displacement, or another mode's authored musical response/freshness. If an extreme Bubble full-expansion tail is too large, fix only that proven tail.

Committed viewport extent is ordinary runtime truth. While CUSTOM is active, its working extent may temporarily override
that committed value. Ending CUSTOM removes the temporary override: Save leaves the newly committed extent authoritative;
Cancel restores the pre-edit committed extent. "No active CUSTOM session" is not synonymous with canonical `(420,280)`.
During one live Edit session, viewport-only resizing has exactly one cached pixels-per-world authority. Side and corner
handles consume that scalar; they must not relearn scale independently from later retained presentation publications. Only
explicit wheel uniform scaling or an unavoidable cross-display target-fit projection may update the scalar, and the new
rectangle + viewport extent + scalar must remain one coherent transaction. Cross-display transfer may clear a retained
target Visualizer admission only when `DisplayManager` proves that target display unit owns **no** Visualizer lifecycle owner;
any target lifecycle owner is a hard conflict. A manager-proven orphan is scene-local residue, not permission to recreate or
move the logical runtime.

During a live edit, the working rectangle also owns its preview scale. Normal logical-frame publications cannot
restore the saved size at the new dragged origin; independently rounded axes must admit the same uniform scale.

Sine/Oscilloscope glow spreads perpendicular to the curve and scales with visible content area relative to
420x280. A huge saved world at a small uniform scale must not weaken a halo on the same visible footprint.
Glow size/intensity and line-core antialiasing remain independent.

Sphere is a **standard registered Visualizer mode** with the same canonical per-mode activation/selection semantics as other modes; registry growth must not require rewriting this contract. The current representation is **Voxel Sphere**: a frameless transparent stepped-voxel shell using one static cube mesh and one static instance buffer with vertex-shader deformation. Its current musical behaviour—event-owned fragmentation/cohorts, stable four-corner population identity, sustained body growth, event-stepped tracer travel, continuous rotation and vocal-linked intake recoil—is a golden preservation target. Presentation or maintenance work may not reduce its reactivity/freshness or introduce ambient/private cadence.

Sphere uses the shared Scene3D resource/ring substrate while its reaction remains mode-owned. Its descriptor lazily resolves its Settings builder, capture, frame runtime and renderer; heavy resources stay dormant while disabled and retire through the normal render-context lifecycle. Canonical `sphere_*` state owns the descriptor-declared consumed technical inputs and selected frequency splits. Missing old values are promoted once from the former RAW Spectrum profile before defaults, including Custom-cache and SST inputs; there is no live Spectrum dependency. Only Spectrum, Extruded Spectrum and Shockwave Grid enter the Spectrum-authored bar-shaping pipeline; Shockwave uses its shape to drive its horizon. Bubble and Sphere consume shared FFT/zone/control/transient analysis without Spectrum shape nodes or lane interpolation. Sine heartbeat and Dev Curve get pre-AGC musical energy independently of bar shapes; Dev Curve owns its separate layer editor. Activation fencing carries the policy across the existing shared BeatEngine and detached compute snapshots. The original Sphere isolation was operator-accepted in R150, expanded here to all mode capabilities. Direct fill/edge/tracer RGBA and Sphere-local Rainbow speed/extent retain their renderer consumers without opting into unused shared Rainbow/bar-appearance controls. Product admission is standard: Settings and Guided Setup expose Voxel Sphere normally, while renderer/runtime imports and heavy resources remain lazy and dormant whenever the mode is disabled or inactive. `Docs/Reference/Sphere_Visualizer.md` owns the detailed settings contract.

The reusable architectural asset is the **experimental host/isolation seam**—descriptor-driven lazy wiring, independent dormancy/retirement, private setting prefix and explicit shared-family opt-outs. It is suitable for future experimental modes. Sphere audio logic, voxel settings, shader semantics and mode-specific capability memberships are not a shared foundation and must not be generalized merely to make that seam look cleaner. Any future experimental mode begins isolated; sharing beyond the host seam requires an explicitly scoped promotion.

The currently curated Sphere presentation examples include **Glass Current** (Preset 5; intake/transparent snapshot) and **Voxel Bloom** (Preset 2; outtake/opaque snapshot with shadow enabled); their **operator-authored slots are editable and must never be frozen as test oracles**. Any historical behaviour snapshot used by a test must be test-owned and not regenerated from today's curated files. Dead experimental-era controls Block Relief, Bass Response, Mid Response, High Response, Energy Curve and Idle Drift are retired and stale state is forward-stripped; Base Rotation owns continuous idle rotation. The former Deformation × Block Reactivity coupling is migrated exactly to one Fragment Strength control plus independent Particle Distance, while Particle Amount changes only post-admission cohort population. Rainbow Ghosting is retired; Sphere-local Taste The Rainbow can independently colour Surfaces and Edges without shared-family ownership. Perspective Strength is Sphere-local and bounded `0..1`, where `1.0` is the accepted projection exactly and lower values only flatten toward orthographic. Edge Weight (`1.0`), Voxel Size Variation (`0.35`) and Tracer Color (`[255,242,194,255]`) expose the renderer's accepted pre-existing constants as Sphere-local presentation controls; those baseline values are visually equivalent to the previous hard-coded path. Optional Depth Shading defaults off and may only darken rear voxels from already-transformed depth in the existing draw; it adds no neighbouring-voxel sampling, extra pass or audio/geometry authority. Sphere Drop Shadow is now a flat-colour **projected voxel silhouette** that compiles the exact hero vertex shader, so rotation/deformation/tracer-local turns and detached intake/outtake positions cannot drift from the visible voxel geometry. Sphere-local Shadow Opacity (`1.0`), Softness (`0.18`), Distance (`1.0`) and Size (`1.0`) parameterize that pass; softness is one optional expanded instanced layer, not an FBO blur or shadow map. Recommended slider marks remain UI guidance matching Glass Current, not defaults. The accepted Sphere preservation/isolation contract lives in `Docs/Reference/Sphere_Visualizer.md`.

## Visualizer preset catalogue ownership

Per-mode visualizer preset JSON files are **user-authored state**. Users may add arbitrary counts, delete presets down to one survivor, and leave sparse authored numbers such as `1, 5, 20`. Runtime compacts whatever authored presets exist into slider positions plus trailing Custom without renaming/deleting their files. Edit Preset resolves the real backing file; Save Preset As chooses a non-colliding authored number. Shipped preset manifests may support packaging/reconciliation but are never runtime authority over the user catalogue, and startup must never require authored numbers to be contiguous.
Frozen Standard, Media Center **and Diagnostic** share the **same** `%ProgramData%\SRPSS\presets\visualizer_modes` curated directory and `%ProgramData%\SRPSS\presets\visualizer_mode_overrides` explicit-override directory. Diagnostic is a logging/build profile, never a separate curated-preset authority; it must not select or migrate old `diagnostic-onefile` preset copies. Source/dev mode retains repository preset resolution. Do not alter, normalize or silently replace operator-authored JSON when enforcing path parity.

## Visualizer interactions

Double-click inside the active retained Visualizer advances to the next visualizer mode. Middle-click is a separate action:
it advances exactly one preset in the current mode with wraparound and consumes no next-image, exit or context-menu action.
The Custom slot is user-owned: leaving it snapshots the exact normalized **mode-owned** payload and returning restores it.
Preset/Custom payloads never own widget admission, `position`, `monitor`, or outer CUSTOM geometry; those remain live route
and layout authority across every preset transition. Runtime
preset persistence replaces only `widgets.spotify_visualizer` plus the canonical `visualizer_custom_presets` cache in one
Settings transaction; it must not refresh the whole widgets map or disturb Media. A same-mode preset activation reuses the
one Visualizer owner, controller, BeatEngine/source, logical-runtime slot, retained presentation and display frame pacer.

## Visualizer display routing

Outside CUSTOM, the Visualizer follows Media's effective position/monitor route. In committed CUSTOM, the Visualizer's
own persisted position, monitor and geometry are authoritative and may place it on a different selected display from
Media. A live `QuickDisplayUnit` participates when it is not retired and has no display-binding loss; Media presence on
that unit is not an admission condition. `DisplayManager` still admits exactly one Visualizer owner, with the existing
generation-fenced CUSTOM grace/fallback/reclaim lifecycle when the requested display is unavailable. Playback truth is
bound from the already-admitted effective Media presentation model across the active display set; a CUSTOM Visualizer on
another display must not require or construct a duplicate Media presentation on its own unit.

## Transitions

Transition membership is owned by the canonical transition registry and lazy Quick implementation host; this specification does not duplicate a fixed catalog count. Registry entries resolve immutable request parameters once, remain dormant while unselected and retire effect-local resources through the shared owner. Effect-specific appearance, defaults, accepted/rejected variants and physical acceptance live in `Docs/Reference/Transitions.md`; persisted state for retired identities is normalized away rather than preserving hidden compatibility renderers. Shared options such as Slide Perspective Push remain options of their owning transition identity rather than creating duplicate registry entries.

Transitions resolve canonical settings/admission into immutable request/run state and lazy Quick rendering. Old
`GLCompositor*Transition` pixels are not destination authority after caller proof.

Slide has one canonical identity and four cardinal directions. Its frozen per-run `motion_style` is one of Linear,
Elastic, Wobble or Flex: endpoints sample the unmodified source/destination, each pixel has one image owner, and
Elastic's bounded late-arrival settlement samples destination coordinates relative to arrival without wrap strips.
Slide adds no effect-local timer, clock, worker or resource owner; true Perspective remains a separate 3D feature.

## Optional feature extension contracts

- The independently enabled system-master-volume/mute OSD (on by canonical default) is an ordinary retained Qt Quick widget inside the single display scene. It shares the event-driven Core Audio endpoint/action authority with Media, coalesces notifications onto GUI publication, uses one event-owned visibility deadline/fade and the ordinary CUSTOM owner, and has no separate audio poll/endpoint/window. The old import-owned process-global mute runtime/poll is retired; do not restore it. See `Docs/Reference/System_Volume_OSD.md`.
- Games You Follow is the default-off `steam_progress`-identity ordinary Steam card for explicitly followed games. Its source uses the existing linked identity/key, globally date-ranked discovered news, secure identity-derived article action, verified cached art and a bounded account-private last-good cache. Initial complete coverage is followed by persisted-cursor maintenance of up to eight apps per refresh session. One retained Quick model and four grouped CUSTOM roles own presentation; no surrogate follow source or second Steam backend. See `Docs/Reference/Steam_Games_You_Follow.md`.
- FEEDS CUSTOM 1–4 are the four fixed CUSTOM feed identities, admitted through one adapter/descriptor/presentation/Settings path. It reads RSS, Atom, JSON Feed, JF2 and IndieWeb h-feed into one model. Its address may be a feed or a website; the site's feed is found by standards-based discovery (no per-site rules) and found again if it moves. It uses the bounded shared Feed transport/parser/cache/source runtime, local-only optional artwork, secure HTTP/S and validated-magnet product actions, shared `BrandedHeader`, independent X/Y `content_extent`, and shared semantic child geometry. Semantic colour is the resting border/state language; admitted active clickable boundaries/text use the product-wide bright-white cue, while dense List rows remain borderless with a neutral-white surface wash. See `Docs/Reference/Feeds.md`.
- FEEDS NEWS are six fixed category cards (`feeds_news_world`, `_us`, `_politics`, `_gaming`, `_tech`, `_anime`) on the same adapter/descriptor/presentation/Settings path. Each merges the selected official no-signup publisher feeds of its category (at least twelve independent publishers per category in the data-table catalog, stable provider IDs in `core/feeds/news.py`) newest first, with exact-URL deduplication only and the publisher named on every row. A failed publisher keeps its last-good stories and never blanks the others. SRPSS does not rank, score or filter stories. See `Docs/Reference/Feeds.md` § NEWS.
- A new transition identity enters the one canonical transition registry and lazy Quick render host. Effect-local resources remain removable/dormant, canonical Settings owns persistence, and neither a parallel experimental engine nor permanent second architecture is required. Existing Slide modifiers stay in Slide. Accepted Voxel Sphere isolation and Bubble/Visualizer goldens are unaffected by this transition extension rule.

## Lifecycle

Old generation loses admission before replacement gains authority; generation 0 is valid. GPU resources are
created/used/destroyed by legal render/context owner. No `glFinish()`, `DwmFlush()`, GUI sleeps or nested event pumping
as cadence repair. Shared `QQmlEngine` is component/cache owner, not hidden runtime-generation owner.

## Production authority

The accepted Quick destination is the sole production owner:

```text
selected display
-> one QuickDisplayRuntime
-> one display-owned WidgetRuntimeManager
-> canonical capability/ordinary-instance resolution
-> existing neutral runtime/service leases
-> stable family presentation models
-> QuickSceneController
-> retained family items
```

Do not run old/new production runtime managers in parallel or restore the deleted physical presenter/backend. Preserve semantic cardinality. Ordinary committed Visualizer viewport extent remains authoritative outside CUSTOM and the temporary CUSTOM working override wins only while editing.

Current source must be reasoned about from present owners/contracts rather than the former F/G/H/I/J cutover phase labels. Surviving compatibility and persisted-schema migration bridges are documented as architecture in `Docs/Architecture/Persisted_Input_Compatibility.md` (user-data protection, horizon-gated); active product/bug work lives in `Current_Plan.md`.

## Documentation roles

- `Current_Plan.md`: active work/next acceptance debt;
- `Spec.md`: durable product/architecture;
- focused docs/guardrails: durable subsystem contracts;
- `Docs/TestSuite.md`: live test inventory/status ledger;
- `Docs/Architecture/Persisted_Input_Compatibility.md`: persisted-input compatibility-bridge guard (user-data protection, horizon-gated);
- `Future_Work.md`: deferred features, their admission rules and dormant order;
- `Docs/Historical_Bugs/`: durable regression/failed-method history; ordinary chronology remains in source control.


## Runtime integration details

### Sphere orbit, authored alpha and quarantined Extruded cast shadows

Sphere's instanced voxel shells project through the shared Scene3D camera with one CPU mirror for Edit bounds. The operator accepted normal Sphere orbit/spin in runtime; an Alt+left-drag release adds a **finite** momentum tail evaluated against the existing logical capture clock. The transient velocity is not preset state or a second camera/animation owner. Persist only the analytically resolved endpoint; re-grab, held-key orbit and preset activation cancel the old tail. Sphere's authored perpetual base spin continues independently. Momentum was physically accepted on Windows (R132); Sphere is operator-accepted; any later loaded-GPU-tail anomaly belongs to the conditional watchlist in `Current_Plan.md`.

Extruded bodies consume fill-swatch alpha and their independent edge lines consume border-swatch alpha; the retired Body Alpha multiplier has no authority. **Extruded cast shadows are disabled** across the renderer, Edit bounds and greyed-out Settings. Historical shadow settings survive for compatibility but cannot reactivate the GL pass. The disabled feature's failed implementations belong in `Docs/Historical_Bugs/R-125_to_R-128_Extruded_Cast_Shadow_Failure.md`; no shadow physics acceptance is claimed.

### Persistent Ban Image admission

The image menu's Ban Image acts on the original local path or stable remote URL, never the decoded/cache derivative. `core/sources/image_bans.py` persists SHA-256-named empty sentinels in the Settings profile. When `.active` is absent, nothing is hashed or enumerated; when bans exist, digest filenames are read **once per runtime generation** into an in-memory membership set. The `ImageQueue` keeps all original source metadata for Clear while active local/RSS/combined queues contain *only eligible images*. Initial hydration and explicit Ban/Clear reindex these queues; normal Next/Peek/Preview/Wrap never call a ban predicate, hash an image, probe the filesystem or loop over banned candidates. All-banned returns immediately; incoming source updates are filtered once, and Clear restores eligibility without source-provider rescan. Multi-display/worker retries and history also use the in-memory membership gate. Only explicit actions write/delete persistent bans. Memory and one-time index work scale with bans/source count; the active rendering and rotation paths do not. No Settings list, polling, new scheduler or GPU work. Implementation is operator-accepted; reopen only from a concrete regression.


### Off-frame transition preparation contract

Reserved Random and explicitly selected upcoming transitions may be prepared only after *all selected displays* have finished the current foreground transition batch. The display manager owns one serial bounded Qt render-job stream for the entire runtime; display GL preparation never overlaps across monitors. Each step is scheduled with `QQuickWindow.scheduleRenderJob` at `NoStage` in the owning window's current GL context, never through `QQuickItem.update()`, forced frames, redraw loops, or independent polling. Steps are spaced using the existing generation-owned GUI one-shot authority (200 ms, at most 96 per display), in display order. New transition admission, a different reservation, window retirement or generation changes cancel delayed steps and invalidate queued results; completion from an old job cannot start a sibling display. If optional preparation fails, the actual transition retains the authoritative render-time compilation path; it must not strand liveness or foreground image delivery. First-image startup remains 200 ms apart; subsequent multi-display starts use 400 ms and duration compensation for the later display, without modifying user-authored transition durations.

### Wallpaper cache lock containment

The cache serializes only LRU/accounting/protected-key decisions. Its shared mutex is never held while logging or releasing the final cache reference to a large QImage. Speculative completions and foreground lookups must remain mutually consistent, while diagnostics and deallocation may finish after unlocking. No new cache, worker, timer, copy or eviction-policy authority is introduced. The previously severe dual-display physical performance regression was reported recovered only after a Windows restart (2026-10-09); root cause remains unproven. See `Docs/Historical_Bugs/R-134_to_R-145_Dual_Display_Reboot_Recovery.md`. The cache contention fix remains a useful bounded safeguard, not a proved cause of the recovery.

### Speculative response CPU ownership and foreground admission (R144)

The separate IMAGE_PREFETCH worker process remains the authorized source of scaled derivatives. Its supervisor-side **response listener also performs full-resolution RGBA shared-memory transfers/cache admission** inside the parent process; this existing listener must run at Windows below-normal/no-boost priority, using `core.windows.thread_priority.apply_best_effort_thread_priority()` **on that listener thread**. Other listeners, foreground image processing, Qt GUI and Qt Quick render-thread priorities must not be demoted. Priority tuning is best effort and cannot strand a response or kill the listener if denied by the OS.

The owned `ImagePrefetcher` may begin a new source batch only when the runtime is active and the owning GUI has neither foreground loading nor a pending multi-display image-change/transition batch. The gate reads only already-published scalar state; it does not call GUI-owned Qt objects from the speculative response listener. It is checked *at each new source admission*, not just at the initial resume, so a previous derivative finishing during a new transition cannot spawn further work. **An already-admitted derivative may finish**; retain queued intents and byte budgets, do not invalidate a generation or cancel the prefetch worker. The existing final-display transition-complete resume reopens the pump **even when the latest lookahead adds no new requests** and retains bounded source ordering and 100 ms source spacing. No new timer, thread, periodic polling or reduced lookahead is permitted. This removes unnecessary CPU scheduling contention but does not prove that the larger, pre-existing dual-display regression is solved.

### Render-thread GL job QObject lifetime (R140)

`QQuickWindow.scheduleRenderJob(..., NoStage)` takes ownership of its `QRunnable` and deletes it on Qt's render thread, including after an optional one-shot. A Python QRunnable may retain only Python-owned GL retirement state, scalar reservation fields, and a thread-safe cancellation token. **Do not store a strong reference to any GUI-affine Qt object (`QQuickWindow`, GUI signal reporter, QObject parent, timer, or bound GUI slot) in such a job**: PySide wrapper refcounts can release on the render thread and invoke destruction of Qt timer-bearing GUI wrappers from the wrong thread. Resolve GUI-owned window/reporter through weak references only at execution, and fail closed if the runtime/window/receiver has retired. Render-thread completion may signal the GUI receiver through its existing explicitly queued Qt connection; stale reservation serials/generations are ignored. Never poll or cause a repaint to compensate. R139's weak-reference-only Python `QRunnable` subclass did not resolve the startup abort: `logs13afa0ec418.zip` reproduces the paired `QBasicTimer::stop` wrong-thread warnings and `Fatal Python error: Aborted`. **R140 MUST NOT pass a Python-defined QRunnable subclass into Qt-owned render-thread deletion**. Use `QRunnable.create(payload.run)` where `payload` is a plain Python object holding weak references to GUI-affine QObjects and a non-QObject scenegraph retirement owner. The GUI manager retains reporter and window lifetime; a queued job that Qt drops without executing cannot make a stale GUI callback. Qt remains the owner of the native runnable. R141 received operator-confirmed Windows clean-startup acceptance with no Qt timer warning; source tests alone would not have sufficed. Preserve the same weak-reference/Qt-native runnable design and continue the separate performance investigation.

### First-use GL and texture attribution (R142–R143)

**Correctness invariant (R143):** Every event name used inside Qt Quick `updatePaintNode()` must resolve in that module at actual execution, not merely parse and appear in a text assertion. R142 omitted the `FrameTraceEvent` import in `background_item.py`, so `--frame-trace` could prevent node creation with no logged Python traceback while Qt continued its frame cycles. The traced node-construction path is now executable under GPU-boundary doubles, and `tools/frame_trace_report.py` decodes paired first-use durations and reports a no-background-render anomaly when Qt cycles are present. This diagnostic repair must never change QSG node/GL ownership. The native texture bridge is untouched.

The existing opt-in binary `FrameTraceEvent` v1 adds event IDs **66–73** for paired retained scenegraph node creation, first background GL initialization, first frame of each transition run, and native image identity changes. Native completion's auxiliary field differentiates **1 = adopted existing GPU texture** from **2 = upload/new texture**. Only the already-enabled frame-trace path emits these markers; ordinary frame rendering, image selection and widget work must incur no new tracing computation. No new frame request, QTimer, worker, GL allocation or synchronous texture upload may be introduced just to collect evidence. Compare first-use spans against `QT_SYNC`/`QT_RENDER_PASS`, worker completion and per-display transition admission before attributing the observed dual-display regression. The operator accepted R141's crash fix; dual-display launch and transition smoothness remain physically rejected.

### Bounded idle transition-preparation ownership (R138)

The serial idle GL warm-up is optional, batch-idle-only and Qt `NoStage`-owned. Its 200 ms step spacing uses **only** `ThreadManager.single_shot` on the GUI thread. Schedule the bound `DisplayManager._admit_idle_warm_step` slot (never an anonymous closure) so the QTimer is parented to the runtime owner and registered against its generation. Retire its one pending handle on new reservations, active transitions and runtime teardown. No OS-thread `threading.Timer`, no independent recurring clock, and no repaint-for-warmup. Prefetch source-batch delayed callbacks are generation-tagged and checked at execution; stale-runtime deferrals must be cancellable through the same central timer registry. Preserve the historical deferred-Qt-delete callback-release guardrail (R-89). Do not attribute the 2026-10-09 reboot-dependent dual-display recovery to this preparation path; see the historical incident.
