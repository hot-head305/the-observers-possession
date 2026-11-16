"""CV gate for candidate `Spec` (candidates.RulesSpec) against v2 `shape` and `fix_stop`.

PLAN.md §6b protocol: CV matches, 5 seeds, 3 bridges, fitted profile (p_dead 0.3/0.5/0.7),
leave-one-match-out shape weights. The Holm budget for this gate counts four candidates (the three
review fixes of 2026-11-15 and Spec), so all four are re-scored here and corrected together.
Per-bridge results are reported separately (DFL BallPossession may follow another convention).
Rows go to the registry (split cv).

    uv run python experiments/spec_cv.py
"""
import json
import os
import sys
import warnings
from dataclasses import asdict

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from possession import bridge as br, candidates as cd, harness as hs  # noqa: E402
from profile_cv import CELLS  # noqa: E402
from review_cv import CANDS as FIX  # noqa: E402
from shape_cv import MIN_S, THR  # noqa: E402
from shape_train import train  # noqa: E402

# Spec parameters chosen on dev (experiments/spec_dev.py, 3 seeds) and spec_calib.py, before this run.
SPEC = {"pre_dead_s": 2.0, "vanish_out_s": 1.0, "dead_lead_f": 25}
GATE_6B = 0.010


def factory(cls, kw):
    return lambda mids: cd.WithChannel(cls(shape_w=train(mids), shape_thr=THR, shape_min_s=MIN_S, **kw))


def config(cls, kw):
    d = asdict(cd.WithChannel(cls(shape_w=(), shape_thr=THR, shape_min_s=MIN_S, **kw)))
    d["base"]["shape_w"] = "lomo"
    return {"class": "WithChannel", "base_class": cls.__name__, **d}


def per_bridge(r, b):
    return hs.Result(r.name, r.matches, r.spell[:, :, b:b + 1], r.macro[:, :, b:b + 1], r.n_pred[:, :, b:b + 1])


def gate(cmps, cands, inc):
    adj = hs.holm([c["p_value"] for c in cmps])
    for c, p, r in zip(cmps, adj, cands):
        g = r.per_match() - inc.per_match()
        c["p_holm"] = float(p)
        c["promote"] = bool(c["gain"] >= hs.MIN_GAIN and 1 - p >= hs.P_MIN and c["no_sign_flip"])
        c["gate_6b"] = bool(c["gain"] >= GATE_6B and (g > 0).all())
        c["per_match_gain"] = [round(float(v), 4) for v in g]
    return cmps


if __name__ == "__main__":
    warnings.filterwarnings("ignore")
    cv = hs.SPLIT["cv"]
    inc = hs.evaluate_lomo(factory(cd.RulesFix, {}), cv, name="v2_shape", cells=CELLS)
    print(json.dumps({"name": inc.name, **inc.summary()}), flush=True)
    res = {}
    for k, kw in FIX.items():
        res["fix_" + k] = hs.evaluate_lomo(factory(cd.RulesFix, kw), cv, name="fix_" + k, cells=CELLS)
    res["spec"] = hs.evaluate_lomo(factory(cd.RulesSpec, SPEC), cv, name="spec", cells=CELLS)
    for k, r in res.items():
        print(json.dumps({"name": r.name, **r.summary(), "n_pred": float(r.n_pred.mean())}), flush=True)
    names = list(res)
    cmps = gate([hs.compare(res[k], inc) for k in names], [res[k] for k in names], inc)
    out = {"vs_shape": {}, "vs_fix_stop": {}, "per_bridge": {}}
    for k, c in zip(names, cmps):
        out["vs_shape"][k] = c
        print(json.dumps({"candidate": k, "vs": inc.name, **c}), flush=True)
    c2 = hs.compare(res["spec"], res["fix_stop"])
    g = res["spec"].per_match() - res["fix_stop"].per_match()
    c2["per_match_gain"] = [round(float(v), 4) for v in g]
    c2["gate_6b"] = bool(c2["gain"] >= GATE_6B and (g > 0).all())
    out["vs_fix_stop"]["spec"] = c2
    print(json.dumps({"candidate": "spec", "vs": "fix_stop", **c2}), flush=True)
    for b, c in enumerate(br.C_GRID):
        incb = per_bridge(inc, b)
        rb = [per_bridge(res[k], b) for k in names]
        cb = gate([hs.compare(r, incb) for r in rb], rb, incb)
        fb = hs.compare(per_bridge(res["spec"], b), per_bridge(res["fix_stop"], b))
        row = {"bridge_c": c, "shape": float(incb.spell.mean()),
               **{k: {"spell": float(r.spell.mean()), **cc} for k, r, cc in zip(names, rb, cb)},
               "spec_vs_fix_stop": fb}
        out["per_bridge"][c] = row
        print(json.dumps(row), flush=True)
    for k, kw in FIX.items():
        hs.log(res["fix_" + k], "cv", config(cd.RulesFix, kw),
               {"vs": inc.name, "profile": "fitted", "holm_m": 4, **out["vs_shape"]["fix_" + k]})
    hs.log(res["spec"], "cv", config(cd.RulesSpec, SPEC),
           {"vs": inc.name, "profile": "fitted", "holm_m": 4, **out["vs_shape"]["spec"],
            "vs_fix_stop": c2,
            "per_bridge": {str(c): {"spell": out["per_bridge"][c]["spec"]["spell"],
                                    "gain_vs_shape": out["per_bridge"][c]["spec"]["gain"],
                                    "p_holm": out["per_bridge"][c]["spec"]["p_holm"],
                                    "gain_vs_fix_stop": out["per_bridge"][c]["spec_vs_fix_stop"]["gain"]}
                           for c in br.C_GRID}})
    hs.log(inc, "cv", config(cd.RulesFix, {}), {"profile": "fitted", "lomo": True})
    os.makedirs(os.path.join(hs.ROOT, "scratch", "out"), exist_ok=True)
    with open(os.path.join(hs.ROOT, "scratch", "out", "spec_cv.json"), "w") as f:
        json.dump(out, f, indent=1, default=str)
