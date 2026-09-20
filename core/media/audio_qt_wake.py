"""One retained, pre-created Qt queued-signal bridge for shared Core Audio.

Construct on the GUI thread, before subscribing to COM callbacks. Neither a
QObject nor ThreadManager's invoker is constructed on a COM callback thread.
No QObject/property/scene manipulation happens in the notification callback.
"""
from __future__ import annotations

import threading
from typing import Callable

from PySide6.QtCore import QObject, QCoreApplication, QThread, Qt, Signal

from core.media.audio_event_mailbox import AudioEventMailbox, AudioNotification


class AudioEventQtBridge(QObject):
    wake = Signal()

    def __init__(self, deliver: Callable[[AudioNotification], None], parent=None) -> None:
        app = QCoreApplication.instance()
        if app is None or QThread.currentThread() != app.thread():
            raise RuntimeError("Core Audio Qt bridge must be constructed on the GUI thread")
        super().__init__(parent)
        if self.thread() is not app.thread():
            raise RuntimeError("Core Audio Qt bridge must live in the application thread")
        self._closed = False
        self._mailbox = AudioEventMailbox(post_wake=self._post,
                                          deliver=deliver)
        self.wake.connect(self._drain, Qt.ConnectionType.QueuedConnection)

    @property
    def mailbox(self) -> AudioEventMailbox:
        return self._mailbox

    def _post(self) -> bool:
        if self._closed or QCoreApplication.closingDown():
            return False
        # Signal emission across threads queues to this pre-existing QObject.
        self.wake.emit()
        return True

    def _drain(self) -> None:
        if not self._closed:
            self._mailbox.drain()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._mailbox.retire()
        self.wake.disconnect(self._drain)
