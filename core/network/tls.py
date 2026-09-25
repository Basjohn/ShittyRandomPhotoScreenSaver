"""The process's one verified TLS client context for direct-socket connections.

``ssl.create_default_context()`` loads the system trust store. On Windows that
enumerates the CA and ROOT certificate stores and parses every certificate
with the GIL held: about 22 ms for ~145 certificates on the 2026-09-25 probe,
during which another Python thread stalled 36 ms. ``urllib`` builds one per
connection unless it is given a context, so Steam requests and feed artwork
fetches stalled the GUI and Visualizer threads on every connection.

``imaplib.IMAP4_SSL`` without a context uses ``ssl._create_stdlib_context``,
which is *unverified* (no certificate or hostname check), so Gmail needs an
explicit verified context as well.

``requests`` paths keep their own library-owned context and are not routed here.
An ``SSLContext`` is safe to share between threads. Trust-store changes made
while the process runs are picked up by the next process, as with ``requests``.
"""
from __future__ import annotations

import ssl
import threading

_LOCK = threading.Lock()
_CONTEXT: ssl.SSLContext | None = None


def verified_client_context() -> ssl.SSLContext:
    """Return the shared client context: system trust, certificate and hostname checks on."""
    global _CONTEXT
    context = _CONTEXT
    if context is None:
        with _LOCK:
            if _CONTEXT is None:
                _CONTEXT = ssl.create_default_context()
            context = _CONTEXT
    return context


__all__ = ["verified_client_context"]
