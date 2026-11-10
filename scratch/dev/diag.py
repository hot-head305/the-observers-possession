"""Dev diagnostics: alive/dead F1, team accuracy, spells for Rules vs HMM (J03WPY, cell 4, seed 0)."""
import os, pickle, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from possession import candidates as cd, degrade as dg, harness as hs, hmm  # noqa: E402
pm = hs.pm
base = pickle.load(open(os.path.join(hs.ROOT, "scratch", "data", "hmm_dev_fit.pkl"), "rb"))
mid = "J03WPY"
secs, gts = hs.truths(mid)
gt = hs._assemble([g[1] for g in gts])
for name, c in [("rules", cd.Rules()), ("hmm", hmm.with_params(base, switch=4, w=0.1)),
                ("hmm+rulesD", None)]:
    preds = []
    for si, s in enumerate(secs):
        obs = dg.degrade(s, dg.GRID[4], hs._rng(mid, 4, 0, si))
        if c is None:
            m = hmm.with_params(base, switch=4, w=0.1)
            p = m(obs)
            dead = cd.Rules().dead_mask(cd.ft.frame_features(obs))
            p[dead] = 2
            p[(~dead) & (p == 2)] = 0  # placeholder, refined below
            p = c_fix = p
        else:
            p = c(obs)
        preds.append(p)
    pred = hs._assemble(preds); pred[gt == pm.X] = pm.X
    r = pm.evaluate(gt, pred)
    print(name, {k: round(r[k], 3) for k in ("spell_f1_mean", "macro_f1", "alive_dead_f1", "team_acc_gt_alive", "n_pred_spells", "n_gt_spells")})
