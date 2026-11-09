"""private/{align,fallback,meta}.py on a tiny synthetic bundle (no real data anywhere)."""
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "private"))
import align  # noqa: E402
import fallback  # noqa: E402
import meta  # noqa: E402

N = 300
STEM = "BAR-ATH_tactical"


def make_bundle(root, extra_channel=False, kickoff=(10, 200)):
    t = root / "tactical"
    t.mkdir(parents=True)
    ball_refs = '<BallChannelRef channelId="x"/><BallChannelRef channelId="y"/>' \
                '<BallChannelRef channelId="speed"/>'
    if extra_channel:
        ball_refs += '<BallChannelRef channelId="extra1"/>'
    (t / (STEM + "_atd.xml")).write_text(
        '<Root><Teams><Team id="T1"><Name>Home</Name></Team><Team id="T2"><Name>Away</Name></Team>'
        '</Teams><Players><Player id="P1" teamId="T1"/><Player id="P2" teamId="T2"/></Players>'
        '<DataFormatSpecifications><DataFormatSpecification>{}</DataFormatSpecification>'
        '</DataFormatSpecifications></Root>'.format(ball_refs))
    lines = []
    for i in range(1, N + 1):
        home_near = (i // 150) % 2 == 0
        p1, p2 = ("0.50,0.50,1.0", "0.90,0.90,1.0") if home_near else ("0.10,0.10,1.0", "0.50,0.50,1.0")
        jitter = (i % 13) / 1000.0
        ball = "{:.3f},{:.3f},{:.1f}".format(0.51 + jitter, 0.51 - jitter, 5 + jitter * 100) \
            if i % 7 else "NaN,NaN,NaN"
        if extra_channel:
            ball += ",{}".format(1 if home_near else 2)
        lines.append("{}:{};{}:{}".format(i, p1, p2, ball))
    (t / (STEM + "_atd.txt")).write_text("\n".join(lines) + "\n")
    hdr = "frame,h00,h01,h02,h10,h11,h12,h20,h21,h22,reprojection_error,valid\n"
    (t / (STEM + "_homography.csv")).write_text(
        hdr + "".join("{},1,0,0,0,1,0,0,0,1,0.2,1\n".format(i) for i in range(N)))
    (t / (STEM + "_smart_tagging.xml")).write_text(
        "<file><ALL_INSTANCES>" + "".join(
            "<instance><code>SET PIECES</code><start>{}</start><end>{}</end>"
            "<label><group>Type</group><text>Kick Off (Start)</text></label>"
            "<label><group>Half</group><text>{}</text></label></instance>".format(
                (f - 5) / 25, (f + 5) / 25, h)
            for h, f in zip(("1st Half", "2nd Half"), kickoff)) + "</ALL_INSTANCES></file>")
    return root


def run(mod, root, out, capsys, monkeypatch=None):
    code = mod.main(["--data", str(root), "--out", str(out), "--n-frames", str(N)])
    return code, capsys.readouterr().out


def test_align_pass_and_fail(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(align, "KICKOFFS", {"1st Half": 10, "2nd Half": 200})
    root = make_bundle(tmp_path / "ok")
    code, out = run(align, root, tmp_path / "o1", capsys)
    assert code == 0 and out.count("PASS") == 3 and "FAIL" not in out
    root = make_bundle(tmp_path / "bad", kickoff=(50, 250))
    code, out = run(align, root, tmp_path / "o2", capsys)
    assert code == 1 and "FAIL  Smart Tagging" in out


def test_fallback_valid(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(fallback, "official_sha", lambda: None)
    root = make_bundle(tmp_path / "b")
    code, out = run(fallback, root, tmp_path / "o", capsys)
    assert code == 0 and "PASS  fallback validates" in out
    text = (tmp_path / "o" / "The_Observers.csv").read_text().splitlines()
    assert text[0] == "frame,label" and len(text) == N + 1
    assert set(l.split(",")[1] for l in text[1:]) <= {"H", "A", "D"}


@pytest.mark.parametrize("extra,expect", [(False, "NO  "), (True, "YES ")])
def test_meta_detects_extra_channel(tmp_path, capsys, extra, expect):
    root = make_bundle(tmp_path / "b", extra_channel=extra)
    code, out = run(meta, root, tmp_path / "o", capsys)
    assert code == 0
    for h in ("H1a", "H1b", "H1c"):
        assert "{}  {}".format(expect, h) in out
    detail = json.loads((tmp_path / "o" / "meta.json").read_text())
    assert detail["categorical_fields"] == ([3] if extra else [])


def test_submission_rules_on_synthetic_bundle(tmp_path, capsys, monkeypatch):
    import submission
    from possession import match
    monkeypatch.setattr(match.games, "half_video_blocks", lambda game: [(1, 0, 139), (2, 160, 299)])
    monkeypatch.setattr(match, "KICKOFF_2ND", 170)
    monkeypatch.setattr(match.predict, "__defaults__", (match.games.GAME, 170))
    root = make_bundle(tmp_path / "b")
    for cand in ("rules", "baseline"):
        out = tmp_path / cand
        code = submission.main(["--data", str(root), "--out", str(out), "--n-frames", str(N),
                                "--cand", cand])
        assert code == 0 and "PASS" in capsys.readouterr().out
        rows = (out / "The_Observers.csv").read_text().splitlines()
        assert rows[0] == "frame,label" and len(rows) == N + 1
        lab = [r.split(",")[1] for r in rows[1:]]
        assert set(lab[140:160]) == {"X"} and set(lab[160:170]) == {"D"}
        assert set(lab[:140]) <= {"H", "A", "D"}
