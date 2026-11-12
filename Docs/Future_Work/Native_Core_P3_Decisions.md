# Native core P3: decisions before any C++ (P3.0)

**Status (12 Nov 2026, after the milestone audit).** D4 is decided and partly built (D4.1 to D4.3 merged 12 Nov;
D4.4 to D4.8 in flight). D5 (the core's shape), D6 (device ownership), D7 (the card-material backdrop), D8 (what
Parity+ means, with the ranked plus items), D9 (async GPU jobs), D10 (the Vulkan rehearsal path and the flip gate)
and D11 (the Qt version) were decided by the one-off architectural audit of 12 Nov 2026 (Fable 5.2, at the lead's
request, answering the operator's direction of 11 and 12 Nov). They bind until the lead or the operator supersedes
one in writing here; a superseded decision is kept with its date, never overwritten. D1 to D3 and the transport
rule are still to be written. Apart from D4.1 to D4.3 nothing in this file is built. The ordered work that carries
these decisions out is `Current_Plan.md`, item 8b.

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

The drift solver (`rendering/quick/visualizer/implementations/extruded_bubble_drift_solver.py`) is two compute
programs that use `double`. On OpenGL 4.6 Core that is guaranteed. On Vulkan it is the optional device feature
`shaderFloat64` (absent on Intel Arc, most mobile GPUs and Apple's), and QRhi cannot even ask. A second, lesser
path for devices without it would make Vulkan the weaker face on exactly those devices.

### What the doubles are actually for

From the inventory of 11 Nov (`D:\Temp\Scratch\SRPSS\research\20261111\eb_fp64_drift_inventory.md`; the facts are
repeated in the plan). Everything the draws read is already 32-bit: displacement, shift, phase offset and progress
leave the solver as `vec4` of floats, and displacement is 32-bit state between steps. The doubles serve three
things only, with add, multiply, divide, `floor` and `mod` and no double transcendental:

1. **A discrete decision per chain per step:** how many knots the chain's history moves,
   `floor(shifted / stepSize + 1e-10)`, with the remainder `shift` carried to the next step. A float32 span or
   carry once moved this one tick early against the CPU reference. At most 240 chains.
2. **Three growing phase arguments,** `sin(wrapped(t * k + c * p))` for k = 0.37, 0.83, 0.29: the music phase `t`
   grows without limit and must be reduced mod 2 pi before `sin`. These are per step, not per point.
3. **One growing quotient per mote,** `progress = mod(seed + travel * carry / span + phaseOffset, 1)`: `travel`
   grows without limit (about 5,000 after an hour at the default, 32,000 at the fastest), and there are up to
   218,500 motes, so this one must stay on the GPU.

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
- **(2) Phase reduction moves to the step record.** The worker reduces `t * k` mod 2 pi in float64 for the three
  constants and publishes three float32 angles per step. The shader computes `sin(angle + c * p)` in 32-bit, both
  terms bounded. The rule "reduce mod 2 pi in 64-bit before `sin`" is kept; it simply runs where 64-bit is free.
- **(3) The per-mote quotient is rebuilt exactly from pairs of floats (double-single arithmetic).** The division
  leaves the GPU: at geometry build the worker computes `r = carry / span` per mote in float64 and stores it as a
  high and a low float32 in the two unused floats of the mote's second `vec4` (the geometry record does not grow).
  Each step carries `travel` as a high and a low float32, split by the worker in float64. The shader forms
  `travel * r` as an error-free product of pairs (`fma`-based two-product, results marked `precise` so the
  compiler may not contract or reorder them) and takes its fractional part. That gives about 48 significant bits
  for the quotient; the output is a float32 with 24. At an hour's quotient of 800 the pair arithmetic is exact to
  about 3e-12 of a span, against 1e-13 for a double, and both are four or more orders of magnitude below the
  6e-8 of a span the float32 result can resolve. The geometry-edit rebase (`oldTravel / oldSpan`) uses the same
  pairs.

**Why not the alternatives.** Keeping `double` where `shaderFloat64` exists and a second path elsewhere gives two
solvers to test and makes the feature-less Vulkan devices the lesser face. Integrating all drift in the worker
would ship about 4 MB a revision at full population and brings back the cost the GPU solver was built to remove
(152 ms a tick at 216,000 specks in the old CPU path). A camera-relative or periodically rebased quotient in plain
float32 accumulates rounding at every rebase and loses the closed form the reference is compared against.

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

A NumPy model of the pair arithmetic for 218,500 motes (float32 span 2 to 54, the two carries, random seed and
phase offset), against the float64 value, beside a shader that would simply use float32. Error in fractions of a
span, largest over all motes:

| Horizon | Largest quotient | Plain float32 | Float pairs |
|---|---|---|---|
| 1 hour at the default speed (travel 5,200) | 2,305 | 2.2e-4 | 2.4e-7 |
| 1 hour at the fastest speed (32,400) | 14,364 | 1.3e-3 | 2.4e-7 |
| 8 hours at the fastest speed (259,200) | 114,909 | 8.6e-3 | 2.1e-7 |
| 24 hours at the fastest speed (777,600) | 344,728 | 3.2e-2 | 2.1e-7 |

The pairs hold a constant error of a few float32 steps (the result itself resolves 6e-8) however long the saver
runs, where plain float32 degrades with time to a visible 3 % of a span after a day. 2.4e-7 of the longest span
is about 1.3e-5 world units, far inside the 1e-4 the solver's tests allow, and it comes from the last three
float32 additions, not from the product; D4.1 models the whole solver and may tighten the final sum. The check
used an exact two-product (what `fma` returns); it says nothing yet about real shader compilers, which is what
D4.7's self-check is for.

### Consequences

- The solver stops being a Vulkan blocker and can be ported by the native core like any other compute pass.
- This can be built **now, in the existing OpenGL renderer**, before any C++ exists: it is a change to two shader
  programs, the step record, the mote geometry record and the worker's drift log, all behind the existing
  reference tests.
- The step record grows by three floats and the travel pair; chains gain their per-step decision stream; mote
  geometry does not grow. D3 (geometry once per revision) is unaffected and still owed.
- A device or driver whose compiler ignores `precise` would break (3). The readiness test therefore includes a
  runtime self-check of the two-product on a known pair at warm-up, on the edge, never per frame; a failure is
  logged and reported rather than silently producing drift.

## D5. The core's shape (decided 12 Nov 2026; the full resource and lifetime contract is still owed, N0.5)

Four rules. They are what keeps the ceiling high: none of them is needed for Spectrum, all of them are expensive
to retrofit once nine modes and twenty-eight transitions sit on the core.

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
  alpha, the rounded-rectangle coverage, the quarter turn), not as a `QSGRenderNode` that draws inside Qt's pass.
  Qt's renderer then applies clip, opacity, order and batching itself. This is Qt's own pattern: *header*,
  `QQuickRhiItemNode` is a `QSGSimpleTextureNode` and a texture provider driven from `beforeRendering`
  (`private/qquickrhiitem_p.h:27,49`), and `QQuickWindow::createTextureFromRhiTexture` wraps the core's texture
  (`qquickwindow.h:125`).
- The card clip (plan 1C.4: nothing outside the card, nothing under the border's anti-aliased edge) becomes the
  coverage term of that composite material plus Qt's own scissor and stencil. No inherited state is read or
  restored, and the hand-built stencil pipelines the P1 spike's risk 5 feared are not written.
- Because each layer is a texture provider, a QML `ShaderEffect` can sample it. That is what D7's backdrop and
  SMP's sections need, and it costs nothing when nobody samples.
- Exactness: the core renders at the item's device-pixel rectangle and the composite maps texels one to one.
  The first port proves this (Spectrum through the texture node equals the Python renderer's direct draw, also
  under pixel shift and a uniform CUSTOM scale). If it cannot be made exact, that surface falls back to a render
  node with one composite draw (the lead's N3.0 form); the rest of this decision stands either way.

*Where this differs from the lead's position:* the lead's N3.0 had the composite as one draw in a render node
with stencil reference, scissor and coverage built by us. The texture node removes that code and that risk, and
gives texture providers for free. The cost is one extra card-sized target for the three modes that draw straight
into the window today (Spectrum, Spline Curve, Bubble); the six scene modes already composite.

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
| Indirect and count draws | no indirect draw in 6.11 (*header*) | measured against "draw the maximum, cull in the vertex shader" on the population harness; gone if D11 moves to a Qt that has it |
| Per-sample multisample reads | QRhi forbids sampling a resolved multisample texture | only if resolve-first fails a mode's look or cost; parity is single-sampled |
| Formats (RG16F, RG32F, R11G11B10F) | not in QRhi's format list | only where widening to RGBA16F or RGBA32F measurably costs memory or time (N1.7 widens first) |
| Async GPU jobs | QRhi records on one queue | D9 |

A feature with no OpenGL form is allowed only as an opt-in extra that changes nothing by default (temporal
upscaling is the known example). This supersedes the 8 Nov sentence "Such a pass is Vulkan-only: on OpenGL it is
unavailable or takes its QRhi form" (see the addendum in `Graphics_Backend_Decision_2026-11-05.md`).

*Where this differs from the lead's position:* the lead listed five raw-Vulkan routes as decided. Here each is a
service that must earn its place by a measurement and must ship its OpenGL twin; two of them (formats, per-sample
reads) are expected not to be needed for parity at all.

**D5.4 No Python on any thread the core runs on.** The render thread and the job thread (D9) never hold a Python
thread state for a native surface: connections are made in C++, introspection lives in C++, and every port reruns
the P1 probe (calls made with a Python thread state: zero).

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
   device. *Not* a reason: feature bits. *Unverified*: Qt's own device creation appears to enable every feature
   the device supports (its private header keeps the 1.0 to 1.3 feature structs, `private/qrhivulkan_p.h:915-924`),
   so the lead's "feature bits Qt would not enable" is probably not the gap; the proof step records what is true.
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
   the semaphores are binary. Owning the frame submit is therefore not needed for async work and does not move
   earlier. D9's default route needs no GPU-side wait at all.

**Proof before anything is built on it (plan item 8b, N0.6):** in the P1 harness, a hidden Qt Quick host on the
module's device renders the spike scene pixel-identical to the same host on Qt's own device; validation layers
are clean through create, render, resize and teardown (windows first, then devices, then the instance); the
second queue is found on the development GPU and its absence is forced as a negative control; then one bounded
run of a real window on Display 1 by the lead (swapchain, resize, DPI change, sleep and wake).

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
8. **SMP.** In the compositor host (saver and MC builds) the backdrop is this one. In the desktop-window host
   (the SMP build has no compositor) the window's backdrop is also the core's own: a background layer made from
   the current artwork, with the Visualizer layer where a section overlaps it, through the same pyramid and the
   same card shader. That is document 04 section 5's "one backdrop capture shared by all panes" with no
   dependency on the desktop.

**During the migration.** The product's OpenGL window keeps today's blit until the whole background family is
native in that window (D10); the native backdrop is built with the native presenter and runs from the start on
the Vulkan rehearsal path, so the blit is never needed on Vulkan. At the switch on OpenGL the native backdrop is
compared with the blit on the same frames.

*Where this differs from the lead's position:* (a) no saturation or luminosity in the build pass (rule 5);
(b) fragment passes, not a compute pass, by default (rule 4); (c) dimming at sample time; (d) the SMP desktop
window does not use the system backdrop: a Vulkan swapchain window on Windows cannot be relied on to be
per-pixel translucent over the desktop (*unverified*; composite alpha is commonly opaque only), so the look must
not depend on it. Whether such a window can be see-through at all is a proof step (N0.6), and it matters before
SMP: the Studio's window is translucent today (`ui/studio/surface.py:181,242`) and changes backend with
everything else at the flip.

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
| 6 | High-potential 3D primitives without a consumer (N4.c, N4.h, N4.k, N4.m, N6.1 to N6.3) | What scenes can look like: populations, shadows, many lights, merged shafts, a reactive surface, places, smoke | Moderate each | Building what nobody uses well | Each on its harness with measured cost, lazy creation and a showcase; none blocks the flip |
| 7 | GPU-driven populations with count draws | Populations of 10^5 to 10^6 with GPU culling and no readback, for droplets, debris, sprites | Moderate | No indirect draw in QRhi 6.11 | The population harness at one million sprites against "draw the maximum, cull in the vertex shader"; the two existing transitions port on the simple route |
| 8 | Persistent high-rate rings | Larger histories and denser strands and particles at one copy per frame | Small | Low | D5.3's measurement; not built if QRhi's dynamic buffers are within 0.05 ms |
| 9 | HDR output | Emissive scenes on an HDR display | Moderate | Window format and tone mapping per backend | Not admitted; reconsider after the flip |
| 10 | Per-pass temporal upscaling, descriptor indexing, mesh shaders, ray tracing | None today | High | High | Not admitted: low potential until a consumer exists (the operator's rule); D6 keeps the door open |

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
   outputs. At rest the thread is parked on a condition variable and wakes only for a job (no polling, no timer).
2. **First consumers, in order of reward.** (a) An incoming photo: the texture upload, its mips, the reflection
   copy, the backdrop seed, and what the next transition needs prepared (edge field, propagation field,
   population scan). The transition starts on the job's completion edge, with a deadline after which the in-frame
   form runs. (b) Warm-up: static meshes, heightfield builds, probe filtering, raw pipelines. (c) Simulation
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

**How it is proved (plan item 8b, N0.7), before the substrate depends on it:** on the P1 harness with a fixed
scene rendering at the display's rate in a hidden host: (i) a heavy job (the edge field at 4K, repeated) run
in-frame and as a job, with frame GPU time median, p90 and p99 and late frames for both, system conditions
recorded; (ii) the job's outputs hashed, identical between the two forms; (iii) no Python thread state on the job
thread; (iv) validation layers with synchronisation validation clean; (v) retirement and device destruction in
the middle of a job, without a crash or a leak; (vi) at rest, zero wake-ups of the job thread over a minute.
If (i) shows no gain on the development GPU, compute jobs stay in-frame on that vendor and the job thread is kept
for uploads, whose CPU half (the staging copy) leaves the render thread whatever the GPU does.

*Where this differs from the lead's position:* the lead framed async compute as simulation on a second queue,
synchronised through Qt's frame submit, with ownership of the submit as the open risk. Here the first consumers
are uploads and transition preparation, the default route needs no GPU-side wait, and the open risk is closed by
the header (D6 point 6).

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
by a forced device failure; translucent windows are settled (D7's last paragraph); a frozen GitHub build runs on
Vulkan on Display 1; and one load session after the operator's yes shows Vulkan no worse than OpenGL. OpenGL then
stays selectable in Settings as the fallback.

## D11. The Qt version the core is built against (decided 12 Nov 2026)

The core is compiled against the exact Qt of the shipped PySide6 (P1), and every upgrade reruns every parity gate
on both backends. So the version is chosen once, at the entry to the first C++ slice (plan N0.8), not drifted
into: if a PySide6 release newer than 6.11.2 is available whose QRhi has indirect draws (Qt's documentation lists
`DrawIndirect`, `DrawIndirectMulti` and `ShaderDrawParameters` for 6.12; they are absent from the 6.11.2 header),
the lead takes the upgrade first, through the whole suite and a GitHub frozen build, and one service of D5.3
disappears. Otherwise the core starts on 6.11.2. After that, Qt is upgraded only between stages of the ladder,
through a scripted step: fetch the matching SDK, rebuild, both backends' parity gates, a frozen build.

## D1, D2, D3 and the transport rule

Not yet written. Their one-line statements are in `Current_Plan.md` (item 8b, stage N0) and their inputs in the
closeout document's section 3. Order: D1 and D2 with the drop edge, then D3. D9's job thread uses D1's quiescence
barrier, so D1 is written with both readers in mind.

## Long-term risks of this direction, and what holds each (audit, 12 Nov 2026)

| Risk | Why it could make the direction fail | What holds it |
|---|---|---|
| The flip is a big bang | Vulkan gets no real-window hours until every Python renderer is gone | D10: the rehearsal path from the first port, both backends at every port, an explicit flip gate |
| The size of the port | About 31,000 lines of Python GL, 63 programs, 838 loose-uniform call sites, 9 modes, 28 transitions; agents stop at usage limits | The ladder is cut into ports that each finish inside one window (plan 8b); N1 makes shaders portable in the OpenGL renderer first, so a port is a translation; two ordered tracks instead of one queue; the parity gate, not review, says "done" |
| Qt and PySide6 churn | QRhi has limited compatibility guarantees; PySide6 exposes none of the Vulkan set-up; a Qt upgrade can change behaviour under us | D5.1: Qt is touched at one adapter; D6: the device is ours and does not change with Qt; D11: the version is chosen once and upgraded only between stages through a scripted step; the module refuses to load under another Qt (P1) |
| The native module's build and distribution | A compiled extension in a Nuitka build, an MSVC runtime that must match what shiboken loads, an SDK that must be fetched per Qt version, builds that run only on GitHub | P1 proved the frozen probe; the first box of the substrate (N2.1) is the build itself: the exact-Qt guard, the `msvcp140` import guard, a scripted SDK fetch, the GitHub workflow building the module, and a check that fails the build when the module is missing from the artifact |
| Driver variance on `precise` and `fma` (D4) | A compiler that contracts or reorders the two-product silently reintroduces drift on one vendor | D4.7's warm-up self-check on a known pair, logged and reported; the long-horizon test stays in the suite; the cross-backend parity record of the Extruded Bubble port includes the drift outputs |
| Driver variance in general on Vulkan | Start-up crashes, swapchain behaviour on sleep and wake, device loss, differences between vendors; the project has one development GPU | D6 point 5: automatic start on OpenGL with the reason shown, and the remembered failed start; device loss rebuilt from the last packet; OpenGL kept selectable for good; GitHub's frozen build as the second environment; what cannot be run here is a Watchlist entry, never a claim |
| Translucent windows on Vulkan | The Studio's window is translucent today and SMP's desktop window is planned; a Vulkan swapchain window may not be see-through on Windows | Proved in N0.6 before anything depends on it; D7 point 8 makes SMP's look independent of it; for the Studio the fallback is an opaque window with the system's own rounded corners, decided at the flip gate |
| Two forms of every service | Each native route doubles a test surface, and the less-used form rots | D5.3: the list is closed, each service must win a measurement to exist, the two forms are tested against each other, and QRhi stays the default |
| Async work | Cross-queue synchronisation bugs are rare, late and hard to reproduce | D9: self-contained jobs, latched publication with no GPU-side wait, an in-frame form that always exists, validation layers as a gate, adversarial teardown in the proof |
| Linux | Never run; best effort by the operator's decision | The core is one code path through QRhi with OpenGL as the selectable backend there; the conventions (N0.3) are tested per backend on Windows; what a first Linux run would show stays a Watchlist entry |
| Building primitives nobody uses | High-potential work with no consumer can drift from what modes need | Each has a harness scene, a measured cost and a showcase before it counts as built, and none blocks the flip (D8 plus 6) |
| The Python path during the migration | Two renderers exist for a ported transition until the family switches; the protected clip and background optimisations must not be retuned meanwhile | D10 point 4 bounds it to the background family and deletes at the switch; the protected commits stay untouched; the native background must measure no worse than them before it replaces them |

## Where the audit of 12 Nov disagreed, in one place

With the lead's position of 12 Nov: the composite is a scene-graph texture node, not a render node with our own
stencil (D5.2); native routes are measured services with an OpenGL twin, not five decided raw-Vulkan routes
(D5.3); the device is owned for its second queue and for determinism, not for feature bits, and there is one per
window (D6); Qt's frame submit can wait on our semaphore, so the frame submit does not need to move (D6 point 6);
async work starts with uploads and transition preparation and publishes by latch (D9); the backdrop keeps
saturation, luminosity and dimming at sample time, is built by fragment passes, and SMP's desktop window does not
rely on the system backdrop (D7); the presenter is built early so that Vulkan is rehearsed from the first port,
and Waveform Ribbon and Extruded Bubble are ported before Neon Lake, Extruded Spectrum and Sphere because they
are the measured need and Expanded Visualizer M6 waits on Extruded Bubble (D10 and the plan); multi-threaded
recording is not a plus (D8).

With the decision of 8 Nov: three sentences are superseded and recorded as such in the addendum of 12 Nov in
`Graphics_Backend_Decision_2026-11-05.md` (a raw pass being Vulkan-only; Qt Quick owning the device; async compute
as "not our bottleneck" and only a trigger). Everything else in it stands.
