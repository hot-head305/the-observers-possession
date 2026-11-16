"""Calibration measurements for candidate `Spec` on the dev match J03WPY (degraded, fitted
profile). Nothing here reads CV, test or match data.

  touches   recall of DFL pass events (kick frame) by a detected touch of the passing team
            within +-0.5 s, and the timing offset (touch - event) in frames
  latency   per bridge: GT live switch frame minus the latest touch of the gaining team in the
            2 s before it (R8 touch-to-switch latency); share of switches with no such touch
  d_onset   fix_stop dead-mask onset minus GT D onset (frames), split by ball near a line or not
  d_end     GT live start minus the first detected touch after the dead-mask end (R6 convention
            on IDSSE: ~0 = live at the kick, > 0 = live after the kick)

    uv run python experiments/spec_calib.py [dv ...]
"""
import json
import os
import sys
import warnings

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from possession import bridge as br, candidates as cd, degrade as dg, harness as hs, touch  # noqa: E402
from possession import idsse  # noqa: E402
from profile_cv import CELLS  # noqa: E402

FPS = 25
H, A, D = 0, 1, 2
BASE = cd.RulesFix(inside_m=5.0, calm_dead_s=6.0, calm_decel=0.0)  # fix_stop without shape


def _runs(mask):
    e = np.diff(np.concatenate(([0], mask.astype(np.int8), [0])))
    return list(zip(np.flatnonzero(e == 1), np.flatnonzero(e == -1)))


def q(x):
    x = np.asarray(x, float)
    if not len(x):
        return {"n": 0}
    return {"n": int(len(x)), "median": float(np.median(x)), "q25": float(np.percentile(x, 25)),
            "q75": float(np.percentile(x, 75)), "mean": float(np.mean(x))}


def pass_frames(mid, secs):
    out = [[] for _ in secs]
    for si, f, team in idsse.passes(mid, secs):
        out[si].append((f, team))
    return out


def main(dvs=(2.0, 3.0, 4.0), mid="J03WPY", seeds=(0, 1)):
    secs, gts = hs.truths(mid)
    pf = pass_frames(mid, secs)
    out = {}
    for dv in dvs:
        rec, off = [], []
        lat = {c: [] for c in br.C_GRID}
        lat_after = {c: [] for c in br.C_GRID}
        miss = {c: 0 for c in br.C_GRID}
        onset_line, onset_in, dend, dend_touch = [], [], [], []
        for ci, cell in enumerate(CELLS):
            for seed in seeds:
                for si, s in enumerate(secs):
                    obs = dg.degrade(s, cell, hs._rng(mid, ci, seed, si))
                    f = BASE.features(obs)
                    t, team = touch.detect(f, dv=dv)
                    # (1) pass recall
                    for pfr, pteam in pf[si]:
                        if np.isnan(obs.ball[pfr, 0]):
                            continue  # ball hidden at the kick: not detectable
                        near = np.flatnonzero((np.abs(t - pfr) <= FPS // 2) & (team == pteam))
                        rec.append(len(near) > 0)
                        if len(near):
                            off.append(int(t[near[np.argmin(np.abs(t[near] - pfr))]] - pfr))
                    # (2) latency per bridge
                    for bi, c in enumerate(br.C_GRID):
                        g = gts[si][bi]
                        sw = np.flatnonzero((g[1:] != g[:-1]) & (g[1:] < 2) & (g[:-1] < 2)) + 1
                        for s0 in sw:
                            k = g[s0]
                            before = np.flatnonzero((t <= s0) & (t > s0 - 2 * FPS) & (team == k))
                            if len(before):
                                lat[c].append(int(s0 - t[before[-1]]))
                            else:
                                after = np.flatnonzero((t > s0) & (t <= s0 + FPS) & (team == k))
                                if len(after):
                                    lat_after[c].append(int(t[after[0]] - s0))
                                else:
                                    miss[c] += 1
                    # (3) D onset / (4) D end against the raw GT (bridges do not move D)
                    dead = BASE.dead_mask(f)
                    pr = _runs(dead)
                    pstarts = np.array([a for a, b in pr]) if pr else np.empty(0, int)
                    pends = np.array([b for a, b in pr]) if pr else np.empty(0, int)
                    outm = np.nan_to_num(f["out_m"], nan=-99)
                    for a, b in _runs(s.label == D):
                        if len(pstarts):
                            j = np.argmin(np.abs(pstarts - a))
                            if abs(pstarts[j] - a) <= 3 * FPS:
                                near_line = outm[max(0, a - FPS):a + 1].max() > -2.0
                                (onset_line if near_line else onset_in).append(int(pstarts[j] - a))
                        if len(pends) and b < len(dead):
                            j = np.argmin(np.abs(pends - b))
                            if abs(pends[j] - b) <= 3 * FPS:
                                dend.append(int(pends[j] - b))
                                i = touch.first_after(t, pends[j], 3.0, lo=FPS)
                                if i >= 0:
                                    dend_touch.append(int(b - t[i]))
        out[dv] = {"pass_recall": float(np.mean(rec)), "n_pass": len(rec), "touch_offset_f": q(off),
                   "latency_f": {c: q(lat[c]) for c in br.C_GRID},
                   "gt_before_touch_f": {c: q(lat_after[c]) for c in br.C_GRID},
                   "no_touch_within_2s": {c: miss[c] for c in br.C_GRID},
                   "d_onset_lag_line_f": q(onset_line), "d_onset_lag_inside_f": q(onset_in),
                   "d_end_lag_f": q(dend), "gt_live_minus_first_touch_f": q(dend_touch)}
        print(json.dumps({"dv": dv, **out[dv]}), flush=True)
    return out


if __name__ == "__main__":
    warnings.filterwarnings("ignore")
    dvs = tuple(float(x) for x in sys.argv[1:]) or (2.0, 3.0, 4.0)
    main(dvs)
