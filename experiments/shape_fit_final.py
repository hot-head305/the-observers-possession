"""Fit the shipped team-shape weights on the CV + dev IDSSE matches (never the 2 locked test
matches) and write possession/shape_weights.json, which the submission reads.

    uv run python experiments/shape_fit_final.py
"""
import json
import os
import sys
import warnings

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from possession import harness as hs  # noqa: E402
from shape_train import train  # noqa: E402

if __name__ == "__main__":
    warnings.filterwarnings("ignore")
    w = train(hs.SPLIT["cv"] + hs.SPLIT["dev"])
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "possession", "shape_weights.json")
    with open(path, "w") as f:
        json.dump({"trained_on": list(hs.SPLIT["cv"] + hs.SPLIT["dev"]), "weights": list(w)}, f, indent=1)
    print(path)
