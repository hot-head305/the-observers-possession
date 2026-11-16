"""Touch events from ball kinematics (possession-spec.md section 1, R8-R10).

A touch is a sudden change of the ball's velocity vector while the ball is visible: a kick, a
stop, a header, a deflection. The tracking is smooth, so a change above `dv` m/s within +-0.24 s
(features.ball_dv) is motion, not noise. Each touch belongs to the team of the nearest tracked
player at that frame, or to nobody (-1) when no player is within `r` metres or when the nearest
players of both teams are within `margin` metres of each other (a contested ball).

    t, team = detect(f, dv=3.0, r=2.5)     # frames (sorted) and H/A/-1 per touch
"""
import numpy as np

from .features import FPS

H, A = 0, 1


def detect(f, dv=3.0, r=2.5, margin=0.0, sep=6):
    """Local maxima of ball_dv at or above dv, at least `sep` frames apart (the larger wins)."""
    x = np.nan_to_num(f["ball_dv"], nan=0.0)
    cand = np.flatnonzero(x >= dv)
    if not len(cand):
        return np.empty(0, int), np.empty(0, np.int8)
    keep = []
    for t in cand:
        lo, hi = max(0, t - sep), min(len(x), t + sep + 1)
        if x[t] >= x[lo:hi].max() and (not keep or t - keep[-1] > sep or x[t] > x[keep[-1]]):
            if keep and t - keep[-1] <= sep:
                keep[-1] = t
            else:
                keep.append(t)
    t = np.array(keep, int)
    dH = np.nan_to_num(f["dH"][t], nan=np.inf)
    dA = np.nan_to_num(f["dA"][t], nan=np.inf)
    team = np.where(dH <= dA, H, A).astype(np.int8)
    team[np.minimum(dH, dA) > r] = -1
    team[np.abs(dH - dA) < margin] = -1
    return t, team


def first_after(t, start, max_s, lo=0):
    """Index of the first touch at a frame in [start - lo, start + max_s*FPS), or -1."""
    i = np.searchsorted(t, start - lo)
    if i < len(t) and t[i] < start + max_s * FPS:
        return int(i)
    return -1
