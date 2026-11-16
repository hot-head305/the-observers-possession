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

## 2026-11-10 — Gate 5, tracking profile, extra-channel branch, report draft

**Changed:**
- `private/sanity.py` checks, with thresholds fixed in advance:
  - validates;
  - X outside the halves;
  - second-half pre-kickoff block is D;
  - possessions per alive-minute within 3.5–13.7 (the IDSSE range over every bridge, widened 25 %);
  - ≥ 50 % of Smart Tagging set-piece starts have a D within ±3 s.
- `possession/profile.py` + `private/degrade_profile.py`: real versus simulated tracking statistics, PASS/FAIL per statistic. The jitter estimator recovers the injected noise exactly (0.30 / 0.59 m).
- `candidates.WithChannel`: the hypothesis (i) branch, now the default `rules` candidate. It is a no-op without a categorical ball column. `match.read_atd` keeps the extra ball fields. `Observed.ball_extra`.
- `docs/PRIVATE.md`: new targets and a Nov 10 run section.
- `docs/REPORT.md`: technical document draft (the form accepts `.md`).
- Stress test re-run with smoothing: gain +0.18 to +0.22 in every setting (`scratch/out/stress.txt`).
- 83 tests pass, 1 opt-in.

**Broke:** nothing failing. `private-degrade-profile` loads the IDSSE cache, so it only runs where `make idsse-download` has run (Fadel's Mac has it).

**Next:** Fadel runs the Nov 10 section of docs/PRIVATE.md. Nov 13 freeze (pre-register the config hash, then the locked test once). Nov 14: flip the repo to public, then upload the CSV and `docs/REPORT.md` as `The_Observers.md`.

## 2026-11-10 — Freeze and one-shot locked test

**Changed:**
- `experiments/locked_test.py` + `make freeze` / `make locked-test`.
  - The frozen candidate is the submission default, `WithChannel(Rules())`.
  - freeze: once, clean tree; writes a `freeze` row with the config hash.
  - locked-test: needs a freeze, a clean tree and an unchanged hash. It writes `test_started` before scoring, so even a crash uses up the single run. Then it writes the baseline and candidate `test` rows on J03WQQ/J03WR9.
- `possession/harness.py`: `append` and `result_row` were split out of `log`; `log` still refuses `test`.
- `tests/test_locked_test.py`. 86 pass, 1 opt-in.

**Broke:** a relay-protocol slip: Fadel wrote "done all pass" about the Nov 10 private run. No code or design choice uses it. Which CSV to upload stays his call, per docs/PRIVATE.md.
**Next:** Nov 13: Claude runs `make freeze`, commits, then `make locked-test` once and puts the result in REPORT §5. Nov 14: Fadel flips the repo to public and uploads.

## 2026-11-14 — Freeze + one-shot locked test

**Changed:**
- `make freeze`: `freeze` row in `experiments/registry.jsonl`, config hash `4185e57a0bad` (`WithChannel(Rules())`), commit 5a66ca0.
- `make locked-test` (ran once, on J03WQQ/J03WR9): baseline 0.259 spellF1 / 0.616 macroF1; ours 0.442 / 0.809. Gain +0.183, p 0.0, minimum cell gain +0.153, no sign flip. Per match 0.447 / 0.438.
- `docs/REPORT.md` §5: locked-test result added.
**Broke:** nothing. 86 pass, 1 opt-in. No typecheck configured. The freeze ran a day late (scheduled for Nov 13); no output-changing work happened in between.
**Next:** Fadel: `make private-repro` with Docker running; flip the GitHub repo to public; upload the CSV and `docs/REPORT.md` as `The_Observers.md` (deadline Nov 17). After the freeze, only format or index fixes.

## 2026-11-14 — Firewall lifted; sanity + repro on the match data; release check

**Changed:**
- Policy: the organisers allowed AI use on the competition data, per Fadel; **not in writing** (`docs/LLM-USE.md`). `.claude/settings.json` (hook config) removed from the repo; Fadel's `.claude/settings.json.off` stays untracked.
- `PLAN.md` §0 rewritten (firewall Nov 7–14, lifted Nov 14); §5 and §7 item 8 adjusted. `docs/REPORT.md` §8 (AI use) and header. `docs/PRIVATE.md` header. `README.md` reproduction commands.
- Claude ran on the match data:
  - `make private-sanity`: 5/5 PASS.
  - `make private-repro`: checkout, fresh clone + venv, docker linux/amd64 all PASS. SHA-256 `2f8b4a618978847d34c14dbefdb13647d922e549f1b5d7d6422bc32e243fc677` = `private_out/submission/The_Observers.csv`.
  - The README command (`make submission DATA=… OUT=…`) gives the same SHA.
- Release check: `make check-repo` rc 0; nothing data-like tracked (no CSV, mp4, private_out, local_cache, Makefile.private); `.gitignore` covers them. No model change.
- Repo flipped to public on Fadel's yes.

**Broke:** nothing. 86 pass, 1 opt-in. No typecheck configured.
**Next:** Fadel uploads `private_out/submission/The_Observers.csv` (SHA above) and `docs/REPORT.md` as `The_Observers.md` before 2026-11-17.

## 2026-11-14 — Sprint v2: fitted degradation (A), retune (B), team-shape evidence (C)

**Changed:**
- `PLAN.md` §6b: Nov 14–17 sprint, v2 gate fixed in advance (707d4b3).
- A, `experiments/fit_profile.py` → `experiments/profile_params.json`:
  - the degradation is fitted to the real tracking profile (gap median 8 s, no aerial hide, no position noise);
  - `experiments/profile_cv.py`: CV baseline 0.235 (real match 0.243), v1 0.394.
- B, `experiments/profile_dev_sweep.py`: v1's parameters are already near the dev optimum; the best single change is +0.007. Not shipped.
- C, `possession/shape.py`: ball-free team-shape logistic model (dev AUC 0.893).
  - `candidates.RulesShape` uses it as evidence inside ball gaps of 3 s or more (thr 0.6).
  - `candidates.RulesGap` (switch placed inside the gap) was worse; dropped.
  - `Rules` gained the `features` / `_switch_at` hooks. Its output is unchanged and the config hash is unchanged.
- v2 = submission candidate `shape`. Weights in `possession/shape_weights.json` (IDSSE CV + dev). `experiments/shape_cv.py`, `experiments/shape_fit_final.py`.
- `tests/test_shape.py`: 91 pass, 1 opt-in.

**Results:**
- CV LOMO, fitted profile: v1 0.394 → v2 0.427, gain +0.033, all 4 matches positive, minimum cell +0.010. **§6b gate passes.**
- Old grid: +0.009 (p_gain_pos 1.0, worst cell −0.005).
- Real match:
  - `private-sanity` on v2: 5/5 PASS; 398 spells (v1: 371).
  - Public window: identical to v1 (0.421).
  - Repro on v2: fresh venv and docker both PASS, SHA `c0fd9e484873d550ace048a59eea877d8fbfef95a1ebb26da92d5cf276a7e987`.

**Broke:** nothing failing. Spurious `RuntimeWarning` from matmul in `shape.fit` (Accelerate BLAS); the results are finite and deterministic (repro PASS).
**Next:**
- Main session / Fadel: decide the v2 freeze. Steps: switch the `submission.py` default to `shape`, `make freeze`, locked test #2 (disclosed as a second use).
- Then REPORT for v2. D (Smart Tagging) not started.

## 2026-11-15 — v2 review fixes (RulesFix): CV vs `shape`, real-match counts; neither promoted

**Changed:** branch `v2-review-fixes` (from main 31d5eb2; main untouched).
- `possession/features.py`: ball speed relative to each team's nearest slot (`relH`/`relA`), ball velocity change over ±0.24 s (`ball_dv`), half-second ball speeds.
- `possession/candidates.py`: `RulesShape` is plain `Rules` when `shape_w` is empty; new `RulesFix(RulesShape)`, both flags off by default and output-identical to `shape` then.
  - (1) `ctrl_rel_v`/`ctrl_dv`: control evidence only if the ball moves with the player or is touched (velocity change), not distance alone.
  - (2) `inside_m`/`calm_dead_s`/`calm_decel`: no slowness-only stoppage while the ball is visible and > `inside_m` m inside; such runs need ≥ `calm_dead_s` s (and a deceleration ≥ `calm_decel`, which dev set to 0, see below).
- `experiments/review_dev.py` (dev sweep, J03WPY, fitted profile, 2 seeds), `experiments/review_cv.py` (§6b protocol: CV, 5 seeds, 3 bridges, fitted profile, LOMO shape weights, Holm over 3), `private/review_counts.py` (unsupervised counts on the match).
- `private/submission.py`: candidates `fix_ctrl`, `fix_stop`, `fix_both`. v1 SHA `2f8b4a61…` and shape SHA `c0fd9e48…` rebuilt unchanged.
- `tests/test_review_fixes.py`: 96 pass, 1 opt-in. v1 config hash still `4185e57a0bad`.
- Registry: 4 rows (split cv, profile fitted).

**Results (CV, fitted profile, incumbent v2 `shape` 0.4264):**

| candidate | spell | gain | min-cell gain | p_holm | per-match gain | promote (§2e) | §6b gate |
|---|---|---|---|---|---|---|---|
| fix_ctrl (rel 2 m/s, dv 2 m/s) | 0.4280 | +0.0016 | −0.0099 | 0.47 | +.008 +.010 +.001 −.013 | no | no |
| fix_stop (5 m, 6 s, decel 0) | 0.4313 | +0.0049 | −0.0001 | 0.22 | +.006 +.013 +.007 −.006 | no | no |
| fix_both | 0.4320 | +0.0056 | −0.0074 | 0.47 | +.012 +.023 +.007 −.019 | no | no |

Dev (J03WPY): every control variant was below `shape` (−0.004 to −0.038; without the touch clause −0.038); the stop fix with the deceleration clause (0.5 m/s) was −0.003 and cost macroF1 (0.809 → 0.782, real fouls dropped), so `calm_decel` was set to 0 on dev. Scope deviation from the brief: the "collective deceleration" clause is in the code but off in the named candidate.

**Real match (unsupervised, no GT; `private/review_counts.py`, D runs < 6 s, last sighting > 5 m inside, same team before and after):**

| file | spells | D runs | fake-stoppage count | H↔A turnovers | spells < 2 s |
|---|---|---|---|---|---|
| v1 | 371 | 148 | 19 (QA counted 21 with a looser sighting rule) | 224 | 36 |
| shape (v2) | 398 | 148 | 19 | 251 | 48 |
| fix_ctrl | 325 | 148 | 18 | 178 | 21 |
| fix_stop | 394 | 132 | 4 | 263 | 50 |
| fix_both | 316 | 132 | 4 | 185 | 21 |

`private-sanity` 5/5 PASS for all three. Outputs in `private_out/submission_fix_*`, `private_out/review_counts_*`, `private_out/sanity_fix_*`; `private_out/submission/` untouched.

**Broke:** nothing failing. No typecheck configured. The IDSSE gate does not confirm Fadel's two video findings: the fixes move the real match in the expected direction (19 → 4 fake stoppages, 73 fewer spells) but on CV they are within noise and J03WOY is negative for all three.
**Next:** Fadel decides: v1 or `shape` ships as is (the gate says so), or the stop fix is taken on review evidence alone (disclosed in the report as not CV-validated). If taken: switch the default, `make freeze`, locked test #2, repro.

## 2026-11-16 — v3 candidate `Spec` (possession-spec.md): CV +0.031 vs `shape`, promote yes

**Changed:** branch `v3-spec` (from `v2-review-fixes` 3522949; main and `private_out/submission/` untouched).
- `possession/touch.py`: touches from ball kinematics (local maxima of `ball_dv` ≥ 3 m/s while visible, ≥ 0.24 s apart), assigned to the nearest player's team within 2.5 m, else unassigned.
- `possession/candidates.py`: `RulesSpec(RulesFix)`, defaults = fix_stop + shape. R8: control (10 evidence frames, as v1) decides whether; the switch is placed `lat_f` frames after the first touch of the gaining team's final uninterrupted touch sequence (look-back 3 s, R17), never before it; no touch found (hidden ball) → streak start. A touch sequence without later control never flips (R9/R10). R11 `pre_dead_s`: a switch < 2 s before a stoppage is dropped. R5: restart team = first touch after D. R16 `vanish_out_s`: hidden run starting with the ball heading over a line within 1 s = D from the last sighting. R2/3 `dead_lead_f`: inside-field stoppages start 25 frames earlier (the measured dead-mask onset lag on dev). R6 `restart_lat_f` built but off (hurt on dev; IDSSE goes live at the kick).
- `possession/features.py`: ball x/y and velocity exported. `experiments/spec_calib.py` (dev measurements), `experiments/spec_dev.py` (dev sweep), `experiments/spec_cv.py` (§6b gate, Holm over 4). `private/submission.py`: candidate `spec`. `tests/test_spec.py`: 8 tests; `make test` 104 pass, 1 skipped.
- Registry: 5 rows at 8926185 (split cv, profile fitted, `holm_m` 4; the fix_* rows are re-scores for the 4-candidate Holm budget).

**Calibration on dev J03WPY (fitted profile, 2 seeds, `scratch/out/spec_calib_dev.json`):**
- Touch detector: recall of DFL pass kicks (ball visible) 0.54 at dv 3 (0.60 at dv 2); offset median +1 frame.
- Touch-to-switch latency (GT switch − latest touch of the gaining team within 2 s): median **1 frame** at every bridge c ∈ {0.5, 1, 2} s (q25 0, q75 1). IDSSE flips at the touch; the public window (Fadel, 8:26) shows ~15 frames. Not tuned; `lat_f = 1`.
- No touch of the gaining team within 2 s before ~50 % of GT switches (hidden ball): the shape/streak fallback covers these.
- Dead-mask onset lag: ball near a line median 0; ball inside the field median +25 frames (q75 48) → `dead_lead_f = 25`.
- D end: GT live start − first detected touch after D median −6 frames (IDSSE goes live at the kick); the public window shows +17–25. `restart_lat_f` left off.
- Dev sweep (3 seeds): shape 0.4481, fix_stop 0.4538, Spec default 0.4580, +pre_dead 2 s / vanish 1 s / lead 25 → 0.4810. ctrl_k 15 was higher (0.4845) with 268 spells (under-segmentation risk) → kept 10. ctrl_rel_v hurt.

**CV (§6b: 4 matches, 5 seeds, 3 bridges, fitted profile p_dead 0.3/0.5/0.7, LOMO shape weights; incumbent shape 0.4264):**

| candidate | spell | gain vs shape | min-cell gain | p_holm (m=4) | per-match gain | promote §2e | gate 6b |
|---|---|---|---|---|---|---|---|
| Spec | **0.4569** | +0.0305 | +0.0100 | 0.00 | +.021 +.041 +.038 +.021 | **yes** | yes |
| fix_stop | 0.4313 | +0.0049 | −0.0001 | 0.22 | +.006 +.013 +.007 −.006 | no | no |
| fix_both | 0.4320 | +0.0056 | −0.0074 | 0.47 | | no | no |
| fix_ctrl | 0.4280 | +0.0016 | −0.0099 | 0.47 | | no | no |

Spec vs fix_stop: +0.0256, min-cell +0.0101, all 4 matches positive (+.016 +.029 +.031 +.027).

| bridge c | shape | Spec | gain | min-cell | p_holm | per-match | promote §2e | Spec − fix_stop |
|---|---|---|---|---|---|---|---|---|
| 0.5 s | 0.3975 | 0.4235 | +0.0260 | +0.0100 | 0.00 | +.019 +.034 +.031 +.021 | no (gain < 0.03) | +0.0216 |
| 1 s | 0.4224 | 0.4530 | +0.0306 | +0.0123 | 0.00 | +.021 +.042 +.038 +.022 | yes | +0.0259 |
| 2 s | 0.4593 | 0.4942 | +0.0349 | +0.0138 | 0.00 | +.024 +.049 +.046 +.021 | yes | +0.0293 |

Macro F1 0.8044 (shape 0.7969). Predicted spells 305/match (shape ~330).

**Real match (unsupervised, `private/review_counts.py`):** spells 365 (v1 371, shape 398, fix_stop 394), D runs 135, fake stoppages 4 (shape 19), H↔A turnovers 231 (shape 251), spells < 2 s 36 (shape 48), alive 58.9 min (fix_stop 61.6). `private-sanity` 5/5 PASS. Deterministic: two builds, SHA `3f4c5bb3…`. Outputs `private_out/submission_spec`, `review_counts_submission_spec`, `sanity_spec`.

**Broke:** nothing failing. No typecheck configured. Scope deviations: R12 (keeper) has no explicit rule (Observed carries no keeper flag; a parry followed by control flips under R8, else not). R7 (restart team = team that did not touch last) not used; R5 via the first touch after D. R6 implemented (`restart_lat_f`) but off: IDSSE goes live at the kick, Fadel's public-window read says later; left to IDSSE per the brief. Latency 1 frame per IDSSE, not the ~15 frames seen in the public window (not tuned). Holm over 4 broke harness.promote's 3-candidate assert, so spec_cv.py has its own gate(). The 2026-11-15 fix_* registry rows now have duplicates with `holm_m` 4.
**Next:** Fadel decides: promote Spec (gate passes on all three bridges by §6b; §2e by two of three) → switch default, `make freeze`, locked test #2, repro, public-window format check. Open: whether to add a public-window-derived switch latency (would be tuning) and the R6 restart convention.
