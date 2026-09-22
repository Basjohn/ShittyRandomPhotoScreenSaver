"""Durable source-level tripwires for saver-owned external-link routing.

R-02 is easy to regress because a direct browser call can look harmless in a
normal desktop run while freezing Firefox or trapping it on Winlogon's desktop
in a real SCR session.  These checks keep saver-owned product actions behind the
single secure URL handoff and make Gmail's older direct runtime seam explicit.
"""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_saver_external_link_families_share_one_secure_handoff_boundary() -> None:
    display = _text("engine/display_manager.py")
    binder = _text("rendering/quick/widgets/family_binder.py")
    gmail = _text("rendering/quick/widgets/gmail.py")

    # Reddit, general FEEDS and every Steam semantic action terminate in the
    # DisplayManager-owned secure launcher path. Gmail's client owns URL
    # construction, but successful handoff is reported back to the same saver
    # exit consequence and its inbox route is injected here too.
    for method in (
        "_open_quick_reddit_url",
        "_open_quick_feed_url",
        "_open_quick_steam_target",
    ):
        assert f"def {method}" in display
    assert "gmail_open_inbox_requested=_open_gmail_inbox" in display
    assert "gmail_browser_opened=_gmail_browser_opened" in display
    assert "GmailFamilyAdapter(" in binder
    assert "on_browser_opened=gmail_browser_opened" in binder
    assert 'self._connect("openMessageRequested", self._handle_open_message_requested)' in gmail
    assert "if opened and self._on_browser_opened is not None:" in gmail


def test_gmail_auth_from_saver_routes_to_settings_not_oauth_browser() -> None:
    binder = _text("rendering/quick/widgets/family_binder.py")
    gmail = _text("rendering/quick/widgets/gmail.py")
    targets = _text("ui/settings_launch_targets.py")

    assert 'settings_target_requested("gmail_authorization")' in binder
    assert "if self._on_auth_requested is not None:" in gmail
    assert "return bool(self._on_auth_requested())" in gmail
    assert 'target_id="gmail_authorization"' in targets
    assert 'focus_attr="gmail_authorize_btn"' in targets


def test_saver_runtime_modules_cannot_grow_direct_browser_launches() -> None:
    """Negative guard: retained/runtime code may not launch browsers itself.

    Direct browser APIs remain legitimate in explicitly interactive Settings,
    MC/diagnostic seams and the user-session helper.  They are forbidden in the
    saver-owned retained presentation and service directories where a future
    widget could otherwise silently recreate R-02.
    """

    roots = (
        ROOT / "rendering" / "quick" / "widgets",
        ROOT / "widgets",
    )
    forbidden = (
        "QDesktopServices.openUrl",
        "webbrowser.open",
        "os.startfile(",
    )
    offenders: list[str] = []
    for root in roots:
        for path in root.rglob("*.py"):
            source = path.read_text(encoding="utf-8")
            if any(token in source for token in forbidden):
                offenders.append(path.relative_to(ROOT).as_posix())
    assert offenders == []


def test_gmail_runtime_propagates_secure_handoff_failure() -> None:
    source = _text("widgets/gmail_runtime.py")
    block = source.split("def open_message_in_browser(self, message_id: str) -> bool:", 1)[1]
    block = block.split("# ------------------------------------------------------------------", 1)[0]
    assert "return bool(opener(message_id))" in block
    assert "opener(message_id)\n            return True" not in block


def test_secure_launcher_fails_closed_for_ordinary_saver_and_task_owns_helper() -> None:
    launcher = _text("core/windows/secure_url_launcher.py")
    runtime = _text("core/windows/reddit_helper_runtime.py")
    helper = _text("helpers/reddit_helper_worker.py")

    assert 'in {"winlogon", "services"}' in launcher
    assert 'source=f"scr_url_handoff_{source}"' in launcher
    assert "handoff remains durable" in launcher
    queued_block = launcher.split("if ok:", 1)[1].split("else:", 1)[0]
    assert "return True" in queued_block
    assert "return False" not in queued_block
    assert 'normalized.startswith(("run_session", "scr_url_handoff_"))' in runtime
    assert "_run_helper_scheduled_task(source=source)" in runtime
    # R-02 final invariant: the helper waits for the saver/session boundary and
    # only then uses the interactive user's shell to open the URL.
    assert "_session_ticket_active(session_ticket_path" in helper
    assert "os.startfile(url)" in helper


def test_feed_runtime_config_has_no_shadow_product_defaults() -> None:
    tree = ast.parse(_text("widgets/feed_runtime.py"))
    runtime = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "FeedRuntimeConfig"
    )
    fields = {
        node.target.id: node
        for node in runtime.body
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
    }
    assert fields["show_images"].value is None
    assert fields["view_mode"].value is None
