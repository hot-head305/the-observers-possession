"""Human-run: frame alignment of the tactical bundle (the official checks, PASS/FAIL only).

    ATD     records numbered 1..N, contiguous, one per video frame
    homog.  N rows, frame 0..N-1
    tagging both 'Kick Off (Start)' tags contain the published kickoff frames
"""
import sys

import numpy as np
import pandas as pd

from _common import KICKOFFS, parser, paths, report


def atd_ids(raw_path):
    first = last = None
    count = 0
    with open(raw_path) as f:
        for line in f:
            fid = int(line[:line.index(":")])
            first = fid if first is None else first
            last = fid
            count += 1
    return first, last, count


def kickoffs(tag_path, fps=25):
    import xml.etree.ElementTree as ET
    found = {}
    for inst in ET.parse(tag_path).iter("instance"):
        code = (inst.findtext("code") or "").strip().lower()
        tags = {l.findtext("group"): l.findtext("text") for l in inst.findall("label")}
        if code == "set pieces" and (tags.get("Type") or "").strip().lower() == "kick off (start)":
            a = int(round(float(inst.findtext("start")) * fps))
            b = int(round(float(inst.findtext("end")) * fps))
            found.setdefault(tags.get("Half"), []).append((a, b))
    return found


def main(argv=None):
    a = parser(__doc__).parse_args(argv)
    p = paths(a.data)
    first, last, count = atd_ids(p["atd_raw"])
    frames = pd.read_csv(p["homography"], usecols=["frame"])["frame"].values
    ko = kickoffs(p["smart_tagging"])
    ko_ok = all(any(s <= f <= e for s, e in ko.get(h, [])) for h, f in KICKOFFS.items())
    checks = [
        ("ATD records == {} and numbered 1..N contiguous".format(a.n_frames),
         count == a.n_frames and first == 1 and last == a.n_frames),
        ("homography rows == {} with frame 0..N-1".format(a.n_frames),
         len(frames) == a.n_frames and np.array_equal(frames, np.arange(a.n_frames))),
        ("Smart Tagging kickoffs contain the published kickoff frames", ko_ok),
    ]
    detail = {"atd": {"first": first, "last": last, "count": count},
              "homography_rows": int(len(frames)), "kickoff_tags": ko}
    return report(a.out, "align", checks, detail)


if __name__ == "__main__":
    sys.exit(main())
