"""Dev-match comparison: Rules vs RulesViterbi variants (J03WPY, 3 cells, 1 seed).

    uv run python scratch/dev/quick_rv.py "switch_cost=6" "switch_cost=10,ctrl_r=1.2"
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from possession import candidates as cd, harness as hs  # noqa: E402

cands = [cd.Rules()] + [cd.RulesViterbi(**cd.parse_kw(a.split(","))) for a in sys.argv[1:]]
for c in cands:
    r = hs.evaluate(c, hs.SPLIT["dev"], cells=(0, 4, 8), seeds=(0,), workers=1)
    print("{:<50} spell {:.3f} macro {:.3f} n_pred {:.0f}".format(
        c.name[:50], r.spell.mean(), r.macro.mean(), r.n_pred.mean()), flush=True)
