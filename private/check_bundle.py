"""Human-run: is the downloaded match bundle complete? Prints PASS/FAIL only.

Expected layout is the one published in the official DATA.md. Checks existence and non-zero size;
never opens a file. Run it in your own terminal, never through an AI tool:

    python3 private/check_bundle.py --data <your data folder>
"""
import argparse
import os

EXPECTED = {
    "tactical": ["BAR-ATH_tactical.mp4", "BAR-ATH_tactical_atd.xml", "BAR-ATH_tactical_atd.txt",
                 "BAR-ATH_tactical_homography.csv", "BAR-ATH_tactical_smart_tagging.xml"],
    "broadcast": ["BAR-ATH_broadcast.mp4", "BAR-ATH_broadcast_atd.xml", "BAR-ATH_broadcast_atd.txt",
                  "BAR-ATH_broadcast_homography.csv"],
}


def check(root):
    lines, ok = [], True
    for folder, names in EXPECTED.items():
        for name in names:
            path = os.path.join(root, folder, name)
            good = os.path.isfile(path) and os.path.getsize(path) > 0
            ok &= good
            lines.append("{}  {}/{}".format("PASS" if good else "FAIL", folder, name))
    lines.append("{}  bundle complete".format("PASS" if ok else "FAIL"))
    return ok, lines


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ok, lines = check(os.path.expanduser(ap.parse_args().data))
    print("\n".join(lines))
    if not ok:
        print("Missing files: unpack the download so the two folders above exist (see DATA.md).")
