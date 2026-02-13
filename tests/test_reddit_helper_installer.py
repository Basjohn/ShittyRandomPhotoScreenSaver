from pathlib import Path


class TestRedditHelperInstallerFlow:
    def test_trigger_prefers_scheduler_first(self, monkeypatch):
        from core.windows import reddit_helper_installer as installer

        helper_path = Path("dummy_helper.exe")
        queue_path = Path("dummy_queue")

        monkeypatch.setattr(installer, "ensure_helper_installed", lambda: helper_path)
        monkeypatch.setattr(
            installer.reddit_helper_bridge, "get_queue_dir", lambda: queue_path
        )
        monkeypatch.setattr(
            installer, "_maybe_register_helper_task", lambda *_, **__: None
        )
        monkeypatch.setattr(installer, "_prefer_scheduler_launch", lambda: True)
        monkeypatch.setattr(installer, "_token_launch_enabled", lambda: True)

        call_order: list[str] = []

        def fake_scheduler():
            call_order.append("scheduler")
            return True

        def fake_token(_command: str):
            call_order.append("token")
            return True

        monkeypatch.setattr(
            installer, "_trigger_helper_via_scheduler", fake_scheduler
        )
        monkeypatch.setattr(installer, "_launch_as_active_user", fake_token)

        assert installer.trigger_helper_run() is True
        assert call_order == ["scheduler"]
