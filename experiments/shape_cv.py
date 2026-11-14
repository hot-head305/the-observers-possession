"""Workstream C gate (PLAN.md §6b): RulesShape vs v1 on CV under the fitted profile.
Leave-one-match-out: the shape model is trained on the other CV matches only.

    uv run python experiments/shape_cv.py
"""
import json
import os
import sys
import warnings

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from possession import candidates as cd, harness as hs  # noqa: E402
from profile_cv import CELLS  # noqa: E402
from shape_train import train  # noqa: E402

THR, MIN_S = 0.6, 3.0  # chosen on dev (J03WPY), under the fitted profile and the old grid


def factory(mids):
    return cd.WithChannel(cd.RulesShape(shape_w=train(mids), shape_thr=THR, shape_min_s=MIN_S))


if __name__ == "__main__":
    warnings.filterwarnings("ignore")
    cv = hs.SPLIT["cv"]
    v1 = hs.evaluate(cd.WithChannel(cd.Rules()), cv, cells=CELLS, name="v1")
    v2 = hs.evaluate_lomo(factory, cv, name="v2_shape", cells=CELLS)
    for r in (v1, v2):
        print(json.dumps({"name": r.name, **r.summary()}))
    print(json.dumps({"v2_vs_v1": hs.compare(v2, v1)}))
