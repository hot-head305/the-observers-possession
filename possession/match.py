"""The provided match: FIFA/EPTS ATD -> Observed per half -> one label per video frame.

No path is hard-coded; callers pass the ATD files. Frame layout comes from the official games.py
(half blocks, per-half offsets) and the published second-half kickoff; nothing else about the
match is a constant here.
"""
import os
import sys
import xml.etree.ElementTree as ET

import numpy as np

from .degrade import Observed
from .idsse import ROOT

OFFICIAL = os.path.join(ROOT, "vendor", "official")
sys.path.insert(0, OFFICIAL)
import games  # noqa: E402

H, A, D, X = 0, 1, 2, 3
LETTERS = np.array(["H", "A", "D", "X"])
KICKOFF_2ND = 113742  # published (DATA.md / FAQ.md): graded D from the 2nd-half block start to here


def slot_teams(meta_path):
    """Same convention as the official baseline: first Team in the metadata is home."""
    root = ET.parse(meta_path).getroot()
    ids = [t.get("id") for t in root.iter("Team")]
    if len(ids) != 2:
        raise ValueError("expected 2 teams, found {}".format(len(ids)))
    return np.array([H if p.get("teamId") == ids[0] else A for p in root.iter("Player")], np.int8)


def _xy(group):
    if not group or group[0] == "N":
        return np.nan, np.nan
    a, b = group.split(",")[:2]
    return float(a), float(b)


def read_atd(raw_path, n_slots, n_frames):
    """ball (N, 2) and slots (N, S, 2), normalised 0-1 as in the file, NaN where missing.
    Row i is video frame i (ATD frame ids count from 1, as in the official baseline)."""
    ball = np.full((n_frames, 2), np.nan, np.float32)
    slots = np.full((n_frames, n_slots, 2), np.nan, np.float32)
    with open(raw_path) as fh:
        for line in fh:
            parts = line.rstrip("\n").split(":")
            if len(parts) != 3:
                continue
            i = int(parts[0]) - 1
            if not 0 <= i < n_frames:
                continue
            ball[i] = _xy(parts[2])
            for j, g in enumerate(parts[1].split(";")[:n_slots]):
                slots[i, j] = _xy(g)
    return ball, slots


def load(meta_path, raw_path, n_frames):
    team = slot_teams(meta_path)
    ball, slots = read_atd(raw_path, len(team), n_frames)
    return ball, slots, team


def predict(cand, ball, slots, team, game=games.GAME, kickoff_2nd=KICKOFF_2ND):
    """Codes for every video frame: X outside the half blocks, the candidate inside each half,
    D on the graded pre-kickoff stretch of the second half."""
    out = np.full(len(ball), X, np.int8)
    for half, first, last in games.half_video_blocks(game):
        a, b = max(0, first), min(len(ball), last + 1)
        if b <= a:
            continue
        if half == 2 and a < kickoff_2nd <= b:
            out[a:kickoff_2nd] = D
            a = kickoff_2nd
        out[a:b] = cand(Observed(ball[a:b], slots[a:b], team))
    return out


def write_csv(path, codes):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    lab = LETTERS[codes]
    with open(path, "w", newline="\n") as fh:
        fh.write("frame,label\n")
        fh.writelines("{},{}\n".format(i, l) for i, l in enumerate(lab))
    return path
