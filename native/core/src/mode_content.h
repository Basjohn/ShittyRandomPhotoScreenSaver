// Generic mode content (Current_Plan.md item 8b, N2.9): a Visualizer mode drawn by the core from data alone, so a new
// mode, or a port of a 2D mode (N5), needs no per-mode C++ and no module build while it is iterated. The Python renderer
// and the core draw the same shader file.
//
// A mode is four things Python owns (Docs/Reference/Transitions.md, "Where a mode's work lives on the native core"):
// - its simulation, in the engine worker, publishing a fixed-layout frame record per frame (native_schema.py);
// - its schema, the record's table, handed over when the stream is bound (mode_schema.h RuntimeSchema): the reader admits
//   the mode's slots by it and the record's fields are packed by name;
// - its program: one or more full-target passes (ModePass), each a fragment pack (the product's .qsb, baked by
//   tools/regen_qrc.py's baker, handed over as bytes) and a blend;
// - its settings (every Settings- and mode-derived value, resolved in Python from the spec, by name) and its card (the
//   item as shown: ModeCard, resolved by Python from the presentation and the composite's geometry).
//
// The product 2D shader's shape (lead's decision on audit N29 M5, binding): a pass declares
// - one std140 block of its own, any name (`OscilloscopeDraw`, `DevCurveDraw`, ...), at any binding but 17;
// - optionally the conventions block (`SrpssConventions`, binding 17: fragPixel gives the target's pixel on every
//   backend);
// - optionally `in vec2 v_uv` at location 0 (the core's triangle, shaders/mode.vert, gives it: position * 0.5 + 0.5 as
//   the native Spectrum's vertex stage, so its row orientation is the backend's clip space; a pass that needs the pixel
//   takes fragPixel);
// - one vec4 output at location 0.
// Anything else is refused: a texture, a sampler, storage, a push constant, a second block of its own, another input.
// Sampling an earlier pass or an image, depth, more targets or compute are primitives with their own C++ and harness.
//
// One rule fills the block, by member name, from exactly one of three sources:
// 1. the core's conventions (kModeCoreMembers, one table for every mode: what the Python renderers compute per frame
//    from the card and the target: the item's sizes and quarter turns, the dpr, the fade, the border width, the maps
//    from the target's pixel to the window's and to the item, the target's pixels);
// 2. the mode's settings (packed when they change, never per frame);
// 3. the record's fields (packed per accepted frame; a field fits a member only exactly: recordFieldFits).
// A setting or a record field no pass declares is refused (unknown); a setting or field that names a core member, or a
// setting that names a record field, is refused (one owner per member); a member none of the three fills is refused
// (unfilled). The checks run when the program, the schema and the settings meet (at bind, program and settings), so a
// mode whose data does not match its shaders never draws zeros. A program whose members the core and the record fill
// alone draws with no settings at all (audit L5).
//
// The passes (ModeContent): the surface's target is cleared by a draw (targets.h rule B), then every pass draws one
// triangle over the whole target, in order, blended as it says (PassBlend): replace, alpha (straight alpha over:
// Spectrum's), premultiplied, add (light added, the target's alpha kept). The conventions block is bound only to a pass
// that declares it.
//
// The stream, the admission, the retire job, the refused-frame rule and the failure latch are the shared ones
// (stream_source.h). Nothing at rest: the surface records only when a frame was accepted or dropped, or the program, the
// settings or the card changed.
#pragma once

#include "mode_schema.h"
#include "packet_reader.h"
#include "program_blocks.h"
#include "stream_source.h"
#include "surfaces.h"

#include <QtCore/QByteArray>
#include <QtCore/QJsonObject>
#include <QtCore/QList>
#include <QtCore/QSharedPointer>
#include <QtCore/QSize>
#include <QtCore/QString>
#include <rhi/qrhi.h>
#include <rhi/qshader.h>

#include <memory>

namespace srpss_core {

constexpr int kMaxModePasses = 8;

// The core's conventions: the members the core fills for every mode (name, components). The values: modeCoreValues.
struct ModeCoreMember
{
    const char *name;
    int components;
    bool fromCard;   // false: the core's own (a constant, or the target's pixels)
};
extern const ModeCoreMember kModeCoreMembers[];
extern const int kModeCoreMemberCount;
bool isModeCoreMember(const QByteArray &name);

// The item as shown, resolved by Python (rendering/native/mode.py mode_card).
struct ModeCard
{
    bool valid = false;
    int quarters = 0;
    double itemSize[2] = {};
    double orientedSize[2] = {};
    double dpr = 1.0;
    double contentFade = 1.0;
    double borderWidth = 0.0;
    double windowFromTarget[6] = {};
    double itemFromWindow[6] = {};

    static bool fromJson(const QByteArray &json, ModeCard *out, QString *error);
    QJsonObject toJson() const;
    bool operator==(const ModeCard &other) const;
    bool operator!=(const ModeCard &other) const { return !(*this == other); }
};

// The core member's numbers for this card and target (false: the member is not a core member).
bool modeCoreValues(const QByteArray &name, const ModeCard &card, const QSize &target, double *out, int *count);

enum class PassBlend { Replace = 0, Alpha = 1, Premultiplied = 2, Add = 3 };
bool parsePassBlend(const QString &text, PassBlend *out);
QString passBlendName(PassBlend blend);

struct ModePass
{
    QByteArray name;
    PassBlend blend = PassBlend::Alpha;
    QShader fragment;
    BlockLayout block;        // the pass's own block (not valid: the pass declares none)
    bool conventions = false; // the pass declares SrpssConventions
    bool uv = false;          // the pass reads v_uv
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
    bool declares(const QByteArray &member) const;
    bool needsCard() const;

    // The one rule (the header) for what is known: `schema` and `settings` may be null (not given yet). False with the
    // reason (unknown, unfilled, a field that does not fit, a name with two owners). `ready`: everything a draw needs
    // is known (settings may be absent when the core and the record fill every member).
    bool check(const frame_abi::Schema *schema, const QJsonObject *settings, bool *ready, QString *error) const;
    // The settings packed into each pass's block (an empty block for a pass without one); refused on a value of the
    // wrong size or with no defined conversion.
    bool packSettings(const QJsonObject &settings, QList<BlockValues> *out, QString *error) const;
    // One frame: the record's fields and the core's members, by name, over the packed settings (`blocks`, one per pass,
    // overwritten in place). Refused (a NaN, a value with no defined conversion) with the reason.
    bool packFrame(const frame_abi::Schema &schema, const QByteArray &record, const ModeCard &card, const QSize &target,
                   QList<BlockValues> &blocks, QString *error) const;
};

// GPU-free: what the content uploads for one record (each pass's block bytes), with the same refusals; `facts` names
// each pass's block and which source filled each member.
bool modeBlocks(const RuntimeSchema &schema, const ModeProgram &program, const QJsonObject &settings,
                const ModeCard &card, const QSize &target, const QByteArray &record, QList<QByteArray> *blocksOut,
                QJsonObject *facts, QString *reason);

int modeContentObjects();

// The stream, the schema, the program, the settings and the card a generic mode item draws: shared by the item (GUI
// thread) and its node (render thread).
class ModeSource final : public StreamSource
{
public:
    ModeSource();
    ~ModeSource() override;

    // GUI thread. The stream's schema rides on its reader configuration (PacketReaderConfig::runtimeSchema); bind refuses
    // a stream without one, one the program cannot draw (the one rule) and the pause_in_copy hook (the reader harness's
    // and the Spectrum item's).
    // A new program with `settings` (null: the settings given before), checked by the one rule; refused, the drawn
    // program kept, when they do not fit.
    bool setProgram(const ModeProgram &program, const QJsonObject *settings, QString *error);
    bool setSettings(const QJsonObject &settings, QString *error);
    void setCard(const ModeCard &card);

    // Render thread, at the item's sync. True when the surface must record.
    bool sync();

    // Render thread, while recording.
    const ModeProgram &drawnProgram() const { return m_drawnProgram; }
    const QList<BlockValues> &drawnSettings() const { return m_drawnSettings; }
    const RuntimeSchema *drawnSchema() const { return m_drawnSchema.data(); }
    const ModeCard &drawnCard() const { return m_drawnCard; }
    bool drawnReady() const { return m_drawnReady; }
    QString drawnWaiting() const { return m_drawnWaiting; }
    quint64 drawnGeneration() const { return m_takenGeneration; }

    static int liveSources();

protected:
    bool acceptStream(const PacketReaderConfig &config, QString *error) override;
    void stateInto(QJsonObject &o) const override;

private:
    bool admit(const ModeProgram &program, const QSharedPointer<const RuntimeSchema> &schema,
               const QJsonObject *settings, QList<BlockValues> *packed, bool *ready, QString *error) const;

    // Under m_mutex.
    QSharedPointer<const RuntimeSchema> m_schema; // the current stream's
    ModeProgram m_program;
    QJsonObject m_settings;
    bool m_hasSettings = false;
    QList<BlockValues> m_packedSettings;
    bool m_ready = false;
    ModeCard m_card;
    quint64 m_generation = 0;                   // a stream, program, settings or card change

    // Render thread.
    quint64 m_takenGeneration = 0;
    ModeProgram m_drawnProgram;
    QList<BlockValues> m_drawnSettings;
    QSharedPointer<const RuntimeSchema> m_drawnSchema;
    ModeCard m_drawnCard;
    bool m_drawnReady = false;
    QString m_drawnWaiting;
};

class ModeContent final : public SurfaceContent
{
public:
    explicit ModeContent(std::shared_ptr<ModeSource> source);
    ~ModeContent() override;

    bool keepsTarget(QRhi *rhi, ColorTarget &target) override;
    bool record(QRhi *rhi, QRhiCommandBuffer *cb, ColorTarget &target, QString *error) override;
    void release() override;
    int liveResources() const override;

private:
    struct Resources;
    bool ensure(QRhi *rhi, ColorTarget &target, QString *error);
    bool build(QRhi *rhi, ColorTarget &target, QString *error);
    void pack(const ColorTarget &target);

    std::shared_ptr<ModeSource> m_source;
    std::unique_ptr<Resources> m_res;
    ContentLatch m_latch;
    // One block per pass, kept and overwritten per frame (audit L4); rebuilt from the settings when they change.
    QList<BlockValues> m_blocks;
    quint64 m_blocksGeneration = 0;
    bool m_draw = false;
    bool m_refused = false;
    QString m_reason;
    QJsonObject m_facts;
    const QRhiTexture *m_drawnTexture = nullptr;
    QSize m_drawnSize;
};

} // namespace srpss_core
