// The composite (D5.2; Current_Plan.md item 8b, N2.4): what the core draws reaches the window as an ordinary
// scene-graph texture node with a small material of ours, never as a render node drawing inside Qt's pass. Qt's
// renderer then applies clip, opacity, order and batching itself; no inherited state is read or restored.
//
// - CompositeItem: a Qt Quick item placed where the target lies (its geometry is the target's rect, on whole device
//   pixels: the card's drawn rect, or an admitted overflow's rect). At sync its node takes the item's device-pixel size
//   (the window's effective device pixel ratio) and gives its surface (surfaces.h) a target of exactly that size, turned
//   by the content's quarter turns.
// - The material maps texels one to one: each fragment's texel is the integer index floor(uv x the item's device size),
//   read with texelFetch (no filtering, no threshold on a pixel centre), turned by the quarter turn as
//   widgets/spotify_visualizer/presentation_orientation.py logical_uv_from_physical_uv does. The vertex stage puts the
//   item's quad on whole pixels of its render target wherever the item lies (R-NEW: at a half-pixel origin the two
//   triangles read neighbouring texels along the diagonal), so the map holds at any placement; the state's
//   origin_shift is the last draw's shift.
// - The card's coverage (plan 1C.4: no pass writes outside the card, nor under the border's anti-aliased edge) is the
//   rounded rectangle Python resolves (presentation_geometry.resolve_card_clip_path, through
//   rendering/native/composite.py), tested at each texel's centre in device pixels, exactly the clip host's rule
//   (rendering/quick/visualizer/clip_host.py: a pixel is content when its centre's distance to the path is <= 0). An
//   admitted overflow (Sphere's, Extruded Spectrum's, not held by the record) skips the term; Python decides which.
// - Opacity is Qt's (the item's own and its ancestors'); the content is premultiplied. An opaque content (N5.7a: the
//   background layer) is drawn without blending in Qt's opaque pass, as the retained image node it stands for.
// - The layer (N5.7a, D5.2): a background-layer surface is recorded before every other surface of its window.
// - Content: the harness's pattern, or a mode's (N2.5: Spectrum, spectrum.h; N2.9: a generic mode, mode_content.h,
//   read and recorded by the same rules). With Spectrum bound, the node reads the
//   item's stream at every sync on the render thread (the accept edge), releases the streams the item retired (the
//   render-thread retire job, also run when Qt deletes the node), and its surface records only when a frame was
//   accepted or dropped or the card changed.
//
// GUI thread for the item; its node lives on the render thread.
#pragma once

#include <QtCore/QByteArray>
#include <QtCore/QJsonObject>
#include <QtCore/QRectF>
#include <QtCore/QSize>
#include <QtCore/QString>
#include <QtQuick/QQuickItem>

#include <memory>

class QPropertyAnimation;
class QQuickWindow;

namespace srpss_core {

class WindowSurfaces;
class SpectrumSource;
class ModeSource;
class TexturesLostListener;
struct CompositeStats;
struct ModeCard;
struct ModeProgram;
struct PacketReaderConfig;
struct SpectrumPresentation;

// Render thread (or the GUI thread blocked in Qt's sync): the window's framebuffer in device pixels, from Qt's own
// swapchain or redirect target (audit N29 L1); invalid when it has neither yet. The backdrop pyramid is sized from it
// (N5.7b), as the Python pyramid is from Qt Quick's render target.
QSize windowFramebufferPixels(QQuickWindow *window);

struct CompositeConfig
{
    QRectF rect;               // parent-local logical: where the target lies
    bool coverage = true;      // the card's coverage term; false: skipped (an admitted overflow)
    QRectF coverageRect;       // item-local logical: the card's clip path
    qreal coverageRadius = 0.0;
    int quarters = 0;          // the content's clockwise quarter turns
    QString pattern = QStringLiteral("texel_id");
    QString surfaceFormat = QStringLiteral("rgba8"); // the surface's texels: rgba8 or rgba16f (N2.5 rule (a))
    bool visible = true;
    qreal opacity = 1.0;
    // A change of `visible` fades over this many milliseconds (0: at once): a failed route fades its card out, never
    // hides it (audit N29 M1).
    qreal fadeMs = 0.0;
    // The window's own logical-to-framebuffer ratio per axis (framebuffer pixels / window.size(), the ratio Qt's
    // projection draws with); 0: the window's device pixel ratio. At a scale where the logical window size times the
    // device pixel ratio is not the framebuffer (2560x1440 at 150 %: logical 1707) the two differ (audit 14 Nov, H1).
    qreal pixelRatioX = 0.0;
    qreal pixelRatioY = 0.0;
    // N5.7a: the surface's place in the frame's dependency order ("content", or "background": recorded first, D5.2).
    QString layer = QStringLiteral("content");
    // N5.7a: the content covers every texel opaquely (the background layer's photo), so the node is drawn in Qt's
    // opaque pass as the retained QSGImageNode it stands for is (the material without blending; Qt still blends it
    // while its opacity is below one, a fade). A content with transparent texels is never marked opaque.
    bool opaque = false;

    // Updates `out` from the harness's JSON (missing keys keep what `out` holds); false with `error` for a bad value.
    static bool update(const QByteArray &json, CompositeConfig *out, QString *error);
    QJsonObject toJson() const;
};

class CompositeItem final : public QQuickItem
{
public:
    explicit CompositeItem(QQuickItem *parent);
    ~CompositeItem() override;

    void apply(const CompositeConfig &config);
    const CompositeConfig &config() const { return m_config; }
    QJsonObject stateJson() const;
    // GUI thread: the window's framebuffer in device pixels, from Qt's own swapchain or redirect target (audit N29 L1):
    // the last sync's, else read now; invalid before the window has either.
    QSize windowPixels() const;

    // Spectrum (N2.5), GUI thread. bindSpectrum opens the stream (the previous one retires); unbindSpectrum retires it
    // (never waits); presentSpectrum sets the card as shown; each asks Qt for a frame. spectrum() is null until bound.
    // One content per item: each is refused on an item that draws a generic mode (audit N29 L3).
    bool bindSpectrum(const QString &mappingName, const PacketReaderConfig &config, QString *error);
    void unbindSpectrum();
    bool presentSpectrum(const SpectrumPresentation &presentation, QString *error);
    // The program (N2.5's standing port rule): the fragment pack's bytes (empty: the module's compiled-in copy, the
    // harness's negative control) and the Settings-derived values by name; false with `error` when refused.
    bool programSpectrum(const QByteArray &qsb, QString *error);
    bool settingsSpectrum(const QJsonObject &settings, QString *error);
    SpectrumSource *spectrum() const { return m_spectrum.get(); }
    // A shared owner (a harness wait holds one for its duration: audit N29 L8).
    std::shared_ptr<SpectrumSource> spectrumShared() const { return m_spectrum; }

    // A generic mode (N2.9, mode_content.h), GUI thread: its stream (the schema rides on the reader configuration), its
    // program (with settings, or keeping the ones given before), its settings by name and its card. One content per
    // item: a mode is refused on an item that draws Spectrum. mode() is null until a mode call.
    bool bindMode(const QString &mappingName, const PacketReaderConfig &config, QString *error);
    void unbindMode();
    bool programMode(const ModeProgram &program, const QJsonObject *settings, QString *error);
    bool settingsMode(const QJsonObject &settings, QString *error);
    bool cardMode(const ModeCard &card, QString *error);
    // N5.7a: the generic mode drawn as a still (no stream; mode_content.h "Stills"): the background layer's photo.
    bool stillMode(bool still, QString *error);
    // N4.a: the item's textures (mode_content.h): an image by name (RGBA8, rows top first), or its removal. `inFrame`
    // (N3.8, a harness control): uploaded in the frame where the device has a job service.
    bool textureMode(const QByteArray &name, const QByteArray &pixels, const QSize &size, bool mips, QString *error,
                     bool inFrame = false);
    bool removeTextureMode(const QByteArray &name, QString *error);
    // N3.8: the owner's listener of the lost edge (null: none), called on the GUI thread (item_notifier.h).
    bool texturesLostListener(const std::shared_ptr<TexturesLostListener> &listener, QString *error);
    ModeSource *mode() const { return m_mode.get(); }

    // Any thread: composite items alive in the process.
    static int liveItems();

protected:
    QSGNode *updatePaintNode(QSGNode *oldNode, UpdatePaintNodeData *data) override;
    void itemChange(ItemChange change, const ItemChangeData &value) override;

private:
    bool modeRefused(QString *error) const;
    bool spectrumRefused(QString *error) const;
    // The item's generic mode source, its notifier attached to this item (N3.8): the current one, or a new one the
    // caller keeps only when its call succeeds; modeSource() keeps it at once.
    std::shared_ptr<ModeSource> currentOrNewMode();
    std::shared_ptr<ModeSource> modeSource();

    CompositeConfig m_config;
    std::shared_ptr<WindowSurfaces> m_surfaces; // the window's registry (GUI thread; copied by the node at sync)
    std::shared_ptr<CompositeStats> m_stats;
    std::shared_ptr<SpectrumSource> m_spectrum; // shared with the node, which holds it until Qt deletes the node
    std::shared_ptr<ModeSource> m_mode;         // the same, for a generic mode
    QPropertyAnimation *m_fade = nullptr;       // the item's opacity fade (a child QObject)
    bool m_fadingOut = false;
};

} // namespace srpss_core
