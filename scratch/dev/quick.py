"""Quick dev-match comparison: baseline vs Rules variants (J03WPY, 3 cells, 1 seed)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from possession import candidates as cd, harness as hs  # noqa: E402

cands = [cd.Baseline(50), cd.Rules()] + [eval("cd.Rules({})".format(a)) for a in sys.argv[1:]]
for c in cands:
    r = hs.evaluate(c, hs.SPLIT["dev"], cells=(0, 4, 8), seeds=(0,), workers=1)
    print("{:<70} spell {:.3f} macro {:.3f} n_pred {:.0f} cells {}".format(
        c.name[:70], r.spell.mean(), r.macro.mean(), r.n_pred.mean(),
        " ".join("{:.3f}".format(v) for v in r.spell.mean(axis=(0, 2)))), flush=True)
