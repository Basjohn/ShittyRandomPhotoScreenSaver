// The card-material backdrop pyramid on the native core (Current_Plan.md N5.7b; D7 points 2 to 6;
// Docs/Architecture/Card_Surface_Materials.md section 3 for what a card sees). The Python pyramid
// (rendering/quick/render/surface_backdrop.py, BackdropPipeline) blits Qt Quick's window target after the wallpaper and
// the dimming are drawn; no backend lets the core read Qt Quick's target inside its pass, so here the source is the
// core's own background layer (N5.7a, D7 point 1), which the frame driver records before every other surface.
//
// What it builds, level for level the Python pyramid's (the same arithmetic, so a card samples the same backdrop):
//   window --seed--> 1/2 --down--> 1/4 --> 1/8 --> 1/16 --> 1/32     (dual-filter, the Python _DOWN)
//   1/8  --up--> output level 0 (1/4 of the window, the light blur)    (the Python _UP)
//   1/32 --up--> 1/16 --up--> output level 1 (1/8, the heavy blur)
// The output is one RGBA8 texture with mips; levels 0 and 1 are written, and MaterialSurface's textureLod reads only
// those (its blur level is 0 to 1: surface_material.frag), so the levels past 1 that QRhi gives a mipmapped texture are
// never sampled. Every build writes alpha 1; the output is cleared to transparent when it is made and whenever the
// layer holds no frame, so a card samples transparent there and shows exactly its Normal fill (fail closed, D7 point 6).
//
// The seed (the Python blit) samples the background layer where it lies in the window: the layer's target covers the
// display, which sits at a whole device pixel inside the (overscanned) window, and the window outside it is the
// window's clear colour, black (rendering/quick/window.py). The seed reads the layer bilinearly at the window position
// the blit reads, black outside the layer, and writes the level's rows in the window framebuffer's own row order
// (bottom-up on OpenGL), so the output is sampled in screen space exactly as the Python texture is (surface_material.vert:
// vScreen from the vertex's own clip position). Dimming (DisplayScene's black rectangle over the wallpaper, which the
// Python blit reads) is applied in the seed as the uniform blend it is (the layer times one minus the dimming), so
// MaterialSurface samples the pyramid unchanged; a dimming change is one build. (D7 point 5 puts dimming at sample time;
// that would change the card shader the plan keeps unchanged: the lead's call, recorded in the decisions doc.)
//
// When it builds (D7 points 2 and 3): in the frame in which the layer drew a new frame (a photo committed, its target
// resized; later every transition frame, N5.2a), only while the item is not parked (the owner's demand above zero), and
// once when it is made or woken, its size changes, the dimming changes or a harness asks for a readback. Never
// otherwise: at rest the frame driver reads one atomic. No minimum interval: every layer frame is followed (the budget,
// 0.3 ms at 2560 x 1440 and 0.6 ms at 4K, is measured by native/core/python/backdrop_pyramid_check.py).
//
// The passes are data (the N4.a shape where it fits: a fullscreen triangle, one block, one sampler): a table of
// (source, target, kind) built from the window's size, recorded in order. Reading an earlier pass is this primitive's
// own C++ (D12 point 3): every intermediate is a target of its own, so no pass samples the texture it writes.
//
// Lifetime: the item (GUI thread) is a texture provider; its node (render thread) owns the pyramid, which registers in
// its window's surface registry so the frame driver records it after the background layer (D5.2's order). Parking
// (demand 0) releases every QRhi object and unregisters it at the next sync; the node's destruction (the item removed,
// the scene graph invalidated) does the same. Counted process-wide (backdropCounts) for the lifecycle proofs.
#pragma once

#include "targets.h"

#include <QtCore/QAtomicInteger>
#include <QtCore/QByteArray>
#include <QtCore/QJsonObject>
#include <QtCore/QList>
#include <QtCore/QMutex>
#include <QtCore/QPoint>
#include <QtCore/QSize>
#include <QtCore/QString>
#include <QtQuick/QQuickItem>
#include <QtQuick/QSGTextureProvider>
#include <rhi/qrhi.h>

#include <memory>

class QSGNode;

namespace srpss_core {

class Surface;
class WindowSurfaces;

// The levels, in the Python pyramid's order (its _levels 1/2 .. 1/32, its one heavy-chain scratch at 1/16, its output's
// two levels): a readback names them so.
enum class BackdropLevel { Half = 0, Quarter, Eighth, Sixteenth, ThirtySecond, Scratch, Light, Heavy, Count };
QString backdropLevelName(BackdropLevel level);

// The level sizes of a window of `window` device pixels (each halving floors, at least 1): the Python pyramid_sizes.
QList<QSize> backdropPyramidSizes(const QSize &window);

// One level's pixels as read back (RGBA8, rows in the texture's memory order; harness only).
struct BackdropLevelPixels
{
    QString name;
    QSize size;
    QByteArray rgba;
};

// What the GUI thread asks of the pyramid (copied by the node at sync).
struct BackdropRequest
{
    bool parked = false;
    double dimmingKeep = 1.0;   // one minus the dimming opacity (1: no dimming)
    quint64 readbacks = 0;      // harness: a readback of every level at the next build (a build is made for it)
    quint64 builds = 0;         // harness: a build asked for (the layer unchanged)

    bool operator==(const BackdropRequest &o) const
    {
        return parked == o.parked && dimmingKeep == o.dimmingKeep && readbacks == o.readbacks && builds == o.builds;
    }
    bool operator!=(const BackdropRequest &o) const { return !(*this == o); }
};

// The pyramid (render thread only, but stateJson and the readback's results).
class BackdropPyramid
{
public:
    BackdropPyramid();
    ~BackdropPyramid();
    BackdropPyramid(const BackdropPyramid &) = delete;
    BackdropPyramid &operator=(const BackdropPyramid &) = delete;

    // Render thread, at the item's sync: the window's QRhi and framebuffer, and what the GUI asked. A new size remakes
    // the targets (the output is the same QRhiTexture at its new size, so Qt Quick's bindings follow its generation)
    // and clears the output; anything that changes what is built marks the pyramid wanting a build. False with `error`
    // when a QRhi object cannot be made (the output stays transparent or absent: the cards stay Normal).
    bool sync(QRhi *rhi, const QSize &window, const BackdropRequest &request, QString *error);
    // Render thread, inside the frame (the frame driver, after the background layer): builds when it wants to or the
    // layer `source` (null: the window has none) drew a frame it has not built from. `recorded`: passes were recorded.
    bool record(QRhi *rhi, QRhiCommandBuffer *cb, const Surface *source, bool *recorded, QString *error);
    // Render thread: every QRhi object goes (parking, the node's destruction).
    void release();

    // Whether a build is wanted regardless of the layer (made, woken, resized, dimming, a harness request).
    bool wanting() const { return m_wanting.loadAcquire() != 0; }
    // Render thread, the frame edge: whether record would record anything for this layer (the frame driver times only
    // the records that do).
    bool needsRecord(const Surface *source) const;
    // The output texture (null until made). Ready once a record wrote it (cleared or built): a texture provider hands it
    // out only then, so Qt Quick never samples texels nobody wrote.
    QRhiTexture *output() const;
    QSize outputSize() const;
    bool ready() const { return m_ready.loadAcquire() != 0; }
    // Render thread: told once each time the output becomes ready (the provider's textureChanged).
    class ReadyListener
    {
    public:
        virtual ~ReadyListener() = default;
        virtual void outputReady() = 0;
    };
    void setReadyListener(std::shared_ptr<ReadyListener> listener) { m_listener = std::move(listener); }
    int liveResources() const { return m_live.loadRelaxed(); }
    QJsonObject stateJson() const;
    // Any thread: the last readback's levels (taken once; false when none completed since).
    bool takeLevels(QList<BackdropLevelPixels> *out);

    static int livePyramids();
    static int liveResourcesTotal();

    // A readback of every level (render thread starts it, the QRhi completes it; backdrop.cpp).
    struct Readback;

private:
    struct Resources;
    bool ensure(QRhi *rhi, QString *error);
    // The levels and the output at the window's size (made, or the same objects resized), and the bindings over them.
    bool makeTargets(QString *error);
    void writeBlocks(QRhiResourceUpdateBatch *updates, const QSize &layer, const QPoint &origin);
    bool clearOutput(QRhi *rhi, QRhiCommandBuffer *cb, QString *error);
    void startReadback(QRhi *rhi, QRhiResourceUpdateBatch *updates);
    void setLive(int count);

    std::unique_ptr<Resources> m_res;
    QSize m_syncWindow;                 // the window framebuffer as the item's sync (or the layer's) read it
    QSize m_window;                     // the window framebuffer the levels are sized from
    BackdropRequest m_request;
    quint64 m_readbacksDone = 0;
    quint64 m_builtFrom = 0;            // the layer's drawn generation the output holds (0: none, cleared)
    bool m_outputClear = false;         // the output is known to be transparent
    QAtomicInteger<int> m_wanting { 1 };
    QAtomicInteger<int> m_ready { 0 };
    QAtomicInteger<int> m_live { 0 };
    std::shared_ptr<ReadyListener> m_listener;

    mutable QMutex m_mutex;             // guards the facts below and the readback's results
    qint64 m_builds = 0;
    qint64 m_clears = 0;
    qint64 m_buildNs = 0;               // the last build's render-thread CPU time
    QString m_lastReason;
    QString m_error;
    QSize m_lastLayer;
    QPoint m_lastOrigin;
    bool m_rowsUp = false;
    std::shared_ptr<Readback> m_readback;
};

class BackdropNode;

// The item: a texture provider whose texture is the pyramid's output (MaterialSurface's `source`), drawing nothing.
// GUI thread for its API; textureProvider() and the provider's texture() on the render thread.
class BackdropItem final : public QQuickItem
{
public:
    explicit BackdropItem(QQuickItem *parent);
    ~BackdropItem() override;

    // GUI thread: demand went to zero (true: every QRhi object goes at the next sync, the node is never recorded), or
    // came back. The owner unbinds every consumer before parking (Card_Surface_Materials.md section 3.2).
    void setParked(bool parked);
    bool parked() const;
    // GUI thread: the dimming over the wallpaper (0 to 1; DisplayScene's backgroundDimming opacity).
    void setDimming(double opacity);
    // GUI thread, harness: a build at the next frame, and a readback of every level with it.
    void requestBuild();
    void requestReadback();
    bool takeLevels(QList<BackdropLevelPixels> *out);
    QJsonObject stateJson() const;

    bool isTextureProvider() const override { return true; }
    QSGTextureProvider *textureProvider() const override;

    static int liveItems();

    // Shared by the item (GUI thread), its node and its provider (render thread); backdrop.cpp. Public: the node and
    // the provider are file-local classes in backdrop.cpp that hold it (MSVC C2248 when it was protected).
    struct Shared;

protected:
    QSGNode *updatePaintNode(QSGNode *oldNode, UpdatePaintNodeData *data) override;
    void itemChange(ItemChange change, const ItemChangeData &value) override;
    void geometryChange(const QRectF &newGeometry, const QRectF &oldGeometry) override;

private:
    std::shared_ptr<Shared> m_shared;
    std::shared_ptr<WindowSurfaces> m_surfaces; // the window's registry (GUI thread; copied by the node at sync)
};

// The process's backdrop objects (lifecycle proofs and composite_live's reading).
struct BackdropCounts
{
    int items = 0;
    int pyramids = 0;
    int resources = 0;
    qint64 builds = 0;
};
BackdropCounts backdropCounts();

} // namespace srpss_core
