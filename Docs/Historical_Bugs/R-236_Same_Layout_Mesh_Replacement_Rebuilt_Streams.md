# R-236: Same-layout mesh replacement rebuilt retained streams

**16 November 2026. Source repair; official build and candidate runtime proof pending.**

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

Independent High source review is clear, including immediate publication of the existing rebind counter.
Candidate GL/Vulkan tail/fresh-byte/layout/lifecycle proof and live compute failure/recovery/combined-texture
controls remain required. Initial probe corrections used the real stream-generation producer and judged a lost
mesh on the final cleared surface: unused scene attachments retain their prior contents and are not that contract.
Physical device-fault recovery remains N3.6, distinct from the scene-graph reconstruction control.

Qt6.12's [QRhi input-layout equality and pipeline getter](https://github.com/qt/qtbase/blob/v6.12.0/src/gui/rhi/qrhi.h)
are retained with the executable falsifier, proposed design and compute fixture in the evidence preparation folder.
D15 owns the current contract; the live plan owns pending proof.
