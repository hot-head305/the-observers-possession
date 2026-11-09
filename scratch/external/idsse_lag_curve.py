"""Lag curve (perfect labels shifted k frames late) on IDSSE labels, raw and after a
definition-based 'controlled possession' relabel (spells shorter than m frames absorbed by the
previous team). Reported for comparison with EVALUATION.md's 1/3/8/25 -> 1.0/.9818/.8933/.6539.
Not used to fit anything.
"""
import glob
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "vendor", "official", "evaluation"))
sys.path.insert(0, os.path.join(ROOT, "scratch", "metric"))
import possession_metrics as pm  # noqa: E402
from sensitivity import boundary_lag  # noqa: E402

LBL = os.path.join(ROOT, "scratch", "out", "idsse_labels")


def absorb_short(lab, m):
    lab = lab.copy()
    if m <= 0:
        return lab
    changed = True
    while changed:
        changed = False
        for a, b, k in pm.segments(lab, [(0, len(lab))]):
            if k in (pm.H, pm.A) and b - a < m and a > 0 and lab[a - 1] in (pm.H, pm.A):
                lab[a:b] = lab[a - 1]
                changed = True
    return lab


def match_arrays():
    files = sorted(glob.glob(os.path.join(LBL, "J03*_*.npy")))
    by = {}
    for f in files:
        by.setdefault(os.path.basename(f).split("_")[0], []).append(np.load(f))
    for mid, secs in sorted(by.items()):
        parts = []
        for s in secs:
            parts += [s.astype(np.int8), np.full(500, pm.X, np.int8)]
        yield mid, np.concatenate(parts)


def main():
    print("published: lag1 1.0000 lag3 0.9818 lag8 0.8933 lag25 0.6539")
    for m in (0, 13, 25, 50):
        vals, stats = [], []
        for mid, gt in match_arrays():
            gt = absorb_short(gt, m)
            st = pm.possession_stats(gt, pm.valid_runs(gt))
            stats.append((st["n_spells"], st["mean_duration_s"]))
            vals.append([pm.evaluate(gt, boundary_lag(gt, None, k))["spell_f1_mean"] for k in (1, 3, 8, 25)])
        v = np.mean(vals, axis=0)
        n, d = np.mean(stats, axis=0)
        print("absorb<{:>3}f  poss/match {:>4.0f} mean {:>5.1f}s  lag1 {:.4f} lag3 {:.4f} lag8 {:.4f} lag25 {:.4f}".format(
            m, n, d, *v))


if __name__ == "__main__":
    main()
