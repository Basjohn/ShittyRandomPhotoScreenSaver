"""Available-byte response reads retain decoder/bounds and cancel trickle bodies."""
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.parametrize("kind", ["body", "gzip"])
def test_slow_body_retires_within_existing_barrier_budget_in_owned_child(kind):
    from tools.build_runner import BuildProcessOwner
    root = Path(__file__).resolve().parents[1]
    owner = BuildProcessOwner()
    process = owner.start([sys.executable, "-m", "tests._feed_transport_cancel_probe", kind],
                          cwd=str(root), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        try:
            output, _ = process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            owner.cancel()
            output, _ = process.communicate(timeout=3)
            pytest.fail("Owned transport child did not retire before external deadline: " + output)
        assert process.returncode == 0, output
        assert '"drained": true' in output
    finally:
        owner.retire(process)
        owner.shutdown()
