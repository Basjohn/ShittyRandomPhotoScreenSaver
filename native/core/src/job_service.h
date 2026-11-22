// The async job service (D9; Current_Plan.md item 8b, N3.8): GPU work that must not lengthen one frame's command buffer
// runs on a job thread with its own queue, and is published to the frame by a latch. D9's "As built (N3.8)" is the
// contract; N0.7 (native/spike_p1 vk_n07.cpp) is the proof it is built to. The first job is a photo's upload and its GPU
// mips into one of N4.a's core-owned textures (mode_content.h).
//
// - One service per Vulkan device (vulkan_context.h asks for the second queue of Qt's graphics family; a family with one
//   queue gets no service and every job runs in its in-frame form). The service object exists from the device's
//   creation; its thread and its backend (a QRhi on our VkDevice and the job queue, its own allocator) are created at
//   the first job. The thread has no event loop: it is parked on a QWaitCondition (no polling, no timer) and every
//   return from the wait is counted (wakeups). A backend that cannot be set up fails the service closed: every job then
//   fails at once and its consumer runs the in-frame form.
// - A job (UploadJob) owns every input it reads: the image's pixels (shared, immutable), its size, whether it has mips.
//   It reads nothing of a live frame, of an item or of Qt's QRhi. Its output is a new texture in the job's QRhi (never
//   a slot a frame may read).
// - The latch: a job is a ticket with one atomic state. The job thread publishes by compare-and-set from running to done
//   after writing the result (the native image and its layout), then tells the job's notifier (the item's: a queued
//   frame request on the GUI thread). The consumer reads the state at its record, on the render thread; a frame never
//   waits for a job.
// - Cancellation by compare-and-set (UploadJob::cancel): a queued job never runs; a running one drops its output on the
//   job thread after its GPU wait; a job that published first hands its output to the consumer, which releases it.
// - An output Qt sampled is released (release()) only after Qt's frames that sampled it completed: the consumer's window
//   retire list (surfaces.h) decides when. The job thread destroys it with its own QRhi.
// - Teardown (stop(), from the device's destruction): queued jobs and the job in flight are abandoned (dropped
//   unpublished after its own GPU wait), every output still held is destroyed, the backend goes (its queue idle), the
//   thread is joined. The device then waits idle and goes.
//
// The backend is an interface (JobBackend) so the service's thread, latch and cancellation run GPU-free under a scripted
// backend (jobServiceSelfTestJson: tests/test_native_core_jobs.py); the product's backend is the QRhi upload
// (job_service.cpp RhiUploadBackend).
#pragma once

#include "field_recipe.h"
#include "pipeline_cache.h"
#include "thread_probe.h"

#include <QtCore/QAtomicInteger>
#include <QtCore/QByteArray>
#include <QtCore/QHash>
#include <QtCore/QJsonArray>
#include <QtCore/QJsonObject>
#include <QtCore/QList>
#include <QtCore/QMutex>
#include <QtCore/QSharedPointer>
#include <QtCore/QSize>
#include <QtCore/QString>
#include <QtCore/QWaitCondition>

#include <memory>

class QVulkanInstance;

namespace srpss_core {

struct TextureImage; // mode_content.h
enum class ModeTextureFormat; // mode_content.h (ABI 33: RGBA8 or RGBA16F)
class JobThread;

enum class JobState : int {
    Queued = 0,    // submitted, not taken by the job thread yet
    Running = 1,   // the job thread records it or waits for its GPU work
    Done = 2,      // published: its output is the consumer's
    Failed = 3,    // it could not run (the pixels are kept for the in-frame form)
    Cancelled = 4, // the consumer cancelled it (superseded, removed, released); its output, if any, was dropped
    Abandoned = 5, // the service stopped first; its output, if any, was dropped
};
QString jobStateName(JobState state);
bool jobTerminal(JobState state);

// Told by the job thread when a job of its consumer finished (published or failed): any thread may call it; it must not
// block (the item's notifier queues a frame request on the GUI thread).
class JobNotifier
{
public:
    virtual ~JobNotifier() = default;
    virtual void jobFinished() = 0;
};

// ABI 43 (N5.2g): one published output of a field job (its ids are consecutive from the first).
struct JobOutput
{
    quint64 id = 0;
    quint64 nativeImage = 0;   // VkImage
    int nativeLayout = 0;      // VkImageLayout the job left it in
    qint64 bytes = 0;
};

// One upload job: a photo's pixels into a new texture of the job's QRhi, with its mips when asked. The ticket the
// consumer (render thread) and the job thread share.
// ABI 43 (N5.2g, D9 point 2 consumer (a)): or a field job: a field recipe (field_recipe.h) recorded on the job queue by
// the shared FieldRecorder, its input photo uploaded by the job from `pixels` (null: the recipe samples none), its outputs
// (one to kMaxFieldOutputs) published together under consecutive ids. Everything else (the latch, cancellation, release,
// teardown) is the upload's.
class UploadJob
{
public:
    UploadJob(const QByteArray &name, quint64 generation, const QSharedPointer<TextureImage> &pixels,
              std::shared_ptr<JobNotifier> notifier);
    UploadJob(const QByteArray &name, quint64 generation, const QSharedPointer<TextureImage> &pixels,
              std::shared_ptr<const FieldRecipe> recipe, std::shared_ptr<JobNotifier> notifier);
    ~UploadJob();
    UploadJob(const UploadJob &) = delete;
    UploadJob &operator=(const UploadJob &) = delete;

    const QByteArray name;     // the item's texture
    const quint64 generation;  // the image's (ModeTexture::generation)
    const QSize size;
    const bool mips;
    const ModeTextureFormat format; // ABI 33: the image's (its output texture's format)
    const std::shared_ptr<const FieldRecipe> recipe; // ABI 43: a field job's (null: an upload)

    // ABI 43: the outputs it publishes (an upload one, a field job its recipe's), and output `index`'s id once published.
    int outputCount() const;
    quint64 outputIdOf(int index) const;

    JobState state() const { return JobState(m_state.loadAcquire()); }

    // Job thread.
    bool start();                          // queued -> running; false: cancelled or abandoned before it ran
    bool publish();                        // running -> done (after the output is written); false: cancelled meanwhile
    void fail(const QString &error);       // queued or running -> failed; the pixels are kept for the in-frame form
    void abandon();                        // queued or running -> abandoned (the service stops)
    QSharedPointer<TextureImage> pixels() const; // the input, until dropped
    void dropPixels();                     // the upload is recorded: the core's copy goes (the job's success path only)
    void notifyFinished();                 // the notifier, once (after publish or fail)

    // Consumer.
    enum class Cancelled { Pending, Published, Over };
    // queued or running -> cancelled (Pending: the job drops whatever it makes); done: Published (the output is the
    // consumer's to release); failed, cancelled or abandoned: Over.
    Cancelled cancel();
    // After failed: the pixels for the in-frame form (null when they were dropped).
    QSharedPointer<TextureImage> takePixels();

    // The output, written by the job thread before publish() (read after state() == Done).
    quint64 outputId = 0;
    quint64 nativeImage = 0;   // VkImage
    int nativeLayout = 0;      // VkImageLayout the job left it in
    qint64 outputBytes = 0;    // every level (a field job: every output)
    JobOutput fieldOutputs[kMaxFieldOutputs]; // ABI 43: a field job's, in its recipe's output order (outputId the first)
    QString error;             // failed: why

    // Times (ns on one monotonic clock): submitted (consumer), started, recorded (submitted to the GPU), completed (the
    // GPU wait returned), published or finished.
    qint64 submittedNs = 0;
    qint64 startedNs = 0;
    qint64 recordedNs = 0;
    qint64 completedNs = 0;
    qint64 finishedNs = 0;
    // Every field: only once the job thread's own edge is set (done, failed, abandoned: written before it), or on the
    // job thread itself.
    QJsonObject toJson() const;
    // Audit N38 L2: what any thread may read while the job thread may be writing its fields (the job in flight): its
    // constant fields and its atomic state only.
    QJsonObject briefJson() const;

private:
    QAtomicInteger<int> m_state { int(JobState::Queued) };
    mutable QMutex m_pixelsMutex;
    QSharedPointer<TextureImage> m_pixels;
    std::shared_ptr<JobNotifier> m_notifier;
    QAtomicInteger<int> m_notified { 0 };
};

// What does the work, on the job thread only.
class JobBackend
{
public:
    virtual ~JobBackend() = default;
    // At the first job. False with the reason: the service fails closed.
    virtual bool setUp(QString *error) = 0;
    // Records the upload (and mips), submits, drops the job's pixels (job.dropPixels()) and waits for its own GPU work.
    // True: the output exists under `id` (job.outputId, nativeImage, nativeLayout, outputBytes written). False with the
    // reason: nothing exists under `id` and the pixels are kept unless the upload was submitted.
    // ABI 43: a field job (job.recipe) records its recipe instead; true: its outputs exist under `id` to `id` +
    // outputCount() - 1 (job.fieldOutputs written, outputId the first); false: none of them exists.
    virtual bool upload(UploadJob &job, quint64 id, QString *error) = 0;
    // An output nobody will sample: destroyed (after flush(), its memory is free).
    virtual void destroy(quint64 id) = 0;
    // After destroys: the backend's deferred releases run (the job QRhi's finish()).
    virtual void flush() = 0;
    // Every output it holds and itself go (the service stops).
    virtual void tearDown() = 0;
    // The service's stop() was asked (any thread, before the join): the job in flight will be abandoned. The QRhi
    // backend has nothing to do (its GPU wait ends by itself); the scripted one opens its held "GPU wait".
    virtual void stopping() {}
    // Audit N38 L1, job thread: the device was found lost (an upload's completion edge returned it). The service then
    // fails closed: the job fails, every later job fails at once and its consumer runs the in-frame form.
    virtual bool deviceLost() const { return false; }
    // N3.6, checkpoint audit 11 L2 (any thread, before the service's stop): the device was found lost outside the job
    // thread (its window's QRhi reported it). deviceLost() is true afterwards: no job touches it, the teardown saves
    // nothing of it.
    virtual void markDeviceLost() {}
    virtual QJsonObject stateJson() const = 0;
};

// The product's backend: a QRhi on the module's VkDevice and the job queue (D9 as built point 1).
struct JobDevice
{
    QVulkanInstance *instance = nullptr;
    quint64 physicalDevice = 0; // VkPhysicalDevice
    quint64 device = 0;         // VkDevice
    quint32 family = 0;         // Qt's graphics family
    quint32 queueIndex = 1;     // the job queue
    bool debugMarkers = false;  // validation loaded: the job QRhi names its objects
    // N3.6 (pipeline_cache.h): the core's pipeline cache file and the device it must have been made on. The job QRhi
    // loads it when it is created and saves it at its orderly teardown (not after a device loss).
    PipelineCacheIdentity cacheIdentity;
    QString cacheFile;
};
std::unique_ptr<JobBackend> createRhiUploadBackend(const JobDevice &device);

// Process-wide counts (the destruction barrier's reading, lifecycle proofs).
struct JobCounts
{
    int services = 0;      // services alive
    int threads = 0;       // job threads running
    int queued = 0;        // jobs queued
    int running = 0;       // jobs the job thread is running
    int images = 0;        // outputs the services hold (published, not yet released)
    qint64 imageBytes = 0;
    int releasesPending = 0; // releases asked for and not yet done
    qint64 wakeups = 0;    // returns from the park, every service
};
JobCounts jobCounts();
QJsonObject jobCountsJson();

class JobService
{
public:
    // GUI thread (the device's creation): a service over `backend`, registered under `key` (the VkDevice; 0: not
    // registered, the self-test's).
    static std::shared_ptr<JobService> create(std::unique_ptr<JobBackend> backend, quint64 key, const QString &label);
    // Any thread: the service of this VkDevice (null: none, or stopped).
    static std::shared_ptr<JobService> forDevice(quint64 device);
    ~JobService();
    JobService(const JobService &) = delete;
    JobService &operator=(const JobService &) = delete;

    // Any thread (the consumer: the render thread). Queues the job and wakes the thread (started at the first job).
    // False when the service failed or stopped: the consumer runs the in-frame form.
    bool submit(const std::shared_ptr<UploadJob> &job);
    // Any thread: an output nobody samples any more; the job thread destroys it at its next wake.
    void release(quint64 id);
    // The thread that destroys the device (GUI). Abandons, destroys every output, tears the backend down, joins.
    // Idempotent; the service refuses jobs afterwards.
    QJsonObject stop();
    // N3.6, checkpoint audit 11 L2: the device's destruction, before stop(), for a device its window found lost (the
    // backend's markDeviceLost; the stop record's told_device_lost and device_lost say so).
    void deviceWasLost();
    bool failed() const { return m_failed.loadAcquire() != 0; }
    bool stopped() const { return m_stopped.loadAcquire() != 0; }

    // A harness's wait (GUI thread, never the render thread): until nothing is queued, running or waiting for release,
    // or the timeout. True when idle.
    bool waitIdle(int timeoutMs);
    QJsonObject stateJson(bool withLog) const;
    // Every registered service (the devices'): their states; the harness's wait for all of them.
    static QJsonArray allStatesJson(bool withLog);
    static bool waitAllIdle(int timeoutMs);
    QString label() const { return m_label; }

    // The job thread's body (JobThread::run).
    void threadMain();
    // The self-test's control (GUI thread, before the first job): the thread's start fails (audit N38 L3).
    void failThreadStartForTest()
    {
        QMutexLocker lock(&m_mutex);
        m_failThreadStart = true;
    }

private:
    JobService(std::unique_ptr<JobBackend> backend, quint64 key, const QString &label);
    // Under m_mutex: the thread started at the first job; false when it is not running (the service then fails closed).
    bool startThread();
    void runJob(const std::shared_ptr<UploadJob> &job);
    void runReleases(const QList<quint64> &ids);
    void logJob(const UploadJob &job);
    bool idleLocked() const;

    std::unique_ptr<JobBackend> m_backend;
    const quint64 m_key;
    const QString m_label;
    std::unique_ptr<JobThread> m_thread;

    mutable QMutex m_mutex;                      // guards the members below
    QWaitCondition m_wake;                       // the job thread's park
    QWaitCondition m_idle;                       // the harness's waitIdle
    QList<std::shared_ptr<UploadJob>> m_queue;
    QList<quint64> m_releases;
    std::shared_ptr<UploadJob> m_running;
    bool m_quit = false;
    bool m_setUp = false;
    QString m_setUpError;
    QHash<quint64, qint64> m_images;             // outputs held: id -> bytes
    quint64 m_nextId = 0;
    QJsonArray m_log;                            // the last jobs (bounded)
    qint64 m_wakeups = 0;
    qint64 m_published = 0;
    qint64 m_failedJobs = 0;
    qint64 m_cancelled = 0;
    qint64 m_abandoned = 0;
    qint64 m_destroyed = 0;
    qint64 m_releasesDone = 0;
    QJsonObject m_stopRecord;

    bool m_toldDeviceLost = false;               // deviceWasLost() (audit 11 L2)
    bool m_started = false;                      // the thread was started (at the first job)
    bool m_failThreadStart = false;              // the self-test's control (L3)

    QAtomicInteger<int> m_failed { 0 };
    QAtomicInteger<int> m_stopped { 0 };
    QAtomicInteger<int> m_abandon { 0 };
    ThreadProbe m_probe;                         // D5.4 on the job thread: no Python thread state, never the GUI's
};

// GPU-free: the service's thread, latch, cancellation and teardown under a scripted backend. `scriptJson` is a list of
// steps run in order on the calling (GUI) thread (tests/test_native_core_jobs.py documents them); the result is one JSON
// object with each step's observations. Never registered under a device.
QByteArray jobServiceSelfTestJson(const QByteArray &scriptJson);

// The monotonic clock the job times use (ns).
qint64 jobClockNs();

} // namespace srpss_core
