"""Generate the submission from the provided data with a named candidate. Also the public
reproduction entry point (`make submission DATA=... OUT=...`).

Writes <out>/The_Observers.csv. PASS line: the official validator accepts it. Its SHA-256 goes to
<out>/submission.json only.
"""
import hashlib
import os
import sys

from _common import ROOT, parser, paths, report

sys.path.insert(0, ROOT)
from possession import candidates as cd, match  # noqa: E402

TEAM_FILE = "The_Observers.csv"
CANDIDATES = {"rules": cd.Rules(), "baseline": cd.Baseline(50)}


def build(data, n_frames, cand):
    p = paths(data)
    ball, slots, team = match.load(p["atd_meta"], p["atd_raw"], n_frames)
    return match.predict(CANDIDATES[cand], ball, slots, team)


def sha256(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def main(argv=None):
    ap = parser(__doc__)
    ap.add_argument("--cand", default="rules", choices=sorted(CANDIDATES))
    a = ap.parse_args(argv)
    import possession_metrics as pm
    path = match.write_csv(os.path.join(a.out, TEAM_FILE), build(a.data, a.n_frames, a.cand))
    reason = pm.validate_submission(pm.read_label_csv(path), a.n_frames)
    return report(a.out, "submission", [("{} validates ({})".format(a.cand, TEAM_FILE), reason is None)],
                  {"path": path, "sha256": sha256(path), "candidate": a.cand,
                   "config": repr(CANDIDATES[a.cand]), "invalid_reason": reason})


if __name__ == "__main__":
    sys.exit(main())
