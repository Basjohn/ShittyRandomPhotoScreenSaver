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
#include <QtCore/QPoint>
#include <QtCore/QSize>
#include <QtCore/QString>
#include <rhi/qrhi.h> // QRhiTexture::Format in a declaration needs the class (round 5's first compile)

#include <memory>

class QQuickWindow;
class QRhi;
class QRhiCommandBuffer;
class QRhiTexture;

namespace srpss_core {

class BackdropPyramid;
class JobService;

enum class SurfacePattern {
    TexelIdentity = 0, // r, g: the texel's x and y modulo 256; b: their high nibbles (x in the low four bits)
    White = 1,         // opaque white everywhere: content touching every edge and corner
    Transparent = 2,   // every texel transparent: the surface's own clear of a target a content never wrote (N29 r2 M4;
                       // never a configuration's pattern)
};

bool parseSurfacePattern(const QString &text, SurfacePattern *out);
QString surfacePatternName(SurfacePattern pattern);

// Where a surface lies in the frame's dependency order (D5.2: background layer, backdrop pyramid, Visualizer scene,
// overlays). The frame driver records the window's background-layer surfaces before every other (N5.7a: what the
// backdrop pyramid, N5.7b, will be built from must be drawn first in the frame).
enum class SurfaceLayer {
    Content = 0,    // a card's content (Spectrum, a generic mode)
    Background = 1, // the display's background layer (the photo; later its transition)
};

bool parseSurfaceLayer(const QString &text, SurfaceLayer *out);
QString surfaceLayerName(SurfaceLayer layer);

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
    // After a record that returned true: whether it recorded no pass and the target keeps what it holds (N5.7a: a
    // still whose drawn inputs did not change; its new image handed to its job). The surface then counts no pass.
    virtual bool keptTargetLastRecord() const { return false; }
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
    // Render thread, at sync: the surface's place in the frame's order (N5.7a). Any thread reads it.
    void setLayer(SurfaceLayer layer) { m_layer.storeRelease(int(layer)); }
    SurfaceLayer layer() const { return SurfaceLayer(m_layer.loadAcquire()); }
    // Passes a content recorded whose target then kept its frame (N5.7a, keptTargetLastRecord): not counted as passes.
    qint64 keptRecords() const { return m_kept.loadRelaxed(); }
    // N5.7b, render thread: a process-unique number for the frame of its content the target holds, new at every content
    // pass that drew one; 0 while the target holds none (never written, cleared, released or resized). The backdrop
    // pyramid builds when it differs from the one it built from (backdrop.h).
    quint64 drawnGeneration() const { return m_drawnGeneration; }
    // N5.7b, render thread, at sync: where the target lies in its window, in the window framebuffer's device pixels
    // (rows top-down: the item's scene origin times the window's ratio, on the pixel grid composite.vert snaps it to),
    // and that framebuffer's size. The backdrop's seed reads the layer where it lies in the window.
    void setPlacement(const QPoint &origin, const QSize &window)
    {
        m_origin = origin;
        m_windowPixels = window;
    }
    QPoint origin() const { return m_origin; }
    QSize windowPixels() const { return m_windowPixels; }

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
    quint64 m_drawnGeneration = 0;         // render thread (N5.7b): the content's frame the target holds, 0 for none
    QPoint m_origin;                       // render thread (N5.7b): the target's place in its window
    QSize m_windowPixels;
    QAtomicInteger<int> m_dirty { 1 };
    QAtomicInteger<int> m_layer { 0 };     // SurfaceLayer
    QAtomicInteger<qint64> m_passes { 0 };
    QAtomicInteger<qint64> m_kept { 0 };
    QAtomicInteger<qint64> m_clears { 0 };
    QAtomicInteger<int> m_live { 0 };
    mutable QMutex m_mutex; // guards m_lastPrime (read from the GUI thread)
    QString m_lastPrime;
};

// The surfaces of one Qt Quick window and the frame drivers connected to it. Entries are made on the GUI thread (a
// composite item entering the window, a driver connecting); nodes add and remove their surfaces on the render thread;
// the driver reads the dirty ones on its frame edge.
//
// The window's retire list (N3.8, D9 as built point 6): a job's output that this window's frames sampled is released
// only once those frames completed. A content hands it over stamped with the frame edge of its last possible use; the
// frame driver counts the window's edges and releases an entry at the edge `stamp + FramesInFlight` (Qt's beginFrame of
// that frame waited for the stamped one), or every entry at once after QRhi::finish() outside a frame. An entry still
// here when the registry goes (no driver released it) is left to its service, which destroys it when it stops, after
// Qt's QRhi is gone. At rest the list is empty and the edge reads one atomic.
class WindowSurfaces
{
public:
    WindowSurfaces() = default;
    ~WindowSurfaces();
    WindowSurfaces(const WindowSurfaces &) = delete;
    WindowSurfaces &operator=(const WindowSurfaces &) = delete;

    // GUI thread: the window's registry (a new one when the window at this address was destroyed).
    static std::shared_ptr<WindowSurfaces> forWindow(QQuickWindow *window);

    // The frame edges (render thread): one per rendered frame of the window, whatever number of frame drivers is
    // connected to it (audit N38 M1: a second driver, or one detached and not yet released, counted the frame again and
    // released a retired image a frame early). The first driver's beforeRendering in a frame counts it; the window's
    // afterRendering (one connection per registry, made by forWindow) opens the next frame's count. A driver connected
    // in the middle of a frame whose count is taken counts from the next one (never twice; at worst one frame late).
    qint64 noteEdge()
    {
        if (m_frameCounted.testAndSetOrdered(0, 1))
            return m_edges.fetchAndAddOrdered(1) + 1;
        return m_edges.loadAcquire();
    }
    void frameRendered() { m_frameCounted.storeRelease(0); }
    qint64 edges() const { return m_edges.loadAcquire(); }
    // Render thread: a job's output this window's frames may have sampled up to the current edge. Asks the window for a
    // frame (audit N38 M2): the frames its release waits for are rendered even when nothing else changes.
    void retire(const std::shared_ptr<JobService> &service, quint64 output);
    bool retiring() const { return m_retiring.loadAcquire() > 0; }
    // Render thread, at the frame edge `edge`: the entries whose frames completed go to their services; while any is
    // left the window is asked for the next frame (M2: one request per frame until the list is empty, an edge each,
    // never a timer; at rest the list is empty and nothing is asked).
    int releaseRetired(qint64 edge, int framesInFlight);
    // Frames the retire list asked the window for (M2's proof).
    qint64 frameRequests() const { return m_frameRequests.loadRelaxed(); }
    // Render thread, outside a frame, after QRhi::finish(): every entry goes.
    int releaseAllRetired();
    // Any thread: entries waiting in every window (the destruction barrier's reading), and the ones left to their
    // services when a registry went.
    static int retiringTotal();
    static qint64 leftToServicesTotal();

    void driverAttached();
    void driverDetached();
    int drivers() const;

    void add(const std::shared_ptr<Surface> &surface);
    void remove(const Surface *surface);
    int count() const;
    // The surfaces with content to record this frame (empty at rest), the background layer's first (D5.2's order).
    QList<std::shared_ptr<Surface>> dirtySurfaces() const;

    // N5.7b, the backdrop pyramids (backdrop.h; render thread): added by a backdrop node while its item is not parked,
    // recorded by the frame driver after the background layer. A pyramid that wants a build regardless of the layer
    // (made, woken, resized, dimming) notes it at its sync; the frame edge takes the note (one atomic at rest).
    void addBackdrop(const std::shared_ptr<BackdropPyramid> &pyramid);
    void removeBackdrop(const BackdropPyramid *pyramid);
    QList<std::shared_ptr<BackdropPyramid>> backdrops() const;
    void noteBackdropWanting() { m_backdropWanted.storeRelease(1); }
    bool takeBackdropWanted() { return m_backdropWanted.testAndSetOrdered(1, 0); }
    // The window's background layer the pyramid is built from: the last added background-layer surface holding a frame
    // (a display generation's new layer is added after the one it replaces), else the last added one; null when the
    // window has none.
    std::shared_ptr<Surface> backgroundSource() const;

private:
    struct Retired
    {
        std::shared_ptr<JobService> service;
        quint64 output = 0;
        qint64 lastUse = 0; // the frame edge of its last possible use
    };

    // Render thread, inside one of the window's frames (the window is alive while it renders): a queued update() of the
    // window on its own (GUI) thread, dropped by Qt if the window goes first.
    void requestFrame();

    QQuickWindow *m_window = nullptr; // set by forWindow; dereferenced only inside the window's own frames
    QAtomicInteger<qint64> m_frameRequests { 0 };
    mutable QMutex m_mutex;
    QList<std::shared_ptr<Surface>> m_surfaces;
    int m_drivers = 0;
    QAtomicInteger<qint64> m_edges { 0 };
    QAtomicInteger<int> m_frameCounted { 0 }; // this frame's edge is counted (M1); cleared at afterRendering
    QAtomicInteger<int> m_retiring { 0 };
    QList<Retired> m_retired; // under m_mutex
    QList<std::shared_ptr<BackdropPyramid>> m_backdrops; // under m_mutex (N5.7b)
    QAtomicInteger<int> m_backdropWanted { 0 };
};

} // namespace srpss_core
