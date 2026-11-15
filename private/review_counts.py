"""Unsupervised review counts of a candidate file on the match (no GT; PLAN.md §6b review fixes).

    spells          H/A spells inside the graded half blocks
    d_runs          D runs inside the blocks
    d_inside_short  D runs under --max-s seconds whose last ball sighting (within 1 s before the
                    run, or at its first frame) lies more than --inside-m metres inside the field,
                    with the same team labelled before and after the run (v1 has 21 of these)
    turnovers       direct H<->A switches
    short_spells    H/A spells under 2 s

Detail to <out>/review_counts.json; one line per count. Exit 0 always (these are counts, not gates).
"""
import json
import os
import sys

import numpy as np

from _common import ROOT, parser, paths

sys.path.insert(0, ROOT)
from possession import match  # noqa: E402

FPS = 25
PITCH = np.array([105.0, 68.0])


def runs(mask):
    e = np.diff(np.concatenate(([0], mask.astype(np.int8), [0])))
    return list(zip(np.flatnonzero(e == 1), np.flatnonzero(e == -1)))


def counts(codes, ball, inside, max_s=6.0, inside_m=5.0):
    c = np.where(inside, codes, match.X)
    xy = ball * PITCH
    depth = np.minimum(np.minimum(xy[:, 0], PITCH[0] - xy[:, 0]), np.minimum(xy[:, 1], PITCH[1] - xy[:, 1]))
    vis = ~np.isnan(ball[:, 0])
    spells = [(a, b) for a, b in runs(np.isin(c, (match.H, match.A))) if True]
    # maximal single-team runs
    team_runs = [(a, b) for k in (match.H, match.A) for a, b in runs(c == k)]
    team_runs.sort()
    d_runs = runs(c == match.D)
    n_short_inside = 0
    for a, b in d_runs:
        if b - a >= max_s * FPS:
            continue
        lo = max(0, a - FPS)
        seen = np.flatnonzero(vis[lo:a + 1])
        if not len(seen):
            continue
        t = lo + seen[-1]
        if depth[t] <= inside_m:
            continue
        before = c[a - 1] if a > 0 else match.X
        after = c[b] if b < len(c) else match.X
        if before in (match.H, match.A) and before == after:
            n_short_inside += 1
    turn = int(np.sum((c[1:] != c[:-1]) & np.isin(c[1:], (0, 1)) & np.isin(c[:-1], (0, 1))))
    short = sum(1 for a, b in team_runs if b - a < 2 * FPS)
    return {"spells": len(team_runs), "d_runs": len(d_runs), "d_inside_short": n_short_inside,
            "turnovers": turn, "short_spells": short,
            "alive_min": float(np.isin(c, (0, 1)).sum() / FPS / 60)}


def main(argv=None):
    ap = parser(__doc__)
    ap.add_argument("--csv", required=True)
    ap.add_argument("--max-s", type=float, default=6.0)
    ap.add_argument("--inside-m", type=float, default=5.0)
    a = ap.parse_args(argv)
    import possession_metrics as pm
    import games
    codes = pm.label_codes(pm.read_label_csv(a.csv))
    p = paths(a.data)
    ball, slots, team, extra = match.load(p["atd_meta"], p["atd_raw"], a.n_frames)
    inside = np.zeros(len(codes), bool)
    for half, first, last in games.half_video_blocks(games.GAME):
        inside[max(0, first):min(len(codes), last + 1)] = True
    out = {"csv": a.csv, **counts(codes, ball, inside, a.max_s, a.inside_m)}
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, "review_counts.json"), "w") as f:
        json.dump(out, f, indent=2, sort_keys=True)
    for k, v in out.items():
        print("{:<16} {}".format(k, v))
    return 0


if __name__ == "__main__":
    sys.exit(main())
