"""Check the make template in docs/PRIVATE.md uses tab-indented recipes and parses with make -n."""
import os
import re
import subprocess
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
text = open(os.path.join(ROOT, "docs", "PRIVATE.md")).read()
block = re.search(r"^```make\n(.*?)^```$", text, re.S | re.M).group(1)
recipes = [l for l in block.splitlines() if l.startswith(("\t", "    ")) and l.strip()]
print("recipe lines", len(recipes), "all tab-indented:", all(l.startswith("\t") for l in recipes))
with tempfile.TemporaryDirectory() as d:
    mk = os.path.join(d, "M")
    open(mk, "w").write(block.replace("$(HOME)/", "/nonexistent/"))
    r = subprocess.run(["make", "-n", "-f", mk, "private-day1"], capture_output=True, text=True, cwd=ROOT)
    print("make -n exit", r.returncode, "commands", len(r.stdout.splitlines()), r.stderr.strip()[:200])
