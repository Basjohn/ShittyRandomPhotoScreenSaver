// Scene targets (N3.1, D14): scene_targets.h has the contract.
#include "scene_targets.h"

#include <QtCore/QJsonValue>

#include <cmath>

namespace srpss_core {

namespace {

QAtomicInteger<int> g_targets { 0 };
QAtomicInteger<int> g_textures { 0 };
QAtomicInteger<qint64> g_bytes { 0 };
QAtomicInteger<qint64> g_allocations { 0 };
QAtomicInteger<qint64> g_steps { 0 };
QAtomicInteger<int> g_readbacksPending { 0 };

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

const char *const kFormatNames[] = { "rgba8", "rgba16f", "r16f", "r32f" };

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
    const QSize size = texture->pixelSize();
    return qint64(size.width()) * qint64(size.height()) * qint64(textureBytesPerSample(texture->format()))
        * qint64(qMax(1, texture->sampleCount()));
}

} // namespace

// ------------------------------------------------------------------------------------------------- formats

bool parseTargetFormat(const QString &text, TargetFormat *out)
{
    for (int i = 0; i < 4; ++i) {
        if (text == QLatin1String(kFormatNames[i])) {
            *out = TargetFormat(i);
            return true;
        }
    }
    return false;
}

QString targetFormatName(TargetFormat format)
{
    return QLatin1String(kFormatNames[qBound(0, int(format), 3)]);
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
    if (name != o.name || depth != o.depth || depthRead != o.depthRead || samples != o.samples || capture != o.capture
        || colour.size() != o.colour.size() || surfaceSized() != o.surfaceSized())
        return false;
    for (qsizetype i = 0; i < colour.size(); ++i) {
        const TargetAttachment &a = colour.at(i);
        const TargetAttachment &b = o.colour.at(i);
        if (a.name != b.name || a.format != b.format || a.read != b.read)
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
        list.append(c);
    }
    o.insert(QStringLiteral("colour"), list);
    o.insert(QStringLiteral("depth"), depth);
    o.insert(QStringLiteral("depth_read"), depthRead);
    o.insert(QStringLiteral("samples"), samples);
    o.insert(QStringLiteral("capture"), capture);
    return o;
}

bool parseTargetDeclaration(const QJsonValue &value, TargetDeclaration *out, QString *error)
{
    const QString shape = QStringLiteral("a target is {\"name\": an identifier, \"size\": \"surface\" or [w, h], "
                                         "\"colour\": [{\"name\", \"format\": rgba8, rgba16f, r16f or r32f, "
                                         "\"clear\"?: [r, g, b, a]}, 1 to %1], \"depth\"?: true or false, "
                                         "\"samples\"?: 1 to %2}").arg(kMaxTargetColour).arg(kMaxSceneSamples);
    if (!value.isObject()) {
        *error = shape;
        return false;
    }
    const QJsonObject o = value.toObject();
    const QStringList keys = { QStringLiteral("name"), QStringLiteral("size"), QStringLiteral("colour"),
                               QStringLiteral("depth"), QStringLiteral("samples") };
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
        if (!entry.isObject() || c.size() != (withClear ? 3 : 2) || !identifier(a.name)
            || !parseTargetFormat(c.value(QStringLiteral("format")).toString(), &a.format)) {
            *error = QStringLiteral("target '%1': an attachment is {\"name\": an identifier, \"format\": rgba8, "
                                    "rgba16f, r16f or r32f, \"clear\"?: [r, g, b, a]}").arg(label);
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
    *out = d;
    return true;
}

// ------------------------------------------------------------------------------------------------- allocation rules

int bucketPixels(int pixels)
{
    const int p = qMax(1, pixels);
    return qMax(kSceneBucket, ((p + kSceneBucket - 1) / kSceneBucket) * kSceneBucket);
}

QSize nextAllocation(const QSize &current, const QSize &needed, QString *reason)
{
    const QSize bucketed(bucketPixels(needed.width()), bucketPixels(needed.height()));
    if (current.isEmpty()) {
        *reason = QStringLiteral("made");
        return bucketed;
    }
    if (needed.width() > current.width() || needed.height() > current.height()) {
        *reason = QStringLiteral("grown");
        return bucketed;
    }
    // Shrink only with hysteresis: two or more buckets below the allocation on either axis.
    if (current.width() - bucketed.width() >= 2 * kSceneBucket
        || current.height() - bucketed.height() >= 2 * kSceneBucket) {
        *reason = QStringLiteral("shrunk");
        return bucketed;
    }
    reason->clear();
    return current;
}

QRect contentViewport(bool yUpInFramebuffer, const QSize &allocation, const QSize &content)
{
    const int w = qMin(content.width(), allocation.width());
    const int h = qMin(content.height(), allocation.height());
    return QRect(0, yUpInFramebuffer ? allocation.height() - h : 0, w, h);
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

void setRemovedSampleCounts(const QList<int> &removed)
{
    QMutexLocker lock(&removedMutex());
    removedCounts() = removed;
}

QList<int> removedSampleCounts()
{
    QMutexLocker lock(&removedMutex());
    return removedCounts();
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
    return c;
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
    return samples > 1 ? depthResolve.get() : depth.get();
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
    // Reverse order of creation: the capture's target, its descriptor and textures; the target, its descriptor; the
    // depth and its resolve; the colour attachments and their resolves.
    t.captureTarget.reset();
    t.captureRenderPass.reset();
    t.captureDepth.reset();
    t.captureColour.reset();
    t.renderTarget.reset();
    t.renderPass.reset();
    t.depthResolve.reset();
    t.depth.reset();
    for (int i = kMaxTargetColour - 1; i >= 0; --i) {
        t.resolve[i].reset();
        t.colour[i].reset();
    }
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
    m_supported = supportedSampleCounts(rhi);
    m_resolveDepth = rhi && rhi->isFeatureSupported(QRhi::ResolveDepthStencil);
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
        }
    }
    m_count = int(declarations.size());
    for (int i = 0; i < m_count; ++i) {
        const TargetDeclaration &d = declarations.at(i);
        if (!m_targets[i])
            m_targets[i] = std::make_unique<Target>();
        Target &t = *m_targets[i];
        const QSize needed = d.surfaceSized() ? surface : d.size;
        if (needed.width() < 1 || needed.height() < 1) {
            *error = QStringLiteral("target '%1' has no size (the surface has none yet)").arg(QString::fromLatin1(d.name));
            return false;
        }
        const int samples = clampSamples(m_supported, d.samples);
        if (samples > 1 && d.depthRead && !m_resolveDepth) {
            // Choice E: QRhi's depth resolve or nothing (no workaround is built); the content fails with this reason.
            *error = QStringLiteral("target '%1': a multisampled depth that is read needs QRhi::ResolveDepthStencil, which "
                                    "this device does not report").arg(QString::fromLatin1(d.name));
            return false;
        }
        const bool layoutChanged = !t.decl.sameLayout(d) || samples != t.samples || !t.renderPass;
        QString reason;
        const QSize allocation = nextAllocation(layoutChanged ? QSize() : t.allocation, needed, &reason);
        if (allocation.width() > sizeMax || allocation.height() > sizeMax) {
            *error = QStringLiteral("target '%1' needs %2 x %3, past the device's %4 a side")
                         .arg(QString::fromLatin1(d.name)).arg(allocation.width()).arg(allocation.height()).arg(sizeMax);
            return false;
        }
        t.content = needed;
        if (!layoutChanged && allocation == t.allocation) {
            t.decl = d;                       // the same layout; nothing to make
            continue;
        }
        if (layoutChanged) {
            if (t.renderPass || t.captureRenderPass)
                *relayout = true;
            t.newLayout = true;
        } else {
            t.newLayout = false;              // the same objects at the new size
        }
        t.decl = d;
        t.samples = samples;
        t.allocation = allocation;
        t.stepsDone = 0;
        t.stepsTotal = int(d.colour.size()) + (d.depth ? 1 : 0) + 1 + (d.capture ? 1 : 0);
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
        if (!step(t, i, error)) {
            releaseTarget(t);
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
    const auto make = [&](std::unique_ptr<QRhiTexture> &texture, QRhiTexture::Format format, int samples,
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
    const QRhiTexture::Flags readableFlags = QRhiTexture::RenderTarget | QRhiTexture::UsedAsTransferSource;
    if (k < colourCount) {
        const TargetAttachment &a = t.decl.colour.at(k);
        const QRhiTexture::Format format = targetRhiFormat(a.format);
        const QByteArray name = label + QByteArrayLiteral(".") + a.name;
        bool ok = make(t.colour[k], format, t.samples, t.samples > 1 ? QRhiTexture::RenderTarget : readableFlags, name);
        if (ok && t.samples > 1)
            ok = make(t.resolve[k], format, 1, readableFlags, name + QByteArrayLiteral(" resolve"));
        if (!ok)
            *error = QStringLiteral("target '%1': attachment '%2' could not be created at %3 x %4 (%5 sample(s))")
                         .arg(QString::fromLatin1(t.decl.name), QString::fromLatin1(a.name))
                         .arg(t.allocation.width()).arg(t.allocation.height()).arg(t.samples);
        return ok;
    }
    int next = colourCount;
    if (t.decl.depth) {
        if (k == next) {
            bool ok = make(t.depth, QRhiTexture::D32F, t.samples, QRhiTexture::RenderTarget, label + ".depth");
            if (ok && t.samples > 1 && t.decl.depthRead)
                ok = make(t.depthResolve, QRhiTexture::D32F, 1, QRhiTexture::RenderTarget, label + ".depth resolve");
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
        if (t.newLayout || !t.renderTarget) {
            QList<QRhiColorAttachment> attachments;
            for (int i = 0; i < colourCount; ++i) {
                QRhiColorAttachment attachment(t.colour[i].get());
                if (t.samples > 1)
                    attachment.setResolveTexture(t.resolve[i].get());
                attachments.append(attachment);
            }
            QRhiTextureRenderTargetDescription description;
            description.setColorAttachments(attachments.cbegin(), attachments.cend());
            if (t.depth) {
                description.setDepthTexture(t.depth.get());
                if (t.depthResolve)
                    description.setDepthResolveTexture(t.depthResolve.get());
            }
            QRhiTextureRenderTarget::Flags flags = QRhiTextureRenderTarget::PreserveColorContents;
            if (t.depth)
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
        if (!t.decl.capture) {
            // The last step: the counts follow the objects.
            qint64 bytes = 0;
            int textures = 0;
            for (int i = 0; i < colourCount; ++i) {
                bytes += textureBytes(t.colour[i].get()) + textureBytes(t.resolve[i].get());
                textures += (t.colour[i] ? 1 : 0) + (t.resolve[i] ? 1 : 0);
            }
            bytes += textureBytes(t.depth.get()) + textureBytes(t.depthResolve.get());
            textures += (t.depth ? 1 : 0) + (t.depthResolve ? 1 : 0);
            if (t.textures == 0 && t.bytes == 0)
                g_targets.fetchAndAddRelaxed(1);
            g_textures.fetchAndAddRelaxed(textures - t.textures);
            g_bytes.fetchAndAddRelaxed(bytes - t.bytes);
            t.textures = textures;
            t.bytes = bytes;
        }
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
    qint64 bytes = 0;
    int textures = 0;
    for (int i = 0; i < colourCount; ++i) {
        bytes += textureBytes(t.colour[i].get()) + textureBytes(t.resolve[i].get());
        textures += (t.colour[i] ? 1 : 0) + (t.resolve[i] ? 1 : 0);
    }
    bytes += textureBytes(t.depth.get()) + textureBytes(t.depthResolve.get()) + textureBytes(t.captureColour.get())
        + textureBytes(t.captureDepth.get());
    textures += (t.depth ? 1 : 0) + (t.depthResolve ? 1 : 0) + 2;
    if (t.textures == 0 && t.bytes == 0)
        g_targets.fetchAndAddRelaxed(1);
    g_textures.fetchAndAddRelaxed(textures - t.textures);
    g_bytes.fetchAndAddRelaxed(bytes - t.bytes);
    t.textures = textures;
    t.bytes = bytes;
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

QList<QRhiTexture *> SceneTargets::loadedColour(int index) const
{
    QList<QRhiTexture *> list;
    const Target *t = target(index);
    if (!t)
        return list;
    for (int i = 0; i < int(t->decl.colour.size()); ++i) {
        if (t->colour[i])
            list.append(t->colour[i].get());
    }
    return list;
}

int SceneTargets::liveObjects() const
{
    int objects = 0;
    for (int i = 0; i < m_count; ++i) {
        if (!m_targets[i])
            continue;
        objects += m_targets[i]->textures + (m_targets[i]->renderTarget ? 2 : 0)
            + (m_targets[i]->captureTarget ? 2 : 0);
    }
    return objects;
}

void SceneTargets::release()
{
    for (int i = 0; i < kMaxSceneTargets; ++i) {
        if (m_targets[i]) {
            releaseTarget(*m_targets[i]);
            m_targets[i].reset();
        }
    }
    m_count = 0;
    m_rhi = nullptr;
    ++m_layoutGeneration;
    ++m_objectGeneration;
}

std::shared_ptr<SceneReadback> SceneTargets::startReadback(QRhiResourceUpdateBatch *updates)
{
    pruneReadbacks();
    auto set = std::make_shared<SceneReadback>();
    SceneReadback *raw = set.get();
    const auto add = [&](const Target &t, const QString &name, QRhiTexture *texture, const QString &format) {
        if (!texture || raw->count >= int(sizeof(raw->results) / sizeof(raw->results[0])))
            return;
        SceneTargetPixels p;
        p.name = name;
        p.size = t.allocation;
        p.content = t.content;
        p.format = format;
        p.samples = t.samples;
        raw->pixels.append(p);
        ++raw->count;
    };
    for (int i = 0; i < m_count; ++i) {
        const Target &t = *m_targets[i];
        if (!t.ready())
            continue;
        const QString base = QString::fromLatin1(t.decl.name);
        for (int c = 0; c < int(t.decl.colour.size()); ++c) {
            add(t, base + QLatin1Char('.') + QString::fromLatin1(t.decl.colour.at(c).name), t.readable(c),
                targetFormatName(t.decl.colour.at(c).format));
        }
        if (t.decl.capture) {
            add(t, base + QStringLiteral(".capture_colour"), t.captureColour.get(),
                targetFormatName(t.decl.colour.at(0).format));
            add(t, base + QStringLiteral(".capture_depth"), t.captureDepth.get(), QStringLiteral("r32f"));
        }
    }
    if (raw->count == 0)
        return set;
    raw->pending.storeRelease(raw->count);
    g_readbacksPending.fetchAndAddRelaxed(1);
    // The textures, in the order the pixels were listed.
    int r = 0;
    for (int i = 0; i < m_count && r < raw->count; ++i) {
        const Target &t = *m_targets[i];
        if (!t.ready())
            continue;
        QList<QRhiTexture *> textures;
        for (int c = 0; c < int(t.decl.colour.size()); ++c) {
            if (t.readable(c))
                textures.append(t.readable(c));
        }
        if (t.decl.capture) {
            if (t.captureColour)
                textures.append(t.captureColour.get());
            if (t.captureDepth)
                textures.append(t.captureDepth.get());
        }
        for (QRhiTexture *texture : textures) {
            if (r >= raw->count)
                break;
            raw->results[r].completed = [raw]() {
                if (raw->pending.fetchAndAddOrdered(-1) == 1)
                    g_readbacksPending.fetchAndAddRelaxed(-1);
            };
            updates->readBackTexture(QRhiReadbackDescription(texture), &raw->results[r]);
            ++r;
        }
    }
    QMutexLocker lock(&readbackMutex());
    readbacksInFlight().append(set);
    return set;
}

QJsonObject SceneTargets::stateJson(QRhi *rhi) const
{
    QJsonObject o;
    QJsonArray supported;
    for (const int count : m_supported)
        supported.append(count);
    o.insert(QStringLiteral("supported_samples"), supported);
    QJsonArray removed;
    for (const int count : removedSampleCounts())
        removed.append(count);
    o.insert(QStringLiteral("removed_samples"), removed);
    o.insert(QStringLiteral("resolve_depth_stencil"), m_resolveDepth);
    o.insert(QStringLiteral("per_render_target_blending"),
             rhi ? rhi->isFeatureSupported(QRhi::PerRenderTargetBlending) : false);
    o.insert(QStringLiteral("multisample_texture"), rhi ? rhi->isFeatureSupported(QRhi::MultisampleTexture) : false);
    o.insert(QStringLiteral("backend"), rhi ? QString::fromLatin1(rhi->backendName()) : QString());
    o.insert(QStringLiteral("allocations"), double(m_allocations));
    o.insert(QStringLiteral("steps"), double(m_steps));
    o.insert(QStringLiteral("layout_generation"), double(m_layoutGeneration));
    o.insert(QStringLiteral("object_generation"), double(m_objectGeneration));
    QJsonArray targets;
    for (int i = 0; i < m_count; ++i) {
        const Target &t = *m_targets[i];
        QJsonObject e = t.decl.toJson();
        e.insert(QStringLiteral("content"), QJsonArray { t.content.width(), t.content.height() });
        e.insert(QStringLiteral("allocation"), QJsonArray { t.allocation.width(), t.allocation.height() });
        e.insert(QStringLiteral("requested_samples"), t.decl.samples);
        e.insert(QStringLiteral("effective_samples"), t.samples);
        e.insert(QStringLiteral("bytes"), double(t.bytes));
        e.insert(QStringLiteral("textures"), t.textures);
        e.insert(QStringLiteral("generation"), double(t.generation));
        e.insert(QStringLiteral("ready"), t.ready());
        e.insert(QStringLiteral("last_reason"), t.lastReason);
        if (rhi) {
            const QRect v = contentViewport(rhi->isYUpInFramebuffer(), t.allocation, t.content);
            e.insert(QStringLiteral("viewport"), QJsonArray { v.x(), v.y(), v.width(), v.height() });
        }
        targets.append(e);
    }
    o.insert(QStringLiteral("targets"), targets);
    return o;
}

} // namespace srpss_core
