"""Refuse commits that could carry data: videos, archives, big CSVs, big files. Exit 1 on any hit."""
import os
import subprocess
import sys

BANNED_EXT = (".mp4", ".mov", ".avi", ".mkv", ".npz", ".npy", ".parquet", ".zip", ".gz", ".pkl", ".xml")
MAX_BYTES = 5 * 1024 * 1024
MAX_CSV_ROWS = 1000


def problems(paths, root="."):
    out = []
    for p in paths:
        f = os.path.join(root, p)
        if not os.path.isfile(f):
            continue
        if p.lower().endswith(BANNED_EXT):
            out.append((p, "banned file type"))
        elif os.path.getsize(f) > MAX_BYTES:
            out.append((p, "larger than 5 MB"))
        elif p.lower().endswith((".csv", ".txt", ".tsv")):
            with open(f, "rb") as fh:
                if sum(1 for _ in fh) > MAX_CSV_ROWS:
                    out.append((p, "more than 1000 rows"))
    return out


def staged():
    r = subprocess.run(["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
                       capture_output=True, text=True, check=True)
    return [l for l in r.stdout.splitlines() if l]


def main(argv=None):
    paths = argv if argv else staged()
    bad = problems(paths)
    for p, why in bad:
        print("REFUSED  {}: {}".format(p, why))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
