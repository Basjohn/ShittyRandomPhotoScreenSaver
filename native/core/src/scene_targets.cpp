// Scene targets (N3.1, D14): scene_targets.h has the contract.
#include "scene_targets.h"
#include "rhi_owned.h"

#include <QtCore/QJsonValue>
#include <QtGui/QOpenGLContext>
#include <QtGui/QOpenGLFunctions>

#include <algorithm>
#include <cmath>

namespace srpss_core {

namespace {

QAtomicInteger<int> g_targets { 0 };
QAtomicInteger<int> g_textures { 0 };
QAtomicInteger<qint64> g_bytes { 0 };
QAtomicInteger<qint64> g_allocations { 0 };
QAtomicInteger<qint64> g_steps { 0 };
QAtomicInteger<int> g_readbacksPending { 0 };
QAtomicInteger<int> g_contentAtTop { 0 };
QAtomicInteger<int> g_onePixelBucket { 0 };
QAtomicInteger<int> g_allocationStepLimit { 0 };
QAtomicInteger<int> g_skipScissor { 0 };
QAtomicInteger<int> g_oversizeViewport { 0 };
QAtomicInteger<qint64> g_selfMips { 0 };    // ABI 33
QAtomicInteger<qint64> g_cubeFaceRuns { 0 };     // ABI 42
QAtomicInteger<qint64> g_cubePrefilters { 0 };
QAtomicInteger<qint64> g_cubeLevelCopies { 0 };

QMutex &removedMutex()
{
    static QMutex mutex;
    return mutex;
}

QList<int> &removedCounts()
{
    static QList<int> list;
    return list;
}

// Readbacks QRhi may still write into after their content went (harness only): kept until done.
QMutex &readbackMutex()
{
    static QMutex mutex;
    return mutex;
}

QList<std::shared_ptr<SceneReadback>> &readbacksInFlight()
{
    static QList<std::shared_ptr<SceneReadback>> list;
    return list;
}

void pruneReadbacks()
{
    QMutexLocker lock(&readbackMutex());
    QList<std::shared_ptr<SceneReadback>> &list = readbacksInFlight();
    for (qsizetype i = list.size() - 1; i >= 0; --i) {
        if (list.at(i)->done())
            list.removeAt(i);
    }
}

// ABI 37 (N4.i): "r8", the motion trails' ghost buffer (Python's GL_R8, trails.py MotionTrails).
const char *const kFormatNames[] = { "rgba8", "rgba16f", "r16f", "r32f", "r8" };
constexpr int kFormatCount = int(sizeof(kFormatNames) / sizeof(kFormatNames[0]));

bool identifier(const QByteArray &name)
{
    if (name.isEmpty() || name.size() > 64 || (name.at(0) >= '0' && name.at(0) <= '9'))
        return false;
    for (const char c : name) {
        if (!((c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') || c == '_'))
            return false;
    }
    return true;
}

int textureBytesPerSample(QRhiTexture::Format format)
{
    switch (format) {
    case QRhiTexture::RGBA16F:
        return 8;
    case QRhiTexture::R16F:
        return 2;
    case QRhiTexture::R8:
        return 1;                             // ABI 37: the trails' ghost buffer
    case QRhiTexture::RGBA8:
    case QRhiTexture::R32F:
    case QRhiTexture::D32F:
        return 4;
    default:
        return 4;
    }
}

qint64 textureBytes(const QRhiTexture *texture)
{
    if (!texture)
        return 0;
    QSize size = texture->pixelSize();
    const qint64 perTexel = qint64(textureBytesPerSample(texture->format())) * qint64(qMax(1, texture->sampleCount()));
    qint64 bytes = qint64(size.width()) * qint64(size.height()) * perTexel;
    if (texture->flags().testFlag(QRhiTexture::MipMapped)) {
        // N3.4: a mipped target's every level (the defocus layer).
        while (size.width() > 1 || size.height() > 1) {
            size = QSize(qMax(1, size.width() / 2), qMax(1, size.height() / 2));
            bytes += qint64(size.width()) * qint64(size.height()) * perTexel;
        }
    }
    if (texture->flags().testFlag(QRhiTexture::CubeMap))
        bytes *= kCubeFaces;                  // ABI 42: every face of every level
    return bytes;
}

void countTargetObjects(SceneTargets::Target &t)
{
    qint64 bytes = 0;
    int textures = 0;
    const auto add = [&](const RhiOwned<QRhiTexture> &texture) {
        if (texture) {
            ++textures;
            bytes += textureBytes(texture.get());
        }
    };
    for (int i = 0; i < kMaxTargetColour; ++i) {
        add(t.colour[i]);
        add(t.resolve[i]);
    }
    add(t.depth);
    add(t.depthNearest);
    add(t.captureColour);
    add(t.captureDepth);
    for (int level = 0; level < kMaxCubeLevels; ++level)
        add(t.stage[level]);                  // ABI 42: a cube target's prefilter stages
    if ((textures > 0) != (t.textures > 0))
        g_targets.fetchAndAddRelaxed(textures > 0 ? 1 : -1);
    if (textures != t.textures)
        g_textures.fetchAndAddRelaxed(textures - t.textures);
    if (bytes != t.bytes)
        g_bytes.fetchAndAddRelaxed(bytes - t.bytes);
    t.textures = textures;
    t.bytes = bytes;
}

} // namespace

// ------------------------------------------------------------------------------------------------- formats

bool parseTargetFormat(const QString &text, TargetFormat *out)
{
    for (int i = 0; i < kFormatCount; ++i) {
        if (text == QLatin1String(kFormatNames[i])) {
            *out = TargetFormat(i);
            return true;
        }
    }
    return false;
}

QString targetFormatName(TargetFormat format)
{
    return QLatin1String(kFormatNames[qBound(0, int(format), kFormatCount - 1)]);
}

QRhiTexture::Format targetRhiFormat(TargetFormat format)
{
    switch (format) {
    case TargetFormat::RGBA16F:
        return QRhiTexture::RGBA16F;
    case TargetFormat::R16F:
        return QRhiTexture::R16F;
    case TargetFormat::R32F:
        return QRhiTexture::R32F;
    case TargetFormat::R8:
        return QRhiTexture::R8;               // ABI 37
    case TargetFormat::RGBA8:
        break;
    }
    return QRhiTexture::RGBA8;
}

int targetFormatBytes(TargetFormat format)
{
    return textureBytesPerSample(targetRhiFormat(format));
}

// ------------------------------------------------------------------------------------------------- the declaration

bool TargetDeclaration::sameLayout(const TargetDeclaration &o) const
{
    if (name != o.name || depth != o.depth || depthRead != o.depthRead || depthSampled != o.depthSampled
        || samples != o.samples || capture != o.capture || colour.size() != o.colour.size()
        || surfaceSized() != o.surfaceSized()
        || transparencyOf != o.transparencyOf || owner != o.owner || borrow != o.borrow || mips != o.mips // N3.4
        || exact != o.exact || selfMips != o.selfMips // ABI 33
        || cube != o.cube)                    // ABI 42
        return false;
    for (qsizetype i = 0; i < colour.size(); ++i) {
        const TargetAttachment &a = colour.at(i);
        const TargetAttachment &b = o.colour.at(i);
        if (a.name != b.name || a.format != b.format || a.read != b.read || a.nearest != b.nearest
            || a.borrowed != b.borrowed || a.ownerColour != b.ownerColour || a.mipsRead != b.mipsRead) // ABI 33
            return false;
        for (int c = 0; c < 4; ++c) {
            if (a.clear[c] != b.clear[c])
                return false;
        }
    }
    return true;
}

int TargetDeclaration::colourIndex(const QByteArray &attachment) const
{
    for (qsizetype i = 0; i < colour.size(); ++i) {
        if (colour.at(i).name == attachment)
            return int(i);
    }
    return -1;
}

QJsonObject TargetDeclaration::toJson() const
{
    QJsonObject o;
    o.insert(QStringLiteral("name"), QString::fromLatin1(name));
    if (surfaceSized())
        o.insert(QStringLiteral("size"), QStringLiteral("surface"));
    else
        o.insert(QStringLiteral("size"), QJsonArray { size.width(), size.height() });
    QJsonArray list;
    for (const TargetAttachment &a : colour) {
        QJsonObject c;
        c.insert(QStringLiteral("name"), QString::fromLatin1(a.name));
        c.insert(QStringLiteral("format"), targetFormatName(a.format));
        c.insert(QStringLiteral("clear"), QJsonArray { a.clear[0], a.clear[1], a.clear[2], a.clear[3] });
        c.insert(QStringLiteral("read"), a.read);
        c.insert(QStringLiteral("resolve"), a.nearest ? QStringLiteral("nearest") : QStringLiteral("average"));
        c.insert(QStringLiteral("borrowed"), a.borrowed); // N3.4
        c.insert(QStringLiteral("mips_read"), a.mipsRead); // ABI 33
        list.append(c);
    }
    o.insert(QStringLiteral("colour"), list);
    o.insert(QStringLiteral("depth"), depth);
    o.insert(QStringLiteral("depth_read"), depthRead);
    o.insert(QStringLiteral("depth_sampled"), depthSampled);
    o.insert(QStringLiteral("samples"), samples);
    o.insert(QStringLiteral("previous_frame"), previousFrame);
    o.insert(QStringLiteral("capture"), capture);
    // N3.4 (D17)
    o.insert(QStringLiteral("transparency_of"), transparency() ? QJsonValue(QString::fromLatin1(transparencyOf))
                                                               : QJsonValue());
    QJsonArray borrowed;
    for (const QByteArray &b : borrow)
        borrowed.append(QString::fromLatin1(b));
    o.insert(QStringLiteral("borrow"), borrowed);
    o.insert(QStringLiteral("mips"), mips);
    o.insert(QStringLiteral("self_mips"), selfMips);                                   // ABI 33
    o.insert(QStringLiteral("allocation"), exact ? QStringLiteral("exact") : QStringLiteral("bucket"));
    o.insert(QStringLiteral("cube"), cube);                                            // ABI 42
    return o;
}

// N3.4 (D17 point 2): {"name", "transparency": {"of": <owner>, "borrow"?: [<owner attachment>, ...]}}, nothing else (its
// layout is derived from the owner by deriveTransparencyTargets).
static bool parseTransparencyDeclaration(const QJsonObject &o, TargetDeclaration *d, QString *error)
{
    const QString label = QString::fromLatin1(d->name);
    const QString shape = QStringLiteral("target '%1': a transparency target is {\"name\", \"transparency\": {\"of\": "
                                         "a scene target declared before it, \"borrow\"?: [its attachments]}} and "
                                         "nothing else (its size, samples and depth are its owner's)").arg(label);
    if (o.size() != 2 || !o.value(QStringLiteral("transparency")).isObject()) {
        *error = shape;
        return false;
    }
    const QJsonObject t = o.value(QStringLiteral("transparency")).toObject();
    const QJsonValue of = t.value(QStringLiteral("of"));
    const QJsonValue borrow = t.value(QStringLiteral("borrow"));
    if (t.size() != (borrow.isUndefined() ? 1 : 2) || !of.isString() || !identifier(of.toString().toLatin1())
        || (!borrow.isUndefined() && !borrow.isArray())) {
        *error = shape;
        return false;
    }
    d->transparencyOf = of.toString().toLatin1();
    for (const QJsonValue &entry : borrow.toArray()) {
        const QByteArray name = entry.toString().toLatin1();
        if (!entry.isString() || !identifier(name) || d->borrow.contains(name)) {
            *error = QStringLiteral("target '%1' borrows an attachment by its name, each once").arg(label);
            return false;
        }
        d->borrow.append(name);
    }
    // Its own two attachments (Python's oit_accum and oit_reveal, the reveal stored inverted as coverage: both clear
    // to 0, D17 choice B).
    TargetAttachment accum;
    accum.name = QByteArrayLiteral("accum");
    accum.format = TargetFormat::RGBA16F;
    TargetAttachment coverage;
    coverage.name = QByteArrayLiteral("coverage");
    coverage.format = TargetFormat::R16F;
    d->colour = { accum, coverage };
    d->depth = true;                          // the owner's (deriveTransparencyTargets checks it has one)
    return true;
}

bool deriveTransparencyTargets(QList<TargetDeclaration> &targets, QString *error)
{
    for (int i = 0; i < int(targets.size()); ++i) {
        TargetDeclaration &d = targets[i];
        if (!d.transparency())
            continue;
        const QString label = QString::fromLatin1(d.name);
        int owner = -1;
        for (int o = 0; o < i; ++o) {
            if (targets.at(o).name == d.transparencyOf)
                owner = o;
        }
        if (owner < 0) {
            *error = QStringLiteral("transparency target '%1': its owner '%2' is no target declared before it")
                         .arg(label, QString::fromLatin1(d.transparencyOf));
            return false;
        }
        const TargetDeclaration &o = targets.at(owner);
        if (o.transparency() || o.mips || !o.surfaceSized() || !o.depth) {
            *error = QStringLiteral("transparency target '%1': its owner '%2' is a surface-sized scene target with depth "
                                    "(not a transparency or mipped target)").arg(label, QString::fromLatin1(o.name));
            return false;
        }
        for (int other = 0; other < i; ++other) {
            if (targets.at(other).transparency() && targets.at(other).owner == owner) {
                *error = QStringLiteral("target '%1' has two transparency targets").arg(QString::fromLatin1(o.name));
                return false;
            }
        }
        QList<TargetAttachment> colour = d.colour.mid(0, 2);
        for (const QByteArray &name : d.borrow) {
            const int index = o.colourIndex(name);
            if (index <= 0) {
                *error = QStringLiteral("transparency target '%1' borrows '%2': %3")
                             .arg(label, QString::fromLatin1(name),
                                  index == 0 ? QStringLiteral("the owner's colour 0 is what the resolve draws into")
                                             : QStringLiteral("the owner '%1' has no such attachment")
                                                   .arg(QString::fromLatin1(o.name)));
                return false;
            }
            TargetAttachment a = o.colour.at(index);
            a.borrowed = true;
            a.ownerColour = index;
            a.read = false;                   // the owner resolves it; the borrower sets no resolve
            a.nearest = false;
            colour.append(a);
        }
        if (colour.size() > kMaxTargetColour) {
            *error = QStringLiteral("transparency target '%1' has %2 attachments with those it borrows: at most %3")
                         .arg(label).arg(colour.size()).arg(kMaxTargetColour);
            return false;
        }
        d.owner = owner;
        d.colour = colour;
        d.size = o.size;
        d.samples = o.samples;
        d.depth = true;
        d.previousFrame = false;
    }
    return true;
}

bool parseTargetDeclaration(const QJsonValue &value, TargetDeclaration *out, QString *error)
{
    const QString shape = QStringLiteral("a target is {\"name\": an identifier, \"size\": \"surface\" or [w, h], "
                                         "\"colour\": [{\"name\", \"format\": rgba8, rgba16f, r16f, r32f or r8, "
                                         "\"clear\"?: [r, g, b, a], \"resolve\"?: average or nearest}, 1 to %1], "
                                         "\"depth\"?: true or false, "
                                         "\"samples\"?: 1 to %2, \"previous_frame\"?: true or false, \"mips\"?: "
                                         "true or false, \"allocation\"?: bucket or exact}")
                                .arg(kMaxTargetColour).arg(kMaxSceneSamples);
    if (!value.isObject()) {
        *error = shape;
        return false;
    }
    const QJsonObject o = value.toObject();
    const QStringList keys = { QStringLiteral("name"), QStringLiteral("size"), QStringLiteral("colour"),
                               QStringLiteral("depth"), QStringLiteral("samples"), QStringLiteral("previous_frame"),
                               QStringLiteral("transparency"), QStringLiteral("mips"), // N3.4
                               QStringLiteral("allocation"),                           // ABI 33
                               QStringLiteral("cube") };                               // ABI 42
    for (auto it = o.begin(); it != o.end(); ++it) {
        if (!keys.contains(it.key())) {
            *error = QStringLiteral("unknown target key '%1': %2").arg(it.key(), shape);
            return false;
        }
    }
    TargetDeclaration d;
    d.name = o.value(QStringLiteral("name")).toString().toLatin1();
    if (!identifier(d.name) || d.name == "surface") {
        *error = QStringLiteral("a target's name is an identifier (a-z, 0-9, _; not 'surface'): %1").arg(shape);
        return false;
    }
    const QString label = QString::fromLatin1(d.name);
    if (o.contains(QStringLiteral("transparency"))) {
        // N3.4 (D17 point 2): its layout is its owner's (deriveTransparencyTargets, once every target is parsed).
        if (!parseTransparencyDeclaration(o, &d, error))
            return false;
        *out = d;
        return true;
    }
    const QJsonValue mips = o.value(QStringLiteral("mips"));
    if (!mips.isUndefined() && !mips.isBool()) {
        *error = QStringLiteral("target '%1': mips is true or false").arg(label);
        return false;
    }
    d.mips = mips.toBool(false);
    // ABI 33: the allocation rule (D14 point 2's buckets, or the content's exact size).
    const QJsonValue allocation = o.value(QStringLiteral("allocation"));
    if (!allocation.isUndefined()
        && !(allocation.isString() && (allocation.toString() == QLatin1String("bucket")
                                       || allocation.toString() == QLatin1String("exact")))) {
        *error = QStringLiteral("target '%1': allocation is bucket or exact").arg(label);
        return false;
    }
    d.exact = allocation.toString() == QLatin1String("exact");
    const QJsonValue size = o.value(QStringLiteral("size"));
    if (size.isString() && size.toString() == QLatin1String("surface")) {
        d.size = QSize();
    } else if (size.isArray() && size.toArray().size() == 2 && size.toArray().at(0).isDouble()
               && size.toArray().at(1).isDouble()) {
        const double w = size.toArray().at(0).toDouble();
        const double h = size.toArray().at(1).toDouble();
        if (w != std::floor(w) || h != std::floor(h) || w < 1 || h < 1 || w > 16384 || h > 16384) {
            *error = QStringLiteral("target '%1': an explicit size is whole pixels, 1 to 16384 a side").arg(label);
            return false;
        }
        d.size = QSize(int(w), int(h));
    } else {
        *error = QStringLiteral("target '%1': its size is \"surface\" or [w, h]").arg(label);
        return false;
    }
    const QJsonArray colour = o.value(QStringLiteral("colour")).toArray();
    if (colour.isEmpty() || colour.size() > kMaxTargetColour) {
        *error = QStringLiteral("target '%1' has 1 to %2 colour attachments").arg(label).arg(kMaxTargetColour);
        return false;
    }
    for (const QJsonValue &entry : colour) {
        const QJsonObject c = entry.toObject();
        TargetAttachment a;
        a.name = c.value(QStringLiteral("name")).toString().toLatin1();
        const bool withClear = c.contains(QStringLiteral("clear"));
        const bool withResolve = c.contains(QStringLiteral("resolve"));
        if (!entry.isObject() || c.size() != 2 + (withClear ? 1 : 0) + (withResolve ? 1 : 0) || !identifier(a.name)
            || !parseTargetFormat(c.value(QStringLiteral("format")).toString(), &a.format)) {
            *error = QStringLiteral("target '%1': an attachment is {\"name\": an identifier, \"format\": rgba8, "
                                    "rgba16f, r16f, r32f or r8, \"clear\"?: [r, g, b, a], \"resolve\"?: average or "
                                    "nearest}").arg(label);
            return false;
        }
        if (withResolve) {
            const QString resolve = c.value(QStringLiteral("resolve")).toString();
            if (resolve != QLatin1String("average") && resolve != QLatin1String("nearest")) {
                *error = QStringLiteral("target '%1': attachment '%2''s resolve is average or nearest")
                             .arg(label, QString::fromLatin1(a.name));
                return false;
            }
            a.nearest = resolve == QLatin1String("nearest");
        }
        if (a.nearest && (a.format != TargetFormat::R32F || d.colour.isEmpty())) {
            // D14 point 10 (b): the nearest resolve takes the minimum of one float channel; attachment 0 is the colour
            // the capture copies, averaged.
            *error = QStringLiteral("target '%1': attachment '%2' resolves to the nearest sample only as an r32f "
                                    "attachment past the first").arg(label, QString::fromLatin1(a.name));
            return false;
        }
        if (a.name == "depth" || a.name == "capture_colour" || a.name == "capture_depth") {
            *error = QStringLiteral("target '%1': '%2' names the target's depth or capture, not an attachment")
                         .arg(label, QString::fromLatin1(a.name));
            return false;
        }
        if (withClear) {
            const QJsonArray clear = c.value(QStringLiteral("clear")).toArray();
            bool ok = clear.size() == 4;
            for (int i = 0; ok && i < 4; ++i) {
                ok = clear.at(i).isDouble() && std::isfinite(clear.at(i).toDouble());
                if (ok)
                    a.clear[i] = float(clear.at(i).toDouble());
            }
            if (!ok) {
                *error = QStringLiteral("target '%1': attachment '%2''s clear is four finite numbers")
                             .arg(label, QString::fromLatin1(a.name));
                return false;
            }
        }
        if (d.colourIndex(a.name) >= 0) {
            *error = QStringLiteral("target '%1' names the attachment '%2' twice").arg(label, QString::fromLatin1(a.name));
            return false;
        }
        d.colour.append(a);
    }
    const QJsonValue depth = o.value(QStringLiteral("depth"));
    if (!depth.isUndefined() && !depth.isBool()) {
        *error = QStringLiteral("target '%1': depth is true or false").arg(label);
        return false;
    }
    d.depth = depth.toBool(false);
    const QJsonValue samples = o.value(QStringLiteral("samples"));
    if (!samples.isUndefined()) {
        const double n = samples.toDouble(-1.0);
        if (!samples.isDouble() || n != std::floor(n) || n < 1 || n > kMaxSceneSamples) {
            *error = QStringLiteral("target '%1': samples is a whole number, 1 to %2 (the request; the core clamps it to "
                                    "the device)").arg(label).arg(kMaxSceneSamples);
            return false;
        }
        d.samples = int(n);
    }
    const QJsonValue previous = o.value(QStringLiteral("previous_frame"));
    if (!previous.isUndefined() && !previous.isBool()) {
        *error = QStringLiteral("target '%1': previous_frame is true or false").arg(label);
        return false;
    }
    d.previousFrame = previous.toBool(false);
    if (d.previousFrame && d.samples > 1) {
        // Audit 2, M4: a multisampled target's nearest resolves are made after the runs that read them, so a pass
        // before its first run would read memory nothing wrote.
        *error = QStringLiteral("target '%1' is read as the frame before only single-sampled (it requests %2 "
                                "samples: before its first run a pass would read resolves nothing wrote)")
                     .arg(label).arg(d.samples);
        return false;
    }
    // ABI 42 (N5.6): a cube target (probe.py's SceneProbe): an explicit square size, one RGBA16F attachment, single-
    // sampled, no previous_frame and no "mips" (its chain is its prefilter step's, never a box kernel's or
    // generateMips), its allocation exact (the probe's face size per tier, never a bucket).
    const QJsonValue cube = o.value(QStringLiteral("cube"));
    if (!cube.isUndefined() && !cube.isBool()) {
        *error = QStringLiteral("target '%1': cube is true or false").arg(label);
        return false;
    }
    d.cube = cube.toBool(false);
    if (d.cube) {
        if (d.surfaceSized() || d.size.width() != d.size.height() || d.colour.size() != 1
            || d.colour.at(0).format != TargetFormat::RGBA16F || d.colour.at(0).nearest || d.samples != 1
            || d.previousFrame || d.mips || allocation.toString() == QLatin1String("bucket")) {
            *error = QStringLiteral("target '%1': a cube target has an explicit square size, one rgba16f attachment, one "
                                    "sample, no previous_frame, no mips (its prefilter step makes its levels) and an "
                                    "exact allocation").arg(label);
            return false;
        }
        d.exact = true;
    }
    if (d.mips) {
        // N3.4 (D17 point 6): single-sampled (its chains are generated from the texture drawn), no nearest attachment,
        // no previous_frame. ABI 33: a depth and an explicit size are allowed (a drawable mipped target: Waveform's
        // reflection); the defocus step still takes only a surface-sized, bucketed layer without depth
        // (mode_content.cpp parseStageStep).
        bool nearest = false;
        for (const TargetAttachment &a : d.colour)
            nearest = nearest || a.nearest;
        if (d.samples != 1 || nearest || d.previousFrame) {
            *error = QStringLiteral("target '%1': a mipped target is single-sampled, without nearest resolves or "
                                    "previous_frame").arg(label);
            return false;
        }
    }
    *out = d;
    return true;
}

// ------------------------------------------------------------------------------------------------- allocation rules

int bucketPixels(int pixels)
{
    const int p = qMax(1, pixels);
    if (g_onePixelBucket.loadAcquire())
        return p;
    return qMax(kSceneBucket, ((p + kSceneBucket - 1) / kSceneBucket) * kSceneBucket);
}

QSize nextAllocation(const QSize &current, const QSize &needed, QString *reason)
{
    const QSize bucketed(bucketPixels(needed.width()), bucketPixels(needed.height()));
    if (current.isEmpty()) {
        *reason = QStringLiteral("made");
        return bucketed;
    }
    // Each axis on its own (audit 2, L1): grown at once past the allocation, shrunk only two or more buckets below it,
    // else kept (a grow on one axis never re-buckets the other one down).
    bool grown = false;
    bool shrunk = false;
    const int bucketSize = g_onePixelBucket.loadAcquire() ? 1 : kSceneBucket;
    const auto axis = [&](int have, int need, int bucket) {
        if (need > have) {
            grown = true;
            return bucket;
        }
        if (have - bucket >= 2 * bucketSize) {
            shrunk = true;
            return bucket;
        }
        return have;
    };
    const QSize next(axis(current.width(), needed.width(), bucketed.width()),
                     axis(current.height(), needed.height(), bucketed.height()));
    if (grown)
        *reason = QStringLiteral("grown");
    else if (shrunk)
        *reason = QStringLiteral("shrunk");
    else
        reason->clear();
    return next;
}

QSize exactAllocation(const QSize &current, const QSize &needed, QString *reason)
{
    const QSize exact(qMax(1, needed.width()), qMax(1, needed.height()));
    if (current.isEmpty())
        *reason = QStringLiteral("made");
    else if (current != exact)
        *reason = QStringLiteral("resized");
    else
        reason->clear();
    return exact;
}

QRect contentViewport(bool yUpInFramebuffer, const QSize &allocation, const QSize &content)
{
    const int w = qMin(content.width(), allocation.width());
    const int h = qMin(content.height(), allocation.height());
    const int slack = allocation.height() - h;
    return QRect(0, g_contentAtTop.loadAcquire() ? (yUpInFramebuffer ? 0 : slack)
                                              : (yUpInFramebuffer ? slack : 0), w, h);
}

bool setSceneTargetControl(const QByteArray &name, int value)
{
    if (name == "content_at_top" && (value == 0 || value == 1))
        g_contentAtTop.storeRelease(value);
    else if (name == "one_pixel_bucket" && (value == 0 || value == 1))
        g_onePixelBucket.storeRelease(value);
    else if (name == "allocation_steps" && value >= 0 && value <= 32)
        g_allocationStepLimit.storeRelease(value);
    else if (name == "skip_scissor" && (value == 0 || value == 1))
        g_skipScissor.storeRelease(value);
    else if (name == "oversize_viewport" && (value == 0 || value == 1))
        g_oversizeViewport.storeRelease(value);
    else
        return false;
    return true;
}

int sceneAllocationStepLimit()
{
    return g_allocationStepLimit.loadAcquire();
}

bool sceneScissorEnabled()
{
    return !g_skipScissor.loadAcquire();
}

bool sceneOversizeViewport()
{
    return g_oversizeViewport.loadAcquire();
}

int clampSamples(const QList<int> &supported, int requested)
{
    int best = 1;
    for (const int count : supported) {
        if (count <= requested && count > best)
            best = count;
    }
    return best;
}

namespace {
QAtomicInteger<quint64> g_removedGeneration { 0 };
} // namespace

void setRemovedSampleCounts(const QList<int> &removed)
{
    QMutexLocker lock(&removedMutex());
    removedCounts() = removed;
    g_removedGeneration.fetchAndAddOrdered(1);
}

quint64 removedSampleCountsGeneration()
{
    return g_removedGeneration.loadAcquire();
}

QList<int> removedSampleCounts()
{
    QMutexLocker lock(&removedMutex());
    return removedCounts();
}

namespace {
QAtomicInteger<int> g_skipDepthPrime { 0 };
QAtomicInteger<qint64> g_depthPrimes { 0 };
} // namespace

void setSkipDepthPrime(bool skip)
{
    g_skipDepthPrime.storeRelease(skip ? 1 : 0);
}

bool skipDepthPrime()
{
    return g_skipDepthPrime.loadAcquire() != 0;
}

void countDepthPrime()
{
    g_depthPrimes.fetchAndAddRelaxed(1);
}

namespace {
QAtomicInteger<int> g_skipResolvePrime { 0 };
QAtomicInteger<qint64> g_resolvePrimes { 0 };
} // namespace

void setSkipResolvePrime(bool skip)
{
    g_skipResolvePrime.storeRelease(skip ? 1 : 0);
}

bool skipResolvePrime()
{
    return g_skipResolvePrime.loadAcquire() != 0;
}

void countResolvePrimes(int primed)
{
    if (primed > 0)
        g_resolvePrimes.fetchAndAddRelaxed(primed);
}

namespace {
QAtomicInteger<int> g_nearestFirstSample { 0 };
QAtomicInteger<qint64> g_nearestResolves { 0 };
} // namespace

void setNearestFirstSample(bool firstOnly)
{
    g_nearestFirstSample.storeRelease(firstOnly ? 1 : 0);
}

bool nearestFirstSample()
{
    return g_nearestFirstSample.loadAcquire() != 0;
}

void countNearestResolve()
{
    g_nearestResolves.fetchAndAddRelaxed(1);
}

QList<int> supportedSampleCounts(QRhi *rhi)
{
    QList<int> counts;
    if (!rhi)
        return counts;
    const QList<int> removed = removedSampleCounts();
    const bool multisample = rhi->isFeatureSupported(QRhi::MultisampleTexture);
    for (const int count : rhi->supportedSampleCounts()) {
        if (count > 1 && !multisample)
            continue;                         // a multisampled target is a multisample texture here
        if (!removed.contains(count))
            counts.append(count);
    }
    return counts;
}

SceneTargetCounts sceneTargetCounts()
{
    SceneTargetCounts c;
    c.targets = g_targets.loadRelaxed();
    c.textures = g_textures.loadRelaxed();
    c.bytes = g_bytes.loadRelaxed();
    c.allocations = g_allocations.loadRelaxed();
    c.steps = g_steps.loadRelaxed();
    c.readbacksPending = g_readbacksPending.loadRelaxed();
    c.depthPrimes = g_depthPrimes.loadRelaxed();
    c.resolvePrimes = g_resolvePrimes.loadRelaxed();
    c.nearestResolves = g_nearestResolves.loadRelaxed();
    c.generatedMips = g_selfMips.loadRelaxed();
    c.cubeFaceRuns = g_cubeFaceRuns.loadRelaxed();       // ABI 42
    c.cubePrefilters = g_cubePrefilters.loadRelaxed();
    c.cubeLevelCopies = g_cubeLevelCopies.loadRelaxed();
    return c;
}

void countCubeFaceRun()
{
    g_cubeFaceRuns.fetchAndAddRelaxed(1);
}

void countCubePrefilter(int levelCopies)
{
    g_cubePrefilters.fetchAndAddRelaxed(1);
    g_cubeLevelCopies.fetchAndAddRelaxed(levelCopies);
}

QRhiTextureRenderTarget *SceneTargets::Target::faceRenderTarget(int face) const
{
    if (!decl.cube)
        return renderTarget.get();
    if (face <= 0)
        return renderTarget.get();            // face 0 is the target's own render target
    return face < kCubeFaces ? faceTarget[face].get() : nullptr;
}

// ------------------------------------------------------------------------------------------------- a target

QRhiTexture *SceneTargets::Target::readable(int colourIndex) const
{
    if (colourIndex < 0 || colourIndex >= int(decl.colour.size()))
        return nullptr;
    return samples > 1 ? resolve[colourIndex].get() : colour[colourIndex].get();
}

QRhiTexture *SceneTargets::Target::readableDepth() const
{
    return samples > 1 ? depthNearest.get() : depth.get();
}

QRhiTexture *SceneTargets::Target::colourTexture(int colourIndex) const
{
    if (colourIndex < 0 || colourIndex >= int(decl.colour.size()) || colourIndex >= kMaxTargetColour)
        return nullptr;
    return decl.colour.at(colourIndex).borrowed ? borrowedColour[colourIndex] : colour[colourIndex].get();
}

void SceneTargets::setDormant(quint32 mask, const QStringList &reasons)
{
    if (mask == m_dormant && reasons == m_fallbacks)
        return;
    m_dormant = mask;
    m_fallbacks = reasons;
    ++m_stateVersion;
}

bool SceneTargets::Target::nearestActive(int slot) const
{
    if (samples <= 1)
        return false;
    if (slot == kNearestDepthSlot)
        return decl.depth && decl.depthRead;
    return slot >= 0 && slot < int(decl.colour.size()) && decl.colour.at(slot).nearest && decl.colour.at(slot).read;
}

QRhiTexture *SceneTargets::Target::nearestSource(int slot) const
{
    if (!nearestActive(slot))
        return nullptr;
    return slot == kNearestDepthSlot ? depth.get() : colour[slot].get();
}

QRhiTexture *SceneTargets::Target::nearestDest(int slot) const
{
    if (!nearestActive(slot))
        return nullptr;
    return slot == kNearestDepthSlot ? depthNearest.get() : resolve[slot].get();
}

SceneTargets::SceneTargets() = default;

SceneTargets::~SceneTargets()
{
    release();
}

int SceneTargets::indexOf(const QByteArray &name) const
{
    for (int i = 0; i < m_count; ++i) {
        if (m_targets[i] && m_targets[i]->decl.name == name)
            return i;
    }
    return -1;
}

void SceneTargets::releaseTarget(Target &t)
{
    // Reverse order of creation: the capture's target, its descriptor and textures; the nearest resolves' targets and
    // descriptors; the target, its descriptor; the depth and its nearest resolve; the colour attachments and their
    // resolves. ABI 42: a cube target's prefilter stages (their face targets, descriptors, textures) and face targets
    // first: they name the cube.
    for (int level = kMaxCubeLevels - 1; level >= 0; --level) {
        for (int f = kCubeFaces - 1; f >= 0; --f)
            t.stageTarget[level][f].reset();
        t.stagePass[level].reset();
        t.stage[level].reset();
    }
    for (int f = kCubeFaces - 1; f >= 0; --f)
        t.faceTarget[f].reset();
    t.cubeLevels = 0;
    t.captureTarget.reset();
    t.captureRenderPass.reset();
    t.captureDepth.reset();
    t.captureColour.reset();
    for (int s = kNearestSlots - 1; s >= 0; --s) {
        t.nearestTarget[s].reset();
        t.nearestRenderPass[s].reset();
    }
    t.renderTarget.reset();
    t.renderPass.reset();
    t.depthNearest.reset();
    t.depth.reset();
    for (int i = kMaxTargetColour - 1; i >= 0; --i) {
        t.resolve[i].reset();
        t.colour[i].reset();
        t.borrowedColour[i] = nullptr;        // N3.4: the owner's, never ours
    }
    t.borrowedDepth = nullptr;
    releaseChain(t);                          // ABI 33: its chain's bindings name these textures
    if (t.textures > 0 || t.bytes > 0)
        g_targets.fetchAndAddRelaxed(-1);
    g_textures.fetchAndAddRelaxed(-t.textures);
    g_bytes.fetchAndAddRelaxed(-t.bytes);
    t.textures = 0;
    t.bytes = 0;
    t.stepsDone = 0;
    t.newLayout = true;
}

bool SceneTargets::sync(QRhi *rhi, const QList<TargetDeclaration> &declarations, const QSize &surface, bool *relayout,
                        QString *error)
{
    *relayout = false;
    if (m_rhi && m_rhi != rhi) {
        *relayout = m_count > 0;
        release();                            // another QRhi: every object again (a node made again)
    }
    m_rhi = rhi;
    // QRhi's counts (a list by value) and the control's (under its mutex) only when either may have changed (audit 2,
    // M5: nothing allocated per record).
    const quint64 control = removedSampleCountsGeneration();
    if (rhi != m_supportedRhi || control != m_supportedControl) {
        m_supported = supportedSampleCounts(rhi);
        m_supportedRhi = rhi;
        m_supportedControl = control;
        ++m_stateVersion;
    }
    const int sizeMax = rhi ? rhi->resourceLimit(QRhi::TextureSizeMax) : 16384;
    if (declarations.size() > kMaxSceneTargets) {
        *error = QStringLiteral("a program declares at most %1 targets").arg(kMaxSceneTargets);
        return false;
    }
    // Targets no longer declared (or another order): their objects go.
    for (int i = 0; i < kMaxSceneTargets; ++i) {
        const bool kept = i < declarations.size() && m_targets[i] && m_targets[i]->decl.name == declarations.at(i).name;
        if (!kept && m_targets[i]) {
            if (m_targets[i]->renderPass || m_targets[i]->captureRenderPass)
                *relayout = true;
            releaseTarget(*m_targets[i]);
            m_targets[i].reset();
            ++m_stateVersion;
        }
    }
    if (m_count != int(declarations.size()))
        ++m_stateVersion;
    m_count = int(declarations.size());
    bool relaid[kMaxSceneTargets] = {};       // N3.4: a target whose objects are made anew this sync (a borrower follows)
    for (int i = 0; i < m_count; ++i) {
        const TargetDeclaration &d = declarations.at(i);
        if (!m_targets[i]) {
            m_targets[i] = std::make_unique<Target>();
            ++m_stateVersion;
        }
        Target &t = *m_targets[i];
        const bool dormant = d.transparency() && (m_dormant & (1u << i)) != 0;
        if (dormant != t.dormant) {
            // N3.4 (D17 point 3): a transparency target not admitted holds nothing; admitted again, it is made anew.
            if (t.renderPass)
                *relayout = true;
            releaseTarget(t);
            t.renderTarget.reset();
            t.dormant = dormant;
            t.decl = TargetDeclaration();
            t.allocation = QSize();
            ++m_stateVersion;
            ++m_layoutGeneration;             // the pipelines of its passes are built again (into it, or the owner)
        }
        if (dormant) {
            t.decl = d;
            t.content = QSize();
            continue;
        }
        const Target *owner = d.transparency() && d.owner >= 0 && d.owner < i ? m_targets[d.owner].get() : nullptr;
        if (d.transparency() && (!owner || owner->dormant)) {
            *error = QStringLiteral("transparency target '%1' has no owner allocated").arg(QString::fromLatin1(d.name));
            return false;
        }
        const QSize needed = owner ? owner->content : d.surfaceSized() ? surface : d.size;
        if (needed.width() < 1 || needed.height() < 1) {
            *error = QStringLiteral("target '%1' has no size (the surface has none yet)").arg(QString::fromLatin1(d.name));
            return false;
        }
        // N3.4: a transparency target is its owner's allocation and samples, made again whenever its owner's are.
        const int samples = owner ? owner->samples : clampSamples(m_supported, d.samples);
        // A planned layout can be between attachment steps, before its final render-pass descriptor exists.
        // Its nonempty allocation identifies that in-progress plan; a matching sync must preserve its steps.
        const bool layoutChanged = !t.decl.sameLayout(d) || samples != t.samples
            || (!t.renderPass && t.allocation.isEmpty())
            || (owner && relaid[d.owner]);
        QString reason;
        QSize allocation = d.exact ? exactAllocation(layoutChanged ? QSize() : t.allocation, needed, &reason) // ABI 33
                                   : nextAllocation(layoutChanged ? QSize() : t.allocation, needed, &reason);
        if (owner) {
            // Its owner's allocation (the owner, declared before it, was decided above): a new owner allocation is a new
            // one here, so the borrower's render target is made again over the owner's re-made objects.
            allocation = owner->allocation;
            reason = owner->allocation != t.allocation ? owner->lastReason : QString();
        }
        if (allocation.width() > sizeMax || allocation.height() > sizeMax) {
            *error = QStringLiteral("target '%1' needs %2 x %3, past the device's %4 a side")
                         .arg(QString::fromLatin1(d.name)).arg(allocation.width()).arg(allocation.height()).arg(sizeMax);
            return false;
        }
        if (t.content != needed)
            ++m_stateVersion;
        t.content = needed;
        if (!layoutChanged && allocation == t.allocation) {
            if (t.decl.size != d.size || t.decl.previousFrame != d.previousFrame)
                ++m_stateVersion;             // what the state reports of the declaration (the rest is the layout)
            t.decl = d;                       // the same layout; nothing to make (implicitly shared: no copy)
            continue;
        }
        ++m_stateVersion;
        if (layoutChanged) {
            if (t.renderPass || t.captureRenderPass)
                *relayout = true;
            t.newLayout = true;
        } else {
            t.newLayout = false;              // the same objects at the new size
        }
        relaid[i] = layoutChanged;
        t.decl = d;
        t.samples = samples;
        t.allocation = allocation;
        t.stepsDone = 0;
        // N3.4: a transparency target makes no depth of its own (its owner's) and has no capture.
        // ABI 42: a cube target's prefilter stages are one step more (no capture: refused at the program's parse).
        t.stepsTotal = d.transparency() ? int(d.colour.size()) + 1
                                        : int(d.colour.size()) + (d.depth ? 1 : 0) + 1 + (d.capture ? 1 : 0)
                                              + (d.cube ? 1 : 0);
        t.generation = nextTargetGeneration();
        t.lastReason = layoutChanged && reason == QLatin1String("made") ? QStringLiteral("made") : reason;
        ++m_allocations;
        g_allocations.fetchAndAddRelaxed(1);
    }
    return true;
}

bool SceneTargets::complete() const
{
    for (int i = 0; i < m_count; ++i) {
        if (m_targets[i] && !m_targets[i]->ready())
            return false;
    }
    return true;
}

bool SceneTargets::allocateStep(bool *done, QString *error)
{
    *done = false;
    for (int i = 0; i < m_count; ++i) {
        Target &t = *m_targets[i];
        if (t.ready())
            continue;
        if (t.stepsDone == 0 && t.newLayout)
            releaseTarget(t);                 // the old layout's objects (the caller released the pipelines over them)
        ++m_stateVersion;
        const bool ok = step(t, i, error);
        // Counts describe every owned texture, including a partial allocation or failed step awaiting release.
        // This runs at allocation edges only; completed targets do no bookkeeping per record.
        countTargetObjects(t);
        if (!ok) {
            // Audit 2, L5: the objects stay until the caller released the pipelines built over this target's
            // render-pass descriptor, then every target (release(); the header's order).
            t.allocation = QSize();
            return false;
        }
        ++t.stepsDone;
        ++m_steps;
        g_steps.fetchAndAddRelaxed(1);
        *done = complete();
        return true;
    }
    *done = true;
    return true;
}

bool SceneTargets::step(Target &t, int index, QString *error)
{
    Q_UNUSED(index);
    QRhi *rhi = m_rhi;
    const QByteArray label = QByteArrayLiteral("srpss core scene target ") + t.decl.name;
    const int colourCount = int(t.decl.colour.size());
    const int k = t.stepsDone;
    const auto make = [&](RhiOwned<QRhiTexture> &texture, QRhiTexture::Format format, int samples,
                          QRhiTexture::Flags flags, const QByteArray &name) {
        if (!t.newLayout && texture) {
            texture->setPixelSize(t.allocation);
            m_objectGeneration += 1;
            return texture->create();
        }
        texture.reset(rhi->newTexture(format, t.allocation, samples, flags));
        texture->setName(name);
        m_objectGeneration += 1;
        return texture->create();
    };
    QRhiTexture::Flags readableFlags = QRhiTexture::RenderTarget | QRhiTexture::UsedAsTransferSource;
    if (t.decl.mips)
        readableFlags |= QRhiTexture::MipMapped | QRhiTexture::UsedWithGenerateMips; // N3.4 (D17 choice G)
    const Target *owner = t.decl.transparency() && t.decl.owner >= 0 && t.decl.owner < m_count
        ? m_targets[t.decl.owner].get() : nullptr;
    if (k < colourCount) {
        const TargetAttachment &a = t.decl.colour.at(k);
        if (a.borrowed)
            return true;                      // N3.4: the owner's (taken at the render target's step)
        const QRhiTexture::Format format = targetRhiFormat(a.format);
        const QByteArray name = label + QByteArrayLiteral(".") + a.name;
        QRhiTexture::Flags flags = t.samples > 1 ? QRhiTexture::Flags(QRhiTexture::RenderTarget) : readableFlags;
        if (t.decl.selfMips && a.mipsRead)
            flags |= QRhiTexture::UsedWithLoadStore; // ABI 33: its chain is the core's box kernel's (image stores)
        if (t.decl.cube)
            flags |= QRhiTexture::CubeMap | QRhiTexture::MipMapped; // ABI 42: the probe's cube, its chain the prefilter's
        bool ok = make(t.colour[k], format, t.samples, flags, name);
        // A resolve only for an attachment a sampler or the capture reads (D14 point 8). An unread resolve is never
        // read between two passes' stores, and its render pass's UNDEFINED transition then races the last store
        // (SYNC-HAZARD-WRITE-AFTER-WRITE, build round 1's msaa round).
        if (ok && t.samples > 1 && a.read)
            ok = make(t.resolve[k], format, 1, readableFlags, name + QByteArrayLiteral(" resolve"));
        if (!ok)
            *error = QStringLiteral("target '%1': attachment '%2' could not be created at %3 x %4 (%5 sample(s))")
                         .arg(QString::fromLatin1(t.decl.name), QString::fromLatin1(a.name))
                         .arg(t.allocation.width()).arg(t.allocation.height()).arg(t.samples);
        return ok;
    }
    int next = colourCount;
    if (t.decl.depth && !t.decl.transparency()) {
        if (k == next) {
            bool ok = make(t.depth, QRhiTexture::D32F, t.samples, QRhiTexture::RenderTarget, label + ".depth");
            // D14 point 10: a read multisampled depth's nearest resolve (R32F window depth), written by the core's pass.
            if (ok && t.samples > 1 && t.decl.depthRead)
                ok = make(t.depthNearest, QRhiTexture::R32F, 1, readableFlags, label + ".depth nearest");
            if (!ok)
                *error = QStringLiteral("target '%1': its depth could not be created at %2 x %3 (%4 sample(s))")
                             .arg(QString::fromLatin1(t.decl.name)).arg(t.allocation.width())
                             .arg(t.allocation.height()).arg(t.samples);
            return ok;
        }
        ++next;
    }
    if (k == next) {
        // The render target over every attachment (rule B: colour and depth preserved, cleared by a draw).
        if (owner) {
            // N3.4 (D17 point 2): the owner's borrowed attachments and depth, as the owner holds them now (its objects
            // were made before this target's: it is declared first).
            for (int i = 0; i < colourCount; ++i) {
                const TargetAttachment &a = t.decl.colour.at(i);
                t.borrowedColour[i] = a.borrowed ? owner->colour[a.ownerColour].get() : nullptr;
                if (a.borrowed && !t.borrowedColour[i]) {
                    *error = QStringLiteral("transparency target '%1': its owner's attachment '%2' is not made")
                                 .arg(QString::fromLatin1(t.decl.name), QString::fromLatin1(a.name));
                    return false;
                }
            }
            t.borrowedDepth = owner->depth.get();
            if (!t.borrowedDepth) {
                *error = QStringLiteral("transparency target '%1': its owner's depth is not made")
                             .arg(QString::fromLatin1(t.decl.name));
                return false;
            }
        }
        if (t.newLayout || !t.renderTarget) {
            // N3.4: a transparency target's borrowed attachments are its owner's textures (no resolve: the owner's run
            // that follows resolves them), its depth the owner's. The owner's objects re-made in place at a new size keep
            // their addresses, so the description stays true and create() below follows them; a new owner layout is a
            // new layout here too (sync).
            QList<QRhiColorAttachment> attachments;
            for (int i = 0; i < colourCount; ++i) {
                QRhiColorAttachment attachment(t.colourTexture(i));
                if (t.samples > 1 && !t.decl.colour.at(i).nearest && !t.decl.colour.at(i).borrowed)
                    attachment.setResolveTexture(t.resolve[i].get()); // QRhi's average (null: not read)
                if (t.decl.cube) {
                    attachment.setLayer(0);   // ABI 42: face 0 (+X) of level 0; the other faces' targets below
                    attachment.setLevel(0);
                }
                attachments.append(attachment);
            }
            QRhiTextureRenderTargetDescription description;
            description.setColorAttachments(attachments.cbegin(), attachments.cend());
            if (t.depthTexture())
                description.setDepthTexture(t.depthTexture()); // never a depth resolve: the samples are stored (D14 10)
            QRhiTextureRenderTarget::Flags flags = QRhiTextureRenderTarget::PreserveColorContents;
            if (t.depthTexture())
                flags |= QRhiTextureRenderTarget::PreserveDepthStencilContents;
            t.renderTarget.reset(rhi->newTextureRenderTarget(description, flags));
            t.renderTarget->setName(label);
            t.renderPass.reset(t.renderTarget->newCompatibleRenderPassDescriptor());
            t.renderTarget->setRenderPassDescriptor(t.renderPass.get());
            ++m_layoutGeneration;
        }
        m_objectGeneration += 1;
        if (!t.renderTarget->create()) {
            *error = QStringLiteral("target '%1': its render target could not be created at %2 x %3")
                         .arg(QString::fromLatin1(t.decl.name)).arg(t.allocation.width()).arg(t.allocation.height());
            return false;
        }
        if (t.decl.cube) {
            // ABI 42 (N4.d, the lead's decision: six passes, one render target per face): faces 1..5 of level 0, each
            // over the same depth (cleared per face by its run), all compatible with face 0's descriptor, so the passes'
            // pipelines (built over renderPass) draw into every face.
            for (int f = 1; f < kCubeFaces; ++f) {
                if (t.newLayout || !t.faceTarget[f]) {
                    QRhiColorAttachment attachment(t.colour[0].get());
                    attachment.setLayer(f);
                    attachment.setLevel(0);
                    QRhiTextureRenderTargetDescription description { attachment };
                    if (t.depth)
                        description.setDepthTexture(t.depth.get());
                    QRhiTextureRenderTarget::Flags flags = QRhiTextureRenderTarget::PreserveColorContents;
                    if (t.depth)
                        flags |= QRhiTextureRenderTarget::PreserveDepthStencilContents;
                    t.faceTarget[f].reset(rhi->newTextureRenderTarget(description, flags));
                    t.faceTarget[f]->setName(label + QByteArrayLiteral(".face") + QByteArray::number(f));
                    t.faceTarget[f]->setRenderPassDescriptor(t.renderPass.get());
                }
                if (!t.faceTarget[f]->create()) {
                    *error = QStringLiteral("target '%1': face %2's render target could not be created at %3 x %3")
                                 .arg(QString::fromLatin1(t.decl.name)).arg(f).arg(t.allocation.width());
                    return false;
                }
            }
        }
        // D14 point 10: each nearest resolve's render target (one R32F attachment, written whole: no load).
        for (int s = 0; s < kNearestSlots; ++s) {
            QRhiTexture *dest = t.nearestDest(s);
            if (!dest) {
                t.nearestTarget[s].reset();
                t.nearestRenderPass[s].reset();
                continue;
            }
            if (t.newLayout || !t.nearestTarget[s]) {
                QRhiTextureRenderTargetDescription description { QRhiColorAttachment(dest) };
                t.nearestTarget[s].reset(rhi->newTextureRenderTarget(description));
                t.nearestTarget[s]->setName(label + QByteArrayLiteral(".nearest"));
                t.nearestRenderPass[s].reset(t.nearestTarget[s]->newCompatibleRenderPassDescriptor());
                t.nearestTarget[s]->setRenderPassDescriptor(t.nearestRenderPass[s].get());
                ++m_layoutGeneration;
            }
            if (!t.nearestTarget[s]->create()) {
                *error = QStringLiteral("target '%1': a nearest resolve's render target could not be created at %2 x %3")
                             .arg(QString::fromLatin1(t.decl.name)).arg(t.allocation.width())
                             .arg(t.allocation.height());
                return false;
            }
        }
        return true;
    }
    if (t.decl.cube) {
        // ABI 42: the prefilter's stage cube of each level L >= 1 (one level, the level's side) and its six face render
        // targets: the prefilter draws level L of a face here from the cube's level L - 1, then copies it into the cube
        // (cube_prefilter.h). Made again whole at an allocation edge (never per record).
        for (int level = kMaxCubeLevels - 1; level >= 1; --level) {
            for (int f = kCubeFaces - 1; f >= 0; --f)
                t.stageTarget[level][f].reset();
            t.stagePass[level].reset();
            t.stage[level].reset();
        }
        t.cubeLevels = qMin(mipChainLevels(t.allocation), kMaxCubeLevels);
        for (int level = 1; level < t.cubeLevels; ++level) {
            const int side = qMax(1, t.allocation.width() >> level);
            t.stage[level].reset(rhi->newTexture(QRhiTexture::RGBA16F, QSize(side, side), 1,
                                                 QRhiTexture::CubeMap | QRhiTexture::RenderTarget
                                                     | QRhiTexture::UsedAsTransferSource));
            t.stage[level]->setName(label + QByteArrayLiteral(".prefilter stage ") + QByteArray::number(level));
            m_objectGeneration += 1;
            if (!t.stage[level]->create()) {
                *error = QStringLiteral("target '%1': its prefilter stage of level %2 could not be created at %3 x %3")
                             .arg(QString::fromLatin1(t.decl.name)).arg(level).arg(side);
                return false;
            }
            for (int f = 0; f < kCubeFaces; ++f) {
                QRhiColorAttachment attachment(t.stage[level].get());
                attachment.setLayer(f);
                QRhiTextureRenderTargetDescription description { attachment };
                t.stageTarget[level][f].reset(rhi->newTextureRenderTarget(description)); // written whole: no load
                t.stageTarget[level][f]->setName(label + QByteArrayLiteral(".prefilter ") + QByteArray::number(level)
                                                 + QByteArrayLiteral(".") + QByteArray::number(f));
                if (f == 0)
                    t.stagePass[level].reset(t.stageTarget[level][0]->newCompatibleRenderPassDescriptor());
                t.stageTarget[level][f]->setRenderPassDescriptor(t.stagePass[level].get());
                if (!t.stageTarget[level][f]->create()) {
                    *error = QStringLiteral("target '%1': its prefilter target of level %2, face %3 could not be "
                                            "created").arg(QString::fromLatin1(t.decl.name)).arg(level).arg(f);
                    return false;
                }
            }
        }
        ++m_layoutGeneration;                 // the prefilter's pipeline is built over the stages' descriptors
        return true;
    }
    // The capture (D14 point 5): the colour as attachment 0's format, linear; the nearest window depth R32F, nearest.
    const QRhiTexture::Format captureFormat = targetRhiFormat(t.decl.colour.at(0).format);
    bool ok = make(t.captureColour, captureFormat, 1, readableFlags, label + ".capture_colour")
        && make(t.captureDepth, QRhiTexture::R32F, 1, readableFlags, label + ".capture_depth");
    if (ok) {
        if (t.newLayout || !t.captureTarget) {
            QRhiTextureRenderTargetDescription description;
            const QList<QRhiColorAttachment> attachments = { QRhiColorAttachment(t.captureColour.get()),
                                                             QRhiColorAttachment(t.captureDepth.get()) };
            description.setColorAttachments(attachments.cbegin(), attachments.cend());
            t.captureTarget.reset(rhi->newTextureRenderTarget(description,
                                                              QRhiTextureRenderTarget::PreserveColorContents));
            t.captureTarget->setName(label + ".capture");
            t.captureRenderPass.reset(t.captureTarget->newCompatibleRenderPassDescriptor());
            t.captureTarget->setRenderPassDescriptor(t.captureRenderPass.get());
            ++m_layoutGeneration;
        }
        ok = t.captureTarget->create();
    }
    if (!ok) {
        *error = QStringLiteral("target '%1': its capture could not be created at %2 x %3")
                     .arg(QString::fromLatin1(t.decl.name)).arg(t.allocation.width()).arg(t.allocation.height());
        return false;
    }
    return true;
}

QRhiTexture *SceneTargets::sampledTexture(const QByteArray &name) const
{
    const qsizetype dot = name.indexOf('.');
    if (dot <= 0)
        return nullptr;
    const Target *t = target(indexOf(name.left(dot)));
    if (!t || !t->ready())
        return nullptr;
    const QByteArray attachment = name.mid(dot + 1);
    if (attachment == "depth")
        return t->readableDepth();
    if (attachment == "capture_colour")
        return t->captureColour.get();
    if (attachment == "capture_depth")
        return t->captureDepth.get();
    return t->readable(t->decl.colourIndex(attachment));
}

int SceneTargets::loadedColour(int index, QRhiTexture **out) const
{
    const Target *t = target(index);
    int n = 0;
    for (int i = 0; t && i < int(t->decl.colour.size()) && i < kMaxTargetColour; ++i) {
        if (QRhiTexture *texture = t->colourTexture(i)) // N3.4: a borrowed attachment is loaded too (the owner's)
            out[n++] = texture;
    }
    return n;
}

int SceneTargets::averageResolves(int index, QRhiTexture **out) const
{
    const Target *t = target(index);
    int n = 0;
    if (!t || t->samples <= 1)
        return 0;
    for (int i = 0; i < int(t->decl.colour.size()) && i < kMaxTargetColour; ++i) {
        if (!t->decl.colour.at(i).nearest && t->resolve[i])   // the render target's resolve (step's attachments)
            out[n++] = t->resolve[i].get();
    }
    return n;
}

int SceneTargets::generateSelfMips(QRhi *rhi, QRhiCommandBuffer *cb, int index, bool *ok, QString *error)
{
    *ok = true;
    Target *t = target(index);
    if (!rhi || !cb || !t || !t->decl.selfMips || t->dormant || t->samples != 1)
        return 0;
    bool any = false;
    for (int c = 0; c < int(t->decl.colour.size()) && c < kMaxTargetColour; ++c)
        any = any || (t->decl.colour.at(c).mipsRead && t->colour[c]);
    if (!any)
        return 0;                             // no sampler reads a level past 0: nothing to make
    if (t->chainGeneration != t->generation || t->chainBindings() == 0) {
        // The bindings over this allocation's textures (made once per allocation, never per record).
        releaseChain(*t);
        for (int c = 0; c < int(t->decl.colour.size()) && c < kMaxTargetColour; ++c) {
            if (!t->decl.colour.at(c).mipsRead || !t->colour[c])
                continue;
            if (!m_chainKernel.bind(rhi, t->colour[c].get(), t->allocation, &t->chain[c], error)) {
                *ok = false;
                *error = QStringLiteral("target '%1': %2").arg(QString::fromLatin1(t->decl.name), *error);
                releaseChain(*t);
                return 0;
            }
        }
        t->chainGeneration = t->generation;
    }
    int made = 0;
    for (int c = 0; c < int(t->decl.colour.size()) && c < kMaxTargetColour; ++c) {
        if (!t->decl.colour.at(c).mipsRead || !t->colour[c])
            continue;
        m_chainKernel.record(cb, t->chain[c]); // one compute pass a level (mip_chain.h)
        ++made;
    }
    if (made)
        g_selfMips.fetchAndAddRelaxed(made);
    return made;
}

int SceneTargets::Target::chainBindings() const
{
    int bindings = 0;
    for (const MipChain &c : chain)
        bindings += c.bindings;
    return bindings;
}

void SceneTargets::releaseChain(Target &t)
{
    for (int c = kMaxTargetColour - 1; c >= 0; --c)
        t.chain[c].release();
    t.chainGeneration = 0;
}

int SceneTargets::liveObjects() const
{
    int objects = 0;
    for (int i = 0; i < m_count; ++i) {
        if (!m_targets[i])
            continue;
        objects += m_targets[i]->textures + (m_targets[i]->renderTarget ? 2 : 0)
            + (m_targets[i]->captureTarget ? 2 : 0) + m_targets[i]->chainBindings(); // ABI 33: the chain's
        for (int s = 0; s < kNearestSlots; ++s)
            objects += m_targets[i]->nearestTarget[s] ? 2 : 0;
        // ABI 42: a cube's face targets and its prefilter stages' targets and descriptors (their textures are counted).
        for (int f = 0; f < kCubeFaces; ++f)
            objects += m_targets[i]->faceTarget[f] ? 1 : 0;
        for (int level = 0; level < kMaxCubeLevels; ++level) {
            objects += m_targets[i]->stagePass[level] ? 1 : 0;
            for (int f = 0; f < kCubeFaces; ++f)
                objects += m_targets[i]->stageTarget[level][f] ? 1 : 0;
        }
    }
    return objects;
}

void SceneTargets::release()
{
    if (m_rhi || m_count > 0)
        ++m_stateVersion;                     // a set that was synced reports its release (a never-used one: nothing)
    for (int i = 0; i < kMaxSceneTargets; ++i) {
        if (m_targets[i]) {
            releaseTarget(*m_targets[i]);
            m_targets[i].reset();
        }
    }
    m_count = 0;
    m_chainKernel.release();                  // ABI 33 (ABI 35: mip_chain.h)
    m_rhi = nullptr;
    m_supportedRhi = nullptr;                 // a later QRhi may take the address: its counts are read again
    ++m_layoutGeneration;
    ++m_objectGeneration;
}

std::shared_ptr<SceneReadback> SceneTargets::startReadback(QRhiCommandBuffer *cb)
{
    pruneReadbacks();
    auto set = std::make_shared<SceneReadback>();
    SceneReadback *raw = set.get();
    const auto levelCount = [](const Target &t) {
        // N3.4: a mipped target's every level (the defocus layer's mips, D17 choice G's proof), else its base.
        int levels = 1;
        if (t.decl.cube)
            return qMax(1, t.cubeLevels);     // ABI 42: a cube's every level (the prefilter's proof)
        for (QSize s = t.allocation; t.decl.mips && (s.width() > 1 || s.height() > 1); ++levels)
            s = QSize(qMax(1, s.width() / 2), qMax(1, s.height() / 2));
        return levels;
    };
    // ABI 42: a cube's six faces ("<target>.<attachment>#<face>@<level>"), every other texture's one.
    const auto faceCount = [](const Target &t) { return t.decl.cube ? kCubeFaces : 1; };
    const auto add = [&](const Target &t, const QString &name, QRhiTexture *texture, const QString &format,
                         int level = 0, int face = -1) {
        if (!texture)
            return;
        SceneTargetPixels p;
        const QString faced = face >= 0 ? name + QLatin1Char('#') + QString::number(face) : name;
        p.name = level ? faced + QLatin1Char('@') + QString::number(level) : faced;
        p.face = face;
        p.size = QSize(qMax(1, t.allocation.width() >> level), qMax(1, t.allocation.height() >> level));
        // Project the base content's normalized rectangle, rounding out to touched level texels. This is nominal
        // coverage, not a promise about the mip filter's footprint outside the rectangle on odd-sized levels.
        p.content = QSize(int((qint64(t.content.width()) * p.size.width() + t.allocation.width() - 1)
                             / t.allocation.width()),
                          int((qint64(t.content.height()) * p.size.height() + t.allocation.height() - 1)
                             / t.allocation.height()));
        p.format = format;
        p.samples = t.samples;
        p.level = level;
        raw->pixels.append(p);
        ++raw->count;
    };
    for (int i = 0; i < m_count; ++i) {
        const Target &t = *m_targets[i];
        if (!t.ready() || t.dormant)
            continue;
        const QString base = QString::fromLatin1(t.decl.name);
        for (int c = 0; c < int(t.decl.colour.size()); ++c) {
            for (int face = 0; face < faceCount(t); ++face) {
                for (int level = 0; level < levelCount(t); ++level)
                    add(t, base + QLatin1Char('.') + QString::fromLatin1(t.decl.colour.at(c).name), t.readable(c),
                        targetFormatName(t.decl.colour.at(c).format), level, t.decl.cube ? face : -1);
            }
        }
        if (t.depthNearest)
            add(t, base + QStringLiteral(".depth"), t.depthNearest.get(), QStringLiteral("r32f"));
        if (t.decl.capture) {
            add(t, base + QStringLiteral(".capture_colour"), t.captureColour.get(),
                targetFormatName(t.decl.colour.at(0).format));
            add(t, base + QStringLiteral(".capture_depth"), t.captureDepth.get(), QStringLiteral("r32f"));
        }
    }
    if (raw->count == 0)
        return set;
    // Qt 6.12's QRhiGles2 reads R16F straight into a tightly sized buffer without changing GL_PACK_ALIGNMENT.
    // Odd-width rows must be tight before the read runs; repacking afterward would read past Qt's buffer.
    const bool tightPack = m_rhi->backend() == QRhi::OpenGLES2
        && std::any_of(raw->pixels.cbegin(), raw->pixels.cend(), [](const SceneTargetPixels &p) {
               return p.format == QStringLiteral("r16f") && p.size.width() % 2 != 0;
           });
    QOpenGLContext *readContext = nullptr;
    GLint previousAlignment = 1;
    if (tightPack) {
        cb->beginExternal();
        readContext = QOpenGLContext::currentContext();
        if (readContext) {
            QOpenGLFunctions *gl = readContext->functions();
            gl->glGetIntegerv(GL_PACK_ALIGNMENT, &previousAlignment);
            gl->glPixelStorei(GL_PACK_ALIGNMENT, 1);
        }
        cb->endExternal();
        if (!readContext) {
            qWarning("Cannot read odd-width R16F scene targets without the current OpenGL context");
            return {};
        }
    }
    QRhiResourceUpdateBatch *updates = m_rhi->nextResourceUpdateBatch();
    // All accepted attachments and mip levels. Callback result addresses stay stable for the entire shared lifetime.
    raw->results = std::make_unique<QRhiReadbackResult[]>(raw->count);
    raw->pending.storeRelease(raw->count);
    g_readbacksPending.fetchAndAddRelaxed(1);
    // The textures, in the order the pixels were listed.
    int r = 0;
    for (int i = 0; i < m_count && r < raw->count; ++i) {
        const Target &t = *m_targets[i];
        if (!t.ready() || t.dormant)
            continue;
        struct Read { QRhiTexture *texture; int level; int layer; };
        QList<Read> textures; // (texture, level, layer), in the order the pixels were listed
        for (int c = 0; c < int(t.decl.colour.size()); ++c) {
            for (int face = 0; face < faceCount(t); ++face) {
                for (int level = 0; t.readable(c) && level < levelCount(t); ++level)
                    textures.append({ t.readable(c), level, face }); // ABI 42: a cube's face is its layer
            }
        }
        if (t.depthNearest)
            textures.append({ t.depthNearest.get(), 0, 0 });
        if (t.decl.capture) {
            if (t.captureColour)
                textures.append({ t.captureColour.get(), 0, 0 });
            if (t.captureDepth)
                textures.append({ t.captureDepth.get(), 0, 0 });
        }
        for (const Read &texture : textures) {
            if (r >= raw->count)
                break;
            raw->results[r].completed = [raw]() {
                if (raw->pending.fetchAndAddOrdered(-1) == 1)
                    g_readbacksPending.fetchAndAddRelaxed(-1);
            };
            QRhiReadbackDescription description(texture.texture);
            description.setLevel(texture.level);
            description.setLayer(texture.layer);
            updates->readBackTexture(description, &raw->results[r]);
            ++r;
        }
    }
    {
        QMutexLocker lock(&readbackMutex());
        readbacksInFlight().append(set);
    }
    cb->resourceUpdate(updates);
    if (readContext) {
        // On OpenGL this boundary executes the queued readbacks before restoring the context's pixel-store state.
        cb->beginExternal();
        if (QOpenGLContext::currentContext() == readContext)
            readContext->functions()->glPixelStorei(GL_PACK_ALIGNMENT, previousAlignment);
        cb->endExternal();
    }
    return set;
}

SceneTargetsState SceneTargets::state(QRhi *rhi) const
{
    SceneTargetsState s;
    s.noted = true;
    s.supported = m_supported;
    if (rhi) {
        s.backend = QString::fromLatin1(rhi->backendName());
        s.yUpInFramebuffer = rhi->isYUpInFramebuffer();
        s.resolveDepthStencil = rhi->isFeatureSupported(QRhi::ResolveDepthStencil);
        s.perRenderTargetBlending = rhi->isFeatureSupported(QRhi::PerRenderTargetBlending);
        s.multisampleTexture = rhi->isFeatureSupported(QRhi::MultisampleTexture);
    }
    s.allocations = m_allocations;
    s.steps = m_steps;
    s.layoutGeneration = m_layoutGeneration;
    s.objectGeneration = m_objectGeneration;
    for (int i = 0; i < m_count; ++i) {
        const Target &t = *m_targets[i];
        SceneTargetsState::Entry e;
        e.decl = t.decl;
        e.content = t.content;
        e.allocation = t.allocation;
        e.samples = t.samples;
        e.bytes = t.bytes;
        e.textures = t.textures;
        e.generation = t.generation;
        e.ready = t.ready();
        e.lastReason = t.lastReason;
        s.targets.append(e);
    }
    s.fallbacks = m_fallbacks;                // N3.4
    return s;
}

bool SceneTargets::takeStateChange()
{
    if (m_stateVersion == m_stateNoted)
        return false;
    m_stateNoted = m_stateVersion;
    return true;
}

QJsonObject sceneTargetsStateJson(const SceneTargetsState &s)
{
    QJsonObject o;
    if (!s.noted)
        return o;
    QJsonArray supported;
    for (const int count : s.supported)
        supported.append(count);
    o.insert(QStringLiteral("supported_samples"), supported);
    QJsonArray removed;
    for (const int count : removedSampleCounts())
        removed.append(count);
    o.insert(QStringLiteral("removed_samples"), removed);
    // A fact only (D14 point 10: the core's nearest resolve replaces QRhi's depth resolve on every backend).
    o.insert(QStringLiteral("resolve_depth_stencil"), s.resolveDepthStencil);
    o.insert(QStringLiteral("nearest_first_sample_control"), nearestFirstSample());
    o.insert(QStringLiteral("per_render_target_blending"), s.perRenderTargetBlending);
    o.insert(QStringLiteral("multisample_texture"), s.multisampleTexture);
    o.insert(QStringLiteral("backend"), s.backend);
    o.insert(QStringLiteral("allocations"), double(s.allocations));
    o.insert(QStringLiteral("steps"), double(s.steps));
    o.insert(QStringLiteral("layout_generation"), double(s.layoutGeneration));
    o.insert(QStringLiteral("object_generation"), double(s.objectGeneration));
    QJsonArray targets;
    for (const SceneTargetsState::Entry &t : s.targets) {
        QJsonObject e = t.decl.toJson();
        e.insert(QStringLiteral("content"), QJsonArray { t.content.width(), t.content.height() });
        e.insert(QStringLiteral("allocation"), QJsonArray { t.allocation.width(), t.allocation.height() });
        e.insert(QStringLiteral("requested_samples"), t.decl.samples);
        e.insert(QStringLiteral("effective_samples"), t.samples);
        e.insert(QStringLiteral("bytes"), double(t.bytes));
        e.insert(QStringLiteral("textures"), t.textures);
        e.insert(QStringLiteral("generation"), double(t.generation));
        e.insert(QStringLiteral("ready"), t.ready);
        e.insert(QStringLiteral("last_reason"), t.lastReason);
        if (!s.backend.isEmpty()) {
            const QRect v = contentViewport(s.yUpInFramebuffer, t.allocation, t.content);
            e.insert(QStringLiteral("viewport"), QJsonArray { v.x(), v.y(), v.width(), v.height() });
        }
        targets.append(e);
    }
    o.insert(QStringLiteral("targets"), targets);
    o.insert(QStringLiteral("transparency_fallbacks"), QJsonArray::fromStringList(s.fallbacks)); // N3.4 (D17 point 3)
    return o;
}

} // namespace srpss_core
