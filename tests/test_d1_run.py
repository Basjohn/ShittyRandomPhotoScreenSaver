"""``tools/d1_run.py``: the lead's Display 1 run harness, proved without showing a window (1B.14).

Argument handling, the refusals, the profile copy and its settings edits, the crop code on synthetic images, the
teardown paths (a child that hangs, one that exits early, a guard violation) and the verdict. The real saver is never
started here; the hidden end-to-end run is the agent's probe, the visible one the lead's.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import psutil
import pytest

from tools import artifact_paths
from tools import d1_run

D0 = d1_run.Display(0, "MSI", True, 0, 0, 1707, 960, 1.5)
D1 = d1_run.Display(1, "LG TV", False, 2560, 0, 2560, 1440, 1.5)
MONITORS = [d1_run.Monitor(0, 0, 2560, 1440, True, r"\\.\DISPLAY1"),
            d1_run.Monitor(2560, 0, 6400, 2160, False, r"\\.\DISPLAY2")]


# -- arguments --------------------------------------------------------------------------------------------------------

def test_steps_parse_and_malformed_ones_are_usage_errors():
    assert d1_run.parse_step("12:grab:Steady A") == d1_run.Step(12.0, "grab", "steady_a")
    assert d1_run.parse_step("3.5:key:esc").arg == "esc"
    assert d1_run.parse_step("4:click:@visualizerExpandGlyph").arg == "@visualizerExpandGlyph"
    assert d1_run.parse_target("10, 20") == ("point", 10, 20)
    for bad in ("12:grab", "x:grab:a", "0:grab:a", "-1:grab:a", "nan:grab:a", "5:jump:a", "5:key:NOPE",
                "5:click:10", "5:click:@", "5:grab:..."):
        with pytest.raises(Exception):
            d1_run.parse_step(bad)


def test_the_display_is_required_and_bounds_hold(capsys):
    for argv in ([], ["--display", "-1"], ["--display", "1", "--seconds", "0"], ["--display", "1", "--seconds", "601"],
                 ["--display", "1", "--viz-set", "devcurve_bar_count=8"], ["--display", "1", "--zoom", "0"],
                 ["--display", "1", "--app-arg=--only-display=0"], ["--display", "1", "--diag", "fresh"],
                 ["--display", "1", "--diag", "exit-after"]):
        with pytest.raises(SystemExit):
            d1_run.parse_args(argv)
    assert d1_run.parse_args(["--list-displays"]).list_displays


def test_the_runner_command_forwards_every_option(tmp_path):
    argv =["--display", "1", "--seconds", "25", "--hidden", "--diag", "perf", "--app-arg=--viz-in-process",
            "--step", "16:grab:b", "--step", "12:grab:a", "--crop", "left-mid", "--crop", "bottom-right",
            "--setting", "widgets.global.card_border_width_px=5", "--item", "visualizerCardFrame", "--zoom", "3",
            "--entry", "main"]
    args = d1_run.parse_args(argv)
    assert [step.text() for step in args.step] == ["12:grab:a", "16:grab:b"]            # sorted by time
    assert args.diag == ["--perf", "--noupdates"]                 # no live network unless --updates
    assert d1_run.parse_args(["--display", "1", "--updates"]).diag == []
    with artifact_paths.use_root(tmp_path / ".artifacts"):
        out = artifact_paths.scratch_root("d1_run") / "run" / "out"     # where the parent points the runner
        command = d1_run.runner_command(args, out)
        assert command[1].endswith("d1_run.py") and "--runner" in command
        forwarded = d1_run.parse_args(command[2:])
    assert forwarded.out == out.resolve() and forwarded.runner
    for name in ("display", "seconds", "hidden", "diag", "app_arg", "step", "crop", "setting", "item", "zoom",
                 "entry", "crop_size", "clip"):
        assert getattr(forwarded, name) == getattr(args, name), name


# -- refusals ---------------------------------------------------------------------------------------------------------

def test_the_display_choice_refuses_one_display_a_missing_index_and_the_primary():
    assert d1_run.check_display_choice([D0, D1], 1) is D1
    for displays, index in (([D1], 1), ([D0, D1], 2), ([D0, D1], 0)):
        with pytest.raises(d1_run.Refusal):
            d1_run.check_display_choice(displays, index)
    assert d1_run.check_display_choice([D0, D1], 0, allow_primary=True) is D0
    with pytest.raises(d1_run.Refusal, match="only 1 display"):
        d1_run.check_display_choice([D0], 0, allow_primary=True)


def test_the_windows_monitor_must_match_exactly_one_and_not_the_primary():
    assert d1_run.match_monitor(D1, MONITORS) is MONITORS[1]
    with pytest.raises(d1_run.Refusal, match="matches 0"):
        d1_run.match_monitor(D1, MONITORS[:1])
    with pytest.raises(d1_run.Refusal, match="matches 2"):
        d1_run.match_monitor(D1, [MONITORS[1], MONITORS[1]])
    # Qt says not primary but Windows does: still refused.
    swapped = [MONITORS[0], d1_run.Monitor(2560, 0, 6400, 2160, True, r"\\.\DISPLAY2")]
    with pytest.raises(d1_run.Refusal, match="primary"):
        d1_run.match_monitor(D1, swapped)


def test_the_plan_refuses_late_steps_hidden_desktop_grabs_and_unknown_settings():
    def plan(*argv):
        d1_run.check_plan(d1_run.parse_args(["--display", "1", "--seconds", "20", *argv]))

    plan("--step", "15:grab:a", "--crop", "left-mid", "--setting", "widgets.global.card_border_width_px=5")
    for argv in (["--step", "18:grab:a"], ["--hidden", "--step", "5:screen:a"], ["--crop", "left-mid"],
                 ["--setting", "widgets.global.no_such_key=1"],
                 ["--mode", "devcurve", "--setting", "widgets.spotify_visualizer.devcurve_bar_border_opacity=1.0"]):
        with pytest.raises(d1_run.Refusal):
            plan(*argv)


# -- two displays, the second always invisible (1C.2) -------------------------------------------------------------------

def test_a_step_can_name_the_always_invisible_display_and_only_with_in_process_input_or_a_grab():
    assert d1_run.parse_step("10:hover@0:@visualizerCardFrame") == d1_run.Step(10.0, "hover", "@visualizerCardFrame", 0)
    assert d1_run.parse_step("11:press@0:@visualizerExpandRightGlyph").text() == "11:press@0:@visualizerExpandRightGlyph"
    with pytest.raises(Exception):
        d1_run.parse_step("5:grab@x:a")

    def plan(*argv):
        d1_run.check_plan(d1_run.parse_args(["--display", "1", "--seconds", "20", *argv]))

    plan("--with-hidden-display", "0", "--step", "5:hover@0:@visualizerCardFrame", "--step", "6:press@0:10,10",
         "--step", "7:grab@0:moved")
    for argv in (["--step", "5:grab@0:a"],                                          # no such display in the run
                 ["--with-hidden-display", "0", "--step", "5:click@0:@visualizerCardFrame"],   # posted: dropped
                 ["--with-hidden-display", "0", "--step", "5:screen@0:a"],          # its desktop shows something else
                 ["--with-hidden-display", "0", "--step", "5:key@0:esc"]):
        with pytest.raises(d1_run.Refusal):
            plan(*argv)
    with pytest.raises(SystemExit):
        d1_run.parse_args(["--display", "1", "--with-hidden-display", "1"])


def test_the_runner_command_forwards_the_invisible_display(tmp_path):
    args = d1_run.parse_args(["--display", "1", "--with-hidden-display", "0", "--hidden",
                              "--step", "5:press@0:@visualizerExpandRightGlyph"])
    with artifact_paths.use_root(tmp_path / ".artifacts"):
        command = d1_run.runner_command(args, artifact_paths.scratch_root("d1_run") / "run" / "out")
        forwarded = d1_run.parse_args(command[2:])
    assert forwarded.with_hidden_display == 0 and forwarded.step == args.step


def test_the_visible_second_display_needs_its_pair_and_the_primary_permission(tmp_path):
    """``--second-display-visible`` (the lead's two-display run, 13 Nov): refused without ``--with-hidden-display``,
    without ``--allow-primary`` or with ``--hidden``; the runner gets both flags back."""
    base = ["--display", "1", "--with-hidden-display", "0"]
    for argv in (["--display", "1", "--second-display-visible", "--allow-primary"],     # no second display named
                 [*base, "--second-display-visible"],                                    # no primary permission
                 [*base, "--second-display-visible", "--allow-primary", "--hidden"]):    # visible and hidden at once
        with pytest.raises(SystemExit):
            d1_run.parse_args(argv)
    args = d1_run.parse_args([*base, "--second-display-visible", "--allow-primary"])
    assert args.second_display_visible
    assert not d1_run.parse_args(base).second_display_visible                          # off unless asked
    with artifact_paths.use_root(tmp_path / ".artifacts"):
        command = d1_run.runner_command(args, artifact_paths.scratch_root("d1_run") / "run" / "out")
        forwarded = d1_run.parse_args(command[2:])
    assert forwarded.second_display_visible and forwarded.allow_primary and forwarded.with_hidden_display == 0


def test_the_pair_admits_exactly_the_two_displays_present():
    class Manager:
        def _get_allowed_screen_indices(self, screen_count):
            return set(range(screen_count))              # the profile's selection: every screen

    d1_run.install_display_pair(1, 0, manager_class=Manager)
    assert Manager()._get_allowed_screen_indices(3) == {0, 1}         # never the third
    assert Manager()._get_allowed_screen_indices(1) == {0}            # a display gone: never another


def test_the_guard_admits_an_off_display_window_only_while_it_cannot_show_a_pixel(monkeypatch):
    """The visible run's guard: a saver window on another monitor kills the run unless the run has an
    always-invisible display and that window cannot show a pixel (``window_could_show`` is None)."""
    chosen = (2560, 0, 6400, 2160)
    other = (0, 0, 2560, 1440)
    showing = {"value": "hwnd 7 could show"}
    monkeypatch.setattr(d1_run.live_check, "window_could_show", lambda _hwnd: showing["value"])
    monitor = MONITORS[1]
    assert not d1_run.off_display_violates(7, chosen, monitor, unseen_ok=True)       # on the chosen display
    assert d1_run.off_display_violates(7, other, monitor, unseen_ok=False)
    assert d1_run.off_display_violates(7, other, monitor, unseen_ok=True)            # it could show: killed
    showing["value"] = None
    assert not d1_run.off_display_violates(7, other, monitor, unseen_ok=True)        # invisible: admitted
    assert d1_run.off_display_violates(7, other, monitor, unseen_ok=False)           # only with the option


def test_the_two_display_guard_judges_each_window_of_one_scan_by_handle():
    """``--second-display-visible``: a window violates only when it is on neither named monitor. One scan per check;
    a window that moves between two scans (or whose rect changes) is still judged, by its handle."""
    chosen, second = MONITORS
    elsewhere = (6400, 0, 8320, 1080)                                    # a third monitor
    as_rect = lambda monitor: (monitor.left, monitor.top, monitor.right, monitor.bottom)  # noqa: E731
    scans = [
        [d1_run.VisibleWindow(1, as_rect(chosen), "hwnd 1 rect A"), d1_run.VisibleWindow(2, as_rect(second), "hwnd 2"),
         d1_run.VisibleWindow(3, elsewhere, "hwnd 3 rect (6400, 0, 7000, 600)")],
        # The next scan of the same windows: hwnd 3 has moved (a new rect, so a new description).
        [d1_run.VisibleWindow(1, as_rect(chosen), "hwnd 1 rect A"), d1_run.VisibleWindow(2, as_rect(second), "hwnd 2"),
         d1_run.VisibleWindow(3, elsewhere, "hwnd 3 rect (6500, 0, 7100, 600)")],
    ]
    calls = []

    def scan(pids):
        calls.append(pids)
        return scans[len(calls) - 1]

    guard = d1_run.two_display_guard(chosen, second, scan=scan)
    assert guard({9}) == ["hwnd 3 rect (6400, 0, 7000, 600)"]
    assert len(calls) == 1                                                # one scan per check
    # Both admitted monitors stay admitted; only the window on neither is named.
    assert d1_run.windows_off_monitors(scans[0][:2], (chosen, second)) == []

    # Negative control: the old guard, two scans compared as strings, lets the moving window through.
    calls.clear()

    def old_guard(pids):
        outside_second = set(d1_run.off_display_windows(pids, second, scan=scan))
        return [entry for entry in d1_run.off_display_windows(pids, chosen, scan=scan) if entry in outside_second]

    assert old_guard({9}) == [] and len(calls) == 2


def _fake_appdata(tmp_path) -> Path:
    appdata = tmp_path / "appdata"
    (appdata / "SRPSS").mkdir(parents=True)
    (appdata / "SRPSS_MC").mkdir()
    for folder in ("SRPSS", "SRPSS_MC"):
        (appdata / folder / "settings_v2.json").write_text(json.dumps(
            {"snapshot": {"widgets": {"spotify_visualizer": {"mode": "bubble", "preset_bubble": 0}}}}))
    return appdata


def test_settings_are_written_to_the_copy_through_the_settings_manager_and_read_back(tmp_path, qt_app):
    from core.settings import SettingsManager

    applied = d1_run.apply_settings([("widgets.global.card_border_width_px", 5),
                                     ("widgets.spotify_visualizer.expanded_display_requested", True)],
                                    application="Screensaver_MC", storage_base_dir=tmp_path / "copy")
    assert applied["widgets.global.card_border_width_px"]["after"] == 5
    assert Path(applied["_path"]) == (tmp_path / "copy" / "SRPSS_MC" / "settings_v2.json").resolve()
    reopened = SettingsManager(application="Screensaver_MC", storage_base_dir=tmp_path / "copy")
    reopened.load()
    assert reopened.get("widgets.global.card_border_width_px") == 5
    assert reopened.get("widgets.spotify_visualizer.expanded_display_requested") is True
    with pytest.raises(KeyError):
        d1_run.apply_settings([("widgets.global.no_such_key", 1)], application="Screensaver_MC",
                              storage_base_dir=tmp_path / "copy")
    # A member of a mapping setting (1D.2's display style): merged into the stored record, the rest kept.
    key = "widgets.spotify_visualizer.fullscreen_overlays"
    stored = reopened.get(key)
    applied = d1_run.apply_settings([(f"{key}.display_style", "borders_to_edge")], application="Screensaver_MC",
                                    storage_base_dir=tmp_path / "copy")
    assert applied[f"{key}.display_style"]["after"] == "borders_to_edge"
    merged = SettingsManager(application="Screensaver_MC", storage_base_dir=tmp_path / "copy").get(key)
    assert merged == {**stored, "display_style": "borders_to_edge"}
    with pytest.raises(KeyError):
        d1_run.apply_settings([(f"{key}.no_such_member", 1)], application="Screensaver_MC",
                              storage_base_dir=tmp_path / "copy")


def test_a_set_step_writes_a_setting_or_a_member_live_through_the_savers_own_manager(tmp_path, qt_app):
    """1D.2: ``AT:set:DOTTED.KEY=JSON`` (a style switch while expanded) writes through the running saver's
    SettingsManager, as Settings would: a whole setting, or one member of a mapping-valued setting merged into it
    (everything else in it kept), read back; an unknown key or member is refused before anything starts."""
    from types import SimpleNamespace

    from core.settings import SettingsManager

    step = d1_run.parse_step('14:set:widgets.spotify_visualizer.fullscreen_overlays.display_style="hide_borders"')
    assert step.kind == "set"
    manager = SettingsManager(application="Screensaver_MC", storage_base_dir=tmp_path / "live")
    before = manager.get("widgets.spotify_visualizer.fullscreen_overlays")
    (tmp_path / "out").mkdir()
    driver = d1_run.D1Driver([step], display=1, out=tmp_path / "out")
    driver._engine = SimpleNamespace(settings_manager=manager)
    driver.fire(0)
    assert driver.results[-1]["ok"] is True, driver.results[-1]
    after = manager.get("widgets.spotify_visualizer.fullscreen_overlays")
    assert after["display_style"] == "hide_borders"
    assert {k: v for k, v in after.items() if k != "display_style"} == {
        k: v for k, v in before.items() if k != "display_style"}
    for bad in ("widgets.spotify_visualizer.fullscreen_overlays.no_such_member", "widgets.global.no_such_key"):
        with pytest.raises(d1_run.Refusal):
            d1_run.check_plan(d1_run.parse_args(["--display", "1", "--seconds", "20",
                                                 "--step", f"5:set:{bad}=1"]))
        driver.steps = [d1_run.parse_step(f"5:set:{bad}=1")]
        driver.fire(0)
        assert driver.results[-1]["ok"] is False


def test_the_main_entry_edits_its_own_profile_and_the_source_is_never_touched(tmp_path):
    from tools.visualizer_live_check import _prepare_profile

    appdata = _fake_appdata(tmp_path)
    before = {folder: (appdata / folder / "settings_v2.json").read_text() for folder in ("SRPSS", "SRPSS_MC")}
    root = _prepare_profile(tmp_path / "run", "devcurve", 2, {}, appdata_root=appdata, settings_folder="SRPSS")
    ordinary = json.loads((root / "SRPSS" / "settings_v2.json").read_text())["snapshot"]["widgets"]
    assert ordinary["spotify_visualizer"]["mode"] == "devcurve"
    assert ordinary["spotify_visualizer"]["preset_devcurve"] == 1
    assert json.loads((root / "SRPSS_MC" / "settings_v2.json").read_text()) == json.loads(before["SRPSS_MC"])
    plain = _prepare_profile(tmp_path / "run2", None, None, {}, appdata_root=appdata)
    assert (plain / "SRPSS_MC" / "settings_v2.json").read_text() == before["SRPSS_MC"]
    assert {folder: (appdata / folder / "settings_v2.json").read_text() for folder in before} == before


# -- crops on synthetic images ----------------------------------------------------------------------------------------

def test_named_points_and_crops_stay_on_the_rectangle_and_inside_the_image():
    rect = (100.0, 50.0, 400.0, 200.0)
    assert d1_run.anchor_point(rect, "left-mid") == (100.0, 150.0)
    assert d1_run.anchor_point(rect, "bottom-mid") == (300.0, 250.0)
    assert d1_run.anchor_point(rect, "bottom-left") == (100.0, 250.0)
    assert d1_run.anchor_point(rect, "bottom-right") == (500.0, 250.0)
    assert d1_run.anchor_point(rect, "top-right") == (500.0, 50.0)
    assert d1_run.anchor_point(rect, "center") == (300.0, 150.0)
    assert d1_run.crop_rect(rect, "left-mid", 32, (1000, 600)) == (84, 134, 32, 32)
    assert d1_run.crop_rect((0.0, 0.0, 1000.0, 600.0), "bottom-right", 32, (1000, 600)) == (968, 568, 32, 32)
    assert d1_run.crop_rect((0.0, 0.0, 1000.0, 600.0), "top-left", 32, (1000, 600)) == (0, 0, 32, 32)
    with pytest.raises(ValueError):
        d1_run.crop_rect(rect, "middle", 32, (1000, 600))


def test_a_zoomed_crop_is_the_source_pixels_in_exact_blocks(qt_app):
    from PySide6.QtGui import QColor, QImage

    image = QImage(64, 48, QImage.Format.Format_ARGB32)
    for y in range(48):
        for x in range(64):
            image.setPixelColor(x, y, QColor((x * 4) % 256, (y * 5) % 256, (x + y) % 256))
    image.setDevicePixelRatio(1.5)                           # as grabWindow returns it: the crop must ignore it
    rect = d1_run.crop_rect((10.0, 8.0, 40.0, 30.0), "bottom-left", 8, (64, 48))
    zoomed = d1_run.zoom_crop(image, rect, 4)
    assert (zoomed.width(), zoomed.height()) == (32, 32)
    x0, y0 = rect[:2]
    for zy in range(32):
        for zx in range(32):
            assert zoomed.pixelColor(zx, zy) == image.pixelColor(x0 + zx // 4, y0 + zy // 4), (zx, zy)


def test_a_grabbed_frame_is_encoded_off_the_gui_thread_and_recorded_on_it(qt_app, tmp_path):
    """A grab's PNG encode never runs on the saver's GUI thread (1C.2: a 4K encode there took 2.0-2.3 s, no window
    rendered meanwhile, and a 1.85 s display move took 7 s). The grab returns at once with its record still open; the
    encode runs on another thread; the record is completed on the GUI thread; an exit drain writes what is pending.
    Control: on the pre-fix harness the record was complete, and the file written by the GUI thread, on return."""
    import threading
    import time

    from PySide6.QtGui import QColor, QImage

    driver = d1_run.D1Driver([], display=1, out=tmp_path)
    encoded_on, completed_on = [], []
    save_frame, complete = driver._save_frame, driver._complete

    def recording_save(*args):
        encoded_on.append(threading.current_thread())
        return save_frame(*args)

    def recording_complete(record):
        completed_on.append(threading.current_thread())
        complete(record)
    driver._save_frame, driver._complete = recording_save, recording_complete
    image = QImage(64, 48, QImage.Format.Format_RGBX8888)
    image.fill(QColor(10, 20, 30))
    records = []
    for name in ("a", "b"):
        record = {"index": len(records), "step": f"1:grab:{name}"}
        records.append(record)
        driver._grabbed(None, d1_run.Step(1.0, "grab", name), record, image)
        assert driver.results == [] and "ok" not in record          # nothing written or recorded on the GUI thread
    deadline = time.monotonic() + 10.0
    while len(driver.results) < 1 and time.monotonic() < deadline:
        qt_app.processEvents()
        time.sleep(0.005)
    driver.finish()                                                  # the exit drain: whatever is still pending
    assert [r["frame"] for r in driver.results] == ["a.png", "b.png"]
    assert all(r["ok"] for r in driver.results)
    assert all((tmp_path / "frames" / r["frame"]).is_file() for r in driver.results)
    assert encoded_on and all(t is not threading.main_thread() for t in encoded_on)
    assert completed_on == [threading.main_thread()] * 2


_GRAB_SCRIPT = r'''
import json
import sys

sys.path.insert(0, sys.argv[1])
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QGuiApplication, QOpenGLContext
from PySide6.QtQuick import QQuickView, QQuickWindow, QSGRendererInterface

from tools import d1_run

API = {"opengl": QSGRendererInterface.GraphicsApi.OpenGL, "vulkan": QSGRendererInterface.GraphicsApi.Vulkan}
QQuickWindow.setGraphicsApi(API[sys.argv[2]])
app = QGuiApplication([])
window = QQuickView()
window.setOpacity(0.0)
window.setFlag(Qt.WindowType.WindowTransparentForInput, True)
window.setFlag(Qt.WindowType.Tool, True)
window.setResizeMode(QQuickView.ResizeMode.SizeRootObjectToView)
window.setSource(QUrl.fromLocalFile(sys.argv[3]))
window.resize(320, 200)
out = {"old_path": None}


def old_path():
    """The pre-N2.8 grab's first step: an OpenGL context current on the render thread inside afterRendering."""
    window.afterRendering.disconnect(old_path)
    window.beginExternalCommands()
    try:
        out["old_path"] = "ok" if QOpenGLContext.currentContext() is not None else \
            "no current OpenGL context in afterRendering"
    finally:
        window.endExternalCommands()


def done(result):
    try:
        out["delivered"] = type(result).__name__
        if isinstance(result, Exception):
            out["error"] = repr(result)
        else:
            image = d1_run.frame_image(result)
            out["size"] = [image.width(), image.height()]
            out["device_size"] = [round(320 * window.devicePixelRatio()), round(200 * window.devicePixelRatio())]
            out["pixels"] = {f"{fx},{fy}": image.pixelColor(int(image.width() * fx),
                                                            int(image.height() * fy)).name()
                             for fx, fy in ((0.25, 0.25), (0.75, 0.25), (0.25, 0.75), (0.75, 0.75))}
            out["render_thread_ms"] = grabs[0].render_thread_ms
    except Exception as exc:
        out["error"] = repr(exc)
    print("RESULT " + json.dumps(out), flush=True)
    app.quit()


grabs = []


def first_frame():
    if grabs:
        return
    window.afterRendering.connect(old_path, Qt.ConnectionType.DirectConnection)
    grabs.append(d1_run._FrameGrab(window, done))


window.frameSwapped.connect(first_frame)
window.show()
app.exec()
'''

_QUADRANTS_QML = """import QtQuick
Item {
    Rectangle { x: 0; y: 0; width: parent.width / 2; height: parent.height / 2; color: "#ff0000" }
    Rectangle { x: parent.width / 2; y: 0; width: parent.width / 2; height: parent.height / 2; color: "#00ff00" }
    Rectangle { x: 0; y: parent.height / 2; width: parent.width / 2; height: parent.height / 2; color: "#0000ff" }
    Rectangle { x: parent.width / 2; y: parent.height / 2; width: parent.width / 2; height: parent.height / 2
                color: "#ffffff" }
}
"""


@pytest.mark.parametrize("backend", ["opengl", "vulkan"])
def test_a_grab_reads_the_drawn_frame_back_on_both_backends_and_makes_the_image_off_the_render_thread(
        tmp_path, backend):
    """N2.8: the grab reads the swap chain back through QRhi, so it works on OpenGL and Vulkan: the grabbed pixels
    are the known drawn frame (four coloured quadrants, the right way up) at the window's device pixels. 1C.2: the
    render thread hands over the raw read-back (``RawFrame``); the image is made on the writer thread.
    Controls: the old path (an OpenGL context current in ``afterRendering``) fails on Vulkan here; on the pre-fix
    harness the Vulkan grab failed with that error and the OpenGL grab delivered a ``QImage`` made on the render thread.
    An invisible window in a child process (the graphics API is chosen once per process)."""
    import subprocess

    script = tmp_path / "grab_child.py"
    script.write_text(_GRAB_SCRIPT, encoding="utf-8")
    scene = tmp_path / "quadrants.qml"
    scene.write_text(_QUADRANTS_QML, encoding="utf-8")
    root = Path(__file__).resolve().parents[1]
    completed = subprocess.run([sys.executable, str(script), str(root), backend, str(scene)], capture_output=True,
                               text=True, timeout=120)
    lines = [line for line in completed.stdout.splitlines() if line.startswith("RESULT ")]
    assert lines, completed.stdout + completed.stderr
    out = json.loads(lines[-1][len("RESULT "):])
    assert out["delivered"] == "RawFrame", out
    assert out["size"] == out["device_size"]
    assert out["pixels"] == {"0.25,0.25": "#ff0000", "0.75,0.25": "#00ff00", "0.25,0.75": "#0000ff",
                             "0.75,0.75": "#ffffff"}
    assert out["render_thread_ms"] is not None
    expected_old = "ok" if backend == "opengl" else "no current OpenGL context in afterRendering"
    assert out["old_path"] == expected_old


def test_steps_are_armed_on_precise_timers_and_fire_in_order(qt_app, tmp_path):
    """Qt's default single-shot is coarse (5 %: about 1 s at 22 s) and reordered steps planned 0.1 s apart (12 Nov: a
    grab fired before the press it was meant to follow). Every step is armed precise and fires in plan order.
    Control: the pre-fix harness armed coarse timers."""
    import time

    from PySide6.QtCore import QObject, Qt, QTimer

    steps = [d1_run.Step(0.05, "key", "esc"), d1_run.Step(0.06, "key", "esc"), d1_run.Step(0.08, "key", "esc")]
    driver = d1_run.D1Driver(steps, display=1, out=tmp_path)
    fired = []
    driver.fire = lambda index: fired.append(index)
    engine = QObject()
    driver._on_reveal(engine)
    armed = [timer for timer in engine.findChildren(QTimer) if timer.isActive()]
    assert len(armed) == 3 and all(timer.timerType() == Qt.TimerType.PreciseTimer for timer in armed)
    deadline = time.monotonic() + 5.0
    while len(fired) < 3 and time.monotonic() < deadline:
        qt_app.processEvents()
        time.sleep(0.002)
    assert fired == [0, 1, 2]


# -- teardown ---------------------------------------------------------------------------------------------------------

def _child(tmp_path, body: str) -> list[str]:
    script = tmp_path / "child.py"
    script.write_text(body, encoding="utf-8")
    return [sys.executable, str(script)]


def test_a_child_that_hangs_is_ended_by_the_watchdog_and_nothing_is_left(tmp_path):
    command = _child(tmp_path, "import subprocess, sys, time\n"
                               "subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)'])\n"
                               "time.sleep(120)\n")
    seen = {}

    def guard(pids):
        seen.setdefault("pids", set()).update(pids)
        return []

    outcome = d1_run.supervise(command, log_path=tmp_path / "runner.txt", deadline_s=3.0, guard=guard)
    assert outcome["ended"] == "watchdog" and outcome["seconds"] < 30
    assert not psutil.pid_exists(outcome["pid"]) or psutil.Process(outcome["pid"]).status() == psutil.STATUS_ZOMBIE
    for pid in seen["pids"]:                                  # the grandchild went with the tree
        assert not psutil.pid_exists(pid) or not psutil.Process(pid).is_running()


def test_a_child_that_exits_early_is_a_failure_with_its_code(tmp_path):
    outcome = d1_run.supervise(_child(tmp_path, "import sys\nprint('bye')\nsys.exit(3)\n"),
                               log_path=tmp_path / "runner.txt", deadline_s=60.0)
    assert outcome == {**outcome, "ended": "exited", "returncode": 3, "violation": None}
    assert "bye" in (tmp_path / "runner.txt").read_text()
    verdict = d1_run.analyse_run(tmp_path, outcome, [d1_run.Step(5.0, "grab", "a")])
    assert any("exited with code 3" in failure for failure in verdict["failures"])
    assert any("never revealed" in failure for failure in verdict["failures"])
    assert any("never ran" in failure for failure in verdict["failures"])


def test_a_guard_violation_kills_the_run(tmp_path):
    outcome = d1_run.supervise(_child(tmp_path, "import time\ntime.sleep(120)\n"), log_path=tmp_path / "runner.txt",
                               deadline_s=60.0, guard=lambda pids: ["hwnd 1 on monitor (0, 0, 2560, 1440)"])
    assert outcome["ended"] == "guard" and outcome["violation"] and outcome["seconds"] < 30
    verdict = d1_run.analyse_run(tmp_path, outcome, [])
    assert any("left the chosen display" in failure for failure in verdict["failures"])


# -- the verdict ------------------------------------------------------------------------------------------------------

def _state(tmp_path, *, events=("initialized", "reveal", "armed", "exit_after_stop", "finish"), results=None):
    steps = [d1_run.Step(5.0, "grab", "a")]
    state = {"events": [{"event": name, "at": i} for i, name in enumerate(events)],
             "results": results if results is not None else [{"index": 0, "step": "5:grab:a", "ok": True}],
             "received": None}
    (tmp_path / d1_run.STATE_NAME).write_text(json.dumps(state))
    (tmp_path / "logs").mkdir(exist_ok=True)
    (tmp_path / "logs" / "screensaver_frame_trace.bin").write_bytes(b"trace")
    return steps


def test_a_complete_run_passes_and_each_missing_piece_fails_it(tmp_path):
    ok = {"ended": "exited", "returncode": 0, "violation": None}
    steps = _state(tmp_path)
    assert d1_run.analyse_run(tmp_path, ok, steps)["failures"] == []
    _state(tmp_path, events=("initialized", "reveal", "armed", "finish"))
    assert any("--exit-after" in f for f in d1_run.analyse_run(tmp_path, ok, steps)["failures"])
    _state(tmp_path, results=[{"index": 0, "step": "5:grab:a", "ok": False, "error": "no item"}])
    assert any("failed: no item" in f for f in d1_run.analyse_run(tmp_path, ok, steps)["failures"])
    _state(tmp_path)
    (tmp_path / "logs" / "native_faults.log").write_text("Windows fatal exception: access violation\n")
    assert any("native fault" in f for f in d1_run.analyse_run(tmp_path, ok, steps)["failures"])
    (tmp_path / "logs" / "native_faults.log").unlink()
    (tmp_path / "logs" / "screensaver_frame_trace.bin").unlink()
    assert any("frame trace" in f for f in d1_run.analyse_run(tmp_path, ok, steps)["failures"])
    _state(tmp_path)
    assert any("watchdog" in f for f in d1_run.analyse_run(tmp_path, {**ok, "ended": "watchdog"}, steps)["failures"])


def test_posted_input_the_window_never_received_fails_a_visible_run_and_is_noted_in_a_hidden_one(tmp_path):
    ok = {"ended": "exited", "returncode": 0, "violation": None}
    _state(tmp_path, results=[{"index": 0, "step": "5:move:1,1", "ok": True}])
    steps = [d1_run.Step(5.0, "move", "1,1")]
    state = json.loads((tmp_path / d1_run.STATE_NAME).read_text())
    state["received"] = {"mouse_move": 0, "key_press": 0}
    (tmp_path / d1_run.STATE_NAME).write_text(json.dumps(state))
    visible = d1_run.analyse_run(tmp_path, ok, steps)
    hidden = d1_run.analyse_run(tmp_path, ok, steps, hidden=True)
    assert any("no mouse event" in f for f in visible["failures"])
    assert hidden["failures"] == [] and any("no mouse event" in n for n in hidden["notes"])
    state["received"]["mouse_move"] = 2
    (tmp_path / d1_run.STATE_NAME).write_text(json.dumps(state))
    assert d1_run.analyse_run(tmp_path, ok, steps)["failures"] == []


# -- the parent end to end, with the child and the displays faked ------------------------------------------------------

def _main(monkeypatch, tmp_path, argv, *, displays=(D0, D1), outcome=None):
    monkeypatch.setattr(d1_run, "enumerate_displays", lambda: list(displays))
    monkeypatch.setattr(d1_run, "win32_monitors", lambda: list(MONITORS))
    launched = []

    def supervise(command, **kwargs):
        launched.append((command, kwargs))
        out = Path(command[command.index("--out") + 1])
        launched.append(("profile_during_run", (out / "profile" / "SRPSS_MC" / "settings_v2.json").is_file()))
        return outcome or {"ended": "exited", "returncode": 1, "violation": None, "pid": 0, "seconds": 0.1}

    monkeypatch.setattr(d1_run, "supervise", supervise)
    with artifact_paths.use_root(tmp_path / ".artifacts"):
        out = artifact_paths.evidence_dir("display", "d1_run", "unit")
        code = d1_run.main(["--display", "1", "--profile", str(_fake_appdata(tmp_path)), "--out", str(out), *argv])
        from tools import evidence_media
        evidence_media._PENDING.clear()          # the CLI's finish() is not part of main(); nothing is published here
    return code, launched


def test_a_refused_display_starts_nothing_and_leaves_nothing(monkeypatch, tmp_path):
    code, launched = _main(monkeypatch, tmp_path, [], displays=(D1,))
    assert code == 2 and launched == []
    assert not (tmp_path / ".artifacts").exists()


def test_a_failed_run_still_deletes_the_profile_copy_and_keeps_its_settings(monkeypatch, tmp_path):
    code, launched = _main(monkeypatch, tmp_path, ["--mode", "devcurve", "--step", "5:grab:a"])
    assert code == 3
    command, kwargs = launched[0]
    assert launched[1] == ("profile_during_run", True)
    assert kwargs["deadline_s"] > 30 and kwargs["guard"] is not None
    out = Path(command[command.index("--out") + 1])
    assert not (out / "profile").exists(), "the profile copy outlived the run"
    mc = json.loads((out / "run_settings_v2_mc.json").read_text())
    assert mc["snapshot"]["widgets"]["spotify_visualizer"]["mode"] == "devcurve"
    summary = json.loads((out / "summary.json").read_text())
    assert summary["failures"] and json.loads((out / "plan.json").read_text())["display"]["index"] == 1
