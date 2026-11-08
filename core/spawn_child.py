"""Whether this interpreter is a worker process re-executing its parent's main module (checkpoint audit 10, A10-M1).

A ``spawn`` worker re-executes the parent's main module before its target: from source multiprocessing runs it as
``__mp_main__`` (``multiprocessing.spawn._fixup_main_from_path``; the Linux ``forkserver`` preloads it the same way),
and a Nuitka build runs the same executable with ``--multiprocessing-fork``, its root module compiled a second time as
``__parents_main__`` (the always-on multiprocessing plugin). Every worker role (the image workers, the Visualizer's
engine worker) therefore executed ``main.py``'s whole module level first, the Qt GUI, Quick and Widgets stack, the
engine and Settings included: measured 8 Nov at ~1.3 s more per spawn and ~80 MB more per worker than its own target
needs. ``main.py`` (and an entry wrapper that imports it, ``main_mc.py``) asks this before its application imports and
skips them in a worker: a worker only needs what its target imports, and its environment (the native thread-pool size,
the Quick render-loop variables) is inherited from the parent that set it. The parent's own module level is unchanged.

Standard library only: imported at the top of ``main.py``, in the parent and in every worker.
"""
from __future__ import annotations

import sys

#: The names multiprocessing gives the parent's main module when a worker re-executes it (source, then Nuitka).
SPAWN_MAIN_MODULE_NAMES = frozenset({"__mp_main__", "__parents_main__"})


def importing_parents_main(module_name: str) -> bool:
    """True while a worker process is executing its parent's main module (or something that module imports), so the
    module can leave out what only the application's own process needs.

    ``module_name`` is the caller's ``__name__``. Three cases: the main module itself re-executed under its spawn name;
    a module it imports, in a Nuitka worker (``__parents_main__`` is being imported); and the same from source or a
    forkserver (multiprocessing marks the process as inheriting while it prepares the parent's main module). A parent
    process, and a test or tool that imports the module normally, sees False: nothing changes there.
    """
    if module_name in SPAWN_MAIN_MODULE_NAMES or "__parents_main__" in sys.modules:
        return True
    process_module = sys.modules.get("multiprocessing.process")      # never imported here: a parent may not have it
    if process_module is None:
        return False
    current = getattr(process_module, "_current_process", None)
    return bool(getattr(current, "_inheriting", False))


__all__ = ["SPAWN_MAIN_MODULE_NAMES", "importing_parents_main"]
