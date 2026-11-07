// P1 spike: the one QRhi renderer every host in the spike shares.
//
// Hosts: (1) a standalone offscreen QRhi on a native thread (no Qt Quick),
// (2) the "hybrid" node, a PySide6 QSGRenderNode whose prepare()/render()
// delegate here (proves ABI and RHI sharing with PySide6's Qt Quick), and
// (3) the native QSGRenderNode (SPIKE_WITH_QUICK), where no Python runs at all.
#pragma once

#include <rhi/qrhi.h>
#include <QtGui/QMatrix4x4>

#include <memory>

namespace srpss_spike {

class QuadField
{
public:
    explicit QuadField(int instanceCount);
    ~QuadField();

    QuadField(const QuadField &) = delete;
    QuadField &operator=(const QuadField &) = delete;

    // Creates the buffers and the pipeline on first use, and the pipeline again
    // when the render pass is no longer compatible. Static uploads go into
    // `updates`; the caller submits that batch before recording.
    bool ensure(QRhi *rhi, QRhiRenderPassDescriptor *renderPass, int sampleCount,
                QRhiResourceUpdateBatch *updates);

    // unitToClip maps the unit square of the drawn area (0..1, y down) to clip
    // space, including the backend's clip-space correction.
    void update(QRhiResourceUpdateBatch *updates, const QMatrix4x4 &unitToClip,
                float timeSeconds, float aspect);

    // Records the draw. Must be inside a render pass compatible with ensure().
    void record(QRhiCommandBuffer *cb, const QRhiViewport &viewport);

    void release();

    int instanceCount() const { return m_instances; }
    bool isReady() const { return m_pipeline != nullptr; }

private:
    bool createPipeline(QRhiRenderPassDescriptor *renderPass, int sampleCount);

    int m_instances;
    QRhi *m_rhi = nullptr;
    int m_sampleCount = 1;
    std::unique_ptr<QRhiRenderPassDescriptor> m_renderPass; // owned compatible copy
    std::unique_ptr<QRhiBuffer> m_corners;
    std::unique_ptr<QRhiBuffer> m_instanceData;
    std::unique_ptr<QRhiBuffer> m_uniforms;
    std::unique_ptr<QRhiShaderResourceBindings> m_bindings;
    std::unique_ptr<QRhiGraphicsPipeline> m_pipeline;
};

// Unit square (0..1, y down) to clip space for a target that QRhi owns
// directly (no Qt Quick projection available).
QMatrix4x4 unitToClipForRhi(QRhi *rhi);

} // namespace srpss_spike
