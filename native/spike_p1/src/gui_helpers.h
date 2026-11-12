// P1 spike: helpers that need only QtGui (buildable without the Qt Quick SDK).
#pragma once

#include <QtCore/QString>

class QRhi;
class QRhiRenderPassDescriptor;
class QRhiTexture;
class QRhiTextureRenderTarget;
class QWindow;

namespace srpss_spike {

// Gives a never-shown window (a QQuickWindow is a QWindow) a QVulkanInstance.
// PySide6 6.11 exposes neither QVulkanInstance nor setVulkanInstance. The
// instance lives until process exit. GUI thread only.
bool attachVulkanInstance(QWindow *window, QString *error);

// A colour texture + render target on someone else's QRhi (for example the
// one QQuickRenderControl created), to hand to QQuickRenderTarget.
struct OffscreenTarget
{
    QRhiTexture *texture = nullptr;
    QRhiRenderPassDescriptor *renderPass = nullptr;
    QRhiTextureRenderTarget *renderTarget = nullptr;
};

// preserveColor (N0.7, validation): QRhiTextureRenderTarget::PreserveColorContents. Without it QRhiVulkan's
// offscreen render pass begins with initialLayout UNDEFINED and has no external subpass dependency
// (createOffscreenRenderPass, Qt 6.12), so a target rendered every frame shows SYNC-HAZARD-WRITE-AFTER-WRITE at
// vkCmdBeginRenderPass under synchronisation validation; with it the pass keeps COLOR_ATTACHMENT_OPTIMAL and the
// resource tracker's barrier orders the frames. The scene covers the whole target, so the pixels are the same.
bool createOffscreenTarget(QRhi *rhi, int width, int height, OffscreenTarget *out, QString *error,
                           bool preserveColor = false);
void destroyOffscreenTarget(OffscreenTarget *target);

} // namespace srpss_spike
