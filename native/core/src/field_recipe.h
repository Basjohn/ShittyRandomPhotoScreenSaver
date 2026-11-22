// Field recipes (ABI 43, Current_Plan.md N5.2g with N4.g; D9 point 2, consumer class (a)): a transition's per-run
// fields (Edge Bloom's edge fields, Capillary Bloom's propagation field) as item textures made from a recipe, not from
// pixels, so the job service can make them off the frame and the frame can make them when it cannot.
//
// - A recipe is plain data the Python owner builds from the field's own compute texts and values
//   (rendering/quick/scene3d/edge_field.py, propagation_field.py): its packs (compute .qsb from tools/regen_qrc.py), its
//   blocks (std140 bytes Python packed with the same layout its GLSL declares), its images ({"name", "format" r16f, r32f,
//   rgba16f, rgba32f or rgba8, "size": [w, h]}), a flat list of dispatches ({"pack", "block" (-1: none), "groups":
//   [x, y, z], "bindings": {shader name: {"image", "access"} or "input"}}) and its outputs ({"image", "texture"}: each an
//   item texture of the image's format, rgba16f, rgba32f or r32f). "input" names the item texture the recipe samples
//   (a sampler2D, linear and clamped, no mips: the photograph); absent when it samples none. A flat list needs no repeat
//   or per-dispatch scoping: 192 relax dispatches are 192 entries over two packs and one block.
// - Admission (fromJson, any thread, GPU-free): every pack a compute shader on descriptor set 0 with at most one uniform
//   block, no storage block, separate image or sampler, or push constant; every reflected image bound by name to a recipe
//   image of its format (image2D), its access fitting the shader's qualifiers; every sampler bound to "input"; the block's
//   bytes from its reflected size to that size rounded up to 16; every binding name declared; counts bounded.
// - The recorder (FieldRecorder, one QRhi: the job's or Qt's) records a recipe as one QRhi compute pass a dispatch (D16
//   choice A: every dispatch is a hazard boundary, QRhi derives the barriers), its images made for the record (scratch
//   ones released after it, deleteLater), its blocks in one Static uniform buffer at ubufAligned offsets uploaded once,
//   the bindings made once per distinct set, the pipelines kept per pack and binding kinds for the recorder's life
//   (their layouts made over the recorder's own placeholders, never over a record's resources). The outputs go to the
//   caller. The same recorder is the job form (job_service.cpp) and the in-frame form (mode_content.cpp), so both write
//   the same outputs (D9 point 5): async changes when the work happens, never what is drawn.
#pragma once

#include "compute_passes.h"
#include "rhi_owned.h"

#include <QtCore/QByteArray>
#include <QtCore/QJsonObject>
#include <QtCore/QList>
#include <QtCore/QSize>
#include <QtCore/QString>
#include <rhi/qrhi.h>
#include <rhi/qshader.h>

#include <memory>
#include <vector>

namespace srpss_core {

enum class ModeTextureFormat; // mode_content.h

constexpr int kMaxFieldPacks = 8;
constexpr int kMaxFieldBlocks = 64;
constexpr int kMaxFieldBlockBytes = 4096;
constexpr int kMaxFieldImages = 8;
constexpr int kMaxFieldDispatches = 512;
constexpr int kMaxFieldOutputs = 4;
constexpr int kMaxFieldImageSide = 8192;
constexpr qint64 kMaxFieldImageBytes = qint64(256) << 20; // every image of a recipe together
constexpr quint32 kMaxFieldGroups = 65535;
constexpr int kMaxFieldDeadlineMs = 60000;

struct FieldImage
{
    QByteArray name;
    QRhiTexture::Format format = QRhiTexture::RGBA8;
    QSize size;
};

struct FieldBinding
{
    QByteArray name;          // the shader's image or sampler
    bool input = false;       // the recipe's input photograph (a sampler2D)
    int image = -1;           // or the recipe image it binds
    StorageAccess access = StorageAccess::Read;
    int binding = -1;         // reflected
};

struct FieldDispatch
{
    int pack = -1;
    int block = -1;           // the recipe block it reads (-1: the shader declares none)
    int blockBinding = -1;    // reflected
    int blockSize = 0;        // reflected
    quint32 groups[3] = { 1, 1, 1 };
    QList<FieldBinding> bindings;
};

struct FieldOutput
{
    int image = -1;
    QByteArray texture;       // the item texture it becomes
};

struct FieldRecipe
{
    QList<QShader> packs;
    QList<quint64> packKeys;  // each pack's bytes' hash (the recorder's pipeline key)
    QList<QByteArray> blocks;
    QList<FieldImage> images;
    QList<FieldDispatch> dispatches;
    QList<FieldOutput> outputs;
    QByteArray input;         // the item texture sampled (empty: none)

    // The recipe from its declaration and its packs and blocks (the header's admission); false with the reason.
    static bool fromJson(const QByteArray &json, const QList<QByteArray> &packs, const QList<QByteArray> &blocks,
                         FieldRecipe *out, QString *error);
    QJsonObject toJson() const;
    qint64 imageBytes() const;            // every image's bytes
    qint64 outputBytes(int output) const; // one output's bytes
    // An output's mode texture format (rgba16f, rgba32f or r32f; admission refuses any other).
    ModeTextureFormat outputFormat(int output) const;
    QSize outputSize(int output) const;
};

// Process-wide counts (the destruction barrier's and the proofs' reading).
struct FieldCounts
{
    qint64 recorded = 0;      // recipes recorded (both forms)
    qint64 dispatches = 0;    // their dispatches
    qint64 pipelines = 0;     // pipelines made (flat once warm)
    int recorders = 0;        // recorders holding pipelines
};
FieldCounts fieldCounts();
QJsonObject fieldCountsJson();

// The recorder's outputs, in the recipe's output order (each the caller's).
struct FieldOutputs
{
    RhiOwned<QRhiTexture> textures[kMaxFieldOutputs];
};

class FieldRecorder
{
public:
    FieldRecorder() = default;
    ~FieldRecorder();
    FieldRecorder(const FieldRecorder &) = delete;
    FieldRecorder &operator=(const FieldRecorder &) = delete;

    // Records `recipe` on `cb` (outside any pass), sampling `input` where the recipe names one. `*pending` (may be null)
    // is the record's resource updates: the recipe's block upload joins it and the first compute pass takes it (then
    // `*pending` is null). False with the reason: nothing was recorded and `*pending` is as it was (its uploads stand).
    bool record(QRhi *rhi, QRhiCommandBuffer *cb, const FieldRecipe &recipe, QRhiTexture *input,
                QRhiResourceUpdateBatch **pending, FieldOutputs *out, QString *error);
    // The pipelines and placeholders go (the QRhi's invalidation, the content's release, the job QRhi's teardown).
    void release();
    int pipelines() const { return int(m_pipes.size()); }

private:
    struct Pipe
    {
        quint64 key = 0;
        RhiOwned<QRhiComputePipeline> pipeline;
        RhiOwned<QRhiShaderResourceBindings> layout;
    };
    bool ensurePlaceholders(QRhi *rhi, QString *error);
    QRhiComputePipeline *pipelineFor(QRhi *rhi, const FieldRecipe &recipe, const FieldDispatch &d, QString *error);

    QRhi *m_rhi = nullptr;
    RhiOwned<QRhiSampler> m_sampler;          // the input's: linear, clamped, no mips
    RhiOwned<QRhiTexture> m_placeholder;      // a 1 x 1 load-store texture the layouts are made over
    RhiOwned<QRhiBuffer> m_placeholderBlock;  // a uniform buffer of kMaxFieldBlockBytes the layouts are made over
    std::vector<std::unique_ptr<Pipe>> m_pipes;
    bool m_counted = false;
};

// GPU-free: the admission of a recipe (`json`, `packs`, `blocks`) as JSON: {"ok", "error"?, "recipe"?} (the reflected
// bindings per dispatch). tests/test_native_field_recipe.py.
QByteArray fieldRecipeCheckJson(const QByteArray &json, const QList<QByteArray> &packs, const QList<QByteArray> &blocks);

} // namespace srpss_core
