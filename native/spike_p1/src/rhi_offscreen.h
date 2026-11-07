// P1 spike: a standalone QRhi (no Qt Quick) that renders the QuadField
// offscreen on a native QThread and reads the last frame back to a PNG.
#pragma once

#include <rhi/qrhi.h>

#include <QtCore/QList>
#include <QtCore/QString>

class QOffscreenSurface;
class QThread;
class QVulkanInstance;

namespace srpss_spike {

struct OffscreenRequest
{
    QRhi::Implementation backend = QRhi::D3D11;
    int width = 640;
    int height = 360;
    int frames = 120;
    int instances = 4096;
    QString pngPath;
    // Negative control: take and drop the GIL once per frame on the render
    // thread, the way a Python render() override does today.
    bool gilPerFrame = false;
};

struct OffscreenResult
{
    bool ok = false;
    QString error;
    QString backendName;
    QString deviceName;
    QList<double> frameMs;
    quintptr renderThread = 0;
    quintptr callerThread = 0;
    int framesWithPythonThreadState = 0;
    int litPixels = 0;
    quint64 pixelChecksum = 0;
};

// One run: prepared on the calling (GUI) thread, rendered on its own QThread.
class OffscreenRun
{
public:
    explicit OffscreenRun(const OffscreenRequest &request);
    ~OffscreenRun();

    bool start();          // GUI thread
    void wait();           // any thread; call with the GIL released
    bool isFinished() const;
    const OffscreenResult &result() const { return m_result; }
    OffscreenResult &result() { return m_result; }

    void renderThreadMain(); // runs on the render thread only

private:

    OffscreenRequest m_request;
    OffscreenResult m_result;
    QThread *m_thread = nullptr;
    QVulkanInstance *m_vulkan = nullptr;
    QOffscreenSurface *m_glFallback = nullptr;
};

QRhi::Implementation backendFromName(const QString &name, bool *ok);

} // namespace srpss_spike
