// Compute passes (Current_Plan.md item 8b, N3.3; decision D16 in Docs/Future_Work/Native_Core_P3_Decisions.md): the
// storage a program's compute entries write and its draws read, and what one compute entry declares.
//
// - A compute entry (D16 point 1) is a pass of the program's list with "compute": true and one compute pack (the
//   product's .comp, baked by tools/regen_qrc.py). It declares its own block (in the block arena, D15 point 3), its
//   group counts ("groups": three counts, each a number or a name the record or the settings fill, or {"over": a
//   resource}: the resource's extent over the pack's reflected local size, rounded up), its trigger (point 7) and its
//   bindings by the shader's names, each with its access. It is recorded at its place in the list as its own QRhi
//   compute pass (D16 choice A), outside any render pass, and only when its trigger has new work.
// - The storage (D16 point 2, choices B, C, L): a program declares storage buffers ({"name", "bytes": a number or a
//   setting, "usage"?: ["vertex", "indirect"], "layout"?: a record layout for its use as per-instance input}) and
//   storage images ({"name", "dimensions": 2 or 3, "format": rgba8, rgba16f, rgba32f, r16f or r32f, "size": [w, h] or
//   [w, h, d]}, the size set again by Python at a size edge). Both are QRhi Static GPU-resident objects of the content
//   (ModeStorage), created zeroed: a buffer by the core's clear kernel, an image by one upload of zeros, at its
//   allocation edge only. A buffer whose size changes keeps its prefix through the core's copy kernel (QRhi has no
//   buffer copy and no buffer clear); any other change makes it again, zeroed. The storage survives a pipeline rebuild
//   and a new program that declares it the same way, and so does each entry's history over it (checkpoint audit 5 M2).
//   A program that declares none releases what the last one held through the same delayed release as a resize: at the
//   next record's sync (audit 5 M1). An image is at most kMaxStorageImageBytes (audit 5 L4), and its format is checked
//   against the device's facts only when it is made (L3).
// - The barriers (D16 points 3 and 4): every binding's access maps to QRhi's load, store or load-store binding and is
//   checked against the pack's reflection; QRhi derives every barrier from those bindings at the pass boundaries. The
//   core issues none of its own.
// - The trigger (D16 point 7, choice E): "frame" (a newly accepted record; a re-record of the same one, for the card, the
//   settings or a fade, dispatches nothing) or {"field": a record u32 scalar} (dispatched only when it changes). Fresh
//   is per entry (audit 5 M2): an entry is fresh at its first dispatch and whenever a storage buffer or image it binds
//   was made zeroed since its last dispatch (a prefix copy keeps its source's history); a fresh entry dispatches at the
//   next record. A new program keeps the history of each entry it declares again by name; one whose pack, bindings or
//   trigger changed dispatches at the next record, not fresh. The core member u_srpss_compute (a uvec4) is (the
//   trigger's value, its value at the last dispatch, 1 when fresh, the dispatches before this one since it was fresh).
// - Admission (audit 5 M3): an entry that binds one resource twice with two accesses is refused (QRhi's tracker keeps
//   one access a resource a pass, so the other's barrier would be lost).
// - No readback in the product (D16 point 8): the storage readback here is the harness's.
//
// Render thread only, but the declarations (any thread) and the process-wide counts and controls (any thread).
#pragma once

#include "geometry_arena.h"
#include "mesh_buffers.h"
#include "rhi_owned.h"

#include <QtCore/QAtomicInteger>
#include <QtCore/QByteArray>
#include <QtCore/QHash>
#include <QtCore/QJsonArray>
#include <QtCore/QJsonObject>
#include <QtCore/QJsonValue>
#include <QtCore/QList>
#include <QtCore/QString>
#include <QtCore/QStringList>
#include <rhi/qrhi.h>
#include <rhi/qshader.h>

#include <memory>

namespace srpss_core {

constexpr int kMaxStorageBuffers = 8;
// ABI 33 (N5.4): Waveform with Floor Give on holds 9 (the world field 1, floor give 2, two fog volumes 3 each).
constexpr int kMaxStorageImages = 9;
constexpr int kMaxComputeBindings = 8;
constexpr qint64 kMaxStorageBufferBytes = qint64(256) << 20;
constexpr int kMaxStorageImageSide2D = 16384;
constexpr int kMaxStorageImageSide3D = 2048;
constexpr qint64 kMaxStorageImageBytes = qint64(256) << 20; // audit 5 L4: as a buffer's (every slice, every texel)
// The core's kernels' local size (shaders/storage_clear.comp, storage_copy.comp).
constexpr quint32 kStorageKernelGroup = 256;
// Their block (StorageKernel: the destination's and source's first words, the words, a value, the stride; std140).
constexpr quint32 kKernelBlockBytes = 32;
// At most this many kernel operations (clears and copies) in one record: two per buffer.
constexpr int kMaxStorageEdgeOps = 2 * kMaxStorageBuffers;
extern const char kComputeMember[]; // "u_srpss_compute": a uvec4 (trigger, last trigger, fresh, dispatches)

enum class StorageAccess { Read = 0, Write = 1, ReadWrite = 2 };
QString storageAccessName(StorageAccess access);
bool parseStorageAccess(const QString &text, StorageAccess *out);

// ------------------------------------------------------------------------------------------- declarations (any thread)

struct StorageBufferDeclaration
{
    QByteArray name;
    DrawCount bytes;          // a number, or a setting's name (a record field never sizes a buffer)
    bool vertex = false;      // also a VertexBuffer (a draw reads it per instance through `layout`)
    bool indirect = false;    // also an IndirectBuffer (a draw's commands)
    RecordLayout layout;      // its per-instance attributes (vertex only)
    // ABI 42 (D3, geometry_arena.h): a geometry buffer ({"name", "geometry": {"family", "key"}}): read only, its bytes
    // uploaded once per key from the arena's bank (ModeStorage::syncGeometry), the key read from the record's u32 array
    // field `geometryKey`. A compute entry binds the previous key's buffer as "<name>@previous" (the rebase record).
    bool geometry = false;
    quint32 geometryFamily = 0;
    QByteArray geometryKey;

    bool sameShape(const StorageBufferDeclaration &other) const; // usage and layout (the size may differ)
    QJsonObject toJson() const;
};
bool parseStorageBuffer(const QJsonValue &value, StorageBufferDeclaration *out, QString *error);

struct StorageImageDeclaration
{
    QByteArray name;
    int dimensions = 2;
    QRhiTexture::Format format = QRhiTexture::RGBA8;
    int size[3] = { 1, 1, 1 }; // depth 1 for a 2D image

    bool sameShape(const StorageImageDeclaration &other) const; // dimensions and format (the size may differ)
    bool sameSize(const StorageImageDeclaration &other) const;
    QJsonObject toJson() const;
};
bool parseStorageImage(const QJsonValue &value, StorageImageDeclaration *out, QString *error);
// An image's size from Python (size edge): refused with the reason outside its dimensions' bounds or past
// kMaxStorageImageBytes.
bool storageImageSizeFits(const StorageImageDeclaration &image, const int *size, QString *error);
QString storageFormatName(QRhiTexture::Format format);
bool parseStorageFormat(const QString &text, QRhiTexture::Format *out);
int storageTexelBytes(QRhiTexture::Format format);
// The reflected image format a declared format is written as (QShaderDescription::ImageFormat).
int storageReflectedFormat(QRhiTexture::Format format);

enum class ComputeResource { Buffer = 0, Image = 1, Stream = 2, Mesh = 3 };
QString computeResourceName(ComputeResource kind);

// One binding of a compute entry: the shader's buffer block or image, by name, to a storage buffer, a storage image, a
// storage stream (read only) or a mesh with storage usage (read only).
struct ComputeBinding
{
    QByteArray name;
    QByteArray resource;
    ComputeResource kind = ComputeResource::Buffer;
    StorageAccess access = StorageAccess::Read;
    int binding = -1;         // reflected

    QJsonObject toJson() const;
};

// ABI 37 (N4.i): "draw", a derived kernel of what this record draws (the motion blur's tile max over the velocity the
// passes before it wrote): dispatched at every record that records the program's passes, which for a still (the
// background layer's scene transitions) is every record that draws a changed frame, never at rest. The one trigger a
// still's compute entry may take (a still has no record: "frame" and a field would never or always fire).
struct ComputeTrigger
{
    // ABI 42 (N5.6): "once", dispatched at the entry's first record (fresh storage) and never again (a check).
    enum class Kind { Frame = 0, Field = 1, Draw = 2, Once = 3 };
    Kind kind = Kind::Frame;
    QByteArray field;

    QJsonValue toJson() const;
};
bool parseComputeTrigger(const QJsonValue &value, ComputeTrigger *out);

// ------------------------------------------------------------------------------------------- counts and controls

struct ComputeCounts
{
    int buffers = 0;              // storage buffers resident
    qint64 bufferBytes = 0;
    int images = 0;               // storage images resident
    qint64 imageBytes = 0;
    qint64 dispatches = 0;        // compute dispatches recorded
    qint64 computePasses = 0;     // QRhi compute passes recorded (the kernels' included)
    qint64 skipped = 0;           // compute entries a drawn record did not dispatch (no new work)
    qint64 clears = 0;            // the clear kernel's dispatches
    qint64 copies = 0;            // the copy kernel's dispatches
    qint64 imageZeroUploads = 0;  // images zeroed by an upload
    qint64 objectsCreated = 0;    // every buffer, texture and kernel object this file created (flat at rest)
    qint64 statesLost = 0;        // a content made again found its storage gone (the owner's edge)
    int readbacksPending = 0;     // harness readbacks in flight
    // ABI 42 (D3): geometry residencies (steady one key a family, two during a swap, zero after teardown), uploads (one
    // per key), keys failed (each logged once), residencies released, and records that waited for a first key.
    int geometryResident = 0;
    qint64 geometryUploads = 0;
    qint64 geometryFailed = 0;
    qint64 geometryReleased = 0;
    qint64 geometryWaits = 0;
    // ABI 42 (N5.6): a check entry's one-shot readbacks started, their bytes, and the results reported (each once).
    qint64 checkReadbacks = 0;
    qint64 checkReadbackBytes = 0;
    qint64 checkReports = 0;
};
ComputeCounts computeCounts();
void countDispatch();
void countComputePass();
void countSkipped();
void countStateLost();
void countCheckReadback(quint32 bytes);
void countCheckReport();

// Harness controls (each the negative control of one proof; process-wide, the harness's only):
// - every written binding recorded as a read (QRhi then derives no barrier for the write: read-after-write's control);
// - consecutive dispatching compute entries recorded in one QRhi compute pass (write-after-read's control);
// - every compute entry dispatched at every drawn record (the trigger's control: a stateful pass integrates twice);
// - the content's release skips its storage (the retirement proof's control: counts left above zero).
void setComputeWriteAsRead(bool on);
bool computeWriteAsRead();
void setComputeSinglePass(bool on);
bool computeSinglePass();
void setComputeTriggerEveryRecord(bool on);
bool computeTriggerEveryRecord();
void setSkipStorageRelease(bool on);
bool skipStorageRelease();

// ABI 33 (N5.4): the harness's faked device without linear filtering of 32-bit float formats (rgba32f, r32f): the
// negative control of the linear-filter check below (process-wide, the harness's only).
void setComputeNoFloat32Linear(bool on);
bool computeNoFloat32Linear();

// ABI 33 (N5.4): whether this device filters a storage image of `format` with a linear sampler (Vulkan guarantees no
// linear filtering of 32-bit float formats). On a Vulkan device the core created, its facts read at creation decide
// (VK_FORMAT_FEATURE_SAMPLED_IMAGE_FILTER_LINEAR_BIT: vulkan_context.h linear_filter_formats); on OpenGL every format
// is filterable on desktop GL, and a 32-bit float format on OpenGL ES only with GL_OES_texture_float_linear (the
// context current, render thread); elsewhere (D3D, a device of Qt's own) QRhi has no question for it and the format is
// taken as filterable (D3D11's feature level 10 filters it). False with the reason (`why`, may be null). The
// harness's faked device answers false for rgba32f and r32f.
bool storageImageLinearFilter(QRhi *rhi, QRhiTexture::Format format, QString *why);

// The device's compute facts (QRhi's features and limits; any thread). ABI 33: and linear_filter_formats (per storage
// format, storageImageLinearFilter's answer; OpenGL's needs its context current) and float32_linear_control.
QJsonObject computeDeviceFacts(QRhi *rhi);

// ------------------------------------------------------------------------------------------- harness readback

// One storage resource as read back (harness only): a buffer's bytes, or an image's texels as stored (rows top first,
// slices in order).
struct StoragePixels
{
    QString name;
    QString kind;             // "buffer" or "image"
    QString format;           // "bytes" for a buffer
    int size[3] = { 0, 0, 0 };
    QByteArray data;
};

// ABI 42 (N5.6), the one named exception to "nothing in the product reads storage back": a check entry's results
// ("readback" on a "once" entry, at most kMaxCheckReadbackBytes), read once after its dispatch. QRhi completes it
// at a later frame; the content takes it at a later record (never waited on) and reports it once (state and log).
// Held by the source too, so a content released first leaves QRhi's completion nothing dangling.
constexpr quint32 kMaxCheckReadbackBytes = 4096;
struct CheckReadback
{
    QByteArray entry;
    QByteArray buffer;
    quint32 bytes = 0;
    QRhiReadbackResult result;
    QAtomicInteger<int> done { 0 };
};

// Written by QRhi at a frame's end (each result's completion), read by the GUI thread once done. Allocated only when the
// harness asks for a readback.
struct StorageReadback
{
    QList<StoragePixels> items;
    QList<int> firstResult;   // per item, its first result (an image has one per slice)
    QList<int> resultCount;
    std::unique_ptr<QRhiReadbackResult[]> results;
    int count = 0;
    QAtomicInteger<int> pending { 0 };
    bool done() const { return pending.loadAcquire() == 0; }
    // The items with their bytes (a 3D image's slices joined in order).
    QList<StoragePixels> take() const;
};

// ------------------------------------------------------------------------------------------- render thread

class ModeStorage
{
public:
    struct Buffer
    {
        StorageBufferDeclaration decl;
        quint32 bytes = 0;
        RhiOwned<QRhiBuffer> buffer;
        quint64 fresh = 0;    // the storage serial it was made zeroed at (a resize's prefix copy keeps its source's)
    };
    struct Image
    {
        StorageImageDeclaration decl;
        RhiOwned<QRhiTexture> texture;
        qint64 bytes = 0;
        quint64 fresh = 0;    // the storage serial it was made zeroed at
    };

    ModeStorage() = default;
    ~ModeStorage();
    ModeStorage(const ModeStorage &) = delete;
    ModeStorage &operator=(const ModeStorage &) = delete;

    // At a record: the declared buffers (sizes resolved from `settings`) and images (sizes as set) made, kept or made
    // again; the new ones zeroed and a resized buffer's prefix copied (queued as kernel operations for `recordEdges`;
    // an image's zeros into `updates`). `fresh` is set when any resource was made zeroed (the content's lost edge; each
    // entry's own fresh is freshOf). False with the reason (the content's failure: nothing is drawn, the storage stays
    // as it was). A record whose declarations are all kept returns before any allocation (audit 5 L1).
    bool sync(QRhi *rhi, QRhiResourceUpdateBatch *updates, const QList<StorageBufferDeclaration> &buffers,
              const QList<StorageImageDeclaration> &images, const QHash<QByteArray, double> &settings, bool *fresh,
              QString *error);
    // The queued kernel operations, each its own QRhi compute pass (D16 choice A); `updates` (may be null) goes with
    // the first. Returns the batch when nothing was recorded (the caller hands it to its first pass).
    QRhiResourceUpdateBatch *recordEdges(QRhi *rhi, QRhiCommandBuffer *cb, QRhiResourceUpdateBatch *updates);
    bool hasEdges() const { return m_opCount > 0; }
    bool uploadedAtSync() const { return m_uploaded; } // the last sync put an image's zeros into its batch

    const Buffer *buffer(const QByteArray &name) const;
    const Image *image(const QByteArray &name) const;
    // The serial a buffer or image was last made zeroed at (0: none of that name); an entry is fresh when the largest
    // over its bindings changed since its last dispatch (audit 5 M2).
    quint64 freshOf(ComputeResource kind, const QByteArray &name) const;
    quint64 objects() const { return m_objects; } // a buffer or image made or gone (the bindings follow)
    int live() const;
    // Declared resources held (the lost edge's "held").
    bool holds() const { return !m_buffers.isEmpty() || !m_images.isEmpty(); }
    // Nothing held at all: no resource, no replaced buffer awaiting its release, no kernel (audit 5 M1: a sync is still
    // needed while any is held, so a program without storage releases the last one's).
    // ABI 42: the geometry residencies count (a program without storage still syncs while they remain).
    bool empty() const {
        return !holds() && m_retiring.isEmpty() && !m_clear && !m_copy && !m_opBlocks && m_geometry.isEmpty()
            && m_geometryRetiring.isEmpty();
    }
    void release();
    QJsonObject stateJson() const;

    // Harness: every buffer and image read back into `updates` (an image slice by slice).
    std::shared_ptr<StorageReadback> startReadback(QRhiResourceUpdateBatch *updates) const;

    // ABI 42 (D3, geometry_arena.h): at a record, each geometry buffer's key (`keys`, from the record) made resident:
    // a key it holds changes nothing; a new key is read whole from `arena` and uploaded into a new buffer (one upload
    // per key), the old key's kept as "<name>@previous" until a frame using the new one was recorded (geometryRecorded),
    // never released before its replacement exists. A key the arena does not hold yet (absent or torn) is asked again at
    // the next record, the old one still drawn; a key that fails (its object, or an invalid bank) is `failed`: logged
    // once, never retried, the old one still drawn. `changed`: a buffer the bindings name is new (they are made
    // again); `waiting`: a geometry buffer has no resident key at all (the content keeps its frame: never an empty one).
    // No arena yet waits as an absent key. False is reserved for a declaration it cannot serve (`error`: none today).
    bool syncGeometry(QRhi *rhi, QRhiResourceUpdateBatch *updates, const GeometryArena *arena,
                      const QList<StorageBufferDeclaration> &declared, const QHash<QByteArray, GeometryKey> &keys,
                      bool *changed, bool *waiting, QString *error);
    // A frame drawing every current key was recorded: each previous key's residency goes (released at the next sync, a
    // frame after the record that used it last).
    void geometryRecorded();
    // Every geometry residency goes (D3 point 3: mode or activation change, drop, retire, device loss, the content's
    // release).
    void releaseGeometry();
    int geometryResidencies() const;

private:
    struct GeometrySlot
    {
        QByteArray name;
        quint32 family = 0;
        Buffer *current = nullptr;
        GeometryKey currentKey;
        Buffer *previous = nullptr;
        GeometryKey previousKey;
        QList<GeometryKey> failed;    // keys never retried
    };
    void releaseGeometryBuffer(Buffer *b);
    QList<GeometrySlot *> m_geometry;
    QList<Buffer *> m_geometryRetiring;
    QList<StorageBufferDeclaration> m_declaredSource; // sync's declared list (shared), and its buffers other than geometry
    QList<StorageBufferDeclaration> m_plainBuffers;
    struct Op
    {
        bool copy = false;
        QRhiBuffer *dst = nullptr;
        QRhiBuffer *src = nullptr;
        quint32 dstWord = 0;
        quint32 srcWord = 0;
        quint32 words = 0;
    };
    // Every declaration matches what is held (sizes resolved from `settings`) and nothing waits for a release: the
    // record's sync has no work (no allocation, audit 5 L1).
    bool unchanged(const QList<StorageBufferDeclaration> &buffers, const QList<StorageImageDeclaration> &images,
                   const QHash<QByteArray, double> &settings) const;
    bool ensureKernels(QRhi *rhi, QString *error);
    void releaseKernels();
    void releaseBuffer(Buffer *b);
    void releaseImage(Image *i);

    QList<Buffer *> m_buffers;          // owned (Qt containers only)
    QList<Image *> m_images;
    QList<Buffer *> m_retiring;         // replaced buffers, released at the next record's sync (after their copy ran)
    QRhi *m_rhi = nullptr;              // the QRhi the storage was made on (the skipped-release control's key)
    Op m_ops[kMaxStorageEdgeOps];
    int m_opCount = 0;
    bool m_uploaded = false;
    quint64 m_objects = 0;
    quint64 m_freshSerial = 0;          // bumped by every buffer or image made zeroed
    // The kernels (made at the first edge that needs them): their pipelines, a block per operation in one Dynamic
    // uniform buffer, and a bindings object per operation (made at the edge, released after it).
    QRhi *m_kernelRhi = nullptr;
    RhiOwned<QRhiComputePipeline> m_clear;
    RhiOwned<QRhiComputePipeline> m_copy;
    RhiOwned<QRhiShaderResourceBindings> m_clearLayout;
    RhiOwned<QRhiShaderResourceBindings> m_copyLayout;
    RhiOwned<QRhiBuffer> m_opBlocks;
    RhiOwned<QRhiBuffer> m_dummy;  // a 16-byte storage buffer the layouts are made over
    RhiOwned<QRhiShaderResourceBindings> m_opBindings[kMaxStorageEdgeOps];
    quint32 m_opStride = 0;
};

} // namespace srpss_core
