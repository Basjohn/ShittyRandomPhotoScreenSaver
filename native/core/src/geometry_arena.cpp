// Geometry once per key (ABI 42, D3): geometry_arena.h has the contract.
#include "geometry_arena.h"

#include <QtCore/QAtomicInteger>

#include <cstring>

#ifdef Q_OS_WIN
#include <windows.h>
#else
#include <fcntl.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>
#endif

namespace srpss_core {

namespace {

QAtomicInteger<int> g_arenas { 0 };
QAtomicInteger<qint64> g_found { 0 };
QAtomicInteger<qint64> g_torn { 0 };

quint32 u32At(const unsigned char *p)
{
    quint32 v;
    std::memcpy(&v, p, 4);
    return v;
}

quint64 u64At(const unsigned char *p)
{
    quint64 v;
    std::memcpy(&v, p, 8);
    return v;
}

// The seqlock's loads: a compiler barrier between the sequence and the copy (x86-64 keeps load order; the packet
// reader's rule, D2 as built: no <atomic> in the module).
quint32 sequenceAt(const unsigned char *p)
{
    const quint32 v = *reinterpret_cast<const volatile quint32 *>(p);
#if defined(_MSC_VER)
    _ReadWriteBarrier();
#else
    __asm__ __volatile__("" ::: "memory");
#endif
    return v;
}

} // namespace

QString GeometryKey::text() const
{
    return QStringLiteral("(namespace %1, engine %2, activation %3, family %4, revision %5, capacity %6)")
        .arg(ns).arg(engine).arg(activation).arg(family).arg(revision).arg(capacity);
}

GeometryKey GeometryKey::fromWords(const quint32 *w)
{
    GeometryKey k;
    k.ns = quint64(w[0]) | (quint64(w[1]) << 32);
    k.engine = w[2];
    k.activation = w[3];
    k.family = w[4];
    k.revision = quint64(w[5]) | (quint64(w[6]) << 32);
    k.capacity = w[7];
    return k;
}

quint64 geometryBankOffset(quint32 family, quint32 bank, quint64 bankBytes)
{
    return quint64(kGeometryHeaderBytes)
        + (quint64(family) * kGeometryBanks + bank) * (quint64(kGeometryBankHeaderBytes) + bankBytes);
}

quint64 geometryArenaBytes(quint32 families, quint64 bankBytes)
{
    return geometryBankOffset(families, 0, bankBytes);
}

GeometryArena::~GeometryArena()
{
    close();
}

int GeometryArena::liveArenas()
{
    return g_arenas.loadRelaxed();
}

qint64 GeometryArena::readsFound()
{
    return g_found.loadRelaxed();
}

qint64 GeometryArena::readsTorn()
{
    return g_torn.loadRelaxed();
}

void GeometryArena::close()
{
    if (!m_view)
        return;
#ifdef Q_OS_WIN
    UnmapViewOfFile(m_view);
    if (m_mapping)
        CloseHandle(HANDLE(m_mapping));
#else
    munmap(const_cast<unsigned char *>(m_view), size_t(m_viewBytes));
#endif
    m_view = nullptr;
    m_mapping = nullptr;
    m_viewBytes = 0;
    m_families = 0;
    m_bankBytes = 0;
    m_name.clear();
    g_arenas.fetchAndAddRelaxed(-1);
}

bool GeometryArena::open(const QByteArray &name, QString *error)
{
    close();
    if (name.isEmpty()) {
        *error = QStringLiteral("a geometry arena needs a mapping name");
        return false;
    }
    const unsigned char *view = nullptr;
    quint64 viewBytes = 0;
#ifdef Q_OS_WIN
    const QString wide = QString::fromLatin1(name);
    HANDLE mapping = OpenFileMappingW(FILE_MAP_READ, FALSE, reinterpret_cast<LPCWSTR>(wide.utf16()));
    if (!mapping) {
        *error = QStringLiteral("geometry arena '%1' does not open (retired)").arg(wide);
        return false;
    }
    void *mapped = MapViewOfFile(mapping, FILE_MAP_READ, 0, 0, 0);
    MEMORY_BASIC_INFORMATION info = {};
    if (!mapped || VirtualQuery(mapped, &info, sizeof(info)) == 0) {
        if (mapped)
            UnmapViewOfFile(mapped);
        CloseHandle(mapping);
        *error = QStringLiteral("geometry arena '%1' could not be mapped").arg(wide);
        return false;
    }
    view = static_cast<const unsigned char *>(mapped);
    viewBytes = quint64(info.RegionSize);
    m_mapping = mapping;
#else
    const QByteArray path = name.startsWith('/') ? name : QByteArrayLiteral("/") + name;
    const int fd = shm_open(path.constData(), O_RDONLY, 0);
    struct stat st = {};
    if (fd < 0 || fstat(fd, &st) != 0 || st.st_size <= 0) {
        if (fd >= 0)
            ::close(fd);
        *error = QStringLiteral("geometry arena '%1' does not open (retired)").arg(QString::fromLatin1(name));
        return false;
    }
    void *mapped = mmap(nullptr, size_t(st.st_size), PROT_READ, MAP_SHARED, fd, 0);
    ::close(fd);
    if (mapped == MAP_FAILED) {
        *error = QStringLiteral("geometry arena '%1' could not be mapped").arg(QString::fromLatin1(name));
        return false;
    }
    view = static_cast<const unsigned char *>(mapped);
    viewBytes = quint64(st.st_size);
#endif
    m_view = view;
    m_viewBytes = viewBytes;
    m_name = name;
    g_arenas.fetchAndAddRelaxed(1);
    const quint32 families = viewBytes >= kGeometryHeaderBytes ? u32At(view + 8) : 0u;
    const quint64 bankBytes = viewBytes >= kGeometryHeaderBytes ? u64At(view + 16) : 0u;
    if (viewBytes < kGeometryHeaderBytes || u32At(view) != kGeometryArenaMagic
        || u32At(view + 4) != kGeometryArenaVersion || families == 0 || families > kMaxGeometryFamilies
        || u32At(view + 12) != kGeometryBanks || bankBytes == 0 || bankBytes > kMaxGeometryBankBytes
        || u32At(view + 24) != kGeometryHeaderBytes || u32At(view + 28) != kGeometryBankHeaderBytes
        || geometryArenaBytes(families, bankBytes) > viewBytes) {
        *error = QStringLiteral("geometry arena '%1' is not a version %2 arena of its own size (magic, banks, sizes)")
                     .arg(QString::fromLatin1(name)).arg(kGeometryArenaVersion);
        close();
        return false;
    }
    m_families = families;
    m_bankBytes = bankBytes;
    return true;
}

GeometryArena::Read GeometryArena::read(const GeometryKey &key, QByteArray *out, QString *error) const
{
    if (!m_view || key.family >= m_families)
        return Read::Absent;
    bool torn = false;
    for (quint32 bank = 0; bank < kGeometryBanks; ++bank) {
        const unsigned char *header = m_view + geometryBankOffset(key.family, bank, m_bankBytes);
        const quint32 before = sequenceAt(header);
        if (before & 1u) {
            torn = true;                      // being written (its key is not yet whole): maybe ours, read again later
            continue;
        }
        GeometryKey held;
        held.ns = u64At(header + 8);
        held.engine = u32At(header + 16);
        held.activation = u32At(header + 20);
        held.family = u32At(header + 24);
        held.capacity = u32At(header + 28);
        held.revision = u64At(header + 32);
        if (held != key)
            continue;
        const quint32 bytes = u32At(header + 4);
        if (quint64(bytes) > m_bankBytes || bytes % 4 != 0) {
            *error = QStringLiteral("geometry %1: %2 payload bytes past its bank's %3")
                         .arg(key.text()).arg(bytes).arg(m_bankBytes);
            return Read::Invalid;
        }
        out->resize(qsizetype(bytes));
        std::memcpy(out->data(), header + kGeometryBankHeaderBytes, bytes);
        if (sequenceAt(header) != before) {
            torn = true;                      // rewritten under the copy: never trusted
            continue;
        }
        g_found.fetchAndAddRelaxed(1);
        return Read::Found;
    }
    if (torn)
        g_torn.fetchAndAddRelaxed(1);
    return torn ? Read::Torn : Read::Absent;
}

} // namespace srpss_core
