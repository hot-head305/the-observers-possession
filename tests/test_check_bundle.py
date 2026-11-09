"""check_bundle on a synthetic fixture (empty-named fake files, no real data)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "private"))
import check_bundle as cb  # noqa: E402


def test_complete_and_incomplete(tmp_path):
    for folder, names in cb.EXPECTED.items():
        os.makedirs(tmp_path / folder)
        for n in names:
            (tmp_path / folder / n).write_text("x")
    ok, lines = cb.check(str(tmp_path))
    assert ok and lines[-1].startswith("PASS")
    os.remove(tmp_path / "tactical" / "BAR-ATH_tactical.mp4")
    ok, lines = cb.check(str(tmp_path))
    assert not ok and "FAIL  tactical/BAR-ATH_tactical.mp4" in lines
