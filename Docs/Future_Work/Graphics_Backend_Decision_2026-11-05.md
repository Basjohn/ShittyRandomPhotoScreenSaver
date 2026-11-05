# Graphics backend decision: Vulkan backend vs SMP & Full Display (5 Nov 2026)

**Status:** DECIDED by the lead at the operator's request ("ideally you should render that decision"), 5 Nov 2026.
Supersedes the open question in `Future_Work.md` §2 / §2.5 and `Current_Plan.md` §0 step 4. The operator may overrule.

## Decision

1. **Next large series: SMP & Full Display**, in the order its own plans set: Expanded Visualizer
   (`Docs/Future_Work/SRPSS_Expanded_Visualizer_and_SMP_Implementation_Plans_2026-11-05.zip`, plan 01) after Waveform
   acceptance, then ShittyMusicPlayer (plan 02).
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
5. When a SPIR-V compiler is admitted to the dev tooling, a test compiles every program to SPIR-V; until then, reviews
   enforce 1-4.

## Re-decision points

Revisit this decision at Expanded Visualizer acceptance (with its full-display measurements) and whenever a trigger is
recorded. If the operator prefers to front-load the port despite the cost, the order becomes: native Vulkan core
(parity across all accepted modes first) -> Expanded Visualizer -> SMP -> new 3D modes.
