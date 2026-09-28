# Future Work

The single live router for deferred features and dormant ideas. `Current_Plan.md` owns active work; this file keeps
good ideas, their admission rules and a suggested order so they survive without widening current scope. Technical notes
are provisional: inspect the **current** Qt Quick architecture before coding any of them.

## 1. Authority and activation

This file is **not active sequencing**. An agent may implement an item only when:

1. the operator explicitly asks for a named item (this overrides the normal sequencing: unfinished `Current_Plan.md`
   work is not a reason to refuse or defer it; only a genuine technical prerequisite may block it, and where practical
   that prerequisite becomes the opening slice of the requested work); or
2. `Current_Plan.md` has no remaining important active work. A horizon-gated persisted-input bridge
   (`Docs/Architecture/Persisted_Input_Compatibility.md`) is dormant user-data protection and does not block this.

Reading, indexing or cross-linking this file is not permission to begin a feature. When an item is promoted, move it to
`Current_Plan.md`; when it is implemented and accepted, delete it here and leave its durable contract in `Spec.md` or the
relevant `Docs/Reference/` document.

**Decomposition rule.** Before substantial coding on long, sizeable or architecturally unique work, commit a focused
decomposition (a `Docs/Future_Work/<Name>.md` live checklist, created only when needed) that:

1. inventories the current foundation and names the real source/tests that already own it;
2. pins a rollback/comparison HEAD;
3. defines state, cadence, Settings, presentation, GPU/resource and retirement ownership;
4. classifies new primitives as **feature-local**, **justified reusable infrastructure** or **speculative reuse
   deferred** until a second concrete consumer proves it;
5. splits the work into resumable slices that leave the repository coherent;
6. separates deterministic/source, lifecycle/resource, performance and eyes-on visual acceptance bars;
7. keeps explicit landed/remaining status, and is deleted when the work closes.

Build the requested vertical feature first; extract only reuse the real implementation justifies.

## 2. Admission rules for new effects

### 2.1 Workflow (every transition or Visualizer idea)

- [ ] Record the visual contract and a rollback reference; classify the idea as a **new transition**, an **option of an
      existing transition**, or a **distinct Visualizer mode** before coding.
- [ ] Wire it to the canonical catalog/descriptor/defaults, a lazy implementation and the one Qt Quick scene from day
      one. Expensive resources stay module-local; no parallel experimental engine or Settings shadow tree.
- [ ] Use deterministic seeds/inputs and test owner state, disabled dormancy, GPU retirement/context loss, Settings and
      removability; preserve accepted owners and Visualizer goldens.
- [ ] Validate native Quick rendering, measured GPU/event-loop/frame/freshness cost, visual quality on real photos and
      multi-display behaviour where material. A shader that compiles, or an offline preview, is not acceptance.
- [ ] On acceptance, offer it through the existing Settings/cycle/transition flow. On rejection, delete the
      implementation, descriptor and owned canonical state (with one bounded migration if profiles can hold old
      values); leave no dead branches.

### 2.2 Transitions

- A **new identity** adds one cheap descriptor plus a lazy implementation to the existing registry/host and uses the
  current transition source/state/presentation/Settings authority. It starts deactivated until the operator accepts
  it. Deactivated: no heavy imports, shaders, buffers, cadence or frame work; enable → switch away → retire releases
  every owned GPU/context resource.
- A **modifier of an existing effect** (Slide → Perspective Push, Blinds → 3D Slats) extends that effect's single
  descriptor/implementation and options. No fake identity for removability; revisit the boundary only if independent
  resources, owners or cadence emerge.
- Effects consume the monotonic transition run; they may author deformation/easing/physics deterministically from it
  but never become another clock. Per-run options are solved once (at request resolution or on COMPUTE) and evaluated
  analytically on the GPU.
- Persisted values stay in `default_settings.py` / SettingsManager under the accepted schema namespace. Descriptor
  metadata chooses generic Settings participation and is never a second default/value authority.
- Settings bodies stay lazy and transactional: attach on complete success, remove a partial body on failure, retry
  without duplicate controls. New persisted bucket keys need canonical UI-state defaults and identity tests.
- Removal proof: deleting the implementation, one registry entry and its owned settings/tests/docs leaves shared hosts
  and unrelated options working; a source search for the ID shows only justified references.

### 2.3 Visualizer modes

- Each mode (**Unique Mode**) has one canonical descriptor and its own lazy logical/runtime/renderer/Settings
  implementation, per-mode settings and preset authority, and an explicit shell/clip policy (CARD + CARD_INTERIOR or
  FRAMELESS + VIEWPORT_RECT). It may reuse shared analysis bands, the typed transient bus, shader utilities and proven
  math, but it never runs another mode's runtime, installs a second clock or adds a switch outside the descriptor seam.
- `VisualizerLogicalRuntime` stays the authored clock: presentation may not discard logical steps or turn render
  refresh into simulation cadence. History (spectrum rows, recent events) is bounded plain data owned by the mode's
  logical state and carried whole in the immutable snapshot.
- Follow `Docs/Guides/Visualizer_Reactivity_Authoring.md` §12 (reaction vocabulary, separate presence/admission/
  magnitude/sustain, hot-chorus tests) and `Docs/Guides/Visualizer_Change_Checklist.md`. Canonical, wide and tall
  viewports keep authored amplitude (R-69).
- The accepted **Voxel Sphere** and the **Bubble** reaction contract are golden and are not modified by a new mode
  (`Docs/Reference/Sphere_Visualizer.md`, `Docs/Guardrails/Bubble_Temporal_Fidelity.md`).

### 2.4 Shared 3D foundation and dormancy

**Operator direction (2026-09-29), superseding the earlier "extract only what two consumers prove identical" rule for
transitions:** build and grow a shared 3D foundation when it raises fidelity at low, adjustable cost. It exists now:
`rendering/gl_programs/scene3d.py` (GLSL library + CPU mirrors: hash, camera with near-plane clipping, impulse flight,
departure solver, lighting, ember colour, planar soft shadows, streaks, and the 3D Detail tier table) and
`rendering/quick/transitions/scene3d_support.py` (blend scopes and the multisampled `SceneTarget`), with the host's
`park()` after every run and a fence that restores framebuffer and blend state. Contract and measurements:
`Docs/Reference/Transitions.md`. New 3D transitions start from it; a capability two effects would repeat belongs in it.

Other 3D consumers: 3D Block Spins, Glass Shatter, Crumble and Directional Pixel Accretion (`mesh_support.py`), and the
isolated experimental Voxel Sphere (Visualizer). Proven seams there: `gl_InstanceID` instancing, per-run CPU geometry
prepared on COMPUTE (`run_geometry.py`), per-run tables read by vertex texture fetch (Crumble's motion table).

- When every consumer of a 3D path is dormant, its meaningful overhead is dormant too: no shader compiles, meshes,
  buffers, targets, depth work, workers or cadence. Per-run targets are dropped at `park()`.
- Every fidelity feature has a cost switch in the 3D Detail tiers; the cheapest tier stays close to a plain draw.
- Sphere is an independent consumer, not a foundation or base class; its Settings, state, materials and shaders stay
  private. A 3D Visualizer mode may use `scene3d.py`'s GLSL, never Sphere internals.
- No generic scene graph, material hierarchy, physics engine or always-resident "3D engine"; per-effect state stays
  analytic and local.

**Foundation next — promoted 2026-09-29.** The foundation plan (self-test harness, shared home and Visualizer option,
uniform blocks, camera, migration of the other 3D transitions, bloom, motion blur, shared particles/shadows/grid,
photo reflections, cheaper High, first-frame compile) is active work: order in `Current_Plan.md`, detail in
`Docs/Future_Work/3D_Scene_Foundation.md`.
- Performance: no Python/QObject object and no draw call per shard/tile/particle; instance repeated geometry; build
  per-run geometry once; reuse source/destination textures; derive per-piece state from compact seeds; bound
  blur/refraction/trail samples; adapt quality to measured cost. `Docs/Guardrails/Performance_Optimization_Contract.md`
  applies.
- **R-69:** geometry/aspect adaptation may reframe or project but never globally compresses authored musical response.
- **R-63:** black=0 outranks exact shared-edge cover. An effect that exposes a backdrop shows an image (for example a
  dimmed destination), never black or stale pixels; seam geometry derives from actual monitor rectangles/DPR.

## 3. 3D transitions (dormant ideas)

Each is analytic on the GPU over one static mesh, needs no new host machinery, and is judged on real photos. All share
the departure negative controls in `Docs/Reference/Transitions.md` (no premature in-viewport shrink or fade as a
departure substitute; exact endpoints plus near-endpoint continuity).

- [ ] **Page Curl** — *new identity; high confidence.* The source peels from an edge or corner around a moving cylinder
      (an analytic curl of a subdivided grid, roughly 64×36 quads), showing a dimmed mirrored or paper-tinted back, and
      casts a soft shadow onto the destination through an effect-local underlay. Options: Direction (4 edges, 4 corners,
      Random), curl radius, back style; a **Roll Up** style keeps the curled part wrapped like a scroll. Risk: grid
      density must follow the curl radius so tight creases stay smooth; the roll must fully leave the frame.
- [ ] **Cube Turn** — *new identity or 3D Block Spins option (classify first); high confidence.* Source and destination
      sit on adjacent faces of a box that turns 90° about the vertical or horizontal axis with a slight pull-back and
      shading on the leading edge. The exposed backdrop during the pull-back is a dimmed destination, never black. Two
      quads, one draw.
- [ ] **Accordion Fold** — *new identity; high confidence.* The source splits into vertical or horizontal strips that
      fold zig-zag like a paper fan (alternating hinge angles), facets shading by orientation, compressing toward one
      edge before the folded stack leaves the frame. One strip mesh, per-strip index from the vertex or instance ID.
- [ ] **Relief Rise** — *new identity; medium-high confidence.* A grid mesh displaced by source luminance (vertex texture
      fetch) rises into lit relief under a sweeping light, morphs its height and colour toward the destination along a
      wave, then settles flat. Endpoints are exact at zero height. Risk: without a small camera tilt it can read as
      embossing; any tilt must not expose the frame edges.
- [ ] **Blinds → 3D Slats** — *option of the existing Blinds identity; high confidence.* Each slat is a thin box turning
      180° about its long axis (source front, destination back) with lighting and a staggered wave: 3D Block Spins per
      slat, instanced by `gl_InstanceID`.

## 4. 3D Visualizer modes (dormant ideas)

Every entry is a Unique Mode under §2.3.

- [ ] **Deformable Blob Sphere** — its own mode and renderer lifecycle; never mutates the accepted Voxel Sphere or
      Bubble. Its identity should not collapse into a generic audio sphere; worth preserving even if a first prototype
      is abandoned.
- [ ] **Extruded Spectrum** — one cuboid mesh, 32–128 instances with per-instance height/colour/energy, restrained
      lighting/specular and mild perspective or orthographic depth.
- [ ] **Waveform Ribbon** — Oscilloscope/Sine-like state as a ribbon of a few hundred vertices: amplitude on Y,
      authored phase/history through an X/Z twist, neighbour-sample normals, bounded ghost ribbons.
- [ ] **Bubble Depth Field** — shallow Z/parallax over unchanged Bubble logical motion and R-69 amplitude; instanced
      billboard sphere impostors with analytic normals/specular and per-bubble Z from authored state. Depth must not
      become a viewport-dependent damping term.
- [ ] **Reactive Particle Field** — a bounded instanced point/quad field (hundreds to low thousands in one or a few
      draws) driven by existing analysis; persistent state, if needed, belongs to the mode's logical runtime.
- [ ] **Spectrum Terrain** — spectrum across one axis and a short retained history into depth on a grid of a few
      thousand vertices, displaced from compact data with normals and lighting. A **Skyline** style draws the same
      history as instanced columns.
- [ ] **Spectrum Tunnel** — *high confidence.* Each logical step's spectrum wraps into a ring; bounded ring history
      (about 48 rows) recedes along a tunnel the camera looks down, kicks brighten the newest ring. Instanced ring
      segments; the history travels whole in the snapshot and uploads as one small texture per frame.
- [ ] **Shockwave Grid** — *high confidence.* A perspective lattice plane toward a horizon: bass drives a rolling
      swell, each admitted kick launches a circular shockwave from a seeded point (the last ≤8 events and their logical
      ages as uniforms), vocals warm the horizon glow. Static grid mesh with analytic displacement; consume-once events
      are aged by the logical runtime, never replayed.

## 5. Other dormant work

- [ ] **Settings FlowContainer polish [LOW]** — only for a demonstrated Settings layout problem; improve alignment and
      space use without restructuring ownership or eagerly building lazy bodies.
- [ ] **Wallpaper feed consolidation** — reuse FEEDS normalization/image-candidate primitives only where that makes the
      wallpaper engine simpler, without merging its image-primary cache/scheduling authority into FEEDS last-good
      state; prove wallpaper parity first.

## 6. Suggested order (dormant; the operator picks)

1. Blinds → 3D Slats, Page Curl, Cube Turn (smallest, most certain wins);
2. Extruded Spectrum, then Shockwave Grid (first two 3D Visualizers; Extruded Spectrum proves instanced 3D inside a
   carded Visualizer renderer);
3. Deformable Blob Sphere; Spectrum Terrain / Tunnel; Waveform Ribbon;
4. Accordion Fold, Relief Rise;
5. Reactive Particle Field, Bubble Depth Field;
6. Settings FlowContainer polish.

## 7. Not backlog

- **Implemented:** Glass Shatter, Crumble, Exploding Tiles, Directional Pixel Accretion, Ink Bloom, Melt Drip and Slide
  → Perspective Push (`Docs/Reference/Transitions.md`, open physical acceptance at its end); Runtime Widget Themes;
  Games You Follow and the system volume/mute OSD (`Docs/Reference/`). Reopen only for a concrete defect or an
  explicitly requested extension.
- **Rejected:** Tendril Reveal (fully retired). Runtime frosted/glass ordinary-widget cards are shelved; reconsider only
  if a future renderer independently justifies the capability, starting from the rejected-experiment record.

Capability terminology follows the landed contract: *activated/deactivated* is the application-level capability gate;
*enabled/disabled* is feature/instance state inside an activated capability.
