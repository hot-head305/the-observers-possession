"""Approach #1: 3-state (H, A, D) decoder with learned emissions and switch costs.

Emissions: naive Bayes over binned observable features, P(bin | state) counted on degraded
training matches (bridged labels, c = 1 s), scaled by `w` because neighbouring frames are far from
independent. Decoding: Viterbi with a cost per H<->A switch, per stop and per restart, so a switch
is only bought with sustained evidence. Non-causal, so no detection lag to correct.

    model = fit(train_matches)          # HMM with emission tables
    codes = model(obs)
"""
from dataclasses import dataclass, field, replace

import numpy as np

from . import bridge as br, degrade as dg, features as ft, idsse

H, A, D = 0, 1, 2
INF = np.inf

MARGIN = np.array([-INF, -5, -2, -1, -0.5, 0, 0.5, 1, 2, 5, INF])
NEAR = np.array([0, 1, 2, 4, 8, INF])
HID = np.array([0, 1, 2, 4, 8, INF])
BSPEED = np.array([0, 1, 1.5, 2, 3, 5, 10, INF])
PSPEED = np.array([0, 1, 1.25, 1.5, 1.75, 2, 2.5, 3, INF])
OUT = np.array([-INF, -5, -1, 0, 0.5, 2, INF])


def _bin(x, edges):
    """Bin index, with an extra last bin for NaN."""
    k = np.clip(np.searchsorted(edges, x, side="right") - 1, 0, len(edges) - 2)
    return np.where(np.isnan(x), len(edges) - 1, k)


def categories(f, ctrl_mode="bins"):
    """(T, 4) int category per feature group; sizes in SIZES.
    ctrl_mode "rules": group 0 is the rule machine's control evidence (H / A / none) in the
    first margin bins instead of binned distances; same table size, unused bins stay empty."""
    hidden = f["hidden"] > 0
    if ctrl_mode == "rules":
        from .candidates import Rules
        ev = Rules().evidence(f)
        n_ctrl = (len(MARGIN) - 1) * (len(NEAR) - 1)
        c0 = np.where(ev >= 0, ev, 2)
        c0 = np.where(hidden, n_ctrl + np.minimum(_bin(f["hidden_run_s"], HID), len(HID) - 2), c0)
        return np.stack([c0, _bin(f["bspeed_1s"], BSPEED), _bin(f["pspeed_4s"], PSPEED),
                         _bin(f["out_m"], OUT)], 1)
    m = np.nan_to_num(f["dA"], nan=INF) - np.nan_to_num(f["dH"], nan=INF)
    m = np.where(np.isnan(m), 0.0, m)  # inf - inf: nobody tracked near either side
    near = np.fmin(f["dH"], f["dA"])
    ctrl = _bin(m, MARGIN) * (len(NEAR) - 1) + np.minimum(_bin(near, NEAR), len(NEAR) - 2)
    n_ctrl = (len(MARGIN) - 1) * (len(NEAR) - 1)
    hid = n_ctrl + np.minimum(_bin(f["hidden_run_s"], HID), len(HID) - 2)
    c0 = np.where(hidden, hid, ctrl)
    return np.stack([c0, _bin(f["bspeed_1s"], BSPEED), _bin(f["pspeed_4s"], PSPEED),
                     _bin(f["out_m"], OUT)], 1)


SIZES = ((len(MARGIN) - 1) * (len(NEAR) - 1) + len(HID) - 1, len(BSPEED), len(PSPEED), len(OUT))


@dataclass(frozen=True)
class HMM:
    w: float = 0.1             # emission weight (frames are strongly autocorrelated)
    switch: float = 8.0        # cost of an H<->A switch, nats
    stop: float = 6.0          # alive -> D
    restart: float = 4.0       # D -> alive
    tables: tuple = field(default=(), repr=False, compare=False)  # log P(cat | state) per group
    ctrl_mode: str = "bins"
    tag: str = ""

    @property
    def name(self):
        return "hmm_{}_w{}_s{}_d{}_r{}{}".format(self.ctrl_mode, self.w, self.switch, self.stop,
                                                 self.restart, self.tag)

    def emissions(self, obs):
        c = categories(ft.frame_features(obs), self.ctrl_mode)
        e = np.zeros((len(c), 3))
        for g, tab in enumerate(self.tables):
            e += np.asarray(tab)[c[:, g]]
        return self.w * e

    def __call__(self, obs):
        return viterbi(self.emissions(obs), self.cost_matrix())

    def cost_matrix(self):
        C = np.zeros((3, 3))
        C[H, A] = C[A, H] = self.switch
        C[H, D] = C[A, D] = self.stop
        C[D, H] = C[D, A] = self.restart
        return C


def viterbi(e, C):
    """argmax_s sum_t e[t, s_t] - sum_t C[s_{t-1}, s_t].

    Where the evidence can't place a switch (ball hidden through a loose ball), every position
    scores the same. The tie goes to the latest one, because a loose ball carries the last team
    (CHALLENGE.md): a tie in a back-pointer prefers the other state, so backtracking from the end
    switches at the first (i.e. latest) frame it can.
    """
    T = len(e)
    back = np.zeros((T, 3), np.int8)
    score = e[0].copy()
    eps = 1e-9 * np.eye(3)  # back-pointer ties prefer a switch
    for t in range(1, T):
        cand = score[:, None] - C - eps    # from i to j
        back[t] = np.argmax(cand, axis=0)
        score = cand[back[t], np.arange(3)] + e[t]
    path = np.zeros(T, np.int8)
    path[-1] = int(np.argmax(score))
    for t in range(T - 1, 0, -1):
        path[t - 1] = back[t, path[t]]
    return path


def fit(matches, cells=(0, 4, 8), seed=0, c=25, alpha=1.0, ctrl_mode="bins", **kw):
    """Count P(cat | state) on degraded training matches. Deterministic."""
    from .harness import _rng
    counts = [np.full((n, 3), alpha) for n in SIZES]
    for mid in matches:
        secs = idsse.load(mid)
        ps = idsse.passes(mid, secs)
        for si, s in enumerate(secs):
            lab = br.bridge(s.label, br.pass_index(ps, si), c)
            for cell in cells:
                obs = dg.degrade(s, dg.GRID[cell], _rng("fit|" + mid, cell, seed, si))
                cat = categories(ft.frame_features(obs), ctrl_mode)
                for g in range(len(SIZES)):
                    np.add.at(counts[g], (cat[:, g], lab), 1)
    counts = symmetrise(counts, ctrl_mode)
    tables = tuple(tuple(map(tuple, np.log(k / k.sum(0, keepdims=True)))) for k in counts)
    return HMM(tables=tables, ctrl_mode=ctrl_mode, **kw)


def symmetrise(counts, ctrl_mode="bins"):
    """Home and away are the same kind of team: H with control margin m counts as A with -m, and
    every category that says nothing about which team (ball hidden, speeds, out of play) gets the
    same H and A column. Stops IDSSE's home/away habits leaking into the provided match."""
    out = [k.copy() for k in counts]
    n_m, n_n = len(MARGIN) - 1, len(NEAR) - 1
    c0 = counts[0]
    pairs = ([(H, A), (A, H), (2, 2)] if ctrl_mode == "rules" else
             [(mb * n_n + nb, (n_m - 1 - mb) * n_n + nb) for mb in range(n_m) for nb in range(n_n)])
    for i, j in pairs:
        out[0][i, H] = out[0][j, A] = (c0[i, H] + c0[j, A]) / 2
    rest = slice(n_m * n_n, None)
    out[0][rest, H] = out[0][rest, A] = (c0[rest, H] + c0[rest, A]) / 2
    for g in range(1, len(out)):
        out[g][:, H] = out[g][:, A] = (counts[g][:, H] + counts[g][:, A]) / 2
    return out


def with_params(model, **kw):
    return replace(model, **kw)
