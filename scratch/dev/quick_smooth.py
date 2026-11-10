"""Dev match: Rules with position smoothing, at default noise and at 2x noise (J03WPY, 1 seed)."""
import os
import sys
from dataclasses import replace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from possession import candidates as cd, degrade as dg, harness as hs  # noqa: E402

noisy = [replace(dg.GRID[c], pos_noise=0.6, ball_noise=1.2) for c in (0, 4, 8)]
for k in (0, 1, 2, 4, 6):
    c = cd.Rules(smooth_f=k)
    a = hs.evaluate(c, hs.SPLIT["dev"], cells=(0, 4, 8), seeds=(0,), workers=1)
    b = hs.evaluate(c, hs.SPLIT["dev"], cells=noisy, seeds=(0,), workers=1)
    print("smooth +-{}  default noise {:.3f}  2x noise {:.3f}".format(k, a.spell.mean(), b.spell.mean()),
          flush=True)
