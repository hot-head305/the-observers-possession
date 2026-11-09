"""Does the official baseline behave on degraded IDSSE the way it does on the challenge match?

Target (published in EVALUATION.md, full match): spellF1 raw 0.0486, +-25 0.1996, +-50 0.2433,
+-125 0.2242; macroF1 0.6532 / 0.6752 / 0.6724 / 0.6356.

IDSSE positions are clean TRACAB. We degrade the ball only (the dominant noise source):
  ball hidden on ~41% of alive frames in bursty gaps, gap lengths lognormal (median g s),
  and hidden on all dead frames with prob p_dead_hidden (stoppage ball often off camera).
Then: nearest player to visible ball -> team, else D; centred majority vote; score vs IDSSE labels
with the official scorer. Only external data is read.

    uv run python -I scratch/external/idsse_baseline_transfer.py scratch/data/idsse
"""
import glob
import os
import sys
import xml.etree.ElementTree as ET

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "vendor", "official", "evaluation"))
sys.path.insert(0, os.path.join(ROOT, "vendor", "official", "starter"))
import possession_metrics as pm  # noqa: E402
from baseline import smooth  # noqa: E402  (official majority-vote smoother)

FPS = 25
TARGET = {0: 0.0486, 25: 0.1996, 50: 0.2433, 125: 0.2242}


def load_match(path, info_path):
    """Per section: frame ids, ball xy, label, and per-team player xy arrays [T, P, 2]."""
    teams = {}
    for t in ET.parse(info_path).getroot().iter("Team"):
        teams[t.get("TeamId")] = t.get("Role")  # home / guest
    sections = {}
    for ev, el in ET.iterparse(path, events=("end",)):
        if el.tag != "FrameSet":
            continue
        sec = el.get("GameSection")
        tid = el.get("TeamId")
        fr = el.findall("Frame")
        n = np.array([int(f.get("N")) for f in fr])
        xy = np.array([[float(f.get("X")), float(f.get("Y"))] for f in fr])
        s = sections.setdefault(sec, {"ball": None, "players": []})
        if "BALL" in (tid or "").upper():
            st = np.array([int(f.get("BallStatus")) for f in fr])
            po = np.array([int(f.get("BallPossession")) for f in fr])
            s["ball"] = (n, xy, np.where(st == 0, pm.D, np.where(po == 1, pm.H, pm.A)))
        elif teams.get(tid) in ("home", "guest"):
            s["players"].append((n, xy, pm.H if teams[tid] == "home" else pm.A))
        el.clear()
    out = []
    for sec, s in sections.items():
        n, bxy, lab = s["ball"]
        index = {f: i for i, f in enumerate(n)}
        T = len(n)
        P = len(s["players"])
        pxy = np.full((T, P, 2), np.nan)
        team = np.zeros(P, dtype=np.int8)
        for j, (pn, xy, t) in enumerate(s["players"]):
            team[j] = t
            idx = np.array([index.get(f, -1) for f in pn])
            ok = idx >= 0
            pxy[idx[ok], j] = xy[ok]
        out.append((bxy, lab, pxy, team))
    return out


def gap_mask(rng, lab, hide_total, gap_median_s, p_dead_hidden):
    """True where the ball is hidden; hide_total is the share of ALL graded frames (DATA.md: 41%).
    Stoppages are hidden whole with prob p_dead_hidden; alive play gets bursty gaps for the rest."""
    T = len(lab)
    if hide_total <= 0:
        return np.zeros(T, bool)
    dshare = np.mean(lab == pm.D)
    hide_alive = (hide_total - p_dead_hidden * dshare) / (1 - dshare)
    hide_alive = float(np.clip(hide_alive, 0.02, 0.95))
    hidden = np.zeros(T, bool)
    mu_h = np.log(gap_median_s * FPS)
    # visible-run mean chosen so the hidden fraction of alive frames ~= hide_alive
    mean_h = np.exp(mu_h + 0.5)
    mean_v = mean_h * (1 - hide_alive) / hide_alive
    t, vis = 0, True
    while t < T:
        L = int(max(1, rng.exponential(mean_v))) if vis else int(max(1, rng.lognormal(mu_h, 1.0)))
        if not vis:
            hidden[t:t + L] = True
        t += L
        vis = not vis
    dead = lab == pm.D
    for a, b in runs_bool(dead):
        if rng.random() < p_dead_hidden:
            hidden[a:b] = True
    return hidden


def runs_bool(m):
    e = np.diff(np.concatenate(([0], m.astype(int), [0])))
    return zip(np.flatnonzero(e == 1), np.flatnonzero(e == -1))


def drop_players(rng, pxy, off_share=0.07, off_mean_s=2.0):
    """Per-player on/off dropout: ~20.5 of 22 tracked on average (DATA.md)."""
    pxy = pxy.copy()
    T, P, _ = pxy.shape
    mean_off = off_mean_s * FPS
    mean_on = mean_off * (1 - off_share) / off_share
    for j in range(P):
        t, on = int(rng.integers(0, int(mean_on))), True
        while t < T:
            L = int(max(1, rng.exponential(mean_on if on else mean_off)))
            if not on:
                pxy[t:t + L, j] = np.nan
            t += L
            on = not on
    return pxy


def nearest_codes(bxy, pxy, team, hidden):
    d = np.nansum((pxy - bxy[:, None, :]) ** 2, axis=2)
    d[np.isnan(pxy[:, :, 0])] = np.inf
    j = np.argmin(d, axis=1)
    codes = team[j].astype(np.int8)
    codes[hidden] = -1
    return codes


def assemble(parts):
    """Concatenate sections with a 500-frame X gap so the scorer treats them as halves."""
    gt, codes = [], []
    for g, c in parts:
        gt += [g, np.full(500, pm.X, np.int8)]
        codes += [c, np.full(500, -1, np.int8)]
    return np.concatenate(gt).astype(np.int8), np.concatenate(codes)


def main():
    root = sys.argv[1]
    # (hide_total over graded frames, gap median s, p_dead_hidden, player dropout on)
    # Fixed a priori from DATA.md (41%, ~7% players missing); gap median and dead split unknown,
    # so a grid is reported, not fitted.
    regimes = [(0.0, 1.0, 0.0, False)] + [(0.41, g, p, True) for p in (0.3, 0.5, 0.7) for g in (0.5, 1.0, 2.0)]
    SEEDS = 3
    matches = []
    for path in sorted(glob.glob(os.path.join(root, "DFL_04_03_positions_raw_observed_*.xml"))):
        mid = path.rsplit("-", 1)[-1].split(".")[0]
        info = glob.glob(os.path.join(root, "DFL_02_01_matchinformation_*{}.xml".format(mid)))[0]
        matches.append((mid, load_match(path, info)))
        print("loaded", mid, flush=True)
    print("\npublished target spellF1:", TARGET)
    for hide, gmed, pdh, drop in regimes:
        res = {w: [] for w in TARGET}
        for mi, (mid, secs) in enumerate(matches):
          for seed in range(SEEDS):
            rng = np.random.default_rng(1000 * mi + seed)
            parts = []
            for bxy, lab, pxy, team in secs:
                hidden = gap_mask(rng, lab, hide, gmed, pdh)
                px = drop_players(rng, pxy) if drop else pxy
                parts.append((lab, nearest_codes(bxy, px, team, hidden)))
            gt, codes = assemble(parts)
            for w in TARGET:
                lab_s = smooth(codes, w)
                pred = pm.label_codes(lab_s)
                pred[gt == pm.X] = pm.X
                r = pm.evaluate(gt, pred)
                res[w].append((r["spell_f1_mean"], r["macro_f1"]))
        print("hide_total {:.2f} gap_median {:.1f}s p_dead_hidden {:.1f} players_drop {}: ".format(hide, gmed, pdh, drop) + "  ".join(
            "w{} spell {:.3f}+-{:.3f} macro {:.3f}".format(
                w, np.mean([v[0] for v in res[w]]), np.std([v[0] for v in res[w]]),
                np.mean([v[1] for v in res[w]])) for w in TARGET), flush=True)


if __name__ == "__main__":
    main()
