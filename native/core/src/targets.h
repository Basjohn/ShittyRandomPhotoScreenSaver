// The core's colour render targets and the two Qt 6.12.0 rules they follow (Native_Core_N06_N07_Qt_Facts.md section I):
// - B: every target keeps its contents (PreserveColorContents), because QRhi gives a non-preserving offscreen render pass
//   an UNDEFINED initial layout and no external dependency (a write-after-write hazard between frames). A target that
//   must be cleared is cleared by its first draw, never by an UNDEFINED load.
// - C: on Vulkan a preserving target is primed: the transition to COLOR_ATTACHMENT_OPTIMAL is recorded by the core with
//   READ and WRITE in its second scope, at creation and again after any other use (a readback), because QRhi's tracker
//   makes the image visible to the pass's write only, not to its load.
// Render thread only (the QRhi's thread).
#pragma once

#include <QtCore/QByteArray>
#include <QtCore/QSize>
#include <QtCore/QString>
// The whole QRhiTexture declaration, not a forward one: the target helpers name QRhiTexture::Format in their defaults.
#include <rhi/qrhi.h>

#include <memory>

class QRhi;
class QRhiCommandBuffer;
class QRhiRenderBuffer;
class QRhiRenderPassDescriptor;
class QRhiTexture;
class QRhiTextureRenderTarget;

namespace srpss_core {

struct ColorTarget
{
    // Destroyed in reverse order: the render target, its pass descriptor, the depth-stencil buffer, then the texture.
    std::unique_ptr<QRhiTexture> texture;
    std::unique_ptr<QRhiRenderBuffer> depthStencil; // only a Qt Quick target's (createColorTarget's withDepthStencil)
    std::unique_ptr<QRhiRenderPassDescriptor> renderPass;
    std::unique_ptr<QRhiTextureRenderTarget> renderTarget;

    ColorTarget();
    ~ColorTarget();
    ColorTarget(ColorTarget &&) noexcept;
    ColorTarget &operator=(ColorTarget &&) noexcept;
    void reset();
    bool isValid() const { return texture && renderTarget && renderPass; }
    // A process-unique number per creation of the target (createColorTarget) and per change of its size (a content's
    // latch keys on it, never on an address that can repeat: audit N29 round 2, L4). 0 for none.
    quint64 generation = 0;
};

// The next target generation (any thread).
quint64 nextTargetGeneration();

// An RGBA8 target the core owns: a render target, read back as a transfer source, keeping its contents (rule B).
// `withDepthStencil`: a depth-stencil buffer beside it, which Qt Quick needs when it renders into the target (its opaque
// items are drawn front to back against the depth buffer and its clips use the stencil; Qt creates none for a target
// handed over with QQuickRenderTarget::fromRhiRenderTarget). Not preserved: Qt Quick clears it at every pass.
bool createColorTarget(QRhi *rhi, const QSize &size, const QByteArray &name, ColorTarget *out, QString *error,
                       bool withDepthStencil = false, QRhiTexture::Format format = QRhiTexture::RGBA8);

// Rule C: on Vulkan, when the texture is not in COLOR_ATTACHMENT_OPTIMAL, records the transition into `cb` (recording,
// outside any pass) and tells QRhi the layout; elsewhere nothing. Returns what was done.
QString primeForLoad(QRhi *rhi, QRhiCommandBuffer *cb, QRhiTexture *texture);

// The same for a texture outside any frame: an offscreen frame of its own, waited on (a target's creation edge before
// any frame of the host exists, the hidden host's Quick target).
QString primeForLoadOutsideFrame(QRhi *rhi, QRhiTexture *texture);

} // namespace srpss_core
