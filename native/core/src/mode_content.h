// Generic mode content (Current_Plan.md item 8b, N2.9): a Visualizer mode drawn by the core from data alone, so a new
// mode, or a change to one, needs no module build while it is iterated.
//
// A mode is three things Python owns (Docs/Reference/Transitions.md, "Where a mode's work lives on the native core"):
// - its simulation, in the engine worker, publishing a fixed-layout frame record per frame (native_schema.py);
// - its schema, the record's table, handed over when the stream is bound (mode_schema.h RuntimeSchema): the reader admits
//   the mode's slots by it and the frame block is packed from it;
// - its program: one or more full-target passes (ModePass), each a fragment pack baked by tools/regen_qrc.py's baker and
//   handed over as bytes, with its blend; and its settings, every Settings- and card-derived value resolved in Python
//   from the spec and handed over by name.
//
// The blocks of a pass (std140, reflected by name; program_blocks.h):
// - `ModeSettings`: the settings, packed when they change (never per frame). Every key must be a member of some pass's
//   ModeSettings (an unknown name is refused) and every ModeSettings member of every pass must be given (an unfilled
//   member is refused). A new program keeps the settings unless new ones come with it, and is refused when they do not
//   fit it.
// - `ModeFrame`: the frame record, packed per accepted frame by name: each member is named exactly as the record's field
//   that fills it (recordFieldFits: the same kind and length). A ModeFrame member no field names (unfilled) and a record
//   field no pass's ModeFrame declares (unknown) are refused when the program meets the schema, at bind or at program.
// - `SrpssConventions` at binding 17 (the conventions include; fragPixel gives the target's pixel on every backend).
// Nothing else: a pass that declares a texture, a sampler, a storage buffer or image, a push constant, another block, or
// any input is refused (the core's triangle, shaders/mode.vert, gives none: a pass's pixel is fragPixel). Sampling an earlier pass, depth, more targets or compute
// are primitives, each with its own C++ and harness (Current_Plan.md port rule (g) and N2.9), never pass data.
//
// The passes (ModeContent): the surface's target is cleared by a draw (targets.h rule B), then every pass draws one
// triangle over the whole target, in the program's order, blended as it says (PassBlend): replace (no blending), alpha
// (straight alpha over: the target then holds premultiplied colour, which the composite draws; Spectrum's blend),
// premultiplied (the shader writes premultiplied colour) or add (light added, the target's alpha kept).
//
// The stream (ModeSource) follows the Spectrum item's rules (spectrum.h): bound by mapping name on the GUI thread, read
// at the item's sync on the render thread (D2's accept edge), retired without waiting and released by the render
// thread's retire job (D1); a frame is drawn only when the slot is a present frame and, while playing, its reactive
// source is its own activation's (the Spectrum node's admission). Nothing at rest: the surface records only when a frame
// was accepted or dropped, or the program or the settings changed.
#pragma once

#include "mode_schema.h"
#include "packet_reader.h"
#include "program_blocks.h"
#include "surfaces.h"
#include "thread_probe.h"

#include <QtCore/QByteArray>
#include <QtCore/QJsonObject>
#include <QtCore/QList>
#include <QtCore/QMutex>
#include <QtCore/QSharedPointer>
#include <QtCore/QString>
#include <rhi/qshader.h>

#include <memory>

namespace srpss_core {

constexpr int kMaxModePasses = 8;
extern const char kModeSettingsBlock[]; // "ModeSettings"
extern const char kModeFrameBlock[];    // "ModeFrame"

enum class PassBlend { Replace = 0, Alpha = 1, Premultiplied = 2, Add = 3 };
bool parsePassBlend(const QString &text, PassBlend *out);
QString passBlendName(PassBlend blend);

struct ModePass
{
    QByteArray name;
    PassBlend blend = PassBlend::Alpha;
    QShader fragment;
    BlockLayout settings; // ModeSettings (not valid: the pass declares none)
    BlockLayout frame;    // ModeFrame (not valid: the pass declares none)
};

struct ModeProgram
{
    QList<ModePass> passes;
    quint64 generation = 0; // a new program rebuilds the pipelines at the next record

    // The program from its declaration ({"passes": [{"name", "blend"}, ...]}) and one fragment pack per pass, in order;
    // false with `error` when a pack does not load or a pass declares what a pass may not (the header).
    static bool fromJson(const QByteArray &json, const QList<QByteArray> &packs, ModeProgram *out, QString *error);
    bool valid() const { return !passes.isEmpty(); }
    QJsonObject toJson() const;

    // Why this program cannot draw records of `schema` (empty: every ModeFrame member is named by a record field that
    // fits it, and every record field is some pass's ModeFrame member).
    QString frameProblem(const frame_abi::Schema &schema) const;
    // The settings, packed into each pass's ModeSettings (an empty block for a pass without one); refused on an unknown
    // name, a value of the wrong size, or a member left unfilled.
    bool packSettings(const QJsonObject &settings, QList<QByteArray> *out, QString *error) const;
    // The record, packed into each pass's ModeFrame by name (an empty block for a pass without one).
    bool packFrame(const frame_abi::Schema &schema, const QByteArray &record, QList<QByteArray> *out,
                   QString *error) const;
};

// GPU-free: what the content uploads for one record (each pass's ModeSettings and ModeFrame bytes), with the same
// refusals; `facts` names each pass's blocks.
bool modeBlocks(const RuntimeSchema &schema, const ModeProgram &program, const QJsonObject &settings,
                const QByteArray &record, QList<QByteArray> *settingsOut, QList<QByteArray> *frameOut,
                QJsonObject *facts, QString *reason);

// Any thread: the QRhi objects every mode content holds in the process (lifecycle proofs).
int modeContentObjects();

// The stream, the schema, the program and the settings a generic mode item draws: shared by the item (GUI thread) and
// its node (render thread).
class ModeSource
{
public:
    ModeSource();
    ~ModeSource();
    ModeSource(const ModeSource &) = delete;
    ModeSource &operator=(const ModeSource &) = delete;

    // GUI thread. A new stream read by `schema` (the previous one retires); refused when the mapping is not a frame
    // buffer, when the program cannot draw the schema's records, or for the pause_in_copy hook (the reader's harness and
    // the Spectrum item's only).
    bool bind(const QString &mappingName, const PacketReaderConfig &config,
              const QSharedPointer<const RuntimeSchema> &schema, QString *error);
    void unbind();
    void retireCurrent();
    // GUI thread. A new program (refused when it cannot draw the bound schema's records) with `settings` (null: the
    // settings given before), packed against its blocks; refused, the drawn program kept, when they do not fit. A
    // shader change that adds a ModeSettings member therefore comes with the settings that fill it, in one call.
    bool setProgram(const ModeProgram &program, const QJsonObject *settings, QString *error);
    // GUI thread. The settings by name; unchanged settings record nothing.
    bool setSettings(const QJsonObject &settings, QString *error);
    void dropRetainedFrame();
    bool readHead(SlotHead *out);

    // Render thread, at the item's sync: the retired readers released, the current stream read, the program and the
    // settings taken. True when the surface must record.
    bool sync();
    void releaseRetired();

    // Render thread, while recording.
    bool hasFrame() const { return m_hasFrame; }
    const QByteArray &frameRecord() const { return m_record; }
    const ModeProgram &drawnProgram() const { return m_drawnProgram; }
    const QList<QByteArray> &drawnSettings() const { return m_drawnSettings; }
    const RuntimeSchema *drawnSchema() const { return m_drawnSchema.data(); }

    void noteRecorded(bool drawn, const QString &reason, const QJsonObject &facts);
    QJsonObject stateJson() const;
    static int liveSources();

private:
    mutable QMutex m_mutex;                     // guards the members down to m_lastReader
    PacketReader *m_current = nullptr;
    QList<PacketReader *> m_retiring;
    QSharedPointer<const RuntimeSchema> m_schema; // the current stream's
    ModeProgram m_program;
    QJsonObject m_settings;
    QList<QByteArray> m_packedSettings;         // empty until settings fit the program
    quint64 m_generation = 0;                   // a stream, program or settings change
    QString m_mapping;
    qint64 m_binds = 0;
    qint64 m_retired = 0;
    qint64 m_released = 0;
    QJsonObject m_lastReader;

    ThreadProbe m_syncProbe;

    // Render thread.
    quint64 m_takenGeneration = 0;
    ModeProgram m_drawnProgram;
    QList<QByteArray> m_drawnSettings;
    QSharedPointer<const RuntimeSchema> m_drawnSchema;
    QByteArray m_record;
    bool m_hasFrame = false;

    mutable QMutex m_reportMutex;
    qint64 m_syncs = 0;
    qint64 m_accepted = 0;
    qint64 m_admissionRejected = 0;
    bool m_reportedFrame = false;
    qint64 m_records = 0;
    qint64 m_draws = 0;
    QString m_lastReason;
    QJsonObject m_lastFacts;
    QString m_lastResult;
};

// The surface content that draws a generic mode: its pipelines and buffers live on the render thread with the surface.
class ModeContent final : public SurfaceContent
{
public:
    explicit ModeContent(std::shared_ptr<ModeSource> source);
    ~ModeContent() override;

    bool record(QRhi *rhi, QRhiCommandBuffer *cb, ColorTarget &target, QString *error) override;
    void release() override;
    int liveResources() const override;

private:
    struct Resources;
    bool ensure(QRhi *rhi, ColorTarget &target, QString *error);

    std::shared_ptr<ModeSource> m_source;
    std::unique_ptr<Resources> m_res;
};

} // namespace srpss_core
