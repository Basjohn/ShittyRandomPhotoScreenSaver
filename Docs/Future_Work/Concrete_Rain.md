# Concrete Rain — deferred Visualizer concept

**Status:** queued third in `Current_Plan.md` §7 (after Waveform Ribbon and Melt Pool), built lab-first (§7.0) on the shared 3D primitives of §6. This document records the visual target, likely shared architecture and the guardrails for future admission.

**Reference image:** `references/Low and High Reactivity Concrete Rain Comparison.png` (operator-owned local reference; intentionally omitted from GODZIP payloads). The left panel is the low-reactivity target and the right panel is the high-reactivity target.

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


## 7. Post-flip Vulkan-native construction and camera proof (operator, 23 Nov 2026)

**Second new Vulkan-native Visualizer after Reactive Liquid / Audio Melt Pool.** The scene is eligible to require
`VK_EXT_mesh_shader`; there is no requirement to construct or visually match a legacy OpenGL or mesh-free twin.
Only the selected Visualizer mode is unavailable when the required capability is absent; the OpenGL fallback and
existing accepted modes continue to work. The raw Vulkan pass lives in the shared native core N6.7, not a private
renderer or a new window/scene/compositor owner.

**Procedural spatial construction, not obligatory Blender asset authoring:** prove asphalt and road crown with
real geometric relief where the near-ground camera exposes it; individually varied pavement slabs/tiles, joints,
curbs, drains, chipped edges and street fixtures; bounded middle-distance wall/building geometry with convincing
depth. Use mesh/task shading for geometry that benefits, conventional instancing, fragment/normal detail and
compute where those are the better tool. Distant architecture and light may be simplified with fog/bokeh
impostors only where depth, parallax and orbit tests remain convincing. Keep the established wet substrate,
puddle optics, reflections, rain impulses, ripple interference, crown/droplet mechanics and stable authored lights.

**Camera:** preserve the original low/high reference's *same-camera, same-street* comparison (no scenery
changing to fake reactivity). In addition prove optional, modest free orbit around a bounded street/crosswalk/
intersection with a credible **360-degree view**, if the resulting scene remains believable: no missing
backfaces/buildings, paper-thin slabs, broken reflection coverage or impossible light parallax. This is a pocket
environment, not a requirement for unrestricted walking down a street. Use the existing framed-camera authority.

**Acceptance order:** (1) dry urban geometry with orbit and occlusion; (2) materials and rain-wet reflections
including from moved views; (3) impact/ripple/splash primitives; (4) recorded live-audio mapping across density,
energy, ripple complexity and reflection disturbance; (5) low/high comparison and multi-view native captures
against the operator-owned mock, measured GPU cost and device/lifecycle proof. No runtime Blender dependency,
no unbounded world/particle simulation, no anticipatory choreography.
