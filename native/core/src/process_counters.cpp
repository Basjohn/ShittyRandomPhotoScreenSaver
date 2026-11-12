#include "process_counters.h"

#include <QtCore/QJsonDocument>
#include <QtCore/QJsonObject>

#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#include <psapi.h>
#include <tlhelp32.h>

namespace srpss_core {

namespace {

int processThreadCount()
{
    const DWORD pid = GetCurrentProcessId();
    HANDLE snapshot = CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0);
    if (snapshot == INVALID_HANDLE_VALUE)
        return -1;
    int count = 0;
    THREADENTRY32 entry = {};
    entry.dwSize = sizeof(entry);
    if (Thread32First(snapshot, &entry)) {
        do {
            if (entry.th32OwnerProcessID == pid)
                ++count;
            entry.dwSize = sizeof(entry);
        } while (Thread32Next(snapshot, &entry));
    }
    CloseHandle(snapshot);
    return count;
}

} // namespace

QByteArray processCountersJson()
{
    QJsonObject o;
    HANDLE process = GetCurrentProcess();
    DWORD handles = 0;
    GetProcessHandleCount(process, &handles);
    o.insert(QStringLiteral("handles"), qint64(handles));
    o.insert(QStringLiteral("gdi_objects"), qint64(GetGuiResources(process, GR_GDIOBJECTS)));
    o.insert(QStringLiteral("user_objects"), qint64(GetGuiResources(process, GR_USEROBJECTS)));
    o.insert(QStringLiteral("threads"), processThreadCount());
    PROCESS_MEMORY_COUNTERS_EX memory = {};
    memory.cb = sizeof(memory);
    if (K32GetProcessMemoryInfo(process, reinterpret_cast<PROCESS_MEMORY_COUNTERS *>(&memory), sizeof(memory))) {
        o.insert(QStringLiteral("private_mib"), double(memory.PrivateUsage) / (1024.0 * 1024.0));
        o.insert(QStringLiteral("working_set_mib"), double(memory.WorkingSetSize) / (1024.0 * 1024.0));
    }
    return QJsonDocument(o).toJson(QJsonDocument::Compact);
}

} // namespace srpss_core
