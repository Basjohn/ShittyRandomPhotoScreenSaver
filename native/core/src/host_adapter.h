// The host adapter (D5.1): the one seam where the core meets Qt Quick's frame. A host gives the core a device, a
// place to record this frame's commands and the frame edge; nothing else in the core names a QQuickWindow.
//
// N2.1 builds the entry only: it checks that it was handed a Qt Quick window and does nothing else. The frame driver
// connected on beforeRendering (D5.2, N2.2) is built behind this entry.
#pragma once

class QObject;

namespace srpss_core {

enum class HostKind {
    Window, // the Qt Quick window of the saver, MC and both SMP hosts
    Hidden, // the hidden host (QQuickRenderControl: parity, capture and release-media tools, the Studio's preview)
};

// Parses "window" or "hidden"; false for anything else.
bool parseHostKind(const char *text, HostKind *kind);

// The no-op entry: true when `object` is a QQuickWindow (the only thing a host hands over), false otherwise.
bool attachHost(HostKind kind, QObject *object);

} // namespace srpss_core
