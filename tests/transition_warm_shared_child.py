"""Child process of ``test_transition_warm_units.py`` (a fresh interpreter: imports are process-wide): which of the
given modules (default ``SHARED_RENDERER_MODULES``) no renderer module or its resolve on the native layer
(``native_transition_renderer``) imports, after the native layer's own module, printed as JSON.

Usage: python tests/transition_warm_shared_child.py [module ...]
"""
from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main() -> None:
    import rendering.quick.render.native_background  # noqa: F401  (imported by the product before any warm-up)
    from rendering.quick.transitions import implementation_registry as registry

    names = tuple(sys.argv[1:]) or registry.SHARED_RENDERER_MODULES
    before = set(sys.modules)
    from rendering.quick.render.native_background import native_transition_renderer

    for transition_id, descriptor in registry._BY_ID.items():
        importlib.import_module(descriptor.module_name)
        native_transition_renderer(transition_id)       # the layer's resolve unit, the warm-up's last

    pulled = set(sys.modules) - before
    print(json.dumps({"unused": [name for name in names if name not in pulled],
                      "renderers": len(registry._BY_ID)}))


if __name__ == "__main__":
    main()
