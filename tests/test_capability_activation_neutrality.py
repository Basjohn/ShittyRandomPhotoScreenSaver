"""Import-neutrality regression for the capability activation authority (Phase E).

``core.settings.capability_activation`` and ``core.settings.widget_family_catalog``
are the presentation-neutral authority that Settings SETUP and the future
``WidgetRuntimeManager`` consume. Importing them must NOT drag in QtWidgets, the
Settings tab/builder modules, widget implementations/providers, or Quick renderer
modules — otherwise the E1/E2 dependency boundary is violated (the exact defect
this test guards, doc 07 §1).

Runs in a fresh subprocess because the pytest process itself imports QtWidgets,
which would otherwise pollute ``sys.modules``.
"""
from __future__ import annotations

import subprocess
import sys

_PROBE = r"""
import sys
import core.settings.capability_activation  # noqa: F401
import core.settings.widget_family_catalog  # noqa: F401

mods = set(sys.modules)

forbidden_exact = {
    "PySide6.QtWidgets",
    "PySide6.QtGui",
    "rendering.widget_descriptors",
}
present_exact = sorted(forbidden_exact & mods)

# Presentation / implementation surfaces that must not be pulled transitively.
def _bad(name: str) -> bool:
    if name.startswith("ui."):
        return True
    if name.startswith("widgets."):          # widget implementations/providers
        return True
    if name.startswith("rendering.quick"):   # Quick renderer modules
        return True
    if "widgets_tab" in name:
        return True
    return False

present_prefixed = sorted(m for m in mods if _bad(m))

import json
print(json.dumps({"exact": present_exact, "prefixed": present_prefixed}))
"""


def test_capability_activation_authority_is_presentation_neutral():
    proc = subprocess.run(
        [sys.executable, "-c", _PROBE],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    import json

    payload = json.loads(proc.stdout.strip().splitlines()[-1])
    assert payload["exact"] == [], (
        "capability activation authority transitively imported a forbidden module: "
        f"{payload['exact']}"
    )
    assert payload["prefixed"] == [], (
        "capability activation authority transitively imported a presentation/"
        f"implementation module: {payload['prefixed']}"
    )
