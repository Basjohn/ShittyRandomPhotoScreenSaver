// P1 spike: records, on every native render call, which thread ran it and
// whether that thread had a Python thread state. A thread without a Python
// thread state cannot hold the GIL and cannot run Python code.
#pragma once

#include <QtCore/QAtomicInteger>
#include <QtCore/QThread>
#include <QtCore/QCoreApplication>

namespace srpss_spike {

struct ThreadProbe
{
    QAtomicInteger<int> calls { 0 };
    QAtomicInteger<int> callsOnGuiThread { 0 };
    QAtomicInteger<int> callsWithPythonThreadState { 0 };
    QAtomicInteger<quintptr> lastThread { 0 };

    void hit();
    void reset()
    {
        calls.storeRelaxed(0);
        callsOnGuiThread.storeRelaxed(0);
        callsWithPythonThreadState.storeRelaxed(0);
        lastThread.storeRelaxed(0);
    }
};

} // namespace srpss_spike
