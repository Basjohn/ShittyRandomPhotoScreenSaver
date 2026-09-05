# Visualizer Presentation Guardrails

Last updated: 2026-09-02

Read for visualizer cadence, source freshness, render state, fade/readiness, shell/clip policy,
geometry, and presentation work.

For Bubble also read `Docs/Guardrails/Bubble_Temporal_Fidelity.md`.
For any performance-motivated change also read `Docs/Guardrails/Performance_Optimization_Contract.md`; it makes freshness/reactivity and R-69 explicit admission vetoes, not post-hoc checks.

## 1. Ownership

Accepted direction:

```text
audio / analysis
        ↓
VisualizerLogicalRuntime
        ↓ latest logical/render state
Quick presentation bridge
        ↓
display QQuickWindow scene/render owner
        ↓
physical presentation
```

`VisualizerLogicalRuntime` remains the sole authored visualizer clock.

It owns:

- authored deadline/dt;
- source snapshot consumption;
- mode simulation;
- envelopes/events/transients;
- visual-only logical motion;
- latest plain-data publication.

It does **not** mutate:

- QWidget;
- QQuickItem/QObject scene state directly from the worker;
- QPixmap/QPainter;
- GPU/GL/RHI resources.

### Configuration ownership follows the consumer

Do not classify visualizer settings by legacy widget field location, Settings subsection, or by whether a name sounds
"visual" or "technical". If authored logical evolution or a Spectrum/Oscilloscope/Sine/Bubble/DevCurve mode-owned logical
frame runtime consumes the value, the value must be available through presentation-neutral resolved logical/runtime
configuration. Renderer-only colour/glow/card/chrome/style remains presentation-owned. Do not solve missing neutral
configuration by copying every `SpotifyVisualizerWidget` attribute into the controller.

The canonical resolved technical cache is also split by consumer:

- floor/sensitivity/audio-block/dynamic-range/AGC/input-gain/kick-lane and similar DSP inputs go through the **single
  controller-owned shared BeatEngine/audio-worker boundary**;
- transient pulse/clamp and mode transient-mix values consumed by authored logical evolution live on controller-owned logical
  state even though their settings provenance is "technical";
- bar-count changes must keep controller `bar_count`, shared-engine reconfiguration/generation, and the logical display-bar
  mirror/freshness state coherent;
- legacy overlay mirrors do not survive merely because the old QWidget technical applier wrote them.

Needing the shared BeatEngine is not a reason to retain a QWidget owner.

Accepted audio-analysis ownership after H is one persistent serial `visualizer.audio_analysis` compute lane: one packet executing, at most one newest pending source replacement, retained detached DSP state across ordinary frames, explicit config/activation/reset epoch invalidation, and stale-result rejection across an epoch boundary. There is no generic per-frame Future/task fallback. Preserve the small stable previous-bars packet snapshot unless a replacement correctness proof removes the live-list mutation race.

## 2. One logical clock

Forbidden logical owners:

- recurring GUI visualizer timer;
- AnimationManager visualizer listener;
- per-mode logical timer/thread;
- physical compositor/render timer;
- Quick animation driver as simulation authority.

Qt Quick may present at display cadence while logical simulation remains independently authored.

## 3. Latest-state rule

Latest wins after authored integration.

No:

- FIFO;
- backlog;
- catch-up;
- one GUI callback per logical publication as a requirement;
- paint/present acknowledgement.

Protected short-lived visible edges require explicit survival tests.

## 4. Quick presentation bridge

The GUI/Quick boundary must be:

- bounded;
- latest-state oriented;
- generation-fenced;
- safe for Quick scene/render-thread ownership;
- independent of physical paint completion.

The migration removes obsolete GUI `present_tick`/QRhiWidget ownership as pixels move to Quick rather
than wrapping it permanently inside another layer.

### Bridge population is an ownership bar

A `VisualizerSnapshotBridge` connected to the Quick item is not sufficient. Exactly one GUI/Quick synchronization owner must:

```text
latest VisualizerLogicalFrame
+ current resolved presentation state
-> identity-fenced VisualizerRenderSnapshot
-> existing bridge
-> retained Quick visualizer consumer
```

It may coalesce latest state. It may not add a second timer/cadence, FIFO/catch-up queue, producer wait, paint acknowledgement
or call into legacy `present_tick()`/QWidget/compositor presentation. The resolved presentation record used to compose the
snapshot must also be committed to the retained item at the same synchronization boundary so geometry/policy cannot be resolved
twice into conflicting states.

A test that calls `VisualizerSnapshotBridge.take_for_render()` directly proves the bridge contract only. Destination delivery
requires the real retained `VisualizerRenderItem`/render-node synchronization path to admit the exact identity-fenced snapshot.

## 5. Physical presentation

The display's standalone `QQuickWindow` is the sole accelerated runtime presentation surface.

No:

- visualizer native overlay window;
- visualizer `QQuickWidget`;
- second accelerated surface;
- separate visualizer swap/vsync owner.

## 6. Shell policy is not mode rendering

Do not hard-code "visualizer always owns a card" into the render host.

Resolve a lightweight presentation policy before render-thread admission.

Minimum policies:

```text
shell:
    CARD
    FRAMELESS

clip:
    CARD_INTERIOR
    VIEWPORT_RECT
```

All current five modes remain:

```text
CARD + CARD_INTERIOR
```

A future explicitly authored frameless mode may use:

```text
FRAMELESS + VIEWPORT_RECT
```

`FRAMELESS` removes card background/frame/shadow only. It does not create a new native window and does
not grant unrestricted display-wide drawing.

Shell policy must not become a second playback/mode clock.

## 7. Clip contract

Carded custom-GL content must remain:

```text
above card fill
below visible frame/border
inside rounded inner card path
```

Historical R-21 is binding evidence that shrinking the GL render rect to hide bleed is wrong because
it changes authored content geometry.

The exact pinned PySide 6.9.1 scene-graph clip-node proof failed. Current Quick ownership is one
render-node-local SDF/stencil host:

- `CARD_INTERIOR` uses the rounded canonical inner-card geometry;
- `VIEWPORT_RECT` uses the same host with zero radius;
- the host and mode draw use the same render-target viewport;
- valid inherited scissor/stencil state that genuinely corresponds to real framebuffer contents is
  honored (composed with, not cleared); the failed `QSGClipNode` handoff proved arbitrary PySide clip
  metadata is not trustworthy, so this is only the narrower compose-with-valid-state guarantee;
- direct GL does not clear or overwrite scene-graph clip contents as if it owned the framebuffer;
- temporary stencil contents and every touched direct-GL state are restored.

Do not preserve the failed clip-node route as a second selectable implementation.

## 8. Card interior geometry

Do not copy QWidget/QPainter mask constants into Quick.

Historical centred-pen math such as:

```text
1px inset + border_width / 2
```

was specific to the old painted-card implementation.

Qt Quick card border geometry is different; derive the content clip from the actual retained Quick
shell.

One canonical geometry authority owns:

- outer card;
- border width;
- inner content path;
- inner radius;
- content rect;
- DPR.

Card frame and custom GL may not use competing geometry calculations.

## 9. Geometry: one baseline aspect; scale and viewport extent are distinct

All five current modes share one canonical baseline viewport aspect in the Quick architecture. Mode changes and mode presets do not resize that baseline viewport. The legacy per-mode `spectrum_growth`, `osc_growth`, `sine_wave_growth`, `bubble_growth`, and `devcurve_growth` card-height controls are retired and must not be copied into Quick.

The visualizer geometry model must distinguish:

```text
uniform_visual_scale
```

from:

```text
content_viewport_size / extent
```

Uniform scale changes the whole authored visual size while preserving the canonical baseline aspect. Scroll-wheel and corner-handle resize use uniform scale.

Viewport extent changes how much layout/world is available. The required retained CUSTOM edge operations change one viewport axis independently:

```text
left/right edge -> viewport width only
top/bottom edge -> viewport height only
```

All five current production modes must support this destination operation, including Bubble. The core capability policy is
landed for all five modes; do not reintroduce a false Bubble gate as a workaround for viewport defects.

Do not implement wide/tall visualizers by stretching a rendered texture or scaling X and Y independently. Do not use a
retired per-mode growth value as a hidden viewport-extent alias.

Where a logical mode needs spatial bounds, viewport metrics enter the logical runtime as configuration. Ordinary committed
extent is truth outside edit mode; an active CUSTOM working extent is a temporary higher-precedence override. Save commits
the new extent, Cancel restores the old committed extent, and ending CUSTOM removes the override without assuming canonical
`(420,280)`. Bubble is the strict case: positions/trails reflow through the expanded logical world, circles remain round,
and authored render radius uses the operator-authorized equal-area response height
`sqrt(content_width * content_height / 1.5)` rather than actual-height coupling or a baseline/current cap. Velocity,
collision and BTF semantics stay coherent: collision/spawn radii and collision-only gap/correction distances multiply by
`domain_h` when mapped back into the expanded world, with an exact canonical 1x1 no-op. Geometry never becomes a clock.

## 9A. Extreme viewport scaling contract — axis, amplitude and time are separate

Edge resizing changes `viewport_extent`; it does **not** grant permission to apply one generic "large viewport" multiplier to every reaction. For every mode/effect, identify all five quantities separately:

```text
1. authored logical/normalized response
2. viewport/world geometry (width and height independently)
3. uniform visual scale (stroke/radius/pixel-like authored size)
4. temporal response (smoothing, decay, hysteresis, travel rate)
5. final physical-pixel displacement/velocity
```

A bigger physical displacement is not automatically a bug. Wide/tall CUSTOM viewports are allowed to make authored normalized motion occupy more pixels. Compensation is justified only for a **proven presentation-temporal failure** (aliasing/flicker/rate-zone change/etc.), and then only on the axis and channel that causes it. Never compensate twice by changing both source magnitude and presentation timing.

Axis rules:

- a Y-only effect may use viewport **height** when a proven temporal correction is required; width alone must not alter it;
- an X-only effect may use viewport **width** when a proven temporal correction is required; height alone must not alter it;
- an isotropic 2-D effect may use both axes only when its actual geometry requires both; do not casually use `max(width_ratio, height_ratio)` as a generic "large viewport" proxy;
- stroke widths, glow radii and other pixel-like authored sizes normally follow `uniform_visual_scale`, not edge-expanded viewport extent;
- BeatEngine/DSP/source magnitude is upstream authored signal and must not be attenuated to hide a renderer/presentation scaling defect.

Current five-mode audit (2026-09-02):

| Mode | Edge-expanded geometry | Temporal/scaling status | Guardrail |
| --- | --- | --- | --- |
| **Spectrum** | Bars fill the current vertical field; width changes bar distribution/width, height changes bar travel distance and renderer segment density. | **R-76 proven/fixed:** live Quick visual smoothing scales from expanded vertical bar-field height only; continuous-bar hysteresis uses one canonical internal temporal segment domain. | Width alone must not slow bars. Do not also change BeatEngine, `0.55` transfer, height boost or peak lifetime without separate evidence. |
| **Bubble** | Logical world expands independently on X/Y; positions/trails/collisions project through that world while heads stay circular and renderer head response remains authored. | R-69/BTF already cover viewport projection. No new temporal multiplier is admitted by this audit. | Never globally compress head/Ghost radius, motion or amplitude because the viewport is large. Ripple-wake correction is a narrowly separate presentation footprint contract. |
| **Oscilloscope** | Waveform X spans the current width; waveform amplitude/line placement uses the current vertical field. Vertical line-spacing control scales with height; line/glow thickness follows uniform scale. | 60/120 ms energy filtering and waveform blend remain authored/viewport-neutral. Continuous antialiased curves naturally traverse more pixels in a taller card; no source-proven flicker seam was found. | Do not pre-emptively slow/attenuate the waveform for tall cards. If physical tall-only strobing is observed, trace Y displacement first and apply at most one height-local presentation correction. |
| **Sine** | Wave/amplitude is normalized into current height; phase/travel spans current width; vertical line spacing scales with height; line/glow thickness follows uniform scale. | Reactivity/envelopes are viewport-neutral. Extreme width therefore increases physical X travel per normalized phase and extreme height increases physical Y displacement, but current source contains no discrete viewport-dependent rate switch analogous to Spectrum. | Treat extreme-wide X travel and extreme-tall Y motion as **watchpoints**, not bugs. Any future fix must target the implicated axis/channel, never generic source sensitivity. |
| **DevCurve** | Four normalized curves fill the content rect. Quick explicitly rebases pixel-like outline/specular geometry with baseline/current normalized scales. | Solver energy smoothing/slope limits and foreground/specular travel are normalized-domain. Extreme width can increase physical X travel speed and extreme height can increase physical Y displacement, but no viewport-dependent temporal branch/reset was found. | Watch physical X travel/specular speed at very wide extents. Preserve the existing normalized-scale renderer correction; do not globally retune solver energy/amplitude. |

The audit conclusion is deliberately conservative: **Spectrum is the only additional source-proven temporal scaling bug in this pass.** Oscilloscope/Sine/DevCurve have plausible physical-pixel scaling watchpoints, but changing them without operator evidence would risk repeating the R-69 over-compensation failure. When a new extreme-aspect symptom appears, compare canonical / wide-only / tall-only / wide+tall using the same recorded logical input before tuning anything.

## 10. Readiness

Distinguish:

```text
presentation_ready
reactive_source_ready
```

Paused Spectrum may reveal presentation-owned idle state while source identity remains absent.

Readiness depends only on resources actually required by the resolved shell policy. A frameless mode
must not wait for card resources it does not own.

On Play, fresh current-generation/current-activation data replaces idle state in place.

## 11. Fade

One authored fade authority applies to the complete visualizer presentation root (the single
animation/progress owned by `presentation_fade`).

That one authority resolves into two DERIVED per-layer values on
`ResolvedVisualizerPresentation`, mirroring the legacy scene-fade/gpu-fade split:

- `scene_fade` -> the presentation-root/card opacity (`scene_controller` applies it via
  `root.setOpacity`);
- `content_fade` -> the GL content opacity fed to shader `u_fade` by every mode renderer; it is the
  Quick-era successor of the authored bars-stagger fade (`bars_fade_from_progress`), so content arrives
  after the card is established.

`content_fade` is a distinct LAYER value, not a second clock. It must always be a pure function of the
same fade progress as `scene_fade`; never drive it from an independent animation/timer and never treat
it as a permanent second fade authority.

**Quick-path wiring (2026-09-01).** In the retained Quick path the visualizer's first-appearance fade is
owned by `QuickDisplayVisualizerOwner`, not the QWidget-era `VisualizerPresentationFade`/`ShadowFadeProfile`
(those, and the retired per-tick `push_spotify_visualizer_frame`, must not be resurrected). The owner eases
`scene_fade` 0→1 once per activation (`_activation_scene_fade`, smoothstep over
`_ACTIVATION_SCENE_FADE_DURATION_S`) sampled through the existing pacer-driven `sync_present` + transition
clock — no new timer. Because the GL content is a custom `QSGRenderNode` that the scene graph cannot apply
item opacity to, `rendering/quick/visualizer/node.py` folds `inheritedOpacity()` (authored `scene_fade` x
generation `startupRevealOpacity` gate) into `content_fade` at render time, only while genuinely fading. The
whole visualizer therefore fades shell + content coherently and honours the coordinated startup reveal, and
`content_fade` remains free to carry the mode-transition crossfade layer.

For carded modes the authority fades shell + content coherently.

For frameless modes it fades content without manufacturing invisible card dependencies.

Do not create competing QWidget and Quick opacity owners for the same visible pixels, and do not add a
second Quick fade animation/clock for the visualizer content.

During migration, temporary old/new paths must never both present the same visualizer simultaneously.

## 12. Source freshness

Measure separately:

- capture/source age;
- logical integration;
- logical publication;
- presentation synchronization;
- render consumption;
- physical delivery.

Smooth motion over stale audio is not healthy.

Do not retune Bubble/shader smoothing to conceal source staleness.

## 13. Pause / Play

Ordinary Pause/Play preserves:

- logical runtime;
- mode identity;
- warm source/capture policy;
- render identity where practical;
- no cold-start detour.

The migration may change the pixel owner; it must not reintroduce playback debounce or recreate the
logical runtime on ordinary Pause/Play.

## 14. Fidelity

Preserve all current-mode personality and behavioral goldens.

BTF additionally binds Bubble trajectory, elasticity, transients, source freshness, logical cadence,
edge survival, state-to-screen timing, and final continuity.

Non-default viewport aspect must not be implemented by anisotropically stretching Bubble circles,
line widths, or future 3D objects.

Bubble stream/drift movement remains renderer-content-relative across viewport extents: project each nonbaseline axis once
into the expanded logical world and solve trail smear in content coordinates. Do not compensate viewport loss with input
gain, authored speed/control retuning, a new timer, or a second motion state.

Bubble wake history and Bubble-head magnitude are separate contracts. Stored trail history remains content-space invariant and
head radius/reactivity follows the equal-area canonical-height projection, but the Quick ripple wake is an authored presentation effect: each
trail source's **complete** visible footprint (source separation, ripple radius/cap and ring spacing) remains baseline-pixel
authoritative under edge-resized wide/tall viewports. Correcting only the three trail-source centres is insufficient.

**R-69 remains the golden optimization rule.** The operator-authorized equal-area response correction
(2026-09-05) deliberately supersedes the rejected height-only aspect coupling; it preserves the full
waveform at a shape-independent size reference and does not cap large views.
 Bubble's renderer-facing head radius must not receive a global `baseline/current`, `1 / viewport_extent`, or equivalent large-viewport compressor. Ghost consumes already-normalized historical positions exactly once and must not inherit the ripple-wake axis/radial compression. The rejected global head compressor made extreme CUSTOM Bubble look nearly non-reactive while DSP/logical telemetry stayed healthy. If full expansion is aesthetically too large, target only a proven upper visual tail; do not flatten the full response curve. The same principle applies across Spectrum/Oscilloscope/Sine/DevCurve: geometry adaptation or smoothing may not silently weaken authored musical response or freshness.

**R-76 Spectrum temporal-axis rule.** Spectrum bar motion is vertical. Viewport-shape temporal compensation may depend on expanded vertical bar-field height, but viewport width alone must not slow authored response. The live Quick `SpectrumFrameRuntime` owns this treatment; do not restore a QWidget/painter/present-loop smoothing owner. Continuous solid-bar hysteresis is an authored temporal helper and keeps a canonical internal segment domain rather than changing rate zones when viewport height changes. Renderer segment geometry remains independent. Never use this rule to attenuate BeatEngine/source magnitude, the historical `0.55` upload transfer, or `compute_spectrum_height_scale()`.

Bubble lifecycle visibility is subordinate to that rule. Runtime birth/pop fades may change only the existing per-bubble alpha envelope (current contract: ~200 ms active birth, ~500 ms idle birth, ~400 ms pop). They must not add a cadence, timer, viewport multiplier, radius/pulse/motion rewrite, Ghost/history compression, or presentation queue. Canonical/wide/tall CUSTOM shapes must receive the same alpha timing.

## 14A. Product display admission and semantic input

Current product semantics admit one visualizer instance. Resolve its requested monitor against participating Quick displays
before constructing the visualizer owner. Exactly one display owns the controller/logical runtime/Quick edge for an admitted
activation; other displays construct none. Preserve committed/CUSTOM geometry and requested-display fallback/transfer
semantics.

Double-click inside the retained visualizer cycles visualizer mode. Only if family/visualizer semantic hit admission declines
the event may the display-level fallback advance to the next image.

## 14B. Hard retirement barrier

The sole authored `VisualizerLogicalRuntime` is non-daemon generation-owned work. Stop/join failure blocks visualizer and
owning-display generation retirement. Never detach the bridge, report successful owner retirement or continue terminal window
teardown while that runtime remains owned.

## 15. Generation fencing

Generation/activation are ownership identity.

`0` is valid.

Retired state cannot enter a replacement Quick scene, trigger reveal, or mutate current render state.

## 16. Native renderer rule

A native/C++ visualizer renderer is not a migration phase.

Only consider localized native code if profiling of the migrated Quick implementation proves a
specific Python render callback materially limits the result.

Keep the same logical contract and the same display `QQuickWindow`.
