# Transition effects

All effects use the canonical transition catalog, Settings activation and Random-pool controls, an immutable request/run, and the existing inline Quick render host. They share the current monotonic run; none adds a clock or changes Visualizer cadence. Activate an effect in **Transitions -> SETUP**, then select it and configure its options. Activation and Random-pool membership are separate controls.

## Expanded effects

These six capabilities are implemented and **deactivated by default** while operator visual/load acceptance is open in `Current_Plan.md` and `Docs/Future_Work/Transition_Expansion.md`. Existing activated effects and settings retain their values.

| Effect | Appearance | Controls |
| --- | --- | --- |
| Glass Shatter | Seeded irregular Voronoi shards carry the original image through arbitrary-axis rotation, perspective and depth. Cool edges, normal-based sheen and restrained transmission separate glass from solid tiles. | Direction including Center Out, 24–180 shards, depth, duration |
| Exploding Tiles | Regular shallow cuboids release in a directional/radial wave, rotate in real 3D, show shaded sides and leave the image plane. | Direction including Center Out, 6–48 columns, depth, duration |
| Directional Pixel Accretion | Destination micro-tiles translate along one event direction, then settle in sequence over the source. Slight temporary height and oversize give the landing front depth. | Eight directions or Random, physical tile size, travel, duration |
| Ink Bloom | Connected domain-warped pigment fronts reveal destination with a narrow wet edge. | Detail, duration |
| Tendril Reveal | Seeded branches extend from a common root, fork, then thicken into the destination. | Detail, duration |
| Melt Drip | A gravity-directed boundary develops rounded drips while surviving source imagery stretches near the front. | Direction, detail, duration |

**Slide -> Motion Style -> Perspective Push** is an option in the existing Slide identity. It uses an aspect-correct view-ray/tilted-plane intersection for the outgoing image, with shallow translation/tilt/depth and the existing sealed coverage partition. Linear, Elastic, Wobble and Flex keep their existing authored math. Perspective Push does not add a scene, mesh owner, transition ID or clock.

## Implementation contracts

- Direction and seed resolve once before request admission. Renderers consume explicit immutable parameters; no per-frame Settings access or random choices.
- Glass builds one deterministic convex-cell mesh per run/aspect. Texture coordinates stay attached to the original fracture coordinates. GPU motion is analytic; there is no CPU physics simulation.
- Exploding Tiles uses one immutable cuboid mesh and `gl_InstanceID`. Accretion uses one immutable micro-quad mesh, a viewport-derived grid capped at 60,000 instances, and a bounded flight interval so early tiles land before later ones start. Neither uploads evolving instance arrays.
- `rendering/quick/transitions/mesh_support.py` owns only the small shared context-local program/VAO/VBO primitives, image underlay and viewport-scoped depth clear. It is imported by admitted implementations. No always-resident 3D engine or dependency on Sphere exists.
- The mesh effects draw the destination (departure effects) or source (accretion) beneath the pieces. Exact full-image endpoint draws are supplemented by near-endpoint continuity tests so endpoint branches cannot hide pops.
- The shared Quick host restores GL state on exceptions. Depth clearing intersects the active scissor and viewport, then restores scissor state. Partial cleanup retains failed handles for retry; disable/context retirement releases owned resources.
- New Settings pages follow the same lazy build, hydrate, save and retirement owner. Canonical defaults and generated snapshots remain under the existing Settings authority.

## Verification and remaining acceptance

`tests/test_qtquick_future_transition_gl.py` renders through the real driver and production host to check exact/near endpoints, repeatability, parameter and direction sensitivity, and resource retirement. The focused fracture/instanced tests cover topology, bounded counts, flight/settlement and depth-clear cleanup; existing registry/request/Settings/run/fence suites cover integration.

`tools/transition_contact_sheet.py` produces textured progression frames and optional supplied-image contact sheets. Its `--quick-smoke` mode reuses the existing threaded QQuickWindow lifecycle harness. See `Docs/Reference/Harness_Index.md` for commands. Diagnostic timing includes context/driver effects and is not a claim of heavy-load or mixed-display performance neutrality.

Operator acceptance still needs actual photographs at authored duration, preferred glass sheen/tile density, both displays and representative heavy external load with active Visualizers. Automated pixel/scene evidence cannot close those perceptual/freshness gates.
