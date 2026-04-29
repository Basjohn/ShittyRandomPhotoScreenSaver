"""Notification sound player for overlay widgets.

Lightweight wrapper around ``QMediaPlayer`` + ``QAudioOutput``. Provides a
process-singleton ``NotificationSoundPlayer`` that outlives individual widget
instances so playback is not cut off when a widget is destroyed (e.g. on
screensaver exit).

Design:
- Singleton parented to ``QApplication.instance()``.
- Volume is a 0-100 integer (matches UI sliders); converted to 0.0-1.0 for Qt.
- ``play()`` is a no-op if disabled / file missing.
- A *single* failure to load the file disables sound for the session and logs
  a single WARNING (no spam on repeated calls).
"""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, QUrl, Qt
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import QApplication

from core.logging.logger import get_logger
from core.audio.sound_paths import resolve_notification_sound_path

logger = get_logger(__name__)


class NotificationSoundPlayer(QObject):
    """Singleton OGG/WAV/MP3 player for overlay-widget notifications."""

    _instance: Optional["NotificationSoundPlayer"] = None
    _instance_lock = threading.Lock()

    @classmethod
    def instance(cls) -> "NotificationSoundPlayer":
        """Return the process-wide singleton, creating it on first call."""
        with cls._instance_lock:
            if cls._instance is None:
                parent = QApplication.instance()
                cls._instance = cls(parent=parent)
            return cls._instance

    def __init__(
        self,
        file_path: Optional[str] = None,
        volume_percent: int = 50,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._file_path: Optional[str] = None
        self._volume_percent: int = self._clamp_volume(volume_percent)
        self._disabled_for_session: bool = False
        self._load_warned: bool = False

        # QMediaPlayer + QAudioOutput must be created on the UI thread.
        self._audio_output = QAudioOutput(self)
        self._audio_output.setVolume(self._volume_percent / 100.0)

        self._player = QMediaPlayer(self)
        self._player.setAudioOutput(self._audio_output)
        try:
            # Surface playback errors via the errorOccurred signal where
            # available (Qt 6.5+); fall back silently on older builds.
            self._player.errorOccurred.connect(self._on_error)  # type: ignore[attr-defined]
        except Exception:
            pass

        if file_path:
            self.set_file_path(file_path)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_file_path(self, path: Optional[str]) -> None:
        """Set the source file. Resets the *disabled-for-session* flag so a
        previously-bad path can be replaced without restarting the app."""
        if not path:
            self._file_path = None
            self._player.setSource(QUrl())
            return

        resolved = self._resolve_path(path)
        if resolved is None:
            if not self._load_warned:
                logger.warning("[NOTIFY_SOUND] Sound file not found: %s", path)
                self._load_warned = True
            self._file_path = None
            self._disabled_for_session = True
            return

        # New path → re-enable for this session and clear the warn flag.
        self._file_path = str(resolved)
        self._disabled_for_session = False
        self._load_warned = False
        try:
            self._player.setSource(QUrl.fromLocalFile(self._file_path))
        except Exception as exc:
            logger.warning("[NOTIFY_SOUND] Failed to set source %s: %s", self._file_path, exc)
            self._disabled_for_session = True

    def set_volume(self, percent: int) -> None:
        """Set the playback volume (0-100). Applies immediately."""
        self._volume_percent = self._clamp_volume(percent)
        try:
            self._audio_output.setVolume(self._volume_percent / 100.0)
        except Exception as exc:
            logger.debug("[NOTIFY_SOUND] setVolume failed: %s", exc)

    def play(self) -> None:
        """Play the configured sound. Safe to call from any thread; the actual
        playback is dispatched onto the player's owning (UI) thread."""
        if self._disabled_for_session or not self._file_path:
            return

        # ``QMediaPlayer.play()`` is documented as thread-safe on Qt 6, but
        # ``stop()``/``setPosition()`` are not. We always invoke through the
        # player's thread to be safe across versions.
        try:
            from PySide6.QtCore import QMetaObject
            QMetaObject.invokeMethod(self._player, "stop", Qt.ConnectionType.QueuedConnection)
            QMetaObject.invokeMethod(self._player, "play", Qt.ConnectionType.QueuedConnection)
        except Exception as exc:
            logger.debug("[NOTIFY_SOUND] play dispatch failed: %s", exc)

    @property
    def file_path(self) -> Optional[str]:
        return self._file_path

    @property
    def volume_percent(self) -> int:
        return self._volume_percent

    @property
    def is_disabled(self) -> bool:
        return self._disabled_for_session

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _clamp_volume(percent: int) -> int:
        try:
            return max(0, min(100, int(percent)))
        except (TypeError, ValueError):
            return 50

    @staticmethod
    def _resolve_path(path: str) -> Optional[Path]:
        """Resolve to an absolute path that exists, or None."""
        try:
            return resolve_notification_sound_path(path)
        except Exception:
            return None

    def _on_error(self, _err, message: str = "") -> None:
        if not self._load_warned:
            logger.warning("[NOTIFY_SOUND] Playback error: %s", message or "(no message)")
            self._load_warned = True
        self._disabled_for_session = True
