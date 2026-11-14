# Private targets (human-run only)

These read the match data. Until 2026-11-14 Claude never ran them or saw their output. From 2026-11-14,
with the organisers' permission (`docs/LLM-USE.md`), Claude may run them too (PLAN.md §0). Each prints PASS/FAIL lines; detail goes to `private_out/<target>/`.

## One-time setup (your own Mac Terminal)

```
cd ~/hack2027
sed -n '/^```make$/,/^```$/p' docs/PRIVATE.md | sed '1d;$d' > Makefile.private
```

## Template

```make
DATA ?= $(HOME)/mtah-data
OUT  := private_out
PY   := uv run python

private-bundle:
	python3 private/check_bundle.py --data $(DATA)

private-align:
	$(PY) private/align.py --data $(DATA) --out $(OUT)/align

private-fallback:
	$(PY) private/fallback.py --data $(DATA) --out $(OUT)/fallback

private-meta:
	$(PY) private/meta.py --data $(DATA) --out $(OUT)/meta

private-submission:
	$(PY) private/submission.py --data $(DATA) --out $(OUT)/submission

private-repro:
	$(PY) private/repro.py --data $(DATA) --out $(OUT)/repro

private-sanity:
	$(PY) private/sanity.py --data $(DATA) --out $(OUT)/sanity --csv $(OUT)/submission/The_Observers.csv

private-degrade-profile:
	$(PY) private/degrade_profile.py --data $(DATA) --out $(OUT)/degrade_profile

private-day1:
	-$(MAKE) -f Makefile.private private-bundle
	$(MAKE) -f Makefile.private private-align private-fallback private-meta
	@echo "Done. These results stay with you: do not paste them into any AI tool."
```

## Run (Nov 8)

```
cd ~/hack2027
make private-day1
```

- `private-fallback` writes `private_out/fallback/The_Observers.csv`. That is the file to upload as soon as the
  form URL arrives (editable later).
- `private-meta` answers hypothesis (i) with YES/NO. Both answers are fine and need no action: the
  pipeline auto-detects the channel either way. Don't tell Claude.
- `private-bundle` failing on the two `.mp4` files does not stop the other targets; no current code
  reads the videos.
- Read the matching `private_out/<target>/*.json` for detail if something fails.

## Run (Nov 9): approach #4 and the determinism gate

```
cd ~/hack2027
make private-submission
open -a Docker
make private-repro
```

- `private-submission` writes `private_out/submission/The_Observers.csv` from approach #4 (rules).
  It is a candidate, not yet the upload: it still has to pass `private-sanity`, which comes later.
  The fallback stays the file to upload first.
- `private-repro` rebuilds the file from a fresh clone of HEAD in a fresh venv, then in Docker
  linux/amd64, and compares bytes. Docker Desktop must be running, otherwise that line says SKIP.
  The first Docker run downloads an image and the dependencies, which takes a few minutes.
- A failure here is for you to keep: the next Claude task is "make the build deterministic on
  external data", which needs no result from you.

## Run (Nov 10): gate 5 and the tracking profile

```
cd ~/hack2027
make private-submission
make private-sanity
make private-degrade-profile
```

- `private-sanity` checks the exact file in `private_out/submission/`. All PASS means approach #4
  may replace the fallback in the form on Nov 14. Any FAIL: keep the fallback; tell Claude nothing
  beyond "keep working on external data".
- `private-degrade-profile` compares the real tracking's ball gaps, fragments and position jitter
  with our simulation. FAIL lines are expected and need no action now; they become the input for
  the training side later, read from file by code.
