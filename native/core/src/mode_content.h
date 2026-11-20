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
//
// Scene targets (N3.1, D14; scene_targets.h): a program may declare up to kMaxSceneTargets targets beside its passes
// ({"passes": [...], "targets": [...]}), and a pass names the target it draws into ("target"; the surface without it).
// A pass on a scene target writes outputs at locations 0..n-1 for the target's n colour attachments, each with its own
// write mask and blend ("attachments": [{"write", "blend"}], default: every attachment with the pass's blend; differing
// states need per-attachment blending: N3.4, read from the core's device facts, post_stages.h perTargetBlendReal), may
// test and write the target's depth ("depth": {"test", "write"}) and
// write gl_FragDepth (only into a target with depth). A capture step ({"name", "capture": <target>}, an empty pack) ends
// the target's pass, copies its colour and nearest window depth into the target's capture (Python's
// SceneTarget.background()) and the next pass on the target loads it again. A sampler reads a target's attachment by
// "<target>.<attachment>" (its resolve when multisampled), "<target>.depth", "<target>.capture_colour" or
// "<target>.capture_depth" (never an attachment of the pass's own target), with no mips. The passes are recorded in
// order, one render pass per run of passes on the same target; a target is cleared by a draw at its first run of a
// record, and the surface is opened (and cleared) once at least. A pass on a scene target draws over its content
// viewport (scene_targets.h contentViewport); its v_uv and vUv are the surface's for a surface-sized target and the
// target's own for an explicit size, and u_target_px is its target's content size.
//
// Meshes and buffers (N3.2, D15; mesh_buffers.h): a pass may bring its own vertex stage ("vertex": true, its pack after
// the fragment's; a batched pass's draw-parameters pack after that) and its geometry: "topology" (triangles or
// triangle_strip; points refused), "vertices" (a number, "mesh", or a name the record or the settings fill), "instances"
// (likewise; 0 draws nothing), "first_vertex", "mesh" (its per-vertex inputs: an item's mesh or the built-in "quad"),
// "instance_from" (per-instance inputs, step rate 1: a mesh's instance stream or an instance stream), "storage"
// ([{"name": the shader's buffer block, "stream": a storage stream}], read only), "cull" (none, back, front),
// "front_face" (ccw, cw, or a name choosing between two pipelines built ahead: 0 ccw, 1 cw), "indirect" (an indirect
// stream, with "draw_count"), "batches" (a u32 array field of {first, count} pairs, with "batch_count": D15 point 6) and
// "blend" as a full declaration ({"color": [op, src, dst], "alpha": [...]}) beside the presets. The vertex stage's inputs
// bind by name to the mesh's and the instance source's attributes; its outputs carry the fragment's inputs by location.
// Its block is the pass's own (the same block in both stages when both declare it), and it may read the conventions
// block, samplers and storage. The program declares its streams ({"streams": [...]}: a record field each), and (ABI 26)
// the record's fields it reads nowhere ({"unread": [...]}: a stage the program leaves out reads them, as the
// Oscilloscope's Glow 0 program leaves the bloom strength; any other unread field is refused). Every block of
// the content (the passes', the conventions, the clears', the captures', the nearest resolves') lives in one block arena
// given as dynamic offsets; firstInstance is always 0. The core member uMatrix (item pixels, the item's own unrotated
// coordinates, to the drawn target's clip space, corrected once: conventions.h rule 1) is filled for a pass with its own
// vertex stage; on the core's triangle it stays zeros (nothing reads it there).
//
// Compute passes (N3.3, D16; compute_passes.h): a program may declare storage buffers and images ({"buffers": [...],
// "images": [...]}) and compute entries in its pass list ({"name", "compute": true, "trigger": "frame" or {"field"},
// "groups": [x, y, z] or {"over": a resource}, "bindings": [{"name": the shader's buffer block or image, "buffer" |
// "image" | "stream" | "mesh": the resource, "access": read, write or read_write}], "samplers"?: [...]}, one compute pack
// each). An entry is recorded at its place as its own QRhi compute pass, outside any render pass, only when its trigger
// has new work (a re-record for the card, the settings, a texture or a harness readback dispatches nothing). A draw reads
// a storage buffer as storage ("storage": [{"name", "stream": the buffer}]), per instance ("instance_from") or as its
// indirect commands ("indirect"), and an image through a sampler naming it (sampler2D, or sampler3D for a 3D image).
// Every count a draw or a dispatch reads over a storage buffer is checked against that buffer; a named group count is a
// record u32 under an at_most rule (or a setting); groups past the device's limit are not dispatched. The content owns
// the storage (ModeStorage); it survives a pipeline rebuild and a new program that declares it the same way, and each
// entry declared again by name keeps its history over it (fresh is per entry: checkpoint audit 5 M2). A content
// made again finds its storage gone: it is made zeroed, the entries dispatch fresh, and the owner is told once through
// the lost edge with the names "state:<resource>" (NativeMode.on_state_lost). A still draws no compute.
//
// Stages (N3.4, D17; post_stages.h): transparency and post-processing, each data in the program and absent unless
// declared (a program without it holds no object of it and records nothing of it):
// - a transparency target ({"name", "transparency": {"of": <scene target>, "borrow": [...]}}, scene_targets.h): its
//   passes are the mode's, drawn into its accumulation (location 0), coverage (1) and borrowed attachments (2..), the
//   core fixing the blends of the first two (ONE, ONE; ONE, ONE_MINUS_SRC_COLOR), depth tested against the owner's
//   loaded depth (less unless declared) and never written. Each such pass ships its sorted pack after its others
//   ("sorted": true): drawn into the owner, premultiplied over, where the device gate does not admit the stage. A
//   resolve step ({"name", "transparency_resolve": <target>, "alpha"?: "coverage" | "keep"}, an empty pack) composites
//   it onto the owner's colour 0, per sample when multisampled; it follows every pass on the target, and nothing samples
//   the owner between them;
// - a bloom step ({"name", "bloom": "<target>.<attachment>"}, an empty pack): its chain from the attachment (its resolve
//   when multisampled), its glow read by a later sampler as "<step>.glow";
// - a composite step ({"name", "composite": overlay | overlay_glow | opaque_glow, "scene": "<target>.<attachment>",
//   "glow"?: "<bloom step>.glow"}, an empty pack): a pass on the surface whose fragment is the core's, its block filled
//   by the one rule (u_target_px and u_fade the core's; u_bloom_strength and u_hdr_exposure the record's or the
//   settings'), its blend the form's (overlay: alpha; overlay_glow: premultiplied; opaque_glow: replace);
// - a defocus step ({"name", "defocus": <mips target>, "onto": <scene target>}, an empty pack): the layer's mips, the
//   clip, the gather and the highlight sprites; its block (u_defocus_radius, u_defocus_highlight, u_defocus_level) filled
//   by the one rule. The read level is at most post_stages.h defocusReadLevelCap of the layer's allocation (a deeper
//   one is the content's failure, latched, with its reason); the run that draws the gather and the sprites is followed
//   by targets.h chainShaderReads (the layer is read in two shader stages of one pass).
// A device that does not admit the transparency stage (post_stages.h transparencyGate) leaves the transparency target
// dormant and draws its passes' sorted packs; the fallback is noted once in the targets' state. A program whose passes
// write attachments with differing states is refused where per-attachment blending is not real (the core's device facts,
// never QRhi's flag): the mode-level fallback, Python's to log. A record of a program with stages is timed on the render
// thread (composite_live's stage_records_timed, stage_record_ns).
#pragma once

#include "compute_passes.h"
#include "mesh_buffers.h"
#include "mode_schema.h"
#include "packet_reader.h"
#include "post_stages.h"
#include "program_blocks.h"
#include "scene_targets.h"
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

constexpr int kMaxModePasses = 16; // N3.1: a 3D scene's passes and captures (8 before)
constexpr int kMaxModeUnread = 16; // ABI 26: the record fields a program may leave unread

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

// N3.1: Additive (ONE, ONE on every channel) for the light attachments (EB's emission, Bubble's ambient light).
enum class PassBlend { Replace = 0, Alpha = 1, Premultiplied = 2, Add = 3, Additive = 4 };
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
    int stages = 0;       // N3.2: QRhiShaderResourceBinding::StageFlags the pass's stages read it in (0: the fragment)
    int dimensions = 2;   // N3.3: 3 for a sampler3D (it reads a 3D storage image)

    QJsonObject toJson() const;
};

// N3.1: one colour attachment's write mask and blend in a pass.
struct PassOutput
{
    bool write = true;
    PassBlend blend = PassBlend::Alpha;
    bool custom = false;                            // N3.2: a full declaration (customBlend) in place of `blend`
    QRhiGraphicsPipeline::TargetBlend customBlend;
};

// N3.2 (D15 point 1): a pass's geometry.
enum class PassTopology { Triangles = 0, TriangleStrip = 1 };
enum class PassCull { None = 0, Back = 1, Front = 2 };

// A vertex stage's input, bound by name at the build to its mesh's or its instance source's attribute.
struct PassInput
{
    QByteArray name;
    int location = 0;
    int components = 0;
};

// A storage block of the pass's stages bound by name to a storage stream (read only).
struct PassStorage
{
    QByteArray name;      // the shader's buffer block
    QByteArray stream;
    int binding = -1;     // reflected
    int stages = 0;       // QRhiShaderResourceBinding::StageFlags
};

// N3.1: a pass's depth test (none: the depth is neither tested nor written).
enum class DepthTest { None = 0, Never, Less, Equal, LessOrEqual, Greater, NotEqual, GreaterOrEqual, Always };
bool parseDepthTest(const QString &text, DepthTest *out);
QString depthTestName(DepthTest test);

struct ModePass
{
    QByteArray name;
    PassBlend blend = PassBlend::Alpha;
    QShader fragment;
    BlockLayout block;        // the pass's own block (not valid: the pass declares none)
    bool conventions = false; // the pass declares SrpssConventions
    PassUv uv = PassUv::None; // the quad uv the pass reads at location 0
    QList<PassSampler> samplers;
    // N3.1 (scene targets): the target it draws into (-1: the surface), or the target a capture step copies.
    int target = -1;
    bool capture = false;     // a capture step (no fragment, no block, no samplers)
    QList<PassOutput> outputs; // one per colour attachment of its target (the surface: one, the pass's blend)
    DepthTest depthTest = DepthTest::None;
    bool depthWrite = false;
    bool fragDepth = false;   // the fragment writes gl_FragDepth
    // N3.2 (D15): its own vertex stage and geometry (mode_content.h's header, mesh_buffers.h).
    bool customBlend = false;                        // "blend" was a full declaration
    QRhiGraphicsPipeline::TargetBlend blendState;    // its state (customBlend)
    QShader vertex;                                  // invalid: the core's triangle (N2.9 to N3.1)
    QShader vertexDrawParameters;                    // a batched pass's draw-parameters pack (D15 point 6)
    int blockStages = 0;                             // the stages that declare the pass's block (0: the fragment)
    int conventionsStages = 0;                       // the stages that declare SrpssConventions (0: the fragment)
    PassTopology topology = PassTopology::Triangles;
    DrawCount vertices;                              // a number, "mesh", or a name
    DrawCount instances;                             // a number (1 by default) or a name; 0 draws nothing
    quint32 firstVertex = 0;
    QByteArray mesh;                                 // per-vertex inputs (an item's mesh or "quad")
    QByteArray instanceFrom;                         // per-instance inputs (a mesh's instance stream, or a stream)
    QList<PassInput> inputs;                         // the vertex stage's, reflected
    QList<PassStorage> storage;
    PassCull cull = PassCull::None;
    bool frontClockwise = false;                     // the fixed front face (cw), when no selector
    DrawCount frontSelector;                         // a name choosing ccw (0) or cw (1) per record
    QByteArray indirect;                             // an indirect stream (empty: a direct draw)
    DrawCount drawCount;                             // its commands drawn
    QByteArray batches;                              // a batched draw's u32 {first, count} pairs (D15 point 6)
    DrawCount batchCount;                            // how many batches the record holds
    // N3.3 (D16): a compute entry (its pack is `computeShader`; no fragment, no target).
    bool compute = false;
    QShader computeShader;
    ComputeTrigger trigger;
    DrawCount groups[3];                             // each a number or a name (record u32 under at_most, or a setting)
    QByteArray groupsOver;                           // or the extent of this resource over the local size
    QList<ComputeBinding> computeBindings;
    quint32 localSize[3] = { 1, 1, 1 };              // reflected
    int computeMemberOffset = -1;                    // u_srpss_compute's offset in its block (-1: not declared)
    // N3.4 (D17): a stage entry (post_stages.h). A resolve's `target` is the owner and `stageSource` the transparency
    // target; a bloom's `stageSource` and `stageAttachment` its source (`target` -1: it has its own); a defocus's
    // `target` the onto target and `stageSource` the layer; a composite is a surface pass with the core's fragment.
    StageKind stage = StageKind::None;
    int stageSource = -1;
    int stageAttachment = -1;
    bool coverageAlpha = true;                       // a resolve: alpha ONE (an overlay's coverage), else ZERO (kept)
    CompositeForm compositeForm = CompositeForm::Overlay;
    // A pass on a transparency target: its sorted pack and its outputs on the owner (the fallback, D17 choice D).
    QShader sorted;
    QList<PassOutput> sortedOutputs;

    bool ownVertex() const { return vertex.isValid(); }
    bool batched() const { return !batches.isEmpty(); }
    // A bloom or defocus step: recorded outside the runs of passes, with render passes of its own.
    bool stepOfItsOwn() const { return stage == StageKind::Bloom || stage == StageKind::Defocus; }
};

struct ModeProgram
{
    QList<ModePass> passes;
    QList<TargetDeclaration> targets; // N3.1: its scene targets (reads derived from the samplers and captures)
    QList<StreamDeclaration> streams; // N3.2: its streams (a record field each)
    QList<StorageBufferDeclaration> buffers; // N3.3: its storage buffers
    QList<StorageImageDeclaration> images;   // N3.3: its storage images
    // ABI 26 (N5.1, the Oscilloscope's Glow 0): the record's fields the program reads nowhere ({"unread": [...]}: a
    // stage it leaves out reads them), each a field of the record that no pass, draw or stream reads; any other record
    // field no pass reads is refused as before.
    QList<QByteArray> unread;
    // N3.2: the numbers of the settings the draws name (counts and selectors), set where the settings are admitted.
    QHash<QByteArray, double> drawSettings;
    quint64 generation = 0; // a new program rebuilds the pipelines at the next record

    // The program from its declaration ({"passes": [{"name", "blend", "samplers"?: [{"name", "texture", "filter",
    // "wrap", "mips"}, ...]}, ...]}) and one fragment pack per pass, in order; false with `error` when a pack does not
    // load or a pass declares what a pass may not (the header), or a sampler is unbound, unknown or doubly bound.
    static bool fromJson(const QByteArray &json, const QList<QByteArray> &packs, ModeProgram *out, QString *error);
    bool valid() const { return !passes.isEmpty(); }
    QJsonObject toJson() const;
    bool declares(const QByteArray &member) const;
    // N3.2: whether a draw names `name` (a count or a selector a record field or a setting fills), or a stream reads it.
    bool drawNames(const QByteArray &name) const;
    bool streamReads(const QByteArray &field) const;
    // N3.2: the meshes the passes draw (each once; never the built-in quad). N3.3: and the meshes compute reads.
    QList<QByteArray> drawnMeshes() const;
    // N3.3: the declared storage by name (null: none), and whether any pass is a compute entry.
    const StorageBufferDeclaration *storageBuffer(const QByteArray &name) const;
    const StorageImageDeclaration *storageImage(const QByteArray &name) const;
    bool hasCompute() const;
    // N3.2: the settings' numbers the draws name, from `settings`.
    QHash<QByteArray, double> drawSettingNumbers(const QJsonObject &settings) const;
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
    // N3.1: `passTargets` (one per pass) gives each pass's target content size for its core members (u_target_px);
    // null: `target` for every pass.
    // N3.2: `clipCorrection` (16 floats, column-major; null: none) is the target's correction (conventions.h rule 1) of
    // the uMatrix of a pass with its own vertex stage.
    bool packFrame(const frame_abi::Schema &schema, const QByteArray &record, const ModeCard &card, const QSize &target,
                   QList<BlockValues> &blocks, QString *error, const QList<QSize> *passTargets = nullptr,
                   const float *clipCorrection = nullptr) const;
    // N3.1: each pass's target content size for a surface of `surface` pixels (a surface-sized target's is the surface's)
    // under `targets` (the program's own when null: ModeSource::drawnTargets carries the sizes set since), into `out`
    // in place (audit 2, M5: no new list per frame once its capacity holds the passes).
    void passTargetSizes(const QSize &surface, const QList<TargetDeclaration> *targets, QList<QSize> *out) const;
};

// GPU-free: what the content uploads for one record (each pass's block bytes), with the same refusals; `facts` names
// each pass's block and which source filled each member.
// N3.2: `clipCorrection` (16 floats, column-major; null: none) is a target's correction of a vertex stage's uMatrix
// (the GPU-free test gives each backend's, as targetCorrection makes it).
bool modeBlocks(const RuntimeSchema &schema, const ModeProgram &program, const QJsonObject &settings,
                const ModeCard &card, const QSize &target, const QByteArray &record, QList<QByteArray> *blocksOut,
                QJsonObject *facts, QString *reason, const float *clipCorrection = nullptr);

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
    // N3.2 (D15 point 2), GUI thread: a mesh (makeModeMesh's declaration and bytes), replacing the one of that name;
    // refused for a bad name, declaration or byte count, or more than kMaxModeMeshes. removeMesh: false when there is
    // none of that name.
    bool setMesh(const QByteArray &name, const QByteArray &declaration, const QByteArray &vertices,
                 const QByteArray &instances, QString *error);
    bool removeMesh(const QByteArray &name, QString *error);

    // N3.8: the item's notifier (the job thread's frame request, the lost edge); the item attaches it.
    const std::shared_ptr<ItemNotifier> &notifier() const { return m_notifier; }

    // Render thread, at the item's sync. True when the surface must record.
    bool sync();

    // Render thread, while recording.
    const ModeProgram &drawnProgram() const { return m_drawnProgram; }
    const QList<BlockValues> &drawnSettings() const { return m_drawnSettings; }
    const RuntimeSchema *drawnSchema() const { return m_drawnSchema.data(); }
    // N3.2 audit 4 H1: the drawn schema, shared with what is built from it (the streams point into its fields).
    const QSharedPointer<const RuntimeSchema> &drawnSchemaShared() const { return m_drawnSchema; }
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
    // N3.2: the drawn meshes, and the bytes of the drawn mesh `name` (they move to the caller; null when taken before).
    const QList<ModeMesh> &drawnMeshes() const { return m_drawnMeshes; }
    QSharedPointer<MeshImage> takeMeshImage(const QByteArray &name);
    // N3.2: the content's meshes, streams and arena as built (render thread, at a build or a mesh change only; never
    // per record: N3.1 audit's lesson), and the meshes found lost.
    void noteMeshBuffers(const QJsonObject &state);
    // The content's texture report (render thread writes, any thread reads).
    void noteTextures(const TextureReport &report);
    // N3.8: a record that changed an image (the last kImageChangeRecords are kept).
    void noteImageChange(const ImageChangeRecord &record);
    // N3.8: textures newly found lost: the owner's edge (queued to the GUI thread).
    void texturesLost(const QStringList &names);
    static constexpr int kImageChangeRecords = 64;

    // N3.1, GUI thread: an explicit-size target's size (Bubble's ambient target follows its card) with no new program:
    // the allocation follows at the next record (the pipelines kept). Refused for a target the program does not
    // declare with an explicit size, or a size outside 1 to 16384.
    bool setTargetSize(const QByteArray &name, const QSize &size, QString *error);
    // Render thread: the drawn program's targets with the sizes set since.
    const QList<TargetDeclaration> &drawnTargets() const { return m_drawnTargets; }

    // N3.1, harness: a readback of every scene target's readable textures at the next record (GUI thread; the caller
    // asks the item for a frame), and its pixels once QRhi completed it (any thread; taken once).
    void requestTargetRead();
    quint64 targetReadRequests() const { return m_targetReads.loadAcquire(); }
    void setTargetReadback(const std::shared_ptr<SceneReadback> &readback);
    bool takeTargetPixels(QList<SceneTargetPixels> *out);
    // N3.1: the scene targets' state (render thread writes it when it changed; the state's "scene_targets", made into
    // JSON only when the state is asked for: audit 2, M5).
    void noteTargets(const SceneTargetsState &state);

    // N3.3, GUI thread: a storage image's size ([w, h] or [w, h, d]) with no new program (Waveform's fog grid follows
    // its surface): the image is made again at the next record. Refused for an image the program does not declare or
    // a size outside its bounds.
    bool setImageSize(const QByteArray &name, const int *size, QString *error);
    // Render thread: the drawn program's images with the sizes set since.
    const QList<StorageImageDeclaration> &drawnImages() const { return m_drawnImages; }
    // N3.3, render thread: whether a content of this source held storage before (a content made again finds it lost).
    bool storageHeld() const { return m_storageHeld.loadRelaxed() != 0; }
    void setStorageHeld(bool held) { m_storageHeld.storeRelaxed(held ? 1 : 0); }
    // N3.3, harness: a readback of every storage buffer and image at the next record (GUI thread; the caller asks the
    // item for a frame), and its bytes once QRhi completed it (any thread; taken once). The record it rides on
    // dispatches nothing (no new work).
    void requestStorageRead();
    quint64 storageReadRequests() const { return m_storageReads.loadAcquire(); }
    void setStorageReadback(const std::shared_ptr<StorageReadback> &readback);
    bool takeStoragePixels(QList<StoragePixels> *out);
    // N3.3: the storage's state and the device's compute facts (render thread, at an edge only).
    void noteStorage(const QJsonObject &state);

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
    QList<TargetDeclaration> m_targetSizes;     // N3.1: explicit sizes set since the program (name and size only)
    QList<ModeMesh> m_meshes;                   // N3.2: the item's meshes, their bytes until taken
    QList<StorageImageDeclaration> m_imageSizes; // N3.3: sizes set since the program (name and size only)
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
    QList<TargetDeclaration> m_drawnTargets;    // N3.1
    QList<ModeMesh> m_drawnMeshes;              // N3.2
    QList<StorageImageDeclaration> m_drawnImages; // N3.3
    quint64 m_takenJobsFinished = 0;            // N3.8: the notifier's count at the last sync
    QAtomicInteger<int> m_storageHeld { 0 };    // N3.3

    const std::shared_ptr<ItemNotifier> m_notifier;

    mutable QMutex m_textureReportMutex;        // guards the texture report
    TextureReport m_textureReport;
    QList<ImageChangeRecord> m_imageChanges;
    SceneTargetsState m_targetsState;           // N3.1, under m_textureReportMutex
    std::shared_ptr<SceneReadback> m_targetReadback; // N3.1, under m_textureReportMutex
    QAtomicInteger<quint64> m_targetReads { 0 };
    QJsonObject m_meshBuffersState;             // N3.2, under m_textureReportMutex
    QJsonObject m_storageState;                 // N3.3, under m_textureReportMutex
    std::shared_ptr<StorageReadback> m_storageReadback; // N3.3, under m_textureReportMutex
    QAtomicInteger<quint64> m_storageReads { 0 };
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
    // The passes' bindings over current objects, the pipelines kept; false: build everything again. A mesh-only edge
    // retargets only compute SRBs that read meshes; graphics binds its current vertex buffers per draw.
    bool rebindResources(bool meshesOnly);
    bool geometryInputLayout(int index, QRhiVertexInputLayout *input, bool *meshBound, bool *instanceBound,
                             QString *reason) const;
    bool geometryLayoutsHold() const;
    // N4.a, N3.1: the texture a sampler reads: an item texture's front, or a scene target's ("<target>.<attachment>").
    QRhiTexture *samplerTexture(const QByteArray &name) const;
    // N3.1: a pass's bindings (its block, the conventions, its samplers; a capture's block and sources), in build()'s order.
    bool passBindings(const Resources &r, int index, QList<QRhiShaderResourceBinding> *out) const;
    // D14 point 10: a nearest resolve's bindings (its block, the conventions, the multisampled source).
    bool nearestBindings(const Resources &r, int target, int slot, QList<QRhiShaderResourceBinding> *out) const;
    // D14 point 10: after a run of passes on `target` ending at pass `last`, the nearest resolves a later pass reads (or
    // the readback, after the target's last run).
    void recordNearest(QRhiCommandBuffer *cb, int target, int last, bool readback);
    // N3.1: the program's targets at this surface's size, allocated (every step, until N3.6 spaces them); false with the
    // reason (the content's failure).
    bool syncTargets(QRhi *rhi, const ColorTarget &target, QString *error);
    // N3.1: the passes, the captures and the surface's opening(s) of one record (the surface cleared once at least);
    // `readback`: the harness reads the targets after this record (their nearest resolves are made after the last run).
    void recordPasses(QRhi *rhi, QRhiCommandBuffer *cb, ColorTarget &target, QRhiResourceUpdateBatch *updates,
                      bool draw, bool readback);
    bool build(QRhi *rhi, ColorTarget &target, bool withPasses, QString *error);
    // N3.2: a pass with its own vertex stage: its pipelines (two when its front face is chosen per record).
    // N3.4: `sorted`, the pass's sorted pack and its outputs on the owner (a transparency target not admitted).
    bool buildGeometryPass(QRhi *rhi, Resources &r, int index, QRhiRenderPassDescriptor *renderPass, int samples,
                           QString *reason, int *objects, bool sorted = false);
    // N3.2: a batched pass's batches the arena holds (its batch table's pairs, at most kMaxBatches).
    int batchCapacity(const ModePass &pass) const;
    // N3.2: the meshes' and streams' state, noted on the source only when their objects changed (never per record).
    void noteMeshBuffers();
    // N3.2: one pass's draw on its open render pass (pipeline, viewport, the arena's offsets, inputs, the draw call).
    void drawPass(QRhi *rhi, QRhiCommandBuffer *cb, int index, const QRect &viewport,
                  const QRhiCommandBuffer::VertexInput &triangle, const QRect &scissor);
    // N3.2: a count or a selector for this record (a number, the mesh's, a record u32 field, a setting).
    quint32 resolveCount(const DrawCount &count, quint32 meshCount) const;
    // N3.2 audit 4 (H2, M1): pass `index`'s draw refused this record: `what` (a DrawRefusal) asked `asked` of a buffer
    // holding `held`. The reason is made, and noted in the mesh-buffer state, once at the refusal's edge; the record's
    // reason names it.
    void refuseDraw(int index, int what, quint64 asked, quint64 held);
    // N3.2: the passes' blocks into the arena's CPU copy (a batched pass: one copy a batch, its u_srpss_batch set).
    void fillArena();
    // N3.2: the drawn passes' meshes all uploaded.
    bool meshesReady() const;
    // Which passes' meshes are missing (bit 2 * pass its mesh, the next its instance source; 0: none), read in place.
    quint64 missingMeshMask() const;
    // N3.3 (D16): the storage at this record (made, kept or made again; its edge kernels recorded now, before any pass);
    // false with the reason (the content's failure, latched like a build's).
    bool syncStorage(QRhi *rhi, QRhiCommandBuffer *cb, const ColorTarget &target, QString *error);
    // N3.3: which compute entries dispatch at this drawn record (their trigger has new work), u_srpss_compute filled into
    // the arena's copy for each.
    void decideDispatches();
    // N3.3: one compute entry's dispatch (its own QRhi compute pass; under the single-pass control the pass stays open
    // for the next entry). `open`: a compute pass is open; `pending`: the record's uploads, for the first pass.
    void recordCompute(QRhi *rhi, QRhiCommandBuffer *cb, int index, QRhiResourceUpdateBatch **pending, bool *open);
    // N3.3: a compute entry's group count on one axis for this record (0: nothing to dispatch).
    quint32 computeGroups(QRhi *rhi, const ModePass &pass, int axis) const;
    // N3.3: a storage buffer's record count for a draw reading it (its bytes over `stride`).
    const ModeStorage::Buffer *storageBuffer(const QByteArray &name) const { return m_storage.buffer(name); }
    // N3.3: a compute entry's bindings (its block, its resources by access, its samplers), in build()'s order.
    bool computeBindings(const Resources &r, int index, QList<QRhiShaderResourceBinding> *out) const;
    void pack(QRhi *rhi, const ColorTarget &target);
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
    SceneTargets m_targets;                  // N3.1 (D14 choice B: the content owns its targets)
    ModeMeshes m_meshes;                     // N3.2 (D15 choice A: the content owns its meshes)
    ModeStreams m_streams;                   // N3.2: the streams and the block arena
    QByteArray m_arena;                      // N3.2: the arena's CPU copy, written whole per drawn record (choice D)
    QStringList m_meshesLost;                // N3.2: drawn meshes with nothing to upload from (a content made again)
    // N3.2 audit 4's side defect: the waiting reason (textures uploading or lost, meshes lost), made at its edge only,
    // and what it was made for.
    bool m_waitingValid = false;
    quint64 m_waitingProgram = 0;
    int m_waitingJobs = 0;
    quint64 m_waitingMeshes = 0;
    QStringList m_waitingLost;
    QString m_waitingReason;
    QByteArray m_batchShadow;                // N3.2: the batched passes' indirect commands (form 3), written per record
    quint64 m_meshBuffersNoted = ~quint64(0); // N3.2: the meshes' and streams' objects the state was last noted for
    quint64 m_targetObjectsSeen = 0;         // the targets' object generation the bindings were made over
    quint64 m_targetReadsDone = 0;           // N3.1, harness: readback requests served
    QList<QSize> m_passTargets;              // N3.1: each pass's target content size (packed with the frame)
    // N3.3 (D16): the storage (choice B: the content's), its trigger bookkeeping per compute entry and the harness's
    // readbacks served.
    struct ComputeTrack
    {
        bool dispatched = false;             // since the content was made (a new program keeps it by the entry's name)
        bool changed = false;                // a new program changed the entry (pack, bindings, trigger): due once
        quint64 lastTrigger = 0;
        quint64 freshSeen = 0;               // audit 5 M2: its bindings' largest storage serial at its last dispatch
        quint64 dispatches = 0;
        // What the entry was, to find it in the next program (set at a program edge only, never per record).
        QByteArray name;
        QShader shader;
        QList<ComputeBinding> bindings;
        ComputeTrigger trigger;
    };
    // Audit 5 M2: the largest serial ModeStorage made the entry's storage bindings zeroed at (0: none).
    quint64 entryFreshKey(const ModePass &pass) const;
    // Audit 5 M2: the tracks of a new program, each entry's kept from the last program by its name.
    void retrackCompute(const ModeProgram &program);
    ModeStorage m_storage;
    ComputeTrack m_compute[kMaxModePasses];
    bool m_dispatch[kMaxModePasses] = {};
    quint64 m_computeProgram = 0;            // the program the tracks are of
    quint64 m_freshGeneration = 0;           // the storage made again (fresh) this many times
    quint64 m_storageObjectsSeen = 0;        // the storage's objects the bindings were made over
    quint64 m_storageNoted = ~quint64(0);    // the storage's objects the state was last noted for
    bool m_storageHeldHere = false;          // this content made storage (a later one of the source finds it lost)
    quint64 m_storageReadsDone = 0;          // harness readbacks served
    // N3.4 (D17): the stages' objects (the content's), the program's bloom and defocus steps (derived once per program),
    // the device gate's answer (decided per QRhi, program and harness control: never per record) and the stages' object
    // generation the bindings were made over.
    PostStages m_post;
    QList<BloomSpec> m_bloomSpecs;
    QList<DefocusSpec> m_defocusSpecs;
    quint64 m_specsProgram = 0;
    bool m_stagesDeclared = false;            // the drawn program holds a stage step (its records' time is counted)
    const QRhi *m_gateRhi = nullptr;
    quint64 m_gateProgram = 0;
    quint64 m_gateControls = 0;
    quint64 m_gateSampleControls = 0;
    quint32 m_dormant = 0;                   // the transparency targets not admitted on this device (bit: target)
    quint64 m_postObjectsSeen = 0;
    // The target a pass draws into this record: its own, or a dormant transparency target's owner (the sorted fallback).
    int effectiveTarget(int pass) const;
    // N3.4: the gate (D17 point 3) at its edge, the stages' objects at the targets' sizes; false with the reason.
    void decideTransparencyGate(QRhi *rhi);
    bool syncStages(QRhi *rhi, QString *error);
    // N3.4: the read level of a defocus step (its block's u_defocus_level as packed) and its radius.
    int defocusLevel(int pass) const;
    float defocusRadius(int pass) const;
    // N3.4: a defocus step's record: the layer's mips and the clip, then a run on the onto target with the gather and the
    // sprites (cleared there first when no pass drew it yet this record).
    void recordDefocus(QRhi *rhi, QRhiCommandBuffer *cb, int index, QRhiResourceUpdateBatch **pending, bool *cleared,
                       bool readback);
    // N3.4: each defocus step's block offsets of its level and radius (derived with the specs, never per record).
    int m_defocusLevelOffset[kMaxModePasses] = {};
    int m_defocusRadiusOffset[kMaxModePasses] = {};
};

} // namespace srpss_core
