"""R142 first-use frame trace remains observational and explicitly opted in."""
from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
TRACE = ROOT / "core/performance/frame_trace.py"
ITEM = ROOT / "rendering/quick/render/background_item.py"


def test_first_use_event_ids_extend_the_binary_v1_enum_without_reusing_ids():
    tree = ast.parse(TRACE.read_text(encoding="utf-8"))
    enum = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "FrameTraceEvent")
    entries = {n.targets[0].id: n.value.value for n in enum.body
               if isinstance(n, ast.Assign) and isinstance(n.value, ast.Constant)
               and isinstance(n.targets[0], ast.Name) and isinstance(n.value.value, int)}
    assert len(entries.values()) == len(set(entries.values()))
    assert entries["PREFETCH_HANDOFF_END"] == 65
    assert [entries[n] for n in (
        "BACKGROUND_GL_SETUP_BEGIN", "BACKGROUND_GL_SETUP_READY",
        "NATIVE_TEXTURE_CHANGE_BEGIN", "NATIVE_TEXTURE_CHANGE_READY",
        "TRANSITION_FIRST_RENDER_BEGIN", "TRANSITION_FIRST_RENDER_READY",
        "RETAINED_NODE_CREATE_BEGIN", "RETAINED_NODE_CREATE_READY",
    )] == list(range(66, 74))
    assert '_RECORD = struct.Struct("<QHhqqq")' in TRACE.read_text()
    assert '_VERSION: Final[int] = 1' in TRACE.read_text()


def test_offline_report_exposes_first_use_attribution_and_missing_background(tmp_path):
    """Keep the R142 silent-empty-background failure visible in future logs."""
    import struct
    import subprocess
    import sys

    header = struct.Struct("<8sHHI")
    record = struct.Struct("<QHhqqq")
    sample = tmp_path / "trace.bin"
    samples = [
        (1_000_000, 48, 0, 1, 0, 0),
        (2_000_000, 72, 0, -1, 0, 0),
        (4_000_000, 73, 0, -1, 0, 0),
        (5_000_000, 68, 0, 1, 0, 0),
        (8_000_000, 69, 0, 1, 0, 2),
    ]
    sample.write_bytes(header.pack(b"SRPSSFT1", 1, record.size, 512)
                       + b"".join(record.pack(*row) for row in samples))
    result = subprocess.run(
        [sys.executable, str(ROOT / "tools/frame_trace_report.py"), str(sample)],
        capture_output=True, text=True, check=True, timeout=20,
    )
    assert "first_use=retained_node_create n=1" in result.stdout
    assert "first_use=native_texture_change n=1" in result.stdout
    assert "native_texture adopted=0 uploaded=1" in result.stdout
    assert "zero background render events" in result.stdout
