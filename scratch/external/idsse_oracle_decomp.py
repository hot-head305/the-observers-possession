"""Hypothesis (ii): is the baseline's spellF1 loss driven by team flicker or by dead-ball errors?

On degraded IDSSE (regime that reproduced the published baseline curve), swap in an oracle for one
factor at a time:
  oracle_dead : alive/dead taken from GT; team from the baseline (baseline-D on GT-alive -> X).
  oracle_team : alive/dead from the baseline; team from GT wherever both say alive.
  oracle_team_smooth : as oracle_team, but GT team only revealed through the baseline's own
                       spell structure is NOT used -- i.e. pure team relabel of each predicted spell
                       by GT majority (keeps baseline boundaries).
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import idsse_baseline_transfer as T  # noqa: E402

pm = T.pm


def spell_majority(pred, gt):
    out = pred.copy()
    for a, b, k in pm.possession_spells(pred, pm.valid_runs(gt)):
        g = gt[a:b]
        h, w = np.sum(g == pm.H), np.sum(g == pm.A)
        if h + w:
            out[a:b] = pm.H if h >= w else pm.A
    return out


def main():
    import glob
    root = sys.argv[1]
    rows = {}
    for mi, path in enumerate(sorted(glob.glob(os.path.join(root, "DFL_04_03_positions_raw_observed_*.xml")))):
        mid = path.rsplit("-", 1)[-1].split(".")[0]
        info = glob.glob(os.path.join(root, "DFL_02_01_matchinformation_*{}.xml".format(mid)))[0]
        secs = T.load_match(path, info)
        rng = np.random.default_rng(mi)
        parts = [(lab, T.nearest_codes(bxy, pxy, team, T.gap_mask(rng, lab, 0.41, 1.0, 0.8)))
                 for bxy, lab, pxy, team in secs]
        gt, codes = T.assemble(parts)
        for w in (0, 25, 50, 125):
            pred = pm.label_codes(T.smooth(codes, w))
            pred[gt == pm.X] = pm.X
            alive_gt = np.isin(gt, (pm.H, pm.A))
            alive_pr = np.isin(pred, (pm.H, pm.A))
            od = pred.copy()
            od[~alive_gt & (gt != pm.X)] = pm.D
            od[alive_gt & ~alive_pr] = pm.X
            ot = pred.copy()
            both = alive_gt & alive_pr
            ot[both] = gt[both]
            om = spell_majority(pred, gt)
            for name, p in (("baseline", pred), ("oracle_dead", od), ("oracle_team_frame", ot),
                            ("oracle_team_spell", om)):
                r = pm.evaluate(gt, p)
                rows.setdefault((w, name), []).append((r["spell_f1_mean"], r["n_pred_spells"], r["n_gt_spells"]))
        print("done", mid, flush=True)
    for (w, name), v in sorted(rows.items()):
        v = np.array(v, float)
        print("w{:<4} {:<18} spellF1 {:.3f}  pred/gt spells {:.0f}/{:.0f}".format(
            w, name, v[:, 0].mean(), v[:, 1].mean(), v[:, 2].mean()))


if __name__ == "__main__":
    main()
