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

`themes/dark.qss` is legacy structural stylesheet residue, not theme authority. Production Settings/tray code has
severed the loader/caller dependency; the surviving structure is owned by narrow renderers and semantic visual values
remain in `SettingsThemeSpec`. The real repository/build asset is still awaiting the Windows/PySide file-absent matrix
because GODZIP workspaces intentionally omit `themes/`. Do not restore a loader, copy the QSS blob/literals elsewhere,
use native-backdrop workarounds, or add a fail-open theme path. The complete permanent contract is
`Docs/Architecture/Settings_Theme_Architecture.md`.

## Runtime Widget Themes / semantic visuals

Runtime Widget Themes (`.srwtheme`) are separate from the Settings QWidget theme. They are **colour/semantic bundles only**. `Widgets -> General -> Style Overrides` contains Card Surface, Card Border, Header Fill and Card Border Width: the three colour edits fork a named Widget Theme into persisted `Custom`, while Border Width remains global geometry styling outside Widget Theme schema. Branded-header family colour swatches are retired; header Fill/Text/Border resolve through Widget Theme semantics instead of a Media/Gmail/Reddit/Steam Settings bucket. Existing non-header per-family colour swatches remain higher-precedence only when intentionally authored. `Reset All Colours to Theme` is an explicit operator normalization/cleanup action that normalizes ordinary Clock/Weather/Reddit/Gmail/Media/Steam family colour fields (and card alpha fields that make a colour explicit) back to canonical implicit-Inherit values; it never runs at startup and never changes the selected Widget Theme/Custom palette. Specialized optional visual roles are sparse and inherit through one resolver (`intentional family override -> exact role -> semantic parent -> local/current semantic value -> preserved fallback`); `local.*` roles are presentation context and never persistence. Visualizer-authored colours remain outside this generic reset/theme authority. The retained Context Menu has no family override and consumes the generation-scoped Widget Theme palette directly.

Settings-theme <-> Widget-theme linking is one persisted **bidirectional** stable-ID relationship. The same compact lock/unlock control appears on both theme catalogue pages. While locked, selecting either catalogue activates and persists the explicit paired theme on the other side; selection must never implicitly unlock. A theme without an available counterpart (including Widget `Custom`) requires Independent mode first. Display names are never a pairing authority. Theme Foundry may explicitly save a linked Widget counterpart only through the same deterministic Settings->Widget projection authority used by the curated mirror generator; the Settings theme must have a real stable catalogue identity first. Clock is semantic through shared `card.text` when its family swatch remains canonical. Abandonment Issues' archive/BACKLOG accent is the specialized `abandonment_issues.accent -> widget.accent` role; the block consumes that accent while its label consumes ordinary themed text for contrast.

Live Settings theme publication must distinguish Python wrapper lifetime from C++ QObject lifetime. Registries may use weak references for ownership, but before applying live QSS they must verify that the PySide wrapper still owns a valid C++ QObject and prune stale wrappers. A stale deleted wrapper is cleanup, not a renderer failure; an exception from a still-live renderer remains transaction-fatal and rolls the theme back.

Runtime cards remain the ordinary retained Qt Quick RGBA surface/border/shadow path. The rejected runtime Glass/Acrylic card experiment has no schema field, Surface Style override, card material Loader, background capture/layer, mask tree or cadence callback. The wallpaper/transition render node is directly composited under the display scene using the healthy pre-material topology, selectively restored while preserving the later Bidirectional theme/lifetime/C++ fixes. Settings-window Glass/Acrylic remains a separate native QWidget/HWND theme concern. The failed runtime-card experiments are preserved as negative-control history in `Docs/Historical_Bugs/Runtime_Card_Backdrop_Materials_Rejected_2026-09-02.md`.

The curated source pack currently contains 58 Settings themes and 58 deterministic colour-only Widget counterparts, including four deliberately light/white-adjacent themes and four silver/metal themes. Settings-theme filenames may legitimately retain `[Glass]`/`[Acrylic]` because those tags describe the Settings HWND. Widget counterpart display names and filenames omit those tags while preserving stable links back to the actual Settings-theme identity. Installed theme storage is the same machine-wide curated asset family as visualizer presets: source/dev reads `<repo-root>/themes`, while frozen/installed runtime reads `%ProgramData%\SRPSS\themes` and Widget Themes live under its `widgets/` child. Normal and Media Center installers seed/clean-replace that tree; Nuitka may bundle the source pack for build completeness, but frozen runtime does not merge the bundled extraction/app-local copy into the active catalogue.

Static assets use two intentional lanes. `ui/resources/assets.qrc` compiled to `ui/resources/assets_rc.py` embeds Settings-UI fonts/small QSS icons addressable as `:/ui/assets/...`. Runtime branded/widget imagery remains raw `images/` data and frozen builds must package that directory separately. Changing the QRC manifest requires regenerating `assets_rc.py`; adding a runtime logo such as `Steam_Logo_Cropped.png` does not belong in the QRC unless the asset architecture is deliberately changed.

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

SRPSS already has a bounded **real-3D foundation inside the accepted Qt Quick scene**; future 3D work must inspect and
reuse/extend this foundation where appropriate rather than creating a second renderer stack.

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
merely because two features both contain Z coordinates. Extract shared primitives when a real consumer justifies them;
defer speculative abstraction until another concrete consumer proves it.

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
content. Friend Pulse and Games You Follow both use this cache-first rule.

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

Retained Windows GSMTC event observation has a stricter ownership rule than ordinary burst IO. The manager, selected session and their subscription/remove tokens are created, rebound, detached and released only on one lazy ThreadManager-owned **affinity lane**. The general IO pool is not an apartment authority and the Qt UI thread must never clear retained WinRT wrappers. Native manager callbacks capture only a coarse edge and queue any session rebind back to that lane; session dirty callbacks remain presentation-neutral. Teardown fences the observation generation first, then synchronously executes detach/release on the affinity owner. This lane is Condition-driven and owns no polling cadence.

Source/developer runs and explicit debug/verbose runtime logging must persist recoverable native/SEH faulthandler output to `native_faults.log`; the dedicated diagnostic build uses `diagnostic_crash.log` and adds lifecycle breadcrumbs. Ordinary compiled non-diagnostic runs without explicit debug/verbose logging must not activate this native-fault companion. One-shot hang diagnostics may schedule `faulthandler.dump_traceback_later()` to their own file but may not call `faulthandler.enable()` or retarget the persistent native-fault stream.

Media transport is non-blocking at GUI ingress. Queue admission is not provider
success: GSMTC Play/Pause/Toggle/Previous/Next/seek publishes its asynchronous
Boolean or exception outcome to the single shared Media runtime owner, which
generation-fences it and then refreshes accepted state. Play/Pause capability is
the state-appropriate union of canonical GSMTC Play, Pause and Toggle controls;
seek position is an absolute 100 ns tick value.

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
Clock digital/analogue are the first required example.

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

All six current modes share a default/baseline 1.5 aspect and support two distinct CUSTOM operations:

```text
uniform_visual_scale
    wheel -> whole visualizer scales uniformly; viewport extent unchanged

viewport_extent
    left/right edge -> width only
    top/bottom edge -> height only
    corner -> width + height independently, opposite corner anchored
```

Viewport extent is world/layout playroom, not final-pixel X/Y stretch. All six current modes—Spectrum,
Oscilloscope, Sine, Bubble, DevCurve and Sphere—must reflow/adapt to wide/tall extents. Bubble's viewport bounds are spatial
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

The all-six-mode viewport capability policy is part of the destination contract and the core Bubble reflow path has landed.
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

Sphere is an **accepted experimental**, independently enabled sixth mode; existing profiles retain the original five enabled modes. The current representation is **Voxel Sphere (Experimental)**: a frameless transparent stepped-voxel shell using one static cube mesh and one static instance buffer with vertex-shader deformation. Its current musical behaviour—event-owned fragmentation/cohorts, stable four-corner population identity, sustained body growth, event-stepped tracer travel, continuous rotation and vocal-linked intake recoil—is a golden preservation target. Presentation or maintenance work may not reduce its reactivity/freshness or introduce ambient/private cadence.

Sphere remains architecturally isolated until the operator explicitly authorizes promotion into shared/permanent architecture. Its descriptor lazily resolves its Settings builder, capture, frame runtime and renderer; heavy implementation resources stay dormant while disabled and retire through the normal render-context lifecycle. Canonical state remains in the `sphere_*` namespace, while shared technical/Rainbow/bar-appearance ownership is explicitly opted out. Sphere currently resolves its hidden technical profile through canonical Spectrum settings; those resolved values are behavioural input and must be recorded before any future promotion. Sphere-local Taste The Rainbow is implemented independently inside the voxel renderer and does not make the shared Rainbow family an owner.

The reusable architectural asset is the **experimental host/isolation seam**—descriptor-driven lazy wiring, independent dormancy/retirement, private setting prefix and explicit shared-family opt-outs. It is suitable for future experimental modes. Sphere audio logic, voxel settings, shader semantics and mode-specific capability memberships are not a shared foundation and must not be generalized merely to make that seam look cleaner. All experimental modes use isolation by default until the operator explicitly authorizes promotion.

The only curated Sphere presets are **Glass Current** (Preset 1; accepted intake/transparent snapshot) and **Voxel Bloom** (Preset 2; accepted outtake/opaque presentation snapshot with shadow enabled). Dead experimental-era controls Block Relief, Bass Response, Mid Response, High Response, Energy Curve and Idle Drift are retired and stale state is forward-stripped; Base Rotation owns continuous idle rotation. The former Deformation × Block Reactivity coupling is migrated exactly to one Fragment Strength control plus independent Particle Distance, while Particle Amount changes only post-admission cohort population. Rainbow Ghosting is retired; Sphere-local Taste The Rainbow can independently colour Surfaces and Edges without shared-family ownership. Perspective Strength is Sphere-local and bounded `0..1`, where `1.0` is the accepted projection exactly and lower values only flatten toward orthographic. Edge Weight (`1.0`), Voxel Size Variation (`0.35`) and Tracer Color (`[255,242,194,255]`) expose the renderer's accepted pre-existing constants as Sphere-local presentation controls; those baseline values are visually equivalent to the previous hard-coded path. Optional Depth Shading defaults off and may only darken rear voxels from already-transformed depth in the existing draw; it adds no neighbouring-voxel sampling, extra pass or audio/geometry authority. Sphere Drop Shadow is now a flat-colour **projected voxel silhouette** that compiles the exact hero vertex shader, so rotation/deformation/tracer-local turns and detached intake/outtake positions cannot drift from the visible voxel geometry. Sphere-local Shadow Opacity (`1.0`), Softness (`0.18`), Distance (`1.0`) and Size (`1.0`) parameterize that pass; softness is one optional expanded instanced layer, not an FBO blur or shadow map. Recommended slider marks remain UI guidance matching Glass Current, not defaults. The accepted experimental preservation/isolation contract lives in `Docs/Reference/Sphere_Visualizer.md`.

## Visualizer preset catalogue ownership

Per-mode visualizer preset JSON files are **user-authored state**. Users may add arbitrary counts, delete presets down to one survivor, and leave sparse authored numbers such as `1, 5, 20`. Runtime compacts whatever authored presets exist into slider positions plus trailing Custom without renaming/deleting their files. Edit Preset resolves the real backing file; Save Preset As chooses a non-colliding authored number. Shipped preset manifests may support packaging/reconciliation but are never runtime authority over the user catalogue, and startup must never require authored numbers to be contiguous.

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

Glass Shatter, Exploding Tiles, Directional Pixel Accretion, Ink Bloom, Tendril Reveal and Melt Drip use the canonical catalog and lazy Quick host, initially deactivated pending operator acceptance. Glass uses closed beveled fracture prisms with independent optical material controls; Tiles use closed beveled cubes; Ink uses a raised vortical pigment mesh; Tendril couples branch tubes to the same Bezier-path canopy; and Melt ray-intersects a bounded implicit 3D liquid volume with advected source imagery and gravity drops. Crumble shares the fracture solids, with rough broken sides and parent-seam debris. Accretion uses bounded instanced translating micro-tiles. Slide Perspective Push remains one Slide motion option and uses a true tilted-plane projective mapping with sealed coverage. See `Docs/Reference/Transitions.md` for appearance, ownership and limits; live acceptance stays in `Current_Plan.md`.

Transitions resolve canonical settings/admission into immutable request/run state and lazy Quick rendering. Old
`GLCompositor*Transition` pixels are not destination authority after caller proof.

Slide has one canonical identity and four cardinal directions. Its frozen per-run `motion_style` is one of Linear,
Elastic, Wobble or Flex: endpoints sample the unmodified source/destination, each pixel has one image owner, and
Elastic's bounded late-arrival settlement samples destination coordinates relative to arrival without wrap strips.
Slide adds no effect-local timer, clock, worker or resource owner; true Perspective remains a separate 3D feature.

## Optional feature extension contracts

- The independently opt-in system-master-volume/mute OSD is an ordinary retained Qt Quick widget inside the single display scene. It shares the event-driven Core Audio endpoint/action authority with Media, coalesces notifications onto GUI publication, uses one event-owned visibility deadline/fade and the ordinary CUSTOM owner, and has no separate audio poll/endpoint/window. The old import-owned process-global mute runtime/poll is retired; do not restore it. See `Docs/Reference/System_Volume_OSD.md`.
- Games You Follow is the default-off `steam_progress`-identity ordinary Steam card for explicitly followed games. Its source uses the existing linked identity/key, globally date-ranked discovered news, secure identity-derived article action, verified cached art and a bounded account-private last-good cache. Initial complete coverage is followed by persisted-cursor maintenance of up to eight apps per refresh session. One retained Quick model and four grouped CUSTOM roles own presentation; no surrogate follow source or second Steam backend. See `Docs/Reference/Steam_Games_You_Follow.md`.
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

- `Current_Plan.md`: current checkpoint/work/next/debt;
- `Spec.md`: durable product/architecture;
- focused docs/guardrails: durable subsystem contracts;
- `Docs/TestSuite.md`: live test inventory/status ledger;
- `Docs/Architecture/Persisted_Input_Compatibility.md`: persisted-input compatibility-bridge guard (user-data protection, horizon-gated);
- `Future_Work.md`: deferred features;
- `FWPlan.md`: operator-activated Future Work implementation and validation checklists;
- `Docs/Historical_Bugs/`: durable regression/failed-method history; ordinary chronology remains in source control.
