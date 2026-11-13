#include "gpu_timer.h"

#include <rhi/qrhi.h>
#include <rhi/qrhi_platform.h>

#include <QtCore/QElapsedTimer>
#include <QtCore/QJsonArray>
#include <QtCore/QJsonDocument>
#include <QtCore/QStringList>
#include <QtGui/QOpenGLContext>
#include <QtGui/QVulkanFunctions>
#include <QtGui/QVulkanInstance>

#ifndef VK_NO_PROTOTYPES
#define VK_NO_PROTOTYPES // the module never links vulkan-1.lib (vulkan_context.cpp)
#endif
#include <vulkan/vulkan.h>

#include <cmath>

#ifdef APIENTRY
#define SRPSS_GLAPI APIENTRY
#else
#define SRPSS_GLAPI
#endif

namespace srpss_core {

namespace {

QAtomicInteger<int> g_timers { 0 };
QAtomicInteger<int> g_pools { 0 };
QAtomicInteger<int> g_queries { 0 };

constexpr unsigned int kGlTimeElapsed = 0x88BF;
constexpr unsigned int kGlQueryResult = 0x8866;
constexpr unsigned int kGlQueryResultAvailable = 0x8867;
constexpr int kQueriesPerSlot = GpuTimer::kMaxScopes * 2; // Vulkan: a begin and an end timestamp per scope
constexpr int kVulkanQueries = GpuTimer::kRingFrames * kQueriesPerSlot;
constexpr int kGlQueries = GpuTimer::kRingFrames * GpuTimer::kMaxScopes; // OpenGL: one TIME_ELAPSED query per scope

using GlGenQueries = void(SRPSS_GLAPI *)(int, unsigned int *);
using GlDeleteQueries = void(SRPSS_GLAPI *)(int, const unsigned int *);
using GlBeginQuery = void(SRPSS_GLAPI *)(unsigned int, unsigned int);
using GlEndQuery = void(SRPSS_GLAPI *)(unsigned int);
using GlGetQueryObjectiv = void(SRPSS_GLAPI *)(unsigned int, unsigned int, int *);
using GlGetQueryObjectui64v = void(SRPSS_GLAPI *)(unsigned int, unsigned int, quint64 *);

} // namespace

QString gpuPassKindName(GpuPassKind kind)
{
    switch (kind) {
    case GpuPassKind::Frame:
        return QStringLiteral("frame");
    case GpuPassKind::Probe:
        return QStringLiteral("probe");
    case GpuPassKind::Surface:
        return QStringLiteral("surface");
    case GpuPassKind::Load:
        return QStringLiteral("load");
    }
    return QStringLiteral("unknown");
}

// ------------------------------------------------------------------------------------------------- the configuration

bool GpuTimerConfig::fromJson(const QByteArray &json, GpuTimerConfig *out, QString *error)
{
    QJsonParseError parse;
    const QJsonDocument document = QJsonDocument::fromJson(json, &parse);
    if (!document.isObject()) {
        *error = QStringLiteral("the timer's configuration is a JSON object");
        return false;
    }
    const QJsonObject o = document.object();
    const QStringList known = { QStringLiteral("enabled"), QStringLiteral("keep_when_off"),
                                QStringLiteral("wait_for_results") };
    for (auto it = o.begin(); it != o.end(); ++it) {
        if (!known.contains(it.key())) {
            *error = QStringLiteral("unknown timer option '%1' (%2)").arg(it.key(), known.join(QStringLiteral(", ")));
            return false;
        }
        if (!it.value().isBool()) {
            *error = QStringLiteral("the timer option '%1' is true or false").arg(it.key());
            return false;
        }
    }
    GpuTimerConfig c;
    c.enabled = o.value(QStringLiteral("enabled")).toBool(c.enabled);
    c.keepWhenOff = o.value(QStringLiteral("keep_when_off")).toBool(c.keepWhenOff);
    c.waitForResults = o.value(QStringLiteral("wait_for_results")).toBool(c.waitForResults);
    *out = c;
    return true;
}

QJsonObject GpuTimerConfig::toJson() const
{
    QJsonObject o;
    o.insert(QStringLiteral("enabled"), enabled);
    o.insert(QStringLiteral("keep_when_off"), keepWhenOff);
    o.insert(QStringLiteral("wait_for_results"), waitForResults);
    return o;
}

// ------------------------------------------------------------------------------------------------- the queue

void GpuSampleQueue::append(const GpuTimingSample &sample)
{
    QMutexLocker lock(&m_mutex);
    ++m_appended;
    if (m_samples.size() >= kCapacity) {
        ++m_dropped;
        return;
    }
    m_samples.append(sample);
}

QList<GpuTimingSample> GpuSampleQueue::take()
{
    QMutexLocker lock(&m_mutex);
    QList<GpuTimingSample> out;
    out.swap(m_samples);
    return out;
}

qint64 GpuSampleQueue::dropped() const
{
    QMutexLocker lock(&m_mutex);
    return m_dropped;
}

qint64 GpuSampleQueue::appended() const
{
    QMutexLocker lock(&m_mutex);
    return m_appended;
}

// ------------------------------------------------------------------------------------------------- the timer

struct GpuTimer::Vulkan
{
    QVulkanDeviceFunctions *df = nullptr;
    VkDevice device = VK_NULL_HANDLE;
    VkQueue queue = VK_NULL_HANDLE;
    VkQueryPool pool = VK_NULL_HANDLE;
    quint64 mask = ~quint64(0);
};

struct GpuTimer::OpenGl
{
    GlGenQueries genQueries = nullptr;
    GlDeleteQueries deleteQueries = nullptr;
    GlBeginQuery beginQuery = nullptr;
    GlEndQuery endQuery = nullptr;
    GlGetQueryObjectiv getQueryObjectiv = nullptr;
    GlGetQueryObjectui64v getQueryObjectui64v = nullptr;
    unsigned int names[kGlQueries] = {};
    bool generated = false;
};

GpuTimer::GpuTimer(const GpuTimerConfig &config, std::shared_ptr<GpuSampleQueue> queue)
    : m_config(config), m_queue(std::move(queue))
{
    g_timers.fetchAndAddRelaxed(1);
}

GpuTimer::~GpuTimer()
{
    // release() ran on the render thread (the frame driver's contract); a timer whose QRhi is gone holds nothing of it.
    setQueryObjects(0, 0);
    g_timers.fetchAndAddRelaxed(-1);
}

void GpuTimer::setQueryObjects(int pools, int queries)
{
    g_pools.fetchAndAddRelaxed(pools - m_pools);
    g_queries.fetchAndAddRelaxed(queries - m_queryObjects);
    m_pools = pools;
    m_queryObjects = queries;
}

QJsonObject GpuTimer::liveJson()
{
    QJsonObject o;
    o.insert(QStringLiteral("timers"), g_timers.loadRelaxed());
    o.insert(QStringLiteral("query_pools"), g_pools.loadRelaxed());
    o.insert(QStringLiteral("queries"), g_queries.loadRelaxed());
    return o;
}

bool GpuTimer::ensure(QRhi *rhi)
{
    m_created = true;
    m_backend = QString::fromLatin1(rhi->backendName());
    m_framesInFlight = rhi->resourceLimit(QRhi::FramesInFlight);
    if (m_framesInFlight + 1 >= kRingFrames) {
        m_perPass = QStringLiteral("unavailable: the QRhi runs %1 frames in flight, the ring holds %2")
                        .arg(m_framesInFlight)
                        .arg(kRingFrames);
        return false;
    }
    if (rhi->backend() == QRhi::Vulkan) {
        const auto *handles = static_cast<const QRhiVulkanNativeHandles *>(rhi->nativeHandles());
        if (!handles || !handles->inst || !handles->dev || !handles->physDev) {
            m_error = QStringLiteral("Vulkan: no native handles");
            return false;
        }
        QVulkanFunctions *f = handles->inst->functions();
        QVulkanDeviceFunctions *df = handles->inst->deviceFunctions(handles->dev);
        if (!f || !df) {
            m_error = QStringLiteral("Vulkan: no instance or device functions");
            return false;
        }
        VkPhysicalDeviceProperties properties = {};
        f->vkGetPhysicalDeviceProperties(handles->physDev, &properties);
        uint32_t families = 0;
        f->vkGetPhysicalDeviceQueueFamilyProperties(handles->physDev, &families, nullptr);
        QList<VkQueueFamilyProperties> familyProperties;
        familyProperties.resize(qsizetype(families));
        f->vkGetPhysicalDeviceQueueFamilyProperties(handles->physDev, &families, familyProperties.data());
        const qint64 family = qint64(handles->gfxQueueFamilyIdx);
        m_timestampValidBits = (family >= 0 && family < qint64(families))
                                   ? int(familyProperties.at(qsizetype(family)).timestampValidBits)
                                   : 0;
        m_timestampPeriodNs = double(properties.limits.timestampPeriod);
        if (m_timestampValidBits == 0 || !(m_timestampPeriodNs > 0.0)) {
            m_perPass = QStringLiteral("unavailable: the graphics queue family has no timestamps");
            return false;
        }
        auto vk = std::make_unique<Vulkan>();
        vk->df = df;
        vk->device = handles->dev;
        vk->queue = handles->gfxQueue;
        vk->mask = m_timestampValidBits >= 64 ? ~quint64(0) : ((quint64(1) << m_timestampValidBits) - 1);
        VkQueryPoolCreateInfo info = {};
        info.sType = VK_STRUCTURE_TYPE_QUERY_POOL_CREATE_INFO;
        info.queryType = VK_QUERY_TYPE_TIMESTAMP;
        info.queryCount = uint32_t(kVulkanQueries);
        const VkResult result = df->vkCreateQueryPool(handles->dev, &info, nullptr, &vk->pool);
        if (result != VK_SUCCESS) {
            m_error = QStringLiteral("vkCreateQueryPool: %1").arg(int(result));
            return false;
        }
        m_vk = std::move(vk);
        m_perPass = QStringLiteral("vulkan timestamps");
        setQueryObjects(1, kVulkanQueries);
        return true;
    }
    if (rhi->backend() == QRhi::OpenGLES2) {
        if (!rhi->makeThreadLocalNativeContextCurrent()) {
            m_error = QStringLiteral("OpenGL: the QRhi's context could not be made current");
            return false;
        }
        QOpenGLContext *context = QOpenGLContext::currentContext();
        if (!context) {
            m_error = QStringLiteral("OpenGL: no current context");
            return false;
        }
        const QSurfaceFormat format = context->format();
        const bool timerQueries = !context->isOpenGLES()
                                  && (format.version() >= qMakePair(3, 3)
                                      || context->hasExtension(QByteArrayLiteral("GL_ARB_timer_query")));
        if (!timerQueries) {
            m_perPass = QStringLiteral("unavailable: this OpenGL context has no timer queries (desktop 3.3 or "
                                       "GL_ARB_timer_query)");
            return false;
        }
        auto gl = std::make_unique<OpenGl>();
        gl->genQueries = reinterpret_cast<GlGenQueries>(context->getProcAddress("glGenQueries"));
        gl->deleteQueries = reinterpret_cast<GlDeleteQueries>(context->getProcAddress("glDeleteQueries"));
        gl->beginQuery = reinterpret_cast<GlBeginQuery>(context->getProcAddress("glBeginQuery"));
        gl->endQuery = reinterpret_cast<GlEndQuery>(context->getProcAddress("glEndQuery"));
        gl->getQueryObjectiv = reinterpret_cast<GlGetQueryObjectiv>(context->getProcAddress("glGetQueryObjectiv"));
        gl->getQueryObjectui64v =
            reinterpret_cast<GlGetQueryObjectui64v>(context->getProcAddress("glGetQueryObjectui64v"));
        if (!gl->genQueries || !gl->deleteQueries || !gl->beginQuery || !gl->endQuery || !gl->getQueryObjectiv
            || !gl->getQueryObjectui64v) {
            m_error = QStringLiteral("OpenGL: the timer query functions did not resolve");
            return false;
        }
        gl->genQueries(kGlQueries, gl->names);
        gl->generated = true;
        m_gl = std::move(gl);
        m_perPass = QStringLiteral("opengl GL_TIME_ELAPSED");
        setQueryObjects(0, kGlQueries);
        return true;
    }
    m_perPass = QStringLiteral("unavailable on %1: QRhi times the whole frame only (D5.3: the per-pass service's "
                               "native forms are Vulkan and OpenGL)")
                    .arg(m_backend);
    return false;
}

void GpuTimer::beginFrame(QRhi *rhi, QRhiCommandBuffer *cb, qint64 edge)
{
    ++m_frames;
    m_edge = edge;
    m_current = -1;
    if (!rhi)
        return;
    if (!m_created)
        ensure(rhi);
    resolve(rhi, cb, edge);
    if (cb)
        readFrameFigure(cb, edge);
    if (m_stopped || (!m_vk && !m_gl))
        return;
    const int index = int(edge % kRingFrames);
    Slot &slot = m_slots[index];
    if (slot.pending) {
        ++m_slotBusyFrames; // its frame's results are still unread: this frame goes untimed, they are kept
        return;
    }
    slot.edge = edge;
    slot.scopes = 0;
    m_current = index;
}

void GpuTimer::readFrameFigure(QRhiCommandBuffer *cb, qint64 edge)
{
    // QRhi's own figure: the last completed frame's GPU time, 0 when the QRhi was created without EnableTimestamps or has
    // none yet. Read at the edge, never waited for.
    const double seconds = cb->lastCompletedGpuTime();
    if (!(seconds > 0.0) || seconds == m_lastFrameSeconds)
        return;
    m_lastFrameSeconds = seconds;
    ++m_frameFigures;
    GpuTimingSample sample;
    sample.kind = int(GpuPassKind::Frame);
    sample.frame = -1;
    sample.readAt = edge;
    sample.nanoseconds = qint64(std::llround(seconds * 1e9));
    m_queue->append(sample);
}

void GpuTimer::resolve(QRhi *rhi, QRhiCommandBuffer *cb, qint64 edge)
{
    Q_UNUSED(cb);
    bool any = false;
    for (const Slot &slot : m_slots)
        any = any || (slot.pending && slot.edge < edge);
    if (!any)
        return;
    QElapsedTimer clock;
    clock.start();
    if (m_gl && !rhi->makeThreadLocalNativeContextCurrent()) {
        m_error = QStringLiteral("OpenGL: the context could not be made current to read results");
        return;
    }
    for (int i = 0; i < kRingFrames; ++i) {
        if (m_slots[i].pending && m_slots[i].edge < edge && !resolveSlot(i, edge))
            ++m_notReadyReads;
    }
    const qint64 ns = clock.nsecsElapsed();
    m_resolveNsTotal += ns;
    m_resolveNsMax = qMax(m_resolveNsMax, ns);
}

bool GpuTimer::resolveSlot(int index, qint64 edge)
{
    Slot &slot = m_slots[index];
    const bool wait = m_config.waitForResults;
    qint64 nanoseconds[kMaxScopes] = {};
    for (int s = 0; s < slot.scopes; ++s) {
        if (!slot.scope[s].closed)
            continue;
        if (m_vk) {
            const uint32_t first = uint32_t(index * kQueriesPerSlot + 2 * s);
            quint64 data[4] = {};
            VkResult result = VK_SUCCESS;
            if (wait) {
                result = m_vk->df->vkGetQueryPoolResults(m_vk->device, m_vk->pool, first, 2, sizeof(data), data,
                                                         sizeof(quint64),
                                                         VK_QUERY_RESULT_64_BIT | VK_QUERY_RESULT_WAIT_BIT);
                ++m_blockingReads;
                if (result != VK_SUCCESS) {
                    m_error = QStringLiteral("vkGetQueryPoolResults (wait): %1").arg(int(result));
                    return false;
                }
                data[2] = data[1];
            } else {
                result = m_vk->df->vkGetQueryPoolResults(m_vk->device, m_vk->pool, first, 2, sizeof(data), data,
                                                         2 * sizeof(quint64),
                                                         VK_QUERY_RESULT_64_BIT
                                                             | VK_QUERY_RESULT_WITH_AVAILABILITY_BIT);
                if (result == VK_NOT_READY || data[1] == 0 || data[3] == 0)
                    return false; // read again at a later edge
                if (result != VK_SUCCESS) {
                    m_error = QStringLiteral("vkGetQueryPoolResults: %1").arg(int(result));
                    return false;
                }
            }
            const quint64 ticks = (data[2] - data[0]) & m_vk->mask;
            nanoseconds[s] = qint64(std::llround(double(ticks) * m_timestampPeriodNs));
        } else if (m_gl) {
            const unsigned int name = m_gl->names[index * kMaxScopes + s];
            if (!wait) {
                int available = 0;
                m_gl->getQueryObjectiv(name, kGlQueryResultAvailable, &available);
                if (!available)
                    return false;
            } else {
                ++m_blockingReads;
            }
            quint64 value = 0;
            m_gl->getQueryObjectui64v(name, kGlQueryResult, &value); // the negative control waits here
            nanoseconds[s] = qint64(value);
        }
    }
    const qint64 latency = edge - slot.edge;
    for (int s = 0; s < slot.scopes; ++s) {
        if (!slot.scope[s].closed)
            continue;
        GpuTimingSample sample;
        sample.kind = slot.scope[s].kind;
        sample.frame = slot.edge;
        sample.readAt = edge;
        sample.nanoseconds = nanoseconds[s];
        m_queue->append(sample);
        ++m_results;
    }
    m_latencyMin = m_latencyMin < 0 ? latency : qMin(m_latencyMin, latency);
    m_latencyMax = qMax(m_latencyMax, latency);
    ++m_latencyHistogram[qBound(qint64(0), latency - 1, qint64(7))];
    slot.pending = false;
    slot.scopes = 0;
    return true;
}

int GpuTimer::begin(QRhi *rhi, QRhiCommandBuffer *cb, GpuPassKind kind)
{
    if (m_stopped || m_current < 0 || !rhi || !cb || (!m_vk && !m_gl))
        return -1;
    Slot &slot = m_slots[m_current];
    if (slot.scopes >= kMaxScopes) {
        ++m_overCapacity;
        return -1;
    }
    const int s = slot.scopes;
    cb->beginExternal(); // outside any pass: what QRhi holds is recorded first, so the bracket is in submission order
    if (m_vk) {
        const auto *handles = static_cast<const QRhiVulkanCommandBufferNativeHandles *>(cb->nativeHandles());
        if (!handles || !handles->commandBuffer) {
            cb->endExternal();
            m_error = QStringLiteral("Vulkan: no native command buffer");
            return -1;
        }
        const uint32_t base = uint32_t(m_current * kQueriesPerSlot);
        if (s == 0) // the slot's queries are reset in the frame, before its first write, outside the pass
            m_vk->df->vkCmdResetQueryPool(handles->commandBuffer, m_vk->pool, base, uint32_t(kQueriesPerSlot));
        m_vk->df->vkCmdWriteTimestamp(handles->commandBuffer, VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT, m_vk->pool,
                                      base + uint32_t(2 * s));
    } else {
        m_gl->beginQuery(kGlTimeElapsed, m_gl->names[m_current * kMaxScopes + s]);
    }
    cb->endExternal();
    slot.scope[s].kind = int(kind);
    slot.scope[s].closed = false;
    slot.scopes = s + 1;
    slot.pending = true;
    m_lastWriteEdge = m_edge;
    return s;
}

void GpuTimer::end(QRhi *rhi, QRhiCommandBuffer *cb, int scope)
{
    if (scope < 0 || m_current < 0 || !rhi || !cb)
        return;
    Slot &slot = m_slots[m_current];
    if (scope >= slot.scopes || slot.scope[scope].closed)
        return;
    cb->beginExternal(); // the pass's commands are recorded (OpenGL: issued) first
    if (m_vk) {
        const auto *handles = static_cast<const QRhiVulkanCommandBufferNativeHandles *>(cb->nativeHandles());
        if (handles && handles->commandBuffer) {
            m_vk->df->vkCmdWriteTimestamp(handles->commandBuffer, VK_PIPELINE_STAGE_BOTTOM_OF_PIPE_BIT, m_vk->pool,
                                          uint32_t(m_current * kQueriesPerSlot + 2 * scope + 1));
            slot.scope[scope].closed = true;
        } else {
            m_error = QStringLiteral("Vulkan: no native command buffer");
        }
    } else if (m_gl) {
        m_gl->endQuery(kGlTimeElapsed);
        slot.scope[scope].closed = true;
    }
    cb->endExternal();
    ++m_timedPasses;
}

void GpuTimer::stop(qint64 edge)
{
    Q_UNUSED(edge);
    m_stopped = true;
    m_current = -1;
}

bool GpuTimer::drained(QRhi *rhi, qint64 edge) const
{
    Q_UNUSED(rhi);
    return m_lastWriteEdge < 0 || edge - m_lastWriteEdge > m_framesInFlight;
}

void GpuTimer::release(QRhi *rhi, bool outsideFrame)
{
    if (m_vk) {
        if (m_vk->pool != VK_NULL_HANDLE) {
            if (m_lastWriteEdge >= 0) {
                if (outsideFrame && rhi) {
                    rhi->finish(); // the frames that wrote the pool complete first
                } else if (!outsideFrame && !drained(rhi, m_edge)) {
                    // A detach inside a frame: the earlier frames may still use the pool. Once, at teardown only.
                    m_vk->df->vkQueueWaitIdle(m_vk->queue);
                    ++m_releaseWaits;
                }
            }
            m_vk->df->vkDestroyQueryPool(m_vk->device, m_vk->pool, nullptr);
            m_vk->pool = VK_NULL_HANDLE;
        }
        m_vk.reset();
    }
    if (m_gl) {
        if (m_gl->generated && rhi && rhi->makeThreadLocalNativeContextCurrent()) {
            m_gl->deleteQueries(kGlQueries, m_gl->names); // OpenGL defers the deletion of a query still in use
            m_gl->generated = false;
        }
        m_gl.reset();
    }
    for (Slot &slot : m_slots) {
        slot.pending = false;
        slot.scopes = 0;
    }
    m_current = -1;
    m_stopped = true;
    setQueryObjects(0, 0);
}

QJsonObject GpuTimer::stateJson() const
{
    QJsonObject o;
    o.insert(QStringLiteral("config"), m_config.toJson());
    o.insert(QStringLiteral("backend"), m_backend);
    o.insert(QStringLiteral("per_pass"), m_perPass);
    o.insert(QStringLiteral("created"), m_created);
    o.insert(QStringLiteral("stopped"), m_stopped);
    o.insert(QStringLiteral("frames_in_flight"), m_framesInFlight);
    o.insert(QStringLiteral("ring_frames"), kRingFrames);
    o.insert(QStringLiteral("max_scopes"), kMaxScopes);
    o.insert(QStringLiteral("query_pools"), m_pools);
    o.insert(QStringLiteral("queries"), m_queryObjects);
    o.insert(QStringLiteral("timestamp_period_ns"), m_timestampPeriodNs);
    o.insert(QStringLiteral("timestamp_valid_bits"), m_timestampValidBits);
    o.insert(QStringLiteral("frames"), m_frames);
    o.insert(QStringLiteral("timed_passes"), m_timedPasses);
    o.insert(QStringLiteral("results"), m_results);
    o.insert(QStringLiteral("frame_figures"), m_frameFigures);
    o.insert(QStringLiteral("not_ready_reads"), m_notReadyReads);
    o.insert(QStringLiteral("blocking_reads"), m_blockingReads);
    o.insert(QStringLiteral("slot_busy_frames"), m_slotBusyFrames);
    o.insert(QStringLiteral("over_capacity"), m_overCapacity);
    o.insert(QStringLiteral("release_waits"), m_releaseWaits);
    o.insert(QStringLiteral("resolve_ns_max"), m_resolveNsMax);
    o.insert(QStringLiteral("resolve_ns_total"), m_resolveNsTotal);
    o.insert(QStringLiteral("latency_min"), m_latencyMin);
    o.insert(QStringLiteral("latency_max"), m_latencyMax);
    QJsonArray histogram;
    for (qint64 count : m_latencyHistogram)
        histogram.append(count);
    o.insert(QStringLiteral("latency_histogram"), histogram);
    o.insert(QStringLiteral("error"), m_error);
    return o;
}

} // namespace srpss_core
