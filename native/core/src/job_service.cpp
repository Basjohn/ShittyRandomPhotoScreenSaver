// The async job service (D9, N3.8): job_service.h has the contract.
#include "job_service.h"

#include "mode_content.h" // TextureImage, rgba8TextureBytes

#include <rhi/qrhi.h>
#include <rhi/qrhi_platform.h>

#include <QtCore/QDeadlineTimer>
#include <QtCore/QElapsedTimer>
#include <QtCore/QJsonDocument>
#include <QtCore/QThread>
#include <QtGui/QVulkanInstance>

#ifndef VK_NO_PROTOTYPES
#define VK_NO_PROTOTYPES // the module never links vulkan-1.lib (vulkan_context.cpp)
#endif
#include <vulkan/vulkan.h>

namespace srpss_core {

// The job thread: no event loop, its body is the service's (a QThread so that Qt names it and onGuiThread holds).
class JobThread final : public QThread
{
public:
    explicit JobThread(JobService *service) : m_service(service) {}

protected:
    void run() override { m_service->threadMain(); }

private:
    JobService *m_service; // outlives the thread: stop() joins before the service goes
};

namespace {

QAtomicInteger<int> g_services { 0 };
QAtomicInteger<int> g_threads { 0 };
QAtomicInteger<int> g_queued { 0 };
QAtomicInteger<int> g_running { 0 };
QAtomicInteger<int> g_images { 0 };
QAtomicInteger<qint64> g_imageBytes { 0 };
QAtomicInteger<int> g_releasesPending { 0 };
QAtomicInteger<qint64> g_wakeups { 0 };

constexpr int kLogEntries = 64;

QMutex &registryMutex()
{
    static QMutex mutex;
    return mutex;
}

QHash<quint64, std::weak_ptr<JobService>> &registry()
{
    static QHash<quint64, std::weak_ptr<JobService>> services;
    return services;
}

const QElapsedTimer &jobClock()
{
    static const QElapsedTimer timer = []() {
        QElapsedTimer t;
        t.start();
        return t;
    }();
    return timer;
}

} // namespace

qint64 jobClockNs()
{
    return jobClock().nsecsElapsed();
}

QString jobStateName(JobState state)
{
    switch (state) {
    case JobState::Queued: return QStringLiteral("queued");
    case JobState::Running: return QStringLiteral("running");
    case JobState::Done: return QStringLiteral("done");
    case JobState::Failed: return QStringLiteral("failed");
    case JobState::Cancelled: return QStringLiteral("cancelled");
    case JobState::Abandoned: return QStringLiteral("abandoned");
    }
    return QStringLiteral("unknown");
}

bool jobTerminal(JobState state)
{
    return state != JobState::Queued && state != JobState::Running;
}

// ------------------------------------------------------------------------------------------------- UploadJob

UploadJob::UploadJob(const QByteArray &nameIn, quint64 generationIn, const QSharedPointer<TextureImage> &pixelsIn,
                     std::shared_ptr<JobNotifier> notifier)
    : name(nameIn),
      generation(generationIn),
      size(pixelsIn ? pixelsIn->size : QSize()),
      mips(pixelsIn ? pixelsIn->mips : false),
      m_pixels(pixelsIn),
      m_notifier(std::move(notifier))
{
}

UploadJob::~UploadJob() = default;

bool UploadJob::start()
{
    return m_state.testAndSetOrdered(int(JobState::Queued), int(JobState::Running));
}

bool UploadJob::publish()
{
    return m_state.testAndSetOrdered(int(JobState::Running), int(JobState::Done));
}

void UploadJob::fail(const QString &why)
{
    error = why;
    if (!m_state.testAndSetOrdered(int(JobState::Running), int(JobState::Failed)))
        m_state.testAndSetOrdered(int(JobState::Queued), int(JobState::Failed));
}

void UploadJob::abandon()
{
    if (!m_state.testAndSetOrdered(int(JobState::Running), int(JobState::Abandoned)))
        m_state.testAndSetOrdered(int(JobState::Queued), int(JobState::Abandoned));
}

QSharedPointer<TextureImage> UploadJob::pixels() const
{
    QMutexLocker lock(&m_pixelsMutex);
    return m_pixels;
}

void UploadJob::dropPixels()
{
    QSharedPointer<TextureImage> dropped;
    {
        QMutexLocker lock(&m_pixelsMutex);
        dropped.swap(m_pixels);
    }
    // `dropped` goes here, outside the lock: the core's copy is freed on the job thread.
}

QSharedPointer<TextureImage> UploadJob::takePixels()
{
    QSharedPointer<TextureImage> taken;
    QMutexLocker lock(&m_pixelsMutex);
    taken.swap(m_pixels);
    return taken;
}

void UploadJob::notifyFinished()
{
    if (m_notifier && m_notified.testAndSetOrdered(0, 1))
        m_notifier->jobFinished();
}

UploadJob::Cancelled UploadJob::cancel()
{
    for (;;) {
        const int s = m_state.loadAcquire();
        if (s == int(JobState::Queued) || s == int(JobState::Running)) {
            if (m_state.testAndSetOrdered(s, int(JobState::Cancelled))) {
                // A queued job never runs; its pixels go now. A running one drops whatever it makes on its own thread.
                if (s == int(JobState::Queued))
                    dropPixels();
                return Cancelled::Pending;
            }
            continue; // the job thread moved it meanwhile: read again
        }
        if (s == int(JobState::Done))
            return Cancelled::Published;
        return Cancelled::Over;
    }
}

QJsonObject UploadJob::toJson() const
{
    QJsonObject o;
    o.insert(QStringLiteral("name"), QString::fromLatin1(name));
    o.insert(QStringLiteral("generation"), double(generation));
    o.insert(QStringLiteral("size"), QJsonArray { size.width(), size.height() });
    o.insert(QStringLiteral("mips"), mips);
    o.insert(QStringLiteral("state"), jobStateName(state()));
    o.insert(QStringLiteral("output"), double(outputId));
    o.insert(QStringLiteral("output_bytes"), double(outputBytes));
    if (!error.isEmpty())
        o.insert(QStringLiteral("error"), error);
    const auto ms = [](qint64 a, qint64 b) { return (a > 0 && b > 0) ? double(b - a) / 1e6 : -1.0; };
    o.insert(QStringLiteral("queued_ms"), ms(submittedNs, startedNs));     // submitted -> taken by the job thread
    o.insert(QStringLiteral("record_ms"), ms(startedNs, recordedNs));      // the CPU half on the job thread
    o.insert(QStringLiteral("gpu_wait_ms"), ms(recordedNs, completedNs));  // its own GPU work
    o.insert(QStringLiteral("latency_ms"), ms(submittedNs, finishedNs));   // submitted -> published (the latch)
    return o;
}

// ------------------------------------------------------------------------------------------------- counts

JobCounts jobCounts()
{
    JobCounts c;
    c.services = g_services.loadRelaxed();
    c.threads = g_threads.loadRelaxed();
    c.queued = g_queued.loadRelaxed();
    c.running = g_running.loadRelaxed();
    c.images = g_images.loadRelaxed();
    c.imageBytes = g_imageBytes.loadRelaxed();
    c.releasesPending = g_releasesPending.loadRelaxed();
    c.wakeups = g_wakeups.loadRelaxed();
    return c;
}

QJsonObject jobCountsJson()
{
    const JobCounts c = jobCounts();
    QJsonObject o;
    o.insert(QStringLiteral("job_services"), c.services);
    o.insert(QStringLiteral("job_threads"), c.threads);
    o.insert(QStringLiteral("jobs_queued"), c.queued);
    o.insert(QStringLiteral("jobs_running"), c.running);
    o.insert(QStringLiteral("job_images"), c.images);
    o.insert(QStringLiteral("job_image_bytes"), double(c.imageBytes));
    o.insert(QStringLiteral("job_releases_pending"), c.releasesPending);
    o.insert(QStringLiteral("job_wakeups"), double(c.wakeups));
    return o;
}

// ------------------------------------------------------------------------------------------------- the service

JobService::JobService(std::unique_ptr<JobBackend> backend, quint64 key, const QString &label)
    : m_backend(std::move(backend)), m_key(key), m_label(label), m_thread(new JobThread(this))
{
    m_thread->setObjectName(QStringLiteral("srpss-core-jobs"));
    g_services.fetchAndAddRelaxed(1);
}

std::shared_ptr<JobService> JobService::create(std::unique_ptr<JobBackend> backend, quint64 key, const QString &label)
{
    std::shared_ptr<JobService> service(new JobService(std::move(backend), key, label));
    if (key) {
        QMutexLocker lock(&registryMutex());
        registry().insert(key, service);
    }
    return service;
}

std::shared_ptr<JobService> JobService::forDevice(quint64 device)
{
    if (!device)
        return {};
    QMutexLocker lock(&registryMutex());
    std::shared_ptr<JobService> service = registry().value(device).lock();
    if (service && service->stopped())
        return {};
    return service;
}

JobService::~JobService()
{
    stop();
    g_services.fetchAndAddRelaxed(-1);
}

bool JobService::submit(const std::shared_ptr<UploadJob> &job)
{
    if (!job || failed() || stopped())
        return false;
    QMutexLocker lock(&m_mutex);
    if (m_quit)
        return false;
    job->submittedNs = jobClockNs();
    m_queue.append(job);
    g_queued.fetchAndAddRelaxed(1);
    if (!m_started) {
        // The first job starts the thread (D9 as built point 1: a device that never uploads holds no thread).
        m_started = true;
        m_thread->start();
    }
    m_wake.wakeOne();
    return true;
}

void JobService::release(quint64 id)
{
    if (!id)
        return;
    QMutexLocker lock(&m_mutex);
    if (m_quit || !m_started)
        return; // the teardown destroys every output (or none exists)
    m_releases.append(id);
    g_releasesPending.fetchAndAddRelaxed(1);
    m_wake.wakeOne();
}

bool JobService::idleLocked() const
{
    return m_queue.isEmpty() && m_releases.isEmpty() && !m_running;
}

bool JobService::waitIdle(int timeoutMs)
{
    QDeadlineTimer deadline(timeoutMs);
    QMutexLocker lock(&m_mutex);
    while (!idleLocked() && !m_quit) {
        if (!m_idle.wait(&m_mutex, deadline))
            break;
    }
    return idleLocked();
}

void JobService::threadMain()
{
    m_probe.hit();
    g_threads.fetchAndAddRelaxed(1);
    QMutexLocker lock(&m_mutex);
    for (;;) {
        while (m_queue.isEmpty() && m_releases.isEmpty() && !m_quit) {
            m_idle.wakeAll();
            m_wake.wait(&m_mutex); // parked: no timeout, no polling; every return counted
            ++m_wakeups;
            g_wakeups.fetchAndAddRelaxed(1);
        }
        if (m_quit)
            break;
        QList<quint64> releases;
        releases.swap(m_releases);
        std::shared_ptr<UploadJob> job;
        if (!m_queue.isEmpty()) {
            job = m_queue.takeFirst();
            g_queued.fetchAndAddRelaxed(-1);
            m_running = job;
            g_running.fetchAndAddRelaxed(1);
        }
        lock.unlock();
        m_probe.hit();
        if (!releases.isEmpty())
            runReleases(releases);
        if (job)
            runJob(job);
        lock.relock();
        if (job) {
            m_running.reset();
            g_running.fetchAndAddRelaxed(-1);
        }
    }
    // Quiesce (stop()): queued jobs are abandoned, pending releases are covered by the teardown below.
    QList<std::shared_ptr<UploadJob>> queued;
    queued.swap(m_queue);
    g_queued.fetchAndAddRelaxed(-int(queued.size()));
    const int releases = int(m_releases.size());
    m_releases.clear();
    g_releasesPending.fetchAndAddRelaxed(-releases);
    const bool setUp = m_setUp;
    lock.unlock();
    for (const std::shared_ptr<UploadJob> &job : queued) {
        job->abandon();
        logJob(*job);
    }
    if (setUp)
        m_backend->tearDown(); // every output it holds, then its QRhi (its own queue idle)
    lock.relock();
    m_abandoned += queued.size();
    m_destroyed += m_images.size();
    for (auto it = m_images.cbegin(); it != m_images.cend(); ++it) {
        g_images.fetchAndAddRelaxed(-1);
        g_imageBytes.fetchAndAddRelaxed(-it.value());
    }
    m_images.clear();
    m_idle.wakeAll();
    lock.unlock();
    g_threads.fetchAndAddRelaxed(-1);
}

void JobService::runJob(const std::shared_ptr<UploadJob> &job)
{
    if (!job->start()) {
        // Cancelled (or abandoned) while queued: it never runs.
        {
            QMutexLocker lock(&m_mutex);
            ++m_cancelled;
        }
        logJob(*job);
        return;
    }
    job->startedNs = jobClockNs();
    bool setUp = false;
    QString setUpError;
    {
        QMutexLocker lock(&m_mutex);
        setUp = m_setUp;
        setUpError = m_setUpError;
    }
    if (!setUp && setUpError.isEmpty()) {
        QString error;
        setUp = m_backend->setUp(&error);
        if (!setUp)
            setUpError = error.isEmpty() ? QStringLiteral("the job backend could not be set up") : error;
        QMutexLocker lock(&m_mutex);
        m_setUp = setUp;
        m_setUpError = setUpError;
        if (!setUp)
            m_failed.storeRelease(1); // fails closed: every later job runs in its in-frame form
    }
    if (!setUp) {
        job->finishedNs = jobClockNs(); // every field before the state's edge (the consumer reads after it)
        job->fail(QStringLiteral("the job service failed: %1").arg(setUpError));
        {
            QMutexLocker lock(&m_mutex);
            ++m_failedJobs;
        }
        job->notifyFinished();
        logJob(*job);
        return;
    }
    quint64 id = 0;
    {
        QMutexLocker lock(&m_mutex);
        id = ++m_nextId;
    }
    QString error;
    if (!m_backend->upload(*job, id, &error)) {
        job->finishedNs = jobClockNs();
        job->fail(error);
        {
            QMutexLocker lock(&m_mutex);
            ++m_failedJobs;
        }
        job->notifyFinished();
        logJob(*job);
        return;
    }
    job->completedNs = jobClockNs();
    if (m_abandon.loadAcquire()) {
        // D9 point 6: a job in flight at the service's stop is dropped unpublished.
        m_backend->destroy(id);
        m_backend->flush();
        job->abandon();
        {
            QMutexLocker lock(&m_mutex);
            ++m_abandoned;
            ++m_destroyed;
        }
        logJob(*job);
        return;
    }
    {
        QMutexLocker lock(&m_mutex);
        m_images.insert(id, job->outputBytes);
        g_images.fetchAndAddRelaxed(1);
        g_imageBytes.fetchAndAddRelaxed(job->outputBytes);
    }
    job->finishedNs = jobClockNs();
    if (!job->publish()) {
        // Cancelled while it ran: Qt never saw its output, which goes now.
        {
            QMutexLocker lock(&m_mutex);
            m_images.remove(id);
            g_images.fetchAndAddRelaxed(-1);
            g_imageBytes.fetchAndAddRelaxed(-job->outputBytes);
            ++m_cancelled;
            ++m_destroyed;
        }
        m_backend->destroy(id);
        m_backend->flush();
        logJob(*job);
        return;
    }
    {
        QMutexLocker lock(&m_mutex);
        ++m_published;
    }
    job->notifyFinished(); // the latch is set: the consumer's item asks for a frame
    logJob(*job);
}

void JobService::runReleases(const QList<quint64> &ids)
{
    int destroyed = 0;
    for (const quint64 id : ids) {
        bool held = false;
        {
            QMutexLocker lock(&m_mutex);
            const auto it = m_images.constFind(id);
            if (it != m_images.cend()) {
                held = true;
                g_images.fetchAndAddRelaxed(-1);
                g_imageBytes.fetchAndAddRelaxed(-it.value());
                m_images.erase(it);
            }
        }
        if (held) {
            m_backend->destroy(id);
            ++destroyed;
        }
    }
    if (destroyed)
        m_backend->flush();
    QMutexLocker lock(&m_mutex);
    m_destroyed += destroyed;
    m_releasesDone += ids.size();
    g_releasesPending.fetchAndAddRelaxed(-int(ids.size()));
}

void JobService::logJob(const UploadJob &job)
{
    const QJsonObject entry = job.toJson();
    QMutexLocker lock(&m_mutex);
    m_log.append(entry);
    while (m_log.size() > kLogEntries)
        m_log.removeAt(0);
}

QJsonObject JobService::stop()
{
    if (!m_stopped.testAndSetOrdered(0, 1)) {
        QMutexLocker lock(&m_mutex);
        return m_stopRecord;
    }
    if (m_key) {
        QMutexLocker lock(&registryMutex());
        registry().remove(m_key);
    }
    QElapsedTimer timer;
    timer.start();
    QJsonObject o;
    bool started = false;
    {
        QMutexLocker lock(&m_mutex);
        o.insert(QStringLiteral("queued_at_stop"), int(m_queue.size()));
        o.insert(QStringLiteral("running_at_stop"), m_running ? QJsonValue(m_running->toJson()) : QJsonValue());
        m_quit = true;
        m_abandon.storeRelease(1);
        started = m_started;
        m_wake.wakeAll();
    }
    m_backend->stopping();
    if (started)
        m_thread->wait(); // the join (D1's barrier, in the device's destruction)
    QMutexLocker lock(&m_mutex);
    o.insert(QStringLiteral("thread_started"), started);
    o.insert(QStringLiteral("quiesce_ms"), double(timer.nsecsElapsed()) / 1e6);
    o.insert(QStringLiteral("published"), double(m_published));
    o.insert(QStringLiteral("failed"), double(m_failedJobs));
    o.insert(QStringLiteral("cancelled"), double(m_cancelled));
    o.insert(QStringLiteral("abandoned"), double(m_abandoned));
    o.insert(QStringLiteral("destroyed"), double(m_destroyed));
    o.insert(QStringLiteral("wakeups"), double(m_wakeups));
    o.insert(QStringLiteral("images_left"), int(m_images.size()));
    m_stopRecord = o;
    return o;
}

QJsonObject JobService::stateJson(bool withLog) const
{
    QJsonObject o;
    o.insert(QStringLiteral("label"), m_label);
    o.insert(QStringLiteral("failed"), failed());
    o.insert(QStringLiteral("stopped"), stopped());
    o.insert(QStringLiteral("thread_calls"), m_probe.calls.loadRelaxed());
    o.insert(QStringLiteral("thread_calls_on_gui_thread"), m_probe.callsOnGuiThread.loadRelaxed());
    o.insert(QStringLiteral("thread_calls_with_python_thread_state"),
             m_probe.callsWithPythonThreadState.loadRelaxed());
    QMutexLocker lock(&m_mutex);
    o.insert(QStringLiteral("started"), m_started);
    o.insert(QStringLiteral("set_up"), m_setUp);
    o.insert(QStringLiteral("set_up_error"), m_setUpError);
    o.insert(QStringLiteral("queued"), int(m_queue.size()));
    o.insert(QStringLiteral("running"), m_running ? QJsonValue(m_running->toJson()) : QJsonValue());
    o.insert(QStringLiteral("releases_pending"), int(m_releases.size()));
    o.insert(QStringLiteral("images"), int(m_images.size()));
    o.insert(QStringLiteral("wakeups"), double(m_wakeups));
    o.insert(QStringLiteral("published"), double(m_published));
    o.insert(QStringLiteral("failed_jobs"), double(m_failedJobs));
    o.insert(QStringLiteral("cancelled"), double(m_cancelled));
    o.insert(QStringLiteral("abandoned"), double(m_abandoned));
    o.insert(QStringLiteral("destroyed"), double(m_destroyed));
    o.insert(QStringLiteral("releases_done"), double(m_releasesDone));
    o.insert(QStringLiteral("backend"), m_backend->stateJson());
    if (!m_stopRecord.isEmpty())
        o.insert(QStringLiteral("stop"), m_stopRecord);
    if (withLog)
        o.insert(QStringLiteral("log"), m_log);
    return o;
}

namespace {

QList<std::shared_ptr<JobService>> registeredServices()
{
    QList<std::shared_ptr<JobService>> services;
    QMutexLocker lock(&registryMutex());
    for (auto it = registry().cbegin(); it != registry().cend(); ++it) {
        if (std::shared_ptr<JobService> service = it.value().lock())
            services.append(service);
    }
    return services;
}

} // namespace

QJsonArray JobService::allStatesJson(bool withLog)
{
    QJsonArray out;
    for (const std::shared_ptr<JobService> &service : registeredServices())
        out.append(service->stateJson(withLog));
    return out;
}

bool JobService::waitAllIdle(int timeoutMs)
{
    QDeadlineTimer deadline(timeoutMs);
    bool idle = true;
    for (const std::shared_ptr<JobService> &service : registeredServices())
        idle = service->waitIdle(int(qMax<qint64>(0, deadline.remainingTime()))) && idle;
    return idle;
}

// ------------------------------------------------------------------------------------------------- the QRhi backend

namespace {

class RhiUploadBackend final : public JobBackend
{
public:
    explicit RhiUploadBackend(const JobDevice &device) : m_device(device) {}
    ~RhiUploadBackend() override
    {
        // tearDown ran on the job thread (the service's stop); nothing of a QRhi is touched here.
    }

    bool setUp(QString *error) override
    {
        if (!m_device.instance || !m_device.device || !m_device.physicalDevice) {
            *error = QStringLiteral("no Vulkan instance or device for the job QRhi");
            return false;
        }
        QRhiVulkanInitParams params;
        params.inst = m_device.instance;
        QRhiVulkanNativeHandles handles;
        handles.physDev = reinterpret_cast<VkPhysicalDevice>(quintptr(m_device.physicalDevice));
        handles.dev = reinterpret_cast<VkDevice>(quintptr(m_device.device));
        handles.gfxQueueFamilyIdx = m_device.family;
        handles.gfxQueueIdx = m_device.queueIndex;
        handles.vmemAllocator = nullptr; // its own allocator: Qt's has no mutex (facts C1)
        QRhi::Flags flags;
        if (m_device.debugMarkers)
            flags |= QRhi::EnableDebugMarkers;
        QElapsedTimer timer;
        timer.start();
        m_rhi.reset(QRhi::create(QRhi::Vulkan, &params, flags, &handles));
        QJsonObject facts;
        facts.insert(QStringLiteral("create_ms"), double(timer.nsecsElapsed()) / 1e6);
        if (!m_rhi) {
            setFacts(facts);
            *error = QStringLiteral("QRhi::create(Vulkan) on the module's device and the job queue failed");
            return false;
        }
        const auto *native = static_cast<const QRhiVulkanNativeHandles *>(m_rhi->nativeHandles());
        const bool ours = native && native->dev == handles.dev && native->gfxQueueFamilyIdx == m_device.family
            && native->gfxQueueIdx == m_device.queueIndex;
        facts.insert(QStringLiteral("on_our_device_and_queue"), ours);
        facts.insert(QStringLiteral("queue_family"), qint64(m_device.family));
        facts.insert(QStringLiteral("queue_index"), qint64(m_device.queueIndex));
        facts.insert(QStringLiteral("debug_markers"), m_device.debugMarkers);
        setFacts(facts);
        if (!ours) {
            m_rhi.reset();
            *error = QStringLiteral("the job QRhi is not on the module's device and the job queue");
            return false;
        }
        return true;
    }

    bool upload(UploadJob &job, quint64 id, QString *error) override
    {
        const QSharedPointer<TextureImage> pixels = job.pixels();
        if (!pixels) {
            *error = QStringLiteral("the job has no pixels");
            return false;
        }
        const QRhiTexture::Flags flags = job.mips ? (QRhiTexture::MipMapped | QRhiTexture::UsedWithGenerateMips)
                                                  : QRhiTexture::Flags();
        std::unique_ptr<QRhiTexture> texture(m_rhi->newTexture(QRhiTexture::RGBA8, job.size, 1, flags));
        texture->setName(QByteArrayLiteral("srpss core job texture ") + job.name);
        if (!texture->create()) {
            *error = QStringLiteral("%1 could not be created at %2 x %3 on the job queue")
                         .arg(QString::fromLatin1(job.name)).arg(job.size.width()).arg(job.size.height());
            return false;
        }
        QRhiCommandBuffer *cb = nullptr;
        if (m_rhi->beginOffscreenFrame(&cb) != QRhi::FrameOpSuccess || !cb) {
            *error = QStringLiteral("beginOffscreenFrame failed on the job QRhi");
            return false;
        }
        QRhiResourceUpdateBatch *updates = m_rhi->nextResourceUpdateBatch();
        const QRhiTextureSubresourceUploadDescription level(pixels->pixels); // implicitly shared, no copy
        updates->uploadTexture(texture.get(), QRhiTextureUploadDescription(QRhiTextureUploadEntry(0, 0, level)));
        if (job.mips)
            updates->generateMips(texture.get());
        cb->resourceUpdate(updates); // the staging copy, on this thread
        if (m_rhi->endOffscreenFrame() != QRhi::FrameOpSuccess) {
            *error = QStringLiteral("endOffscreenFrame failed on the job QRhi");
            m_rhi->finish();
            return false;
        }
        job.recordedNs = jobClockNs();
        job.dropPixels(); // the core's copy goes: the upload is in the staging buffer
        m_rhi->finish();  // the completion edge: this QRhi's own queue idle (facts C2)
        const QRhiTexture::NativeTexture native = texture->nativeTexture();
        job.outputId = id;
        job.nativeImage = native.object;
        job.nativeLayout = native.layout;
        job.outputBytes = rgba8TextureBytes(job.size, job.mips);
        m_textures.insert(id, texture.release());
        QMutexLocker lock(&m_factsMutex);
        ++m_uploads;
        return true;
    }

    void destroy(quint64 id) override
    {
        delete m_textures.take(id); // QRhi defers the native release; flush() runs it
    }

    void flush() override
    {
        if (m_rhi)
            m_rhi->finish(); // outside a frame: waits for its queue, then runs its deferred releases
    }

    void tearDown() override
    {
        for (auto it = m_textures.begin(); it != m_textures.end(); ++it)
            delete it.value();
        m_textures.clear();
        if (m_rhi) {
            m_rhi->finish();
            m_rhi.reset(); // QRhiVulkan::destroy: its own queue idle, its pools and allocator; never the device
        }
        QMutexLocker lock(&m_factsMutex);
        m_tornDown = true;
    }

    QJsonObject stateJson() const override
    {
        QMutexLocker lock(&m_factsMutex);
        QJsonObject o = m_facts;
        o.insert(QStringLiteral("kind"), QStringLiteral("qrhi_vulkan"));
        o.insert(QStringLiteral("uploads"), double(m_uploads));
        o.insert(QStringLiteral("torn_down"), m_tornDown);
        return o;
    }

private:
    void setFacts(const QJsonObject &facts)
    {
        QMutexLocker lock(&m_factsMutex);
        m_facts = facts;
    }

    JobDevice m_device;
    std::unique_ptr<QRhi> m_rhi;                 // job thread only
    QHash<quint64, QRhiTexture *> m_textures;    // job thread only (owned)
    mutable QMutex m_factsMutex;                 // guards the report below (read from the GUI thread)
    QJsonObject m_facts;
    qint64 m_uploads = 0;
    bool m_tornDown = false;
};

} // namespace

std::unique_ptr<JobBackend> createRhiUploadBackend(const JobDevice &device)
{
    return std::unique_ptr<JobBackend>(new RhiUploadBackend(device));
}

// ------------------------------------------------------------------------------------------------- the self-test

namespace {

// A GPU-free backend whose "GPU wait" a script holds and releases, and whose next upload or set-up it can fail.
class ScriptedBackend final : public JobBackend
{
public:
    bool setUp(QString *error) override
    {
        QMutexLocker lock(&m_mutex);
        ++m_setUps;
        if (m_failSetUp) {
            *error = QStringLiteral("scripted set-up failure");
            return false;
        }
        return true;
    }

    bool upload(UploadJob &job, quint64 id, QString *error) override
    {
        {
            QMutexLocker lock(&m_mutex);
            if (m_failNext) {
                m_failNext = false;
                *error = QStringLiteral("scripted upload failure");
                return false; // nothing submitted: the pixels stay
            }
        }
        if (!job.pixels()) {
            *error = QStringLiteral("the job has no pixels");
            return false;
        }
        job.recordedNs = jobClockNs();
        job.dropPixels();
        QMutexLocker lock(&m_mutex);
        ++m_entered;
        m_changed.wakeAll();
        while (m_hold)
            m_changed.wait(&m_mutex); // the "GPU wait" the script holds
        job.outputId = id;
        job.nativeImage = 0x1000 + id;
        job.nativeLayout = 7;
        job.outputBytes = rgba8TextureBytes(job.size, job.mips);
        m_outputs.insert(id, true);
        ++m_uploads;
        return true;
    }

    void destroy(quint64 id) override
    {
        QMutexLocker lock(&m_mutex);
        if (m_outputs.remove(id))
            ++m_destroyed;
    }

    void flush() override
    {
        QMutexLocker lock(&m_mutex);
        ++m_flushes;
    }

    void tearDown() override
    {
        QMutexLocker lock(&m_mutex);
        m_destroyedAtTearDown += int(m_outputs.size());
        m_outputs.clear();
        m_tornDown = true;
    }

    void stopping() override
    {
        hold(false); // the held "GPU wait" completes: the job in flight is then abandoned by the service
    }

    QJsonObject stateJson() const override
    {
        QMutexLocker lock(&m_mutex);
        QJsonObject o;
        o.insert(QStringLiteral("kind"), QStringLiteral("scripted"));
        o.insert(QStringLiteral("set_ups"), m_setUps);
        o.insert(QStringLiteral("uploads"), m_uploads);
        o.insert(QStringLiteral("outputs"), int(m_outputs.size()));
        o.insert(QStringLiteral("destroyed"), m_destroyed);
        o.insert(QStringLiteral("destroyed_at_teardown"), m_destroyedAtTearDown);
        o.insert(QStringLiteral("flushes"), m_flushes);
        o.insert(QStringLiteral("torn_down"), m_tornDown);
        return o;
    }

    // The script's controls (GUI thread).
    void hold(bool on)
    {
        QMutexLocker lock(&m_mutex);
        m_hold = on;
        m_changed.wakeAll();
    }
    void failNext()
    {
        QMutexLocker lock(&m_mutex);
        m_failNext = true;
    }
    void failSetUp()
    {
        QMutexLocker lock(&m_mutex);
        m_failSetUp = true;
    }
    // Until `count` uploads have entered their GPU wait, or the timeout.
    bool waitEntered(int count, int timeoutMs)
    {
        QDeadlineTimer deadline(timeoutMs);
        QMutexLocker lock(&m_mutex);
        while (m_entered < count) {
            if (!m_changed.wait(&m_mutex, deadline))
                break;
        }
        return m_entered >= count;
    }

private:
    mutable QMutex m_mutex;
    QWaitCondition m_changed;
    bool m_hold = false;
    bool m_failNext = false;
    bool m_failSetUp = false;
    int m_entered = 0;
    int m_setUps = 0;
    int m_uploads = 0;
    int m_destroyed = 0;
    int m_destroyedAtTearDown = 0;
    int m_flushes = 0;
    bool m_tornDown = false;
    QHash<quint64, bool> m_outputs;
};

class CountingNotifier final : public JobNotifier
{
public:
    void jobFinished() override { calls.fetchAndAddRelaxed(1); }
    QAtomicInteger<int> calls { 0 };
};

} // namespace

QByteArray jobServiceSelfTestJson(const QByteArray &scriptJson)
{
    QJsonObject out;
    const QJsonDocument document = QJsonDocument::fromJson(scriptJson);
    if (!document.isArray()) {
        out.insert(QStringLiteral("error"), QStringLiteral("the script is a JSON list of steps"));
        return QJsonDocument(out).toJson(QJsonDocument::Compact);
    }
    auto *backend = new ScriptedBackend;
    std::shared_ptr<JobService> service = JobService::create(std::unique_ptr<JobBackend>(backend), 0,
                                                             QStringLiteral("self-test"));
    const std::shared_ptr<CountingNotifier> notifier = std::make_shared<CountingNotifier>();
    QHash<QString, std::shared_ptr<UploadJob>> jobs;
    QJsonArray steps;
    for (const QJsonValue &value : document.array()) {
        const QJsonObject step = value.toObject();
        const QString op = step.value(QStringLiteral("op")).toString();
        const QString name = step.value(QStringLiteral("name")).toString();
        QJsonObject seen;
        seen.insert(QStringLiteral("op"), op);
        if (!name.isEmpty())
            seen.insert(QStringLiteral("name"), name);
        if (op == QLatin1String("submit")) {
            const int side = step.value(QStringLiteral("side")).toInt(4);
            const QSize size(side, side);
            const QByteArray pixels(qsizetype(side) * side * 4, char(step.value(QStringLiteral("fill")).toInt(7)));
            const auto image = QSharedPointer<TextureImage>::create(pixels, size,
                                                                     step.value(QStringLiteral("mips")).toBool());
            auto job = std::make_shared<UploadJob>(name.toLatin1(), quint64(step.value(QStringLiteral("generation"))
                                                                               .toInt(1)),
                                                   image, notifier);
            jobs.insert(name, job);
            seen.insert(QStringLiteral("submitted"), service->submit(job));
        } else if (op == QLatin1String("hold")) {
            backend->hold(true);
        } else if (op == QLatin1String("go")) {
            backend->hold(false);
        } else if (op == QLatin1String("fail_next")) {
            backend->failNext();
        } else if (op == QLatin1String("fail_setup")) {
            backend->failSetUp();
        } else if (op == QLatin1String("wait_entered")) {
            seen.insert(QStringLiteral("entered"), backend->waitEntered(step.value(QStringLiteral("count")).toInt(1),
                                                                        step.value(QStringLiteral("timeout_ms"))
                                                                            .toInt(5000)));
        } else if (op == QLatin1String("wait_idle")) {
            seen.insert(QStringLiteral("idle"), service->waitIdle(step.value(QStringLiteral("timeout_ms")).toInt(5000)));
        } else if (op == QLatin1String("cancel")) {
            const std::shared_ptr<UploadJob> job = jobs.value(name);
            const UploadJob::Cancelled result = job ? job->cancel() : UploadJob::Cancelled::Over;
            seen.insert(QStringLiteral("result"), result == UploadJob::Cancelled::Pending ? QStringLiteral("pending")
                                                  : result == UploadJob::Cancelled::Published
                                                      ? QStringLiteral("published")
                                                      : QStringLiteral("over"));
            if (job && result == UploadJob::Cancelled::Published && step.value(QStringLiteral("release")).toBool(true))
                service->release(job->outputId); // the consumer's duty for an output it was handed
        } else if (op == QLatin1String("release")) {
            const std::shared_ptr<UploadJob> job = jobs.value(name);
            if (job)
                service->release(job->outputId);
        } else if (op == QLatin1String("take_pixels")) {
            const std::shared_ptr<UploadJob> job = jobs.value(name);
            seen.insert(QStringLiteral("pixels"), job && !job->takePixels().isNull());
        } else if (op == QLatin1String("rest")) {
            const qint64 before = jobCounts().wakeups;
            QThread::msleep(ulong(step.value(QStringLiteral("ms")).toInt(200)));
            seen.insert(QStringLiteral("wakeups_during_rest"), double(jobCounts().wakeups - before));
        } else if (op == QLatin1String("stop")) {
            seen.insert(QStringLiteral("stop"), service->stop());
            seen.insert(QStringLiteral("submit_after_stop"),
                        service->submit(std::make_shared<UploadJob>(
                            QByteArrayLiteral("late"), 99,
                            QSharedPointer<TextureImage>::create(QByteArray(64, 0), QSize(4, 4), false), notifier)));
        } else if (op != QLatin1String("state")) {
            seen.insert(QStringLiteral("error"), QStringLiteral("unknown op"));
        }
        // A job's fields are read only after the job thread's own edge (done, failed, abandoned: written before it);
        // otherwise (queued, running, or cancelled by the consumer while the job thread may still run it) its state and
        // whether it still holds its pixels.
        QJsonObject states;
        for (auto it = jobs.cbegin(); it != jobs.cend(); ++it) {
            const JobState state = it.value()->state();
            const bool settled = state == JobState::Done || state == JobState::Failed || state == JobState::Abandoned;
            QJsonObject j = settled ? it.value()->toJson() : QJsonObject();
            j.insert(QStringLiteral("state"), jobStateName(state));
            j.insert(QStringLiteral("pixels_held"), !it.value()->pixels().isNull());
            states.insert(it.key(), j);
        }
        seen.insert(QStringLiteral("jobs"), states);
        seen.insert(QStringLiteral("service"), service->stateJson(false));
        seen.insert(QStringLiteral("counts"), jobCountsJson());
        seen.insert(QStringLiteral("notified"), notifier->calls.loadRelaxed());
        steps.append(seen);
    }
    out.insert(QStringLiteral("steps"), steps);
    out.insert(QStringLiteral("final_stop"), service->stop());
    jobs.clear();
    service.reset();
    out.insert(QStringLiteral("counts_after"), jobCountsJson());
    return QJsonDocument(out).toJson(QJsonDocument::Compact);
}

} // namespace srpss_core
