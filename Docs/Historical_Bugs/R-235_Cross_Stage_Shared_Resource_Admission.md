# R-235: Vertex and fragment stages disagreed about a shared resource

**16 November 2026. Repaired and proved on official build `b1451eb11`; independent High review.**

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

`tests/test_native_cross_stage_interface.py` retains all 24 reflected negative and valid controls. The official
build passes all 99 focused cross-stage, sorted-pack, mesh-buffer, generic-mode and post-stage tests without skips.
Run43929409887/token20261116_202944_090456 built `b1451eb11`; the retained manifest matches the installed binary.

Hidden OpenGL and Vulkan draws each pass 211 guards across shared baseline, different stage-local aliases,
and vertex-only/fragment-only UBO or SSBO variants. Independent mutations move the triangle exactly eight
pixels through its UBO or five through storage, and change its constant colour by the expected distinct amounts.
Absent-stage mutations leave pixels exact; each restore is exact; corresponding alias frames are exact.
Actual qsb reflection, settings, raw frames, clear/covered pixels and ownership receipts are retained under
`n3_2/20261116_cross_stage_runtime/`. All checked resources and hosts retire to zero. The lead inspected both sheets.
Vulkan validation loaded: ten recorded Qt defectA errors are excused, zero unexplained errors/warnings;
the instance-creation loader warning remains attributed. This is synthetic offscreen proof, not broad visual
acceptance, a performance claim, or a D3D/Metal result.

Canonical batched/loop/direct form regression passes on both backends and actually records form3. Post-stage
gate/parity also passes with the Python reference, rule(a), rule(b) and analytic checks; the lead inspected both
native sheets. Each Vulkan regression retains ten known Qt defectA errors and zero unexplained findings.
Evidence under `.artifacts/evidence/native_core/`: `n3_2/20261116_cross_stage_fixed/` holds XML/manifest;
`n3_2/20261116_cross_stage_b1451eb11/` holds draw forms;
`n3_4/20261116_cross_stage_b1451eb11/` holds post-stage regression.

D15 owns the contract. This repair does not establish the canonical shape of a malformed stage-only
`SrpssConventions` block or admit unsupported descriptor sets; those separate reproductions remain in the plan.

Primary source: [Qt6.12 reflection equality](https://github.com/qt/qtbase/blob/v6.12.0/src/gui/rhi/qshaderdescription.cpp).
