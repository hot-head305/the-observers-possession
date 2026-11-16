"""Dev sweep (J03WPY only, fitted profile) for candidate `Spec` (candidates.RulesSpec).

Sets the Spec parameters before the candidate is named for CV (PLAN.md §2e item 2). References:
shape (v2) and fix_stop under the same seeds. Shape weights from the CV matches (shape_cv).

    uv run python experiments/spec_dev.py [seeds] [round]
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

STOP = {"inside_m": 5.0, "calm_dead_s": 6.0, "calm_decel": 0.0}
ROUNDS = {
    "1": {  # one at a time from the defaults (dv 3, r 2.5, ctrl_k 10, lat 1, back 3 s)
        "spec": {},
        "dv2": {"touch_dv": 2.0}, "dv4": {"touch_dv": 4.0}, "dv5": {"touch_dv": 5.0},
        "r2": {"touch_r": 2.0}, "r3": {"touch_r": 3.0}, "margin05": {"touch_margin": 0.5},
        "k6": {"ctrl_k": 6}, "k15": {"ctrl_k": 15}, "k20": {"ctrl_k": 20},
        "lat0": {"lat_f": 0}, "lat5": {"lat_f": 5},
        "back1": {"back_s": 1.0}, "back2": {"back_s": 2.0}, "back5": {"back_s": 5.0},
        "pre1": {"pre_dead_s": 1.0}, "pre2": {"pre_dead_s": 2.0}, "pre3": {"pre_dead_s": 3.0},
        "rlat-6": {"restart_lat_f": -6}, "rlat0": {"restart_lat_f": 0},
        "van1": {"vanish_out_s": 1.0}, "van2": {"vanish_out_s": 2.0},
        "lead12": {"dead_lead_f": 12}, "lead25": {"dead_lead_f": 25}, "lead40": {"dead_lead_f": 40},
        "relv2": {"ctrl_rel_v": 2.0, "ctrl_dv": 2.0}, "relv3": {"ctrl_rel_v": 3.0, "ctrl_dv": 3.0},
    },
}


def make(w, **kw):
    return cd.WithChannel(cd.RulesSpec(shape_w=w, shape_thr=THR, shape_min_s=MIN_S, **kw))


if __name__ == "__main__":
    warnings.filterwarnings("ignore")
    seeds = range(int(sys.argv[1]) if len(sys.argv) > 1 else 2)
    rnd = sys.argv[2] if len(sys.argv) > 2 else "1"
    w = train(hs.SPLIT["cv"])
    refs = {"shape": cd.WithChannel(cd.RulesShape(shape_w=w, shape_thr=THR, shape_min_s=MIN_S)),
            "fix_stop": cd.WithChannel(cd.RulesFix(shape_w=w, shape_thr=THR, shape_min_s=MIN_S, **STOP))}
    for k, c in refs.items():
        r = hs.evaluate(c, hs.SPLIT["dev"], cells=CELLS, seeds=seeds, name=k, workers=1)
        print(json.dumps({"variant": k, **r.summary(), "n_pred": float(r.n_pred.mean())}), flush=True)
    variants = ROUNDS[rnd] if rnd in ROUNDS else json.loads(rnd)
    for k, kw in variants.items():
        r = hs.evaluate(make(w, **kw), hs.SPLIT["dev"], cells=CELLS, seeds=seeds, name=k, workers=1)
        print(json.dumps({"variant": k, **kw, **r.summary(), "n_pred": float(r.n_pred.mean())}), flush=True)
