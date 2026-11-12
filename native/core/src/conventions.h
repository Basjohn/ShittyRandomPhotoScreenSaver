// The core's backend conventions (Docs/Future_Work/Native_Core_P3_Decisions.md, N0.3 rules 1 to 4 with the decided F1
// to F3, proved by the N0.3 harness run 2): the one place the core learns a backend's clip space and row order.
//
// - A matrix arrives in OpenGL form (one camera owner, D5.5) and is corrected exactly once, when its block is written
//   (rule 1). For a target the core owns the correction is clipSpaceCorrMatrix() times a Y flip where the framebuffer is
//   Y-up (F1: OpenGL), so texel (0,0) is the top-left in memory on every backend and the core's readbacks are never
//   flipped (rule 2).
// - The front face of a culling pass is chosen from the matrix as uploaded, after that correction (rule 4, F3).
// - The conventions block of a core-owned target: x (the fragment row flip) 0 on every backend (F1), y (the clip-NDC Y
//   flip) isYUpInNDC() && !isYUpInFramebuffer() (F2: 1 on D3D11, D3D12, Metal).
#pragma once

#include <QtGui/QMatrix4x4>

class QRhi;

namespace srpss_core {

// The conventions block's binding in every shader that includes srpss_conventions.glsl (N0.3 question 3, chosen once:
// rendering/gl_programs/scene3d.py SCENE3D_CONVENTIONS_BLOCK_BINDING, the OpenGL renderer's, so one include serves both).
constexpr int kConventionsBinding = 17;

// Rule 1 with F1: the upload correction for a target the core owns.
QMatrix4x4 targetCorrection(QRhi *rhi);

// An OpenGL-form matrix on its way into a block: corrected exactly once. A second correction is refused and leaves the
// matrix as it is (the caller records the refusal); the matrix knows whether it was corrected.
class UploadMatrix
{
public:
    explicit UploadMatrix(const QMatrix4x4 &glForm) : m_matrix(glForm) {}

    bool correct(const QMatrix4x4 &correction);
    bool corrected() const { return m_corrected; }
    const QMatrix4x4 &matrix() const { return m_matrix; }

private:
    QMatrix4x4 m_matrix;
    bool m_corrected = false;
};

// Rule 4 (rendering/gl_programs/conventions.py front_face_clockwise): whether the front faces are clockwise, from the
// matrix's handedness and the backend's clip-space Y. `uploaded` is the matrix as uploaded, after the correction (F3);
// the front faces are those counter-clockwise in OpenGL's clip space through a Y-down (Quick-like) matrix.
bool frontFaceClockwise(const QMatrix4x4 &uploaded, bool ndcYUp);

// The std140 conventions block (one vec4) of a target.
struct ConventionsBlock
{
    float fragmentFlip = 0.0f; // x
    float ndcFlip = 0.0f;      // y
    float reserved0 = 0.0f;
    float reserved1 = 0.0f;
};
static_assert(sizeof(ConventionsBlock) == 16, "std140 vec4");

// F1 and F2: the block of a target the core owns on this QRhi's backend.
ConventionsBlock targetConventions(QRhi *rhi);

} // namespace srpss_core
