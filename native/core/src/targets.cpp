#include "targets.h"

#include <rhi/qrhi.h>
#include <rhi/qrhi_platform.h>

#include <QtGui/QVulkanFunctions>
#include <QtGui/QVulkanInstance>

#ifndef VK_NO_PROTOTYPES
#define VK_NO_PROTOTYPES // the module never links vulkan-1.lib (vulkan_context.cpp)
#endif
#include <vulkan/vulkan.h>

namespace srpss_core {

ColorTarget::ColorTarget() = default;
ColorTarget::~ColorTarget() = default;
ColorTarget::ColorTarget(ColorTarget &&) noexcept = default;
ColorTarget &ColorTarget::operator=(ColorTarget &&) noexcept = default;

void ColorTarget::reset()
{
    renderTarget.reset();
    renderPass.reset();
    texture.reset();
}

bool createColorTarget(QRhi *rhi, const QSize &size, const QByteArray &name, ColorTarget *out, QString *error)
{
    out->reset();
    out->texture.reset(rhi->newTexture(QRhiTexture::RGBA8, size, 1,
                                       QRhiTexture::RenderTarget | QRhiTexture::UsedAsTransferSource));
    out->texture->setName(name);
    if (!out->texture->create()) {
        *error = QStringLiteral("%1: texture create failed").arg(QString::fromUtf8(name));
        out->reset();
        return false;
    }
    out->renderTarget.reset(rhi->newTextureRenderTarget({ QRhiColorAttachment(out->texture.get()) },
                                                        QRhiTextureRenderTarget::PreserveColorContents));
    out->renderTarget->setName(name);
    out->renderPass.reset(out->renderTarget->newCompatibleRenderPassDescriptor());
    out->renderTarget->setRenderPassDescriptor(out->renderPass.get());
    if (!out->renderTarget->create()) {
        *error = QStringLiteral("%1: render target create failed").arg(QString::fromUtf8(name));
        out->reset();
        return false;
    }
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
        barrier.subresourceRange.levelCount = 1;
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
