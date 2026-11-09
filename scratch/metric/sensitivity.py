"""Synthetic spellF1 sensitivity study with the official scorer.

Synthetic GT only (no competition data). A GT is a sequence of possessions (H/A) and
stoppages (D) laid over two halves with the published graded-frame layout. Each experiment
applies one error type to a perfect prediction and scores it with possession_metrics.evaluate.

    uv run python -I scratch/metric/sensitivity.py > scratch/out/sensitivity.txt
"""
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "vendor", "official", "evaluation"))
import possession_metrics as pm  # noqa: E402

N = 199319
HALVES = ((11185, 90652), (110808, 190198))
H2_PREKICK = 2934
FPS = 25
SEEDS = range(8)

# Generator regimes: (mean possession s, lognormal sigma, P(stoppage after a possession),
# mean stoppage s). "base" is tuned so the public-window stats (mean poss ~14 s) and a plausible
# full-match dead share (~35-40%) both hold; "short" is a choppier match.
REGIMES = {
    "base": dict(mu_s=14.0, sigma=1.0, p_dead=0.40, dead_s=22.0),
    "short": dict(mu_s=8.0, sigma=1.1, p_dead=0.30, dead_s=18.0),
    # Heavy-tailed regime that reproduces the published lag table (calibrate_lag.py); used only to
    # understand the scorer, never to fit a model.
    "heavy": dict(mu_s=11.0, sigma=1.2, p_dead=0.35, dead_s=20.0),
}


def lognormal_frames(rng, mean_s, sigma, size=None):
    mu = np.log(mean_s * FPS) - sigma ** 2 / 2
    return np.maximum(1, np.round(rng.lognormal(mu, sigma, size))).astype(int)


def make_gt(rng, mu_s, sigma, p_dead, dead_s):
    gt = np.full(N, pm.X, dtype=np.int8)
    for h, (a, b) in enumerate(HALVES):
        pos = a
        if h == 1:
            gt[a:a + H2_PREKICK] = pm.D
            pos += H2_PREKICK
        team = rng.integers(0, 2)
        while pos < b:
            L = int(lognormal_frames(rng, mu_s, sigma))
            gt[pos:min(b, pos + L)] = team
            pos += L
            if pos >= b:
                break
            if rng.random() < p_dead:
                Ld = int(lognormal_frames(rng, dead_s, 0.7))
                gt[pos:min(b, pos + Ld)] = pm.D
                pos += Ld
                team = rng.integers(0, 2)
            else:
                team = 1 - team
    return gt


def runs_of(codes):
    return pm.valid_runs(codes)


def score(gt, pred):
    r = pm.evaluate(gt, pred)
    return r["spell_f1_mean"], r["macro_f1"], r["n_pred_spells"], r["n_gt_spells"]


# -- perturbations: each takes (gt, rng, param) and returns a prediction ------------------------

def boundary_lag(gt, rng, k):
    """Every label change happens k frames late (uniform lag)."""
    pred = gt.copy()
    for start, stop in runs_of(gt):
        w = gt[start:stop]
        shifted = np.concatenate((np.full(k, w[0]), w[:-k])) if k else w
        pred[start:stop] = shifted
    return pred


def boundary_jitter(gt, rng, k):
    """Each boundary moved independently by U[-k, k] frames."""
    pred = gt.copy()
    for (f, a, b) in pm.transitions(gt, runs_of(gt)):
        d = int(rng.integers(-k, k + 1))
        if d > 0:
            pred[f:f + d] = a
        elif d < 0:
            pred[f + d:f] = b
    return pred


def flicker(gt, rng, rate_per_min, length=5):
    """Opposite-team runs of `length` frames inserted inside possessions, Poisson rate/min alive."""
    pred = gt.copy()
    alive = np.flatnonzero((gt == pm.H) | (gt == pm.A))
    n = rng.poisson(rate_per_min * len(alive) / (60 * FPS))
    for f in rng.choice(alive, size=n, replace=False):
        seg = slice(f, f + length)
        if np.all(gt[seg] == gt[f]):
            pred[seg] = 1 - gt[f]
    return pred


def spurious_d(gt, rng, rate_per_min, length=25):
    """D runs inserted inside possessions."""
    pred = gt.copy()
    alive = np.flatnonzero((gt == pm.H) | (gt == pm.A))
    n = rng.poisson(rate_per_min * len(alive) / (60 * FPS))
    for f in rng.choice(alive, size=n, replace=False):
        seg = slice(f, f + length)
        if np.all(gt[seg] == gt[f]):
            pred[seg] = pm.D
    return pred


def missed_d(gt, rng, frac):
    """A fraction of stoppages not detected: the D run is filled with the preceding label."""
    pred = gt.copy()
    for (a, b, k) in pm.segments(gt, runs_of(gt)):
        if k == pm.D and a > 0 and gt[a - 1] in (pm.H, pm.A) and rng.random() < frac:
            pred[a:b] = gt[a - 1]
    return pred


def missed_d_xfill(gt, rng, frac):
    """Same as missed_d but the system writes X over the missed stoppage (scorer forward-fills)."""
    pred = gt.copy()
    for (a, b, k) in pm.segments(gt, runs_of(gt)):
        if k == pm.D and a > 0 and gt[a - 1] in (pm.H, pm.A) and rng.random() < frac:
            pred[a:b] = pm.X
    return pred


def d_shrink(gt, rng, frames):
    """Every stoppage detected but `frames` too short at each end (ball declared alive early)."""
    pred = gt.copy()
    for (a, b, k) in pm.segments(gt, runs_of(gt)):
        if k == pm.D and b - a > 2 * frames and a > 0:
            prev = gt[a - 1] if gt[a - 1] in (pm.H, pm.A) else None
            nxt = gt[b] if b < N and gt[b] in (pm.H, pm.A) else None
            if prev is not None:
                pred[a:a + frames] = prev
            if nxt is not None:
                pred[b - frames:b] = nxt
    return pred


def missed_switch(gt, rng, frac):
    """A fraction of direct H<->A changes missed: the new possession keeps the old team."""
    pred = gt.copy()
    segs = pm.segments(gt, runs_of(gt))
    for i in range(1, len(segs)):
        a, b, k = segs[i]
        pa, pb, pk = segs[i - 1]
        if k in (pm.H, pm.A) and pk in (pm.H, pm.A) and pk != k and pb == a and rng.random() < frac:
            pred[a:b] = pk
    return pred


def wrong_team(gt, rng, frac):
    """A fraction of whole possessions given to the wrong team."""
    pred = gt.copy()
    for (a, b, k) in pm.possession_spells(gt, runs_of(gt)):
        if rng.random() < frac:
            pred[a:b] = 1 - k
    return pred


def drop_short(gt, rng, max_s):
    """Under-segmentation: possessions shorter than max_s seconds are absorbed by the previous label."""
    pred = gt.copy()
    for (a, b, k) in pm.possession_spells(gt, runs_of(gt)):
        if b - a < max_s * FPS and a > 0 and pred[a - 1] != pm.X:
            pred[a:b] = pred[a - 1]
    return pred


def x_at_transitions(gt, rng, w):
    """X written over +/-w frames around every transition (abstain at hand-overs)."""
    pred = gt.copy()
    for (f, a, b) in pm.transitions(gt, runs_of(gt)):
        pred[max(0, f - w):f + w] = pm.X
    return pred


def x_inside(gt, rng, frac):
    """X on a random fraction of interior possession frames, in 2 s blocks (occlusion)."""
    pred = gt.copy()
    alive = np.flatnonzero((gt == pm.H) | (gt == pm.A))
    n = int(frac * len(alive) / 50)
    for f in rng.choice(alive, size=n, replace=False):
        seg = slice(f, f + 50)
        if np.all(gt[seg] == gt[f]):
            pred[seg] = pm.X
    return pred


EXPERIMENTS = [
    ("perfect", lambda g, r, p: g.copy(), [0]),
    ("boundary_lag_frames", boundary_lag, [1, 3, 8, 25, 50]),
    ("boundary_jitter_U(+-k)", boundary_jitter, [1, 3, 8, 25, 50]),
    ("flicker5f_per_min", flicker, [0.5, 1, 2, 5, 10]),
    ("flicker1f_per_min", lambda g, r, p: flicker(g, r, p, 1), [1, 5, 10]),
    ("flicker25f_per_min", lambda g, r, p: flicker(g, r, p, 25), [0.5, 1, 2, 5]),
    ("spuriousD25f_per_min", spurious_d, [0.5, 1, 2, 5]),
    ("spuriousD3f_per_min", lambda g, r, p: spurious_d(g, r, p, 3), [1, 5, 10]),
    ("missed_D_frac", missed_d, [0.1, 0.25, 0.5, 1.0]),
    ("missed_D_as_X_frac", missed_d_xfill, [0.25, 1.0]),
    ("D_shrunk_each_end_frames", d_shrink, [5, 12, 25, 50]),
    ("missed_switch_frac", missed_switch, [0.1, 0.25, 0.5]),
    ("wrong_team_frac", wrong_team, [0.05, 0.1, 0.25]),
    ("drop_poss_shorter_than_s", drop_short, [1, 2, 3, 5]),
    ("X_at_transitions_w", x_at_transitions, [3, 12, 25]),
    ("X_inside_poss_frac", x_inside, [0.1, 0.3]),
]


def main():
    for regime, params in REGIMES.items():
        gts = [make_gt(np.random.default_rng(1000 + s), **params) for s in SEEDS]
        g0 = gts[0]
        graded = g0 != pm.X
        st = pm.possession_stats(g0, runs_of(g0))
        print("## regime {} {}".format(regime, params))
        print("   gt: {} spells, mean {:.1f} s, D share {:.1%}, spells/min alive {:.2f}".format(
            st["n_spells"], st["mean_duration_s"], np.mean(g0[graded] == pm.D),
            st["n_spells"] / (np.sum((g0 == pm.H) | (g0 == pm.A)) / (60 * FPS))))
        print("{:<28} {:>7} {:>8} {:>8} {:>7} {:>7}".format(
            "experiment", "param", "spellF1", "sd", "macroF1", "poss"))
        for name, fn, ps in EXPERIMENTS:
            for p in ps:
                vals = []
                for s, gt in enumerate(gts):
                    pred = fn(gt, np.random.default_rng(s), p)
                    vals.append(score(gt, pred))
                v = np.array(vals, dtype=float)
                print("{:<28} {:>7} {:>8.4f} {:>8.4f} {:>7.4f} {:>7.0f}".format(
                    name, p, v[:, 0].mean(), v[:, 0].std(), v[:, 1].mean(), v[:, 2].mean()))
        print()


if __name__ == "__main__":
    main()
