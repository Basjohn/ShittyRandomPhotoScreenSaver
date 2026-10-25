> Operator-supplied concept brief, copied verbatim from `references/waveform_ribbon_concept_package.zip` (local, git-ignored) on 2026-10-25 so the plan can
> link it. The mock image(s) (Waveform_Ribbon_Concept.png, Waveform_Ribbon_Alternate_Annotated_Mock.png) stay in that package. Sequencing lives in `Current_Plan.md` §7.

# Waveform Ribbon — SRPSS concept package

## Included image
- `Waveform_Ribbon_Concept.png`

This package intentionally includes the **single approved Waveform Ribbon concept image** (the standalone annotated concept board), not the mixed multi-mode board and not the failed Terrain / Skyline / Tunnel mock.

---

## 1. Concept summary

**Waveform Ribbon** is a 3D audio visualizer built from one or more flowing translucent ribbon strips that travel through space as a continuous representation of live music.

The visual target is:
- elegant and readable at low react;
- more energetic, thicker, brighter, twistier, and more particle-accented at high react;
- still the **same scene**, with the same camera, environment, and general composition.

This is not meant to be a chaotic particle storm. The core identity is the **ribbon itself**.

---

## 2. What should react

Recommended musical mappings:

- **Overall amplitude / energy**
  - global emissive intensity;
  - bloom contribution;
  - optional slight overall expansion.

- **Bass / low frequencies**
  - ribbon body width / thickness;
  - slower large-scale undulation.

- **Mid frequencies**
  - twist amount;
  - vertical and lateral deformation;
  - waveform complexity.

- **High frequencies**
  - edge shimmer;
  - particle accents / small sparks;
  - fine surface detail and glow accents.

- **Transient hits**
  - brief local brightness spikes;
  - short-lived particle bursts;
  - temporary increase in curvature/tension.

---

## 3. What should stay stable

To keep the mode legible and artistically controlled, these should remain stable across low and high react:

- camera angle and framing;
- environment and lighting design;
- floor/reflection setup;
- overall scene composition;
- ribbon continuity (always flowing, not snapping apart);
- color-family identity unless an explicit palette mode says otherwise.

The reactivity should feel like the music is animating the ribbon, **not replacing the scene**.

---

## 4. OpenGL 4.6-achievable implementation approach

This concept is realistically achievable in **OpenGL 4.6** without inventing a second renderer.

### 4.1 Core rendering model

A practical implementation path:

1. Maintain a short **history buffer** of waveform / frequency-derived control samples.
2. Convert those samples into one or more **ribbon centerlines**.
3. Build a ribbon strip mesh from the centerline using either:
   - CPU-generated dynamic VBO updates, or
   - compute-assisted generation into SSBO/VBO.
4. Shade the ribbon as a translucent emissive material.
5. Composite bloom and reflections using the existing post-process path.
6. Optionally draw small instanced particles driven by highs/transients.

### 4.2 Ribbon geometry options

Two realistic geometry approaches:

#### Option A — CPU-generated ribbon mesh
- Build vertices each frame from a bounded sample history.
- Simple and straightforward.
- Likely enough for a moderate vertex count.

#### Option B — compute-assisted ribbon generation
- Store control points / amplitudes in SSBOs.
- Use a compute shader or GPU-side generation step to produce ribbon attributes.
- Better headroom for multiple ribbons and extra detail.

Either route is compatible with OpenGL 4.6.

### 4.3 Shading and blending

Needed shading traits:
- translucent body;
- emissive glow;
- soft edge falloff / fresnel-like edge emphasis;
- optional subtle inner line structure or banding;
- additive or weighted translucent contribution depending on the composite path.

### 4.4 Reflections and bloom

The concept benefits strongly from:
- a reflective floor plane or controlled reflective surface;
- framebuffer bloom/postprocess;
- stable exposure and restrained glow so the ribbon remains readable.

### 4.5 Particle accents

Optional secondary layer:
- small instanced particles or point sprites;
- only a supporting accent, not the main act;
- driven primarily by highs and transients.

---

## 5. Architecture needed inside SRPSS

This concept fits SRPSS best as a **shared-substrate consumer**, not a one-off rendering island.

### 5.1 Shared capabilities it should reuse

The mode should reuse existing shared machinery where possible:
- canonical SRPSS visualizer lifecycle and logical clock;
- accepted Qt Quick / OpenGL rendering path;
- shared scene target / postprocess path for bloom/composite;
- existing audio analysis feeds / FFT bands;
- existing dormancy and resource release expectations;
- existing 3D quality vocabulary and settings conventions.

### 5.2 New shared or semi-shared capability likely needed

The main missing reusable piece is a **ribbon primitive / ribbon-generation path**:
- dynamic ribbon mesh generation from audio/history;
- bounded multi-ribbon support;
- stable transparent rendering for overlapping strips;
- optional secondary particle emission.

This aligns most closely with the repo's deferred **G4 / S18 particle/ribbon extensions** direction.

### 5.3 Recommended mode structure

A practical mode decomposition:

- **Audio mapping layer**
  - maps FFT / amplitude / transient data into low, mid, high control values.

- **Ribbon state layer**
  - maintains short history and smoothing;
  - produces centerline + width/twist/emission controls.

- **Geometry builder**
  - generates one or more ribbon strips.

- **Material / render pass**
  - draws translucent emissive ribbons;
  - draws optional accent particles.

- **Post / composite**
  - bloom, reflection, final composite.

---

## 6. Important characteristics for it to remain achievable

To keep this realistic and shippable:

### 6.1 Keep the geometry bounded
- fixed maximum history length;
- fixed maximum ribbon count;
- fixed maximum particles;
- no unbounded trail accumulation.

### 6.2 Keep the reactivity readable
- do not drive every parameter equally;
- separate bass/body, mids/twist, highs/sparkle;
- use smoothing so the ribbon feels musical, not noisy.

### 6.3 Prioritize continuity
- the ribbon should flow as one intentional structure;
- avoid popping, snapping, or topology changes that look like bugs.

### 6.4 Preserve low-react beauty
- low react must still look attractive and intentional;
- not merely an almost-off version of high react.

### 6.5 Avoid overcomplicating the camera
- the concept works well with a stable view;
- no need for heavy navigation complexity unless later requested.

---

## 7. Hard gates / non-negotiables

These are the hard gates that should be met before calling the mode successful:

### Gate A — Same-scene low/high integrity
Low react and high react must clearly read as the **same visualizer scene**.
- Same camera.
- Same environment.
- Same composition.
- Reactivity changes the ribbon behavior, not the whole visual identity.

### Gate B — No second renderer
The mode must not introduce a separate parallel rendering architecture.
It should live inside the accepted SRPSS Qt Quick / OpenGL path.

### Gate C — One logical clock
No mode-private simulation clock or timer loop.
Use the canonical visualizer logical/runtime cadence.

### Gate D — Real dormancy and cleanup
When the mode is inactive:
- no retained heavy ribbon resources;
- no persistent per-frame work;
- resources retire correctly.

### Gate E — Bounded cost
The mode must have a bounded vertex count, ribbon count, particle count, and post cost.
No runaway geometry or pathological transparency cost.

### Gate F — Live music legibility
The user must be able to perceive:
- bass widening / body response;
- mid deformation / twist;
- high shimmer / particle accents.

If the mapping is too muddy to read, the mode has failed artistically.

### Gate G — Stable transparency quality
Overlapping translucent ribbons must remain visually convincing.
No severe sorting artifacts, broken blending, or unreadable glow washout.

### Gate H — Low-react still attractive
Quiet passages must still look composed and pleasing, not dead.

---

## 8. Recommended settings (minimal useful set)

Suggested operator-facing controls:
- Ribbon Count
- Ribbon Width
- Twist Amount
- Glow Strength
- Reflection Strength
- Particle Accents On/Off
- Particle Density
- Reactivity / Sensitivity
- Color Mode / Palette
- Optional Band Mapping preset

Avoid exploding the mode into too many settings early.

---

## 9. Suggested implementation order

1. **Single ribbon, no particles**
   - stable centerline;
   - width from bass;
   - twist/deformation from mids;
   - glow from energy.

2. **Quality shading + bloom**
   - translucent/emissive material;
   - good readability.

3. **Reflection layer**
   - floor reflection / controlled surface reflection.

4. **Multi-ribbon support**
   - separated bands or companion ribbons.

5. **Particle accents**
   - highs/transient details.

6. **Settings and polish**
   - restrained operator control surface.

---

## 10. Risks / failure modes to avoid

- making it a generic particle scene instead of a ribbon scene;
- too much camera or environment change between reactivity states;
- overusing bloom until the ribbon loses form;
- chaotic color cycling that destroys readability;
- excessive complexity before the single-ribbon version is good;
- unbounded mesh history or particle counts.

---

## 11. Bottom line

This concept is **realistically achievable in OpenGL 4.6**.

The key enabling work is not a whole new engine, but a **good shared ribbon-capable dynamic geometry path**, stable translucent rendering, and disciplined audio mapping.

If the implementation preserves scene stability, ribbon continuity, bounded cost, and clear band-driven reactivity, it should be a strong SRPSS visualizer candidate.
