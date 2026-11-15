"""v2 review fixes (candidates.RulesFix): flags off reproduce RulesShape; each flag does what the
review asked for on synthetic tracking."""
import numpy as np

from possession import candidates as cd, shape
from possession.degrade import Observed
from tests.test_shape import _obs

H, A, D = 0, 1, 2
FPS = 25


def test_flags_off_is_shape():
    obs = _obs(hide=slice(200, 400))
    w = shape.shipped()
    a = cd.RulesShape(shape_w=w, shape_thr=0.6, shape_min_s=3.0)(obs)
    b = cd.RulesFix(shape_w=w, shape_thr=0.6, shape_min_s=3.0)(obs)
    assert np.array_equal(a, b)
    assert np.array_equal(cd.RulesFix()(obs), cd.Rules()(obs))


def _pass_by():
    """Home carries the ball, then a 5 m/s pass runs 0.8 m past a static away player to a
    home team-mate who carries on. The home players keep moving so nothing looks dead."""
    T = 1500
    t = np.arange(T)
    slots = np.full((T, 3, 2), np.nan, np.float32)
    ball = np.full((T, 2), np.nan, np.float32)
    slots[:, 0, 0] = 0.3 + 0.1 * np.sin(t / 30)                   # home 1, ~5 m/s, y = 0.5
    slots[:, 0, 1] = 0.5
    slots[:, 1] = [0.5, 0.5 + 0.8 / 68]                            # away, 0.8 m off the pass line
    slots[:, 2, 0] = 0.75 + 0.1 * np.sin(t / 30)                  # home 2
    slots[:, 2, 1] = 0.5
    ball[:600] = slots[:600, 0] + [0.004, 0.0]
    n = int(((0.75 - slots[600, 0, 0]) * 105) / 5 * FPS)         # pass at 5 m/s along y = 0.5
    ball[600:600 + n, 0] = np.linspace(slots[600, 0, 0], 0.75, n)
    ball[600:600 + n, 1] = 0.5
    rest = slice(600 + n, T)
    ball[rest] = slots[rest, 2] + [0.004, 0.0]
    return Observed(ball, slots, np.array([H, A, H], np.int8))


def test_pass_running_past_opponent_is_not_control():
    obs = _pass_by()
    base = cd.RulesFix()(obs)
    fixed = cd.RulesFix(ctrl_rel_v=2.0, ctrl_dv=2.0)(obs)
    assert np.any(base == A), "v1 flips on the passing ball (the review case)"
    assert not np.any(fixed == A)
    assert np.mean(fixed == H) > 0.95


def _calm_buildup(ball_x):
    """A slow ball well inside the field with slow players for 4 s in the middle of live play."""
    T = 2000
    t = np.arange(T)
    slots = np.zeros((T, 2, 2), np.float32)
    w = 2 * np.pi * t / 750
    pos = np.stack([0.5 + 0.2 * np.sin(w), 0.5 + 0.3 * np.cos(w)], 1).astype(np.float32)
    slots[:, 0] = pos
    slots[:, 1] = pos + 0.2
    ball = pos + 0.004
    calm = slice(900, 1000)
    slots[calm, 0] = [ball_x, 0.5]
    slots[calm, 1] = [ball_x + 0.03, 0.5]
    ball[calm] = [ball_x + 0.003, 0.5]
    return Observed(ball, slots, np.array([H, A], np.int8))


def test_no_slowness_only_stoppage_inside_the_field():
    inside = _calm_buildup(0.5)                    # ball 52 m inside
    base = cd.RulesFix()(inside)
    fixed = cd.RulesFix(inside_m=5.0, calm_decel=0.0)(inside)
    assert np.mean(base[910:990] == D) > 0.6, "v1 calls a fake stoppage"
    assert not np.any(fixed[910:990] == D)
    near = _calm_buildup(0.02)                     # ball 2 m from the goal line: rule unchanged
    assert np.mean(cd.RulesFix(inside_m=5.0, calm_decel=0.0)(near)[910:990] == D) > 0.6


def test_long_calm_run_is_still_a_stoppage():
    obs = _calm_buildup(0.5)
    obs.slots[900:1200, 0] = [0.5, 0.5]
    obs.slots[900:1200, 1] = [0.53, 0.5]
    obs.ball[900:1200] = [0.503, 0.5]
    fixed = cd.RulesFix(inside_m=5.0, calm_dead_s=6.0, calm_decel=0.0)(obs)
    assert np.mean(fixed[950:1150] == D) > 0.9


def test_v1_config_hash_unchanged():
    from dataclasses import asdict
    from possession import harness as hs
    assert hs.config_hash({"class": "WithChannel", **asdict(cd.WithChannel(cd.Rules()))}) == "4185e57a0bad"
