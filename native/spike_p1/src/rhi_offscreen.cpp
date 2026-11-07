#define PY_SSIZE_T_CLEAN
#include <Python.h>

#include "rhi_offscreen.h"

#include "image_stats.h"
#include "quadfield.h"

#include <rhi/qrhi_platform.h>

#include <QtCore/QElapsedTimer>
#include <QtCore/QThread>
#include <QtGui/QOffscreenSurface>
#include <QtGui/QVulkanInstance>

#include <memory>

namespace srpss_spike {

namespace {

class RenderThread final : public QThread
{
public:
    explicit RenderThread(OffscreenRun *run, void (OffscreenRun::*entry)())
        : m_run(run), m_entry(entry)
    {
    }

protected:
    void run() override { (m_run->*m_entry)(); }

private:
    OffscreenRun *m_run;
    void (OffscreenRun::*m_entry)();
};

} // namespace

QRhi::Implementation backendFromName(const QString &name, bool *ok)
{
    const QString n = name.toLower();
    *ok = true;
    if (n == QLatin1String("d3d11"))
        return QRhi::D3D11;
    if (n == QLatin1String("d3d12"))
        return QRhi::D3D12;
    if (n == QLatin1String("vulkan"))
        return QRhi::Vulkan;
    if (n == QLatin1String("opengl"))
        return QRhi::OpenGLES2;
    if (n == QLatin1String("null"))
        return QRhi::Null;
    *ok = false;
    return QRhi::Null;
}

OffscreenRun::OffscreenRun(const OffscreenRequest &request)
    : m_request(request)
{
}

OffscreenRun::~OffscreenRun()
{
    wait();
    delete m_thread;
    delete m_vulkan;
    delete m_glFallback;
}

bool OffscreenRun::start()
{
    m_result.callerThread = quintptr(QThread::currentThreadId());
    // Platform objects belong to the GUI thread; only the QRhi lives on the render thread.
    if (m_request.backend == QRhi::Vulkan) {
        m_vulkan = new QVulkanInstance;
        m_vulkan->setExtensions(QRhiVulkanInitParams::preferredInstanceExtensions());
        if (!m_vulkan->create()) {
            m_result.error = QStringLiteral("QVulkanInstance::create failed (VkResult %1)")
                                 .arg(int(m_vulkan->errorCode()));
            return false;
        }
    } else if (m_request.backend == QRhi::OpenGLES2) {
        m_glFallback = QRhiGles2InitParams::newFallbackSurface();
    }
    m_thread = new RenderThread(this, &OffscreenRun::renderThreadMain);
    m_thread->setObjectName(QStringLiteral("srpss-spike-render"));
    m_thread->start();
    return true;
}

void OffscreenRun::wait()
{
    if (m_thread)
        m_thread->wait();
}

bool OffscreenRun::isFinished() const
{
    return !m_thread || m_thread->isFinished();
}

void OffscreenRun::renderThreadMain()
{
    OffscreenResult &res = m_result;
    res.renderThread = quintptr(QThread::currentThreadId());
    const int w = m_request.width;
    const int h = m_request.height;

    std::unique_ptr<QRhi> rhi;
    switch (m_request.backend) {
    case QRhi::D3D11: {
        QRhiD3D11InitParams params;
        rhi.reset(QRhi::create(QRhi::D3D11, &params));
        break;
    }
    case QRhi::D3D12: {
        QRhiD3D12InitParams params;
        rhi.reset(QRhi::create(QRhi::D3D12, &params));
        break;
    }
    case QRhi::Vulkan: {
        QRhiVulkanInitParams params;
        params.inst = m_vulkan;
        rhi.reset(QRhi::create(QRhi::Vulkan, &params));
        break;
    }
    case QRhi::OpenGLES2: {
        QRhiGles2InitParams params;
        params.fallbackSurface = m_glFallback;
        rhi.reset(QRhi::create(QRhi::OpenGLES2, &params));
        break;
    }
    default: {
        QRhiNullInitParams params;
        rhi.reset(QRhi::create(QRhi::Null, &params));
        break;
    }
    }
    if (!rhi) {
        res.error = QStringLiteral("QRhi::create failed");
        return;
    }
    res.backendName = QString::fromLatin1(rhi->backendName());
    res.deviceName = QString::fromUtf8(rhi->driverInfo().deviceName);

    {
        std::unique_ptr<QRhiTexture> texture(rhi->newTexture(
            QRhiTexture::RGBA8, QSize(w, h), 1,
            QRhiTexture::RenderTarget | QRhiTexture::UsedAsTransferSource));
        if (!texture->create()) {
            res.error = QStringLiteral("texture create failed");
            return;
        }
        std::unique_ptr<QRhiTextureRenderTarget> target(
            rhi->newTextureRenderTarget({ QRhiColorAttachment(texture.get()) }));
        std::unique_ptr<QRhiRenderPassDescriptor> pass(target->newCompatibleRenderPassDescriptor());
        target->setRenderPassDescriptor(pass.get());
        if (!target->create()) {
            res.error = QStringLiteral("render target create failed");
            return;
        }

        QuadField field(m_request.instances);
        QRhiReadbackResult readback;
        const QMatrix4x4 unitToClip = unitToClipForRhi(rhi.get());
        const float aspect = float(w) / float(h);
        QElapsedTimer timer;
        for (int i = 0; i < m_request.frames; ++i) {
            timer.start();
            if (m_request.gilPerFrame) {
                // What a Python render() override costs: the render thread must win the GIL.
                PyGILState_STATE gil = PyGILState_Ensure();
                PyGILState_Release(gil);
            } else if (PyGILState_GetThisThreadState() != nullptr) {
                ++res.framesWithPythonThreadState;
            }
            QRhiCommandBuffer *cb = nullptr;
            if (rhi->beginOffscreenFrame(&cb) != QRhi::FrameOpSuccess) {
                res.error = QStringLiteral("beginOffscreenFrame failed");
                break;
            }
            QRhiResourceUpdateBatch *updates = rhi->nextResourceUpdateBatch();
            if (!field.ensure(rhi.get(), pass.get(), 1, updates)) {
                updates->release();
                rhi->endOffscreenFrame();
                res.error = QStringLiteral("pipeline create failed");
                break;
            }
            field.update(updates, unitToClip, float(i) / 60.0f, aspect);
            cb->beginPass(target.get(), QColor::fromRgbF(0.06f, 0.07f, 0.10f, 1.0f),
                          { 1.0f, 0 }, updates);
            field.record(cb, QRhiViewport(0, 0, float(w), float(h)));
            QRhiResourceUpdateBatch *readbackBatch = nullptr;
            if (i == m_request.frames - 1) {
                readbackBatch = rhi->nextResourceUpdateBatch();
                readbackBatch->readBackTexture(QRhiReadbackDescription(texture.get()), &readback);
            }
            cb->endPass(readbackBatch);
            rhi->endOffscreenFrame(); // offscreen frames complete synchronously
            res.frameMs << double(timer.nsecsElapsed()) / 1.0e6;
        }
        field.release();

        if (res.error.isEmpty()) {
            const QImage image = imageFromReadback(readback.data, readback.pixelSize,
                                                   rhi->isYUpInFramebuffer());
            const ImageStats stats = imageStats(image);
            res.litPixels = stats.litPixels;
            res.pixelChecksum = stats.checksum;
            if (image.isNull())
                res.error = QStringLiteral("readback returned no pixels");
            else if (!m_request.pngPath.isEmpty() && !image.save(m_request.pngPath, "PNG"))
                res.error = QStringLiteral("PNG save failed: ") + m_request.pngPath;
        }
    }
    rhi.reset();
    res.ok = res.error.isEmpty();
}

} // namespace srpss_spike
