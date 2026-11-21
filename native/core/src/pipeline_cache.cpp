// The core's own pipeline cache file (N3.6): pipeline_cache.h has the contract.
#include "pipeline_cache.h"

#include "abi.h"

#include <QtCore/QAtomicInteger>
#include <QtCore/QCryptographicHash>
#include <QtCore/QDir>
#include <QtCore/QFile>
#include <QtCore/QFileInfo>
#include <QtCore/QJsonArray>
#include <QtCore/QJsonDocument>
#include <QtCore/QList>
#include <QtCore/QMutex>
#include <QtCore/QSaveFile>
#include <QtCore/QStandardPaths>
#include <QtCore/QSysInfo>
#include <QtCore/QThread>
#include <QtCore/QtEndian>

#include <algorithm>
#include <cstring>

namespace srpss_core {

namespace {

const char kMagic[4] = { 'S', 'R', 'P', 'C' };
constexpr quint32 kFormat = 1;
constexpr int kUuidBytes = 16;    // VK_UUID_SIZE
constexpr int kBackendBytes = 16; // the backend's name, zero padded
// magic, format, abi, driver version, vendor, device (6 x 4), the UUID, the backend, the section count (4), the
// payload's size (8), its MD5 (16).
constexpr int kHeaderBytes = 24 + kUuidBytes + kBackendBytes + 4 + 8 + 16;
constexpr int kUuidAt = 24;
constexpr int kBackendAt = kUuidAt + kUuidBytes;
constexpr int kCountAt = kBackendAt + kBackendBytes;
constexpr int kSizeAt = kCountAt + 4;
constexpr int kHashAt = kSizeAt + 8;

QMutex &directoryMutex()
{
    static QMutex mutex;
    return mutex;
}

QString &directoryOverride()
{
    static QString directory;
    return directory;
}

void putU32(QByteArray *out, quint32 value)
{
    char bytes[4];
    qToLittleEndian(value, bytes);
    out->append(bytes, 4);
}

void putU64(QByteArray *out, quint64 value)
{
    char bytes[8];
    qToLittleEndian(value, bytes);
    out->append(bytes, 8);
}

quint32 u32At(const QByteArray &in, qsizetype at)
{
    return qFromLittleEndian<quint32>(in.constData() + at);
}

quint64 u64At(const QByteArray &in, qsizetype at)
{
    return qFromLittleEndian<quint64>(in.constData() + at);
}

QByteArray fixedBytes(const QByteArray &bytes, int size)
{
    QByteArray out = bytes.left(size);
    if (out.size() < size)
        out.append(QByteArray(size - out.size(), '\0'));
    return out;
}

} // namespace

QByteArray encodePipelineCache(const PipelineCacheIdentity &identity, const PipelineCacheSections &sections, quint32 abi)
{
    QList<quint32> tags = sections.keys();
    std::sort(tags.begin(), tags.end());
    QByteArray payload;
    for (const quint32 tag : tags) {
        const QByteArray bytes = sections.value(tag);
        putU32(&payload, tag);
        putU64(&payload, quint64(bytes.size()));
        payload.append(bytes);
    }
    QByteArray out;
    out.reserve(kHeaderBytes + payload.size());
    out.append(kMagic, 4);
    putU32(&out, kFormat);
    putU32(&out, abi);
    putU32(&out, identity.driverVersion);
    putU32(&out, identity.vendorId);
    putU32(&out, identity.deviceId);
    out.append(fixedBytes(identity.cacheUuid, kUuidBytes));
    out.append(fixedBytes(identity.backend.toLatin1(), kBackendBytes));
    putU32(&out, quint32(tags.size()));
    putU64(&out, quint64(payload.size()));
    out.append(QCryptographicHash::hash(payload, QCryptographicHash::Md5));
    out.append(payload);
    return out;
}

QString decodePipelineCache(const QByteArray &file, const PipelineCacheIdentity &identity,
                            PipelineCacheSections *sections)
{
    sections->clear();
    if (file.size() < kHeaderBytes)
        return QStringLiteral("short");
    if (std::memcmp(file.constData(), kMagic, 4) != 0)
        return QStringLiteral("magic");
    if (u32At(file, 4) != kFormat)
        return QStringLiteral("format");
    if (u32At(file, 8) != quint32(SRPSS_NATIVE_CORE_ABI))
        return QStringLiteral("abi");
    if (file.mid(kBackendAt, kBackendBytes) != fixedBytes(identity.backend.toLatin1(), kBackendBytes))
        return QStringLiteral("backend");
    if (u32At(file, 12) != identity.driverVersion)
        return QStringLiteral("driver_version");
    if (u32At(file, 16) != identity.vendorId)
        return QStringLiteral("vendor");
    if (u32At(file, 20) != identity.deviceId)
        return QStringLiteral("device");
    if (file.mid(kUuidAt, kUuidBytes) != fixedBytes(identity.cacheUuid, kUuidBytes))
        return QStringLiteral("cache_uuid");
    const quint32 count = u32At(file, kCountAt);
    const quint64 size = u64At(file, kSizeAt);
    if (size != quint64(file.size() - kHeaderBytes))
        return QStringLiteral("size");
    const QByteArray payload = file.mid(kHeaderBytes);
    if (QCryptographicHash::hash(payload, QCryptographicHash::Md5) != file.mid(kHashAt, 16))
        return QStringLiteral("checksum");
    PipelineCacheSections parsed;
    qsizetype at = 0;
    for (quint32 i = 0; i < count; ++i) {
        if (payload.size() - at < 12)
            return QStringLiteral("sections");
        const quint32 tag = u32At(payload, at);
        const quint64 bytes = u64At(payload, at + 4);
        at += 12;
        if (bytes > quint64(payload.size() - at) || parsed.contains(tag))
            return QStringLiteral("sections");
        parsed.insert(tag, payload.mid(at, qsizetype(bytes)));
        at += qsizetype(bytes);
    }
    if (at != payload.size())
        return QStringLiteral("sections");
    *sections = parsed;
    return QString();
}

QString pipelineCacheDirectory()
{
    {
        QMutexLocker lock(&directoryMutex());
        if (!directoryOverride().isEmpty())
            return directoryOverride();
    }
    // Qt Quick's own directory (qsgrhisupport.cpp: <CacheLocation>/qtpipelinecache-<buildAbi>), so both files sit together.
    return QDir(QStandardPaths::writableLocation(QStandardPaths::CacheLocation))
        .filePath(QStringLiteral("qtpipelinecache-") + QSysInfo::buildAbi());
}

void setPipelineCacheDirectory(const QString &directory)
{
    QMutexLocker lock(&directoryMutex());
    directoryOverride() = directory;
}

QString pipelineCacheFile(const QString &directory, const QString &backend)
{
    return QDir(directory).filePath(QStringLiteral("srpss_core_") + backend);
}

PipelineCacheSections loadPipelineCache(const QString &path, const PipelineCacheIdentity &identity, QJsonObject *report)
{
    report->insert(QStringLiteral("file"), path);
    QFile file(path);
    if (!file.exists()) {
        report->insert(QStringLiteral("result"), QStringLiteral("absent"));
        return {};
    }
    if (!file.open(QIODevice::ReadOnly)) {
        report->insert(QStringLiteral("result"), QStringLiteral("unreadable"));
        return {};
    }
    const QByteArray bytes = file.readAll();
    file.close();
    report->insert(QStringLiteral("bytes"), double(bytes.size()));
    PipelineCacheSections sections;
    const QString reason = decodePipelineCache(bytes, identity, &sections);
    report->insert(QStringLiteral("result"), reason.isEmpty() ? QStringLiteral("accepted")
                                                              : QStringLiteral("rejected: ") + reason);
    return sections;
}

bool savePipelineCache(const QString &path, const PipelineCacheIdentity &identity, const PipelineCacheSections &sections,
                       QJsonObject *report)
{
    report->insert(QStringLiteral("file"), path);
    if (!QDir().mkpath(QFileInfo(path).absolutePath())) {
        report->insert(QStringLiteral("save_failed"), QStringLiteral("the directory could not be made"));
        return false;
    }
    const QByteArray bytes = encodePipelineCache(identity, sections, quint32(SRPSS_NATIVE_CORE_ABI));
    QSaveFile file(path); // a temporary file beside it, renamed over it at commit
    if (!file.open(QIODevice::WriteOnly)) {
        report->insert(QStringLiteral("save_failed"), file.errorString());
        return false;
    }
    if (file.write(bytes) != qint64(bytes.size())) {
        report->insert(QStringLiteral("save_failed"), file.errorString());
        file.cancelWriting();
        return false;
    }
    if (!file.commit()) {
        report->insert(QStringLiteral("save_failed"), file.errorString());
        return false;
    }
    report->insert(QStringLiteral("saved_bytes"), double(bytes.size()));
    return true;
}

// ------------------------------------------------------------------------------------------------- the self-test

namespace {

// One writer of the self-test's concurrency case: `rounds` saves of its own sections.
class WriterThread final : public QThread
{
public:
    WriterThread(const QString &path, const PipelineCacheIdentity &identity, const PipelineCacheSections &sections,
                 int rounds)
        : m_path(path), m_identity(identity), m_sections(sections), m_rounds(rounds)
    {
    }

    QAtomicInteger<int> saved { 0 };
    QAtomicInteger<int> failed { 0 };

protected:
    void run() override
    {
        for (int i = 0; i < m_rounds; ++i) {
            QJsonObject report;
            if (savePipelineCache(m_path, m_identity, m_sections, &report))
                saved.fetchAndAddRelaxed(1);
            else
                failed.fetchAndAddRelaxed(1);
        }
    }

private:
    QString m_path;
    PipelineCacheIdentity m_identity;
    PipelineCacheSections m_sections;
    int m_rounds;
};

QByteArray withByte(const QByteArray &bytes, qsizetype at, char value)
{
    QByteArray out = bytes;
    out[at] = value;
    return out;
}

} // namespace

QByteArray pipelineCacheSelfTestJson(const QString &directory)
{
    QJsonObject o;
    PipelineCacheIdentity id;
    id.backend = QStringLiteral("vulkan");
    id.driverVersion = 0x12345678u;
    id.vendorId = 0x10deu;
    id.deviceId = 0x2684u;
    for (int i = 0; i < kUuidBytes; ++i)
        id.cacheUuid.append(char(0x40 + i));
    PipelineCacheSections a;
    a.insert(kPipelineCacheJobQrhi, QByteArray(4096, 'a') + QByteArrayLiteral("end of a"));
    PipelineCacheSections b;
    b.insert(kPipelineCacheJobQrhi, QByteArray(9000, 'b') + QByteArrayLiteral("end of b"));
    b.insert(7, QByteArrayLiteral("a second section"));
    const QByteArray good = encodePipelineCache(id, a, quint32(SRPSS_NATIVE_CORE_ABI));

    PipelineCacheSections decoded;
    const QString accepted = decodePipelineCache(good, id, &decoded);
    o.insert(QStringLiteral("accepted"), accepted.isEmpty() && decoded == a);
    PipelineCacheSections decodedB;
    o.insert(QStringLiteral("two_sections_accepted"),
             decodePipelineCache(encodePipelineCache(id, b, quint32(SRPSS_NATIVE_CORE_ABI)), id, &decodedB).isEmpty()
                 && decodedB == b);
    o.insert(QStringLiteral("header_bytes"), kHeaderBytes);

    // Every refusal: the case's file or identity differs from the good one in the one fact named.
    QJsonObject refusals;
    QJsonObject refusalsLeftSections;
    auto refuse = [&](const char *name, const QByteArray &file, const PipelineCacheIdentity &as) {
        PipelineCacheSections left;
        left.insert(99, QByteArrayLiteral("stale"));
        refusals.insert(QLatin1String(name), decodePipelineCache(file, as, &left));
        refusalsLeftSections.insert(QLatin1String(name), int(left.size()));
    };
    PipelineCacheIdentity other = id;
    other.driverVersion += 1;
    refuse("driver_version", good, other);
    other = id;
    other.vendorId += 1;
    refuse("vendor", good, other);
    other = id;
    other.deviceId += 1;
    refuse("device", good, other);
    other = id;
    other.cacheUuid[3] = char(other.cacheUuid.at(3) ^ 0x01);
    refuse("cache_uuid", good, other);
    other = id;
    other.backend = QStringLiteral("opengl");
    refuse("backend", good, other);
    refuse("abi", encodePipelineCache(id, a, quint32(SRPSS_NATIVE_CORE_ABI) + 1), id);
    refuse("short", good.left(kHeaderBytes - 1), id);
    refuse("size", good.chopped(1), id);
    refuse("checksum", withByte(good, good.size() - 1, char(good.at(good.size() - 1) ^ 0x20)), id);
    refuse("magic", withByte(good, 0, 'X'), id);
    refuse("format", withByte(good, 4, char(kFormat + 1)), id);
    refuse("sections", withByte(good, kCountAt, char(u32At(good, kCountAt) + 1)), id);
    o.insert(QStringLiteral("refusals"), refusals);
    o.insert(QStringLiteral("refusals_left_sections"), refusalsLeftSections);

    // The file: absent, saved, loaded back, refused for another device (the silent recompile).
    const QString path = pipelineCacheFile(directory, id.backend);
    QFile::remove(path);
    QJsonObject absent;
    loadPipelineCache(path, id, &absent);
    o.insert(QStringLiteral("absent"), absent);
    QJsonObject saved;
    o.insert(QStringLiteral("save_committed"), savePipelineCache(path, id, a, &saved));
    o.insert(QStringLiteral("saved"), saved);
    QJsonObject loaded;
    o.insert(QStringLiteral("round_trip_equal"), loadPipelineCache(path, id, &loaded) == a);
    o.insert(QStringLiteral("loaded"), loaded);
    other = id;
    other.deviceId += 1;
    QJsonObject otherDevice;
    o.insert(QStringLiteral("other_device_sections"), int(loadPipelineCache(path, other, &otherDevice).size()));
    o.insert(QStringLiteral("other_device"), otherDevice);

    // Two writers replacing the file while this thread reads it: every read is one writer's whole file or a read that
    // lost the race to open (never a torn file).
    constexpr int kRounds = 60;
    constexpr int kMinReads = 200;
    WriterThread writerA(path, id, a, kRounds);
    WriterThread writerB(path, id, b, kRounds);
    writerA.start();
    writerB.start();
    int reads = 0;
    int readA = 0;
    int readB = 0;
    int torn = 0;
    int unopened = 0;
    QJsonArray tornResults;
    while ((writerA.isRunning() || writerB.isRunning() || reads < kMinReads) && reads < 200000) {
        QJsonObject report;
        const PipelineCacheSections read = loadPipelineCache(path, id, &report);
        ++reads;
        const QString result = report.value(QStringLiteral("result")).toString();
        if (result == QLatin1String("accepted")) {
            if (read == a)
                ++readA;
            else if (read == b)
                ++readB;
            else
                ++torn;
        } else if (result == QLatin1String("unreadable") || result == QLatin1String("absent")) {
            ++unopened;
        } else {
            ++torn;
            if (tornResults.size() < 8)
                tornResults.append(result);
        }
    }
    writerA.wait();
    writerB.wait();
    QJsonObject concurrency;
    concurrency.insert(QStringLiteral("reads"), reads);
    concurrency.insert(QStringLiteral("read_a"), readA);
    concurrency.insert(QStringLiteral("read_b"), readB);
    concurrency.insert(QStringLiteral("torn"), torn);
    concurrency.insert(QStringLiteral("torn_results"), tornResults);
    concurrency.insert(QStringLiteral("unopened"), unopened);
    concurrency.insert(QStringLiteral("writer_a_saved"), writerA.saved.loadRelaxed());
    concurrency.insert(QStringLiteral("writer_a_failed"), writerA.failed.loadRelaxed());
    concurrency.insert(QStringLiteral("writer_b_saved"), writerB.saved.loadRelaxed());
    concurrency.insert(QStringLiteral("writer_b_failed"), writerB.failed.loadRelaxed());
    QJsonObject last;
    const PipelineCacheSections finalSections = loadPipelineCache(path, id, &last);
    concurrency.insert(QStringLiteral("final_is_one_writers"), finalSections == a || finalSections == b);
    concurrency.insert(QStringLiteral("final"), last);
    // Leftover temporary files of a writer (QSaveFile removes its own on every path).
    const QStringList left = QDir(directory).entryList(QDir::Files);
    concurrency.insert(QStringLiteral("files_left"), QJsonArray::fromStringList(left));
    o.insert(QStringLiteral("concurrency"), concurrency);
    QFile::remove(path);
    return QJsonDocument(o).toJson(QJsonDocument::Compact);
}

} // namespace srpss_core
