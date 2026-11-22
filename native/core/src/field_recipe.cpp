// Field recipes (ABI 43, N5.2g): field_recipe.h has the contract.
#include "field_recipe.h"

#include "mode_content.h" // ModeTextureFormat

#include <QtCore/QAtomicInteger>
#include <QtCore/QJsonArray>
#include <QtCore/QJsonDocument>
#include <QtCore/QJsonValue>

#include <cstring>

namespace srpss_core {

namespace {

QAtomicInteger<qint64> g_recorded { 0 };
QAtomicInteger<qint64> g_dispatches { 0 };
QAtomicInteger<qint64> g_pipelines { 0 };
QAtomicInteger<int> g_recorders { 0 };

bool identifier(const QByteArray &name)
{
    if (name.isEmpty() || name.size() > 64)
        return false;
    for (const char c : name) {
        if (!((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9') || c == '_'))
            return false;
    }
    return true;
}

quint64 bytesKey(const QByteArray &bytes)
{
    // FNV-1a over the pack (its key in the recorder's pipeline list; the size is folded in as well).
    quint64 h = 1469598103934665603ull ^ quint64(bytes.size());
    for (const char c : bytes) {
        h ^= quint64(quint8(c));
        h *= 1099511628211ull;
    }
    return h;
}

bool accessFits(StorageAccess access, bool readOnly, bool writeOnly)
{
    if (readOnly)
        return access == StorageAccess::Read;
    if (writeOnly)
        return access == StorageAccess::Write;
    return access != StorageAccess::Read; // the shader can write it: a read declaration would skip its barrier
}

// A binding's kind in a layout (QRhi's layouts compare the kind, not the resource).
char bindingKind(const FieldBinding &b)
{
    if (b.input)
        return 's';
    return b.access == StorageAccess::Read ? 'l' : b.access == StorageAccess::Write ? 'w' : 'x';
}

bool checkDispatch(FieldRecipe &recipe, int index, QString *error)
{
    FieldDispatch &d = recipe.dispatches[index];
    const QString where = QStringLiteral("field dispatch %1").arg(index);
    const QShader &shader = recipe.packs.at(d.pack);
    const QShaderDescription desc = shader.description();
    if (!desc.storageBlocks().isEmpty() || !desc.separateImages().isEmpty() || !desc.separateSamplers().isEmpty()
        || !desc.pushConstantBlocks().isEmpty()) {
        *error = QStringLiteral("%1: its pack declares a storage block, a separate texture or sampler, or a push "
                                "constant (a field reads and writes images only)").arg(where);
        return false;
    }
    QList<int> used;
    const auto claim = [&used](int binding) {
        if (binding < 0 || used.contains(binding))
            return false;
        used.append(binding);
        return true;
    };
    const QList<QShaderDescription::UniformBlock> blocks = desc.uniformBlocks();
    if (blocks.size() > 1) {
        *error = QStringLiteral("%1: its pack declares %2 uniform blocks, a field's dispatch reads one (merge them: "
                                "native_one_block)").arg(where).arg(blocks.size());
        return false;
    }
    d.blockBinding = -1;
    d.blockSize = 0;
    if (blocks.isEmpty()) {
        if (d.block >= 0) {
            *error = QStringLiteral("%1 gives a block, but its pack declares none").arg(where);
            return false;
        }
    } else {
        const QShaderDescription::UniformBlock &b = blocks.first();
        if (b.descriptorSet != 0 || !claim(b.binding)) {
            *error = QStringLiteral("%1: its block '%2' is not on descriptor set 0 at a binding of its own")
                         .arg(where, QString::fromLatin1(b.blockName));
            return false;
        }
        if (d.block < 0) {
            *error = QStringLiteral("unfilled: %1's pack declares the block '%2', which the dispatch gives no bytes")
                         .arg(where, QString::fromLatin1(b.blockName));
            return false;
        }
        const int bytes = int(recipe.blocks.at(d.block).size());
        const int rounded = (b.size + 15) / 16 * 16;
        if (b.size < 1 || bytes < b.size || bytes > rounded) {
            *error = QStringLiteral("%1: the block '%2' is %3 bytes in its pack (std140), but %4 bytes are given")
                         .arg(where, QString::fromLatin1(b.blockName)).arg(b.size).arg(bytes);
            return false;
        }
        d.blockBinding = b.binding;
        d.blockSize = b.size;
    }
    for (FieldBinding &f : d.bindings)
        f.binding = -1;
    const auto bindingFor = [&d](const QByteArray &name) -> FieldBinding * {
        for (FieldBinding &f : d.bindings) {
            if (f.name == name)
                return &f;
        }
        return nullptr;
    };
    for (const QShaderDescription::InOutVariable &image : desc.storageImages()) {
        FieldBinding *f = bindingFor(image.name);
        if (!f || f->input) {
            *error = QStringLiteral("unbound: %1 uses the image '%2', which the dispatch binds to no recipe image")
                         .arg(where, QString::fromLatin1(image.name));
            return false;
        }
        const FieldImage &target = recipe.images.at(f->image);
        if (image.descriptorSet != 0 || image.type != QShaderDescription::Image2D
            || int(image.imageFormat) != storageReflectedFormat(target.format)) {
            *error = QStringLiteral("%1: the image '%2' is not an image2D of the format %3 of recipe image '%4' (set 0)")
                         .arg(where, QString::fromLatin1(image.name), storageFormatName(target.format),
                              QString::fromLatin1(target.name));
            return false;
        }
        const bool readOnly = image.imageFlags.testFlag(QShaderDescription::ReadOnlyImage);
        const bool writeOnly = image.imageFlags.testFlag(QShaderDescription::WriteOnlyImage);
        if (!accessFits(f->access, readOnly, writeOnly)) {
            *error = QStringLiteral("%1: the image '%2' is bound %3, which its qualifiers do not match")
                         .arg(where, QString::fromLatin1(image.name), storageAccessName(f->access));
            return false;
        }
        if (!claim(image.binding)) {
            *error = QStringLiteral("%1: the image '%2' shares binding %3").arg(where, QString::fromLatin1(image.name))
                         .arg(image.binding);
            return false;
        }
        f->binding = image.binding;
    }
    for (const QShaderDescription::InOutVariable &sampler : desc.combinedImageSamplers()) {
        FieldBinding *f = bindingFor(sampler.name);
        if (!f || !f->input || recipe.input.isEmpty()) {
            *error = QStringLiteral("unbound: %1 samples '%2', which the dispatch does not bind to the recipe's input")
                         .arg(where, QString::fromLatin1(sampler.name));
            return false;
        }
        if (sampler.descriptorSet != 0 || sampler.type != QShaderDescription::Sampler2D || !claim(sampler.binding)) {
            *error = QStringLiteral("%1: the sampler '%2' is not a sampler2D on set 0 at a binding of its own")
                         .arg(where, QString::fromLatin1(sampler.name));
            return false;
        }
        f->binding = sampler.binding;
    }
    for (const FieldBinding &f : d.bindings) {
        if (f.binding < 0) {
            *error = QStringLiteral("unknown: %1 binds '%2', which its pack does not declare")
                         .arg(where, QString::fromLatin1(f.name));
            return false;
        }
    }
    return true;
}

} // namespace

// ------------------------------------------------------------------------------------------------- the recipe

bool FieldRecipe::fromJson(const QByteArray &json, const QList<QByteArray> &packs, const QList<QByteArray> &blocks,
                           FieldRecipe *out, QString *error)
{
    FieldRecipe r;
    QJsonParseError parse;
    const QJsonDocument document = QJsonDocument::fromJson(json, &parse);
    if (!document.isObject()) {
        *error = QStringLiteral("a field recipe is a JSON object (%1)").arg(parse.errorString());
        return false;
    }
    const QJsonObject o = document.object();
    if (packs.isEmpty() || packs.size() > kMaxFieldPacks || blocks.size() > kMaxFieldBlocks) {
        *error = QStringLiteral("a field recipe has 1 to %1 packs and at most %2 blocks").arg(kMaxFieldPacks)
                     .arg(kMaxFieldBlocks);
        return false;
    }
    for (int i = 0; i < int(packs.size()); ++i) {
        const QShader shader = QShader::fromSerialized(packs.at(i));
        if (!shader.isValid() || shader.stage() != QShader::ComputeStage) {
            *error = QStringLiteral("field pack %1 is not a compute shader (a .qsb from tools/regen_qrc.py's baker)")
                         .arg(i);
            return false;
        }
        r.packs.append(shader);
        r.packKeys.append(bytesKey(packs.at(i)));
    }
    for (int i = 0; i < int(blocks.size()); ++i) {
        if (blocks.at(i).isEmpty() || blocks.at(i).size() > kMaxFieldBlockBytes) {
            *error = QStringLiteral("field block %1 is 1 to %2 bytes").arg(i).arg(kMaxFieldBlockBytes);
            return false;
        }
        r.blocks.append(blocks.at(i));
    }
    const QJsonValue input = o.value(QStringLiteral("input"));
    if (!input.isUndefined() && !input.isNull()) {
        r.input = input.toString().toLatin1();
        if (!identifier(r.input)) {
            *error = QStringLiteral("a field recipe's input is an item texture's name");
            return false;
        }
    }
    const QJsonArray images = o.value(QStringLiteral("images")).toArray();
    if (images.isEmpty() || images.size() > kMaxFieldImages) {
        *error = QStringLiteral("a field recipe has 1 to %1 images").arg(kMaxFieldImages);
        return false;
    }
    qint64 bytes = 0;
    for (const QJsonValue &value : images) {
        const QJsonObject io = value.toObject();
        FieldImage image;
        image.name = io.value(QStringLiteral("name")).toString().toLatin1();
        const QJsonArray size = io.value(QStringLiteral("size")).toArray();
        image.size = QSize(size.size() == 2 ? size.at(0).toInt() : 0, size.size() == 2 ? size.at(1).toInt() : 0);
        bool named = identifier(image.name);
        for (const FieldImage &other : r.images)
            named = named && other.name != image.name;
        if (!named || !parseStorageFormat(io.value(QStringLiteral("format")).toString(), &image.format)
            || image.size.width() < 1 || image.size.height() < 1 || image.size.width() > kMaxFieldImageSide
            || image.size.height() > kMaxFieldImageSide) {
            *error = QStringLiteral("field image '%1': a name of its own, a format (rgba8, rgba16f, rgba32f, r16f, "
                                    "r32f) and a size of 1 to %2 a side").arg(QString::fromLatin1(image.name))
                         .arg(kMaxFieldImageSide);
            return false;
        }
        bytes += qint64(image.size.width()) * image.size.height() * storageTexelBytes(image.format);
        r.images.append(image);
    }
    if (bytes > kMaxFieldImageBytes) {
        *error = QStringLiteral("a field recipe's images hold %1 bytes, more than %2").arg(bytes)
                     .arg(kMaxFieldImageBytes);
        return false;
    }
    const auto imageIndex = [&r](const QByteArray &name) {
        for (int i = 0; i < int(r.images.size()); ++i) {
            if (r.images.at(i).name == name)
                return i;
        }
        return -1;
    };
    const QJsonArray dispatches = o.value(QStringLiteral("dispatches")).toArray();
    if (dispatches.isEmpty() || dispatches.size() > kMaxFieldDispatches) {
        *error = QStringLiteral("a field recipe has 1 to %1 dispatches").arg(kMaxFieldDispatches);
        return false;
    }
    for (const QJsonValue &value : dispatches) {
        const QJsonObject dobj = value.toObject();
        FieldDispatch d;
        const int index = int(r.dispatches.size());
        d.pack = dobj.value(QStringLiteral("pack")).toInt(-1);
        d.block = dobj.value(QStringLiteral("block")).toInt(-1);
        const QJsonArray groups = dobj.value(QStringLiteral("groups")).toArray();
        bool ok = d.pack >= 0 && d.pack < int(r.packs.size()) && d.block >= -1 && d.block < int(r.blocks.size())
            && groups.size() == 3;
        for (int a = 0; ok && a < 3; ++a) {
            const qint64 g = qint64(groups.at(a).toDouble(-1));
            ok = g >= 1 && g <= qint64(kMaxFieldGroups);
            d.groups[a] = quint32(qMax<qint64>(1, g));
        }
        if (!ok) {
            *error = QStringLiteral("field dispatch %1: a pack, a block (-1: none) and three group counts of 1 to %2")
                         .arg(index).arg(kMaxFieldGroups);
            return false;
        }
        const QJsonObject bindings = dobj.value(QStringLiteral("bindings")).toObject();
        for (auto it = bindings.begin(); it != bindings.end(); ++it) {
            FieldBinding b;
            b.name = it.key().toLatin1();
            if (it.value().isString() && it.value().toString() == QLatin1String("input")) {
                b.input = true;
            } else {
                const QJsonObject bo = it.value().toObject();
                b.image = imageIndex(bo.value(QStringLiteral("image")).toString().toLatin1());
                if (b.image < 0 || !parseStorageAccess(bo.value(QStringLiteral("access")).toString(), &b.access)) {
                    *error = QStringLiteral("field dispatch %1: '%2' binds \"input\" or {\"image\": a recipe image, "
                                            "\"access\": read, write or read_write}").arg(index).arg(it.key());
                    return false;
                }
            }
            d.bindings.append(b);
        }
        r.dispatches.append(d);
        if (!checkDispatch(r, index, error))
            return false;
    }
    const QJsonArray outputs = o.value(QStringLiteral("outputs")).toArray();
    if (outputs.isEmpty() || outputs.size() > kMaxFieldOutputs) {
        *error = QStringLiteral("a field recipe has 1 to %1 outputs").arg(kMaxFieldOutputs);
        return false;
    }
    for (const QJsonValue &value : outputs) {
        const QJsonObject oo = value.toObject();
        FieldOutput output;
        output.image = imageIndex(oo.value(QStringLiteral("image")).toString().toLatin1());
        output.texture = oo.value(QStringLiteral("texture")).toString().toLatin1();
        bool fresh = identifier(output.texture) && output.texture != r.input;
        for (const FieldOutput &other : r.outputs)
            fresh = fresh && other.texture != output.texture && other.image != output.image;
        const QRhiTexture::Format format = output.image >= 0 ? r.images.at(output.image).format : QRhiTexture::RGBA8;
        if (output.image < 0 || !fresh
            || (format != QRhiTexture::RGBA16F && format != QRhiTexture::RGBA32F && format != QRhiTexture::R32F)) {
            *error = QStringLiteral("field output '%1': a recipe image of its own, rgba16f, rgba32f or r32f, as an item "
                                    "texture named once (never the input)").arg(QString::fromLatin1(output.texture));
            return false;
        }
        r.outputs.append(output);
    }
    *out = r;
    return true;
}

QJsonObject FieldRecipe::toJson() const
{
    QJsonObject o;
    o.insert(QStringLiteral("input"), input.isEmpty() ? QJsonValue() : QJsonValue(QString::fromLatin1(input)));
    QJsonArray is;
    for (const FieldImage &i : images) {
        QJsonObject io;
        io.insert(QStringLiteral("name"), QString::fromLatin1(i.name));
        io.insert(QStringLiteral("format"), storageFormatName(i.format));
        io.insert(QStringLiteral("size"), QJsonArray { i.size.width(), i.size.height() });
        is.append(io);
    }
    o.insert(QStringLiteral("images"), is);
    QJsonArray ds;
    for (const FieldDispatch &d : dispatches) {
        QJsonObject dobj;
        dobj.insert(QStringLiteral("pack"), d.pack);
        dobj.insert(QStringLiteral("block"), d.block);
        dobj.insert(QStringLiteral("block_binding"), d.blockBinding);
        dobj.insert(QStringLiteral("block_size"), d.blockSize);
        dobj.insert(QStringLiteral("groups"), QJsonArray { double(d.groups[0]), double(d.groups[1]),
                                                           double(d.groups[2]) });
        QJsonObject bs;
        for (const FieldBinding &b : d.bindings) {
            QJsonObject bo;
            bo.insert(QStringLiteral("binding"), b.binding);
            if (b.input) {
                bo.insert(QStringLiteral("input"), true);
            } else {
                bo.insert(QStringLiteral("image"), QString::fromLatin1(images.at(b.image).name));
                bo.insert(QStringLiteral("access"), storageAccessName(b.access));
            }
            bs.insert(QString::fromLatin1(b.name), bo);
        }
        dobj.insert(QStringLiteral("bindings"), bs);
        ds.append(dobj);
    }
    o.insert(QStringLiteral("dispatches"), ds);
    QJsonArray os;
    for (const FieldOutput &out : outputs) {
        QJsonObject oo;
        oo.insert(QStringLiteral("image"), QString::fromLatin1(images.at(out.image).name));
        oo.insert(QStringLiteral("texture"), QString::fromLatin1(out.texture));
        os.append(oo);
    }
    o.insert(QStringLiteral("outputs"), os);
    o.insert(QStringLiteral("image_bytes"), double(imageBytes()));
    return o;
}

qint64 FieldRecipe::imageBytes() const
{
    qint64 bytes = 0;
    for (const FieldImage &i : images)
        bytes += qint64(i.size.width()) * i.size.height() * storageTexelBytes(i.format);
    return bytes;
}

qint64 FieldRecipe::outputBytes(int output) const
{
    const FieldImage &i = images.at(outputs.at(output).image);
    return qint64(i.size.width()) * i.size.height() * storageTexelBytes(i.format);
}

ModeTextureFormat FieldRecipe::outputFormat(int output) const
{
    switch (images.at(outputs.at(output).image).format) {
    case QRhiTexture::RGBA32F:
        return ModeTextureFormat::RGBA32F;
    case QRhiTexture::R32F:
        return ModeTextureFormat::R32F;
    default:
        break;
    }
    return ModeTextureFormat::RGBA16F;
}

QSize FieldRecipe::outputSize(int output) const
{
    return images.at(outputs.at(output).image).size;
}

FieldCounts fieldCounts()
{
    FieldCounts c;
    c.recorded = g_recorded.loadRelaxed();
    c.dispatches = g_dispatches.loadRelaxed();
    c.pipelines = g_pipelines.loadRelaxed();
    c.recorders = g_recorders.loadRelaxed();
    return c;
}

QJsonObject fieldCountsJson()
{
    const FieldCounts c = fieldCounts();
    QJsonObject o;
    o.insert(QStringLiteral("fields_recorded"), double(c.recorded));
    o.insert(QStringLiteral("field_dispatches"), double(c.dispatches));
    o.insert(QStringLiteral("field_pipelines"), double(c.pipelines));
    o.insert(QStringLiteral("field_recorders"), c.recorders);
    return o;
}

// ------------------------------------------------------------------------------------------------- the recorder

FieldRecorder::~FieldRecorder()
{
    release();
}

void FieldRecorder::release()
{
    m_pipes.clear();
    m_sampler.reset();
    m_placeholder.reset();
    m_placeholderBlock.reset();
    m_rhi = nullptr;
    if (m_counted) {
        g_recorders.fetchAndAddRelaxed(-1);
        m_counted = false;
    }
}

bool FieldRecorder::ensurePlaceholders(QRhi *rhi, QString *error)
{
    if (m_rhi != rhi)
        release();
    m_rhi = rhi;
    if (!m_counted) {
        g_recorders.fetchAndAddRelaxed(1);
        m_counted = true;
    }
    if (m_sampler && m_placeholder && m_placeholderBlock)
        return true;
    m_sampler.reset(rhi->newSampler(QRhiSampler::Linear, QRhiSampler::Linear, QRhiSampler::None,
                                    QRhiSampler::ClampToEdge, QRhiSampler::ClampToEdge));
    m_placeholder.reset(rhi->newTexture(QRhiTexture::RGBA8, QSize(1, 1), 1, QRhiTexture::UsedWithLoadStore));
    m_placeholder->setName(QByteArrayLiteral("srpss core field layout placeholder"));
    m_placeholderBlock.reset(rhi->newBuffer(QRhiBuffer::Static, QRhiBuffer::UniformBuffer, kMaxFieldBlockBytes));
    m_placeholderBlock->setName(QByteArrayLiteral("srpss core field layout block"));
    if (!m_sampler->create() || !m_placeholder->create() || !m_placeholderBlock->create()) {
        m_sampler.reset();
        m_placeholder.reset();
        m_placeholderBlock.reset();
        *error = QStringLiteral("the field recorder's sampler or layout placeholders could not be created");
        return false;
    }
    return true;
}

QRhiComputePipeline *FieldRecorder::pipelineFor(QRhi *rhi, const FieldRecipe &recipe, const FieldDispatch &d,
                                                QString *error)
{
    // The key: the pack, its block's binding and every binding's place and kind (a layout compares kinds, not
    // resources), so one pipeline serves every dispatch of that shape in every record.
    quint64 key = recipe.packKeys.at(d.pack) ^ (quint64(d.blockBinding + 1) * 0x9e3779b97f4a7c15ull);
    for (const FieldBinding &b : d.bindings)
        key = (key ^ (quint64(b.binding) << 8 | quint64(quint8(bindingKind(b))))) * 1099511628211ull;
    for (const std::unique_ptr<Pipe> &pipe : m_pipes) {
        if (pipe->key == key)
            return pipe->pipeline.get();
    }
    if (m_pipes.size() >= 32)
        m_pipes.clear();                     // bounded: a recorder keeps the shapes of the fields it records
    const QRhiShaderResourceBinding::StageFlags cs = QRhiShaderResourceBinding::ComputeStage;
    QList<QRhiShaderResourceBinding> layout;
    if (d.blockBinding >= 0)
        layout.append(QRhiShaderResourceBinding::uniformBuffer(d.blockBinding, cs, m_placeholderBlock.get(), 0,
                                                               quint32(d.blockSize)));
    for (const FieldBinding &b : d.bindings) {
        QRhiTexture *t = m_placeholder.get();
        if (b.input)
            layout.append(QRhiShaderResourceBinding::sampledTexture(b.binding, cs, t, m_sampler.get()));
        else if (b.access == StorageAccess::Read)
            layout.append(QRhiShaderResourceBinding::imageLoad(b.binding, cs, t, 0));
        else if (b.access == StorageAccess::Write)
            layout.append(QRhiShaderResourceBinding::imageStore(b.binding, cs, t, 0));
        else
            layout.append(QRhiShaderResourceBinding::imageLoadStore(b.binding, cs, t, 0));
    }
    auto pipe = std::make_unique<Pipe>();
    pipe->key = key;
    pipe->layout.reset(rhi->newShaderResourceBindings());
    pipe->layout->setBindings(layout.cbegin(), layout.cend());
    pipe->pipeline.reset(rhi->newComputePipeline());
    pipe->pipeline->setName(QByteArrayLiteral("srpss core field pipeline"));
    pipe->pipeline->setShaderStage({ QRhiShaderStage::Compute, recipe.packs.at(d.pack) });
    pipe->pipeline->setShaderResourceBindings(pipe->layout.get());
    if (!pipe->layout->create() || !pipe->pipeline->create()) {
        *error = QStringLiteral("a field pipeline (pack %1) could not be created").arg(d.pack);
        return nullptr;
    }
    g_pipelines.fetchAndAddRelaxed(1);
    m_pipes.push_back(std::move(pipe));
    return m_pipes.back()->pipeline.get();
}

bool FieldRecorder::record(QRhi *rhi, QRhiCommandBuffer *cb, const FieldRecipe &recipe, QRhiTexture *input,
                           QRhiResourceUpdateBatch **pending, FieldOutputs *out, QString *error)
{
    if (!rhi->isFeatureSupported(QRhi::Compute)) {
        *error = QStringLiteral("a field needs QRhi::Compute");
        return false;
    }
    if (!recipe.input.isEmpty() && !input) {
        *error = QStringLiteral("the field's input '%1' has no picture").arg(QString::fromLatin1(recipe.input));
        return false;
    }
    const quint32 maxGroups = quint32(qMax(1, rhi->resourceLimit(QRhi::MaxThreadGroupsPerDimension)));
    for (const FieldDispatch &d : recipe.dispatches) {
        if (d.groups[0] > maxGroups || d.groups[1] > maxGroups || d.groups[2] > maxGroups) {
            *error = QStringLiteral("a field dispatch asks more groups than this device's %1 a dimension")
                         .arg(maxGroups);
            return false;
        }
    }
    if (!ensurePlaceholders(rhi, error))
        return false;
    // The images of this record (each sampled where it is an output; QRhi tracks them from creation).
    std::vector<RhiOwned<QRhiTexture>> images;
    images.reserve(size_t(recipe.images.size()));
    for (const FieldImage &i : recipe.images) {
        RhiOwned<QRhiTexture> t(rhi->newTexture(i.format, i.size, 1, QRhiTexture::UsedWithLoadStore));
        t->setName(QByteArrayLiteral("srpss core field image ") + i.name);
        if (!t->create()) {
            *error = QStringLiteral("field image '%1' could not be created at %2 x %3").arg(QString::fromLatin1(i.name))
                         .arg(i.size.width()).arg(i.size.height());
            return false;
        }
        images.push_back(std::move(t));
    }
    // The blocks, each once at its aligned offset in one Static buffer.
    QList<quint32> offsets;
    quint32 total = 0;
    for (const QByteArray &b : recipe.blocks) {
        offsets.append(total);
        total += quint32(rhi->ubufAligned(int(b.size())));
    }
    RhiOwned<QRhiBuffer> blocks;
    if (total > 0) {
        blocks.reset(rhi->newBuffer(QRhiBuffer::Static, QRhiBuffer::UniformBuffer, total));
        blocks->setName(QByteArrayLiteral("srpss core field blocks"));
        if (!blocks->create()) {
            *error = QStringLiteral("the field's block buffer could not be created");
            return false;
        }
    }
    // The bindings, one object per distinct set, and the pipelines (kept by the recorder).
    const QRhiShaderResourceBinding::StageFlags cs = QRhiShaderResourceBinding::ComputeStage;
    std::vector<RhiOwned<QRhiShaderResourceBindings>> sets;
    QList<QByteArray> setKeys;
    QList<int> setOf;
    QList<QRhiComputePipeline *> pipelines;
    for (const FieldDispatch &d : recipe.dispatches) {
        QRhiComputePipeline *pipeline = pipelineFor(rhi, recipe, d, error);
        if (!pipeline)
            return false;
        pipelines.append(pipeline);
        QByteArray key;
        key.append(reinterpret_cast<const char *>(&d.pack), sizeof(d.pack));
        key.append(reinterpret_cast<const char *>(&d.block), sizeof(d.block));
        for (const FieldBinding &b : d.bindings) {
            key.append(reinterpret_cast<const char *>(&b.binding), sizeof(b.binding));
            key.append(reinterpret_cast<const char *>(&b.image), sizeof(b.image));
            key.append(bindingKind(b));
        }
        const int found = int(setKeys.indexOf(key));
        if (found >= 0) {
            setOf.append(found);
            continue;
        }
        QList<QRhiShaderResourceBinding> list;
        if (d.blockBinding >= 0)
            list.append(QRhiShaderResourceBinding::uniformBuffer(d.blockBinding, cs, blocks.get(),
                                                                 offsets.at(d.block), quint32(d.blockSize)));
        for (const FieldBinding &b : d.bindings) {
            if (b.input) {
                list.append(QRhiShaderResourceBinding::sampledTexture(b.binding, cs, input, m_sampler.get()));
                continue;
            }
            QRhiTexture *t = images.at(size_t(b.image)).get();
            if (b.access == StorageAccess::Read)
                list.append(QRhiShaderResourceBinding::imageLoad(b.binding, cs, t, 0));
            else if (b.access == StorageAccess::Write)
                list.append(QRhiShaderResourceBinding::imageStore(b.binding, cs, t, 0));
            else
                list.append(QRhiShaderResourceBinding::imageLoadStore(b.binding, cs, t, 0));
        }
        RhiOwned<QRhiShaderResourceBindings> set(rhi->newShaderResourceBindings());
        set->setBindings(list.cbegin(), list.cend());
        if (!set->create()) {
            *error = QStringLiteral("a field dispatch's bindings could not be created");
            return false;
        }
        setOf.append(int(sets.size()));
        setKeys.append(key);
        sets.push_back(std::move(set));
    }
    // Everything exists: record. The blocks join the record's uploads; the first pass takes them.
    QRhiResourceUpdateBatch *batch = *pending ? *pending : rhi->nextResourceUpdateBatch();
    for (int i = 0; i < int(recipe.blocks.size()); ++i)
        batch->uploadStaticBuffer(blocks.get(), offsets.at(i), quint32(recipe.blocks.at(i).size()),
                                  recipe.blocks.at(i).constData());
    for (int i = 0; i < int(recipe.dispatches.size()); ++i) {
        const FieldDispatch &d = recipe.dispatches.at(i);
        cb->beginComputePass(batch);
        batch = nullptr;
        cb->setComputePipeline(pipelines.at(i));
        cb->setShaderResources(sets.at(size_t(setOf.at(i))).get());
        cb->dispatch(int(d.groups[0]), int(d.groups[1]), int(d.groups[2]));
        cb->endComputePass();
    }
    *pending = nullptr;                       // taken by the first pass (a recipe has at least one dispatch)
    for (int o = 0; o < int(recipe.outputs.size()); ++o)
        out->textures[o] = std::move(images.at(size_t(recipe.outputs.at(o).image)));
    // The scratch images, the blocks and the bindings go with their owners here (deleteLater: after this frame).
    g_recorded.fetchAndAddRelaxed(1);
    g_dispatches.fetchAndAddRelaxed(recipe.dispatches.size());
    return true;
}

QByteArray fieldRecipeCheckJson(const QByteArray &json, const QList<QByteArray> &packs, const QList<QByteArray> &blocks)
{
    QJsonObject o;
    FieldRecipe recipe;
    QString error;
    const bool ok = FieldRecipe::fromJson(json, packs, blocks, &recipe, &error);
    o.insert(QStringLiteral("ok"), ok);
    if (ok)
        o.insert(QStringLiteral("recipe"), recipe.toJson());
    else
        o.insert(QStringLiteral("error"), error);
    return QJsonDocument(o).toJson(QJsonDocument::Compact);
}

} // namespace srpss_core
