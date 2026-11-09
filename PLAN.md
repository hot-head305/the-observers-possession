# PLAN — More Than a Hack 2027, Phase 1 (spellF1 possession)

Status: **draft for Fadel's review** · written 2026-11-07 · planning session only (no model pipeline built).
Rules source: `vendor/official` @ `f8f2629ff1e0985f81d7e59d8413678514ee1530` (2026-10-23). Where this plan and the official repo disagree, the repo wins.
Evidence lives in `scratch/` (code) and `scratch/out/` (outputs). Every number below is from public docs, external data or synthetic data, and the file it comes from is cited.

---

## 0. Data firewall (built, tested, live)

**Rule.** No competition video, data or extract goes to a hosted LLM. The official FAQ/OVERVIEW extend this to "any videos, datasets … provided in connection with the Competition, or any extracts thereof". Claude never reads, lists, greps, loads, decodes or describes anything under `~/mtah-data`, `local_cache/`, `private_out/` or `Makefile.private`.

**Strictest reading, applied (a deviation from the session prompt, see Decision 1).** The repo's `evaluation/gt/*public*` and `evaluation/results/baseline_*.csv` are datasets provided in connection with the competition. Claude deleted them from its local clone (restore with `git -C vendor/official checkout -- evaluation`) and has not read them. So Step 2b (baseline_raw diagnostics, public-window evaluation) is a **human-run private target** here (§5), not something Claude ran. The prose docs (README, DATA, EVALUATION …) were read: they are MIT documentation, and the numbers quoted from them (17 possessions, 14.2 s, the baseline scores, the lag table) are published text.

**Mechanism.**
- `.claude/settings.json` has a PreToolUse hook on **every** tool (matcher `*`, which also covers MCP file tools like desktop-commander) running `.claude/hooks/firewall.py`, plus `permissions.deny` rules as a second layer.
- The hook blocks (exit 2, fails closed on any error) when any of these is true:
  - the input references the forbidden names (normalised: case-folded, with quotes, backslashes, `-` and `_` stripped);
  - a path resolves (through symlinks) under a forbidden dir;
  - a glob could match one (checked with fnmatch, whether or not the dir exists);
  - a recursive or listing command, or a Grep/Glob, would traverse a directory that contains one (`~`, `/`, and the repo root, since the repo root holds `local_cache/`);
  - a Bash command uses a file whose contents reference the forbidden names, or a `.py` file with a sibling module that does;
  - the command decodes or evals (`base64 -d`, `eval`, `xxd -r`, `bytes.fromhex` …);
  - the command is `make private-*`;
  - a Write/Edit/Bash call would modify `.claude/settings*` or `.claude/hooks/` (tamper guard).
- Write/Edit **content** may mention the names only in `*.md` and `Makefile.private`, which Claude can never read or run.
- `tests/test_firewall.py`: 67 tests, all passing (`make test`). They cover `cat`, `head`, `python -c`, kloppy, `ffmpeg`/`ffprobe`, `$HOME` and case and quote variants, globs, symlinks, sibling modules, `cd`-relative paths, operator-glued words, recursive traversal, decoding, private make targets, MCP read tools, the tamper guard and fail-closed. The test file contains none of the literal names.
- Live check: `echo` of the data dir name is blocked in this session.

**Hole found and fixed today.** Words glued to `;` (e.g. `cat X;`) skipped the file-content scan, so one public file containing a forbidden *name* (the official `.gitignore` mentions an organiser folder) was printed. No data was involved, but it was a real gap. Fixed: the tokenizer now splits on shell operators, and the Bash tamper guard was added. The patch went in through `scratch/tools/patch_fw.py` before the tamper guard existed. **Fadel should review `.claude/hooks/firewall.py`** (Decision 9).

**Known limits (documented, not closed).** It is string- and path-based. It cannot stop the following: a program that builds a path at runtime from innocuous pieces and is not caught by the sibling scan; a `cd` into `~` hidden inside a script; a teammate pasting output into a chat. The real control is procedural. Every match-data computation is a `make private-*` target that writes to `private_out/` and prints only PASS/FAIL. Humans run it, and humans never paste results back to any LLM, including a different AI tool.

**Side effects to know about.**
- `MTAH_DATA_DIR` (the official env var) contains a forbidden name, so official files mentioning it can only be read with the Read tool, and our own code must not use that name. The private Makefile passes paths via `--data/--out` arguments instead.
- Repo-wide `grep -r .` and `Glob **` from the repo root are refused. Use subdirectories.

---

## 1. Problem decomposition and what each part is worth

The GT is mechanical: **D where the corrected tracking marks the ball dead, else the team the corrected tracking names as owner** (CHALLENGE.md). A possession is a maximal H or A run. spellF1 is the F1 of one-to-one temporal-IoU matching, averaged over IoU 0.3–0.7. `X` is forward-filled before matching.

### 1a. Metric mechanics (synthetic, official scorer) — `scratch/out/sensitivity.txt`

Two synthetic GT regimes: "base" (290 poss, 13 s mean) and "short" (480 poss, 7 s mean, close to IDSSE). 8 seeds each. Each row applies one error type to a perfect prediction.

| error type | magnitude | spellF1 base | spellF1 short | macroF1 |
|---|---|---|---|---|
| uniform lag | 1 / 3 / 8 / 25 / 50 frames | 1.00 / .999 / .980 / .819 / .602 | 1.00 / .988 / .903 / .614 / .384 | .997–.82 |
| independent boundary jitter U(±k) | 8 / 25 / 50 | .995 / .938 / .823 | .966 / .812 / .647 | ≥.90 |
| **H/A flicker inside possessions** (5-frame) | 0.5 / 1 / 2 / 5 per alive-min | **.887 / .792 / .647 / .401** | .933 / .870 / .765 / .552 | ≥.98 |
| flicker length 1 vs 25 frames | 1 per min | .792 vs .800 | .869 vs .875 | — |
| spurious D inside possessions (25 f) | 0.5 / 1 / 2 / 5 per min | .933 / .873 / .764 / .545 | .961 / .922 / .852 / .683 | ≥.96 |
| missed stoppage (filled with prev team) | 10 / 25 / 50 / 100 % | .965 / .907 / .812 / .611 | .970 / .927 / .854 / .711 | .97–.53 |
| missed stoppage written as X | 25 / 100 % | same as above | same | better |
| stoppage edges late (alive too early) | 12 / 25 / 50 f each end | .993 / .966 / .904 | .976 / .927 / .852 | — |
| missed direct H↔A switch | 10 / 25 / 50 % | .930 / .826 / .643 | .907 / .769 / .539 | — |
| whole possession wrong team | 5 / 10 / 25 % | .950 / .886 / .706 | .944 / .877 / .682 | — |
| under-segmentation: drop poss < T s | 1 / 2 / 3 / 5 s | .992 / .942 / .880 / .745 | .928 / .788 / .672 / .493 | ≥.91 |
| X over ±w at every transition | 3 / 12 / 25 | .999 / .952 / .828 | .988 / .831 / .628 | — |
| X inside possessions (2 s blocks) | 10 / 30 % of frames | .999 / .999 | .999 / .998 | .97 / .92 |

What this says about where spellF1 is lost:
1. **Spurious splits are the most expensive error per event.** One flicker per alive-minute (≈60 extra spells per match) costs 0.13–0.21. Flicker length barely matters: a 1-frame flicker costs as much as a 25-frame one. **Every decision must be judged by the number of possession boundaries it creates.**
2. Spurious D inside a possession costs about two-thirds of a flicker (it splits but adds no opposite-team spell).
3. **Systematic lag costs much more than symmetric jitter**: lag 25 → .61, jitter ±25 → .81 (short regime). A decoder with a consistent detection delay must be latency-corrected.
4. Under-segmentation (merging short possessions) is cheap only when spells are long. In a 7 s-mean match, swallowing every possession under 2 s costs 0.21. Smoothing to death is not safe.
5. Dead-ball *edges* are cheap (12 f late at each end: −0.007 / −0.024). Missing whole stoppages is moderately expensive (25 % missed: −0.07 to −0.09).
6. **X is free inside possessions and expensive at hand-overs**, confirming EVALUATION.md. X never helps spellF1, so it should be used only where we would otherwise flicker.

### 1b. What the hidden GT probably looks like (docs only) — `scratch/out/calibrate_lag.txt`, `idsse_lag_curve.txt`

- The published lag table (1/3/8/25 f → 1.0000/.9818/.8933/.6539) is reproduced by heavy-tailed possession lengths (lognormal σ≈1.2–1.4) with a mean of about 10–15 s, i.e. **~290–400 possessions** in the match. "1 frame late = 1.0000" implies essentially no spells of ≤5 frames. Weakly identified, and it is not stated whether the table was computed on the full match or the public window. Use it as a prior on the *shape*, not as a target.
- The public window (docs): 17 possessions in 5 min, mean 14.2 s, D 19.6 % of frames.
- IDSSE raw labels give lag1 = .9905 (they have 2.2 % of spells under 0.2 s). The MTAH GT is cleaner than raw DFL possession at the very short end (§2c).
- **We do not fit anything to these numbers.** They come from the GT, and tuning to them is tuning to the public window by another route.

### 1c. Components and their likely share of the loss

| component | what it is | evidence of how much spellF1 it controls |
|---|---|---|
| **possession switching (H↔A segmentation)** | when control passes, without inventing switches during loose balls, deflections and duels | **dominant.** On degraded IDSSE (v1 ball-only degradation; the v2 grid is lower in level, see §2b), baseline ±50 = 0.284. With an oracle for in-play team timing (alive/dead still from baseline) it reaches 0.716. With oracle alive/dead it reaches 0.388. Fixing only the team label of the baseline's own spells reaches 0.396, so the problem is boundary placement and flicker, not team identity. `idsse_oracle_decomp.txt` |
| boundary timing / latency | systematic delay of detected switches | moderate. Lag is ~2× as costly as jitter. Fix by latency calibration on external data |
| live/dead detection | stoppages (ball out, fouls, goals, injuries) | second: +0.10 with an oracle on IDSSE. 23 % of IDSSE possessions end in a stoppage. Missing 25 % of stoppages costs ~0.08 |
| restarts | who restarts after D, and when the ball is live again | edges are cheap. The team after a restart matters, because a D→wrong team error counts as a whole wrong spell (5 % wrong-team spells costs ~0.05). Smart Tagging `Set Pieces` gives the team for most restarts except throw-ins (`N/A`) |
| ball occlusion (41 % graded frames) | no ball: the main cause of flicker in the baseline | the root cause of the first row. Handled by state persistence (HMM/HSMM), team-shape cues (video ball recovery dropped, §3) |

---

## 2. Evaluation design

### 2a. Datasets

| dataset | licence | per-frame labels? | definition match | use |
|---|---|---|---|---|
| **IDSSE** (7 Bundesliga 1/2 matches 2022/23, TRACAB 25 fps, DFL). Mirror `huggingface.co/datasets/pysport/idsse-data`. The figshare original returns an empty 202 bot challenge to scripts | CC-BY 4.0 | **yes:** ball `BallStatus` (1 alive / 0 dead) and `BallPossession` (1 home / 2 away) on every frame. 1,002,644 frames, 0 frame gaps, 0 unknown labels. `BallPossession` names a team on 100 % of dead frames, which matches CHALLENGE.md's note about the corrected tracking | **close:** same construction, "dead flag + owning team" from (operator-corrected) tracking. Mismatch: DFL possession is choppier (437 poss/match, mean 7.2 s, 30 % < 2 s, 2.2 % < 0.2 s) and the D share is higher (44.8 %; a DFL alive flag around restarts is likely stricter). Events XML (passes, set pieces) allows a definition-based relabel | **primary train/dev/test** |
| **Metrica sample-data** Games 1–3 (anonymised; tracking 25 fps; Game 3 in FIFA EPTS like our ATD) | no licence file; README asks for attribution only | no per-frame possession. Human events (PASS 799, RECOVERY 278, BALL LOST 257, BALL OUT 51, SET PIECE 77 in Game 1) let us derive H/A/D | Metrica's own possession-change conventions (BALL LOST / RECOVERY), so closest in *definition*, but event-derived boundaries are coarse (event timing ±0.5 s) | **second-domain test only** (3 matches), never for training model selection |
| **SkillCorner open data** (10 A-League 2024/25 matches, broadcast tracking 10 fps) | MIT | `possession.group` per frame, but **player-control based**: `None` on 45.6 % of frames (loose and dead balls alike), no ball-status flag | poor: no D, no carry-over through loose balls; 6.5 spells/possessed-min. Broadcast extrapolated tracking | **degradation realism only** (broadcast-style ball gaps); not for labels |

Kloppy gotcha: `sportec.load_open_tracking_data` defaults to `only_alive=True`, which silently **drops every dead frame**. Always pass `only_alive=False`. Kloppy also maps `BallPossession != 1` to away; parse the raw XML for labels (as `scratch/external/idsse_profile.py` does). Kloppy's EPTS reader hardcodes `ball_owning_team=None, ball_state=None`, so any extra ball channels in our ATD would be silently dropped (relevant to hypothesis (i)).

### 2b. Degradation to match the published ATD noise

Applied to clean IDSSE. Target values are all published in DATA.md.

| ATD property | target | model |
|---|---|---|
| ball visible | 59.3 % of graded frames | **41 % of all graded frames hidden** (corrected after the red team: v1 used alive frames as the denominator). Stoppages are fully hidden with probability p_dead ∈ {0.3, 0.5, 0.7} (unknown, so it's a grid, not a fit). Alive play gets bursty hidden runs for the rest: hidden runs lognormal (median *g*), visible runs exponential. **Hidden probability rises with ball height Z (IDSSE has Z) and with local crowding**, because DATA.md says the ball goes missing "disproportionately on the frames that matter" |
| gap-length distribution | baseline_raw D-run distribution (private) | default median *g* = 1 s. `make private-degrade-profile` writes the real distribution to `private_out/`, and the training pipeline reads it from there without anyone viewing it. `make private-degrade-check` prints PASS/FAIL per statistic against our default |
| tracked objects | mean 20.5, occasionally > 22 | per-player on/off Markov dropout (camera coverage: players far from the ball drop more), duplicates as a cloned player with +0.3–1 m offset at a low rate |
| slot fragmentation / swaps | 46 slots for 22 players, no identities | new anonymous slot id on every reappearance; occasional swap of two nearby same-team slots; rare cross-team mislabel (a slot following an opponent) |
| ball false positives | unknown | outlier ball positions at a low rate (heads, lines). Exact rate unmatchable |
| position noise | unknown | Gaussian 0.2–0.5 m on players, 0.5–1 m on the ball |

**Can't be matched:** the tactical camera's real coverage pattern; Metrica tracker-specific failure modes; the exact correlation between ball loss and events; Barcelona's possession style (long spells, high possession share); the GT definition gap (§2c); the 2nd-half graded pre-kickoff D block (2,934 frames, trivial to hard-code from the published half table, which is allowed because it's published).

**Transfer consistency check (post-hoc, not validation)** — `scratch/out/idsse_baseline_transfer_v2.txt` (v1 is superseded; see §10).
- Setup: the *official* baseline (nearest player + majority vote), run on degraded IDSSE and scored with the official scorer against IDSSE labels.
- Degradation fixed a priori from DATA.md: 41 % of graded frames without a ball, ~7 % of players missing. A 3×3 grid over the two unknowns (gap median *g*, p_dead), 7 matches × 3 seeds.

| window | 0 | ±25 | ±50 | ±125 |
|---|---|---|---|---|
| published, BAR-ATH | 0.0486 | 0.1996 | **0.2433** | 0.2242 |
| degraded IDSSE, range over the 9 grid cells | 0.013–0.091 | 0.144–0.250 | **0.198–0.282** | 0.195–0.215 |
| clean IDSSE (no degradation, control) | 0.098 | 0.296 | 0.308 | 0.218 |

What it shows:
- ±50 is the argmax in **all 9** degraded cells, and the published level lies inside the band. The *shape* of this method family's behaviour transfers.
- The *level* is only bracketed, with ±0.04 of uncertainty driven by unknowns that `private-degrade-profile` will pin down.
- It says nothing about whether a *learned* model transfers.
- The published curve was computed on the private GT, so it is used **only** as this report-only check. No parameter was chosen by comparing against it, and the full grid is reported.

### 2c. Label definition bridge (IDSSE → challenge GT)

Without a bridge, models trained on raw DFL labels will over-segment relative to a GT that appears to have no ≤5-frame spells. Bridge **from the written definition, not from GT statistics** (CHALLENGE.md: a touch, deflection or aerial duel without control does not change possession; "a player keeps the ball for a few seconds" / "more than two consecutive passes"). Rule: a possession by team T that lasts < *c* seconds **and** contains no completed pass by T (from IDSSE events) is absorbed into the previous team. *c* ∈ {0.5, 1, 2} s; the grid comes from the text's "a few seconds" and does not depend on any GT number.
- **D predecessor:** a spell that follows D is never absorbed. CHALLENGE.md says that "whenever play restarts … there is a clear possessor", so the restart team owns it.
- Promotion must hold for **all three** values (§2e), so *c* is never picked.
- `idsse_lag_curve.txt` shows how much the label definition moves the metric. It is report-only and was not used to set the grid.

### 2d. Split

Match-level, both halves of a match always together.
- **Train:** 4 IDSSE matches (J03WMX, J03WN1, J03WOH, J03WOY), with 4-fold leave-one-match-out CV inside them.
- **Dev:** 1 IDSSE match (J03WPY), for early stopping and hyper-search **only**, never for promotion.
- **Locked test:** 2 IDSSE matches (J03WQQ, J03WR9) **plus** the 3 Metrica games. **Run exactly once**, on Nov 13, on the single frozen candidate, with its config hash pre-registered in the registry on Nov 12. It reports the expected level; it never chooses.
- Degradation is re-sampled with **5 seeds per match**, averaged *within* the match. Seeds are not bootstrap units, so the sample size stays the number of matches.
- Caveat: 4 of the 7 IDSSE matches feature Fortuna Düsseldorf (home). A cross-team generalisation check holds out all Düsseldorf matches once.

### 2e. Promotion rule

Candidate B replaces incumbent A only if **all** hold:
1. On the 4 leave-one-match-out CV folds (dev excluded): mean spellF1 gain ≥ **0.03**, with a paired block bootstrap over **matches** (seed-averaged) giving P(gain > 0) ≥ 0.9.
2. **At most 3 candidates per gate**, with Holm correction across them. The decoder grid search happens on dev *before* a candidate is named.
3. It holds under all three label bridges *c* ∈ {0.5, 1, 2} and across the 3×3 degradation grid, i.e. no sign flip in any cell.
4. Predicted possessions per alive-minute within the IDSSE range after the bridge (no over-segmentation drift).
5. `make private-sanity` returns PASS on the match. This is unsupervised: validity, a possession count within a broad prior band, and no spell across halftime. The **Smart-Tagging agreement criterion is dropped for any candidate that consumes Smart Tagging**, so the gate is never circular.
6. Determinism: `make private-repro` returns PASS.

The **public window is never part of promotion.** `make private-public-check` (§5) runs **once in total**, on the frozen candidate (Nov 13). It is a format/alignment PASS/FAIL. On FAIL, only index or format bugs may be changed, never latency, thresholds or model.

### 2f. Experiment registry

`experiments/registry.jsonl`, append-only, one line per run: git SHA, config hash, data versions (IDSSE file SHAs), seeds, CV/dev/test scores with bootstrap intervals, possession stats, wall time, who ran it. Locked-test lines are written only by `make locked-test`, which refuses a repeat. Only external-data results are ever logged. Private results stay in `private_out/` on the runner's machine.

### 2g. How far external scores transfer

- **Ordering of methods within a family: moderately trusted** (the baseline curve transferred with the right argmax).
- **Absolute level: not trusted** (±0.04 for the baseline family; probably worse for learned models).
- Expected sources of shortfall on the real match:
  - definition mismatch (§2c);
  - tracker artefacts we can't simulate;
  - team style (Barcelona long spells; this *raises* spellF1 for a persistent decoder);
  - SPELL_NOISE_BAND = 0.04 on the full match.
- Rule of thumb: treat an external gain below 0.03 as noise for the real match, and prefer robust, structurally simple gains (fewer spurious splits) over gains that rely on fine-grained emissions.

---

## 3. Approach portfolio (ranked)

Floor: 0.2433.
- Expected values are on degraded IDSSE (baseline ±50 = 0.20–0.28 across the grid).
- **No prototype exists yet.** The oracle bounds (team timing 0.716, dead 0.388) are *headroom under perfect information*, not achievable gains, so the ranges below were revised down after the red team (§10).
- **Real-match projection:** subtract ~0.0–0.05 for definition gap and tracker artefacts. A realistic target for #1+#2+#3 on the real match is **0.30–0.40**; anything above that is upside.
- Hours are team-hours.

| rank | approach | hypothesis | expected spellF1 (degraded IDSSE) | cost | risk | data dependency |
|---|---|---|---|---|---|---|
| **1** | **3-state HSMM/Viterbi with evidence-dependent switch costs** (H, A, D states; switch cost lowered when the ball is near an opponent, ball speed jumps, or team-shape changes; explicit duration priors) | most baseline loss is spurious splits from occlusion. A persistent state model with costly switches removes them, and the oracle shows ~+0.4 headroom in switching | 0.30–0.40 | 20 h | low–med: hand-set emissions may be weak; mitigated by #2 | ATD only + IDSSE for priors and cost fitting |
| **2** | **Factorised GBM emissions** (alive/dead and owner models, LightGBM on window features from team aggregates: centroids, compactness, speeds, ball-relative distances, ball visibility, nearest-player margins, time since ball seen), trained on degraded IDSSE and decoded by #1 | learned emissions beat hand-set ones, and team-level features survive slot fragmentation | +0.00–0.06 over #1 (stretch) | 24 h | med: domain shift; determinism of GBM (pin, single thread, quantised features) | IDSSE train; ATD at inference |
| **3** | **Smart Tagging fusion** (set-piece intervals as D anchors and restart team; phase team tags as a soft owner prior in emissions) | algorithmic tags are free evidence for restarts and owner; most useful where the ball is unseen | +0.00–0.04 | 8 h | med: tags are noisy, and throw-ins are `N/A`. **No external analogue to validate on.** It ships only as a hard restart anchor, with its weight fixed in advance from the definition ("every set piece is a restart"); gate 5 drops its own Smart-Tagging criterion for it | Smart Tagging (match only) |
| **4** | **Rule/geometry state machine** (possession = sustained proximity with hysteresis, dead = ball out of bounds / ball unseen + players slow + regroup) | interpretable, fast, a strong fallback | 0.25–0.35 | 10 h | low | ATD only |
| 5 | **Self-training on the match** (pseudo-labels from #1/#2 on confident frames, retrain emissions; algorithmic, no human decision) | adapts emissions to the Metrica tracker's noise | +0–0.04 | 10 h | med: confirmation bias; no external way to validate it as-is (simulate with IDSSE → Metrica-sample transfer) | ATD |
| 6 | **Tactical-video ball recovery** (pretrained ball detector on the tactical video for frames with no ATD ball, mapped to pitch via the per-frame homography) | ~41 % ball gaps are the root cause; recovering even a third of them cuts flicker | ~0 within schedule | 30 h + compute | **dropped.** Detector inference on MPS/GPU plus video decode is unlikely to be byte-identical across machines (RULES §3). Committed per-frame detections would be a "frame-level tracking export" (RULES data section). Debugging on the provided video invites frame-tied constants (rule 1) | tactical video + homography |
| 7 | **Broadcast alignment** (align broadcast ATD to tactical by matching player configurations, use broadcast ball where tactical is missing) | broadcast sees the ball on 50.5 % of *its* frames, partly on different moments | +0.01–0.05 | 20 h | high: cuts, replays, 34 % unusable homography | broadcast ATD + homography |
| 8 | **Sequence NN (TCN/GRU) on team aggregates + CRF decoding** | end-to-end might find cues the GBM misses | ±0.05 vs #2 | 24 h | high: data hungry (7 matches), more domain shift | IDSSE |

**Recommended path:** #4 rule machine (also the first repro test, Nov 9) → **#1 HSMM as the core** → #3 restart anchors. #2 GBM emissions are a stretch goal, promoted only if they clear §2e by Nov 12. #6 and #7 are dropped; #8 is dropped unless #1 stalls. Reasoning: the evidence says the money is in not inventing switches (§1a, §1c), which is exactly what a persistent decoder with good switch costs delivers, and that family's behaviour transferred from IDSSE to the match (§2b).

---

## 4. Hypotheses to test, not assume

**(i) The ATD metadata may expose extra ball channels (owner / alive).** Motivation: CHALLENGE.md says "the tracking names a team even while the ball is out of play". Metrica's public EPTS sample (Game 3) declares only ball `x, y`. The baseline parses at least 3 comma fields per ball group, and kloppy would silently drop extras. **Test:** `make private-meta` parses `DataFormatSpecification`, counts ball channels and the comma-fields per ball group on the first 1000 raw lines, and auto-detects categorical columns. Output (PASS/FAIL lines only):
- `H1a ball channels beyond x,y,z,speed declared`
- `H1b a ball field is categorical with ≤3 values`
- `H1c that field changes ≤ 1x per 5 s`

Detail goes to `private_out/meta.json`. **Decision:** on PASS, the pipeline gets a generic `extra_ball_channels` input. The parser auto-maps by code (values, not names), so nobody has to tell Claude the channel names, and it becomes a top-ranked emission feature validated by private-sanity. Rules check: using such a channel is "an algorithm reading the provided data", not human-produced data; it is the *automatic* tracking's own output. Still note it in the report. On FAIL, nothing changes.

**(ii) H/A flicker, not dead-ball detection, drives most baseline loss.** External evidence **supports** it (§1c: switching oracle +0.43, dead oracle +0.10 on degraded IDSSE). Remaining test on the match without GT: `make private-baseline-diag`. On the regenerated baseline_raw/smooth50 it computes: spells shorter than 1 s; share of H/A changes not adjacent to D; D-run length distribution; graded-frame D share. PASS/FAIL against "flicker-dominated" thresholds fixed in advance (e.g. PASS if > 50 % of spell boundaries are direct H↔A within 2 s of another boundary). Informs whether week-2 effort goes to switching (#1/#2) or dead-ball detection.

**(iii) Calibrating possession count and duration priors from external data improves spellF1.** Test on external data only. Run HSMM with lognormal duration priors fitted on train-fold IDSSE (raw: mean 7.8 s, σ 1.23; stoppages median 19.6 s) against HMM with geometric durations, under all three label bridges. Then a **misspecification test**: fit priors under one bridge, evaluate under another. Promote only if the gain survives misspecification (§2e-3), because the real GT's durations are unknown and look coarser than DFL's. Never calibrate priors to the public-window stats or the lag table.

---

## 5. Private-data diagnostics (human-run, PASS/FAIL only)

All live in `Makefile.private` (gitignored), created by Fadel from the template below. The scripts in `private/` take `--data DIR --out DIR` and contain no paths, so Claude can write and unit-test them on synthetic fixtures. Each writes detail to `private_out/<target>/` and prints only PASS/FAIL lines with fixed thresholds. **Run by humans, read by humans, never pasted into any LLM.**

| target | computes | informs |
|---|---|---|
| `private-meta` | ATD XML channel spec; ball field count/categoricals (H1a–c) | hypothesis (i) |
| `private-align` | ATD 199,319 records numbered from 1, homography rows, Smart Tagging kickoffs contain 11185 / 113742 (the official checks) | pipeline correctness |
| `private-fallback` | regenerates baseline_smooth50 via the official `starter/baseline.py`, validates it, copies it to `private_out/submission_fallback.csv`; PASS if valid and its SHA equals the official committed baseline's SHA | **fallback always ready** from day 1 |
| `private-baseline-diag` | (ii) statistics above; D-run distribution | hypothesis (ii) |
| `private-degrade-profile` / `-check` | real ball visible/hidden run-length distributions, objects per frame, slot lifetimes, duplicate rate → `private_out/degrade_profile.json`; check = PASS/FAIL per statistic vs our default degradation (KS < 0.1) | degradation realism; training can consume the profile |
| `private-sanity CAND=...` | validity; possessions/alive-min within the IDSSE-bridged band; no spell crosses halftime; the pre-kickoff 2nd-half block is D; Smart-Tagging restart agreement ≥ fixed floor **only for candidates that don't consume Smart Tagging** | promotion gate 5 |
| `private-public-check CAND=...` | official evaluator on the public window, **once in total**, on the frozen candidate. PASS = the file validates and spellF1 ≥ 0.15 (a vacuous floor: it only catches a broken index or mapping) | format/alignment only. On FAIL, fix only index or format bugs |
| `private-repro` | builds twice (fresh venv, plus docker linux/amd64), compares SHA-256. **First run Nov 9 on #4**, again at the freeze | determinism gate |
| `private-submit-check` | `validate_submission.py` on the exact upload file; prints its SHA | final upload |

**Relay protocol: what may reach Claude.** Even a PASS/FAIL bit about the match is arguably an "extract" under the strictest reading (red-team finding 7). So:
- **Claude never receives private outcomes, not even PASS/FAIL.**
- Claude builds every branch that a private result could select, behind flags or auto-detection in code:
  - extra ball channels auto-detected and used if present;
  - the degradation profile read from file if present, default otherwise;
  - each candidate kept runnable.
- Humans run the gates and choose which pre-built branch ships.
- Task instructions to Claude are about *external* work only ("improve #1 on CV"), never "#1 failed the sanity check".

Template (Fadel types this himself; paths stay on his machine):

```make
DATA := $(HOME)/mtah-data
OUT  := private_out
PY   := uv run python -I
private-meta: ; $(PY) private/meta.py --data $(DATA) --out $(OUT)/meta
private-fallback: ; $(PY) private/fallback.py --data $(DATA) --out $(OUT)/fallback
# ...one line per target in the table above
```

---

## 6. Schedule (Nov 7 – Nov 16; submit Nov 16, deadline Nov 17)

Roles:
- **F** = Fadel: lead, private runner, submission.
- **B** = member 2: decoder.
- **C** = member 3: data, degradation, features, report.
- **Backup private runner:** C. Each person runs private targets on their own machine. Nobody pastes private output into any AI tool.
- Claude codes external-data work for B and C (loaders, degradation, harness, decoder) and never touches private outputs.

| day | F | B | C | gate (end of day) |
|---|---|---|---|---|
| Sat 7 | review this plan, decisions §9, create `Makefile.private` | — | — | plan approved |
| Sun 8 | `private-align`, `private-fallback`, `private-meta` | IDSSE loaders, labels, bridge, metric harness | degradation module (ball + players + slots) + tests; registry | **fallback file exists** |
| Mon 9 | `private-baseline-diag`, `private-degrade-profile`; **`private-repro` on #4** | #4 rule machine | degradation grid; Metrica-sample harness | #4 beats baseline on CV; repro PASS |
| Tue 10 | **submit the fallback via the form as soon as the URL arrives** (editable; SUBMISSION.md) | #1 HSMM decoder | Smart Tagging restart anchors #3 | **G1 (CV only):** #1 vs #4 |
| Wed 11 | `private-sanity` on #1 | #1 duration priors (hyp. iii), latency calibration | #2 GBM emissions (stretch) | — |
| Thu 12 | `private-sanity` on the best; pre-register the frozen config | X policy (measure the macroF1 cost too), bug fixes | #2 if it clears §2e; report draft | **G2 (CV only):** promote, then pre-register |
| Fri 13 | **FREEZE** (no output-changing work after this); `private-repro`; `private-public-check` once | locked test once | report | **G3:** locked test (report-only); frozen + fallback both valid |
| Sat 14 | repro on a clean machine; update the form submission | bug fixes only (format/index) | report | repro PASS twice |
| Sun 15 | report review | — | — | report final |
| Mon 16 | `private-submit-check`; **F submits the final** (team-named csv + pdf + repo URL) | — | — | submitted, receipt saved |

After the freeze: only format or index bug fixes. If any gate fails on Nov 13, ship the last promoted candidate. If none was promoted, ship the fallback, which is already in the form.

---

## 7. Reproducibility and release

- `uv` with Python 3.11 pinned, `uv.lock` committed; numpy/pandas/kloppy/lightgbm pinned exactly.
- Determinism:
  - fixed seeds;
  - `OMP_NUM_THREADS=1` and LightGBM `deterministic=True, num_threads=1`;
  - features rounded to 1e-4 before the model, so cross-CPU last-ulp differences cannot flip a split;
  - integer-scaled Viterbi scores with a fixed tie-break;
  - no dict-order or set-order dependence.
- The committed model artifact (trained on IDSSE only, CC-BY, attributed) and its SHA are in the repo. `make submission` = inference only. `make train` retrains bit-identically on the reference platform.
- Two-build check: `private-repro` builds in a fresh clone + fresh venv on macOS arm64 **and** in `docker --platform linux/amd64`. The output SHA-256 must match the uploaded file's.
- Public repo hygiene:
  - `.gitignore` covers data, `local_cache/`, `private_out/`, `Makefile.private` and `*.csv` outside tests;
  - a pre-commit hook plus a CI check reject `*.mp4`, any CSV with > 1,000 rows, any file > 5 MB, and frame-level exports;
  - the submission CSV is **not** committed (it is labels for the match).
- Technical report outline (≤ 5 pages):
  1. Approach and why: the evidence from §1–2.
  2. Assets used and dropped: video and broadcast, if dropped.
  3. Training data: IDSSE (DFL via Bassek et al. 2025, CC-BY 4.0, labels are DFL ball status/possession, 7 matches); the Metrica sample games used for testing only; no labels on the provided match. Disclosed explicitly if used: the degradation profile computed from the match's own ATD (unsupervised, kept out of the public repo, regenerated by code) and any pseudo-label self-training.
  4. Possession rules: loose balls carry the last team; the control threshold; restarts.
  5. Handling missing ball and noisy tracking.
  6. Limitations.
  7. Reproduction commands.
  8. Statement on LLM use: Claude used for code on public/external data only; it never accessed match data.

---

## 8. Risk register

| risk | likelihood | impact | mitigation |
|---|---|---|---|
| External→match transfer fails for learned emissions | med | high | the transfer check covers the baseline only; prefer the structural decoder (#1); private-sanity gates; keep #4 as fallback |
| Label-definition gap (DFL choppier than GT) | high | med | bridge from the written definition; promote only if robust to all *c* |
| Over-fitting to the public window, or to GT-derived published numbers | med | high (rules + wrong choice) | public check once in total; published curves report-only; bridge grid from the definition text |
| Match information reaching Claude through gate results | med | breach of strict reading | relay protocol (§5): no private outcome is ever relayed; all branches pre-built |
| Rule breach: human decisions tied to specific match frames (e.g. "fix the kickoff at frame N") | low | disqualifying | only published constants (half table, row count); code review checklist item |
| Firewall bypass / accidental data paste into an LLM | low | breach of terms | hook + deny rules + procedure; team briefing; private outputs never leave the machine |
| Non-reproducible output across machines | med | disqualifying for winners | determinism rules; two-platform SHA check from Nov 9 (#4) |
| B overloaded (single point of failure on the decoder) | med | high | #2 is stretch, owned by C; #4 fallback by Nov 9 |
| IDSSE Düsseldorf bias (4/7 matches) | med | low–med | cross-team hold-out check |
| Team of 3 → eligibility | — | low | 3 meets the 3–5 rule |
| Upload mistakes (wrong file, name, Google account) | low | fatal | `private-submit-check` on the exact file; name `<team_name>.csv/.pdf`; test the form access Nov 14 |
| SPELL_NOISE_BAND 0.04: a "better" model is not better | high | med | promotion needs ≥ 0.03 CV gain, a match-level bootstrap, Holm correction over ≤ 3 candidates, and robustness across the grid |

---

## 9. DECISIONS FOR FADEL

**2026-11-07: Fadel approved all recommendations below.**
- Team name: **The Observers**. Upload files are `The_Observers.csv` and `The_Observers.pdf`; I chose the underscore over a space so the files work in scripts.
- Roles: Fadel currently holds F, B and C. Claude covers the external-data coding.
- Solo-mode schedule cut: approach #2 (GBM emissions) is dropped; the core is #4 → #1 → #3. The Nov 9 repro check, the early fallback submission and the freeze dates are unchanged. There is no backup private runner until other members join.
- Eligibility (RULES.md): teams need 3–5 members. Fewer than 3 means no Innovation Challenge or Final Pitch, but the ranking still counts.
- The bundle check shows both videos missing (non-blocking; the video is needed only for decision 6).

1. **Strictest reading covers the repo's public GT/baseline CSVs.** I didn't read them and turned Step 2b into private targets. *Recommend: keep* (FAQ: "any datasets … or extracts thereof").
2. **May the degradation profile computed from the match ATD (`private_out/degrade_profile.json`) feed training without anyone viewing it?** *Recommend: yes.* It's unsupervised use of the provided data, which the rules allow.
3. **If H1 passes (extra ball channels), use them?** *Recommend: yes*, auto-mapped by code, disclosed in the report. Nobody tells Claude channel names or values.
4. **Public-window check: once in total, on the frozen candidate, format/alignment only.** *Recommend: yes.*
5. **Relay protocol (§5): no private outcome, not even PASS/FAIL, ever reaches Claude; all branches pre-built.** *Recommend: yes.* It's the only reading consistent with Decision 1.
6. **Qualitative read of the public GT against the video** (CHALLENGE.md calls it "the reference"). *Recommend: you alone do it once, write only general definitional notes (no frames, no constants), and do **not** relay them to Claude*; any resulting code change is written by a human. Alternative discarded: skipping it, which leaves the definition gap (D share 45 % in IDSSE vs 20 % in the public window) unexamined.
7. **Drop video ball recovery (#6) and broadcast alignment (#7).** *Recommend: drop both* (reproducibility and frame-tied-debugging risk).
8. **Submit the fallback in the form as soon as the URL arrives, then edit it** (it counts as "sending as you" under INTENT.md, so it's your yes). *Recommend: yes.* Confirm the team name for the file names.
9. **Team roles:** F lead/private runner, B decoder, C data/report and backup runner. *Recommend as written;* assign the names.
10. **Metrica sample-data has no formal licence.** *Recommend: test-only, attributed.*
11. **Review the firewall patch** (`.claude/hooks/firewall.py`, today's operator-tokenizer fix and tamper guard). Optionally add the deleted vendor CSV paths to `permissions.deny` yourself; the tamper guard stops me editing it.
12. **Asking the organisers** (red-team finding 7). You ruled this out, so I won't recommend it. Every near-line choice above is therefore resolved toward the strictest option.

---

## 10. Red team: critique and responses

An independent subagent attacked the v1 plan (rules, leakage, gains, schedule). Its findings in short, with my response (✔ = accepted and plan changed):

1. **Critical. Transfer check mis-calibrated and overclaimed.** v1 hid 41 % of *alive* frames plus 80 % of stoppages (≈ 58 % total), degraded only the ball, ran one seed, had a crashing control, and had parameters eyeballed against the GT-derived target. ✔ Re-run as v2:
   - 41 % of graded frames hidden, player dropout added, 3 seeds, working clean control;
   - a fixed 3×3 grid over the unknowns, all reported;
   - it is now framed as a post-hoc consistency check.

   The result still holds in weaker form: ±50 is the argmax in 9/9 cells and the published level sits inside the band 0.198–0.282.
2. **Critical. Video ball recovery (#6) conflicts with byte-identical regeneration and invites frame-tied debugging.** ✔ Dropped.
3. **Major. Locked test used for selection at three gates.** ✔ One run, Nov 13, pre-registered config, report-only.
4. **Major. Pseudo-replication (seeds as bootstrap units), dev double use, multiple comparisons, 0.02 vs 0.03 inconsistency.** ✔ Match-level bootstrap on CV only; ≤ 3 candidates per gate with Holm; threshold 0.03.
5. **Major. GT-derived published numbers (lag table, baseline curve, public-window stats) shape the plan.** ✔ Partly:
   - the bridge grid is now justified from the definition text;
   - published curves are report-only;
   - the synthetic sensitivity regimes stay, because they describe the *scorer*, not a model, but they are labelled as such.

   Not accepted: removing them entirely. Understanding the metric's response to errors is not tuning a submission.
6. **Major. The plan ignores the public GT as the official definitional reference.** ✔ Partly, as Decision 6: Fadel does a human-only qualitative read, and nothing is relayed to Claude.
7. **Major. No protocol for match-derived information reaching Claude; near-line questions not asked.** ✔ Relay protocol added (§5). Asking the organisers is excluded by Fadel's instruction (Decision 12).
8. **Major. Smart Tagging fusion validated in a circle.** ✔ The criterion is dropped for Smart-Tagging candidates; #3 ships as a fixed-weight restart anchor.
9. **Major. Gain estimates are headroom, not achievable gains.** ✔ Ranges revised down (#1 0.30–0.40, #4 0.25–0.35, #2 +0–0.06, #6 ~0), with a real-match projection of 0.30–0.40.
10. **Major. Schedule infeasible (B ~60 h), freeze contradicted by post-freeze latency/X work, repro check too late.** ✔
    - #2 moved to stretch under C;
    - latency and X work moved to Nov 11–12;
    - repro check on #4 Nov 9;
    - fallback submitted early;
    - backup runner named.
11. **Minor. Public check repeated and vacuous; its shift criterion invites tuning.** ✔ Once in total; shift criterion removed.
12. **Minor. The "base" sensitivity regime doesn't match the lag-table calibration.** ✔ Added a "heavy" regime (mean 9.5 s, σ 1.2, lag25 = 0.657 vs published 0.654). Its error costs:
    - flicker 1/min: −0.17;
    - spurious D 1/min: −0.10;
    - 25 % stoppages missed: −0.08;
    - 10 % switches missed: −0.08;
    - jitter ±25: −0.17 vs lag 25: −0.34.

    The conclusions in §1a are unchanged.
13. **Minor. "Trained on IDSSE only" contradicts using the match-derived degradation profile and self-training.** ✔ Disclosure added to the report outline (§7).
14. **Minor. Bridge D-predecessor unspecified; X's macroF1 cost ignored; greedy same-team matching not modelled.** ✔
    - D predecessor specified (§2c);
    - the X policy must report its macroF1 delta (tie-break) on Nov 12;
    - the matching subtlety goes into the Sunday metric harness as a test case.
