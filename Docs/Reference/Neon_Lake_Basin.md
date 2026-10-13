# Neon Lake Basin

Neon Lake Basin replaces the flat Shockwave Grid picture. The stable mode ID, settings prefix and layout profile remain
`shockwave_grid`, `shockwave_grid_*` and `3d:shockwave_grid`. Visual fidelity and musical acceptance remain live work in
`Current_Plan.md` §2A V4A. The supplied low/high mock in
`Docs/Future_Work/Additional_Future_Transitions_Package.zip` remains the visual target.

## Card, scene pose and input

The descriptor declares CARD / CARD_INTERIOR with independent freeform-3D CUSTOM stage geometry. The saved outer card
rectangle and logical viewport remain their existing authorities; shell policy supplies ordinary card chrome and the
rounded interior stencil. Every rendered pose remains clipped, including Edit and extreme zoom/pan. The old overflow
key is forward-retired by the canonical settings and preset filters.

| Existing 3D input | Framed scene result |
| --- | --- |
| WASD | Internal turn/tilt on the existing logical capture clock |
| Alt+left-drag | Internal turn/tilt |
| Alt+right-drag | Internal pan, expressed as fractions of the card interior |
| Alt+scroll, on either Qt wheel axis | Internal scale about the interior centre |

These operations never move or resize the card or change its viewport. Plain CUSTOM geometry controls retain their
ordinary Edit behavior. Native Alt input during framed Edit is intercepted before QML wheel delivery; the filter exists
only while that capability and Edit are active. Descriptor admission and runtime generation fence all gestures.

The descriptor's `view_orbit_settings` and optional `scene_transform_settings` supply the complete five-key view pose.
The existing view owner settles and persists it once through canonical Settings, independently from curated art presets,
Custom art snapshots, layout Save/Cancel and SST geometry. A pan gesture uses a press-time baseline; scaling rebases
that baseline. Scene settlement does not cancel held WASD. Dormant input does not poll Settings.

Edit selection remains the fixed card rectangle. The internal eight-point guide and pivot use the same `basin_fit` /
`basin_item_point` projection as rendering and clamp to the card interior. They remain paint, never geometry authorities.

## Authoring and migration

`core/settings/visualizer_mode_settings.py` owns typed controls, ranges, defaults admission, UI buckets, conditions and
presentation/source projections. `core/settings/default_settings.py` owns default values. Primary Terrain contains the
bespoke lazy editor; Appearance and Waves contain the distinct material/reaction controls. Advanced Frequency Response
preserves the consumed old nodes, notches, lanes and smoothing; those audio coordinates are never relabelled as terrain.
Advanced Render supplies curve wires, glow, fill, water flow and optional sky/sun. The sun has independent enablement
and RGBA authoring; sky intensity does not suppress its colour. The five view fields have no Settings body rows.

The canonical terrain record is `{version: 1, size: N, heights: [N*N floats]}`, with `N` within 2..65 and finite heights
within 0..1. Rows run near/front to far/back. Explicit malformed records raise; missing old terrain receives the canonical
basin seed. Positive values below the normal float32 minimum are rejected so packing cannot silently turn authored land
into water. `rendering/gl_programs/heightfield.py` owns admission, float32 packing and the bilinear CPU sampler. Water is
exactly an authored sampled height of zero, independent of waves, view pose and land height scale.

The terrain editor supports Raise, Lower, Flatten and exact Water, bounded brush radius/strength, per-stroke Undo/Redo,
reset and an explicit blue water preview. Loading is silent; one completed stroke saves once through the existing Custom
spec hook. Escape/hide cancels an unfinished stroke. Brush/history state is ephemeral; closed Settings has no terrain
timer, scene renderer or simulation.

Old source profiles and Custom snapshots retain their consumed musical intent. Input/model serialization, Settings,
preset application and repair all use canonical admission. Shipped presets explicitly own the current art/source keys,
exclude view pose, and remain operator-editable; their artistic numbers are not regression goldens.

## Shared rendering and lifecycle

`rendering/quick/visualizer/implementations/shockwave_grid.py` remains the lazy mode renderer. It reuses MeshResources,
StreamRing, SceneTarget and optional emission bloom. `rendering/gl_programs/neon_lake_basin_program.py` owns the new
projection and distinct terrain/water shaders. The retired flat shaders and their overflow/fit implementation are removed.

Settings configuration packs terrain once into immutable FrozenFields. Captures retain that same payload by identity;
they do not copy or pack the control grid. A shared lazy `HeightfieldTexture` supports R32F heights or explicit RG32F
height/bank-distance storage; Neon uses the latter as one representation. The distance transform is derived once at
configuration, leaving exact authored-zero water ownership unchanged. Water displacement tapers over a narrow bank
band so a crest meets the solid shore continuously. The texture uploads only changed authored data and fences
unpack/texture/sampler state. Allocation/deletion failures stay loud and owned for retry.
It creates no clock or global texture cache.

The existing Scene3D bendable mesh samples an opt-in positive cubic B-spline surface. The wire paths are continuous
curved surface coordinates and height contours, not the tessellation's straight triangle edges. Cubic smoothing cannot
overshoot its local control-height range; authored bilinear zero remains the water-classification authority.
An authored tier change replaces the one active mesh; ordinary frames allocate/rebuild nothing. Authored patch
bounds are derived once per terrain change; static conservative fitting changes only with authored terrain/view/aspect.
Audio cannot pump the fit, resize the target or move the water boundary.

The preserved Shockwave onset ring admits each serial once, spaces events by passage intensity, caps capacity and ages
on the existing logical clock. Water uses travelling crests and echo rings, with bounded displacement even when events
overlap. Land has eight separate mode-owned growth envelopes with authored rise/settle times, static surface detail
and frequency-driven lighting. Growth=0 freezes land geometry while its light can still react. The renderer consumes
immutable growth values; it does not simulate them. Disabled movement discards envelope work; re-enabling starts from
zero on the existing capture clock. Sky, sun and bloom remain optional. All context-local resources retire
through the normal mode owner; unchanged shared consumers acquire no heightfield work.

Focused regression inventory lives in `Docs/TestSuite.md`. The pre-replacement render-cost baseline is
`tools/baselines/overhead/2026-10-13_000e222e.json`; current comparative cost and visual acceptance remain in the live plan.
