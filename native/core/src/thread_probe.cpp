#define PY_SSIZE_T_CLEAN
#include <Python.h>

#include "thread_probe.h"

#include <QtCore/QCoreApplication>
#include <QtCore/QThread>

namespace srpss_core {

quint64 currentThreadNumber()
{
    return quint64(quintptr(QThread::currentThreadId()));
}

bool onGuiThread()
{
    QCoreApplication *app = QCoreApplication::instance();
    return app && QThread::currentThread() == app->thread();
}

void ThreadProbe::hit()
{
    calls.fetchAndAddRelaxed(1);
    if (onGuiThread())
        callsOnGuiThread.fetchAndAddRelaxed(1);
    // Reads thread-local storage only; safe without the GIL (the spike's P1 probe).
    if (PyGILState_GetThisThreadState() != nullptr)
        callsWithPythonThreadState.fetchAndAddRelaxed(1);
    lastThread.storeRelaxed(currentThreadNumber());
}

} // namespace srpss_core
