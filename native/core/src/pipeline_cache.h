// The core's own pipeline cache file (N3.6, Current_Plan.md item 8b, the pipeline-cache box; research
// Docs/Future_Work/Native_Core_QRhi_Research_N3.md section 10).
//
// Pipelines the core builds on Qt Quick's QRhi go into that QRhi's one pipeline cache and Qt Quick saves them in its own
// file (<CacheLocation>/qtpipelinecache-<abi>/qqpc_<backend>): they need nothing here. What Qt never saves is the job
// thread's QRhi (job_service.h: a second QRhi on the module's device) and any raw Vulkan pipeline; they get one file of
// the core's beside Qt's, <CacheLocation>/qtpipelinecache-<QSysInfo::buildAbi()>/srpss_core_<backend>:
// - a header with the same checks as Qt's own (the core's ABI, the backend, the driver version, the vendor, the device
//   and the pipeline cache UUID), then the payload's size and an MD5 of it (a torn or cut file is refused), then the
//   sections (a tag and its bytes: kPipelineCacheJobQrhi is the job QRhi's QRhi::pipelineCacheData(); a raw
//   VkPipelineCache gets its own tag when the first raw pipeline exists);
// - a file that does not pass is a silent recompile: refused with its reason in the reader's report, never logged, and
//   the QRhi starts empty (QRhi checks its own blob's header again and ignores a mismatch the same way);
// - loaded when the job QRhi is created, saved at its orderly teardown (never after a device loss, as Qt does), through
//   QSaveFile: written to a temporary file and renamed over the old one, so two windows or processes never leave a torn
//   file. Some writer wins, not necessarily the last (checkpoint audit 11 L3: on Windows a rename over a file another
//   reader holds open fails): such a commit keeps the earlier writer's whole file and is reported as a skip
//   (save_failed), never an error.
// Today the job QRhi builds no pipeline (uploads and blitted mips only), so its blob is empty and nothing is written;
// the warm-up jobs (D9 point 2, consumer (b)) are the first producer. Any thread; no state but the harness's directory.
#pragma once

#include <QtCore/QByteArray>
#include <QtCore/QHash>
#include <QtCore/QJsonObject>
#include <QtCore/QString>

namespace srpss_core {

// The device a cache was made on: the checks Qt's own header makes (VK qrhivulkan.cpp's QVkPipelineCacheDataHeader).
struct PipelineCacheIdentity
{
    QString backend;          // "vulkan"
    quint32 driverVersion = 0;
    quint32 vendorId = 0;
    quint32 deviceId = 0;
    QByteArray cacheUuid;     // VkPhysicalDeviceProperties::pipelineCacheUUID (VK_UUID_SIZE bytes)
};

constexpr quint32 kPipelineCacheJobQrhi = 1; // the section of the job thread's QRhi::pipelineCacheData()

using PipelineCacheSections = QHash<quint32, QByteArray>;

// The file's bytes for these sections (sorted by tag). `abi` is the core's (a harness passes another for the control).
QByteArray encodePipelineCache(const PipelineCacheIdentity &identity, const PipelineCacheSections &sections, quint32 abi);
// Empty: accepted, `sections` filled. Otherwise the reason it is refused ("short", "magic", "format", "abi", "backend",
// "driver_version", "vendor", "device", "cache_uuid", "size", "checksum", "sections"); `sections` is left empty.
QString decodePipelineCache(const QByteArray &file, const PipelineCacheIdentity &identity,
                            PipelineCacheSections *sections);

// The directory: the harness's (setPipelineCacheDirectory) or <CacheLocation>/qtpipelinecache-<buildAbi>, Qt's own.
QString pipelineCacheDirectory();
// Harness only: the directory of every device made afterwards (an empty string: Qt's default again).
void setPipelineCacheDirectory(const QString &directory);
// <directory>/srpss_core_<backend>.
QString pipelineCacheFile(const QString &directory, const QString &backend);

// Reads and checks the file; `report`: file, result ("absent", "unreadable", "accepted", "rejected: <reason>"), bytes.
PipelineCacheSections loadPipelineCache(const QString &file, const PipelineCacheIdentity &identity, QJsonObject *report);
// Writes the file through QSaveFile (the directory made first); `report`: file, saved_bytes, or save_failed. True when
// committed.
bool savePipelineCache(const QString &file, const PipelineCacheIdentity &identity, const PipelineCacheSections &sections,
                       QJsonObject *report);

// GPU-free (tests/test_native_core_pipeline_cache.py): the format's accept and every refusal, the file's round trip, and
// two writer threads replacing the file while a reader reads it (never a torn read), in `directory`. One JSON object.
QByteArray pipelineCacheSelfTestJson(const QString &directory);

} // namespace srpss_core
