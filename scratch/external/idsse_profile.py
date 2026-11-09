"""Profile IDSSE (DFL, TRACAB, 25 fps, CC-BY 4.0) ball channels as H/A/D labels.

Builds labels the way the challenge GT is built: D where BallStatus == 0, else the team in
BallPossession (1 = home, 2 = away). Reports the stats a synthetic GT and a prior need, and
writes per-match label arrays to scratch/out/idsse_labels/ for later use.

    uv run python -I scratch/external/idsse_profile.py scratch/data/idsse
"""
import glob
import os
import sys
import xml.etree.ElementTree as ET

import numpy as np

FPS = 25
H, A, D = 0, 1, 2


def ball_labels(path):
    """{section: (frame_numbers, labels, ball_status_raw, possession_raw)} from the ball FrameSet."""
    out = {}
    ctx = ET.iterparse(path, events=("start", "end"))
    in_ball, section, rows = False, None, []
    for ev, el in ctx:
        if ev == "start" and el.tag == "FrameSet":
            in_ball = el.get("TeamId", "").upper() in ("BALL", "SPORTEC") or "BALL" in el.get("TeamId", "").upper()
            section = el.get("GameSection")
            rows = []
        elif ev == "end" and el.tag == "Frame":
            if in_ball:
                rows.append((int(el.get("N")), el.get("BallStatus"), el.get("BallPossession")))
            el.clear()
        elif ev == "end" and el.tag == "FrameSet":
            if in_ball and rows:
                n = np.array([r[0] for r in rows])
                st = np.array([int(r[1]) if r[1] is not None else -1 for r in rows])
                po = np.array([int(r[2]) if r[2] is not None else -1 for r in rows])
                lab = np.where(st == 0, D, np.where(po == 1, H, np.where(po == 2, A, -1)))
                out[section] = (n, lab, st, po)
            el.clear()
            in_ball = False
    return out


def runs(lab):
    br = np.flatnonzero(lab[1:] != lab[:-1]) + 1
    b = np.concatenate(([0], br, [len(lab)]))
    return [(b[i], b[i + 1], lab[b[i]]) for i in range(len(b) - 1)]


def main():
    root = sys.argv[1]
    outdir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "out", "idsse_labels")
    os.makedirs(outdir, exist_ok=True)
    allp, alld, tot = [], [], {"frames": 0, "D": 0, "alive_min": 0.0, "spells": 0, "ha": 0, "hd": 0,
                               "dead_owner_kept": 0, "gaps": 0, "unk": 0}
    for path in sorted(glob.glob(os.path.join(root, "DFL_04_03_positions_raw_observed_*.xml"))):
        mid = path.rsplit("-", 1)[-1].split(".")[0]
        secs = ball_labels(path)
        line = [mid]
        for sec, (n, lab, st, po) in secs.items():
            gaps = int(np.sum(np.diff(n) != 1))
            tot["gaps"] += gaps
            tot["unk"] += int(np.sum(lab < 0))
            np.save(os.path.join(outdir, "{}_{}.npy".format(mid, sec)), lab.astype(np.int8))
            rs = runs(lab)
            p = [b - a for a, b, k in rs if k in (H, A)]
            d = [b - a for a, b, k in rs if k == D]
            allp += p
            alld += d
            tot["frames"] += len(lab)
            tot["D"] += int(np.sum(lab == D))
            tot["alive_min"] += np.sum(np.isin(lab, (H, A))) / (60 * FPS)
            tot["spells"] += len(p)
            for (a1, b1, k1), (a2, b2, k2) in zip(rs[:-1], rs[1:]):
                if k1 in (H, A) and k2 in (H, A):
                    tot["ha"] += 1
                elif k1 in (H, A) and k2 == D:
                    tot["hd"] += 1
            # Does BallPossession keep naming a team while dead? (the GT throws that away)
            tot["dead_owner_kept"] += int(np.sum((st == 0) & np.isin(po, (1, 2))))
            line.append("{} {} frames D {:.1%} spells {}".format(
                sec, len(lab), np.mean(lab == D), len(p)))
        print("  ".join(line))
    p = np.array(allp) / FPS
    d = np.array(alld) / FPS
    print("\nTOTAL frames {} D share {:.1%}  frame gaps {}  unknown-label frames {}".format(
        tot["frames"], tot["D"] / tot["frames"], tot["gaps"], tot["unk"]))
    print("possessions {} over 7 matches = {:.0f}/match; {:.2f} per alive minute".format(
        len(p), len(p) / 7, len(p) / tot["alive_min"]))
    print("possession s: mean {:.1f} median {:.1f} p10 {:.1f} p90 {:.1f} max {:.0f}; <1s {:.1%} <2s {:.1%} <0.2s {:.1%}".format(
        p.mean(), np.median(p), *np.percentile(p, [10, 90]), p.max(), np.mean(p < 1), np.mean(p < 2), np.mean(p < 0.2)))
    print("lognormal fit: mean {:.1f}s sigma {:.2f}".format(np.exp(np.mean(np.log(p)) + np.var(np.log(p)) / 2),
                                                         np.std(np.log(p))))
    print("stoppage s: n {} mean {:.1f} median {:.1f} p10 {:.1f} p90 {:.1f}".format(
        len(d), d.mean(), np.median(d), *np.percentile(d, [10, 90])))
    print("possession ends: direct H<->A {} ({:.0%}), into D {}".format(
        tot["ha"], tot["ha"] / (tot["ha"] + tot["hd"]), tot["hd"]))
    print("dead frames that still name a team in BallPossession: {:.1%}".format(
        tot["dead_owner_kept"] / max(1, tot["D"])))
    np.save(os.path.join(outdir, "_possession_lengths_frames.npy"), np.array(allp))
    np.save(os.path.join(outdir, "_stoppage_lengths_frames.npy"), np.array(alld))


if __name__ == "__main__":
    main()
