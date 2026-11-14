// What every mode item of the core shares (N2.9 round 2, audit 14 Nov N29 M2): the frame stream an item draws from
// (StreamSource) and its content's failure latch (ContentLatch). The Spectrum item (spectrum.h) and the generic mode
// item (mode_content.h) are built on them, so a fix to the stream's lifetime, its admission or the latch lands once.
//
// StreamSource, the stream (Spectrum's rules since N2.5, now the one implementation):
// - bound by mapping name on the GUI thread; the packet reader is opened there and read only at the item's sync on the
//   render thread (the accept edge, D2);
// - retiring a stream (a rebind, an unbind, the item's destruction) stores Retiring at once and never waits (D1); the
//   render-thread retire job releases it at the next sync, or when Qt deletes the item's node (the render thread, the
//   QRhi alive); a source whose node never existed releases on its own last owner's thread (no read can be in progress);
// - the admission (the Python node's render_contract.snapshot_is_render_admissible): a frame is drawn only when its slot
//   is a present frame and, while playing, its reactive source is its own activation's; otherwise the last admitted frame
//   stays;
// - the drop edge (R-184) is the reader's own (dropRetainedFrame, applied by the next read);
// - an unbind keeps the last admitted frame (audit N29 round 2, L3): the card fades out over it, never over a cleared
//   target; a new stream's first sync clears it (nothing of the old stream is drawn under the new one);
// - the report: the render thread copies the reader's counters into it when a read changed something (audit L9: the GUI
//   thread never reads the reader's consumer-thread state; round 2 L2: a plain copy, the JSON is built on the GUI thread
//   when the state is asked for), with the content's records, draws, refusals and failures;
// - the status (round 2, M4 and M5): the content's health as four numbers the route reads at its sync without JSON:
//   draws, failures, whether the content is failing now (a build failed and nothing has recorded since) and the run of
//   refused frames since the last drawn one.
//
// ContentLatch, the content's failure latch (N2.5 audit M2, N2.9 audit M2 and L10): a content whose QRhi objects cannot
// be built records the failure once and builds nothing again for the same key: the QRhi, the target (its generation,
// never its address: round 2 L4), the program and the settings. The card is not in the key (no pipeline depends on it,
// so a fade's every step does not retry a build). Any of them changing re-arms it; a latch held for the same key retries
// once per kRetryEvery held records, at most kRetries times, so a transient failure recovers with no changed input and a
// lasting one costs nothing per frame. While latched the surface keeps what it holds (cleared once when it holds nothing
// of the content's, round 2 M4) and reports no error per frame; the state and the status say why.
//
// A refused frame (audit N29 M4): a frame the content cannot pack (a NaN in a record, a value with no defined
// conversion) never clears the card. The target keeps the last drawn frame, the refusal is counted and its reason
// reported once per run of refusals, and the next good frame draws.
#pragma once

#include "packet_reader.h"
#include "thread_probe.h"

#include <QtCore/QByteArray>
#include <QtCore/QJsonObject>
#include <QtCore/QList>
#include <QtCore/QMutex>
#include <QtCore/QString>

class QRhi;

namespace srpss_core {

// The content's health for the route (round 2, M4 and M5): read at the route's sync, no JSON.
struct ContentStatus
{
    qint64 draws = 0;       // records that drew a frame
    qint64 failures = 0;    // build failures
    qint64 refusedRun = 0;  // frames refused since the last drawn one
    bool failing = false;   // a build failed and nothing has recorded since
};

class StreamSource
{
public:
    StreamSource();
    virtual ~StreamSource();
    StreamSource(const StreamSource &) = delete;
    StreamSource &operator=(const StreamSource &) = delete;

    // GUI thread. A new stream (the previous one retires); false with `error` when the mapping is not a frame buffer
    // this build reads (a name that does not open gives a retired reader, D1 rule 1) or acceptStream refuses it.
    bool bind(const QString &mappingName, const PacketReaderConfig &config, QString *error);
    void unbind();                                    // the current stream retires (never waits)
    void retireCurrent();                             // any thread: Retiring at once (D1); unbind releases it
    void dropRetainedFrame();                         // R-184's edge, applied by the next read
    bool readHead(SlotHead *out);                     // D2's head read of the current stream (consumes nothing)
    // The D1 hook (the pause_in_copy control only): wait until the current reader is paused inside a copy; resume it.
    // The caller holds a shared owner of the source for the wait (audit L8).
    bool waitPaused(int timeoutMs);
    void resume();

    // Render thread: every retired reader released (the retire job; also the node's destruction).
    void releaseRetired();

    // Render thread, while recording. `streamBound`: the last sync had a stream (an unbound source keeps its last frame
    // for the card's fade, L3).
    bool hasFrame() const { return m_hasFrame; }
    bool streamBound() const { return m_streamBound; }
    const QByteArray &frameRecord() const { return m_record; }

    // The content's report (render thread writes, any thread reads). `refused`: a frame the content could not pack (the
    // target kept); its reason is reported once per run of refusals.
    void noteRecorded(bool drawn, const QString &reason, const QJsonObject &facts);
    void noteRefused(const QString &reason);
    void noteFailure(const QString &reason, qint64 failures);

    QJsonObject stateJson() const;
    ContentStatus status() const;           // any thread

protected:
    // GUI thread, under m_mutex: a subclass's refusal of a stream (the generic mode's schema against its program).
    virtual bool acceptStream(const PacketReaderConfig &config, QString *error);
    // GUI thread, under m_mutex: the current stream was unbound (the generic mode forgets its schema, so a program
    // given before the next bind is not checked against the stream that went: N4.a).
    virtual void streamUnbound() {}
    // Render thread, at the item's sync after the subclass took its inputs: the retired readers released, the current
    // stream read at its accept edge and admitted. True when the drawn frame changed (accepted, dropped, unbound).
    bool syncStream();
    // Under m_mutex: the subclass's part of the state.
    virtual void stateInto(QJsonObject &o) const = 0;

    mutable QMutex m_mutex;                 // guards the stream members and the subclass's GUI-side inputs
    PacketReader *m_current = nullptr;      // read only on the render thread; replaced on the GUI thread
    QList<PacketReader *> m_retiring;       // retired, waiting for the render thread's release
    int m_waiters = 0;                      // waitPaused calls in progress: no retired reader is deleted under them
    QString m_mapping;
    qint64 m_binds = 0;
    qint64 m_retired = 0;
    qint64 m_released = 0;
    QJsonObject m_lastReader;               // the last released reader's state

    ThreadProbe m_syncProbe;                // D5.4 at the accept edge: the threads the syncs (the reads) ran on

private:
    // Render thread.
    QByteArray m_record;
    bool m_hasFrame = false;
    bool m_streamBound = false;

    mutable QMutex m_reportMutex;           // guards the report
    qint64 m_syncs = 0;
    qint64 m_accepted = 0;
    qint64 m_admissionRejected = 0;         // accepted frames the node's admission rule does not draw
    bool m_reportedFrame = false;
    qint64 m_records = 0;
    qint64 m_draws = 0;
    qint64 m_refusedFrames = 0;
    bool m_refusing = false;
    qint64 m_refusedRun = 0;                // refused since the last drawn frame (M5)
    bool m_failing = false;                 // a build failed and nothing has recorded since (M4)
    QString m_lastRefusal;
    qint64 m_contentFailures = 0;
    QString m_contentFailure;
    QString m_lastReason;
    QJsonObject m_lastFacts;
    QString m_lastResult;
    PacketReaderSnapshot m_readerSnapshot;  // the render thread's copy of the current reader's counters (L9, L2)
    const PacketReader *m_snapshotOf = nullptr; // the reader it is of (compared only, never dereferenced)
};

// A latch key (L4): the target by its generation, never its address.
struct LatchKey
{
    const QRhi *rhi = nullptr;
    quint64 target = 0;     // ColorTarget::generation
    quint64 program = 0;
    quint64 settings = 0;
    bool operator==(const LatchKey &o) const
    {
        return rhi == o.rhi && target == o.target && program == o.program && settings == o.settings;
    }
    bool operator!=(const LatchKey &o) const { return !(*this == o); }
};

class ContentLatch
{
public:
    static constexpr int kRetryEvery = 240; // held records between the retries of one key (about 4 s at 60 frames)
    static constexpr int kRetries = 3;      // retries of one key

    // keepsTarget's question, once per record: whether the content may build now. Counts a held record; true for a
    // due retry, which then holds until the build's result.
    bool admit(const LatchKey &key);
    // ensure's question (no count): the same answer admit gave this record.
    bool mayBuild(const LatchKey &key) const { return !m_latched || key != m_key || m_retryGranted; }
    // A failed build at this key: latched until it changes. Returns the failure count.
    qint64 failed(const LatchKey &key, const QString &error);
    void succeeded()
    {
        m_latched = false;
        m_retryGranted = false;
        m_retries = 0;
    }
    bool latched() const { return m_latched; }
    const QString &error() const { return m_error; }
    qint64 failures() const { return m_failures; }
    int retries() const { return m_retries; }

private:
    bool m_latched = false;
    bool m_retryGranted = false;
    LatchKey m_key;
    int m_held = 0;
    int m_retries = 0;
    QString m_error;
    qint64 m_failures = 0;
};

} // namespace srpss_core
