"""Cache all IDSSE matches and print degradation + bridge stats per match (external data only)."""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from possession import bridge as br, degrade as dg, idsse  # noqa: E402

for mid in idsse.MATCHES:
    secs = idsse.load(mid)
    ps = idsse.passes(mid, secs)
    row = [mid, "passes {}".format(len(ps))]
    for si, s in enumerate(secs):
        obs = dg.degrade(s, dg.Params(), np.random.default_rng(si))
        pi = br.pass_index(ps, si)
        n = [len([r for r in br.runs(br.bridge(s.label, pi, c) if c else s.label) if r[2] in (0, 1)])
             for c in (0,) + br.C_GRID]
        row.append("{} hidden {:.2f} tracked {:.1f} slots {} spells raw/c12/c25/c50 {}".format(
            s.name[:5], np.isnan(obs.ball[:, 0]).mean(), (~np.isnan(obs.slots[:, :, 0])).sum(1).mean(),
            obs.slots.shape[1], "/".join(map(str, n))))
    print("  ".join(row), flush=True)
