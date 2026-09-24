"""Production-shaped DNS-stall harness shared by the per-family network tests.

Runs in a subprocess (the exit fence is one-way) with ``socket.getaddrinfo``
patched to stall for 30 s, like an unanswered DNS server, and the real
``ThreadManager`` IO lane (four workers):

1. Retirement: four stalled family requests fill the lane; the family's own
   retirement fence fires; an unrelated IO task (Media, Weather...) must run
   within a second. Families whose requests are shared across widgets and so
   have no per-call fence pass ``retire=None``: the lane must then free within
   the DNS deadline instead.
2. Exit: four more stalled requests are in flight when the engine's exit path
   runs (``close_network_admission()`` then ``shutdown(wait=True, timeout=5)``).
   The call must return within a second and the process must not linger for
   the 30 s stalls still sleeping on their daemon threads.

Headless: no Qt windows, no real network, no user profile state.
"""
from __future__ import annotations

import json
import subprocess
import sys
import textwrap
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

_SCRIPT = """
import json, socket, sys, threading, time
sys.path.insert(0, {repo!r})
socket.getaddrinfo = lambda *a, **k: time.sleep(30.0)
from core.threading.manager import ThreadManager
from core.resources.manager import ResourceManager
from core.network.bounded_dns import close_network_admission

{setup}

manager = ThreadManager(resource_manager=ResourceManager())
outcomes = []

def task():
    started = time.monotonic()
    try:
{work}
        outcomes.append(["returned", round(time.monotonic() - started, 2)])
    except BaseException as exc:
        outcomes.append([type(exc).__name__, round(time.monotonic() - started, 2)])

facts = {{}}
for _ in range(4):
    manager.submit_io_task(task, category={category!r})
time.sleep(0.4)
retired_at = time.monotonic()
{retire}
ran = threading.Event()
manager.submit_io_task(ran.set, category="other_family")
facts["lane_free"] = ran.wait(10.0)
facts["lane_free_s"] = round(time.monotonic() - retired_at, 2)
# Every retired request must finish (some families serialise requests behind
# their own lock), not merely free one worker, before the fence is re-armed.
while len(outcomes) < 4 and time.monotonic() - retired_at < 10.0:
    time.sleep(0.01)
facts["retired_all_s"] = round(time.monotonic() - retired_at, 2)
facts["retired_outcomes"] = list(outcomes)

{rearm}
for _ in range(4):
    manager.submit_io_task(task, category={category!r})
time.sleep(0.4)
exit_at = time.monotonic()
close_network_admission()
manager.shutdown(wait=True, timeout=5.0)
facts["shutdown_s"] = round(time.monotonic() - exit_at, 2)
facts["outcomes"] = outcomes
print(json.dumps(facts), flush=True)
sys.exit(0)
"""


def _indent(code: str, spaces: int) -> str:
    return textwrap.indent(textwrap.dedent(code).strip("\n"), " " * spaces)


def run_family_stall(*, setup: str, work: str, retire: str | None, rearm: str = "",
                     category: str) -> dict:
    """Run both phases for one family; returns the facts plus ``lifetime_s``."""
    script = _SCRIPT.format(
        repo=str(REPO),
        setup=textwrap.dedent(setup).strip("\n"),
        work=_indent(work, 8),
        retire=textwrap.dedent(retire or "pass").strip("\n"),
        rearm=textwrap.dedent(rearm or "pass").strip("\n"),
        category=category,
    )
    started = time.monotonic()
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True,
                            timeout=90, cwd=str(REPO))
    lifetime = time.monotonic() - started
    assert result.returncode == 0, result.stderr[-3000:]
    facts = json.loads(result.stdout.strip().splitlines()[-1])
    facts["lifetime_s"] = round(lifetime, 2)
    return facts


def assert_lane_and_exit_bounded(facts: dict, *, retirement_fenced: bool = True,
                                 dns_deadline_s: float = 4.0) -> None:
    assert facts["lane_free"], facts
    limit = 1.0 if retirement_fenced else dns_deadline_s + 1.0
    assert facts["lane_free_s"] < limit, facts
    # All four stalled requests of phase 1 finished within the bound.
    assert len(facts["retired_outcomes"]) == 4, facts
    assert facts["retired_all_s"] < limit + 0.5, facts
    assert facts["shutdown_s"] < 1.0, facts
    # The 30 s lookups are still sleeping on daemon threads: exit must not wait.
    assert facts["lifetime_s"] < 20.0, facts
