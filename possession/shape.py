"""Team-shape possession evidence for frames where the ball is not seen (PLAN.md §6b, C).

Ball-free features per frame, oriented by each team's attacking direction within a half:
forward position and forward velocity of each team's centroid, and the width and length of
each team. A logistic regression on IDSSE (bridged labels, alive frames) gives P(H has the ball).
Deterministic: IRLS with a fixed number of steps, no randomness.
"""
import numpy as np

from .features import FPS, PITCH, box_mean

H, A = 0, 1
N_FEAT = 10


def _team(slots, team, k):
    xy = np.where((team == k)[None, :, None], slots, np.nan)
    ok = ~np.isnan(xy[:, :, 0])
    n = np.maximum(ok.sum(1), 1)
    cx = np.where(ok, xy[:, :, 0], 0).sum(1) / n
    cy = np.where(ok, xy[:, :, 1], 0).sum(1) / n
    sx = np.sqrt(np.where(ok, (xy[:, :, 0] - cx[:, None]) ** 2, 0).sum(1) / n)
    sy = np.sqrt(np.where(ok, (xy[:, :, 1] - cy[:, None]) ** 2, 0).sum(1) / n)
    empty = ok.sum(1) == 0
    for a in (cx, sx, sy):
        a[empty] = np.nan
    return cx, sx, sy


def _vel(x, w):
    v = np.full(len(x), np.nan)
    v[w:-w] = (x[2 * w:] - x[:-2 * w]) * FPS / (2 * w)
    return v


def features(obs):
    slots = obs.slots * PITCH
    team = obs.slot_team
    cxH, sxH, syH = _team(slots, team, H)
    cxA, sxA, syA = _team(slots, team, A)
    d = 1.0 if np.nanmean(cxH) < np.nanmean(cxA) else -1.0  # H attacks +x when it defends low x
    mid = PITCH[0] / 2
    fxH, fxA = d * (cxH - mid), -d * (cxA - mid)
    cols = [fxH, fxA,
            d * _vel(box_mean(cxH, FPS), FPS), -d * _vel(box_mean(cxA, FPS), FPS),
            d * _vel(box_mean(cxH, FPS), 3 * FPS), -d * _vel(box_mean(cxA, FPS), 3 * FPS),
            box_mean(sxH - sxA, FPS), box_mean(syH - syA, FPS),
            box_mean(fxH + fxA, 2 * FPS), box_mean(syH, FPS) - box_mean(syA, FPS)]
    X = np.stack(cols, 1).astype(np.float64)
    return np.nan_to_num(X, nan=0.0)


def fit(X, y, l2=1.0, steps=25):
    mu, sd = X.mean(0), X.std(0) + 1e-9
    Z = np.hstack([np.ones((len(X), 1)), (X - mu) / sd])
    w = np.zeros(Z.shape[1])
    R = l2 * np.eye(Z.shape[1])
    R[0, 0] = 0
    for _ in range(steps):
        p = 1 / (1 + np.exp(-Z @ w))
        g = Z.T @ (p - y) + R @ w
        Hm = (Z * (p * (1 - p))[:, None]).T @ Z + R
        w -= np.linalg.solve(Hm, g)
    return tuple(np.round(np.concatenate([mu, sd, w]), 8))


def predict(params, X):
    p = np.asarray(params)
    mu, sd, w = p[:N_FEAT], p[N_FEAT:2 * N_FEAT], p[2 * N_FEAT:]
    z = w[0] + ((X - mu) / sd) @ w[1:]
    return 1 / (1 + np.exp(-z))
