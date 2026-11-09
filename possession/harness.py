"""Evaluation harness on degraded IDSSE (PLAN.md §2d-2f). External data only.

A candidate is a callable `predict(obs) -> (T,) int8 codes` (H/A/D/X as in possession_metrics)
per section. Each match is scored with the official scorer against the bridged DFL labels for
every degradation cell x seed x bridge c; seeds are averaged within a match, so the sample size
for every comparison is the number of matches.

    res = evaluate(cand, SPLIT["cv"])       # res.spell[match, cell, bridge]
    cmp = compare(res_b, res_a)             # paired, block bootstrap over matches
"""
import hashlib
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass

import numpy as np

from . import bridge as br, degrade as dg, idsse

ROOT = idsse.ROOT
sys.path.insert(0, os.path.join(ROOT, "vendor", "official", "evaluation"))
import possession_metrics as pm  # noqa: E402

SPLIT = {"cv": ("J03WMX", "J03WN1", "J03WOH", "J03WOY"), "dev": ("J03WPY",),
         "test": ("J03WQQ", "J03WR9")}
SEEDS = 5
GAP = 500  # X frames between sections so the scorer treats them as separate halves
REGISTRY = os.path.join(ROOT, "experiments", "registry.jsonl")
MIN_GAIN = 0.03
P_MIN = 0.9
BOOT_N = 10000


@dataclass
class Result:
    name: str
    matches: tuple
    spell: np.ndarray   # (M, cells, bridges) spellF1 mean, seed-averaged
    macro: np.ndarray   # same shape, macroF1
    n_pred: np.ndarray  # same shape, predicted spells per match

    def per_match(self):
        return self.spell.mean(axis=(1, 2))

    def summary(self):
        return {"spell": float(self.spell.mean()), "macro": float(self.macro.mean()),
                "spell_per_match": [round(float(v), 4) for v in self.per_match()],
                "spell_min_cell": float(self.spell.mean(0).min()),
                "spell_max_cell": float(self.spell.mean(0).max())}


def _rng(mid, cell, seed, si):
    h = hashlib.sha256("{}|{}|{}|{}".format(mid, cell, seed, si).encode()).digest()
    return np.random.default_rng(int.from_bytes(h[:8], "little"))


def truths(mid):
    secs = idsse.load(mid)
    ps = idsse.passes(mid, secs)
    return secs, [[br.bridge(s.label, br.pass_index(ps, si), c) for c in br.C_GRID]
                  for si, s in enumerate(secs)]


def _assemble(parts):
    out = []
    for p in parts:
        out += [p.astype(np.int8), np.full(GAP, pm.X, np.int8)]
    return np.concatenate(out)


def _score_match(args):
    cand, mid, cells, seeds = args
    secs, gts = truths(mid)
    nb = len(br.C_GRID)
    gt = [_assemble([g[b] for g in gts]) for b in range(nb)]
    S = np.zeros((len(cells), nb, 3))
    for ci, cell in enumerate(cells):
        p = dg.GRID[cell]
        for seed in seeds:
            pred = _assemble([cand(dg.degrade(s, p, _rng(mid, cell, seed, si)))
                              for si, s in enumerate(secs)])
            pred[gt[0] == pm.X] = pm.X
            for b in range(nb):
                r = pm.evaluate(gt[b], pred)
                S[ci, b] += (r["spell_f1_mean"], r["macro_f1"], r["n_pred_spells"])
    return S / len(seeds)


def evaluate(cand, matches, cells=range(len(dg.GRID)), seeds=range(SEEDS), name=None, workers=None):
    cells, seeds = tuple(cells), tuple(seeds)
    jobs = [(cand, m, cells, seeds) for m in matches]
    if workers == 1:
        out = [_score_match(j) for j in jobs]
    else:
        with ProcessPoolExecutor(max_workers=workers or min(len(jobs), os.cpu_count() or 1)) as ex:
            out = list(ex.map(_score_match, jobs))
    S = np.stack(out)
    return Result(name or getattr(cand, "name", repr(cand)), tuple(matches), S[..., 0], S[..., 1], S[..., 2])


def compare(b, a, n=BOOT_N, seed=0):
    """Paired gain of b over a. Bootstrap resamples matches (the only independent unit)."""
    assert b.matches == a.matches
    g = b.per_match() - a.per_match()
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(g), (n, len(g)))
    boot = g[idx].mean(1)
    cell_gain = (b.spell - a.spell).mean(0)  # (cells, bridges)
    return {"gain": float(g.mean()), "p_gain_pos": float((boot > 0).mean()),
            "p_value": float((boot <= 0).mean()), "min_cell_gain": float(cell_gain.min()),
            "no_sign_flip": bool((cell_gain > 0).all())}


def holm(pvals):
    """Holm-adjusted p-values, same order as given."""
    order = np.argsort(pvals)
    m, adj, run = len(pvals), np.zeros(len(pvals)), 0.0
    for k, i in enumerate(order):
        run = max(run, min(1.0, (m - k) * pvals[i]))
        adj[i] = run
    return adj


def promote(cands, incumbent):
    """Promotion rule §2e items 1-3 on external data, for at most 3 candidates."""
    assert len(cands) <= 3
    cmps = [compare(c, incumbent) for c in cands]
    adj = holm([c["p_value"] for c in cmps])
    for c, p in zip(cmps, adj):
        c["p_holm"] = float(p)
        c["promote"] = bool(c["gain"] >= MIN_GAIN and 1 - p >= P_MIN and c["no_sign_flip"])
    return cmps


def _git_sha():
    """HEAD, suffixed -dirty when tracked files differ from it (the row then isn't reproducible)."""
    try:
        run = lambda *a: subprocess.run(["git", "-C", ROOT, *a], capture_output=True, text=True,
                                        check=True).stdout.strip()
        dirty = run("status", "--porcelain", "--untracked-files=no", "--ignore-submodules=dirty")
        return run("rev-parse", "HEAD") + ("-dirty" if dirty else "")
    except Exception:
        return "unknown"


def config_hash(config):
    return hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()[:12]


def log(result, split, config, extra=None, path=REGISTRY):
    if split == "test":
        raise RuntimeError("locked-test lines are written only by make locked-test")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    row = {"time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "git": _git_sha(),
           "name": result.name, "split": split, "config": config, "config_hash": config_hash(config),
           "seeds": SEEDS, "matches": list(result.matches), **result.summary(), **(extra or {})}
    with open(path, "a") as f:
        f.write(json.dumps(row, sort_keys=True) + "\n")
    return row
