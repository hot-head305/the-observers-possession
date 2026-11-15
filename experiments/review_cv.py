"""CV gate for the v2 review fixes (candidates.RulesFix) against the v2 incumbent `shape`.

PLAN.md §6b protocol: CV matches, 5 seeds, 3 bridges, fitted profile with p_dead in {0.3,0.5,0.7};
leave-one-match-out shape weights for every candidate (experiments/shape_cv.py). Holm over the
three candidates (ctrl, stop, both); rows logged to the registry (split cv).

    uv run python experiments/review_cv.py
"""
import json
import os
import sys
import warnings
from dataclasses import asdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from possession import candidates as cd, harness as hs  # noqa: E402
from profile_cv import CELLS  # noqa: E402
from shape_cv import MIN_S, THR  # noqa: E402
from shape_train import train  # noqa: E402

# Flag values chosen on dev (experiments/review_dev.py), before this run.
CTRL = {"ctrl_rel_v": 2.0, "ctrl_dv": 2.0}
STOP = {"inside_m": 5.0, "calm_dead_s": 6.0, "calm_decel": 0.0}
CANDS = {"ctrl": CTRL, "stop": STOP, "both": {**CTRL, **STOP}}


def factory(kw):
    return lambda mids: cd.WithChannel(cd.RulesFix(shape_w=train(mids), shape_thr=THR,
                                                   shape_min_s=MIN_S, **kw))


def config(kw):
    c = cd.RulesFix(shape_w=(), shape_thr=THR, shape_min_s=MIN_S, **kw)
    d = asdict(cd.WithChannel(c))
    d["base"]["shape_w"] = "lomo"
    return {"class": "WithChannel", "base_class": "RulesFix", **d}


if __name__ == "__main__":
    warnings.filterwarnings("ignore")
    cv = hs.SPLIT["cv"]
    inc = hs.evaluate_lomo(factory({}), cv, name="v2_shape", cells=CELLS)
    print(json.dumps({"name": inc.name, **inc.summary()}), flush=True)
    res = {}
    for k, kw in CANDS.items():
        res[k] = hs.evaluate_lomo(factory(kw), cv, name="fix_" + k, cells=CELLS)
        print(json.dumps({"name": res[k].name, **kw, **res[k].summary()}), flush=True)
    cmps = hs.promote(list(res.values()), inc)
    for (k, kw), cmp in zip(CANDS.items(), cmps):
        g = res[k].per_match() - inc.per_match()
        cmp["gate_6b"] = bool(cmp["gain"] >= 0.010 and (g > 0).all())
        cmp["per_match_gain"] = [round(float(v), 4) for v in g]
        print(json.dumps({"candidate": res[k].name, "vs": inc.name, **cmp}), flush=True)
        hs.log(res[k], "cv", config(kw), {"vs": inc.name, "profile": "fitted", **cmp})
    hs.log(inc, "cv", config({}), {"profile": "fitted", "lomo": True})
