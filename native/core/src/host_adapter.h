// The host adapter (D5.1): the one seam where the core meets Qt Quick's frame. A host gives the core a device, a place to
// record this frame's commands and the frame edge (HostFrameSource, frame_driver.h); nothing else in the core names a
// QQuickWindow. Two hosts behind one interface (Host):
//
// - WindowHost: a Qt Quick window the product shows (the saver, MC and both SMP hosts), rendered by Qt's render loop. On
//   Vulkan the window gets the process instance and a device of the module's before it is first shown (D6), and the
//   device lives until the window object is destroyed (facts A7); on the other backends Qt's device is used.
// - HiddenHost: a Qt Quick window driven by a QQuickRenderControl on the core's own render thread (parity, capture and
//   release-media tools, the Studio's preview), never shown. The host owns the render control and its window, so it
//   can tear down in the decided order (the frame driver, Qt's scene graph and QRhi, the window, then the device); a
//   caller hands it the Qt Quick content item to render.
//
// Attaching connects a new frame driver to the host's window (beforeRendering, a C++ direct connection); detaching stops
// it and releases its resources on the render thread; a host can be attached again. GUI thread only, except where said.
#pragma once

#include "frame_driver.h"

#include <QtCore/QJsonObject>
#include <QtCore/QString>

#include <memory>

class QObject;
class QQuickItem;
class QQuickWindow;

namespace srpss_core {

enum class HostKind {
    Window, // the Qt Quick window of the saver, MC and both SMP hosts
    Hidden, // the hidden host (QQuickRenderControl: parity, capture and release-media tools, the Studio's preview)
};

// Parses "window" or "hidden"; false for anything else.
bool parseHostKind(const char *text, HostKind *kind);

class Host
{
public:
    virtual ~Host();
    virtual HostKind kind() const = 0;

    // A new frame driver connected to the host's window; false with `error` when attached already or the window is
    // gone.
    virtual bool attach(QString *error) = 0;
    // The driver stops recording and releases its resources on the render thread.
    virtual bool detach(QString *error) = 0;
    bool attached() const { return m_driver != nullptr; }

    // The probe pass (probe_pass.h) on the attached driver: from the next frame; null config removes it.
    bool setProbe(const ProbeConfig *config, QString *error);
    bool requestReadback(QString *error);
    bool takeProbeResult(QJsonObject *facts, QByteArray *rgba, int *width, int *height, qint64 *frame);

    virtual QJsonObject stateJson() const;

protected:
    std::shared_ptr<FrameDriver> m_driver;     // the current attachment, or null
    std::shared_ptr<FrameDriver> m_lastDriver; // the one detached last (its record stays readable)
    int m_attachments = 0;
};

class WindowHost final : public Host
{
public:
    // Null with `error` when `object` is not a QQuickWindow, or on Vulkan when its scene graph was initialised on a
    // device that is not the module's (a window is hosted before it is first shown, D6).
    static std::unique_ptr<WindowHost> create(QObject *object, QString *error);
    ~WindowHost() override;

    HostKind kind() const override { return HostKind::Window; }
    bool attach(QString *error) override;
    bool detach(QString *error) override;
    QJsonObject stateJson() const override;

    struct WindowRecord;

private:
    explicit WindowHost(std::shared_ptr<WindowRecord> record);
    std::shared_ptr<WindowRecord> m_record;
    std::shared_ptr<const HostFrameSource> m_source;
};

class HiddenHost final : public Host
{
public:
    // threaded: the render control's work runs on the core's own render thread (the product's form); false runs it on
    // the calling (GUI) thread, the thread probe's negative control.
    static std::unique_ptr<HiddenHost> create(int width, int height, bool threaded, QString *error);
    ~HiddenHost() override;

    HostKind kind() const override { return HostKind::Hidden; }
    bool attach(QString *error) override;
    bool detach(QString *error) override;
    QJsonObject stateJson() const override;

    // The Qt Quick item it renders (parented to the window's content item, sized to it; never owned or deleted).
    bool setContent(QQuickItem *item, QString *error);
    // `count` frames: polish on the calling thread, then begin, sync, render and end on the render thread (beforeRendering
    // drives the frame driver there). Call with the GIL released.
    bool frames(int count, QString *error);
    // Detaches, invalidates Qt's scene graph on the render thread, deletes the render control (Qt's QRhi) and the window,
    // then destroys the device (Vulkan). Call with the GIL released. Idempotent.
    QJsonObject close();

    class RenderThread;
    struct State;

private:
    HiddenHost();
    std::unique_ptr<State> m_state;
};

} // namespace srpss_core
