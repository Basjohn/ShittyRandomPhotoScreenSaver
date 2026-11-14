# Native core P3 decisions: history

**This file is history, not instructions.** It holds the drafts, superseded text, round-by-round evidence and the
questions the lead answered, moved verbatim out of `Native_Core_P3_Decisions.md` on 14 Nov 2026 when that file was
consolidated to the current decisions. Nothing here binds: where it disagrees with the main file, the main file wins.
Each block names the section it came from. Headings inside a block are demoted two levels so this file's own
structure stays readable; the text is otherwise unchanged, including words such as "proposed" and "nothing here is
decided", which describe the draft's state when it was written. The whole pre-consolidation file is also in git at
`05d3d079e`.

## Original status paragraph (12 Nov 2026)

**Status (12 Nov 2026, after the milestone audit; refreshed by the doc sweep of 12 Nov evening).** D4 is decided and
built (D4.1 to D4.8 merged 12 Nov). D5 (the core's shape), D6 (device ownership), D7 (the card-material backdrop), D8 (what
Parity+ means, with the ranked plus items), D9 (async GPU jobs), D10 (the Vulkan rehearsal path and the flip gate)
and D11 (the Qt version) were decided by the one-off architectural audit of 12 Nov 2026 (Fable 5.2, at the lead's
request, answering the operator's direction of 11 and 12 Nov). They bind until the lead or the operator supersedes
one in writing here; a superseded decision is kept with its date, never overwritten. D1 to D3 and the transport
rule, the rest of D5 (N0.5), N0.3 and N0.4 (D5.5) were drafted as "proposed" and accepted by the lead on 12 Nov
(section "Lead decisions on the N0 drafts"); their "proposed" headings are history, the decision is the lead's
answers. Built so far: D4 and the two harness proofs N0.6 and N0.7 (in `native/spike_p1`, never shipped); the
product module `native/core/` (D5.7) and its one importer `rendering/native/` were merged on 12 Nov (N2.1: a
version, Qt and ABI report and a no-op host adapter entry, nothing rendered and nothing in the product loading it).
The ordered work that carries these decisions out is `Current_Plan.md`, item 8b.

## From D4: the problem, what the doubles were for, the alternatives, the first numeric check, the consequences

##### The problem

The drift solver (`rendering/quick/visualizer/implementations/extruded_bubble_drift_solver.py`) is two compute
programs that use `double`. On OpenGL 4.6 Core that is guaranteed. On Vulkan it is the optional device feature
`shaderFloat64` (absent on Intel Arc, most mobile GPUs and Apple's), and QRhi cannot even ask. A second, lesser
path for devices without it would make Vulkan the weaker face on exactly those devices.

##### What the doubles are actually for

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
**Why not the alternatives.** Keeping `double` where `shaderFloat64` exists and a second path elsewhere gives two
solvers to test and makes the feature-less Vulkan devices the lesser face. Integrating all drift in the worker
would ship about 4 MB a revision at full population and brings back the cost the GPU solver was built to remove
(152 ms a tick at 216,000 specks in the old CPU path). A camera-relative or periodically rebased quotient in plain
float32 accumulates rounding at every rebase and loses the closed form the reference is compared against.

##### First numeric check of (3) (lead, 12 Nov 2026; not yet the D4.1 test)

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

##### Consequences

- The solver stops being a Vulkan blocker and can be ported by the native core like any other compute pass.
- This can be built **now, in the existing OpenGL renderer**, before any C++ exists: it is a change to two shader
  programs, the step record, the mote geometry record and the worker's drift log, all behind the existing
  reference tests.
- The step record grows by three floats and the travel pair; chains gain their per-step decision stream; mote
  geometry does not grow. D3 (geometry once per revision) is unaffected (written and accepted on 12 Nov, section "D1, D2, D3" below).

## From D5: where the drafts differed from the lead's position

*Where this differs from the lead's position:* the lead's N3.0 had the composite as one draw in a render node
with stencil reference, scissor and coverage built by us. The texture node removes that code and that risk, and
gives texture providers for free. The cost is one extra card-sized target for the three modes that draw straight
into the window today (Spectrum, Spline Curve, Bubble); the six scene modes already composite.
*Where this differs from the lead's position:* the lead listed five raw-Vulkan routes as decided. Here each is a
service that must earn its place by a measurement and must ship its OpenGL twin; two of them (formats, per-sample
reads) are expected not to be needed for parity at all.


## From D6: the N0.6 rounds, as recorded

**As proved (N0.6 harness, `native/spike_p1`, 12 Nov 2026; each round built on GitHub and run by the lead; evidence
`.artifacts/evidence/native_core/n06/`).** The rounds' record, moved from the plan:

- Round 1, facts (29bdd8f1, built on GitHub first time; `run_n06.py --round facts`, PASS, evidence
  `.artifacts/evidence/native_core/n06/20261112_n06_facts/summary.json`): loader 1.4.341
  (`C:\WINDOWS\SYSTEM32\vulkan-1.dll`); RTX 4090, API 1.4.351, NVIDIA 617.42; queue families 0 graphics+compute+
  transfer x16 (presents), 1 transfer x2, 2 compute+transfer x8 (presents), 3 video decode x1, 4 video encode x2, 5
  optical flow x1: a second queue in the graphics family exists (15 spare) and a compute-only family too. Qt's own
  device (API 1.2) takes family 0 queue 0; all five `preferredExtensionsForImportedDevice()` names are available;
  by Qt's rule it enables 109 features (1.0, 1.1, 1.2 structures; only `robustBufferAccess` of the supported ones is
  left out; unsupported: ETC2, ASTC LDR/HDR, protectedMemory, storageInputOutput16); its QRhi reports every feature
  flag except RenderBufferImport. Qt's route-(i) instance also enables `VK_KHR_portability_enumeration`,
  `VK_EXT_debug_utils` and the two surface extensions beside the preferred two. No validation layer installed
  (implicit layers present: NV optimus, NV present, WEOBS hook, Steam overlay and fossilize); no Qt or loader
  environment variable set.
- Round 2, our instance and device (731faf28, built first time; `run_n06.py --round device`, PASS, 16 of 16
  checks, evidence `.artifacts/evidence/native_core/n06/20261112_n06_device/`): our VkInstance at API 1.2 (surface,
  win32 surface, the two preferred instance extensions, debug utils) adopted by a QVulkanInstance with the same
  lists; our VkDevice on family 0, one queue, the five imported-device extensions plus `VK_EXT_device_fault`, the
  1.0/1.1/1.2 features equal to Qt's rule name for name (plus the shading-rate, divisor and fault structures);
  the hidden Qt Quick host (the spike's QuadField, 120 frames) ran on our device (QRhi's native handle = ours,
  family 0 queue 0) and is pixel-identical to the same host on Qt's own device (max difference 0; negative control,
  the next frame: max 186, 108,748 pixels); QRhi feature flags equal. Teardown (device idle, destroy,
  `resetDeviceFunctions`, both QVulkanInstances, messenger, instance) clean. Messenger: 0 errors and 0 warnings in
  render and teardown; one loader warning at create ("Registry lookup failed to get layer manifest files", no
  layers installed). Validation still owed.
- Rounds 3 and 4, lifecycle and the second queue (347e7d62, built first time; `run_n06.py --round lifecycle`,
  FAIL on two of 18 checks, evidence `.artifacts/evidence/native_core/n06/20261112_n06_lifecycle/`): 10 cycles of
  create, render, resize (960x540 to 1280x720), render, teardown on our device all clean, teardown order exact,
  pixel-identical to Qt's own device before and after the resize; the second queue is found every cycle in family
  0 at index 1 (D9's same-family rule) and executes (distinct handle, empty submit, fence signalled); the forced
  absence (negative control) reports none and the device still renders. Threads and GPU heap usage return to
  baseline (delta 0). Failed: handles grow exactly +3 per cycle (444 after the warm-up, 471 after cycle 10), and
  private bytes swing 295 to 399 MiB with no trend (the last-minus-first metric read 2.3 MiB per cycle). Round 5
  (`--round owners`) attributes the growth.
- Round 5, whose growth (94426903, built first time; `run_n06.py --round owners --cycles 12`, evidence
  `.artifacts/evidence/native_core/n06/20261112_n06_owners/summary.json`): the driver's, not ours. Handles per
  cycle by kind: our raw VkInstance 0, Qt's adoption 0, our device with one queue 3, plus the second queue and its
  fence 3 (0 added), plus the reference instance 3 (0 added), our host without readback 3 (0 added), the full
  cycle 3 (readback and resize 0 added; 40 cycles, linear at 3.0 in the second half), Qt's own device under the
  same host 3. So NVIDIA 617.42 keeps 3 process handles per VkDevice create and destroy, whoever creates it; our
  code adds none. Threads, GPU heaps and Python gc objects 0 per cycle everywhere; private bytes plateau (lowest
  of the first third 304.3 MiB, of the last third 295.8). The lifecycle round now checks handles as the baseline
  plus 3 per device the run created (counted from the run) and private bytes as that plateau: rerun on the round-5
  module, 16 of 16 PASS (9 devices after the baseline, expected and measured +27;
  `.artifacts/evidence/native_core/n06/20261112_n06_lifecycle_rerun/`).
  For the decisions document's long-term risk table, driver variance row (the lead moves it): on NVIDIA 617.42 a
  device rebuild costs 3 process handles that are never returned, so the product never rebuilds a device except
  on device loss or window replacement (D6 point 4 already says so).
- Round 6, translucent Vulkan window, hidden (a32e18cd, built first time; `run_n06.py --round translucent`,
  evidence `.artifacts/evidence/native_core/n06/20261112_n06_translucent/`): real Qt Quick windows kept invisible
  by `tests/_invisible_windows.py`'s pattern presented continuously on our device and on Qt's own (30 frames
  each). The finding that keeps D7 point 8's first route in play: NVIDIA 617.42 on Windows reports
  `supportedCompositeAlpha` OPAQUE and PRE_MULTIPLIED for an alpha window (OPAQUE only for an opaque one), so Qt's
  rule picks PRE_MULTIPLIED (Qt's source comment says NVIDIA reports OPAQUE only); `SurfaceHasPreMulAlpha` is set
  exactly on the alpha windows; Qt's grab reads alpha 0 in the empty region, 128 in the half-red one, 255 in the
  opaque one, identical to the OpenGL comparison window, and 255 everywhere on the opaque window (negative
  control). The DWM system backdrop (with the frame extended) and the project's AccentPolicy glass both applied
  and the window kept presenting (30 frames after each). Every hidden window is WS_EX_LAYERED (the pattern's
  opacity 0), none uses WS_EX_NOREDIRECTIONBITMAP, and PrintWindow reads opaque black (alpha 255) from Vulkan and
  OpenGL alike: the composed alpha cannot be read hidden, so see-through to the desktop is the lead's visible run
  on Display 1. The run's one FAIL (`qt_scene_alpha_translucent`) was the driver's check reading `0.0 or 255`;
  fixed in Python (missing readings now fail, 0.0 passes; checked on the same summary, old expression False, new
  True); a rerun needs no build.

Long-term risk (driver variance): on NVIDIA 617.42 a device rebuild costs 3 process handles that are never returned,
so the product never rebuilds a device except on device loss or window replacement (point 4 already says so).

## From D7: the first form of point 8 (superseded by the operator) and the lead-position differences

8. **SMP.** In the compositor host (saver and MC builds) the backdrop is this one. In the desktop-window host
   (the SMP build has no compositor) the window's backdrop is also the core's own: a background layer made from
   the current artwork, with the Visualizer layer where a section overlaps it, through the same pyramid and the
   same card shader. That is document 04 section 5's "one backdrop capture shared by all panes" with no
   dependency on the desktop.
   *Superseded for the dedicated SMP build by the operator, 12 Nov 2026:* "Artwork Backdrop if running MC or
   Screensaver Profile/Builds. Desktop when running dedicated SMP builds. Material is meant to show what is
   behind, and that is the consistent way to it." So: in the compositor host (saver and MC builds) the backdrop
   stays the core's background layer as above; in the SMP build's desktop window the material shows the desktop
   behind the window. The artwork-and-Visualizer layer above remains only as the fallback for a device or backend
   on which the window cannot be made see-through, never the chosen look. Routes, in order, proved in N0.6 before
   SMP depends on them: (1) the Qt Quick Vulkan window with a per-pixel alpha swapchain (composite alpha other
   than opaque) and the DWM system backdrop behind it; (2) if the swapchain is opaque on Windows, presenting
   through DirectComposition (the frame shared to a D3D11 swapchain for composition by external memory); (3) the
   OpenGL backend for that one window. The desktop pixels are never captured by us: the window is see-through
   and the system composes, so the cost is the system's.
*Where this differs from the lead's position:* (a) no saturation or luminosity in the build pass (rule 5);
(b) fragment passes, not a compute pass, by default (rule 4); (c) dimming at sample time; (d) (superseded 12
Nov by the operator, see point 8: the SMP build's window shows the desktop; this reasoning now only explains the
fallback) the SMP desktop window does not use the system backdrop: a Vulkan swapchain window on Windows cannot be relied on to be
per-pixel translucent over the desktop (*unverified*; composite alpha is commonly opaque only), so the look must
not depend on it. Whether such a window can be see-through at all is a proof step (N0.6), and it matters before
SMP: the Studio's window is translucent today (`ui/studio/surface.py:181,242`) and changes backend with
everything else at the flip.

## From D7 (N5.7a): the Python presenter read-first, in full

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


## From D9: the proof plan's first form, the lead-position difference, and the N0.7 proof detail

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

*Accepted by the lead, 12 Nov 2026 (N0.7 rounds 1 to 4).* *Proposed (draft for the lead), 12 Nov 2026, from N0.7 (`native/spike_p1`, build rounds 1 to 3: 5475b04d,
71cac383, 3bd851cd; evidence `.artifacts/evidence/native_core/n07/`; Qt findings in `Native_Core_N06_N07_Qt_Facts.md`
section I).* **Verdict: jobs for compute on this vendor (NVIDIA RTX 4090, driver 617.42, Qt 6.12.0), and uploads.**
The job service as built: one job thread per device with its own QRhi on our VkDevice and the second queue of Qt's
graphics family (family 0, index 1); the probe found that second QRhi working (created in under 1 ms, its own
queue, an upload read back exactly), so the job bodies are QRhi, not raw Vulkan. Three slots per job kind; the job
waits on its own `QRhi::finish()` and publishes one atomic generation; the frame driver reads it at frame start and
Qt's QRhi imports the slot with `createFrom`, layouts handed over both ways with `setNativeLayout`.
- (i) A hidden Qt Quick host on our device at the display's 164.8 Hz (6.07 ms), every frame completed with
  `finish()`; the heavy job is the edge field's five stages ported 1:1 at 3840x2160, four builds per job, every 30
  frames; 600 frames x 2 passes per form. Round 1: no jobs 0 late of 1200, Qt frame GPU p99 0.032 ms, completion p99
  3.78 ms; in-frame 40 late (every job frame), 214 periods missed, frame GPU p99 32.7 ms (job frames median 31.2 ms),
  completion p99 34.0 ms; as a job 0 late, 0 missed, frame GPU p99 0.036 ms, completion p99 2.94 ms, the job's GPU
  wait median 19.8 ms (p99 216.7), published a median 26.6 ms after its trigger and swapped in 5 frames later
  (median; p99 36). Round 3 (a new photo): no jobs 0 late, p99 0.024 / 2.20 ms; in-frame 40 late, 185 missed, p99
  31.2 / 32.2 ms (job frames median 20.2 ms); as a job 0 late, p99 0.022 / 2.06 ms, GPU wait median 33.3 ms (p99
  76.2), swap 6 frames later (median; p99 13). Conditions: other GPU users dwm, Firefox, Spotify, Ld9BoxHeadless
  and System (round 1), Ld9BoxHeadless, System and another python.exe (round 3); GPU in P0 at 2595 MHz; two
  third-party hooks injected into the process (`we-graphics-hook64.dll`, in the `vkCmdBeginRenderPass` chain, and
  `windhawk.dll`).
- (ii) Hash-identical outputs: the upload's mip 0 equals the photo's own hash and mip 0 and mip 4 equal the in-frame
  upload; the edge field equals the in-frame field; other seeds and thresholds differ (negative controls).
- (iii) No Python thread state on the job thread (9 of 9 calls) or in the frame driver.
- (iv) Synchronisation validation: the job rounds show only Qt 6.12.0's finding A (every QRhi texture's creation);
  nothing names the second QRhi, the job queue or the latch path, so a second QRhi on one device (U1) and the latch's
  visibility after a host-side completion edge (U3) are clean on this vendor. Qt's other findings (B, C, D) are on
  other paths and are recorded with their routes.
- (v) Twelve retirements with the job's GPU work in flight, by both routes (render side, quiesce with abandon; or the
  context's teardown quiescing first): no crash, the job dropped unpublished, handles exactly the baseline plus the
  driver's 3 per device (+30 for +30), threads, GPU heaps and private bytes back; the job service, jobs and both
  abandon routes add no handle (owners round).
- (vi) 60 s at rest while the host read the latch 9,890 times: 0 wake-ups and 0 CPU cycles on the job thread; one job
  afterwards woke it once (negative control).

Why compute and not uploads only: the 4K build is 20 to 31 ms on Qt's queue, so the in-frame form makes every frame
that carries it late at 165 Hz, while the same work on the second queue leaves every frame on time and Qt's own frame
GPU time unchanged (p99 0.02 to 0.04 ms either way). The cost moves to the job's latency, which is long and uneven
(GPU wait median 20 to 33 ms, p99 217 ms in round 1, when dwm, Firefox and Spotify were also on the GPU, 76 ms in
round 3; the cause of the tail is not attributed): consumers of class (a) and (b)
wait for the completion edge with point 2's deadline and in-frame fallback, and simulations stay in the frame
(point 2c) unless their own measurement moves one. Limits of the proof: the host's scene is light (frame GPU 0.02
ms), so contention under a heavy Visualizer frame is not yet measured (N3.8 re-measures it as D8 row 3 states:
image changes with a Visualizer running); AMD and Intel are unmeasured; a device with no second queue in the graphics
family runs the in-frame form (D6 point 5).


## From D11: the research facts and the recommendation

*Decided by the lead, 12 Nov 2026: take 6.12 (its newest patch release at the checkpoint) before N2.1, as the plan's N0.8 checkpoint lists; the venv is bumped only while no agent is running tests; fallback 6.11.3.* *Proposed (draft for the lead), 12 Nov 2026 (N0.8, researched from pypi.org and doc.qt.io only).* **Facts.**
PyPI lists PySide6 6.12.0 (uploaded 8 Oct 2026, `Requires-Python >=3.10,<3.16`, classifier "Python :: 3.14",
wheel `pyside6-6.12.0-cp310-abi3-win_amd64.whl`, so CPython 3.14 x64 Windows is covered) as the newest minor and
6.11.3 (26 Oct 2026) as the newest 6.11; 6.11.2 was 18 Aug 2026. The Qt 6.12.0 class reference and "What's New in
Qt 6.12" give QRhi: `QRhiCommandBuffer::drawIndirect(QRhiBuffer *indirectBuffer, quint32 indirectBufferOffset,
quint32 drawCount, quint32 stride = sizeof(QRhiIndirectDrawCommand))` and `drawIndexedIndirect(...)` (both "since
6.12"), the buffer usage `IndirectDrawBuffer`, and the features `QRhi::DrawIndirect`, `QRhi::DrawIndirectMulti`
(drawCount > 1 natively supported by the backend) and `QRhi::ShaderDrawParameters` (`gl_BaseInstance`,
`gl_BaseVertex`, `gl_DrawID`). The Vulkan backend also uses `VK_EXT_device_fault` for device-lost detail. Nothing
else D5.3 or D5.6 lists is gained: `QRhiTexture::Format` in 6.12 still has no RG16F, RG32F or R11G11B10F;
sampling a resolved multisample colour texture is still not offered (`ResolveDepthStencil` is since 6.8, so it
is already in 6.11.2); `VertexShaderPointSize` and `Timestamps` (whole command buffer) are unchanged. So the one
D5.3 row that disappears is "Indirect and count draws", and D5.6 row 14 (the dead-tail cull) could use
`drawIndirect` instead of the restructured pass. Compatibility: the class reference still says QRhi has "no source
or binary compatibility guarantees" (Qt GuiPrivate). Every QRhi call `native/spike_p1/src/` makes (`QRhi::create`,
`beginOffscreenFrame`/`endOffscreenFrame`, `nextResourceUpdateBatch`, `newBuffer`, `newTexture`,
`newTextureRenderTarget`, `newShaderResourceBindings`, `newGraphicsPipeline`, `driverInfo`, `isYUpInFramebuffer`,
`nativeHandles`, `QRhiVulkanInitParams::preferredInstanceExtensions`, `QRhiGles2InitParams::newFallbackSurface`,
and on the command buffer `beginPass`, `endPass`, `setGraphicsPipeline`, `setViewport`, `setShaderResources`,
`setVertexInput`, `draw`, `resourceUpdate`) is still documented in 6.12.0 with no obsolete or removed marker.

**Recommendation: take 6.12.0 first, before N2.1.** One paragraph of reason: the core is compiled against the
exact Qt, so every later upgrade reruns both backends' parity gates against native code; today nothing native
exists, so the move costs only what D11 already names (the suite and a GitHub frozen build, which the lead runs)
and the first C++ slice starts on the final API. Waiting pays the same cost later with C++ in the way, and the
version we would then adopt has `drawIndirect`, which lets the dead-tail cull and the population harness's
"draw the maximum" comparison in D5.3 be decided on the API that will ship. The gain is modest (one service row,
and "indirect" is a measured admission anyway), so the recommendation rests on the timing, not on the feature. If
the suite or the frozen build shows a regression that is not ours, the fallback is 6.11.3 or 6.11.2 with D5.3's
row kept, and nothing native has been lost. **Risks:** 6.12.0 is a `.0` five weeks old (a 6.12.1 is likely
soon); a Qt Quick scene-graph or clip behaviour change could touch the protected optimisations (ce07b991, 07486d83,
985b9d53), which the suite and the clip oracles must show unchanged; PySide6 6.12 behaviour on Python 3.14 is
unverified here; `DrawIndirectMulti` backend coverage (D3D11 in particular) is not stated in what I read, so the
count-draw form may need a per-backend feature check or a fallback loop. **Not confirmed:** the exact Qt 6.12.0
release date (taken from the PyPI upload date), that the 6.12.0 wheel bundles Qt 6.12.0 (assumed from the version
match), whether PySide6 exposes any of the new names (the core is C++ against the SDK, so it does not need to),
the fields of `QRhiIndirectDrawCommand`/`QRhiIndexedIndirectDrawCommand`, `QRhi::create` and
`beginOffscreenFrame`/`clipSpaceCorrMatrix`/`backendName` signatures (the pages' text I read did not define them),
and any 6.12 changelog entry beyond "What's New".

## From D12: the problem

**The problem.** Port rule (g) (N2.5 round 4) made Settings and Studio work rebuild-free for a ported mode, but its
per-frame values were still hand-written C++ (Spectrum's `spectrumBlock`), and the reader knew only the schemas compiled
into `frame_abi_generated.h`. A new mode, or a new field in a mode's record, therefore still meant a module build, which
the lead's rule of 14 Nov forbids while a mode is iterated ("new modes are built on the native core only, through its
generic mode content").

## From D13: what the product fullscreen fragments read

Supersedes D12 point 3's refusal of samplers and its "v_uv only" input; the rest of D12 stands.

**The problem.** The first consumers of the background layer (N5.7a's presenter, N5.2a's seven transitions: Crossfade,
Burn, Particle, Ripple, Slide, Warp Dissolve, Wipe) each draw one fragment between two pictures through
`rendering/quick/transitions/fullscreen_pass.py`, and Bubble samples two textures from its ambient render. N2.9's pass
refused every sampler and gave only `v_uv`, so none of them could be drawn without a second pass layer. What the
product fullscreen fragments read (the root cause of the shape, from their baked packs' reflection):
- the transitions: `layout(location = 0) in vec2 vUv` (the item quad's uv, `rendering/gl_programs/item_quad.py`: y up,
  1 at the item's top; each fragment samples at `(vUv.x, 1 - vUv.y)`), `uOldTex` at binding 0 and `uNewTex` at binding
  1 (linear, clamp to edge, no mips: `tools/transition_contact_sheet.py` and the presenter's textures), one pass block
  at binding 18 opening with `uMatrix`, `uItemSize` (only the Python vertex stage reads them), `u_progress`, then the
  transition's own values; Particle, Ripple and Warp Dissolve also `u_resolution`, meaning the viewport's pixels;
- the 2D modes: `v_uv` (the Visualizer quad's uv, `render_contract.py`: y down) and one block; Bubble also
  `u_ambient_texture` (binding 0) and `u_ambient_light` (binding 1).


## From D1, D2, D3 and the transport rule: the drafts, the source inventory, the tests and the questions

#### D1, D2, D3 and the transport rule

*Decided by the lead, 12 Nov 2026 (answers in "Lead decisions on the N0 drafts" below); drafted as:* *Proposed (draft for the lead), 12 Nov 2026. Nothing in this section is decided. Drafted by a Sonnet agent from
current source; every "today" claim carries a file:line and was read on 12 Nov 2026 at commit `7ac980d7`. The
statements are in `Current_Plan.md` (item 8b, N0, box P3.0) and the inputs in the closeout document's section 3.
D9's job thread uses D1's barrier, so D1 is written with both readers in mind.*

##### What exists today (the ground the three contracts stand on)

The shared-memory stream is one object per Visualizer session, `PacketMailbox`
(`core/visualizer_engine/packet_mailbox.py:101`) over the frame packet ABI (`core/visualizer_engine/packet_abi.py`,
ABI 2: a 64-byte header, three slots, a seqlock per slot, `consumed_sequence` written by the reader,
`packet_abi.py:8-58`).

- **Owner of the mapping:** the main process. `PacketMailbox(role="reader")` creates it (`packet_mailbox.py:135`,
  `packet_abi.py:325-334`), the worker attaches by name (`packet_mailbox.py:140`), and only the owner closes and
  unlinks it (`close`, `packet_mailbox.py:459-482`). A capacity growth creates a second mapping (`stage_capacity`,
  `:398-412`) and swaps on the writer's acknowledgement (`commit_capacity`, `:423-436`; the writer's side
  `attach_capacity`, `:438-453`); the link drives it (`engine_worker_link.py:664-701`).
- **The only reader is Python, on the GUI thread.** `take()` and `peek()` run under the mailbox lock
  (`packet_mailbox.py:297-310`), which `close()` and `commit_capacity()` also take. `FramePacketReader.read_latest`
  copies the payload into a `bytes` (`packet_abi.py:303`) and the mailbox decodes it (`packet_mailbox.py:246`). The
  render thread never touches the mapping: it receives an immutable snapshot published through the render bridge
  (`quick_presentation_sync.py:204-211`). That is why no close/unmap hazard exists today: Python holds a
  `memoryview`, so `SharedMemory.close()` raises `BufferError` rather than unmapping under a live view, and the
  mailbox releases its views before closing (`packet_mailbox.py:477-480`). A native reader holds a raw pointer, which
  Python's export count cannot see.
- **Three readers of different strength already call the mailbox**, and D2 has to separate them:
  1. *Consuming take*: `quick_presentation_sync.py:207` and `:312` (the per-wake sync) and
     `quick_display_visualizer_owner.py:2421` (recovery pacing). `_consume` acknowledges at once, right after decode
     (`packet_mailbox.py:259-263`).
  2. *Peek*: `quick_display_visualizer_owner.py:646` ("is anything unread", to re-arm the wake after a display
     transfer) and `:2017` (`_worker_waiting_for_fresh_frame`: reads `present_frame`, `engine_generation`,
     `activation_id` and `mode_id` of the newest frame). `peek` is not as light as its name: it decodes the whole
     payload (`_read`, `packet_mailbox.py:238-257`) and `read_latest` already advances `accepted`
     (`packet_abi.py:307`), so a later `read_latest` of the same frame returns nothing; only the `_peeked` cache lets
     `take` hand it out.
  3. *Held frame*: `last_taken` (`packet_mailbox.py:290-295`), read by the recovery hold
     (`quick_display_visualizer_owner.py:2247-2256`, dropped at `:2258-2267`) and by
     `rendering/quick/visualizer/edit_content_envelope.py:399`. It is a decoded Python object, so it survives the
     mapping being closed; `commit_capacity` clears it (`packet_mailbox.py:434`).
- **Liveness today** is two things: the supervisor's per-process heartbeat (3 s; it only retires a dead or hung
  worker, `engine_worker_link.py:28-35`), and a per-session cadence watch run from the worker's heartbeat handler
  (`engine_worker.py:1064-1075` calling `watch_cadence_liveness`, `:587-618`): the session fails closed when its
  runtime's step count does not move across two heartbeats at least a second apart
  (`STALLED_HEARTBEATS_BEFORE_CLOSE = 2`, `STALL_OBSERVATION_MIN_S = 1.0`, `:92-93`), and a failed-closed session ends
  the wake pipe (`_fail_closed`, `:620-632`), which the owner's listener reports as the session's end
  (`packet_mailbox.py:324-352`, `engine_worker_link.py:815-825`). This is the L4 fix and it is per stream already
  on the writer side; nothing exists on the reader side.
- **The retained-frame drop edge exists once, in Python:** R-184
  (`Docs/Historical_Bugs/R-184_Engine_Worker_Mode_Switch_Kept_Drawing_The_Outgoing_Frame_After_Its_Fade_Out.md`):
  `VisualizerItem.drop_retained_frame` (`rendering/quick/visualizer/item.py:294`) marks the item; its next
  `updatePaintNode` passes `clear_snapshot` once (`item.py:381,578`; `node.py:113,127`); reached through
  `scene_controller.drop_visualizer_retained_frame` (`scene_controller.py:2829-2839`) from
  `_activate_pending_mode_on_worker` (`quick_display_visualizer_owner.py:2062`).
- **Slot identity is already in the slot** (ABI 2: runtime generation, engine generation, activation id, mode code,
  flags, `publish_ns`, all under the slot's seqlock, `packet_abi.py:40-47`), so a head read needs no payload.
  `payload_schema` is written (`packet_mailbox.py:172`) but **read by nobody**; the only schema check is the codec's
  own two-byte prefix inside `decode` (`frame_codec.py:153-154`).

##### D1. The native reader against the GUI thread closing the mapping (proposed; decided by the lead 12 Nov)

**The hazard (new with the native reader).** The render thread would read slots through a raw pointer while the GUI
thread runs `close`/`commit_capacity`/retire/recovery, which close the Python `SharedMemory`, unmap it and (POSIX)
unlink the name. Python's `BufferError` guard (above) does not exist for a C++ pointer. Five edges close or replace
a mapping: owner `close` (`packet_mailbox.py:459`), `commit_capacity` (`:423`, a remap to a larger mapping),
`link.retire` (`engine_worker_link.py:746-780`) and `link.close` (`:782-811`), and worker replacement
(`quick_display_visualizer_owner.py:2279-2351`, `_bind_replacement` `:2396-2406`).

**Proposal, three rules.**

1. **The core maps its own view; it never uses Python's pointer.** At activation the core opens the mapping *by
   name* (`OpenFileMapping`/`MapViewOfFile` on Windows, `shm_open`/`mmap` on POSIX), validates magic, ABI and
   shape exactly as `_validate` does (`packet_abi.py:169-182`), and owns that view until its own release edge. The
   name is plain data carried by the activation (the mapping name the link already holds, `mapping_name`,
   `packet_mailbox.py:455`). On both platforms a mapped view keeps the section alive after the owner closes or
   unlinks the name (Windows removes a named mapping when its last handle closes, as
   `shared_memory_transport.py:1-7` already relies on), so the owner's close can never unmap memory the reader is
   copying. A name that no longer opens means the stream is retired: the reader enters the retired state, never an
   error loop. This is the "pin the mapping" branch of the plan's wording, chosen because it removes the
   GUI-waits-for-render-thread dependency (which can deadlock against Qt's synchronisation of the two threads).
2. **The reader has three states, changed by one atomic: `open`, `retiring`, `retired`.** The GUI side's retire
   edge (the same edge as `link.retire()`, `engine_worker_link.py:746`, which already never waits) posts a *retire
   request* to the core: it sets `retiring` (release store) and schedules the reader's release on the render thread
   (`QQuickWindow::scheduleRenderJob`, run at a render-thread stage, or `sceneGraphInvalidated` at window
   destruction; Qt documentation, to be confirmed in the N0.6 harness). The render thread, at its next frame edge
   or job, finishes or abandons any copy, unmaps its view and any held frame, and stores `retired`. A frame never
   starts a copy once `retiring` is set. The GUI never waits for `retired`: nothing it does afterwards (close,
   unlink, replacement) depends on it, because of rule 1. This is the *render admission closure plus quiescence
   barrier* of the plan's wording, made asynchronous and used for the *semantic* part only: no frame of a retired
   stream is presented, and the reader's held resources (a copied frame, uploaded geometry, D9's job slots) are
   released on the render thread that owns them.
3. **A remap is a new stream, not a new pointer.** `commit_capacity` (a larger mapping) and worker replacement hand
   the core a new `(mapping name, engine generation, activation)` key; the core opens the new view, validates it,
   and only then retires the old reader state (the old view is released by the rule-2 job). Between the two, frames
   from the old stream are not presented after the new stream's first frame is accepted. The old mapping's name may
   already be unlinked; nothing depends on it.

**D9's job thread uses the same barrier.** A job holds a reference on the reader state it was built from (a
generation counter, not a pointer into the mapping); a retire request marks the device's jobs for that stream
abandoned; the job thread checks the stream state before it publishes its completion edge, and the device is not
destroyed until the render-thread retire job and the job thread have both reached their quiescent point (a join in
the device's destruction, never in the GUI thread's close). This is D9 point 6 made concrete.

**Liveness is per stream.** A stream is `(mapping name, engine generation, activation)`. Writer-side liveness is
what `watch_cadence_liveness` already is (`engine_worker.py:587-618`) and is kept. Reader-side liveness is new and
separate from "the render thread answered a heartbeat": the core keeps, per stream, in a small block the GUI can
read without a lock, `last_accepted_sequence`, `copies_started` and `copies_finished` (two monotonic counters).
`copies_started != copies_finished` across two observations a second apart is a reader stalled inside a copy, and is
reported as that stream's failure (the owner's existing failure edge, `_on_engine_worker_failed`), not as a worker
failure. This answers the closeout's "the render thread answered is not the reader finished its copy"
(closeout section 3, inputs, L4). The GUI reads these counters only on the heartbeat edge and on edges it already
has; no timer, thread or poll is added.

**Today vs new.** Already today: the owner is the only closer and unlinker (`packet_mailbox.py:459-482`); a retiring
link never waits (`engine_worker_link.py:746-749`); a retired generation's frame is never handed to a replacement
(`packet_mailbox.py:10`, test `test_a_retired_generation_never_reaches_its_replacement`,
`tests/test_visualizer_engine_packet_mailbox.py:113`); per-session writer liveness (`engine_worker.py:587`). New:
the core's own view, the three states, the retire job, the reader counters. The owner of all of them is the
module's reader class (one small C++ type, the packet reader), with the GUI side a single "retire stream" call.

**The test that fails without the contract** (harness C++ test in `native/spike_p1`'s successor, after N0.9, plus a
Python driver):
- *close during copy:* a test hook (compiled into the harness only, never the product) pauses the reader inside a
  copy of a slot; the GUI side then closes and unlinks the mapping and (second case) commits a capacity remap; the
  hook resumes. Pass: no fault, the copy completes against the pinned view, the frame is discarded because the stream
  is `retiring`, the next stream's first frame is accepted. *Negative control:* the same test with the reader
  built to borrow Python's pointer (the thing the contract forbids; a harness variant, seen to fault or to trip the
  reader's deliberate "view unmapped" assertion on the pause-close-resume order).
- *resize and remap:* a capacity commit with frames in flight: no frame of the old stream presented after the new
  stream's first; both views released exactly once (the reader counts opens and releases).
- *retire:* retire with the render thread parked in a copy and with it idle; the release job runs; the GUI call
  returns without waiting (measured: the call's duration does not depend on the pause).
- *worker replacement:* kill the worker mid-publish (the harness writer stops with `sequence_begin` odd, the torn
  state the ABI defines), replace it; the core never accepts the torn slot (`torn_reads` counter,
  `packet_abi.py:310`), never presents the old stream after the replacement's first frame
  (`_bind_replacement`, `quick_display_visualizer_owner.py:2396`), and releases the old view.
- *per-stream liveness:* a reader paused inside a copy is reported for its stream while the worker's own
  heartbeats keep answering; negative control: remove the counters, the test sees no failure.

##### D2. One consuming reader, a non-consuming head read, and the drop edge (proposed; decided by the lead 12 Nov)

**Rule.** Once a stream is native, the core is the only reader that consumes: only it writes `consumed_sequence`
(`packet_abi.py:317-319`), and only it decodes payloads. The Python owner reads the slot **head** only.

**The consuming reader's acknowledgement edge.** Today the acknowledgement happens at the end of `take`, right
after decode and before the frame is presented (`packet_mailbox.py:259-263`), and the closeout asks that the edge be
defined exactly. Proposed, to keep parity with today: the core acknowledges a sequence at its **accept edge**:
after the whole frame is copied and validated (both seqlock reads, identity equal to the expected stream, schema
known) and after the frame's protected-edge mask has been handed to the frame driver's edge handler, and before the
frame is recorded for presentation. It does not wait for the swap. Reason: edges are "short-lived" and a writer
carries them into every later slot until acknowledged (`packet_abi.py:28-31`, `FramePacketWriter.publish`
`:218-223`); acknowledging at the swap would carry an edge across several frames the core had already read, a
behaviour change from Python. If the lead prefers the swap edge, it is one flag in the reader and the parity
gate shows the difference. A frame the core rejects (torn, wrong identity, unknown schema) is not acknowledged.

**The head read (new).** A function on the reader, `read_head()`, that returns, from the newest *whole* slot, only
the 64-byte head: sequence, flags, protected-edge mask, runtime/engine generation, activation id, mode code,
logical timestamp. It performs the seqlock check on the head and reads no payload, copies nothing, **does not move
`accepted` and does not write `consumed_sequence`**. It is what every Python read that is not the consumer needs:
`_worker_waiting_for_fresh_frame` needs `present_frame` (the `FLAG_PRESENT_FRAME` bit), `engine_generation`,
`activation_id`, and the mode (`mode_code`, `packet_abi.py:80-97`; the owner compares `mode_id` strings, so it maps
the code through the table that already exists); "anything unread" (`quick_display_visualizer_owner.py:646`) is
`latest_sequence > consumed_sequence`, which `has_unread` already is (`packet_abi.py:313-315`). Owner today:
`FramePacketReader` in Python; the native head read is the same function in the module, exposed as plain data. The
Python `PacketMailbox` keeps `peek`/`take` for the in-process and offline paths; on a native stream the owner calls
only `read_head`. The three call sites of the consuming take (`quick_presentation_sync.py:207,312`,
`quick_display_visualizer_owner.py:2421`) are retired with the Python renderer; until then a native stream has no
Python consumer (the stream is either Python-consumed or native-consumed, chosen at activation, never both).

**The drop edge (R-184), written as a contract.** Every frame a native reader retains (a copied payload, geometry
uploaded from it, a texture rendered from it) is tagged with `(stream key, sequence)`. The core exposes one
`drop_retained_frame()` edge, posted from the GUI thread and applied by the core at its next frame edge exactly as
`item.py:294,381,578` does today (a flag read, not a per-frame check). It is raised by the same owner call sites
that raise it now: a hidden activation commit that discards the pending snapshot
(`quick_display_visualizer_owner.py:2062`, R-184's cause), a recovery hold's drop (`:2258-2267`), display power off,
and retire (rule 2 of D1). The drop clears the retained frame and keeps the stream bound and the geometry resident
(D3), as R-184's fix keeps the source bound. **The head read cannot resurrect a dropped frame** because it returns
only metadata and the core's accepted-sequence watermark: after a drop the core sets `dropped_through =
the sequence it held`, and any frame with `sequence <= dropped_through` is never re-presented, whatever a head read
or a late wake says; only a frame with a larger sequence and a matching identity is. (Today `read_latest` has the
same property through `accepted`, `packet_abi.py:290-291`; the contract makes it hold across the drop.)
As built (ABI 9, audit 14 Nov low 2): the retained frame is always the last accepted one, so the accepted watermark
is the drop's; the reader keeps no `dropped_through` of its own (it could never exceed `accepted`). The drop round's
control is still `head_resets_watermark`, which resets `accepted` and resurrects the dropped frame.

**Today vs new.** Today: acknowledgement at take; `peek` decodes and advances `accepted`; one drop edge for the
Python node. New: a head read that decodes nothing and moves nothing; the native accept-edge acknowledgement; the
drop edge and watermark in the core.

**Test that fails without it.**
- *one consumer:* run a native stream with the Python owner's calls active; assert `consumed_sequence` is written
  only by the core (a counter on the Python reader's `acknowledge`, `packet_abi.py:317`, stays zero) and that a
  protected edge published while the owner polls the head is still delivered to the core exactly once. Negative
  control: let the owner call `take()` on the same stream (the forbidden second consumer); the edge is stolen and
  the test fails.
- *head read is non-consuming:* `read_head()` ten times between two publishes; `accepted` and `consumed_sequence`
  unchanged; the core still receives the frame and its edges.
- *drop edge, the R-184 shape:* publish a frame, take it, raise a profile-change discard and the drop in one GUI
  turn; render; the card is empty at the next render (the existing parity bar,
  `tests/test_visualizer_owner_render_parity.py::test_the_worker_path_draws_the_in_process_pixels_at_non_default_settings`,
  must pass on the native item). Negative control: remove the drop call (the pre-fix owner); the outgoing frame
  stays, as R-184 recorded.
- *no resurrection:* drop at sequence S, then a head read and a replayed wake for S; the frame is not presented;
  publish S+2: presented. Negative control: reset the watermark on the head read.

##### D3. Extruded Bubble geometry once per revision (proposed; decided by the lead 12 Nov)

**Today.** The drift families' geometry (`DriftFamily.geometry`, packed rows, `extruded_bubble_drift_log.py:46-72,
102-115`) travels **inside every frame**: the frame carries `drift_families`
(`logical_frame_capture.py:455`), the codec writes the dataclass with its `bytes` field each time
(`frame_codec.py:34,115-120`), and the slot is sized to hold the maximum geometry beside the base envelope
(`frame_capacity.py:35-42`: chains `CHAIN_GEOMETRY_BYTES + STEP_HISTORY * KNOT_DECISION_BYTES` per chain, snow and
specks `CLOUD_GEOMETRY_BYTES` per row, at `SPECKS_FULL = 216000` and `SNOW_FULL = 2500`,
`core/constants/extruded_bubble_world.py:11-12`). Three slots of that size are mapped.
`DriftLog.admit` (`:147-170`) mints the key: a different `key` is a new revision continuing from the old one
(`rebase_from`, `first_serial`), a larger capacity with the same key extends rows and keeps the revision
(`:159-165`). `_REVISIONS` is `itertools.count(1)` (`:43`): unique inside one process only, **so a replacement
worker's revision 1 is not distinguishable from the first worker's revision 1 by revision alone**. The render
side keys its state on the revision alone: `state.revision == family.revision` (`extruded_bubble_drift_solver.py:476,
539`). Whether a replacement worker could alias there is not proved today; the first test below is that proof.
Today's release edges: `release()` (`:380-389`), family left the list (`:464-467`), geometry edit (`:523-537`: old
buffers deleted after the dispatch), revision change (`:539-542`), capacity change (`:545-549`). **Two failure edges
are not covered:** at `:539-542` and `:545-549` the old buffers are deleted *before* `_allocate` runs, and
`_allocate` can raise (`ValueError` at `:563`, or a GL error), leaving `self._families[name]` holding names that
were deleted; at `:529-536` a raise inside `_dispatch` skips `_delete(state.geometry ...)` at `:536` and leaks the
old rows. The CPU oracle data is already off the wire: `render_descriptor` strips `source`
(`extruded_bubble_drift_log.py:63-72`, used at `logical_frame_capture.py:455`), and the codec's array tag
(`frame_codec.py:127-137`) exists only for offline captures.

**Proposal.**

1. **Identity.** A geometry resource is keyed by `(worker namespace, engine generation, activation id, family,
   geometry revision, capacity)`. The *worker namespace* is the stream's mapping token (the `srpss_viz_<token>_<n>`
   name, `packet_abi.py:73,330`), unique per process run and per mapping, so a replacement worker or a remap is a
   different namespace. Bare revision is never an identity. The solver's compare at `:476,539` becomes the whole key.
2. **Geometry is not in the frame.** The frame carries only the key of each live family and the small per-frame
   state (steps, knots, counts, controls). The geometry bytes travel once per key in a *geometry arena*: a second
   mapping, created and owned by the main process like the frame mapping (so the owner model of
   `packet_mailbox.py:104-105` is unchanged), with two banks per family. The worker writes the back bank
   completely **before** it publishes a frame that names its key; the reader uploads when it first sees a key it
   does not hold. A bank is rewritten only after the core has acknowledged a frame that names a different key for
   that family (so a reader copying a bank is never overwritten). The arena's size is part of admission
   (`required_slot_bytes`'s geometry term, `frame_capacity.py:35-42`, moves from the slot to the arena; the slot
   shrinks to the base envelope). D3 sizes nothing against the worker's +34 MB at the first Waveform Ribbon
   (OpenBLAS's reserve, per the plan).
3. **Residency and release, one rule per edge.** A per-key residency in the core: `requested`, `uploading`,
   `resident`, `failed`, `retiring`.
   - *Geometry change (new key, same activation):* the old key stays `resident` until the new key is `resident`
     and one frame using it has been recorded; then the old is released (matches the CPU rebase and the
     two-buffer overlap of `:523-537`). Never an empty frame in between.
   - *Failed swap / upload failure:* the new key goes `failed` (one logged error, no retry on the next frame; a
     retry only for a *new* key), the old key stays resident and in use, and nothing is deleted before the
     replacement exists. This fixes the `:539-549` ordering for the native path; the OpenGL solver gets the same
     ordering as an N1 box if the lead wants it now.
   - *Capacity growth, same key:* a new key (capacity is in the key), with the history rows copied from the old
     residency before it is released (the `_allocate(family, state)` copy, `:559-576`).
   - *Mode or activation change, drop edge, retire, device loss, window destruction:* all residencies of the stream
     are released on the render thread by the D1 retire job; device loss releases without reading back (nothing
     is read back, solver docstring `:11-12` of the drift log).
   - *Counting:* the residency table counts live keys per family; steady state is one, transient two, after
     teardown zero (`DriftSolver.has_resources`, `:376-378`, is today's equivalent for the Python path).
4. **Oracle data stays off the wire.** The native frame schema has no array and no `source` field. The worker keeps
   `source` (the float64 arrays) for `MaterialDriftReference` (`extruded_bubble_drift_log.py:238`) only. A frame
   built with a non-empty `source` is refused at encode, not silently stripped.
5. **Per-frame state is separate and small:** the step record (`STEP_FIELDS`, `:29-34`, 30 fields), the knot
   decisions and the counts: what changes every tick.

**Tests that fail without it.**
- *identity:* two streams (a worker and its replacement, or two mappings) both publish "revision 1" with different
  geometry; the renderer must upload the second. *Negative control:* key on revision alone (today's compare,
  `:476,539`): the stale geometry is drawn; assert on the uploaded bytes' hash.
- *once per key:* N frames under one key upload the geometry once (an upload counter), and the frame bytes on the
  wire contain no geometry (frame size is independent of `capacity`). Negative control: today's per-frame
  descriptor (`frame_codec.py:115-120`), where frame size scales with capacity.
- *geometry change, failed swap, upload failure:* inject an allocation failure at the new key; the old key's
  buffers still exist, are still drawn, the failure is logged once and not retried per frame; assert residency
  counts after each edge. Negative control: the delete-before-allocate order (`:539-542`), where the old names are
  gone and the next frame uses them.
- *release:* after teardown, drop edge, mode switch and window destruction the residency count is zero and the
  allocator's live-buffer count returns to its baseline. Negative control: skip the retire job.
- *oracle off the wire:* encode a frame whose descriptor still has `source`; refused. Negative control: the
  Python codec's `_ARRAY` tag would carry it.

##### The transport rule (proposed)

1. **Nothing crosses through the stdlib resource sharer.** An ordered control refuses a sharer-backed `Connection`
   or socket on every platform (`core/process/control_messages.py:28-36,71-74`) because the sharer keeps a
   sender-side duplicate that a worker dying before decoding never collects
   (`core/process/control_messages.py:7-14`, `core/visualizer_engine/wake_channel.py:10-15`). The core adds no
   descriptor of its own through any queue.
2. **How a handle or mapping reaches a process.** POSIX: a *name* in the control message (plain data), opened by the
   receiver (`wake_channel.py:10-11`, `packet_mailbox.py:140`). Windows: either a name (named mappings, as the frame
   mapping already does) or a handle **duplicated into the exact target process** by the supervisor under its
   lock (`control_messages.py:39-58,75-84`: the duplicate belongs to the child even if never decoded; its exit
   reclaims it). The native core follows the same two forms; a new native object that needs to reach the worker
   (the geometry arena of D3, a job-thread signal) is a mapping name or an exact-process duplicate, never a
   pickled handle.
3. **Fixed-layout per-mode native schemas.** Each mode that crosses to the core has a fixed-layout record
   (explicit offsets, little-endian, 16-byte aligned, a version), so a native reader validates by size and offsets
   and does not decode a tagged stream. The slot's `payload_schema` field (`packet_abi.py:19,230`) selects it. It is
   **written today but read by nobody** (`packet_mailbox.py:172`; no reader reads `payload_schema`): the native
   reader and the Python reader both start validating it.
4. **The tagged Python codec namespace is reserved.** `CODEC_SCHEMA = 1` (`frame_codec.py:21`) keeps meaning "tagged
   Python codec" and is never used by a native schema. Proposed numbering: `payload_schema` 1 is the Python codec;
   native schemas are `0x100 | mode_code` in the low byte for the mode and the version in bits 16-23 (mode codes are
   append-only, `packet_abi.py:80-90`); values 2 to 0xFF are reserved. (The lead may prefer another scheme; the
   rule is that the namespaces cannot collide and a mode's schema is derivable from its mode code and version.)
5. **An unsupported payload fails explicitly.** A reader that does not know a slot's `payload_schema`, mode code
   or schema version refuses the frame: the stream is reported failed (the owner's failure edge), a counter and one
   logged error are recorded, and the frame is not acknowledged and not presented. It does not guess, skip silently,
   or fall back to the Python decode. The Python reader's equivalent today is the `FrameCodecError` raised by
   `decode` (`frame_codec.py:153-154,199,225,232`), which surfaces from `take()` to its caller; the contract adds
   the check at the slot head, before any payload copy.

**Tests.** (a) A native reader given a slot with an unknown `payload_schema`, an unknown mode code, a schema version
newer than it knows, and a size that disagrees with the fixed layout: each is refused, counted, not acknowledged
(`consumed_sequence` unchanged), stream reported failed. Negative control: a reader that falls through to a
generic decode accepts the frame. (b) A control message carrying a sharer-backed `Connection` is refused
(`SharerBackedTransferRefused`; the existing guard's test), and a native object's transfer in the harness uses a
name or a target-process duplicate and leaves no handle behind after the target dies before decoding (handle count
before and after). Negative control: send it through a queue with the sharer. (c) The codec namespace: assert no
native schema id equals `frame_codec.CODEC_SCHEMA` and that the Python decoder refuses a native schema's payload.

##### Questions for the lead (D1 to D3 and the transport rule)

1. D1 chooses *pin by the core's own view* plus an asynchronous retire job, never a GUI-side wait. Is that the
   branch you want, or the barrier with a bounded GUI wait? (The wait risks a deadlock against Qt's sync of the GUI
   and render threads; the draft avoids it.)
2. D2's acknowledgement edge is the *accept* edge (parity with `packet_mailbox.py:259-263`), not the swap. Confirm.
3. D3 moves geometry out of the slot into a parent-owned arena with two banks per family. The alternative is to
   keep geometry in the frame and key only the retention; it costs the 216,000-row bytes per frame (about 6.9 MB
   of specks geometry at `SPECKS_FULL`, `frame_capacity.py:35-42`) and is what the plan's "once per" is meant to
   remove. Confirm the arena, and whether the OpenGL solver's delete-before-allocate failure order
   (`extruded_bubble_drift_solver.py:539-549`) is fixed now in N1 or only in the native path.
4. The `payload_schema` numbering in transport rule 4 is a proposal.

## From D5, the rest (N0.5): the full draft

#### D5, the rest: resources, lifetime, admission, device loss, and what a mode may not do (N0.5)

*Bake targets (doc sweep, 12 Nov 2026): the spike still bakes `100 es`; the product module (`native/core/`) does not (SPIR-V, GLSL 430, HLSL 5.0, MSL 1.2).*

*Decided by the lead, 12 Nov 2026 (answers in "Lead decisions on the N0 drafts" below); drafted as:* *Proposed (draft for the lead), 12 Nov 2026. This completes D5 (N0.5); it does not change D5.1 to D5.4, D6, D7, D9
or D10, and nothing here is decided. Every "today" claim was read in source at commit `7ac980d7`.*

##### Today, in source

- **A mode renderer is a small Protocol** (`rendering/quick/visualizer/render_contract.py:175-188`): `mode_id`,
  `has_resources`, `render(frame)`, `release_resources()`, and for a renderer with `prepared_reveal` an optional
  `prepare_step(frame) -> bool`. It receives a frame object that carries Quick's own state (the item matrix
  `matrix_values`, a shared `quad_vao`, a viewport; `render_host.py:206-213`).
- **One host per window owns the mode renderers** (`QuickVisualizerRenderHost`,
  `rendering/quick/visualizer/render_host.py`): it creates a renderer on the mode's first frame
  (`:200-203`), sets blend, cull, depth and viewport itself before the mode runs (`:229-241`), and releases the
  inactive modes **once, after the active mode has drawn**, at the mode boundary (`_retire_inactive_at_boundary`,
  `:285-301`; `release_inactive_implementations`, `:303-357`): render-thread only, a failed release stays cached and
  accounted and is retried only at the next boundary or at teardown, never per frame. `release_resources` at
  teardown (`:359-388`) refuses to run without a current context. The node's `releaseResources`
  (`rendering/quick/visualizer/node.py:415-444`) runs on Qt's render owner; `sceneGraphInvalidated` reaches the item's
  retirement (`item.py:182-191,351-357`).
- **Warm-up is gradual and host-owned**: a hidden mode (content fade 0) is prepared one unit at a time, spaced by
  `PREPARE_SPACING_S` using the host's clock (`render_host.py:252-262`).
- **Accounting exists and is passive**: `has_resources` on every renderer, `_record_ownership` in the host
  (`render_host.py:205,352,388`), and `ResourceAccountingRecord` / `ResourceAccountingSnapshot` (owner, generation,
  bytes, lease count; `core/performance/resource_metrics.py:41-88`).
- **Per display, one render thread and one context** (`rendering/quick/gl_query.py:6-7`, per the research file);
  a display transfer rebuilds on the target (plan 1C.2; D6 point 4).
- **No mode implementation reads a clock** (a grep of `rendering/quick/visualizer` finds clocks only in the item
  and host, `item.py:371,439,481`, `render_host.py:257`, and trace sampling, `render_contract.py:73,107`;
  `rendering/quick/scene3d` has none). Time is in the frame (`ExtrudedBubbleFrame.time`,
  `logical_frame_capture.py:446-450`).
- **No device-loss handling exists** in the Python renderer: a grep for graphics reset status, context lost or
  device lost in `rendering/`, `engine/`, `core/` and `ui/` finds nothing.
- **Modes set GL state today**: 97 `glEnable`/`glDisable`/`glBlendFunc`/`glDepthFunc`/`glDepthMask`/`glCullFace`/
  `glFrontFace`/`glViewport`/`glScissor` sites in six implementation files
  (`rendering/quick/visualizer/implementations/`: `shockwave_grid.py` 31, `sphere_voxel.py` 21, `extruded_bubble.py`
  19, `bubble_ambient_gl.py` 17, `extruded_spectrum.py` 5, `oscilloscope.py` 4). That is the count the port removes.

##### Resource ownership and lifetime (proposed)

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

**Test that fails without it.** Create and destroy cycles of a mode on a hidden host: the ownership table returns
to its baseline after each cycle and after teardown, for the same mode, for two modes alternating, for a failed
release (injected), and for a display transfer (the source device's table is zero after the target presents).
*Negative control:* skip the deferred release (free a resource a frame in flight still uses) and run under
validation layers: they report it. The ownership table has a second negative control: delete the registration of one
resource kind; the baseline test fails.

##### Admission and dormancy (proposed)

- **Admission is lazy and edge-driven.** A window gets a device, a frame driver and layer targets when something
  needs them; a mode renderer exists only after its first activation; the backdrop pyramid exists only while the
  demand count is above zero (D7 point 2); the job thread exists once per device and is parked (D9 point 1).
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
job-thread wake-ups, ownership table unchanged (it is the per-frame cost test of the performance contract applied to
the core). *Negative control:* a mode that requests a repaint at rest fails the zero-pass count. A mode switch
releases the outgoing mode exactly once (a counter on `release`).

##### Device loss (proposed)

Today nothing handles it (above). QRhi reports it (the end-of-frame result is `FrameOpDeviceLost`; `QRhi::isDeviceLost()`
answers afterwards; the research file, addendum B, records it as Qt's), and Qt Quick then invalidates and
re-initialises the scene graph.

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
5. **Bounded.** A window that loses its device twice within a bounded count of frames is treated as a backend
   failure, not retried: the Visualizer on that window is parked (fade out), the failure is logged and remembered
   by D6 point 5's state file so the next start uses OpenGL; there is never a teardown from Vulkan to OpenGL in a
   running process (D6 point 5).
6. **The OpenGL fallback** does the same on a reset status from the context (`GL_GUILTY_CONTEXT_RESET` and the
   other reset codes, where the context was created with robustness; else Qt's own context-lost handling).

**Test that fails without it.** A harness-only hook marks the device lost at a chosen point (mid-frame, mid-job,
during a display transfer, during warm-up): no crash, the ownership table is empty afterwards, validation layers
are clean, a rebuilt frame is presented and equals the pre-loss frame (a fixed packet; single-sampled), the mode is
revealed by fade, and the second loss within the bound parks the Visualizer. *Negative control:* a core that keeps
recording after the lost mark (the pre-contract behaviour) trips the validation layers or the "record after loss"
assertion. The hook is compiled into the harness only.

##### What a mode's native renderer may not do (proposed)

A mode renderer is a pure function of its inputs: the decoded frame (from the packet), the resolved parameters the
packet carries, the targets and extents the frame driver gives it, and the core's matrices. Each rule is enforced
where it can be enforced mechanically, and each states what today's Python renderers do.

| May not | Why | Enforced by | Today |
|---|---|---|---|
| Read a clock (any `now`) | time is a logical input; D1's packets carry it; the same packet draws the same pixels | the mode API offers no clock; a mode translation unit that includes `<chrono>`/the platform timer fails a CI include check | holds already for modes (above); the host and item keep the only clocks |
| Compute or own a camera | one camera owner (N0.4); the core receives finished matrices and rays | the mode API has no projection builder; matrices arrive as plain data | `core/settings/framed_camera.py` is the owner; `perspective_matrix` at `:286-289` |
| Allocate per frame (heap, GPU buffers, pipelines, descriptor sets, textures) | no allocation per frame; warm-up units create things | debug build: a counting allocator and the ownership table; both must read zero growth over a steady frame; `prepare_step` is the only creating entry | not enforced; `StreamRing` slots and the drift solver's ring (`:441-449`) are the allocation edges |
| Set render state (blend, depth, cull, front face, viewport, scissor, stencil) | state belongs to pipelines; the pass graph declares it; QRhi has no state setters | the mode API has no such call: it declares passes and pipelines as data | 97 call sites in six implementation files (above); the host sets baseline state (`render_host.py:229-241`) |
| Name Qt Quick (`QQuickWindow`, `QSG*`, Quick's render target, the item matrix) | D5.1: only the host adapter touches Qt | a CI include check: no `QtQuick`/`qsg` header in a mode or primitive translation unit | the Python renderer's frame carries `matrix_values` and a Quick-owned VAO (`render_host.py:206-213`) |
| Hold or call Python (a thread state, a callback, an attribute lookup) | D5.4 | the P1 probe: calls made with a Python thread state, zero, rerun at every port | n/a; today's renderers are Python |
| Call the graphics API directly (GL or Vulkan) except through a D5.3 service | the service list is closed | include check on `<vulkan/…>` and GL headers outside the service sources | the six files above call GL directly |
| Read back from the GPU, wait on a fence, or block the render thread | a frame is never held; D9 publishes by latch | the mode API offers no readback or wait; harness-only readbacks live in tools | some readbacks exist in tools only; the product's drift path reads nothing back |
| Create threads, do file, network or environment access, or read settings | modes are pure; settings arrive resolved in the packet; no environment flags | include check; the mode API takes no path or handle | n/a |
| Write outside its own targets (the card, other surfaces, Quick's target) | the composite owns the card edge (D5.2) | the mode has no handle to any target but its own | the clip host and fence exist to protect this (`clip_host.py`, per the research file, N0.2 item 3) |
| Keep state across activations that the ownership table cannot see | a mode must release to zero | the table baseline test (above) | accounted by `has_resources` per renderer |
| Build or compile a pipeline while a visible frame is recording | no hitch | a trace assertion: no pipeline creation inside a `render` call | `prepare_step` exists; not enforced |

**Test that fails without it.** For each row a compile-or-run check with a negative control: (a) a mode snippet that
includes the clock header, a Quick header, or a graphics API header fails the include check (the harness carries
three must-fail snippets); (b) a mode that allocates inside `render` trips the debug counting allocator; (c) a mode
that tries to set blend state does not compile because the API has no such function; (d) the P1 probe on a mode with
a Python callback reports a Python thread state.

##### Questions for the lead (N0.5)

1. The drift solver's GPU-only per-mote state restarts after device loss (a visible reset of snow and specks,
   hidden by the mode's reveal fade). Is that acceptable, or must it be reconstructed from the worker's log? (The
   log keeps only `STEP_HISTORY` = 128 steps, `extruded_bubble_drift_log.py:37`, so a full rebuild is not possible
   from the log alone.)
2. The bound in "device loss, rule 5" (how many losses, in how many frames) is a number to choose.
3. Is a per-window GPU-memory budget part of admission (refuse or degrade a surface that would exceed it), or is
   accounting (the table) enough, as today? The draft proposes accounting only.
4. Pipelines are device-scoped and survive a mode release (rule 5). The alternative, releasing a mode's private
   pipelines with it, saves a little memory and costs a warm-up on every return to the mode.

## From D5.6 (N0.2): the full dependency table, the rows' proofs, the corrections and the questions

##### D5.6 The dependency table: what OpenGL gives that QRhi does not, and the route for each (N0.2)

*Decided by the lead, 12 Nov 2026 (answers in "Lead decisions on the N0 drafts" below); drafted as:* *Proposed (draft for the lead), 12 Nov 2026. Nothing here is decided; it applies D5.2 (the frame driver records
before Qt Quick's pass, the composite is a texture node, the clip is its coverage term) and D5.3 (the closed list of
six services, five since the indirect-draw service was retired on 12 Nov, each admitted by a measurement and shipping a raw Vulkan and a raw OpenGL form) to the eighteen
dependencies of the research file's table A.2 (`native_core_qrhi_gaps_and_conventions.md`). Every "today"
citation was re-read at commit `bdf9b246`; where source had moved, the research's citation is corrected in
"Where source differed" below. The QRhi names are the Qt 6.11.2 header (`rhi/qrhi.h`, line numbers given) and the
pages of doc.qt.io/qt-6 (`qrhi.html`, `qrhicommandbuffer.html`, `qrhitexturerendertargetdescription.html`; the
online pages track Qt 6.12, so a feature the page lists is used here only if the 6.11.2 header has it).*

**How to read the table.** "Service" names the D5.3 service that applies, or "none". "Chosen route" is what the
native core does; where a service is named it is built only when its D5.3 measurement admits it, and the chosen
route until then is the QRhi default. Every proof uses the P1 harness in a hidden host on OpenGL and Vulkan (D8's
gates), and every proof names its negative control, a change that must make it fail.

| # | Dependency | Today (file:line) | QRhi route | Service | Chosen route | Proof and negative control |
|---|---|---|---|---|---|---|
| 1 | Offscreen passes and compute inside the node's `render()` | scopes: `scene3d/target.py:1177-1188` (restores Quick's FBOs, viewport, scissor), `visualizer/implementations/sphere_voxel.py:961`, `shockwave_grid.py:350`, `extruded_bubble.py:581`, `oscilloscope.py:165`, `extruded_spectrum.py:252`, `scene3d/waveform.py:381`, and 13 transition files (e.g. `transitions/implementations/blinds.py:204`); compute in the same call: `scene3d/compute.py:23-32`, `extruded_bubble_drift_solver.py:412-413,604-606`, `scene3d/fog_volume.py:162-171` | `beginPass` on the core's own `QRhiTextureRenderTarget`, `beginComputePass`/`dispatch` (`qrhi.h:1754-1757`); a pass cannot open inside Quick's pass | none | D5.2 as decided: the frame driver records every offscreen and compute pass in dependency order on `beforeRendering`; the composite is one texture node. No `prepare()`/`render()` split is needed any more (the research's two-phase contract is replaced by D5.2) | A pass-graph scene (offscreen pass, compute pass, composite) renders pixel-identical on both backends and Quick's own content around it is unchanged. Control: record the composite before the offscreen pass: the frame shows the previous frame's content or the clear colour, and the comparison fails |
| 2 | GPU timer queries | only `scene3d/ribbon.py:281,396-408` (`GL_TIME_ELAPSED`, reached only when a lab passes `timing_query`); no other `glBeginQuery`, `glQueryCounter` or `glGenQueries` in `rendering/` | `QRhi::Timestamps` (`qrhi.h:1894`), `QRhiCommandBuffer::lastCompletedGpuTime()` (`:1763`): whole frame only, 2 to 3 frames late, needs `EnableTimestamps` (`:1878`); Quick's own QRhi takes it through `QQuickGraphicsConfiguration::setTimestamps` | GPU timer (per pass) | Whole-frame time from `setTimestamps(true)`, opt-in. Per-pass time from the service: Vulkan `vkCmdWriteTimestamp` and OpenGL `GL_TIME_ELAPSED`, built with the substrate (D8 plus 2), off by default with no query objects; production telemetry stays absent | Per-pass figures agree with the offline tool on one scene, and the Vulkan and OpenGL forms agree with each other within a stated tolerance. Control: with the option off a counter of live query objects reads zero and the trace has no extra cost; a build that creates the pool anyway fails that counter |
| 3 | GL state restoration against Qt's scene graph (the protected clip and fence work) | `visualizer/clip_host.py:1-9` (the fallback's contract), `:373-432` (INCR/EQUAL/DECR stencil), `:499` (scissor); `visualizer/gl_state.py:36-85`; `visualizer/node.py:173-187` (flags and dirtied states); `render/background_node.py:232-243`; `render/surface_backdrop.py:419-423` | no inherited state exists; pipeline state plus `setStencilRef`/`setScissor` need `UsesStencilRef`/`UsesScissor` on the pipeline (`qrhi.h:1313,1736`) | none | Not written. D5.2: nothing reaches the window but a texture node, so Qt's own scissor, stencil and clip apply to it and the clip is the coverage term of the composite material. The fence, the 17-value capture and the DECR redraw are deleted with the Python renderer; the protected commits' behaviour is the oracle, not code carried over | The existing clip and render-node pixel oracles pass unchanged (the protected optimisations are never retuned to satisfy them), plus plan 1C.4's own test: a scene whose content overflows the card writes no pixel outside the card or under the border's anti-aliased edge. Control: switch the coverage term off and the overflow pixels appear |
| 4 | Direct state access and immutable storage | required set `bootstrap.py:30-55`; e.g. `scene3d/target.py:1190-1205` (plain and multisample textures), `:1223-1229` (renderbuffer), `scene3d/stream.py:171-187` | `QRhiBuffer`, `QRhiTexture`, `QRhiRenderBuffer` with usage flags declared at `create()` (`StorageBuffer` `qrhi.h:868`, `UsedWithGenerateMips`/`UsedWithLoadStore` `:914-915`); sampler state moves from `glTextureParameteri` (`target.py:1194-1195`) into a `QRhiSampler` | none | QRhi; the `direct_state_access` requirement goes with the OpenGL validator. Usage flags are part of each resource's declaration in its pass graph | The N0.5 ownership-table baseline test (create and destroy cycles return the table to baseline). Control: create a texture without `UsedWithLoadStore` and bind it as a storage image: validation layers report it |
| 5 | Program binary cache | `render/gl_resources.py:30-44` (compile), `:47-62` (driver identity), `:107-128` (`_link`: load on a hit, `glGetProgramBinary` after a cold link); store `render/gl_program_cache.py:70,103,129` (R-180: a cold basin link was about 6 s) | `QRhi::PipelineCacheDataLoadSave` (`qrhi.h:1916`), `pipelineCacheData()`/`setPipelineCacheData()` (`:2081-2082`); Quick's own `setAutomaticPipelineCache` and save/load file options on `QQuickGraphicsConfiguration`; per pipeline, in the backend's blob, and SPIR-V to native compilation still happens on first use | none | Quick's pipeline cache for pipelines created on Quick's QRhi (the core's are, even on the module's device, D6 point 1); shaders baked with `qsb` for every backend at build so no runtime HLSL parse; pipelines created in warm-up units only (D5 rule 5). Own `VkPipelineCache` only for the raw pipelines of an admitted service | Cold against warm start over the full pipeline set: pipeline creation time and first-reveal time, recorded. Control: change the stored driver identity or corrupt the file: it is ignored, the cold path runs, output is identical |
| 6 | Per-draw image and sampler bindings, storage-image units | `scene3d/resources.py:110-133` (`glBindTextures` `:124`, `glProgramUniform1i` `:132`); `scene3d/compute.py:36-57` (`bound_image` saves and restores the unit) | `QRhiShaderResourceBindings` per resource set, `sampledTexture`, `imageLoad/imageStore/imageLoadStore`, bound with `setShaderResources` and dynamic offsets (`qrhi.h:1727`); texture and sampler separate | none | One srb per (pipeline layout, resource set), built in warm-up and per ring slot, never per frame; per-draw variation by dynamic offsets. `bound_image`'s save and restore disappear (no unit state exists) | A steady-state scene over many frames: a counter of srb creations reads zero after warm-up. Control: create the srb inside the frame and the counter reads one per frame |
| 7 | Multisample resolve control | multisample textures `scene3d/target.py:1198-1211` (clamped by `GL_MAX_SAMPLES` and `GL_MAX_COLOR_TEXTURE_SAMPLES`); composite averages by `texelFetch` on `sampler2DMS` (`:88`, `:312-346`), per-sample OIT composite with `gl_SampleID` (`:189-196`), shaft source `scene3d/shafts.py:52`; no resolve blit (`:9-17`, about 0.5 ms measured at 2560 x 1440 on the development GPU); a shader resolve pass already feeds bloom and motion blur (`:1131-1175`) | `setResolveTexture` (`qrhi.h:596`), `setDepthResolveTexture` (`:647`, needs `ResolveDepthStencil` `:1933`), `MultisampleTexture` (`:1891`), `SampleVariables` (`:1938`); doc: with a resolve texture the multisample texture "must not be used afterwards with shaders for sampling" | per-sample multisample reads, only if resolve-first fails a mode's look or cost | Resolve-first: a QRhi resolve into a single-sample texture, then the composite samples that; the existing `scene_resolve` shader pass becomes the resolve attachment. Parity is single-sampled (D8.1); multisampled output is judged repeat-relative. The service is not built unless an A/B shows a look or cost loss | A/B at 2560 x 1440 and 3840 x 2160: resolve-first against the shader average, GPU time median and p90, and the pixel difference on edge-heavy scenes; single-sample equality against the Python renderer. Control: force 4 samples and compare exactly: it must fail, which is why multisampled output is repeat-relative |
| 8 | Stencil for the card clip | same code as row 3: `clip_host.py:373-432`, overflow bypass `visualizer/node.py:291-311` | stencil exists but belongs to Quick's pass; a separate offscreen scene cannot test it | none | As row 3: the coverage term in the composite, the same rounded-rectangle distance as `clip_host.py:44-60`. Open edge case in Questions 1 and 2 | As row 3, with the anti-aliased edge compared against the stencil's hard edge (`clip_host.py:56` discards) |
| 9 | Persistent mapped buffers (`StreamRing`) | `scene3d/stream.py:32` (map flags), `:61-66` (defaults: 4 slots, 16,384 bytes per slot, 4,096 held), `:161-187` (fence wait, map); 12 users (`sphere_voxel.py:711`, `shockwave_grid.py:98`, `oscilloscope.py:97`, `extruded_spectrum.py:87`, `extruded_bubble_drift_solver.py:448`, `scene3d/uniforms.py:38`, `scene3d/ribbon.py:245,516`, `scene3d/ribbon_bursts.py:47`, `disintegrate.py:52`, `exploding_tiles.py:56`, `volumetric_dissolve.py:72`) | `Dynamic` buffers (per frame in flight) and `updateDynamicBuffer` (`qrhi.h:1789`) in the frame's resource-update batch; `NonDynamicUniformBuffers` (`:1898`) otherwise uniform buffers must be dynamic; no mapped pointer | stream ring (persistent mapped) | QRhi dynamic buffers by default, one per frame in flight, dynamic offsets for slices (alignment `ubufAlignment()` `:2055`). The service is built only if the measurement below shows 0.05 ms or more (D5.3) | Per product ring, at its real size, QRhi write against the raw persistent-mapped form: render-thread CPU and GPU time, median and p90, system conditions recorded. Control: a synthetic extra copy of known cost is added to one side and the harness must report it; a write past the held bytes still fails loudly (`stream.py:16`) |
| 10 | Reading what Quick already drew (the backdrop blit) | `render/surface_backdrop.py:236-283` (blit `:262`; multisample refusal `:243-245`), `:428-452`, eight dirtied states `:419-423` | no read of the current target inside its pass | none | D7 as decided: the pyramid is built from the core's own background layer texture with QRhi fragment passes, only in the frame the layer changed and only while demand is above zero; nothing reads the window. The research's "Quick layer or `ShaderEffectSource`" route is superseded by D7 | D7's gate: the pyramid equals the blit pyramid on the same frames on OpenGL, at most 0.3 ms at 2560 x 1440 and 0.6 ms at 4K. Control: skip the rebuild on a layer change and the sampled value is stale; at rest zero passes recorded |
| 11 | Point sprites (`gl_PointSize`, `gl_PointCoord`, `GL_PROGRAM_POINT_SIZE`) | Bubble ambient `visualizer/implementations/bubble_ambient_gl.py:73-76,101,114,352-389` (size clamped 1 to 128); Neon Lake `gl_programs/neon_lake_basin_program.py:515,703`, `shockwave_grid.py:542-585`; Waveform sparks `gl_programs/ribbon.py:436,636`, `scene3d/ribbon.py:441-455,491,521`; cull trick `gl_programs/ribbon.py:401` | `Points` topology and `VertexShaderPointSize` (`qrhi.h:1905`), not portable (D3D has no point size); `gl_PointCoord` has no portable form through `qsb` | none | Instanced screen-space quads (the Oscilloscope already draws instanced quads): per-instance pixel size, corners from the vertex index, the sprite coordinate as a varying; the cull trick becomes a zero-size or degenerate quad | Per mode, pixel parity against the Python point renderer at single sample on OpenGL; a sprite-size sweep scene (1 to 128 px, sub-pixel centres, the half-texel rule noted at `bubble_ambient_gl.py:114`). Control: move the sprite centre by half a pixel and the sweep fails |
| 12 | Compute dispatch, memory barriers, storage images | `scene3d/compute.py:23-57` (`dispatch` with a named barrier, `bound_image`); users `scene3d/edge_field.py:330-359`, `fog_volume.py:162-171`, `floor_give.py:75-82`, `motion.py:199`, `population.py:236-240`, `propagation_field.py:191-215`, `waveform_field.py:52-53`; drift solver `extruded_bubble_drift_solver.py:412-413,572,604-606` | `QRhi::Compute`, `beginComputePass`, `setComputePipeline`, `dispatch` (`qrhi.h:1754-1757`); barriers inserted by QRhi from the srb access types (`bufferLoad/bufferStore/imageLoad/...`), compute only inside a compute pass | async GPU jobs (D9) only where a job is admitted; in-frame compute has none | QRhi compute passes in the frame driver; the `barriers` argument is replaced by correct srb access types; formats from row 13; `double` is already gone (D4) and loose uniforms go in N1.2 | Per compute program, native output equals the Python/OpenGL output for fixed inputs (hash, or a stated tolerance) on both backends. Control: bind one resource with the wrong access type: validation layers (synchronisation validation) report it or the output goes stale |
| 13 | Texture formats QRhi 6.11.2 lacks (`RG16F`, `RG32F`, `R11G11B10F`) | `RG16F`: `scene3d/motion.py:199,251`, `target.py:1168,1215`, `defocus.py:250`, `edge_field.py:273,359`, `waveform.py:98`; `RG32F`: `edge_field.py:273,344-357`, `heightfield.py:59`; `R11F_G11F_B10F`: `bubble_ambient_gl.py:284,301` | format list ends at `RGBA16F`/`RGBA32F`/`R16F`/`R32F`/`RGB10A2` (`qrhi.h:926-958`) | formats, only where widening measurably costs | N1.7 widens first: `RG16F` to `RGBA16F`, `RG32F` to `RGBA32F`, `R11G11B10F` to `RGBA16F` (not `RGB10A2`: it is unorm, no headroom). Cost: 2 times the bytes per texel, e.g. 66 MB to 133 MB for one `RG32F` target at 3840 x 2160 if it is allocated at that size. The service (raw `VK_FORMAT_R16G16_SFLOAT` and friends, wrapped with `createFrom`, `qrhi.h:1032`) only for a target whose measured memory or time hurts | Outputs of the edge field, defocus, motion tiles and the Bubble light attachment equal the Python results at the stated tolerance; one memory and bandwidth line per widened target in the harness. Control: initialise the unused channels to a non-zero value: any consumer that reads them changes its output and the comparison fails |
| 14 | Indirect draws | `bootstrap.py:66` requires `glMultiDrawArraysIndirect`: nothing calls it (below); the only indirect draw is `scene3d/population.py:258-260` (`glDrawArraysIndirect`, buffer bound `:187-206`) after the count and scatter dispatches (`:236-240`), used by `CompactedPopulation` in Disintegrate (`disintegrate.py:51`) and Volumetric Dissolve (`volumetric_dissolve.py:71`) | none in 6.11.2: the feature list ends at `DepthClamp` (`qrhi.h:1940`); `DrawIndirect`, `DrawIndirectMulti`, `ShaderDrawParameters` come with 6.12 | indirect and count draws | Draw the population's maximum instance count and cull the dead tail in the vertex shader from the compacted count (`gl_Position` outside the clip volume). The service (`vkCmdDrawIndirect`, `glDrawArraysIndirect` in a QRhi-declared pass) only if the population harness at 1,000,000 sprites shows the dead tail costing more than the 0.05 ms rule allows; gone if D11 moves to a Qt that has it. The `glMultiDrawArraysIndirect` requirement is simply dropped | Both routes draw the same image for the same compacted count (hash). Control: remove the vertex-shader cull and the dead tail appears in the image |
| 15 | Sampled depth textures and depth-dependent reads | `scene3d/target.py:40-44` (contract), `:306-322` (nearest depth per pixel by `texelFetch` over samples), `:575` (`background()`), `:1221,1243` (`DEPTH_COMPONENT32F`); otherwise a 24-bit depth renderbuffer (`:1223-1229`) | `D32F` texture, depth as a render-target attachment, `setDepthResolveTexture` with `ResolveDepthStencil` (`qrhi.h:647,1933`); a texture cannot be an attachment and sampled in one pass | per-sample multisample reads (see below) | QRhi; `background()` splits the scene pass, the second pass loads the first's colour and depth (no `DoNotStoreDepthStencilContents`), the capture is a resolve into plain textures. Consequence to check: the product takes the nearest depth over the samples (`target.py:306-322`) and a depth resolve returns one sample's value, which one depends on the backend (*unverified*); at single sample (the gate) there is no difference | Extruded Bubble's refraction and fade scene: single-sample equality against the Python renderer, then the multisampled difference measured. Control: swap the nearest-depth rule for a first-sample read and the comparison fails on edges |
| 16 | Pass structure, no state leakage | `shockwave_grid.py:473-581` (depth function changes through the frame), `sphere_voxel.py:966-975,989-1027,1070-1077,1122` (mid-scope depth clear, front face from the matrix sign), `scene3d/target.py:547-571,1177-1181` (per-attachment `glColorMaski`) | every pipeline carries blend per target (`PerRenderTargetBlending` `qrhi.h:1937`), depth, cull, front face, stencil and colour write mask; load and clear are per pass; only viewport, scissor and stencil ref are dynamic | none | Passes declared as data (D5's "may not" table: no state setters in a mode); each state combination is a pre-built pipeline created in warm-up; a mid-scope depth clear becomes a new pass with a clear load op or a clear draw; per-attachment write protection becomes a colour write mask in the pipeline's per-target blend; the front face follows N0.3 | The N0.5 negative controls (a mode that sets state does not compile). Plus a harness scene per state combination a mode uses, equal to OpenGL. Control: leave out the write mask of the velocity target and its content changes |
| 17 | Image and texture upload paths, wrapped Quick textures | `render/image_textures.py:246-270` (`glTexParameteri`, `glTexImage2D`), `:284,309` (delete); `render/native_texture_bridge.py:24-123` (adopts a GL name, refuses when the API is not OpenGL `:111-114`) | `QRhiResourceUpdateBatch::uploadTexture`, `QRhiTexture::createFrom` (`qrhi.h:1032`), `QQuickWindow::createTextureFromRhiTexture` (D5.2) | async GPU jobs (D9) for the upload, mips and derived maps | The native presenter owns its images as QRhi textures, uploaded in the frame driver's batch; D9's job form is the async variant with the in-frame form always present. The wrapped-texture bridge is a GL-only seam and is retired with the presenter | Image-change harness: p99 frame time and late frames with a Visualizer running (D9's proof), and upload pixel equality against the current path. Control: use the bridge in a Vulkan window: it refuses (`native_texture_bridge.py:111-114`), which is why it cannot survive the flip |
| 18 | Needs no replacement (checked), and the probe's six-face draw | instancing, `texelFetch`, mip generation, cube and 3D textures, the 1D rim texture, `BaseInstance`; probe `scene3d/probe.py:54-66` (one geometry-shader draw, `gl_Layer`), face tables `:117-134` | `GeometryShader` is experimental (`qrhi.h:1923`); `MultiView` (`:1931`) | none | Six draws per level, one per face view; `MultiView` only if a measurement asks | Per-face equality against the Python probe and the existing face-orientation tests. Control: swap two faces and the comparison fails |

**Rows with no QRhi route and no service that fits, and the smallest option.**
- Row 13, the three missing formats: widen in N1.7 (above). It is the smallest option and it never needs a service
  for parity.
- Row 7 and row 15, per-sample reads and the nearest-depth rule: the resolve-first rule from N1.8 for parity (single
  sample); the nearest-depth rule has no QRhi equivalent, so a multisampled `background()` is a look question, not
  a blocker, decided by the A/B in row 7.
- Row 14, indirect draws: the dead-tail cull is a restructured pass; nothing new is added to D5.3's list.
  *Superseded 12 Nov 2026 by the move to Qt 6.12:* the population's `glDrawArraysIndirect`
  (`scene3d/population.py`) ports 1:1 to `QRhiCommandBuffer::drawIndirect`; the dead-tail cull stays only as the
  path for a backend without `QRhi::DrawIndirect`.
- Row 11, point sprites: a restructured draw (quads); no feature is missing.
No row needs a service outside D5.3's six.

**`glMultiDrawArraysIndirect`, box 2.** See the sub-line under N0.2 in `Current_Plan.md`: nothing calls it and nothing
but the startup validator and one test names it.

**Where source differed from the research (corrections to its citations; none changes a conclusion).**
- Waveform's scope is `scene3d/waveform.py:381`; the research's `V/waveform_ribbon.py:381` is not where it is.
- The drift solver's compute and barrier sites are `extruded_bubble_drift_solver.py:412-413,572,604-606`, not `:383,417-430`.
- `StreamRing` is `stream.py:161-187` for wait and map (research: `:173-179`); the `bound` and `rebind` entry points are `:96-135`.
- The node flags and dirtied states are `visualizer/node.py:173-187` (research: `:163-178`); the clip host's stencil
  operations are `clip_host.py:373-432` (research: `:347-420`).
- The research describes `ribbon.py` timer queries at `:397,408`; they are `:396-408`, still reachable only through
  `timing_query`.
- The research says there is no resolve at all; source already has a shader resolve pass for bloom and motion blur
  (`target.py:1131-1175`) and a second `sampler2DMS` consumer the research did not list (`scene3d/shafts.py:52`).
- Item 10 of the research proposes Quick's `ShaderEffectSource` for the backdrop; D7 supersedes it (the core's own
  background layer).
- Item 1 of the research proposes a `prepare()`/`render()` split in a render node; D5.2 supersedes it (frame driver
  on `beforeRendering`, composite as a texture node).

**Questions for the lead.**
1. Overflow modes (Sphere, Extruded Spectrum): today they bypass the local clip and the stencil clips them to the
   widget's painted footprint (`visualizer/node.py:291-311`, `:175-180`). D5.2 renders "at the item's device-pixel
   rectangle". Does the core's target for an overflow mode cover the overflow footprint (a larger target, so more
   memory at rest), or is overflow cut at the item? Rows 3 and 8 depend on it.
2. The clip's edge: `clip_host.py:56` discards (a hard edge) and the border is drawn over it; the coverage term is
   anti-aliased. Is a one-pixel difference on the inner edge acceptable parity, or must the coverage reproduce the
   hard edge exactly at the gate?
3. D5.3's first service row says a service is admitted by measurement; row 15's nearest-depth rule is a per-sample
   behaviour the draft routes through "resolve-first, then a look question". Should a multisampled `background()`
   stay a Parity+ item (decided by the A/B) or be named a parity gate that admits the per-sample service
   unconditionally for Extruded Bubble?
4. D5.2 says one `beforeRendering` driver records everything. A per-pass GPU timer (row 2) inside a QRhi graphics
   pass cannot write a timestamp from the secondary command buffer the external block gives (research addendum A.1,
   unverified); the draft assumes the timer wraps whole passes from a compute-pass external block. Accept this as
   the service's form, or time per frame segment only?

## From N0.3: the draft, the inventory, the questions, run 1's figures and the findings' evidence

#### N0.3. Conventions, written once and tested per backend

*Decided by the lead, 12 Nov 2026 (answers in "Lead decisions on the N0 drafts" below); drafted as:* *Proposed (draft for the lead), 12 Nov 2026. Nothing here is decided. Inputs: the lead's research file (outside the
repository, `D:\Temp\Scratch\SRPSS\research\20261112\native_core_qrhi_gaps_and_conventions.md`, section N0.3, read
only; its file:line citations were taken at `a5ee7189`, and the ones restated below were re-read at `7ac980d7`
unless marked "research"), the Qt 6.11.2 QRhi documentation (doc.qt.io/qt-6/qrhi.html: `clipSpaceCorrMatrix()` "can
be used to allow applications keep using OpenGL-targeted vertex data and perspective projection matrices ...
regardless of the active QRhi backend", vertex data "Y up" and viewports "with depth range 0 - 1"; the example
flips a readback with `if (rhi->isYUpInFramebuffer())`), and the sentences the research file quotes for
`isYUpInNDC()` (false in practice for Vulkan only), `isYUpInFramebuffer()` (true in practice for OpenGL only) and
`isClipDepthZeroToOne()` (false in practice for OpenGL only). Items marked *unverified* are proved by the harness
scenes below before anything is built on them. The page was only partly readable in the fetch used for this draft
(its first 100,000 of 151,680 characters), so the three `is*` sentences rest on the research file.*

##### The conventions, per backend

| Convention | OpenGL | Vulkan | D3D11 / D3D12 | Metal |
|---|---|---|---|---|
| Clip-space Y (`isYUpInNDC()`) | up | **down** | up (QRhi's rule: false for Vulkan only) | up |
| Framebuffer / render-target origin (`isYUpInFramebuffer()`) | bottom-left (true) | top-left | top-left | top-left |
| Clip depth range (`isClipDepthZeroToOne()`) | -1..1 | 0..1 | 0..1 | 0..1 |
| `gl_FragCoord` origin in the shader | bottom-left | top-left (SPIR-V `FragCoord`) | top-left | top-left |
| `QRhiCommandBuffer` viewport and scissor origin | bottom-left on every backend (QRhi's rule; research, QRhiCommandBuffer page) | same | same | same |
| Texture row order on upload | first uploaded row is texel row 0; QRhi's GL backend hides the API's own bottom-up order (*unverified here*) | same | same | same |
| Front-face winding | QRhi defines CCW-front on the pre-correction, Y-up output for every backend, and the Vulkan backend compensates for the Y flip (research, *unverified*; one-triangle test below) | | | |
| Uniform and storage layout | std140 and std430, identical across backends after SPIRV-Cross; use reflected offsets | | | |
| sRGB | `QRhiTexture::sRGB` flag, not a format; non-sRGB targets in the product | same | same | same |
| HDR intermediates | RGBA16F/RGBA32F/R16F/R32F; `RGB10A2` is unorm; no RG16F, RG32F, R11G11B10F (N0.2 item 13) | same | same | same |

Metal is listed as QRhi reports it; it cannot be run on this project's machine (Windows only), so it is a Watchlist
entry and never a claim. D3D11 and D3D12 are run through QRhi's backends in the hidden harness where Qt provides
them (the P1 spike already creates a D3D pipeline, `Native_Core_P1_Spike.md:103-106`).

##### The rules (proposed)

1. **CPU matrices stay in OpenGL form, from one owner, and are corrected once, at upload.**
   `core/settings/framed_camera.py:286-289` (`perspective_matrix`) builds the OpenGL form (`(far + near) /
   (near - far)` and `2 far near / (near - far)`, NDC z in [-1, 1], the docstring of `view_matrices` at `:294` says
   "GL mat4 projection"); the substrate multiplies `clipSpaceCorrMatrix()` on the left exactly once, when the scene's
   uniform block is written, never in a shader and never twice. Matrices that arrive from Quick
   (`QSGRenderNode::projectionMatrix()`) are already corrected by Qt for Quick's own pass and are **not** corrected
   again (the P1 spike's use: `native/spike_p1/src/quick_item.cpp:40`, `quadfield.cpp:184-190`, per the research
   file); the composite uses Quick's matrices, the scenes the core renders itself use the corrected camera matrix.
   One flag in the matrix object records "corrected", and writing a corrected matrix through the correcting path
   fails an assertion.
2. **Offscreen targets the core owns have one defined origin: texel (0,0) is top-left, window Y points down, on every
   backend.** The include provides the translation from whatever the backend's `gl_FragCoord` is, so a texture
   written by one pass and sampled by the next never needs a per-pass flip. Item-pixel arithmetic that is Y-up today
   (`rendering/quick/scene3d/frame.py:19-34` keeps "the bottom-up convention the transition fragments were authored
   in": `vUv = vec2(aPosition.x, 1.0 - aPosition.y)`, `:31`) gets one flip at the substrate boundary.
3. **One include, `srpss_conventions.glsl`, is the only place a shader learns a backend convention.** It provides:
   - `ivec2 fragTexel()`: the fragment's pixel in the top-left, Y-down convention (flips `gl_FragCoord.y` against
     the target height when the backend's framebuffer is Y-up);
   - `vec2 fragUv(vec2 targetSize)`: `(fragTexel() + 0.5) / targetSize`;
   - `vec2 ndcToUv(vec2 ndc)` and `vec2 uvToNdc(vec2 uv)`: the clip-to-texture mapping for the backend's NDC Y
     direction (after rule 1 this is the same expression on every backend; the include exists so no shader writes
     `ndc * 0.5 + 0.5` by hand, the form at `rendering/gl_programs/waveform_ribbon.py:159` and
     `rendering/quick/qml/shaders/surface_material.vert:30` per the research);
   - `float viewDepthFromDepthTexture(float d)`: sampled depth is window depth in [0, 1] on every backend once
     rule 1 has run, so this is one function and the only place a reverse-Z or range change would ever go.
   The backend values arrive in a small std140 block (two or three floats and ints) at one reserved binding. It is
   written once per device at creation (the values never change for a device), so it adds no per-frame upload. (SPIR-V is
   shared by Vulkan, D3D and Metal after translation, so a compile-time branch per backend is not available; a
   uniform is.)
4. **Front face is one function of (the item matrix's handedness, `isYUpInNDC()`)**, evaluated when pipelines are
   created, giving two pre-built pipeline variants (CW and CCW) for every culling pass. Today
   `sphere_voxel.py:988-992` and `:1072-1076` choose `GL_CW` or `GL_CCW` each frame from the sign of
   `matrix_values[0] * matrix_values[5]` (Quick's item matrix is Y-down) and restore the state after
   (`:1025-1026`); modes that cull are few (the rest draw with culling off; research). `gl_FrontFacing` users
   (`rendering/gl_programs/ribbon.py:658`, the back-side normal) are covered by the third test scene.
5. **Uniform blocks are std140, storage blocks std430, and C++ packs from reflected offsets, never hand-computed
   ones.** Rules the packer and the shaders follow: `vec3` aligns to 16; arrays of scalars, `vec2` or `vec3` in a
   std140 block have a 16-byte stride (so padded float arrays become `vec4`-packed arrays); `mat3` is three `vec4`;
   structs round to 16; a following scalar may fill a preceding `vec3`'s padding; storage blocks keep natural
   array strides but `vec3` stays 16-aligned; dynamic uniform offsets are aligned to `QRhi::ubufAlignment()`.
   Today: 838 `glUniform*`/`glProgramUniform*` call sites with loose uniforms (research count), 33 block
   declarations in 13 files; N1.2 and N1.3 move every program to blocks (`Current_Plan.md`, N1). The Python packer
   `Scene3DBlockLayout` (`rendering/gl_programs/scene3d.py:1070`) is the oracle the C++ packer is first tested against.
6. **sRGB and HDR: keep the product's rule.** Targets are plain unorm or float and shaders do the math, so a backend
   change moves no pixel; the single sRGB asset (the floor albedo, `GL_SRGB8_ALPHA8`,
   `rendering/quick/scene3d/waveform.py:114`) uses the `sRGB` texture flag on every backend, and the harness checks
   the sampled value against the OpenGL decode. No `GL_FRAMEBUFFER_SRGB` is enabled anywhere in `rendering/` (grep:
   none). An HDR swapchain is not admitted (D8 plus 9).

**Amended by the lead, 12 Nov 2026, from run 1 (decisions F1 to F4 below; the rules above are kept as drafted):**
- Rule 1: for a target the core owns, the correction is `clipSpaceCorrMatrix()` times a Y flip where
  `isYUpInFramebuffer()` (F1). Quick's matrices for Quick's own pass stay as Qt gives them.
- Rule 2: holds by rule 1's flip, not by the include; the core's readbacks are never flipped (F1).
- Rule 3: the block (`x` the fragment Y flip, `y` the clip-NDC Y flip) is declared by every stage that includes the
  conventions and its values belong to the target, set by the host that owns it, not once per device (F1). The core
  writes `x` 0 for every target it owns and `y` = `isYUpInNDC() && !isYUpInFramebuffer()`; the Python OpenGL renderer
  keeps 0 and 0 for every target until it retires. `ndcToUv`/`uvToNdc` take the clip NDC of the pass's own (uploaded)
  matrices and negate Y from `y` under the native core (F2). New in the include: `srgbToLinear` (F4).
- Rule 4: the function is evaluated on the matrix after the upload correction (F3).
- Rule 6: the sRGB flag is not relied on anywhere; the floor albedo is plain RGBA8 decoded in its shader (F4).

##### What today assumes OpenGL conventions (inventory, `rendering/` and `core/settings/`, at `7ac980d7`)

- **`gl_FragCoord` as texel or uv: 51 occurrences in 14 files.** Texel addressing into offscreen targets:
  `rendering/quick/scene3d/target.py:112,130,142,180,193,228,235,272,279,289,304,317,334,343` (for example
  `ivec2 texel = ivec2(gl_FragCoord.xy) - uOrigin` at `:130,142,228,235,272,279`), `defocus.py:93,150-153`,
  `motion.py:115`, `trails.py:40`, `shafts.py:56`, `rendering/gl_programs/fog_volume.py:160,283`,
  `reflection.py:84`. Uv from fragment position over a target size:
  `rendering/gl_programs/extruded_bubble_program.py:194,196,584-587,896,1010,1058,1940`, `waveform_ribbon.py:159,189,
  204`, `extruded_spectrum_program.py:415`, `rendering/quick/visualizer/implementations/sphere_voxel.py:651`,
  `defocus.py:106,119`. NDC from fragment position: `extruded_bubble_program.py:980,1164`
  (`gl_FragCoord.xy / uFrameSize * 2.0 - 1.0 - uLensShift`). The Quick material shaders use it for a noise seed only
  (`surface_material.frag:178`), which no convention can change visibly.
- **Front-face and culling:** `sphere_voxel.py:988-992,1025-1026,1072-1076`; `ribbon.py:658` (`gl_FrontFacing`).
- **The perspective matrix and depth:** `core/settings/framed_camera.py:286-289` (OpenGL form, rule 1);
  `glClearDepth(1.0)` with the OpenGL depth test at `scene3d/target.py:845,885`, `scene3d/resources.py:324`,
  `transitions/render_host.py:139`, `transitions/implementations/block_spins.py:172`; depth read back as a sampled
  texture in `scene3d/target.py:306` (the nearest depth, `texelFetch(uDepth).r`; research).
- **Texture and readback origin:** `rendering/quick/offscreen_target.py:179` and
  `rendering/quick/render/background_node.py:686` (`glReadPixels`, bottom-up rows); `frame.py:31` above.
- **sRGB:** `scene3d/waveform.py:114` only.
- **Not re-read for this draft (research file, `a5ee7189`):** the transition fragments' own flips
  (`gl_programs/blinds_program.py:60-61`, `beam_program.py:136`, `blockspin_program.py:281-290`,
  `capillary_bloom_program.py:92`, `blinds_slats_program.py:141`), `visualizer` depth-func flips in
  `shockwave_grid.py:473-581`, and the Quick `.qsb` shaders baked `--glsl 460` only (`surface_material.vert:2`).

N1.4 applies the include to every existing shader in the OpenGL renderer, where each stays pixel-identical on
OpenGL (the include's OpenGL values make it an identity there) before any C++ exists; the include is therefore
proved against the Python path first.

##### The three test scenes (hidden host, run on OpenGL, Vulkan, D3D11 and D3D12 where available; Metal Watchlist)

Each scene renders a fixed, single-sampled frame to an offscreen target, reads it back (flipped by
`isYUpInFramebuffer()` only in the harness's own readback), and is compared with **both** the analytical expected
image and the OpenGL result. They are the proof for rules 1 to 6; they live in the P1 harness (after N0.9).

1. **Checkerboard with a gradient.** A target of non-square size (so a width/height mix-up shows) with a checker
   whose four corner cells have four distinct colours, a horizontal red gradient and a vertical green gradient, drawn
   by a first pass and then sampled by a second pass that writes its own `fragUv()` and `fragTexel()` as colour.
   Checks: texel (0,0) is top-left on every backend; `fragUv`, `fragTexel` and `ndcToUv` agree with the pass
   that wrote the texture; the upload row order; the harness readback flip; the sRGB strip (a small sRGB-flagged
   gradient texture) equals the OpenGL decode; a std140 block with a `vec3`, a `vec3` array, a `mat3` and a trailing
   scalar is packed from reflected offsets and its values read back through colour. *Negative controls:* drop
   the Y correction in the include (the corner colours swap on Vulkan); drop `clipSpaceCorrMatrix()` from rule 1
   (the image is upside down on Vulkan); pack the block with hand-computed offsets that ignore the `vec3` rule (the
   block test fails).
2. **A known-depth plane.** A plane facing the camera at a chosen view depth (and a second nearer one that
   overlaps it), rendered through the project's camera matrix (`framed_camera.perspective_matrix` with the corrected
   upload) into a `D32F` target, then sampled by a pass that writes `viewDepthFromDepthTexture()`. Checks: the stored
   value equals the analytical window depth (the same number on every backend, within a stated float tolerance); the
   nearer plane wins the depth test; clear value and `GL_LESS`-style compare agree; the near and far clip planes
   cull at the same depths. *Negative controls:* skip the depth part of the correction (the value is wrong on
   Vulkan, D3D and Metal); upload an uncorrected matrix.
3. **One culled triangle.** Two triangles, one counter-clockwise and one clockwise as authored in OpenGL form, drawn
   with back-face culling and the front face from rule 4, once with Quick's Y-down item matrix and once with an
   up-facing one; each triangle has a distinct colour, and a second pass colours by `gl_FrontFacing`. Checks: the
   same triangle is culled on every backend; the matrix-handedness switch of `sphere_voxel.py:988-992` gives the same
   image; `gl_FrontFacing` agrees. *Negative control:* fix the front face to CCW regardless of handedness (the
   wrong triangle is culled on Vulkan or with the Y-down matrix).

**Pass condition per scene:** the harness image equals the analytical image within its stated tolerance on each
available backend and the backends equal each other within the P1 spike's measured backend difference (0 to 3 of
255 on trivial content, D8 point 1). A new backend or a Qt upgrade (D11) reruns the three scenes first.

##### Questions for the lead (N0.3)

1. Rule 2 chooses **top-left, Y-down** for core-owned offscreen targets (the research file's choice), not OpenGL's
   bottom-up. The alternative keeps OpenGL's bottom-up and flips on Vulkan, D3D and Metal; it leaves the existing
   shaders untouched on OpenGL but makes every other backend the odd one. The draft prefers the former because
   Vulkan is to be the front face.
2. Reverse-Z (`D32F`, near at 1) is not proposed; it is a separate decision if depth precision at EB's near plane
   (N1, "the beads at the near plane") calls for it.
3. The conventions block is one binding reserved in every shader. Is a fixed binding index acceptable, or should it
   be allocated by the pass-graph builder?

##### As proved (N0.3 harness, `native/spike_p1`, run 1, 12 Nov 2026)

Harness 63f0e75e (`src/n03_scenes.*`, `shaders/n03_*` with the production include baked in, `python/run_n03.py`),
built on GitHub and run by the lead with the Khronos layer and `--require-validation`
(`.artifacts/evidence/native_core/n0_3/20261112_n03_scenes/`); the same module rerun with the corrected analysis
(`20261112_n03_scenes_reanalysed/`, no rebuild). One process, four backends: Vulkan on our N0.6 device, OpenGL 4.6,
D3D11, D3D12 (RTX 4090, NVIDIA 617.42). Validation clean: 10 errors, all Qt defect A by ID, 0 unexplained.

- **Scene 2, the known-depth plane: proved on all four.** Through `framed_camera.perspective_matrix` corrected at
  upload, `viewDepthFromDepthTexture` equals the analytical window depth within 1.6e-7 (tolerance 2e-6), the backends
  within 1.2e-7 of OpenGL; the nearer plane wins whichever is drawn first, LESS rejects an equal depth, the cleared
  depth reads 1.0 exactly, the near and far planes clip at the same depths. Negative controls fail where they change
  anything: the depth part skipped (Vulkan, D3D11, D3D12; it changes nothing on OpenGL), no correction (all four).
- **Scene 3, the culled triangle: proved on all four.** Rule 4 evaluated on the uploaded matrix keeps the authored-front
  triangle with Quick's Y-down matrix and an up-facing one, `gl_FrontFacing` agrees, the up-facing image mirrored back
  equals Quick's, and the C++ rule equals `front_face_clockwise` on the same matrix. Negative controls: the front face
  fixed counter-clockwise culls the wrong triangle (up-facing on Vulkan, D3D11, D3D12; Quick's on OpenGL); rule 4 fed
  the uncorrected matrix culls the wrong one on Vulkan and OpenGL (finding F3).
- **Scene 1, the checkerboard: proved on all four except two findings that waited for the lead (F2, F4; decided 12
  Nov, below; run 2 on the decided include and harness is owed, build round 2).** Texel (0,0)
  top-left in memory, the upload row order, `fragTexel`, `fragUv` and `fragPixel` against the writing pass, the std140
  probe from reflected offsets (equal to `Scene3DBlockLayout`'s offsets), the double correction refused: all four,
  the backends identical to OpenGL (max 0). Negative controls fail: the include's flip inverted (all four), no
  correction (Vulkan, OpenGL; it changes nothing in 2D on D3D), the probe packed by hand (all four).
- Two errors of the first analysis, corrected without a rebuild: the sRGB check compared with the exact IEC curve at
  1e-3, but the hardware decode carries 8 significant bits (below); and it compared the other backends with OpenGL's
  decode, which does not exist (F4).

##### Run 1's findings (decided by the lead 12 Nov 2026; drafted as proposals, kept below with their evidence)

All four accepted. Each decision follows its finding; the proposal's text stays as drafted.

**F1. OpenGL keeps texel (0,0) top-left only if the upload correction flips Y for core-owned targets.** Evidence
(scene 1, OpenGL): with the correction `clipSpaceCorrMatrix() x flipY` (the harness's "target" route) every scene-1
check holds and the image is byte-identical to Vulkan's, D3D11's and D3D12's; flipping the readback by
`isYUpInFramebuffer()` (the draft's harness rule) would then show it upside down. With `clipSpaceCorrMatrix()` alone and
the include's flip at 1 (what `rendering/gl_programs/conventions.py:19-21` says the core does), the content is upside
down in memory (`content_upside_down_in_memory`), and `fragTexel`, `fragUv`, the upload fetch and `ndcToUv` all
disagree with the writing pass. `gl_FragCoord` is the memory texel's centre on every backend (all four, exact).
*Recommended rule:* for a target the core owns, the upload correction is `clipSpaceCorrMatrix()` times a Y flip where
`isYUpInFramebuffer()`; the include's flip is 0 for every core-owned target on every backend (it would be 1 only for a
core shader drawing into a bottom-up target it does not own, which D5.2's texture-node composite removes); readbacks
of core targets are never flipped. Correct `conventions.py`'s docstring when this is accepted.
**Decided by the lead 12 Nov:** for the core's offscreen targets the upload correction flips Y on OpenGL; the
include's flip is 0 for those targets on every backend; the core's readbacks are never flipped. Guard: the shipping
Python OpenGL renderer does not change; its targets keep their value until it retires, so the block's values belong to
the target and are set by its host (that renderer writes `OPENGL_CONVENTIONS`, 0, for every target; the core writes 0
for its own), not one global constant. *Rejected alternative:* `clipSpaceCorrMatrix()` alone with the include's flip at
1 on OpenGL (bottom-up rows in memory, a per-pass flip for every sampled texture). *As built:* `conventions.py`'s
docstring says both (3a2e2e51); the harness's "target" correction is this rule. Proof that product pixels did not
move, recorded before and compared after with `tools/conventions_identity.py` (one change for F1 and F2): every mode
(9) and every catalogue transition case (32) IDENTICAL frame for frame, and `pairs` against the parent revision 28 of 28
changed fragment sources IDENTICAL, the multisample-only programs among them (`n0_3/20261112_identity_before*`,
`_after_f1f2*`, `_pairs_f1f2`); `tests/test_conventions_include.py` passes (16).

**F2. `ndcToUv` and `uvToNdc` of the clip NDC are wrong on D3D11 and D3D12 (predicted, confirmed).** Evidence
(scene 1, "target" route, texel (0,0) = the top-left): `fragUv` (0.005208, 0.008929); the clip NDC the rasterizer
used (-0.989583, +0.982143) on D3D11 and D3D12 but (-0.989583, -0.982143) on Vulkan and OpenGL; the production
`ndcToUv` gives (0.005208, **0.991071**) on D3D, the mirrored row; `uvToNdc(fragUv)` gives y -0.982143 against the clip
+0.982143. Worst error over the target: 0.982 in uv y, 1.964 in NDC y, on both D3D backends; 1.5e-7 or less on Vulkan
and OpenGL. With the NDC's Y negated first, the D3D error is 1.5e-7 (`candidate_ndc_to_uv_agrees`,
`candidate_uv_to_ndc_agrees`: true on all four). The cause: D3D's clip Y points up (`isYUpInNDC()`) while its rows are
top-down (`isYUpInFramebuffer()` false), and the correction leaves D3D's Y alone; no matrix can move D3D's NDC +1 off
row 0. *Recommended rule:* the conventions block's reserved `y` carries `ndcYFlip = isYUpInNDC() && !isYUpInFramebuffer()`
(1 on D3D11, D3D12 and Metal; 0 on Vulkan, on OpenGL with F1's correction, and in today's OpenGL renderer), and
`ndcToUv`/`uvToNdc` negate Y when it is set. Consequence: the mapping functions read the block, so any stage that maps
(vertex, compute) declares it too; `tests/test_conventions_include.py`'s "only a program that reads the block holds it"
then covers mapping-only programs, and N1.4's identity runs prove the OpenGL renderer bit-identical with `y` 0.
*Alternative:* define `ndc` in the include as the view NDC (OpenGL form, Y up) and compute it from the uncorrected
matrix; rejected here because rule 1 gives shaders only corrected matrices.
**Decided by the lead 12 Nov:** the block carries the "Y up in clip space, rows top-down" flip in `y`, read by
`ndcToUv` and `uvToNdc`; stages that use the mapping functions declare the block; on OpenGL and Vulkan the value makes
them compute what they compute today. *Rejected alternative:* the view NDC (above). *As built (3a2e2e51), one
departure to note:* the block is declared by every stage that includes the conventions (the fog march and composite
now hold it), but the Python renderer's text keeps the authored arithmetic, `ndc * 0.5 + 0.5` and `uv * 2.0 - 1.0`,
and only the native core's text (`#define SRPSS_NATIVE_CORE`, set by the core's bake and the harness) reads `y`.
Reason, measured: with `y` read at run time (0 bound), the composed `ndcToUv(uvToNdc(fragUv))` of the include test
changed its last bits on NVIDIA 617.42 OpenGL (0x3c5d67c8 became 0x3c5d67c0 at the first texel: the driver no longer
folds the arithmetic around a select on a uniform), so a value alone does not keep the renderer bit-identical. The
renderer's `y` is 0 for good, so its text and the value say the same thing; the identity proof under F1 covers it.
`tests/test_conventions_include.py` proves the core's text negates Y when `y` is 1 and is the plain arithmetic at 0, and
that the renderer's text never reads it.

**F3. Rule 4's input is the uploaded matrix, never the OpenGL-form one.** Evidence (scene 3): `front_face_clockwise` on
the uploaded (corrected) matrix keeps the authored-front triangle on all four backends with both matrices; the same
function on the uncorrected matrix culls the wrong triangle on Vulkan (the correction flips Y there) and OpenGL (F1's
flip), with both matrices, and changes nothing on D3D. *Recommended rule:* the core evaluates rule 4 once per pipeline
choice on the matrix after the upload correction, with `ndc_y_up = isYUpInNDC()`; the two prebuilt variants stay. Today's
OpenGL renderer is unchanged (it uploads uncorrected matrices on an identity correction).
**Decided by the lead 12 Nov:** the front-face rule is evaluated on the matrix after the upload correction (also
recorded in D6, below its amendments, and in the C++ copy's comment, `native/spike_p1/src/n03_scenes.cpp`
`frontFaceClockwise`, and `front_face_clockwise`'s docstring). *Rejected alternative:* the OpenGL-form matrix (wrong
faces on Vulkan and on the core's OpenGL).

**F4 (new). Qt 6.12.0's OpenGL backend ignores `QRhiTexture::sRGB` for uncompressed formats.** Evidence: on OpenGL the
sRGB-flagged strip samples as byte/255 exactly (max 3e-8; worst 0.287 from the curve at byte 136), identical to the
unflagged strip; on Vulkan, D3D11 and D3D12 it decodes, bit-identical across the three. A hidden probe through
PySide6's QRhi read `GL_TEXTURE_INTERNAL_FORMAT` = `GL_RGBA` for the flagged and the unflagged RGBA8 texture alike, and
qtbase v6.12.0 `src/gui/rhi/qrhigles2.cpp` reads the flag only in `toGlCompressedTextureFormat` (`toGlTextureFormat`
takes no flags). So the cause is Qt's, not the harness's target creation; no rebuild fixes it. Rule 6 ("the `sRGB`
texture flag on every backend") does not hold on OpenGL. Also measured: the hardware decode where it exists carries 8
significant bits (7 fraction bits), worst 0.00375 at byte 251 (1.3 steps of that mantissa, 0.86 of half the gap to the
neighbouring byte), monotonic, every byte kept.
*Recommended rule:* the one sRGB asset (the floor albedo, `scene3d/waveform.py:114`) is uploaded as plain RGBA8 and
decoded in its shader with the exact IEC formula on every backend: one route, bit-identical across backends, no reliance
on a flag one backend ignores. Its parity bar against today's OpenGL renderer (hardware `GL_SRGB8_ALPHA8`) is the
hardware's own precision, at most 0.00375 linear, recorded at the port. *Alternatives:* decode in the shader on OpenGL
only (a block value; the backends then differ by up to 0.00375); or a native `GL_SRGB8_ALPHA8` texture adopted with
`QRhiTexture::createFrom` on OpenGL (a D5.3 service, raw GL, to win a measurement first).
**Decided by the lead 12 Nov:** the floor albedo is decoded in its shader with the exact sRGB formula on every
backend. Filtering consequence, stated: the GPU filters (bilinear, trilinear, anisotropic) and mips the *encoded*
values, and the decode follows, so a filtered sample is `decode(average(encoded))` instead of the hardware's
`average(decode(encoded))`; that is accepted for this one asset (a dark, low-contrast concrete) and is not a general
rule for sRGB assets: another sRGB asset gets its own decision. Qt's behaviour is defect E in
`Native_Core_N06_N07_Qt_Facts.md` section I. *Rejected alternatives:* the two above. *As built (25688bbf):*
`srgbToLinear` in the include (IEC 61966-2-1, exactly); `load_floor_textures` stores the albedo as plain `GL_RGBA8`;
the floor fragment decodes its three albedo reads (the grain pair, the 1x1 mean level, the wet-film ratio). Before and
after on Waveform Ribbon, the mode that owns the floor (every frame of its identity run, 549 frames at 739 x 529):
pixels move, by exactly one 8-bit step (1/255) at most, on 0.513 % of pixels in 296 of 549 frames (the worst frame's
difference image shows the floor band only); no pixel moves by more. Every other mode IDENTICAL (Sphere's last 52
frames differ only because its script switches to Waveform Ribbon at frame 497). Evidence
`n0_3/20261112_f4_floor/` (before, after, difference scaled) and `20261112_identity_after_f4/`. The harness gates the
shader's decode against the exact curve (`srgb_shader_decode_matches_analytic`) and across backends; the sampler's
decode of a flagged copy stays a record.

## From N0.4: the source inventory, the cost evidence, the draft and the questions

#### N0.4. The camera (proposed D5.5; decided by the lead 12 Nov)

*Decided by the lead, 12 Nov 2026 (answers in "Lead decisions on the N0 drafts" below); drafted as:* *Proposed (draft for the lead), 12 Nov 2026. Nothing here is decided. Read at `7ac980d7`. One finding differs from
the plan's wording ("the core receives finished matrices and rays from the worker"): today no finished matrix
travels from the worker to the renderer at all, so "keeps receiving" is not available and the contract below says
what has to be added.*

##### What is true in source

- **One owner of the camera's math.** `core/settings/framed_camera.py` ("the standard physical camera for framed
  3D Visualizer modes", header `:1-14`; "pure and Qt-free: admission, flight on the capture clock, Settings editors
  and renderers all call it"): `FramedCameraSpec` per mode (`spec_for_mode`, `:94`; declared through the mode
  descriptor's `framed_camera`, `core/settings/visualizer_mode_registry.py:163,400,441,473`), `camera_axes` (`:116`),
  `camera_baseline` (`:174`), `bound_eye` (`:201`), `resolve_camera_position` (`:214`), `resolve_camera_frame`
  (`:247`), `viewport_tangents` (`:259`), `effective_aperture_scale` (`:275`), `perspective_matrix` (`:286`),
  `view_matrices` (`:292`), `project_point` (`:302`). The per-mode modules are thin (`extruded_bubble_camera.py:33-34`
  forwards `camera_axes` with its `SPEC`; Neon Lake and Waveform Ribbon declare specs the same way).
- **Three consumers build matrices from it, in three places, none of them the worker's tick:**
  1. Extruded Bubble: `rendering/gl_programs/extruded_bubble_scene.py:233-268` (`camera`, `physical_camera`), called
     once per rendered frame by the render thread (`rendering/quick/visualizer/implementations/extruded_bubble.py:427-433`)
     with the parameters from the frame, `width / height` from the card's pixel rect and `aperture_scale` from the
     presentation.
  2. Waveform Ribbon: `core/waveform_ribbon_view.py:16-27` (`physical_view`, "the renderer draws with `physical_view`"),
     called per frame by the render thread (`implementations/waveform_ribbon.py:64-65`) with
     `framed_aperture_scale(presentation, content=True)` and the per-frame `state.zoom`; **and** by the logical side
     (`card_span`, `waveform_ribbon_view.py:56-72`, "within a few percent of the renderer's": it uses the extent
     without the shell inset).
  3. Neon Lake: `rendering/gl_programs/neon_lake_basin_program.py:81,99` takes `camera_axes` in its program builders.
- **What reaches a renderer today is parameters, not matrices:** the frame's `parameters` (turn, tilt, scene scale,
  pan, camera position, fov) cross the mapping as plain values (the Extruded Bubble frame,
  `logical_frame_capture.py:457`); the renderer asks `framed_camera` for the matrices each frame, with two inputs that
  only the GUI side knows exactly: the card's pixel size and `framed_aperture_scale`
  (`widgets/spotify_visualizer/presentation_geometry.py:456-468`, driven by edge resizing and CUSTOM stages).
- **Rays are not arrays.** The shaders rebuild a view ray from the tangent pair: `framedRayDirection(ndc, span) =
  normalize(vec3(ndc * span, -1.0))` (`rendering/gl_programs/framed_camera.py:14-16`; "the CPU projection matrix and
  these ray uniforms are resolved from the same camera", `:3-4`). So "matrices and rays" is: the view (axes and eye),
  the projection, and the tangent pair `tan` (two floats).
- **The worker already receives the GUI's view inputs** at edges: `VIS_SET_VIEW` carries the layout metrics and the
  presentation inputs that changed (`widgets/spotify_visualizer/engine_worker_link.py:579-620`; the owner's
  `set_view_source`). It is latest-wins and one send per GUI turn at most; it is what lets the worker size
  Waveform's travelling pulse.

##### Per-frame cost today (evidence)

A pure-Python timing of the camera build, 2,000 laps in one process, no GL, no window (script
`.artifacts/scratch/n04_camera/time_camera.py`, deleted afterwards; development machine at `7ac980d7`):
`physical_camera` (Extruded Bubble, the whole per-frame build) median 6.6 us, p99 8.3 us; `view_matrices` median
1.9 us; `project_point` median 3.8 us. **Cost per frame argues against nothing: no per-frame cost was found that
justifies a second camera.** Waveform Ribbon's `physical_view` (which also admits the full parameter set through
`resolve_camera_frame`) was not timed: it needs the mode's complete parameter record. The reason the build must
still leave the render thread is not its cost but D5.4: a Python call there puts the GIL back on the render thread.

##### Proposed D5.5

1. `core/settings/framed_camera.py` stays the **only** implementation of camera math. The core contains no
   `perspective_matrix`, no `viewport_tangents`, no axes and no eye resolution; there is no second camera to keep in
   step, in C++ or elsewhere.
2. **Finished camera data is built on the Python side by that module and published per frame in the packet**, in the
   fixed per-mode native schema (transport rule 3): the view (`view_to_world` and `world_to_view` as float32, the
   eye as float32), the projection (a 4 by 4, in OpenGL form, corrected once at upload, N0.3 rule 1), and the tangent
   pair `tan`. That is about 40 floats, 160 bytes a frame. The core does not derive any of it.
3. **The builder runs where the inputs are exact.** The worker's tick builds the camera; this needs two numbers the
   worker only has approximately today: the card's exact pixel aspect and the exact `framed_aperture_scale`
   (`content=True`). They are added to the `VIS_SET_VIEW` record as two plain floats, resolved by the same GUI-side
   functions the renderer calls now (`item_pixel_rect`, `framed_aperture_scale`), and sent at the edges where they
   change (resize, CUSTOM edge resize, DPI), never per frame. The approximation of `card_span`
   (`waveform_ribbon_view.py:59-60`) then ends: logical and render use the same record.
4. Per-frame inputs that change with the music (Waveform's `state.zoom`, Dynamic Zoom) are inputs to the worker's
   build, not to the core.
5. **A framed mode's pixels are a function of the packet alone:** same packet, same camera.

*Alternative, if the lead rejects 3:* the core receives the parameters and the two exact numbers and builds the
matrices itself. That is a C++ port of about 30 lines of `framed_camera` arithmetic and a second owner to keep equal
to the Python one (the thing the plan forbids), so the draft does not propose it; it is the fallback only if the
worker's build proves to cost the tick.

##### Tests that fail without it

- *Equality to today's renderer:* for a recorded parameter set and a range of card sizes and apertures (resized,
  CUSTOM edge-resized, DPI changed), the matrices, eye and `tan` in the packet equal bit for bit (after the float32
  narrowing the schema defines) what `physical_camera` and `physical_view` return for the same inputs. The oracle is
  the existing renderer code. *Negative control:* build the packet camera with the approximate extent
  (`card_span`'s extent without the shell inset); the test fails on a CUSTOM stage.
- *One owner:* a test that greps the native sources and the schemas for a perspective or tangent construction fails
  if one exists (negative control: add `tan(fov / 2)` to a core file).
- *Resize edge:* an edge resize reaches the packet within the next worker tick (`VIS_SET_VIEW` latest-wins), and a
  frame between the resize and the tick is drawn with the old camera and the old target size together, never a
  mixed pair (the packet carries the extent it was built for; the core compares it with the target it draws into and,
  on a mismatch, holds the previous frame, the existing latest-wins behaviour). *Negative control:* ignore the
  stamp; a stretched frame appears.

##### Questions for the lead (N0.4)

1. Confirm that the camera is built in the worker's tick (proposed) rather than in the Python presentation sync on
   the GUI thread. The GUI route needs no change to `VIS_SET_VIEW` but puts about 7 us of Python on the GUI turn per
   frame per window and leaves the packet camera-less (the core would wait for the GUI's snapshot, which is the
   hybrid the plan wants to avoid).
2. The exact aspect and aperture are two new floats in the view record. They change the stored shape of the
   worker's view message (an internal protocol, not a persisted one); confirm no bridge is needed.
3. Neon Lake builds its axes inside program builders (`neon_lake_basin_program.py:81,99`); under the proposal that
   moves to the packet like the others. Confirm it is in scope of the Neon Lake port (N5.5), not of N0.

## Lead decisions on the N0 drafts (12 Nov 2026), as given

#### Lead decisions on the N0 drafts (12 Nov 2026)

The four drafted sections above (D1 to D3 and the transport rule; the rest of D5; N0.3; N0.4) are accepted as
written, with these answers to their questions. "Nothing here is decided" in their headers is history.

**D1 to D3 and the transport rule.**
1. D1: the core maps its own view by name and retires asynchronously on the render thread; the GUI never waits.
   The bounded GUI wait is rejected (it can deadlock against Qt's synchronisation of the two threads).
2. D2: the core acknowledges at the accept edge (parity with today's `take`), not at the swap.
3. D3: geometry moves into the parent-owned arena, two banks per family; the slot shrinks to the base envelope.
   The OpenGL solver's delete-before-allocate order and its leak on a failed dispatch are fixed now, in the
   OpenGL renderer (plan N1), not only in the native path: they are today's defects. The revision-only identity is
   proved or disproved now by the D3 identity test against the Python solver.
4. Transport: the numbering stands (`payload_schema` 1 the tagged Python codec; native `0x100 | mode_code`, the
   version in bits 16 to 23; 2 to 0xFF reserved).

**The rest of D5.**
1. After a device loss the drift solver's GPU-only per-mote state restarts, hidden by the mode's reveal fade (fade,
   never vanish). It is not rebuilt from the log (128 steps cannot rebuild it), and a device loss is rare.
2. The bound: a second device loss on a window before 3,600 presented frames since its rebuild is a backend
   failure: the Visualizer on that window fades out and parks, and D6 point 5's remembered failed start applies.
   Counted in frames at the frame edge, never by a timer.
3. Admission is accounting only (the ownership table and today's capacity envelope); a per-window GPU-memory
   budget is added only if a measurement shows a surface exceeding what the device can hold.
4. Pipelines are device-scoped and survive a mode release: the set is finite and a return to a mode then costs no
   warm-up.

**N0.3.**
1. Core-owned offscreen targets are top-left, Y-down on every backend (Vulkan is the front face; OpenGL is the
   backend that flips).
2. No reverse-Z now; it is decided separately only if the near-plane bead check (plan N1) calls for depth precision.
3. The conventions block has one fixed, reserved binding in every shader; N2 chooses the index once.

**N0.4.**
1. The camera is built in the worker's tick by `core/settings/framed_camera.py` and published in the packet; the
   GUI-thread build is rejected.
2. The two new view floats (exact pixel aspect, exact aperture scale) change an internal message, not a persisted
   shape: no bridge; the message's version is raised.
   *Amended 12 Nov (as built):* three numbers, not two: Extruded Bubble's renderer draws with the aperture scale of the
   whole extent (`framed_aperture_scale(presentation)`, content=False) and Waveform Ribbon with the content's, so
   `FramedView(pixel_aspect, aperture_scale, extent_aperture_scale)` (`core/framed_view.py`, `VIS_SET_VIEW` version 2).
3. Neon Lake's camera axes move into the packet at its port (N5.5), not in N0.

**D5.6, the dependency table (N0.2).** Accepted as written, every row to its chosen route, with these answers:
1. Overflow modes (Sphere, Extruded Spectrum) keep today's look: their target covers the painted overflow footprint
   the stencil allows today, and the composite's coverage term clips to that footprint, not to the item rectangle.
2. The anti-aliased coverage edge replaces the hard `discard` edge, provided the card-clip contract of R-191 holds on
   the native composite (no content under a straight-edge frame pixel; in the corners only under pixels the frame
   covers by at most half): `tests/test_visualizer_card_clip_contract.py`'s rules are the native port's parity bar.
3. A multisampled `background()` stays resolve-first; the per-sample service (D5.3) is admitted for Extruded Bubble
   only if the A/B at its port shows a visible or cost loss (N1.8's rule).
4. The per-pass timer service's form is provisional until the N0.7 harness shows a timestamp around a whole pass
   from where the core records it; until then only the whole-frame time is relied on.
   *Settled from where the core records a pass (N2.6, built 13 Nov 2026; proved when `timer_check.py` passes in its
   build round):* the core records every pass in one place, the frame driver's `beforeRendering` edge, before Qt
   Quick's pass and outside any render pass (D5.2). There the timer brackets each whole pass through
   `QRhiCommandBuffer::beginExternal()` on the frame's own command buffer: outside a pass QRhi first records what it
   holds into the primary command buffer, so the bracket sits exactly between the passes in submission order and no
   secondary command buffer exists (the research's A.1 worry concerns only a timestamp inside a pass, which the core
   never takes). Vulkan: `vkCmdWriteTimestamp` TOP_OF_PIPE before and BOTTOM_OF_PIPE after, in a query pool of the
   timer's own, reset in the frame before its first write. OpenGL: `GL_TIME_ELAPSED` begun before and ended after
   (QRhi's OpenGL backend issues its recorded commands at `beginExternal`, so the query encloses the pass's own GL
   commands). D3D11 and D3D12: QRhi offers no per-pass time and D5.3 gives the service no third form, so what QRhi
   provides is used there, as on the other two: the whole frame, `QRhiCommandBuffer::lastCompletedGpuTime()` of a QRhi
   created with `EnableTimestamps` (a host opts in at creation). No compute-pass external block is needed. Results are
   latched in a ring of eight frame slots and read only when available (no wait bit; OpenGL's availability first); a
   frame whose slot still holds unread results goes untimed and is counted, never waits (a hidden host's unpaced OpenGL
   frames run ahead of their results; a real window times every frame); a switched-off timer's objects go once every
   result was read; off, the driver holds no timer and no query object. The figures reach the frame trace as events 77 and 78 (GPU
   nanoseconds), read by `tools/frame_trace_report.py`; admitted by `--gpu-pass-timing` with `--frame-trace`.
The `glMultiDrawArraysIndirect` start-up requirement is removed (nothing calls it; the only indirect draw is
`glDrawArraysIndirect` in `scene3d/population.py`, which row 14 routes).

## Where the audit of 12 Nov disagreed, in one place

#### Where the audit of 12 Nov disagreed, in one place

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
