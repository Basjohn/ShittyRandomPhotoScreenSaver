// The async job service (D9, N3.8): job_service.h has the contract.
#include "job_service.h"
#include "rhi_owned.h"

#include "mode_content.h" // TextureImage, rgba8TextureBytes

#include <rhi/qrhi.h>
#include <rhi/qrhi_platform.h>

#include <QtCore/QDeadlineTimer>
#include <QtCore/QElapsedTimer>
#include <QtCore/QJsonDocument>
#include <QtCore/QThread>
#include <QtGui/QVulkanFunctions>
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
      format(pixelsIn ? pixelsIn->format : ModeTextureFormat::RGBA8),
      m_pixels(pixelsIn),
      m_notifier(std::move(notifier))
{
}

UploadJob::UploadJob(const QByteArray &nameIn, quint64 generationIn, const QSharedPointer<TextureImage> &pixelsIn,
                     std::shared_ptr<const FieldRecipe> recipeIn, std::shared_ptr<JobNotifier> notifier)
    : name(nameIn),
      generation(generationIn),
      size(pixelsIn ? pixelsIn->size : QSize()),
      mips(false),
      format(ModeTextureFormat::RGBA8),
      recipe(std::move(recipeIn)),
      m_pixels(pixelsIn),
      m_notifier(std::move(notifier))
{
}

UploadJob::~UploadJob() = default;

int UploadJob::outputCount() const
{
    return recipe ? int(recipe->outputs.size()) : 1;
}

quint64 UploadJob::outputIdOf(int index) const
{
    if (!recipe)
        return index == 0 ? outputId : 0;
    return index >= 0 && index < outputCount() ? fieldOutputs[index].id : 0;
}

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

QJsonObject UploadJob::briefJson() const
{
    QJsonObject o;
    o.insert(QStringLiteral("name"), QString::fromLatin1(name));
    o.insert(QStringLiteral("generation"), double(generation));
    o.insert(QStringLiteral("size"), QJsonArray { size.width(), size.height() });
    o.insert(QStringLiteral("mips"), mips);
    o.insert(QStringLiteral("state"), jobStateName(state()));
    return o;
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
    if (recipe) {                             // ABI 43: a field job's outputs
        QJsonArray ids;
        for (int i = 0; i < outputCount(); ++i)
            ids.append(double(fieldOutputs[i].id));
        o.insert(QStringLiteral("field_outputs"), ids);
    }
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
    if (!m_started) {
        // The first job starts the thread (D9 as built point 1: a device that never uploads holds no thread).
        m_started = true;
        if (!startThread()) {
            // Audit N38 L3: Qt could not start the thread (it only warns). The service fails closed now: nothing is
            // queued that no thread would run, this job and every later one run in their in-frame form, and a release
            // is never queued (m_quit), so no count stays up for the destruction barrier.
            m_failed.storeRelease(1);
            m_quit = true;
            m_setUpError = QStringLiteral("the job thread could not be started");
            return false;
        }
    }
    job->submittedNs = jobClockNs();
    m_queue.append(job);
    g_queued.fetchAndAddRelaxed(1);
    m_wake.wakeOne();
    return true;
}

bool JobService::startThread()
{
    // Under m_mutex: the new thread's body takes it first, so it cannot run (or end) before this returns; a thread that
    // is not running here was never started (Qt's start() sets running before it returns, and clears it on failure).
    if (m_failThreadStart)
        return false;                         // the self-test's control of a start that fails
    m_thread->start();
    return m_thread->isRunning();
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
    if (setUp && m_backend->deviceLost()) {
        // Audit N38 L1: a job queued behind the one that found the device lost never touches it again.
        setUp = false;
        setUpError = QStringLiteral("the device is lost");
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
    const int outputs = job->outputCount();   // ABI 43: a field job's outputs take consecutive ids
    {
        QMutexLocker lock(&m_mutex);
        id = m_nextId + 1;
        m_nextId += quint64(outputs);
    }
    const auto bytesOf = [&job](int i) { return job->recipe ? job->fieldOutputs[i].bytes : job->outputBytes; };
    const auto destroyAll = [this, id, outputs]() {
        for (int i = 0; i < outputs; ++i)
            m_backend->destroy(id + quint64(i));
    };
    QString error;
    if (!m_backend->upload(*job, id, &error)) {
        if (m_backend->deviceLost()) {
            // L1: the upload's completion edge found the device lost: no output is published (Qt would import an image
            // whose upload never completed), and the service fails closed for every later job.
            m_failed.storeRelease(1);
            QMutexLocker lock(&m_mutex);
            m_setUpError = QStringLiteral("the device is lost");
        }
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
        destroyAll();
        m_backend->flush();
        job->abandon();
        {
            QMutexLocker lock(&m_mutex);
            ++m_abandoned;
            m_destroyed += outputs;
        }
        logJob(*job);
        return;
    }
    {
        QMutexLocker lock(&m_mutex);
        for (int i = 0; i < outputs; ++i) {
            m_images.insert(id + quint64(i), bytesOf(i));
            g_images.fetchAndAddRelaxed(1);
            g_imageBytes.fetchAndAddRelaxed(bytesOf(i));
        }
    }
    job->finishedNs = jobClockNs();
    if (!job->publish()) {
        // Cancelled while it ran: Qt never saw its outputs, which go now.
        {
            QMutexLocker lock(&m_mutex);
            for (int i = 0; i < outputs; ++i) {
                m_images.remove(id + quint64(i));
                g_images.fetchAndAddRelaxed(-1);
                g_imageBytes.fetchAndAddRelaxed(-bytesOf(i));
            }
            ++m_cancelled;
            m_destroyed += outputs;
        }
        destroyAll();
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

void JobService::deviceWasLost()
{
    m_backend->markDeviceLost(); // thread-safe in each backend (an atomic, or the backend's own mutex)
    QMutexLocker lock(&m_mutex);
    m_toldDeviceLost = true;
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
        // L2: the job in flight's constant fields and state only (the job thread may be writing the rest).
        o.insert(QStringLiteral("running_at_stop"), m_running ? QJsonValue(m_running->briefJson()) : QJsonValue());
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
    // Audit 11 L2: whether the device's destruction said the device was lost, and whether the backend took it as lost.
    o.insert(QStringLiteral("told_device_lost"), m_toldDeviceLost);
    o.insert(QStringLiteral("device_lost"), m_backend->deviceLost());
    // N3.6: what the job QRhi loaded and saved of the core's pipeline cache file (absent while it never existed).
    const QJsonObject backend = m_backend->stateJson();
    if (backend.contains(QStringLiteral("pipeline_cache_load")))
        o.insert(QStringLiteral("pipeline_cache_load"), backend.value(QStringLiteral("pipeline_cache_load")));
    if (backend.contains(QStringLiteral("pipeline_cache_save")))
        o.insert(QStringLiteral("pipeline_cache_save"), backend.value(QStringLiteral("pipeline_cache_save")));
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
    o.insert(QStringLiteral("running"), m_running ? QJsonValue(m_running->briefJson()) : QJsonValue()); // L2
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
        // N3.6: the pipeline cache's data is kept (QRhi::pipelineCacheData is empty without the flag) for the core's file.
        QRhi::Flags flags = QRhi::EnablePipelineCacheDataSave;
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
        if (ours && !m_device.cacheFile.isEmpty()) {
            // N3.6: the core's file, before the QRhi builds any pipeline. A file of another device, driver, Qt or core
            // is refused silently (the report says why) and the QRhi starts empty: a recompile, never an error.
            QJsonObject cache;
            const QByteArray blob = loadPipelineCache(m_device.cacheFile, m_device.cacheIdentity, &cache)
                                        .value(kPipelineCacheJobQrhi);
            if (!blob.isEmpty())
                m_rhi->setPipelineCacheData(blob);
            cache.insert(QStringLiteral("qrhi_blob_loaded_bytes"), double(blob.size()));
            facts.insert(QStringLiteral("pipeline_cache_load"), cache);
        }
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
        if (job.recipe)
            return field(job, id, error);     // ABI 43
        QSharedPointer<TextureImage> pixels = job.pixels();
        if (!pixels) {
            *error = QStringLiteral("the job has no pixels");
            return false;
        }
        // ABI 35: a texture with mips holds every level, written past level 0 by the core's box kernel on the render
        // thread after the import (mode_content.cpp recordTextureChains), never by generateMips here.
        const QRhiTexture::Flags flags = job.mips ? (QRhiTexture::MipMapped | QRhiTexture::UsedWithLoadStore)
                                                  : QRhiTexture::Flags();
        RhiOwned<QRhiTexture> texture(m_rhi->newTexture(modeTextureRhiFormat(job.format), job.size, 1, flags));
        texture->setName(QByteArrayLiteral("srpss core job texture ") + job.name);
        if (!texture->create()) {
            *error = QStringLiteral("%1 could not be created at %2 x %3 on the job queue")
                         .arg(QString::fromLatin1(job.name)).arg(job.size.width()).arg(job.size.height());
            return false;
        }
        QRhiCommandBuffer *cb = nullptr;
        const QRhi::FrameOpResult begun = m_rhi->beginOffscreenFrame(&cb);
        if (begun != QRhi::FrameOpSuccess || !cb) {
            *error = QStringLiteral("beginOffscreenFrame failed on the job QRhi");
            if (begun == QRhi::FrameOpDeviceLost || m_rhi->isDeviceLost())
                noteDeviceLost(error);
            return false;
        }
        QRhiResourceUpdateBatch *updates = m_rhi->nextResourceUpdateBatch();
        const QRhiTextureSubresourceUploadDescription level(pixels->pixels); // implicitly shared, no copy
        updates->uploadTexture(texture.get(), QRhiTextureUploadDescription(QRhiTextureUploadEntry(0, 0, level)));
        cb->resourceUpdate(updates); // the staging copy, on this thread
        const QRhi::FrameOpResult ended = m_rhi->endOffscreenFrame();
        if (ended != QRhi::FrameOpSuccess) {
            *error = QStringLiteral("endOffscreenFrame failed on the job QRhi");
            if (ended == QRhi::FrameOpDeviceLost || m_rhi->isDeviceLost())
                noteDeviceLost(error);
            else
                m_rhi->finish();
            return false;
        }
        job.recordedNs = jobClockNs();
        pixels.reset();
        job.dropPixels(); // the core's copy goes: the upload is in the staging buffer
        // The completion edge with its own result (audit N38 L1): QRhi::finish() waits for this QRhi's queue but drops
        // the wait's result, so a device lost during the upload would publish an image whose upload never completed.
        // A fence on the job queue (an empty submit after the upload's, waited for here) returns the loss.
        const bool completed = waitQueue(error);
        if (!completed || m_rhi->isDeviceLost()) {
            if (error->isEmpty())
                *error = QStringLiteral("the upload's completion failed");
            if (m_rhi->isDeviceLost() && !deviceLost())
                noteDeviceLost(error);
            texture.reset();          // never published
            return false;
        }
        m_rhi->finish();  // this QRhi's own bookkeeping (its queue is idle: facts C2)
        const QRhiTexture::NativeTexture native = texture->nativeTexture();
        job.outputId = id;
        job.nativeImage = native.object;
        job.nativeLayout = native.layout;
        job.outputBytes = modeTextureBytes(job.size, job.mips, job.format);
        m_textures.insert(id, texture.release());
        QMutexLocker lock(&m_factsMutex);
        ++m_uploads;
        return true;
    }

    // ABI 43 (N5.2g): a field job. Its input photo (when the recipe samples one) uploaded from the job's pixels into a
    // texture of this record, the recipe recorded by the shared recorder (field_recipe.h) in the same offscreen frame,
    // then the fence (as an upload's: L1) and the outputs published under id .. id + outputs - 1.
    bool field(UploadJob &job, quint64 id, QString *error)
    {
        const FieldRecipe &recipe = *job.recipe;
        QSharedPointer<TextureImage> pixels = job.pixels();
        RhiOwned<QRhiTexture> input;
        if (!recipe.input.isEmpty()) {
            if (!pixels) {
                *error = QStringLiteral("the field job has no pixels for its input '%1'")
                             .arg(QString::fromLatin1(recipe.input));
                return false;
            }
            input.reset(m_rhi->newTexture(QRhiTexture::RGBA8, pixels->size, 1, QRhiTexture::Flags()));
            input->setName(QByteArrayLiteral("srpss core field job input ") + job.name);
            if (!input->create()) {
                *error = QStringLiteral("the field job's input could not be created at %1 x %2")
                             .arg(pixels->size.width()).arg(pixels->size.height());
                return false;
            }
        }
        QRhiCommandBuffer *cb = nullptr;
        const QRhi::FrameOpResult begun = m_rhi->beginOffscreenFrame(&cb);
        if (begun != QRhi::FrameOpSuccess || !cb) {
            *error = QStringLiteral("beginOffscreenFrame failed on the job QRhi");
            if (begun == QRhi::FrameOpDeviceLost || m_rhi->isDeviceLost())
                noteDeviceLost(error);
            return false;
        }
        QRhiResourceUpdateBatch *updates = m_rhi->nextResourceUpdateBatch();
        if (input) {
            const QRhiTextureSubresourceUploadDescription level(pixels->pixels); // implicitly shared, no copy
            updates->uploadTexture(input.get(), QRhiTextureUploadDescription(QRhiTextureUploadEntry(0, 0, level)));
        }
        FieldOutputs outputs;
        QString why;
        const bool recorded = m_fields.record(m_rhi.get(), cb, recipe, input.get(), &updates, &outputs, &why);
        if (updates)
            cb->resourceUpdate(updates);      // not recorded: the batch is handed back (nothing reads it)
        const QRhi::FrameOpResult ended = m_rhi->endOffscreenFrame();
        if (!recorded || ended != QRhi::FrameOpSuccess) {
            *error = recorded ? QStringLiteral("endOffscreenFrame failed on the job QRhi") : why;
            if (ended == QRhi::FrameOpDeviceLost || m_rhi->isDeviceLost())
                noteDeviceLost(error);
            else
                m_rhi->finish();
            return false;                     // the outputs (if any) go with `outputs` (never published)
        }
        job.recordedNs = jobClockNs();
        pixels.reset();
        job.dropPixels();
        const bool completed = waitQueue(error);
        if (!completed || m_rhi->isDeviceLost()) {
            if (error->isEmpty())
                *error = QStringLiteral("the field job's completion failed");
            if (m_rhi->isDeviceLost() && !deviceLost())
                noteDeviceLost(error);
            return false;
        }
        m_rhi->finish();                      // this QRhi's bookkeeping; the input and the scratch images go here
        input.reset();
        qint64 total = 0;
        for (int i = 0; i < int(recipe.outputs.size()); ++i) {
            const QRhiTexture::NativeTexture native = outputs.textures[i]->nativeTexture();
            JobOutput &o = job.fieldOutputs[i];
            o.id = id + quint64(i);
            o.nativeImage = native.object;
            o.nativeLayout = native.layout;
            o.bytes = recipe.outputBytes(i);
            total += o.bytes;
            m_textures.insert(o.id, outputs.textures[i].release());
        }
        job.outputId = job.fieldOutputs[0].id;
        job.nativeImage = job.fieldOutputs[0].nativeImage;
        job.nativeLayout = job.fieldOutputs[0].nativeLayout;
        job.outputBytes = total;
        QMutexLocker lock(&m_factsMutex);
        ++m_fieldJobs;
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
        m_fields.release();                   // ABI 43: its pipelines, before their QRhi
        QJsonObject cache;
        if (m_rhi) {
            m_rhi->finish();
            // N3.6: the orderly teardown saves the core's file (Qt saves its own the same way, in destroyRhi); never after
            // a device loss. An empty blob (the QRhi built no pipeline) writes nothing.
            if (deviceLost()) {
                cache.insert(QStringLiteral("save"), QStringLiteral("skipped: the device was lost"));
            } else if (!m_device.cacheFile.isEmpty()) {
                const QByteArray blob = m_rhi->pipelineCacheData();
                if (blob.isEmpty()) {
                    cache.insert(QStringLiteral("save"), QStringLiteral("nothing to save: the job QRhi built no "
                                                                        "pipeline"));
                } else {
                    PipelineCacheSections sections;
                    sections.insert(kPipelineCacheJobQrhi, blob);
                    savePipelineCache(m_device.cacheFile, m_device.cacheIdentity, sections, &cache);
                    cache.insert(QStringLiteral("qrhi_blob_bytes"), double(blob.size()));
                }
            }
            m_rhi.reset(); // QRhiVulkan::destroy: its own queue idle, its pools and allocator; never the device
        }
        QMutexLocker lock(&m_factsMutex);
        if (!cache.isEmpty())
            m_facts.insert(QStringLiteral("pipeline_cache_save"), cache);
        m_tornDown = true;
    }

    bool deviceLost() const override { return m_deviceLost.loadAcquire() != 0; }
    void markDeviceLost() override { m_deviceLost.storeRelease(1); } // audit 11 L2: the window's QRhi found it lost

    QJsonObject stateJson() const override
    {
        QMutexLocker lock(&m_factsMutex);
        QJsonObject o = m_facts;
        o.insert(QStringLiteral("kind"), QStringLiteral("qrhi_vulkan"));
        o.insert(QStringLiteral("device_lost"), m_deviceLost.loadRelaxed() != 0);
        o.insert(QStringLiteral("uploads"), double(m_uploads));
        o.insert(QStringLiteral("field_jobs"), double(m_fieldJobs)); // ABI 43
        o.insert(QStringLiteral("torn_down"), m_tornDown);
        return o;
    }

private:
    void setFacts(const QJsonObject &facts)
    {
        QMutexLocker lock(&m_factsMutex);
        m_facts = facts;
    }

    void noteDeviceLost(QString *error)
    {
        m_deviceLost.storeRelease(1);
        *error = QStringLiteral("the device was lost (%1)").arg(*error);
    }

    // L1: waits for every submission on the job queue through a fence of our own and returns its result (false with the
    // reason, the device marked lost on VK_ERROR_DEVICE_LOST). Job thread only: the job queue is this thread's alone.
    bool waitQueue(QString *error)
    {
        const VkDevice dev = reinterpret_cast<VkDevice>(quintptr(m_device.device));
        QVulkanDeviceFunctions *df = m_device.instance ? m_device.instance->deviceFunctions(dev) : nullptr;
        if (!df) {
            *error = QStringLiteral("no device functions for the job queue's fence");
            return false;
        }
        VkQueue queue = VK_NULL_HANDLE;
        df->vkGetDeviceQueue(dev, m_device.family, m_device.queueIndex, &queue);
        VkFenceCreateInfo info = {};
        info.sType = VK_STRUCTURE_TYPE_FENCE_CREATE_INFO;
        VkFence fence = VK_NULL_HANDLE;
        VkResult result = df->vkCreateFence(dev, &info, nullptr, &fence);
        if (result == VK_SUCCESS) {
            result = df->vkQueueSubmit(queue, 0, nullptr, fence); // signalled once every earlier submission completed
            if (result == VK_SUCCESS)
                result = df->vkWaitForFences(dev, 1, &fence, VK_TRUE, UINT64_MAX);
            df->vkDestroyFence(dev, fence, nullptr);
        }
        if (result == VK_SUCCESS)
            return true;
        *error = QStringLiteral("the job queue's completion returned VkResult %1").arg(int(result));
        if (result == VK_ERROR_DEVICE_LOST)
            noteDeviceLost(error);
        return false;
    }

    JobDevice m_device;
    QAtomicInteger<int> m_deviceLost { 0 };
    std::unique_ptr<QRhi> m_rhi;                 // job thread only
    QHash<quint64, QRhiTexture *> m_textures;    // job thread only (owned)
    mutable QMutex m_factsMutex;                 // guards the report below (read from the GUI thread)
    QJsonObject m_facts;
    qint64 m_uploads = 0;
    qint64 m_fieldJobs = 0;                      // ABI 43
    FieldRecorder m_fields;                      // ABI 43: job thread only, released before its QRhi
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
            if (m_loseNext) {
                // L1's control: the upload was submitted and its completion edge found the device lost.
                m_loseNext = false;
                m_lost = true;
                job.dropPixels();
                *error = QStringLiteral("the device was lost (scripted)");
                return false;
            }
        }
        // ABI 43: a field job needs pixels only when its recipe samples an input.
        const bool needsPixels = !job.recipe || !job.recipe->input.isEmpty();
        if (needsPixels && !job.pixels()) {
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
        if (job.recipe) {
            qint64 total = 0;
            for (int i = 0; i < job.outputCount(); ++i) {
                JobOutput &o = job.fieldOutputs[i];
                o.id = id + quint64(i);
                o.nativeImage = 0x2000 + o.id;
                o.nativeLayout = 1;           // VK_IMAGE_LAYOUT_GENERAL, a load-store image's
                o.bytes = job.recipe->outputBytes(i);
                total += o.bytes;
                m_outputs.insert(o.id, true);
            }
            job.outputId = id;
            job.nativeImage = job.fieldOutputs[0].nativeImage;
            job.nativeLayout = 1;
            job.outputBytes = total;
            ++m_fields;
            return true;
        }
        job.outputId = id;
        job.nativeImage = 0x1000 + id;
        job.nativeLayout = 7;
        job.outputBytes = modeTextureBytes(job.size, job.mips, job.format);
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

    bool deviceLost() const override
    {
        QMutexLocker lock(&m_mutex);
        return m_lost;
    }
    void markDeviceLost() override
    {
        QMutexLocker lock(&m_mutex);
        m_lost = true;
    }
    void loseNext()
    {
        QMutexLocker lock(&m_mutex);
        m_loseNext = true;
    }

    QJsonObject stateJson() const override
    {
        QMutexLocker lock(&m_mutex);
        QJsonObject o;
        o.insert(QStringLiteral("kind"), QStringLiteral("scripted"));
        o.insert(QStringLiteral("set_ups"), m_setUps);
        o.insert(QStringLiteral("uploads"), m_uploads);
        o.insert(QStringLiteral("fields"), m_fields);   // ABI 43
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
    bool m_loseNext = false;
    bool m_lost = false;
    bool m_failSetUp = false;
    int m_entered = 0;
    int m_setUps = 0;
    int m_uploads = 0;
    int m_fields = 0;                            // ABI 43: field jobs run
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
        } else if (op == QLatin1String("submit_field")) {
            // ABI 43: a field job of `outputs` 2 x 2 rgba16f outputs, sampling an input (with `pixels`) or none.
            auto recipe = std::make_shared<FieldRecipe>();
            const int outputs = qBound(1, step.value(QStringLiteral("outputs")).toInt(1), kMaxFieldOutputs);
            for (int i = 0; i < outputs; ++i) {
                FieldImage image;
                image.name = QByteArray("out") + QByteArray::number(i);
                image.format = QRhiTexture::RGBA16F;
                image.size = QSize(2, 2);
                recipe->images.append(image);
                FieldOutput output;
                output.image = i;
                output.texture = QByteArray("field") + QByteArray::number(i);
                recipe->outputs.append(output);
            }
            if (step.value(QStringLiteral("input")).toBool())
                recipe->input = QByteArrayLiteral("photo");
            QSharedPointer<TextureImage> image;
            if (step.value(QStringLiteral("pixels")).toBool(true) && !recipe->input.isEmpty())
                image = QSharedPointer<TextureImage>::create(QByteArray(64, 0), QSize(4, 4), false);
            auto job = std::make_shared<UploadJob>(name.toLatin1(), quint64(step.value(QStringLiteral("generation"))
                                                                               .toInt(1)),
                                                   image, std::shared_ptr<const FieldRecipe>(recipe), notifier);
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
        } else if (op == QLatin1String("lose_device")) {
            backend->loseNext();                 // audit N38 L1
        } else if (op == QLatin1String("device_was_lost")) {
            service->deviceWasLost();            // audit 11 L2: the device's destruction says so before the stop
        } else if (op == QLatin1String("fail_thread_start")) {
            service->failThreadStartForTest();   // audit N38 L3
        } else if (op == QLatin1String("running_state")) {
            // Audit N38 L2: the service's state while a job runs reports only its constant fields and state.
            const QJsonObject running = service->stateJson(false).value(QStringLiteral("running")).toObject();
            seen.insert(QStringLiteral("running_keys"), QJsonArray::fromStringList(running.keys()));
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
            if (job && result == UploadJob::Cancelled::Published && step.value(QStringLiteral("release")).toBool(true)) {
                for (int i = 0; i < job->outputCount(); ++i)
                    service->release(job->outputIdOf(i)); // the consumer's duty for every output it was handed
            }
        } else if (op == QLatin1String("release")) {
            const std::shared_ptr<UploadJob> job = jobs.value(name);
            // ABI 43: "outputs" releases the first n of a field job's outputs (all by default).
            const int count = job ? qMin(job->outputCount(), step.value(QStringLiteral("outputs"))
                                                                  .toInt(job->outputCount()))
                                  : 0;
            for (int i = 0; i < count; ++i)
                service->release(job->outputIdOf(i));
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
