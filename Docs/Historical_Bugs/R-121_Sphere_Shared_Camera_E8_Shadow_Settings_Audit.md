# R-121 | Sphere Shared Camera, E8 Receiver and Extruded Settings Authority

## Scope and operator evidence

R-120: 972 grouped Windows tests passed in 58.09 seconds, exit code 0. The operator nevertheless reported a tiny and unusable Extruded cast-shadow corner at maximum strength with opaque reflective bars. A passing shadow-pixel regression is not the physical acceptance gate. Operator explicitly authorized Sphere migration now rather than deferring it behind repeated E8 attempts. No transition implementation or WebP generation in R-121.

## Sphere: what changed and what did not

**Shared Scene3D camera**: the existing `sphere_voxel.py` renderer already draws instanced 3D cube meshes with depth testing and audio-driven shell deformation. We retain its bar/cohort/fragment/tracer mechanics, vertex cube positions, render-quality tier, mirror and backdrop passes. Only the *final vertex camera/projection* is migrated to `SCENE3D_GLSL` / `sceneProjectAt` via the pure `sceneProjectSphere` item-space adapter. `sceneClipDepth` now governs clip z, rather than Sphere's bespoke clip-depth assignment. The zero-view adapter is algebraically equivalent to the old on-screen Sphere perspective for identical shell vertices; the camera adds an independent authored view pose without changing the reactive mesh rotation.

**State ownership**: Sphere registers `sphere_turn` and `sphere_tilt` through the existing mode descriptor's `view_orbit_settings`, the same per-mode presentation authority as Extruded/Shockwave. Default/model/configure pass these through the canonical Settings hydrator. They are excluded from curated/Custom preset capture. The renderer reads the already-authored pose through the existing immutable mode-state capture while the logical Sphere runtime still consumes no camera changes to decide audio reactions. No second camera owner, render scheduler, polling or dormant resource work.

**Geometry parity**: `edit_content_envelope` projects its Sphere cage through the pure CPU mirror `scene3d_sphere_item_position`, matching the production camera transform. Unlike a separate QML approximation, changing orbit should not create an independently authored cage orientation. The existing stage layout profile remains `3d:sphere`, keyed per display.

**Risks requiring Windows evidence**: GLSL shader compile/link under GL 4.6 core; GPU/CPU mirror across yaw/tilt and perspective; clip-depth and reflective/translucent voxels; icon/cage orientation; real-world display sizing, rate, performance/dormancy. Existing Sphere goldens cannot be declared accepted from source inspection.

## Extruded E8

The prior shadow projected onto a receiver that provided little visible area under front-on viewing; tests established only that shadow pixels changed, not a useful cast silhouette outside the opaque foreground. The new projected-space receiver starts at each base footprint and moves the elevated vertices by `EXTRUDED_SHADOW_CAST_REACH * height * canonical_screen_direction` to produce a nonzero-area sweep even at shallow tilt. The same pure projection is used in reach and Edit-footprint mirrors. No new GL target, additional shadow pass, retained animation, or duplicate Settings authority. Keep E8 **open** until its physical appearance is convincing on the operator's desktop.

**Open test gate**: strength 0/0.45/1.0; SE direction; opaque bar swatches and reflection on; shallow and steep orbit; no clipped/corner-only cast or giant unwanted side smear. A real-GL image-difference oracle cannot substitute for the physical test.

## Extruded Settings and opacity

Only four groups remain: Appearance, Shape, Response, 3D Effects (material finish, reflection, shadow, overflow, ghosting). Shape stays independent for its node/lane editor. Retired `extruded_spectrum_body_alpha` from canonical defaults, dataclass schema, four curated preset files, Settings builder/binding, GL uniforms, and Edit content visibility rules. Body opacity reads fill-swatch alpha; edge opacity reads border-swatch alpha. Older persisted body-alpha keys are inert and must not override the swatches. Tests must retain independent-body/edge alpha and preset/custom roundtrip coverage.

## Future transition WebPs (plan only)

`Current_Plan.md` M1 now selects two Windows-local user artworks, `D:\Artwork\Usu\Scenes4k\UsuScenePaper1.png` and `D:\Artwork\Usu\Scenes4k\UsuScenePaper2.png`, for *all future transition WebPs*. Render around 480 pixels high, preserve original aspect, use high-quality WebP and inspect motion/edges. Paths must be resolved on operator Windows host at capture time, never inferred as present here or embedded in the full Godzip. No transition work is authorized now.

## Delivery gate and order

1. Grouped Windows Qt/GL regression gate including new Sphere projection, E8 shadow reach and Extruded alpha Settings.
2. Physical acceptance of Sphere (including Edit and mode switches) and E8 (obviously visible cast, not just changed pixels).
3. Full Scene3D / Visualizer / lifecycle / default/preset/geometry self-audit.
4. Python 3.13 upgrade only after dependency + PySide6/Qt6 + Nuitka/installer compatibility is established; never replace 3.11 requirements blind.

In this container PySide6/OpenGL are unavailable. Pure CPU tests and AST checks are possible, not full Qt/GL acceptance.
