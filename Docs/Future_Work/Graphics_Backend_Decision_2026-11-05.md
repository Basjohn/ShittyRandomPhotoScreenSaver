# Graphics backend decision: Vulkan backend vs SMP & Full Display (5 Nov 2026)

**Status:** DECIDED by the lead at the operator's request ("ideally you should render that decision"), 5 Nov 2026.
Supersedes the open question in `Future_Work.md` §2 / §2.5 and `Current_Plan.md` §0 step 4. The operator may overrule.

**Current implementation note (10 Nov 2026):** This document records the **dated** decision and its later
P1/P2/P3 addendum, not an assertion that every phase below is still future. P1's C++/QRhi spike is proven;
P2's supervised Python Visualizer engine worker is the Windows default; P3's universal C++/QRhi custom
renderer is not a production implementation yet. `Current_Plan.md` §8b controls the remaining work/order.
The intended post-port default is Vulkan through QRhi, with the same core supporting an OpenGL fallback.
The old phrase "No Vulkan backend now" below describes the 5 Nov decision, not an indefinite ban on modernization.

## Decision

1. **Next large series: SMP & Full Display**, in the order its own plans set: Expanded Visualizer
   (`Docs/Future_Work/Expanded_Visualizer/01_Expanded_Visualizer_Implementation_Plan.md`) after Waveform
   acceptance, then ShittyMusicPlayer
   (`Docs/Future_Work/ShittyMusicPlayer/02_ShittyMusicPlayer_Implementation_Plan.md`).
2. **No Vulkan backend now.** A Vulkan backend is the right *eventual* direction, but only in one form: a **native (C++)
   render core behind the existing `QSGRenderNode` boundary, hosted by Qt Quick on its Vulkan RHI backend**, never a
   Python-driven Vulkan port. It starts when one of the measured triggers below fires, and if it starts it precedes any
   further new 3D mode.
3. **Port-readiness rules apply to all new GPU code from today** (below), so whatever is built on OpenGL meanwhile is
   cheap to move later. This is what answers the operator's parity concern ("if we choose Vulkan the earlier the better
   for parity"): parity cost grows with *GL-specific* surface, and the rules stop that growth.
4. **New 3D modes** (§6 shared primitives, Melt Pool, Concrete Rain, Usu Moonscape) resume only after Expanded
   Visualizer is accepted (its full-display measurements decide whether the triggers fire) and only under the
   port-readiness rules.

**For the agent that implements this WHEN a trigger fires (binding, also in `Docs/Guardrails.md`):** the benefit of
Vulkan exists only as a native render core. Moving the existing Python GL calls to Python Vulkan calls (via a Python
binding, or Qt's QRhi driven from Python per draw) makes the product *worse* than today's GL: Vulkan needs more calls per
frame (command buffers, descriptor sets, barriers), and from Python each one contends for the GIL with the logical tick,
which is already the measured live bottleneck. The core must record its frames in native code without the GIL, with
Python only publishing immutable frame data across the existing frame/snapshot boundary.

## Why

**What a Vulkan backend would buy, measured against this product** (as a native render core; a Python-driven port buys
nothing and costs GIL contention):

| Benefit | Real for SRPSS? |
| --- | --- |
| DLSS (NVIDIA RTX) and FSR 2/3 temporal upscaling / frame generation | Only via Vulkan or D3D (DLSS has no OpenGL path; FSR 2/3 ship DX12/Vulkan backends). But both are temporal: they need per-mode motion vectors, jittered projection, depth and reactive/transparency masks. Our modes are dominated by exactly what temporal upscalers smear: thin emissive lines (lattices, rims, contour lines), particles and sparks, OIT sheets, volumetric mist, fast music-driven flashes. Each mode would need its own masks and tuning, and frame generation adds interpolated frames to content whose point is to react sharply. High quality risk per mode. |
| Lower driver overhead, explicit sync, async compute | Not our bottleneck. Measured costs are CPU/GIL: the logical tick is pure Python (Waveform ~1.3-2.3 ms median), and the live-check tool documents the render thread starving behind GIL-held Python ("every GL call hands the GIL over"). A *Python* Vulkan port makes this worse (far more API calls per frame). |
| GPU headroom | Not a measured deficit today at card size: Waveform P2 ~6-7.6 ms GPU at the live card size, Neon Lake 0.6-1.6 ms up to 2560x1440. Full Display at 4K is where it could become one: that is plan 01's job to measure. |
| Ray tracing, mesh shaders | No admitted mode needs them. |

**What it would cost:** about 31k lines of Python GL programs/scene code (`rendering/gl_programs`, `rendering/quick/scene3d`,
`rendering/quick/visualizer/implementations`), 87 Python modules importing PyOpenGL, 63 GLSL 460 programs incl. 8 compute
shaders, DSA/persistent-buffer/indirect paths, the `QSGRenderNode` GL integration, and parity for eight accepted modes
(BTF, pixel oracles, the operator-protected QSG/clip optimisations). A Vulkan backend in practice means a new native render
core plus a compiled extension in the Nuitka build. Doing that now would stop product work for a long stretch with no
measured product need, and risk regressions in accepted modes.

**What SMP & Full Display buys:** direct product value, independent of the render API (library/playlists/playback,
Settings, Quick panes, the takeover state machine). Expanded Visualizer is a presentation-layer feature on the existing
retained Quick scene: it does not add GL-specific rendering surface, so doing it first does not raise the later port cost.
It also produces the evidence the backend question lacks: the GPU cost of the 3D modes at full display, 4K, under load.

**Why the eventual backend is "native core on Qt's Vulkan RHI", not a hand-rolled Vulkan app:** Qt Quick already runs on
QRhi (Vulkan, D3D11/12, Metal, GL); this PySide6 build exposes `QRhi`. Staying inside Qt Quick keeps one window/scene/
compositor owner (Spec: one retained `QQuickWindow` per display) while `QSGRenderNode` hands the native core Qt's
`VkDevice`/command buffer through the RHI native handles, which is also where DLSS (Streamline/NGX) or FidelityFX
integrate. A native core also removes the GIL from the render thread, the one live-performance problem we have actually
measured, which no API change made from Python can fix.

**QRhi by default, raw Vulkan per pass where measured; OpenGL selectable, Vulkan the default** (operator, 8 Nov: "as
long as it is a genuine significant improvement we still win"; "we keep OpenGL selectable since it's cheap but Vulkan
the default"). Binding for P3:
- **Why QRhi, not raw Vulkan, as the core's base API.** Qt Quick on Vulkan owns the device, queue, swapchain, render
  pass and frames in flight, and our items draw inside that frame: through QRhi, Qt tracks barriers, resource lifetime
  across frames in flight and render-pass compatibility, which raw Vulkan inside Qt's frame would re-implement against
  Qt's internals (the likeliest place for a port to go wrong). QRhi is what makes one core run on Vulkan, D3D12 and
  OpenGL, so the GL fallback costs no second renderer, and what lets QRhi-native nodes run beside today's Python GL
  nodes in the GL window while modes port one at a time. Its CPU overhead is a thin recording layer, negligible at our
  scale (a handful of passes per frame).
- **The API is not where GIL contention comes from.** QRhi is C++ inside Qt: a native node calling it never touches
  the GIL, exactly like raw Vulkan (P1: a native render thread kept running while a Python thread held the GIL). The GIL
  matters only where Python runs: the logical tick (P2) and Python on the render thread (P3 removes it either way).
- **QRhi's limits and the escape hatch.** QRhi has no async compute queue (4V), and no bindless/descriptor indexing,
  mesh shaders, ray tracing or arbitrary Vulkan extensions. A pass that measurably needs one records raw Vulkan inside
  Qt's own command buffer through `QRhiCommandBuffer::beginExternal()`/`endExternal()` and the native device/texture
  handles (also the DLSS/FSR route). Such a pass is Vulkan-only: on OpenGL it is unavailable or takes its QRhi form.
  Never raw Vulkan by default, never a capability given up when a measurement asks for it.
- **API stability.** QRhi is public with limited compatibility guarantees: a PySide6/Qt upgrade can change it, so each
  upgrade rebuilds and re-runs the core's parity gates (the core is built against PySide6's exact Qt, as in P1).
- **Backend selection.** After the flip (P3 step 6) the backend stays a setting: Vulkan the default once it matches
  OpenGL's pixels, OpenGL (Qt's GL RHI backend running the same core) kept selectable as the fallback for driver
  bugs, VMs and software-rendered Linux. Its cost is the per-backend test matrix; Vulkan-only features are simply off
  on OpenGL. Keeping today's raw Python-GL renderer alongside the core is not planned (that is the double maintenance
  P3 removes).
- **The one coupling left inside Qt Quick, and its escalation.** Every Qt Quick frame passes a short sync with the GUI
  thread (raw Vulkan inside Qt Quick has the same): a GUI thread stuck in a long Python slot, or Python anywhere in the
  sync/render path, delays the frame. P3 keeps the whole sync and render path Python-free (4V), and P2 keeps the GUI
  thread idle. If gate 3 or P3 measurements still show late syncs, the escalation is a core that owns the swapchain
  and frame pacing on its own native thread, with Qt Quick rendering only the UI layer into a texture
  (`QQuickRenderControl`) for the core to composite: the Visualizer then never waits for the GUI thread. Only when a
  measurement demands it; it is a larger change to the window owner.

## Triggers that start the native Vulkan render core (any one, measured, recorded in `Current_Plan.md`)

1. **GPU budget:** an accepted 3D mode at Full Display 4K under `tools/visualizer_live_check.py --load game60` exceeds its
   render budget even with mixed-resolution soft layers (below) at its quality floor.
2. **Render-thread starvation:** after logical-tick optimisation, GIL starvation of the render/GUI threads remains the
   top live-hitch cause (live-check `logical_gil_share`, age chain, hitches/min), with a native render path the remaining
   fix.
3. **Capability:** an admitted mode genuinely needs ray tracing, mesh shaders or async compute.
4. **Platform:** an OpenGL driver/platform blocker on a supported target.

## Meanwhile: cheap wins on OpenGL

- **Mixed resolution, never whole-frame upscaling.** Our content is mostly thin emissive lines (lattices, rims, contour
  lines), dot grids, 1-px particle cores and sharp music-driven flashes. A spatial upscaler such as FSR 1 (EASU + RCAS)
  has no history so it does not smear in time, but it cannot recreate those details: it softens lines and rings on dots
  and cores (operator, 5 Nov: "smeary and ugly"). Temporal upscalers smear them over time. So: render only the soft,
  expensive layers (mist/fog volumes, bloom, reflection and glass blur, wide glows) at reduced resolution with
  depth-aware/bilateral upsampling, and keep every line, dot, particle and rim at native resolution. Parts of the
  codebase already do this (the reduced-resolution fog march; S3D-7). This ports unchanged to Vulkan.
- **Measure, don't assume:** plan 01 records per-mode GPU time at full display 4K (with and without the reduced-resolution
  soft layers) with system conditions, per the benchmarking rules (relative to a control, load recorded).

## Port-readiness rules (all new GPU code, from 5 Nov 2026)

1. GLSL is written in the Vulkan-compatible subset: `#version 450/460`, explicit `layout(location=)` and
   `layout(binding=)` on every interface, uniforms in std140/std430 blocks (no loose `uniform` scalars in new programs),
   no legacy built-ins, no `gl_` fixed-function state, combined samplers only where QRhi/SPIR-V allows.
2. GPU resources (buffers, textures, framebuffers, programs) are created and owned through the shared Scene3D/render
   substrate (`Docs/Reference/Scene3D_Resources.md`), never ad hoc in mode code, so the substrate is the porting seam.
3. No new dependence on GL-only features without an RHI/Vulkan equivalent noted in the code (e.g. persistent mapping,
   `glMultiDraw*Indirect` are fine; GL-specific state tricks or extensions are not).
4. Coordinate conventions explicit (clip-space depth range, framebuffer Y-origin, texture origin) and isolated in one
   helper per program, since GL and Vulkan differ.
5. A test compiles every program to SPIR-V. Enforced for compute shaders since 8 Nov 2026 with PySide6's own `qsb`
   (`tests/test_vulkan_shader_readiness.py`, `tools/vulkan_shader_readiness.py`): the 18 compute sources written
   before it use loose uniforms (rule 1) and sit on a legacy list that only shrinks as P3 ports each mode; every other
   compute shader must compile. Vertex/fragment programs: extend the same test when P3's first port lands.

## Addendum, 7 Nov 2026: a universal visualizer performance architecture (operator direction)

The operator: "The Native Core and the Vulkan support once we've finished this set of optimization and fixes? We
should have it be universal so we have improvements to all visualizer modes which are more needed than ever when it
could be going fullscreen."

**Trigger status:**
- **Trigger 2 (render-thread starvation)** is effectively met. Waveform Ribbon's logical tick holds the GIL 73-75%
  under game60, so render-mode time is 16-21 ms and frames fall to 37-44 fps; offline its dynamics cost about 1.3 ms.
  Extruded Bubble is the second case (GIL 0.53).
- **Trigger 1 (GPU budget)** is close: at display size Extruded Bubble already renders 8.2 ms under game60 (M0
  receipts), over §0.7's 8 ms. Full display now covers every mode except Sphere and Extruded Spectrum.
- Trigger 2's wording asks for logical-tick optimisation first. That was the byte-identical tick cut (merged 7 Nov,
  13-16% offline), and it confirmed the trigger:
  - live with NO load, the Waveform Ribbon tick took 7.49 ms (median; p90 12.5; GIL share 0.67; 51.7 fps), against
    about 1.5 ms of its own work in replay;
  - about 6 ms of every live tick is therefore spent waiting for the GIL held by the render and GUI threads;
  - code trimming cannot remove that wait. Piece A below removes it by construction.

**The plan: three combinable pieces, each likely to pay off, each removing a different bottleneck.**

| Piece | Removes | Fidelity | Why it is likely to pay |
| --- | --- | --- | --- |
| **A. Out-of-process visualizer engine** (universal) | GIL contention between the logical tick and the GUI/render threads | byte-identical | The same Python tick code runs in one worker process (only one Visualizer runs at a time). It publishes immutable frame packets through shared memory (the triple-buffer pattern of the audio capture, R-171), so the main process never runs the tick. Replay identity tests apply unchanged. Settings edits reach the worker as versioned snapshots; the worker lives and retires per generation like the image and audio workers. |
| **B. Native render core** behind `QSGRenderNode` on Qt Quick's RHI (Vulkan; D3D12/GL selectable through the RHI) | Python and the GIL on the render thread, for every mode | pixel parity per mode | The core reads A's packets straight from shared memory and records frames natively, so no Python runs per frame on the render thread. Modes port one at a time behind a capability flag; the GL path stays until each mode's parity (BTF, pixel oracles, protected QSG/clip work) is proven. "Vulkan support" comes with it: the backend becomes Qt's choice. |
| **C. Mixed-resolution soft layers** as a core service | GPU fill cost at full display and 4K | lines, dots, particles and rims stay native | Mist/fog, bloom, glass/reflection blur and wide glows render at reduced resolution with depth-aware upsampling (the rule above). It is universal, and it is the measured risk of full display. |

A makes B cheaper (the packet layout is fixed and already off-thread). C slots into B's frame graph. Together they
cover all three measured costs: the logical tick's GIL, the render thread's Python, and GPU fill.

**One core for everything we draw ourselves, never GL and Vulkan mixed** (operator, 7 Nov: "would transitions have
their own native core as well? I cannot imagine combining Vulkan and GL is very efficient").
- **One backend per window:** Qt Quick runs one RHI backend per window, and every render node in that window's scene
  graph must speak it. A Vulkan window cannot host our Python OpenGL nodes, and nothing mixes the two in one frame.
- **One core, written against QRhi (not raw Vulkan):** B is a single native core for every custom-rendered surface:
  Visualizer modes, transitions (the fullscreen-pass family, Crumble, Particle, 3D Block Spins…), the image presenter
  and background nodes, and the Scene3D substrate. Transitions do not get a second core; they share the core's pass
  and resource substrate, and they are among the cheapest ports.
- **QRhi runs on GL too:** the window stays on Qt's OpenGL RHI backend while pieces move one at a time. Both Python
  GL nodes and QRhi-native nodes run on GL during the migration.
- **The flip:** when nothing raw-GL is left, the window flips to Vulkan (or D3D12) by Qt setting, with no second
  port. Qt's own items and our `.qsb` material shaders are already RHI-native.
- **Order inside P3:**
  1. the core substrate;
  2. Spectrum (parity proof);
  3. the transitions' shared fullscreen pass (most transitions at once);
  4. Waveform Ribbon and Extruded Bubble;
  5. the rest;
  6. the backend flip, behind a setting with the GL backend kept as the fallback until physical acceptance.

**Temporal upscaling and frame generation (DLSS 4+, FSR 3+): kept open, scoped to where they can help** (operator, 7
Nov: "We also should not close the door on whatever small benefits FSR3+ or DLSS 4+ could give us and *where*").
- **Prerequisite:** both need the native core on Vulkan or D3D12. Neither has an OpenGL path, and both integrate
  through the RHI's native handles (Streamline/NGX for DLSS, the FidelityFX SDK for FSR).
- **Where super-resolution can help:**
  - **Candidates:** the 3D scene pass of upscaler-friendly modes at full display or 4K: soft-shaded, few hairlines
    (Extruded Bubble's bubbles and water; future Melt Pool and Usu Moonscape surfaces).
  - **Scope:** only that pass is upscaled. Lines, dots, particles, rims, HUD and cards composite afterwards at
    native resolution.
  - **Each candidate mode supplies** motion vectors, depth, a jittered projection, and reactive/transparency masks.
  - **Opt-in per mode, off by default,** accepted only on an A/B of renders and the music-response traces.
- **Where it cannot help:** line, dot and particle-dominated modes (Spectrum, Oscilloscope, Spline Curve, Neon Lake's
  wire terrain, Waveform Ribbon's strands and sparks), and every transition: temporal reconstruction smears exactly
  what they are made of.
- **Frame generation:**
  - **At most** an opt-in for full display at high refresh on slow ambient scenes, with its added latency measured.
  - **Never on by default:** interpolated frames blur music-driven hits, which are the point.
- **DLSS ray reconstruction:** only if a mode ever ray traces; none does.
- **What changes in the Decision:** whole-frame upscaling stays rejected. Per-pass upscaling on a scene layer
  becomes a permitted, measured option after B.

**Secondary options:**
- **D. Per-mode GPU simulation** (a ribbon's per-vertex motion, strands, particle populations): only where a profile
  after A shows the simulation itself dominates. Identity becomes tolerance-based, judged on renders.
- **E. Compiled hot loops** (Cython/C, `nogil`): only if A is rejected or a hot spot remains inside the worker.
- **F. Free-threaded CPython 3.14t:** a spike only. It depends on PySide6, PyOpenGL and numpy being production-ready
  free-threaded; if they become so, it could someday replace A.

**Rejected:**
- A lower tick rate with interpolation: it moves transients and changes dynamics, so reaction is lost.
- Whole-frame upscalers (above).

**Order, after the current set of fixes and optimisations lands** (the tick cut, card surfaces, the Studio fixes):
1. **P1, toolchain spike for B (go/no-go):**
   - a minimal native `QSGRenderNode` built against PySide6's exact Qt version (QRhi headers), loaded from Python;
   - drawing through the RHI on Vulkan inside the existing `QQuickWindow`;
   - packaged by Nuitka in a frozen build, which the operator runs.
2. **P2, A for every mode:**
   - byte-identical packets on all recordings × all modes;
   - GIL share and frame age before/after in one game60 run of at most 10 minutes, only after the operator's yes.
3. **P3, B:**
   - the core skeleton, then Spectrum as the parity proof (simplest);
   - then the starved modes (Waveform Ribbon, Extruded Bubble), then the rest.
4. **P4, C inside the core** for full display and 4K.

Expanded Visualizer M2-M5 (behaviour) continue on the current path. M6, the 4K performance acceptance, waits for P2 and
the first P3 ports. New 3D modes stay behind P3, as the Decision already says.

## Re-decision points

Revisit this decision at Expanded Visualizer acceptance (with its full-display measurements) and whenever a trigger is
recorded. If the operator prefers to front-load the port despite the cost, the order becomes: native Vulkan core
(parity across all accepted modes first) -> Expanded Visualizer -> SMP -> new 3D modes.
