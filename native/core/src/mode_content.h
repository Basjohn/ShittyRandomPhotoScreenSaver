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
// The product fullscreen shaders' shape (lead's decision on audit N29 M5, binding; N4.a widened it to the fullscreen
// transitions and Bubble's samplers): a pass declares
// - one std140 block of its own, any name (`OscilloscopeDraw`, `DevCurveDraw`, `CrossfadePass`, ...), at any binding
//   but 17;
// - optionally the conventions block (`SrpssConventions`, binding 17: fragPixel gives the target's pixel on every
//   backend);
// - optionally one vec2 input at location 0, filled by its NAME from the core's triangle (shaders/mode.vert), the same on
//   every backend (N4.a):
//   - `v_uv`: the Visualizer quad's uv (rendering/quick/visualizer/render_contract.py: x right, y DOWN from the
//     target's top row; the 2D modes);
//   - `vUv`: the item quad's uv (rendering/gl_programs/item_quad.py: x right, y UP, 1 at the target's top row; the
//     fullscreen transitions, which sample their pictures at (vUv.x, 1 - vUv.y));
//   the core's triangle carries both at each vertex (exact values) and a pass's pipeline reads the one it names, so the
//   pass sees the Python quad's convention without a matrix or a uniform; any other input is refused;
// - optionally combined image samplers (`sampler2D` only), each bound BY NAME in the program's declaration to a texture
//   the item holds, with its sampler state declared beside it (PassSampler, N4.a: the sampling primitive); an unbound,
//   unknown or doubly bound sampler is refused, as is one at binding 17 or at its block's binding;
// - one vec4 output at location 0.
// Anything else is refused: a separate texture or sampler, storage, a push constant, a second block of its own.
// Sampling an earlier pass, depth, more targets or compute are primitives with their own C++ and harness.
//
// The textures (N4.a): an item holds up to kMaxModeTextures named textures (ModeTexture), each uploaded from pixels
// Python holds (RGBA8, rows top first) and owned by the core: the GUI thread stores the image (a new generation); the
// render thread takes it at the item's sync and uploads it once, at the next record, into a QRhiTexture the content
// owns (mips generated on the GPU when the texture asks for them), then drops the core's copy. Nothing is uploaded
// again at rest. A replaced image of the same size and mips is uploaded into the same QRhiTexture; another size
// recreates it in place (Qt's bindings follow its generation). A removed texture's QRhiTexture is released on the render
// thread at the next record (the retire path) and the pipelines that bound it are rebuilt; every texture goes with the
// content (the node's destruction, on the render thread, the QRhi alive). A content made again (a new node, another
// QRhi) has no copy to upload from: the texture is reported lost and the item draws nothing until its owner sends the
// image again. Counted process-wide (modeTextureCounts) so a lifecycle proof sees every texture and copy released.
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
// that declares it. A pass whose textures are not all uploaded (missing, or lost) is not drawn: the target is cleared
// and the state says which texture it waits for.
//
// The stream, the admission, the retire job, the refused-frame rule and the failure latch are the shared ones
// (stream_source.h). Nothing at rest: the surface records only when a frame was accepted or dropped, or the program, the
// settings, the card or a texture changed; a texture is uploaded once per image.
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
#include <QtCore/QStringList>
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

// The vec2 a pass reads at location 0 (by its name, the header): none, the Visualizer quad's (v_uv, y down) or the item
// quad's (vUv, y up).
enum class PassUv { None = 0, Down = 1, Up = 2 };
QString passUvName(PassUv uv);

constexpr int kMaxPassSamplers = 8;
constexpr int kMaxModeTextures = 8;
constexpr int kMaxTextureSide = 16384;

// A sampler's state, declared beside it (N4.a): the filter (min and mag), the wrap (both axes) and the mip filter
// (none: the base level only).
enum class SamplerFilter { Nearest = 0, Linear = 1 };
enum class SamplerWrap { Clamp = 0, Repeat = 1, Mirror = 2 };
enum class SamplerMips { None = 0, Nearest = 1, Linear = 2 };

// One combined image sampler of a pass, bound by name to a texture of the item.
struct PassSampler
{
    QByteArray name;      // the shader's sampler2D
    QByteArray texture;   // the item's texture it reads (ModeTexture::name)
    int binding = -1;     // reflected from the pack
    SamplerFilter filter = SamplerFilter::Linear;
    SamplerWrap wrap = SamplerWrap::Clamp;
    SamplerMips mips = SamplerMips::None;

    QJsonObject toJson() const;
};

struct ModePass
{
    QByteArray name;
    PassBlend blend = PassBlend::Alpha;
    QShader fragment;
    BlockLayout block;        // the pass's own block (not valid: the pass declares none)
    bool conventions = false; // the pass declares SrpssConventions
    PassUv uv = PassUv::None; // the quad uv the pass reads at location 0
    QList<PassSampler> samplers;
};

struct ModeProgram
{
    QList<ModePass> passes;
    quint64 generation = 0; // a new program rebuilds the pipelines at the next record

    // The program from its declaration ({"passes": [{"name", "blend", "samplers"?: [{"name", "texture", "filter",
    // "wrap", "mips"}, ...]}, ...]}) and one fragment pack per pass, in order; false with `error` when a pack does not
    // load or a pass declares what a pass may not (the header), or a sampler is unbound, unknown or doubly bound.
    static bool fromJson(const QByteArray &json, const QList<QByteArray> &packs, ModeProgram *out, QString *error);
    bool valid() const { return !passes.isEmpty(); }
    QJsonObject toJson() const;
    bool declares(const QByteArray &member) const;
    bool needsCard() const;
    // The item's textures the passes sample (each once, in first-use order).
    QList<QByteArray> sampledTextures() const;
    // Why a texture of these mips cannot be sampled by this program (empty: it can): a sampler that reads mips of a
    // texture set without them.
    QString textureFits(const QByteArray &texture, bool mips) const;

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

// N4.a: a texture's pixels as the core holds them until the render thread uploads them (RGBA8, rows top first, tight).
// Counted while alive (the copies the core holds).
struct TextureImage
{
    const QByteArray pixels;
    const QSize size;
    const bool mips = false;

    TextureImage(const QByteArray &pixels, const QSize &size, bool mips);
    ~TextureImage();
    TextureImage(const TextureImage &) = delete;
    TextureImage &operator=(const TextureImage &) = delete;
};

// One named texture of an item, as its source holds it.
struct ModeTexture
{
    QByteArray name;
    quint64 generation = 0;              // a new image (process-wide, never reused)
    QSize size;
    bool mips = false;
    QSharedPointer<TextureImage> image;  // the core's copy, until the render thread takes it for its upload
};

// The process's textures (lifecycle proofs and the destruction barrier's reading): the QRhiTextures the contents hold,
// their bytes (every level), the CPU copies the core holds, and the uploads done.
struct ModeTextureCounts
{
    int textures = 0;
    qint64 textureBytes = 0;
    int images = 0;
    qint64 imageBytes = 0;
    qint64 uploads = 0;
};
ModeTextureCounts modeTextureCounts();

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
    // N4.a, GUI thread: a texture's image (RGBA8, `size`, rows top first, tight; `mips`: generated on the GPU), replacing
    // the one of that name; refused for a bad name, size or byte count, more than kMaxModeTextures, or mips the current
    // program samples that this texture lacks. removeTexture: false when there is no such texture.
    bool setTexture(const QByteArray &name, const QByteArray &pixels, const QSize &size, bool mips, QString *error);
    bool removeTexture(const QByteArray &name, QString *error);

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
    const QList<ModeTexture> &drawnTextures() const { return m_drawnTextures; }
    // The image of the drawn texture `name` (its core copy moves to the caller; null when it was taken before).
    QSharedPointer<TextureImage> takeTextureImage(const QByteArray &name);
    // The content's texture report (render thread writes, any thread reads).
    void noteTextures(qint64 uploads, int resident, const QStringList &lost);

    static int liveSources();

protected:
    bool acceptStream(const PacketReaderConfig &config, QString *error) override;
    void streamUnbound() override;
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
    QList<ModeTexture> m_textures;              // N4.a: the item's textures, their images until taken
    quint64 m_generation = 0;                   // a stream, program, settings, card or texture change

    // Render thread.
    quint64 m_takenGeneration = 0;
    ModeProgram m_drawnProgram;
    QList<BlockValues> m_drawnSettings;
    QSharedPointer<const RuntimeSchema> m_drawnSchema;
    ModeCard m_drawnCard;
    bool m_drawnReady = false;
    QString m_drawnWaiting;
    QList<ModeTexture> m_drawnTextures;

    mutable QMutex m_textureReportMutex;        // guards the texture report
    qint64 m_textureUploads = 0;
    int m_texturesResident = 0;
    QStringList m_texturesLost;
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
    // N4.a: one texture the content owns (render thread).
    struct GpuTexture
    {
        QByteArray name;
        quint64 generation = 0;              // the image uploaded into it
        std::unique_ptr<QRhiTexture> texture;
        qint64 bytes = 0;
    };

    bool ensure(QRhi *rhi, ColorTarget &target, bool withPasses, QString *error);
    bool build(QRhi *rhi, ColorTarget &target, bool withPasses, QString *error);
    void pack(const ColorTarget &target);
    void releasePipelines();
    // The textures: a removed one released, a lost one named (keepsTarget, before anything is recorded).
    void retireTextures();
    // Each drawn texture with a new image created or recreated and uploaded into `updates` (record).
    void uploadTextures(QRhi *rhi, QRhiResourceUpdateBatch *updates);
    // Every texture the drawn program samples is uploaded at its drawn generation.
    bool texturesReady() const;
    GpuTexture *gpuTexture(const QByteArray &name);
    const GpuTexture *gpuTexture(const QByteArray &name) const;
    void releaseTexture(GpuTexture &texture);
    void reportTextures();

    std::shared_ptr<ModeSource> m_source;
    std::unique_ptr<Resources> m_res;
    ContentLatch m_latch;
    GpuTexture m_textures[kMaxModeTextures];
    quint64 m_textureObjects = 0;            // a texture object created or released: the bindings are rebuilt
    qint64 m_textureUploads = 0;
    QStringList m_textureFailures;           // "<name> could not be created ...", until a new image of that name
    QStringList m_texturesLost;
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
