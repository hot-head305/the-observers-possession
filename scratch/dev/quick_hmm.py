"""Dev-match tuning of the HMM: fit on the 4 CV matches, score on J03WPY (3 cells, 1 seed).

    uv run python scratch/dev/quick_hmm.py "w=0.1, switch=8" ...
"""
import os
import pickle
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from possession import harness as hs, hmm  # noqa: E402

MODE = os.environ.get("CTRL", "bins")
cache = os.path.join(hs.ROOT, "scratch", "data", "hmm_dev_fit_{}.pkl".format(MODE))
if os.path.exists(cache):
    base = pickle.load(open(cache, "rb"))
else:
    base = hmm.fit(hs.SPLIT["cv"], ctrl_mode=MODE)
    pickle.dump(base, open(cache, "wb"))
for a in sys.argv[1:] or [""]:
    m = eval("hmm.with_params(base, {})".format(a))
    r = hs.evaluate(m, hs.SPLIT["dev"], cells=(0, 4, 8), seeds=(0,), workers=1)
    print("{:<40} spell {:.3f} macro {:.3f} n_pred {:.0f}".format(
        a or "default", r.spell.mean(), r.macro.mean(), r.n_pred.mean()), flush=True)
