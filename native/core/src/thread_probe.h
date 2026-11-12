// D5.4's probe (the P1 spike's, rerun at every port): on every call into the core's frame work it records which thread
// ran it and whether that thread had a Python thread state. A thread without one cannot hold the GIL and cannot run
// Python code; the core's render-thread work must report zero. Plain atomics: nothing is allocated or locked per call.
#pragma once

#include <QtCore/QAtomicInteger>

namespace srpss_core {

struct ThreadProbe
{
    QAtomicInteger<qint64> calls { 0 };
    QAtomicInteger<qint64> callsOnGuiThread { 0 };
    QAtomicInteger<qint64> callsWithPythonThreadState { 0 };
    QAtomicInteger<quint64> lastThread { 0 };

    void hit();
};

// The calling thread's id (QThread::currentThreadId), as a number.
quint64 currentThreadNumber();
// Whether the calling thread is the application's (GUI) thread.
bool onGuiThread();

} // namespace srpss_core
