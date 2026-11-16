# R-236: Same-layout mesh replacement rebuilt retained streams

**16 November 2026. Repaired and proved on official `7d7fe160a`; independent High review.**

`ModeContent::ensure()` treated every `ModeMeshes::objects()` edge as a vertex-input layout change and released
all program resources. Replacing a mesh with identical bytes/layout therefore rebuilt its streams and uniform
arena, discarding storage bytes beyond the next record's used length. That violates the stream's retained-tail
contract and performs unrelated allocations. Graphics already resolves current mesh buffers/counts per draw;
compute mesh bindings instead cache their buffers in SRBs and must be explicitly retargeted.

The old official `b1451eb11` hidden OpenGL falsifier reproduces three buffers instead of one, stream generation
1→2 for identical bytes, and a retained-tail pixel mismatch against a fresh mixed-tail control. Changed geometry
uses fresh bytes correctly but still rebuilds; static instance replacement and compute mesh replacement also
advance the unrelated stream generation. Named missing-mesh, layout-change and resend controls pass.
Evidence: `.artifacts/evidence/native_core/n3_2/20261116_mesh_retarget_preparation/old_gl_surface/`.

The repair shares the existing geometry input-layout assembler with the mesh-edge check and compares against
the authoritative QRhi pipeline layout. Compatible replacements retain pipelines, streams and arena. Mesh-dependent
compute SRBs retarget through existing binding assembly; a simultaneous texture edge uses the full rebind owner.
Only a successful rebind acknowledges the mesh object edge. Failure retains the original release/rebuild path.
Still redraw and failed-attempt retry generations remain unchanged; no layout cache, timer or fallback is added.

Official run43938820599/token20261116_212318_688444 passes206 focused tests. GL/Vulkan candidate proofs
retain one buffer and generation1→1 for identical/changed meshes and tail updates, two buffers with unchanged
generation for static-instance replacement, fresh-geometry pixels and exact mixed-tail controls. Genuine layout
changes rebuild; missing meshes clear the final surface, re-add/resend recovers, and scene-graph reconstruction
requires a fresh upload. The lead inspected both geometry/tail sheets.

Live compute reads all64 fresh values after replacement; mesh-only rebind reporting advances0→1 immediately.
A non-storage replacement and mesh removal dispatch nothing, name the refusal and recover exactly after resend.
Simultaneous mesh and texture-object replacement reads both new inputs exactly; the texture actually resizes2×2→4×4
to force the full rebind branch. Same-size pixel uploads reuse the texture object and would not establish that edge.

The durable regression is `mesh_buffer_check.py --rounds retarget`, using its existing baker, API children,
validation and retirement owner. `mesh_retarget_check.py` is its non-CLI round implementation. Canonical execution
passes55 guards per API; all checked resources and hosts retire to zero. A focused counter/verdict negative rejects
the old three-buffer/rebuild snapshot. The changed harness/mesh tests pass81 cases. Independent source and
built-evidence reviews are clear. Vulkan records ten excused Qt defectA errors and zero unexplained errors/warnings;
the loader warning remains attributed. Compute parity, batched forms and post-stage gate/parity regressions also
pass on both APIs with the Python reference where applicable.

Evidence under `.artifacts/evidence/native_core/`: `n3_2/20261116_retarget_reserved_fixed/` holds manifests/XML;
`n3_2/20261116_retarget_canonical_7d7fe160a/` holds the canonical guard receipt and images;
the preparation folder's `candidate_*` folders retain the first main/compute-edge proofs. Relevant regressions are
`n3_2`, `n3_3` and `n3_4`'s `20261116_retarget_reserved_7d7fe160a/` folders. This establishes avoided allocations
and retained data in these cases; no general timing speedup or physical driver-fault recovery is claimed.

Initial probe corrections used the real stream-generation producer and judged a lost
mesh on the final cleared surface: unused scene attachments retain their prior contents and are not that contract.
Physical device-fault recovery remains N3.6, distinct from the scene-graph reconstruction control.

Qt6.12's [QRhi input-layout equality and pipeline getter](https://github.com/qt/qtbase/blob/v6.12.0/src/gui/rhi/qrhi.h)
are retained with the executable falsifier, proposed design and compute fixture in the evidence preparation folder.
D15 owns the current contract; N3.6 owns physical device-fault recovery.
