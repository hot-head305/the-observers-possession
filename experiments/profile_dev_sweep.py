"""Workstream B: one-at-a-time sweep of Rules on the dev match under the fitted profile.

    uv run python experiments/profile_dev_sweep.py
"""
import json
import os
import sys
from dataclasses import replace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from possession import candidates as cd, harness as hs  # noqa: E402
from profile_cv import CELLS  # noqa: E402

SWEEP = dict(switch_k=(5, 10, 15, 25, 40), hidden_dead_s=(2.0, 4.0, 8.0, 15.0, 1e9),
             ctrl_r=(1.0, 1.5, 2.0, 3.0), ctrl_margin=(0.0, 0.5, 1.0),
             slow_ball=(1.2, 1.8, 2.5), slow_players=(1.2, 1.6, 2.0),
             min_dead_s=(1.0, 2.0, 3.0), fill_alive_s=(1.0, 3.0, 5.0), smooth_f=(0, 2, 5))


def dev(r):
    return float(hs.evaluate(cd.WithChannel(r), hs.SPLIT["dev"], cells=CELLS).spell.mean())


if __name__ == "__main__":
    base = cd.Rules()
    print(json.dumps({"base": dev(base)}), flush=True)
    for k, vals in SWEEP.items():
        print(json.dumps({k: {str(v): round(dev(replace(base, **{k: v})), 4) for v in vals}}), flush=True)
