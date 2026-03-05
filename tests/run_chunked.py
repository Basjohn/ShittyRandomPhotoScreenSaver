"""
Chunked test runner — runs the full test suite in isolated subprocess chunks.

Each chunk gets its own Python process so GL state, Qt singletons, and memory
are cleanly released between groups.  If any chunk fails the script continues
with remaining chunks and reports a combined exit code.

Usage::

    python tests/run_chunked.py              # auto 4 chunks
    python tests/run_chunked.py --chunks 6   # 6 chunks
    python tests/run_chunked.py --chunks 4 --verbose
    python tests/run_chunked.py --log        # write per-chunk logs

The script also works when invoked by an LLM or CI — it always sections
the suite rather than running everything in one process.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
LOG_DIR = TESTS_DIR.parent / "logs"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run pytest suite in chunks")
    parser.add_argument("--chunks", type=int, default=4,
                        help="Number of chunks to split the suite into (default: 4)")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Pass -v to pytest")
    parser.add_argument("--log", action="store_true",
                        help="Write per-chunk output to logs/pytest_chunk_N.log")
    parser.add_argument("--extra", nargs=argparse.REMAINDER, default=[],
                        help="Extra args forwarded to pytest (after --)")
    args = parser.parse_args()

    total = max(1, args.chunks)
    results: list[tuple[int, float, int]] = []  # (chunk, elapsed, returncode)
    any_fail = False

    LOG_DIR.mkdir(exist_ok=True)

    for chunk in range(1, total + 1):
        cmd = [
            sys.executable, "-m", "pytest", str(TESTS_DIR),
            f"--chunk={chunk}", f"--total-chunks={total}",
            "--tb=short", "-q",
        ]
        if args.verbose:
            cmd.append("-v")
        cmd.extend(args.extra)

        header = f"=== Chunk {chunk}/{total} ==="
        print(f"\n{header}")
        print(f"  Command: {' '.join(cmd)}")

        t0 = time.time()
        log_path = LOG_DIR / f"pytest_chunk_{chunk}.log" if args.log else None

        if log_path:
            with open(log_path, "w", encoding="utf-8") as lf:
                proc = subprocess.run(cmd, stdout=lf, stderr=subprocess.STDOUT,
                                      cwd=str(TESTS_DIR.parent))
        else:
            proc = subprocess.run(cmd, cwd=str(TESTS_DIR.parent))

        elapsed = time.time() - t0
        results.append((chunk, elapsed, proc.returncode))
        if proc.returncode != 0:
            any_fail = True
            print(f"  ✗ Chunk {chunk} FAILED (exit {proc.returncode}) [{elapsed:.1f}s]")
            if log_path:
                print(f"    Log: {log_path}")
        else:
            print(f"  ✓ Chunk {chunk} passed [{elapsed:.1f}s]")

    # Summary
    print("\n" + "=" * 50)
    print("CHUNKED TEST SUMMARY")
    print("=" * 50)
    total_time = sum(e for _, e, _ in results)
    for chunk, elapsed, rc in results:
        status = "PASS" if rc == 0 else f"FAIL (exit {rc})"
        print(f"  Chunk {chunk}: {status}  [{elapsed:.1f}s]")
    print(f"  Total time: {total_time:.1f}s")
    print(f"  Result: {'ALL PASSED' if not any_fail else 'SOME CHUNKS FAILED'}")

    return 1 if any_fail else 0


if __name__ == "__main__":
    sys.exit(main())
