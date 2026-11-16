# R-235: Vertex and fragment stages disagreed about a shared resource

**16 November 2026. Source repair; official build and runtime proof pending.**

`checkGeometryPass` joined independently baked vertex/fragment resource declarations into one binding plan.
Its own uniform block comparison checked name, binding and total size, then selected the fragment layout to
pack the buffer used by both stages. Conventions checked only their reserved binding; shared storage checked
name and binding. Equal outer sizes could therefore hide different member offsets or access qualifiers.
Shared samplers could likewise overwrite the dimension selected by the earlier stage.

On the official ABI25 module `14be99283`, independently baked, actually reflected fixtures reproduce four
shared-layout/access mismatches admitted by `module.mode_blocks`. A fifth admits a shared sampler declared
3D in the vertex stage and 2D in the fragment, with reflection differing only in type. Three adjacent failures establish that
geometry also admitted writable storage and distinct storage blocks at one binding, despite its read-only
binding contract. Sixteen valid shared, stage-only, alias and distinct-binding controls pass. These are
GPU-free admission failures; no invalid pipeline or undefined draw is required. Receipts are retained under
`.artifacts/evidence/native_core/n3_2/20261116_cross_stage_old/`.

The repair compares resources common to both stages before selecting a packing layout, using Qt6.12 deep
reflection equality. Uniform `structName` and storage `instanceName` remain pack-local aliases, excluded on
copies by the same predicates used for alternate packs. Stage-only resources remain legal. Each geometry
storage declaration must be readonly and distinct storage blocks must have distinct bindings. Checks happen
at program admission; no per-record work, ABI change, fallback or render-state workaround is introduced.

`tests/test_native_cross_stage_interface.py` retains reflected negative and valid controls. Official-build
regressions, separate OpenGL/Vulkan shared-buffer draws and independent evidence review remain required.
D15 owns the contract. This repair does not establish the canonical shape of a malformed stage-only
`SrpssConventions` block or admit unsupported descriptor sets; those separate reproductions remain in the plan.

Primary source: [Qt6.12 reflection equality](https://github.com/qt/qtbase/blob/v6.12.0/src/gui/rhi/qshaderdescription.cpp).
