"""Per-frame observable features from degraded / automatic tracking (Observed). Metres, 25 fps."""
import numpy as np

FPS = 25
PITCH = np.array([105.0, 68.0], dtype=np.float32)
H, A = 0, 1


def box_mean(x, w):
    """Centred mean over +-w frames ignoring NaN; NaN where the window has no value."""
    ok = ~np.isnan(x)
    c = np.concatenate(([0.0], np.cumsum(np.where(ok, x, 0.0))))
    n = np.concatenate(([0], np.cumsum(ok)))
    i = np.arange(len(x))
    lo, hi = np.maximum(0, i - w), np.minimum(len(x), i + w + 1)
    cnt = n[hi] - n[lo]
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(cnt > 0, (c[hi] - c[lo]) / np.maximum(cnt, 1), np.nan)


def hidden_run_length(hidden):
    """For each hidden frame, the length of the hidden run it belongs to (0 when visible)."""
    out = np.zeros(len(hidden), np.int32)
    e = np.diff(np.concatenate(([0], hidden.astype(np.int8), [0])))
    for a, b in zip(np.flatnonzero(e == 1), np.flatnonzero(e == -1)):
        out[a:b] = b - a
    return out


def smooth_xy(x, w):
    """NaN-aware centred mean over +-w frames along axis 0, kept NaN where x is NaN (never
    fills a gap). Damps per-frame jitter; a no-op on tracking that is already smooth."""
    if w <= 0:
        return x
    ok = ~np.isnan(x)
    c = np.concatenate([np.zeros((1,) + x.shape[1:]), np.cumsum(np.where(ok, x, 0.0), 0)])
    n = np.concatenate([np.zeros((1,) + x.shape[1:]), np.cumsum(ok, 0)])
    i = np.arange(len(x))
    lo, hi = np.maximum(0, i - w), np.minimum(len(x), i + w + 1)
    cnt = n[hi] - n[lo]
    out = ((c[hi] - c[lo]) / np.maximum(cnt, 1)).astype(np.float32)
    return np.where(ok, out, np.nan)


def frame_features(obs, smooth=0):
    ball = smooth_xy(obs.ball * PITCH, smooth)
    slots = smooth_xy(obs.slots * PITCH, smooth)
    team = obs.slot_team
    hidden = np.isnan(ball[:, 0])
    d = np.linalg.norm(slots - ball[:, None, :], axis=2)  # NaN where slot empty or ball hidden
    dH = _team_min(d, team == H)
    dA = _team_min(d, team == A)
    v = _speed(slots, cap=12)
    n = (~np.isnan(v)).sum(1)
    pspeed = np.where(n > 0, np.nansum(v, 1) / np.maximum(n, 1), np.nan)
    bspeed = _speed(ball[:, None, :], cap=45)[:, 0]
    out_x = np.maximum(-ball[:, 0], ball[:, 0] - PITCH[0])
    out_y = np.maximum(-ball[:, 1], ball[:, 1] - PITCH[1])
    # Review fixes (v2): ball motion relative to the nearest player of each team, and whether the
    # ball is slowing down (speed over the next half second against the previous half second).
    vb = _velocity(ball[:, None, :])[:, 0]
    vs = _velocity(slots)
    relH = _rel_speed(vb, vs, d, team == H)
    relA = _rel_speed(vb, vs, d, team == A)
    b_prev, b_next = _half_speeds(ball)
    dv = _velocity_change(ball)
    return {"hidden": hidden.astype(float), "hidden_run_s": hidden_run_length(hidden) / FPS,
            "dH": dH, "dA": dA, "pspeed_1s": box_mean(pspeed, FPS // 2),
            "pspeed_4s": box_mean(pspeed, 2 * FPS), "bspeed_1s": box_mean(bspeed, FPS // 2),
            "out_m": np.maximum(out_x, out_y), "relH": relH, "relA": relA,
            "bspeed_prev": b_prev, "bspeed_next": b_next, "ball_dv": dv}


def _speed(xy, cap, k=FPS // 2):
    """Speed from the displacement over +-k frames (per-frame noise would swamp a 1-frame diff).
    Anything above cap m/s is a fragment re-use or a false detection, not motion."""
    v = np.full(xy.shape[:2], np.nan, np.float32)
    v[k:-k] = np.linalg.norm(xy[2 * k:] - xy[:-2 * k], axis=2) * FPS / (2 * k)
    return np.where(v > cap, np.nan, v)


def _team_min(d, mask):
    sub = np.where(mask[None, :], d, np.nan)
    with np.errstate(invalid="ignore"):
        allnan = np.isnan(sub).all(1)
        sub = np.where(np.isnan(sub), np.inf, sub)
        m = sub.min(1)
    m[allnan] = np.nan
    return m


def _velocity(xy, k=FPS // 2):
    """Velocity vector (m/s) from the displacement over +-k frames; NaN at the edges or gaps."""
    v = np.full(xy.shape, np.nan, np.float32)
    v[k:-k] = (xy[2 * k:] - xy[:-2 * k]) * FPS / (2 * k)
    return v


def _rel_speed(vb, vs, d, mask):
    """Speed of the ball relative to the team's nearest slot (NaN where no slot or ball)."""
    sub = np.where(mask[None, :], d, np.nan)
    allnan = np.isnan(sub).all(1)
    j = np.argmin(np.where(np.isnan(sub), np.inf, sub), 1)
    vj = vs[np.arange(len(vs)), j]
    rel = np.linalg.norm(vb - vj, axis=1)
    rel[allnan] = np.nan
    return rel


def _half_speeds(ball, k=FPS // 2):
    """Ball speed over the previous k frames and over the next k frames (m/s)."""
    prev = np.full(len(ball), np.nan, np.float32)
    nxt = np.full(len(ball), np.nan, np.float32)
    step = np.linalg.norm(ball[k:] - ball[:-k], axis=1) * FPS / k
    prev[k:] = step
    nxt[:-k] = step
    return prev, nxt


def _velocity_change(ball, k=6):
    """|v_after - v_before| (m/s) of the ball over +-k frames: a kick, stop or deflection at t.
    k is short (0.24 s) so the change is placed at the touch, not spread over a passing ball."""
    out = np.full(len(ball), np.nan, np.float32)
    vb = (ball[k:-k] - ball[:-2 * k]) * FPS / k
    va = (ball[2 * k:] - ball[k:-k]) * FPS / k
    out[k:-k] = np.linalg.norm(va - vb, axis=1)
    return out
