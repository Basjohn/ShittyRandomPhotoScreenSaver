// Transparency and post-processing as shared stages (Current_Plan.md item 8b, N3.4; decision D17 in
// Docs/Future_Work/Native_Core_P3_Decisions.md). Each stage is data in a mode's program (mode_content.h's header,
// "Stages"), absent unless declared: a program without it holds no object of it and records nothing of it. The Python
// oracles: rendering/quick/scene3d/target.py (SceneTarget's transparency, composites and HDR tone map), post.py
// (BloomChain) and defocus.py (DefocusLayer).
//
// - Transparency (D17 point 2): a target declared "transparency" of a scene target (scene_targets.h) owns accumulation
//   RGBA16F and coverage R16F (both cleared to 0 by rule B's clearing draw) and borrows its owner's depth and named
//   attachments. Coverage is stored inverted (blend ONE, ONE_MINUS_SRC_COLOR of the fragment's alpha: c' = a + c(1 - a),
//   so 1 - c is the textbook revealage), for precision: half-float steps are finest near 0 (D17 choice B). The resolve
//   step composites it onto the owner's colour 0, premultiplied, per sample when multisampled (choice C;
//   shaders/scene_oit_resolve*.frag).
// - The gate (D17 point 3): the transparency stage is admitted where the per-attachment blend is real and the formats
//   blend: on Vulkan the core's device facts (independentBlend, VK_FORMAT_FEATURE_COLOR_ATTACHMENT_BLEND_BIT on RGBA16F
//   and R16F, sampleRateShading for the per-sample resolve), never QRhi's PerRenderTargetBlending, which Vulkan reports
//   true whatever the device; on OpenGL QRhi's PerRenderTargetBlending (GL 4.0; GL 4.6 guarantees both formats blend;
//   per-sample shading is GL 4.0 core). Elsewhere the transparent passes draw their sorted pack into the owner and the
//   fallback is noted once with its reason (choice D). N3.1's check of differing attachment states reads the same facts
//   (perTargetBlendReal).
// - Bloom (D17 point 4): kBloomLevels RGBA16F textures, one a level (never levels of one texture: QRhi tracks a whole
//   texture), each half the last from the source's allocation (Python's max(1, w / 2)), so the chain follows N3.1's
//   bucket rule through its source; the 13-tap downsample (the first with the bright pass) and the 3x3 tent upsample
//   added onto the larger level (shaders/bloom_*.frag); never generateMips. Its glow (level 0) is "<step>.glow".
// - The composite step (D17 point 5): an ordinary surface pass whose fragment is the core's (shaders/composite_*.frag),
//   its block filled by the one rule (u_target_px and u_fade the core's; u_bloom_strength and u_hdr_exposure the mode's).
// - Defocus (D17 point 6): a "mips" target (the near layer) and a step onto a scene target: QRhi's generateMips on the
//   layer (choice G: admitted for this layer only, as Python's glGenerateTextureMipmap), the clip into a texture at the
//   read level's size, the gather and the highlight sprites onto the scene (shaders/defocus_*). The read level is a
//   member the mode fills (u_defocus_level); the read level's texture and the sprite count are the core's (choice I).
// - The photo environment (N5.2c, N4.j's PhotoEnvironment: rendering/quick/scene3d/environment.py): a step
//   {"name", "environment": <an item texture>, "size": [w, h]} draws the texture, box-filtered by the core's
//   shaders/environment.frag (Python's _COPY_FRAGMENT: 16 bilinear taps a quarter copy texel apart), into an RGBA8
//   texture of that size with a full mip chain, its levels then made by the core's box kernel (mip_chain.h, ABI 36:
//   Python's PhotoEnvironment the same kernel's text, never generateMips); a later sampler reads it as
//   "<step>.environment", with mips. It is drawn only when the texture's front changed (a new image
//   committed, a texture object made again) or its own texture was made again: once per photo, never per record.
//   Python gives the size (environment_size, its one owner) in the declaration.
//
// Render thread only, but the counts and the harness controls (any thread).
#pragma once

#include "scene_targets.h"
#include "mip_chain.h"
#include "rhi_owned.h"

#include <QtCore/QByteArray>
#include <QtCore/QList>
#include <QtCore/QSize>
#include <QtCore/QString>
#include <QtCore/QStringList>
#include <rhi/qrhi.h>
#include <rhi/qshader.h>

#include <memory>

namespace srpss_core {

constexpr int kBloomLevels = 4;            // post.py BLOOM_LEVELS
constexpr int kMaxBloomStages = 2;
constexpr int kMaxDefocusStages = 2;
constexpr int kMaxEnvironmentStages = 2;   // N5.2c: a program's photo environments (Python's two roles)
// fail_allocation's ordinals: a bloom level's texture and target, a defocus step's two, and (N5.2c audit) an
// environment's texture, chain bindings and target, counted on from the same record's sync.
constexpr int kMaxStageAllocationAttempts = 2 * (kMaxBloomStages * kBloomLevels + kMaxDefocusStages)
                                            + 3 * kMaxEnvironmentStages;
constexpr int kMaxStageBuildAttempts = kMaxBloomStages * (2 * kBloomLevels + 3) + kMaxDefocusStages * 8;
constexpr int kMaxEnvironmentSide = 4096;

// A pass entry's stage (mode_content.h ModePass::stage); None for a mode's own pass.
enum class StageKind { None = 0, TransparencyResolve = 1, Bloom = 2, Defocus = 3, Composite = 4, Environment = 5 };
QString stageKindName(StageKind kind);

// The composite step's forms (D17 point 5): target.py's overlay, overlay with glow (and the HDR tone map), opaque
// with glow, and (N5.2c) opaque without one (the 3D transitions' scenes without bloom: target.py's scene_composite and
// scene_composite_samples, the multisampled scene read through its resolve, D5.6 row 7).
enum class CompositeForm { Overlay = 0, OverlayGlow = 1, OpaqueGlow = 2, Opaque = 3 };
bool parseCompositeForm(const QString &text, CompositeForm *out);
QString compositeFormName(CompositeForm form);

// The core's embedded stage shaders (shaders/*.frag, baked by CMake as every core shader).
QShader compositeShader(CompositeForm form);
QShader transparencyResolveShader(bool multisampled, bool firstSampleControl);
enum class BloomShader { DownFirst = 0, Down = 1, Up = 2 };
QShader bloomShader(BloomShader which);
enum class DefocusShader { Clip = 0, Gather = 1, SpritesVertex = 2, SpritesFragment = 3 };
QShader defocusShader(DefocusShader which);
QShader environmentShader();               // N5.2c: shaders/environment.frag
constexpr char kCompositeBlock[] = "SceneComposite";
constexpr char kDefocusBlock[] = "SceneDefocus";
constexpr char kDefocusLevelMember[] = "u_defocus_level";
constexpr char kGlowAttachment[] = "glow";
constexpr char kEnvironmentAttachment[] = "environment"; // N5.2c: "<step>.environment"

// D17 point 3: whether the transparency stage is admitted on this device; `reason` names what is missing.
struct TransparencyGate
{
    bool admitted = false;
    bool perTargetBlend = false;   // Vulkan: independentBlend; OpenGL: QRhi::PerRenderTargetBlending
    bool blendFormats = false;     // RGBA16F and R16F blend as colour attachments
    bool sampleShading = false;    // per-sample shading (a multisampled transparency only)
    QString reason;
};
// `multisampled`: the transparency target is multisampled (the per-sample resolve needs per-sample shading). Reads the
// core's device facts once per call: the caller keeps the answer per QRhi and program (nothing per record).
TransparencyGate transparencyGate(QRhi *rhi, bool multisampled);
// N3.1's check of differing attachment states (D17's fix of the latent defect): the per-attachment blend is real on this
// device (Vulkan: the core's device facts' independentBlend; OpenGL: QRhi::PerRenderTargetBlending). False with the
// reason. Under the harness's skipBlendGate control it answers true (its negative control).
bool perTargetBlendReal(QRhi *rhi, QString *reason);

// Harness controls (each D17 negative control; any thread; read where noted).
void setSkipBlendGate(bool skip);               // the gates answer "admitted" whatever the device (read at a build)
bool skipBlendGate();
void setBlendFormatsMissing(bool missing);      // the blendable-format fact read as false (read at a gate)
bool blendFormatsMissing();
void setSampleShadingMissing(bool missing);     // the per-sample shading fact read as false (read at a gate)
bool sampleShadingMissing();
void setTransparencyFirstSample(bool first);    // the per-sample resolve reads sample 0 (read at a build)
bool transparencyFirstSample();
void setSkipBloomPrime(bool skip);              // the bloom upsample's rule C prime skipped (read per record)
bool skipBloomPrime();
void setBloomSameTexture(bool same);            // an upsample samples the level it draws into (read at a build)
bool bloomSameTexture();
// ABI 27's negative control: the bloom's grid and the composite's texel anchored at the target's origin again (as before
// ABI 27), not at the item's own pixel (u_scene_item reads the whole target; read per record).
void setBloomAtTargetOrigin(bool atOrigin);
bool bloomAtTargetOrigin();
// ABI 29's negative control: a turned card's scene anchored in the surface's (turned) frame, as ABI 28 anchors an
// unturned one, not in the window's frame its composite declares (u_scene_from_target the surface's; read per record).
void setSceneFrameSurface(bool surface);
bool sceneFrameSurface();
// ABI 32's negative control: the mode's v_uv passes on the surface draw over the full triangle again (as before ABI 32),
// not over the card's own quad (mode_content.cpp cardQuad; read per record).
void setCardTriangle(bool triangle);
bool cardTriangle();
void setSkipStageRelease(bool skip);            // the stages' objects left behind at a release (counted)
bool skipStageRelease();
void setSkipReadChain(bool skip);               // the defocus run's chainShaderReads skipped (read per record)
bool skipReadChain();
// Harness only: fail this texture/target create attempt in one sync (0: off). The bound follows the stage limits.
void setStageAllocationFailure(int attempt);
void setStageBuildFailure(int attempt);         // the build/rebind's sampler, binding or pipeline create attempt
// The defocus cost's diagnosis (the lead, 15 Nov), OpenGL only: GL timestamps before the gather, between it and the
// sprites, and after them, read back latched (never waited for) at a later record; their sums join composite_live
// (stage_defocus_timed, stage_gather_gpu_ns, stage_sprites_gpu_ns). Off: no query object and no call.
void setTimeDefocusDraws(bool on);
bool timeDefocusDraws();
// Harness-only: the same external-command boundaries without queries. Query mode wins if both are enabled.
void setFlushDefocusDraws(bool on);
void setFlushDefocusBoundary(int mark, bool on); // harness: isolate one of the three existing sites (0..2)
void setDeclareDefocusExternal(bool on);       // declaration only, without external-command boundaries or queries
void setDisableDefocusComputeTracking(bool on); // tracking flag only; harness must prove the whole program has no compute
// A new number at every control change (a content's gate is decided again only then).
quint64 stageControlGeneration();

// The process's stages (lifecycle proofs, composite_live, the destruction barrier's reading).
struct StageCounts
{
    int bloomChains = 0;          // chains holding objects
    int defocusSteps = 0;         // defocus steps holding their read level's texture
    int textures = 0;             // the stages' own QRhiTextures (bloom levels, read-level textures)
    qint64 bytes = 0;
    int pipelines = 0;            // owned pipeline, sampler and shader-resource-binding wrappers (partial builds too)
    qint64 buildFailures = 0;     // harness-injected failures only, to prove which actual edge was reached
    qint64 rebindFailures = 0;
    qint64 objectsCreated = 0;    // every QRhi object a stage made (flat at rest)
    qint64 bloomRecords = 0;      // bloom chains recorded
    qint64 defocusRecords = 0;    // defocus steps recorded
    qint64 transparencyResolves = 0;
    qint64 generatedMips = 0;     // generateMips recorded (the defocus layer's attachments)
    qint64 fallbacks = 0;         // transparency fallbacks noted (one per content and gate edge)
    int leftBehind = 0;           // objects the skipped-release control left behind
    qint64 recordsTimed = 0;      // records of programs with stages, timed on the render thread
    qint64 recordNs = 0;          // their summed CPU time (the whole record: every pass and stage)
    qint64 defocusTimed = 0;      // the timeDefocusDraws control's records read back (OpenGL)
    qint64 gatherGpuNs = 0;       // their gathers' summed GPU time
    qint64 spritesGpuNs = 0;      // their sprites' summed GPU time
    qint64 defocusTimeSkipped = 0; // records left untimed (every slot still pending)
    qint64 defocusFlushes = 0; // boundary-only external blocks (none with controls off or in query mode)
    qint64 defocusExternalPasses = 0; // controlled passes using the cached declaration/tracking flags
    qint64 defocusUntrackedPasses = 0;
    int environments = 0;         // N5.2c: photo environments holding their texture
    qint64 environmentCopies = 0; // N5.2c: copies drawn (once per photo)
};
StageCounts stageCounts();
void countTransparencyResolve();
void countFallback();
void countGeneratedMips(int count);
void countStageRecordTime(qint64 recordNs);     // a record of a program with stages: the render thread's whole record
// The deepest read level a defocus step may take over a layer of `layer` texels: two levels above the last level made
// only from even-sized levels (the clip's local mean and the sprites read level + 2), so every level read is one both
// backends' generateMips make alike (the lead, 15 Nov; D17 as built). A deeper level is refused with a reason.
int defocusReadLevelCap(const QSize &layer);

// A program's bloom step and defocus step as the stages need them (mode_content.cpp derives them once per program).
struct BloomSpec
{
    int pass = -1;
    QByteArray name;
    int source = -1;              // the source target
    int attachment = -1;          // its colour attachment
    bool operator==(const BloomSpec &o) const
    {
        return pass == o.pass && name == o.name && source == o.source && attachment == o.attachment;
    }
};
struct DefocusSpec
{
    int pass = -1;
    int near = -1;                // the mips target (colour 0 the premultiplied light, 1 the circle)
    int onto = -1;                // the scene target the gather and the sprites draw onto
    int level = 0;                // the read level this record (the block's u_defocus_level)
    bool operator==(const DefocusSpec &o) const
    {
        return pass == o.pass && near == o.near && onto == o.onto && level == o.level;
    }
};
// N5.2c: a program's photo environment step.
struct EnvironmentSpec
{
    int pass = -1;
    QByteArray name;              // its texture is "<name>.environment"
    QByteArray source;            // the item texture it copies
    QSize size;                   // Python's environment_size
    bool operator==(const EnvironmentSpec &o) const
    {
        return pass == o.pass && name == o.name && source == o.source && size == o.size;
    }
};

// A content's stage objects (render thread): the bloom chains and the defocus steps' read-level textures (made at an
// allocation edge, kept, made again in place at a new size) and their pipelines and bindings (made at a build).
class PostStages
{
public:
    PostStages();                 // defined in post_stages.cpp, where DrawTimer is complete (MSVC: the constructor's
    ~PostStages();                // unwinding destroys the unique_ptr member)
    PostStages(const PostStages &) = delete;
    PostStages &operator=(const PostStages &) = delete;

    // Render thread, after the targets' sync (every target allocated): each chain at its source's allocation and each
    // read level's texture at the near target's allocation and level. Objects are made only when a size or a spec
    // changed. False with the reason (a level past the layer's mips, an object that could not be made).
    bool sync(QRhi *rhi, const QList<BloomSpec> &blooms, const QList<DefocusSpec> &defocus, const SceneTargets &targets,
              QString *error);
    // A new number whenever a texture object was made or re-made (the bindings that sample one are made again).
    quint64 objectGeneration() const { return m_objectGeneration; }
    // The glow of the bloom step `step` (its level 0); null when there is none.
    QRhiTexture *glow(const QByteArray &step) const;

    // Build: every chain's pipelines and bindings (`vs` the core's triangle, `layout` its vertex input with vUv), and
    // each defocus step's over the onto target's render pass (the clip's over its own). False with the reason.
    bool build(QRhi *rhi, const SceneTargets &targets, const QShader &vs, const QRhiVertexInputLayout &layout,
               QRhiBuffer *arena, quint32 conventionsBytes, quint32 defocusBlockBytes, QString *reason, int *objects);
    // The bindings made again over the textures' current objects (a resize); false: build again.
    bool rebind(const SceneTargets &targets);
    void releasePipelines();
    void release();
    int live() const;

    // Record (outside any pass): the bloom step `pass`'s chain, each level a render pass of its own; `triangle` the core's
    // triangle (its own uv); `firstTriangle` the first downsample's (ABI 27: its uv from the item's own pixel, so level 0
    // pairs the source's pixels as Python's SceneTarget does). `pending`: the record's uploads, handed to the first pass
    // and nulled.
    void recordBloom(QRhi *rhi, QRhiCommandBuffer *cb, int pass, const QRhiCommandBuffer::VertexInput &triangle,
                     const QRhiCommandBuffer::VertexInput &firstTriangle, QRhiResourceUpdateBatch **pending);
    // Record: the defocus step `pass`'s clip (its own render pass, the layer's mips generated first in `mips`), then,
    // inside the onto target's render pass the caller has begun, its gather and sprites. The arena's offsets are the
    // step's block and the conventions.
    void recordDefocusClip(QRhi *rhi, QRhiCommandBuffer *cb, int pass, const QRhiCommandBuffer::VertexInput &triangle,
                           QRhiResourceUpdateBatch *mips, quint32 blockOffset, quint32 conventionsOffset);
    void recordDefocusOnto(QRhiCommandBuffer *cb, int pass, const QRhiCommandBuffer::VertexInput &triangle,
                           quint32 blockOffset, quint32 conventionsOffset, bool drawSprites, const QRect &scissor);
    bool hasDefocus(int pass) const { return defocusFor(pass) != nullptr; }
    QRhiCommandBuffer::BeginPassFlags defocusPassFlags() const { return m_defocusPassFlags; }

    // N5.2c, render thread, after sync: each environment's texture and render target at its declared size (made only
    // when a size or a spec changed), and the item texture each copies (`photos`, one per spec: its front, null while
    // it has none). A new texture object or another photo object is a new objectGeneration (the bindings that sample
    // one are made again). False with the reason.
    bool syncEnvironments(QRhi *rhi, const QList<EnvironmentSpec> &specs, const QList<QRhiTexture *> &photos,
                          QString *error);
    int environmentCount() const { return m_environmentCount; }
    // The texture of the environment step `step` ("<step>.environment"); null when there is none.
    QRhiTexture *environment(const QByteArray &step) const;
    // Record (outside any pass): the environment step `pass`'s copy and its box chain, only when its photo's front
    // (`photoGeneration`, the item texture's image) or its own texture changed since it was last drawn; `pending` the
    // record's uploads (the photo's among them), handed to its pass and nulled. Returns whether it drew.
    bool recordEnvironment(QRhi *rhi, QRhiCommandBuffer *cb, int pass, const QRhiCommandBuffer::VertexInput &triangle,
                           quint64 photoGeneration, QRhiResourceUpdateBatch **pending);

private:
    struct Bloom
    {
        BloomSpec spec;
        QSize sizes[kBloomLevels];
        RhiOwned<QRhiTexture> levels[kBloomLevels];
        RhiOwned<QRhiRenderPassDescriptor> passes[kBloomLevels];
        RhiOwned<QRhiTextureRenderTarget> targets[kBloomLevels];
        QRhiTexture *source = nullptr;   // the source's readable texture (the target's)
        // Build: a linear sampler; the downsamples' bindings (level k samples level k - 1, level 0 the source) and the
        // upsamples' (up[k] samples level k and draws into level k - 1); three pipelines over level 0's render pass.
        RhiOwned<QRhiSampler> sampler;
        RhiOwned<QRhiShaderResourceBindings> down[kBloomLevels];
        RhiOwned<QRhiShaderResourceBindings> up[kBloomLevels];
        RhiOwned<QRhiGraphicsPipeline> downFirst;
        RhiOwned<QRhiGraphicsPipeline> downRest;
        RhiOwned<QRhiGraphicsPipeline> upAdd;
        qint64 bytes = 0;
    };
    struct Defocus
    {
        DefocusSpec spec;
        QSize belowSize;
        RhiOwned<QRhiTexture> below;
        RhiOwned<QRhiRenderPassDescriptor> belowPass;
        RhiOwned<QRhiTextureRenderTarget> belowTarget;
        QRhiTexture *colour = nullptr;   // the near layer's (the target's)
        QRhiTexture *circle = nullptr;
        QSize layerSize;
        // Build: the layer's sampler (linear, nearest mips), the read level's (linear), three bindings, three pipelines.
        RhiOwned<QRhiSampler> mipSampler;
        RhiOwned<QRhiSampler> linearSampler;
        RhiOwned<QRhiShaderResourceBindings> clipBindings;
        RhiOwned<QRhiShaderResourceBindings> gatherBindings;
        RhiOwned<QRhiShaderResourceBindings> spriteBindings;
        RhiOwned<QRhiGraphicsPipeline> clip;
        RhiOwned<QRhiGraphicsPipeline> gather;
        RhiOwned<QRhiGraphicsPipeline> sprites;
        qint64 bytes = 0;
    };
    // N5.2c: one photo environment (its texture and render target at the spec's size; its sampler, block, bindings and
    // pipeline made at a build; what it last drew).
    struct Environment
    {
        EnvironmentSpec spec;
        QSize size;
        RhiOwned<QRhiTexture> texture;
        RhiOwned<QRhiRenderPassDescriptor> pass;
        RhiOwned<QRhiTextureRenderTarget> target;
        MipChain chain;                  // ABI 36: its levels' box-kernel bindings (made with the texture)
        QRhiTexture *photo = nullptr;    // the item texture's front it copies (the item's, never owned here)
        RhiOwned<QRhiBuffer> block;      // its uStep (Python's 0.25 / size), written once per size
        RhiOwned<QRhiSampler> sampler;   // the photo's: linear, clamped, no mips (Python's lent texture)
        RhiOwned<QRhiShaderResourceBindings> bindings;
        RhiOwned<QRhiGraphicsPipeline> pipeline;
        bool blockWritten = false;
        bool drawn = false;              // the texture holds the copy of drawnPhoto's drawnGeneration
        const QRhiTexture *drawnPhoto = nullptr;
        quint64 drawnGeneration = 0;
        qint64 bytes = 0;
    };

    // The timeDefocusDraws control's GL queries (made at its first use on this QRhi, deleted with the stages).
    struct DrawTimer;
    std::unique_ptr<DrawTimer> m_drawTimer;
    void markDefocus(QRhiCommandBuffer *cb, int mark);
    void releaseDrawTimer();

    Defocus *defocusFor(int pass) const;
    bool bloomBindings(Bloom &b);
    bool defocusBindings(Defocus &d);
    bool environmentBindings(Environment &e);
    void releaseEnvironmentPipelines(Environment &e);
    void releaseEnvironment(Environment &e);
    static int allocationObjects(const Environment &e);
    void beginBuildAttempts(bool rebinding = false);
    void noteBuildFailure();
    template<typename Resource> bool createBuildResource(Resource *resource)
    {
        if (m_failBuild && ++m_buildAttempt == m_failBuild) {
            resource->destroy();
            noteBuildFailure();
            return false;
        }
        return resource->create();
    }
    // The harness's allocation fault (fail_allocation): one count across a record's sync and syncEnvironments (each
    // create or bind attempt an ordinal; the snapshot taken and the count reset at sync). False: the injected failure.
    bool allocationAllowed()
    {
        if (m_failAllocation && ++m_allocationAttempt == m_failAllocation) {
            m_allocationInjected = true;
            return false;
        }
        return true;
    }
    template<typename Resource> bool createAllocation(Resource *resource)
    {
        if (!allocationAllowed()) {
            resource->destroy();                // a resize fault retires its previous storage too
            return false;
        }
        return resource->create();
    }
    QString allocationFault() const;            // " [harness fail_allocation=N]" when the injected failure was met
    void countPipelineObjects(int delta);
    void releaseBloomPipelines(Bloom &b);
    void releaseDefocusPipelines(Defocus &d);
    static int allocationObjects(const Bloom &b);
    static int allocationObjects(const Defocus &d);
    void releaseBloom(Bloom &b);
    void releaseDefocus(Defocus &d);
    void count(int textures, qint64 bytes, int chains, int steps);

    QRhi *m_rhi = nullptr;
    QRhiCommandBuffer::BeginPassFlags m_defocusPassFlags;
    int m_defocusDrawControl = 0; // one sync snapshot governs both pass declaration and every mark
    std::unique_ptr<Bloom> m_blooms[kMaxBloomStages];
    int m_bloomCount = 0;
    std::unique_ptr<Defocus> m_defocus[kMaxDefocusStages];
    int m_defocusCount = 0;
    std::unique_ptr<Environment> m_environments[kMaxEnvironmentStages]; // N5.2c
    int m_environmentCount = 0;
    MipChainKernel m_environmentChains; // ABI 36: the environments' box kernel (mip_chain.h)
    QRhiBuffer *m_arena = nullptr;       // the content's block arena (the defocus bindings name it)
    quint32 m_conventionsBytes = 0;
    quint32 m_defocusBlockBytes = 0;
    int m_pipelineObjects = 0;
    int m_failAllocation = 0;       // harness snapshot at sync; only create/bind attempts advance it
    int m_allocationAttempt = 0;
    bool m_allocationInjected = false;
    int m_failBuild = 0;            // harness snapshot; only build/rebind edges advance attempts
    int m_buildAttempt = 0;
    bool m_buildInjected = false;
    bool m_rebinding = false;
    quint64 m_objectGeneration = 1;
};

} // namespace srpss_core
