"""A custom combo popup shows one rounded outline: the view's, never a framed container around it.

Qt's private popup container is a QFrame that the native style frames and fills (the Windows 11
style draws a StyledPanel). Left alone, its opaque rectangle shows around the view's rounded
border as a second, nested outline. The real SettingsDialog's 3D Visualizers selectors and a
font combo are opened in an offscreen subprocess (never a visible window) under the production
``windows11`` style, and the popup windows are read as pixels. No theme colour is asserted: only
that everything outside the view's own rounded border is see-through.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.qt

_PROBE = r"""
import json, sys, tempfile
from pathlib import Path
from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget
app = QApplication(["combo-popup-probe"]); app.setStyle("windows11")
assert app.platformName() == "offscreen"
from core.animation import AnimationManager
from core.settings.settings_manager import SettingsManager
from ui.settings_dialog import SettingsDialog
from ui.tabs import shared_styles
from ui.widgets import StyledComboBox, StyledFontComboBox


def pump():
    for _ in range(8):
        app.processEvents()


def measure(combo):
    combo.showPopup(); pump()
    view = combo.view(); container = view.parentWidget()
    assert container.inherits("QComboBoxPrivateContainer") and container.isVisible()
    image = container.grab().toImage()
    g = view.geometry()
    # Pixels the view does not cover, plus the view's own corners (outside its rounded border).
    outside = [(x, y) for y in range(image.height()) for x in range(image.width())
               if not g.contains(x, y)]
    corners = [(g.left(), g.top()), (g.right(), g.top()), (g.left(), g.bottom()), (g.right(), g.bottom())]
    alpha = lambda p: image.pixelColor(*p).alpha() if image.hasAlphaChannel() else 255
    mid_y = g.center().y()
    # Opaque runs on the middle row from the left edge to the first interior pixel.
    row = [alpha((x, mid_y)) for x in range(0, g.left() + 4)]
    result = {
        "frame_width": container.frameWidth(),
        "opaque_outside": sum(1 for p in outside if alpha(p) > 0),
        "outside": len(outside),
        "opaque_corners": sum(1 for p in corners if alpha(p) > 0),
        "row": row,
    }
    combo.hidePopup(); pump()
    return result


settings = SettingsManager(application="combopopupprobe", storage_base_dir=Path(tempfile.mkdtemp()))
settings.set("sources.folders", [str(Path(tempfile.mkdtemp()))])
dialog = SettingsDialog(settings, AnimationManager()); dialog.resize(1280, 900); dialog.show(); pump()
index = dialog._tab_index_for_key("scene3d")
dialog._switch_tab(index, animate=False); pump()
tab = dialog.content_stack.widget(index)
tab.show_page("visualizers"); pump()
combos = [c for c in tab.findChildren(StyledComboBox) if c.isVisibleTo(tab)]
assert combos, "no visible 3D Visualizers selector"
results = {"scene3d": measure(combos[0])}

host = QWidget(); host.resize(420, 120); QVBoxLayout(host)
shared_styles.bind_shared_styles(host, "COMBOBOX_STYLE")
font_combo = StyledFontComboBox(size_variant="compact")
host.layout().addWidget(font_combo); host.show(); pump()
results["font"] = measure(font_combo)
print("RESULT " + json.dumps(results), flush=True)
import os; os._exit(0)  # skip Qt teardown; the answer is already out
"""


def _probe() -> dict:
    root = Path(__file__).resolve().parents[1]
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", QT_QPA_FONTDIR="C:/Windows/Fonts", PYTHONPATH=str(root))
    completed = subprocess.run([sys.executable, "-c", _PROBE], cwd=root, env=env,
                               capture_output=True, text=True, timeout=240)
    line = next((l for l in completed.stdout.splitlines() if l.startswith("RESULT ")), None)
    assert line is not None, completed.stderr[-3000:]
    return json.loads(line[len("RESULT "):])


def test_custom_combo_popups_draw_one_rounded_outline():
    results = _probe()
    for name, popup in results.items():
        # The container contributes no frame and no fill: nothing outside the view is painted ...
        assert popup["frame_width"] == 0, (name, popup)
        assert popup["opaque_outside"] == 0, (name, popup)
        # ... and the view's own corners, outside its rounded border, stay see-through.
        assert popup["opaque_corners"] == 0, (name, popup)
        # From the window edge inward the first painted pixel is the view's own border: a single
        # transparent -> opaque step, with no opaque band (a second outline) in front of it.
        row = popup["row"]
        first = next(i for i, a in enumerate(row) if a > 0)
        assert all(a == 0 for a in row[:first]), (name, popup)
