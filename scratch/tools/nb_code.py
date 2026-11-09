"""Print only code-cell sources of a notebook; outputs are discarded unread."""
import json, sys
nb = json.load(open(sys.argv[1]))
for i, c in enumerate(nb["cells"]):
    if c["cell_type"] == "code":
        print("# --- cell", i)
        print("".join(c["source"]))
