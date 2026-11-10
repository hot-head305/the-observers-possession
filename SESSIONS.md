# SESSIONS

## 2026-11-07 — Data firewall + evidence-grounded PLAN.md (planning only)

**Changed:**
- `.claude/settings.json` + `.claude/hooks/firewall.py`: PreToolUse firewall on all tools, deny rules, tamper guard.
- `tests/test_firewall.py`: 67 tests.
- `Makefile`: test, evidence targets, and a `private-%` forwarder.
- `pyproject.toml` / `uv.lock`: Python 3.11; numpy 2.2.6, pandas 2.2.3, kloppy 3.18.0, pytest 8.3.5.
- `.gitignore`.
- `vendor/official` cloned @ f8f2629ff1e0985f81d7e59d8413678514ee1530. The public GT and baseline CSVs were deleted locally and never read; restore with `git -C vendor/official checkout -- evaluation`.
- `scratch/metric/*`: synthetic spellF1 sensitivity and the lag-table fit.
- `scratch/external/*`: IDSSE profile, baseline transfer on degraded IDSSE, oracle decomposition, IDSSE lag curve, SkillCorner profile.
- `scratch/out/*.txt`: the outputs.
- `PLAN.md`.

**Broke:**
- The firewall had a gap: words glued to `;` skipped the file scan, so a public `.gitignore` containing a forbidden *name* (no data) was printed. Fixed with an operator-aware tokenizer and a Bash tamper guard; Fadel should review the hook.
- The figshare IDSSE URLs return an empty 202 bot challenge, so I used the Hugging Face PySport mirror.
- v1 transfer check (`idsse_baseline_transfer.py`) was mis-calibrated, as the red team found: wrong hidden-frame denominator, ball-only degradation, 1 seed, crashing control. Superseded by `idsse_transfer_v2.py` → `scratch/out/idsse_baseline_transfer_v2.txt`. The oracle decomposition still uses the v1 degradation (level indicative only).
- Red team appended to PLAN.md §10; the plan was revised accordingly.
- No typecheck is configured (no mypy/pyright in the project); `make test` passes (67/67).
- Repo-wide `grep -r .` / Glob from the repo root are blocked by design.

**Next:** Fadel reviews PLAN.md §9 decisions and creates `Makefile.private`; then Nov 8 gate: `private-align`, `private-fallback`, `private-meta`.

## 2026-11-07 — Plan approved; bundle completeness checker

**Changed:** `PLAN.md` §9 marked approved; `private/check_bundle.py` (human-run, PASS/FAIL per expected file); `tests/test_check_bundle.py`; memory note on the firewall rule.
**Broke:** nothing. 68/68 tests pass. Claude did not inspect the data folder or the Google Drive.
**Next:** Fadel runs check_bundle in his own terminal; fill in team name and roles; Nov 8 gate (`private-align`, `private-fallback`, `private-meta`).

## 2026-11-07 — Team name and solo roles recorded

**Changed:** `PLAN.md` §9: team "The Observers" (files `The_Observers.csv/.pdf`), Fadel holds all roles, #2 GBM dropped for solo mode.
**Broke:** the bundle is missing both mp4 videos (Fadel's own check). This does not block the pipeline.
**Next:** next session builds the `private/*.py` targets (align, fallback, meta) and the `Makefile.private` template; Fadel fetches the videos and re-runs the checker.

## 2026-11-08 — Day-1 private targets + external-data foundation

**Changed:**
- `private/_common.py`, `private/align.py`, `private/fallback.py` (writes `The_Observers.csv` and checks it is byte-identical to the official baseline_smooth50 via git), `private/meta.py` (hypothesis i, auto-detects categorical ball fields by value).
- `docs/PRIVATE.md`: `Makefile.private` template plus a one-line extract command; the template was checked with `make -n`.
- `possession/idsse.py` (loader, npz cache, completed passes from events), `possession/bridge.py` (definition bridge, c ∈ {0.5, 1, 2} s, restarts never absorbed), `possession/degrade.py` (ball hidden 41 % of frames incl. aerial/dead, player dropout, slot fragmentation, cross-team fragments, duplicates, noise; 3×3 GRID).
- Tests: `tests/test_private_targets.py`, `tests/test_possession.py`. 75/75 pass.
- Real-data smoke (`scratch/out/idsse_cache_smoke.txt`): hidden 0.40–0.43, tracked 19.5–20.6, all 7 matches cached.

**Broke:** nothing failing. Known gaps: our slots per half (~25) fragment less than the ATD's 46 (to be set from `private-degrade-profile`). Claude did not move or inspect the video files; Fadel moves them himself.

**Next:** Fadel runs the docs/PRIVATE.md setup, then `make private-day1`. Claude builds the metric harness (match-level CV, Holm, registry) and approach #4 (rule machine), then the Nov 9 repro check on #4.

## 2026-11-09 — Private-day1 UX fix after a relay-protocol slip

**Changed:** `private/_common.py` (`report` gains `words`/`gate`), `private/meta.py` (hypothesis answers print YES/NO, exit 0), `docs/PRIVATE.md` (day1 runs past a bundle FAIL, ends with a do-not-paste reminder), `tests/test_private_targets.py`. 75/75 pass; template `make -n` exit 0.
**Broke:** relay protocol: Fadel pasted the full `private-day1` output into Claude Code. Root cause: hypothesis "FAIL" plus a make error looked like a bug. Decision: no design choice uses that output; the pipeline keeps auto-detecting the channel. The bundle still lacks both mp4 files; no code reads them.
**Next:** Fadel re-extracts `Makefile.private`, places the videos, uploads `The_Observers.csv` when the form opens. Claude: metric harness + approach #4, then the repro check.

## 2026-11-09 — Submission form not open yet

**Changed:** nothing in code. Verified: `vendor/official` has no upstream commits past f8f2629; SUBMISSION.md says the form URL is "shared by email to all registered participants".
**Broke:** the form also needs a public repo URL and a technical document. There is no git repo or GitHub remote yet, so an early fallback upload is blocked on those too.
**Next:** Fadel watches the registration inbox and creates the public GitHub repo (his outward-facing action). Claude prepares a data-free repo and a stub report so both are ready when the email arrives.

## 2026-11-09 — Repo, CV harness, approach #4, match pipeline, repro gate

**Changed:**
- git repo + **private** GitHub repo `hot-head305/the-observers-possession` (flip to public before submitting). `vendor/official` is a submodule pinned at f8f2629. `tools/check_repo.py` + `make check-repo` refuse data-like files. `README.md`.
- `possession/harness.py`: match × 9 cells × 5 seeds × 3 bridges, seed-averaged; paired match bootstrap; Holm; promotion rule §2e 1–3; registry with git SHA and a dirty flag.
- `possession/features.py`, `possession/candidates.py` (Baseline, Rules #4), `experiments/run_cv.py`, `make cv`.
- `possession/degrade.py`: IDSSE freezes the ball on 100 % of dead frames, which leaks the label. Fixed with `dead_ball_path` (roll out, carried by the restart taker, placed for 2 s).
- `possession/match.py` (ATD reader, per-half predict, published 2nd-half pre-kickoff D), `private/submission.py`, `private/repro.py` (checkout vs fresh clone + venv vs docker linux/amd64), template targets in `docs/PRIVATE.md`, `make submission DATA=...`.
- `make test` now runs every test (it ran only the firewall tests before). 79 pass, 1 opt-in (`REPRO_IT=1`: fresh-clone rebuild byte-identical on synthetic data, passed).

**Results (external data only):**
- CV: baseline ±50 0.251, Rules 0.429. Gain +0.177, positive in all 27 cell × bridge combinations; promotes over the baseline.
- Rules defaults were set on the dev match only (`scratch/dev/quick.py`).

**Broke / caveats:**
- The dead detector relies on slow ball + slow players. Our stoppage trajectory is a model, so the real-match level is probably lower.
- Slot fragmentation is still ~25 vs 46.
- Docker was not running here, so the docker leg is untested.
- An auto-mode classifier denied writing `.git/hooks/pre-commit`; `make check-repo` runs by hand.
- The extra-ball-channel branch (hypothesis i) is not built yet.

**Next:** Fadel runs `make private-submission` and `make private-repro` (docs/PRIVATE.md). Claude: #1 HSMM with evidence-dependent switch costs vs #4 (G1, Nov 10), the extra-channel branch, `private-sanity`, and a stub report.

## 2026-11-10 — G1: #1 HMM not promoted; #4 hardened against position noise

**Changed:**
- `possession/hmm.py` (#1): 3-state Viterbi; naive-Bayes emissions, team-symmetrised so IDSSE home/away habits don't transfer; tie-break that places switches late (a loose ball carries the last team). `ctrl_mode="rules"` variant.
- `candidates.RulesViterbi`: optimal segmentation on the rule evidence. `candidates.parse_kw`.
- `harness.evaluate_lomo`. Cells may now be `Params`, for stress tests.
- `features.smooth_xy`; `Rules.smooth_f` (default 2).
- `experiments/stress.py` → `scratch/out/stress.txt`; `experiments/smooth_cv.py`.
- Tests: 81 pass, 1 opt-in.

**Results (external only):**
- G1 on the dev match J03WPY (cells 0/4/8, 1 seed):

  | candidate | best spellF1 |
  |---|---|
  | HMM (binned) | 0.426 |
  | HMM (rule evidence) | 0.426 |
  | RulesViterbi | 0.448 |
  | Rules (greedy) | 0.491 |

  No #1 variant was taken to CV (the Holm budget is kept). #4 stays the incumbent.
- Stress test: gain over the baseline stays +0.16 to +0.18 under 4× fragmentation, 5 % cross-team fragments, 50 % ball hidden, 15 % dropout and every stoppage-ball variant. Under 2× position noise it falls to +0.076.
- Smoothing ±2 frames fixes that on CV: +0.016 at 1× noise, +0.134 at 2× (0.297 → 0.431).
- CV now: Rules 0.446 vs baseline 0.251 (+0.195, min cell +0.152). Registry row @ d03757e.

**Broke:** nothing failing. The `RuntimeWarning` (inf − inf) in `hmm.categories` is harmless. The greedy rules beating the optimal segmentation is unexplained; worth a look if time allows.

**Next:** Fadel re-runs `make private-submission` (new default) and `make private-repro`, with Docker running. Claude: `private-sanity` (gate 5), the extra-ball-channel branch, the report draft, and `private-degrade-profile` so the degradation can be checked against the real ATD noise.
