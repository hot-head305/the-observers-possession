"""Human-run: regenerate the official baseline_smooth50 as the always-ready fallback submission.

Writes <out>/The_Observers.csv (the upload name). PASS lines:
    valid      official validator accepts it
    official   byte-identical to the baseline_smooth50.csv committed in the official repo
               (read from git, so a locally deleted copy does not matter); SKIP if git is unavailable
"""
import hashlib
import os
import subprocess
import sys

from _common import OFFICIAL, parser, paths, report

TEAM_FILE = "The_Observers.csv"
WINDOW = 50


def official_sha():
    try:
        blob = subprocess.run(["git", "-C", OFFICIAL, "show",
                               "HEAD:evaluation/results/baseline_smooth50.csv"],
                              capture_output=True, check=True).stdout
    except Exception:
        return None
    return hashlib.sha256(blob).hexdigest()


def build(data, n_frames):
    import baseline
    from games import GAMES, GAME
    p = paths(data)
    codes = baseline.nearest_player_labels(p["atd_raw"], baseline.team_of_each_track(p["atd_meta"]),
                                           n_frames, GAMES[GAME]["pitch"])
    return baseline.smooth(codes, WINDOW)


def main(argv=None):
    a = parser(__doc__).parse_args(argv)
    import baseline
    import possession_metrics as pm
    path = baseline.write_submission(os.path.join(a.out, TEAM_FILE), build(a.data, a.n_frames))
    reason = pm.validate_submission(pm.read_label_csv(path), a.n_frames)
    with open(path, "rb") as f:
        sha = hashlib.sha256(f.read()).hexdigest()
    ref = official_sha()
    checks = [("fallback validates ({})".format(TEAM_FILE), reason is None)]
    if ref is None:
        print("SKIP  official baseline SHA unavailable (git)")
    else:
        checks.append(("fallback byte-identical to official baseline_smooth50", sha == ref))
    return report(a.out, "fallback", checks, {"path": path, "sha256": sha, "official_sha256": ref,
                                              "invalid_reason": reason})


if __name__ == "__main__":
    sys.exit(main())
