"""tools/check_repo.py refuses data-like files and accepts code."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
import check_repo  # noqa: E402


def test_refuses_data_like_files(tmp_path):
    (tmp_path / "v.mp4").write_bytes(b"x")
    (tmp_path / "big.csv").write_text("frame,label\n" + "0,H\n" * 2000)
    (tmp_path / "huge.py").write_bytes(b"#" * (6 * 1024 * 1024))
    (tmp_path / "ok.py").write_text("print(1)\n")
    (tmp_path / "small.csv").write_text("a,b\n1,2\n")
    bad = dict(check_repo.problems(["v.mp4", "big.csv", "huge.py", "ok.py", "small.csv"], str(tmp_path)))
    assert set(bad) == {"v.mp4", "big.csv", "huge.py"}
