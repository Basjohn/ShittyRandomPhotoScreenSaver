// Meshes and buffers (N3.2, D15): mesh_buffers.h has the contract.
#include "mesh_buffers.h"

#include "frame_abi_generated.h"

#include <QtCore/QJsonDocument>
#include <QtCore/QJsonParseError>

#include <cstring>

namespace srpss_core {

namespace fa = frame_abi;

const char kBuiltinQuadMesh[] = "quad";
const char kBatchMember[] = "u_srpss_batch";

namespace {

QAtomicInteger<int> g_meshes { 0 };
QAtomicInteger<qint64> g_meshBytes { 0 };
QAtomicInteger<int> g_meshImages { 0 };
QAtomicInteger<qint64> g_meshImageBytes { 0 };
QAtomicInteger<qint64> g_meshUploads { 0 };
QAtomicInteger<int> g_streams { 0 };
QAtomicInteger<qint64> g_streamBytes { 0 };
QAtomicInteger<qint64> g_streamWrites { 0 };
QAtomicInteger<qint64> g_streamBytesWritten { 0 };
QAtomicInteger<int> g_arenas { 0 };
QAtomicInteger<qint64> g_arenaBytes { 0 };
QAtomicInteger<qint64> g_arenaWrites { 0 };
QAtomicInteger<qint64> g_buffersCreated { 0 };
QAtomicInteger<qint64> g_indirectDraws { 0 };
QAtomicInteger<qint64> g_batchedIndirect { 0 };
QAtomicInteger<qint64> g_batchedLoop { 0 };
QAtomicInteger<quint64> g_meshGenerations { 0 };
QAtomicInteger<int> g_hideDrawParameters { 0 };
QAtomicInteger<quint32> g_directFirstInstance { 0 };
QAtomicInteger<int> g_recreateStreams { 0 };
QAtomicInteger<int> g_skipMeshRelease { 0 };

// The item quad of the Python host (render_host.py _ensure_quad): (0,0), (1,0), (0,1), (1,1), a strip.
constexpr float kQuadVertices[8] = { 0.0f, 0.0f, 1.0f, 0.0f, 0.0f, 1.0f, 1.0f, 1.0f };

bool identifier(const QByteArray &name, bool upper)
{
    if (name.isEmpty() || name.size() > 64 || (name.at(0) >= '0' && name.at(0) <= '9'))
        return false;
    for (const char c : name) {
        const bool ok = (c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') || c == '_' || (upper && c >= 'A' && c <= 'Z');
        if (!ok)
            return false;
    }
    return true;
}

bool u32Of(const QJsonValue &value, quint32 *out)
{
    if (!value.isDouble())
        return false;
    const double number = value.toDouble();
    if (!(number >= 0.0 && number <= 4294967295.0) || number != double(qint64(number)))
        return false;
    *out = quint32(number);
    return true;
}

const char *const kBlendOps[] = { "add", "subtract", "reverse_subtract", "min", "max" };
const char *const kBlendFactors[] = { "zero", "one", "src_color", "one_minus_src_color", "dst_color",
                                      "one_minus_dst_color", "src_alpha", "one_minus_src_alpha", "dst_alpha",
                                      "one_minus_dst_alpha" };

QRhiGraphicsPipeline::BlendOp rhiOp(int i)
{
    switch (i) {
    case 1: return QRhiGraphicsPipeline::Subtract;
    case 2: return QRhiGraphicsPipeline::ReverseSubtract;
    case 3: return QRhiGraphicsPipeline::Min;
    case 4: return QRhiGraphicsPipeline::Max;
    default: return QRhiGraphicsPipeline::Add;
    }
}

int opIndex(QRhiGraphicsPipeline::BlendOp op)
{
    switch (op) {
    case QRhiGraphicsPipeline::Subtract: return 1;
    case QRhiGraphicsPipeline::ReverseSubtract: return 2;
    case QRhiGraphicsPipeline::Min: return 3;
    case QRhiGraphicsPipeline::Max: return 4;
    default: return 0;
    }
}

QRhiGraphicsPipeline::BlendFactor rhiFactor(int i)
{
    static const QRhiGraphicsPipeline::BlendFactor factors[] = {
        QRhiGraphicsPipeline::Zero, QRhiGraphicsPipeline::One, QRhiGraphicsPipeline::SrcColor,
        QRhiGraphicsPipeline::OneMinusSrcColor, QRhiGraphicsPipeline::DstColor, QRhiGraphicsPipeline::OneMinusDstColor,
        QRhiGraphicsPipeline::SrcAlpha, QRhiGraphicsPipeline::OneMinusSrcAlpha, QRhiGraphicsPipeline::DstAlpha,
        QRhiGraphicsPipeline::OneMinusDstAlpha };
    return factors[qBound(0, i, 9)];
}

int factorIndex(QRhiGraphicsPipeline::BlendFactor factor)
{
    for (int i = 0; i < 10; ++i) {
        if (rhiFactor(i) == factor)
            return i;
    }
    return -1;
}

int indexOf(const QString &text, const char *const *names, int count)
{
    for (int i = 0; i < count; ++i) {
        if (text == QLatin1String(names[i]))
            return i;
    }
    return -1;
}

bool parseBlendTriple(const QJsonValue &value, QRhiGraphicsPipeline::BlendOp *op, QRhiGraphicsPipeline::BlendFactor *src,
                      QRhiGraphicsPipeline::BlendFactor *dst)
{
    const QJsonArray a = value.toArray();
    if (!value.isArray() || a.size() != 3)
        return false;
    const int o = indexOf(a.at(0).toString(), kBlendOps, 5);
    const int s = indexOf(a.at(1).toString(), kBlendFactors, 10);
    const int d = indexOf(a.at(2).toString(), kBlendFactors, 10);
    if (o < 0 || s < 0 || d < 0)
        return false;
    *op = rhiOp(o);
    *src = rhiFactor(s);
    *dst = rhiFactor(d);
    return true;
}

QJsonArray tripleJson(QRhiGraphicsPipeline::BlendOp op, QRhiGraphicsPipeline::BlendFactor src,
                      QRhiGraphicsPipeline::BlendFactor dst)
{
    const int s = factorIndex(src);
    const int d = factorIndex(dst);
    return QJsonArray { QLatin1String(kBlendOps[opIndex(op)]), s >= 0 ? QLatin1String(kBlendFactors[s]) : QLatin1String("?"),
                        d >= 0 ? QLatin1String(kBlendFactors[d]) : QLatin1String("?") };
}

void countBuffer(QAtomicInteger<int> &live, QAtomicInteger<qint64> &bytes, qint64 size, int sign)
{
    live.fetchAndAddRelaxed(sign);
    bytes.fetchAndAddRelaxed(sign * size);
}

} // namespace

// ------------------------------------------------------------------------------------------- declarations

const MeshAttribute *RecordLayout::attribute(const QByteArray &name) const
{
    for (const MeshAttribute &a : attributes) {
        if (a.name == name)
            return &a;
    }
    return nullptr;
}

QJsonObject RecordLayout::toJson() const
{
    QJsonArray list;
    for (const MeshAttribute &a : attributes) {
        list.append(QJsonObject { { QStringLiteral("name"), QString::fromLatin1(a.name) },
                                  { QStringLiteral("components"), a.components },
                                  { QStringLiteral("offset"), double(a.offset) } });
    }
    return QJsonObject { { QStringLiteral("stride"), double(stride) }, { QStringLiteral("attributes"), list } };
}

bool parseRecordLayout(const QJsonValue &value, RecordLayout *out, const QString &label, QString *error)
{
    const QJsonObject o = value.toObject();
    RecordLayout layout;
    const QJsonArray attributes = o.value(QStringLiteral("attributes")).toArray();
    const bool shaped = value.isObject() && o.size() == 2 && u32Of(o.value(QStringLiteral("stride")), &layout.stride)
        && layout.stride > 0 && layout.stride % 4 == 0 && layout.stride <= 256 && !attributes.isEmpty()
        && attributes.size() <= kMaxMeshAttributes;
    if (!shaped) {
        *error = QStringLiteral("%1: a layout is {\"stride\": bytes (a multiple of 4, at most 256), \"attributes\": 1 to "
                                "%2 {\"name\", \"components\": 1 to 4, \"offset\"}}").arg(label).arg(kMaxMeshAttributes);
        return false;
    }
    for (const QJsonValue &entry : attributes) {
        const QJsonObject a = entry.toObject();
        MeshAttribute attribute;
        attribute.name = a.value(QStringLiteral("name")).toString().toLatin1();
        quint32 components = 0;
        const bool ok = entry.isObject() && a.size() == 3 && identifier(attribute.name, true)
            && u32Of(a.value(QStringLiteral("components")), &components) && components >= 1 && components <= 4
            && u32Of(a.value(QStringLiteral("offset")), &attribute.offset) && attribute.offset % 4 == 0
            && attribute.offset + 4 * components <= layout.stride;
        if (!ok || layout.attribute(attribute.name)) {
            *error = QStringLiteral("%1: attribute '%2' is {\"name\": an identifier named once, \"components\": 1 to 4, "
                                    "\"offset\": a multiple of 4 inside the stride}")
                         .arg(label, QString::fromLatin1(attribute.name));
            return false;
        }
        attribute.components = int(components);
        layout.attributes.append(attribute);
    }
    *out = layout;
    return true;
}

QJsonValue DrawCount::toJson() const
{
    switch (kind) {
    case Kind::Named:
        return QString::fromLatin1(name);
    case Kind::Mesh:
        return QStringLiteral("mesh");
    case Kind::Number:
        break;
    }
    return double(number);
}

bool parseDrawCount(const QJsonValue &value, bool meshAllowed, DrawCount *out)
{
    DrawCount count;
    if (value.isDouble()) {
        if (!u32Of(value, &count.number))
            return false;
        *out = count;
        return true;
    }
    const QByteArray text = value.toString().toLatin1();
    if (text == "mesh") {
        if (!meshAllowed)
            return false;
        count.kind = DrawCount::Kind::Mesh;
        *out = count;
        return true;
    }
    if (!value.isString() || !identifier(text, false))
        return false;
    count.kind = DrawCount::Kind::Named;
    count.name = text;
    *out = count;
    return true;
}

QString streamKindName(StreamKind kind)
{
    return kind == StreamKind::Instance ? QStringLiteral("instance")
        : kind == StreamKind::Indirect ? QStringLiteral("indirect")
                                        : QStringLiteral("storage");
}

QJsonObject StreamDeclaration::toJson() const
{
    QJsonObject o;
    o.insert(QStringLiteral("name"), QString::fromLatin1(name));
    o.insert(QStringLiteral("field"), QString::fromLatin1(field));
    o.insert(QStringLiteral("kind"), streamKindName(kind));
    if (kind == StreamKind::Instance)
        o.insert(QStringLiteral("layout"), layout.toJson());
    o.insert(QStringLiteral("capacity"), double(capacity));
    return o;
}

bool parseStreamDeclaration(const QJsonValue &value, StreamDeclaration *out, QString *error)
{
    const QJsonObject o = value.toObject();
    StreamDeclaration s;
    s.name = o.value(QStringLiteral("name")).toString().toLatin1();
    s.field = o.value(QStringLiteral("field")).toString().toLatin1();
    const QString kind = o.value(QStringLiteral("kind")).toString();
    const bool instance = kind == QLatin1String("instance");
    s.kind = instance ? StreamKind::Instance
        : kind == QLatin1String("indirect") ? StreamKind::Indirect
                                            : StreamKind::Storage;
    const bool known = instance || kind == QLatin1String("storage") || kind == QLatin1String("indirect");
    if (!value.isObject() || !known || o.size() != (instance ? 4 : 3) || !identifier(s.name, false)
        || !identifier(s.field, false)) {
        *error = QStringLiteral("a stream is {\"name\", \"field\": the record's array field, \"kind\": instance, storage "
                                "or indirect, \"layout\": {...} (instance only)}");
        return false;
    }
    if (instance && !parseRecordLayout(o.value(QStringLiteral("layout")), &s.layout,
                                       QStringLiteral("stream '%1'").arg(QString::fromLatin1(s.name)), error))
        return false;
    *out = s;
    return true;
}

QString streamFieldFits(const StreamDeclaration &stream, const fa::Field &field)
{
    const QString label = QStringLiteral("stream '%1' (field '%2')")
                              .arg(QString::fromLatin1(stream.name), QLatin1String(field.name));
    const bool f32 = field.kind == fa::FieldKind::F32;
    const bool u32 = field.kind == fa::FieldKind::U32;
    if (stream.kind == StreamKind::Instance && !f32)
        return QStringLiteral("%1: an instance stream reads an f32 field").arg(label);
    if (stream.kind == StreamKind::Storage && !(f32 || (u32 && field.count > 1)))
        return QStringLiteral("%1: a storage stream reads an f32 field or a u32 array").arg(label);
    if (stream.kind == StreamKind::Indirect && !(u32 && field.count % 4 == 0))
        return QStringLiteral("%1: an indirect stream reads a u32 array of four-number commands").arg(label);
    const quint32 bytes = 4u * field.count;
    if (stream.kind == StreamKind::Instance && bytes % stream.layout.stride != 0)
        return QStringLiteral("%1: %2 bytes are not whole %3-byte records").arg(label).arg(bytes).arg(stream.layout.stride);
    return QString();
}

bool parseBlendObject(const QJsonValue &value, QRhiGraphicsPipeline::TargetBlend *out)
{
    const QJsonObject o = value.toObject();
    QRhiGraphicsPipeline::TargetBlend b;
    b.enable = true;
    if (!value.isObject() || o.size() != 2
        || !parseBlendTriple(o.value(QStringLiteral("color")), &b.opColor, &b.srcColor, &b.dstColor)
        || !parseBlendTriple(o.value(QStringLiteral("alpha")), &b.opAlpha, &b.srcAlpha, &b.dstAlpha))
        return false;
    *out = b;
    return true;
}

QJsonObject blendJson(const QRhiGraphicsPipeline::TargetBlend &b)
{
    return QJsonObject { { QStringLiteral("color"), tripleJson(b.opColor, b.srcColor, b.dstColor) },
                         { QStringLiteral("alpha"), tripleJson(b.opAlpha, b.srcAlpha, b.dstAlpha) } };
}

ArenaLayout arenaLayout(const QList<quint32> &sizes, int alignment)
{
    ArenaLayout layout;
    const quint32 align = quint32(qMax(1, alignment));
    quint32 offset = 0;
    for (const quint32 size : sizes) {
        offset = (offset + align - 1) / align * align;
        layout.offsets.append(offset);
        offset += size;
    }
    layout.size = (offset + align - 1) / align * align;
    return layout;
}

// ------------------------------------------------------------------------------------------- meshes (GUI thread)

MeshImage::MeshImage(const QByteArray &verticesIn, const QByteArray &instancesIn)
    : vertices(verticesIn), instances(instancesIn)
{
    g_meshImages.fetchAndAddRelaxed(1);
    g_meshImageBytes.fetchAndAddRelaxed(qint64(vertices.size()) + qint64(instances.size()));
}

MeshImage::~MeshImage()
{
    g_meshImages.fetchAndAddRelaxed(-1);
    g_meshImageBytes.fetchAndAddRelaxed(-(qint64(vertices.size()) + qint64(instances.size())));
}

QJsonObject ModeMesh::toJson() const
{
    QJsonObject o;
    o.insert(QStringLiteral("name"), QString::fromLatin1(name));
    o.insert(QStringLiteral("generation"), double(generation));
    o.insert(QStringLiteral("vertices"), vertexLayout.toJson());
    o.insert(QStringLiteral("vertex_count"), double(vertexCount));
    o.insert(QStringLiteral("instances"), instanceLayout.valid() ? QJsonValue(instanceLayout.toJson()) : QJsonValue());
    o.insert(QStringLiteral("instance_count"), double(instanceCount));
    o.insert(QStringLiteral("image_held"), !image.isNull());
    return o;
}

bool makeModeMesh(const QByteArray &name, const QByteArray &declaration, const QByteArray &vertices,
                  const QByteArray &instances, ModeMesh *out, QString *error)
{
    const QString label = QStringLiteral("mesh '%1'").arg(QString::fromLatin1(name));
    if (!identifier(name, false) || name == kBuiltinQuadMesh) {
        *error = QStringLiteral("a mesh's name is an identifier (a-z, 0-9, _; at most 64), not the built-in 'quad'");
        return false;
    }
    QJsonParseError parse;
    const QJsonDocument document = QJsonDocument::fromJson(declaration, &parse);
    const QJsonObject o = document.object();
    const bool withInstances = o.contains(QStringLiteral("instances"));
    if (parse.error != QJsonParseError::NoError || !document.isObject() || o.size() != (withInstances ? 2 : 1)) {
        *error = QStringLiteral("%1: its declaration is {\"vertices\": a layout, \"instances\"?: a layout}").arg(label);
        return false;
    }
    ModeMesh mesh;
    mesh.name = name;
    if (!parseRecordLayout(o.value(QStringLiteral("vertices")), &mesh.vertexLayout, label + QStringLiteral(" vertices"),
                           error))
        return false;
    if (withInstances && !parseRecordLayout(o.value(QStringLiteral("instances")), &mesh.instanceLayout,
                                            label + QStringLiteral(" instances"), error))
        return false;
    if (vertices.isEmpty() || vertices.size() % mesh.vertexLayout.stride != 0
        || (withInstances && (instances.isEmpty() || instances.size() % mesh.instanceLayout.stride != 0))
        || (!withInstances && !instances.isEmpty())
        || qint64(vertices.size()) + qint64(instances.size()) > kMaxMeshBytes) {
        *error = QStringLiteral("%1: %2 vertex bytes and %3 instance bytes are not whole records of their strides, or "
                                "pass %4 bytes").arg(label).arg(vertices.size()).arg(instances.size()).arg(kMaxMeshBytes);
        return false;
    }
    mesh.vertexCount = quint32(vertices.size()) / mesh.vertexLayout.stride;
    mesh.instanceCount = withInstances ? quint32(instances.size()) / mesh.instanceLayout.stride : 0u;
    mesh.generation = g_meshGenerations.fetchAndAddRelaxed(1) + 1;
    mesh.image = QSharedPointer<MeshImage>::create(vertices, instances);
    *out = mesh;
    return true;
}

// ------------------------------------------------------------------------------------------- counts and controls

MeshBufferCounts meshBufferCounts()
{
    MeshBufferCounts c;
    c.meshes = g_meshes.loadRelaxed();
    c.meshBytes = g_meshBytes.loadRelaxed();
    c.meshImages = g_meshImages.loadRelaxed();
    c.meshImageBytes = g_meshImageBytes.loadRelaxed();
    c.meshUploads = g_meshUploads.loadRelaxed();
    c.streams = g_streams.loadRelaxed();
    c.streamBytes = g_streamBytes.loadRelaxed();
    c.streamWrites = g_streamWrites.loadRelaxed();
    c.streamBytesWritten = g_streamBytesWritten.loadRelaxed();
    c.arenas = g_arenas.loadRelaxed();
    c.arenaBytes = g_arenaBytes.loadRelaxed();
    c.arenaWrites = g_arenaWrites.loadRelaxed();
    c.buffersCreated = g_buffersCreated.loadRelaxed();
    c.indirectDraws = g_indirectDraws.loadRelaxed();
    c.batchedIndirect = g_batchedIndirect.loadRelaxed();
    c.batchedLoop = g_batchedLoop.loadRelaxed();
    return c;
}

void countIndirectDraw() { g_indirectDraws.fetchAndAddRelaxed(1); }
void countBatched(bool indirect) { (indirect ? g_batchedIndirect : g_batchedLoop).fetchAndAddRelaxed(1); }
void meshesCountUpload() { g_meshUploads.fetchAndAddRelaxed(1); }

void setHideDrawParameters(bool hide) { g_hideDrawParameters.storeRelaxed(hide ? 1 : 0); }
bool hideDrawParameters() { return g_hideDrawParameters.loadRelaxed() != 0; }
void setDirectFirstInstance(quint32 first) { g_directFirstInstance.storeRelaxed(first); }
quint32 directFirstInstance() { return g_directFirstInstance.loadRelaxed(); }
void setRecreateStreams(bool recreate) { g_recreateStreams.storeRelaxed(recreate ? 1 : 0); }
bool recreateStreams() { return g_recreateStreams.loadRelaxed() != 0; }
void setSkipMeshRelease(bool skip) { g_skipMeshRelease.storeRelaxed(skip ? 1 : 0); }
bool skipMeshRelease() { return g_skipMeshRelease.loadRelaxed() != 0; }

bool drawParametersAvailable(QRhi *rhi)
{
    return rhi && !hideDrawParameters() && rhi->isFeatureSupported(QRhi::DrawIndirect)
        && rhi->isFeatureSupported(QRhi::DrawIndirectMulti) && rhi->isFeatureSupported(QRhi::ShaderDrawParameters);
}

// ------------------------------------------------------------------------------------------- ModeMeshes

ModeMeshes::~ModeMeshes()
{
    release();
}

const ModeMeshes::Gpu *ModeMeshes::find(const QByteArray &name) const
{
    for (const Gpu &gpu : m_meshes) {
        if (!gpu.name.isEmpty() && gpu.name == name && gpu.vertices)
            return &gpu;
    }
    return nullptr;
}

int ModeMeshes::live() const
{
    int n = 0;
    for (const Gpu &gpu : m_meshes)
        n += (gpu.vertices ? 1 : 0) + (gpu.instances ? 1 : 0);
    return n;
}

void ModeMeshes::releaseGpu(Gpu &gpu)
{
    if (gpu.vertices)
        countBuffer(g_meshes, g_meshBytes, gpu.bytes, -1);
    gpu.vertices.reset();                     // QRhi releases the native buffer after the frames that use it
    gpu.instances.reset();
    gpu.name.clear();
    gpu.generation = 0;
    gpu.bytes = 0;
    ++m_objects;
}

void ModeMeshes::release()
{
    if (skipMeshRelease())
        return;                               // the retirement proof's control: the meshes left behind (counted)
    for (Gpu &gpu : m_meshes) {
        if (gpu.vertices || !gpu.name.isEmpty())
            releaseGpu(gpu);
    }
}

bool ModeMeshes::upload(QRhi *rhi, QRhiResourceUpdateBatch *updates, Gpu &gpu, const ModeMesh &mesh,
                        const QSharedPointer<MeshImage> &image, QStringList *lost)
{
    std::unique_ptr<QRhiBuffer> vertices(rhi->newBuffer(QRhiBuffer::Immutable, QRhiBuffer::VertexBuffer,
                                                        quint32(image->vertices.size())));
    vertices->setName(QByteArrayLiteral("srpss core mesh ") + mesh.name);
    std::unique_ptr<QRhiBuffer> instances;
    bool ok = vertices->create();
    g_buffersCreated.fetchAndAddRelaxed(1);
    if (ok && !image->instances.isEmpty()) {
        instances.reset(rhi->newBuffer(QRhiBuffer::Immutable, QRhiBuffer::VertexBuffer,
                                       quint32(image->instances.size())));
        instances->setName(QByteArrayLiteral("srpss core mesh instances ") + mesh.name);
        ok = instances->create();
        g_buffersCreated.fetchAndAddRelaxed(1);
    }
    if (!ok) {
        lost->append(QStringLiteral("%1 could not be created").arg(QString::fromLatin1(mesh.name)));
        return false;
    }
    // The bytes are implicitly shared with the batch (the QByteArray overload): no copy; the core's copy goes with the
    // image once the batch is done.
    updates->uploadStaticBuffer(vertices.get(), image->vertices);
    if (instances)
        updates->uploadStaticBuffer(instances.get(), image->instances);
    if (gpu.vertices)
        releaseGpu(gpu);                      // the one it replaces (this record draws the new one)
    gpu.name = mesh.name;
    gpu.generation = mesh.generation;
    gpu.vertexLayout = mesh.vertexLayout;
    gpu.instanceLayout = mesh.instanceLayout;
    gpu.vertexCount = mesh.vertexCount;
    gpu.instanceCount = mesh.instanceCount;
    gpu.vertices = std::move(vertices);
    gpu.instances = std::move(instances);
    gpu.bytes = qint64(image->vertices.size()) + qint64(image->instances.size());
    countBuffer(g_meshes, g_meshBytes, gpu.bytes, 1);
    meshesCountUpload();
    m_uploaded = true;
    ++m_objects;
    return true;
}

bool ModeMeshes::ensureQuad(QRhi *rhi, QRhiResourceUpdateBatch *updates)
{
    Gpu &quad = m_meshes[kMaxModeMeshes];
    if (quad.vertices)
        return true;
    quad.vertices.reset(rhi->newBuffer(QRhiBuffer::Immutable, QRhiBuffer::VertexBuffer, sizeof(kQuadVertices)));
    quad.vertices->setName(QByteArrayLiteral("srpss core mesh quad"));
    g_buffersCreated.fetchAndAddRelaxed(1);
    if (!quad.vertices->create()) {
        quad.vertices.reset();
        return false;
    }
    updates->uploadStaticBuffer(quad.vertices.get(), kQuadVertices);
    quad.name = kBuiltinQuadMesh;
    quad.generation = 1;
    quad.vertexLayout.stride = 2 * sizeof(float);
    quad.vertexLayout.attributes = { MeshAttribute { QByteArrayLiteral("aPosition"), 2, 0 } };
    quad.vertexCount = 4;
    quad.bytes = sizeof(kQuadVertices);
    countBuffer(g_meshes, g_meshBytes, quad.bytes, 1);
    ++m_objects;
    return true;
}

QJsonArray ModeMeshes::stateJson() const
{
    QJsonArray list;
    for (const Gpu &gpu : m_meshes) {
        if (!gpu.vertices)
            continue;
        list.append(QJsonObject { { QStringLiteral("name"), QString::fromLatin1(gpu.name) },
                                  { QStringLiteral("generation"), double(gpu.generation) },
                                  { QStringLiteral("vertex_count"), double(gpu.vertexCount) },
                                  { QStringLiteral("instance_count"), double(gpu.instanceCount) },
                                  { QStringLiteral("bytes"), double(gpu.bytes) } });
    }
    return list;
}

// ------------------------------------------------------------------------------------------- ModeStreams

ModeStreams::~ModeStreams()
{
    release();
}

void ModeStreams::release()
{
    for (Stream *s : m_streams) {
        if (s->buffer)
            countBuffer(g_streams, g_streamBytes, qint64(s->buffer->size()), -1);
        delete s;
    }
    m_streams.clear();
    if (m_arena)
        countBuffer(g_arenas, g_arenaBytes, qint64(m_arena->size()), -1);
    m_arena.reset();
    if (m_batchCommands)
        countBuffer(g_streams, g_streamBytes, qint64(m_batchCommands->size()), -1);
    m_batchCommands.reset();
    m_arenaBytes = 0;
}

int ModeStreams::live() const
{
    int n = m_arena ? 1 : 0;
    n += m_batchCommands ? 1 : 0;
    for (const Stream *s : m_streams)
        n += s->buffer ? 1 : 0;
    return n;
}

const ModeStreams::Stream *ModeStreams::find(const QByteArray &name) const
{
    for (const Stream *s : m_streams) {
        if (s->decl.name == name)
            return s;
    }
    return nullptr;
}

bool ModeStreams::build(QRhi *rhi, const QList<StreamDeclaration> &streams, const fa::Schema *schema,
                        quint32 arenaBytes, quint32 indirectBatchBytes, QString *error)
{
    release();
    ++m_generation;
    for (const StreamDeclaration &decl : streams) {
        const fa::Field *field = nullptr;
        for (quint32 i = 0; schema && i < schema->fieldCount; ++i) {
            if (decl.field == schema->fields[i].name)
                field = &schema->fields[i];
        }
        if (!field) {
            *error = QStringLiteral("stream '%1': the record has no field '%2'")
                         .arg(QString::fromLatin1(decl.name), QString::fromLatin1(decl.field));
            release();
            return false;
        }
        const quint32 bytes = 4u * field->count;
        std::unique_ptr<Stream> s(new Stream);
        s->decl = decl;
        s->decl.capacity = bytes;
        s->field = field;
        switch (decl.kind) {
        case StreamKind::Instance:
            s->buffer.reset(rhi->newBuffer(QRhiBuffer::Dynamic, QRhiBuffer::VertexBuffer, bytes));
            break;
        case StreamKind::Storage:
            s->buffer.reset(rhi->newBuffer(QRhiBuffer::Static, QRhiBuffer::StorageBuffer, bytes));
            s->staging.resize(qsizetype(bytes));
            break;
        case StreamKind::Indirect:
            s->buffer.reset(rhi->newBuffer(QRhiBuffer::Dynamic, QRhiBuffer::IndirectBuffer, bytes));
            break;
        }
        s->buffer->setName(QByteArrayLiteral("srpss core stream ") + decl.name);
        g_buffersCreated.fetchAndAddRelaxed(1);
        if (!s->buffer->create()) {
            *error = QStringLiteral("stream '%1' (%2 bytes) could not be created")
                         .arg(QString::fromLatin1(decl.name)).arg(bytes);
            release();
            return false;
        }
        countBuffer(g_streams, g_streamBytes, qint64(bytes), 1);
        m_streams.append(s.release());
    }
    if (arenaBytes > 0) {
        m_arena.reset(rhi->newBuffer(QRhiBuffer::Dynamic, QRhiBuffer::UniformBuffer, arenaBytes));
        m_arena->setName(QByteArrayLiteral("srpss core block arena"));
        g_buffersCreated.fetchAndAddRelaxed(1);
        if (!m_arena->create()) {
            *error = QStringLiteral("the block arena (%1 bytes) could not be created").arg(arenaBytes);
            release();
            return false;
        }
        countBuffer(g_arenas, g_arenaBytes, qint64(arenaBytes), 1);
        m_arenaBytes = arenaBytes;
    }
    if (indirectBatchBytes > 0) {
        m_batchCommands.reset(rhi->newBuffer(QRhiBuffer::Dynamic, QRhiBuffer::IndirectBuffer, indirectBatchBytes));
        m_batchCommands->setName(QByteArrayLiteral("srpss core batched draw commands"));
        g_buffersCreated.fetchAndAddRelaxed(1);
        if (!m_batchCommands->create()) {
            *error = QStringLiteral("a batched draw's commands (%1 bytes) could not be created").arg(indirectBatchBytes);
            release();
            return false;
        }
        countBuffer(g_streams, g_streamBytes, qint64(indirectBatchBytes), 1);
    }
    return true;
}

void ModeStreams::write(QRhi *rhi, QRhiResourceUpdateBatch *updates, const QByteArray &record)
{
    for (Stream *s : m_streams) {
        if (recreateStreams() && s->decl.kind != StreamKind::Storage) {
            // The no-allocation proof's control: a stream made again at every record (the counts grow). Not a storage
            // stream: the pass's bindings name it (an instance or indirect stream is given per draw).
            const QRhiBuffer::Type type = s->buffer->type();
            const QRhiBuffer::UsageFlags usage = s->buffer->usage();
            const quint32 size = s->buffer->size();
            s->buffer.reset(rhi->newBuffer(type, usage, size));
            g_buffersCreated.fetchAndAddRelaxed(1);
            if (!s->buffer->create())
                continue;
        }
        const quint32 bytes = s->decl.capacity;
        if (quint64(s->field->offset) + bytes > quint64(record.size()))
            continue;                         // the record is the schema's (checked at its accept): never reached
        const char *data = record.constData() + s->field->offset;
        if (s->decl.kind == StreamKind::Storage) {
            // The QByteArray overload with bytes kept across records (D15 point 4): the batch takes a reference; the
            // write below detaches only if a batch still holds the last record's (it was released with its frame).
            std::memcpy(s->staging.data(), data, bytes);
            updates->uploadStaticBuffer(s->buffer.get(), 0, s->staging);
        } else {
            char *p = s->buffer->beginFullDynamicBufferUpdateForCurrentFrame();
            if (p)
                std::memcpy(p, data, bytes);
            s->buffer->endFullDynamicBufferUpdateForCurrentFrame();
        }
        s->used = bytes;
        g_streamWrites.fetchAndAddRelaxed(1);
        g_streamBytesWritten.fetchAndAddRelaxed(bytes);
    }
}

void ModeStreams::writeArena(const QByteArray &bytes)
{
    if (!m_arena)
        return;
    char *p = m_arena->beginFullDynamicBufferUpdateForCurrentFrame();
    if (p)
        std::memcpy(p, bytes.constData(), size_t(qMin(quint32(bytes.size()), m_arenaBytes)));
    m_arena->endFullDynamicBufferUpdateForCurrentFrame();
    g_arenaWrites.fetchAndAddRelaxed(1);
}

void ModeStreams::writeBatchCommands(const char *bytes, quint32 size)
{
    if (!m_batchCommands)
        return;
    char *p = m_batchCommands->beginFullDynamicBufferUpdateForCurrentFrame();
    if (p)
        std::memcpy(p, bytes, size_t(qMin(size, m_batchCommands->size())));
    m_batchCommands->endFullDynamicBufferUpdateForCurrentFrame();
}

QJsonObject ModeStreams::stateJson() const
{
    QJsonArray list;
    for (const Stream *s : m_streams)
        list.append(s->decl.toJson());
    QJsonObject o;
    o.insert(QStringLiteral("streams"), list);
    o.insert(QStringLiteral("arena_bytes"), double(m_arenaBytes));
    o.insert(QStringLiteral("batch_command_bytes"), m_batchCommands ? double(m_batchCommands->size()) : 0.0);
    o.insert(QStringLiteral("generation"), double(m_generation));
    return o;
}

} // namespace srpss_core
