# SRPSS Specification

Last updated: 2026-09-04

Canonical durable architecture and product-behavior contracts. `Current_Plan.md` owns sequence; independent closure
narrative belongs under `Docs/audits/` or historical evidence.

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

## Migration epoch

The legacy `DisplayWidget` / QRhiWidget / `GLCompositorWidget` physical path was removed by H after caller proof established
the Quick destination as sole production authority. It is not rollback architecture and must not be restored as a facade or
fallback.

**Pre-H product continuity is not a migration requirement.** The old path must not be preserved, rebuilt or expanded
merely to keep a half-migrated screensaver functional. Caller-dead old pixels/helpers should retire as soon as their
replacement owns the contract. H wired the destination production owner, removed the remaining physical host and closed post-cutover runtime/performance acceptance; I is
caller-proven residue only; J is final visual/installed/physical acceptance and residual evidence-driven performance polish.

## Settings themes / native backdrop

Settings remains a frameless translucent QWidget top-level. `SettingsThemeSpec` schema v5 is the semantic visual
authority and compiled Default Dark is the unconditional no-file fallback. Complete `.srtheme` files may request
`off`, `acrylic` or `glass` and must pass strict whole-theme validation.

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

`themes/dark.qss` is legacy stylesheet residue, not theme authority. Its guarded retirement is in `Future_Cleanup.md`.
The complete permanent contract is `Docs/Settings_Theme_Architecture.md`.

## Runtime Widget Themes / semantic visuals

Runtime Widget Themes (`.srwtheme`) are separate from the Settings QWidget theme. They are **colour/semantic bundles only**. `Widgets -> General -> Style Overrides` contains Card Surface, Card Border, Header Fill and Card Border Width: the three colour edits fork a named Widget Theme into persisted `Custom`, while Border Width remains global geometry styling outside Widget Theme schema. Branded-header family colour swatches are retired; header Fill/Text/Border resolve through Widget Theme semantics instead of a Media/Gmail/Reddit/Steam Settings bucket. Existing non-header per-family colour swatches remain higher-precedence only when intentionally authored. `Reset All Colours to Theme` is an explicit operator migration/cleanup action that normalizes ordinary Clock/Weather/Reddit/Gmail/Media/Steam family colour fields (and card alpha fields that make a colour explicit) back to canonical implicit-Inherit values; it never runs at startup and never changes the selected Widget Theme/Custom palette. Specialized optional visual roles are sparse and inherit through one resolver (`intentional family override -> exact role -> semantic parent -> local/current semantic value -> preserved fallback`); `local.*` roles are presentation context and never persistence. Visualizer-authored colours remain outside this generic reset/theme authority. The retained Context Menu has no family override and consumes the generation-scoped Widget Theme palette directly.

Settings-theme <-> Widget-theme linking is one persisted **bidirectional** stable-ID relationship. The same compact lock/unlock control appears on both theme catalogue pages. While locked, selecting either catalogue activates and persists the explicit paired theme on the other side; selection must never implicitly unlock. A theme without an available counterpart (including Widget `Custom`) requires Independent mode first. Display names are never a pairing authority. Theme Foundry may explicitly save a linked Widget counterpart only through the same deterministic Settings->Widget projection authority used by the curated mirror generator; the Settings theme must have a real stable catalogue identity first. Clock is semantic through shared `card.text` when its family swatch remains canonical. Abandonment Issues' archive/BACKLOG accent is the specialized `abandonment_issues.accent -> widget.accent` role; the block consumes that accent while its label consumes ordinary themed text for contrast.

Live Settings theme publication must distinguish Python wrapper lifetime from C++ QObject lifetime. Registries may use weak references for ownership, but before applying live QSS they must verify that the PySide wrapper still owns a valid C++ QObject and prune stale wrappers. A stale deleted wrapper is cleanup, not a renderer failure; an exception from a still-live renderer remains transaction-fatal and rolls the theme back.

Runtime cards remain the ordinary retained Qt Quick RGBA surface/border/shadow path. The rejected runtime Glass/Acrylic card experiment has no schema field, Surface Style override, card material Loader, background capture/layer, mask tree or cadence callback. The wallpaper/transition render node is directly composited under the display scene using the healthy pre-material topology, selectively restored while preserving the later Bidirectional theme/lifetime/C++ fixes. Settings-window Glass/Acrylic remains a separate native QWidget/HWND theme concern. The failed runtime-card experiments are historical evidence only in `Docs/QtQuick_Migration/Rejected_Card_Material_Experiments_2026-09-02.md`.

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
- Achievement Pulse: neutral Steam runtime/preparation/cache/selection ownership;
- Abandonment Issues: neutral Steam runtime/data/cache/rotation ownership.

Do not create services/managers merely for naming symmetry.

App volume is a Media-dependent scene-local accessory, not an independent widget-family capability. Its default
presentation is an **external right accessory lane inside the same retained `OverlayWidget` root** as the Media card.
`OverlayWidget.rightAccessoryExtent/rightAccessoryContent` reserves authored width beside the card; the card then keeps
its accepted ordinary content width while the accessory receives its own visible bounds/hit target and the whole Media
presentation still shares one outer geometry, uniform CUSTOM transform, lifecycle and display route. The display-level
ordinary-card shadow uses the card-only visual width and therefore does not expand over the accessory lane. The lane
exists only while Media plus provider app-volume capability are effective and is default-enabled by the Media setting.
It consumes the existing Media presentation model plus its one `MediaVolumeRuntimeService` lease/action seam. It does
**not** persist an independent CUSTOM child rect, own an independent monitor, create another retained presentation root,
or gain its own model/controller/poller/service. A future independently movable volume child would require a separately
approved geometry contract rather than being inferred from this accessory lane. Moving volume back inside the card is
likewise an explicit presentation option/feature, not a parity fallback, and must not steal the reclaimed Media card
content width.

## State / actions

Ordinary widgets support optional **Widget Glow on Hover** and **Widget Glow on Click** under Display -> Interaction.
One shared swatch inherits the active Widget Theme's `card.border` semantic by default (`input.widget_glow_color=null`);
an explicit RGBA choice persists until **Use Theme** clears it. Existing interaction/Ctrl/context-menu admission gates
the shared retained glow. Hover edges and admitted discrete presses trigger finite Quick animations; there is no new
poller, timer, worker or visualizer clock. Runtime theme colours resolve with the existing generation configuration.

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
-> process-engine image provider
-> retained Image source identity
```

No QPixmap worker transport, base64 churn, tempfile-per-update or unchanged-image reupload.

## Shadows / fade

Canonical direction is NW/N/NE/W/E/SW/S/SE, default SE, resolved in Python. No Text Blur, Intense mode,
`widgets.shadows.offset`, `shadowtuning.json`, or replacement hidden tuning. Ordinary card = cached retained
`RectangularShadow`; ordinary text = duplicate glyph + signed offset; whole-widget fade = one retained root opacity.
Clock analogue hard shadows are permanent family-authored exceptions under doc 11.

Settings-window theme/shadow ownership is separate from runtime overlay-widget shadow authority; see
`Docs/Settings_Theme_Architecture.md` and `ui/widgets/control_shadow.py`.

## Geometry / CUSTOM

Outer geometry is Python/session-owned. Variant key supports `(widget_id, display_identity, geometry_variant)`.
Clock digital/analogue are the first required example.

Edit-mode X changes working session only: duplicate removal or singleton ordinary-enabled OFF. Never family capability
deactivation. Save/Enter commits; Cancel restores pre-edit geometry/instances/enabled state.

Layout slots save/load ordinary visible-layout state, including ordinary ON/OFF, but never capability activation or
provider/account/source settings.

CUSTOM is a **global layout mode**. If any effective widget route is `Custom`, ordinary authored stacking and the
non-CUSTOM Media/Visualizer adjacency projection are disabled for the entire retained layout, not selectively per
widget. The same subsystem switch is asserted before live Edit Layout captures geometry and before number-key layout
slot loads rebuild the runtime. While dormant, ordinary cards use base/committed rectangles and overlap is legal; an
uncommitted Visualizer uses Media's plain authored slot rather than the ordinary adjacent displacement. Cancel restores
authored packing only when no effective route remains `Custom`. This boundary is event-driven and owns no cadence.

## Visualizer geometry

`VisualizerLogicalRuntime` remains sole mode-general authored visualizer clock. Quick presentation does not own
simulation cadence.

All six current modes share a default/baseline 1.5 aspect and support two distinct CUSTOM operations:

```text
uniform_visual_scale
    wheel/corner -> whole visualizer scales uniformly; viewport extent unchanged

viewport_extent
    left/right edge -> width only
    top/bottom edge -> height only
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
rendered-overlap and event test under BTF.

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
During a live edit, the working rectangle also owns its preview scale. Normal logical-frame publications cannot
restore the saved size at the new dragged origin; independently rounded axes must admit the same uniform scale.

Sine/Oscilloscope glow spreads perpendicular to the curve and scales with visible content area relative to
420x280. A huge saved world at a small uniform scale must not weaken a halo on the same visible footprint.
Glow size/intensity and line-core antialiasing remain independent.

Sphere is an experimental, independently enabled sixth mode; existing profiles retain the original five enabled
modes. Its frameless transparent viewport contains a static 3D mesh with authored-time deformation, reconstructed
normals and material-specific bump/roughness. Chrome, Obsidian, Magma, Silver and Water have curated presets plus
Custom. Independent controls shape band/vocal-range deformation, whole-body transient size response, base bump and
reactive bump. Magma adds diffuse fire, smoke, ash and lava drips; Water transmits the existing background and sheds
rounded 3D blobs. Static effect geometry is allocated only for an admitted material that uses it. Settings normalize
parameters once; current playing source identity gates both musical and transient energy, while idle motion
continues on the existing logical clock. A fixed camera/common pixel scale preserves aspect and reserves the full
canonical deformation envelope. Inactive renderer resources retire on one-shot render-context events, including a
mode change that never receives its first source frame. Detail and validation: `Docs/Future_Work/Sphere_Visualizer_Decomposition.md`.

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

Transitions resolve canonical settings/admission into immutable request/run state and lazy Quick rendering. Old
`GLCompositor*Transition` pixels are not destination authority after caller proof.

Slide has one canonical identity and four cardinal directions. Its frozen per-run `motion_style` is one of Linear,
Elastic, Wobble or Flex: endpoints sample the unmodified source/destination, each pixel has one image owner, and
Elastic's bounded late-arrival settlement samples destination coordinates relative to arrival without wrap strips.
Slide adds no effect-local timer, clock, worker or resource owner; true Perspective remains a separate 3D feature.

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

The H closure record is `Docs/QtQuick_Migration/H_Phase_Closure_2026-09-01.md`. Current migration epochs are:

- G: closed retained CUSTOM/input/auxiliary foundation;
- H: closed production Quick ownership + post-cutover physical/performance acceptance;
- I: closed caller-proven residue/test/tool/source reconciliation;
- current post-cutover P0: remove recurring Visualizer delivery hitches while preserving authored cadence/reactivity/freshness, with mode authority/dormancy established before deep active-path tuning;
- J/Parity+: remaining visual/compiled/installed/physical 1/2/N-display/DPR/topology acceptance plus evidence-driven residual performance work.

## Documentation roles

- `Current_Plan.md`: current checkpoint/work/next/debt;
- `Spec.md`: durable product/architecture;
- focused docs/guardrails: durable subsystem contracts;
- `Docs/audits/`: independent audit findings/closure evidence;
- `Docs/TestSuite.md`: live test inventory/status ledger;
- `Future_Cleanup.md`: deferred deletion/debt;
- `Future_Work.md`: deferred features;
- `FWPlan.md`: operator-activated Future Work implementation and validation checklists;
- historical records: history only.
