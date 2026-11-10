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
    return {"hidden": hidden.astype(float), "hidden_run_s": hidden_run_length(hidden) / FPS,
            "dH": dH, "dA": dA, "pspeed_1s": box_mean(pspeed, FPS // 2),
            "pspeed_4s": box_mean(pspeed, 2 * FPS), "bspeed_1s": box_mean(bspeed, FPS // 2),
            "out_m": np.maximum(out_x, out_y)}


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
