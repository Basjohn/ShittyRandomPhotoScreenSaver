# Transition effects

All effects use the canonical transition catalog, Settings activation and Random-pool controls, an immutable request/run, and the existing inline Quick render host. They share the current monotonic run; none adds a clock or changes Visualizer cadence. Activate an effect in **Transitions -> SETUP**, then select it and configure its options. Activation and Random-pool membership are separate controls.

## Expanded effects

These capabilities are **deactivated by default**. Tendril Reveal is additionally unavailable and pending removal after operator rejection; Melt remains visually rejected and is retained for possible rework. Remaining visual/load acceptance is open in `Current_Plan.md` and `Docs/Future_Work/Transition_Expansion.md`. Existing activated effects and settings retain their values.

| Effect | Appearance | Controls |
| --- | --- | --- |
| Glass Shatter | Seeded closed beveled prisms depart geometrically offscreen. Screen-space destination transmission, refraction, dispersion and sheen make the glass material independent of the printed source face. | Direction including Center Out, 24–180 shards, depth, thickness/transparency/refraction/dispersion/sheen 0–1, duration |
| Exploding Tiles | Closed beveled cubes use full ray-exit departure, thickness and force to release in a directional/radial wave. | Direction including Center Out, 6–48 columns, depth, thickness 0–1, force 0.5–2, duration |
| Directional Pixel Accretion | Destination micro-tiles translate along one event direction, then settle in sequence over the source. Slight temporary height and oversize give the landing front depth. | Eight directions or Random, physical tile size, travel, duration |
| Ink Bloom | A raised mesh surface transports vortical marbled pigment with image-derived wet reflections and normals. | Detail, depth/gloss 0–1, duration |
| Tendril Reveal | Rejected and pending removal. Visible but greyed out; excluded from activation and runtime selection. | Unavailable |
| Melt Drip | A bounded implicit 3D liquid volume forms a round wet film, ligaments and pinched gravity drops while the source photo advects through the fluid. | Gravity direction, detail, depth/gloss 0–1, duration |

**Slide -> Motion Style -> Perspective Push** is an option in the existing Slide identity. It uses an aspect-correct view-ray/tilted-plane intersection for the outgoing image, with shallow translation/tilt/depth and the existing sealed coverage partition. Linear, Elastic, Wobble and Flex keep their existing authored math. Perspective Push does not add a scene, mesh owner, transition ID or clock.

## Implementation contracts

- Direction and seed resolve once before request admission. Renderers consume explicit immutable parameters; no per-frame Settings access or random choices.
- Glass and Crumble share deterministic closed fracture prisms. Glass uses screen-space transmission/refraction and analytic offscreen departure without a shrink retirement; Crumble first draws growing recessed cracks along those same polygon borders while the image stays still, then releases thick chunks and their seam debris. Rough stone sides and release weighting remain. Crumble accepts 4–128 pieces, depth 0.2–1.5 and thickness/debris 0–1; its float seed remains intact across its deterministic geometry and debris.
- Exploding Tiles uses one immutable closed beveled-cube mesh and `gl_InstanceID`; Accretion uses one immutable micro-quad mesh, a viewport-derived grid capped at 60,000 instances, and a bounded flight interval so early tiles land before later ones start. Neither uploads evolving instance arrays.
- Ink transports bounded vortical pigment over a raised mesh. Tendril uploads bounded tube topology and samples that same finite Bezier path set for its canopy. Melt ray-intersects a bounded implicit volume with 52 steps and at most three neighboring lanes; it has no full fluid simulation or opacity wipe. Melt direction is gravity: its upper source film recedes and drops travel along that direction.
- `rendering/quick/transitions/mesh_support.py` owns only the small shared context-local program/VAO/VBO primitives, image underlay and viewport-scoped depth clear. It is imported by admitted implementations. No always-resident 3D engine or dependency on Sphere exists.
- The mesh effects draw the destination (departure effects) or source (accretion) beneath the pieces. Exact full-image endpoint draws are supplemented by near-endpoint continuity tests so endpoint branches cannot hide pops.
- The shared Quick host restores GL state on exceptions. Depth clearing intersects the active scissor and viewport, then restores scissor state. Partial cleanup retains failed handles for retry; disable/context retirement releases owned resources.
- New Settings pages follow the same lazy build, hydrate, save and retirement owner. Canonical defaults and generated snapshots remain under the existing Settings authority.
- Crumble's weighting menu names the actual release order: Top, Bottom, Random Weighted, Random Choice and Age Weighted. Former Bias Old Image/Bias New Image values both resolved to Top; reopening and saving replaces those misleading labels. The unused mosaic request field has been removed.

## Verification and remaining acceptance

`tests/test_qtquick_future_transition_gl.py` renders through the real driver and production host to check exact/near endpoints, repeatability, parameter and direction sensitivity, and resource retirement. Focused `crumble_volume`, `melt_surface`, `organic_surfaces`, `transition_material_settings` and `tile_departure` tests cover bounded topology, material controls and continuous departure; registry/request/Settings/run/fence suites cover integration.

`tools/transition_contact_sheet.py` produces textured progression frames, optional supplied-image contact sheets, and a 60-frame/two-second WebP with `--animate`. It accepts `--source` and `--destination` photos; `--quick-smoke` reuses the existing threaded QQuickWindow lifecycle harness. See `Docs/Reference/Harness_Index.md` for commands. Diagnostic timing includes context/driver effects and is not a claim of performance neutrality.

Operator acceptance still needs actual photographs at authored duration, preferred glass sheen/tile density, both displays and representative heavy external load with active Visualizers. Automated pixel/scene evidence cannot close those perceptual/freshness gates.
