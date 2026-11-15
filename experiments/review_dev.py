"""Dev sweep (J03WPY only) for the v2 review fixes (candidates.RulesFix), fitted profile.

Picks the flag values before the candidates are named for CV (PLAN.md §2e item 2). The shape
weights come from the CV matches, as in experiments/shape_cv.py.

    uv run python experiments/review_dev.py [seeds]
"""
import json
import os
import sys
import warnings

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from possession import candidates as cd, harness as hs  # noqa: E402
from profile_cv import CELLS  # noqa: E402
from shape_cv import MIN_S, THR  # noqa: E402
from shape_train import train  # noqa: E402

VARIANTS = {
    "shape": {},
    "ctrl3_dv3": {"ctrl_rel_v": 3.0}, "ctrl3_dv2": {"ctrl_rel_v": 3.0, "ctrl_dv": 2.0},
    "ctrl3_dv4": {"ctrl_rel_v": 3.0, "ctrl_dv": 4.0}, "ctrl4_dv3": {"ctrl_rel_v": 4.0},
    "ctrl2_dv2": {"ctrl_rel_v": 2.0, "ctrl_dv": 2.0}, "ctrl3_nodv": {"ctrl_rel_v": 3.0, "ctrl_dv": 0.0},
    "stop5_d6_dec0": {"inside_m": 5.0, "calm_decel": 0.0},
    "stop5_d4_dec0": {"inside_m": 5.0, "calm_dead_s": 4.0, "calm_decel": 0.0},
    "stop5_d8_dec0": {"inside_m": 5.0, "calm_dead_s": 8.0, "calm_decel": 0.0},
    "stop5_d6_dec025": {"inside_m": 5.0, "calm_decel": 0.25},
    "stop5_d6_dec05": {"inside_m": 5.0, "calm_decel": 0.5},
    "stop10_d6_dec0": {"inside_m": 10.0, "calm_decel": 0.0},
}


def make(w, **kw):
    return cd.WithChannel(cd.RulesFix(shape_w=w, shape_thr=THR, shape_min_s=MIN_S, **kw))


if __name__ == "__main__":
    warnings.filterwarnings("ignore")
    seeds = range(int(sys.argv[1]) if len(sys.argv) > 1 else 2)
    w = train(hs.SPLIT["cv"])
    for k, kw in VARIANTS.items():
        r = hs.evaluate(make(w, **kw), hs.SPLIT["dev"], cells=CELLS, seeds=seeds, name=k, workers=1)
        print(json.dumps({"variant": k, **kw, **r.summary()}), flush=True)
