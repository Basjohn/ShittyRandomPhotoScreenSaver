// The packet reader (N2.3): packet_reader.h has the contract.
#include "packet_reader.h"

#include <QtCore/QJsonArray>
#include <QtCore/QJsonDocument>
#include <QtCore/QJsonParseError>
#include <QtCore/QStringList>

#include <cmath>
#include <cstddef>
#include <cstring>

#include <intrin.h>

#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>

#if !defined(_M_X64)
#error "the packet reader's seqlock loads rely on x86-64 load ordering (the module's one target)"
#endif

namespace srpss_core {

namespace fa = frame_abi;

namespace {

QAtomicInt g_readers { 0 };
QAtomicInt g_views { 0 };

static_assert(sizeof(SlotHead) == fa::kSlotPayloadOffset, "the slot head is the payload's offset long");
static_assert(offsetof(SlotHead, sequence) == fa::kSlotSequenceBegin, "slot head layout");
static_assert(offsetof(SlotHead, payloadBytes) == fa::kSlotPayloadBytes, "slot head layout");
static_assert(offsetof(SlotHead, payloadSchema) == fa::kSlotPayloadSchema, "slot head layout");
static_assert(offsetof(SlotHead, logicalTimestamp) == fa::kSlotLogicalTimestamp, "slot head layout");
static_assert(offsetof(SlotHead, sourceTimestamp) == fa::kSlotSourceTimestamp, "slot head layout");
static_assert(offsetof(SlotHead, flags) == fa::kSlotFlags, "slot head layout");
static_assert(offsetof(SlotHead, protectedEdgeMask) == fa::kSlotProtectedEdgeMask, "slot head layout");
static_assert(offsetof(SlotHead, runtimeGeneration) == fa::kSlotRuntimeGeneration, "slot head layout");
static_assert(offsetof(SlotHead, engineGeneration) == fa::kSlotEngineGeneration, "slot head layout");
static_assert(offsetof(SlotHead, activationId) == fa::kSlotActivationId, "slot head layout");
static_assert(offsetof(SlotHead, modeCode) == fa::kSlotModeCode, "slot head layout");
static_assert(offsetof(SlotHead, publishNs) == fa::kSlotPublishNs, "slot head layout");

// A compiler barrier: no load or store is moved across it. On x86-64 the hardware never reorders a load with an earlier
// load, nor a store with an earlier store, so with it an aligned load is an acquire load and an aligned store a release
// store (packet_abi.py's ordering: "the P3 C reader acquire-loads latest_sequence and sequence_end, copies, then loads
// sequence_begin after a load fence"). MSVC's intrinsic, not the standard library's fence (the module's runtime rule
// keeps <atomic> out of the core's sources).
inline void barrier()
{
    _ReadWriteBarrier();
}

inline quint64 loadAcquire64(const uchar *p)
{
    const quint64 value = static_cast<quint64>(__iso_volatile_load64(reinterpret_cast<const volatile __int64 *>(p)));
    barrier();
    return value;
}

inline void storeRelease64(uchar *p, quint64 value)
{
    barrier();
    __iso_volatile_store64(reinterpret_cast<volatile __int64 *>(p), static_cast<__int64>(value));
}

inline quint32 read32(const uchar *p)
{
    quint32 value;
    std::memcpy(&value, p, sizeof value);
    return value;
}

inline quint16 read16(const uchar *p)
{
    quint16 value;
    std::memcpy(&value, p, sizeof value);
    return value;
}

bool knownMode(quint32 code)
{
    for (const fa::ModeCode &mode : fa::kModeCodes) {
        if (mode.code == code)
            return true;
    }
    return false;
}

// native_schema.parse_native_schema_id: (mode code, version) of a well-formed native id.
bool parseNative(quint32 schema, quint32 *mode, quint32 *version)
{
    if ((schema & ~0x00FF01FFu) || !(schema & fa::kNativeBase))
        return false;
    *mode = schema & 0xFFu;
    *version = (schema >> 16) & 0xFFu;
    return *mode != 0 && *version != 0;
}

QString hexText(quint32 value)
{
    return QStringLiteral("0x%1").arg(value, 0, 16);
}

} // namespace

const char *readResultName(ReadResult result)
{
    switch (result) {
    case ReadResult::Nothing: return "nothing";
    case ReadResult::Accepted: return "accepted";
    case ReadResult::Torn: return "torn";
    case ReadResult::Stale: return "stale";
    case ReadResult::Foreign: return "foreign";
    case ReadResult::Refused: return "refused";
    case ReadResult::Failed: return "failed";
    case ReadResult::Retiring: return "retiring";
    case ReadResult::Retired: return "retired";
    }
    return "unknown";
}

// ------------------------------------------------------------------------------------------------ the config

bool PacketReaderConfig::fromJson(const QByteArray &json, PacketReaderConfig *out, QString *error)
{
    QJsonParseError parse;
    const QJsonDocument document = QJsonDocument::fromJson(json, &parse);
    if (!document.isObject()) {
        *error = QStringLiteral("the packet reader's configuration is a JSON object");
        return false;
    }
    const QJsonObject o = document.object();
    const QStringList known = { QStringLiteral("expect"), QStringLiteral("controls") };
    for (auto it = o.begin(); it != o.end(); ++it) {
        if (!known.contains(it.key())) {
            *error = QStringLiteral("unknown packet reader option '%1' (%2)").arg(it.key(),
                                                                                   known.join(QStringLiteral(", ")));
            return false;
        }
    }
    PacketReaderConfig c;
    const QJsonValue expect = o.value(QStringLiteral("expect"));
    if (!expect.isUndefined() && !expect.isNull()) {
        if (!expect.isObject()) {
            *error = QStringLiteral("'expect' is an object of runtime_generation, engine_generation, activation_id and "
                                    "mode_code (u32 as stored)");
            return false;
        }
        const QJsonObject e = expect.toObject();
        const char *names[] = { "runtime_generation", "engine_generation", "activation_id", "mode_code" };
        quint32 *targets[] = { &c.runtimeGeneration, &c.engineGeneration, &c.activationId, &c.modeCode };
        if (e.size() != 4) {
            *error = QStringLiteral("'expect' names exactly runtime_generation, engine_generation, activation_id and "
                                    "mode_code");
            return false;
        }
        for (int i = 0; i < 4; ++i) {
            const QJsonValue value = e.value(QLatin1String(names[i]));
            const double number = value.toDouble(-1.0);
            if (!value.isDouble() || number < 0.0 || number > 4294967295.0 || number != std::floor(number)) {
                *error = QStringLiteral("'expect'.%1 is a u32").arg(QLatin1String(names[i]));
                return false;
            }
            *targets[i] = quint32(number);
        }
        c.expectIdentity = true;
    }
    const QJsonValue controls = o.value(QStringLiteral("controls"));
    if (!controls.isUndefined() && !controls.isNull()) {
        if (!controls.isArray()) {
            *error = QStringLiteral("'controls' is a list of negative-control names");
            return false;
        }
        for (const QJsonValue &value : controls.toArray()) {
            const QString name = value.toString();
            if (name == QLatin1String("skip_head_check"))
                c.skipHeadCheck = true;
            else if (name == QLatin1String("skip_seqlock"))
                c.skipSeqlock = true;
            else if (name == QLatin1String("accept_unordered"))
                c.acceptUnordered = true;
            else if (name == QLatin1String("acknowledge_refused"))
                c.acknowledgeRefused = true;
            else if (name == QLatin1String("head_resets_watermark"))
                c.headResetsWatermark = true;
            else if (name == QLatin1String("skip_identity"))
                c.skipIdentity = true;
            else if (name == QLatin1String("pause_in_copy"))
                c.pauseInCopy = true;
            else {
                *error = QStringLiteral("unknown packet reader control '%1'").arg(name);
                return false;
            }
        }
    }
    *out = c;
    return true;
}

QJsonObject PacketReaderConfig::toJson() const
{
    QJsonObject o;
    if (expectIdentity) {
        QJsonObject e;
        e.insert(QStringLiteral("runtime_generation"), double(runtimeGeneration));
        e.insert(QStringLiteral("engine_generation"), double(engineGeneration));
        e.insert(QStringLiteral("activation_id"), double(activationId));
        e.insert(QStringLiteral("mode_code"), double(modeCode));
        o.insert(QStringLiteral("expect"), e);
    } else {
        o.insert(QStringLiteral("expect"), QJsonValue());
    }
    QJsonArray controls;
    if (skipHeadCheck)
        controls.append(QStringLiteral("skip_head_check"));
    if (skipSeqlock)
        controls.append(QStringLiteral("skip_seqlock"));
    if (acceptUnordered)
        controls.append(QStringLiteral("accept_unordered"));
    if (acknowledgeRefused)
        controls.append(QStringLiteral("acknowledge_refused"));
    if (headResetsWatermark)
        controls.append(QStringLiteral("head_resets_watermark"));
    if (skipIdentity)
        controls.append(QStringLiteral("skip_identity"));
    if (pauseInCopy)
        controls.append(QStringLiteral("pause_in_copy"));
    o.insert(QStringLiteral("controls"), controls);
    return o;
}

// ------------------------------------------------------------------------------------------------ the reader

PacketReader::PacketReader(const QString &name, const PacketReaderConfig &config)
    : m_name(name), m_config(config)
{
    g_readers.ref();
}

PacketReader::~PacketReader()
{
    if (m_ownPin) {
        m_ownPin = false;
        unpin();
    }
    unmap(); // a read still in progress cannot exist here: the Python face destroys a reader only from its own thread
    g_readers.deref();
}

const fa::Schema *PacketReader::schema(quint32 schemaId)
{
    for (const fa::Schema &schema : fa::kSchemas) {
        if (schema.schemaId == schemaId)
            return &schema;
    }
    return nullptr;
}

PacketReader *PacketReader::open(const QString &name, const PacketReaderConfig &config, QString *error)
{
    const QLatin1String prefix(fa::kMappingPrefix);
    if (!name.startsWith(prefix) || name.size() > 240) {
        *error = QStringLiteral("'%1' is not a frame mapping's name (they start with %2)").arg(name, prefix);
        return nullptr;
    }
    auto *reader = new PacketReader(name, config);
    HANDLE mapping = OpenFileMappingW(FILE_MAP_READ | FILE_MAP_WRITE, FALSE, reinterpret_cast<LPCWSTR>(name.utf16()));
    if (!mapping) {
        // D1 rule 1: a name that no longer opens is a retired stream, never an error loop.
        const DWORD code = GetLastError();
        reader->m_openError = QStringLiteral("the mapping %1 does not open (Windows error %2): the stream is retired")
                                  .arg(name)
                                  .arg(qulonglong(code));
        reader->m_state.storeRelease(Retired);
        reader->m_unmapped.storeRelease(1);
        return reader;
    }
    void *view = MapViewOfFile(mapping, FILE_MAP_READ | FILE_MAP_WRITE, 0, 0, 0);
    const DWORD mapCode = view ? 0 : GetLastError();
    CloseHandle(mapping); // the view keeps the section alive (D1 rule 1)
    if (!view) {
        *error = QStringLiteral("the mapping %1 opened but could not be mapped (Windows error %2)")
                     .arg(name)
                     .arg(qulonglong(mapCode));
        reader->m_unmapped.storeRelease(1);
        delete reader;
        return nullptr;
    }
    MEMORY_BASIC_INFORMATION info;
    std::memset(&info, 0, sizeof info);
    VirtualQuery(view, &info, sizeof info);
    reader->m_base = static_cast<uchar *>(view);
    reader->m_viewBytes = quint64(info.RegionSize);
    g_views.ref();
    reader->m_pins.storeRelease(1);
    reader->m_ownPin = true;
    QString problem;
    if (!reader->validate(&problem)) {
        *error = problem;
        delete reader;
        return nullptr;
    }
    reader->m_staging.reserve(qsizetype(reader->m_capacity));
    reader->m_frame.reserve(qsizetype(reader->m_capacity));
    return reader;
}

// packet_abi.py's _validate.
bool PacketReader::validate(QString *problem)
{
    if (m_viewBytes < fa::kHeaderBytes) {
        *problem = QStringLiteral("mapping is smaller than the frame header");
        return false;
    }
    if (std::memcmp(m_base + fa::kHeaderMagic, fa::kMagic, 4) != 0) {
        *problem = QStringLiteral("not a visualizer frame mapping");
        return false;
    }
    const quint16 version = read16(m_base + fa::kHeaderAbiVersion);
    const quint16 headerBytes = read16(m_base + fa::kHeaderHeaderBytes);
    const quint32 slotCount = read32(m_base + fa::kHeaderSlotCount);
    if (version != fa::kAbiVersion || headerBytes != fa::kHeaderBytes || slotCount != fa::kSlotCount) {
        *problem = QStringLiteral("frame ABI %1 (header %2, %3 slots) is not this build's %4")
                       .arg(version)
                       .arg(headerBytes)
                       .arg(slotCount)
                       .arg(fa::kAbiVersion);
        return false;
    }
    const quint32 slotBytes = read32(m_base + fa::kHeaderSlotBytes);
    if (slotBytes < fa::kSlotOverhead + 16 || slotBytes % 16) {
        *problem = QStringLiteral("slot_bytes must be a multiple of 16 with room for a payload");
        return false;
    }
    if (m_viewBytes < quint64(fa::kHeaderBytes) + quint64(fa::kSlotCount) * slotBytes) {
        *problem = QStringLiteral("mapping is smaller than its declared slots");
        return false;
    }
    m_slotBytes = slotBytes;
    m_capacity = slotBytes - fa::kSlotOverhead;
    for (int i = 0; i < 3; ++i)
        m_headerIdentity[i] = read32(m_base + fa::kHeaderRuntimeGeneration + 4 * i);
    m_headerIdentity[3] = read32(m_base + fa::kHeaderModeCode);
    return true;
}

bool PacketReader::pin()
{
    for (;;) {
        const int pins = m_pins.loadAcquire();
        if (pins <= 0)
            return false;
        if (m_pins.testAndSetAcquire(pins, pins + 1))
            return true;
    }
}

void PacketReader::unpin()
{
    if (!m_pins.deref()) // the last pin: nobody reads the view any more
        unmap();
}

void PacketReader::unmap()
{
    if (m_base && m_unmapped.testAndSetOrdered(0, 1)) {
        UnmapViewOfFile(m_base);
        g_views.deref();
    }
}

void PacketReader::retire()
{
    m_state.testAndSetOrdered(Open, Retiring);
}

void PacketReader::release()
{
    if (m_state.fetchAndStoreOrdered(Retired) == Retired)
        return;
    m_hasFrame = false;
    m_frameSchema = nullptr;
    m_staging = QByteArray();
    m_frame = QByteArray();
    if (m_ownPin) {
        m_ownPin = false;
        unpin();
    }
}

void PacketReader::dropRetainedFrame()
{
    m_dropRequested.storeRelease(1);
}

bool PacketReader::waitPaused(int timeoutMs)
{
    return m_paused.tryAcquire(1, timeoutMs);
}

void PacketReader::resume()
{
    m_resume.release();
}

void PacketReader::applyDrop()
{
    if (!m_dropRequested.fetchAndStoreAcquire(0))
        return;
    if (m_hasFrame)
        m_droppedThrough = qMax(m_droppedThrough, m_frameHead.sequence);
    m_droppedThrough = qMax(m_droppedThrough, m_accepted);
    m_hasFrame = false;
    m_frameSchema = nullptr;
    ++m_dropsApplied;
}

int PacketReader::wholeSlot(quint64 latest, SlotHead *head, bool *ambiguous, bool strict) const
{
    *ambiguous = false;
    int found = -1;
    for (quint32 slot = 0; slot < fa::kSlotCount; ++slot) {
        const uchar *base = m_base + fa::kHeaderBytes + quint64(slot) * m_slotBytes;
        if (loadAcquire64(base + fa::kSlotSequenceBegin) != latest)
            continue;
        if (found >= 0) {
            *ambiguous = true; // two slots claim one sequence: no correct writer does that
            return -1;
        }
        found = int(slot);
    }
    if (found < 0)
        return -1;
    const uchar *base = m_base + fa::kHeaderBytes + quint64(found) * m_slotBytes;
    // Seqlock read order: sequence_end (stored last) first, then the head, then sequence_begin (stored first) again.
    const quint64 end = loadAcquire64(base + m_slotBytes - 8);
    if (strict && end != latest)
        return -1;
    std::memcpy(head, base, sizeof(SlotHead));
    barrier();
    const quint64 begin = loadAcquire64(base + fa::kSlotSequenceBegin);
    if (strict && (head->sequence != latest || begin != latest))
        return -1;
    return found;
}

bool PacketReader::admit(const SlotHead &head, QString *cause, QString *reason) const
{
    // native_schema.admit_slot_head(accept="native"), check for check.
    const quint32 schemaId = head.payloadSchema;
    const quint32 mode = head.modeCode;
    if (mode && !knownMode(mode)) {
        *cause = QStringLiteral("mode");
        *reason = QStringLiteral("unknown mode code %1 in the slot head").arg(mode);
        return false;
    }
    if (schemaId == fa::kCodecSchema) {
        *cause = QStringLiteral("schema");
        *reason = QStringLiteral("a tagged-codec payload on a native stream");
        return false;
    }
    quint32 schemaMode = 0;
    quint32 version = 0;
    if (!parseNative(schemaId, &schemaMode, &version)) {
        *cause = QStringLiteral("schema");
        *reason = QStringLiteral("unknown payload schema %1").arg(hexText(schemaId));
        return false;
    }
    if (!knownMode(schemaMode)) {
        *cause = QStringLiteral("mode");
        *reason = QStringLiteral("schema %1 names unknown mode code %2").arg(hexText(schemaId)).arg(schemaMode);
        return false;
    }
    if (schemaMode != mode) {
        *cause = QStringLiteral("mode");
        *reason = QStringLiteral("schema %1 is for mode code %2, the slot's is %3").arg(hexText(schemaId)).arg(schemaMode).arg(mode);
        return false;
    }
    const fa::Schema *found = schema(schemaId);
    if (!found) {
        quint32 newest = 0;
        for (const fa::Schema &known : fa::kSchemas) {
            if (known.modeCode == schemaMode)
                newest = qMax(newest, known.version);
        }
        if (!newest) {
            *cause = QStringLiteral("schema");
            *reason = QStringLiteral("mode code %1 has no native schema in this build").arg(schemaMode);
        } else {
            *cause = QStringLiteral("version");
            *reason = QStringLiteral("schema %1: version %2 is %3 this build's newest %4")
                          .arg(hexText(schemaId))
                          .arg(version)
                          .arg(version > newest ? QStringLiteral("newer than") : QStringLiteral("not one of"))
                          .arg(newest);
        }
        return false;
    }
    if (head.payloadBytes != found->recordBytes) {
        *cause = QStringLiteral("size");
        *reason = QStringLiteral("schema %1: a %2-byte payload disagrees with its %3-byte layout")
                      .arg(hexText(schemaId))
                      .arg(head.payloadBytes)
                      .arg(found->recordBytes);
        return false;
    }
    if (found->recordBytes > m_capacity) {
        *cause = QStringLiteral("size");
        *reason = QStringLiteral("schema %1: its %2-byte record does not fit the %3-byte slot")
                      .arg(hexText(schemaId))
                      .arg(found->recordBytes)
                      .arg(m_capacity);
        return false;
    }
    return true;
}

bool PacketReader::checkRecord(const fa::Schema *schema, const QByteArray &record, QString *cause,
                               QString *reason) const
{
    // spectrum_native_schema.decode: native_schema.validate_record_head, then the record's own range rules in order.
    if (quint32(record.size()) != schema->recordBytes) {
        *cause = QStringLiteral("size");
        *reason = QStringLiteral("a %1-byte payload is not the %2-byte record of schema %3")
                      .arg(record.size())
                      .arg(schema->recordBytes)
                      .arg(hexText(schema->schemaId));
        return false;
    }
    const uchar *data = reinterpret_cast<const uchar *>(record.constData());
    const quint32 head = read32(data);
    const quint32 size = read32(data + 4);
    if (head != schema->schemaId || size != schema->recordBytes) {
        *cause = QStringLiteral("schema");
        *reason = QStringLiteral("the record names schema %1 (%2 bytes), not %3 (%4 bytes)")
                      .arg(hexText(head))
                      .arg(size)
                      .arg(hexText(schema->schemaId))
                      .arg(schema->recordBytes);
        return false;
    }
    for (quint32 i = 0; i < schema->checkCount; ++i) {
        const fa::Field &field = schema->fields[schema->checkOrder[i]];
        const quint32 value = read32(data + field.offset);
        bool bad = false;
        switch (field.check) {
        case fa::FieldCheck::AtMost:
            bad = value > field.limit;
            break;
        case fa::FieldCheck::Boolean:
            bad = value > 1;
            break;
        case fa::FieldCheck::Enum:
            bad = value != fa::kEnumOutside && value >= field.limit;
            break;
        case fa::FieldCheck::None:
            break;
        }
        if (bad) {
            *cause = QStringLiteral("record");
            *reason = QStringLiteral("%1 is %2, outside its rule").arg(QLatin1String(field.name)).arg(value);
            return false;
        }
    }
    return true;
}

ReadResult PacketReader::refuse(quint64 sequence, const QString &cause, const QString &reason)
{
    ++m_refused;
    if (!m_failed) {
        m_failed = true;
        m_refusalCause = cause;
        m_refusalReason = reason;
        m_refusalSequence = sequence;
    }
    if (m_config.acknowledgeRefused) { // the negative control only: a refused slot is never acknowledged
        storeRelease64(m_base + fa::kHeaderConsumedSequence, sequence);
        ++m_acknowledged;
        m_acknowledgedSequence = sequence;
    }
    return ReadResult::Refused;
}

ReadResult PacketReader::read()
{
    ++m_reads;
    const int state = m_state.loadAcquire();
    if (state == Retired)
        return ReadResult::Retired;
    if (state == Retiring) {
        ++m_readsWhileRetiring;
        return ReadResult::Retiring;
    }
    applyDrop();
    if (m_failed)
        return ReadResult::Failed;
    if (!pin())
        return ReadResult::Retired;
    struct Guard
    {
        PacketReader *self;
        ~Guard() { self->unpin(); }
    } guard { this };

    const quint64 latest = loadAcquire64(m_base + fa::kHeaderLatestSequence);
    const quint64 watermark = qMax(m_accepted, m_droppedThrough);
    if (m_config.acceptUnordered) {
        if (latest == m_accepted || latest == 0)
            return ReadResult::Nothing;
    } else if (latest <= watermark) {
        if (latest < watermark) {
            if (latest != m_lastStale) {
                ++m_stale;
                m_lastStale = latest;
            }
            return ReadResult::Stale;
        }
        return ReadResult::Nothing;
    }
    const bool strict = !m_config.skipSeqlock;
    if (strict && (latest % 2)) {
        ++m_torn;
        return ReadResult::Torn;
    }
    SlotHead head;
    bool ambiguous = false;
    const int slot = wholeSlot(latest, &head, &ambiguous, strict);
    if (slot < 0) {
        if (ambiguous)
            ++m_ambiguous;
        ++m_torn;
        return ReadResult::Torn;
    }
    const fa::Schema *found = nullptr;
    QString cause;
    QString reason;
    if (!m_config.skipHeadCheck) {
        // The head alone, whole under its seqlock, decides admission before any payload byte is copied.
        if (!admit(head, &cause, &reason))
            return refuse(latest, cause, reason);
        found = schema(head.payloadSchema);
    }
    if (m_config.expectIdentity && !m_config.skipIdentity
        && (head.runtimeGeneration != m_config.runtimeGeneration || head.engineGeneration != m_config.engineGeneration
            || head.activationId != m_config.activationId || head.modeCode != m_config.modeCode)) {
        if (latest != m_lastForeign) {
            ++m_foreign;
            m_lastForeign = latest;
        }
        return ReadResult::Foreign;
    }
    if (m_state.loadAcquire() != Open) { // D1: no copy starts once the stream is retiring
        ++m_readsWhileRetiring;
        return ReadResult::Retiring;
    }
    const uchar *base = m_base + fa::kHeaderBytes + quint64(slot) * m_slotBytes;
    const quint32 size = qMin(head.payloadBytes, m_capacity);
    m_staging.resize(qsizetype(size));
    m_copiesStarted.ref();
    if (m_config.pauseInCopy) {
        // The D1 hook (harness only): paused inside the copy, its view pinned, until another thread resumes it (after
        // closing and unlinking the mapping, or retiring the stream).
        m_pauses.ref();
        m_paused.release();
        m_resume.acquire();
    }
    std::memcpy(m_staging.data(), base + fa::kSlotPayloadOffset, size);
    barrier();
    const quint64 begin = loadAcquire64(base + fa::kSlotSequenceBegin);
    m_copiesFinished.ref();
    if (strict && (begin != latest || head.payloadBytes > m_capacity)) {
        ++m_torn; // a write began during the copy: the previous frame stays
        return ReadResult::Torn;
    }
    if (m_state.loadAcquire() != Open) {
        // D1: the stream began retiring during the copy; the copy completed against the pinned view, and nothing of it
        // is presented or acknowledged.
        ++m_readsWhileRetiring;
        ++m_copiesDiscarded;
        return ReadResult::Retiring;
    }
    if (found && !checkRecord(found, m_staging, &cause, &reason))
        return refuse(latest, cause, reason);

    // The accept edge (D2): the frame is retained with its protected-edge mask, then acknowledged.
    m_accepted = latest;
    m_staging.swap(m_frame);
    m_frameHead = head;
    m_frameSchema = found;
    m_hasFrame = true;
    ++m_acceptedCount;
    m_lastAccepted.storeRelease(latest);
    storeRelease64(m_base + fa::kHeaderConsumedSequence, latest);
    ++m_acknowledged;
    m_acknowledgedSequence = latest;
    return ReadResult::Accepted;
}

bool PacketReader::readHead(SlotHead *out)
{
    if (m_state.loadAcquire() == Retired || !pin())
        return false;
    struct Guard
    {
        PacketReader *self;
        ~Guard() { self->unpin(); }
    } guard { this };
    m_headReads.ref();
    if (m_config.headResetsWatermark) { // the negative control only (consumer state from the caller's thread)
        m_accepted = 0;
        m_droppedThrough = 0;
    }
    const quint64 latest = loadAcquire64(m_base + fa::kHeaderLatestSequence);
    if (latest == 0 || (latest % 2))
        return false;
    bool ambiguous = false;
    return wholeSlot(latest, out, &ambiguous, true) >= 0;
}

bool PacketReader::retained(SlotHead *head, const QByteArray **record) const
{
    if (!m_hasFrame)
        return false;
    *head = m_frameHead;
    *record = &m_frame;
    return true;
}

QJsonObject PacketReader::stateJson() const
{
    static const char *states[] = { "open", "retiring", "retired" };
    QJsonObject o;
    o.insert(QStringLiteral("mapping"), m_name);
    o.insert(QStringLiteral("state"), QLatin1String(states[qBound(0, m_state.loadAcquire(), 2)]));
    o.insert(QStringLiteral("open_error"), m_openError.isEmpty() ? QJsonValue() : QJsonValue(m_openError));
    o.insert(QStringLiteral("config"), m_config.toJson());
    o.insert(QStringLiteral("mapped"), m_unmapped.loadAcquire() == 0 && m_base != nullptr);
    o.insert(QStringLiteral("slot_bytes"), double(m_slotBytes));
    o.insert(QStringLiteral("capacity"), double(m_capacity));
    QJsonArray identity;
    for (quint32 value : m_headerIdentity)
        identity.append(double(value));
    o.insert(QStringLiteral("header_identity"), identity);
    o.insert(QStringLiteral("reads"), double(m_reads));
    o.insert(QStringLiteral("accepted"), double(m_acceptedCount));
    o.insert(QStringLiteral("accepted_sequence"), double(m_accepted));
    o.insert(QStringLiteral("acknowledged"), double(m_acknowledged));
    o.insert(QStringLiteral("acknowledged_sequence"), double(m_acknowledgedSequence));
    o.insert(QStringLiteral("torn_reads"), double(m_torn));
    o.insert(QStringLiteral("ambiguous_slots"), double(m_ambiguous));
    o.insert(QStringLiteral("stale_reads"), double(m_stale));
    o.insert(QStringLiteral("foreign_reads"), double(m_foreign));
    o.insert(QStringLiteral("refused"), double(m_refused));
    o.insert(QStringLiteral("failed"), m_failed);
    if (m_failed) {
        QJsonObject refusal;
        refusal.insert(QStringLiteral("cause"), m_refusalCause);
        refusal.insert(QStringLiteral("reason"), m_refusalReason);
        refusal.insert(QStringLiteral("sequence"), double(m_refusalSequence));
        o.insert(QStringLiteral("refusal"), refusal);
    } else {
        o.insert(QStringLiteral("refusal"), QJsonValue());
    }
    o.insert(QStringLiteral("retained"), m_hasFrame);
    o.insert(QStringLiteral("retained_sequence"), m_hasFrame ? double(m_frameHead.sequence) : 0.0);
    o.insert(QStringLiteral("dropped_through"), double(m_droppedThrough));
    o.insert(QStringLiteral("drops_applied"), double(m_dropsApplied));
    o.insert(QStringLiteral("head_reads"), double(m_headReads.loadAcquire()));
    o.insert(QStringLiteral("reads_while_retiring"), double(m_readsWhileRetiring));
    // D1's per-stream liveness block.
    o.insert(QStringLiteral("copies_started"), double(m_copiesStarted.loadAcquire()));
    o.insert(QStringLiteral("copies_finished"), double(m_copiesFinished.loadAcquire()));
    o.insert(QStringLiteral("last_accepted_sequence"), double(m_lastAccepted.loadAcquire()));
    o.insert(QStringLiteral("copies_discarded"), double(m_copiesDiscarded));
    o.insert(QStringLiteral("pauses"), double(m_pauses.loadAcquire()));
    return o;
}

QJsonObject PacketReader::liveJson()
{
    QJsonObject o;
    o.insert(QStringLiteral("readers"), g_readers.loadAcquire());
    o.insert(QStringLiteral("views"), g_views.loadAcquire());
    return o;
}

} // namespace srpss_core
