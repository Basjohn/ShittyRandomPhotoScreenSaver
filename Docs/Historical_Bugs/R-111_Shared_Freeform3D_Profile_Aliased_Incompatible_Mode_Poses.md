# R-111 | Shared freeform-3D layout profile aliased incompatible mode poses

**Status:** ARCHITECTURAL REPAIR IN CODE / REGRESSION-PROTECTED / PHYSICAL ACCEPTANCE PENDING

## Trigger

The first Visualizer CUSTOM geometry split used one descriptor value, `geometry_profile = planar | freeform_3d`, for both interaction mechanics and persisted pose identity. That solved the original 2D↔3D inheritance problem but physical authoring exposed the next abstraction failure: Extruded Spectrum, Shockwave Grid and Voxel Sphere all need freeform-3D interaction mechanics while useful position/size/viewport poses can be radically different.

A single saved `freeform_3d` pose therefore made 3D↔3D hot-swap inherit geometry that was semantically valid but visually absurd for the target mode. This would become worse as additional frameless 3D modes were registered.

The same operator logs showed isolated `viz_geometry_mismatches` at explicit CUSTOM Save / mode-geometry transaction edges. They did not climb continuously; the bridge was correctly rejecting one stale unread presentation snapshot after authority changed.

## Root cause

One metadata identity was being asked to answer two different questions:

1. **How does this mode's geometry behave?**
2. **Which authored CUSTOM stage pose is compatible with this mode?**

Those answers happened to match when the only distinction was planar versus 3D. They are not equivalent once multiple 3D presentations have different authored camera/frustum/footprint needs.

## Repair

Visualizer descriptors now separate:

- `geometry_kind`: mechanics only (`planar` or `freeform_3d`);
- `layout_profile`: the descriptor-owned compatibility-group ID used on the existing CUSTOM `geometry_variant` axis.

Current canonical layout profiles are:

- all current planar modes: `planar`;
- Extruded Spectrum: `3d:extruded_spectrum`;
- Shockwave Grid: `3d:shockwave_grid`;
- Voxel Sphere: `3d:sphere`.

This is **not** a second geometry store and not a policy that every future mode gets its own slot. A future pair of modes may deliberately share a profile only when their stage geometry is actually compatible. The existing one Visualizer widget, one `custom_layout` map, one `CustomLayoutSession`, one hydration path and one commit path remain authoritative.

Turn, tilt, camera, material, response and preset values remain the mode's existing presentation/settings state. A complete visible pose is composed from the target layout profile plus that mode's presentation state; neither authority serializes or restores the other.

Legacy `default` / `freeform_3d` variants are one-way interpretation input. Only an explicit/current claimant may promote one ambiguous record into its canonical layout profile; sibling 3D modes never clone it. Missing profiles start from authored baseline rather than outgoing geometry.

At the explicit transaction seam, a hidden target-profile switch discards one unread outgoing render snapshot after logical production is stopped. CUSTOM Save may rebase the one unread newest logical snapshot onto the exact committed presentation being promoted. Normal render admission still rejects mismatched presentation everywhere else.

## Edit orientation cage

The 3D Edit guide is now derivative projected wireframe paint rather than a flat decorative box. The renderer-side Edit envelope publishes eight read-only projected cage vertices and the canonical north/far-face centre. QML draws twelve edges at high opacity and a white `N` with thin black outline.

The cage is never geometry authority. It may not persist, snap, collide, move, resize, invoke Fit Scene, or alter the saved stage. It is only an orientation/footprint aid derived from the active renderer projection.

## Permanent regression

Regression coverage must prove:

- geometry kind and layout profile are independent descriptor facts;
- Extruded, Shockwave and Sphere can retain distinct profiles simultaneously;
- 2D↔3D and 3D↔3D hidden hot-swap resolves the target profile without outgoing-pose borrowing;
- Save/Cancel, display transfer, alias merge and layout slots preserve dormant sibling profiles;
- legacy freeform geometry can be claimed once without cloning it to siblings;
- mode turn/tilt remains outside layout payloads;
- projected 3D cage publication is eight finite points plus a north marker and changes with camera/orbit state;
- explicit snapshot discard/rebase at profile switch / Save does not increment `presentation_mismatch_count`.

## Physical acceptance

Author deliberately incompatible Spectrum, Extruded, Shockwave and Sphere stage poses on both displays. Give the 3D modes different turn/tilt where supported. Exercise repeated 2D↔3D and 3D↔3D hot-swap, curated↔Custom, Save/Cancel, Settings reinit, display transfer and layout-slot replay. Each target must restore its own stage and independent camera state without visible borrowing or new `viz_geometry_mismatches`. The wireframe cage and `N` must remain useful through orbit without moving the persisted stage.

## Explicit follow-up acceptance boundaries (2026-10-08)

- Arrange, runtime Edit, display transfer and saved layout slots must all route through descriptor-owned `layout_profile` and preserve sibling profiles. A mode change while Edit owns a transaction is refused rather than silently changing the working session identity.
- Camera turn/tilt is a persistent, mode-scoped view fact independent of curated/Custom presets. Editing view orientation must not switch presets; preset activation must not overwrite it.
- The Edit cage is a read-only projected wireframe. Its north face is the *world -Z face* of the cage (vertices 4–7); the N marker is a vector glyph warped within that projected face quad, so tilt and turn agree with the cage rather than a screen-facing label. It adds no separate camera, stage, event loop or serialization. Sphere's cage is a static orientation/extent guide, not a tracker for dynamically spinning internal voxels.
- At a Save boundary the retained bridge atomically discards only an unread snapshot with a different frozen presentation. It never rewrites a snapshot's geometry to suppress mismatch diagnostics.
- Physical evaluation on Windows/PySide6/OpenGL is required before closing this incident.
