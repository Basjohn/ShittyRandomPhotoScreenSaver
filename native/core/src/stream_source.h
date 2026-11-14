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
// - the report: the render thread snapshots the reader's state into it when a read changed something (audit L9: the GUI
//   thread never reads the reader's consumer-thread state), with the content's records, draws, refusals and failures.
//
// ContentLatch, the content's failure latch (N2.5 audit M2, N2.9 audit M2 and L10): a content whose QRhi objects cannot
// be built records the failure once and builds nothing again for the same key (the QRhi, the target's pass, the program
// and the item's inputs: the card and the settings). Any of them changing re-arms it, so a transient failure is retried
// at the next changed input, never every frame. While latched the surface keeps what it holds and reports no error per
// frame; the state says why.
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
class QRhiRenderPassDescriptor;

namespace srpss_core {

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

    // Render thread, while recording.
    bool hasFrame() const { return m_hasFrame; }
    const QByteArray &frameRecord() const { return m_record; }

    // The content's report (render thread writes, any thread reads). `refused`: a frame the content could not pack (the
    // target kept); its reason is reported once per run of refusals.
    void noteRecorded(bool drawn, const QString &reason, const QJsonObject &facts);
    void noteRefused(const QString &reason);
    void noteFailure(const QString &reason, qint64 failures);

    QJsonObject stateJson() const;

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

    mutable QMutex m_reportMutex;           // guards the report
    qint64 m_syncs = 0;
    qint64 m_accepted = 0;
    qint64 m_admissionRejected = 0;         // accepted frames the node's admission rule does not draw
    bool m_reportedFrame = false;
    qint64 m_records = 0;
    qint64 m_draws = 0;
    qint64 m_refusedFrames = 0;
    bool m_refusing = false;
    QString m_lastRefusal;
    qint64 m_contentFailures = 0;
    QString m_contentFailure;
    QString m_lastReason;
    QJsonObject m_lastFacts;
    QString m_lastResult;
    QJsonObject m_readerState;              // the render thread's snapshot of the current reader (audit L9)
};

class ContentLatch
{
public:
    // Whether the content may build for this key now (false while latched for the same key).
    bool mayBuild(const QRhi *rhi, const QRhiRenderPassDescriptor *pass, quint64 program, quint64 inputs) const;
    // A failed build at this key: latched until one of them changes. Returns the failure count.
    qint64 failed(const QRhi *rhi, const QRhiRenderPassDescriptor *pass, quint64 program, quint64 inputs,
                  const QString &error);
    void succeeded() { m_latched = false; }
    bool latched() const { return m_latched; }
    const QString &error() const { return m_error; }
    qint64 failures() const { return m_failures; }

private:
    bool m_latched = false;
    const QRhi *m_rhi = nullptr;
    const QRhiRenderPassDescriptor *m_pass = nullptr;
    quint64 m_program = 0;
    quint64 m_inputs = 0;
    QString m_error;
    qint64 m_failures = 0;
};

} // namespace srpss_core
