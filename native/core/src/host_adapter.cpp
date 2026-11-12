#include "host_adapter.h"

#include <QtCore/QObject>
#include <QtQuick/QQuickWindow>

#include <cstring>

namespace srpss_core {

bool parseHostKind(const char *text, HostKind *kind)
{
    if (!text || !kind)
        return false;
    if (std::strcmp(text, "window") == 0) {
        *kind = HostKind::Window;
        return true;
    }
    if (std::strcmp(text, "hidden") == 0) {
        *kind = HostKind::Hidden;
        return true;
    }
    return false;
}

bool attachHost(HostKind kind, QObject *object)
{
    Q_UNUSED(kind);
    // Both hosts are QQuickWindows (the hidden host's window is driven by a QQuickRenderControl). No frame driver
    // yet (N2.2): nothing is connected and nothing is kept.
    return qobject_cast<QQuickWindow *>(object) != nullptr;
}

} // namespace srpss_core
