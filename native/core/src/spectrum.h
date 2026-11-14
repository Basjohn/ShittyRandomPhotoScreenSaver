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
//   plain values. The maps from the target's pixel to the window's (u_window_from_target) and from the window's pixel
//   to the item's oriented logical coordinate (u_item_from_frag, the Python renderer's own float32 rows) are two of
//   them: the target is the card's drawn rect on whole device pixels, in the content's orientation.
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
#include "program_blocks.h"
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
    // The pixel arithmetic runs in the Python renderer's own space and precision (N2.5 rule (a), lead 14 Nov): the
    // target's pixel is first rebuilt as the window's (u_window_from_target: exact, whole-pixel offsets and a sign),
    // then mapped by the Python renderer's own rows (u_item_from_frag, from Qt's float32 item matrix).
    double windowFromTarget[6] = {};// rows x, y of the target pixel (fragPixel) to the window's pixel (y up)
    double itemFromWindow[6] = {};  // rows x, y of the window's pixel to the oriented item coordinate
    double targetSize[2] = {};      // the target's pixels (fragPixel's target)

    static bool fromJson(const QByteArray &json, SpectrumPresentation *out, QString *error);
    QJsonObject toJson() const;
    bool operator==(const SpectrumPresentation &other) const;
    bool operator!=(const SpectrumPresentation &other) const { return !(*this == other); }
};


// The program a native Spectrum draws (N2.5's standing port rule, program_blocks.h): the product's fragment pack
// loaded at run time (tools/regen_qrc.py --shaders bakes it; Python hands the bytes over), its reflected SpectrumDraw
// block, and the Settings- and card-derived values Python resolved (name -> value). The C++ fills only the per-frame
// members (kSpectrumFrameMembers) from the record.
struct SpectrumProgram
{
    QShader fragment;
    BlockLayout layout;
    QJsonObject settings;
    BlockValues packed;             // the settings packed into the block once, when they change (audit 14 Nov, L3)
    quint64 shaderGeneration = 0;   // the pipeline is rebuilt when it changes
    bool compiledIn = false;        // the module's own copy (the harness's negative control only)

    // The program for `qsb` (the serialized pack; empty: the module's compiled-in copy); false with `error` when it
    // does not load or holds no SpectrumDraw block.
    static bool fromPack(const QByteArray &qsb, SpectrumProgram *out, QString *error);
    // The settings checked against the block (every name a member, every size right) before they are kept.
    bool setSettings(const QJsonObject &settings, QString *error);
};

// The members the C++ computes per frame (bars, peaks, the bar layout that follows the bar count, the clock's hues,
// the play state); every other reflected member comes from the program's settings.
extern const char *const kSpectrumFrameMembers[];

// The block for one record under one presentation and program, as QuickSpectrumRenderer.render computes it. False when
// nothing is drawn (no bars, a layout the renderer refuses, a refused value) with the reason; `facts` carries the
// derived values a test reads and "unfilled": the reflected members neither side filled (a harness error).
bool spectrumBlock(const QByteArray &record, const SpectrumPresentation &presentation, const SpectrumProgram &program,
                   QByteArray *block, QJsonObject *facts, QString *reason);

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
    // GUI thread: the program (a new pack rebuilds the pipeline at the next record) and its settings (re-packed only
    // when they change: nothing per frame at rest). A new program keeps the settings it was given before; it is
    // refused when they no longer fit its block (audit 14 Nov, L4: the route sends unchanged settings only once).
    bool setProgram(const SpectrumProgram &program, QString *error);
    bool setSettings(const QJsonObject &settings, QString *error);
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
    const SpectrumProgram &drawnProgram() const { return m_drawnProgram; }

    // The content's report (render thread writes, any thread reads).
    void noteRecorded(bool drawn, const QString &reason, const QJsonObject &facts);

    QJsonObject stateJson() const;
    static int liveSources();

private:
    mutable QMutex m_mutex;                 // guards the members down to m_presentationGeneration
    PacketReader *m_current = nullptr;      // read only on the render thread; replaced on the GUI thread
    QList<PacketReader *> m_retiring;       // retired, waiting for the render thread's release
    int m_waiters = 0;                      // waitPaused calls in progress: no retired reader is deleted under them
    SpectrumPresentation m_presentation;    // the GUI's latest
    SpectrumProgram m_program;              // the GUI's latest program and settings
    quint64 m_presentationGeneration = 0;   // the presentation's or the program's change
    QString m_mapping;
    qint64 m_binds = 0;
    qint64 m_retired = 0;
    qint64 m_released = 0;
    QJsonObject m_lastReader;               // the last released reader's state

    ThreadProbe m_syncProbe;                // D5.4 at the accept edge: the threads the syncs (the reads) ran on

    // Render thread.
    quint64 m_takenGeneration = 0;
    SpectrumPresentation m_drawn;
    SpectrumProgram m_drawnProgram;
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
    bool build(QRhi *rhi, ColorTarget &target, QString *error);

    std::shared_ptr<SpectrumSource> m_source;
    std::unique_ptr<Resources> m_res;
    // A failed build (audit 14 Nov, M2): the inputs it failed with; nothing is created again until one of them changes
    // (another QRhi, another target pass, another program pack), so a refused pipeline is not rebuilt every frame.
    bool m_failed = false;
    QRhi *m_failedRhi = nullptr;
    QRhiRenderPassDescriptor *m_failedPass = nullptr;
    quint64 m_failedGeneration = 0;
    QString m_failedError;
    qint64 m_failures = 0;
};

} // namespace srpss_core
