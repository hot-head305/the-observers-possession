import numpy as np

from possession import candidates as cd, shape
from possession.degrade import Observed

H, A = 0, 1


def _obs(T=600, hide=slice(None)):
    rng = np.random.default_rng(0)
    t = np.arange(T)
    slots = np.zeros((T, 4, 2), np.float32)
    for j, (x0, k) in enumerate([(0.3, H), (0.35, H), (0.6, A), (0.65, A)]):
        slots[:, j, 0] = x0 + 0.05 * np.sin(t / 50 + j)
        slots[:, j, 1] = 0.3 + 0.1 * j + 0.01 * rng.standard_normal(T)
    ball = slots[:, 0].copy()
    ball[hide] = np.nan
    return Observed(ball, slots, np.array([H, H, A, A], np.int8))


def test_fit_predict_separable_and_deterministic():
    rng = np.random.default_rng(1)
    X = rng.standard_normal((400, shape.N_FEAT))
    y = (X[:, 0] > 0).astype(float)
    w1, w2 = shape.fit(X, y), shape.fit(X, y)
    assert w1 == w2
    p = shape.predict(w1, X)
    assert ((p > 0.5) == (y == 1)).mean() > 0.95


def test_features_finite():
    X = shape.features(_obs())
    assert X.shape == (600, shape.N_FEAT) and np.isfinite(X).all()


def test_shipped_weights_load():
    assert len(shape.shipped()) == 3 * shape.N_FEAT + 1


def test_shape_is_rules_when_ball_visible():
    obs = _obs()
    w = shape.shipped()
    assert (cd.RulesShape(shape_w=w)(obs) == cd.Rules()(obs)).all()


def test_rules_gap_alpha_one_is_rules():
    obs = _obs(hide=slice(200, 400))
    assert (cd.RulesGap(switch_alpha=1.0)(obs) == cd.Rules()(obs)).all()
