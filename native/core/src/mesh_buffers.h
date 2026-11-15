// Meshes and buffers (Current_Plan.md item 8b, N3.2; decision D15 in Docs/Future_Work/Native_Core_P3_Decisions.md): the
// data a pass with its own vertex stage draws, and the one buffer every block of a content lives in.
//
// - Meshes (D15 point 2, choice A): data from Python, as a texture is. A mesh is a name, interleaved f32 vertex bytes with
//   their attributes (name, components, offset) and stride, and optionally a per-instance stream of the same shape. The
//   GUI thread stores the bytes (a new generation); the render thread uploads them once, at the next record, into an
//   Immutable QRhiBuffer and drops the core's copy. A replaced mesh is uploaded in the record that first draws it and its
//   old buffer goes after that record (QRhi defers the native release past the frames in flight). Content scope:
//   released with the content. A content made again has no copy to upload from: the mesh is reported lost and the passes
//   that draw it wait until the owner sends it again. The built-in mesh `quad` is the item quad's four vertices exactly
//   as the Python host's VAO holds them (rendering/quick/visualizer/render_host.py _ensure_quad), attribute `aPosition`.
// - Streams (D15 point 4, choice B, E): a record's f32 (or u32 array) field bound by name as an instance stream (a
//   Dynamic VertexBuffer read as per-instance attributes, written by the fast path), a storage stream (a Static
//   StorageBuffer, uploadStaticBuffer of the used bytes through a QByteArray the stream keeps across records), or an
//   indirect stream (a Dynamic IndirectBuffer of 16-byte commands {vertexCount, instanceCount, firstVertex, 0}). Each is
//   sized at the build from its field's capacity and never resized; written only by a record that draws. The streams
//   hold the schema they were built from (audit 4 H1: their fields point into it) and are built again when the bound
//   schema's fingerprint changes.
// - The block arena (D15 point 3, choices C and D): every block of a content in one Dynamic UniformBuffer at offsets
//   rounded up with QRhi::ubufAligned, given per draw as dynamic offsets; written whole once per record from the content's
//   CPU copy through beginFullDynamicBufferUpdateForCurrentFrame, never a batch update.
// - Counts and selectors (D15 point 1): a number, or a name the record (a u32 scalar field) or the settings fill.
//
// Render thread only, but the declarations (any thread) and the process-wide counts (any thread).
#pragma once

#include <QtCore/QAtomicInteger>
#include <QtCore/QByteArray>
#include <QtCore/QHash>
#include <QtCore/QJsonArray>
#include <QtCore/QJsonObject>
#include <QtCore/QJsonValue>
#include <QtCore/QList>
#include <QtCore/QSharedPointer>
#include <QtCore/QString>
#include <QtCore/QStringList>
#include <rhi/qrhi.h>

#include <memory>

namespace srpss_core {

namespace frame_abi {
struct Field;
struct Schema;
}
class RuntimeSchema;

constexpr int kMaxModeMeshes = 8;
constexpr int kMaxModeStreams = 8;
constexpr int kMaxPassStorage = 4;
constexpr int kMaxMeshAttributes = 8;
constexpr qint64 kMaxMeshBytes = qint64(64) << 20;
constexpr int kMaxBatches = 64;
// D15 point 3: a pass's bindings carry at most this many dynamic-offset blocks (inside OpenGL's 8 a bind and Vulkan's
// specification minimum of 8 a set).
constexpr int kMaxDynamicOffsetBlocks = 4;
constexpr quint32 kIndirectCommandBytes = 16; // {vertexCount, instanceCount, firstVertex, firstInstance}
extern const char kBuiltinQuadMesh[];         // "quad"
extern const char kBatchMember[];             // "u_srpss_batch": the core's per-batch member (D15 point 6)

// ------------------------------------------------------------------------------------------- declarations (any thread)

struct MeshAttribute
{
    QByteArray name;
    int components = 0; // 1 to 4 floats
    quint32 offset = 0; // bytes, in the record of `stride`
};

// The interleaved f32 records of a mesh's vertices, its instance stream, or an instance stream: a stride and its
// attributes, each inside the record.
struct RecordLayout
{
    quint32 stride = 0;
    QList<MeshAttribute> attributes;

    bool valid() const { return stride > 0 && !attributes.isEmpty(); }
    const MeshAttribute *attribute(const QByteArray &name) const;
    QJsonObject toJson() const;
};
// {"stride": bytes, "attributes": [{"name", "components", "offset"}, ...]}; false with the reason.
bool parseRecordLayout(const QJsonValue &value, RecordLayout *out, const QString &label, QString *error);

// A count or a selector (D15 point 1): a number, or the name of a record u32 scalar or a setting; `mesh` for a vertex count
// that is the mesh's.
struct DrawCount
{
    enum class Kind { Number = 0, Named = 1, Mesh = 2 };
    Kind kind = Kind::Number;
    quint32 number = 0;
    QByteArray name;

    QJsonValue toJson() const;
};
bool parseDrawCount(const QJsonValue &value, bool meshAllowed, DrawCount *out);

enum class StreamKind { Instance = 0, Storage = 1, Indirect = 2 };
QString streamKindName(StreamKind kind);

struct StreamDeclaration
{
    QByteArray name;
    QByteArray field;          // the record's array field (f32, or u32 for storage and indirect)
    StreamKind kind = StreamKind::Storage;
    RecordLayout layout;       // an instance stream's records
    // D15 point 4 (the lead, 15 Nov): an f32 stream's used length, a record u32 scalar counting the field's f32
    // elements, with an at_most rule no larger than the field's count; only those bytes are written each record (a
    // variable-length consumer never pays the capacity). Required for an f32 field, refused for a u32 one.
    QByteArray used;
    quint32 capacity = 0;      // derived at the check: the field's bytes

    QJsonObject toJson() const;
};
// {"name", "field", "kind": "instance" | "storage" | "indirect", "layout"?: {...} (instance only), "used"?: a u32
// field (an f32 field's used elements)}.
bool parseStreamDeclaration(const QJsonValue &value, StreamDeclaration *out, QString *error);
// Why the record's `field` cannot feed `stream` (empty: it can): an array of f32 or u32 (indirect: u32 in fours), a
// whole number of an instance stream's records.
QString streamFieldFits(const StreamDeclaration &stream, const frame_abi::Field &field);
// Why `stream`'s used length does not fit (empty: it does): an f32 field names a u32 scalar `used` whose at_most rule
// bounds it within the field's count; a u32 field names none. `used` is null when the schema has no such field.
QString streamUsedFits(const StreamDeclaration &stream, const frame_abi::Field &field, const frame_abi::Field *used);

// A full blend declaration (D15 point 1): {"color": [op, src, dst], "alpha": [op, src, dst]}.
bool parseBlendObject(const QJsonValue &value, QRhiGraphicsPipeline::TargetBlend *out);
QJsonObject blendJson(const QRhiGraphicsPipeline::TargetBlend &blend);

// D15 point 3 (GPU-free; rendering/native/streams.py mirrors it): each block's offset at `alignment` (a power of two, or
// 1), and the arena's size.
struct ArenaLayout
{
    QList<quint32> offsets;
    quint32 size = 0;
};
ArenaLayout arenaLayout(const QList<quint32> &sizes, int alignment);

// ------------------------------------------------------------------------------------------- the GUI thread's meshes

// A mesh's bytes as the core holds them until the render thread uploads them. Counted while alive.
struct MeshImage
{
    const QByteArray vertices;
    const QByteArray instances;

    MeshImage(const QByteArray &vertices, const QByteArray &instances);
    ~MeshImage();
    MeshImage(const MeshImage &) = delete;
    MeshImage &operator=(const MeshImage &) = delete;
};

struct ModeMesh
{
    QByteArray name;
    quint64 generation = 0;           // process-wide, never reused
    RecordLayout vertexLayout;
    RecordLayout instanceLayout;      // invalid: no instance stream
    quint32 vertexCount = 0;
    quint32 instanceCount = 0;
    QSharedPointer<MeshImage> image;  // the core's copy, until the render thread takes it

    QJsonObject toJson() const;
};
// GUI thread: a mesh from its declaration ({"vertices": layout, "instances"?: layout}) and bytes; refused with the reason
// (a bad name, layout or byte count, past kMaxMeshBytes, the built-in name).
bool makeModeMesh(const QByteArray &name, const QByteArray &declaration, const QByteArray &vertices,
                  const QByteArray &instances, ModeMesh *out, QString *error);

// ------------------------------------------------------------------------------------------- process-wide counts

struct MeshBufferCounts
{
    int meshes = 0;            // mesh buffers resident (vertex and instance buffers counted once per mesh)
    qint64 meshBytes = 0;
    int meshImages = 0;        // the core's copies not yet uploaded
    qint64 meshImageBytes = 0;
    qint64 meshUploads = 0;
    int streams = 0;           // stream buffers
    qint64 streamBytes = 0;    // their capacity (a Dynamic one counts once; QRhi keeps one per frame slot on Vulkan)
    qint64 streamWrites = 0;   // stream writes recorded
    qint64 streamBytesWritten = 0;
    int arenas = 0;
    qint64 arenaBytes = 0;
    qint64 arenaWrites = 0;
    qint64 buffersCreated = 0; // every QRhiBuffer this file created (the no-allocation proof: flat in a steady minute)
    qint64 indirectDraws = 0;  // drawIndirect calls recorded
    qint64 batchedIndirect = 0; // batched passes recorded as one multi-draw (D15 point 6, form 3)
    qint64 batchedLoop = 0;     // batched passes recorded as one draw a batch (form 2)
    // The stream ring's CPU axis (D15 point 7): the render thread's time in the drawn records of a stream-bound
    // content (the whole record, the batch QRhi runs at the pass's begin included) and in their stream and arena
    // writes alone, summed; the harness reads the differences over a counted run. Timed with the record's own timer
    // (N3.8's), so nothing is added at rest.
    qint64 recordsTimed = 0;
    qint64 recordNs = 0;
    qint64 streamWriteNs = 0;
};
MeshBufferCounts meshBufferCounts();
void countIndirectDraw();
void countBatched(bool indirect);
void countRecordTime(qint64 recordNs, qint64 streamWriteNs);

// Harness controls (each the negative control of one proof; process-wide, the harness's only).
// - hide the draw-parameters features: a batched pass is recorded one draw a batch on every device;
// - a direct draw's firstInstance (0 by the rule; 3 shows QRhi's OpenGL backend ignores it);
// - every stream recreated at each record (the no-allocation proof's control);
// - the content's release skips its meshes (the retirement proof's control: counts left above zero).
void setHideDrawParameters(bool hide);
bool hideDrawParameters();
void setDirectFirstInstance(quint32 first);
quint32 directFirstInstance();
void setRecreateStreams(bool recreate);
bool recreateStreams();
void setSkipMeshRelease(bool skip);
bool skipMeshRelease();

// The draw-parameters forms this device can record (D15 point 6): DrawIndirect, DrawIndirectMulti and
// ShaderDrawParameters, less the harness control.
bool drawParametersAvailable(QRhi *rhi);

// ------------------------------------------------------------------------------------------- render thread

// A content's meshes, as uploaded (and the built-in quad).
class ModeMeshes
{
public:
    struct Gpu
    {
        QByteArray name;
        quint64 generation = 0;
        RecordLayout vertexLayout;
        RecordLayout instanceLayout;
        quint32 vertexCount = 0;
        quint32 instanceCount = 0;
        std::unique_ptr<QRhiBuffer> vertices;
        std::unique_ptr<QRhiBuffer> instances;
        qint64 bytes = 0;
    };

    ModeMeshes() = default;
    ~ModeMeshes();
    ModeMeshes(const ModeMeshes &) = delete;
    ModeMeshes &operator=(const ModeMeshes &) = delete;

    // At a record: a mesh the item no longer holds goes; a drawn mesh with a new generation is uploaded into `updates`
    // (its image taken through `take`); the built-in quad is made once, when a pass draws it (`quad`). `lost` names the
    // drawn meshes with no image to upload from (a content made again). False with the reason when a buffer could not
    // be created (that mesh lost).
    template <typename Take>
    void sync(QRhi *rhi, QRhiResourceUpdateBatch *updates, const QList<ModeMesh> &drawn, Take take, QStringList *lost,
              bool quad);
    const Gpu *find(const QByteArray &name) const;
    bool uploadedThisRecord() const { return m_uploaded; }
    quint64 objects() const { return m_objects; } // a buffer made or gone (the latch key and the still signature)
    int live() const;
    void release();
    QJsonArray stateJson() const;

private:
    bool upload(QRhi *rhi, QRhiResourceUpdateBatch *updates, Gpu &gpu, const ModeMesh &mesh,
                const QSharedPointer<MeshImage> &image, QStringList *lost);
    bool ensureQuad(QRhi *rhi, QRhiResourceUpdateBatch *updates);
    void releaseGpu(Gpu &gpu);

    Gpu m_meshes[kMaxModeMeshes + 1]; // the item's, and the built-in quad (the last)
    quint64 m_objects = 0;
    bool m_uploaded = false;
};

// A content's streams and block arena.
class ModeStreams
{
public:
    struct Stream
    {
        StreamDeclaration decl;
        const frame_abi::Field *field = nullptr; // into the schema the streams hold (m_schema: audit 4 H1)
        const frame_abi::Field *usedField = nullptr; // an f32 stream's used length (D15 point 4), the same
        std::unique_ptr<QRhiBuffer> buffer;
        QByteArray staging;                       // a storage stream's bytes, kept across records (D15 point 4)
        quint32 used = 0;                         // bytes written by the last record
    };

    ModeStreams() = default;
    ~ModeStreams();
    ModeStreams(const ModeStreams &) = delete;
    ModeStreams &operator=(const ModeStreams &) = delete;

    // At a build: one buffer per declared stream, sized from its field, and the arena of `arenaBytes` (0: none). The
    // streams hold `schema` (shared: their fields point into it) until they are released. False with the reason (the
    // content's failure).
    bool build(QRhi *rhi, const QList<StreamDeclaration> &streams, const QSharedPointer<const RuntimeSchema> &schema,
               quint32 arenaBytes, quint32 indirectBatchBytes, QString *error);
    // Whether the streams were built for a schema of `schema`'s layout (the same table, or the same fingerprint);
    // false: the content builds them again (audit 4 H1). Nothing is allocated.
    bool builtFor(const RuntimeSchema *schema) const;
    // At a record that draws: each stream's bytes from the record: an f32 stream's used elements (its used-length
    // field, at most its capacity; none written at 0), a u32 stream's whole field.
    void write(QRhi *rhi, QRhiResourceUpdateBatch *updates, const QByteArray &record);
    // The arena written whole from `bytes` (its size), the fast path.
    void writeArena(const QByteArray &bytes);
    // A batched pass's indirect commands (form 3), the fast path into the content's own indirect buffer.
    void writeBatchCommands(const char *bytes, quint32 size);

    QRhiBuffer *arena() const { return m_arena.get(); }
    QRhiBuffer *batchCommands() const { return m_batchCommands.get(); }
    const Stream *find(const QByteArray &name) const;
    int live() const;
    quint64 generation() const { return m_generation; } // a build made new buffers (the bindings name them)
    void release();
    QJsonObject stateJson() const;

private:
    QList<Stream *> m_streams;  // owned (Qt containers only)
    QSharedPointer<const RuntimeSchema> m_schema; // the schema they were built from (audit 4 H1)
    std::unique_ptr<QRhiBuffer> m_arena;
    std::unique_ptr<QRhiBuffer> m_batchCommands;
    quint32 m_arenaBytes = 0;
    quint64 m_generation = 0;
};

// --------------------------------------------------------------------------------------- ModeMeshes::sync (template)

void meshesCountUpload();

template <typename Take>
void ModeMeshes::sync(QRhi *rhi, QRhiResourceUpdateBatch *updates, const QList<ModeMesh> &drawn, Take take,
                      QStringList *lost, bool quad)
{
    m_uploaded = false;
    if (quad)
        ensureQuad(rhi, updates);                 // only for a program that draws it (none of N2.9's or N3.1's)
    // The retire path: a mesh the item no longer holds goes now.
    for (int i = 0; i < kMaxModeMeshes; ++i) {
        Gpu &gpu = m_meshes[i];
        if (gpu.name.isEmpty())
            continue;
        bool held = false;
        for (const ModeMesh &mesh : drawn)
            held = held || mesh.name == gpu.name;
        if (!held)
            releaseGpu(gpu);
    }
    for (const ModeMesh &mesh : drawn) {
        Gpu *gpu = nullptr;
        Gpu *freeSlot = nullptr;
        for (int i = 0; i < kMaxModeMeshes; ++i) {
            if (m_meshes[i].name == mesh.name)
                gpu = &m_meshes[i];
            else if (!freeSlot && m_meshes[i].name.isEmpty())
                freeSlot = &m_meshes[i];
        }
        if (gpu && gpu->generation == mesh.generation)
            continue;                             // uploaded: nothing again at rest
        const QSharedPointer<MeshImage> image = take(mesh.name);
        if (!image) {
            lost->append(QString::fromLatin1(mesh.name));
            continue;
        }
        if (!gpu)
            gpu = freeSlot;
        if (!gpu) {
            lost->append(QString::fromLatin1(mesh.name));
            continue;
        }
        upload(rhi, updates, *gpu, mesh, image, lost);
    }
}

} // namespace srpss_core
