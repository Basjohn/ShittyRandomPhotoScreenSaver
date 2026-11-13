"""UI geometry contracts for the stdlib/Tk Build Foundry."""

import tkinter as tk

import pytest

from tools import build_runner


def test_github_rows_scroll_without_hiding_footer_actions(monkeypatch):
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tk display unavailable")
    root.withdraw()
    monkeypatch.setattr(
        build_runner, "helper_build_status",
        lambda *_a, **_k: build_runner.HelperBuildStatus(False, "Stable", "fixture", 0),
    )
    monkeypatch.setattr(
        build_runner, "run_preflight", lambda *_a, **_k: build_runner.PreflightResult(),
    )
    try:
        app = build_runner.BuildRunnerApp(root, initial_mode="github")
        # Simulate a short desktop work area, not the full monitor including the taskbar.
        monkeypatch.setattr(app, "_work_area", lambda: (0, 0, 1280, 720))
        root.update()
        margin = app._dip(build_runner.WINDOW_WORKAREA_MARGIN_DIP)
        assert root.winfo_height() <= 720 - 2 * margin
        assert app._body_content.winfo_reqheight() > app._body_canvas.winfo_height()
        assert len(app._job_widgets) == 9
        assert app._footer.winfo_ismapped()
        assert app._footer.winfo_rooty() + app._footer.winfo_height() <= 720
        assert app._body_canvas.winfo_rooty() + app._body_canvas.winfo_height() <= app._footer.winfo_rooty()
        for name in (
            "_select_all_button", "_select_none_button", "_emergency_stop_button",
            "_start_button", "_auto_close_checkbox",
        ):
            button = getattr(app, name)
            assert button.winfo_ismapped(), name
            assert button.winfo_rootx() >= root.winfo_rootx(), name
            assert button.winfo_rootx() + button.winfo_width() <= root.winfo_rootx() + root.winfo_width(), name

        # A long live status must never consume the action buttons' row.
        app._footer_status.configure(text="Building on GitHub; " * 16)
        root.update_idletasks()
        assert app._start_button.winfo_ismapped()
        assert app._start_button.winfo_width() > 80
        # User resizing does not require reconstructing job/status widgets.
        root.geometry(f"{root.winfo_width()}x{root.winfo_height() - 40}")
        root.update_idletasks()
        assert app._footer.winfo_ismapped()
        assert len(app._job_widgets) == 9
    finally:
        root.destroy()
