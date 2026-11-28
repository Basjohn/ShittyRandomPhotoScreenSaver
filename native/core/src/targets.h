// The core's colour render targets and the two Qt 6.12.0 rules they follow (Native_Core_N06_N07_Qt_Facts.md section I):
// - B: every target keeps its contents (PreserveColorContents), because QRhi gives a non-preserving offscreen render pass
//   an UNDEFINED initial layout and no external dependency (a write-after-write hazard between frames). A target that
//   must be cleared is cleared by its first draw, never by an UNDEFINED load. That hazard is Vulkan's: on OpenGL a
//   target to be cleared at a pass's start is cleared by the pass itself (glClear: clearingRenderTarget, N5.2h).
// - C: on Vulkan a preserving target is primed: the transition to COLOR_ATTACHMENT_OPTIMAL is recorded by the core with
//   READ and WRITE in its second scope, at creation and again after any other use (a readback), because QRhi's tracker
//   makes the image visible to the pass's write only, not to its load.
// Render thread only (the QRhi's thread).
#pragma once

#include "rhi_owned.h"

#include <QtCore/QByteArray>
#include <QtCore/QList>
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
    RhiOwned<QRhiTexture> texture;
    RhiOwned<QRhiRenderBuffer> depthStencil; // only a Qt Quick target's (createColorTarget's withDepthStencil)
    RhiOwned<QRhiRenderPassDescriptor> renderPass;
    RhiOwned<QRhiTextureRenderTarget> renderTarget;
    // N5.2h, OpenGL only: the same texture's render target without PreserveColorContents (its pass clears the whole
    // target at its start) and its own descriptor, made when first asked for (clearingRenderTarget) and again for a
    // later generation; compatible with renderPass's (the load is the only difference). Destroyed first.
    RhiOwned<QRhiRenderPassDescriptor> clearingRenderPass;
    RhiOwned<QRhiTextureRenderTarget> clearingRenderTargetObject;
    quint64 clearingGeneration = 0;
    // N5.2h: the generation whose clearing render target failed to create: not retried (nor reported again) until the
    // target's next generation, the scene targets' rule (scene_targets.cpp: dropped until the next layout).
    quint64 clearingFailedGeneration = 0;

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

// N5.2h: on OpenGL, the target's clearing render target (a pass begun on it clears the whole texture to the pass's clear
// colour, as a full-target clearing draw did, without that draw's fragments), made for the target's generation when
// needed; nullptr on every other backend (rule B: Vulkan clears by a draw) or when it cannot be made (`error` set once
// for that generation, which is then not retried), and the caller clears by its draw. Render thread only.
QRhiTextureRenderTarget *clearingRenderTarget(QRhi *rhi, ColorTarget *target, QString *error);

// Rule C: on Vulkan, when the texture is not in COLOR_ATTACHMENT_OPTIMAL, records the transition into `cb` (recording,
// outside any pass) and tells QRhi the layout; elsewhere nothing. Returns what was done. Every mip level is transitioned
// (N5.7b's mipmapped output; QRhi's layout is the whole image's).
QString primeForLoad(QRhi *rhi, QRhiCommandBuffer *cb, QRhiTexture *texture);

// Rule C for several textures in one external block (N5.7b: every target of a backdrop build): the ones not in
// COLOR_ATTACHMENT_OPTIMAL, each over every level. Returns how many were primed (0 off Vulkan).
int primeForLoad(QRhi *rhi, QRhiCommandBuffer *cb, const QList<QRhiTexture *> &textures);
// The same for `count` textures given as an array (the scene targets' per-run primes: nothing allocated per record).
int primeForLoad(QRhi *rhi, QRhiCommandBuffer *cb, QRhiTexture *const *textures, int count);

// N3.1 audit 2 (H1): a multisampled scene target's resolve textures (QRhi's average), before every run on Vulkan. QRhi
// gives a resolve attachment initialLayout UNDEFINED and no VK_SUBPASS_EXTERNAL dependency (Qt 6.12.0's defect B,
// native/core/python/vk_validation.py), so the run's begin transitions it unordered against the previous frame's resolve
// store whenever no read ordered the two in between. This records, every time, a barrier from every earlier write to
// every later stage (ALL_COMMANDS: the render pass's layout transition included) and tells QRhi the layout. Returns how
// many it recorded (0 off Vulkan).
int primeResolvesForPass(QRhi *rhi, QRhiCommandBuffer *cb, QRhiTexture *const *textures, int count);

// Rule C for a depth texture (N3.1, D14 point 5: depth is preserved and cleared by a draw): on Vulkan, when it is not in
// DEPTH_STENCIL_ATTACHMENT_OPTIMAL (a capture or a later pass sampled it), records the transition with depth read and
// write in its second scope and tells QRhi the layout; elsewhere nothing. True when it recorded one.
bool primeDepthForLoad(QRhi *rhi, QRhiCommandBuffer *cb, QRhiTexture *depth);

// N3.4: a pass that samples one texture in both its vertex and its fragment stage (the defocus step's gather and
// sprites read the layer). Qt 6.12.0's pass tracker keeps the earlier stage (vertex) as the texture's last use, so its
// next barrier on it (generateMips' transition) leaves the fragment reads out of its first scope (synchronisation
// validation's WRITE_AFTER_READ). On Vulkan this records, after that pass, an execution dependency from every vertex and
// fragment shader stage to every later one, which QRhi's barrier chains after; elsewhere nothing. True when recorded.
bool chainShaderReads(QRhi *rhi, QRhiCommandBuffer *cb);

// The same for a texture outside any frame: an offscreen frame of its own, waited on (a target's creation edge before
// any frame of the host exists, the hidden host's Quick target).
QString primeForLoadOutsideFrame(QRhi *rhi, QRhiTexture *texture);

} // namespace srpss_core
