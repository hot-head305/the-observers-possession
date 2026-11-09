"""Profile per-frame possession in one SkillCorner open-data match (A-League, 10 fps, MIT).

    uv run python -I scratch/external/skillcorner_profile.py scratch/data/skillcorner/1886347_tracking.jsonl
"""
import collections
import json
import sys

import numpy as np

path = sys.argv[1]
groups, ball_present, periods = [], [], []
keys = collections.Counter()
for line in open(path):
    fr = json.loads(line)
    keys.update(fr.keys())
    poss = fr.get("possession") or {}
    groups.append(poss.get("group"))
    b = fr.get("ball_data") or {}
    ball_present.append(b.get("x") is not None)
    periods.append(fr.get("period"))

print("frames", len(groups), "keys", dict(keys))
print("possession.group values", collections.Counter(groups).most_common())
g = np.array([{"home team": 0, "away team": 1}.get(x, 2) for x in groups])
per = np.array([p if p is not None else 0 for p in periods])
inplay = per > 0
print("ball xy present on {:.1%} of in-period frames".format(np.mean(np.array(ball_present)[inplay])))
# Possession spells = maximal runs of home/away; None treated as a break (like D).
lens = []
for p in (1, 2):
    w = g[per == p]
    br = np.flatnonzero(w[1:] != w[:-1]) + 1
    b = np.concatenate(([0], br, [len(w)]))
    for i in range(len(b) - 1):
        if w[b[i]] in (0, 1):
            lens.append(b[i + 1] - b[i])
lens = np.array(lens) / 10.0
alive_min = np.sum(np.isin(g[inplay], (0, 1))) / 600
print("spells {}  mean {:.1f}s median {:.1f}s  p10 {:.1f}s p90 {:.1f}s  <1s {:.1%}  <2s {:.1%}".format(
    len(lens), lens.mean(), np.median(lens), *np.percentile(lens, [10, 90]),
    np.mean(lens < 1), np.mean(lens < 2)))
print("null-possession share of in-period frames {:.1%}; spells per possessed minute {:.2f}".format(
    np.mean(g[inplay] == 2), len(lens) / alive_min))
