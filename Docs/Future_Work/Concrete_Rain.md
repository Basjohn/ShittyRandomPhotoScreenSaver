# Concrete Rain — deferred Visualizer concept

**Status:** deferred concept. Not admitted for runtime implementation; `Future_Work.md` routes it and `Current_Plan.md` owns any promoted slice. This document records the visual target, likely shared architecture and the guardrails for future admission.

**Reference image:** `references/Low and High Reactivity Rain Comparison.png` (operator-owned local reference; intentionally omitted from GODZIP payloads). The left panel is the low-reactivity target and the right panel is the high-reactivity target.

---

## 1. Concept

A low-angle night street/pavement Visualizer built around **wet concrete, puddles, raindrop impacts and reflected city lights**. The same authored street, curb, wall, bokeh lights and camera remain stable while music changes the rain field. Quiet passages read as sparse drizzle with isolated rings and comparatively stable reflections; strong passages read as denser impact bursts, overlapping ripples, taller splash crowns, more airborne droplets and visibly disturbed reflections.

The goal is not generic “rain particles everywhere” but a scene that reads as **music changing the pavement’s water behaviour** while preserving the environment.

Success: the viewer can compare two moments in a song and read the same street with low vs high rain response, just as in the supplied reference.

## 2. Visual contract

- Same authored camera, pavement geometry, curb/wall silhouette, background buildings and light placements across reactivity states.
- Low react: steady drizzle, shallow isolated ripple rings, restrained splash height, reflections remain coherent.
- High react: denser/taller impact bursts, many overlapping/interfering rings, more splash crowns and droplets, stronger reflection distortion and more animated surface breakup.
- Reflective/wet look must come primarily from a **shared wet-surface/reflection substrate**, not a painted trick that collapses when the camera or density changes.
- Preserve the dark nocturne look and the warm/cool reflected light mix; do not flood the scene with daylight or flatten the blacks.

## 3. Reactivity

Reactivity should separate several visible axes instead of only scaling one spawn count:

- **Coverage / density:** drizzle versus heavier rainfall.
- **Impact energy:** crown height, droplet rebound, and ring prominence.
- **Ripple complexity:** isolated rings at low react; interference patterns at high react.
- **Reflection disturbance:** more wavering/broken reflections under stronger passages.
- **Burst response:** transients may briefly increase local impact clusters or splash energy without permanently changing the scene.

Do not let reactivity teleport the camera, change environment geometry, or radically recompose the shot.

## 4. Shared architecture to side-build first

Promote only through reusable substrate work, not a one-off mode-private renderer:

1. **Wet-surface / puddle substrate**
   - shallow water-sheet/puddle mask semantics over authored ground geometry;
   - coherent roughness/specular/reflection treatment;
   - optional thickness/distortion logic for puddled regions.

2. **Raindrop impact population**
   - deterministic/semi-seeded impact admission with bounded lifetime;
   - local impact records driving rings, crowns and secondary droplets;
   - density and energy controls that remain count-bounded.

3. **Ripple / crown primitives**
   - expanding ring wavefronts with interference/overlap behaviour;
   - crown/splash primitives that can scale from drizzle to burst without requiring fluid simulation.

4. **Reflection disturbance**
   - bounded distortion sampling for reflected lights on the wet surface;
   - more disturbed reflections at high react, calmer reflections at low react.

5. **Framed low-angle camera consumer**
   - a bordered/framed Visualizer using the shared camera authority;
   - low camera near the pavement, with stable authored composition and no mode-private navigation system.

## 5. Admission guardrails

- No second renderer or separate reflection engine just for this mode.
- No unbounded particle explosion or full fluid simulation without measured justification.
- No anticipatory song-path choreography; current/live audio only.
- No duplication of camera/input ownership.
- Prove each primitive in isolation before combining them into the full scene.

## 6. Likely implementation sequencing when promoted

1. Wet-surface/reflection proof.
2. Ripple and simple impact-ring proof.
3. Splash crown / droplet accent proof.
4. Music mapping for density, energy and reflection disturbance.
5. Final Concrete Rain scene assembly and acceptance against the supplied reference.
