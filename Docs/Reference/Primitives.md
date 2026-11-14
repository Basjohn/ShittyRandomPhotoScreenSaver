# Rendering primitives and shared services (catalogue)

Written 12 Nov 2026 from `Current_Plan.md` item 8b (cited below by item and box name, never by line), the decisions
document `Docs/Future_Work/Native_Core_P3_Decisions.md` ("Decisions"), `Docs/Reference/Scene3D_Resources.md`
("Resources"), `Docs/Reference/Transitions.md` ("Lessons" = its section "3D foundation lessons", line 149) and the
code. Anything not checked against code or a document is marked **unverified**. This file is the catalogue and the
"what is it for, who uses it, what must you know" view; `Scene3D_Resources.md` keeps the resource-level detail
(allocation sizes, state restoration, measured figures) and is not repeated here. Presets are authored content and
are never named here.

## 1. What counts as a primitive, and the rules that bind them

A **primitive** here is a reusable GPU building block or service that has its own proof harness (an off-screen scene,
a test with a CPU mirror, or a lab) and that more than one mode or transition can take, or could. A **mode's own
code** is what a single Visualizer mode or transition draws with its own shaders and state: its program sources
(`rendering/gl_programs/<mode>_program.py`), its renderer (`rendering/quick/visualizer/implementations/`,
`rendering/quick/transitions/implementations/`) and anything in `scene3d/` that only one mode imports. The
borderline cases are listed in section 3, entry E26.

Rules (all from item 8b's "Standing rules of this item"):

1. **Proved on its own off-screen harness** (item 8b, standing rules): GPU time median and p90, lazy creation, no work when
   dormant, clean retirement. A primitive never becomes a second renderer, clock or camera. Read the Lessons before a
   3D slice and append after it.
2. **High potential is built without a consumer; low potential only when a consumer is admitted** (item 8b, standing rules;
   operator, 12 Nov: "High potential primitives should be built regardless, low potential only when a consumer. We
   can always improve."). The lead classifies and writes the class at each item. The class is given below where the
   plan gives it; where it gives none the entry says "no class stated".
3. **No new 3D primitive in the Python OpenGL renderer** unless an open defect needs it; new modes are built on the
   native core only (item 8b, standing rules).
4. **A landed primitive gets one showcase WebP and a "what this makes possible" note** (item 8b, standing rules). The plan names
   `Scene3D_Resources.md` as the place for the note; that file now points here, and the note goes into the entry of
   this catalogue as well (see the open point in section 7).
5. **Dormancy at rest**: nothing allocates before a consumer warms it, nothing costs per frame at rest, everything is
   released at `park()` or retirement (Lessons line 207; `Scene3D_Resources.md` "Fixed-size scene and post-process
   allocations"). Diagnostic instrumentation is opt-in (memory: no recurring work at rest).
6. **A port is done** only with single-sampled pixel parity against the Python renderer, the Vulkan result within a
   stated tolerance, trace figures, GPU time per pass and a bounded rehearsal, and then the Python renderer is
   deleted in the same change (item 8b, standing rules, first bullet). Never two permanent renderers.
7. **A native route beside QRhi is one of D5.3's services**, wins a measurement first and ships its OpenGL twin
   (item 8b, standing rules; Decisions D5.3, line 206).
8. **Ids**: the old `S3D-n` ids map to N-ids as in section 5's table (item 8b, standing rules).

## 2. When primitive work happens

The native ladder (`Current_Plan.md` item 8b, "Order" paragraph): **N0** (decisions, contracts, proofs) and **N1** (every shader
portable, in the existing OpenGL renderer, no C++) now; then **N2** (the 2D half and Spectrum), **N2b** (the
background layer and the first full rehearsal), **N3** (the 3D substrate core, harness scenes, no mode yet). From
there three tracks, one High slot each:

- the **modes track** (N5.1, N5.4, N5.6, N5.5, N5.3; item 8b, the N5.1, N5.4, N5.6, N5.5 and N5.3 boxes);
- the **background track** (N5.2 a to h, N5.9; item 8b, the N5.2 and N5.9 boxes);
- the **primitives track** (N4's unconsumed items and N6) "whenever a High slot is free and never holds the flip"
  (item 8b, "Order" paragraph).

Then **NF** (the flip, item 8b, NF), then item 9: SMP foundations, then new modes (item 9).

**N4 items are ported just before their first consumer** (item 8b, the heading above the N4 boxes: "each ported just before its first
consumer below (the unconsumed ones on the primitives track)"). An N4 item whose consumer is on the modes or the
background track therefore moves with that consumer; an unconsumed one (the N4.c, N4.h, N4.m high-potential items,
and N4.d's wet-surface masks) runs on the primitives track. N6 runs only on the primitives track, native only.

Status today (item 8b, "State" paragraph, 14 Nov): N0's contracts decided; **N0.3, N0.6 and N0.7 proved** (D6 and D9
accepted); N1.6 merged to ratchet 24 (Neon Lake, Extruded Spectrum and Sphere in flight; Extruded Bubble's traced
glass converts at its port); **N2.1, N2.2, N2.4 and N2.6** merged and proved; **N2.3** (Spectrum's native schema and
the C++ packet reader, module ABI 5) merged and proved 14 Nov; **N2.7** (the backend owner) and its first leftovers
merged; N2.5 in flight; N2.8's Vulkan pre-check done. Every box of N2b, N3, N4, N5, NF and N6 is open; no N4 or N6
primitive exists in C++ yet (the module holds the host adapter, frame driver, composite node, GPU timer and packet
reader). `native/spike_p1` is evidence, never a shipped renderer (item 8b, N2's heading). Step by step:

| Step | State (plan, 14 Nov) | Primitive relevance |
|---|---|---|
| N0.3 conventions, three scenes | proved 12 Nov on Vulkan, OpenGL, D3D11 and D3D12 (Metal on the Watchlist) | the conventions include is proved on every backend we ship |
| N0.4 camera | decided (D5.5); remainder built with N5.4 then N5.6 (N0.4's remainder box) | one camera owner, see section 7 |
| N0.6 Vulkan device | proved; validation clean apart from Qt 6.12.0 defects A, B, D (N0.6's box) | the device the core runs on |
| N0.7 async jobs | proved; verdict "jobs for compute on this vendor, and uploads" (Decisions line 569-612) | D9 service; AMD and Intel unmeasured (N0.7's box) |
| N1 portable shaders | in flight: D4 landed; N1.6 at ratchet 24 (the 3D modes left); N1.4 include remainder and N1.8 resolve-first open (the N1 boxes) | what makes existing primitives bakeable |
| N2.1 to N2.8 | N2.1 to N2.4, N2.6 and N2.7 merged (leftover boxes open); N2.5 in flight; N2.8 open (the N2 boxes) | host adapter, frame driver, packet reader, composite, timer, rehearsal path |
| N2b: N4.a, N3.8 jobs, N5.7a/b/c | open (the N2b boxes) | fullscreen pass, job service, background layer, backdrop pyramid |
| N3.1 to N3.9 | open (the N3 boxes); there is no N3.5 in the plan (numbering skips from N3.4 to N3.6) | targets, meshes, compute, post stages, lifetime, orientation, display move |
| N4.b to N4.m | open (the N4 boxes) | ported with first consumer, or on the primitives track |
| N6.1 to N6.6 | open (the N6 boxes) | never built, native only |

## 3. Existing primitives (Python OpenGL renderer today)

Every entry: module; what it does; consumers (grepped imports, 12 Nov; modes and transitions by display name, never
by preset); harness or test; native-ladder id and potential class; notes. All are context-local, lazy, released at
`park()` or retirement, and require the validated OpenGL 4.6 context (`Scene3D_Resources.md:3-5`). Constructing one
costs nothing; the first warm or use allocates.

### E1. Scene frame and item quad
`rendering/quick/scene3d/frame.py` (pure, no GL). The frame protocol a render node supplies (viewport, logical size,
Qt's item matrix, unit quad), `item_pixel_rect` and the quarter-turn orientation helpers (`orient_visualizer_scene_frame`,
`scene_output_frame`). The item-quad vertex stage moved to `rendering/gl_programs/item_quad.py` with N1.6 (12 Nov:
`item_quad_vertex_source(block)` and `item_quad_program`, each program declaring the quad's values in its own pass
block; the loose `ITEM_QUAD_VERTEX_SOURCE` and `QUICK_TRANSITION_VERTEX_SOURCE` are gone). Consumers: nearly every
transition and Visualizer scene (`transitions/fullscreen_pass.py`, `visualizer/framed_view.py`, Beam, Blinds, Cube Turn, Disintegrate, Edge
Bloom, Capillary Bloom, Chromatic Shear, Liquid Lens, Oscilloscope, Neon Lake, Extruded Bubble, Extruded Spectrum,
Sphere, Waveform Ribbon, Page Curl, Surface Tension, VHS, Volumetric Dissolve and others). Tests:
`test_scene3d_item_pixel_rect.py`, `test_scene3d_content_orientation.py`. Native: replaced by D5.2's texture-node
composite and N3.7's orientation contract (N3.7's box). Notes: the item quad keeps "the bottom-up convention the
transition fragments were authored in" (`gl_programs/item_quad.py`); the N0.3 rule 2 (core targets top-left, Y down) puts one
flip at the substrate boundary (Decisions line 1353-1357).

### E2. Program, mesh and image-binding resources
`rendering/quick/scene3d/resources.py` (`MeshResources`, `warm_programs`, `bind_frame`, `ProgramUnavailable`,
`warm_pass_blocks`). Named programs, uniform locations, immutable DSA meshes, the image underlay and camera plane,
one `glBindTextures` per frame bind, compute programs through `compile_compute_program`, gradual warm-up entries.
Consumers: every scene3d user (also `offscreen_target.py:107`). Test: `test_scene3d_resources.py`,
`test_transition_warmup.py` (counts warm-up units). Native: N3.2 (static meshes, dynamic buffers, instancing, srb per
ring slot) and N3.6 (lifetime, warm-up). Notes: a failed program is cached and re-raised, never recompiled until
release (`resources.py:23-26`); no texture-binding cache because Qt changes inherited state (`Scene3D_Resources.md:60-64`);
`MeshResources.uniforms` caches the first uniform-name list per program (Lessons line 322).

### E3. Scene target (colour, depth, post-process attachments)
`rendering/quick/scene3d/target.py` (`SceneTarget`; 51 definitions). A multisampled colour and depth target for any
pixel rect, composited back through the item quad with no resolve blit. Opt-in attachments: RG16F velocity (motion
blur), overlay scope with emission for bloom, depth texture plus mid-scope `background()` capture, weighted-blended
OIT, HDR with an ACES tone map, and a shaft-source attachment. Consumers: Blinds, Block Spins, Crumble, Cube Turn,
Depth Cascade, Disintegrate, Exploding Tiles, Glass Shatter, Jigsaw, Membrane, Page Curl, Pixel Accretion, Volumetric
Dissolve (transitions); Oscilloscope, Neon Lake, Extruded Bubble, Extruded Spectrum, Sphere, Waveform Ribbon (modes).
Tests: `test_scene3d_target.py` (G1, G3A, shafts, scale, lifetime), `test_scene3d_dsa_targets.py`. Native: N3.1
(targets, sampled depth, background capture, one sampling-policy owner) and N3.4 (OIT, bloom, HDR as opt-in stages);
the eight composites in `target.py:125-286` keep raw `gl_FragCoord` and are never converted (D5.2 replaces them;
item 8b, N1.4's remainder). Notes: allocation rounds to 64 px; no `glBlitFramebuffer` resolves (about 0.5 ms at 1440p; Lessons line
176-177); per-sample reads (`sampler2DMS`, `gl_SampleID`) are the N1.8 resolve-first set and the one thing QRhi
cannot sample (Decisions D5.6 rows 7 and 15); the multisampled velocity attachment is the only listed use of D5.3's
formats service (N1.7's box); Waveform hard-codes 4 samples (`scene3d/waveform.py:381`) and the Oscilloscope 1
(N1.8's box); a 1-sample multisampled renderbuffer does not rasterise like a direct draw (Lessons line 178-179).

### E4. Bloom chain
`rendering/quick/scene3d/post.py` (`BloomChain`, `FULLSCREEN_VERTEX_SOURCE`, `BLOOM_PROGRAMS`). Four halvings of
emitted light then tent upsamples, RGBA16F, about a third of a full-screen pass; only emitted light glows (alpha in a
bloom target). Consumers: through `SceneTarget` (every bloom-enabled consumer in E3). The full-screen vertex source is
also used by Environment, Motion, Shafts and Trails: it is the Python seed of **N4.a** (the fullscreen pass and image
sampling, `Current_Plan.md` item 8b, N4.a's box). Test: `test_scene3d_dsa_targets.py:97`, `test_transition_warmup.py:54`. Native: N3.4.
Notes: photographs write 0 emitted light so endpoints stay exact (Lessons line 180-181).

### E5. Motion blur (velocity plus tile max)
`rendering/quick/scene3d/motion.py` (`MotionBlur`, `motion_program`). Analytic screen velocity over a shutter, a
compute tile max (one workgroup per K x K tile, K = target height / 40) and a bounded 3 x 3 neighbourhood gather;
Off compiles and dispatches nothing. Consumers: Block Spins, Crumble, Glass Shatter, Pixel Accretion (all import
`scene3d.motion` directly); Exploding Tiles also measured with it (`Scene3D_Resources.md:323-325`; no direct import). Tests: `test_scene3d_compute.py`, `test_scene3d_target.py`,
`tools/compute_pass_identity.py`. Native: **N4.i** ("five transitions", N4.i's box), N5.2d. Notes: it was the first
compute consumer because it removed passes (Scene3D_Resources "Compute seam", tile max: -14 GL calls per frame with
motion blur, byte-identical output); the barrier order is tested, not pixels (NVIDIA hid a missing barrier,
Lessons line 232-233); a target needing tiles over about 10,000 px high is a loud error.

### E6. Motion trails
`rendering/quick/scene3d/trails.py` (`MotionTrails`, `trail_program`). Ghost silhouettes at earlier moments, edge
filtered into fading light lines laid under the pieces. Consumers: Block Spins, Crumble, Exploding Tiles, Glass
Shatter, Pixel Accretion. Test: `test_scene3d_trails.py`. Native: **N4.i**. Notes: a ghost decides from its own motion
whether to draw (Lessons line 190-192).

### E7. Photo and backdrop environments
`rendering/quick/scene3d/environment.py` (`PhotoEnvironment`, `BackdropEnvironment`). A per-run, renderer-owned,
mipmapped copy of a photograph (the lent presentation texture is never modified) for blurred reflections via
`sceneEnvironment` at `sceneReflectionUv`; `BackdropEnvironment` is the Visualizer's equivalent of the displayed
photograph, once per image change. Consumers: `PhotoEnvironment`: Blinds, Block Spins, Cube Turn, Depth Cascade,
Exploding Tiles, Glass Shatter, Jigsaw, Membrane, Page Curl, Volumetric Dissolve (ten, as the plan says);
`BackdropEnvironment`: Extruded Spectrum, Sphere. Tests: `test_scene3d_environment.py`. Native: **N4.j**; N5.2c, N5.3.
Notes: look up a reflection by the reflected ray, never by screen position (Lessons line 193-195); named construction
allocates the complete mip chain; allocation or copy failure invalidates the cache identity.

### E8. Stream ring (persistently mapped)
`rendering/quick/scene3d/stream.py` (`StreamRing`). One immutable persistently mapped, fenced buffer; a payload is one
`memmove` and one `glBindBuffersRange`. Defaults: 4 slots, 16,384 bytes a slot, 4,096 held per outermost `bound`
(`stream.py:62`); a slot is reused only after its fence, never rotated inside a scope; over-capacity is a loud error.
Consumers: Extruded Spectrum, Extruded Bubble's drift solver, Oscilloscope, Neon Lake, Sphere, the ribbon primitive and
bursts, Disintegrate, Exploding Tiles, Volumetric Dissolve, and every `UniformBlock` / `PassBlocks` (E9). Test:
`test_scene3d_stream.py`. Native: one of D5.3's services ("Stream ring"), built **only if** it beats QRhi dynamic
buffers by 0.05 ms at the product's ring sizes (N3.2, N3.2's box; Decisions D8 row 8). Notes: a new transport earns its
place by removed calls, not by being modern (Lessons line 221-222); never rewrite bytes a submitted draw may still
read (line 220); `restore=False` is for scenes that own their whole frame's state (`Scene3D_Resources.md:269-282`).

### E9. Uniform blocks, pass blocks and layouts
`rendering/quick/scene3d/uniforms.py` (`UniformBlock`, `PassBlocks`, `SCENE3D_UNIFORM_BINDING = 15`) with the pure
layouts in `rendering/gl_programs/scene3d.py` (`Scene3DBlockLayout` at line 1070 per Decisions, `Scene3DStorageLayout`).
std140 and std430 declarations plus packers (and numpy dtypes). Consumers: Spectrum, Sphere (the shared
`SphereFrameBlock`), Disintegrate, Exploding Tiles, Volumetric Dissolve, and every program converted in N1.6.
Tests: `test_scene3d_uniforms.py`, `test_scene3d_stream.py`, `tools/conventions_identity.py`. Native: the Python
packer is the oracle the C++ packer is first tested against (Decisions line 1385); N1.2 and N1.3, N1.6. Notes: block
bindings 16 (compute), 17 (conventions), 18 (pass block) are reserved, 15 is the per-frame uniform block (section 7).

### E10. Compute seam and blend scopes
`rendering/quick/scene3d/compute.py` (`dispatch(groups, barriers)`, `bound_image`, `DispatchBlocks`,
`COMPUTE_BLOCK_BINDING = 16`) and `scene3d/passes.py` (`blend_scope`). The writer issues the barrier its reader needs;
image units are scoped and handed back; no queue, scheduler, worker, readback or polling. Consumers: Edge Field, Fog
Volume, Floor Give and Waveform Field, Motion, Population, Propagation Field, the drift solver. Tests:
`test_scene3d_compute.py`, `tools/compute_pass_identity.py` (`record`, `compare`, `paired`). Native: **N3.3**
(dispatch only when there is new work, barriers from srb access types, no product readback) and D9 where a job is
admitted. Notes: compute earns a stage only where it removes passes, targets or calls (Lessons lines 225-227);
storage-image formats are the shipped backends' (SPIR-V, GLSL 430, HLSL 5.0, MSL 1.2: a scalar half-float image is
`r16f`); `blend_scope` is used by Bloom, Trails, Particles, Shadows, Disintegrate, Jigsaw and Volumetric Dissolve.

### E11. Compacted populations
`rendering/quick/scene3d/population.py` (`CompactedPopulation`). Three dispatches (count, scan, scatter) and one
`glDrawArraysIndirect`; no readback; slots follow id order (prefix sum, not atomic append), so blending order is
stable; fixed capacity, five immutable buffers. Consumers: **Disintegrate and Volumetric Dissolve only**. Test:
`test_scene3d_population.py` (exact against a CPU reference from 1 to 300,000 members). Native: **N4.c, high
potential, built without a consumer** (N4.c's box): both transitions port 1:1 on QRhi's own `drawIndirect` (Qt 6.12);
"draw the maximum, cull in the vertex shader" only for a backend without `QRhi::DrawIndirect`; the harness runs at one
million sprites (Decisions D8 row 7). Notes: measured against per-vertex evaluation, compaction saved 29 to 49 percent
GPU at a fixed cost of about 0.1 ms CPU submit (about 20 calls); the two paths are close in total on the development
GPU (`Scene3D_Resources.md` "Compacted GPU populations", 4 sizes); compact only when the pool is large (Lessons lines
318-319); a population's state is one `vec4` (line 335).

### E12. Ribbon, strip and event sparks
`rendering/quick/scene3d/ribbon.py` (`RibbonPrimitive`, `ribbon_grade`), `ribbon_bursts.py` (`RibbonBurstRenderer`),
with `core/ribbon_geometry.py`, `core/ribbon_frames.py`, `core/ribbon_packet.py` (bounded absolute-coordinate history,
centripetal interpolation, camera-facing width) and the GLSL in `rendering/gl_programs/ribbon.py`. An oriented SSBO
strip with a body pass (inside `transparent_writes`) and a light pass (inside `emission_writes`), strays, cohorts and
sparks. Consumer: Waveform Ribbon (through `scene3d/waveform.py`). Tests: `test_ribbon_gpu.py`,
`test_ribbon_material.py`, `test_ribbon_bursts.py`, `test_ribbon_continuation*.py`, `tools/labs/ribbon_material_probe.py`.
Native: **N4.b** (S3D-1; N4.b's box), ported with Waveform Ribbon (N5.4). No class stated. Notes: OIT, defocus,
broader normal and precision proof and scene composition "remain open" in `Scene3D_Resources.md:611-619`; history
carried shape needs band-limiting and monotone-cubic knot interpolation (Lessons lines 264-268); thin emissive sheets
scale light by path length and widen sub-pixel stretches (lines 271-275); clamp interpolants before `exp` (lines
261-263); hash per-object constants only through `flat` varyings (lines 276-278). Path reference:
`Docs/Reference/Ribbon_Path.md`.

### E13. Planar reflection and rough receivers
`rendering/quick/scene3d/reflection.py` (`PlanarReflection`) with `rendering/gl_programs/reflection.py`
(`mirror_view`, anisotropic receiver sampling, contact hardening). One lazily allocated mipmapped RGBA16F target and
depth renderbuffer; the receiver integrates a roughness footprint (long streaks split into up to eight abutting
Gaussian-weighted segments); emitters opt in by writing luminance times world height into alpha. Consumer: Waveform
Ribbon (floor). Test: `test_scene3d_reflection.py`. Native: **N4.d, planar reflections and rough receivers, wet-surface
masks (the plan calls the item "high potential", N4.d's box)**. Notes: the primitive does **not** yet clip geometry
crossing the plane; it is "a bounded directional filter, not a full microfacet ray-traced reflection"; the lab
measured 0.162 to 0.222 ms median for the wet floor draw at 820 x 718 on an RTX 4090 with an unexplained spiky p90;
consumer inclusion, clipping, resize, failure-path and whole-scene cost remain open in the Waveform lab plan
(`Scene3D_Resources.md:197-205`). Neon Lake's water reflection is analytic in its own basin shader and needs none of
this (N4.d's box).

### E14. Scene probe
`rendering/quick/scene3d/probe.py` (`SceneProbe`). One RGBA16F cube with a full mip chain, rendered in six faces and
pre-filtered over a Gaussian cone (32 taps, across face edges); GLSL `sceneProbe(probe, direction, blur, levels)`.
Consumer: Extruded Bubble. Test: `test_scene3d_probe.py`. Native: **N4.d** ("the scene probe (Extruded Bubble)");
the six-face draw is one geometry-shader `gl_Layer` draw today, which QRhi marks experimental, so the core draws six
draws per level (Decisions D5.6 row 18). Notes: probe cost was 0.18 ms GPU in the EB lab; nothing allocates after the
first capture; `warm()` allocates on a hidden frame.

### E15. Fog volume and fog march
`rendering/quick/scene3d/fog_volume.py` (`FogVolume`, `FogMarch`) with `rendering/gl_programs/fog_volume.py` and
`mist.py`. `FogVolume`: a camera's coarse froxel grid evaluated from a consumer's `fogMedium` compute source into an
RGBA16F 3D texture (plus an R16F steady share) that the mist functions sample. `FogMarch`: a reduced-resolution
detail march that erodes the non-steady coverage with a baked 3D noise. Consumers: `FogVolume`: Waveform Ribbon;
**`FogMarch` has no production consumer** (only `tools/compute_pass_identity.py:484`, `tests/test_scene3d_fog_volume.py`
use it), as the plan says (N4.f2's box). Test: `test_scene3d_fog_volume.py`. Native: **N4.f1** (the fog volume port, before N5.4) and **N4.f2** (reduced-resolution
volumes and mixed-resolution soft layers, "after N5.6, before Expanded Visualizer M6"; N4.f1 and N4.f2's boxes) and the base of
**N6.3**. Notes: the march is "too costly at full size in the Python path" (0.4 to 1.2 ms main march, 0.2 to 0.7 ms
mirrored, at 820 x 718 on an RTX 4090; `Scene3D_Resources.md:167-173`); it has open lifecycle defects in the plan
(raw `glDeleteProgram` that never hands back a conventions hold, `scene3d/fog_volume.py:424`, `Current_Plan.md` item 8b, N1.4's remainder);
the steady share must never be eroded; Lessons "Volume mist" (lines 290-301).

### E16. Edge field
`rendering/quick/scene3d/edge_field.py` (`EdgeField` plus CPU mirrors `edge_field_reference`). Per run and photograph:
luma copy, binomial blurs, Sobel ridges with non-maximum suppression, jump flooding, resolve; a distance-and-strength
field; seven dispatches plus one per flood step; six textures at 768 px on the longer side (about 14.6 MiB at 16:9).
Consumer: Edge Bloom only (`edge_bloom.py:16`). Tests: `test_qtquick_edge_bloom.py`, `tools/compute_pass_identity.py`.
Native: **N4.g** (Edge Bloom and Capillary Bloom only), N5.2g, and the heavy job of D9's proof (the 4K build is 20 to
31 ms on Qt's queue in the frame, 0 late frames as a job; Decisions lines 578-584). No class stated. Notes: seeded
differently it could serve organic fills (`Scene3D_Resources.md:391-392`); the flood buffers were widened from RG32F
to RGBA32F by N1.7 (bit-identical; QRhi lacks RG formats).

### E17. Propagation field
`rendering/quick/scene3d/propagation_field.py` (`PropagationField`, `propagation_reference`). Cheapest cost-weighted
arrival from a few sources over a consumer's `propagationCost`; 192 in-place relaxation passes on a 16-neighbour
stencil and a reduction; three R32F textures at 256 px. Consumer: Capillary Bloom only. Test:
`test_propagation_field.py`. Native: **N4.g**, N5.2g (the first transition preparation run as an async job, D9
consumer class a, N5.2g's box). No class stated. Notes: fingering needs the true cheapest way, a geodesic arrival map,
not a point or line average (Lessons lines 366-368).

### E18. Sphere impostors, optics and water
`rendering/gl_programs/scene3d_spheres.py`, `scene3d_optics.py`, `scene3d_water.py`, `scene3d_sky.py` (import-safe
GLSL plus CPU mirrors, no resources). Exact sphere silhouettes from one quad per instance with true surface depth;
exact Fresnel, thin film, sphere refraction and hollow-sphere light-path tracing (up to eight paths); deep-water
waves, caustics, Snell's window and medium absorption. Consumers: Extruded Bubble (`extruded_bubble_program.py:13-15`,
`extruded_bubble_scene.py:33`); the sky functions by Neon Lake (`neon_celestial.py:11`). Tests:
`test_scene3d_spheres.py`, `test_scene3d_spheres_mirrors.py`, `test_scene3d_optics_water.py`, `test_scene3d_sky.py`,
`test_scene3d_glsl_mirrors.py`. Native: **N4.g** ("sphere impostors, shared optics and underwater light (Extruded
Bubble)"). No class stated. Notes: rough transmission and dispersion were evaluated and recorded unnecessary for the
target (`Scene3D_Resources.md:511`); `scene3d_spheres.py:197` assumes OpenGL's -1..1 depth and is an open side defect
(`Current_Plan.md` item 8b, N1.4's remainder); the vertex-stage variant compiles out the `fwidth` coverage overload because strict
compilers reject derivatives in a vertex shader.

### E19. Defocus layer
`rendering/quick/scene3d/defocus.py` (`DefocusLayer`). Depth of field for objects near the lens: an RGBA16F colour
plus alpha-weighted circle of confusion, a 64-tap golden-angle gather (light conserved) and an optional highlight
split into instanced discs. Consumer: Extruded Bubble. Test: `test_scene3d_defocus.py`. Native: N3.4 ("the defocus
layer") and N5.6. No class stated. Notes: the EB abyss near defocus measured 3.3 ms of its GPU budget (largely the
near shells drawn into the layer; `Scene3D_Resources.md:529-533`); masks are per draw-buffer index (a masked emission
index once dropped every circle); the RG16F circle storage was widened by N1.7.

### E20. Light shafts
`rendering/quick/scene3d/shafts.py` (`LightShafts`, `ShaftLight`) through `SceneTarget(shafts=True)`: a half-size
R16F downsample and two 16-tap radial gathers (256 effective taps). Consumer: Neon Lake. Test:
`test_scene3d_target.py` (shafts). Native: **N4.k, high potential, "ported with Extruded Bubble, then used by Neon
Lake"** (N4.k's box): Extruded Bubble has its **own second implementation** of shafts that the item merges onto one
owner. Notes: the shaft source downsample reads `sampler2DMS` (an N1.8 resolve-first use, `Current_Plan.md` item 8b, N1.8's box).

### E21. Shadows (planar and directional silhouettes)
`rendering/quick/scene3d/shadows.py` (`draw_planar_shadows`, `directional_shadow_vector`, `directional_shadow_pass`,
`extruded_shadow_length`). The photograph-darkening MIN-blended planar shadow of the 3D transitions and the target-free
directional silhouette of the Extruded Spectrum. Consumers: Exploding Tiles (planar), Extruded Spectrum (directional);
Sphere has its own projected-shadow pass in its program and renderer. Tests: `test_extruded_shadow_reach.py`,
`test_qtquick_extruded_spectrum.py`. Native: **N4.l** (silhouette shadows as one shared primitive, distinct from N4.h)
and **N4.h** (a real fitted shadow map, **high potential: built without a consumer**, "not a revival of the rejected
Extruded cast shadows, and no mode turns it on without its own review"; N4.h's box). Notes: the E8-era Extruded cast
shadow receiver is rejected and stays disabled (R-120, R-121 audits `Docs/Audits/`, R-125 to R-128
`Docs/Historical_Bugs/R-125_to_R-128_Extruded_Cast_Shadow_Failure.md`; `Scene3D_Resources.md:12-14`); G2 "none" in the
capability inventory, no fitted depth-map foundation exists (N4.h's box).

### E22. Bendable grid
`rendering/quick/scene3d/grid.py` (`draw_grid`) with `scene3d_grid_vertex_source`, `scene3d_grid_vertices` in
`gl_programs/scene3d.py`. A bendable grid surface drawn around an effect's displacement. Consumers: Membrane, Page
Curl; Neon Lake draws its own lattice from `scene3d_grid_vertices`. Test: `test_scene3d_grid.py`. Native: **N4.l**
("the bendable grid (Membrane, Page Curl)"); N4.e's heightfield mesh is "the grid a dynamic surface field will share".

### E23. Shared particle pass
`rendering/quick/scene3d/particles.py` (`draw_particles`, `particle_budget`). One instanced camera-facing streak or
soft-sprite pass added as light, depth untouched, with the per-tier budget. Consumers: Exploding Tiles' sparks;
`RibbonBurstRenderer` (E12) draws Waveform's event sparks through it. Native: part of N4.l (Exploding Tiles'
particles) and of N3.2 (instanced quads in place of `gl_PointSize`). Notes: point sprites are a restructured draw, not
a missing feature (Decisions D5.6 row 11).

### E24. Heightfields and terrain sampling
`rendering/quick/scene3d/heightfield.py` (`HeightfieldTexture`: one lazy immutable R32F or two-component texture,
upload on change) with `rendering/gl_programs/heightfield.py`, `heightfield_glsl.py`, `heightfield_volume_glsl.py`
(cubic B-spline surface sampling, curved wire coordinates, bounded single-scattering volume over the same sampler:
12, 8, 6 or 4 world-ray steps). Consumer: Neon Lake (`shockwave_grid.py:38,104,112`; the volume in
`neon_lake_basin_program.py:23`). Test: `test_scene3d_heightfield.py`. Native: **N4.e** (the authored heightfield
resource; Neon Lake's tile-refined basin; the grid a dynamic surface field shares). No class stated. Notes: no shared
simulation, clock or global texture cache; the volume is "not a shadow map or a fluid simulation" and may miss thin
ridges between taps (`Scene3D_Resources.md:118-123`); Neon Lake's driver memory at its first draw (about +280 MB
committed) is unattributed (`Current_Plan.md` item 8b, P2 remainders, a P2 remainder).

### E25. Soft-light array
`rendering/gl_programs/lighting.py` (`MAX_SOFT_LIGHTS = 96`, `SOFT_LIGHT_GLSL`). Bounded unshadowed soft-source
irradiance from caller-supplied positions, radii and flux, no resources. Consumers: **none in production** (the only
importers are `tools/labs/ribbon_lighting.py:11` and `tests/test_scene3d_lighting.py:8`), matching the plan ("written,
tested, used by a lab only"). Test: `test_scene3d_lighting.py`, `test_ribbon_lighting.py`. Native: **N4.m, high
potential, built without a consumer** (N4.m's box). Notes: it uses loose `uLightCount` / `uLightPosition[96]` /
`uLightFlux[96]` uniforms, so it needs an N1.6 conversion into a block before it can be baked (**unverified** whether
the conversion is scheduled; N1.6's group list item 8b, N1.6 does not name it); it is "a low-frequency lighting
approximation, not area-light visibility or specular reflection".

### E26. Waveform's own fields (borderline: mode code in a shared folder)
`scene3d/waveform.py` (`WaveformScene`), `waveform_field.py` (`WaveformField`), `floor_give.py` (`FloorGiveField`),
`pulse_rim.py` (`PulseRimField`). Each is imported only by the Waveform scene, with fixed-world compute fields reduced
once per frame without readback. They are Waveform Ribbon's own code (N5.4's "its five compute passes and three
rings, floor and pulse-rim textures"), not primitives for other modes. Listed so nobody mistakes them for shared
ones. The Lessons' "Wet reflective floors" and "Volume mist" blocks (lines 279-301) record what they taught.

### E27. Program binary cache and the one link function
`rendering/quick/render/gl_resources.py` (`_link`, `compile_program`, `compile_compute_program`, `delete_program`) and
`gl_program_cache.py` (`ProgramBinaryCache`). Every custom GL program links through one function; a stored binary
keyed by SHA-256 of schema, driver strings and sources is loaded with `glProgramBinary`; a cold link is paid once per
machine and driver (R-180: Neon Lake's basin ~6 s cold, ~30 ms loaded). Store in `<LOCALAPPDATA>/SRPSS/gl_program_cache`,
bounded to 64 MB. Test: `tests/test_gl_program_cache.py`. Native: replaced by Qt's pipeline cache and `qsb` bakes
(D5.6 row 5); N3.6 owns warm-up. Notes: the conventions buffer registry here is keyed by the native context pointer
(`gl_resources.py:147-196`, R-198, `Docs/Historical_Bugs/R-198_*.md`); see contradiction list in section 7 for the
plan box that still shows it open.

### E28. Backdrop pyramid (card surface materials)
`rendering/quick/render/surface_backdrop.py` (`BackdropPipeline`). One shared blurred backdrop per display, built by a
blit of the window target into half, quarter, eighth, sixteenth and thirty-second levels with up passes into a
two-mip RGBA8 output; armed one-shot or continuously during a transition; absent while every surface is Normal.
Design: `Docs/Architecture/Card_Surface_Materials.md`. Native: **N5.7b** (D7: built from the core's own background layer
texture, only when changed and only while demand is above zero; budgets 0.3 ms at 2560 x 1440 and 0.6 ms at 4K,
Decisions D5.6 row 10), and N5.9 (true glass). Notes: the blit and its eight dirtied states are Python-OpenGL-only
(`surface_backdrop.py:236-283,419-423`); the protected clip and background commits (ce07b991, 07486d83, 985b9d53) are
not retuned.

### E29. Presentation textures and the wrapped-texture bridge
`rendering/quick/render/image_textures.py` (`PresentationTextureHost`), `native_texture_bridge.py`,
`background_node.py`. The only owner and deleter of presentation GL textures; PR-04 lends a transition's destination
texture to the retained background; the bridge adopts a GL name as a scene-graph texture and refuses when the API is
not OpenGL (`native_texture_bridge.py:111-114`). Native: **N5.7a** (the core's background layer owns images as QRhi
textures; D9's job form is the async upload) and N5.2h (the bridge is deleted with the Python presenter). Notes: the
bridge is a GL-only seam that cannot survive the flip.

## 4. Shared services of the native core

"Decided" means the decisions document fixes the design, "proved" means a harness round (`native/spike_p1`, or the
product module's `native/core/python/*_check.py` on a GitHub build) verified it; `native/core/README.md` lists what
the product module holds today.

| Service | Source | Status (14 Nov) | What it enables |
|---|---|---|---|
| **Host adapter** (D5.1) | Decisions line 168-176 | built and proved in N2.2 (`native/core/src/host_adapter.*`, `host_check.py`) | the core never names Qt Quick's frame; a second window kind or a Qt upgrade changes one small file. Hosts: the Qt Quick window, the hidden host, a reserved swapchain-owning host |
| **Frame driver** (D5.2) | Decisions line 178-204 | built and proved in N2.2 (`frame_driver.*`) | all core work recorded in dependency order on `beforeRendering` through a C++ connection (no Python slot) |
| **Texture-node composite** (D5.2) | line 185-199; N2.4 | built and proved 13 Nov (`composite.*`, `composite_check.py`: texels one to one, the 1C.4 clip contract) | each surface reaches the window as a texture provider a `ShaderEffect` can sample at no cost; Qt applies clip, opacity, batching |
| **Packet reader** (D1, D2, transport rule) | Decisions "D1, D2, D3 and the transport rule"; N2.3 | built and proved 14 Nov (`packet_reader.*`, `frame_abi_generated.h`, `packet_reader_check.py`; module ABI 5); its first user is N2.5 | the core reads a Visualizer stream on its own view of the mapping, refuses an unknown payload at the slot head, and is its one consumer |
| **No Python on the core's threads** (D5.4) | line 232-234 | decided; rechecked at every port | frame pacing independent of the GIL (D8 plus 1) |
| **Module location** (D5.7) | line 236-238 | built: `native/core/`, module `_srpss_native_core` (N2.1) | exact-Qt import guard, one Python importer (`rendering/native/`) |
| **GPU timer per pass** (D5.3 row 1) | line 217; N2.6 | built and proved 13 Nov (`native/core/src/gpu_timer.*`, `rendering/native/gpu_timing.py`, `timer_check.py`) | per-pass figures in the frame trace; off means no query objects; every later port measured per pass |
| **Stream ring service** (D5.3 row 2) | line 218; N3.2 | built only if it wins by 0.05 ms | larger histories and denser strands at one copy per frame |
| **Indirect and count draws** (D5.3 row 3) | line 219 | **retired 12 Nov**: QRhi 6.12 has `drawIndirect` and `DrawIndirectMulti`; N4.c queries support at runtime (N4.c's box) | GPU-driven populations of 10^5 to 10^6 without a raw service |
| **Per-sample reads** (D5.3 row 4) | line 220; N1.8 | built only if resolve-first fails a mode's look or cost | Extruded Bubble's nearest-depth `background()` if the A/B fails |
| **Formats service** (D5.3 row 5) | line 221; N1.7 widened first | one listed use, the multisampled velocity attachment (N1.7's box) | RG16F, RG32F, R11G11B10F without doubling memory |
| **Async GPU jobs** (D9, row 6) | line 498-622; N3.8 (N3.8's box) | **proved N0.7** (second QRhi on our VkDevice, queue index 1 of family 0; latched publication; in-frame form always exists); built in N3.8 | no late frame at an image change or a transition's preparation while a Visualizer runs (4K edge-field build in frame: 40 late of 1200, as a job: 0 late) |
| **Vulkan device ownership** (D6) | line 240+ | **proved N0.6** (our instance and device host Qt Quick pixel-identical; teardown, resize, second queue) | one device per window; Vulkan by default at NF |
| **Backdrop pyramid** (D7) | line 383+; N5.7b | decided; unbuilt | materials that follow a transition frame; true glass over the Visualizer (N5.9) |
| **Conventions include** `srpss_conventions.glsl` (N0.3) | `rendering/gl_programs/conventions.py`; Decisions line 1358-1371 | built in Python (N1.4: OpenGL values make it an identity); the three backend scenes proved 12 Nov (Vulkan, OpenGL, D3D11, D3D12; Metal on the Watchlist) | the only place a shader learns a backend convention: `fragPixel/fragTexel/fragUv`, `ndcToUv/uvToNdc`, `viewDepthFromDepthTexture`; `SrpssConventions` block at binding 17, written once per context |
| **Portable programs / pass blocks** (N1.6) | `rendering/gl_programs/portable.py`; `scene3d/uniforms.py` `PassBlocks` | built, converting group by group; `LEGACY_GL_ONLY` was 16 after D4 (N1.6's box) | loose uniforms become one std140 block at binding 18, samplers get `binding = unit`, varyings get locations; arithmetic untouched so OpenGL pixels are identical (`tools/conventions_identity.py`) |
| **Shader readiness ratchet** | `tests/test_vulkan_shader_readiness.py`; `qsb` bakes | active; "discovers compute sources and bakes every target" (N1.6's box) | no non-bakeable shader can be added silently |
| **Pipeline and warm-up policy** (N3.6) | N3.6's box | decided; unbuilt | every state combination is a pre-built pipeline warmed gradually; `VK_EXT_device_fault` logged once |
| **Rehearsal path** (D10, N2.7) | D10 "As built"; the N2.7 leftovers box | built 13-14 Nov (`rendering/quick/bootstrap.py`, `--graphics-backend=vulkan`; reveal on the first presented frame; Settings greys unported modes); N2.8's lead runs on Display 1 | a diagnostic switch for Vulkan on Display 1 before the flip; unported modes not offered |
| **Framed camera** (D5.5, N0.4) | `core/settings/framed_camera.py`; Decisions line 1466+ | decided; the worker publishes the finished camera, built with N5.4 then N5.6 (N0.4's remainder box) | one camera for every framed 3D mode (section 7) |

Quick-side services that stay as they are until the native presenter replaces them: the program cache (E27), the
render-node telemetry (`rendering/quick/render/telemetry.py`, proof telemetry, no thread, timer or context), the
background and image nodes (`background_node.py`, `background_item.py`, `background_image_node.py`) and the GL
query helpers (`rendering/quick/gl_query.py`, raw getters for CPU-cheap reads; Lessons line 168-171).

## 5. Planned primitives (never built)

### The old id map (`Current_Plan.md` item 8b, standing rules)

| Old | New | Meaning |
|---|---|---|
| S3D-1 | N4.b | ribbon and strip |
| S3D-2 | N4.c | compacted populations (sprites, streaks) |
| S3D-3 | N6.2 | static scene geometry and materials (photo shells: N6.4) |
| S3D-4 | N6.1 | dynamic surface field |
| S3D-5 | N4.d | planar reflections, rough receivers, scene probe, wet-surface masks |
| S3D-6 | N4.h | shared shadows |
| S3D-7 | N4.f1, N4.f2 | reduced-resolution volumes; its smoke is N6.3, its lightning N6.6 |

### N6 (primitives track, native only; `Current_Plan.md` item 8b, the N6 boxes)

| Id | What it is | Class | What it makes possible (the plan's words) | Dependencies | Candidate consumers |
|---|---|---|---|---|---|
| **N6.1** | Dynamic surface field: a bounded GPU height-and-velocity grid with impulse injection and damping, a displaced mesh with true normals, reflection distortion driven by it | **High** | "water, ripples, pools, melt, any reactive surface" | N4.d (reflection distortion), N4.e (the grid it shares), N3.3 compute, N3.2 meshes | Reactive Liquid / Melt Pool (S3D-4, plan section 7.2), Concrete Rain (ripples, section 7.3), Neon Lake's water (named by the plan, but its reflection is analytic today), SMP surfaces |
| **N6.2** | Static scene geometry and materials, built once and kept (floors, walls, wells, simple skyline and tunnel slices; roughness, bevel, contact shading) | **High** | "what turns a mode into a place" | N3.2 meshes, N4.d | Melt Pool's chamber (section 7.2), Concrete Rain's street (section 7.3), SMP surfaces |
| **N6.3** | Advected smoke and haze on the volume primitive | **High** | "atmosphere for every 3D scene" | N4.f2 (shares its reduced-resolution path; the fog detail march is its base), N3.3 | every 3D mode, Waveform's atmosphere, Melt Pool, Concrete Rain |
| **N6.4** | Photo-textured shells and planes with real depth | **Low until a consumer** | none stated; "a transition or a mode built round the user's photos" | N3.1 targets, N4.j environments | none admitted |
| **N6.5** | The opt-in deformable sheet | **Low until a consumer** | none stated | N4.l's bendable grid, N4.e | none admitted |
| **N6.6** | Lightning: procedural bolt geometry and its light | **Low until a consumer** | "one effect" | N4.f2 (S3D-7's lightning), N3.4 bloom | none admitted |

### Unbuilt N4 items (ported with their consumer, or on the primitives track)

Existing in Python (section 3) but not yet native: N4.b (E12), N4.c (E11), N4.d (E13, E14), N4.e (E24), N4.f1 and N4.f2 (E15),
N4.g (E16 to E18), N4.h/N4.l (E21, E22, E23), N4.i (E5, E6), N4.j (E7), N4.k (E20), N4.m (E25). Class as stated by
the plan: high potential for N4.c, N4.d's wet-surface masks, N4.h, N4.k, N4.m (D8 row 6 lists N4.c, N4.h, N4.k, N4.m,
N6.1 to N6.3, so it omits N4.d; see contradictions).

Never built in any form:
- **N4.a, the fullscreen pass and image sampling as a primitive** (N4.a's box, in N2b). Seeds exist as
  `FULLSCREEN_VERTEX_SOURCE` (E4) and the background node, not as one primitive. Consumers: the seven fullscreen
  transitions of N5.2a (Crossfade, Burn, Particle, Ripple, Slide, Warp, Wipe) and the background layer (N5.7a). No
  class stated.
- **Mixed-resolution soft layers with depth-aware upsampling** (N4.f2, D8 plus 4): bloom, reflection blur, wide glows
  and fog at reduced resolution; "lines, dots, rims, particles and UI stay at full resolution"; never whole-frame
  upscaling. Gate: stills reviewed by the lead and GPU time before and after; halos at depth edges are the risk.
- **Instanced screen-space quads in place of `gl_PointSize`** (N3.2, N3.2's box): Bubble ambient, Neon Lake's marks and
  Waveform's sparks use point sprites today; the Oscilloscope already draws instanced quads (Decisions D5.6 row 11).
  QRhi's `VertexShaderPointSize` is not portable (D3D has none).
- **Single draw with `ShaderDrawParameters`** (`gl_DrawID`, `gl_BaseInstance`, `gl_BaseVertex`) for a mode's small
  batches (plan note at item 8b, N3.2's box); D3D11 support is not stated.
- **Not admitted** (D8 rows 9 and 10): HDR output, per-pass temporal upscaling, descriptor indexing, mesh shaders, ray
  tracing. Low potential until a consumer exists; the door stays open (D6).

### Candidate consumers beyond today's modes (item 9 and SMP)

New modes (`Current_Plan.md` item 9) are built on the native core only: Reactive Liquid / Melt Pool (section 7.2,
S3D-3, S3D-4, S3D-5, S3D-2: N6.2, N6.1, N4.d, N4.c), Concrete Rain (section 7.3, same four), Usu Moonscape (section 7.4,
"plus S3D-6", i.e. N4.h, with character and world foundations S19 to S27 that are not primitives of this catalogue).
Expanded Visualizer M6 (4K acceptance) waits on N4.f2 for Waveform Ribbon and Extruded Bubble (item 8b, N4.f2's box). SMP surfaces
(item 9, SMP foundations): the plan says "one Visualizer owner, any surface"; the plan names Neon Lake and SMP surfaces as
candidate users of N6.1 (N6.1's box). Which other SMP surface uses which primitive is **unverified**: no SMP document
was read for this catalogue.

## 6. How to read an entry's numbers

Costs in sections 3 and 5 are from `Scene3D_Resources.md` and the Decisions; they are RTX 4090 figures at the sizes
stated, unless an entry says otherwise. Per the Lessons (lines 155-173): GPU cost is `GL_TIME_ELAPSED` over at least 90
frames reported as median and p90 with a flush after every frame; before and after are loaded side by side in one
process, never across sessions; differences of tens of microseconds between processes are GPU clock state.
Per-pass attribution on the native side needs the N2.6 timer.

## 7. Important to note

### Cross-cutting lessons (binding; Lessons section line 149 onward)
- **Measure the right thing**: production runs PyOpenGL with error checking off (`rendering/gl_error_policy.py`);
  harnesses default to on. Count GL calls per frame; every PyOpenGL call also runs `glGetError` (about 4 microseconds).
  A raw setter costs the same as a checked one; cut calls instead.
- **No `glBlitFramebuffer` resolves**; render into texture attachments and resolve in the reading shader.
- **State fences**: the transition host restores texture units 0 to 2 only; a renderer using unit 3 or above hands it
  back (Lessons lines 311-312). Image units go through `bound_image`. `restore=False` only for scenes that own their
  whole frame.
- **Compute needs its barrier tested** by order and bits (NVIDIA hid a missing one); the writer issues it.
- **Determinism**: GLSL randomness is the integer hash with a CPU mirror checked on the GPU (**R-94**; float
  `fract(sin())` hashes seam). The index entry `R-94` is cited in `Transitions.md:142,205` but has no file in
  `Docs/Historical_Bugs/` (checked by glob, 12 Nov): treat as **unverified**.
- **64-bit**: no shader uses a 64-bit float (D4; Vulkan's `shaderFloat64` is optional): decisions of record are made
  once on the logical side in fp64 and published; ever-growing per-member quotients are rebuilt from float pairs with an
  exact two-product (Veltkamp halves, `precise`, never `fma` because `qsb`'s HLSL turns it into `mad`); check every
  target's baked source (Lessons lines 242-252; `tests/test_extruded_bubble_drift_precision.py`).
- **Look-first**: judge at native-pixel zoom beside the reference; stochastic jitter needs real photos; a population
  sized by a continuous count fades its edge across a band of members and is a rate-capped follower, never a beat
  follower (Lessons lines 210-213, 269-270).
- **Reality vs lab**: offline speed is not live speed; the logical tick's GIL-held Python stalled the render thread
  (Lessons lines 256-260). Judge a mode under `tools/visualizer_live_check.py --load game60` (lead only, ten minutes
  at most, only after the operator's yes). Viz hitches come from single GIL-holding C calls (memory "Viz hitch = GIL-held
  C calls").
- **Directions**: a direction label names where motion starts and the way it travels; `test_transition_direction_labels.py`
  renders every labelled direction (Lessons lines 324-333).
- **Shadows**: the rejected Extruded cast shadows stay rejected; do not reuse a translated top cap as a cast
  (`Scene3D_Resources.md:14`; R-125 to R-128).

### Portability (what a primitive must satisfy to bake)
- **Bake targets**: SPIR-V, GLSL 430, HLSL 5.0, MSL 1.2 (`Scene3D_Resources.md:300-301`; `Current_Plan.md` item 8b, N1's boxes).
  GLSL ES is **not** a target (removed by N1.7, 12 Nov). `.qsb` bakes for every backend, not `--glsl 460` only
  (item 8b, N1's boxes). A scalar half-float storage image is `r16f`.
- **No 64-bit types** in any shader on any backend (D4).
- **Reserved block bindings**: 16 `SCENE3D_COMPUTE_BLOCK_BINDING`, 17 `SCENE3D_CONVENTIONS_BLOCK_BINDING`, 18
  `SCENE3D_PASS_BLOCK_BINDING` (`rendering/gl_programs/scene3d.py:1035,1040,1046`); the per-frame uniform block sits
  on 15 (`scene3d/uniforms.py:30`). Samplers, images, storage and blocks share one binding namespace on Vulkan; in
  OpenGL a texture or image unit is that number (`Scene3D_Resources.md:296-299`).
- **No loose uniforms** in a portable program: one std140 block per program (N1.6); C++ packs from reflected offsets,
  never hand-computed ones (N0.3 rule 5); `vec3` aligns to 16, scalar arrays have a 16-byte stride.
- **Conventions**: core-owned targets are top-left, Y down on every backend; matrices stay in OpenGL form from one
  owner (`core/settings/framed_camera.py:286-289`) and are corrected once at upload with `clipSpaceCorrMatrix()` (N0.3
  rule 1); front face is one function of handedness and `isYUpInNDC()`; no hand-written `gl_FragCoord` arithmetic, no
  `ndc * 0.5 + 0.5`; `gl_VertexID` and `gl_InstanceID` read `srpssVertexIndex` and `srpssInstanceIndex`
  (`rendering/gl_programs/conventions.py:58-70`).
- **Formats**: no `RG16F`, `RG32F`, `R11G11B10F` in QRhi's list; widen to RGBA16F/RGBA32F (costs 2 times the bytes per
  texel) unless a target's measured cost justifies D5.3's formats service (Decisions D5.6 row 13). RGB10A2 is unorm and
  never a substitute.
- **Point sprites and geometry shaders**: use instanced quads and per-face draws (E14, E23).
- **Pipeline state is data**: no state setters in a mode; each state combination is a pre-built pipeline (D5.6 row 16).
- **Depth**: window depth in [0, 1] after the correction; reverse-Z is not proposed (Decisions line 1461).

### The framed camera standard
`core/settings/framed_camera.py` is **the standard physical camera for framed 3D Visualizer modes** (its docstring:
operator 2026-10-24; Extruded Bubble's camera is the standard). A mode declares a `FramedCameraSpec` (pivot, orbit
distance, pitch and yaw mapping, admitted eye box, optional floor or ceiling) and shares everything else: orbit axes,
the orbit, pan and dolly baseline, bounds, flight, reset, and the GLSL projection. Specs live in
`core/settings/neon_lake_camera.py`, `core/settings/extruded_bubble_camera.py` and `core/waveform_ribbon_scene.py`,
registered in `core/settings/visualizer_mode_registry.py:400,441,473`. Perspective is the only projection (Orthographic
removed 5 Nov 2026). The horizontal view is capped at 90 degrees by reducing the vertical view, never stretching edge
content (`framed_camera.py:32`). No per-mode cameras and no copied controllers (memory "Framed camera standard";
`Scene3D_Resources.md:16-25`). The native core takes one camera owner: the worker publishes the finished camera and
the renderer builds none (D5.5; N0.4's remainder box; test "no perspective or tangent construction in the native
sources").

### Stale text still open

The contradictions this catalogue found on 12 Nov were settled by the night audit of 12 Nov
(`Docs/Future_Work/Audit_2026-11-12_Night.md`); the catalogue cites the plan by item and box name (line numbers
drift). One stays open until the flip:
- `Scene3D_Resources.md:3-5` ("All admitted operations require the validated OpenGL 4.6 context") and the opening
  "retained Quick transition and visualizer hosts remain their scenes' render owners" describe the Python path
  only; the native core's host adapter (D5.1) changes that, so the sentence needs a "today" qualifier at the
  flip.

### Unverified in this catalogue
- Whether every "consumer" list is complete: it comes from import greps of `rendering/` (12 Nov); consumers through
  dynamic registries (transition discovery) could be missed.
- Test names beyond those grepped or globbed; test coverage of N4.g's edge field is by `test_qtquick_edge_bloom.py`
  only (no dedicated `test_scene3d_edge_field*` file exists in `tests/`).
- Whether `rendering/gl_programs/lighting.py` is scheduled into an N1.6 group (it carries loose uniforms).
- SMP consumers of any primitive; the plan names only N6.1's "SMP surfaces".
- Every figure copied from `Scene3D_Resources.md` and the Decisions was not re-measured.
