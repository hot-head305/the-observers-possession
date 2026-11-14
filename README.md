# The Observers: possession labelling (More Than a Hack 2027, Phase 1)

Labels every frame of the provided match as H / A / D / X from automatic tracking, scored by spellF1.

This repository contains code only, no match data. The data bundle is not redistributable.
All model development uses external open data: the IDSSE DFL/TRACAB matches (Bassek et al. 2025, CC-BY 4.0).

## Setup

```
uv sync
make test
```

## Reproduce the submission

```
git clone --recurse-submodules https://github.com/hot-head305/the-observers-possession
cd the-observers-possession
uv sync --frozen
make submission DATA=/path/to/unpacked/bundle OUT=out
```

This writes `out/The_Observers.csv`, byte-identical across a fresh clone, a fresh venv and
docker linux/amd64. The technical report is `docs/REPORT.md`.
