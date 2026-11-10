"""Freeze / locked-test refusals on a temporary registry (no IDSSE needed)."""
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "experiments"))
sys.path.insert(0, os.path.join(ROOT, "private"))
import locked_test as lt  # noqa: E402
from possession import harness as hs  # noqa: E402


def fake_eval(cand, matches, name=None, **kw):
    v = 0.4 if "rules" in name else 0.25
    s = np.full((len(matches), 2, 3), v) + np.arange(len(matches))[:, None, None] * 0.01
    return hs.Result(name, tuple(matches), s, s, s)


def test_freeze_then_one_locked_test(tmp_path, monkeypatch):
    monkeypatch.setattr(hs, "_git_sha", lambda: "abc")
    reg = str(tmp_path / "r.jsonl")
    assert lt.locked_test(reg, fake_eval) == "not frozen; run make freeze first"
    assert lt.freeze(reg) is None and lt.freeze(reg) == "already frozen"
    assert lt.locked_test(reg, fake_eval) is None
    rows = [json.loads(l) for l in open(reg)]
    assert [r["split"] for r in rows] == ["freeze", "test_started", "test", "test"]
    assert rows[-1]["gain"] > 0 and rows[-1]["matches"] == list(hs.SPLIT["test"])
    assert lt.locked_test(reg, fake_eval) == "the locked test has already run"


def test_locked_test_refuses_dirty_tree_and_changed_config(tmp_path, monkeypatch):
    reg = str(tmp_path / "r.jsonl")
    monkeypatch.setattr(hs, "_git_sha", lambda: "abc-dirty")
    assert lt.freeze(reg) == "tree not clean; commit first"
    monkeypatch.setattr(hs, "_git_sha", lambda: "abc")
    lt.freeze(reg)
    monkeypatch.setattr(lt, "frozen", lambda: lt.cd.WithChannel(lt.cd.Rules(switch_k=11)))
    assert lt.locked_test(reg, fake_eval) == "the candidate changed since the freeze"
    assert all(json.loads(l)["split"] == "freeze" for l in open(reg))


def test_frozen_is_the_submitted_candidate():
    import submission
    assert lt.frozen() == submission.CANDIDATES["rules"]
