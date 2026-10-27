"""Disposable child: parent MUST supervise this process with a hard deadline."""
import json
import sys
import threading
import time
import zlib
from http.server import BaseHTTPRequestHandler, HTTPServer

from core.feeds.transport import FeedHttpTransport


kind = sys.argv[1]
cancelled = threading.Event()
ready = threading.Event()
outcome = []


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        try:
            if kind == "headers":
                ready.set()
                for byte in b"HTTP/1.0 200 OK\r\nX-Trickle: " + b"x" * 2000 + b"\r\n\r\n":
                    self.wfile.write(bytes([byte]))
                    self.wfile.flush()
                    time.sleep(0.04)
                return
            self.send_response(200)
            if kind == "gzip":
                self.send_header("Content-Encoding", "gzip")
            self.end_headers()
            ready.set()
            compressor = zlib.compressobj(wbits=31)
            for _ in range(2000):
                data = compressor.compress(b"x") + compressor.flush(zlib.Z_SYNC_FLUSH) if kind == "gzip" else b"x"
                self.wfile.write(data)
                self.wfile.flush()
                time.sleep(0.04)
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass


server = HTTPServer(("127.0.0.1", 0), Handler)
server_thread = threading.Thread(target=lambda: server.serve_forever(poll_interval=0.05))
server_thread.start()
transport = FeedHttpTransport(connect_timeout=1, read_timeout=3, should_continue=lambda: not cancelled.is_set())
def fetch():
    try:
        transport.fetch(f"http://127.0.0.1:{server.server_port}/feed")
        outcome.append("unexpected_success")
    except Exception as exc:
        outcome.append(type(exc).__name__)

worker = threading.Thread(target=fetch)
worker.start()
assert ready.wait(2), "server never reached the requested response phase"
time.sleep(0.15)
started = time.monotonic()
cancelled.set()
worker.join(1.5)
drained = not worker.is_alive()
print(json.dumps({"phase": kind, "drained": drained, "cancel_seconds": time.monotonic() - started, "outcome": outcome}), flush=True)
if drained:
    transport.close()
    server.shutdown()
    server.server_close()
    server_thread.join(1)
    assert not server_thread.is_alive()
    assert outcome == ["FeedTransportError"]
else:
    # The owned parent's Job deadline terminates this disposable failed probe.
    # Never close a live requests stream concurrently or pretend it drained.
    worker.join()
