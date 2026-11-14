"""CV under the degradation fitted to the real tracking profile (PLAN.md §6b, A/B).

Cells: the fitted Params (experiments/profile_params.json) with p_dead_hidden in {0.3, 0.5, 0.7}
(the share of fully unseen stoppages is the least identified unknown).

    uv run python experiments/profile_cv.py [split]
"""
import json
import os
import sys
from dataclasses import replace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from possession import candidates as cd, degrade as dg, harness as hs  # noqa: E402

FIT = dg.Params(**json.load(open(os.path.join(ROOT, "experiments", "profile_params.json"))))
CELLS = [replace(FIT, p_dead_hidden=p) for p in (0.3, 0.5, 0.7)]


def score(cands, split="cv"):
    out = {}
    for c in cands:
        r = hs.evaluate(c, hs.SPLIT[split], cells=CELLS, name=c.name)
        out[c.name] = r
        print(json.dumps({"name": c.name, **r.summary()}), flush=True)
    return out


if __name__ == "__main__":
    split = sys.argv[1] if len(sys.argv) > 1 else "cv"
    res = score([cd.Baseline(50), cd.WithChannel(cd.Rules())], split)
    b, v1 = list(res.values())
    print(json.dumps({"v1_vs_baseline": hs.compare(v1, b)}))
