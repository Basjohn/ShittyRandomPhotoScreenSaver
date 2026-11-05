# Runtime Presentation Architecture

## 1. Decision

SRPSS's accepted runtime presentation architecture is:

```text
one physical display
        ↓
one standalone top-level QQuickWindow
        ↓
threaded Qt Quick scene graph
        ↓
one composed runtime scene
        ↓
physical presentation
```

The one-surface Quick design was physically compared against the former QWidget/QRhiWidget reference and accepted under both light and heavy external load.

This decision is closed unless new production evidence contradicts it.

## 2. Retired physical path

The accepted Quick runtime replaced the former physical presenter after caller proof:

```text
DisplayWidget
   └── GLCompositorWidget
          └── OpenGL QRhiWidget path
```

Those classes are historical topology only and are absent from production source. Caller-dead family/CUSTOM/auxiliary/transition/visualizer pixel ownership retired with that physical-host edge.

Do not:

- restore the old presenter for compatibility or test convenience;
- create new QRhiWidget-specific architecture;
- treat old class names as permanent product contracts;
- add a production runtime switch between old and Quick presenters.

Installed product acceptance belongs to the current Quick runtime and its maintained tests/physical evidence, not to reconstruction of the retired host.

## 3. One-surface invariant

Each physical display owns one independently presented accelerated runtime surface.

Allowed inside that surface:

- retained base image;
- transition rendering;
- visualizer content;
- optional retained visualizer shell/chrome;
- runtime overlays;
- retained Quick widgets;
- inline custom render nodes.

Forbidden:

- separate native visualizer window;
- transparent accelerated overlay window;
- per-widget accelerated top-level surface;
- `QQuickWidget` as the runtime presenter;
- per-effect fallback to an independently presented old surface.

A frameless visualizer mode is still part of this one surface. `FRAMELESS` means the visualizer omits
its own card fill/frame/shadow; it does not mean a separate window or display-global renderer.

## 4. Threading model

The current presenter requires the Qt Quick **threaded** scene-graph render loop on the supported
Windows path.

The GUI thread remains responsible for GUI/event-loop work and may prepare/publish synchronized state.

The Quick render thread owns custom rendering according to the selected inline scene-graph primitive.

Do not move visualizer logical simulation onto the render thread merely because a render thread exists.

`VisualizerLogicalRuntime` remains independent and authoritative for authored visualizer time.

## 5. State flow

Conceptual flow:

```text
models / providers / logical runtimes
        ↓
bounded immutable/latest render state
        ↓
Quick scene synchronization boundary
        ↓
render-thread scene consumption
        ↓
physical presentation
```

Properties:

- latest-state semantics;
- no FIFO/catch-up;
- no producer wait for paint/present;
- no paint acknowledgement;
- no callback-per-logical-frame requirement;
- generation fencing;
- stale-state rejection.

The exact bounded GUI→Quick synchronization object may vary by owner, but those semantics may not.

## 6. Selected renderer primitives

The ordinary retained-presentation primitive is normal Qt Quick items/components.

The selected SRPSS custom-OpenGL primitive is:

```text
QQuickItem(ItemHasContents)
    -> updatePaintNode()
    -> QSGRenderNode
    -> direct OpenGL inside the owning QQuickWindow scene
```

This choice is the current custom-render contract for transitions and the visualizer.

Why this is the selected path:

- custom rendering stays inline in the one scene;
- correct stacking with retained Quick content;
- no extra offscreen texture/composite pass solely to reinsert the effect;
- supports existing shaders, meshes, depth, VAOs/VBOs, and context-local resources;
- preserves one physical presentation surface.

`QQuickRhiItem` is not the normal/final SRPSS custom-render path. `QQuickWidget` is prohibited.

If pinned PySide/compiled-product evidence proves the selected `QSGRenderNode` seam fundamentally
unusable, stop and deliberately revise the **single** custom-render primitive. Do not keep multiple
product primitives as compatibility fallbacks.

A localized native/C++ renderer may be considered only if profiling of the current implementation
proves a specific Python render callback materially limits the result. It must stay inside the same
QQuickWindow/scene ownership.

## 7. Visualizer

The visualizer remains split:

```text
source/audio
   ↓
VisualizerLogicalRuntime
   ↓
latest immutable logical/render state
   ↓
Quick visualizer item synchronization
   ↓
QSGRenderNode custom GL
```

The logical runtime never mutates Quick scene objects or GPU resources.

The presenter never advances authored visualizer simulation.

### 7.1 Shell policy

Card existence is a presentation policy, not a universal visualizer invariant.

Modes whose descriptor selects the shared card policy use:

```text
shell_policy = CARD
clip_policy  = CARD_INTERIOR
```

A future explicitly authored mode may use:

```text
shell_policy = FRAMELESS
clip_policy  = VIEWPORT_RECT
```

Carded modes use retained Quick card fill/shadow/frame around the custom-GL content. Frameless modes
omit that chrome while preserving the same Quick visualizer root, fade/lifecycle authority and
assigned viewport.

### 7.2 Content clipping

For current carded modes, custom GL must remain above card fill, below the visible frame/border, and
inside the rounded inner card path.

The selected clip ownership is **one render-node-local SDF/stencil host** inside the same
`QQuickWindow`/`QSGRenderNode`. The `QSGClipNode -> QSGRenderNode` handoff was attempted under PySide 6.9.1
and failed that runtime's bar (rounded cases exposed stencil metadata not matching framebuffer contents;
rectangular cases could expose an invalid sentinel scissor). A proposal to replace the current clip owner must first repeat that proof on the current runtime;
version advancement by itself does not reopen the failed handoff. The failed handoff is not a selectable implementation and
is not a fallback. The local host still composes with valid inherited scissor/stencil state when it
genuinely corresponds to real framebuffer contents, and restores every touched state; it does not
assume it owns a blank stencil buffer.

Do not shrink visualizer render geometry to simulate clipping and do not copy old centred-QPainter
border-mask constants into Quick.

### 7.3 Geometry

One visualizer geometry authority feeds retained shell/chrome, clip geometry, custom GL, DPR and CUSTOM/Edit. Its ordinary
runtime base is the committed presentation geometry; an active CUSTOM session may supply a temporary working override.
Those are precedence levels within one geometry/configuration contract, not competing writable authorities.

Modes using the shared card policy share one canonical baseline viewport aspect. Mode changes and Visualizer presets do not change it.

The old per-mode card-height/growth controls are not current geometry:

```text
spectrum_growth
osc_growth
bubble_growth
devcurve_growth
```

Destination geometry keeps separate:

```text
canonical baseline viewport/aspect
uniform_visual_scale
viewport_extent
```

Scroll-wheel and corner-handle resize change uniform whole-visualizer scale and preserve the baseline
aspect.

Required retained CUSTOM left/right edge resize changes viewport width only, while top/bottom edge resize changes
viewport height only, at unchanged visual scale. That changes available mode playroom rather than stretching final
rendered pixels. Every registered mode must remain viewport-resize-capable through its declared policy; carded and frameless policies adapt their own authored domain rather than stretching finished pixels.

Where a logical mode needs spatial bounds, the effective viewport metrics are configuration input to the logical side and
never another clock. Outside CUSTOM the committed extent is truth; while editing, the working CUSTOM extent temporarily
overrides it. Save leaves the newly committed extent active, Cancel restores the pre-edit committed extent, and ending
CUSTOM does not imply canonical `(420,280)`. Bubble must preserve round geometry, motion/collision semantics and BTF as the
domain changes.

## 8. Runtime overlays

Providers/models/settings do not move merely because pixel ownership changes.

Current pattern:

```text
existing Python data/model/action owner
        ↓
small generation-scoped presentation state
        ↓
retained Quick runtime item/layer
```

Same-scene dimming/pixel shift and retained context-menu presentation are current architecture. Cursor Halo is deliberately **outside** the composited scene: `QuickCursorController` supplies one native `QCursor`, so physical pointer motion cannot dirty wallpaper/Visualizer pixels. Avoid reimplementing network/provider/business/settings authority in QML. Any remaining caller-dead QWidget/top-level auxiliary pixels are cleanup residue, not a second presentation path.

The one Quick scene owns runtime pixels that visually coexist over the screensaver.

### Retained OSD and future transition extension

The implemented, independently enabled system-volume OSD is an ordinary retained Quick widget **inside the existing per-display scene**, not a new physical surface or a QML input/polling cadence. The shared event-driven Core Audio/COM source owns its data; the OSD resolves one coalesced snapshot and event-owned visibility. Enabled CUSTOM Edit may show its shell without a new audio event; disabled state must not construct that shell. See `Docs/Reference/System_Volume_OSD.md` for the current product and lifecycle contract.

A new transition identity should be registered in the current canonical transition catalog and lazily resolved by `rendering/quick/transitions/implementation_registry.py` through the existing Quick render host. Keep effect-specific GPU objects private and dormant while off; integration does **not** mean copying shaders/resources into the shared controller or building a parallel experimental compositor. Slide modifiers belong to the existing Slide owner. Voxel Sphere is a separate accepted Visualizer mode with its own preserved contract.

## 9. Readiness / first frame

A runtime window must not be visibly exposed until it can show intentional current-generation content.

Preserve:

- no white/default flash;
- no black placeholder;
- no stale image/texture pop;
- no visualizer/shell flash;
- coordinated multi-display reveal that is never held by a stalled or failed sibling, and never opens a display before its own first wallpaper (Contracts § Startup composition).

Separate:

```text
presentation_ready
reactive_source_ready
```

Do not make real audio/source freshness a universal prerequisite for an intentional idle scene.

Readiness depends only on resources required by the resolved presentation policy; a frameless mode does
not wait for card resources it does not own.

## 10. Lifecycle

Topology, Settings/recreate, Edit, and shutdown remain generation-owned.

Old generation retires before replacement gains authority.

Successful Visualizer retirement joins its sole logical runtime, releases its engine lease and detaches presentation routes
before dropping Quick-runtime references. A failed join retains ownership and blocks display retirement. A display unit drops
its runtime/presenter edges only at the real `retirement_completed` boundary, retaining scalar identity for diagnostics.
This breaks signal-callback cycles even for a startup-frozen Python generation; neither forced collection nor a longer
destruction-barrier deadline is a release authority.

Quick scene/render resources are destroyed on the legal render/context owner for the selected
`QSGRenderNode` contract.

Do not copy QRhiWidget-specific context assumptions into Quick.

Generation `0` remains valid.

### Display power

Before 5 Nov 2026 nothing listened for display power: a power-plan display-off (or an HDMI panel that stays enumerated)
left the logical tick, render thread, transitions and rotation running all night (Waveform Preset 1, invisible MC
run: ~142% of a core and ~10% GPU, 51 swaps/s and 90 publishes/s with the displays "off").

**Authority.** `core.display_power.DisplayPowerAuthority`, owned by the process-scoped `ScreensaverEngine`
(`initialize` → `cleanup`), is the only display-power listener. Windows: `core.windows.display_power_notifier` registers
one message-only window for `GUID_CONSOLE_DISPLAY_STATE` and receives `WM_POWERBROADCAST` / `PBT_POWERSETTINGCHANGE`
through the GUI thread's ordinary pump (0 off, 1 on, 2 dimmed = on; Windows also sends the current state at
registration). Linux: GNOME Mutter `PowerSaveMode` over a blocking D-Bus `PropertiesChanged` listener on a ThreadManager
lane, else the explicit inert backend (always on, one `[PLATFORM]` line). `deliver()` records the latest state and queues
one dispatch: every state before that dispatch collapses into it, and one that ends where the authority already is emits
nothing (no rebuild loop on an off→on→off burst). Each emitted edge carries a new `generation`; the engine and
`DisplayManager` drop older ones. No timer, polling or environment flag.

**Off pauses** (engine `_on_display_power_changed` → `DisplayManager.set_display_power`):

- rotation: the engine's rotation timer stops;
- transitions: each live `QuickDisplayRuntime.set_display_power(False)` snaps an in-flight run to its authored
  destination once (`cancel_current`) and suspends `QuickFramePacer` demand (`power_suspended`, independent of the
  visibility pause, so neither can restart the other's frames); a run admitted while off finishes on its own deadline
  timer without frames;
- Visualizer: `QuickDisplayVisualizerOwner.set_display_power(False)` parks the sole logical runtime (its thread blocks
  on an event with no timeout; the call returns once no step is in flight), drops the unread publication and releases
  the owner's engine reference (the last one stops capture and analysis). The park request lives on the
  `VisualizerRuntimeController`, so a runtime started while off (activation, restart) starts parked;
- Clock: `GlobalClockTicker` stops, so no 1 Hz frame of the whole scene (heavy Visualizer included) is rendered.

**Keeps running:** windows stay shown and bound (wake input must reach them; hiding would expose the desktop and churn
the scene graph); topology stays with the monitor reconciler; data providers (Media, Feeds, Steam, Weather, Gmail,
Reddit, System Stats) keep their own cadence, and a content change still renders one frame; pixel shift (one shift per
configured minute) and the `--usage` sampler continue. Measured cost while off (same run): ~4% of a core median, GPU
~0-1%, ~0.6 swaps/s, 0 publishes/s.

**On resumes:** the engine reference and capture return, `arm_reentry_fresh_frame_fence` keeps a retained pre-off
audio frame from being the first reactive result, `rebase_logical_clocks_after_park` resets every logical last-step
clock (tick state plus each mode state's `rebase_clock()`) so the first resumed step integrates no parked gap while all
simulation state stays warm, and the runtime resumes on a fresh deadline sequence (the parked interval is not counted as
skipped deadlines). The clock ticks at once, then every second; rotation restarts from a full interval (a fresh hold,
never a catch-up). Pure wall-time functions (Auto Rotate pose, shader time) simply read the current time.

**Interactions.** A generation built while off (topology rebuild, Settings return) inherits the state: new units suspend
their pacer, the Visualizer owner parks before `start`, and `engine.start()` leaves rotation waiting. Exit while off
retires normally (`stop()` releases a parked loop). MC (windowed) and the secure-desktop run use the same engine path.

**Limit.** Windows exposes the console (session) display state, not per-monitor power. A monitor switched off at its own
button over DisplayPort usually leaves the topology and already pauses through binding loss; an HDMI panel switched off at
its button that stays enumerated is not observable and keeps running. Evidence and the injection probe:
`tools/visualizer_live_check.py --display-off AT:FOR` (`.artifacts/evidence/display_power/`); tests
`tests/test_display_power.py`, `tests/test_linux_display_power.py`.

## 11. Transition model

Transition request/run semantics are display-local, immutable, monotonic, and exactly-once for
completion/cancellation.

Canonical transition implementations resolve lazily and render through the display's inline Quick
custom-render owner. Existing authored shader/math is preserved where valid.

Do not individually retune transitions to hide physical frame holes.

## 12. Evidence bar

Physical presentation is judged primarily by:

- p95/p99/max physical gaps;
- severe-gap counts;
- continuity;
- load resilience;
- correct per-display refresh behaviour.

Internal render callbacks are not physical-display proof.

The accepted one-surface result selects the architecture. Later evidence is for implementation quality, not for
re-litigating Quick versus the old presenter on every step.
