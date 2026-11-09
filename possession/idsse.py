"""IDSSE (DFL, 7 Bundesliga matches, CC-BY 4.0) loader with an npz cache.

Labels follow the challenge GT construction: D where BallStatus == 0, else BallPossession
(1 = home -> H, 2 = guest -> A). Coordinates are converted to the ATD convention: normalised 0-1
with origin at a corner, so features computed here and on the ATD share units.

    from possession import idsse
    secs = idsse.load("J03WPY")           # list of Section, one per half
    passes = idsse.passes("J03WPY")       # completed passes as (section, frame_index, team)
"""
import glob
import os
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "scratch", "data", "idsse")
CACHE = os.path.join(ROOT, "scratch", "data", "idsse_cache")
MATCHES = ("J03WMX", "J03WN1", "J03WOH", "J03WOY", "J03WPY", "J03WQQ", "J03WR9")
H, A, D = 0, 1, 2
PITCH = (105.0, 68.0)
SECTIONS = ("firstHalf", "secondHalf")


@dataclass
class Section:
    name: str
    t0: datetime          # wall time of frame 0
    label: np.ndarray     # (T,) int8 H/A/D
    ball: np.ndarray      # (T, 3) x, y normalised 0-1, z metres
    players: np.ndarray   # (T, P, 2) normalised 0-1, NaN when off the pitch
    team: np.ndarray      # (P,) int8 H/A


def _file(kind, mid):
    hits = glob.glob(os.path.join(DATA, "DFL_{}_*{}.xml".format(kind, mid)))
    if not hits:
        raise IOError("IDSSE {} file for {} missing; run `make idsse-download`".format(kind, mid))
    return hits[0]


def _time(s):
    return datetime.fromisoformat(s)


def _norm(x, y):
    return (np.asarray(x) + PITCH[0] / 2) / PITCH[0], (PITCH[1] / 2 - np.asarray(y)) / PITCH[1]


def _roles(mid):
    return {t.get("TeamId"): (H if t.get("Role") == "home" else A)
            for t in ET.parse(_file("02_01_matchinformation", mid)).getroot().iter("Team")}


def _parse(mid):
    roles = _roles(mid)
    raw = {s: {"players": []} for s in SECTIONS}
    for _, el in ET.iterparse(_file("04_03_positions_raw_observed", mid), events=("end",)):
        if el.tag != "FrameSet":
            continue
        sec, tid = el.get("GameSection"), el.get("TeamId")
        if sec in raw and (tid == "BALL" or tid in roles):
            fr = el.findall("Frame")
            n = np.array([int(f.get("N")) for f in fr])
            x = np.array([float(f.get("X")) for f in fr])
            y = np.array([float(f.get("Y")) for f in fr])
            if tid == "BALL":
                st = np.array([int(f.get("BallStatus")) for f in fr])
                po = np.array([int(f.get("BallPossession")) for f in fr])
                z = np.array([float(f.get("Z", 0)) for f in fr])
                raw[sec]["ball"] = (n, x, y, z, np.where(st == 0, D, np.where(po == 1, H, A)),
                                    _time(fr[0].get("T")))
            else:
                raw[sec]["players"].append((n, x, y, roles[tid]))
        el.clear()
    out = []
    for sec in SECTIONS:
        n, x, y, z, lab, t0 = raw[sec]["ball"]
        idx = {f: i for i, f in enumerate(n)}
        P = len(raw[sec]["players"])
        players = np.full((len(n), P, 2), np.nan, dtype=np.float32)
        team = np.zeros(P, dtype=np.int8)
        for j, (pn, px, py, t) in enumerate(raw[sec]["players"]):
            team[j] = t
            ii = np.array([idx.get(f, -1) for f in pn])
            ok = ii >= 0
            nx, ny = _norm(px[ok], py[ok])
            players[ii[ok], j, 0], players[ii[ok], j, 1] = nx, ny
        bx, by = _norm(x, y)
        out.append(Section(sec, t0, lab.astype(np.int8),
                           np.stack([bx, by, z], 1).astype(np.float32), players, team))
    return out


def load(mid):
    path = os.path.join(CACHE, mid + ".npz")
    if not os.path.exists(path):
        os.makedirs(CACHE, exist_ok=True)
        secs = _parse(mid)
        np.savez_compressed(path, **{"{}_{}".format(s.name, k): getattr(s, k)
                                     for s in secs for k in ("label", "ball", "players", "team")},
                            **{"{}_t0".format(s.name): np.array(s.t0.isoformat()) for s in secs})
    z = np.load(path)
    return [Section(s, _time(str(z[s + "_t0"])), z[s + "_label"], z[s + "_ball"],
                    z[s + "_players"], z[s + "_team"]) for s in SECTIONS]


def passes(mid, secs=None):
    """Completed passes: [(section_index, frame_index, team)] from the event XML."""
    secs = secs or load(mid)
    roles = _roles(mid)
    out = []
    for ev in ET.parse(_file("03_02_events_raw", mid)).getroot().iter("Event"):
        for play in ev.iter("Play"):
            if play.find("Pass") is None or play.get("Evaluation") != "successfullyCompleted":
                continue
            t = _time(ev.get("EventTime"))
            for si, s in enumerate(secs):
                f = int(round((t - s.t0).total_seconds() * 25))
                if 0 <= f < len(s.label):
                    out.append((si, f, roles.get(play.get("Team"), -1)))
                    break
    return out
