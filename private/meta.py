"""Human-run: hypothesis (i), does the ATD expose extra ball channels? PASS/FAIL only.

    H1a  the metadata declares ball channels beyond position/speed (or more than 4 of them)
    H1b  some ball field in the raw file is categorical (<= 3 distinct non-NaN values)
    H1c  that field is slow-changing (<= 1 change per 125 frames over the file)

Detail (channel ids, per-field stats) goes to <out>/meta.json for a human to read. Downstream code
never needs the names: it auto-detects categorical ball fields by value (see detect()).
"""
import sys
import xml.etree.ElementTree as ET

import numpy as np

from _common import parser, paths, report

STANDARD = {"x", "y", "z", "s", "speed", "position_x", "position_y", "position_z"}
SAMPLE_EVERY = 1  # read every line; the file streams in about a minute


def declared_ball_channels(meta_path):
    root = ET.parse(meta_path).getroot()
    specs = []
    for spec in root.iter("DataFormatSpecification"):
        specs.append([ref.get("channelId") for ref in spec.iter("BallChannelRef")])
    return specs


def ball_fields(raw_path):
    """Per comma-field of the ball group: distinct values (capped) and change counts."""
    distinct, changes, prev, n = [], [], None, 0
    with open(raw_path) as f:
        for i, line in enumerate(f):
            if i % SAMPLE_EVERY:
                continue
            parts = line.rstrip("\n").split(":")
            if len(parts) < 3:
                continue
            vals = parts[2].split(",")
            while len(distinct) < len(vals):
                distinct.append(set())
                changes.append(0)
            for k, v in enumerate(vals):
                if v and v[0] != "N" and len(distinct[k]) <= 50:
                    distinct[k].add(v)
                if prev is not None and k < len(prev) and v != prev[k] and v and v[0] != "N":
                    changes[k] += 1
            prev, n = vals, n + 1
    return [{"field": k, "n_distinct_capped": len(d), "changes": changes[k],
             "frames_per_change": n / max(1, changes[k])} for k, d in enumerate(distinct)]


def detect(fields):
    """Indices of ball fields that look like a categorical state channel."""
    return [f["field"] for f in fields if 1 <= f["n_distinct_capped"] <= 3]


def main(argv=None):
    a = parser(__doc__).parse_args(argv)
    p = paths(a.data)
    specs = declared_ball_channels(p["atd_meta"])
    extra = any(len(s) > 4 or any((c or "").lower() not in STANDARD for c in s) for s in specs)
    fields = ball_fields(p["atd_raw"])
    cat = detect(fields)
    slow = [k for k in cat if fields[k]["frames_per_change"] >= 125]
    checks = [("H1a extra ball channels declared in metadata?", extra),
              ("H1b a ball field is categorical (<=3 values)?", bool(cat)),
              ("H1c that field changes at most once per 5 s?", bool(slow))]
    return report(a.out, "meta", checks, {"declared_ball_channels": specs, "ball_fields": fields,
                                          "categorical_fields": cat, "slow_fields": slow},
                  words=("YES", "NO"), gate=False)


if __name__ == "__main__":
    sys.exit(main())
