"""Evidence comparisons must expose drift and reject incomparable captures."""
import json

from PIL import Image
import pytest

from tools.ordinary_widget_resize_capture import compare


def _capture(path, *, pixel=(10, 20, 30, 255), dpr=1.5):
    path.mkdir()
    Image.new("RGBA", (4, 3), pixel).save(path / "weather__base__1.00.png")
    (path / "ledger.json").write_text(json.dumps({"environment": {"fixture_version": 1},
        "dpr": dpr, "qml_messages": [], "cases": {"weather__base__1.00": {}}}), encoding="utf-8")
    return path


@pytest.mark.parametrize("alpha, changed", [(255, 0), (254, 12)])
def test_comparison_detects_alpha_only_drift(tmp_path, alpha, changed):
    before = _capture(tmp_path / "before")
    after = _capture(tmp_path / "after", pixel=(10, 20, 30, alpha))
    output = tmp_path / "comparison"
    compare(before, after, output)
    row = json.loads((output / "comparison.json").read_text())["weather__base__1.00"]
    assert row["changed_pixels"] == changed
    assert row["difference_bounds"] == ([0, 0, 4, 3] if changed else None)
    with pytest.raises(FileExistsError):
        compare(before, after, output)


def test_comparison_rejects_different_dpr(tmp_path):
    before = _capture(tmp_path / "before")
    after = _capture(tmp_path / "after", dpr=2.)
    with pytest.raises(ValueError, match="dpr mismatch"):
        compare(before, after, tmp_path / "comparison")
    assert not (tmp_path / "comparison").exists()
