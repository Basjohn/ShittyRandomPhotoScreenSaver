// Scene targets (Current_Plan.md item 8b, N3.1; decision D14 in Docs/Future_Work/Native_Core_P3_Decisions.md): the
// intermediate targets a generic mode's or a fullscreen pass's passes draw into before what reaches the surface, as
// data in its program (mode_content.h). The Python oracle is rendering/quick/scene3d/target.py SceneTarget (colour,
// depth, the HDR intermediate, the mid-scope background() capture) and Bubble's ambient target
// (rendering/quick/visualizer/implementations/bubble_ambient_gl.py: a coverage and a light attachment).
//
// A target is declared by its program: a name; a size (the surface's device pixels, or explicit pixels from Python); 1 to
// 4 named colour attachments (RGBA8, RGBA16F, R16F, R32F; D14 point 4: the HDR intermediate is RGBA16F); a depth (none,
// or one D32F texture: D14 point 5, choice C); a requested sample count (D14 point 7: rendering/gl_programs/scene3d.py
// owns the request, the core's clamp here is the only place it meets a device).
//
// Allocation per size (D14 point 2, choice A): 64 px buckets; the allocation grows at once whenever the needed size passes
// it on either axis, and shrinks only when the needed size falls two or more buckets below it on either axis, decided at
// the size edge (the record that sees a new surface or explicit size), never by a timer. An allocation is made one
// attachment per step (allocateStep: N3.6 schedules the steps as warm-up units; until then the record runs them all).
// The content sits at image rows [H-h, H) and columns [0, w) of the allocation (the Python renderer's GL bottom-left), so
// a read past the content's edge reads what Python's reads; contentViewport gives QRhi's viewport per backend.
//
// Resize (D14 point 3): a new allocation of the same layout re-creates the same QRhi objects at the new size (the
// render-pass descriptor stays: the pipelines are kept, the passes' bindings are made again over the new objects:
// objectGeneration); a new layout (formats, attachments, depth, samples) makes new objects and a new render-pass
// descriptor (layoutGeneration: the pipelines are built again; the content releases them before the old descriptor goes).
//
// Multisampled targets resolve first (D14 point 8): every attachment a sampler or the capture reads gets a resolve
// texture, and a read depth a depth resolve (QRhi::ResolveDepthStencil; refused with the reason where the device lacks
// it: choice E, no workaround). Every target keeps its contents (targets.h rule B, depth too) and is cleared by a draw.
//
// Render thread only, but the counts (any thread) and the readback's results (taken by the GUI thread through
// SceneReadback's own lock).
#pragma once

#include "targets.h"

#include <QtCore/QAtomicInteger>
#include <QtCore/QByteArray>
#include <QtCore/QJsonArray>
#include <QtCore/QJsonObject>
#include <QtCore/QList>
#include <QtCore/QMutex>
#include <QtCore/QRect>
#include <QtCore/QSize>
#include <QtCore/QString>
#include <QtCore/QStringList>
#include <rhi/qrhi.h>

#include <memory>

class QJsonValue;

namespace srpss_core {

constexpr int kMaxSceneTargets = 4;
constexpr int kMaxTargetColour = 4;
constexpr int kSceneBucket = 64;
constexpr int kMaxSceneSamples = 8;

enum class TargetFormat { RGBA8 = 0, RGBA16F = 1, R16F = 2, R32F = 3 };
bool parseTargetFormat(const QString &text, TargetFormat *out);
QString targetFormatName(TargetFormat format);
QRhiTexture::Format targetRhiFormat(TargetFormat format);
int targetFormatBytes(TargetFormat format);

struct TargetAttachment
{
    QByteArray name;
    TargetFormat format = TargetFormat::RGBA8;
    float clear[4] = { 0.0f, 0.0f, 0.0f, 0.0f };
    bool read = false; // derived from the program: a sampler or the capture reads it (a resolve when multisampled)
};

struct TargetDeclaration
{
    QByteArray name;
    QSize size;                       // explicit pixels; empty: the surface's
    QList<TargetAttachment> colour;   // 1 to kMaxTargetColour
    bool depth = false;               // one D32F texture
    bool depthRead = false;           // derived: a sampler or the capture reads the depth (a depth resolve when multisampled)
    int samples = 1;                  // the request (1 to kMaxSceneSamples)
    bool capture = false;             // derived: a capture step reads this target

    bool surfaceSized() const { return size.isEmpty(); }
    // Everything but the size: a change needs new objects and a new render-pass descriptor.
    bool sameLayout(const TargetDeclaration &other) const;
    QJsonObject toJson() const;
    int colourIndex(const QByteArray &attachment) const;
};

// {"name", "size": "surface" | [w, h], "colour": [{"name", "format", "clear"?: [r, g, b, a]}, ...], "depth"?: bool,
// "samples"?: n}; false with the reason.
bool parseTargetDeclaration(const QJsonValue &value, TargetDeclaration *out, QString *error);

// D14 point 2, choice A (GPU-free): the bucket of a size, and the next allocation for `needed` given `current` (empty:
// none yet). `reason` names why it changed ("" when it did not).
int bucketPixels(int pixels);
QSize nextAllocation(const QSize &current, const QSize &needed, QString *reason);
// D14 point 2: QRhi's viewport (x, y from the framebuffer's bottom-left, w, h) of a content of `content` pixels at image
// rows [H-h, H) and columns [0, w) of an allocation of `allocation` pixels. On a Y-up framebuffer (OpenGL, whose core
// targets are flipped by F1 so memory row 0 is the image's top) QRhi's y = H - h; elsewhere y = 0.
QRect contentViewport(bool yUpInFramebuffer, const QSize &allocation, const QSize &content);
// D14 point 7: the largest count in `supported` not above `requested`, 1 when there is none.
int clampSamples(const QList<int> &supported, int requested);
// The harness's control of the clamp (its negative control): counts taken out of every device's supported set.
void setRemovedSampleCounts(const QList<int> &removed);
QList<int> removedSampleCounts();
// QRhi's supported sample counts less the control's.
QList<int> supportedSampleCounts(QRhi *rhi);

// The process's scene targets (lifecycle proofs, composite_live, the destruction barrier's reading).
struct SceneTargetCounts
{
    int targets = 0;       // targets holding objects
    int textures = 0;      // their QRhiTextures (colour, resolves, depth, captures)
    qint64 bytes = 0;      // their bytes (every sample)
    qint64 allocations = 0; // allocations made (a new size or layout)
    qint64 steps = 0;      // allocation steps run
    int readbacksPending = 0;
};
SceneTargetCounts sceneTargetCounts();

// One attachment's pixels as read back (harness only): RGBA8 bytes, half floats or floats as stored, rows in the
// texture's memory order (the image's top first on every backend: F1).
struct SceneTargetPixels
{
    QString name;          // "<target>.<attachment>", "<target>.capture_colour", "<target>.capture_depth"
    QSize size;            // the allocation
    QSize content;         // the content's size inside it (image rows [H-h, H), columns [0, w))
    QString format;
    int samples = 1;       // the target's effective samples (a multisampled attachment is read through its resolve)
    QByteArray data;
};

// A readback of every readable texture of a content's targets: written by QRhi at a frame's end, read by the GUI thread.
struct SceneReadback
{
    QList<SceneTargetPixels> pixels;
    QRhiReadbackResult results[kMaxSceneTargets * (kMaxTargetColour + 2)];
    int count = 0;
    QAtomicInteger<int> pending { 0 };
    bool done() const { return pending.loadAcquire() == 0; }
};

class SceneTargets
{
public:
    struct Target
    {
        TargetDeclaration decl;
        QSize content;        // the needed size (the surface's or the declared)
        QSize allocation;
        int samples = 1;      // effective (clamped)
        std::unique_ptr<QRhiTexture> colour[kMaxTargetColour];
        std::unique_ptr<QRhiTexture> resolve[kMaxTargetColour];
        std::unique_ptr<QRhiTexture> depth;
        std::unique_ptr<QRhiTexture> depthResolve;
        std::unique_ptr<QRhiRenderPassDescriptor> renderPass;
        std::unique_ptr<QRhiTextureRenderTarget> renderTarget;
        std::unique_ptr<QRhiTexture> captureColour;
        std::unique_ptr<QRhiTexture> captureDepth;
        std::unique_ptr<QRhiRenderPassDescriptor> captureRenderPass;
        std::unique_ptr<QRhiTextureRenderTarget> captureTarget;
        int stepsDone = 0;
        int stepsTotal = 0;
        bool newLayout = true; // the next steps make new objects (else re-create the same at the new size)
        qint64 bytes = 0;
        int textures = 0;
        quint64 generation = 0; // a new allocation
        QString lastReason;

        bool ready() const { return stepsDone >= stepsTotal && renderTarget; }
        // The texture a sampler reads for this attachment: the resolve when multisampled.
        QRhiTexture *readable(int colourIndex) const;
        QRhiTexture *readableDepth() const;
    };

    SceneTargets();
    ~SceneTargets();
    SceneTargets(const SceneTargets &) = delete;
    SceneTargets &operator=(const SceneTargets &) = delete;

    // Render thread, at the record: the program's targets and the surface's pixels. Decides each target's allocation
    // (D14 point 2) and effective samples; makes nothing yet (allocateStep does). `relayout`: a render-pass descriptor
    // will go, so the caller releases the pipelines built over it first. False with the reason for a target that cannot
    // exist on this device (a read multisampled depth without QRhi::ResolveDepthStencil, a size past the device's limit).
    bool sync(QRhi *rhi, const QList<TargetDeclaration> &declarations, const QSize &surface, bool *relayout,
              QString *error);
    // Render thread: one step of what sync left (one colour attachment with its resolve, the depth with its resolve, the
    // render target, the capture). True once nothing is left (`done`), false with the reason when an object could not be
    // made (every object of that target goes).
    bool allocateStep(bool *done, QString *error);
    bool complete() const;

    int count() const { return m_count; }
    int indexOf(const QByteArray &name) const;
    Target *target(int index) { return index >= 0 && index < m_count ? m_targets[index].get() : nullptr; }
    const Target *target(int index) const { return index >= 0 && index < m_count ? m_targets[index].get() : nullptr; }
    // The texture a sampler named "<target>.<attachment>" reads (an attachment, "depth", "capture_colour",
    // "capture_depth"); null when there is none.
    QRhiTexture *sampledTexture(const QByteArray &name) const;
    // The textures a run on target `index` loads (its colour attachments; rule C primes them) and its depth.
    QList<QRhiTexture *> loadedColour(int index) const;

    quint64 layoutGeneration() const { return m_layoutGeneration; }
    quint64 objectGeneration() const { return m_objectGeneration; }
    int liveObjects() const;

    // Render thread: every object goes (the content's release).
    void release();

    // Render thread, after the record's passes: a readback of every readable texture (harness only).
    std::shared_ptr<SceneReadback> startReadback(QRhiResourceUpdateBatch *updates);

    // The targets' state (render thread writes it into the source's report).
    QJsonObject stateJson(QRhi *rhi) const;

private:
    void releaseTarget(Target &t);
    bool step(Target &t, int index, QString *error);

    QRhi *m_rhi = nullptr;
    std::unique_ptr<Target> m_targets[kMaxSceneTargets];
    int m_count = 0;
    quint64 m_layoutGeneration = 0;
    quint64 m_objectGeneration = 0;
    qint64 m_allocations = 0;
    qint64 m_steps = 0;
    QList<int> m_supported;
    bool m_resolveDepth = false;
};

} // namespace srpss_core
