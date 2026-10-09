"""R142 first-use frame trace remains observational and explicitly opted in."""
from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
TRACE = ROOT / "core/performance/frame_trace.py"
NODE = ROOT / "rendering/quick/render/background_node.py"
NATIVE = ROOT / "rendering/quick/render/background_image_node.py"
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


def test_first_use_spans_do_not_create_a_new_frame_scheduler():
    for path in (NODE, NATIVE, ITEM):
        src = path.read_text(encoding="utf-8")
        ast.parse(src)
        assert "threading.Timer" not in src
        assert "QTimer.singleShot" not in src
    node = NODE.read_text()
    assert "if not self._program:" in node
    assert "FrameTraceEvent.BACKGROUND_GL_SETUP_BEGIN" in node
    assert "FrameTraceEvent.TRANSITION_FIRST_RENDER_BEGIN" in node
    assert "first_run_render = bool(" in node
    assert "self._trace_first_transition_run_id != int(run.run_id)" in node
    assert "if first_run_render:" in node
    native = NATIVE.read_text()
    assert "self._image_identity != presentation_image.identity" in native
    assert "if native_change and self._frame_trace is not None:" in native
    assert "auxiliary=1 if self._image_adopted else 2" in native
    item = ITEM.read_text()
    assert "FrameTraceEvent.RETAINED_NODE_CREATE_BEGIN" in item
    assert "FrameTraceEvent.RETAINED_NODE_CREATE_READY" in item


def test_trace_is_observational_not_an_additional_presentation_owner():
    assert "self.update()" not in NATIVE.read_text()
    assert "self.scheduleRenderJob(" not in NATIVE.read_text()
    src = NODE.read_text()
    assert "trace = self._frame_trace" in src
    assert "if trace is not None:" in src


def test_traced_retained_node_construction_executes_without_missing_trace_names():
    """Execute the actual updatePaintNode body with Qt/GL boundary doubles.

    The R142 textual tests passed despite referring to an unimported
    FrameTraceEvent; this invokes the traced creation branch and fails under
    that exact regression without needing a GPU on the build host.
    """
    from types import SimpleNamespace

    source = ast.parse(ITEM.read_text(encoding="utf-8"))
    item_cls = next(n for n in source.body if isinstance(n, ast.ClassDef) and n.name == "BackgroundRenderItem")
    method = next(n for n in item_cls.body if isinstance(n, ast.FunctionDef) and n.name == "updatePaintNode")
    # Recreate exactly the symbol binding established by this module's imports.
    trace_imports = [n for n in source.body if isinstance(n, ast.ImportFrom)
                     and n.module == "core.performance.frame_trace"]
    names = {alias.asname or alias.name for imp in trace_imports for alias in imp.names}

    class TraceEvents:
        RETAINED_NODE_CREATE_BEGIN = 72
        RETAINED_NODE_CREATE_READY = 73

    events = []
    class Trace:
        def record(self, event, **kwargs):
            events.append((event, kwargs))

    class RetainedNode:
        def __init__(self, **kwargs):
            events.append(("node_created", kwargs["screen_index"]))
        def synchronize(self, **kwargs):
            events.append(("synchronized", kwargs["device_pixel_ratio"]))

    class FakeItem:
        _presentation_image = object()
        _transition_run = None
        _proof_enabled = False
        _frame_trace = Trace()
        _screen_index = 1
        _telemetry = object()
        _proof_state = object()
        _retirement = SimpleNamespace(set_node=lambda node: events.append(("registered", node)))
        _custom_rendering_required = lambda self: False
        _retire_replaced_node = lambda self, old: None
        window = lambda self: SimpleNamespace(effectiveDevicePixelRatio=lambda: 1.5)
        width = lambda self: 800
        height = lambda self: 600

    ns = {"RetainedBackgroundSceneNode": RetainedNode}
    if "FrameTraceEvent" in names:
        ns["FrameTraceEvent"] = TraceEvents
    module = ast.Module(body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0), method], type_ignores=[])
    ast.fix_missing_locations(module)
    exec(compile(module, str(ITEM), "exec"), ns)
    result = ns["updatePaintNode"](FakeItem(), None, None)
    assert isinstance(result, RetainedNode)
    assert events[0][0] == 72
    assert events[1] == ("node_created", 1)
    assert events[2][0] == 73
    assert events[3] == ("synchronized", 1.5)
    assert events[4] == ("registered", result)


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
