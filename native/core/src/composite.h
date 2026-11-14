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
//   widgets/spotify_visualizer/presentation_orientation.py logical_uv_from_physical_uv does.
// - The card's coverage (plan 1C.4: no pass writes outside the card, nor under the border's anti-aliased edge) is the
//   rounded rectangle Python resolves (presentation_geometry.resolve_card_clip_path, through
//   rendering/native/composite.py), tested at each texel's centre in device pixels, exactly the clip host's rule
//   (rendering/quick/visualizer/clip_host.py: a pixel is content when its centre's distance to the path is <= 0). An
//   admitted overflow (Sphere's, Extruded Spectrum's, not held by the record) skips the term; Python decides which.
// - Opacity is Qt's (the item's own and its ancestors'); the content is premultiplied.
// - Content: the harness's pattern, or a mode's (N2.5: Spectrum, spectrum.h). With Spectrum bound, the node reads the
//   item's stream at every sync on the render thread (the accept edge), releases the streams the item retired (the
//   render-thread retire job, also run when Qt deletes the node), and its surface records only when a frame was
//   accepted or dropped or the card changed.
//
// GUI thread for the item; its node lives on the render thread.
#pragma once

#include <QtCore/QJsonObject>
#include <QtCore/QRectF>
#include <QtCore/QString>
#include <QtQuick/QQuickItem>

#include <memory>

namespace srpss_core {

class WindowSurfaces;
class SpectrumSource;
struct CompositeStats;
struct PacketReaderConfig;
struct SpectrumPresentation;

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
    // The window's own logical-to-framebuffer ratio per axis (framebuffer pixels / window.size(), the ratio Qt's
    // projection draws with); 0: the window's device pixel ratio. At a scale where the logical window size times the
    // device pixel ratio is not the framebuffer (2560x1440 at 150 %: logical 1707) the two differ (audit 14 Nov, H1).
    qreal pixelRatioX = 0.0;
    qreal pixelRatioY = 0.0;

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

    // Spectrum (N2.5), GUI thread. bindSpectrum opens the stream (the previous one retires); unbindSpectrum retires it
    // (never waits); presentSpectrum sets the card as shown; each asks Qt for a frame. spectrum() is null until bound.
    bool bindSpectrum(const QString &mappingName, const PacketReaderConfig &config, QString *error);
    void unbindSpectrum();
    void presentSpectrum(const SpectrumPresentation &presentation);
    // The program (N2.5's standing port rule): the fragment pack's bytes (empty: the module's compiled-in copy, the
    // harness's negative control) and the Settings-derived values by name; false with `error` when refused.
    bool programSpectrum(const QByteArray &qsb, QString *error);
    bool settingsSpectrum(const QJsonObject &settings, QString *error);
    SpectrumSource *spectrum() const { return m_spectrum.get(); }

    // Any thread: composite items alive in the process.
    static int liveItems();

protected:
    QSGNode *updatePaintNode(QSGNode *oldNode, UpdatePaintNodeData *data) override;
    void itemChange(ItemChange change, const ItemChangeData &value) override;

private:
    CompositeConfig m_config;
    std::shared_ptr<WindowSurfaces> m_surfaces; // the window's registry (GUI thread; copied by the node at sync)
    std::shared_ptr<CompositeStats> m_stats;
    std::shared_ptr<SpectrumSource> m_spectrum; // shared with the node, which holds it until Qt deletes the node
};

} // namespace srpss_core
