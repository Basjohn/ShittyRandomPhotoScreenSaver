# Native core P3: decisions before any C++ (P3.0)

**Status (14 Nov 2026; consolidated).** D4 is decided and built. D5 (the core's shape), D6 (device ownership), D7 (the
card-material backdrop), D8 (what Parity+ means), D9 (async GPU jobs), D10 (the Vulkan rehearsal path and the flip
gate) and D11 (the Qt version) were decided by the one-off architectural audit of 12 Nov 2026 (Fable 5.2, at the
lead's request, answering the operator's direction of 11 and 12 Nov). D12 and D13 (14 Nov) were proposed by the High
agent for N2.9 and N4.a. They bind until the lead or the operator supersedes one in writing here. D1 to D3 and the
transport rule, the rest of D5 (N0.5), N0.3 and N0.4 (D5.5) were drafted as proposals and accepted by the lead on
12 Nov; this file states each as decided, with the lead's answers folded in. What each decision built is under its
"As built" or "As proved" record. The ordered work is `Current_Plan.md`, item 8b.

**This file is the current record only.** Superseded text, drafts, round-by-round evidence and the questions the
lead answered are in `Native_Core_P3_Decisions_History.md` (history, not instructions); each section below names
what moved. A later decision that overrides an earlier one is stated once, in the earlier section as the current
rule with a pointer. The pre-consolidation file is in git at `05d3d079e`.

Inputs: `Native_Core_P2_Closeout_and_P3_Entry_2026-11-09.md` section 3, `Native_Core_P2_Phase_Boundary_Audit.md`,
`Graphics_Backend_Decision_2026-11-05.md` (with its addendum of 12 Nov), `Native_Core_P1_Spike.md`, and the lead's
research of 12 Nov outside the repository (`D:\Temp\Scratch\SRPSS\research\20261112\`:
`native_core_capability_matrix.md`, `native_core_qrhi_gaps_and_conventions.md`). Qt facts marked *header* were
read in the Qt 6.11.2 SDK headers the P1 spike uses (`D:\Temp\Scratch\SRPSS\native_spike\qt\include`); facts marked
*unverified* are from knowledge of Qt's source and are proved in the step named beside them before anything is
built on them.

**The operator's direction these decisions answer to (11 and 12 Nov 2026, verbatim):**

- "Vulkan is not the fallback backend, it needs to be the front strong stable face." OpenGL stays selectable as
  the fallback. A limitation of Vulkan gets a solution of equal quality, not a degraded path.
- "We are a custom OpenGL and Vulkan Pipeline. Vulkan goes through QRhi from your suggestions but it should still
  be Vulkan. If we rely on QT then we run into other issues no?"
- "We want the best native core with Vulkan support we can muster, no shortcuts only smart low limitation direction
  with high potential ceilings. Async compute would be very useful for things like GIL contention, Transitions and
  Visualizers firing at the same time or other calculations but ultimately I leave it to you to get us to Parity+
  with an emphasis on the plus. You've already identified many areas of benefits with high data rings, indirect
  draws and so on but this needs to be your researched and rewarding decision."
- "You need to decide on the card-material backdrop but obviously we want it working and looking appealing."
- "Don't strictly build primitives when they have a consumer, we like to open potential. High potential primitives
  should be built regardless, low potential only when a consumer."

## D4. Extruded Bubble's drift solver without 64-bit shader floats

### The problem

The drift solver (`rendering/quick/visualizer/implementations/extruded_bubble_drift_solver.py`) used `double` in two
compute programs. That is the optional Vulkan feature `shaderFloat64` (absent on Intel Arc, most mobile GPUs and
Apple's; QRhi cannot ask for it), and a lesser second path for such devices would make Vulkan the weaker face there.

### What the doubles are actually for

Three things only: a discrete per-chain knot decision per step, growing phase arguments of `sin`, and one growing
quotient per mote (`progress`, up to 218,500 motes). Everything the draws read was already 32-bit. The inventory is in
the History file ("D4").

### The decision: no double in any shader, on any backend; precision goes where it is free or is rebuilt exactly


One path for OpenGL, Vulkan, Direct3D and Metal alike. No device feature is queried, so no device is second class.

- **(1) Chain decisions move to the engine worker, in float64, as the reference itself computes them.** The worker
  already produces the step record each tick; it also advances each chain's `shift` and takes the `floor`, in
  NumPy float64 with the reference's own arithmetic, and publishes per step and per chain the pair
  (`moved`, an integer; `shift`, a float32, always in [0, 0.008)). The chain program reads those and does only
  32-bit work (moving the knot row by `moved`, updating displacement). This is not an approximation of the
  64-bit decision: it *is* the 64-bit decision, made once, by the code the tests already treat as truth.
  Cost: 240 chains times a handful of float64 operations per tick in the worker (vectorised; microseconds), and
  8 bytes per chain per unapplied step on the transport (about 2 KB for a typical frame, 246 KB for a full
  128-step history).
- **(2) Phase reduction moves to the step record.** The worker reduces `t * k` mod 2 pi in float64 and publishes
  float32 angles per step (four, not three: the swish term grows too, see "As built"). The shader computes
  `sin(angle + c * p)` in 32-bit, both terms bounded. The rule "reduce mod 2 pi in 64-bit before `sin`" is kept; it
  simply runs where 64-bit is free.
  leaves the GPU: at geometry build the worker computes `r = carry / span` per mote in float64 and stores it as a
  high and a low float32 in the two unused floats of the mote's second `vec4` (the geometry record does not grow).
  Each step carries `travel` as a high and a low float32, split by the worker in float64. The shader forms
  `travel * r` as an error-free product of pairs (`fma`-based two-product, results marked `precise` so the
  compiler may not contract or reorder them) and takes its fractional part. That gives about 48 significant bits
  for the quotient; the output is a float32 with 24. At an hour's quotient of 800 the pair arithmetic is exact to
  about 3e-12 of a span, against 1e-13 for a double, and both are four or more orders of magnitude below the
  6e-8 of a span the float32 result can resolve. The geometry-edit rebase (`oldTravel / oldSpan`) uses the same
  pairs.


Rejected: a `double` path where `shaderFloat64` exists beside a second path elsewhere (two solvers, a lesser face);
integrating all drift in the worker (about 4 MB a revision, the cost the GPU solver removed); a camera-relative or
rebased float32 quotient (rounding at every rebase, no closed form to compare against).

### What "equal quality" means here, and how it is proved

The bar is the float64 CPU reference (`MaterialDriftReference`), the same judge the current solver has:

1. **Tick-exact chains:** `moved` for every chain on every tick equals the reference's, as integers, over a long
   recorded drive. Not a tolerance.
2. **Outputs within the current bound, at long horizon:** displacement, shift, phase offset and progress within
   the existing 1e-4 of the reference, on runs that start at an hour's and at eight hours' `travel` and `phase`
   (today's suite covers about four seconds). The current `double` shader is run on the same horizons, so the new
   path is compared with what it replaces as well as with the reference.
3. **No visible difference:** the largest displacement difference converted to pixels at 4K for the nearest bead
   the camera admits, stated as a number.
4. **It compiles for Vulkan:** both programs pass `qsb` (their loose uniforms move into a block) and leave the
   `LEGACY_GL_ONLY` list; the shader-readiness check discovers compute sources instead of using a fixed list.
5. **No cost at rest and no cost rise:** GPU time per dispatch at preset 1 and at 216,000 specks against today's,
   in one alternated session; the worker's tick cost for (1) and (2); a frame with no new step still dispatches
   nothing.

The pair arithmetic is first proved without a GPU: a NumPy float32 model of the shader's exact operation order
(with `math.fma`) against the reference over the long horizons. Only then is the shader changed.

### First numeric check of (3) (lead, 12 Nov 2026; not yet the D4.1 test)

Moved to the History file ("D4"). Result: float pairs hold a constant error of about 2.4e-7 of the longest span from
one hour to 24 hours, where plain float32 degrades to 3 % of a span after a day.

### Consequences

- The solver is not a Vulkan blocker and can be ported by the native core like any other compute pass.
- The step record grew by the reduced angles and the travel pair; chains gain a per-step decision stream; mote
  geometry does not grow. D3 (geometry once per revision) is unaffected.
- A device or driver whose compiler ignores `precise` would break (3). The readiness test therefore includes a
  runtime self-check of the two-product on a known pair at warm-up, on the edge, never per frame; a failure is
  logged and reported rather than silently producing drift.

### As built (D4.1 to D4.3, merged 12 Nov 2026; moved here from the plan when its boxes were deleted)

Evidence `.artifacts/evidence/native_core/20261112_d4/`. Both drift programs have no 64-bit type. Chain knot
decisions equal the reference as integers on every tick. Everything else is within 1e-4 at one and at eight hours
(worst 3.6e-6), where the `double` programs they replace, run on the same logs, recycled 4,431 to 31,524 motes on
the wrong tick (their spans were float32). Beyond the design above: there are four reduced angles, not three (the
swish term grows too); the chain phase offset is a third decision made on the logical side (12 bytes per chain
per step); the seed and the cloud phase offset are carried as pairs. The logical side's added work is 15 to 17
microseconds a tick. The stream ring grew from about 0.4 MB to 3.1 MB of mapped memory (240 chains times the full
history); sizing it is part of D4.6. D4.4 to D4.8 were merged the same day (the plan's N1 note; what is left of
them is two N1 boxes: the beads at the near plane and the drift programs on another driver).

## D5. The core's shape (decided 12 Nov 2026; the full resource and lifetime contract, N0.5, was drafted and accepted the same day: "D5, the rest" and "Lead decisions on the N0 drafts")

Four rules. They are what keeps the ceiling high. Spectrum alone needs none of them. What would be expensive is
adding the rules to the core itself after nine modes and twenty-eight transitions are built on a core without
them: every mode would then be reworked. Built in from the start, they make each new mode cheaper. A new mode
only declares its passes and resources and takes the host, the jobs, the targets and the lifetime from the core;
it never touches Qt Quick or another mode.

**D5.1 The core does not know Qt Quick's frame; a host adapter does.** The core is a C++ library that renders
into targets it owns and hands its results out as textures. A *host* gives it a device, a place to record this
frame's commands and the frame edge; nothing in a mode, a transition or a primitive names a `QQuickWindow`, a
scene-graph type or Qt Quick's render target. Hosts: the Qt Quick window (the saver, MC and both SMP hosts, which
are all Qt Quick windows); the hidden host (parity, capture and release-media tools, the Studio's preview); and,
reserved and not built, a host where the core owns the swapchain and presents by itself (the escalation of
8 Nov). Because only the adapter touches Qt, that escalation, a second window kind for SMP and a Qt upgrade each
change one small file instead of the renderer. This is the answer to "if we rely on Qt we run into other issues":
we rely on Qt at one seam, and the seam is replaceable.

**D5.2 Everything the core draws is recorded before Qt Quick's own pass; what reaches the window is a texture.**
QRhi cannot open a pass inside Qt Quick's pass, so scenes, post-processing, compute and raw blocks must come first
in any case. Decided beyond that:

- One native *frame driver* per window records all of the core's work for that frame, in dependency order
  (background layer, backdrop pyramid, Visualizer scene, overlays), on the window's `beforeRendering` edge. It is
  connected in C++ with a direct connection; a Python slot there would put the GIL back on the render thread.
- Each surface reaches the window as an ordinary scene-graph texture node with a small material of ours (the card's
  alpha, the rounded-rectangle coverage, the quarter turn), not as a `QSGRenderNode` that draws inside Qt's pass (in
  the code a `QSGGeometryNode` with the core's `CompositeMaterial`, `native/core/src/composite.cpp`).
  Qt's renderer then applies clip, opacity, order and batching itself. This is Qt's own pattern: *header*,
  `QQuickRhiItemNode` is a `QSGSimpleTextureNode` and a texture provider driven from `beforeRendering`
  (`private/qquickrhiitem_p.h:27,49`), and `QQuickWindow::createTextureFromRhiTexture` wraps the core's texture
  (`qquickwindow.h:125`).
- The card clip (plan 1C.4: nothing outside the card, nothing under the border's anti-aliased edge) becomes the
  coverage term of that composite material plus Qt's own scissor and stencil. No inherited state is read or
  restored, and the hand-built stencil pipelines the P1 spike's risk 5 feared are not written.
- Because each layer is a texture provider, a QML `ShaderEffect` can sample it. That is what D7's backdrop and
  SMP's sections need, and it costs nothing when nobody samples.
- Exactness: the core renders at the item's device-pixel rectangle and the composite maps texels one to one. An
  overflow mode (Sphere, Extruded Spectrum) renders to a target that covers the painted overflow footprint the
  stencil allows today, and the coverage term clips to that footprint, not to the item rectangle (lead, 12 Nov).
  The first port proves this (Spectrum through the texture node equals the Python renderer's direct draw, also
  under pixel shift and a uniform CUSTOM scale). If it cannot be made exact, that surface falls back to a render
  node with one composite draw (the lead's N3.0 form); the rest of this decision stands either way.
- The coverage edge is anti-aliased and replaces the hard `discard` edge of `clip_host.py`, provided the card-clip
  contract of R-191 holds on the native composite (no content under a straight-edge frame pixel; in the corners only
  under pixels the frame covers by at most half): `tests/test_visualizer_card_clip_contract.py` is the native port's
  parity bar.

The lead's N3.0 form (one draw in a render node with our own stencil) is superseded by the texture node; the cost is
one extra card-sized target for the three modes that draw straight into the window today (Spectrum, Spline Curve,
Bubble).

**D5.3 One definition per pass; native routes come in pairs.** Every pass is defined once by what it computes.
Its default implementation is QRhi, one code path for both backends. Where QRhi lacks a capability or measurably
costs, the capability sits behind a *service* with exactly two native forms, raw Vulkan and raw OpenGL (both
entered through QRhi's external block or on objects the core owns), and the two forms are tested against each
other for identical output. OpenGL 4.6 has every one of these natively (persistent mapping, indirect draws,
per-sample reads, the two-channel float formats, timer queries: the Python renderer uses them all today), so the
fallback is never the lesser path, and the product is what the operator calls it: a custom OpenGL and Vulkan
pipeline with QRhi as the glue. The list of services is closed; adding one takes a line here:

| Service | Why QRhi is not enough (6.11.2) | Admitted when |
|---|---|---|
| GPU timer (per pass) | QRhi times the whole frame only | built with the substrate (D8 plus 2); opt-in, no objects when off |
| Stream ring (persistent mapped) | QRhi stages and copies dynamic buffers | measured against QRhi dynamic buffers at the product's ring sizes; QRhi stays if the difference is under 0.05 ms |
| Indirect and count draws | no indirect draw in 6.11 (*header*) | measured against "draw the maximum, cull in the vertex shader" on the population harness; gone if D11 moves to a Qt that has it. **Retired 12 Nov 2026:** the project is on Qt 6.12, whose QRhi has `QRhiCommandBuffer::drawIndirect`/`drawIndexedIndirect` (feature `QRhi::DrawIndirect`; several draws per call where `DrawIndirectMulti` is reported); the core uses QRhi's form, and "draw the maximum, cull in the vertex shader" remains only for a backend that does not report `DrawIndirect` |
| Per-sample multisample reads | QRhi forbids sampling a resolved multisample texture | only if resolve-first fails a mode's look or cost; parity is single-sampled |
| Formats (RG16F, RG32F, R11G11B10F) | not in QRhi's format list | only where widening to RGBA16F or RGBA32F measurably costs memory or time (N1.7 widens first) |
| Async GPU jobs | QRhi records on one queue | D9 |

A feature with no OpenGL form is allowed only as an opt-in extra that changes nothing by default (temporal
upscaling is the known example). This supersedes the 8 Nov sentence "Such a pass is Vulkan-only: on OpenGL it is
unavailable or takes its QRhi form" (see the addendum in `Graphics_Backend_Decision_2026-11-05.md`).

Each service is a measured admission that must ship its OpenGL twin; two (formats, per-sample reads) are expected not
to be needed for parity.

**D5.4 No Python on any thread the core runs on.** The render thread and the job thread (D9) never hold a Python
thread state for a native surface: connections are made in C++, introspection lives in C++, and every port reruns
the P1 probe (calls made with a Python thread state: zero).

**D5.7 Where the product module lives (decided 12 Nov 2026, lead).** `native/core/` (C++ and CMake, beside the
harness `native/spike_p1/`), module `_srpss_native_core`; its only Python importer is `rendering/native/`, which checks
the module's Qt version and ABI and is the host adapter's Python face. The spike never ships.

## D6. Real Vulkan, and who owns the Vulkan device (decided 12 Nov 2026)

Operator, 12 Nov: "We are a custom OpenGL and Vulkan Pipeline. Vulkan goes through QRhi from your suggestions but it
should still be Vulkan. If we rely on QT then we run into other issues no?"

**What stands from the 8 Nov decision and the lead's proposal of 12 Nov.** On the Vulkan backend every command the
core records is a Vulkan command; QRhi is a thin C++ recording layer over it (no GIL, negligible overhead), used
where it tracks barriers, frames in flight and render-pass compatibility for us, and bypassed per pass with raw
Vulkan (`QRhiCommandBuffer::beginExternal()`/`endExternal()` and the native handles) wherever D5.3 admits a
service. The OpenGL fallback is the same core on Qt's OpenGL backend. QRhi's compatibility guarantees are limited,
so the core is built against PySide6's exact Qt and every upgrade reruns the parity gates (D11). Qt owns the
swapchain and the frame loop; the core keeps that path Python-free; a core that owns the swapchain stays the
escalation, taken only when a measurement demands it, and D5.1 keeps it cheap to take. D4 is unaffected.

**The decision.**

1. **The native module creates the Vulkan instance and the devices, and gives them to Qt Quick.** One
   `QVulkanInstance` for the process, set on every Vulkan window; for each window a `VkDevice` created by the
   module and handed over with `QQuickWindow::setGraphicsDevice(QQuickGraphicsDevice::fromDeviceObjects(physical
   device, device, queue family, queue index))` before the window is first shown (*header*,
   `qquickgraphicsdevice.h:51`). PySide6 6.11.2 exposes none of this, so it lives in the module, as the P1 spike
   already attaches the instance. Qt renders the UI on our device.
2. **From the first Vulkan host, not from the flip.** The hidden parity host and the rehearsal window (D10) use
   the module's device from their first run, so that every Vulkan hour is spent on the final device model and
   nothing is re-proved when the default changes. The product's OpenGL window is untouched by this.
3. **Why own it.** (a) A second queue: Qt creates its device with one queue, and async jobs (D9) need their own.
   That is the one capability Qt's own device cannot give. (b) Determinism: the API version, extensions, features
   and the choice of GPU are ours, written in one place, identical in the harness and the product and unchanged
   by a Qt upgrade. (c) The escalation and any future SDK that wants its own extensions start from an owned
   device. Feature bits are not a reason: the device enables what Qt's own would (see the amendment below).
4. **One device per window.** With the threaded render loop each window has its own render thread and its own
   QRhi. Two QRhi instances submitting to one `VkQueue` from two threads is undefined, and a queue per window from
   one family exists on some vendors only (many queues on NVIDIA, typically one on AMD and Intel). So each
   window gets its own device, as Qt does today; nothing is shared between displays on the GPU, as today. The
   Visualizer's move between displays (plan 1C.2) keeps its engine session and logical state and rebuilds GPU
   resources on the target device, warmed before the swap. A shared device is reconsidered only with the
   own-swapchain host, where the core serialises submission itself.
5. **Baseline and fallback.** Vulkan 1.2 with the features the D6 proof lists (timeline semaphores among them);
   a job queue is used where the hardware offers one and is otherwise absent (D9's in-frame form runs). A machine
   that cannot give the baseline starts on OpenGL, at start-up, before any window exists, with the reason logged
   and shown where the backend setting is shown. There is never a teardown from Vulkan to OpenGL in a running
   process. A Vulkan start that did not complete is remembered (a small state file beside the settings, no
   environment variable), and the next start uses OpenGL and says so: a driver that crashes at device creation
   must not strand the user.
6. **The lead's open question, answered.** Qt 6.11.2 can make its frame submit wait on, and signal, semaphores we
   supply: `QRhi::setQueueSubmitParams` with `QRhiVulkanQueueSubmitParams` (wait, signal and present-wait
   arrays; *header*, `rhi/qrhi.h:2073`, `rhi/qrhi_platform.h:107-115`). The struct carries no timeline values, so
   the semaphores are binary. Qt waits on them only at `COLOR_ATTACHMENT_OUTPUT` and clears the list after every
   submit, so the wait protects only a job output that is a colour attachment Qt's pass writes or blends into, never
   a job result that a shader samples (D9's amendment). Owning the frame submit is not needed for async work and does
   not move earlier. D9's default route needs no GPU-side wait at all.

**Proof before anything is built on it (plan item 8b, N0.6):** in the P1 harness, a hidden Qt Quick host on the
module's device renders the spike scene pixel-identical to the same host on Qt's own device; validation layers
are clean through create, render, resize and teardown (windows first, then devices, then the instance); the
second queue is found on the development GPU and its absence is forced as a negative control; then one bounded
run of a real window on Display 1 by the lead (swapchain, resize, DPI change, sleep and wake).

**Amended by the lead, 12 Nov 2026, from the Qt 6.12 source facts (`Native_Core_N06_N07_Qt_Facts.md`).**
- The device enables the same features Qt's own device would (every supported feature except `robustBufferAccess`
  and `robustImageAccess`): for an imported device QRhi derives its capability flags from what the physical device
  supports, not from what our device enabled, so a narrower device would make QRhi report capabilities it cannot
  use (`DrawIndirectMulti`, wide lines, shading rate). This settles point 3's "feature bits" question.
- The instance is ours too: created by the module with validation and synchronisation validation enabled in code
  (failing closed when the layer is missing in a harness run), adopted with `QVulkanInstance::setVkInstance` and
  `setApiVersion(1, 2)` (the default is 1.0, and QRhi would treat the device as 1.0).
  `QQuickGraphicsConfiguration::setDebugLayer` and its device extensions do nothing when the instance and device
  are supplied, and no environment variable is used (the project forbids them).
- Lifetime: the device outlives the `QQuickWindow` object, not only its visibility; after our `vkDestroyDevice`,
  `QVulkanInstance::resetDeviceFunctions(device)` (QRhi does not call it for an imported device).
- Translucent windows: Qt's Vulkan swapchain asks for `PRE_MULTIPLIED` composite alpha when the window has an alpha
  format; Qt's own source notes NVIDIA on Windows reports `OPAQUE` only and transparency still works, and the
  Windows plugin applies an empty-region `DwmEnableBlurBehindWindow` to accelerated alpha windows. N0.6 records what
  this machine reports and whether the window is see-through (D7 point 8's first route).

**Amended by the lead, 12 Nov 2026, from N0.3 run 1 (decision F3).** On our device the front face of a culling pass is
chosen by rule 4 (`front_face_clockwise`) on the matrix as uploaded, after `clipSpaceCorrMatrix()` (which flips Y on
Vulkan) and, for a core-owned target on OpenGL, after F1's Y flip; never on the OpenGL-form matrix, which culled the
wrong faces on Vulkan and OpenGL in run 1. For Quick's item matrix the rule then gives counter-clockwise on Vulkan,
D3D11 and D3D12 and clockwise on the core's OpenGL (F1's flip turns the winding); run 1 measured exactly that.


**As proved (N0.6 harness, `native/spike_p1`, 12 Nov 2026; each round built on GitHub and run by the lead; evidence
`.artifacts/evidence/native_core/n06/`).** Six rounds, all PASS after their fixes (the per-round record is in the
History file, "D6"):
- Facts: loader 1.4, RTX 4090, API 1.4.351, NVIDIA 617.42; queue family 0 (graphics, compute, transfer) has 16
  queues, so a second queue in Qt's own family exists; Qt's own device (API 1.2) takes family 0 queue 0 and enables
  109 features (every supported one except `robustBufferAccess`).
- Our instance (API 1.2) and device (the same features as Qt's rule, name for name): the hidden Qt Quick host on our
  device is pixel-identical to the same host on Qt's own device; QRhi feature flags equal; teardown clean.
- Lifecycle and second queue: ten create, render, resize, teardown cycles clean; the second queue is found every
  cycle (family 0, index 1) and executes; its forced absence reports none and the device still renders.
- Owners: the 3 process handles per device create and destroy are NVIDIA 617.42's own, whoever creates the device;
  our code adds none; threads, GPU heaps and Python objects return to baseline.
- Translucent Vulkan window, hidden: NVIDIA 617.42 reports OPAQUE and PRE_MULTIPLIED for an alpha window, Qt picks
  PRE_MULTIPLIED, the alpha in Qt's grab matches OpenGL's, the DWM system backdrop and the project's glass both apply
  and the window keeps presenting. Hidden windows cannot show the composed alpha, so see-through to the desktop is
  the lead's visible run on Display 1 (`Current_Plan.md`).
- Messenger: 0 errors and 0 warnings in render and teardown. Validation layer: owed in the harness round named in
  the plan.

Long-term risk (driver variance): on NVIDIA 617.42 a device rebuild costs 3 process handles that are never returned,
so the product never rebuilds a device except on device loss or window replacement (point 4 already says so).

## D7. The card-material backdrop on the native core (decided 12 Nov 2026)

Operator, 12 Nov: "You need to decide on the card-material backdrop but obviously we want it working and looking
appealing."

Today (`Docs/Architecture/Card_Surface_Materials.md` section 3) one owner per display blits Qt Quick's window
target after the wallpaper and dimming are drawn, blurs it into a two-level texture, and every material surface
samples that texture in screen space, failing closed to Normal. No backend can read Qt Quick's own target inside
its pass, so on the native core the source must change. Everything a card sees stays as it is.

**The decision.**

1. **The source is the core's own background layer.** Wallpaper and transition are rendered by the core into a
   target it keeps (D5.2) and composited into the window as a texture node. At rest that texture is simply
   retained: nothing is drawn again, which is the intent of the protected retained-background work, and the
   native path must measure no worse than it. The pyramid is built from this texture. Nothing reads the window.
2. **Built only when the layer changed, only while someone wants it.** The pyramid is rebuilt in the frame in which
   the background layer was re-rendered (a transition frame, a new image, a resize) and never otherwise; it exists
   only while the existing owner counts demand above zero (section 3.2's dormancy is unchanged: with every surface
   Normal there is no pyramid, no pass and no item).
3. **Every transition frame, by budget.** The rate limit goes: the pyramid follows the transition frame by frame,
   provided its measured cost is at most 0.3 ms of GPU time at 2560 x 1440 and 0.6 ms at 4K on the development
   GPU. Where a device misses that, today's minimum-interval rule stays for that device. Measured, not assumed.
4. **A full chain of levels, one texture, one shader.** Dual-filter downsampling to about 1/32, so a material
   chooses its blur by level of detail (a continuous radius: better Mica and Frosted, and room for depth-dependent
   blur later). "One shader, one texture, one sampling path; materials differ only in uniforms" (section 3.5)
   stands. Fragment passes through QRhi are the default: at these sizes compute buys nothing and fragment passes
   run unchanged on the OpenGL fallback.
5. **Dimming, saturation and luminosity stay at sample time.** Dimming is a uniform blend, which commutes with a
   blur, so the material shader applies it to the sampled value and a dimming change refreshes nothing.
   Saturation and luminosity are per material and stay uniforms; baking them into the pyramid would make it
   per-material and break rule 4.
6. **Cards do not change.** The backdrop is a texture provider; `MaterialSurface` samples it in screen space and
   fails closed to Normal by its alpha exactly as today (transparent until the first build, after a resize, or
   when a build is refused).
7. **True glass over the live Visualizer, as a plus (D8, plus 5), not parity.** A material surface that overlaps
   the Visualizer (overlays on the expanded Visualizer, the Context Menu, an SMP section) may blend in a blurred
   copy of the Visualizer layer, bounded to the overlap rectangle, refreshed per Visualizer frame only while such
   a surface is shown, and absent otherwise. This supersedes invariant 6 of section 2 ("the Visualizer's content
   is never read back; nothing runs per Visualizer frame") for the native core only: there the Visualizer is
   already a core texture, so nothing is read back. Gate: at most 0.3 ms at the overlap sizes that occur, and
   the lead's review of the look. The Visualizer card's *own* material keeps showing the wallpaper: its glass is
   behind its content, which is correct for a framed card.
8. **SMP.** In the compositor host (saver and MC builds) the backdrop is this one: the core's own background layer
   through the same pyramid and card shader. In the SMP build's desktop window the material shows the desktop behind
   the window (operator, 12 Nov 2026: "Artwork Backdrop if running MC or Screensaver Profile/Builds. Desktop when
   running dedicated SMP builds. Material is meant to show what is behind, and that is the consistent way to it.").
   The artwork-and-Visualizer layer (a background layer made from the current artwork, with the Visualizer layer
   where a section overlaps it) remains only as the fallback for a device or backend on which the window cannot be
   made see-through, never the chosen look. Routes, in order, proved in N0.6 before SMP depends on them: (1) the Qt
   Quick Vulkan window with a per-pixel alpha swapchain (composite alpha other than opaque) and the DWM system
   backdrop behind it; (2) if the swapchain is opaque on Windows, presenting through DirectComposition (the frame
   shared to a D3D11 swapchain for composition by external memory); (3) the OpenGL backend for that one window. The
   desktop pixels are never captured by us: the window is see-through and the system composes, so the cost is the
   system's. Whether such a window can be see-through at all is proved in N0.6 and matters before SMP: the Studio's
   window is translucent today (`ui/studio/surface.py:181,242`) and changes backend with everything else at the flip.

**During the migration.** The product's OpenGL window keeps today's blit until the whole background family is
native in that window (D10); the native backdrop is built with the native presenter and runs from the start on
the Vulkan rehearsal path, so the blit is never needed on Vulkan. At the switch on OpenGL the native backdrop is
compared with the blit on the same frames.

The lead's N0 position differed on saturation and luminosity in the build pass (kept at sample time, rule 5), compute
instead of fragment passes (fragment by default, rule 4) and dimming in the build (sample time). The SMP desktop
window shows the desktop (point 8); the earlier reasoning that it must not rely on the system backdrop is in the
History file ("D7").

### Point 1 as built (N5.7a, 14 Nov 2026): the image presenter and background as the core's background layer

**The Python presenter (read at 899c4475; still the OpenGL route until the background family switches).** One
immutable `PresentationImage` (`rendering/quick/image_state.py`: RGBA8, rows top first) per display generation, owned
by the scene's `BackgroundRenderItem.presentation_image` (one identity, one content). The fit and crop (FILL, FIT,
SHRINK) happen in the image worker at the display's device pixels; the presenter's own rule is the processed image's
whole pixel rect over the item's whole logical rect (linear, no mips, opaque). Covered displays are left out upstream
(`image_pipeline._leave_out_covered_destinations`). `QuickDisplayRuntime.set_presentation_image` publishes the base
and a run's finalization publishes its destination. The protected retained-background path (07486d83, in the lineage
of ce07b991 and 985b9d53) at rest is a `QSGImageNode` under an opacity node retained by Qt with no Python per frame;
the custom `BackgroundRenderNode` sits behind an opacity-0 node, drawn only for a run, a proof or a pixel oracle. On
Vulkan (D10 point 2) neither exists and the window shows black where the wallpaper will be. The read-first detail is
in the History file ("D7").

**As built (boxes 2 and 3, ABI 15; owed: its build round and `background_layer_check.py`).**
1. *One owner of the fit and crop* (`rendering/quick/background_placement.py`): the worker's processed image's whole pixel
   rect over the background item's whole logical rect. The Python presenter's `QSGImageNode` reads its source rect and
   rect from it (the same values as before: the protected path is not retuned), and the native layer its pass's
   `u_source_uv`. A test moves the owner and sees both paths move.
2. *The layer is N4.a's fullscreen pass, as a still* (`mode_content.h`, "Stills"): a generic mode item with no stream,
   its frame its textures, settings and card; its program is checked against an empty schema. It records only when what
   it draws changed: the record that hands a new photo to its upload job keeps the target and records no pass (the
   previous photo stays, never a blank), and the commit's record (the frame edge the job's latch publishes at) draws the
   new one once. At rest nothing is recorded; Qt composites the retained target.
3. *Its pass* is the product file `rendering/quick/qml/shaders/background_layer.frag` (baked by `tools/regen_qrc.py
   --shaders`, shipped with the QML): the photo at `u_source_uv` over `vUv`, linear, clamped, no mips, as the retained
   node samples it; replace.
4. *The composite* takes two options: `layer` ("background": the frame driver records the window's background-layer
   surfaces before every other, D5.2's order, so N5.7b builds its pyramid from a layer drawn first in the frame) and
   `opaque` (the material without blending: Qt draws it in its opaque pass, as the retained image node it stands for, and
   blends it while its opacity is below one).
5. *The photo's textures are the core's*: the item's `PresentationImage` is copied once into the core (GUI thread) and
   uploaded by N3.8's job service on a Vulkan device with a second queue (in the frame elsewhere). The wrapped-texture
   bridge (PR-04) is OpenGL only and is not used; it retires with the Python presenter.
6. *The route* (`rendering/quick/render/native_background.py`): on the native background's backend (Vulkan)
   `BackgroundRenderItem` makes the layer, a composite item in itself, at its first image, and hands it every image at the
   same edge the Python presenter takes it, so image ownership, the identity rule, covered-display admission and the
   timing stay the item's and the runtime's. The layer fades in with its first photo and out when the image goes or the
   core's content fails; a lost texture is sent again from the item's image; the scene's retirement closes it before
   the root. On OpenGL nothing native is made. Known limit until N5.2a: on Vulkan a transition is not drawn (D10 point 2),
   so the base photo changes at the run's end as a cut from one photo to the next, never through a blank.
7. *What the build round must prove* (`native/core/python/background_layer_check.py`): rule (a) OpenGL native equal to
   the Python presenter's frames on real photos (landscape, a FILL crop, portrait and a 3:1 aspect, FILL and FIT) at dpr
   1 and 1.5 under the overscan placement; rule (b) Vulkan within 1 level; the route through `BackgroundRenderItem` on
   Vulkan; photo changes through jobs (the hand-over keeps the previous photo and records no pass, the commit draws the
   new one exactly, no fallback, the render thread's and the GUI thread's cost per change); nothing at rest; the cost at
   rest at 2560 x 1440 against the protected retained-background path; the lost edge and teardown in flight; validation
   clean. Then the lead's Display 1 and Display 0 rehearsal with the wallpaper and music.

### Point 1 as built (N5.7a, 14 Nov 2026): the image presenter and background as the core's background layer

**Read first (box 1), the Python presenter as it is at 899c4475.**
- *Image ownership.* The pixels a display shows are one immutable `PresentationImage` (`rendering/quick/image_state.py`:
  RGBA8, rows top first, tight, its pixel size, logical size and dpr), detached from the image worker's processed
  `QImage` by `display_image_route.presentation_image_from_processed_qimage` through `image_boundary.capture_qimage`
  (one deep copy). Its owner in a display generation is the scene's `BackgroundRenderItem.presentation_image`
  (`rendering/quick/render/background_item.py`): one identity, one content (an identity reused for other pixels is
  refused). The retained node keeps the image for as long as its texture exists (`background_image_node.py`, PR-04
  Stage B: the `QImage` wraps its bytes without a copy).
- *The fit and crop.* The fit and crop to the display (FILL, FIT, SHRINK) is done before the presenter, in the image
  worker process, at the display's device pixels (`display.get_target_size()`): `rendering/image_processor_async.py`
  `AsyncImageProcessor.process_qimage` (Smooth) or `rendering/image_quality.process_image` (the Pillow filters); the
  scaled cache keys it by size, mode, filter and dpr. The presenter's own part is one rule: the processed image's whole
  pixel rect over the item's whole logical rect (`QSGImageNode.setSourceRect(0, 0, w, h)`, `setRect(0, 0, lw, lh)`,
  linear, no mips, `TextureIsOpaque`, the opaque pixels labelled premultiplied); a size that does not match the item's
  device pixels (a stale image after a resolution change) is stretched by that same rule. The item covers the scene
  root, which lies at the monitor's exact rect inside the R-63 overscanned window, on whole device pixels
  (`scene_controller._sync_root_*`, `device_geometry.py`).
- *Covered-display admission.* Upstream of the presenter: `image_pipeline._leave_out_covered_destinations` reads
  `DisplayManager.covered_image_destination_screens()` inside the batch admission; a covered display that shows an image
  is left out of the batch through its omission receipt and keeps its image (history keeps its meta). The presenter is
  simply not called for it.
- *The timing and its edges.* `QuickDisplayRuntime.set_presentation_image` (refused during a run) publishes a new base;
  a run starts against the current base (`start_transition` refuses another source) and announces the incoming image at
  its start (`announce_incoming_image`); its finalization publishes the destination as the base, then
  `transition_finalized`. The scene controller tells the backdrop owner (`note_background_changed`) and its one listener
  on an identity change. The item's `update()` reaches the render thread at the next sync; the retained node uploads in
  that frame (`createTextureFromImage`), or adopts the finished run's resident texture (PR-04, the wrapped-texture
  bridge, OpenGL only).
- *The protected retained-background path* (07486d83, in the lineage of ce07b991 and 985b9d53, which own the frame
  pacer and the Visualizer's clip host and are not on this path): at rest a `QSGImageNode` under an opacity node,
  retained by Qt's scene graph, with no Python per frame; the custom `BackgroundRenderNode` lives behind an opacity-0
  node, drawn only for a run, a proof or a pixel oracle. On Vulkan (D10 point 2) neither exists: no background node
  is created, the window shows black where the wallpaper will be.

**As built (boxes 2 and 3, ABI 15; owed: its build round and `background_layer_check.py`).**
1. *One owner of the fit and crop* (`rendering/quick/background_placement.py`): the worker's processed image's whole pixel
   rect over the background item's whole logical rect. The Python presenter's `QSGImageNode` reads its source rect and
   rect from it (the same values as before: the protected path is not retuned), and the native layer its pass's
   `u_source_uv`. A test moves the owner and sees both paths move.
2. *The layer is N4.a's fullscreen pass, as a still* (`mode_content.h`, "Stills"): a generic mode item with no stream,
   its frame its textures, settings and card; its program is checked against an empty schema. It records only when what
   it draws changed: the record that hands a new photo to its upload job keeps the target and records no pass (the
   previous photo stays, never a blank), and the commit's record (the frame edge the job's latch publishes at) draws the
   new one once. At rest nothing is recorded; Qt composites the retained target.
3. *Its pass* is the product file `rendering/quick/qml/shaders/background_layer.frag` (baked by `tools/regen_qrc.py
   --shaders`, shipped with the QML): the photo at `u_source_uv` over `vUv`, linear, clamped, no mips, as the retained
   node samples it; replace.
4. *The composite* takes two options: `layer` ("background": the frame driver records the window's background-layer
   surfaces before every other, D5.2's order, so N5.7b builds its pyramid from a layer drawn first in the frame) and
   `opaque` (the material without blending: Qt draws it in its opaque pass, as the retained image node it stands for, and
   blends it while its opacity is below one).
5. *The photo's textures are the core's*: the item's `PresentationImage` is copied once into the core (GUI thread) and
   uploaded by N3.8's job service on a Vulkan device with a second queue (in the frame elsewhere). The wrapped-texture
   bridge (PR-04) is OpenGL only and is not used; it retires with the Python presenter.
6. *The route* (`rendering/quick/render/native_background.py`): on the native background's backend (Vulkan)
   `BackgroundRenderItem` makes the layer, a composite item in itself, at its first image, and hands it every image at the
   same edge the Python presenter takes it, so image ownership, the identity rule, covered-display admission and the
   timing stay the item's and the runtime's. The layer fades in with its first photo and out when the image goes or the
   core's content fails; a lost texture is sent again from the item's image; the scene's retirement closes it before
   the root. On OpenGL nothing native is made. Known limit until N5.2a: on Vulkan a transition is not drawn (D10 point 2),
   so the base photo changes at the run's end as a cut from one photo to the next, never through a blank.
7. *What the build round must prove* (`native/core/python/background_layer_check.py`): rule (a) OpenGL native equal to
   the Python presenter's frames on real photos (landscape, a FILL crop, portrait and a 3:1 aspect, FILL and FIT) at dpr
   1 and 1.5 under the overscan placement; rule (b) Vulkan within 1 level; the route through `BackgroundRenderItem` on
   Vulkan; photo changes through jobs (the hand-over keeps the previous photo and records no pass, the commit draws the
   new one exactly, no fallback, the render thread's and the GUI thread's cost per change); nothing at rest; the cost at
   rest at 2560 x 1440 against the protected retained-background path; the lost edge and teardown in flight; validation
   clean. Then the lead's Display 1 and Display 0 rehearsal with the wallpaper and music.

## D8. What Parity+ means, and the ranked plus (decided 12 Nov 2026)

**Parity is four things, each a gate at every port and again at the flip:**

1. *Pixels.* On OpenGL, the native renderer equals the Python renderer it replaces on single-sampled targets
   through the existing gate (`tools/visualizer_replay/owner_render_parity.py`). On Vulkan, the same scene equals
   the native OpenGL result within a tolerance the port states and justifies (the P1 spike measured 0 to 3 of
   255 between backends on trivial content). Multisampled output is judged repeat-relative, never exact.
2. *Behaviour.* Settings, Studio and engine-worker parity; fades; lifecycle and retirement; nothing per frame at
   rest. Reactivity is unchanged by construction (the packets are the same) and is shown once per mode with the
   music-response trace.
3. *Cost, no worse on any axis.* GPU time per pass, render-thread CPU time, late frames, GPU memory, working set
   and first-reveal time, at the card and at display size, beside the Python path in one session.
4. *Stability on Vulkan.* Rehearsal hours (D10), sleep and wake, a display arrangement change, device loss
   recovered by rebuilding from the last packet, and the start-up fallback proved by a forced failure.

**The plus, ranked by reward against cost.** Each is built on the core, proved on its own harness, costs nothing at
rest and has an OpenGL form (D5.3). The gate is what admits it into the product.

| # | Plus | What the user or the project gains | Cost | Risk | Gate that admits it |
|---|---|---|---|---|---|
| 1 | Python-free render path | Frame pacing that no longer depends on the GIL, in every mode; this is the measured reason for P3 (Waveform Preset 4 renders 10.4 ms median under load against an 8 ms budget on the worker path; Extruded Bubble 8.2 ms at display size) | The port itself | The size of the port | Per port: zero render-thread calls with a Python thread state; the mode's render median and late frames beside the Python path; under load only in a lead-run session after the operator's yes |
| 2 | Per-pass GPU timing in the frame trace | Every later optimisation and every port is measured per pass in the real window instead of per frame in a lab | Small | Low | Off: no query objects exist and the trace has no cost; on: figures agree with the offline tools on one scene |
| 3 | Async GPU jobs: image upload, mips, derived maps and transition precompute off the frame (D9) | No hitch at an image change or a transition start while a Visualizer runs; the 14 ms image-change constraint goes | Moderate | Cross-queue synchronisation; devices with one queue | D9's proof: p99 frame time and late frames across image changes with a Visualizer running, async against in-frame |
| 4 | Mixed-resolution soft layers (P4, N4.f) | Display-size and 4K budgets for fog, bloom, reflection blur and glows; the base for smoke; lines, dots and rims stay at full resolution | Moderate | Halos at depth edges | Per mode: stills side by side reviewed by the lead and GPU time before and after; never whole-frame upscaling |
| 5 | The backdrop every transition frame with continuous blur levels; true glass over the Visualizer (D7) | Visible: materials that follow a transition instead of stepping, and overlays that are glass over live content | Small to moderate | Cost at 4K | D7's budgets and the lead's review |
| 6 | High-potential 3D primitives without a consumer (N4.c, N4.d's wet-surface masks, N4.h, N4.k, N4.m, N6.1 to N6.3; the masks added 12 Nov night to match the class the lead wrote at the plan's N4.d) | What scenes can look like: populations, shadows, many lights, merged shafts, a reactive surface, places, smoke | Moderate each | Building what nobody uses well | Each on its harness with measured cost, lazy creation and a showcase; none blocks the flip |
| 7 | GPU-driven populations with count draws | Populations of 10^5 to 10^6 with GPU culling and no readback, for droplets, debris, sprites | Moderate (smaller since Qt 6.12: the indirect draw is QRhi's own, no raw service) | No indirect draw in QRhi 6.11 (resolved by Qt 6.12, 12 Nov) | The population harness at one million sprites against "draw the maximum, cull in the vertex shader"; the two existing transitions port on the simple route |
| 8 | Persistent high-rate rings | Larger histories and denser strands and particles at one copy per frame | Small | Low | D5.3's measurement; not built if QRhi's dynamic buffers are within 0.05 ms |
| 9 | HDR output | Emissive scenes on an HDR display | Moderate | Window format and tone mapping per backend | Not admitted; reconsider after the flip |
| 10 | Per-pass temporal upscaling, descriptor indexing, ray tracing | None today | High | High | Not admitted: low potential until a consumer exists (the operator's rule); D6 keeps the door open |
| 10a | Mesh shaders (plan N6.7; operator, 13 Nov: for fidelity) | Geometry that needs them | High | Moderate | A measured candidate, admitted when N2.6's timers show a ported mode's geometry pass is primitive-bound or a fidelity target needs the geometry. Raw Vulkan on the core's device (D6) with a compute-cull and indirect-draw twin for OpenGL; never the only path |

Multi-threaded command recording, which the lead listed as a CPU-side plus, is **not** a plus worth building: a
frame here is a handful of passes and well under a millisecond of recording, and QRhi's command buffer is
single-threaded. It is reconsidered only if a trace shows the render thread recording for more than 2 ms.

**Where the plus sits in the order** (the plan places each): 2 with the substrate, so every port is measured with
it; 3 proved on the harness before the substrate and used first by the presenter; 5 with the presenter; 4 after
Waveform Ribbon and Extruded Bubble are native, before Expanded Visualizer M6; 6, 7 and 8 on the primitives track,
never holding the flip; 1 is every port.

## D9. Async GPU jobs (decided 12 Nov 2026)

Operator, 12 Nov: "Async compute would be very useful for things like GIL contention, Transitions and Visualizers
firing at the same time or other calculations".

**What it is, plainly.** Async compute is scheduling on the GPU. It does not touch the GIL: the GIL is removed
from the logical tick by the engine worker (P2, the default) and from the render thread by the Python-free core
(D8 plus 1). What async work does solve is the other half of the operator's sentence: the GPU work of several
owners landing in one frame (a transition's preparation, the Visualizer's frame, an image upload, the backdrop)
and making that frame late. One caution, so that nobody expects more: on a single GPU a second queue does not
add throughput; the gain is that long work no longer lengthens one frame's command buffer and the driver can
interleave it. It is measured before it is trusted, per vendor.

**The decision.**

1. **Jobs, not only compute.** The core has one native job thread per device, with its own queue (compute and
   transfer), command pool and resources. A job is self-contained: it uploads its own inputs and writes its own
   outputs. The thread and its QRhi are created at the first job (a device that never runs one holds neither), then
   parked on a condition variable; it wakes only for a job (no polling, no timer).
2. **First consumers, in order of reward.** (a) An incoming photo: the texture upload, its mips, the reflection
   copy, the backdrop seed, and what the next transition needs prepared (edge field, propagation field,
   population scan). Two rules, both current. The photo upload (N3.8, built): a frame never waits for the job; the
   old picture stays drawn until the item's textures commit together. A transition's start (N5.2g, not yet built):
   the transition starts on the job's completion edge, with a deadline after which the in-frame form runs. (b) Warm-up: static meshes, heightfield builds, probe filtering, raw pipelines. (c) Simulation
   steps (the drift solver, Waveform's five passes, fog, later the surface field and smoke) stay in the frame by
   default: they are small and tied to the frame; one moves to a job only by its own measurement and a line here.
3. **Synchronisation route: latched publication.** Job outputs are raw resources of the core, shared between the
   graphics and job queue families. A job writes a back slot. The job thread waits for its own submission on its
   own thread and then publishes one atomic "generation N is complete" edge; the frame driver reads it at the
   start of a frame and swaps front and back. The graphics queue never waits for the job queue, Qt is not
   involved, and a frame is never held. A job never reads a resource Qt's queue wrote in the same frame.
4. **The exception, when a frame must contain this frame's job result:** the job signals a binary semaphore and
   Qt's frame submit waits on it (`QRhi::setQueueSubmitParams`, D6 point 6). Not used for parity; each use is a
   line here.
5. **The in-frame form always exists.** The same job body recorded on the graphics queue in the frame: on the
   OpenGL fallback, and on Vulkan devices without a second queue. It writes the same outputs, so async changes
   when work happens and never what is drawn. For class (a) and (b) the consumer waits for the completion edge,
   so there is no visible difference at all.
6. **Teardown and loss.** The job thread is quiesced by the same barrier as the packet reader (D1) before a device
   is destroyed; a job in flight at retirement is abandoned and its slot dropped (the drop edge of R-184).

**How it is proved (plan item 8b, N0.7), before the substrate depends on it:** a fixed scene at the display's rate
in a hidden host: a heavy job (the edge field at 4K, repeated) run in-frame and as a job with frame GPU time median,
p90 and p99 and late frames; the outputs hashed and identical between the two forms; no Python thread state on the
job thread; validation with synchronisation validation clean; retirement and device destruction in the middle of a
job without a crash or a leak; zero wake-ups of the job thread at rest over a minute. If no gain, compute jobs stay
in-frame on that vendor and the job thread is kept for uploads.

**Amended by the lead, 12 Nov 2026, from the Qt 6.12 source facts (`Native_Core_N06_N07_Qt_Facts.md`).**
- Point 4 does not protect a sampled job result: Qt's frame submit waits on the semaphores passed through
  `setQueueSubmitParams` only at `COLOR_ATTACHMENT_OUTPUT`, binary semaphores only, and the list is cleared after
  every submit. So a job result that the same frame's shaders sample is never consumed through point 4; it is
  published by the latch (point 3) and used from the next frame. Point 4 stays only for a job whose output is a
  colour attachment Qt's pass then writes or blends into, and each such use is still a line here.
- Point 3, the queue family: QRhi creates its images and buffers with exclusive ownership and never records a queue
  family ownership transfer. The first proof (N0.7) uses a job queue in the same family as Qt's graphics queue; a
  different family needs raw resources created with `VK_SHARING_MODE_CONCURRENT` and imported with `createFrom`,
  built only if the same-family measurement shows a reason.
- The completion edge is `QRhi::finish()` on the job's own QRhi (it waits for that QRhi's queue only), or a fence on
  raw submissions; `endOffscreenFrame` waits only when a readback is pending, so it is never relied on as one.
- Whether a second QRhi may drive the same `VkDevice` on its own queue is undocumented: N0.7 proves it under
  synchronisation validation, or the job thread records raw Vulkan on its queue (the job bodies are written so
  either form records them).
- Teardown: the job thread is quiesced first, then `vkDeviceWaitIdle` (Qt's `vkQueueWaitIdle` covers its own
  queue only), then the device.

*Accepted by the lead, 12 Nov 2026 (N0.7 rounds 1 to 4).* **Verdict: jobs for compute on this vendor (NVIDIA RTX
4090, driver 617.42, Qt 6.12.0), and uploads.** The job service as built: one job thread per device with its own QRhi
on our VkDevice and the second queue of Qt's graphics family (family 0, index 1); the job bodies are QRhi, not raw
Vulkan (a second QRhi on one device proved clean under synchronisation validation). Three slots per job kind; the job
waits on its own `QRhi::finish()` and publishes one atomic generation; the frame driver reads it at frame start and
Qt's QRhi imports the slot with `createFrom`, layouts handed over both ways with `setNativeLayout`.
- Measured (the 4K edge field, 165 Hz, hidden host, 600 frames per form): in-frame, every job frame is late (40 of
  1,200 late, frame GPU p99 about 32 ms); as a job, 0 late and Qt's frame GPU p99 unchanged at 0.02 to 0.04 ms. The
  cost moves to the job's latency, long and uneven (GPU wait median 20 to 33 ms, p99 up to 217 ms with other GPU
  users running; the tail is not attributed), so consumers of class (a) and (b) wait for the completion edge with
  point 2's deadline and in-frame fallback, and simulations stay in the frame (point 2c).
- Hash-identical outputs; no Python thread state on the job thread; synchronisation validation clean on the job path
  (only Qt 6.12.0's finding A, every QRhi texture's creation); twelve retirements with GPU work in flight by both
  routes without a crash, handle growth beyond the driver's 3 per device, or a leak; 60 s at rest: 0 wake-ups.
- Limits: the host's scene is light (frame GPU 0.02 ms), so contention under a heavy Visualizer frame is not yet
  measured (N3.8 re-measures it as D8 row 3 states); AMD and Intel are unmeasured; a device with no second queue in
  the graphics family runs the in-frame form (D6 point 5). The full measurements are in the History file ("D9").

Rules N0.7 gives N3.8 (the core): the job thread uses no other thread, so no QPainter and no QImage conversion on the
job thread or the render thread (QPainter's large antialiased fills into a non-premultiplied image start Qt GUI's
pooled threads, finding F of the facts document's section I); the core's render targets keep their contents
(`PreserveColorContents`) and are primed once at creation, and again before a loading pass after any readback or
sampling (findings B and C); the core never grabs the swapchain (finding D: Qt Quick's `grabWindow` on Vulkan); slots
are imported into Qt's QRhi with `createFrom` and their layouts handed over with `setNativeLayout` both ways;
retirement releases Qt's wrappers of the slots first, then quiesces the job thread, then the device waits idle; a
device's job QRhi takes debug markers when validation is on. Owed: the validated N0.6 device rerun with the
prime-after-readback fix (N0.7 build round 4); the A excuse goes with the next Qt 6.12 patch release.

**As built (N3.8, 14 Nov 2026; the service's shape, written before its code, `native/core/src/job_service.h`).** The
first job is a photo's upload and its GPU mips into one of N4.a's core-owned textures (D13 point 4).
1. *One job service per device.* The module's Vulkan device asks for two queues of Qt's graphics family when the family
   has them (index 0 Qt's, index 1 the job's, priority 1.0 and 0.5, N0.6's layout); a family with one queue gets no
   service, and every job runs in its in-frame form (D6 point 5). The service object exists from the device's creation;
   its thread and its QRhi (on our `VkDevice`, the job queue, its own allocator: facts C1) are created at the first job,
   so a device that never uploads a photo holds neither. One `QThread` without an event loop, parked on a
   `QWaitCondition`: no polling, no timer, every return from the wait counted. A job QRhi that cannot be created fails
   the service closed: every job then runs in its in-frame form.
2. *Jobs own every input.* An upload job holds the image's pixels (N4.a's `TextureImage`, shared and immutable), its
   size and whether it has mips; it reads nothing of a live frame, of the item or of Qt's QRhi. It creates its output in
   the job QRhi, one new texture per image (never a slot a frame may be reading, so no queue writes what another reads),
   records the upload and the mips, submits, drops the pixels, then waits for its own queue with `QRhi::finish()` on its
   own thread.
3. *The latch.* Each job is a ticket with one atomic state (queued, running, done, failed, cancelled, abandoned).
   Publication is the job thread's compare-and-set from running to done, after the result (the native image and its
   layout) is written; the job thread then asks the item for a frame (a queued `update()` on the GUI thread through the
   item's notifier, never a call into the item from the job thread). The consumer reads its tickets at its record (the
   frame edge, render thread). An item's textures commit together: one record swaps every changed texture of the item,
   and only once every changed texture's job is done or failed (a transition never pairs a new picture with an old
   one). Until then the textures it holds are drawn (the old picture stays; an item's first picture draws nothing until
   its job is done, under the card's own fade). Qt's QRhi imports a done job's image with `createFrom` and the job's
   layout. A frame never waits for a job.
4. *The in-frame form always exists* (point 5): the same upload recorded into Qt's frame, N4.a's path. It runs on
   OpenGL (no second context), on a Vulkan device without a second queue, for a job that failed (fail closed: the
   ticket keeps the pixels until the job recorded them, and the commit uploads them in the frame), and under the
   harness control `in_frame` (the measurement both ways). Both forms write the same texture; only when differs.
5. *Cancellation.* A superseded image (a new one of the same name) or a removed texture cancels its ticket by
   compare-and-set: a queued job never runs; a running one drops its output on its own thread after its GPU wait (Qt
   never saw it); a job that published before the cancel landed hands its output to the consumer, which releases it at
   once (never sampled).
6. *Lifetime against Qt's frames.* A published image is released (on the job thread, by its own QRhi) only after the
   last Qt frame that sampled it completed: the consumer hands the replaced image to its window's retire list stamped
   with the frame edge of its last use, and the frame driver releases it at the edge `stamp + FramesInFlight` (Qt's
   `beginFrame` of that frame waited for the stamped one), or at once after `QRhi::finish()` outside a frame (the scene
   graph's invalidation, the driver's release). An entry no driver released stays held until the service stops, after
   Qt's QRhi is gone. Releases wake the job thread once per image change, never at rest.
7. *Teardown* (point 6, D1's barrier). The device's destruction quiesces the service first, on the thread that destroys
   the device and never in the GUI's close: the job in flight is abandoned (dropped unpublished after its own GPU wait),
   queued jobs are abandoned, every image the service still holds is destroyed, its QRhi is destroyed (its own queue
   idle) and the thread joined; then `vkDeviceWaitIdle` and the device. A content released with jobs in flight (its node
   deleted) cancels them; nothing waits on the render thread.
8. *The destruction barrier sees them* (the N2.5 audit's L8): process-wide counts of jobs queued and running, the
   services' images and bytes, images retiring and job threads, beside N4.a's texture counts, read by
   `RuntimeDestructionBarrier` as pending native work; all zero once a retired generation's items are gone.
9. *Lost textures are an edge.* When a content finds a sampled texture lost (a node made again, a texture that could
   not be created), its item's owner is called once on the GUI thread with the names (`NativeMode.on_textures_lost`),
   never left to a state read.
10. *Nothing at rest.* No job, no wake-up, no retire entry and no record at rest; the frame edge's only addition is one
    atomic read of the window's retire count.

*Amended by the N3.8 audit (`Docs/Future_Work/Audit_2026-11-14_N38.md`, fixed in ABI 15 with N5.7a).* Point 6: a
window's frame edges are counted once per rendered frame whatever number of drivers sees it (M1: the first driver's
`beforeRendering` counts, the window's `afterRendering` opens the next count), and the retire list asks its window for
the frames its release waits for (M2: a queued `update()` per frame while an entry is left; before, a window at rest
after a photo change held the replaced 4K output). Point 8: the barrier waits for work in flight only (M3: jobs queued or
running, releases pending, outputs retiring; textures and fronts that live items hold are process-wide and are proved
released by each item's destruction). Point 4 and 1: an upload's completion is fenced on the job queue and a lost device
fails the service closed (L1); a thread that does not start fails it closed too (L3). Point 3: a failed import switches
none of the item's textures (L5, two phases). The running job is read by its constant fields only (L2); the lost
listener goes with the owner's retire (L4).

## D10. The Vulkan rehearsal path and the flip gate (decided 12 Nov 2026)

**The problem this solves.** One window has one backend, and a Vulkan window cannot host a Python OpenGL node.
The product's window therefore stays on OpenGL until the last Python renderer retires, which is months of ports.
If Vulkan runs only in hidden hosts until then, the "front strong stable face" would get its first real-window
hours on the day it becomes the default. That is the largest risk in the whole direction, and it is avoidable.

**The decision.**

1. **One backend owner, from the first port.** `rendering/quick/bootstrap.py` chooses the backend once per
   process. Until the flip the choice comes from a diagnostic command-line switch (never an environment variable)
   and Vulkan is run by the lead only, bounded, on Display 1 (`tools/d1_run.py`). After the flip the same owner
   reads a setting, Vulkan by default.
2. **On Vulkan, a custom surface without a native renderer is not created.** A mode that is not ported is not
   offered there; a transition that is not ported falls back to Crossfade. There is never a Python OpenGL node in
   a Vulkan window. This small "available on this backend" answer in the capability registries is the only
   migration-time mechanism, and it goes when the last Python renderer goes.
3. **The background family is built early.** The shared fullscreen pass, the native presenter and the native
   backdrop (D7) come directly after Spectrum, so the rehearsal window shows the real product: wallpaper, a
   transition, cards on materials, one Visualizer. Each later port adds to it.
4. **How production on OpenGL switches.** Visualizer modes switch one at a time, each at its own parity (a native
   item beside the Python background in the OpenGL window is the mixed window P1 analysed). The background family
   (presenter, backdrop, all transitions) switches as one unit, when its last transition reaches parity: a native
   presenter under Python transitions would need a hybrid that is thrown away afterwards. Until that switch a
   ported transition's Python renderer stays in production on OpenGL and is deleted at the switch; it is never a
   second permanent renderer.
5. **Both backends at every port.** A port is done when it has its OpenGL parity record against the Python
   renderer *and* its Vulkan record against the native OpenGL result in the hidden host, and the lead has run the
   rehearsal once with it.

**The flip gate (P3.5).** Vulkan becomes the default when all of these hold: no Python OpenGL node is left in any
Qt Quick surface of the process (the Studio's preview and window, the hidden hosts of the tools included, since
the graphics API is process-wide); every port has both records; the rehearsal has run across the lead's checklist
(start, wallpaper, transition, material card, each Visualizer, a Settings round trip, a Studio session, exit,
resize and DPI change, display sleep and wake) with no Vulkan-only defect open; the start-up fallback is proved
by a forced device failure; translucent windows are settled (D7 point 8); a frozen GitHub build runs on
Vulkan on Display 1; and one load session after the operator's yes shows Vulkan no worse than OpenGL. OpenGL then
stays selectable in Settings as the fallback.

**As built (N2.7, 13 Nov 2026; Python only, on the module of 2bec597a).**
- The owner is `rendering/quick/bootstrap.py`: `configure_quick_graphics` chooses once (the request, else
  `--graphics-backend=vulkan|opengl` from `core.diagnostics.experiment_flags`, else OpenGL) and every backend gets the
  same OpenGL surface format and attributes; `start_quick_backend` (after the application, before any window, called
  by `main.py`) loads the module and creates the process instance on Vulkan; `active_quick_backend()` and
  `quick_backend_api()` answer for the process. The lead runs it with `tools/d1_run.py --app-arg=--graphics-backend=vulkan`.
- D6 on the product window: `QuickDisplayWindow` hands itself to the module in its constructor
  (`host_or_quit_quick_window`; on OpenGL it connects the GL 4.6 validation instead, as before). A window that cannot
  be hosted quits through `request_application_quit`, as the OpenGL validation does. A destroyed window closes its
  host; the device goes with the window (facts A7).
- Fallback (D6 point 5): a module or instance failure sets OpenGL before any window exists and logs why. Each Vulkan
  start writes `<data root>/state/graphics_backend/vulkan_start_<pid>.json` ("pending") before the module loads; the
  first frame a hosted window presents, or a clean quit, removes it; a handled failure marks it "failed". The next
  Vulkan start reads every record that is failed, unreadable, or pending from a process no longer running (pid and
  creation time), removes them and runs OpenGL with the reason logged (`QuickBackend.reason`); the start after tries
  Vulkan again. Controls: a module that cannot load, a device that fails in the module itself (no instance), a process
  that dies before its first frame; each next start ran OpenGL (`tests/test_quick_backend_owner.py`).
- "Available on this backend": `renderer_backends` on `VisualizerModeDescriptor` and `TransitionDescriptor` (every one
  `("opengl",)`; a port adds `"vulkan"`), `BACKGROUND_FAMILY_BACKENDS` in `rendering/transition_registry.py`. On a backend
  without a renderer: the Visualizer starts the next enabled mode with one or is not built
  (`resolve_backend_mode`, `VisualizerHostBinding.construct`); activation requests and the double-click cycle skip the
  mode; a transition resolves to Crossfade (`resolve_backend_transition_name` in `resolve_quick_transition_spec`); the
  background and backdrop items create no node. On OpenGL nothing changes: `tools/conventions_identity.py` recorded
  every transition and mode with and without N2.7, all identical, GL calls equal.
- Facts J1 in the owner: `native_hidden_host` creates the process's one hidden host at the first request, keeps it,
  refuses another size, and closes it at the application's quit (a process ending with it alive did not exit).
- Not yet on Vulkan, and so not in the rehearsal: the wallpaper, the card backdrop and every transition (the background
  family), every Visualizer mode but Spectrum (N2.5, 14 Nov: `renderer_backends` `("opengl", "vulkan")`, drawn by
  the native core's item through `rendering/quick/visualizer/native_route.py`), and every mode's Studio: its preview
  is the mode's Python renderer in an OpenGL render node, so `has_studio` answers False on a backend outside
  `STUDIO_PREVIEW_BACKENDS` (`ui/studio/registry.py`, OpenGL only) until a native preview exists. Settings' Visualizers page keeps every mode listed (a selection there is a
  persisted choice; the runtime resolves it as above) and, since 14 Nov, greys a mode with no renderer on the running
  backend (its pill and admission checkbox, each with a one-line reason, and one line on Setup); on OpenGL nothing
  is greyed. Qt Quick's own `.qsb` shaders (`surface_material`,
  `widget_glow`, `text_legibility`) carried SPIR-V from the first (qsb always bakes it) beside GLSL 460; since 14 Nov
  `tools/regen_qrc.py --shaders` bakes them for every shipped target (GLSL 460 kept first, so OpenGL draws with the
  same variant), and `tests/test_quick_shader_packs.py` proves they draw on Vulkan in the hidden host.
- The reveal (14 Nov, 41671a42): with no background renderer on the backend no wallpaper frame can draw, so a
  display reveals on its first presented frame (`DisplayManager._startup_reveal_admits`, the one rule for both
  backends; `QuickSceneReadiness.frame_presented` is published only there); on OpenGL the reveal still waits for the
  background renderer's intentional base frame and the first authored wallpaper.
- The exit (14 Nov, R-207): every exiting stop arms the terminal destruction barrier, whatever its reason, so
  `--exit-after` and a failed start wait for their Quick windows to retire before the quit (a Vulkan window alive at
  process end crashed it). The exits that bypass that stop (the barrier timeouts, the failed Settings, CUSTOM and
  monitor teardowns, a failed replacement) release their Quick windows first and end the loop from the last
  window's `destroyed` (`engine/runtime_destruction.release_quick_windows_then`), and a second exiting stop joins the
  terminal drain instead of cancelling it (14 Nov, R-209). That release is bounded: a deletion waits for the loop
  level it was posted at, so a modal loop entered after it holds every `destroyed` until it ends; after
  `_RELEASE_BOUND_MS` the exit runs anyway, logged critical (the one timer admitted there, since the process is ending
  on a failure; `tests/test_quick_release_bound.py`). The Studio's own window needs no release of its own: the quit
  edge closes it (`close_for_quit`) and the loop's end destroys it; on the core's device it would crash the exit if it
  were left alive (`tests/test_studio_exit_vulkan.py`, its negative control).

## D11. The Qt version the core is built against (decided 12 Nov 2026)

The core is compiled against the exact Qt of the shipped PySide6 (P1), and every upgrade reruns every parity gate
on both backends. So the version is chosen once, at the entry to the first C++ slice (plan N0.8), not drifted
into: if a PySide6 release newer than 6.11.2 is available whose QRhi has indirect draws (Qt's documentation lists
`DrawIndirect`, `DrawIndirectMulti` and `ShaderDrawParameters` for 6.12; they are absent from the 6.11.2 header),
the lead takes the upgrade first and one service of D5.3 disappears. After that, Qt is upgraded only between stages
of the ladder, through a scripted step: fetch the matching SDK, rebuild, both backends' parity gates, a frozen build.

*Current rule (lead, 12 Nov 2026, then the operator): take Qt 6.12 before N2.1; the venv is bumped only while no agent
is running tests. The operator made it a plain bump to 6.12: the checkpoint's whole-suite, GitHub frozen build and
Display 1 card-edge check was not taken, and no frozen product has yet been built on 6.12 (the plan's 1B.14 owns
that). The fallback if a regression is not ours is 6.11.3.* The project is on Qt 6.12 (PySide6 6.12.0, whose QRhi has `drawIndirect`, `drawIndexedIndirect`, `DrawIndirect`, `DrawIndirectMulti`
and `ShaderDrawParameters`), so D5.3's indirect-draw service and D5.6 row 14's restructured pass are retired. Nothing
else D5.3 or D5.6 lists is gained: 6.12 still has no RG16F, RG32F or R11G11B10F, still offers no sampling of a
resolved multisample colour texture, and QRhi still has "no source or binary compatibility guarantees". Open
risks recorded with the research: a `.0` release; a Qt Quick scene-graph or clip change could touch the protected
optimisations (ce07b991, 07486d83, 985b9d53), which the suite and clip oracles must show unchanged;
`DrawIndirectMulti` backend coverage (D3D11 in particular) needs a per-backend feature check. The research of the
PyPI and Qt documentation facts and the recommendation text are in the History file ("D11").

## D12. Generic mode content: a mode drawn by the core from data alone (N2.9, 14 Nov 2026; proposed by the High agent)

Port rule (g) made Settings and Studio work rebuild-free for a ported mode, but its per-frame values were hand-written
C++ and the reader knew only the schemas compiled into `frame_abi_generated.h`, so a new mode or field meant a module
build, which the lead's rule of 14 Nov forbids while a mode is iterated ("new modes are built on the native core
only, through its generic mode content").

**The decision.**
1. *The schema is data.* A mode's `NativeSchema` is handed to the core when its stream is bound, in the compiled
   table's own row shape (`schema_table_entry`: `[name, kind, count, offset, check, limit]`, the check order, the
   fingerprint). The core (`mode_schema.h`, `RuntimeSchema`) validates it as the transport rule demands (a well-formed
   native id agreeing with its mode code and version; a record a multiple of 16; every field at its kind's alignment,
   after the header words, inside the record and overlapping none; range rules on u32 scalars only, each once in the
   check order), recomputes its fingerprint the way `NativeLayout.fingerprint` does, refuses a mode id or code that
   disagrees with the compiled mode table, and never replaces a compiled schema. The packet reader admits the runtime
   schema beside the compiled table by the same rules (its mode code is a known mode; head admission by id, version and
   size; the record's range rules after the copy). The compiled table keeps only the schemas a hand-written consumer
   reads (Spectrum). Mode codes stay append-only: the Python face tolerates codes appended after a module was built.
   *Round 2 (lead's decision on audit N29 M5.1):* the Python registry is split. `_SCHEMA_MODULES` holds the schemas the
   module compiles (the C++ header's table, compared with a built module's by `schema_table_differences`);
   `_RUNTIME_SCHEMA_MODULES` the runtime schemas, known to the transport (`native_schemas`) and handed over at bind, so
   a new one never raises `SchemaTableMismatch`. A mode is in one registry only. A runtime schema naming a compiled
   mode at any version is refused (audit N29 L6).
2. *One block of its own per pass, filled by name from three sources* (round 2, the lead's binding decision on audit
   N29 M5; it supersedes round 1's two blocks `ModeSettings` and `ModeFrame`, which no product shader has). A pass's
   block (any name, any binding but 17) is the product 2D shaders' own (`OscilloscopeDraw`, `DevcurveDraw`,
   `BubbleDraw`). Each member is filled from exactly one source, by its name: the core's conventions (`kModeCoreMembers`
   in `mode_content.cpp`, mirrored as `MODE_CORE_MEMBERS` in `rendering/native/mode.py` and held equal by a test: the
   minimum the Oscilloscope, Spline Curve and Bubble Python renderers take from the card per frame, `uMatrix` (zeros:
   the core draws its own triangle), `uItemSize`, `uContentRotationQuarters`, `u_resolution`, `u_dpr`,
   `u_viewport_origin_px` (0, 0), `u_quick_item_coords` (1), `u_fade`, `u_border_width`, plus Spectrum's target maps
   `u_item_from_frag*`, `u_window_from_target*` and `u_target_px`), read from the item's card (`NativeMode.card`) and
   the target; the settings (the spec's values and anything mode-derived, from Python, packed when they change); and
   the record's fields (packed per accepted frame by `packRecordField`: an f64 a float, an f64x4 a vec4, a u32 a uint,
   a bool, or an int or float under a range rule that fits it (L7), arrays the same length). Refused with a reason: a
   setting or a record field no pass declares (unknown); a member no source fills (unfilled); a name with two owners (a
   setting or a field naming a core member, a setting naming a field); a pass declaring a core member at another size.
   Checked when the program meets the schema (at bind and at program) and when settings arrive, so a mode whose data
   does not match its shaders never draws zeros.
3. *Passes are data, and only what the 2D modes need.* One to eight full-target passes over the composite surface, in
   order, each with a blend (`replace`, `alpha` (Spectrum's straight-alpha over), `premultiplied`, `add` (light added,
   alpha kept)), after a clearing draw, with the core's own triangle (`shaders/mode.vert`, which gives `v_uv` at
   location 0, 0 to 1 over the target). A pass declares its own block, optionally the conventions block (bound at 17
   only to a pass that declares it) and `v_uv`, and nothing else: a texture, a sampler, storage, a push constant, a
   second block of its own, a block at binding 17 (M3) or another input is refused. Over the real `.qsb` packs,
   Oscilloscope's and Spline Curve's fragment shaders are admitted as they are; Bubble's is refused for its two samplers
   alone (`u_ambient_texture`, the water-decoration underlay, and `u_ambient_light`, the glowing particles' linear
   light, both from its offscreen ambient render). Reading an earlier pass or an image, depth, more targets, compute or
   a new resource is a primitive with its own C++ and harness, used by every mode as data afterwards: Bubble's two
   textures wait for the sampling primitive (plan N4.a; superseded for samplers and the `vUv` input by D13). Oscilloscope's Quick renderer no longer draws
   `oscilloscope.frag` (an instanced beam from a storage buffer, its own scene target and bloom): its port needs those
   primitives too, whatever this pass admits.
4. *A program keeps its settings.* A new program is packed against the settings given with it, else the current ones,
   and is refused (the drawn one kept) when they do not fit. Spectrum's program follows the same rule (audit 14 Nov, L4).
5. *The item.* `ModeSource`/`ModeContent` follow the Spectrum item's rules: bound by mapping name on the GUI thread,
   read at the item's sync on the render thread, retired without waiting and released by the render thread's retire
   job (D1), the same admission (a present frame, a current source while playing), nothing recorded at rest. One
   content per composite item. Round 2 (audit N29 M1, M2, M4, L1, L10): the two items share one implementation
   (`stream_source.h`: `StreamSource` for the stream, `ContentLatch` for a content that fails to build: recorded once,
   nothing created again for the same inputs, tried once more when the program, settings, card, stream or target
   changes). A refused frame (a value with no defined conversion) never blanks the card: the last drawn frame stays,
   the refusal counted with its reason. A composite item hides and shows by a fade (`fade_ms`; the product route fades
   out on failure over the Visualizer's activation fade and back in after it; a new activation's first frame shows at
   once under the card's own content fade, so rule (a) holds from it). The window's framebuffer is Qt's own swapchain
   or redirect target (`CompositeItem.window_pixels`), never the logical size times the scale nor a platform call.

**Rejected.** A per-mode C++ renderer (the rule it replaces). A mapping table from record fields to uniform names
(a second table to drift; the name is the contract). Letting a record field go unused or a member be left at zero
(silent: the very failure the refusals exist for). Moving Spectrum onto the generic path now: its per-frame arithmetic
(the bar layout, the resample, the clock) is C++ ported line for line and proved at parity; it moves only when that
arithmetic moves to its simulation, with its parity rerun, as one change.

**How a new mode is built:** `native/core/README.md`, "How a new mode is built". The worked example is the harness-only
mode `native/core/python/probe_rings/` (a simulation, two passes, a spec; never registered).

**As proved (round 2, ABI 10, merged at 9181aafc; N29 PASS).** `generic_mode_check.py` on the built module (the blocks from the three sources against
an independent packer with every refusal, the product packs' admission and Bubble's sampler refusal, the reader by the
runtime schema, the draw on OpenGL and Vulkan at dpr 1 and 1.5 with shader, spec, shader-and-spec and simulation
changes and no rebuild, a refused frame keeping the card, the latch, the fade, nothing at rest, GPU time per pass, the
framebuffer at 2560x1440 at 150 % on both backends, Vulkan within 1 level of OpenGL, validation clean), with N2.3's,
N2.5's and rule (a)'s harnesses unchanged.

## D13. The fullscreen pass and image sampling as a primitive (N4.a, 14 Nov 2026; proposed by the High agent)

Supersedes D12 point 3's refusal of samplers and its "v_uv only" input; the rest of D12 stands.

The first consumers of the background layer (N5.7a's presenter, N5.2a's seven transitions: Crossfade, Burn, Particle,
Ripple, Slide, Warp Dissolve, Wipe) each draw one fragment between two pictures through
`rendering/quick/transitions/fullscreen_pass.py`, and Bubble samples two textures from its ambient render, so N2.9's
pass (every sampler refused, `v_uv` only) could draw none of them. What the product fragments read (`vUv` y up,
`uOldTex`/`uNewTex` at bindings 0 and 1, one pass block at binding 18; `v_uv` y down for the 2D modes) is in the
History file ("D13").

**The decision.**
1. *The location-0 input is filled by its name.* The core's triangle carries both quads' uv at each vertex (exact
   values, from the one target correction: `conventions.h`), and each pass's pipeline feeds the one its fragment names
   (`v_uv`, or `vUv`) to `shaders/mode.vert`. Any other input is refused. On OpenGL and Vulkan `v_uv` is N2.9's value
   for value. No matrix or uniform carries the convention, and the product files are unchanged.
2. *A core member means one thing.* The core's `u_resolution` is the logical size (the 2D modes'); the three
   transitions that meant the viewport's pixels now name them `u_target_px`, the core's member for the target's pixels
   (an invisible change, drawn hash-identical on real photos at nine progress values:
   `.artifacts/evidence/native_core/n4_a/20261114_rename_identity/`).
3. *Samplers are data.* A pass names its samplers in the program's declaration, each bound by name to one of the item's
   textures with its sampler state beside it (filter, wrap, mip filter); the binding is the pack's own. Refused with
   the reason: unbound, unknown, doubly bound (by name or binding), at binding 17 or at the pass block's binding, not a
   `sampler2D`, a mip sampler over a texture without mips. Separate textures and samplers, storage and push constants
   stay refused.
4. *Textures are the core's.* Up to 8 named textures an item, RGBA8 from pixels Python holds, copied once and uploaded
   once on the render thread at the next record (mips generated on the GPU on request), the copy then dropped; the same
   object for an image of the same size; released on the render thread at the next record when removed, and with the
   content when Qt deletes the node. A node made again reports its textures lost and draws nothing until they are sent
   again (the owner keeps its pixels). Counted process-wide for the lifecycle proofs and the destruction barrier's
   reading (`composite_live`: `mode_textures`, `mode_texture_bytes`, `mode_texture_images`). N3.8 moves the upload to
   the job thread; the presenter's photo upload is its first job.
5. *The per-frame values of a transition* (`u_progress`, `u_time`) ride on a record in the harness (a runtime schema
   outside `MODE_CODES`); every other value is a setting, packed when it changes, and the Python renderer's
   `FullscreenPassRenderer.block_values` is the one owner of them all. Where the product's transition clock lives
   (a record from the GUI thread, or the progress computed by the core from the run's start and duration) is N5.2a's.
6. *An unbound stream forgets its schema*, so a program for another schema can be given before the next bind (found
   writing the harness: switching transition on one item was refused both ways).

**Rejected.** A second pass layer for images (the rule this replaces). Rewriting the transitions' fragments to
`v_uv` or to a texture block of the core's (both shapes would differ from the Python renderer's file). A placeholder
texture bound while a picture is missing (draws a wrong picture instead of none). Keeping the core's copy of every
photo to survive a rebuilt node (twice the memory of every displayed photo for a rare event).

**As proved (ABI 11 build round, merged at 8394b992).** `native/core/python/fullscreen_pass_check.py` (rule (a): OpenGL
equal to the production GL host; rule (b): Vulkan within 1 level; rule (e): GPU time and nothing at rest; rule (g);
the textures' lifetime; Vulkan validation clean), with N2.9's `generic_mode_check.py` unchanged in its verdict.

## D1, D2, D3 and the transport rule

*Decided by the lead, 12 Nov 2026 (answers in "Lead decisions on the N0 drafts"). The drafts, with every "today"
claim read at `7ac980d7`, are in the History file ("D1, D2, D3 and the transport rule"). D9's job thread uses D1's
barrier.*

### What exists today (the ground the three contracts stand on)

The inventory (file:line, read at `7ac980d7`) moved to the History file. The facts the contracts stand on: the frame
stream is one `PacketMailbox` per Visualizer session over the frame packet ABI (a 64-byte header, three slots, a
seqlock per slot, `consumed_sequence` written by the reader); the main process owns, closes and unlinks the mapping
and the worker attaches by name; the only reader was Python on the GUI thread and the render thread receives an
immutable snapshot; three readers of different strength call the mailbox (consuming take, peek, held frame); the
retained-frame drop edge exists once, in Python (R-184); slot identity is in the slot under the seqlock, so a head
read needs no payload, and `payload_schema` was written and read by nobody.

### D1. The native reader against the GUI thread closing the mapping (proposed; decided by the lead 12 Nov)

The hazard: the render thread reads slots through a raw pointer while the GUI thread closes, remaps, retires or
replaces the mapping; Python's `BufferError` guard does not exist for a C++ pointer.

1. **The core maps its own view by name** (`OpenFileMapping`/`MapViewOfFile`; `shm_open`/`mmap` on POSIX), validates
   magic, ABI and shape exactly as `_validate` does, and owns that view until its release edge. The name is plain
   data the activation carries (`mapping_name`). A mapped view keeps the section alive after the owner closes or
   unlinks the name, so the owner's close never unmaps memory being copied. A name that no longer opens means the
   stream is retired, never an error loop. The bounded GUI wait is rejected (it can deadlock against Qt's
   synchronisation of the two threads).
2. **The reader has three states, changed by one atomic: `open`, `retiring`, `retired`.** The GUI side's retire edge
   (the edge of `link.retire()`, which never waits) sets `retiring` and schedules the reader's release on the render
   thread (`QQuickWindow::scheduleRenderJob`, or `sceneGraphInvalidated` at window destruction). The render thread, at
   its next frame edge or job, finishes or abandons any copy, unmaps its view and any held frame, and stores
   `retired`. A frame never starts a copy once `retiring` is set. The GUI never waits for `retired`.
3. **A remap is a new stream, not a new pointer.** `commit_capacity` and worker replacement hand the core a new
   `(mapping name, engine generation, activation)` key; the core opens and validates the new view, then retires the
   old one. Frames of the old stream are not presented after the new stream's first frame is accepted.

D9's job thread holds a generation counter on the reader state (never a pointer into the mapping); a retire request
marks the stream's jobs abandoned; the job thread checks the stream state before it publishes; the device is not
destroyed until the render-thread retire job and the job thread have both reached their quiescent point (a join in
the device's destruction, never in the GUI thread's close).

**Liveness is per stream.** Writer-side liveness is `watch_cadence_liveness` (kept). Reader-side: the core keeps per
stream, readable by the GUI without a lock, `last_accepted_sequence`, `copies_started` and `copies_finished`;
`copies_started != copies_finished` across two observations a second apart is a reader stalled inside a copy and is
that stream's failure (the owner's existing failure edge), not a worker failure. The GUI reads the counters only on
the heartbeat edge and edges it already has: no timer, thread or poll.

**Tests that fail without it** (harness C++ test plus a Python driver, each with a negative control; the full list is
in the History file): close during a paused copy and a capacity remap (the copy completes against the pinned view,
the frame is discarded, the next stream's first frame is accepted; control: a reader borrowing Python's pointer);
resize and remap with frames in flight (no old frame after the new one's first; both views released once); retire
with the render thread parked or idle (the GUI call does not wait); worker replacement mid-publish (torn slot never
accepted); per-stream liveness (a paused reader is reported while worker heartbeats answer).

### D2. One consuming reader, a non-consuming head read, and the drop edge (proposed; decided by the lead 12 Nov)

**Rule.** Once a stream is native, the core is the only reader that consumes: only it writes `consumed_sequence` and
decodes payloads. The Python owner reads the slot head only. A stream is Python-consumed or native-consumed, chosen
at activation, never both.

- **Acknowledgement edge: the accept edge** (parity with today's `take`, decided 12 Nov; not the swap): after the
  whole frame is copied and validated (both seqlock reads, identity equal to the expected stream, schema known) and
  after the frame's protected-edge mask has been handed to the frame driver's edge handler, before the frame is
  recorded. A rejected frame (torn, wrong identity, unknown schema) is not acknowledged.
- **`read_head()`** returns, from the newest whole slot, only the 64-byte head (sequence, flags, protected-edge mask,
  runtime and engine generation, activation id, mode code, logical timestamp) under the seqlock check. It copies
  nothing, does not move `accepted` and does not write `consumed_sequence`. It serves every Python read that is not
  the consumer (`_worker_waiting_for_fresh_frame`, "anything unread").
- **The drop edge (R-184)**: every frame a native reader retains is tagged `(stream key, sequence)`. One
  `drop_retained_frame()` edge, posted from the GUI thread and applied at the core's next frame edge (a flag read, not
  a per-frame check), is raised by the same owner call sites as today (a hidden activation commit that discards the
  pending snapshot, a recovery hold's drop, display power off, retire). It clears the retained frame and keeps the
  stream bound and the geometry resident (D3). No sequence at or below the watermark is accepted again, so a head
  read or a late wake cannot resurrect a dropped frame. As built (ABI 9, audit 14 Nov low 2): the retained frame is
  always the last accepted one, so the accepted watermark is the drop's; the reader keeps no `dropped_through` of
  its own. The drop round's control is `head_resets_watermark`, which resets `accepted` and resurrects the frame.

**Tests that fail without it:** one consumer (`consumed_sequence` written only by the core; control: the owner calls
`take()`); head read non-consuming; the R-184 shape (publish, take, discard and drop in one GUI turn, card empty at the
next render; control: remove the drop call); no resurrection (drop at S, head read and replayed wake for S, S+2
presented; control: reset the watermark on a head read).

### D3. Extruded Bubble geometry once per revision (proposed; decided by the lead 12 Nov)

Today the drift families' geometry travels inside every frame and the slot is sized for the maximum, and the revision
counter (`itertools.count`) is unique inside one process only. The OpenGL solver deleted old buffers before
`_allocate` could fail and leaked old rows on a failed dispatch (fixed in the OpenGL renderer in N1, R-195).

1. **Identity.** A geometry resource is keyed by `(worker namespace, engine generation, activation id, family,
   geometry revision, capacity)`. The worker namespace is the stream's mapping token, so a replacement worker or a
   remap is a different namespace. Bare revision is never an identity.
2. **Geometry is not in the frame.** The frame carries the key of each live family and the small per-frame state
   (the step record, knot decisions, counts, controls). The bytes travel once per key in a geometry arena: a second
   mapping created and owned by the main process, two banks per family. The worker writes the back bank completely
   before it publishes a frame naming its key; the reader uploads when it first sees a key it does not hold; a bank is
   rewritten only after the core acknowledged a frame naming a different key for that family. The slot shrinks to the
   base envelope; the arena's size is part of admission.
3. **Residency and release, one rule per edge.** Per-key residency states: `requested`, `uploading`, `resident`,
   `failed`, `retiring`.
   - Geometry change (new key, same activation): the old key stays resident until the new is resident and one frame
     using it was recorded; never an empty frame between.
   - Failed swap or upload failure: the new key goes `failed` (one logged error, no per-frame retry; retry only for a
     new key), the old key stays resident and in use, and nothing is deleted before the replacement exists.
   - Capacity growth, same key: a new key, with the history rows copied from the old residency before release.
   - Mode or activation change, drop edge, retire, device loss, window destruction: all residencies of the stream are
     released on the render thread by the D1 retire job; device loss releases without reading back.
   - Counting: steady state one live key per family, transient two, after teardown zero.
4. **Oracle data stays off the wire.** The native frame schema has no array and no `source` field; the worker keeps
   `source` for `MaterialDriftReference` only. A frame built with a non-empty `source` is refused at encode.
5. **Per-frame state is separate and small:** the step record, the knot decisions and the counts.

**Tests that fail without it:** identity (two streams both publish "revision 1" with different geometry; control: key
on revision alone); once per key (upload counter; frame size independent of capacity); failed swap (allocation failure
injected, old buffers still drawn, logged once; control: delete-before-allocate); release (residency count zero after
teardown, drop, mode switch, window destruction; control: skip the retire job); oracle off the wire.

### The transport rule (proposed)

1. **Nothing crosses through the stdlib resource sharer.** An ordered control refuses a sharer-backed `Connection` or
   socket on every platform (`core/process/control_messages.py`): the sharer keeps a sender-side duplicate that a
   worker dying before decoding never collects. The core adds no descriptor of its own through any queue.
2. **How a handle or mapping reaches a process.** POSIX: a name in the control message, opened by the receiver.
   Windows: a name (named mappings), or a handle duplicated into the exact target process by the supervisor under its
   lock. A new native object that must reach the worker (D3's arena, a job-thread signal) is a mapping name or an
   exact-process duplicate, never a pickled handle.
3. **Fixed-layout per-mode native schemas** (explicit offsets, little-endian, 16-byte aligned, a version), so a native
   reader validates by size and offsets and decodes no tagged stream. The slot's `payload_schema` selects it; both
   readers validate it.
4. **The tagged Python codec namespace is reserved.** `payload_schema` 1 is the Python codec (`CODEC_SCHEMA`); native
   schemas are `0x100 | mode_code` in the low byte and the version in bits 16 to 23; 2 to 0xFF are reserved; mode codes
   are append-only. The numbering was confirmed by the lead.
5. **An unsupported payload fails explicitly.** A reader that does not know a slot's `payload_schema`, mode code or
   schema version refuses the frame at the slot head, before any payload copy: the stream is reported failed (the
   owner's failure edge), a counter and one logged error are recorded, and the frame is not acknowledged or presented.
   It never guesses, skips silently or falls back to the Python decode.

**Tests:** a native reader given an unknown `payload_schema`, mode code, newer schema version, or a size that
disagrees with the layout refuses, counts, does not acknowledge and reports the stream (control: a reader that falls
through to a generic decode); a sharer-backed `Connection` is refused and a native object's transfer leaves no
handle behind after the target dies before decoding; no native schema id equals `CODEC_SCHEMA` and the Python decoder
refuses a native payload.

**As built (N2.3, merged 14 Nov 2026, 8dff805e; module ABI 5; N23 VERDICT PASS on the GitHub-built module).**
- Rules 3 to 5 hold on both readers: `payload_schema` is now read. The numbering of rule 4 is the one shipped
  (`native_schema.native_schema_id`: `(version << 16) | 0x100 | mode_code`); `native_schema.admit_slot_head` is the
  Python reference's head admission and `PacketReader::admit` its C++ twin, check for check. Spectrum's record
  (`spectrum_native_schema.py`) is the only native schema; production still writes the tagged codec (nothing
  configures a native stream before N2.5).
- One table for both readers: `native/core/src/frame_abi_generated.h` is generated from `packet_abi.py` and
  `native_schema.py` by `tools/native_frame_abi_header.py` (`--check` in `tests/test_native_packet_reader_sources.py`);
  `NativeCore.packet_reader` refuses a module whose compiled-in table differs (`SchemaTableMismatch`).
- D1 as built: the reader maps its own view by name (`OpenFileMappingW` and `MapViewOfFile`; a name that no longer
  opens is a retired reader), the three states are one atomic, every read and head read pins the view and the last
  pin unmaps it, and the liveness counters (`copies_started`, `copies_finished`, `last_accepted_sequence`) are in the
  reader's state. The render-thread retire job and the "close during copy" hook exist since N2.5 (the reader's first
  user; the code decides).
- D2 as built: `read()` is the one consuming read and acknowledges at the accept edge (the slot whole under its
  seqlock, admitted by its head, the expected identity, the record's range rules held), with the frame's
  protected-edge mask retained for the frame; `readHead()` moves nothing; the drop edge clears the retained frame
  and no sequence at or below the watermark is accepted again. The seqlock's loads rely on x86-64 load order and a
  compiler barrier (no `<atomic>`: the module's runtime rule).
- The P3.0 adversarial table (`tools/packet_reader_adversary.py`) runs on the Python reference with its naive
  control and on the C++ reader with a named negative control per case; the in-place writer's race gave 0 mixed
  records in 200,000 reads, and the `skip_seqlock` control read until its first mixed record.

### Questions for the lead (D1 to D3 and the transport rule)

Answered by the lead on 12 Nov (D1: pin by the core's own view plus an asynchronous retire job; D2: the accept edge;
D3: the arena, two banks, and the OpenGL solver's failure order fixed now in N1; transport: the numbering stands).
The questions are in the History file.

## D5, the rest: resources, lifetime, admission, device loss, and what a mode may not do (N0.5)

*Bake targets (doc sweep, 12 Nov 2026): the spike still bakes `100 es`; the product module (`native/core/`) does not
(SPIR-V, GLSL 430, HLSL 5.0, MSL 1.2).*

*Decided by the lead, 12 Nov 2026 (answers in "Lead decisions on the N0 drafts"); this completes D5 and does not
change D5.1 to D5.4, D6, D7, D9 or D10. The draft and its source inventory (GL state sites, accounting, clocks) are
in the History file.*

### Today, in source

Moved to the History file ("D5, the rest"): the renderer Protocol, the host's boundary release, gradual warm-up,
passive accounting, one render thread and context per display, no clock in any mode implementation, no device-loss
handling, and 97 GL state-setting sites in six implementation files (the count the port removes).

### Resource ownership and lifetime (proposed)

**Scopes, outermost first.** Each resource has exactly one owner, in one scope, and is created and destroyed on one
thread.

| Scope | Created | Owns | Destroyed |
|---|---|---|---|
| Process | at module load, before any window (D6.1) | the instance (Vulkan), the shader bake tables (read-only), the pipeline-cache policy | at process exit, after every device |
| Device (one per window, D6.4) | with the window's scene graph, on that window's render thread | samplers, shader-resource-binding layouts, the pipeline cache for that device, static meshes, the D9 job thread and its queue, staging | on `sceneGraphInvalidated` or device loss, after every window-scope resource; before the device itself (D6: windows, then devices, then the instance) |
| Window | the frame driver (D5.2), lazily per layer | the background layer target, the backdrop pyramid (D7), per-surface scene targets, the composite's texture providers | with the window's scene graph; the pyramid also when demand reaches zero (D7 point 2) |
| Surface (a Visualizer card, a transition) | when it is first admitted | its output texture, its mode's resources | when the surface goes away |
| Mode renderer | at the mode's first activation on the window (as `render_host.py:200-203`) | its pass graph, pipelines it alone uses, buffers, textures, geometry residencies (D3) | at the mode boundary after the active mode drew (as `:285-357`), or at teardown |
| Job | by the job thread (D9) | its inputs, its back slot | published, then retired by the frame driver |

**Rules.**
1. Resources are never shared across devices. A display transfer is: the target device's mode renderer is built and
   warmed, its first frame is presented, then the source device's renderer is released (the logical session
   stays; D6 point 4). Nothing vanishes between the two (fade-in on the target, fade-out on the source).
2. Creation and destruction of a device-scope or window-scope resource happens on that device's render thread,
   never on the GUI thread and never from a Python callback (D5.4). Job-scope resources are created on the job
   thread and **released on the render thread** after the completion edge or the D1 retire job.
3. Destruction order is the reverse of creation: mode, surface, window, device, process. A release that fails is
   recorded once and retried at the next boundary or at teardown, never per frame (the host's rule above).
4. Every resource registers itself in the device's ownership table (kind, owner, generation, bytes). The table is
   plain data reported to the existing accounting snapshot (`resource_metrics.py:41-88`); it is incremented at
   create and destroy only, so it costs nothing at rest. `has_resources` stays the per-owner question.
5. Pipelines are keyed by (shader hash, fixed pipeline state, render-pass compatibility) at the device and are
   created only in warm-up units (one per spaced already-rendered frame, next-likely first), never inside a frame
   that draws. The device cache is bounded by the finite set of modes, transitions and primitives; a mode release
   does not destroy pipelines other modes share.
6. Frames in flight: a resource a recorded frame still refers to is never freed while Qt's frames in flight use
   it; release is deferred to the frame edge (QRhi's own `releaseLater` discipline for QRhi objects; the core's raw
   objects follow the same two-frame rule).

**Test that fails without it.** Create and destroy cycles of a mode on a hidden host (the same mode, two alternating,
an injected failed release, a display transfer): the ownership table returns to baseline. Controls: free a resource a
frame in flight still uses (validation layers report it); delete one resource kind's registration (the baseline test
fails).

### Admission and dormancy (proposed)

- **Admission is lazy and edge-driven.** A window gets a device, a frame driver and layer targets when something
  needs them; a mode renderer exists only after its first activation; the backdrop pyramid exists only while the
  demand count is above zero (D7 point 2); the job thread and its QRhi are created at the first job, then parked (D9 point 1).
  Admission of capacity-bound inputs stays what it is today for the frame stream (the activation-time capacity
  envelope, `core/visualizer_engine/frame_capacity.py:12-42`); D3 adds the geometry arena to it.
- **Dormancy is a state with a definition:** a surface that is off, a display that is powered off, a mode that is
  not the active one, a transition that is not running. For each: no pass is recorded, no upload is issued, no
  wake-up is requested, no timer runs, no job is queued. The resources of an inactive *mode* are released at the
  next boundary (as today, `render_host.py:285-357`); the resources of a surface that is merely paused (display power
  off) are kept until the display's power edge says otherwise, and the frame driver records nothing for it.
- **The frame driver at rest records nothing** (D5.2's driver is woken by Qt's `beforeRendering`; with no surface
  dirty and nothing animating it records zero passes: the retained background and the retained card textures are
  simply composited by Qt).
- **Warm-up is the only way a pipeline or a large resource is created while hidden**: one unit per spaced rendered
  frame, next-likely first (the existing host does this, `render_host.py:252-262`). No burst at start-up, no
  polling, no driver thread.

**Test that fails without it.** A hidden host at rest for a minute: zero recorded passes, zero uploads, zero
job-thread wake-ups, ownership table unchanged. Control: a mode that requests a repaint at rest. A mode switch
releases the outgoing mode exactly once.

### Device loss (proposed)

QRhi reports loss (`FrameOpDeviceLost`, `QRhi::isDeviceLost()`); Qt Quick then invalidates and re-initialises the
scene graph.

1. **Detect once, at the frame edge**, from QRhi's result. The core marks the device lost with one atomic and stops
   recording for that device immediately (a lost device records nothing, even if the frame driver is called again).
2. **Release without touching the device**: every window-scope, surface-scope and mode-scope resource is
   dropped by the ownership table walk; destroy calls on a lost device are allowed to fail and their failures are not
   errors. Nothing is read back (nothing is read back from the GPU in production anyway, `extruded_bubble_drift_log.py:11-12`).
3. **The D9 job thread is quiesced by the D1 retire job** and its in-flight jobs are abandoned (D9 point 6).
4. **Rebuild from the last packet, through the ordinary admission path**: after Qt re-initialises the scene graph,
   the frame driver is `Absent`, the next frame's admission creates the targets and the mode renderer, warm-up runs,
   and the mode is revealed as an activation is (hidden, then faded in; never a vanish, never an abrupt pop: the
   card fades out before the rebuild if the loss is observed while visible, and in after). The logical side keeps its
   state; state that exists only in GPU memory (the drift solver's per-mote state) restarts as the solver already
   does when the render falls behind its history (`extruded_bubble_drift_solver.py:554-556`, "a lifecycle event").
5. **Bounded (lead, 12 Nov).** A second device loss on a window before 3,600 presented frames since its rebuild is a
   backend failure: the Visualizer on that window fades out and parks, the failure is remembered by D6 point 5's state
   file so the next start uses OpenGL, and there is never a teardown from Vulkan to OpenGL in a running process.
   Counted in frames at the frame edge, never by a timer. The drift solver's GPU-only per-mote state restarts after a
   loss, hidden by the mode's reveal fade (the log keeps 128 steps and cannot rebuild it).
6. **The OpenGL fallback** does the same on a reset status from the context (`GL_GUILTY_CONTEXT_RESET` and the
   other reset codes, where the context was created with robustness; else Qt's own context-lost handling).

**Test that fails without it.** A harness-only hook (compiled into the harness only) marks the device lost mid-frame,
mid-job, during a display transfer and during warm-up: no crash, the ownership table empty afterwards, validation
clean, a rebuilt frame equals the pre-loss frame, the mode is revealed by fade, and the second loss within the bound
parks the Visualizer. Control: a core that keeps recording after the lost mark.

### What a mode's native renderer may not do (proposed)

A mode renderer is a pure function of its inputs: the decoded frame, the resolved parameters the packet carries, the
targets and extents the frame driver gives it, and the core's matrices. Admission is accounting only (the ownership
table and today's capacity envelope; a per-window GPU-memory budget only if a measurement shows a surface exceeding
what the device can hold). Pipelines are device-scoped and survive a mode release.

| May not | Why | Enforced by |
|---|---|---|
| Read a clock (any `now`) | time is a logical input; the same packet draws the same pixels | the mode API offers no clock; a CI include check fails a mode unit that includes `<chrono>` or the platform timer |
| Compute or own a camera | one camera owner (N0.4); the core receives finished matrices and rays | no projection builder in the mode API |
| Allocate per frame (heap, GPU buffers, pipelines, descriptor sets, textures) | warm-up units create things | debug build: a counting allocator and the ownership table read zero growth over a steady frame; `prepare_step` is the only creating entry |
| Set render state (blend, depth, cull, front face, viewport, scissor, stencil) | state belongs to pipelines; the pass graph declares it | the mode API has no such call: it declares passes and pipelines as data |
| Name Qt Quick (`QQuickWindow`, `QSG*`, Quick's target, the item matrix) | D5.1: only the host adapter touches Qt | a CI include check: no `QtQuick`/`qsg` header in a mode or primitive unit |
| Hold or call Python (a thread state, a callback, an attribute lookup) | D5.4 | the P1 probe: calls with a Python thread state, zero, rerun at every port |
| Call the graphics API directly except through a D5.3 service | the service list is closed | include check on Vulkan and GL headers outside the service sources |
| Read back from the GPU, wait on a fence, or block the render thread | a frame is never held; D9 publishes by latch | the mode API offers no readback or wait |
| Create threads, do file, network or environment access, or read settings | modes are pure; settings arrive resolved in the packet; no environment flags | include check; the mode API takes no path or handle |
| Write outside its own targets | the composite owns the card edge (D5.2) | the mode has no handle to any other target |
| Keep state across activations that the ownership table cannot see | a mode must release to zero | the table baseline test |
| Build or compile a pipeline while a visible frame is recording | no hitch | a trace assertion: no pipeline creation inside a `render` call |

**Test that fails without it.** Per row a compile-or-run check with a negative control: three must-fail snippets
(clock, Quick, graphics API header) fail the include check; a mode that allocates inside `render` trips the counting
allocator; a mode that sets blend state does not compile; a mode with a Python callback reports a Python thread state.

### Questions for the lead (N0.5)

Answered by the lead on 12 Nov (device-loss restart of per-mote state, the 3,600-frame bound, accounting-only
admission, device-scoped pipelines; all folded in above). The questions are in the History file.

### D5.6 The dependency table: what OpenGL gives that QRhi does not, and the route for each (N0.2)

*Decided by the lead, 12 Nov 2026 (accepted as written, every row to its chosen route). It applies D5.2 and D5.3 to
the eighteen dependencies of the research file's table A.2. Each row's today-citation (file:line at `bdf9b246`), QRhi
route, and proof with its negative control are in the History file; the chosen route is here.*

| # | Dependency | Service | Chosen route |
|---|---|---|---|
| 1 | Offscreen passes and compute inside the node's `render()` | none | The frame driver records every offscreen and compute pass in dependency order on `beforeRendering` (D5.2); the composite is one texture node. No `prepare()`/`render()` split |
| 2 | GPU timer queries | GPU timer (per pass) | Whole-frame time from `setTimestamps(true)`, opt-in; per-pass time from the service (Vulkan `vkCmdWriteTimestamp`, OpenGL `GL_TIME_ELAPSED`), built with the substrate (D8 plus 2), off by default with no query objects (settled in N2.6, below); production telemetry stays absent |
| 3 | GL state restoration against Qt's scene graph (the protected clip and fence work) | none | Not written. Nothing reaches the window but a texture node, so Qt's scissor, stencil and clip apply and the clip is the coverage term of the composite material. The fence, the 17-value capture and the DECR redraw go with the Python renderer; the protected commits' behaviour is the oracle, not code carried over |
| 4 | Direct state access and immutable storage | none | QRhi; usage flags are part of each resource's declaration; the `direct_state_access` requirement goes with the OpenGL validator |
| 5 | Program binary cache | none | Quick's pipeline cache for pipelines on Quick's QRhi (the core's are, even on the module's device); shaders baked with `qsb` for every backend at build; pipelines created in warm-up units only; an own `VkPipelineCache` only for the raw pipelines of an admitted service |
| 6 | Per-draw image and sampler bindings, storage-image units | none | One shader-resource-bindings object per (pipeline layout, resource set), built in warm-up and per ring slot, never per frame; per-draw variation by dynamic offsets |
| 7 | Multisample resolve control | per-sample reads, only if resolve-first fails a mode's look or cost | Resolve-first: a QRhi resolve into a single-sample texture, then the composite samples that. Parity is single-sampled (D8.1); multisampled output is judged repeat-relative. The service is built for Extruded Bubble only if the A/B at its port shows a visible or cost loss (N1.8's rule) |
| 8 | Stencil for the card clip | none | As row 3: the coverage term in the composite, the same rounded-rectangle distance as `clip_host.py`; the anti-aliased edge replaces the hard `discard` (see D5.2 and R-191's contract) |
| 9 | Persistent mapped buffers (`StreamRing`) | stream ring | QRhi dynamic buffers, one per frame in flight, dynamic offsets for slices; the service only if the measurement shows 0.05 ms or more (D5.3) |
| 10 | Reading what Quick already drew (the backdrop blit) | none | D7: the pyramid is built from the core's own background layer texture with QRhi fragment passes, in the frame the layer changed and while demand is above zero; nothing reads the window |
| 11 | Point sprites | none | Instanced screen-space quads: per-instance pixel size, corners from the vertex index, the sprite coordinate as a varying; the cull trick becomes a degenerate quad |
| 12 | Compute dispatch, memory barriers, storage images | async jobs (D9) only where admitted | QRhi compute passes in the frame driver; the `barriers` argument is replaced by correct access types in the bindings; formats from row 13 |
| 13 | Texture formats QRhi lacks (`RG16F`, `RG32F`, `R11G11B10F`) | formats, only where widening measurably costs | N1.7 widens first: `RG16F` to `RGBA16F`, `RG32F` to `RGBA32F`, `R11G11B10F` to `RGBA16F` (not `RGB10A2`: unorm, no headroom); the service (raw formats wrapped with `createFrom`) only for a target whose measured memory or time hurts |
| 14 | Indirect draws | none since 6.12 | **Superseded 12 Nov 2026 by the move to Qt 6.12:** the population's `glDrawArraysIndirect` ports 1:1 to `QRhiCommandBuffer::drawIndirect`; the dead-tail cull (draw the maximum, cull in the vertex shader) stays only for a backend without `QRhi::DrawIndirect`. The `glMultiDrawArraysIndirect` start-up requirement is removed (nothing calls it) |
| 15 | Sampled depth textures and depth-dependent reads | per-sample reads (see row 7) | QRhi; `background()` splits the scene pass, the second pass loads the first's colour and depth; the capture is a resolve into plain textures. The product takes the nearest depth over the samples and a depth resolve returns one sample's value (which one depends on the backend, unverified); at single sample there is no difference |
| 16 | Pass structure, no state leakage | none | Passes declared as data (no state setters in a mode); each state combination is a pre-built pipeline created in warm-up; a mid-scope depth clear becomes a new pass with a clear load op or a clear draw; per-attachment write protection becomes a colour write mask in the per-target blend; the front face follows N0.3 |
| 17 | Image and texture upload paths, wrapped Quick textures | async jobs (D9) for upload, mips, derived maps | The native presenter owns its images as QRhi textures, uploaded in the frame driver's batch; D9's job form is the async variant with the in-frame form always present. The wrapped-texture bridge (`native_texture_bridge.py`) is a GL-only seam and is retired with the presenter |
| 18 | Needs no replacement, and the probe's six-face draw | none | Six draws per level, one per face view; `MultiView` only if a measurement asks |

No row needs a service outside D5.3's list. Row 13's missing formats are widened (never a service for parity); rows 7
and 15's nearest-depth rule has no QRhi equivalent, so a multisampled `background()` is a look question decided by
the row 7 A/B, not a blocker.

**Lead's answers (12 Nov, N0.2):** overflow modes keep their painted footprint and the anti-aliased coverage edge
replaces the hard discard (D5.2); a multisampled `background()` stays resolve-first (row 7); the per-pass timer
service's form was provisional until the N0.7 harness showed a timestamp around a whole pass from where the core
records it, settled as below.

*Per-pass timer, settled from where the core records a pass (N2.6, built 13 Nov 2026; proved when `timer_check.py`
passes in its build round):* the core records every pass in one place, the frame driver's `beforeRendering` edge,
before Qt Quick's pass and outside any render pass (D5.2). There the timer brackets each whole pass through
`QRhiCommandBuffer::beginExternal()` on the frame's own command buffer: outside a pass QRhi first records what it
holds into the primary command buffer, so the bracket sits exactly between the passes in submission order and no
secondary command buffer exists. Vulkan: `vkCmdWriteTimestamp` TOP_OF_PIPE before and BOTTOM_OF_PIPE after, in a
query pool of the timer's own, reset in the frame before its first write. OpenGL: `GL_TIME_ELAPSED` begun before and
ended after. D3D11 and D3D12: QRhi offers no per-pass time and D5.3 gives the service no third form, so the whole
frame is used, `QRhiCommandBuffer::lastCompletedGpuTime()` of a QRhi created with `EnableTimestamps`. Results are
latched in a ring of eight frame slots and read only when available (no wait bit); a frame whose slot still holds
unread results goes untimed and is counted, never waits; a switched-off timer's objects go once every result was
read; off, the driver holds no timer and no query object. The figures reach the frame trace as events 77 and 78 (GPU
nanoseconds), read by `tools/frame_trace_report.py`; admitted by `--gpu-pass-timing` with `--frame-trace`.

Questions for the lead (the four of N0.2) and "Where source differed from the research" are in the History file.

## N0.3. Conventions, written once and tested per backend

*Decided by the lead, 12 Nov 2026 (answers in "Lead decisions on the N0 drafts"); the draft, the inventory of what
today assumes OpenGL conventions (at `7ac980d7`) and the questions are in the History file. Metal is listed as QRhi
reports it; this project runs Windows only, so Metal is a Watchlist entry and never a claim.*

### The conventions, per backend

| Convention | OpenGL | Vulkan | D3D11 / D3D12 | Metal |
|---|---|---|---|---|
| Clip-space Y (`isYUpInNDC()`) | up | **down** | up (QRhi's rule: false for Vulkan only) | up |
| Framebuffer / render-target origin (`isYUpInFramebuffer()`) | bottom-left (true) | top-left | top-left | top-left |
| Clip depth range (`isClipDepthZeroToOne()`) | -1..1 | 0..1 | 0..1 | 0..1 |
| `gl_FragCoord` origin in the shader | bottom-left | top-left (SPIR-V `FragCoord`) | top-left | top-left |
| `QRhiCommandBuffer` viewport and scissor origin | bottom-left on every backend (QRhi's rule; research, QRhiCommandBuffer page) | same | same | same |
| Texture row order on upload | first uploaded row is texel row 0; QRhi's GL backend hides the API's own bottom-up order (proved, run 2) | same | same | same |
| Front-face winding | QRhi defines CCW-front on the pre-correction, Y-up output for every backend, and the Vulkan backend compensates for the Y flip (research; proved, run 2) | | | |
| Uniform and storage layout | std140 and std430, identical across backends after SPIRV-Cross; use reflected offsets | | | |
| sRGB | `QRhiTexture::sRGB` flag, not a format; non-sRGB targets in the product | same | same | same |
| HDR intermediates | RGBA16F/RGBA32F/R16F/R32F; `RGB10A2` is unorm; no RG16F, RG32F, R11G11B10F (N0.2 item 13) | same | same | same |

All rows were proved on Vulkan, OpenGL, D3D11 and D3D12 by the scenes below (run 2).

### The rules (proposed)

1. **CPU matrices stay in OpenGL form, from one owner, and are corrected once, at upload.**
   `core/settings/framed_camera.py` (`perspective_matrix`) builds the OpenGL form. For a target the core owns, the
   upload correction is `clipSpaceCorrMatrix()` times a Y flip where `isYUpInFramebuffer()` (F1), multiplied on the
   left exactly once, when the scene's uniform block is written, never in a shader and never twice. Matrices from
   Quick (`QSGRenderNode::projectionMatrix()`) are already corrected by Qt for Quick's own pass and are not corrected
   again; the composite uses Quick's matrices, the scenes the core renders itself use the corrected camera matrix. One
   flag in the matrix object records "corrected", and writing a corrected matrix through the correcting path fails an
   assertion.
2. **Offscreen targets the core owns have one defined origin: texel (0,0) is top-left, window Y points down, on every
   backend** (decided by the lead: Vulkan is the front face, OpenGL is the backend that flips). It holds by rule 1's
   flip, not by the include; the core's readbacks are never flipped (F1).
3. **One include, `srpss_conventions.glsl`, is the only place a shader learns a backend convention.** It provides
   `fragTexel()`, `fragUv(targetSize)`, `ndcToUv`/`uvToNdc`, `viewDepthFromDepthTexture(d)` and (F4) `srgbToLinear`.
   The backend values arrive in a small std140 block at one fixed, reserved binding (index chosen once in N2),
   declared by every stage that includes the conventions. Its values belong to the target and are set by the host
   that owns it: `x` the fragment Y flip (0 for every target the core owns) and `y` the clip-NDC Y flip
   (`isYUpInNDC() && !isYUpInFramebuffer()`: 1 on D3D11, D3D12 and Metal, 0 on Vulkan and OpenGL); the Python OpenGL
   renderer keeps 0 and 0 for every target until it retires. `ndcToUv`/`uvToNdc` take the clip NDC of the pass's own
   (uploaded) matrices and negate Y from `y` under the native core (F2).
4. **Front face is one function of (the item matrix's handedness, `isYUpInNDC()`), evaluated on the matrix after the
   upload correction (F3)** when pipelines are created, giving two pre-built pipeline variants (CW and CCW) for every
   culling pass. For Quick's item matrix the rule gives counter-clockwise on Vulkan, D3D11 and D3D12 and clockwise on
   the core's OpenGL (F1's flip turns the winding).
5. **Uniform blocks are std140, storage blocks std430, and C++ packs from reflected offsets, never hand-computed
   ones.** `vec3` aligns to 16; arrays of scalars, `vec2` or `vec3` in a std140 block have a 16-byte stride; `mat3` is
   three `vec4`; structs round to 16; a following scalar may fill a preceding `vec3`'s padding; storage blocks keep
   natural array strides but `vec3` stays 16-aligned; dynamic uniform offsets are aligned to `QRhi::ubufAlignment()`.
   N1.2 and N1.3 move every program to blocks; the Python packer `Scene3DBlockLayout` is the oracle the C++ packer is
   tested against.
6. **sRGB and HDR: targets are plain unorm or float and shaders do the math**, so a backend change moves no pixel.
   The `sRGB` texture flag is not relied on anywhere (F4): the one sRGB asset, the floor albedo, is plain RGBA8
   decoded in its shader. No `GL_FRAMEBUFFER_SRGB` is enabled anywhere in `rendering/`. An HDR swapchain is not
   admitted (D8 plus 9). Reverse-Z is not adopted; it is decided separately only if the near-plane bead check (plan
   N1) calls for depth precision.

N1.4 applies the include to every existing shader in the OpenGL renderer, each pixel-identical on OpenGL (the
include's OpenGL values make it an identity there), before any C++ exists.

### What today assumes OpenGL conventions (inventory, `rendering/` and `core/settings/`, at `7ac980d7`)

Moved to the History file ("N0.3"): 51 `gl_FragCoord` uses in 14 files, front-face and culling sites, the OpenGL
perspective matrix and depth clears, bottom-up readbacks, and the one sRGB asset.

### The three test scenes (hidden host, run on OpenGL, Vulkan, D3D11 and D3D12 where available; Metal Watchlist)

Each scene renders a fixed, single-sampled frame offscreen, reads it back (flipped by `isYUpInFramebuffer()` only in
the harness's own readback), and is compared with both the analytical image and the OpenGL result; they live in the
P1 harness. (1) A non-square checkerboard with gradients: texel (0,0) top-left, `fragUv`, `fragTexel` and `ndcToUv`
against the writing pass, the upload row order, the sRGB strip, a std140 block with `vec3`, `vec3` array, `mat3` and a
trailing scalar packed from reflected offsets. (2) A known-depth plane (with a nearer one overlapping) through the
project's camera into a `D32F` target, sampled by `viewDepthFromDepthTexture()`: analytical window depth, nearer plane
wins, clear value, near and far clip. (3) Two triangles authored CCW and CW, drawn with back-face culling and rule 4,
once with Quick's Y-down item matrix and once with an up-facing one, and a second pass colouring by `gl_FrontFacing`.
Each has negative controls (include flip inverted, no `clipSpaceCorrMatrix()`, hand-packed offsets, depth part
skipped, uncorrected matrix, front face fixed CCW); the draft's list is in the History file.

**Pass condition per scene:** the harness image equals the analytical image within its stated tolerance on each
available backend and the backends equal each other within the P1 spike's measured difference (0 to 3 of 255 on
trivial content, D8 point 1). A new backend or a Qt upgrade (D11) reruns the three scenes first.

### Questions for the lead (N0.3)

Answered by the lead on 12 Nov (top-left Y-down targets, no reverse-Z now, one fixed reserved binding). The questions
are in the History file.

### As proved (N0.3 harness, `native/spike_p1`, run 1, 12 Nov 2026)

Harness 63f0e75e (`src/n03_scenes.*`, `shaders/n03_*`, `python/run_n03.py`), built on GitHub and run by the lead with
the Khronos layer and `--require-validation` (`.artifacts/evidence/native_core/n0_3/20261112_n03_scenes/`, reanalysed
without a rebuild in `20261112_n03_scenes_reanalysed/`). One process, four backends: Vulkan on our N0.6 device, OpenGL
4.6, D3D11, D3D12 (RTX 4090, NVIDIA 617.42). Validation clean: 10 errors, all Qt defect A by ID, 0 unexplained. Scenes
2 and 3 proved on all four; scene 1 proved except two findings the lead then decided (F2, F4); the findings F1 to F4
below came from this run. The per-check figures are in the History file.

### As proved (run 2, 12 Nov 2026): all three scenes pass on all four backends

Harness 29816002 (the decided include: F1's correction, F2's block `y` in the core's form, F4's `srgbToLinear`),
built on GitHub and run by the lead with the layer and `--require-validation`: `N03 VERDICT PASS`
(`.artifacts/evidence/native_core/n0_3/20261112_n03_scenes_run2/`). Validation clean: 10 errors, all Qt defect A by
ID, 0 unexplained.
- Scene 1: every check on Vulkan (our device), OpenGL, D3D11 and D3D12. `ndcToUv` against the writer's uv within
  1.2e-7 per axis and `uvToNdc` against the clip NDC within 3.0e-7 on all four, D3D included (run 1: 0.982 and 1.964);
  the module wrote the backend's `y` (1 on D3D11 and D3D12, 0 elsewhere). `srgbToLinear` against the exact curve
  within 2.6e-7 on all four, against OpenGL's within 1.8e-7; the sampler's own decode stays a record (OpenGL none,
  defect E; the other three bit-identical). The checker identical to OpenGL's on every backend (max 0).
- Scene 2: window depth within 1.6e-7 of the analytical value, backends within 1.2e-7 of OpenGL.
- Scene 3: the authored-front triangle kept and `gl_FrontFacing` right on all four, with both matrices; images
  identical to OpenGL's (max 0, edge-masked).
- Negative controls fail wherever they change anything: the fragment flip inverted and the clip-NDC flip inverted
  (all four), no correction (Vulkan, OpenGL; changes nothing in 2D on D3D), the hand-packed probe (all four), the
  depth part skipped (Vulkan, D3D11, D3D12), no depth correction (all four), CCW fixed (up-facing on Vulkan and D3D;
  Quick's on OpenGL), rule 4 on the uncorrected matrix (Vulkan, OpenGL). Each control is vacuous only where its
  correction or front face equals the right one.
Left open: the y path through the native core itself, on a real D3D backend, when N2 runs it; Metal (Watchlist).

### Run 1's findings (decided by the lead 12 Nov 2026; drafted as proposals, kept below with their evidence)

All four accepted. The decided rules (the evidence and the drafts' recommended-rule text are in the History file).

**F1. OpenGL keeps texel (0,0) top-left only if the upload correction flips Y for core-owned targets.** Decided: for
the core's offscreen targets the upload correction flips Y on OpenGL; the include's flip is 0 for those targets on
every backend; the core's readbacks are never flipped. The shipping Python OpenGL renderer does not change: its
targets keep their value until it retires, so the block's values belong to the target and are set by its host.
Rejected: `clipSpaceCorrMatrix()` alone with the include's flip at 1 on OpenGL. As built: `conventions.py`'s docstring
says both (3a2e2e51); product pixels did not move (`tools/conventions_identity.py`: every mode and every catalogue
transition case identical frame for frame, 28 of 28 changed fragment sources identical).

**F2. `ndcToUv` and `uvToNdc` of the clip NDC are wrong on D3D11 and D3D12 (predicted, confirmed).** D3D's clip Y
points up while its rows are top-down. Decided: the block carries `ndcYFlip = isYUpInNDC() && !isYUpInFramebuffer()`
in `y`, read by `ndcToUv` and `uvToNdc`; stages that use them declare the block. One departure (3a2e2e51): the Python
renderer's text keeps the authored arithmetic (`ndc * 0.5 + 0.5`, `uv * 2.0 - 1.0`) and only the native core's text
(`#define SRPSS_NATIVE_CORE`, set by the core's bake and the harness) reads `y`, because reading `y` at run time (0
bound) changed the composed result's last bits on NVIDIA 617.42 OpenGL. `tests/test_conventions_include.py` proves the
core's text negates Y when `y` is 1, is the plain arithmetic at 0, and that the renderer's text never reads it.

**F3. Rule 4's input is the uploaded matrix, never the OpenGL-form one.** Decided: the front-face rule is evaluated on
the matrix after the upload correction (also in D6's amendment, `native/spike_p1/src/n03_scenes.cpp`
`frontFaceClockwise` and `front_face_clockwise`'s docstring). Rejected: the OpenGL-form matrix (wrong faces on Vulkan
and on the core's OpenGL).

**F4. Qt 6.12.0's OpenGL backend ignores `QRhiTexture::sRGB` for uncompressed formats** (cause in Qt's
`qrhigles2.cpp`, defect E in `Native_Core_N06_N07_Qt_Facts.md` section I; no rebuild fixes it). The hardware decode
where it exists carries 8 significant bits (worst 0.00375 linear). Decided: the floor albedo is uploaded as plain
RGBA8 and decoded in its shader with the exact IEC 61966-2-1 formula on every backend. Filtering consequence: a
filtered sample is `decode(average(encoded))` instead of the hardware's `average(decode(encoded))`; accepted for this
one asset (a dark, low-contrast concrete) and not a general rule: another sRGB asset gets its own decision. As built
(25688bbf): `srgbToLinear` in the include; `load_floor_textures` stores plain `GL_RGBA8`; the floor fragment decodes
its three albedo reads. On Waveform Ribbon pixels move by at most one 8-bit step on 0.513 % of pixels in 296 of 549
frames; every other mode identical (`n0_3/20261112_f4_floor/`, `20261112_identity_after_f4/`).

## N0.4. The camera (proposed D5.5; decided by the lead 12 Nov)

*Decided by the lead, 12 Nov 2026 (answers in "Lead decisions on the N0 drafts"). Today no finished matrix travels from
the worker to the renderer at all, so the contract says what has to be added. The source inventory (three consumers
building matrices from `framed_camera` in three places, rays rebuilt in shaders from the tangent pair) and the timing
(6.6 us median per frame for Extruded Bubble's whole build: cost argues against nothing) are in the History file.*

### What is true in source

Moved to the History file ("N0.4").

### Per-frame cost today (evidence)

Moved to the History file ("N0.4"). No per-frame cost justifies a second camera; the build leaves the render thread
because a Python call there puts the GIL back on it (D5.4).

### Proposed D5.5

1. `core/settings/framed_camera.py` stays the **only** implementation of camera math. The core contains no
   `perspective_matrix`, no `viewport_tangents`, no axes and no eye resolution.
2. **Finished camera data is built on the Python side by that module and published per frame in the packet**, in the
   fixed per-mode native schema: the view (`view_to_world` and `world_to_view` as float32, the eye as float32), the
   projection (a 4 by 4, OpenGL form, corrected once at upload, N0.3 rule 1) and the tangent pair `tan`: about 40
   floats, 160 bytes a frame. The core derives none of it.
3. **The builder runs where the inputs are exact: the worker's tick** (the GUI-thread build is rejected). It needs the
   card's exact pixel aspect and the exact aperture scale; three numbers as built (12 Nov): Extruded Bubble draws
   with the aperture scale of the whole extent (`framed_aperture_scale(presentation)`, content=False) and Waveform
   Ribbon with the content's, so `FramedView(pixel_aspect, aperture_scale, extent_aperture_scale)`
   (`core/framed_view.py`, `VIS_SET_VIEW` version 2), resolved by the GUI-side functions the renderer calls now and
   sent at the edges where they change (resize, CUSTOM edge resize, DPI), never per frame. It is an internal
   message, not a persisted shape: no bridge; the message's version is raised.
4. Per-frame inputs that change with the music (Waveform's `state.zoom`, Dynamic Zoom) are inputs to the worker's
   build, not to the core.
5. **A framed mode's pixels are a function of the packet alone:** same packet, same camera. Neon Lake's camera axes
   (built inside program builders today) move into the packet at its port (N5.5), not in N0.

### Tests that fail without it

(1) Equality to today's renderer: for a recorded parameter set and a range of card sizes and apertures, the packet's
matrices, eye and `tan` equal bit for bit (after the float32 narrowing) what `physical_camera` and `physical_view`
return; control: build with the approximate extent (`card_span`'s extent without the shell inset). (2) One owner: a
grep of the native sources and schemas for a perspective or tangent construction fails if one exists. (3) Resize edge:
an edge resize reaches the packet within the next worker tick, and a frame between the resize and the tick is drawn
with the old camera and the old target size together, never a mixed pair (the packet carries the extent it was built
for; on a mismatch the core holds the previous frame); control: ignore the stamp.

### Questions for the lead (N0.4)

Answered by the lead on 12 Nov (camera in the worker's tick; three view floats, no bridge; Neon Lake at N5.5). The
questions are in the History file.

## Lead decisions on the N0 drafts (12 Nov 2026)

The four drafted sections (D1 to D3 and the transport rule; the rest of D5; N0.3; N0.4) and the D5.6 dependency table
were accepted as written. The lead's answers are folded into those sections, so this section holds only the pointer;
the answers as the lead gave them (including "Nothing here is decided", which is history) are in the History file.

## Long-term risks of this direction, and what holds each (audit, 12 Nov 2026)

| Risk | Why it could make the direction fail | What holds it |
|---|---|---|
| The flip is a big bang | Vulkan gets no real-window hours until every Python renderer is gone | D10: the rehearsal path from the first port, both backends at every port, an explicit flip gate |
| The size of the port | About 31,000 lines of Python GL, 63 programs, 838 loose-uniform call sites, 9 modes, 28 transitions; agents stop at usage limits | The ladder is cut into ports that each finish inside one window (plan 8b); N1 makes shaders portable in the OpenGL renderer first, so a port is a translation; two ordered tracks instead of one queue; the parity gate, not review, says "done" |
| Qt and PySide6 churn | QRhi has limited compatibility guarantees; PySide6 exposes none of the Vulkan set-up; a Qt upgrade can change behaviour under us | D5.1: Qt is touched at one adapter; D6: the device is ours and does not change with Qt; D11: the version is chosen once and upgraded only between stages through a scripted step; the module refuses to load under another Qt (P1) |
| The native module's build and distribution | A compiled extension in a Nuitka build, an MSVC runtime that must match what shiboken loads, an SDK that must be fetched per Qt version, builds that run only on GitHub | P1 proved the frozen probe; the first box of the substrate (N2.1) is the build itself: the exact-Qt guard, the `msvcp140` import guard, a scripted SDK fetch, the GitHub workflow building the module, and a check that fails the build when the module is missing from the artifact |
| Driver variance on `precise` and `fma` (D4) | A compiler that contracts or reorders the two-product silently reintroduces drift on one vendor | D4.7's warm-up self-check on a known pair, logged and reported; the long-horizon test stays in the suite; the cross-backend parity record of the Extruded Bubble port includes the drift outputs |
| Driver variance in general on Vulkan | Start-up crashes, swapchain behaviour on sleep and wake, device loss, differences between vendors; the project has one development GPU | D6 point 5: automatic start on OpenGL with the reason shown, and the remembered failed start; device loss rebuilt from the last packet; OpenGL kept selectable for good; GitHub's frozen build as the second environment; what cannot be run here is a Watchlist entry, never a claim |
| Translucent windows on Vulkan | The Studio's window is translucent today and SMP's desktop window is planned; a Vulkan swapchain window may not be see-through on Windows | Proved in N0.6 before anything depends on it; since the operator's 12 Nov answer (D7 point 8) the SMP build's look depends on it, with the artwork backdrop as the fallback only; for the Studio the fallback is an opaque window with the system's own rounded corners, decided at the flip gate |
| Two forms of every service | Each native route doubles a test surface, and the less-used form rots | D5.3: the list is closed, each service must win a measurement to exist, the two forms are tested against each other, and QRhi stays the default |
| Async work | Cross-queue synchronisation bugs are rare, late and hard to reproduce | D9: self-contained jobs, latched publication with no GPU-side wait, an in-frame form that always exists, validation layers as a gate, adversarial teardown in the proof |
| Linux | Never run; best effort by the operator's decision | The core is one code path through QRhi with OpenGL as the selectable backend there; the conventions (N0.3) are tested per backend on Windows; what a first Linux run would show stays a Watchlist entry |
| Building primitives nobody uses | High-potential work with no consumer can drift from what modes need | Each has a harness scene, a measured cost and a showcase before it counts as built, and none blocks the flip (D8 plus 6) |
| The Python path during the migration | Two renderers exist for a ported transition until the family switches; the protected clip and background optimisations must not be retuned meanwhile | D10 point 4 bounds it to the background family and deletes at the switch; the protected commits stay untouched; the native background must measure no worse than them before it replaces them |

## Where the audit of 12 Nov disagreed, in one place

The audit's list of where it differed from the lead's position of 12 Nov and the decision of 8 Nov is in the History
file ("Where the audit of 12 Nov disagreed"). The current rules it produced are D5.2, D5.3, D6, D7, D9, D10 and D8
as written above. Three sentences of the 8 Nov decision are superseded and recorded as such in the addendum of 12 Nov
in `Graphics_Backend_Decision_2026-11-05.md` (a raw pass being Vulkan-only; Qt Quick owning the device; async compute
as "not our bottleneck" and only a trigger). Everything else in it stands.
