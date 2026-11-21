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


def test_a_setting_reaches_every_session_after_its_own_and_none_by_default(tmp_path):
    """N5.2d: a port's hitch session with a look its defaults leave off (``--setting KEY=JSON``, written last)."""
    import pytest

    rows = [_row()]
    preflip_pack.EXTRA_SETTINGS[:] = [preflip_pack.parse_setting('transitions.beam.sparks=true')]
    try:
        command = preflip_pack.session_command(rows, tmp_path, interval_s=12)
        settings = preflip_pack.session_settings(rows, 12)
    finally:
        preflip_pack.EXTRA_SETTINGS[:] = []
    assert command[-1] == "--setting=transitions.beam.sparks=true" and settings[-1] == ("transitions.beam.sparks", True)
    # Controls: none by default; a token without a key or with a value that is not JSON is refused.
    assert not any("transitions.beam.sparks" in part for part in preflip_pack.session_command(rows, tmp_path,
                                                                                               interval_s=12))
    for bad in ("=true", "transitions.beam.sparks", "transitions.beam.sparks=On"):
        with pytest.raises(ValueError):
            preflip_pack.parse_setting(bad)
