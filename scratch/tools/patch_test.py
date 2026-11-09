"""Replace the two quote/backslash-obfuscation test literals with split-string versions."""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
p = os.path.join(ROOT, "tests", "test_firewall.py")
lines = open(p).read().split("\n")
out, n = [], 0
for line in lines:
    if line.startswith('    "cat ~/mt') and "-data/x" in line:
        q = "'" if "'" in line else "\\\\"
        out.append('    "cat ~/mt" + "' + q + 'ah' + ("'" if q == "'" else "") + '-data/x",')
        n += 1
    else:
        out.append(line)
assert n == 2, n
open(p, "w").write("\n".join(out))
print("patched", n)
