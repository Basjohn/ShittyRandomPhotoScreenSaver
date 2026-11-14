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
// The upload's two forms (N3.8, D9 as built, job_service.h): on a Vulkan device with a job service the render thread
// only hands the image to an upload job (the job owns the pixels; its output is a texture of the job's QRhi), and the
// content imports the job's output into Qt's QRhi (createFrom) once it is published; everywhere else (OpenGL, no second
// queue, a failed job, the harness control in_frame) the upload is recorded in the frame as above. The item's textures
// commit together: one record swaps every changed texture, only once every changed texture's job is done or failed;
// until then the textures held are drawn. A replaced job output goes to the window's retire list (surfaces.h), released
// once Qt's frames that sampled it completed. A superseded image cancels its job. A texture found lost is an edge to the
// owner (item_notifier.h), not only a state entry.
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
//
// Stills (N5.7a, D7 point 1: the background layer's photo): an item set as a still draws with no stream. Its frame is
// its textures, its settings and its card, so its program is checked against an empty schema (no record: every member
// is the core's or a setting, else unfilled) and a stream is refused while it is one (and the still while a stream is
// bound). It records only when one of those changed, and only when what it draws changed: a record that only hands a
// new image to its upload job (the picture drawn is still the old front until the item's textures commit) keeps the
// frame the target holds and records no pass (TextureReport::stillKept), so the layer's texture changes exactly once
// per photo, at the commit's record (the frame edge the latch publishes at). At rest nothing is recorded.
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

struct ModeCard;
class ItemNotifier;
class JobService;
class UploadJob;
class WindowSurfaces;

// The core's conventions: the members the core fills for every mode (name, components) and each one's values, on its
// own row (audit N29 round 2, L6: a row is never filled by a separate list that zero-fills what it does not name).
struct ModeCoreMember
{
    const char *name;
    int components;
    bool fromCard;   // false: the core's own (a constant, or the target's pixels)
    void (*values)(const ModeCard &card, const QSize &target, double *out); // `components` numbers into `out`
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

// The core member's numbers for this card and target (false: the member is not a core member, or its row has no
// values: never zeros for a name it does not know).
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

// Every level's bytes of an RGBA8 texture (the base level only without mips): the one count of the core's and the job
// service's textures.
qint64 rgba8TextureBytes(const QSize &size, bool mips);

// N4.a: a texture's pixels as the core holds them until the render thread uploads them (RGBA8, rows top first, tight).
// Counted while alive (the copies the core holds). N3.8: an upload job owns one until it recorded the upload.
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
    bool inFrame = false;                // N3.8, a harness control: the in-frame form where a job service exists
    QSharedPointer<TextureImage> image;  // the core's copy, until the render thread takes it for its upload
};

// The content's texture report (render thread writes, any thread reads; N4.a, N3.8).
struct TextureReport
{
    qint64 uploads = 0;          // images committed (in-frame uploads and job outputs swapped in)
    int resident = 0;            // textures the content holds
    QStringList lost;            // lost textures (names, and creation failures with their reason)
    QString route;               // "job": this device has a job service; "in_frame" otherwise
    qint64 inFrameUploads = 0;   // in the frame (OpenGL, no service, the control, a failed job's fallback)
    qint64 jobsSubmitted = 0;
    qint64 jobsCommitted = 0;    // job outputs swapped in
    qint64 jobsFellBack = 0;     // failed jobs whose pixels were uploaded in the frame
    qint64 jobsCancelled = 0;    // superseded, removed or released before they were committed
    qint64 importFailures = 0;   // a published output Qt's QRhi could not import (released, reported lost)
    int jobsPending = 0;         // jobs in flight now
    qint64 retired = 0;          // job outputs handed to the window's retire list
    qint64 rebinds = 0;          // the passes' bindings made again over new texture objects (pipelines kept)
    qint64 stillKept = 0;        // N5.7a: a still's records that kept the target (what it draws had not changed)
};

// One record that changed an image (N3.8's measurement: the render thread's cost per image change): its kind ("submit":
// images handed to jobs; "commit_job": job outputs swapped in; "in_frame": uploads recorded in the frame; joined with
// "+"), the record's CPU time on the render thread and the image bytes it moved.
struct ImageChangeRecord
{
    QString kind;
    qint64 recordNs = 0;
    qint64 bytes = 0;
    qint64 edge = 0;             // the window's frame edge
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
    // N5.7a, GUI thread: the item draws as a still (no stream: the header's "Stills") or not. Refused while a stream is
    // bound, and when the program as it stands cannot be drawn so (the item stays as it was).
    bool setStill(bool still, QString *error);
    // N4.a, GUI thread: a texture's image (RGBA8, `size`, rows top first, tight; `mips`: generated on the GPU), replacing
    // the one of that name; refused for a bad name, size or byte count, more than kMaxModeTextures, or mips the current
    // program samples that this texture lacks. removeTexture: false when there is no such texture. `inFrame` (N3.8, a
    // harness control): upload it in the frame where a job service exists (the measurement both ways).
    bool setTexture(const QByteArray &name, const QByteArray &pixels, const QSize &size, bool mips, QString *error,
                    bool inFrame = false);
    bool removeTexture(const QByteArray &name, QString *error);

    // N3.8: the item's notifier (the job thread's frame request, the lost edge); the item attaches it.
    const std::shared_ptr<ItemNotifier> &notifier() const { return m_notifier; }

    // Render thread, at the item's sync. True when the surface must record.
    bool sync();

    // Render thread, while recording.
    const ModeProgram &drawnProgram() const { return m_drawnProgram; }
    const QList<BlockValues> &drawnSettings() const { return m_drawnSettings; }
    const RuntimeSchema *drawnSchema() const { return m_drawnSchema.data(); }
    bool drawnStill() const { return m_drawnStill; }
    const ModeCard &drawnCard() const { return m_drawnCard; }
    bool drawnReady() const { return m_drawnReady; }
    QString drawnWaiting() const { return m_drawnWaiting; }
    quint64 drawnGeneration() const { return m_takenGeneration; }
    // Everything a build reads but the card (the content's latch key, round 2 L4: a fade's card steps retry nothing).
    quint64 drawnBuildGeneration() const { return m_drawnBuildGeneration; }
    const QList<ModeTexture> &drawnTextures() const { return m_drawnTextures; }
    // The image of the drawn texture `name` (its core copy moves to the caller; null when it was taken before).
    QSharedPointer<TextureImage> takeTextureImage(const QByteArray &name);
    // The content's texture report (render thread writes, any thread reads).
    void noteTextures(const TextureReport &report);
    // N3.8: a record that changed an image (the last kImageChangeRecords are kept).
    void noteImageChange(const ImageChangeRecord &record);
    // N3.8: textures newly found lost: the owner's edge (queued to the GUI thread).
    void texturesLost(const QStringList &names);
    static constexpr int kImageChangeRecords = 64;

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
    bool m_still = false;                       // N5.7a: drawn with no stream
    ModeProgram m_program;
    QJsonObject m_settings;
    bool m_hasSettings = false;
    QList<BlockValues> m_packedSettings;
    bool m_ready = false;
    ModeCard m_card;
    QList<ModeTexture> m_textures;              // N4.a: the item's textures, their images until taken
    quint64 m_generation = 0;                   // a stream, program, settings, card or texture change
    quint64 m_buildGeneration = 0;              // the same but the card

    // Render thread.
    quint64 m_takenGeneration = 0;
    quint64 m_drawnBuildGeneration = 0;
    ModeProgram m_drawnProgram;
    QList<BlockValues> m_drawnSettings;
    QSharedPointer<const RuntimeSchema> m_drawnSchema;
    bool m_drawnStill = false;
    ModeCard m_drawnCard;
    bool m_drawnReady = false;
    QString m_drawnWaiting;
    QList<ModeTexture> m_drawnTextures;
    quint64 m_takenJobsFinished = 0;            // N3.8: the notifier's count at the last sync

    const std::shared_ptr<ItemNotifier> m_notifier;

    mutable QMutex m_textureReportMutex;        // guards the texture report
    TextureReport m_textureReport;
    QList<ImageChangeRecord> m_imageChanges;
};

class ModeContent final : public SurfaceContent
{
public:
    // `registry`: the window's (its frame edges and retire list, N3.8); null only in a content with no window.
    ModeContent(std::shared_ptr<ModeSource> source, std::shared_ptr<WindowSurfaces> registry);
    ~ModeContent() override;

    bool keepsTarget(QRhi *rhi, ColorTarget &target) override;
    bool record(QRhi *rhi, QRhiCommandBuffer *cb, ColorTarget &target, QString *error) override;
    bool holdsFrame(const ColorTarget &target) const override;
    bool keptTargetLastRecord() const override { return m_keptTarget; }
    void release() override;
    int liveResources() const override;

private:
    struct Resources;
    // N4.a: one texture of the item (render thread), by name: the front the passes bind, and N3.8's candidate for the
    // drawn image (a job in flight, or the pixels for the in-frame form) until the item's textures commit.
    struct GpuTexture
    {
        QByteArray name;                     // empty: a free slot
        quint64 generation = 0;              // the image the front holds
        std::unique_ptr<QRhiTexture> texture; // the front: Qt's own texture, or its import of a job's output
        qint64 bytes = 0;
        std::shared_ptr<JobService> frontService; // an imported front: its output's service and id
        quint64 frontOutput = 0;
        quint64 candidate = 0;               // the image the candidate carries (0: none)
        std::shared_ptr<UploadJob> job;      // a job in flight for it
        std::shared_ptr<JobService> jobService;
        QSharedPointer<TextureImage> pixels; // or its pixels, for the in-frame form at the commit
    };

    bool ensure(QRhi *rhi, ColorTarget &target, bool withPasses, QString *error);
    // N3.8: the passes' bindings over the current texture objects, the pipelines kept; false: build everything again.
    bool rebindTextures();
    bool build(QRhi *rhi, ColorTarget &target, bool withPasses, QString *error);
    void pack(const ColorTarget &target);
    // The QRhi objects of the passes only: a rebuild (a new program, a failed build) keeps the record of the frame in the
    // target, so a failure leaves that frame for the route to fade the card out over (round 2, M4).
    void releasePipelines();
    LatchKey latchKey(QRhi *rhi, const ColorTarget &target) const;
    // The textures: a removed one released, a lost one named and its owner told (keepsTarget, before anything is
    // recorded).
    void retireTextures();
    // Record: each drawn texture with a new image gets its candidate (a job submitted, or the pixels kept), then the
    // item's textures commit together when every candidate is ready (uploads recorded into `updates`, outputs imported).
    // Returns the kind of image change this record made ("" when none) and the bytes it moved.
    QString advanceTextures(QRhi *rhi, QRhiResourceUpdateBatch *updates, qint64 *bytes);
    bool uploadInFrame(QRhi *rhi, QRhiResourceUpdateBatch *updates, GpuTexture &gpu,
                       const QSharedPointer<TextureImage> &image, quint64 generation);
    // A published job output imported into Qt's QRhi (null on failure, recorded), then made the front (audit N38 L5:
    // the item's commit imports every output before any front switches).
    std::unique_ptr<QRhiTexture> importTexture(QRhi *rhi, GpuTexture &gpu, const UploadJob &job);
    void adoptImport(GpuTexture &gpu, std::unique_ptr<QRhiTexture> imported, const UploadJob &job);
    // Every texture the drawn program samples has a front.
    bool texturesReady() const;
    // N5.7a: what a still draws, as bytes (its program, target, triangle, blocks and the fronts its passes sample).
    QByteArray stillSignature(const ColorTarget &target, const float *triangle) const;
    GpuTexture *slot(const QByteArray &name);
    GpuTexture *front(const QByteArray &name);
    const GpuTexture *front(const QByteArray &name) const;
    GpuTexture *freeSlot();
    // The front goes: an imported one to the window's retire list (Qt's frames may still sample it), Qt's own at once
    // (QRhi defers its native release).
    void releaseFront(GpuTexture &texture);
    // The candidate goes: its job cancelled (an output it published first is released at once: never sampled).
    void dropCandidate(GpuTexture &texture);
    void clearSlotIfEmpty(GpuTexture &texture);
    const std::shared_ptr<JobService> &jobService(QRhi *rhi);
    void reportTextures();

    std::shared_ptr<ModeSource> m_source;
    std::shared_ptr<WindowSurfaces> m_registry;
    std::unique_ptr<Resources> m_res;
    ContentLatch m_latch;
    GpuTexture m_textures[kMaxModeTextures];
    quint64 m_textureObjects = 0;            // a texture object created or released: the bindings are rebuilt
    QStringList m_textureFailures;           // "<name> could not be created ...", until a new image of that name
    QStringList m_texturesLost;
    QStringList m_lostNames;                 // the names last reported lost (the edge fires for a new one)
    TextureReport m_report;
    const QRhi *m_serviceRhi = nullptr;      // the QRhi the job service was looked up for
    std::shared_ptr<JobService> m_service;
    // One block per pass, kept and overwritten per frame (audit L4); rebuilt from the settings when they change.
    QList<BlockValues> m_blocks;
    quint64 m_blocksGeneration = 0;
    bool m_draw = false;
    bool m_refused = false;
    QString m_reason;
    QJsonObject m_facts;
    const QRhiTexture *m_drawnTexture = nullptr;
    QSize m_drawnSize;
    QByteArray m_stillSignature;             // N5.7a: what the still last drew (empty: nothing of a still's)
    bool m_keptTarget = false;               // the last record kept the target (a still's unchanged frame)
};

} // namespace srpss_core
