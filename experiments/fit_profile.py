"""Fit the degradation to the real tracking profile (PLAN.md §6b, workstream A).

Grid search over the degradation unknowns so that degraded IDSSE (2 CV matches, same statistics
code as private/degrade_profile.py) matches the profile of the provided ATD. Uses only the
unsupervised profile, never labels of the provided game. Prints the best Params and writes
experiments/profile_params.json.

    uv run python experiments/fit_profile.py private_out/degrade_profile/degrade_profile.json
"""
import itertools
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from possession import degrade as dg, harness as hs, idsse, profile  # noqa: E402

REF = ("J03WMX", "J03WN1")
KEYS = ("hidden_share", "hidden_run_median_s", "hidden_run_p90_s", "objects_per_frame",
        "fragments_per_min", "fragment_median_s")
GRID = dict(gap_median_s=(8.0, 12.0, 20.0, 30.0),
            p_dead_hidden=(0.1, 0.3, 0.5),
            p_air=(0.0, 0.3, 0.6),
            player_off_mean_s=(3.0, 5.0, 8.0),
            player_off_share=(0.07, 0.09, 0.12))
FIXED = dict(pos_noise=0.0, ball_noise=0.0)


def sim(p, secs):
    rows = [profile.stats(o.ball, o.slots, np.ones(len(o.ball), bool))
            for mid, ss in secs for si, s in enumerate(ss)
            for o in [dg.degrade(s, p, hs._rng(mid, 0, 0, si))]]
    return {k: float(np.mean([r[k] for r in rows])) for k in rows[0]}


def cost(st, real):
    return float(sum(abs(np.log(max(st[k], 1e-9) / real[k])) for k in KEYS))


def main(path):
    real = json.load(open(path))["real"]
    secs = [(m, idsse.load(m)) for m in REF]
    best = None
    for vals in itertools.product(*GRID.values()):
        p = dg.Params(**dict(zip(GRID, vals)), **FIXED)
        st = sim(p, secs)
        c = cost(st, real)
        if best is None or c < best[0]:
            best = (c, dict(zip(GRID, vals)), st)
    c, kw, st = best
    kw.update(FIXED)
    print("cost", round(c, 3), kw)
    for k in st:
        print("  {:22s} real {:8.3f}  sim {:8.3f}".format(k, real[k], st[k]))
    with open(os.path.join(ROOT, "experiments", "profile_params.json"), "w") as f:
        json.dump(kw, f, indent=1, sort_keys=True)


if __name__ == "__main__":
    main(sys.argv[1])
