"""CV gate on degraded IDSSE: incumbent vs <=3 candidates, logged to the registry.

    uv run python experiments/run_cv.py
"""
import json
import os
import sys
from dataclasses import asdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from possession import candidates as cd, harness as hs  # noqa: E402


def run(incumbent, cands, split="cv"):
    res = {}
    for c in [incumbent] + cands:
        r = hs.evaluate(c, hs.SPLIT[split], name=c.name)
        res[c.name] = r
        print(json.dumps({"name": c.name, **r.summary()}), flush=True)
    cmps = hs.promote([res[c.name] for c in cands], res[incumbent.name])
    for c, cmp in zip(cands, cmps):
        print(json.dumps({"candidate": c.name, "vs": incumbent.name, **cmp}), flush=True)
        hs.log(res[c.name], split, {"class": type(c).__name__, **asdict(c)},
               {"vs": incumbent.name, **cmp})
    hs.log(res[incumbent.name], split, {"class": type(incumbent).__name__, **asdict(incumbent)})
    return res, cmps


if __name__ == "__main__":
    run(cd.Baseline(50), [cd.Rules()])
