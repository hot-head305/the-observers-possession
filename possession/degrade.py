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
    dead_ball_motion: bool = True  # IDSSE freezes the ball on every dead frame; real tracking doesn't
    roll_out_s: float = 1.0
    placed_s: float = 2.0


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


def dead_ball_path(sec, p):
    """Replace IDSSE's frozen dead-ball position with a plausible stoppage trajectory.

    The frozen position is taken as the restart spot. Per dead run: the ball first rolls on with
    the last alive velocity, decaying over roll_out_s; then it follows the player who ends the run
    nearest the spot (the restart taker, 0.5 m ahead of him); for the last placed_s it lies still
    on the spot. Deterministic: no rng, so a cell's realism doesn't vary by seed.
    """
    ball = sec.ball[:, :2].astype(np.float32).copy()
    scale = np.array([105.0, 68.0], dtype=np.float32)
    T = len(ball)
    for a, b in _runs(sec.label == D):
        spot = ball[b - 1].copy()
        L = b - a
        n_roll = min(L, int(p.roll_out_s * FPS))
        vel = ball[a - 1] - ball[a - 2] if a >= 2 else np.zeros(2, np.float32)
        decay = np.exp(-np.arange(1, n_roll + 1) / (0.4 * FPS))[:, None]
        roll = ball[a - 1] + np.cumsum(vel * decay, axis=0) if a >= 1 else np.repeat(spot[None], n_roll, 0)
        ball[a:a + n_roll] = roll
        n_place = min(L - n_roll, int(p.placed_s * FPS))
        carry = slice(a + n_roll, b - n_place)
        if carry.stop > carry.start:
            pl = sec.players[b - 1]
            ok = ~np.isnan(pl[:, 0])
            if ok.any():
                j = int(np.flatnonzero(ok)[np.argmin(np.linalg.norm((pl[ok] - spot) * scale, axis=1))])
                track = sec.players[carry, j]
                fill = np.isnan(track[:, 0])
                track = np.where(fill[:, None], spot, track)
                ahead = (spot - track) * scale
                n = np.linalg.norm(ahead, axis=1, keepdims=True)
                ball[carry] = track + np.where(n > 0.5, 0.5 * ahead / np.maximum(n, 1e-6), ahead) / scale
            else:
                ball[carry] = spot
        ball[b - n_place:b] = spot
    return ball[:T]


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
    base = dead_ball_path(sec, p) if p.dead_ball_motion else sec.ball[:, :2]
    ball = base + rng.normal(0, p.ball_noise, (T, 2)).astype(np.float32) / scale
    ball[hidden] = np.nan
    return Observed(ball, slots, np.array(slot_team, dtype=np.int8))


def with_profile(p, profile):
    """Override grid unknowns from a human-generated profile dict (private-degrade-profile)."""
    keys = {k: v for k, v in profile.items() if k in Params.__dataclass_fields__}
    return replace(p, **keys)
