"""Human-run promotion gate 5 (PLAN.md §2e): unsupervised checks of a candidate file on the match.

Every threshold is fixed in advance from published constants or external data, never from the
match. PASS/FAIL lines only; detail to <out>/sanity.json.

    valid       official validator accepts the file
    layout      X outside the two half blocks (games.py), so no spell can cross halftime
    prekick     D on the graded second-half block before the published kickoff
    rate        possessions per alive-minute within RATE_BAND (IDSSE, all label bridges, +-25 %)
    restarts    share of Smart Tagging set-piece starts with a D within +-3 s >= RESTART_FLOOR.
                Only for candidates that do not read Smart Tagging (--uses-tagging skips it).
"""
import sys

import numpy as np

from _common import ROOT, parser, paths, report

sys.path.insert(0, ROOT)
from possession.match import KICKOFF_2ND  # noqa: E402

RATE_BAND = (3.5, 13.7)  # IDSSE 4.69 (c=2 s) .. 10.97 (raw) per alive-minute, widened 25 %
RESTART_FLOOR = 0.5
RESTART_TOL = 75         # frames, 3 s
FPS = 25


def set_piece_starts(tag_path):
    import xml.etree.ElementTree as ET
    out = []
    for inst in ET.parse(tag_path).iter("instance"):
        if (inst.findtext("code") or "").strip().lower() == "set pieces":
            out.append(int(round(float(inst.findtext("start")) * FPS)))
    return np.array(sorted(out), int)


def spells(codes, mask):
    """Maximal H or A runs inside mask (graded frames)."""
    c = np.where(mask, codes, -1)
    br = np.flatnonzero(c[1:] != c[:-1]) + 1
    b = np.concatenate(([0], br, [len(c)]))
    return [(b[i], b[i + 1]) for i in range(len(b) - 1) if c[b[i]] in (0, 1)]


def main(argv=None):
    ap = parser(__doc__)
    ap.add_argument("--csv", required=True, help="the candidate submission file")
    ap.add_argument("--uses-tagging", action="store_true")
    a = ap.parse_args(argv)
    import possession_metrics as pm
    import games

    frame = pm.read_label_csv(a.csv)
    reason = pm.validate_submission(frame, a.n_frames)
    checks = [("candidate validates", reason is None)]
    detail = {"csv": a.csv, "invalid_reason": reason}
    if reason is None:
        codes = pm.label_codes(frame)
        inside = np.zeros(len(codes), bool)
        for half, first, last in games.half_video_blocks(games.GAME):
            inside[max(0, first):min(len(codes), last + 1)] = True
        h2 = games.half_video_blocks(games.GAME)[1][1]
        pre = slice(h2, min(len(codes), KICKOFF_2ND))
        graded = inside.copy()
        alive_min = float(np.sum(graded & np.isin(codes, (pm.H, pm.A)))) / FPS / 60
        n_sp = len(spells(codes, graded))
        rate = n_sp / alive_min if alive_min else float("inf")
        checks += [("X everywhere outside the two halves", bool(np.all(codes[~inside] == pm.X))),
                   ("second-half pre-kickoff block is D", bool(np.all(codes[pre] == pm.D))),
                   ("possessions per alive-minute in {}".format(RATE_BAND),
                    RATE_BAND[0] <= rate <= RATE_BAND[1])]
        detail.update({"n_spells": n_sp, "alive_min": alive_min, "rate": rate})
        if a.uses_tagging:
            print("SKIP  Smart Tagging restart agreement (candidate reads Smart Tagging)")
        else:
            sp = set_piece_starts(paths(a.data)["smart_tagging"])
            sp = sp[(sp >= 0) & (sp < len(codes))]
            sp = sp[inside[sp]]
            dead = np.concatenate(([0], np.cumsum(codes == pm.D)))
            lo, hi = np.maximum(0, sp - RESTART_TOL), np.minimum(len(codes), sp + RESTART_TOL + 1)
            hit = (dead[hi] - dead[lo]) > 0
            share = float(hit.mean()) if len(sp) else 0.0
            checks.append(("Smart Tagging restarts with a D within 3 s >= {}".format(RESTART_FLOOR),
                           share >= RESTART_FLOOR))
            detail.update({"n_set_pieces": int(len(sp)), "restart_share": share})
    return report(a.out, "sanity", checks, detail)


if __name__ == "__main__":
    sys.exit(main())
