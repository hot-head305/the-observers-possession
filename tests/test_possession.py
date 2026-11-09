"""Unit tests for possession.bridge and possession.degrade on synthetic sections."""
import os
import sys
from datetime import datetime

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from possession import bridge as br  # noqa: E402
from possession import degrade as dg  # noqa: E402
from possession.idsse import Section  # noqa: E402

H, A, D = 0, 1, 2


def synthetic_section(T=60000, P=22, seed=0):
    rng = np.random.default_rng(seed)
    lab = np.zeros(T, np.int8)
    t, team = 0, 0
    while t < T:
        L = int(rng.lognormal(np.log(200), 1.0))
        lab[t:t + L] = team
        t += L
        if rng.random() < 0.3:
            Ld = int(rng.lognormal(np.log(500), 0.6))
            lab[t:t + Ld] = D
            t += Ld
        team = 1 - team if rng.random() < 0.8 else team
    players = rng.random((T, P, 2)).astype(np.float32)
    ball = np.concatenate([rng.random((T, 2)), rng.gamma(1.0, 0.8, (T, 1))], 1).astype(np.float32)
    return Section("firstHalf", datetime(2022, 1, 1), lab[:T], ball, players,
                   np.array([H] * (P // 2) + [A] * (P - P // 2), np.int8))


def test_bridge_absorbs_uncontrolled_touch_only():
    lab = np.array([H] * 100 + [A] * 10 + [H] * 100 + [D] * 20 + [A] * 10 + [H] * 50, np.int8)
    out = br.bridge(lab, {}, c=25)
    assert np.all(out[100:110] == H)          # short A touch absorbed
    assert np.all(out[230:240] == A)          # spell after D is a restart: kept
    out2 = br.bridge(lab, {A: np.array([105])}, c=25)
    assert np.all(out2[100:110] == A)         # completed pass by A inside: control, kept


def test_degrade_hits_published_targets():
    sec = synthetic_section()
    for p in dg.GRID[:3]:
        obs = dg.degrade(sec, p, np.random.default_rng(1))
        hidden = np.isnan(obs.ball[:, 0]).mean()
        tracked = (~np.isnan(obs.slots[:, :, 0])).sum(1).mean()
        assert abs(hidden - 0.41) < 0.03, hidden
        assert 19.5 < tracked < 22.0, tracked
        assert obs.slots.shape[1] == len(obs.slot_team)


def test_degrade_is_deterministic():
    sec = synthetic_section(T=5000)
    a = dg.degrade(sec, dg.Params(), np.random.default_rng(7))
    b = dg.degrade(sec, dg.Params(), np.random.default_rng(7))
    assert np.array_equal(np.nan_to_num(a.slots), np.nan_to_num(b.slots))
    assert np.array_equal(np.nan_to_num(a.ball), np.nan_to_num(b.ball))
