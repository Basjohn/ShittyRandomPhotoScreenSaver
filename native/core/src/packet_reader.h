// The packet reader (Current_Plan.md item 8b, N2.3; Docs/Future_Work/Native_Core_P3_Decisions.md, D1, D2 and the
// transport rule): the native core's one consuming reader of a Visualizer frame stream, the C++ twin of the Python
// reference reader (core/visualizer_engine/packet_abi.py FramePacketReader with native_schema.admit_slot_head, and the
// per-mode reference decoder, spectrum_native_schema.decode). The layout, the mode codes and every record's fields and
// range rules come from frame_abi_generated.h, generated from those Python modules.
//
// D1, the barrier against the GUI thread closing the mapping:
// - the reader maps its own view of the mapping BY NAME (OpenFileMappingW, MapViewOfFile) and never borrows Python's
//   pointer: a mapped view keeps the section alive after the owner closes and unlinks its name, so a close can never
//   unmap memory the reader is copying. A name that no longer opens is a retired stream (state Retired), never an
//   error loop;
// - three states changed by one atomic: Open, Retiring, Retired. retire() (any thread, the GUI's "retire stream" call)
//   stores Retiring and returns at once; release() (the render thread's retire job) drops the retained frame and the
//   reader's own pin on the view and stores Retired. No copy starts once Retiring is set. Nobody waits for anybody:
//   every read takes a pin on the view and the last pin to go unmaps it (a head read on the GUI thread racing the
//   render thread's release unmaps on whichever side finishes last);
// - per-stream liveness: copies_started, copies_finished and the last accepted sequence, readable without a lock.
//
// D2, one consumer: read() is the only consuming read. It acknowledges a sequence (consumed_sequence in the mapping)
// at the accept edge: the slot whole under its seqlock, the expected identity (a slot of another identity is foreign
// before its schema is looked at, so a stale slot never fails the stream), admitted by its head (schema, mode code,
// version, size), the payload copied whole and the record's own range rules held; the frame's protected-edge mask is
// then the retained frame's, and the acknowledgement is written before read() returns. Nothing else writes
// consumed_sequence. readHead() returns the newest whole slot's head and moves nothing (not accepted, not
// consumed_sequence).
//
// The drop edge (R-184 as a contract): dropRetainedFrame() (GUI) posts a drop the next read() applies first: the
// retained frame is cleared. The retained frame is always the last accepted one, so the accepted watermark already
// holds it: no frame at or below that watermark is ever accepted again, whatever a head read or a late wake says; only a
// newer sequence is (the drop keeps no watermark of its own: audit 14 Nov, low 2).
//
// The transport rule: a slot whose payload_schema, mode code, version or size the reader does not know is refused at
// its head, before any payload byte is copied; a record whose own field is out of range is refused after the copy.
// A refusal is counted, logged in the state, never acknowledged, and fails the stream (read() returns Failed from then
// on). Nothing is guessed, skipped silently or decoded another way.
//
// Torn, stale and duplicate slots: a latest sequence that is odd, a slot whose begin or end disagrees with it (or two
// slots claiming it), or a begin that changed during the copy is torn: counted, the previous frame kept, nothing
// acknowledged, the next frame edge reads again (no retry loop). A latest sequence at the accepted one is nothing new
// (a republished duplicate is not accepted twice); below it is stale (counted once per value).
//
// `controls` are the harness's negative controls (each disables one guard; the product never sets one).
//
// Windows x64 only (the module's one target); no STL container, lock or function wrapper (README: msvcp140).
#pragma once

#include "frame_abi_generated.h"

#include <QtCore/QAtomicInteger>
#include <QtCore/QByteArray>
#include <QtCore/QJsonObject>
#include <QtCore/QSemaphore>
#include <QtCore/QString>

namespace srpss_core {

// The 64-byte slot head as stored (packet_abi.py: "<QIIddIIIIIIQ").
struct SlotHead
{
    quint64 sequence = 0;
    quint32 payloadBytes = 0;
    quint32 payloadSchema = 0;
    double logicalTimestamp = 0.0;
    double sourceTimestamp = 0.0; // NaN: none
    quint32 flags = 0;
    quint32 protectedEdgeMask = 0;
    quint32 runtimeGeneration = 0; // u32 as stored (0xFFFFFFFF: -1)
    quint32 engineGeneration = 0;
    quint32 activationId = 0;
    quint32 modeCode = 0;
    quint64 publishNs = 0;
};

struct PacketReaderConfig
{
    // The stream's expected identity (D2's accept edge): a slot of another identity is not this stream's frame (counted
    // foreign, not accepted, not acknowledged). Unset: any identity.
    bool expectIdentity = false;
    quint32 runtimeGeneration = 0;
    quint32 engineGeneration = 0;
    quint32 activationId = 0;
    quint32 modeCode = 0;

    // Negative controls (harness only): each disables one guard.
    bool skipHeadCheck = false;       // no head admission and no record rules (a reader that decodes whatever it finds)
    bool skipHeadSeqlock = false;     // the head's seqlock off: an odd latest, the sequence_end check, the head's begin
    bool skipCopyReread = false;      // no begin re-read after the payload copy (the in-place race's guard, alone)
    bool acceptUnordered = false;     // accept any latest sequence other than the accepted one (stale included)
    bool acknowledgeRefused = false;  // a refused slot is acknowledged
    bool headResetsWatermark = false; // a head read resets the accepted watermark (the drop's resurrection)
    bool skipIdentity = false;        // the expected identity is not compared
    // The D1 test hook "close during copy" (harness only, never a guard): the reader pauses inside each copy, after the
    // copy started and before its bytes are read, until resume(); waitPaused() tells another thread it is there.
    bool pauseInCopy = false;
    bool acceptAfterRetire = false;   // negative control: a copy finished after the stream began retiring is accepted
    bool copyWhileRetiring = false;   // negative control: a copy starts although the stream is retiring

    static bool fromJson(const QByteArray &json, PacketReaderConfig *out, QString *error);
    QJsonObject toJson() const;
};

enum class ReadResult : int {
    Nothing = 0,  // no frame newer than the accepted one
    Accepted = 1, // a new frame is retained and acknowledged
    Torn = 2,
    Stale = 3,
    Foreign = 4,  // another identity's slot
    Refused = 5,  // this read refused the slot: the stream failed
    Failed = 6,   // the stream failed earlier: nothing is read
    Retiring = 7,
    Retired = 8,
};

const char *readResultName(ReadResult result);

class PacketReader
{
public:
    // Opens the named mapping and validates it as packet_abi.py's _validate does. A name that does not open gives a
    // Retired reader (openError() says why); a mapping that opens but is not a frame buffer this build reads is refused
    // (nullptr, with `error`).
    static PacketReader *open(const QString &name, const PacketReaderConfig &config, QString *error);
    ~PacketReader();
    PacketReader(const PacketReader &) = delete;
    PacketReader &operator=(const PacketReader &) = delete;

    // The consumer's frame edge (the render thread in the product; any one thread in a harness).
    ReadResult read();
    // The newest whole slot's head, non-consuming (any thread): false when there is none whole, or the view is gone.
    bool readHead(SlotHead *out);

    void retire();             // any thread: Retiring, at once
    void release();            // the consumer's thread (the render thread's retire job): Retired, the view's pin goes
    void dropRetainedFrame();  // any thread: applied by the next read()

    // The pause_in_copy hook (any thread other than the reader's): true once a read is paused inside its copy (within
    // `timeoutMs`); resume() lets it go on.
    bool waitPaused(int timeoutMs);
    void resume();
    bool pausesInCopy() const { return m_config.pauseInCopy; }

    // The retained frame (the consumer's thread): its head and its record (owned by the reader, valid until its next
    // read, drop or release), or false when none is retained. Its schema is null only under skipHeadCheck.
    bool retained(SlotHead *head, const QByteArray **record) const;
    const frame_abi::Schema *retainedSchema() const { return m_hasFrame ? m_frameSchema : nullptr; }

    const QString &openError() const { return m_openError; }
    QJsonObject stateJson() const;

    // Process-wide: readers alive and views mapped (lifecycle proofs: both return to zero).
    static QJsonObject liveJson();

    // The compiled-in schema table (the Python face compares it with its own at reader creation).
    static const frame_abi::Schema *schema(quint32 schemaId);

private:
    enum State : int { Open = 0, Retiring = 1, Retired = 2 };

    PacketReader(const QString &name, const PacketReaderConfig &config);
    bool validate(QString *problem);
    bool pin();
    void unpin();
    void unmap();
    bool admit(const SlotHead &head, QString *cause, QString *reason) const;
    bool checkRecord(const frame_abi::Schema *schema, const QByteArray &record, QString *cause, QString *reason) const;
    // A whole slot's head under its seqlock (sequence_end first, the head, sequence_begin again): -1 none or torn.
    // `strict` false is the skipHeadSeqlock control (the slot found by its begin alone).
    int wholeSlot(quint64 latest, SlotHead *head, bool *ambiguous, bool strict) const;
    ReadResult refuse(quint64 sequence, const QString &cause, const QString &reason);
    void applyDrop();

    QString m_name;
    PacketReaderConfig m_config;
    QString m_openError;
    uchar *m_base = nullptr; // the reader's own view
    quint64 m_viewBytes = 0;
    quint32 m_slotBytes = 0;
    quint32 m_capacity = 0;
    quint32 m_headerIdentity[4] = {}; // the header's configure-time identity at open

    QAtomicInt m_state { Open };
    QAtomicInt m_pins { 0 };          // the reader's own pin (while Open or Retiring) plus one per read in progress
    bool m_ownPin = false;            // the reader holds its own pin (a mapped view, not yet released)
    QAtomicInt m_unmapped { 0 };
    QAtomicInt m_dropRequested { 0 };
    QSemaphore m_paused;              // the pause_in_copy hook: released when a read is paused, ...
    QSemaphore m_resume;              // ... acquired by it until resume()
    QAtomicInteger<qint64> m_pauses { 0 };
    qint64 m_copiesDiscarded = 0;     // copies finished after the stream began retiring (D1: nothing of them presented)

    // Consumer-thread state.
    quint64 m_accepted = 0;        // the accepted watermark (the drop edge's too)
    quint64 m_lastStale = 0;       // the last stale value counted (counted once per value)
    quint64 m_lastForeign = 0;     // the last foreign sequence counted
    bool m_failed = false;
    QString m_refusalCause;
    QString m_refusalReason;
    quint64 m_refusalSequence = 0;
    QByteArray m_staging;          // the copy in progress (never presented)
    QByteArray m_frame;            // the retained frame's record
    SlotHead m_frameHead;
    const frame_abi::Schema *m_frameSchema = nullptr;
    bool m_hasFrame = false;

    // Counters (stateJson; the liveness three are readable from any thread).
    QAtomicInteger<qint64> m_copiesStarted { 0 };
    QAtomicInteger<qint64> m_copiesFinished { 0 };
    QAtomicInteger<quint64> m_lastAccepted { 0 };
    QAtomicInteger<qint64> m_headReads { 0 };
    qint64 m_reads = 0;
    qint64 m_acceptedCount = 0;
    qint64 m_acknowledged = 0;
    quint64 m_acknowledgedSequence = 0;
    qint64 m_torn = 0;
    qint64 m_ambiguous = 0;
    qint64 m_stale = 0;
    qint64 m_foreign = 0;
    qint64 m_refused = 0;
    qint64 m_dropsApplied = 0;
    qint64 m_readsWhileRetiring = 0;
};

} // namespace srpss_core
