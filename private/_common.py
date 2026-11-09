"""Shared helpers for the human-run private targets.

Every private script takes --data (the unpacked bundle) and --out (where detail goes), writes its
detail as JSON under --out, and prints only PASS/FAIL lines. Nothing here hard-codes a data path.
"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OFFICIAL = os.path.join(ROOT, "vendor", "official")
sys.path.insert(0, OFFICIAL)
sys.path.insert(0, os.path.join(OFFICIAL, "evaluation"))
sys.path.insert(0, os.path.join(OFFICIAL, "starter"))

N_FRAMES = 199319  # published: DATA.md
KICKOFFS = {"1st Half": 11185, "2nd Half": 113742}  # published: DATA.md / FAQ.md


def parser(doc):
    ap = argparse.ArgumentParser(description=doc)
    ap.add_argument("--data", required=True, help="unpacked bundle root (tactical/, broadcast/)")
    ap.add_argument("--out", required=True, help="detail output directory")
    ap.add_argument("--n-frames", type=int, default=N_FRAMES)
    return ap


def paths(data, source="tactical"):
    from games import asset_paths
    return asset_paths(data_dir=os.path.expanduser(data), source=source)


def report(out, name, checks, detail, words=("PASS", "FAIL"), gate=True):
    """checks: [(label, bool)]. Writes detail JSON, prints one line per check, returns exit code.
    gate=False is for hypothesis answers: either answer is a valid outcome, so exit 0."""
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, name + ".json"), "w") as f:
        json.dump(detail, f, indent=2, sort_keys=True, default=str)
    for label, ok in checks:
        print("{:<4}  {}".format(words[0] if ok else words[1], label))
    return 0 if not gate or all(ok for _, ok in checks) else 1
