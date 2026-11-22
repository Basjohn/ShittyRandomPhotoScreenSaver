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
        barrier.subresourceRange.layerCount = VK_REMAINING_ARRAY_LAYERS; // ABI 42: a cube's six faces too
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
            barrier.subresourceRange.layerCount = VK_REMAINING_ARRAY_LAYERS; // ABI 42: a cube's six faces too
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

namespace {

constexpr int kArrayBarriers = 8;

// One external block of colour barriers into COLOR_ATTACHMENT_OPTIMAL from every earlier write, for at most
// kArrayBarriers textures, on the stack (nothing allocated): the ones not in that layout, or every one (`always`).
int colourBarriers(QRhi *rhi, QRhiCommandBuffer *cb, QRhiTexture *const *textures, int count, bool always,
                   VkPipelineStageFlags dstStage, VkAccessFlags dstAccess)
{
    if (!rhi || !cb || !textures || count <= 0 || rhi->backend() != QRhi::Vulkan)
        return 0;
    QRhiTexture *due[kArrayBarriers];
    int n = 0;
    for (int i = 0; i < count && n < kArrayBarriers; ++i) {
        QRhiTexture *texture = textures[i];
        if (texture && (always || texture->nativeTexture().layout != VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL))
            due[n++] = texture;
    }
    if (n == 0)
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
        VkImageMemoryBarrier barriers[kArrayBarriers] = {};
        for (int i = 0; i < n; ++i) {
            const QRhiTexture::NativeTexture native = due[i]->nativeTexture();
            VkImageMemoryBarrier &barrier = barriers[i];
            barrier.sType = VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER;
            barrier.srcAccessMask = VK_ACCESS_MEMORY_WRITE_BIT;
            barrier.dstAccessMask = dstAccess;
            barrier.oldLayout = VkImageLayout(native.layout);
            barrier.newLayout = VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL;
            barrier.srcQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED;
            barrier.dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED;
            barrier.image = reinterpret_cast<VkImage>(quintptr(native.object));
            barrier.subresourceRange.aspectMask = VK_IMAGE_ASPECT_COLOR_BIT;
            barrier.subresourceRange.levelCount = VK_REMAINING_MIP_LEVELS;
            // ABI 42: every layer (a cube target's six faces: QRhi's layout is the whole image's, layers included).
            barrier.subresourceRange.layerCount = VK_REMAINING_ARRAY_LAYERS;
        }
        df->vkCmdPipelineBarrier(cbHandles->commandBuffer, VK_PIPELINE_STAGE_ALL_COMMANDS_BIT, dstStage, 0, 0, nullptr,
                                 0, nullptr, uint32_t(n), barriers);
    }
    cb->endExternal();
    if (!recorded)
        return 0;
    for (int i = 0; i < n; ++i)
        due[i]->setNativeLayout(VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL);
    return n;
}

} // namespace

int primeForLoad(QRhi *rhi, QRhiCommandBuffer *cb, QRhiTexture *const *textures, int count)
{
    int primed = 0;
    for (int start = 0; start < count; start += kArrayBarriers) {
        primed += colourBarriers(rhi, cb, textures + start, qMin(kArrayBarriers, count - start), false,
                                 VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT,
                                 VK_ACCESS_COLOR_ATTACHMENT_READ_BIT | VK_ACCESS_COLOR_ATTACHMENT_WRITE_BIT);
    }
    return primed;
}

int primeResolvesForPass(QRhi *rhi, QRhiCommandBuffer *cb, QRhiTexture *const *textures, int count)
{
    int primed = 0;
    for (int start = 0; start < count; start += kArrayBarriers) {
        // ALL_COMMANDS in the second scope: synchronisation validation's own rule for a barrier that must order the
        // render pass's layout transition after it.
        primed += colourBarriers(rhi, cb, textures + start, qMin(kArrayBarriers, count - start), true,
                                 VK_PIPELINE_STAGE_ALL_COMMANDS_BIT,
                                 VK_ACCESS_MEMORY_READ_BIT | VK_ACCESS_MEMORY_WRITE_BIT);
    }
    return primed;
}

bool primeDepthForLoad(QRhi *rhi, QRhiCommandBuffer *cb, QRhiTexture *depth)
{
    if (!rhi || !cb || !depth || rhi->backend() != QRhi::Vulkan)
        return false;
    const QRhiTexture::NativeTexture native = depth->nativeTexture();
    if (native.layout == VK_IMAGE_LAYOUT_DEPTH_STENCIL_ATTACHMENT_OPTIMAL)
        return false;
    const auto *handles = static_cast<const QRhiVulkanNativeHandles *>(rhi->nativeHandles());
    if (!handles || !handles->inst || !handles->dev)
        return false;
    QVulkanDeviceFunctions *df = handles->inst->deviceFunctions(handles->dev);
    if (!df)
        return false;
    cb->beginExternal();
    const auto *cbHandles = static_cast<const QRhiVulkanCommandBufferNativeHandles *>(cb->nativeHandles());
    const bool recorded = cbHandles && cbHandles->commandBuffer;
    if (recorded) {
        VkImageMemoryBarrier barrier = {};
        barrier.sType = VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER;
        barrier.srcAccessMask = VK_ACCESS_MEMORY_WRITE_BIT;
        barrier.dstAccessMask = VK_ACCESS_DEPTH_STENCIL_ATTACHMENT_READ_BIT
            | VK_ACCESS_DEPTH_STENCIL_ATTACHMENT_WRITE_BIT;
        barrier.oldLayout = VkImageLayout(native.layout);
        barrier.newLayout = VK_IMAGE_LAYOUT_DEPTH_STENCIL_ATTACHMENT_OPTIMAL;
        barrier.srcQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED;
        barrier.dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED;
        barrier.image = reinterpret_cast<VkImage>(quintptr(native.object));
        barrier.subresourceRange.aspectMask = VK_IMAGE_ASPECT_DEPTH_BIT; // D32F: depth only
        barrier.subresourceRange.levelCount = 1;
        barrier.subresourceRange.layerCount = 1;
        df->vkCmdPipelineBarrier(cbHandles->commandBuffer, VK_PIPELINE_STAGE_ALL_COMMANDS_BIT,
                                 VK_PIPELINE_STAGE_EARLY_FRAGMENT_TESTS_BIT | VK_PIPELINE_STAGE_LATE_FRAGMENT_TESTS_BIT,
                                 0, 0, nullptr, 0, nullptr, 1, &barrier);
    }
    cb->endExternal();
    if (!recorded)
        return false;
    depth->setNativeLayout(VK_IMAGE_LAYOUT_DEPTH_STENCIL_ATTACHMENT_OPTIMAL);
    return true;
}

bool chainShaderReads(QRhi *rhi, QRhiCommandBuffer *cb)
{
    if (!rhi || !cb || rhi->backend() != QRhi::Vulkan)
        return false;
    const auto *handles = static_cast<const QRhiVulkanNativeHandles *>(rhi->nativeHandles());
    if (!handles || !handles->inst || !handles->dev)
        return false;
    QVulkanDeviceFunctions *df = handles->inst->deviceFunctions(handles->dev);
    if (!df)
        return false;
    cb->beginExternal();
    const auto *cbHandles = static_cast<const QRhiVulkanCommandBufferNativeHandles *>(cb->nativeHandles());
    const bool recorded = cbHandles && cbHandles->commandBuffer;
    if (recorded) {
        // An execution dependency only (a read needs no availability): every earlier vertex and fragment shader read
        // before every later stage, so QRhi's next barrier on those textures (its first scope the earlier stage alone)
        // chains after this one.
        df->vkCmdPipelineBarrier(cbHandles->commandBuffer,
                                 VK_PIPELINE_STAGE_VERTEX_SHADER_BIT | VK_PIPELINE_STAGE_FRAGMENT_SHADER_BIT,
                                 VK_PIPELINE_STAGE_ALL_COMMANDS_BIT, 0, 0, nullptr, 0, nullptr, 0, nullptr);
    }
    cb->endExternal();
    return recorded;
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
