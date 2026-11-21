"""preflip_pack's --app-arg reaches the live check's command line (a native Vulkan row), and is absent by default."""
from tools import preflip_pack


def _row():
    rows, _ = preflip_pack.plan_rows(preflip_pack.build_parser().parse_args(["--rows", "transition/beam/*"]), old=None)
    return rows[0]


def test_app_arg_reaches_the_row_command(tmp_path):
    preflip_pack.APP_ARGS[:] = ["--graphics-backend=vulkan"]
    try:
        command = preflip_pack.row_command(_row(), tmp_path)
    finally:
        preflip_pack.APP_ARGS[:] = []
    assert "--app-arg=--graphics-backend=vulkan" in command


def test_no_app_arg_by_default(tmp_path):
    command = preflip_pack.row_command(_row(), tmp_path)
    assert not any(part.startswith("--app-arg") for part in command)
