# GL-Only Transition Concepts

This document explores a set of **OpenGL-only** transitions proposed for the screensaver, building on the existing compositor-based GL architecture. It is design-only and does not represent a commitment to implementation.

- **Scope**: Peel, Rain Drops, Warp Dissolve, 3D Block Spins, Claw Marks.
- **Target path**: compositor-backed GL transitions (no new per-transition QOpenGLWidgets).
- **Fallback**: when hardware acceleration is disabled, these types should either be hidden in the UI or fall back to a safe CPU transition (typically Crossfade).

---

## 0. Architectural Baseline

- **DisplayWidget** owns a per-display `GLCompositorWidget` for compositor-backed GL transitions.
- Existing transitions (Crossfade, Slide, Wipe, Block Puzzle Flip) already have compositor controllers.
- All transitions flow through the same engine → queue → display pipeline described in `Spec.md`.
- Threading, logging, telemetry, and resource lifecycle are already centralized and should be reused.

**Implications for new GL-only transitions**:

- Reuse the compositor: implement each effect as a new compositor-backed transition type (controller + shader(s)), not as standalone GL widgets.
- Respect existing settings:
  - `display.hw_accel` must gate availability.
  - `transitions.type` should include the new names only when GL is enabled.
  - Directional transitions should respect the current direction model (`SlideDirection`, `WipeDirection`).
- Telemetry + watchdogs must be wired exactly like current GL compositor transitions.

---

## 1. Peel Transition

**Concept**

The current image is divided into N vertical or horizontal strips that **curl and peel away** in a chosen direction, revealing the next image under the curled strips.

- Direction: same model as Slide/Wipe (left/right/up/down).
- Division: user-selectable 1–20 strips.
- Visual goal: each strip looks slightly curled (like a flexible sheet) rather than a rigid flat card.

### 1.1 Architecture Fit

- Implement as a compositor-based GL transition:
  - Single fullscreen draw, with curl simulated in the **vertex/fragment shader** based on a per-fragment "strip index" and time `t`.
  - Avoid per-strip CPU geometry if possible; use math in the shader to compute curl and displacement.
- Reuse existing direction enums:
  - A direction vector `(dx, dy)` drives both displacement and curl orientation.
- Parameterization:
  - `transitions.peel.strips` (int, 1–20).
  - Optional `transitions.peel.curl_strength` and `transitions.peel.shadow_strength` (tunable but likely fixed in UI initially).

### 1.2 Performance

- Workload is dominated by a **single fullscreen fragment shader** with cheap arithmetic (sin/cos, basic lerps); geometry is unchanged.
- Comparable cost to existing GL Diffuse or Wipe when tuned reasonably.
- Frame coherence: animation is smooth as long as we keep the math branchless or with very simple conditionals.

### 1.3 Chances of Success / Blockers

- **Feasibility**: **High**.
  - We already have multi-direction transitions, timing, and compositor scaffolding.
- **Blockers / Risks**:
  - Getting a visually pleasing curl (without obvious stretching or aliasing) may require iteration.
  - Multi-monitor consistency: ensure curl direction is consistent across displays and DPRs.
  - Need careful blending between peeled regions and the underlying next image to avoid halos at strip boundaries.

---

## 2. Rain Drops Transition

**Concept**

3D-ish **raindrops** land on the current image, producing ripples and refractive distortions. Over time the distorted image fades into the next image, with ripples gradually revealing the new content.

- Drops have a sense of depth and specular highlight.
- Ripples expand and fade; underlying image transitions from old → new over the ripple field.

### 2.1 Architecture Fit

- Implement as a **screen-space distortion + crossfade shader**:
  - Maintain a small buffer of active drops (position, start time, radius, amplitude).
  - In the fragment shader, compute a per-pixel displacement based on the contribution of nearby drops.
  - Sample old/new images with displaced UVs, then blend old→new over time.
- No additional geometry required; one or two fullscreen passes are enough:
  - Pass 1 (optional): accumulate a lightweight height/normal field into an off-screen texture.
  - Pass 2: use that field to distort sampling of the images and apply a specular highlight.

### 2.2 Performance

- Moderately heavy fragment work if many drops and large ripple radii are used.
- We can keep it **GPU-friendly** by:
  - Capping active drops (e.g. 32–64).
  - Limiting each pixel to a small number of influencing drops (or pre-baked normal field).
  - Using simple analytic ripple shapes instead of complex noise.

### 2.3 Chances of Success / Blockers

- **Feasibility**: **Medium–High**.
  - Distortion-based effects are straightforward in GL; complexity lies in making it pretty, not in basic implementation.
- **Blockers / Risks**:
  - Visual quality: cheap approximations can look "plastic" rather than watery; may need art tuning.
  - Performance on low-end GPUs: too many drops or large kernels can hurt framerate.
  - Temporal aliasing: quickly moving ripples might shimmer at 60–165 Hz if parameters are not tuned.

---

## 3. Warp Dissolve Transition

**Concept**

A more chaotic version of block-based transitions:

- The image is divided into many small pieces (like Diffuse/Block Puzzle).
- Selected regions **explode outward** briefly over a black background, rotating in 2D/3D.
- Pieces then **fall back** into their original positions, but when they land they show the **next image**.
- Division and number of explosions should be controllable (e.g. full-screen explosion vs smaller regional bursts).

### 3.1 Architecture Fit

- Reuse the conceptual model of Block Puzzle / Diffuse:
  - Represent tiles as small quads with per-tile metadata: center, initial offset direction, random rotation axis/angle.
- Implement via **instanced rendering**:
  - One base quad mesh; per-instance attributes define tile position, explosion origin, and randomization.
  - Vertex shader applies translation and rotation over time.
- For "black under" requirement:
  - Clear or draw a black fullscreen quad first.
  - Draw tiles on top, sampling from old or new image based on a time window (e.g. explode = old, return = crossfade to new).
- Parameters:
  - `transitions.warp_dissolve.divisions` (blocks across/down).
  - `transitions.warp_dissolve.explosions` (1 = single global burst, N = multiple localized bursts).

### 3.2 Performance

- Very GPU-friendly if done via instancing:
  - Vertex work scales with tile count, but each tile is only a few vertices.
  - Fragment cost is similar to existing block transitions.
- Main cost is the **number of tiles**; we can align with existing block size limits in Spec.

### 3.3 Chances of Success / Blockers

- **Feasibility**: **High**.
  - Conceptually close to existing Block Puzzle transitions; we mainly add 3D-ish motion and a black underlay.
- **Blockers / Risks**:
  - Getting a non-ugly random explosion (not just visual noise) requires tuned distributions and easing.
  - Camera/perceptual issues: too much rotation or displacement can be visually tiring.
  - Requires careful handling of black underlay so it feels intentional and not like a flicker regression.

---

## 4. Actual 3D Block Spins

**Concept**

An evolution of the current Block Puzzle: image is divided into blocks that behave like true **3D slabs**, flipping or spinning with visible thickness and a **glossy/glass highlight** on the edges as they rotate from old image to new image.

### 4.1 Architecture Fit

- Treat each tile as a thin 3D box:
  - Use instanced geometry: each instance is a box (or two quads with edge shading), with per-instance transform.
  - Vertex shader applies a 3D rotation matrix around an axis (e.g. Y for horizontal flips).
- Sampling strategy:
  - While a face is visible, sample either old or new texture depending on rotation angle.
  - Edges can be shaded procedurally (bright highlight based on view angle) without extra textures.
- Integration with existing Block Puzzle settings:
  - Reuse block division settings so this can be swapped in as a variant.
  - Reuse timing/ordering logic (wave patterns, random tile ordering, etc.).

### 4.2 Performance

- Similar or slightly heavier than a well-implemented instanced block puzzle:
  - More vertex work (3D transform + edge geometry), but still small per instance.
  - Fragment cost is nearly identical (sample from one of two textures).
- Should remain smooth at current block counts if we avoid pathological divisions.

### 4.3 Chances of Success / Blockers

- **Feasibility**: **High**.
  - Technically simpler than Warp Dissolve since motion is more constrained and regular.
- **Blockers / Risks**:
  - Edge highlight needs tuning to look like glass/shine, not chalk.
  - Perspective choice: full perspective vs subtle pseudo-3D; too much perspective may feel out of place with 2D photos.

---

## 5. Claw Marks Transition

**Concept**

Aggressive **claw or scratch marks** tear through the current image until the entire frame is replaced by the next image.

- 3–5 long, sharp scratch paths.
- Slight randomization per path (jitter, angle, width), while still clearly reading as claws.
- The tears widen over time, revealing the new image beneath.

### 5.1 Architecture Fit

- Mask-based reveal implemented in the compositor:
  - Define a small set of claw paths (parametric curves or simple splines) in normalized coordinates.
  - In the fragment shader, compute distance from each pixel to the nearest path and compare to an animated tear width.
  - Use that as an alpha mask to blend from old → new image.
- Optional enhancements:
  - Slight parallax/offset along the tear edges to imply depth.
  - Subtle drop shadow or highlight along the edges.

### 5.2 Performance

- Extremely GPU-friendly if we keep the math simple:
  - Distance to a handful of line segments or low-order curves.
  - A few `min()` operations and lerps per pixel.
- No extra geometry; standard fullscreen pass.

### 5.3 Chances of Success / Blockers

- **Feasibility**: **Medium–High**.
  - The math is easy; the challenge is making the shapes and pacing look convincingly like claws instead of random stripes.
- **Blockers / Risks**:
  - Procedural art direction: how to encode scratch shapes that always look intentional without shipping external textures.
  - Potential banding/aliasing along tear edges if we don’t anti-alias the mask.

---

## 6. Overall Risk & Rollout Strategy

### 6.1 Prioritized Order

Proposed implementation order based on feasibility vs impact:

1. **3D Block Spins** – technically closest to existing Block Puzzle, high chance of success.
2. **Peel** – straightforward shader math, visually distinct.
3. **Claw Marks** – simple masking, medium art-direction risk.
4. **Warp Dissolve** – more chaotic version of block work; higher tuning cost.
5. **Rain Drops** – most art/physics-sensitive; keep as experimental.

### 6.2 Shared Constraints

- **GL-only**: all five transitions should be **hidden** or **mapped to a safe CPU fallback** when `display.hw_accel` is false.
- **Settings surface**:
  - Avoid exploding the settings UI; reuse existing patterns (block division, direction enums, duration) and add at most 1–2 new knobs per effect.
- **Diagnostics**:
  - Each GL-only transition must emit perf telemetry similar to existing compositor transitions (duration, frames, avg_fps), so they can be profiled on mixed-refresh rigs.

### 6.3 Potential Blockers Across All Effects

- GPU variance: low-end integrated GPUs may struggle if we push tile counts or complex math too far.
- Testing complexity: multi-monitor, mixed-DPI, hw-accel on/off permutations will need at least a manual checklist per transition.
- Visual cohesion: all new effects should respect the general visual language of the app (no overly cartoonish look unless explicitly desired).
