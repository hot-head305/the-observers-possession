"""Human-run determinism gate: the submission must come out byte-identical from
  (a) this checkout, (b) a fresh clone of HEAD with a fresh venv, (c) docker linux/amd64.

PASS lines only; SHAs go to <out>/repro.json. (c) prints SKIP when docker is not installed or
not running. Requires a clean working tree, so that HEAD is what gets built.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

from _common import ROOT, parser, report
import submission

IMAGE = "python:3.11-slim-bookworm"
UV = "uv==0.12.3"  # same uv as the reference Mac, so uv.lock is read identically


def sh(cmd, **kw):
    return subprocess.run(cmd, check=True, capture_output=True, text=True, **kw)


def built_sha(out):
    with open(os.path.join(out, "submission.json")) as f:
        return json.load(f)["sha256"]


def main(argv=None):
    ap = parser(__doc__)
    ap.add_argument("--cand", default="rules")
    a = ap.parse_args(argv)
    data = os.path.abspath(os.path.expanduser(a.data))
    os.makedirs(a.out, exist_ok=True)
    detail, checks = {}, []
    # The submodule's locally deleted public CSVs (strict reading, PLAN.md §0) are not a build input.
    dirty = sh(["git", "-C", ROOT, "status", "--porcelain", "--untracked-files=no",
                "--ignore-submodules=dirty"]).stdout.strip()
    checks.append(("working tree clean (HEAD is what gets built)", not dirty))
    common = ["--data", data, "--n-frames", str(a.n_frames), "--cand", a.cand]

    out_a = os.path.join(a.out, "a_checkout")
    submission.main(common + ["--out", out_a])
    detail["a"] = built_sha(out_a)

    tmp = tempfile.mkdtemp(prefix="repro_")
    try:
        clone = os.path.join(tmp, "repo")
        sh(["git", "clone", "-q", "--recurse-submodules", ROOT, clone])
        env = dict(os.environ, UV_PROJECT_ENVIRONMENT=os.path.join(tmp, "venv"))
        sh(["uv", "sync", "--frozen", "-q"], cwd=clone, env=env)
        out_b = os.path.join(tmp, "out_b")
        sh(["uv", "run", "--frozen", "python", "private/submission.py"] + common + ["--out", out_b],
           cwd=clone, env=env)
        detail["b"] = built_sha(out_b)
        checks.append(("fresh clone + fresh venv byte-identical", detail["b"] == detail["a"]))

        docker = shutil.which("docker")
        up = docker and subprocess.run([docker, "info"], capture_output=True).returncode == 0
        if not up:
            print("SKIP  docker linux/amd64 (docker not installed or not running)")
        else:
            out_c = "/w/out_c"
            script = ("pip install -q '{}' && cd /w/repo && "
                      "UV_PROJECT_ENVIRONMENT=/tmp/venv uv sync --frozen -q && "
                      "UV_PROJECT_ENVIRONMENT=/tmp/venv uv run --frozen python private/submission.py "
                      "--data /data --n-frames {} --cand {} --out {}").format(UV, a.n_frames, a.cand, out_c)
            sh([docker, "run", "--rm", "--platform", "linux/amd64", "-v", tmp + ":/w",
                "-v", data + ":/data:ro", IMAGE, "sh", "-c", script])
            detail["c"] = built_sha(os.path.join(tmp, "out_c"))
            checks.append(("docker linux/amd64 byte-identical", detail["c"] == detail["a"]))
    except subprocess.CalledProcessError as e:
        detail["error"] = (e.stderr or "")[-2000:]
        checks.append(("rebuild ran without error", False))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return report(a.out, "repro", checks, detail)


if __name__ == "__main__":
    sys.exit(main())
