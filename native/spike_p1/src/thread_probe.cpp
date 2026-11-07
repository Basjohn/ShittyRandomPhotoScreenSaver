#define PY_SSIZE_T_CLEAN
#include <Python.h>

#include "thread_probe.h"

namespace srpss_spike {

void ThreadProbe::hit()
{
    calls.fetchAndAddRelaxed(1);
    QCoreApplication *app = QCoreApplication::instance();
    if (app && QThread::currentThread() == app->thread())
        callsOnGuiThread.fetchAndAddRelaxed(1);
    // Reads thread-local storage only; safe without the GIL.
    if (PyGILState_GetThisThreadState() != nullptr)
        callsWithPythonThreadState.fetchAndAddRelaxed(1);
    lastThread.storeRelaxed(quintptr(QThread::currentThreadId()));
}

} // namespace srpss_spike
