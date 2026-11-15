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
//   and a new program that declares it the same way.
// - The barriers (D16 points 3 and 4): every binding's access maps to QRhi's load, store or load-store binding and is
//   checked against the pack's reflection; QRhi derives every barrier from those bindings at the pass boundaries. The
//   core issues none of its own.
// - The trigger (D16 point 7, choice E): "frame" (a newly accepted record; a re-record of the same one, for the card, the
//   settings or a fade, dispatches nothing) or {"field": a record u32 scalar} (dispatched only when it changes). The
//   storage made again is fresh: the next record dispatches every entry. The core member u_srpss_compute (a uvec4) is
//   (the trigger's value, its value at the last dispatch, 1 when fresh, the dispatches since the storage was made).
// - No readback in the product (D16 point 8): the storage readback here is the harness's.
//
// Render thread only, but the declarations (any thread) and the process-wide counts and controls (any thread).
#pragma once

#include "mesh_buffers.h"

#include <QtCore/QAtomicInteger>
#include <QtCore/QByteArray>
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
constexpr int kMaxStorageImages = 8;
constexpr int kMaxComputeBindings = 8;
constexpr qint64 kMaxStorageBufferBytes = qint64(256) << 20;
constexpr int kMaxStorageImageSide2D = 16384;
constexpr int kMaxStorageImageSide3D = 2048;
// The core's kernels' local size (shaders/storage_clear.comp, storage_copy.comp).
constexpr quint32 kStorageKernelGroup = 256;
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
// An image's size from Python (size edge): refused with the reason outside its dimensions' bounds.
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

struct ComputeTrigger
{
    enum class Kind { Frame = 0, Field = 1 };
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
};
ComputeCounts computeCounts();
void countDispatch();
void countComputePass();
void countSkipped();
void countStateLost();

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

// The device's compute facts (QRhi's features and limits; any thread).
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
        std::unique_ptr<QRhiBuffer> buffer;
    };
    struct Image
    {
        StorageImageDeclaration decl;
        std::unique_ptr<QRhiTexture> texture;
        qint64 bytes = 0;
    };

    ModeStorage() = default;
    ~ModeStorage();
    ModeStorage(const ModeStorage &) = delete;
    ModeStorage &operator=(const ModeStorage &) = delete;

    // At a record: the declared buffers (sizes resolved from `settings`) and images (sizes as set) made, kept or made
    // again; the new ones zeroed and a resized buffer's prefix copied (queued as kernel operations for `recordEdges`;
    // an image's zeros into `updates`). `fresh` is set when any resource was made (none kept from before). False with
    // the reason (the content's failure: nothing is drawn, the storage stays as it was).
    bool sync(QRhi *rhi, QRhiResourceUpdateBatch *updates, const QList<StorageBufferDeclaration> &buffers,
              const QList<StorageImageDeclaration> &images, const QHash<QByteArray, double> &settings, bool *fresh,
              QString *error);
    // The queued kernel operations, each its own QRhi compute pass (D16 choice A); `updates` (may be null) goes with
    // the first. Returns the batch when nothing was recorded (the caller hands it to its first pass).
    QRhiResourceUpdateBatch *recordEdges(QRhi *rhi, QRhiCommandBuffer *cb, QRhiResourceUpdateBatch *updates);
    bool hasEdges() const { return m_opCount > 0; }

    const Buffer *buffer(const QByteArray &name) const;
    const Image *image(const QByteArray &name) const;
    quint64 objects() const { return m_objects; } // a buffer or image made or gone (the bindings follow)
    int live() const;
    bool empty() const { return m_buffers.isEmpty() && m_images.isEmpty(); }
    void release();
    QJsonObject stateJson() const;

    // Harness: every buffer and image read back into `updates` (an image slice by slice).
    std::shared_ptr<StorageReadback> startReadback(QRhiResourceUpdateBatch *updates) const;

private:
    struct Op
    {
        bool copy = false;
        QRhiBuffer *dst = nullptr;
        QRhiBuffer *src = nullptr;
        quint32 dstWord = 0;
        quint32 srcWord = 0;
        quint32 words = 0;
    };
    bool ensureKernels(QRhi *rhi, QString *error);
    void releaseKernels();
    void releaseBuffer(Buffer *b);
    void releaseImage(Image *i);

    QList<Buffer *> m_buffers;          // owned (Qt containers only)
    QList<Image *> m_images;
    QList<Buffer *> m_retiring;         // replaced buffers kept until their copy is recorded
    Op m_ops[kMaxStorageEdgeOps];
    int m_opCount = 0;
    quint64 m_objects = 0;
    QByteArray m_zeros;                 // one image slice of zeros, kept for the uploads at an edge
    // The kernels (made at the first edge that needs them): their pipelines, a block per operation in one Dynamic
    // uniform buffer, and a bindings object per operation (made at the edge, released after it).
    QRhi *m_kernelRhi = nullptr;
    std::unique_ptr<QRhiComputePipeline> m_clear;
    std::unique_ptr<QRhiComputePipeline> m_copy;
    std::unique_ptr<QRhiShaderResourceBindings> m_clearLayout;
    std::unique_ptr<QRhiShaderResourceBindings> m_copyLayout;
    std::unique_ptr<QRhiBuffer> m_opBlocks;
    std::unique_ptr<QRhiBuffer> m_dummy;  // a 16-byte storage buffer the layouts are made over
    std::unique_ptr<QRhiShaderResourceBindings> m_opBindings[kMaxStorageEdgeOps];
    quint32 m_opStride = 0;
};

} // namespace srpss_core
