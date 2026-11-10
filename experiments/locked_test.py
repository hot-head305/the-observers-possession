"""Freeze the submitted configuration, then score it once on the locked IDSSE test matches.

    make freeze        records the config hash of the submitted candidate (once, clean tree)
    make locked-test   scores it on SPLIT["test"] against the baseline (once, clean tree, hash must match)

Both write to experiments/registry.jsonl. The test is marked started before scoring, so a crash
or an interrupt also uses up the single run. External data only.
"""
import json
import os
import sys
from dataclasses import asdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from possession import candidates as cd, harness as hs  # noqa: E402


def frozen():
    """The candidate private/submission.py writes by default."""
    return cd.WithChannel(cd.Rules())


def config(c):
    return {"class": type(c).__name__, **asdict(c)}


def rows(path):
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return [json.loads(l) for l in f if l.strip()]


def freeze(path=hs.REGISTRY):
    if any(r["split"] == "freeze" for r in rows(path)):
        return "already frozen"
    if hs._git_sha().endswith("-dirty"):
        return "tree not clean; commit first"
    c = frozen()
    row = hs.append({"split": "freeze", "name": c.name, "config": config(c),
                     "config_hash": hs.config_hash(config(c))}, path)
    print(json.dumps(row))
    return None


def locked_test(path=hs.REGISTRY, evaluate=hs.evaluate):
    reg = rows(path)
    fz = [r for r in reg if r["split"] == "freeze"]
    if not fz:
        return "not frozen; run make freeze first"
    if any(r["split"] in ("test", "test_started") for r in reg):
        return "the locked test has already run"
    if hs._git_sha().endswith("-dirty"):
        return "tree not clean; commit first"
    c = frozen()
    if hs.config_hash(config(c)) != fz[0]["config_hash"]:
        return "the candidate changed since the freeze"
    hs.append({"split": "test_started", "name": c.name, "config_hash": fz[0]["config_hash"]}, path)
    base = cd.Baseline(50)
    rb = evaluate(base, hs.SPLIT["test"], name=base.name)
    rc = evaluate(c, hs.SPLIT["test"], name=c.name)
    cmp = hs.compare(rc, rb)
    hs.append(hs.result_row(rb, "test", config(base)), path)
    print(json.dumps(hs.append(hs.result_row(rc, "test", config(c), {"vs": base.name, **cmp}), path)))
    return None


if __name__ == "__main__":
    err = freeze() if sys.argv[1:] == ["freeze"] else locked_test() if sys.argv[1:] == ["run"] else "usage"
    if err:
        print("refused:", err, file=sys.stderr)
    sys.exit(1 if err else 0)
