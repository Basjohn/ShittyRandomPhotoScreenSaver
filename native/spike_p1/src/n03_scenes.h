// N0.3 (Current_Plan.md item 8b; Docs/Future_Work/Native_Core_P3_Decisions.md, "The three test scenes"): the three
// convention scenes on one QRhi backend. Harness only; nothing here ships.
//
// python/run_n03.py owns everything that is not a GPU call: the target size, the geometry, the OpenGL-form matrices
// (core/settings/framed_camera.perspective_matrix for the depth scene), the uploaded image and strip, the block values
// and every check. This side does what the native core will do: it corrects each matrix once, at upload (rule 1;
// a corrected matrix refuses a second correction), picks the front face from the uploaded matrix (rule 4; both
// pipeline variants are built), draws, and reads every target back raw (memory rows, row 0 first, never flipped).
#pragma once

#include <QtCore/QByteArray>
#include <QtCore/QString>

namespace srpss_spike {

// GUI thread, a QGuiApplication must exist. backend: "vulkan" (our device: the N0.6 context must exist,
// n06ContextCreateJson; on it every run sets the messenger phase "n03_<run>"), "opengl", "d3d11" or "d3d12". Returns
// one JSON object: the backend's facts (isYUpInNDC, isYUpInFramebuffer, isClipDepthZeroToOne, clipSpaceCorrMatrix,
// the probe block's reflection) and per run its matrices, front face and readbacks (base64).
QByteArray n03RunJson(const QString &backend, const QByteArray &specJson);

} // namespace srpss_spike
