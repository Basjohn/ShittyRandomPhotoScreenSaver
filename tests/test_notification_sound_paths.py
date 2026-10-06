"""Notification sound path resolution guardrails."""
from __future__ import annotations


def test_default_notification_sound_prefers_programdata(monkeypatch, tmp_path):
    from core.audio.sound_paths import (
        DEFAULT_NOTIFICATION_SOUND_NAME,
        default_notification_sound_path,
    )

    programdata = tmp_path / "ProgramData"
    installed = programdata / "SRPSS" / "sounds" / DEFAULT_NOTIFICATION_SOUND_NAME
    installed.parent.mkdir(parents=True)
    installed.write_bytes(b"ogg")
    monkeypatch.setenv("PROGRAMDATA", str(programdata))

    assert default_notification_sound_path(root=tmp_path) == str(installed)


def test_default_notification_sound_falls_back_to_repo_resource(monkeypatch, tmp_path):
    from core.audio.sound_paths import (
        DEFAULT_NOTIFICATION_SOUND_NAME,
        default_notification_sound_path,
    )

    monkeypatch.setenv("PROGRAMDATA", str(tmp_path / "MissingProgramData"))
    repo_sound = tmp_path / "resources" / DEFAULT_NOTIFICATION_SOUND_NAME
    repo_sound.parent.mkdir()
    repo_sound.write_bytes(b"ogg")

    assert default_notification_sound_path(root=tmp_path) == str(repo_sound)


def test_relative_default_sound_resolves_to_programdata(monkeypatch, tmp_path):
    from core.audio.sound_paths import (
        DEFAULT_NOTIFICATION_SOUND_RELATIVE,
        DEFAULT_NOTIFICATION_SOUND_NAME,
        resolve_notification_sound_path,
    )

    programdata = tmp_path / "ProgramData"
    installed = programdata / "SRPSS" / "sounds" / DEFAULT_NOTIFICATION_SOUND_NAME
    installed.parent.mkdir(parents=True)
    installed.write_bytes(b"ogg")
    monkeypatch.setenv("PROGRAMDATA", str(programdata))

    assert resolve_notification_sound_path(
        DEFAULT_NOTIFICATION_SOUND_RELATIVE, root=tmp_path
    ) == installed
