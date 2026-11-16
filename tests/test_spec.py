"""Candidate `Spec` (candidates.RulesSpec, possession/touch.py): the spec's rules on synthetic
tracking. R8 touch decides when, control decides whether; R10/R9 no flip without control; R11 no
spell right before a stoppage; R16 D from the last sighting of a ball heading out."""
import numpy as np

from possession import candidates as cd, touch
from possession.degrade import Observed
from tests.test_review_fixes import _calm_buildup

H, A, D = 0, 1, 2
FPS = 25
SX, SY = 105.0, 68.0


def _carry(T, x0, vx, y):
    """A player jogging along x at vx m/s (normalised track)."""
    t = np.arange(T)
    out = np.zeros((T, 2), np.float32)
    out[:, 0] = x0 + vx * t / FPS / SX
    out[:, 1] = y
    return out


def _pass_to_away(deflect=False, out_after=None, T=750, kick=400, v=12.0):
    """Home 1 carries, kicks at `kick` to an away player 15 m ahead. Without `deflect` the away
    player carries the ball on (a real turnover); with it the ball bounces straight back to home 2,
    who carries on. `out_after` frames after the reception the ball crosses the sideline."""
    slots = np.full((T, 4, 2), np.nan, np.float32)
    slots[:, 0] = _carry(T, 0.05, 2.5, 0.5)                        # home 1
    slots[:, 1] = _carry(T, 0.10, 2.5, 0.42)                       # home 2 (team-mate behind)
    slots[:, 3] = _carry(T, 0.80, -1.0, 0.6)                       # away 2, far away
    xk = slots[kick, 0, 0]
    xa = xk + 15.0 / SX
    slots[:kick, 2] = [xa, 0.5]                                    # away 1 waits for the ball
    ball = np.full((T, 2), np.nan, np.float32)
    ball[:kick] = slots[:kick, 0] + [0.3 / SX, 0.0]
    n = int(round(15.0 / v * FPS))
    ball[kick:kick + n, 0] = np.linspace(xk, xa, n)
    ball[kick:kick + n, 1] = 0.5
    r = kick + n
    if deflect:
        slots[kick:, 2] = [xa, 0.5]                                # away 1 stands still
        m = int(round(15.0 / 20.0 * FPS))                           # bounces back at 20 m/s
        xh = slots[r + m, 1, 0]                                     # back to home 2
        ball[r:r + m, 0] = np.linspace(xa, xh, m)
        ball[r:r + m, 1] = np.linspace(0.5, 0.42, m)
        ball[r + m:] = slots[r + m:, 1] + [0.3 / SX, 0.0]
    else:
        slots[kick:, 2] = _carry(T - kick, xa, 2.5, 0.5)           # away 1 carries on
        ball[r:] = slots[r:, 2] + [0.3 / SX, 0.0]
        if out_after is not None:
            o = r + out_after
            m = 20
            ball[o:o + m, 1] = np.linspace(0.5, -2.0 / SY, m)
            ball[o:o + m, 0] = ball[o, 0]
            ball[o + m:] = [ball[o, 0], -2.0 / SY]
            for j in range(4):                                     # everyone stops
                slots[o:, j] = slots[o, j]
    return Observed(ball, slots, np.array([H, H, A, A], np.int8)), kick, r


def test_touch_detector_finds_kick_and_reception_with_teams():
    obs, kick, r = _pass_to_away()
    t, team = touch.detect(cd.RulesSpec().features(obs))
    near_kick = np.flatnonzero(np.abs(t - kick) <= 3)
    near_rec = np.flatnonzero(np.abs(t - r) <= 3)
    assert len(near_kick) == 1 and team[near_kick[0]] == H
    assert len(near_rec) == 1 and team[near_rec[0]] == A
    assert len(t) == 2, t


def test_switch_after_the_receivers_touch_not_before():
    obs, kick, r = _pass_to_away()
    spec = cd.RulesSpec(lat_f=1)
    lab = spec(obs)
    sw = np.flatnonzero((lab[1:] == A) & (lab[:-1] == H)) + 1
    assert len(sw) == 1
    assert r <= sw[0] <= r + 1 + 3, (sw, r)
    assert np.all(lab[:kick] == H) and np.all(lab[r + 30:] == A)
    v1 = cd.Rules()(obs)
    sw1 = np.flatnonzero((v1[1:] == A) & (v1[:-1] == H)) + 1
    assert len(sw1) == 1 and sw1[0] <= r, "v1 switches on proximity, at or before the touch"


def test_latency_shifts_the_switch():
    obs, kick, r = _pass_to_away()
    s = [np.flatnonzero(cd.RulesSpec(lat_f=k)(obs) == A)[0] for k in (0, 10)]
    assert s[1] - s[0] == 10


def test_touch_without_control_never_flips():
    obs, kick, r = _pass_to_away(deflect=True)
    lab = cd.RulesSpec()(obs)
    t, team = touch.detect(cd.RulesSpec().features(obs))
    assert np.any(team == A), "the deflection is a detected away touch"
    assert not np.any(lab == A)
    assert np.mean(lab == H) > 0.95


def test_no_spell_right_before_a_stoppage():
    obs, kick, r = _pass_to_away(out_after=30)                     # out 1.2 s after the turnover
    with_rule = cd.RulesSpec(pre_dead_s=2.0)(obs)
    without = cd.RulesSpec(pre_dead_s=0.0)(obs)
    assert np.any(without == A) and np.any(without == D)
    assert not np.any(with_rule == A)
    assert np.any(with_rule == D)


def _vanish_toward_line(heading_out):
    """Home carries, kicks hard toward the sideline (or along it), and the ball is lost 0.2 s after
    the kick for 8 s while every player keeps running (so no slowness rule fires)."""
    T, kick = 1500, 600
    y = 6.0 / SY                                                   # 6 m from the sideline
    slots = np.full((T, 4, 2), np.nan, np.float32)
    slots[:, 0] = _carry(T, 0.05, 3.0, y)
    slots[:, 1] = _carry(T, 0.10, 3.0, 0.45)
    slots[:, 2] = _carry(T, 0.60, -3.0, 0.55)
    slots[:, 3] = _carry(T, 0.65, -3.0, 0.60)
    ball = np.full((T, 2), np.nan, np.float32)
    ball[:kick] = slots[:kick, 0] + [0.3 / SX, 0.0]
    n = 5
    if heading_out:   # 20 m/s toward y = 0, 6 m away: crosses within 0.3 s
        ball[kick:kick + n, 0] = ball[kick - 1, 0]
        ball[kick:kick + n, 1] = ball[kick - 1, 1] - 20.0 / SY * np.arange(1, n + 1) / FPS
    else:             # 20 m/s along the pitch
        ball[kick:kick + n, 0] = ball[kick - 1, 0] + 20.0 / SX * np.arange(1, n + 1) / FPS
        ball[kick:kick + n, 1] = y
    back = kick + n + 200
    ball[back:] = slots[back:, 0] + [0.3 / SX, 0.0]
    return Observed(ball, slots, np.array([H, H, A, A], np.int8)), kick + n


def test_hidden_ball_heading_out_is_a_stoppage_from_the_last_sighting():
    obs, lost = _vanish_toward_line(True)
    on = cd.RulesSpec(vanish_out_s=1.0)(obs)
    off = cd.RulesSpec(vanish_out_s=0.0)(obs)
    assert np.all(on[lost:lost + 100] == D)
    assert not np.any(off[lost:lost + 100] == D)
    obs2, lost2 = _vanish_toward_line(False)
    assert not np.any(cd.RulesSpec(vanish_out_s=1.0)(obs2)[lost2:lost2 + 100] == D)


def test_inside_stoppage_starts_earlier_with_dead_lead():
    obs = _calm_buildup(0.5)
    obs.slots[900:1200, 0] = [0.5, 0.5]
    obs.slots[900:1200, 1] = [0.53, 0.5]
    obs.ball[900:1200] = [0.503, 0.5]
    a0 = np.flatnonzero(cd.RulesSpec(dead_lead_f=0)(obs) == D)[0]
    a1 = np.flatnonzero(cd.RulesSpec(dead_lead_f=25)(obs) == D)[0]
    assert a0 - a1 == 25


def test_spec_candidate_registered():
    import importlib.util
    import os
    from possession.idsse import ROOT
    import sys
    sys.path.insert(0, os.path.join(ROOT, "private"))
    sub = importlib.import_module("submission")
    c = sub.CANDIDATES["spec"].base
    assert isinstance(c, cd.RulesSpec)
    assert (c.pre_dead_s, c.vanish_out_s, c.dead_lead_f, c.lat_f) == (2.0, 1.0, 25, 1)
