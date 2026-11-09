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


def test_holm_and_compare():
    from possession import harness as hs
    adj = hs.holm([0.01, 0.04, 0.03])
    assert np.allclose(adj, [0.03, 0.06, 0.06])
    M = (4, 2, 3)
    a = hs.Result("a", ("m1", "m2", "m3", "m4"), np.full(M, 0.2), np.zeros(M), np.zeros(M))
    b = hs.Result("b", a.matches, np.full(M, 0.25), np.zeros(M), np.zeros(M))
    c = hs.compare(b, a)
    assert abs(c["gain"] - 0.05) < 1e-9 and c["p_gain_pos"] == 1.0 and c["no_sign_flip"]
    assert hs.promote([b], a)[0]["promote"]


def test_rules_hold_possession_through_loose_ball_and_detect_stoppage():
    from possession import candidates as cd
    T = 1500
    slots = np.full((T, 2, 2), np.nan, np.float32)
    ball = np.full((T, 2), np.nan, np.float32)
    w = 2 * np.pi * np.arange(T) / 750             # circular run at match pace, never still
    pos = np.stack([0.5 + 0.2 * np.sin(w), 0.5 + 0.3 * np.cos(w)], 1).astype(np.float32)
    slots[:, 0] = pos
    slots[:, 1] = pos + 0.2                        # away player 20 m away
    slots[600:900, 1] = pos[600:900]               # away player wins the ball 600-900
    slots[600:900, 0] = pos[600:900] + 0.2
    ball[:] = pos + 0.005
    ball[300:320] = pos[300:320] + 0.05            # loose ball, nobody close: still home
    ball[1100:1400] = 0.5                          # static ball...
    slots[1100:1400] = 0.5 + np.array([[0.0, 0.02], [0.03, 0.0]], np.float32)  # ...players still
    obs = __import__("possession.degrade", fromlist=["Observed"]).Observed(ball, slots, np.array([H, A], np.int8))
    lab = cd.Rules()(obs)
    assert np.all(lab[:600] == H)
    assert np.mean(lab[620:900] == A) > 0.95
    assert np.mean(lab[1150:1350] == D) > 0.95
    assert np.array_equal(lab, cd.Rules()(obs))   # deterministic
