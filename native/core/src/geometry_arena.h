// Geometry once per key (ABI 42, N5.6; decision D3 in Docs/Future_Work/Native_Core_P3_Decisions.md, decided 12 Nov):
// Extruded Bubble's drift families' geometry travels once per key in a geometry arena, never in the frame.
//
// The arena is a second mapping created and owned by the main process (the transport rule: a name the activation
// carries, opened by the reader), two banks per family. The worker writes a bank completely (its sequence odd while it
// writes, even and advanced when it is whole) before it publishes a frame naming the bank's key, and rewrites a bank only
// after the core acknowledged a frame naming a different key for that family (D3 point 2). The frame carries each live
// family's key (a record u32 array of kGeometryKeyWords) and the small per-frame state; the reader uploads a key it first
// sees (ModeStorage::syncGeometry, compute_passes.h) and never reads a bank again for a key it holds.
//
// Identity (D3 point 1): (worker namespace, engine generation, activation id, family, geometry revision, capacity). The
// namespace is the stream's mapping token, so a replacement worker or a remap is another namespace; a bare revision is
// never an identity (GeometryKey::operator== compares every word).
//
// Layout (little-endian, every offset fixed; rendering/native's writer is its Python twin):
//   arena header, 64 bytes: u32 magic 'SRGA', u32 version 1, u32 families, u32 banks (2), u64 bank bytes (a bank's
//   payload capacity), u32 header bytes (64), u32 bank header bytes (64), u64 the writer's key namespace (ABI 46:
//   core/visualizer_engine/geometry_arena.py's writer stamps it for the owner's projection; this reader ignores it),
//   24 bytes reserved;
//   then for family f, bank b (offset geometryBankOffset): a 64-byte bank header (u32 sequence, u32 payload bytes, the
//   key: u64 namespace, u32 engine, u32 activation, u32 family, u32 capacity, u64 revision; 24 bytes reserved) and
//   `bank bytes` of payload.
//
// The reader maps its own view by name and owns it (D1 point 1: the owner's close never unmaps memory being copied); a
// bank is read under its sequence (whole, or torn and read again at a later record), never trusted past the view.
// Render thread only, but the layout functions (any thread, GPU-free).
#pragma once

#include <QtCore/QByteArray>
#include <QtCore/QString>
#include <QtCore/QtGlobal>

namespace srpss_core {

constexpr quint32 kGeometryArenaMagic = 0x41475253u;   // "SRGA" little-endian
constexpr quint32 kGeometryArenaVersion = 1;
constexpr quint32 kGeometryHeaderBytes = 64;
constexpr quint32 kGeometryBankHeaderBytes = 64;
constexpr quint32 kGeometryBanks = 2;
constexpr quint32 kMaxGeometryFamilies = 8;
constexpr quint64 kMaxGeometryBankBytes = quint64(64) << 20;   // the specks at their maximum are 6.9 MB
constexpr int kGeometryKeyWords = 8;  // the record's key: ns lo, ns hi, engine, activation, family, revision lo, hi, capacity

struct GeometryKey
{
    quint64 ns = 0;
    quint32 engine = 0;
    quint32 activation = 0;
    quint32 family = 0;
    quint32 capacity = 0;
    quint64 revision = 0;

    bool valid() const { return ns != 0 || revision != 0 || capacity != 0; }
    bool operator==(const GeometryKey &o) const
    {
        return ns == o.ns && engine == o.engine && activation == o.activation && family == o.family
            && capacity == o.capacity && revision == o.revision;
    }
    bool operator!=(const GeometryKey &o) const { return !(*this == o); }
    QString text() const;
    // From the record's kGeometryKeyWords u32 words (D3 point 2).
    static GeometryKey fromWords(const quint32 *words);
};

// GPU-free: a bank's byte offset in an arena of `bankBytes` per bank (its header first), and an arena's total bytes.
quint64 geometryBankOffset(quint32 family, quint32 bank, quint64 bankBytes);
quint64 geometryArenaBytes(quint32 families, quint64 bankBytes);

class GeometryArena
{
public:
    enum class Read { Found = 0, Absent = 1, Torn = 2, Invalid = 3 };

    GeometryArena() = default;
    ~GeometryArena();
    GeometryArena(const GeometryArena &) = delete;
    GeometryArena &operator=(const GeometryArena &) = delete;

    // The arena named `name` mapped and validated (magic, version, sizes against the view); false with the reason (a
    // name that does not open is not an error loop: the caller reports it once and waits for a new name).
    bool open(const QByteArray &name, QString *error);
    bool isOpen() const { return m_view != nullptr; }
    const QByteArray &name() const { return m_name; }
    void close();

    // The payload of `key`'s family's bank holding `key`, copied whole under its sequence into `out`: Found; Absent (no
    // bank holds it yet: the worker has not written it, or wrote another key since), Torn (a bank holding it was being
    // written: read again at a later record) or Invalid (a size past the view or the bank: `error`).
    Read read(const GeometryKey &key, QByteArray *out, QString *error) const;

    // Process-wide counts (composite_live): arenas open, reads found, reads torn.
    static int liveArenas();
    static qint64 readsFound();
    static qint64 readsTorn();

private:
    QByteArray m_name;
    const unsigned char *m_view = nullptr;
    quint64 m_viewBytes = 0;
    quint32 m_families = 0;
    quint64 m_bankBytes = 0;
    void *m_mapping = nullptr;      // the platform's handle (Windows: the file mapping)
};

} // namespace srpss_core
