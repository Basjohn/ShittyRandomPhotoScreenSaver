#include "quick_offscreen.h"

#include "image_stats.h"

#include <rhi/qrhi.h>

#include <QtCore/QElapsedTimer>
#include <QtCore/QMetaObject>
#include <QtCore/QObject>
#include <QtCore/QThread>
#include <QtQuick/QQuickRenderControl>
#include <QtQuick/QQuickRenderTarget>
#include <QtQuick/QQuickWindow>

#include <functional>

namespace srpss_spike {

// Runs work on the render thread while the GUI thread waits: the GUI thread is
// blocked during sync exactly as with Qt's threaded render loop.
class RenderThreadHost
{
public:
    explicit RenderThreadHost(bool threaded) : m_threaded(threaded)
    {
        if (!m_threaded)
            return;
        m_thread.reset(new QThread);
        m_thread->setObjectName(QStringLiteral("srpss-spike-quick-render"));
        m_context = new QObject;
        m_context->moveToThread(m_thread.get());
        m_thread->start();
    }

    ~RenderThreadHost()
    {
        if (!m_threaded)
            return;
        QObject *context = m_context;
        QMetaObject::invokeMethod(context, [context]() { delete context; },
                                  Qt::BlockingQueuedConnection);
        m_thread->quit();
        m_thread->wait();
    }

    QThread *thread() const { return m_thread.get(); }

    void runBlocking(const std::function<void()> &work)
    {
        if (!m_threaded) {
            work();
            return;
        }
        QMetaObject::invokeMethod(m_context, work, Qt::BlockingQueuedConnection);
    }

private:
    bool m_threaded;
    std::unique_ptr<QThread> m_thread;
    QObject *m_context = nullptr;
};

QuickOffscreenSession::QuickOffscreenSession(QQuickRenderControl *control, QQuickWindow *window,
                                             int width, int height, bool threaded)
    : m_control(control), m_window(window), m_width(width), m_height(height),
      m_host(new RenderThreadHost(threaded))
{
    m_guiThread = quintptr(QThread::currentThreadId());
    if (threaded)
        m_control->prepareThread(m_host->thread());
}

QuickOffscreenSession::~QuickOffscreenSession()
{
    end();
}

bool QuickOffscreenSession::begin()
{
    if (m_window->graphicsApi() == QSGRendererInterface::Vulkan && !m_window->vulkanInstance()) {
        if (!attachVulkanInstance(m_window, &m_error))
            return false;
    }
    m_host->runBlocking([this]() {
        m_renderThread = quintptr(QThread::currentThreadId());
        if (!m_control->initialize()) {
            m_error = QStringLiteral("QQuickRenderControl::initialize failed");
            return;
        }
        QRhi *rhi = m_control->rhi();
        m_backendName = QString::fromLatin1(rhi->backendName());
        m_deviceName = QString::fromUtf8(rhi->driverInfo().deviceName);
        if (!createOffscreenTarget(rhi, m_width, m_height, &m_target, &m_error))
            return;
        m_window->setRenderTarget(QQuickRenderTarget::fromRhiRenderTarget(m_target.renderTarget));
        m_begun = true;
    });
    return m_begun;
}

QuickFramesResult QuickOffscreenSession::frames(QObject *animated, int count, const QString &pngPath)
{
    QuickFramesResult res;
    if (!m_begun) {
        res.error = QStringLiteral("session not begun");
        return res;
    }
    QRhiReadbackResult readback;
    bool yUp = false;
    QElapsedTimer timer;
    for (int i = 0; i < count; ++i) {
        timer.start();
        if (animated)
            animated->setProperty("time", double(m_frameIndex++) / 60.0);
        m_control->polishItems(); // GUI thread
        const bool last = i == count - 1;
        m_host->runBlocking([&]() {
            m_control->beginFrame();
            m_control->sync(); // GUI thread is blocked here
            m_control->render();
            if (last && !pngPath.isEmpty()) {
                QRhi *rhi = m_control->rhi();
                yUp = rhi->isYUpInFramebuffer();
                QRhiResourceUpdateBatch *batch = rhi->nextResourceUpdateBatch();
                batch->readBackTexture(QRhiReadbackDescription(m_target.texture), &readback);
                m_control->commandBuffer()->resourceUpdate(batch);
            }
            m_control->endFrame(); // offscreen frame: completes synchronously
        });
        res.frameMs << double(timer.nsecsElapsed()) / 1.0e6;
    }
    if (!pngPath.isEmpty()) {
        const QImage image = imageFromReadback(readback.data, readback.pixelSize, yUp);
        const ImageStats stats = imageStats(image);
        res.litPixels = stats.litPixels;
        res.pixelChecksum = stats.checksum;
        if (image.isNull())
            res.error = QStringLiteral("readback returned no pixels");
        else if (!image.save(pngPath, "PNG"))
            res.error = QStringLiteral("PNG save failed: ") + pngPath;
    }
    res.ok = res.error.isEmpty();
    return res;
}

void QuickOffscreenSession::end()
{
    if (!m_host)
        return;
    m_host->runBlocking([this]() {
        if (m_begun)
            m_window->setRenderTarget(QQuickRenderTarget());
        destroyOffscreenTarget(&m_target);
        m_control->invalidate();
    });
    m_begun = false;
    m_host.reset();
}

} // namespace srpss_spike
