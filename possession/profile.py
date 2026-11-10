"""Tracking-quality statistics, computed the same way on the provided ATD (privately) and on
degraded IDSSE, so the degradation can be checked against reality without anyone reading it.

All inputs normalised 0-1 like Observed; `mask` selects the frames to profile (graded frames).
"""
import numpy as np

FPS = 25
PITCH = np.array([105.3, 68.0])


def _runs(m):
    e = np.diff(np.concatenate(([0], m.astype(np.int8), [0])))
    return np.flatnonzero(e == -1) - np.flatnonzero(e == 1)


def jitter(xy):
    """Per-frame position noise (m) from second differences: for iid noise sigma, the second
    difference has sd sqrt(6) sigma; real acceleration at 25 fps is ~0.01 m, negligible.
    Robust (MAD) so fragment jumps don't dominate."""
    d2 = xy[2:] - 2 * xy[1:-1] + xy[:-2]
    d2 = d2[~np.isnan(d2)]
    if not len(d2):
        return float("nan")
    return float(1.4826 * np.median(np.abs(d2 - np.median(d2))) / np.sqrt(6))


def stats(ball, slots, mask):
    ball, slots = ball[mask] * PITCH[:2], slots[mask] * PITCH[:2]
    minutes = len(ball) / FPS / 60
    hidden = np.isnan(ball[:, 0])
    hr = _runs(hidden) / FPS
    present = ~np.isnan(slots[:, :, 0])
    frags = np.concatenate([_runs(present[:, j]) for j in range(present.shape[1])]) / FPS
    pj = np.nanmedian([jitter(slots[:, j]) for j in range(slots.shape[1]) if present[:, j].sum() > 50])
    return {"hidden_share": float(hidden.mean()),
            "hidden_run_median_s": float(np.median(hr)) if len(hr) else 0.0,
            "hidden_run_p90_s": float(np.percentile(hr, 90)) if len(hr) else 0.0,
            "objects_per_frame": float(present.sum(1).mean()),
            "fragments_per_min": float(len(frags) / minutes),
            "fragment_median_s": float(np.median(frags)) if len(frags) else 0.0,
            "player_jitter_m": float(pj),
            "ball_jitter_m": jitter(ball)}


# Relative tolerance per statistic for "our degradation looks like the real tracking".
TOL = {"hidden_share": 0.10, "hidden_run_median_s": 0.5, "hidden_run_p90_s": 0.5,
       "objects_per_frame": 0.10, "fragments_per_min": 0.5, "fragment_median_s": 0.5,
       "player_jitter_m": 0.5, "ball_jitter_m": 0.5}


def agree(real, ref, key):
    if np.isnan(real) or np.isnan(ref):
        return False
    return abs(real - ref) <= TOL[key] * max(abs(ref), 1e-9)
