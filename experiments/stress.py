"""Does #4's gain over the baseline survive tracking that is worse than our default degradation?
External data only (CV matches, 2 seeds). Each row changes one Params field from the middle cell.

    uv run python experiments/stress.py > scratch/out/stress.txt
"""
import os
import sys
from dataclasses import replace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from possession import candidates as cd, degrade as dg, harness as hs  # noqa: E402

MID = dg.GRID[4]
ROWS = [
    ("default (middle cell)", {}),
    ("fragmentation x4 (short slot life)", {"player_off_mean_s": 0.5}),
    ("cross-team fragments 5%", {"p_cross_team": 0.05}),
    ("position noise x2", {"pos_noise": 0.6, "ball_noise": 1.2}),
    ("ball hidden 50%", {"hide_total": 0.50}),
    ("player dropout 15%", {"player_off_share": 0.15}),
    ("stoppage ball always carried (never placed)", {"placed_s": 0.0}),
    ("stoppage ball fully hidden", {"p_dead_hidden": 1.0}),
    ("IDSSE frozen dead ball (leaky, reference only)", {"dead_ball_motion": False}),
]

if __name__ == "__main__":
    for label, kw in ROWS:
        p = replace(MID, **kw)
        r = [hs.evaluate(c, hs.SPLIT["cv"], cells=(p,), seeds=(0, 1)) for c in (cd.Baseline(50), cd.Rules())]
        print("{:<48} baseline {:.3f}  rules {:.3f}  gain {:+.3f}  min match gain {:+.3f}".format(
            label, r[0].spell.mean(), r[1].spell.mean(), r[1].spell.mean() - r[0].spell.mean(),
            (r[1].per_match() - r[0].per_match()).min()), flush=True)
