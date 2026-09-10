# Voxel Sphere pseudo-material contamination — 2026-09-09

Status: **fixed / guardrail**

## Symptom

Voxel Sphere Toon, Gloss/Specular, lighting and authored colour were difficult to judge consistently. The old Chrome / Obsidian / Magma / Silver / Water branches modified voxel colour/brightness per cube before the actual lighting/finish stage, so surface controls were being evaluated through an unrelated earlier experiment.

## Root cause

The voxel renderer inherited pseudo-material semantics from the rejected smooth-Sphere work. `materialBase()` applied seed-dependent colour/brightness transforms, while `sphere_material_fx` remained a canonical but inert-looking setting. This created a second hidden surface authority and made finish diagnosis ambiguous.

## Fix

- renderer input is literal `sphere_fill_color` + `sphere_edge_color` only;
- no `uMaterial`, material ID, `materialBase()` or seed-based colour variation remains;
- Gloss/Specular/Toon are the only finish authorities;
- `sphere_finish` is Settings-only convenience that writes the visible Gloss/Specular sliders and is not included in the renderer parameter bundle;
- old `sphere_material`, `sphere_material_color`, and `sphere_material_fx` are forward-migration inputs only and disappear from canonical state;
- Preset 6 is now neutral **Reactive Voxel** for repeatable physical validation.

## Guardrail

Do not reintroduce named pseudo-material branches as hidden renderer math. If textured/reflective voxels are wanted later, add an explicit texture/reflection seam with its own acceptance gate; do not simulate it by secretly recolouring individual cubes before lighting.
