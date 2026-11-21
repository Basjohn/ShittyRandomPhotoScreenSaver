// The core's mip chains (ABI 33 for the self-mipped scene targets, ABI 35 for the item textures; Current_Plan.md N5.4,
// the lead's decision of 21 Nov: every level chain a sampler reads is the core's box kernel, in both renderers).
//
// A level is made from the level above it by shaders/mip_box.comp (RGBA16F) or shaders/mip_box_rgba8.comp (RGBA8), the
// texts rendering/gl_programs/mip_chain.py gives the Python renderer: each destination texel the exact area average of
// the source texels it covers (an odd side 2d + 1: three taps of (d - i), d and (i + 1) over 2d + 1), so the chain is the
// same whichever way the rows are stored and whatever the driver. Never QRhi's generateMips, whose odd levels are the
// driver's (anchored at memory row 0 on OpenGL) or a linear blit (Vulkan).
//
// One compute pass a level (QRhi orders a level's loads after the stores of the level above at the pass boundary,
// never within one pass). The kernel's pipeline is per QRhi and per format, over a layout of its own (a 2 x 2 texture
// of two levels), so it never depends on a texture's objects; a chain's bindings (one SRB a level) belong to the texture
// they name and are made again with it.
//
// Render thread only.
#pragma once

#include "rhi_owned.h"

#include <QtCore/QSize>
#include <QtCore/QString>
#include <rhi/qrhi.h>

namespace srpss_core {

// The most levels a chain holds (16384 a side: 15).
constexpr int kMaxChainLevels = 15;

// The levels of a full chain of `size` (1 for a 1 x 1 texture), at most kMaxChainLevels.
int mipChainLevels(const QSize &size);

// One texture's chain bindings: level L >= 1 loads L - 1 and stores L.
struct MipChain
{
    RhiOwned<QRhiShaderResourceBindings> level[kMaxChainLevels];
    int levels = 0;       // the chain's levels, level 0 included (bindings 1 .. levels - 1)
    int bindings = 0;     // SRBs held (the live count)
    QRhiTexture::Format format = QRhiTexture::RGBA8;
    QSize size;           // level 0's
    void release();
};

class MipChainKernel
{
public:
    MipChainKernel() = default;
    ~MipChainKernel();
    MipChainKernel(const MipChainKernel &) = delete;
    MipChainKernel &operator=(const MipChainKernel &) = delete;

    // The formats the kernel makes levels of (an item texture's RGBA8 and RGBA16F; a target's RGBA16F).
    static bool supports(QRhiTexture::Format format);
    // `texture`'s chain (MipMapped | UsedWithLoadStore, `size` its level 0) into `chain`: its bindings made (the old
    // ones released first). False with the reason: no compute on the device, a format the kernel does not make, or an
    // object the driver refused.
    bool bind(QRhi *rhi, QRhiTexture *texture, const QSize &size, MipChain *chain, QString *error);
    // The chain's passes (outside any pass): one compute pass a level. Nothing for a chain of one level.
    void record(QRhiCommandBuffer *cb, const MipChain &chain) const;
    // Every pipeline goes (the owner's release, or another QRhi).
    void release();

private:
    struct Kernel
    {
        RhiOwned<QRhiComputePipeline> pipeline;
        RhiOwned<QRhiShaderResourceBindings> layout;
        RhiOwned<QRhiTexture> layoutTexture;
    };
    Kernel *kernel(QRhiTexture::Format format);
    const Kernel *kernel(QRhiTexture::Format format) const;
    bool ensure(QRhi *rhi, QRhiTexture::Format format, QString *error);

    Kernel m_rgba8;
    Kernel m_rgba16f;
    const QRhi *m_rhi = nullptr;
};

} // namespace srpss_core
