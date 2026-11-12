// P1 spike, part B driver: renders a Python-built Qt Quick scene offscreen
// through QQuickRenderControl. With `threaded`, sync and render run on a
// dedicated render QThread while the GUI thread blocks during sync, which is
// the shape of Qt's threaded render loop. No window is ever shown.
#pragma once

#include "gui_helpers.h"

#include <QtCore/QList>
#include <QtCore/QString>

#include <memory>

class QObject;
class QQuickRenderControl;
class QQuickWindow;

namespace srpss_spike {

class RenderThreadHost;

struct QuickFramesResult
{
    bool ok = false;
    QString error;
    QList<double> frameMs;
    int litPixels = 0;
    quint64 pixelChecksum = 0;
};

// One render-control session: begin() once, frames() any number of times
// (each call with the GIL released), end() once. GUI thread only.
class QuickOffscreenSession
{
public:
    QuickOffscreenSession(QQuickRenderControl *control, QQuickWindow *window, int width,
                          int height, bool threaded);
    ~QuickOffscreenSession();

    bool begin();
    QuickFramesResult frames(QObject *animated, int count, const QString &pngPath);
    // N0.6: a new offscreen target of this size replaces the old one (the caller resizes the window and the
    // scene on the GUI thread before the next frames()).
    bool resize(int width, int height);
    void end();

    QString error() const { return m_error; }
    QString backendName() const { return m_backendName; }
    QString deviceName() const { return m_deviceName; }
    quintptr guiThread() const { return m_guiThread; }
    quintptr renderThread() const { return m_renderThread; }
    // Vulkan only (0 / -1 otherwise): the session QRhi's VkDevice and graphics queue (family, index).
    quint64 vkDevice() const { return m_vkDevice; }
    int vkQueueFamily() const { return m_vkQueueFamily; }
    int vkQueueIndex() const { return m_vkQueueIndex; }

private:
    QQuickRenderControl *m_control;
    QQuickWindow *m_window;
    int m_width;
    int m_height;
    std::unique_ptr<RenderThreadHost> m_host;
    OffscreenTarget m_target;
    bool m_begun = false;
    int m_frameIndex = 0;
    QString m_error;
    QString m_backendName;
    QString m_deviceName;
    quintptr m_guiThread = 0;
    quintptr m_renderThread = 0;
    quint64 m_vkDevice = 0;
    int m_vkQueueFamily = -1;
    int m_vkQueueIndex = -1;
};

} // namespace srpss_spike
