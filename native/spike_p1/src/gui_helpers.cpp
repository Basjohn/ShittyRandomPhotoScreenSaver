#include "gui_helpers.h"

#include <rhi/qrhi.h>
#include <rhi/qrhi_platform.h>

#include <QtGui/QVulkanInstance>
#include <QtGui/QWindow>

namespace srpss_spike {

bool attachVulkanInstance(QWindow *window, QString *error)
{
    static QVulkanInstance *instance = nullptr;
    if (!window) {
        *error = QStringLiteral("no window");
        return false;
    }
    if (!instance) {
        instance = new QVulkanInstance;
        instance->setExtensions(QRhiVulkanInitParams::preferredInstanceExtensions());
        if (!instance->create()) {
            *error = QStringLiteral("QVulkanInstance::create failed (VkResult %1)")
                         .arg(int(instance->errorCode()));
            delete instance;
            instance = nullptr;
            return false;
        }
    }
    window->setVulkanInstance(instance);
    return true;
}

bool createOffscreenTarget(QRhi *rhi, int width, int height, OffscreenTarget *out, QString *error,
                           bool preserveColor)
{
    out->texture = rhi->newTexture(QRhiTexture::RGBA8, QSize(width, height), 1,
                                   QRhiTexture::RenderTarget | QRhiTexture::UsedAsTransferSource);
    out->texture->setName(QByteArrayLiteral("spike offscreen target"));
    if (!out->texture->create()) {
        *error = QStringLiteral("texture create failed");
        destroyOffscreenTarget(out);
        return false;
    }
    QRhiTextureRenderTarget::Flags flags;
    if (preserveColor)
        flags |= QRhiTextureRenderTarget::PreserveColorContents;
    out->renderTarget = rhi->newTextureRenderTarget({ QRhiColorAttachment(out->texture) }, flags);
    out->renderTarget->setName(QByteArrayLiteral("spike offscreen target"));
    out->renderPass = out->renderTarget->newCompatibleRenderPassDescriptor();
    out->renderTarget->setRenderPassDescriptor(out->renderPass);
    if (!out->renderTarget->create()) {
        *error = QStringLiteral("render target create failed");
        destroyOffscreenTarget(out);
        return false;
    }
    return true;
}

void destroyOffscreenTarget(OffscreenTarget *target)
{
    delete target->renderTarget;
    delete target->renderPass;
    delete target->texture;
    *target = OffscreenTarget();
}

} // namespace srpss_spike
