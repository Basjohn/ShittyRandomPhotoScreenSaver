// The native Spectrum (Current_Plan.md item 8b, N2.5): Spectrum drawn by the core into a composite's surface (D5.2), fed
// by the core's packet reader on the render thread (N2.3, D1 and D2), the reader's first user.
//
// One fragment shader for both renderers: the product's widgets/spotify_visualizer/shaders/spectrum.frag, baked by this
// module's CMake from that path (the conventions include spliced at its marker, as the Python loader splices it), with
// the core's full-target triangle (shaders/spectrum.vert). Its SpectrumDraw block is packed at the offsets the baked
// shader reflects (N0.3 rule 5), with the values the Python renderer computes
// (rendering/quick/visualizer/implementations/spectrum.py QuickSpectrumRenderer.render), ported line for line in double
// precision: the GPU-free spectrum_block entry lets a test compare the two byte for byte.
//
// Who computes what:
// - From the frame (the record, core/visualizer_engine/spectrum_native_schema.py): the levels and their transfer, the
//   expanded card's resample, the bar layout, colours, the rainbow clock, the decoration. Render thread.
// - From the card as shown (SpectrumPresentation): resolved by Python on the GUI thread
//   (rendering/native/spectrum.py) from the ResolvedVisualizerPresentation and the composite's geometry, handed over as
//   plain values. The map from the target's pixel to the item's oriented logical coordinate (u_item_from_frag) is one
//   of them: the target is the card's drawn rect on whole device pixels, in the content's orientation.
//
// The stream (SpectrumSource): the GUI binds a frame mapping by name with its expected identity; the reader is opened on
// the GUI thread and read only at the item's sync, on the render thread (the accept edge, D2; the Python path's
// admit-at-sync). Retiring a stream (a rebind, an unbind, the item's destruction) stores Retiring at once and never
// waits (D1); the render-thread retire job releases it at the next sync, or when Qt deletes the item's node (the render
// thread, the QRhi alive). A source whose node never existed releases on its own last owner's thread: no read can be in
// progress there. The drop edge (R-184) is the reader's own (dropRetainedFrame, applied by the next read).
//
// Nothing at rest: the surface records only when a frame was accepted, the presentation changed or a frame was dropped.
#pragma once

#include "packet_reader.h"
#include "surfaces.h"
#include "thread_probe.h"

#include <QtCore/QByteArray>
#include <QtCore/QJsonObject>
#include <QtCore/QList>
#include <QtCore/QMutex>
#include <QtCore/QString>

#include <memory>

namespace srpss_core {

// The card as shown, resolved by Python (rendering/native/spectrum.py spectrum_presentation).
struct SpectrumPresentation
{
    bool valid = false;
    int quarters = 0;               // content_rotation_quarters
    double itemSize[2] = {};        // the item's logical size (outer rect), physical orientation
    double orientedSize[2] = {};    // u_resolution: the item's logical size in the content's orientation
    double contentRect[4] = {};     // logical_content_rect: item-local, oriented
    double viewportExtent[2] = {};  // logical_viewport_extent
    double visualScale = 1.0;       // uniform_visual_scale
    double dpr = 1.0;
    double contentFade = 1.0;
    bool expanded = false;          // expanded_display
    double itemFromTarget[6] = {};  // rows x, y of the target pixel (fragPixel) to the oriented item coordinate
    double targetSize[2] = {};      // the target's pixels (fragPixel's target)

    static bool fromJson(const QByteArray &json, SpectrumPresentation *out, QString *error);
    QJsonObject toJson() const;
    bool operator==(const SpectrumPresentation &other) const;
    bool operator!=(const SpectrumPresentation &other) const { return !(*this == other); }
};

// SpectrumDraw as the baked fragment shader reflects it.
class SpectrumBlockLayout
{
public:
    struct Member
    {
        QByteArray name;
        int type = 0;     // QShaderDescription::VariableType
        int offset = 0;
        int count = 1;    // array length (1: not an array)
        int stride = 0;   // array stride
        bool strideInferred = false; // the reflection gave 0: std140's rule (a vec4 per element) was applied
    };

    static const SpectrumBlockLayout &instance(); // reflected once from the embedded shader
    bool valid() const { return m_size > 0 && m_binding >= 0; }
    int size() const { return m_size; }
    int binding() const { return m_binding; }
    const QList<Member> &members() const { return m_members; }
    QJsonObject toJson() const;

private:
    SpectrumBlockLayout();
    QList<Member> m_members;
    int m_size = 0;
    int m_binding = -1;
};

// The block for one record under one presentation, as QuickSpectrumRenderer.render computes it. False when nothing is
// drawn (no bars, a layout the renderer refuses) with the reason; `facts` carries the derived values a test reads.
bool spectrumBlock(const QByteArray &record, const SpectrumPresentation &presentation, QByteArray *block,
                   QJsonObject *facts, QString *reason);

// Any thread: the QRhi objects every Spectrum content holds in the process (lifecycle proofs).
int spectrumContentObjects();

// The stream and the card a native Spectrum item draws: shared by the item (GUI thread) and its node (render thread).
class SpectrumSource
{
public:
    SpectrumSource();
    ~SpectrumSource();
    SpectrumSource(const SpectrumSource &) = delete;
    SpectrumSource &operator=(const SpectrumSource &) = delete;

    // GUI thread. A new stream (the previous one retires); false with `error` when the mapping is not a frame buffer
    // this build reads (a name that does not open gives a retired reader, D1 rule 1).
    bool bind(const QString &mappingName, const PacketReaderConfig &config, QString *error);
    void unbind();                                    // the current stream retires (never waits)
    // Any thread: the current stream stores Retiring at once (D1; no copy starts after it, a copy in progress is not
    // presented) and stays bound until unbind() moves it to the render thread's release.
    void retireCurrent();
    void setPresentation(const SpectrumPresentation &presentation);
    void dropRetainedFrame();                         // R-184's edge, applied by the next read
    bool readHead(SlotHead *out);                     // D2's head read of the current stream (consumes nothing)
    // The D1 hook (the pause_in_copy control only): wait until the current reader is paused inside a copy; resume it.
    bool waitPaused(int timeoutMs);
    void resume();

    // Render thread, at the item's sync: the retired readers released (the retire job), the current stream read, the
    // presentation taken. True when the surface must record (a frame accepted or dropped, the presentation changed).
    bool sync();
    // Render thread: every retired reader released (the node's destruction).
    void releaseRetired();

    // Render thread, while recording: what was synchronised last.
    bool hasFrame() const { return m_hasFrame; }
    const QByteArray &frameRecord() const { return m_record; }
    const SpectrumPresentation &drawnPresentation() const { return m_drawn; }

    // The content's report (render thread writes, any thread reads).
    void noteRecorded(bool drawn, const QString &reason, const QJsonObject &facts);

    QJsonObject stateJson() const;
    static int liveSources();

private:
    mutable QMutex m_mutex;                 // guards the members down to m_presentationGeneration
    PacketReader *m_current = nullptr;      // read only on the render thread; replaced on the GUI thread
    QList<PacketReader *> m_retiring;       // retired, waiting for the render thread's release
    SpectrumPresentation m_presentation;    // the GUI's latest
    quint64 m_presentationGeneration = 0;
    QString m_mapping;
    qint64 m_binds = 0;
    qint64 m_retired = 0;
    qint64 m_released = 0;
    QJsonObject m_lastReader;               // the last released reader's state

    ThreadProbe m_syncProbe;                // D5.4 at the accept edge: the threads the syncs (the reads) ran on

    // Render thread.
    quint64 m_takenGeneration = 0;
    SpectrumPresentation m_drawn;
    QByteArray m_record;
    bool m_hasFrame = false;

    mutable QMutex m_reportMutex;           // guards the report
    qint64 m_syncs = 0;
    qint64 m_accepted = 0;
    qint64 m_admissionRejected = 0;         // accepted frames the node's admission rule does not draw
    bool m_reportedFrame = false;
    qint64 m_records = 0;
    qint64 m_draws = 0;
    QString m_lastReason;
    QJsonObject m_lastFacts;
    QString m_lastResult;
};

// The surface content that draws Spectrum: its pipelines and buffers live on the render thread with the surface.
class SpectrumContent final : public SurfaceContent
{
public:
    explicit SpectrumContent(std::shared_ptr<SpectrumSource> source);
    ~SpectrumContent() override;

    bool record(QRhi *rhi, QRhiCommandBuffer *cb, ColorTarget &target, QString *error) override;
    void release() override;
    int liveResources() const override;
    const SpectrumSource *source() const { return m_source.get(); }

private:
    struct Resources;
    bool ensure(QRhi *rhi, ColorTarget &target, QString *error);

    std::shared_ptr<SpectrumSource> m_source;
    std::unique_ptr<Resources> m_res;
};

} // namespace srpss_core
