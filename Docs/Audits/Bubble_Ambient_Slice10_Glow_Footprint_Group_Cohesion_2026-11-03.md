# Bubble Ambient Slice 10: visible halo footprint and further Group Drift decoupling

**Status:** implementation candidate, native visual/GPU acceptance outstanding. Based on `GODZIP_cc4c390a9e_BubbleAmbient_Slice9_Cohesion_Glow_SineRetirement_2026-11-03.zip`. This experiment stays outside `Current_Plan.md` and `Future_Work.md`.

## Scope and preserved contracts

Only two visual behaviours are intentionally changed:

1. **Particles' emitted-light footprint**, without enlarging their solid cores, changing size with sound, introducing another renderer pass or increasing the particle count.
2. **Group Drift cohesion** by a further relative 30% from Slice 9, leaving original stream, normal drift, swirl, bounce, reactivity input, random generation and presets untouched.

No changes to SINE retirement, accepted background ordering, microbubble seeds, colour/preset schema, hero occlusion, ambient silhouette clipping, or other modes.

## Glow: why previous passes still appeared almost unlit

Slice 9 correctly separated emitted radiance from opacity, but the point sprite envelope was just **five core diameters** wide. Its Gaussian radiance declined sharply toward the edge. At the typical 2.4 px authored particle size, almost the entire visibly bright aura occupied just a few physical pixels. Raising a maximum multiplier could therefore only make the central dot look stronger, rather than create the wider, soft light pool the operator wants.

This slice keeps the two existing independent channels (core alpha and premultiplied emissive RGB) and the existing Bubble-shader composite, but changes their *physical shape*:

- Emissive sprites expand to **8–12 core diameters**, depending on the already-resolved glow strength; when glow is disabled, they use a tight 2.2× envelope instead.
- A varying `vCoreRatio` encodes the **actual core-diameter/sprite-diameter** ratio, including the 128 px point-size cap. The fragment calculates the alpha core from that ratio, preserving its exact physical dimensions independent of glow settings.
- Inner and outer emission have separate soft Gaussian falloffs. Light remains visible at 5–11 px from the centre on a representative 2.4 px particle at maximum glow, while **alpha outside the original core remains zero**.
- Numeric radiance samples for this representative case before authored particle colour/opacity: 5 px **0.491**, 8 px **0.314**, 11 px **0.167**, 14.4 px (sprite boundary) **0**. No single sprite's emission exceeds 1.0 in the 8-bit intermediate target. These are CPU formula measurements, **not** observed screen brightness.
- Texture allocation, stencil clipping, occlusion quads, hero render, and number of draw passes are unchanged. Wider points do mean additional bounded *fragment fill*, which must be measured natively under concurrent GPU load. Maximum point diameter remains capped at 128 px.

The current particle *body diameter* still never responds to audio. Only light emission and its halo footprint follow the existing small-bubble breathing signal. Gradients and actual GPU framebuffer appearance still need native acceptance; the mathematical checks do not prove visual fidelity.

## Group Drift: another 30% less shared movement

Slice 9 mixed **70%** shared Group Drift displacement with **30%** existing per-bubble, smoothly phased local travel. This slice reduces the shared component by another 30% **of that 70%**: **49% shared / 51% independently phased**. The same group musical magnitude, locally computed phase, drift parameters, frame clock, RNG and downstream positions/collision handlers are retained. The earlier 70/30 variant remains in the previous archive if needed.

Controlled source-equivalent seeded simulation against Slice 9 (`.72` synthetic energy, 8 big + 35 small configured, horizontal swish drift, same random seed, 1/60 s tick):

| Ticks | Ungrouped positions vs Slice 9 | Grouped positions vs Slice 9 | Grouped survivors (old → new) |
| ---: | --- | --- | --- |
| 1 | exactly identical | no divergence yet | 43 → 43 |
| 10 | exactly identical | divergent | 43 → 43 |
| 45 | exactly identical | divergent | 57 → 55 |
| 90 | exactly identical | divergent | 54 → 58 |

Different surviving populations arise when different trajectories cross lifecycle boundaries. This is **not** a proof of better aesthetic spread; the user must judge real movement and gaps. In particular, group drift still acts through the existing carrier, not an independent new global random path.

## Checks and acceptance

**Checked here:** Python source compilation without generating bytecode; four direct GL-independent radiance/size tests; independent source-equivalent seeded simulation comparison; GODZIP inventory, CRC, file sizes, SHA-256 and debris exclusion. Native PySide6/OpenGL is unavailable in this environment.

**Native operator checks:**

- With a fixed particle size, compare Glow OFF, quiet Glow ON and sustained-loud Glow ON. The core must remain the same size; a broad *soft illumination halo* should extend well beyond it, and high-end settings should be visibly stronger without forming a filled white sphere.
- Check low/default/high particle colour alpha, overlapping light contributions, transparent gradient variants, ambient occlusion by big and small heroes and card stencil/rotated/extreme viewports.
- Check 49/51 Group Drift's filling of holes and independent motion over real recordings. Confirm more variation **without an unwanted reduction in loud-passage movement authority or abrupt directional jitter**.
- Observe FPS and frame time under concurrent load at high particle counts and large/custom viewports. The wider point sprites increase some fragment work even though passes/textures are unchanged.

If light is still weak, capture the ambient FBO and final Bubble pass independently before more tuning. Do not increase opacity or introduce a second glow simulation as a shortcut.
