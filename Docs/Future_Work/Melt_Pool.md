> Operator-supplied concept brief, copied verbatim from `references/Reactive_Liquid_Audio_Melt_Pool_Concept_and_Architecture.zip` (local, git-ignored) on 2026-10-25 so the plan can
> link it. The mock image(s) (Reactive_Liquid_Audio_Melt_Pool_Low_High_Concept.png) stay in that package. Sequencing lives in `Current_Plan.md` §7.

# SRPSS | Reactive Liquid / Audio Melt Pool

**Status:** proposed Visualizer concept and architecture/acceptance brief. **Not implemented, not accepted, not an instruction to modify the repo or its current plan.**

**Supplied mock:** `Reactive_Liquid_Audio_Melt_Pool_Low_High_Concept.png` (1672 × 941). This is the specific two-panel **REACTIVE LIQUID / AUDIO MELT POOL** illustration with a dark concrete chamber, low-react continuous molten pool at left and high-react tall pressure peaks at right. It is an *art direction target*, not proof that the illustrated lighting, peak shape, or performance has been implemented.

**Priority:** Give the new mode its own material and behaviour. Do not reopen, replace, regress, or borrow artistic authority from accepted Neon Lake.

## 1. Non-negotiable scene identity

This is **a complete, bounded 3D scene viewed inside the usual fixed Visualizer card**, not an isolated animated surface pasted over a photograph:

- **Centre:** one heavy, continuous, reflective and emissive *viscous molten/gel liquid body*, contained in a defined shallow architectural well. Its body retains volume/continuity and substantial apparent weight at both low and high musical response.
- **Surrounding concrete is part of the mode.** The concrete rim/retaining lip, slightly wet floor slabs, bevels/joins, contact regions, and adjacent ground are **actual static 3D geometry**, with real depth, correct occlusion, roughness and lighting. The well has a believable physical boundary: liquid cannot spill silently through the curb or hover unsupported.
- **Background is part of the mode.** The dark chamber's distant walls, vertical recesses or columns, wall/floor junctions, stationary practical lamps and ambient darkness are **actual 3D scene elements**. These are not optional wallpaper layers and must remain convincingly situated under camera movement, with proper parallax, perspective, clipping and lighting.
- **Lighting:** stable authored cool/warm scene sources and restrained atmosphere, with bright accents caused by the fluid's emission, specular response and real geometric displacement. Light from the pool may contribute to visible concrete, but the architecture does **not** change colour, structure or placement when the music gets loud.
- **Framing:** the pool must remain the subject, while enough concrete surround and background stays visible to establish a real place and scale. Avoid cropping away the environmental scene just to make the water fill a card.
- **Same scene across low/high:** identical camera/view pose, fixed surrounding geometry, fixed light placements, background, material family and scene composition. Only the reactive medium and its direct lighting/reflection consequences evolve.

Treat concrete, architecture, and lights as **required scene content and render responsibilities**, not decorative extras to add if GPU headroom remains.

## 2. The mock's intended low/high behaviour

| Element | Low react | High react | Invariant |
| --- | --- | --- | --- |
| Main medium | Glossy, slowly moving liquid with shallow rounded mounds | Broad pressure ridges, pronounced columns and folding/slumping peaks | One connected viscous mass, same container and material |
| Motion | Long, damped undulations and subtle inward return | Rapid but heavy lifting, travelling deformations and delayed collapse | Momentum and continuity, never teleporting vertices |
| Crests | Restrained height and curvature | Large, smooth peaks with visible silhouettes, not just glowing bright spots | Valid mesh, normals and bounded displacement |
| Ripples | Sparse, slow waves | Stronger overlapping waves around displaced mass | Waves are a secondary expression of the same fluid |
| Ejection | None or extremely rare | A few brief, small droplets/splashes on strong hits | Droplets accent the main surface, not a replacement particle show |
| Glow/reflection | Subdued cool/hot threads and readable specular | Amplified emissive strands and distorted reflected chamber lights | Same palette and authored stationary light positions |
| Concrete/background | Present, readable and mostly dark | Exactly the same architecture, now potentially more illuminated by the pool | No architectural transformation or surprise new props |

The mock exaggerates the tall peak for artistic readability. Its exact height/shape is **not promised by a basic heightfield**; that must be proved on rendered pixels at real card sizes before accepting the full target.

## 3. What makes this **different from Neon Lake Basin's water**

This separation is an admission gate, not merely different names, colours, or shaders.

| Dimension | Neon Lake Basin | Reactive Liquid / Audio Melt Pool |
| --- | --- | --- |
| **Primary identity** | Landscape, skyline, horizon, authored raised terrain and regions classified as water | A **contained, heavy, deliberately viscous molten material** inside an architectural chamber |
| **Geometry ownership** | Authored basin/terrain heightfield, its land/water classification, coastline and long-reaching horizon | Dedicated **liquid-only dynamic surface** with a fixed concrete vessel; no land-vs-water map or landscape horizon |
| **Motion** | Travelling water crests/ripples, lake and shoreline behaviour within the existing terrain scene | Pressure lift, viscous flow, surface-tension-like pull, delayed recoil, bulky local folds and slumping peaks |
| **Artistic signal** | Terrain/sky/water illumination and musical water waves within a neon landscape | The **mass, weight and shape of one material** are the music-driven subject |
| **Camera & surroundings** | Landscape camera framing toward terrain, water, skyline and sky | Shared framed-camera system specialized to a **bounded chamber and physical pool**; concrete surround and background are real 3D |
| **Surface response** | Water reflection, ripples and terrain/water boundary presentation | Thick, glossy gel/molten-metal feel; strong evolving silhouette, normals, pressure deformation and light distortion |
| **Peak response** | Water crest/ripple dynamics | Physically legible tall columns, bending peaks and **heavy recoil**, with strictly secondary detached droplets |
| **Authoring** | Existing terrain brush and Neon-specific water settings | Pool boundary/material, pressure field, viscosity/damping, displacement and a static room/well description |
| **Failure if confused** | N/A | If it looks or behaves like Neon Lake's water with a new palette, **reject the new mode** |

**Share the renderer, geometry/math helpers, framing, post-process and low-level surface/normal code where useful. Do not share artistic behaviour or force the melt solver into Neon Lake's terrain/water classification, terrain editor, authored presets, settings state or logical reaction implementation.** Existing Neon Lake materials, water semantics and accepted presets remain untouched.

## 4. Actual SRPSS architecture: reuse before adding

Repository contracts to consult before work (read-only sources for this brief):

- `Spec.md` — Shared 3D rendering foundation, canonical clock, laziness and SDR presentation.
- `Docs/Reference/Visualizer_Reference.md` §16 — 3D Visualizers and framed physical camera.
- `Docs/Reference/Scene3D_Resources.md` — `MeshResources`, `SceneTarget`, stream ring/compute, depth/OIT/optics facilities and teardown.
- `Docs/Reference/Neon_Lake_Basin.md` — accepted landscape/terrain/water behaviour that this mode must **not** replace or copy.
- `Future_Work.md` — Reactive Liquid / Audio Melt Pool explicitly proposes **bounded 2D/2.5D height+velocity or deformable sheet**, and explicitly discourages restarting the rejected SDF path or jumping into full 3D SPH without measured cause.

### 4.1 Sole 3D rendering and presentation authority

- Reuse SRPSS's **existing Qt Quick + OpenGL 4.6 Scene3D substrate** and lazy mode renderer. No second GL window, private compositor, scene clock, background GPU service, Qt widget/QPixmap fallback or permanent scene engine.
- Reuse `rendering/quick/scene3d/` concepts such as `MeshResources`, `SceneTarget`, depth/state restoration, material/lighting helpers, optional HDR **intermediate** colour that resolves to canonical **SDR output**, and shared bloom/quality machinery where applicable.
- Mode owns only its dynamic liquid state, static scene description, authored material and relevant GL resources; the shared Visualizer lifecycle owns creation/retirement and normal presentation.
- Use the existing audio analysis and `VisualizerLogicalRuntime` clock. Simulation advances from the accepted logical snapshot, not from `render()` timing, `frameSwapped`, ad hoc timers, frame-rate-dependent physics or another DSP service.

### 4.2 **Shared 3D framed system and 3D framed camera: mandatory**

- Register as a **framed/card-interior 3D Visualizer** with a stable card/border; **camera moves inside the card** and never manipulates the outer widget's CUSTOM placement.
- Opt into the canonical framed-camera descriptor/configuration (`framed_camera="module:SPEC"` or the current canonical equivalent). Reuse `core/settings/framed_camera.py` and the shared framing/interaction owner, **not** a mode-private camera, view-pose persistence mechanism or navigation timer.
- Reuse the shared 3D Camera Position editor and physical camera controls, including orbit, pan, dolly, FOV, reset and keyboard/drag gestures already provided by the framed substrate. The pool mode declares only its own safe pivot, eye limits, floor/ceiling/wall collision constraints, initial view and fit.
- The camera must genuinely orbit through a **3D environment**: concrete lip must occlude appropriate portions of the liquid, wall and lights exhibit parallax, highlights/reflections change with viewpoint, and the pool remains a real 3D surface rather than a flat camera-facing plane.
- Respect near plane, camera-to-pool proximity, card clipping, mixed DPI, wide/tall cards and reset. Do not allow travel beneath the floor, inside a wall, or to camera poses from which the intended subject cannot be sensibly framed without clear bounds.
- Camera presentation state is **separate from mutable operator-authored artistic presets** and Edit/CUSTOM geometry, following existing SRPSS framed camera rules.

### 4.3 Static 3D scene geometry and materials: mandatory

Create or consume bounded static meshes for a **real chamber**:

1. Concrete well/retaining ring, inner lip and floor opening aligned with the exact liquid footprint.
2. Outer slab or floor with visibly separate concrete roughness, seams, bevels and contact shading.
3. Rear walls, pillars/recesses and geometric depth, even if largely subdued in shadow.
4. Fixed authored light positions, coherent ambient and reflections. Where physically possible, luminous fluid influences nearby architecture in a bounded, cost-measured fashion.
5. One scene camera and depth buffer shared with the liquid and optional droplets, ensuring correct near/far occlusion and self-occlusion.

Static geometry must be retained and reused, not rebuilt each musical frame. A style may simplify distant geometry on lower quality tiers, **never reduce the scene to only the liquid or paste a flat background**. The full environment must be visually intentional at low reactivity.

### 4.4 Liquid simulation: bounded and primarily 2.5D

**Recommended first accepted technical foundation:** a fixed-resolution **height + velocity** (or height + momentum/flow) grid constrained to the pool footprint, with coherent damping, broad/near-field force kernels and propagation. Compute/SSBO or ping-pong texture simulation in OpenGL 4.6 is valid; the simplest measured correct route wins.

- A short-lived musical impulse injects **pressure / vertical momentum** over a spatial footprint, not arbitrary instantaneous reshaping of every vertex.
- Use physically suggestive inertia, viscous damping and return-to-rest. Maintain temporal continuity on both growing and falling audio; avoid autonomous pulsing under silence.
- Use area/height constraints or a practical bounded displacement budget to avoid perpetual growth, negative thickness, exploding velocity, unbounded peaks and obvious material disappearing/appearing.
- Reconstruct normals from *the actual displaced surface*. Height response must create **geometric silhouettes**, not merely normal-map or brightness tricks.
- Drive the render mesh at a stable bounded tessellation/LOD. Avoid CPU-per-vertex updates every frame if measured costly; use shared stream/compute seam and shader displacement where appropriate.
- **Important geometry limitation:** a single-valued heightfield cannot form real undercuts, overhanging necks, self-crossing liquid, or detached spouts. The target's smoother peaks can be approached with steep, rounded displacements. If approved art genuinely requires mushrooming necks/overhangs, add a **small opt-in deformable sheet/peak mesh primitive** and measure it separately. Do not quietly claim the basic 2.5D pass reproduces all shapes shown.
- Detached splash droplets are a separate bounded, **transient** instanced population; do not turn the connected liquid into freely spawning particles.
- Never default to full SPH, particle-to-mesh fluid reconstruction, another SDF pipeline or volumetric fluid simulation. Require operator approval and measured concrete insufficiency before proposing them.

### 4.5 Fluid shading and reflected environment

- Continuously connected liquid material with controlled Fresnel/specular, broad glossy reflections, coloured emission **within** a dark heavier core, and coherent normals at crests. Make shape visible without depending exclusively on bloom.
- Choose a bounded reflection method with pixel evidence: environment probes/scene capture or an optional tiered planar/mirror contribution if justified. Screen-space-only approximations must not invent impossible reflections or collapse on camera movement. Do not promise path-traced caustics or free full-scene dynamic GI.
- Static concrete has its **own** roughness and reflections (at most subtly wet). Room lights and pool glow must not accidentally make the concrete appear to be molten fluid.
- Reuse `SceneTarget` colour/depth/post facilities, correct blend/depth behaviour for droplets, GL state restoration and available tier policy. Bloom/glow must not wash out geometry or make a uniform white pool.
- No HDR swapchain or HDR output mode; any higher precision targets are internal implementation details.

### 4.6 Audio-to-material behaviour, not music-driven scene swaps

Suggested starting channels (exact ranges, smoothing and authored values remain operator-controlled):

| Input | Material response | Validation cue |
| --- | --- | --- |
| Broad/low energy | Large, slow pressure swell and pooled-mass elevation | The **whole liquid body** feels heavier and rises/falls without jumping |
| Mids | Multiple travelling deformations, shear-like movement and local folds | Motion propagates across the surface and interacts, not random independent peaks |
| Highs | Fine ripples, sharp specular accents, subdued small surface shimmer | Small details appear while the main mass remains readable |
| Transient/onsets | Local pressure kick with a rising crest; optional handful of droplets | Strong onset causes a **timed mechanical event**, then heavy recoil |
| Sustain/release | Continued pressure followed by damped settling | Gradual return through intermediate geometry; no stuck max state |

Audio response should be demonstrable using recorded live-analysis lanes and matched quiet→loud→quiet clips. Do not hide broken response by cranking an undocumented floor, an autonomous sine oscillator, random time-driven choreography, camera shake, flashing room lights or ever-rising particle count.

## 5. Settings and art authority

Keep a concise, independently authored, **mutable** settings/preset surface within canonical typed Visualizer Settings:

- **Pool / Medium:** footprint/shape only where supported, apparent fill, material style, viscosity, damping, crest/peak limits.
- **Motion / Reactivity:** overall sensitivity, bass-body, mid-wave, high-detail and transient/impact response with appropriate ranges and smoothing.
- **Material:** core colour, emission tint/strength, reflectivity, roughness, edge treatment and limited bloom influence.
- **Droplets:** enable/density/size/lifetime and onset threshold; default restrained rather than defining the look.
- **Scene:** concrete and background art/material/light palette and visibility limits; the surrounding chamber is **always part of the mode**, not a feature that disappears under normal settings.
- **Camera:** use the **existing shared framed-camera** surface and editor, never a replacement widget or new persistence owner.
- **Quality:** reflect the canonical 3D quality policy (`Auto / High / Balanced / Performance / KAK`), with opt-in optional reflection/droplet cost, not a second quality authority.

Operator-created presets are always freely editable. Tests may assert contracts, schemas and round-trips using **test-owned values** but must not freeze the operator's chosen preset materials, colours, camera values, or sample counts as artistic goldens.

## 6. Hard gates: no unearned completion

All of these are proposed **[ ] open gates**; no implementation or visual acceptance is implied by this package.

### [ ] H01 — Correct identity, no Neon Lake clone
Operator sees a **thick, viscous, physically connected molten/gel body** in a concrete architectural well, with visible mass, pressure rises and recoil. It must not read as Neon Lake water with a darker shader/palette.

### [ ] H02 — **Real surrounding concrete and real 3D background**
Render the well, lip, floor, walls/recesses, and fixed lighting with the same 3D scene depth as the pool. Native angled camera captures must prove **parallax, occlusion, correct floor/wall joints, lip contact** and consistent reflection/light response. A flat painted backdrop or only an isolated plane is a rejection.

### [ ] H03 — Canonical framed 3D architecture
Card remains stationary; shared framed-camera orbit/pan/dolly/FOV/flight/reset and Camera Position editor work, safe bounded movement and persistence work, and mode-specific bounds are declared without a second navigation or geometry owner.

### [ ] H04 — Same exact scene in low/high comparison
Capture two logical-time states with **identical scene, camera, geometry, authored lamp placements, environment and palette**. Only fluid height/velocity/deformation/droplets and physically resulting illumination/reflection may differ. No hidden scene swaps.

### [ ] H05 — Continuous liquid geometry
Per-frame/native renders show valid watertight-looking connection across the pool, reasonable footprint boundaries, coherent depth/normals and no breaks, holes, underside inversions, z-fighting, clipping through concrete or boundary leaks.

### [ ] H06 — Real crest displacement and return
High react gives clearly **geometric** peaks and folds with visible silhouettes, not glow-only changes. Each peak builds, bends/slumps, and returns with finite speed and damping. Abrupt changes, permanent held maxima and broken tip geometry fail. If the exact mock requires more than a heightfield can support, record and close that gap **before** claiming full fidelity.

### [ ] H07 — Musical mapping actually reaches native pixels
Recorded input → canonical analysis snapshot → stable logical field → real GPU state/uniform/mesh → native pixels is demonstrated independently for body lift, propagation, mids, surface detail and onsets. Test quiet→loud→quiet and long sustained sections; verify negative/downward response as well as attack.

### [ ] H08 — Low-react beauty and high-react power
Low state is composed, material-rich and readable, not an empty black slab; high state clearly transforms mass/shape without turning into noise, sparks or a white bloom wash. Operator/visual-agent acceptance is required for both.

### [ ] H09 — Stable heavy material identity and lighting
Core viscosity/material look survives at all camera views; static chamber looks like concrete, not another liquid; warm/cool reflections remain coherent under movement. No glowing line painted at impossible contact edges just to match a still image.

### [ ] H10 — Bounded, tiered and measured cost
Fixed maximum field cells, peak displacement, grid/morph vertices, detached droplet count and reflection samples. Measure full visualizer frame CPU/GPU and p50/p90, high react and low react, at small/large/mixed-DPR card sizes and real dual-display use. Add a tier reduction or simplify optional effects before exceeding practical refresh budgets; no magic fixed FPS assertion based on an offline still.

### [ ] H11 — Zero-cost dormancy and reliable retirement
Inactive mode performs no solver ticks, particle updates, offscreen rendering or persistent effect-specific GPU work; resources are lazily created, reused and retired correctly on mode switch, Settings open/close, display changes and scene-graph teardown. No persistent additional GL authority.

### [ ] H12 — Native framed UI + preset authoring
Use canonical registration, typed Settings, Custom and existing preset system. Verify save/load/reset and camera view separation without overwriting any mutable authored preset. Operator can change colour/material/response without migration resetting aesthetic choices.

### [ ] H13 — Source correctness and regression boundary
Do not modify Neon Lake's water classification/terrain, landscape editor, presets or accepted mode merely to share code. Generalize only independently tested useful primitives. Follow the project's no-environment-variable test configuration rule; add only durable behaviour/data/cost tests, not UI-style or current-preset-value goldens.

### [ ] H14 — Image-to-runtime disclosure
For each key mock feature (tall molten peaks, surface tension folds, viscous recoil, reflective concrete, background chamber, limited droplets), show a **native capture** and state whether it is accepted, partial `[~]`, or missing `[ ]`. No claim that "OpenGL 4.6 can do it" substitutes for an implemented, measured, visually checked result.

## 7. Recommended staged implementation / stop points

1. **Static 3D chamber + shared framed camera.** Implement real concrete and background geometry, fixed lighting, reliable angle/size tests. No fluid needed yet. **Stop** unless environment and camera look believable.
2. **Connected viscous surface.** Add 2.5D grid, bounded height/velocity, contact boundaries, real normals, damped recoil and low-react beauty. **Stop** unless the connected material reads correctly at rest and in motion.
3. **Musical pressure and pronounced peaks.** Wire recorded bass/mid/transients into distinct impulse types; demand tall geometric silhouette with smooth recovery and correct return. Determine whether a small higher-order deformable peak mesh is necessary rather than assuming 2.5D can match any silhouette.
4. **Material and environment interplay.** Reflections, constrained emission, light on concrete and safe bloom, with native all-angle proof. Optional features are tiered and measured.
5. **Optional accent droplets, settings and acceptance.** Keep particle count modest; prove dormancy, crashes/retirement, frame costs and same-scene low/high native captures. Do not conclude artistic acceptance without operator sign-off.

**Out of scope unless separately admitted:** full 3D SPH, novel SDF solver, world-scale water simulation, replacing the accepted Neon Lake implementation, an independently owned camera, separate rendering engines, physically exact ray-traced optics and mutable scenery that dances with the music.

---

**Bottom line:** This mode is justified only if it becomes **a sculpted heavy liquid material inside a complete real 3D concrete chamber** that moves under music with pressure, viscosity and recoil. The shared 3D framed camera and scene infrastructure must remain authoritative, and Neon Lake's authored terrain/water behaviour must remain distinct and untouched.
