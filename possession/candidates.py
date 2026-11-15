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
from . import shape
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
    smooth_f: int = 2          # +-frames of position smoothing before features
    # Defaults chosen on the dev match (J03WPY) by a one-at-a-time sweep plus one combined round
    # (scratch/dev/quick.py, 2026-11-09); never on CV or test matches. smooth_f=2 picked on dev
    # (scratch/dev/quick_smooth.py) as the minimax over 1x/2x position noise, confirmed on CV by
    # experiments/smooth_cv.py: +0.016 at 1x, +0.134 at 2x (real tracker noise is unknown).

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
        f = self.features(obs)
        dead = self.dead_mask(f)
        ev = self.evidence(f)
        ev[dead] = -1
        T = len(ev)
        dead_cum = np.cumsum(dead)
        cur, streak_team, streak_start, streak_n, last, last_cur = -1, -1, 0, 0, -1, -1
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
                cur, last_cur = k, t
                switches.append((restart if switches else t, k))
                continue
            if k == cur:
                streak_n, last_cur = 0, t
                continue
            if k != streak_team or streak_n == 0:
                streak_team, streak_start, streak_n = k, t, 0
            streak_n += 1
            if streak_n >= self.switch_k:
                cur = k
                switches.append((self._switch_at(last_cur, streak_start), k))
                streak_n, last_cur = 0, t
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

    def features(self, obs):
        return ft.frame_features(obs, self.smooth_f)

    def _switch_at(self, last_cur, streak_start):
        """Frame where a switch starts: the new team's first evidence frame."""
        return streak_start


@dataclass(frozen=True)
class RulesShape(Rules):
    """#4 plus team-shape evidence (possession/shape.py) on frames where the ball has been
    unseen for at least shape_min_s: P(H) above shape_thr is H evidence, below 1 - shape_thr A."""
    shape_w: tuple = ()
    shape_thr: float = 0.8
    shape_min_s: float = 1.0

    @property
    def name(self):
        return "shape_{}_{}_".format(self.shape_thr, self.shape_min_s) + Rules(**{
            k: getattr(self, k) for k in Rules.__dataclass_fields__}).name

    def features(self, obs):
        f = super().features(obs)
        if self.shape_w:
            f["shape_p"] = np.round(shape.predict(self.shape_w, shape.features(obs)), 6)
        return f

    def evidence(self, f):
        ev = super().evidence(f)
        if not self.shape_w:  # no weights: plain Rules evidence
            return ev
        hid = (f["hidden"] > 0) & (f["hidden_run_s"] >= self.shape_min_s)
        ev[hid & (f["shape_p"] > self.shape_thr)] = H
        ev[hid & (f["shape_p"] < 1 - self.shape_thr)] = A
        return ev


@dataclass(frozen=True)
class RulesFix(RulesShape):
    """v2 review fixes (2026-11-15, Fadel's video review of v1), each off at 0.

    ctrl_rel_v   proximity is not control: a nearby player is control evidence only if the ball
                 moves with him (ball speed relative to the player below ctrl_rel_v m/s) or is
                 touched by him (the ball's velocity changes by at least ctrl_dv m/s within
                 +-0.24 s: a stop, a kick or a deflection). A fast pass running past an opponent
                 gives no evidence. ctrl_dv = 0 disables the touch clause.
    inside_m     no slowness-only stoppage while the ball is visible and more than inside_m metres
                 inside the field: there the slow-ball + slow-players rule needs a run of at least
                 calm_dead_s seconds plus a collective deceleration (mean player speed in the run
                 at least calm_decel m/s below the 4 s before it). Line crossings and long hidden
                 balls are unchanged.
    """
    ctrl_rel_v: float = 0.0
    ctrl_dv: float = 3.0
    inside_m: float = 0.0
    calm_dead_s: float = 6.0
    calm_decel: float = 0.5

    @property
    def name(self):
        return "fix_{}_{}_{}_{}_{}_".format(self.ctrl_rel_v, self.ctrl_dv, self.inside_m,
                                            self.calm_dead_s, self.calm_decel) + super().name

    def evidence(self, f):
        if self.ctrl_rel_v <= 0:
            return super().evidence(f)
        dH, dA = f["dH"], f["dA"]
        dHn, dAn = np.nan_to_num(dH, nan=np.inf), np.nan_to_num(dA, nan=np.inf)
        touch = self.ctrl_dv > 0 and np.nan_to_num(f["ball_dv"], nan=0.0) >= self.ctrl_dv
        withH = (np.nan_to_num(f["relH"], nan=np.inf) < self.ctrl_rel_v) | touch
        withA = (np.nan_to_num(f["relA"], nan=np.inf) < self.ctrl_rel_v) | touch
        ev = np.full(len(dH), -1, np.int8)
        ev[(dHn < self.ctrl_r) & (dHn + self.ctrl_margin < dAn) & withH] = H
        ev[(dAn < self.ctrl_r) & (dAn + self.ctrl_margin < dHn) & withA] = A
        if self.shape_w:  # keep the team-shape evidence inside long ball gaps
            hid = (f["hidden"] > 0) & (f["hidden_run_s"] >= self.shape_min_s)
            ev[hid & (f["shape_p"] > self.shape_thr)] = H
            ev[hid & (f["shape_p"] < 1 - self.shape_thr)] = A
        return ev

    def dead_mask(self, f):
        if self.inside_m <= 0:
            return super().dead_mask(f)
        fps = ft.FPS
        slow_p = np.nan_to_num(f["pspeed_4s"], nan=0) < self.slow_players
        out = np.nan_to_num(f["out_m"], nan=-99) > self.out_m
        slow_b = np.nan_to_num(f["bspeed_1s"], nan=99) < self.slow_ball
        long_hidden = f["hidden_run_s"] >= self.hidden_dead_s
        near_line = (f["hidden"] > 0) | (np.nan_to_num(f["out_m"], nan=-99) > -self.inside_m)
        calm = slow_b & slow_p & ~near_line  # slow, visible, well inside the field
        keep = np.zeros(len(calm), bool)
        p1 = f["pspeed_1s"]
        for a, b in _runs(calm):
            if b - a < self.calm_dead_s * fps:
                continue
            before = np.nanmean(p1[max(0, a - 4 * fps):a]) if a > 0 else np.nan
            during = np.nanmean(p1[a:b])
            if np.isfinite(before) and np.isfinite(during) and before - during >= self.calm_decel:
                keep[a:b] = True
        dead = out | (slow_b & slow_p & near_line) | keep | (long_hidden & slow_p)
        for a, b in _runs(~dead):
            if b - a < self.fill_alive_s * fps and a > 0 and b < len(dead):
                dead[a:b] = True
        for a, b in _runs(dead):
            if b - a < self.min_dead_s * fps:
                dead[a:b] = False
        return dead


@dataclass(frozen=True)
class RulesGap(Rules):
    """#4 with a turnover across a ball gap placed inside the gap: at last_cur + alpha * (gap),
    where the gap runs from the holder's last evidence frame to the new team's first. alpha=1 is
    Rules."""
    switch_alpha: float = 0.5

    @property
    def name(self):
        return "gap_" + super().name

    def _switch_at(self, last_cur, streak_start):
        if last_cur < 0:
            return streak_start
        return last_cur + 1 + int(self.switch_alpha * (streak_start - last_cur - 1))


@dataclass(frozen=True)
class RulesViterbi(Rules):
    """#4 with the greedy switch logic replaced by an optimal segmentation: minimise
    switch_cost per H<->A switch + 1 per evidence frame that disagrees with the label.
    Stoppages come from the same dead mask; a restart is free (any team may restart)."""
    switch_cost: float = 10.0

    @property
    def name(self):
        return "rulesvit_k{}_".format(self.switch_cost) + super().name

    def __call__(self, obs):
        from .hmm import viterbi
        f = ft.frame_features(obs, self.smooth_f)
        dead = self.dead_mask(f)
        ev = self.evidence(f)
        e = np.zeros((len(ev), 3))
        e[:, H] = ev == H
        e[:, A] = ev == A
        e[dead, :2] = -1e6
        e[~dead, D] = -1e6
        C = np.zeros((3, 3))
        C[H, A] = C[A, H] = self.switch_cost
        return viterbi(e, C)


def parse_kw(args):
    """['switch_cost=6', 'ctrl_r=1.2'] -> {'switch_cost': 6.0, 'ctrl_r': 1.2} (numbers only)."""
    out = {}
    for a in args:
        k, v = a.split("=")
        out[k.strip()] = int(v) if v.strip().isdigit() else float(v)
    return out


@dataclass(frozen=True)
class WithChannel:
    """Hypothesis (i) branch: if the tracking writes a categorical ball channel (an owner or
    alive flag), use it. Nobody says what the channel is: a column qualifies by its values alone
    (<= 3 distinct, changes at most once per 5 s on average, present on >= half the frames), and
    each value is mapped to H/A/D by where the base candidate's own labels fall on frames with
    that value. The channel then overrides the base wherever it maps. No qualifying column, or no
    clear mapping: the base output, unchanged."""
    base: object
    max_values: int = 3
    min_frames_per_change: int = 125
    min_coverage: float = 0.5
    min_share: float = 0.6

    @property
    def name(self):
        return "channel_" + self.base.name

    def column(self, x):
        ok = ~np.isnan(x)
        if ok.mean() < self.min_coverage:
            return None
        v = np.round(x[ok], 3)
        vals = np.unique(v)
        if not 2 <= len(vals) <= self.max_values:
            return None
        changes = np.count_nonzero(v[1:] != v[:-1])
        if changes and len(v) / changes < self.min_frames_per_change:
            return None
        return vals

    def mapping(self, x, vals, lab):
        m = {}
        for v in vals:
            sel = np.round(x, 3) == v
            share = np.bincount(lab[sel], minlength=3)[:3] / max(1, sel.sum())
            k = int(np.argmax(share))
            if share[k] >= self.min_share:
                m[float(v)] = k
        return m if len(set(m.values())) >= 2 else None

    def __call__(self, obs):
        lab = self.base(obs)
        X = getattr(obs, "ball_extra", None)
        if X is None:
            return lab
        for k in range(X.shape[1]):
            vals = self.column(X[:, k])
            m = None if vals is None else self.mapping(X[:, k], vals, lab)
            if m is None:
                continue
            out = lab.copy()
            xr = np.round(X[:, k], 3)
            for v, code in m.items():
                out[xr == v] = code
            return out
        return lab
