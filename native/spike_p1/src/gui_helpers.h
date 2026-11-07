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

bool createOffscreenTarget(QRhi *rhi, int width, int height, OffscreenTarget *out, QString *error);
void destroyOffscreenTarget(OffscreenTarget *target);

} // namespace srpss_spike
