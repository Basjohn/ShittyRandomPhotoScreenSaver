"""Bounded event-driven Jedi Mode easter-egg playback.

The feature is deliberately dormant until an admitted hover/click event reaches
it. Playback owns exactly two ``QMediaPlayer`` slots process-wide; a third
simultaneous request is dropped rather than queued. No timer, polling loop,
worker, or render/input cadence is introduced.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Optional

from PySide6.QtCore import QMetaObject, QObject, QThread, Qt, QUrl, Slot
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import QApplication

from core.audio.sound_paths import default_jedi_mode_sound_path, resolve_jedi_mode_sound_path
from core.logging.logger import get_logger

logger = get_logger(__name__)


@dataclass
class _PlayerSlot:
    player: QMediaPlayer
    audio: QAudioOutput
    busy: bool = False
    started: bool = False


class JediModeSoundPlayer(QObject):
    """Lazy process singleton with a hard two-playback concurrency cap."""

    _instance: Optional["JediModeSoundPlayer"] = None
    _instance_lock = threading.Lock()

    @classmethod
    def instance(cls) -> "JediModeSoundPlayer":
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = cls(parent=QApplication.instance())
            return cls._instance

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._disabled_for_session = False
        self._warned = False
        self._slots: list[_PlayerSlot] = []
        resolved = resolve_jedi_mode_sound_path(default_jedi_mode_sound_path())
        if resolved is None:
            self._disabled_for_session = True
            logger.warning(
                "[JEDI_MODE] Sound resource missing; Jedi Mode disabled for this session"
            )
            return

        for index in range(2):
            audio = QAudioOutput(self)
            # Easter egg volume is intentionally fixed and moderate; no Settings
            # cadence or extra control surface is needed.
            audio.setVolume(0.70)
            player = QMediaPlayer(self)
            player.setAudioOutput(audio)
            player.setSource(QUrl.fromLocalFile(str(resolved)))
            slot = _PlayerSlot(player=player, audio=audio)
            self._slots.append(slot)
            player.playbackStateChanged.connect(
                lambda state, slot_index=index: self._on_playback_state(slot_index, state)
            )
            player.mediaStatusChanged.connect(
                lambda status, slot_index=index: self._on_media_status(slot_index, status)
            )
            try:
                player.errorOccurred.connect(
                    lambda _error, message="", slot_index=index: self._on_error(
                        slot_index, message
                    )
                )
            except Exception:
                pass

    def request_play(self) -> None:
        """Request one play edge; thread-hop only when a caller is off the UI thread."""

        if self._disabled_for_session:
            return
        if QThread.currentThread() is not self.thread():
            QMetaObject.invokeMethod(
                self,
                "_play_on_owner_thread",
                Qt.ConnectionType.QueuedConnection,
            )
            return
        self._play_on_owner_thread()

    @Slot()
    def _play_on_owner_thread(self) -> None:
        if self._disabled_for_session:
            return
        for slot in self._slots:
            if slot.busy:
                continue
            # Reserve synchronously before QMediaPlayer transitions state. This
            # closes the rapid double-event race without a timer or queue.
            slot.busy = True
            slot.started = False
            try:
                slot.player.setPosition(0)
                slot.player.play()
            except Exception as exc:
                slot.busy = False
                logger.debug("[JEDI_MODE] Playback dispatch failed: %s", exc)
            return
        # Hard cardinality cap: never queue a third overlapping play.
        logger.debug("[JEDI_MODE] Dropped event; two playback slots already busy")

    def _on_playback_state(
        self, index: int, state: QMediaPlayer.PlaybackState
    ) -> None:
        if not 0 <= index < len(self._slots):
            return
        slot = self._slots[index]
        if state == QMediaPlayer.PlaybackState.PlayingState:
            slot.started = True
        elif state == QMediaPlayer.PlaybackState.StoppedState and slot.started:
            slot.busy = False
            slot.started = False

    def _on_media_status(self, index: int, status: QMediaPlayer.MediaStatus) -> None:
        if not 0 <= index < len(self._slots):
            return
        if status in (
            QMediaPlayer.MediaStatus.EndOfMedia,
            QMediaPlayer.MediaStatus.InvalidMedia,
            QMediaPlayer.MediaStatus.NoMedia,
        ):
            self._slots[index].busy = False
            self._slots[index].started = False

    def _on_error(self, index: int, message: str = "") -> None:
        if 0 <= index < len(self._slots):
            self._slots[index].busy = False
            self._slots[index].started = False
        if not self._warned:
            logger.warning("[JEDI_MODE] Playback error: %s", message or "(no message)")
            self._warned = True
