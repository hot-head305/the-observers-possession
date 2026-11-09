"""Degrade clean IDSSE tracking to look like the provided automatic tracking (PLAN.md §2b).

Targets are published in DATA.md: ball missing on 41 % of graded frames, ~20.5 of 22 players
tracked, anonymous fragmenting slots, occasional duplicates. Unknowns (gap length, how often a
stoppage is fully unseen) are a grid, never fitted to anything derived from the match labels.

    obs = degrade(section, Params(), rng)
    obs.ball      (T, 2) normalised, NaN where hidden
    obs.slots     (T, S, 2) normalised, NaN where the slot is empty
    obs.slot_team (S,) H/A
"""
import itertools
from dataclasses import dataclass, replace

import numpy as np

H, A, D = 0, 1, 2
FPS = 25


@dataclass(frozen=True)
class Params:
    hide_total: float = 0.41      # share of all frames without a ball (DATA.md)
    gap_median_s: float = 1.0     # unknown -> grid
    p_dead_hidden: float = 0.5    # unknown -> grid
    air_z_m: float = 2.5          # ball above this is hidden with p_air (aerial balls get lost)
    p_air: float = 0.6
    player_off_share: float = 0.07  # 22 -> ~20.5 tracked
    player_off_mean_s: float = 2.0
    p_cross_team: float = 0.01    # a fragment attached to a slot of the other team
    dup_rate_per_min: float = 0.5
    dup_mean_s: float = 1.0
    pos_noise: float = 0.3        # metres
    ball_noise: float = 0.6


GRID = [Params(gap_median_s=g, p_dead_hidden=p)
        for p, g in itertools.product((0.3, 0.5, 0.7), (0.5, 1.0, 2.0))]


@dataclass
class Observed:
    ball: np.ndarray
    slots: np.ndarray
    slot_team: np.ndarray


def _runs(mask):
    e = np.diff(np.concatenate(([0], mask.astype(np.int8), [0])))
    return list(zip(np.flatnonzero(e == 1), np.flatnonzero(e == -1)))


def ball_hidden(rng, label, z, p):
    T = len(label)
    hidden = np.zeros(T, bool)
    if p.hide_total <= 0:
        return hidden
    for a, b in _runs(label == D):
        if rng.random() < p.p_dead_hidden:
            hidden[a:b] = True
    for a, b in _runs((z > p.air_z_m) & (label != D)):
        if rng.random() < p.p_air:
            hidden[a:b] = True
    alive = label != D
    need = p.hide_total * T - hidden.sum()
    free = alive & ~hidden
    if need <= 0 or not free.any():
        return hidden
    frac = min(0.95, need / free.sum())
    mu = np.log(p.gap_median_s * FPS)
    mean_h = np.exp(mu + 0.5)
    mean_v = mean_h * (1 - frac) / frac
    t, vis = int(rng.integers(0, max(1, int(mean_v)))), True
    while t < T:
        L = int(max(1, rng.exponential(mean_v) if vis else rng.lognormal(mu, 1.0)))
        if not vis:
            hidden[t:t + L] |= free[t:t + L]
        t += L
        vis = not vis
    return hidden


def _on_runs(rng, T, p):
    mean_off = p.player_off_mean_s * FPS
    mean_on = mean_off * (1 - p.player_off_share) / p.player_off_share
    out, t, on = [], 0, True
    while t < T:
        L = int(max(1, rng.exponential(mean_on if on else mean_off)))
        if on:
            out.append((t, min(T, t + L)))
        t += L
        on = not on
    return out


def degrade(sec, p, rng):
    T, P, _ = sec.players.shape
    scale = np.array([105.0, 68.0], dtype=np.float32)
    # Fragments: (start, stop, player, team-as-tracked)
    frags = []
    for j in range(P):
        present = ~np.isnan(sec.players[:, j, 0])
        for a, b in _runs(present):
            for s, e in _on_runs(rng, b - a, p):
                team = int(sec.team[j])
                if rng.random() < p.p_cross_team:
                    team = 1 - team
                frags.append((a + s, a + e, j, team))
    n_dup = rng.poisson(p.dup_rate_per_min * T / (60 * FPS))
    for _ in range(n_dup):
        j, s = int(rng.integers(0, P)), int(rng.integers(0, T))
        e = min(T, s + int(max(1, rng.exponential(p.dup_mean_s * FPS))))
        if not np.isnan(sec.players[s, j, 0]):
            frags.append((s, e, -1 - j, int(sec.team[j])))
    frags.sort()
    free_at = {H: [], A: []}
    slot_team, assigned = [], []
    for s, e, j, team in frags:
        pool = free_at[team]
        k = next((i for i, (slot, t_free) in enumerate(pool) if t_free <= s), None)
        if k is None:
            slot = len(slot_team)
            slot_team.append(team)
            pool.append([slot, e])
        else:
            slot = pool[k][0]
            pool[k][1] = e
        assigned.append((s, e, j, slot))
    slots = np.full((T, len(slot_team), 2), np.nan, dtype=np.float32)
    for s, e, j, slot in assigned:
        src = sec.players[s:e, abs(j) - 1 if j < 0 else j]
        off = rng.normal(0, 0.7, 2) / scale if j < 0 else 0
        slots[s:e, slot] = src + off + rng.normal(0, p.pos_noise, (e - s, 2)) / scale
    hidden = ball_hidden(rng, sec.label, sec.ball[:, 2], p)
    ball = sec.ball[:, :2] + rng.normal(0, p.ball_noise, (T, 2)).astype(np.float32) / scale
    ball[hidden] = np.nan
    return Observed(ball, slots, np.array(slot_team, dtype=np.int8))


def with_profile(p, profile):
    """Override grid unknowns from a human-generated profile dict (private-degrade-profile)."""
    keys = {k: v for k, v in profile.items() if k in Params.__dataclass_fields__}
    return replace(p, **keys)
