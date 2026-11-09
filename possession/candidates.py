"""Candidates: callables Observed -> (T,) int8 codes H/A/D (possession_metrics codes).

Baseline   the official starter (nearest player to the visible ball, centred majority vote).
Rules      approach #4: hysteresis on sustained control, a dead-ball detector from out-of-bounds
           and slow ball + slow players, restarts owned by the first controlling team.
"""
import os
import sys
from dataclasses import asdict, dataclass

import numpy as np

from . import features as ft
from .idsse import ROOT

sys.path.insert(0, os.path.join(ROOT, "vendor", "official", "starter"))
from baseline import smooth  # noqa: E402  (official majority vote)

H, A, D = 0, 1, 2


def _runs(mask):
    e = np.diff(np.concatenate(([0], mask.astype(np.int8), [0])))
    return list(zip(np.flatnonzero(e == 1), np.flatnonzero(e == -1)))


@dataclass(frozen=True)
class Baseline:
    window: int = 50

    @property
    def name(self):
        return "baseline_w{}".format(self.window)

    def __call__(self, obs):
        f = ft.frame_features(obs)
        dH, dA = np.nan_to_num(f["dH"], nan=np.inf), np.nan_to_num(f["dA"], nan=np.inf)
        codes = np.where(dH <= dA, H, A).astype(np.int8)
        codes[np.isinf(dH) & np.isinf(dA)] = -1
        lab = smooth(codes, self.window)
        return np.select([lab == "H", lab == "A"], [H, A], D).astype(np.int8)


@dataclass(frozen=True)
class Rules:
    ctrl_r: float = 1.5        # m: nearest player this close = control evidence
    ctrl_margin: float = 0.5   # m: nearer than the nearest opponent by this much
    switch_k: int = 10         # evidence frames for the other team before a switch
    out_m: float = 0.5         # m beyond a line = out of play
    slow_ball: float = 1.8     # m/s
    slow_players: float = 1.6  # m/s, mean over tracked players, +-2 s
    hidden_dead_s: float = 4.0  # unseen this long with slow players = stoppage
    min_dead_s: float = 2.0
    fill_alive_s: float = 3.0  # alive blips shorter than this inside a stoppage are dead
    # Defaults chosen on the dev match (J03WPY) by a one-at-a-time sweep plus one combined round
    # (scratch/dev/quick.py, 2026-11-09); never on CV or test matches.

    @property
    def name(self):
        return "rules_" + "_".join("{}".format(v) for v in asdict(self).values())

    def dead_mask(self, f):
        slow_p = np.nan_to_num(f["pspeed_4s"], nan=0) < self.slow_players
        out = np.nan_to_num(f["out_m"], nan=-99) > self.out_m
        slow_b = np.nan_to_num(f["bspeed_1s"], nan=99) < self.slow_ball
        long_hidden = f["hidden_run_s"] >= self.hidden_dead_s
        dead = out | (slow_b & slow_p) | (long_hidden & slow_p)
        fps = ft.FPS
        for a, b in _runs(~dead):
            if b - a < self.fill_alive_s * fps and a > 0 and b < len(dead):
                dead[a:b] = True
        for a, b in _runs(dead):
            if b - a < self.min_dead_s * fps:
                dead[a:b] = False
        return dead

    def evidence(self, f):
        dH, dA = f["dH"], f["dA"]
        dHn, dAn = np.nan_to_num(dH, nan=np.inf), np.nan_to_num(dA, nan=np.inf)
        ev = np.full(len(dH), -1, np.int8)
        ev[(dHn < self.ctrl_r) & (dHn + self.ctrl_margin < dAn)] = H
        ev[(dAn < self.ctrl_r) & (dAn + self.ctrl_margin < dHn)] = A
        return ev

    def __call__(self, obs):
        f = ft.frame_features(obs)
        dead = self.dead_mask(f)
        ev = self.evidence(f)
        ev[dead] = -1
        T = len(ev)
        dead_cum = np.cumsum(dead)
        cur, streak_team, streak_start, streak_n, last = -1, -1, 0, 0, -1
        idx = np.flatnonzero(ev >= 0)
        # Walk evidence frames; a switch is placed at the first evidence frame of the new team's
        # streak (loose ball between carries the previous team, CHALLENGE.md). After a stoppage
        # the first team with evidence owns the restart, back-filled to the end of the D run.
        switches = []
        for t in idx:
            k = int(ev[t])
            if last >= 0 and dead_cum[t] > dead_cum[last]:
                cur, streak_n = -1, 0
                restart = last + int(np.flatnonzero(dead[last:t])[-1]) + 1
            else:
                restart = t
            last = t
            if cur < 0:
                cur = k
                switches.append((restart if switches else t, k))
                continue
            if k == cur:
                streak_n = 0
                continue
            if k != streak_team or streak_n == 0:
                streak_team, streak_start, streak_n = k, t, 0
            streak_n += 1
            if streak_n >= self.switch_k:
                cur = k
                switches.append((streak_start, k))
                streak_n = 0
        lab = np.full(T, -1, np.int8)
        for i, (t, k) in enumerate(switches):
            end = switches[i + 1][0] if i + 1 < len(switches) else T
            lab[t:end] = k
        if switches:
            lab[:switches[0][0]] = switches[0][1]
        else:
            lab[:] = H
        lab[dead] = D
        return lab
