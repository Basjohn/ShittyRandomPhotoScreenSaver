# Transition effects

All effects use the canonical transition catalog, Settings activation and Random-pool controls, an immutable request/run, and the existing inline Quick render host. They share the current monotonic run; none adds a clock or changes Visualizer cadence. Activate an effect in **Transitions -> SETUP**, then select it and configure its options. Activation and Random-pool membership are separate controls.

## Expanded effects

The expansion capabilities remain **deactivated by default** unless explicitly activated, except where accepted: Glass Shatter and Melt Drip are activated and in the Random pool by default (Melt at 8500 ms). Tendril Reveal was rejected and has been fully retired; it has no registry descriptor, Settings surface, renderer or shader, and stale persisted Tendril state is removed by canonical transition normalization. Melt is accepted in its current reworked form: the photograph itself melts from a chosen origin under gravity, without the rejected detached droplet bodies or ray-marched pseudo-volume. Remaining visual/load acceptance is listed under Physical acceptance below. Existing activated effects and settings retain their values.

| Effect | Appearance | Controls |
| --- | --- | --- |
| Glass Shatter | Seeded closed beveled prisms depart geometrically offscreen. Screen-space destination transmission, refraction, dispersion and sheen make the glass material independent of the printed source face. Optional **Shards Collide**: shards that meet in flight (on screen, before 0.80) bounce off each other with a spin kick, at most about a quarter of shards per run. Optional **Shards Break Again**: shards crack into two or three convex pieces in flight — on collision when Shards Collide is on, otherwise about 30% of shards at a random moment. A split piece can crack once more — shortly after an impact with collisions on, otherwise 30% of split pieces later in flight. All of it is solved once per run at build time; every piece still leaves the frame. Shards whose flights would pass through each other on screen get small constant depth offsets (within +-0.25, ramping in at launch; crash partners share one, split pieces keep their parent's), which cuts on-screen intersections by ~80% (93% Center Out) for ~7 ms more per-run build on COMPUTE at 95 shards (~15 ms at 180) and no per-frame cost. | Direction including Center Out, 24–180 shards, depth, thickness/transparency/refraction/dispersion/sheen 0–1, collide/break-again (off by default), duration |
| Exploding Tiles | The picture is blown apart by a blast. Cracks race out from the blast point along the tile grid; the wall domes at its heart and, in the last part of each tile's wait for the shock front, gives a low shudder (about 2.7-5 Hz, neighbouring tiles nearly together, hardest near the blast); at the detonation (9% of the run) a flash and a shock front release each tile with an impulse. Tiles burst outward and toward the viewer, then drift, tumble and fall, dark grey stone tinted toward the photograph's most used colour, briefly white-hot near the blast and lit by the fireball, which also glows on the new photograph. Sparks stream from the front; the tiles cast soft shadows on the new photograph and the unbroken wall shadows its own edges. Center Out blasts near the middle; a direction blasts from the opposite edge or corner. | Direction including Center Out, 6–48 columns, depth (toward the viewer), thickness 0–1, force 0.5–2, Anti-aliasing, Bloom, Bloom Strength and Motion Blur, duration |
| Directional Pixel Accretion | Destination micro-tiles translate along one event direction, then settle in sequence over the source. Slight temporary height and oversize give the landing front depth. | Eight directions or Random, physical tile size, travel, duration |
| Ink Bloom | A raised mesh surface transports vortical marbled pigment with image-derived wet reflections and normals. | Detail, depth/gloss 0–1, duration |
| Melt Drip | The photograph melts, starting at a chosen origin (Top Left, Top Center, Top Right, Center Out or Center In; Random picks one per run). A seeded melt-time field reaches each point with an irregular boundary; melted paint sags with accelerating weight, runs in soft viscous drips, smears and thins until the new image shows through, and casts a soft shadow onto it. Points the melt has not reached stay the untouched source. | Origin, detail, depth/gloss 0–1, duration |
| Page Curl | The old picture is a laminated print that peels from a corner or an edge and rolls up, the roll growing as it travels at an even pace across the picture and off the far side, while the new picture lies beneath, shaded under the roll. The rolled sheet keeps the print's full colour (its back shows the print mirrored through the clear plastic) under a glossy clear coat that catches highlights and reflects the new picture (Gloss). Deactivated by default. | Origin (four corners, four edges, Random), Gloss 0-1, Anti-aliasing, duration |
| Disintegrate | The old picture crumbles into fine grains that the wind blows away, revealing the new picture. A noisy release front crosses the picture from the side the wind comes from; each grain then flies (a hard start that keeps accelerating, a swirl across the wind, a little lift), shrinks and fades. Grains are drawn from the old picture's own pixels, so the front has no seam. Deactivated by default. | Wind direction (eight, Random; the labels say where the wind blows), Grain Size 2-8 px, Wind 0.5-2, Anti-aliasing, duration |
| Accordion Fold | The old picture is the front of an accordion-folded sheet with the new picture on its back: it folds into pleats against an edge (alternate pleats catching and losing the light), the folded stack flips over toward the viewer, and the sheet unfolds back across the picture as the new one. Behind the sheet, a frosted blur of the new picture. Deactivated by default. | Fold edge (Left, Right, Top, Bottom, Random), Pleats 4-16, Gloss 0-1, Anti-aliasing, duration |
| Relief Rise | A wave sweeps across the picture: where it passes, the surface rises as a lit relief of the old picture's brightness, turns into a relief of the new picture and settles flat on it. Hollows darken (contact occlusion). Deactivated by default. | Sweep direction (eight, Random; the labels say where it travels), Relief Depth 0-1, Gloss 0-1, Anti-aliasing, duration |
| Cube Turn | The picture is the front of a box that turns a quarter to show the next picture on its side, the camera drawing back mid-turn so the whole box stays in view, over a dim blur of the new picture. Deactivated by default. | Direction the front moves (Left, Right, Up, Down, Random), Gloss 0-1, Anti-aliasing, duration |

**Slide -> Motion Style -> Perspective Push** is an option in the existing Slide identity. It uses an aspect-correct view-ray/tilted-plane intersection for the outgoing image, with shallow translation/tilt/depth and the existing sealed coverage partition. Linear, Elastic, Wobble and Flex keep their existing authored math. Perspective Push does not add a scene, mesh owner, transition ID or clock.

**Blinds -> Style -> 3D Slats** (`transitions.blinds.style`: Flat, 3D Slats; Flat by default and pixel-identical to the authored bands) turns each stripe into a solid slat: the old picture on its front, the new one on its back and a thin laminated edge. Slats (6-48, default 16) turn over about their long axis one after another, from the top (lying slats, direction Vertical) or the left (upright slats, Horizontal: the same stripe orientation as the flat style); each turns for half the run, eased. The axis runs through the middle of the slat's thickness, so a front rests exactly on the photograph and a turned slat's back rests exactly there too. Through the gap a turning slat opens, the new picture shows, darkened by the slat. While turning, slats are lit by the shared physically based material and reflect the new picture (Slat Gloss 0-1); the light is blended in by each slat's lift (4e(1-e) of its eased turn), so slats at rest and both ends are the photographs exactly. Slats turn only about horizontal or vertical axes: with 3D Slats, Diagonal and Random pick one of the two per run. Anti-aliasing follows the shared Advanced bucket. Measured at 2560x1440 (RTX 4090): High (4x) 0.58 ms CPU submit and 0.073 ms GPU per frame (median); Balanced 0.43 ms and 0.033 ms. The Flat style never loads the slats shader module or allocates scene resources.

## Implementation contracts

Detailed shared resource ownership, DSA/immutable allocation, multi-bind and GL state-restoration contracts live in
`Docs/Reference/Scene3D_Resources.md`; the effect-specific looks and physical acceptance remain here.

- Direction and seed resolve once before request admission. Renderers consume explicit immutable parameters; no per-frame Settings access or random choices.
- Random rotation is session memory. The engine picks the transition (plus a Slide/Wipe direction, with anti-repeat) and hands `RandomTransitionSelection` to `DisplayManager`, which resolves one batch spec from it; Previous reuses the current pick. Rotation never writes Settings and never overwrites the authored Slide/Wipe `direction`; a persisted `random_choice` from older builds is ignored. Random mode always randomizes the Slide/Wipe direction, whatever direction is authored; outside Random mode a direction set to `Random` is randomized per batch.
- Glass and Crumble share deterministic closed fracture prisms. Glass uses screen-space transmission/refraction and analytic offscreen departure without a shrink retirement; Crumble first draws growing recessed cracks along those same polygon borders while the image stays still, then releases thick chunks and small irregular seam debris. Debris uses an asymmetric solid seed shape plus deterministic per-instance XYZ deformation and size variation, avoiding a repeated box/diamond stamp. Rough stone sides and release weighting remain. Glass keeps the jittered-grid fracture; Crumble's own seeded layout (`crumble_cells`) changes every run: each seed picks an impact point (small shards near it, large slabs away from it), stress clusters or an organic warp, and crack complexity (0.5–2.0) sets how far the layout departs from the grid over its whole range. Cells stay convex Voronoi cells of the wall (gap-free; minimum site spacing prevents slivers), so the crack stage still draws on real shared borders. Debris is seeded per run too: a fine/mixed/chunky grain and a hot spot that concentrates chips along nearby cracks; the debris amount drives both chip count and chip size. Crumble accepts 4–128 pieces, depth 0.2–1.5 and thickness/debris 0–1; its float seed remains intact across its deterministic geometry and debris.
- Crumble chunk motion is analytic in `CRUMBLE_VERTEX`, but each chunk's release time, sideways drift and tumble axis are drawn once per run on the CPU (`rendering/quick/transitions/crumble_dynamics.py`, seeded) and carried as vertex attributes, so the path is known exactly on the CPU and identical on every GPU; debris breaks off exactly at its parent's release. **Slabs Collide** (`transitions.crumble.collisions`, off by default) simulates the collapse once per run on COMPUTE and bakes it into a per-run motion table (64 keyframes × chunks of offset xyz and extra tumble, RGBA32F, ≤128 KiB) that the shader interpolates and adds to the analytic path; with the option off the table is all zeros. Overlapping slabs (discs that sweep a growing volume as they tumble) exchange mass-weighted impulses (restitution 0.30) and are pushed apart, so a fast slab falling onto a slower one drives it down instead of passing through it; a standing slab struck by a falling one is knocked loose (released at that moment, its debris with it). Offsets that would hold a chunk in view are faded out over the last 15 keyframes. The chunk program reads the table on texture unit 1, which it does not otherwise use and which the transition host restores. Measured: deep overlaps (penetration past a quarter of the contact distance) fall from ~2,100 samples to 0 at 45 pieces and to 1–7% at 96; the bake costs ~18 ms at 45 pieces and ~57 ms at 128 on COMPUTE; the vectorised chunk build is ~6 ms at 45 and ~22 ms at 128 without collisions (was ~10/~44). Guards: `tests/test_qtquick_crumble_collisions.py`.
- Exploding Tiles uses one immutable closed beveled-cube mesh and `gl_InstanceID`; every tile's state is analytic in the vertex shader (`rendering/gl_programs/exploding_tiles_program.py`, with CPU mirrors for its timeline, blast light, epicentre and flight curve). Its speed is the blast's own push, raised only as far as `sceneDepartureTravel` requires for the tile to be clear of the frame by its exit time and still clear at 98%, where it settles in front of the photograph (so perspective only pushes it out). The rumble runs at a real-time rate from the run's duration (`uSeconds`), so it keeps its speed at any duration; it starts 40% of the way from a tile's cracking to its release. The rejected first rumble (8-15 Hz from the moment of cracking) shook the far wall for ~1.4 s at 8000 ms and was jarring. The body tint is the source's most used colour, sampled once per run (64 x 36 points, ~1 ms at 4K). Accretion uses one immutable micro-quad mesh, a viewport-derived grid capped at 60,000 instances, and a bounded flight interval so early tiles land before later ones start. Neither uploads evolving instance arrays.
- Ink transports bounded vortical pigment over a raised mesh. Melt is an analytic gravity melt rather than a ray-marched pseudo-volume or fluid simulation: a seeded melt-time field (spread from the origin, roughened by value noise on an exact integer lattice hash) decides when each point melts; melted content samples the source from higher up with a sag that grows with the square of its age, soft drip columns sag further, and the film thins to the destination by 0.94 of the run. Depth drives film relief, fold darkening, refraction and the cast shadow; Gloss drives highlights and a wet sheen, never the silhouette; Detail drives drip count and boundary irregularity. Points not yet melted sample the source at original coordinates. It has no detached sphere/capsule bodies or independent clock.
- Glass/Crumble per-run fracture geometry is pure CPU work in `rendering/quick/transitions/run_geometry.py` (the one reference builder). `DisplayManager` starts it on COMPUTE when the batch spec resolves, keyed on each display's render size (`transition_logical_size()`, the R-63 window — R-95); the renderer uploads the prepared bytes, waits up to 0.25 s for a preparation still in flight, or builds the identical bytes itself. Only immutable CPU bytes are shared (bounded LRU keyed by every builder input); GL buffers stay per render context.
- **3D Block Spins Edge Glass** (`transitions.blockspin.edge_glass`: Off, Reflection, Refraction, Both; Off by default and pixel-identical to the plain look). The slab's side faces become polished glass showing the next image: refraction samples it directly; reflection reads it as a photo environment by the reflected ray (see Photo reflections). The edge is rounded: across the slab's thickness the glass normal rolls from the front face's normal to the back face's, so the edge holds a compressed miniature of the picture. (Flat, the thin face sampled a single column and read as a vertical smear.) Reflection sweeps the image across the edge as the slab turns. Refraction bends it through the glass with slight dispersion. Fresnel weighs the two, so the rounded borders read as mirror and the middle as glass. The sheen band and gloss outline keep the flat normal and are drawn over the glass unchanged. Measured at 2560x1440 (RTX 4090): every mode is within 0.001 ms of Off, with or without 4x. `resolve_block_spins_parameters` is the one resolver, used by production and the capture harness; the choices live in `rendering/gl_programs/blockspin_options.py`.
- `rendering/quick/scene3d/resources.py` owns only the small shared context-local program/VAO/VBO primitives, image underlay and viewport-scoped depth clear (shared with Visualizer modes that opt in; see `Docs/Reference/Visualizer_Reference.md` §16). It is imported by admitted implementations. No always-resident 3D engine or dependency on Sphere exists.
- **Shared 3D scene library.** `rendering/gl_programs/scene3d.py` is the import-safe GLSL library plus CPU mirrors: integer hash, rigid rotation, the pinhole camera with a real near plane (`sceneProject`), impulse flight, the departure solver, key-light shading with highlights and Fresnel rim, point lights, ember colour, planar soft shadows of any rigid piece (`ScenePiece`, `scenePieceShadow`, drawn MIN-blended by `rendering/quick/scene3d/shadows.py`), camera-facing streaks, particle flight (`sceneParticleAt` / `sceneParticleStreak`, drawn by the shared additive pass in `rendering/quick/scene3d/particles.py`) and the bendable grid surface (an effect writes `vec3 sceneDisplace(vec2 uv)`; `scene3d_grid_vertex_source` gives it normals and projection, `rendering/quick/scene3d/grid.py` draws the tier's grid; no consumer yet). `rendering/quick/scene3d/` adds MIN/additive blend scopes (`passes.py`) and `SceneTarget` (`target.py`), a multisampled colour+depth target for the item's pixel rect, reused while the rect fits a 64 px bucket, resolved and composited through the item quad (Quick's scissor and item bounds apply as for a direct draw); its `scope` restores Quick's framebuffers, viewport and scissor even when the scene raises. Exploding Tiles is the first consumer.
- **Advanced bucket.** Each 3D transition page keeps its optional quality and look choices (Anti-aliasing, Bloom with Bloom Strength, Motion Blur, Motion Trails, Edge Glass) in one shared collapsible **Advanced** bucket, closed by default. The controls that shape the effect itself stay on the page. New optional settings go into that bucket.
- **Per-transition quality over one tier.** Each 3D transition's page has its own quality choices: Anti-aliasing (Auto, Off, 2x, 4x, 8x) and Motion Blur (Auto, Off, On) on Exploding Tiles, Glass Shatter, Crumble, Directional Pixel Accretion and 3D Block Spins, and Bloom (Auto, Off, On) plus Bloom Strength on Exploding Tiles. Auto follows the global 3D Detail tier; any other value is authoritative for that transition. `resolve_scene_quality` in `parameter_resolution.py` is the one place the two combine, so the request carries effective values (`samples`, `bloom`, `motion_blur`) plus the tier (`detail`) for tier-only features (shadows, spark budget); renderers never consult the tier for anything a transition can set.
- **Bloom** (`rendering/quick/scene3d/post.py`): only emitted light glows. While a scene renders into a bloom target, its alpha is the brightness of the light each pixel emits (opaque passes write theirs; additive sparks add theirs); a bright pass scales each pixel to that brightness, then four half-float levels blur and add back. Photographs write 0, so a bright sky never glows and endpoints stay exact; Exploding Tiles marks sparks, hot cracks, embers and the flash (not the fireball's wash, which is light on the picture). Measured at 2560x1440 on an RTX 4090 (GPU median per frame, Exploding Tiles): direct 0.036 ms, 4x 0.071 ms, 4x with bloom 0.129 ms, bloom without anti-aliasing 0.102 ms.
- **Motion blur** (`rendering/quick/scene3d/motion.py`): moving pieces blur along their own screen motion over a fixed real-time shutter (`SCENE3D_SHUTTER_SECONDS`, 1/60 s: the whole frame interval at 60 Hz), so a piece blurs by how fast it moves on screen whatever the run's duration. Motion Blur is Off by default on every transition, and the first 180-degree shutter (1/120 s, blur capped at 1/30 of the height) read too weak on High, so the shutter doubled and the cap rose to 1/20 of the height. With motion blur the scene target has a second attachment (RG16F) that is write-protected while the scene draws. The passes that move write into it inside `SceneTarget.velocity_writes()`, and their vertex shaders evaluate every point analytically at t and t - shutter (`sceneVelocity`). Exploding Tiles' slabs do this through `tileAtTime`; the photograph, shadows and sparks (already streaks) write none. The other four draw motion variants of their own shaders made by `scene3d_motion_vertex` / `scene3d_motion_fragment`: the vertex `main` becomes a function of the run's time input (`uProgress`; Block Spins' `uAngle`) and runs at t - shutter and at t, and the fragment also writes the motion. Glass shards, Crumble chunks and chips, Accretion tiles and Block Spins' slab write motion; photographs and the void write none. With Motion Blur Off each draws exactly its own program (105 frames across the five transitions and every tier, pixel-identical to before). The reconstruction follows McGuire et al. 2012 without depth (moving pieces are in front of the still photograph). It runs a compute tile max (K = 1/40 of the height; the longest blur is 2K; S15, `Docs/Reference/Scene3D_Resources.md`), then a 16-tap gather along the motion of the pixel's 3x3 tile neighbourhood with a quarter-tap integer-hash jitter. Where nothing nearby moves the pixel is returned unchanged, so still frames and endpoints are exact, and so is everything with Motion Blur Off (pixel-identical to before it existed). Measured at 2560x1440 on an RTX 4090 (4x), before S15 replaced the fragment tile and neighbour maxima with one compute dispatch: Exploding Tiles +0.08 ms GPU (resolve 0.029, tile max 0.019, neighbour max 0.003, gather 0.031); a moving surface that fills the screen costs the most, 3D Block Spins' gather 0.087 ms (about +0.15 ms in all). CPU submit rises ~0.25-0.3 ms (about 70 more GL calls); ~105 MB more VRAM per display at 4x while a run lasts (motion attachment 60, its resolve 15, resolved colour 15, blurred scene 15).
- **Photo reflections** (`rendering/quick/scene3d/environment.py`, `sceneEnvironment` / `sceneReflectionUv` / `sceneEnvironmentLight`): once per run the destination photograph is box-filtered into a 512 px, renderer-owned, mipmapped copy (4K photo: ~0.07 ms GPU, ~0.2 ms CPU). The lent presentation textures are only sampled, never given mip levels. Glossy surfaces read the copy blurred by roughness, taken as a mirror ball: the reflected ray's direction, not the surface's place on screen, picks the point. Used where it improves on the prior look. 3D Block Spins' Edge Glass reflection reads it, fixing early diagonal spins, which reflected only the photo's top border and looked dark and flat. Glass Shatter's Fresnel reflection carries the new photo's colours instead of a constant blue-white; sheen zero still removes all reflection. Released Exploding Tiles reflect the new photo on their photo faces (glossier) and stone sides (rough); the wall is exact until each tile's release. The copies are dropped at the host's `park()`.
- **Motion Trails** (`rendering/quick/scene3d/trails.py`; Off/On, Off by default, offered only on 3D Block Spins, Exploding Tiles, Glass Shatter, Crumble and Directional Pixel Accretion). These are faint, fading, light outlines of where pieces just were. Each effect draws its pieces three more times, 0.045 s of real time apart (`scene3d_trail_ghosts`), as flat silhouettes. The ghost variant is `scene3d_ghost_fragment` of its motion-writing shaders, so a ghost also knows where its piece is now: a piece that moved less than the trail line reaches draws no ghost. The silhouettes are MAX-blended with the newest brightest. An edge filter turns them into soft lines (about 1/540 of the height), laid over the photograph before the pieces draw, so a piece covers its own trail. A still or slow piece never trails or wears a halo (a nearly still run is pixel-identical with trails On), and a dense field of moving tiles still trails. The trails need the scene target. The ghost pass binds each program variant and its invariant uniforms once, then varies only ghost time-dependent fields and fade. Crumble groups chunks and debris by variant; depth-free MAX blending preserves the result. Exploding Tiles rebinds a patched copy of its ghost block per ghost through its stream ring (`Docs/Reference/Scene3D_Resources.md`), independent of generic buffer bindings. Five representative before/after captures are pixel-identical. The original 2560x1440 (4x) measurement was +0.05-0.3 ms GPU and +0.5-1.0 ms CPU per frame. A bounded 960x540 CPU-submit comparison (six warm submissions, 24 samples, fixed progress, trails On) measured total medians before/after of 1.841/1.413 ms for Block Spins, 2.489/2.465 for Tiles, 1.850/1.444 for Glass, 2.184/1.801 for Crumble and 1.850/1.788 for Accretion. These small driver-sensitive samples establish reduced setup work, not a universal timing gain; Tiles' p90 rose from 3.033 to 3.804 ms in that run.
- **Scene target resolve:** the target's colour is a texture that the composite reads directly, averaging the samples itself. With bloom, one shader pass resolves the allocation first. A single-sample target (bloom without anti-aliasing) draws exactly like a direct draw. See the lessons below.
- **3D Detail** (`transitions.detail_3d`, Transitions -> SETUP -> 3D Rendering) is the default every Auto choice follows: **High** renders into a 4x multisampled `SceneTarget` with soft shadows and every spark; **Balanced** draws straight into Quick's target with shadows and 60% of the sparks; **Performance** skips the shadow pass and keeps 30%. The tier also sets the bendable grid's density (192 / 128 / 64 cells along the longer side). An unknown stored value uses the canonical default. Measured at 2560x1440 on an RTX 4090 (Exploding Tiles, warm, GPU median per frame with a per-frame flush): 0.129 / 0.099 / 0.014 ms for High / Balanced / Performance. The High target is ~120 MB of VRAM per display at that size, plus ~25 MB with bloom. High and Balanced admit post effects (Auto Bloom on); Performance does not.
- **Camera.** Effects project through `sceneProjectAt` (their authored resting distance) or `sceneProjectCamera` (offset, tilt, zoom). A camera that moves must draw the photograph through it (`MeshResources.draw_camera_plane`) with the zoom from `scene3d_camera_overscan`, so no frame edge is ever exposed (R-63); shake comes from `scene3d_camera_shake` at real-time rates.
- **Page Curl** (`rendering/gl_programs/page_curl_program.py`) is the first consumer of the bendable grid. Each strip of the page along the peel direction winds behind the moving line into a loose Archimedean roll: the free edge innermost (radius 0.05 of the picture's height), 0.01 more radius per radian, so the roll grows with what has peeled (about 0.2 for a whole diagonal) and a corner peel makes a conical roll. `sceneDisplace` solves the spiral for arc length exactly (four Newton steps), so the sheet never stretches, and tilts the roll so the sheet leaves the page level, with no crease; once a strip has peeled completely its roll rolls on. The line moves at an even pace with soft quarter-run ramps (no rush through the middle; operator 2026-10-03: the first single fold was not gradual, curled too little and looked like dull paper) until the largest roll is 1.6 radii past the far side; the shade under the roll (strongest at its foot, falling off over 1.2 roll radii) fades out from half a roll past the far side, so the run ends on the new picture exactly. The flat page is the photograph exactly (the grid at rest). The lifted sheet is a vivid print gently shaded by its turn (never greyed by diffuse lighting) under a clear coat (shared material's specular and photo-environment reflection), with its cut edge catching the light; the back is chosen per pixel by which way its normal faces the camera. Grid density follows the 3D Detail tier; the tier's grid is built by the gradual warm-up. Measured at 2560x1440 (RTX 4090), median (p90): High (4x) 0.64 (0.71) ms CPU submit and 0.076 (0.091) ms GPU per frame; Balanced 0.48 ms and 0.028 ms; Performance 0.48 ms and 0.022 ms.
- **Cube Turn** (`rendering/gl_programs/cube_turn_program.py`) draws the shared unit box (`SCENE3D_BOX_VERTICES`, also Blinds' slat) as deep as the picture is wide (left/right) or tall (up/down), so its side has the new picture's shape. It turns a quarter about its centre (eased) while the camera's zoom dips by 0.22 x sin(pi e) and returns, so at rest the front, and once turned the side, lie exactly on the photograph. The side shows the new picture where it rests after the turn. Faces are lit by the shared material, blended by sin(2 angle). The backdrop is the renderer-owned copy of the new picture at mip 5, at 35%. Measured at 2560x1440 (RTX 4090): High (4x) 0.55 ms CPU submit and 0.056 ms GPU per frame (median); Balanced 0.39 ms and 0.025 ms.
- **Relief Rise** (`rendering/gl_programs/relief_rise_program.py`) displaces the bendable grid by a height field: each point's phase follows its rank along the sweep (a front 0.4 of the sweep wide, eased), its height is 0.16 x depth x sin(pi x phase) times the blended brightness, and its colour crosses from old to new around the peak. Heights are read from the renderer-owned, mipmapped photo copies (both roles, mip 1.5), never from the lent photographs, so the relief is smooth on every tier. Phases of exactly 0 and 1 are flat and unlit, so ahead of the wave, behind it and both ends are the photographs exactly. The relief is lit by the shared material with a reflection of the new picture, and S17's first contact-occlusion term darkens hollows from six height samples around each point. The second copy sits on texture unit 3, outside the host fence, so the renderer hands that unit back itself. Measured at 2560x1440 (RTX 4090): High (4x) 0.52 ms CPU submit and 0.115 ms GPU per frame (median); Balanced 0.39 ms and 0.044 ms.
- **Accordion Fold** (`rendering/gl_programs/accordion_fold_program.py`; reworked 2026-10-03 after the operator found the fold-and-slide of no visual value) folds a two-sided sheet on the bendable grid: a point `a` from the folding edge lies at `a cos(fold)` and as high as its distance from the nearest crease times `sin(fold)` (a fold, never a stretch) as the fold opens to 0.36 pi over the first 40% of the run; the folded stack then turns over by pi about its own middle, lifting clear of the picture as it turns (until 58%); and the sheet unfolds back up, a point then at `(length - a) cos(fold)` with ridges and valleys swapped, exactly where the turned stack left it. Laid flat back up, the back's mirrored print lands exactly on the new picture. Which side shows is chosen per pixel by the grid normal's facing, so the turning stack shows both. The grid puts a vertex row on every crease (`accordion_grid`) and each pleat is shaded flat from its own screen-space normal: a vivid print shaded by its tilt (0.62 to 1.12) under a light sheen and photo reflection (Gloss), blended in by the fold so the flat sheet at both ends is exact. The backdrop is a nine-tap tent blur of the renderer-owned copy of the new picture at mip 4, at 62% (a single bilinear tap shows the texels). Measured at 2560x1440 (RTX 4090), median (p90): High (4x) 0.62 (0.69) ms CPU submit and 0.087 (0.092) ms GPU per frame; Balanced 0.43 ms and 0.051 ms; Performance 0.43 ms and 0.050 ms.
- **Disintegrate** (`rendering/gl_programs/disintegrate_program.py`) is the first `CompactedPopulation` consumer (`Docs/Reference/Scene3D_Resources.md`). Grains are a device-pixel grid capped at 600,000 (larger grains past that). The release time per grain is the front's rank along the wind, roughened by smooth value noise on the exact integer lattice hash, plus jitter; every grain is gone by 0.97 of the run, so frames from 0.97 on, and before the first release at 0.03, are the photographs exactly through the full population path. The intact picture is one pass that shows the old picture before each grain's release and the new one after; live grains are evaluated once each in compute and drawn with one indirect draw, blended over each other in id order (deterministic). Per-frame values travel in one streamed uniform block shared by the intact pass and both population passes. The population (~20 bytes per grain, about 8 MB at 2560x1440) is per run and released at `park()`. Measured cost and the comparison with per-vertex evaluation: `Docs/Reference/Scene3D_Resources.md`.
- **Materials (S17).** `SceneMaterial` (albedo, perceptual roughness, metalness, dielectric specular, emissive) and `SceneLight` (directional, point or spot with a smooth range window and cone) feed one GGX/Cook-Torrance BRDF with Smith-Schlick visibility and Schlick Fresnel (`sceneBrdfLight`, `sceneMaterialLit` for the key light plus ambient and emission, `sceneMaterialLight` per local light). Photo-environment light uses the split-sum approximation with Karis' analytic environment BRDF (`sceneMaterialEnvironment`), so no BRDF lookup texture is allocated. Every function has a CPU mirror checked on the GPU; a rough white dielectric lit head-on reflects between 80% and 100% of the incoming light. Blinds 3D Slats is the first consumer; `sceneShade` stays for the existing effects.
- **Per-frame CPU.** Shared per-frame values travel in one std140 uniform block (`rendering/quick/scene3d/uniforms.py`, layout from `Scene3DBlockLayout`), written into a persistently mapped, fenced stream ring (`stream.py`); the fence and 3D helpers read GL state through `rendering/quick/gl_query.py` (raw getters, ~5x cheaper than PyOpenGL's checked ones). Exploding Tiles: warm CPU submit ~0.9 ms per frame.
- **Per-run memory.** `QuickTransitionRenderHost.park()` runs when the background node parks after every run (`release_presentation_textures`); renderers drop per-run targets there (the `SceneTarget`) and keep programs and meshes warm. The host fence now also restores draw/read framebuffer bindings and the blend equation and function, so a renderer that fails mid-scene cannot leave Quick drawing into its target.
- The mesh effects draw the destination (departure effects) or source (accretion) beneath the pieces. Exact full-image endpoint draws are supplemented by near-endpoint continuity tests so endpoint branches cannot hide pops.
- The shared Quick host restores GL state on exceptions. Depth clearing intersects the active scissor and viewport, then restores scissor state. Partial cleanup retains failed handles for retry; disable/context retirement releases owned resources.
- New Settings pages follow the same lazy build, hydrate, save and retirement owner. Canonical defaults and generated snapshots remain under the existing Settings authority.
- Crumble's weighting menu names the actual release order: Top, Bottom, Random Weighted, Random Choice and Age Weighted. Former Bias Old Image/Bias New Image values both resolved to Top; reopening and saving replaces those misleading labels. The unused mosaic request field has been removed.

## Verification and remaining acceptance

`tests/test_qtquick_future_transition_gl.py` renders through the real driver and production host to check exact/near endpoints, repeatability, parameter and direction sensitivity, and resource retirement. Focused `crumble_volume`, `melt_surface`, `organic_surfaces`, `transition_material_settings` and `tile_departure` tests cover bounded topology, material controls and continuous departure; registry/request/Settings/run/fence suites cover integration.

`tools/transition_contact_sheet.py` produces textured progression frames, optional supplied-image contact sheets, and a 60-frame/two-second WebP with `--animate`. It accepts `--source` and `--destination` photos, and `TransitionCapture.run(..., duration_ms=)` renders real-time motion (Exploding Tiles' rumble) at an authored duration instead of the 1000 ms default; `--quick-smoke` reuses the existing threaded QQuickWindow lifecycle harness. See `Docs/Reference/Harness_Index.md` for commands. Diagnostic timing includes context/driver effects and is not a claim of performance neutrality.

The open perceptual/freshness work is tracked only in the Physical acceptance checklist below; automated pixel/scene evidence cannot close those items.

## Owners and invariants

- `rendering/transition_registry.py` owns identities/activation participation; `core/settings/default_settings.py` owns values, with existing Settings UI/model/schema integration.
- `rendering/quick/transitions/parameter_resolution.py` resolves settings, direction and seeds once before immutable `TransitionRequest` admission. `state.py` owns monotonic progress/exactly-once completion; effects never create clocks or CPU simulation loops.
- `implementation_registry.py` lazily resolves implementations; `render_host.py` owns the context-local lifetime and inherited GL-state fence. The existing display render node remains the sole presentation surface.
- `rendering/quick/transitions/implementations/block_spins.py` and `rendering/gl_programs/blockspin_program.py` prove mesh/depth resources inside Quick. Voxel Sphere is an independent consumer to inspect for small identical resource seams, not a transition foundation or base class.
- Existing transition tests, `tools/qtquick_render_node_smoke.py` and `tools/qtquick_phase_c_effect_smoke.py` provide production host, endpoint, fence and real-GL seams.

## Resource rules

Feature-local: fracture topology and metadata, tile motion/material shaders, growth formulas, per-run seeds, image mapping. Justified shared primitives may include a small context-local mesh/program holder and fullscreen image underlay used by the actual new mesh consumers. They must stay lazy, own no clock, preserve failed-cleanup handles and support partial-allocation cleanup. Do not build a scene engine, generic physics, material hierarchy or always-live 3D subsystem. Instancing derived from `gl_InstanceID` needs no per-frame instance upload.

Depth clears must stay within the transition viewport and restore scissor state; the existing host restores depth/cull/program/VAO/buffer/texture state on success and failure. Resources retire on disable/context retirement using the existing legal owner. Per-run buffers may be reused only while their geometry key matches.

## Negative controls (binding)

- Melt: no detached sphere/capsule/bulb bodies, no ray-marched pseudo-volume, no narrow wet-band front (rejected), and no seams that cut the photograph into slabs (R-94: exact integer lattice hash).
- Glass/Tiles: no premature in-viewport shrink or fade as a departure substitute; every piece leaves the frame. Exploding Tiles' sparks burn out (they are not departing pieces) and a tile's shadow fades as its tile leaves the view.
- Exploding Tiles: no ease-in launch (the rejected "falling tiles": pieces started from rest and accelerated), no crack glow across the whole wall, no brown/wood sides.
- Organic effects: no generic feathered mask under a new identity; Tendril Reveal stays retired.
- No clocks, evolving CPU fluid simulations, parallel surfaces or fallback effects; per-run options are solved once
  (Glass collisions/re-shatter, Crumble Slabs Collide) and evaluated analytically on the GPU.

## 3D foundation lessons (binding)

Learned the hard way while building the shared 3D foundation. They bind every change to the foundation
(`rendering/gl_programs/scene3d.py`, `rendering/quick/scene3d/`) and every new 3D transition or Visualizer mode.
Each foundation slice adds what it learned here.

**Measuring**
- GPU cost: `GL_TIME_ELAPSED` around a whole frame or one stage, over at least 90 frames, reporting median and p90.
  Flush after every frame as presentation does (`TransitionCapture.benchmark` does). Without a flush, the driver's
  command-buffer boundary lands inside a query and counts the GPU waiting on the CPU: periodic multi-ms spikes
  (every ~9 frames) that are not rendering cost.
- Find where a cost is spent by removing the operation (a skip variant) and timing with `GL_TIME_ELAPSED`.
  `glQueryCounter` timestamp deltas pinned the resolve's cost on the wrong call.
- Before/after on the same machine and build: load the old module next to the new one in the harness, never compare
  against numbers from an earlier session.
- CPU: every PyOpenGL call also runs `glGetError` (~4 µs). Count GL calls per frame and measure CPU submit. Read state
  through `rendering/quick/gl_query.py` (raw getters) and send shared per-frame values in one uniform block. Raw
  entry points only help getters (they skip building an output array); a raw setter costs the same ~2 µs, so cut the
  number of calls instead (no redundant unbinds or state the caller already set).
- Stage timing needs `GL_TIME_ELAPSED` queries that do not nest: time the top-level stages or the leaf passes,
  never both in one run.

**Rendering**
- No `glBlitFramebuffer` resolves (~0.5 ms at 1440p on drawn content, whatever the sample count). Render into texture
  attachments and resolve in the shader that reads them.
- A single-sample target is a plain texture: a 1-sample multisampled renderbuffer does not rasterise like a direct
  draw.
- Post effects work only from emitted light (alpha in a bloom target); photographs write 0, so endpoints stay exact
  and bright photos never glow.
- A per-pixel loop over a whole tile in one pass starves the GPU of parallelism (Motion Blur's 24x24 tile max took
  0.118 ms at 1440p); split it into separable passes (0.019 ms, identical output).
- Stochastic sampling needs its jitter checked on real photos: a full tap of white-noise jitter left sandy speckle
  along blur edges and ordered (Bayer) dither left stripes; a quarter tap with 16 taps is clean. Fewer, heavier taps
  read as grain: taps adapted to the blur length (4-16) saved 0.04 ms but stippled fast blurs, so the gather keeps 16.
- New shader variants (motion, and later others) are made from the effect's own sources by one tested transform,
  and the feature Off draws the original program, so Off stays pixel-identical by construction; prove it against
  HEAD in a worktree anyway.
- An after-image (trail, ghost) decides from its own motion whether to draw: a whole-frame mask of what is still
  here killed every trail in a dense field (Pixel Accretion) and a fixed dilation left specks along slivers; a
  ghost that knows where its piece is now simply skips pieces that barely moved.
- A reflection of the photograph is looked up by the reflected ray's direction (`sceneReflectionUv`), never by the
  surface's place on screen: a screen-position lookup made every edge near the top of the screen reflect the
  picture's top border, so early diagonal Block Spins read dark and flat while X/Y spins looked fine.
- A refactor onto shared functions keeps every expression's operation order (return a product's factors
  separately rather than regrouping them); floating point is not associative. Then prove pixel identity against
  HEAD in a worktree, per tier and option.
- Photo textures are lent: sample them, never modify them (no mipmaps, no writes). Anything derived is a
  renderer-owned per-run copy.
- Reflection or refraction on thin geometry (slab edges, bevels) needs a normal that varies across the face (a rounded
  edge). A flat thin face samples a single column of the picture and reads as a smear.
- A transition resolved in more than one place (production and the capture harness) calls one shared resolver, or
  the harness silently drops new settings.
- Randomness in GLSL is the integer hash with a CPU mirror checked on the GPU (R-94); float `fract(sin())` hashes
  seam.
- Allocate per run or per 64 px bucket and release at `park()` (transitions) or retirement (modes); nothing per frame.
- Interactions between pieces (Glass depth layers and collisions, Crumble Slabs Collide) are solved once per run on
  the CPU/COMPUTE and evaluated analytically on the GPU.

**Streaming per-frame data (S14)**
- Changing per-frame bytes go into the persistently mapped ring and are bound with multi-bind, which leaves the
  generic binding alone: no per-frame buffer re-specification, sub-data writes or generic-binding save/restore.
- A ring slot is written again only after its fence, and slots rotate only when no binding scope is open: a scope's
  exit restores the previous binding, so nothing submitted later can read the ring. Never rotate inside a scope.
- Never rewrite bytes a submitted draw may still read: an update writes a new copy and rebinds it.
- A new transport earns its place by removed calls, not by being modern: a storage buffer replacing two
  `glUniform*v` calls costs more (save, bind, restore), so small fixed values stay uniforms.

**Compute (S15)**
- Compute earns a stage only where it removes passes, targets or calls. Analytic particles culled in the vertex shader,
  single instanced draws and per-level post chains gain nothing; a per-run result the GPU must re-bind every frame can
  cost more CPU than the CPU work it replaces.
- A workgroup per tile with an invocation per row reproduces a separable column-then-row reduction exactly (first
  strictly longest at each step) and beat the two fragment passes, without the per-fragment tile loop that starved the GPU.
- Differences of tens of microseconds between separate processes are GPU clock state: alternate old and new code frame
  by frame in one process (load the old module beside the new one) before believing either direction.
- The writer issues the barrier its reader needs, straight after the dispatch. NVIDIA hid a missing barrier completely,
  so test the dispatch -> barrier -> reader order and bits, not pixels alone.
- Image units are not fenced by the host: bind them through `bound_image`, which hands the unit back.

**Materials and new looks on old transitions (S17)**
- Lighting a photograph changes its pixels: blend the lit look in by how far a piece is from rest (Blinds' lift,
  4e(1-e)), never by a separate endpoint branch, so rest, ends and near-ends are exact by construction.
- A new style on an existing transition keeps the old style untouched and dormant: its shader module loads, and its
  scene resources allocate, only when the style is used (the lazy-import bar caught the first draft importing it).
- Prefer analytic approximations to lookup textures when they cost a few ALU instructions (the environment BRDF):
  nothing to allocate, warm or release.

**Textures outside the fence**
- The transition host restores texture units 0-2 only. A renderer that binds unit 3 or above hands it back itself
  (and its test binds a sentinel there); widening the shared fence would cost every transition every frame.
- A mirror-tolerant pixel bar can be blind to drift in one direction (a narrower wave only enlarges the exact regions
  it checks); test the shader's own GLSL against its CPU mirror directly.

**Populations (S16/S18)**
- Compact only when the pool is large: compaction trades a fixed CPU cost (three dispatches, barriers, bindings) for
  GPU work that scales with the pool. Measure it against per-vertex evaluation of the whole pool, alternating per frame.
- Keep id order through compaction (prefix sums, not atomic append) whenever members blend over each other; then the
  same frame is the same pixels on every run and GPU.
- `MeshResources.uniforms` caches the first name list per program: a shared pass sets its own uniforms through its
  own location cache, and a pass may legitimately not read every hook uniform (look those up with `required=False`).
- Direction labels must describe what the viewer sees, and one convention holds everywhere: a label names where the
  motion starts and the way it travels ("Left to Right" starts on the left; a diagonal starts in its first named
  corner), and a resolved code names the way it travels (``right``). Until 2026-10-03 the shared map sent
  horizontal labels to the starting side while renderers read codes as the travel, so Glass Shatter, Exploding
  Tiles, Pixel Accretion, Slide and Block Spins ran their horizontal labels backwards (Block Flip's vectors were
  mirrored to hide it); Burn read texture v as pointing up, reversing its vertical and diagonal labels and its ash
  drift; Block Spins' diagonals spun about the named diagonal instead of sweeping along it.
  `tests/test_transition_direction_labels.py` renders every labelled direction of every transition through the
  production resolver; a new directional effect joins it.

**Preparing runs (S11)**
- A run's first frames compile and allocate nothing they could have prepared. Every renderer lists the programs
  a run with given parameters uses in `warm(parameters, size)` and then allocates its scene textures through
  `warm_run_resources`; a new program, variant or per-run texture goes there too, or `test_transition_warmup.py`
  fails. Allocate with the same method the run's first use calls (`SceneTarget.warm`, the chains' `warm`), so the
  two cannot drift.
- Only the next transition's textures are held, from its warm-up until `park()` after its run: never keep
  textures for transitions that are not next (they add up as transitions are added).
- Prepare while the displays are idle, never at the image change: that resolves its transition ~14 ms before the
  first frame. The next transition is settled when the previous one completes (a reserved Random pick and a batch
  seed), so the batch meets the spec that was warmed and the geometry COMPUTE built.
- Compile gradually on frames the window renders anyway: one program per step, steps at least 0.2 s apart. No
  startup work, no bursts, no timers, no threads, no polling, no forced frames, and no driver parallel-compile
  threads.
- GL work on `beforeRendering` is bracketed by `beginExternalCommands`/`endExternalCommands` and restores the
  inherited state like a render does.

**Motion and look**
- Real-time rates (rumble, shake, flicker) run on real seconds (`uSeconds`), not progress, and are judged at long
  authored durations (8000 ms), not the harness's 1000 ms default: the jarring rumble only showed at length.
- Pieces launch with their full speed (no ease-in: that read as falling), and every piece leaves the frame.
- Judge looks on real photos. Render new animations only for new transitions, not for tweaks to an existing one.

**Settings**
- A transition's quality choices (Anti-aliasing, Bloom, and future ones such as Motion Blur) live on its own page.
  "Auto" follows the global 3D Detail tier, and any other value wins over it. `resolve_scene_quality` is the only
  place the two combine, and renderers never read the tier for a value the transition can set.
- Choices shared by the Settings page and the resolver live in an import-safe module (`scene3d.py`,
  `blockspin_options.py`). The runtime imports the Settings tabs, and a `*_program` shader module may load only when
  its transition renders; the import-isolation tests in `test_qtquick_transition_implementations.py` enforce it.

## Physical acceptance (open)

Automated image differences are not aesthetic acceptance. One operator pass remains:

- [ ] appearance and timing with actual photos at authored durations, including optics/depth controls;
- [ ] Glass Shards Collide / Shards Break Again, and Crumble Slabs Collide (default and low Collapse Depth), judged in
  motion;
- [ ] Crumble crack complexity at its default and debris;
- [ ] Motion Trails (Off by default) on the five transitions that offer it: strength and length on real
  photos;
- [ ] Photo reflections: Block Spins Edge Glass in both halves of diagonal spins; Glass Shatter's and
  Exploding Tiles' reflections on real photos (deliberately subtle: tell apart from before at full size);
- [ ] Motion Blur (Off by default) on all five 3D transitions: strength of the 360-degree shutter at their
  default durations and at short ones, the blur's edges on real photos (Block Spins' fast mid-spin blur especially), High and
  Balanced;
- [ ] 3D Block Spins Edge Glass: Reflection, Refraction and Both on real photos in every direction, next
  to Off (the sheen and gloss must read the same);
- [ ] Exploding Tiles: build-up, rumble and detonation timing, burst and drift pacing (debris clears by ~65-80%), side colour, sparks, shadows and flash strength on several photos and directions; 3D Detail High vs Balanced vs Performance on both displays, including cost with active Visualizers;
- [ ] both displays with active music and representative heavy load: Visualizer freshness, frame-spacing tails and
  transition first use;
- [ ] Direction labels (2026-10-03 truth fix): Glass Shatter, Exploding Tiles, Pixel Accretion, Slide and 3D Block
  Spins now move "Left to Right" from the left; Burn's "Top to Bottom" and diagonals burn from the top, and its ash
  now falls; Block Spins' diagonals sweep from the named corner. Check each on real photos;
- [ ] Cube Turn on real photos in every direction at 4000 ms: turn pace, how far the camera draws back, the
  backdrop's dimness, Gloss;
- [ ] Relief Rise on real photos in several directions at 6000 ms: relief height (Relief Depth), the colour crossing
  at the peak, hollow darkening, Gloss; High vs Balanced vs Performance grid smoothness;
- [ ] Accordion Fold (fold, flip, unfold; reworked 2026-10-03) on real photos toward every edge at 5000 ms: pleat
  count, the light on alternate pleats, the flip's pace and height, the unfolding back, the frosted backdrop's
  brightness, Gloss;
- [ ] Disintegrate on real photos in several wind directions at 6500 ms: grain size, wind strength, swirl, the noisy
  front and fade; High vs Balanced on both displays, and GPU cost with active Visualizers;
- [ ] Page Curl (laminate roll, 2026-10-03) on real photos from every origin at 5000 ms and longer: roll size and
  growth, pace, the print's colour on the roll, the clear coat and Gloss, the shade under the roll, High vs Balanced
  vs Performance smoothness of the roll on both displays;
- [ ] Blinds 3D Slats on real photos in both orientations at its default 4000 ms and longer: the wave's pace, slat
  lighting and Slat Gloss, the shade through the gaps, 6 vs 48 slats, High vs Balanced;
- [ ] the installed/frozen build: activation and Settings round-trip, repeated switch/interrupt/retire.
