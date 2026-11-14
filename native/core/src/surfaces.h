// The core's composited surfaces (D5.2; Current_Plan.md item 8b, N2.4). A surface is one target the core draws (a
// card's, or an admitted overflow's) that reaches the window as a scene-graph texture node (composite.h). Its target
// is owned by that node, so it lives and dies on the render thread with Qt's scene graph; the window's frame driver
// records its content on beforeRendering, through the window's surface registry (WindowSurfaces), in dependency order
// after everything it samples.
//
// The target keeps its contents (targets.h rule B), so a surface whose content did not change records nothing: at rest
// the window's frame costs only Qt's own composite draw. On Vulkan it is primed before every pass that loads it (rule
// C): Qt Quick samples it between passes, which leaves it in a shader-read layout.
//
// Content is the harness's pattern pass (N2.4's proof: every texel's own index, or opaque white) unless a mode's content
// is set (SurfaceContent; N2.5's Spectrum, spectrum.h), which then records into the same target.
#pragma once

#include "targets.h"

#include <QtCore/QAtomicInteger>
#include <QtCore/QList>
#include <QtCore/QMutex>
#include <QtCore/QSize>
#include <QtCore/QString>
#include <rhi/qrhi.h> // QRhiTexture::Format in a declaration needs the class (round 5's first compile)

#include <memory>

class QQuickWindow;
class QRhi;
class QRhiCommandBuffer;
class QRhiTexture;

namespace srpss_core {

enum class SurfacePattern {
    TexelIdentity = 0, // r, g: the texel's x and y modulo 256; b: their high nibbles (x in the low four bits)
    White = 1,         // opaque white everywhere: content touching every edge and corner
    Transparent = 2,   // every texel transparent: the surface's own clear of a target a content never wrote (N29 r2 M4;
                       // never a configuration's pattern)
};

bool parseSurfacePattern(const QString &text, SurfacePattern *out);
QString surfacePatternName(SurfacePattern pattern);

// A mode's content of a surface (render thread only): it records its passes into the surface's target, which keeps its
// contents (targets.h rule B: a content that must be cleared clears it with its first draw) and was primed for the
// load (rule C) before record is called.
class SurfaceContent
{
public:
    virtual ~SurfaceContent() = default;
    // Inside the frame, outside any pass, before the surface primes its target: true when the content records nothing
    // now and the target keeps what it holds (a refused frame over a frame of its own, a latched failure: audit N29 M4,
    // M2). The surface is then clean and reports no error.
    virtual bool keepsTarget(QRhi *rhi, ColorTarget &target)
    {
        Q_UNUSED(rhi);
        Q_UNUSED(target);
        return false;
    }
    // Inside the frame, outside any pass.
    virtual bool record(QRhi *rhi, QRhiCommandBuffer *cb, ColorTarget &target, QString *error) = 0;
    // Whether `target` holds a frame the content drew into it (audit N29 round 2, M4): when a content keeps the target
    // or fails while it holds none, the surface clears it to transparent once instead of showing what it holds.
    virtual bool holdsFrame(const ColorTarget &target) const
    {
        Q_UNUSED(target);
        return true;
    }
    // Every QRhi object of the content goes (the surface's release, or the content replaced).
    virtual void release() = 0;
    virtual int liveResources() const = 0;
};

class Surface
{
public:
    Surface();
    ~Surface();
    Surface(const Surface &) = delete;
    Surface &operator=(const Surface &) = delete;

    // Render thread, at sync: the target at this size on this QRhi. A new size recreates the same QRhi objects (Qt's
    // QQuickRhiItem pattern, so Qt Quick's bindings follow the texture's generation); either change makes it dirty.
    // `format`: the target's texel format (RGBA8; RGBA16F for content whose translucent pixels must not be rounded to
    // 8 bits before the composite blends them, N2.5): a change recreates every QRhi object of the surface.
    bool ensureTarget(QRhi *rhi, const QSize &pixels, QString *error, QRhiTexture::Format format = QRhiTexture::RGBA8);
    // Render thread, at sync: the content; a change makes it dirty.
    void setPattern(SurfacePattern pattern);
    // Render thread, at sync: a mode's content in place of the pattern (null: the pattern again); the one it replaces
    // releases its QRhi objects now. A change makes it dirty.
    void setContent(const std::shared_ptr<SurfaceContent> &content);
    const std::shared_ptr<SurfaceContent> &content() const { return m_content; }
    // Render thread, at sync: the content's input changed (a frame, the card), so the next edge records.
    void markDirty() { m_dirty.storeRelease(1); }
    bool dirty() const { return m_dirty.loadAcquire() != 0; }

    // Render thread, on beforeRendering (inside the frame, outside any pass): records the content pass when dirty,
    // nothing otherwise (`recorded` says which).
    bool record(QRhi *rhi, QRhiCommandBuffer *cb, bool *recorded, QString *error);

    QRhiTexture *texture() const;
    QSize pixelSize() const;
    qint64 passesRecorded() const { return m_passes.loadRelaxed(); }
    qint64 clears() const { return m_clears.loadRelaxed(); } // the surface's own clears of an unwritten target (M4)
    int liveResources() const { return m_live.loadRelaxed(); }
    QString lastPrime() const;

    // Render thread: every QRhi object goes (the node's destruction; Qt's scene graph invalidation deletes the node
    // while its QRhi still exists).
    void release();

    // Any thread: the surfaces alive in the process and the QRhi objects they hold (lifecycle proofs).
    static int liveSurfaces();
    static int liveResourcesTotal();

private:
    struct Resources;
    bool ensurePass(QString *error);
    bool recordPattern(QRhi *rhi, QRhiCommandBuffer *cb, SurfacePattern pattern, bool *recorded, QString *error);
    bool clearTarget(QRhi *rhi, QRhiCommandBuffer *cb, bool *recorded, QString *error);
    void setLive(int count);

    std::unique_ptr<Resources> m_res;
    std::shared_ptr<SurfaceContent> m_content;
    SurfacePattern m_pattern = SurfacePattern::TexelIdentity;
    bool m_targetClear = false;            // render thread: the target is known to be transparent (cleared by a draw)
    QAtomicInteger<int> m_dirty { 1 };
    QAtomicInteger<qint64> m_passes { 0 };
    QAtomicInteger<qint64> m_clears { 0 };
    QAtomicInteger<int> m_live { 0 };
    mutable QMutex m_mutex; // guards m_lastPrime (read from the GUI thread)
    QString m_lastPrime;
};

// The surfaces of one Qt Quick window and the frame drivers connected to it. Entries are made on the GUI thread (a
// composite item entering the window, a driver connecting); nodes add and remove their surfaces on the render thread;
// the driver reads the dirty ones on its frame edge.
class WindowSurfaces
{
public:
    // GUI thread: the window's registry (a new one when the window at this address was destroyed).
    static std::shared_ptr<WindowSurfaces> forWindow(QQuickWindow *window);

    void driverAttached();
    void driverDetached();
    int drivers() const;

    void add(const std::shared_ptr<Surface> &surface);
    void remove(const Surface *surface);
    int count() const;
    // The surfaces with content to record this frame (empty at rest).
    QList<std::shared_ptr<Surface>> dirtySurfaces() const;

private:
    mutable QMutex m_mutex;
    QList<std::shared_ptr<Surface>> m_surfaces;
    int m_drivers = 0;
};

} // namespace srpss_core
