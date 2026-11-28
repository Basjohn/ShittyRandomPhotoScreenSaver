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
// again is skipped for that frame, never overwritten, until it has stayed unread for more frames than the ring is long:
// then it is abandoned (counted, reused, its late result never read; R-223: a GPU that falls behind without bound, as
// the OpenGL hidden host's did, left every slot pending for good). `waitForResults` is the harness's negative control: the blocking
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
    Backdrop = 4, // a backdrop pyramid's build, every level (backdrop.h, N5.7b)
    ScenePass = 5, // N5.2h: one unit of a mode's record (GpuUnitPart), only under the harness's time_scene_passes
};

QString gpuPassKindName(GpuPassKind kind);

// N5.2h: what a ScenePass figure times inside a mode's record (mode_content.cpp recordPasses), each bracketed between
// render passes, never inside one. `pass` names the program's first pass of the unit (-1: none).
enum class GpuUnitPart : int {
    Unit = 0,      // the unit at `pass`: a run (its primes, its passes, the pass's own resolves at its end), a compute
                   // entry, a capture, an environment, a bloom chain, a defocus or a prefilter
    Nearest = 1,   // the run's nearest copies of its multisampled attachments (recordNearest)
    SelfMips = 2,  // the run's self-mipped chains
    Chains = 3,    // the item textures' chains before any pass (pass -1)
    LastClear = 4, // the surface's clear when no run drew it (pass -1)
    // N5.2h, OpenGL only, under the harness control time_scene_run_parts (time_scene_passes on too): a scene target's
    // run in three parts in place of its Unit, two of them bracketed inside the run's render pass (QRhi's OpenGL
    // backend issues what it holds at beginExternal inside a pass as outside one; Vulkan would need an ExternalContent
    // pass and keeps the Unit):
    RunOpen = 5,    // the run's opening: its primes, its pass's begin and clear, its clearing draw (`pass` the run's)
    RunDraw = 6,    // one pass of the run (`pass` that pass)
    RunResolve = 7, // the run's end: QRhi's end-of-pass resolves of its multisampled attachments (`pass` the run's)
};

// N5.2h: the harness control time_scene_passes (stage_control). While it is on and a host's timer runs, the frame driver
// does not bracket a surface's record whole (OpenGL's GL_TIME_ELAPSED queries cannot nest) but hands the record its unit
// brackets (below), so each unit is a ScenePass figure. Off (the default) nothing changes: the brackets stay null.
void setTimeScenePasses(bool on);
bool timeScenePasses();
// N5.2h: the harness control time_scene_run_parts: under time_scene_passes on OpenGL, a scene target's run is timed as
// RunOpen, a RunDraw per pass and RunResolve in place of its Unit. Off (the default) nothing changes.
void setTimeSceneRunParts(bool on);
bool timeSceneRunParts();

// N5.2h: the render thread's unit brackets for the record in progress (null: no unit is timed, one pointer read per unit).
struct GpuUnitBrackets
{
    void *owner = nullptr;
    int (*begin)(void *owner, QRhi *rhi, QRhiCommandBuffer *cb, int pass, int part) = nullptr;
    void (*end)(void *owner, QRhi *rhi, QRhiCommandBuffer *cb, int scope) = nullptr;
};
const GpuUnitBrackets *gpuUnitBrackets();
void setGpuUnitBrackets(const GpuUnitBrackets *brackets);

// N5.2h: a unit's bracket for its scope (render thread, outside any pass at construction and destruction).
class GpuUnitScope
{
public:
    GpuUnitScope(QRhi *rhi, QRhiCommandBuffer *cb, int pass, GpuUnitPart part);
    ~GpuUnitScope();
    GpuUnitScope(const GpuUnitScope &) = delete;
    GpuUnitScope &operator=(const GpuUnitScope &) = delete;

private:
    const GpuUnitBrackets *m_brackets;
    QRhi *m_rhi;
    QRhiCommandBuffer *m_cb;
    int m_scope = -1;
};

// The ring's rule for a frame's slot (GPU-free; R-223): take it when free; leave the frame untimed while the slot's
// results are unread (Busy); abandon the slot once they have stayed unread for more frames than the ring is long (its
// late result is never read: the slot's queries are reused), so the timer keeps timing every frame it can.
enum class GpuSlotUse { Take, Busy, Abandon };
GpuSlotUse gpuSlotUse(bool pending, qint64 slotEdge, qint64 edge, int ringFrames);
// GPU-free: the ring over `frames` edges whose results become available `lag` edges after their frame (lag < 0: never),
// abandoning or not (the safety net's negative control); the counts the tests read.
struct GpuRingSimulation
{
    int timed = 0;      // frames whose pass was bracketed
    int results = 0;    // results read
    int busy = 0;       // frames left untimed, their slot unread
    int abandoned = 0;  // slots given up on
};
GpuRingSimulation simulateGpuRing(int ringFrames, int frames, int lag, bool abandon);

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
    int pass = -1;          // N5.2h, ScenePass only: the unit's first program pass (-1: none)
    int part = 0;           // N5.2h, ScenePass only: GpuUnitPart
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
    // Frame slots: longer than any QRhi's FramesInFlight plus one, and than OpenGL's read lag (build round 1 read results
    // up to 5 frames late and left 3 of 30 frames untimed with 4 slots; the hidden host then only flushed its OpenGL
    // frames and ran ahead without bound, R-223: it now finishes them, and a slot unread past the ring is abandoned).
    static constexpr int kRingFrames = 8;
    // Timed passes per frame; more are recorded untimed and counted. N5.2h: 32, for a scene's units under
    // time_scene_passes (a 4x scene with motion blur and trails has about a dozen).
    static constexpr int kMaxScopes = 32;

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
    int begin(QRhi *rhi, QRhiCommandBuffer *cb, GpuPassKind kind, int pass = -1, int part = 0);
    void end(QRhi *rhi, QRhiCommandBuffer *cb, int scope);

    // Render thread: no more recording (the timer switched off). Its objects stay until released.
    void stop(qint64 edge);
    bool stopped() const { return m_stopped; }
    // Render thread, at a frame edge: true once every frame that wrote a query completed and its results were read (or
    // the ring went round without them), so the objects can go without a wait and no result is lost.
    bool drained(QRhi *rhi, qint64 edge) const;
    // Render thread: the query objects go. Outside a frame QRhi::finish() completes the earlier frames first. Inside a
    // frame that is not drained (a detach at the frame edge), N3.6: Vulkan's pool goes to the device's deferred queue
    // stamped with the window's edge `windowEdge` (vulkan_context.h, deferRawVulkanDestroy), never a wait inside the frame;
    // only without an edge (windowEdge < 0) does it wait for its queue once, as before.
    void release(QRhi *rhi, bool outsideFrame, qint64 windowEdge = -1);
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
        int pass = -1;
        int part = 0;
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
    qint64 m_abandonedSlots = 0;   // slots given up on, unread for more frames than the ring (R-223's safety net)
    qint64 m_overCapacity = 0;     // passes left untimed because the frame's slot was full
    qint64 m_releaseWaits = 0;     // releases that waited for the queue (a detach inside a frame, no window edge)
    qint64 m_deferredReleases = 0; // N3.6: pools handed to the device's deferred queue instead (a detach inside a frame)
    qint64 m_resolveNsMax = 0;     // CPU time of one edge's reads, the longest
    qint64 m_resolveNsTotal = 0;
    qint64 m_latencyMin = -1;      // edges between a pass's recording and its read
    qint64 m_latencyMax = -1;
    qint64 m_latencyHistogram[8] = {}; // reads 1, 2, ..., 7 and 8 or more edges later
};

} // namespace srpss_core
