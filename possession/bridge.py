"""Label bridge: DFL possession -> the challenge's 'controlled possession' (CHALLENGE.md).

A spell of team T shorter than c frames, with no completed pass by T inside it, is a touch or
deflection without control and is absorbed into the previous team. A spell that follows D is a
restart and is never absorbed ("whenever play restarts ... there is a clear possessor").
c comes from the definition's "a few seconds"; promotion must hold for every c in C_GRID.
"""
import numpy as np

H, A, D = 0, 1, 2
C_GRID = (12, 25, 50)  # 0.5 s, 1 s, 2 s at 25 fps


def runs(lab):
    br = np.flatnonzero(lab[1:] != lab[:-1]) + 1
    b = np.concatenate(([0], br, [len(lab)]))
    return [(int(b[i]), int(b[i + 1]), int(lab[b[i]])) for i in range(len(b) - 1)]


def bridge(lab, pass_frames, c):
    """lab: (T,) H/A/D. pass_frames: {team: sorted array of frames with a completed pass}."""
    out = lab.copy()
    changed = True
    while changed:
        changed = False
        for a, b, k in runs(out):
            if k not in (H, A) or b - a >= c or a == 0 or out[a - 1] not in (H, A) or out[a - 1] == k:
                continue
            pf = pass_frames.get(k, np.empty(0, int))
            if np.any((pf >= a) & (pf < b)):
                continue
            out[a:b] = out[a - 1]
            changed = True
    return out


def pass_index(passes, section):
    by = {}
    for si, f, team in passes:
        if si == section and team in (H, A):
            by.setdefault(team, []).append(f)
    return {k: np.array(sorted(v)) for k, v in by.items()}
