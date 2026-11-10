"""Human-run: does our default degradation look like the provided tracking? (PLAN.md §2b)

Profiles the tactical ATD on the graded half blocks and degraded IDSSE (default middle cell, two
CV matches) with the same code (possession/profile.py). One PASS/FAIL line per statistic;
the real profile goes to <out>/degrade_profile.json, never anywhere else.
"""
import sys

import numpy as np

from _common import ROOT, parser, paths, report

sys.path.insert(0, ROOT)
from possession import degrade as dg, harness as hs, idsse, match, profile  # noqa: E402

REF_MATCHES = ("J03WMX", "J03WN1")


def reference():
    rows = []
    for mid in REF_MATCHES:
        for si, s in enumerate(idsse.load(mid)):
            obs = dg.degrade(s, dg.GRID[4], hs._rng(mid, 4, 0, si))
            rows.append(profile.stats(obs.ball, obs.slots, np.ones(len(obs.ball), bool)))
    return {k: float(np.mean([r[k] for r in rows])) for k in rows[0]}


def main(argv=None):
    a = parser(__doc__).parse_args(argv)
    import games
    p = paths(a.data)
    ball, slots, _, _ = match.load(p["atd_meta"], p["atd_raw"], a.n_frames)
    mask = np.zeros(a.n_frames, bool)
    for _, first, last in games.half_video_blocks(games.GAME):
        mask[max(0, first):min(a.n_frames, last + 1)] = True
    real = profile.stats(ball, slots, mask)
    ref = reference()
    checks = [("{} matches our degradation".format(k), profile.agree(real[k], ref[k], k)) for k in real]
    return report(a.out, "degrade_profile", checks, {"real": real, "reference_degraded_idsse": ref,
                                                     "tolerance": profile.TOL})


if __name__ == "__main__":
    sys.exit(main())
