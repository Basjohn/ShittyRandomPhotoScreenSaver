// What every mode item shares (N2.9 round 2): stream_source.h has the contract.
#include "stream_source.h"

#include <cstring>

namespace srpss_core {

namespace fa = frame_abi;

StreamSource::StreamSource() = default;

StreamSource::~StreamSource()
{
    // The last owner: the node on the render thread, the item when no node ever read, or a harness wait's holder (no
    // read can be in progress on any of them).
    for (PacketReader *reader : m_retiring) {
        reader->release();
        delete reader;
    }
    m_retiring.clear();
    if (m_current) {
        m_current->retire();
        m_current->release();
        delete m_current;
        m_current = nullptr;
    }
}

bool StreamSource::acceptStream(const PacketReaderConfig &config, QString *error)
{
    Q_UNUSED(config);
    Q_UNUSED(error);
    return true;
}

bool StreamSource::bind(const QString &mappingName, const PacketReaderConfig &config, QString *error)
{
    PacketReader *reader = PacketReader::open(mappingName, config, error);
    if (!reader)
        return false;
    QMutexLocker lock(&m_mutex);
    if (!acceptStream(config, error)) {
        reader->retire(); // never read: no copy can be in progress on it
        reader->release();
        delete reader;
        return false;
    }
    if (m_current) {
        m_current->retire(); // D1: Retiring at once; the render thread releases it at its next sync
        m_retiring.append(m_current);
        ++m_retired;
    }
    {
        // Its state at open, taken before the render thread can read it (nothing else touches it yet).
        const QJsonObject opened = reader->stateJson();
        QMutexLocker report(&m_reportMutex);
        m_readerState = opened;
    }
    m_current = reader;
    m_mapping = mappingName;
    ++m_binds;
    return true;
}

void StreamSource::unbind()
{
    QMutexLocker lock(&m_mutex);
    if (!m_current)
        return;
    m_current->retire();
    m_retiring.append(m_current);
    m_current = nullptr;
    m_mapping.clear();
    ++m_retired;
}

void StreamSource::retireCurrent()
{
    QMutexLocker lock(&m_mutex);
    if (m_current)
        m_current->retire();
}

void StreamSource::dropRetainedFrame()
{
    QMutexLocker lock(&m_mutex);
    if (m_current)
        m_current->dropRetainedFrame();
}

bool StreamSource::readHead(SlotHead *out)
{
    QMutexLocker lock(&m_mutex); // the current reader is never released while it is current
    return m_current && m_current->readHead(out);
}

bool StreamSource::waitPaused(int timeoutMs)
{
    // The harness's pause_in_copy hook. The reader is waited on without the lock; while any wait is in progress the
    // retire job keeps every retired reader alive (audit 14 Nov, L9), and the caller's shared owner keeps the source.
    PacketReader *reader = nullptr;
    {
        QMutexLocker lock(&m_mutex);
        reader = m_current;
        if (!reader)
            return false;
        ++m_waiters;
    }
    const bool paused = reader->waitPaused(timeoutMs);
    QMutexLocker lock(&m_mutex);
    --m_waiters;
    return paused;
}

void StreamSource::resume()
{
    QMutexLocker lock(&m_mutex);
    if (m_current)
        m_current->resume();
    for (PacketReader *reader : m_retiring)
        reader->resume();
}

void StreamSource::releaseRetired()
{
    QList<PacketReader *> retiring;
    {
        QMutexLocker lock(&m_mutex);
        if (m_waiters > 0)
            return; // a harness wait holds a reader: released at the first sync after it returns
        retiring.swap(m_retiring);
    }
    for (PacketReader *reader : retiring) {
        reader->release(); // the consumer's thread: its retained frame and its pin go; the last pin unmaps
        const QJsonObject state = reader->stateJson();
        delete reader;
        QMutexLocker lock(&m_mutex);
        ++m_released;
        m_lastReader = state;
    }
}

bool StreamSource::syncStream()
{
    m_syncProbe.hit(); // D5.4: the read's thread, and whether it held a Python thread state
    releaseRetired();  // the render-thread retire job
    PacketReader *current = nullptr;
    {
        QMutexLocker lock(&m_mutex);
        current = m_current;
    }
    bool accepted = false;
    bool rejected = false;
    bool changed = false;
    QString result = QStringLiteral("unbound");
    QJsonObject readerState;
    bool snapshot = false;
    if (current) {
        const ReadResult read = current->read(); // the accept edge (D2), on the render thread
        result = QString::fromLatin1(readResultName(read));
        SlotHead head;
        const QByteArray *retained = nullptr;
        const bool holds = current->retained(&head, &retained);
        // render_contract.snapshot_is_render_admissible for a mode whose first visible reactive output must come from
        // its tracked source (mode_capabilities.requires_authoritative_first_source): a frame that is not a present
        // frame, or a playing one whose reactive source is not its own activation's, is not drawn and the last admitted
        // frame stays (the Python node's rule). The bits are the slot head's (packet_abi FLAG_*).
        const bool admissible = holds && (head.flags & fa::kFlagPresentFrame)
            && (!(head.flags & fa::kFlagPlaying) || (head.flags & fa::kFlagSourceCurrent));
        if (read == ReadResult::Accepted && holds && !admissible) {
            rejected = true;
        } else if (read == ReadResult::Accepted && holds) {
            if (m_record.size() != retained->size())
                m_record.resize(retained->size());
            std::memcpy(m_record.data(), retained->constData(), size_t(retained->size()));
            m_hasFrame = true;
            accepted = true;
            changed = true;
        } else if (m_hasFrame && !holds) {
            m_hasFrame = false; // dropped (R-184's edge), or another stream bound: nothing of the old one is drawn
            changed = true;
        }
        // The reader's state, taken on its own thread when the read did something (audit L9), never per idle sync.
        if (read != ReadResult::Nothing) {
            readerState = current->stateJson();
            snapshot = true;
        }
    } else if (m_hasFrame) {
        m_hasFrame = false;
        changed = true;
    }
    QMutexLocker lock(&m_reportMutex);
    ++m_syncs;
    if (accepted)
        ++m_accepted;
    if (rejected)
        ++m_admissionRejected;
    m_lastResult = result;
    m_reportedFrame = m_hasFrame;
    if (snapshot)
        m_readerState = readerState;
    else if (!current)
        m_readerState = QJsonObject();
    return changed;
}

void StreamSource::noteRecorded(bool drawn, const QString &reason, const QJsonObject &facts)
{
    QMutexLocker lock(&m_reportMutex);
    ++m_records;
    if (drawn) {
        ++m_draws;
        m_refusing = false; // a run of refusals ends with a drawn frame
    }
    m_lastReason = reason;
    m_lastFacts = facts;
}

void StreamSource::noteRefused(const QString &reason)
{
    QMutexLocker lock(&m_reportMutex);
    ++m_refusedFrames;
    if (!m_refusing) {
        m_refusing = true;
        m_lastRefusal = reason; // once per run of refusals
    }
}

void StreamSource::noteFailure(const QString &reason, qint64 failures)
{
    QMutexLocker lock(&m_reportMutex);
    ++m_records;
    m_contentFailures = failures;
    m_contentFailure = reason;
    m_lastReason = QStringLiteral("the content failed: %1").arg(reason);
    QJsonObject facts;
    facts.insert(QStringLiteral("content_failed"), true);
    facts.insert(QStringLiteral("content_failures"), double(failures));
    m_lastFacts = facts;
}

QJsonObject StreamSource::stateJson() const
{
    QJsonObject o;
    {
        QMutexLocker lock(&m_mutex);
        o.insert(QStringLiteral("mapping"), m_mapping);
        o.insert(QStringLiteral("binds"), double(m_binds));
        o.insert(QStringLiteral("retired"), double(m_retired));
        o.insert(QStringLiteral("released"), double(m_released));
        o.insert(QStringLiteral("retiring"), int(m_retiring.size()));
        o.insert(QStringLiteral("bound"), m_current != nullptr);
        o.insert(QStringLiteral("last_released_reader"), m_lastReader.isEmpty() ? QJsonValue() : QJsonValue(m_lastReader));
        stateInto(o);
    }
    QMutexLocker lock(&m_reportMutex);
    o.insert(QStringLiteral("reader"), m_readerState.isEmpty() ? QJsonValue() : QJsonValue(m_readerState));
    o.insert(QStringLiteral("syncs"), double(m_syncs));
    o.insert(QStringLiteral("accepted"), double(m_accepted));
    o.insert(QStringLiteral("admission_rejected"), double(m_admissionRejected));
    o.insert(QStringLiteral("syncs_probed"), double(m_syncProbe.calls.loadRelaxed()));
    o.insert(QStringLiteral("syncs_on_gui_thread"), double(m_syncProbe.callsOnGuiThread.loadRelaxed()));
    o.insert(QStringLiteral("syncs_with_python_thread_state"),
             double(m_syncProbe.callsWithPythonThreadState.loadRelaxed()));
    o.insert(QStringLiteral("has_frame"), m_reportedFrame);
    o.insert(QStringLiteral("last_read"), m_lastResult);
    o.insert(QStringLiteral("records"), double(m_records));
    o.insert(QStringLiteral("draws"), double(m_draws));
    o.insert(QStringLiteral("refused_frames"), double(m_refusedFrames));
    o.insert(QStringLiteral("last_refusal"), m_lastRefusal);
    o.insert(QStringLiteral("content_failures"), double(m_contentFailures));
    o.insert(QStringLiteral("content_failure"), m_contentFailure);
    o.insert(QStringLiteral("last_reason"), m_lastReason);
    o.insert(QStringLiteral("last_facts"), m_lastFacts);
    return o;
}

// ------------------------------------------------------------------------------------------------ the latch

bool ContentLatch::mayBuild(const QRhi *rhi, const QRhiRenderPassDescriptor *pass, quint64 program,
                            quint64 inputs) const
{
    return !(m_latched && m_rhi == rhi && m_pass == pass && m_program == program && m_inputs == inputs);
}

qint64 ContentLatch::failed(const QRhi *rhi, const QRhiRenderPassDescriptor *pass, quint64 program, quint64 inputs,
                            const QString &error)
{
    m_latched = true;
    m_rhi = rhi;
    m_pass = pass;
    m_program = program;
    m_inputs = inputs;
    m_error = error;
    return ++m_failures;
}

} // namespace srpss_core
