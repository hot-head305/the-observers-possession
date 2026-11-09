"""Infer what possession-length distribution reproduces the published lag table.

EVALUATION.md (documentation, not data) quotes spellF1 for a perfect prediction shifted late by
1 / 3 / 8 / 25 frames: 1.0000 / 0.9818 / 0.8933 / 0.6539. Spell IoU under a uniform lag depends
only on the spell lengths, so this table constrains the hidden GT's length distribution.
Grid over lognormal(mean, sigma) with a minimum spell length.
"""
import itertools
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sensitivity as S  # noqa: E402

TARGET = {1: 1.0000, 3: 0.9818, 8: 0.8933, 25: 0.6539}


def make_gt_min(rng, mu_s, sigma, p_dead, dead_s, min_len):
    gt = S.make_gt(rng, mu_s, sigma, p_dead, dead_s)
    # Enforce a minimum spell length by absorbing shorter spells into the previous label.
    for (a, b, k) in S.pm.possession_spells(gt, S.runs_of(gt)):
        if b - a < min_len and a > 0:
            gt[a:b] = gt[a - 1]
    return gt


def main():
    rows = []
    for mu_s, sigma, min_len in itertools.product((5, 7, 9, 11, 14), (0.8, 1.0, 1.2, 1.4),
                                                  (1, 6, 12, 25)):
        sc = {k: [] for k in TARGET}
        stats = []
        for s in range(3):
            gt = make_gt_min(np.random.default_rng(50 + s), mu_s, sigma, 0.35, 20.0, min_len)
            st = S.pm.possession_stats(gt, S.runs_of(gt))
            stats.append((st["n_spells"], st["mean_duration_s"]))
            for k in TARGET:
                sc[k].append(S.pm.evaluate(gt, S.boundary_lag(gt, None, k))["spell_f1_mean"])
        m = {k: float(np.mean(v)) for k, v in sc.items()}
        err = float(np.sqrt(np.mean([(m[k] - TARGET[k]) ** 2 for k in TARGET])))
        n, d = np.mean(stats, axis=0)
        rows.append((err, mu_s, sigma, min_len, n, d, m))
    rows.sort(key=lambda r: r[0])
    print("rmse   mean_s sigma min_len  n_spells mean_dur  lag1   lag3   lag8   lag25")
    for err, mu_s, sigma, min_len, n, d, m in rows[:12]:
        print("{:.4f} {:>6} {:>5} {:>7} {:>9.0f} {:>8.1f}  {:.4f} {:.4f} {:.4f} {:.4f}".format(
            err, mu_s, sigma, min_len, n, d, m[1], m[3], m[8], m[25]))


if __name__ == "__main__":
    main()
