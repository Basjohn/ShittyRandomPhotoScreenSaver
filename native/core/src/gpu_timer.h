// The per-pass GPU timer service (D5.3's first service, D8 plus 2; Current_Plan.md item 8b, N2.6).
//
// Its form (D5.6 answer 4, settled from where the core records a pass): the frame driver brackets each whole pass it
// records, on its beforeRendering edge, outside any render pass, through QRhiCommandBuffer::beginExternal() on the
// frame's own command buffer. Outside a pass QRhi records what it holds into the primary command buffer first, so the
// bracket lands exactly between the passes in submission order and no secondary command buffer is involved (the research
// addendum's worry, A.1, applies only inside a pass, where the core never times):
// - Vulkan: raw timestamps, vkCmdWriteTimestamp TOP_OF_PIPE before the pass and BOTTOM_OF_PIPE after it, in a query pool
//   of the timer's own (reset in the frame, before its first write, outside the pass);
// - OpenGL: timer queries, GL_TIME_ELAPSED begun before the pass and ended after it (QRhi's OpenGL backend issues what it
//   recorded at beginExternal, so the query encloses the pass's own GL commands and nothing else);
// - D3D11 and D3D12: QRhi gives no per-pass time (D5.3: the service has exactly two native forms, Vulkan and OpenGL);
//   what QRhi provides there, and on the other two as well, is the whole frame: QRhiCommandBuffer::lastCompletedGpuTime()
//   of a QRhi created with EnableTimestamps (QQuickGraphicsConfiguration::setTimestamps; a host opts in at creation).
//   The timer reads it at the frame edge and reports it as the frame's figure.
//
// Results are latched, never waited for: each frame's queries live in one of kRingFrames slots, and at every later edge
// the timer reads the slots whose results are available (Vulkan without VK_QUERY_RESULT_WAIT_BIT, with availability;
// OpenGL GL_QUERY_RESULT_AVAILABLE first). A slot is reused only once its frame completed (QRhi never runs more than
// FramesInFlight frames ahead, and the ring is longer); a slot whose results are still not available when its turn comes
// again is skipped for that frame, never overwritten. `waitForResults` is the harness's negative control: the blocking
// read the service never does (Vulkan: every earlier frame's results with VK_QUERY_RESULT_WAIT_BIT at the edge; OpenGL
// also the naive read right after the pass in its own frame, because Qt's OpenGL loop has already finished the previous
// frame on the GPU by the next edge, so a wait there has nothing to show).
//
// Off is free: the frame driver holds no timer at all while it is off, so there is no query object and no per-frame call
// (process-wide counts: liveJson()). Switched off, the timer stops recording at once and its query objects go once the
// frames that wrote them have completed; `keepWhenOff` is the negative control that keeps them.
//
// Render thread only, except takeSamples (the frame driver's queue) and the JSON readers.
#pragma once

#include <QtCore/QAtomicInteger>
#include <QtCore/QByteArray>
#include <QtCore/QJsonObject>
#include <QtCore/QList>
#include <QtCore/QMutex>
#include <QtCore/QString>

#include <memory>

class QRhi;
class QRhiCommandBuffer;

namespace srpss_core {

// What a figure times. The numbers are the frame trace's (rendering/native/gpu_timing.py GPU_PASS_KINDS).
enum class GpuPassKind : int {
    Frame = 0,   // QRhi's whole frame (lastCompletedGpuTime)
    Probe = 1,   // the probe pass (probe_pass.h)
    Surface = 2, // a composited surface's content pass (surfaces.h)
    Load = 3,    // the harness's known-cost pass (load_pass.h)
};

QString gpuPassKindName(GpuPassKind kind);

struct GpuTimerConfig
{
    bool enabled = false;
    bool keepWhenOff = false;    // negative control: the query objects survive switching the timer off
    bool waitForResults = false; // negative control: results read with a blocking wait (see above)

    // From the harness's JSON (missing keys keep the defaults); false with `error` for an unknown key or a wrong type.
    static bool fromJson(const QByteArray &json, GpuTimerConfig *out, QString *error);
    QJsonObject toJson() const;
};

struct GpuTimingSample
{
    int kind = 0;           // GpuPassKind
    qint64 frame = -1;      // the frame edge the pass was recorded at (-1 for QRhi's frame figure: Qt does not say)
    qint64 readAt = -1;     // the edge the result was read at
    qint64 nanoseconds = 0; // GPU time
};

// The frame driver's queue of results, drained from the GUI thread (bounded: the oldest are kept, overflow is counted).
class GpuSampleQueue
{
public:
    static constexpr int kCapacity = 16384;
    void append(const GpuTimingSample &sample);
    QList<GpuTimingSample> take();
    qint64 dropped() const;
    qint64 appended() const;

private:
    mutable QMutex m_mutex;
    QList<GpuTimingSample> m_samples;
    qint64 m_dropped = 0;
    qint64 m_appended = 0;
};

class GpuTimer
{
public:
    // Frame slots: longer than any QRhi's FramesInFlight plus one, and than the OpenGL hidden host's lag (its offscreen
    // frames only flush: build round 1 read results up to 5 frames late and left 3 of 30 frames untimed with 4 slots).
    static constexpr int kRingFrames = 8;
    static constexpr int kMaxScopes = 16;  // timed passes per frame; more are recorded untimed and counted

    GpuTimer(const GpuTimerConfig &config, std::shared_ptr<GpuSampleQueue> queue);
    ~GpuTimer();
    GpuTimer(const GpuTimer &) = delete;
    GpuTimer &operator=(const GpuTimer &) = delete;

    // Render thread, at the frame edge before anything of the core's is recorded: reads the slots of earlier frames whose
    // results are available (never waiting, unless the negative control asks) and QRhi's own frame figure, and makes this
    // frame's slot current. The first call creates the query objects (Vulkan, OpenGL).
    void beginFrame(QRhi *rhi, QRhiCommandBuffer *cb, qint64 edge);
    // Render thread, inside the frame, outside any pass: a bracket around one pass. begin returns its scope, or -1 when
    // nothing is timed (no per-pass form on this backend, the timer stopped, the frame's slot busy or full, an error).
    int begin(QRhi *rhi, QRhiCommandBuffer *cb, GpuPassKind kind);
    void end(QRhi *rhi, QRhiCommandBuffer *cb, int scope);

    // Render thread: no more recording (the timer switched off). Its objects stay until released.
    void stop(qint64 edge);
    bool stopped() const { return m_stopped; }
    // Render thread, at a frame edge: true once every frame that wrote a query completed and its results were read (or
    // the ring went round without them), so the objects can go without a wait and no result is lost.
    bool drained(QRhi *rhi, qint64 edge) const;
    // Render thread: the query objects go. Inside a frame that is not drained, Vulkan waits for its queue once (a detach);
    // outside a frame QRhi::finish() completes the earlier frames first.
    void release(QRhi *rhi, bool outsideFrame);
    bool hasObjects() const { return m_queryObjects > 0; }

    void setWaitForResults(bool wait) { m_config.waitForResults = wait; }
    const GpuTimerConfig &config() const { return m_config; }
    QJsonObject stateJson() const;

    // Process-wide: timers alive and the query objects they hold (Vulkan query pools and queries, OpenGL query names).
    static QJsonObject liveJson();

private:
    struct Scope
    {
        int kind = 0;
        bool closed = false;
    };
    struct Slot
    {
        qint64 edge = -1;
        int scopes = 0;
        bool pending = false; // written and submitted, results not yet read
        Scope scope[kMaxScopes];
    };
    struct Vulkan;
    struct OpenGl;

    bool ensure(QRhi *rhi);
    void resolve(QRhi *rhi, QRhiCommandBuffer *cb, qint64 edge);
    bool resolveSlot(int index, qint64 edge);
    void readFrameFigure(QRhiCommandBuffer *cb, qint64 edge);
    void setQueryObjects(int pools, int queries);

    GpuTimerConfig m_config;
    std::shared_ptr<GpuSampleQueue> m_queue;
    std::unique_ptr<Vulkan> m_vk;
    std::unique_ptr<OpenGl> m_gl;
    QString m_backend;
    QString m_perPass; // "vulkan timestamps", "opengl GL_TIME_ELAPSED", or why there is none
    QString m_error;
    bool m_created = false;
    bool m_stopped = false;
    Slot m_slots[kRingFrames];
    int m_current = -1;    // this frame's slot, or -1
    qint64 m_edge = -1;
    qint64 m_lastWriteEdge = -1;
    int m_framesInFlight = 0;
    int m_pools = 0;
    int m_queryObjects = 0;
    double m_lastFrameSeconds = 0.0;
    double m_timestampPeriodNs = 1.0;
    int m_timestampValidBits = 64;

    // Counters (stateJson).
    qint64 m_frames = 0;           // edges seen
    qint64 m_timedPasses = 0;      // brackets recorded
    qint64 m_results = 0;          // per-pass results read
    qint64 m_frameFigures = 0;     // QRhi frame figures read
    qint64 m_notReadyReads = 0;    // a slot read whose results were not all available yet (read again later)
    qint64 m_blockingReads = 0;    // reads that waited (the negative control only)
    qint64 m_slotBusyFrames = 0;   // frames left untimed because their slot still held unread results
    qint64 m_overCapacity = 0;     // passes left untimed because the frame's slot was full
    qint64 m_releaseWaits = 0;     // releases that waited for the queue (a detach inside a frame)
    qint64 m_resolveNsMax = 0;     // CPU time of one edge's reads, the longest
    qint64 m_resolveNsTotal = 0;
    qint64 m_latencyMin = -1;      // edges between a pass's recording and its read
    qint64 m_latencyMax = -1;
    qint64 m_latencyHistogram[8] = {}; // reads 1, 2, ..., 7 and 8 or more edges later
};

} // namespace srpss_core
