"""Train the team-shape model (possession/shape.py) on IDSSE matches under the fitted profile.

    weights = train(("J03WMX", ...))
"""
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "experiments"))
from possession import degrade as dg, harness as hs, shape  # noqa: E402
from profile_cv import CELLS  # noqa: E402


def train(mids, seeds=(0,)):
    Xs, ys = [], []
    for mid in mids:
        secs, gts = hs.truths(mid)
        for si, s in enumerate(secs):
            for ci, cell in enumerate(CELLS):
                for seed in seeds:
                    o = dg.degrade(s, cell, hs._rng(mid, "shape{}".format(ci), seed, si))
                    y = gts[si][1]
                    m = y < 2
                    Xs.append(shape.features(o)[m])
                    ys.append((y[m] == 0).astype(float))
    with np.errstate(all="ignore"):
        return shape.fit(np.vstack(Xs), np.concatenate(ys))
