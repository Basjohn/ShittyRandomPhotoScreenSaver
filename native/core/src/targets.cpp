#include "targets.h"

#include <QtCore/QAtomicInteger>
#include <rhi/qrhi.h>
#include <rhi/qrhi_platform.h>

#include <QtGui/QVulkanFunctions>
#include <QtGui/QVulkanInstance>

#ifndef VK_NO_PROTOTYPES
#define VK_NO_PROTOTYPES // the module never links vulkan-1.lib (vulkan_context.cpp)
#endif
#include <vulkan/vulkan.h>

namespace srpss_core {

namespace {
QAtomicInteger<quint64> g_targetGenerations { 0 };
}

quint64 nextTargetGeneration()
{
    return g_targetGenerations.fetchAndAddRelaxed(1) + 1;
}

ColorTarget::ColorTarget() = default;
ColorTarget::~ColorTarget() = default;
ColorTarget::ColorTarget(ColorTarget &&) noexcept = default;
ColorTarget &ColorTarget::operator=(ColorTarget &&) noexcept = default;

void ColorTarget::reset()
{
    renderTarget.reset();
    renderPass.reset();
    depthStencil.reset();
    texture.reset();
    generation = 0;
}

bool createColorTarget(QRhi *rhi, const QSize &size, const QByteArray &name, ColorTarget *out, QString *error,
                       bool withDepthStencil, QRhiTexture::Format format)
{
    out->reset();
    out->texture.reset(rhi->newTexture(format, size, 1,
                                       QRhiTexture::RenderTarget | QRhiTexture::UsedAsTransferSource));
    out->texture->setName(name);
    if (!out->texture->create()) {
        *error = QStringLiteral("%1: texture create failed").arg(QString::fromUtf8(name));
        out->reset();
        return false;
    }
    QRhiTextureRenderTargetDescription description { QRhiColorAttachment(out->texture.get()) };
    if (withDepthStencil) {
        out->depthStencil.reset(rhi->newRenderBuffer(QRhiRenderBuffer::DepthStencil, size, 1));
        out->depthStencil->setName(name + QByteArrayLiteral(" depth-stencil"));
        if (!out->depthStencil->create()) {
            *error = QStringLiteral("%1: depth-stencil create failed").arg(QString::fromUtf8(name));
            out->reset();
            return false;
        }
        description.setDepthStencilBuffer(out->depthStencil.get());
    }
    out->renderTarget.reset(rhi->newTextureRenderTarget(description, QRhiTextureRenderTarget::PreserveColorContents));
    out->renderTarget->setName(name);
    out->renderPass.reset(out->renderTarget->newCompatibleRenderPassDescriptor());
    out->renderTarget->setRenderPassDescriptor(out->renderPass.get());
    if (!out->renderTarget->create()) {
        *error = QStringLiteral("%1: render target create failed").arg(QString::fromUtf8(name));
        out->reset();
        return false;
    }
    out->generation = nextTargetGeneration();
    return true;
}

QString primeForLoad(QRhi *rhi, QRhiCommandBuffer *cb, QRhiTexture *texture)
{
    if (!rhi || !cb || !texture || rhi->backend() != QRhi::Vulkan)
        return QStringLiteral("not Vulkan");
    const QRhiTexture::NativeTexture native = texture->nativeTexture();
    if (native.layout == VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL)
        return QStringLiteral("already primed");
    const auto *handles = static_cast<const QRhiVulkanNativeHandles *>(rhi->nativeHandles());
    if (!handles || !handles->inst || !handles->dev)
        return QStringLiteral("no native handles");
    QVulkanDeviceFunctions *df = handles->inst->deviceFunctions(handles->dev);
    if (!df)
        return QStringLiteral("no device functions");
    cb->beginExternal();
    const auto *cbHandles = static_cast<const QRhiVulkanCommandBufferNativeHandles *>(cb->nativeHandles());
    const bool recorded = cbHandles && cbHandles->commandBuffer;
    if (recorded) {
        VkImageMemoryBarrier barrier = {};
        barrier.sType = VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER;
        barrier.srcAccessMask = VK_ACCESS_MEMORY_WRITE_BIT;
        barrier.dstAccessMask = VK_ACCESS_COLOR_ATTACHMENT_READ_BIT | VK_ACCESS_COLOR_ATTACHMENT_WRITE_BIT;
        barrier.oldLayout = VkImageLayout(native.layout); // PREINITIALIZED at creation on Qt 6.12.0 (defect A)
        barrier.newLayout = VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL;
        barrier.srcQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED;
        barrier.dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED;
        barrier.image = reinterpret_cast<VkImage>(quintptr(native.object));
        barrier.subresourceRange.aspectMask = VK_IMAGE_ASPECT_COLOR_BIT;
        // Every level (N5.7b: the backdrop's output has mips, each level a target of its own; QRhi tracks one layout
        // for the whole image, and setNativeLayout below names it for every level). One level for every other target.
        barrier.subresourceRange.levelCount = VK_REMAINING_MIP_LEVELS;
        barrier.subresourceRange.layerCount = 1;
        df->vkCmdPipelineBarrier(cbHandles->commandBuffer, VK_PIPELINE_STAGE_ALL_COMMANDS_BIT,
                                 VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT, 0, 0, nullptr, 0, nullptr, 1,
                                 &barrier);
    }
    cb->endExternal();
    if (!recorded)
        return QStringLiteral("no native command buffer");
    texture->setNativeLayout(VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL);
    return QStringLiteral("primed from layout %1").arg(native.layout);
}

int primeForLoad(QRhi *rhi, QRhiCommandBuffer *cb, const QList<QRhiTexture *> &textures)
{
    if (!rhi || !cb || rhi->backend() != QRhi::Vulkan)
        return 0;
    QList<QRhiTexture *> due;
    for (QRhiTexture *texture : textures) {
        if (texture && texture->nativeTexture().layout != VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL)
            due.append(texture);
    }
    if (due.isEmpty())
        return 0;
    const auto *handles = static_cast<const QRhiVulkanNativeHandles *>(rhi->nativeHandles());
    if (!handles || !handles->inst || !handles->dev)
        return 0;
    QVulkanDeviceFunctions *df = handles->inst->deviceFunctions(handles->dev);
    if (!df)
        return 0;
    cb->beginExternal();
    const auto *cbHandles = static_cast<const QRhiVulkanCommandBufferNativeHandles *>(cb->nativeHandles());
    const bool recorded = cbHandles && cbHandles->commandBuffer;
    if (recorded) {
        QList<VkImageMemoryBarrier> barriers;
        barriers.reserve(due.size());
        for (QRhiTexture *texture : due) {
            const QRhiTexture::NativeTexture native = texture->nativeTexture();
            VkImageMemoryBarrier barrier = {};
            barrier.sType = VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER;
            barrier.srcAccessMask = VK_ACCESS_MEMORY_WRITE_BIT;
            barrier.dstAccessMask = VK_ACCESS_COLOR_ATTACHMENT_READ_BIT | VK_ACCESS_COLOR_ATTACHMENT_WRITE_BIT;
            barrier.oldLayout = VkImageLayout(native.layout);
            barrier.newLayout = VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL;
            barrier.srcQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED;
            barrier.dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED;
            barrier.image = reinterpret_cast<VkImage>(quintptr(native.object));
            barrier.subresourceRange.aspectMask = VK_IMAGE_ASPECT_COLOR_BIT;
            barrier.subresourceRange.levelCount = VK_REMAINING_MIP_LEVELS;
            barrier.subresourceRange.layerCount = 1;
            barriers.append(barrier);
        }
        df->vkCmdPipelineBarrier(cbHandles->commandBuffer, VK_PIPELINE_STAGE_ALL_COMMANDS_BIT,
                                 VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT, 0, 0, nullptr, 0, nullptr,
                                 uint32_t(barriers.size()), barriers.constData());
    }
    cb->endExternal();
    if (!recorded)
        return 0;
    for (QRhiTexture *texture : due)
        texture->setNativeLayout(VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL);
    return int(due.size());
}

QString primeForLoadOutsideFrame(QRhi *rhi, QRhiTexture *texture)
{
    if (!rhi || !texture || rhi->backend() != QRhi::Vulkan)
        return QStringLiteral("not Vulkan");
    QRhiCommandBuffer *cb = nullptr;
    if (rhi->beginOffscreenFrame(&cb) != QRhi::FrameOpSuccess || !cb)
        return QStringLiteral("no offscreen frame");
    const QString note = primeForLoad(rhi, cb, texture);
    rhi->endOffscreenFrame();
    rhi->finish();
    return note;
}

} // namespace srpss_core
