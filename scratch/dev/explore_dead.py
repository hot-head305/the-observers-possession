"""Dev-match only (J03WPY): which observable cues separate D from alive under degradation?"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from possession import degrade as dg, features as ft, harness as hs, idsse  # noqa: E402

secs = idsse.load("J03WPY")
for cell in (0, 4, 8):
    p = dg.GRID[cell]
    rows = []
    for si, s in enumerate(secs):
        obs = dg.degrade(s, p, hs._rng("J03WPY", cell, 0, si))
        f = ft.frame_features(obs)
        rows.append((s.label, f))
    lab = np.concatenate([r[0] for r in rows])
    f = {k: np.concatenate([r[1][k] for r in rows]) for k in rows[0][1]}
    dead = lab == 2
    print("cell", cell, p.gap_median_s, p.p_dead_hidden, "D share {:.3f}".format(dead.mean()))
    for k, v in f.items():
        v = v.astype(float)
        ok = ~np.isnan(v)
        qs = lambda m: np.nanpercentile(v[m & ok], [10, 50, 90]) if (m & ok).any() else [np.nan] * 3
        print("  {:<14} D {}  alive {}  nan D {:.2f} alive {:.2f}".format(
            k, np.round(qs(dead), 2), np.round(qs(~dead), 2), np.isnan(v[dead]).mean(), np.isnan(v[~dead]).mean()))
