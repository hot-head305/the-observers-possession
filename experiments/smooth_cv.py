"""CV check for Rules position smoothing (smooth_f 0 vs 2) on the 9-cell grid and on the same
grid with 2x position noise. External data only; logged to the registry.

    uv run python experiments/smooth_cv.py
"""
import json
import os
import sys
from dataclasses import asdict, replace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from possession import candidates as cd, degrade as dg, harness as hs  # noqa: E402

NOISY = [replace(p, pos_noise=0.6, ball_noise=1.2) for p in dg.GRID]

if __name__ == "__main__":
    for label, cells in (("grid", range(len(dg.GRID))), ("grid_2x_noise", NOISY)):
        a = hs.evaluate(cd.Rules(smooth_f=0), hs.SPLIT["cv"], cells=cells, seeds=(0, 1, 2))
        b = hs.evaluate(cd.Rules(smooth_f=2), hs.SPLIT["cv"], cells=cells, seeds=(0, 1, 2))
        cmp = hs.compare(b, a)
        print(json.dumps({"cells": label, "smooth0": round(a.spell.mean(), 4),
                          "smooth2": round(b.spell.mean(), 4), **cmp}), flush=True)
        hs.log(b, "cv", {"class": "Rules", **asdict(cd.Rules(smooth_f=2)), "cells": label},
               {"vs": a.name, **cmp})
