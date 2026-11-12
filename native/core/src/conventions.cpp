#include "conventions.h"

#include <rhi/qrhi.h>

namespace srpss_core {

QMatrix4x4 targetCorrection(QRhi *rhi)
{
    QMatrix4x4 flip;
    if (rhi && rhi->isYUpInFramebuffer())
        flip.scale(1.0f, -1.0f, 1.0f); // F1: OpenGL is the backend that flips, so rows are top-down in memory
    return (rhi ? rhi->clipSpaceCorrMatrix() : QMatrix4x4()) * flip;
}

bool UploadMatrix::correct(const QMatrix4x4 &correction)
{
    if (m_corrected)
        return false;
    m_matrix = correction * m_matrix;
    m_corrected = true;
    return true;
}

bool frontFaceClockwise(const QMatrix4x4 &uploaded, bool ndcYUp)
{
    const float *d = uploaded.constData(); // column-major: d[0] is m00, d[5] is m11
    const bool mirrored = double(d[0]) * double(d[5]) > 0.0;
    return mirrored == ndcYUp;
}

ConventionsBlock targetConventions(QRhi *rhi)
{
    ConventionsBlock block;
    block.fragmentFlip = 0.0f; // F1: every target the core owns is top-down in memory
    block.ndcFlip = (rhi && rhi->isYUpInNDC() && !rhi->isYUpInFramebuffer()) ? 1.0f : 0.0f; // F2
    return block;
}

} // namespace srpss_core
