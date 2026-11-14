# The Observers: possession from automatic tracking

More Than a Hack 2027, Phase 1. Final, 2026-11-14. Config frozen at hash `4185e57a0bad`.

## 1. Approach

Every frame of the tactical video gets H, A or D from the provided automatic tracking (ATD) alone,
by a rule-based state machine (`possession/candidates.py`, `Rules`). There is no learned model and no
training on the provided game.

1. **Features per frame** (`possession/features.py`):
   - Ball and player positions in metres, smoothed over ±2 frames.
   - Nearest home and nearest away player to the visible ball.
   - Ball speed and mean player speed, from displacements over ±0.5 s.
   - How far the ball is beyond a line.
   - How long the ball has been unseen.
2. **Stoppages:** the ball is out of play when it is more than 0.5 m beyond a line, or when the ball
   and the players are both slow. A ball unseen for 4 s with slow players also counts. Stoppages
   shorter than 2 s are dropped; alive blips under 3 s inside a stoppage are absorbed.
3. **Control evidence:** a team has the ball on a frame when its nearest player is within 1.5 m and
   at least 0.5 m nearer than the nearest opponent.
4. **Possession switches** need 10 frames of evidence for the other team, with no evidence for the
   holder in between. The switch is placed at the first of those frames, so a loose ball in between
   still belongs to the previous team.
5. **Restarts:** after a stoppage, the first team with control evidence owns the restart.

Why rules rather than a model: on our evaluation data, spellF1 is lost mostly to spurious switches
(see 6). A persistent state machine that switches only on sustained evidence removes most of them.
Two decoders tried and dropped are in section 2.

## 2. Assets used and dropped

| asset | use |
|---|---|
| tactical ATD (raw + metadata) | the only input to the labels |
| `games.py` half blocks and the published second-half kickoff | frame layout; the graded pre-kickoff block is D |
| Smart Tagging | not an input. Used only in our own unsupervised sanity check (restart agreement) |
| homography, videos, broadcast ATD | dropped: no reproducible gain within the schedule; video ball detection risks non-determinism across machines |

Tried and dropped, both on the development match, before any cross-validation:

| decoder | dev spellF1 | rules |
|---|---|---|
| 3-state HMM / Viterbi, naive-Bayes emissions | 0.43 | 0.49 |
| optimal (Viterbi) segmentation of the rule evidence | 0.45 | 0.49 |

## 3. Training and evaluation data

- **No labels from the provided game**, no hand labels, no human-produced data about it.
- The public five-minute window was not used for tuning or selection.
- **IDSSE** (Bassek et al. 2025, DFL/TRACAB, CC-BY 4.0): 7 Bundesliga matches, 25 fps. The labels
  are DFL's per-frame `BallStatus` and `BallPossession`, produced by DFL. Mirror:
  huggingface.co/datasets/pysport/idsse-data.
  - Split by match: 4 cross-validation, 1 development (all parameter choices), 2 locked test.
- **Degradation** to resemble the provided tracking (`possession/degrade.py`), with targets from
  the published DATA.md:
  - ball hidden on 41 % of frames, in bursts, more often when it is in the air or play is dead;
  - ~20.5 of 22 players tracked;
  - anonymous slots that fragment;
  - cross-team fragments, duplicates, position noise.

  IDSSE freezes the ball position on every dead frame, which would hand the dead-ball label to
  any model. We replace it with a stoppage trajectory: the ball rolls out, is carried by the
  restart taker, then is placed.
- **Label bridge** from DFL possession to the challenge's controlled possession: a spell shorter
  than *c* with no completed pass is absorbed into the previous team. A spell after a stoppage is
  never absorbed. Every result holds for all *c* ∈ {0.5, 1, 2} s.

## 4. Possession rules implemented

- **Loose balls, deflections and challenges** carry the last team until the other team shows
  sustained control (10 frames within 1.5 m and clearly nearest).
- **Restarts** belong to the first team in control after the stoppage.
- **Before the second-half kickoff** the graded frames are D.
- **Outside the halves** the frames are X.

## 5. Results (external data only)

Official scorer, degraded IDSSE. Each score is the mean over 4 CV matches × 9 degradation settings
× 5 seeds × 3 label bridges.

| | spellF1 | macroF1 |
|---|---|---|
| official baseline (±50 majority vote) | 0.251 | 0.595 |
| **ours** | **0.446** | 0.80 |

- The gain is positive in every match and every degradation × bridge cell (minimum +0.15).
- Locked test, run once after the freeze (config hash `4185e57a0bad`) on the 2 held-out IDSSE
  matches, same grid: baseline 0.259 / 0.616, ours **0.442** / 0.809. Gain +0.183, positive in
  every cell (minimum +0.15); per match 0.447 and 0.438. It matches the CV level, so the
  parameter choices did not overfit the CV and dev matches.
- Under harsher tracking (4× fragmentation, 50 % ball hidden, 15 % dropout, 2× position noise,
  5 % cross-team fragments, other stoppage-ball behaviour) the gain stays between +0.18 and +0.22.
  The smallest per-match gain is +0.12 (`experiments/stress.py`).
- The official baseline scores 0.243 on the real match, inside our band for the baseline
  (0.20–0.28). The absolute level on the real match is still uncertain by several hundredths.

## 6. Limitations

- **Stoppage detection** relies on slow ball plus slow players. Quick restarts, and stoppages where
  players keep running, are missed.
- **The degradation is a model.** The real tracker's failure patterns are not reproduced exactly.
- **Contested balls:** with the ball unseen for long stretches, a turnover is placed at the next
  visible control, which can be late.
- **With more time:** learned emissions on team-shape features, and recovering the ball from the
  tactical video.

## 7. Reproduction

```
git clone --recurse-submodules <this repository>
cd <repository>
uv sync --frozen
make submission DATA=/path/to/unpacked/bundle OUT=out
```

This writes `out/The_Observers.csv`. The build is deterministic: a fresh clone in a fresh
environment reproduces the file byte for byte. `make test` runs the test suite; `make cv`
reproduces the evaluation in section 5 after `make idsse-download`.

## 8. Use of AI tools

- **Code.** Code and documentation were written with an AI coding assistant (Claude, Anthropic).
- **Until 2026-11-14:** the assistant worked on public and external data only (IDSSE, synthetic data,
  the official documentation). It had no access to the provided match data, by a technical block and
  by procedure. A team member ran every computation on the match and did not share the results
  with the assistant.
- **From 2026-11-14:** we asked the organisers, and they allowed AI use on the competition data
  (`docs/LLM-USE.md`). From then on the assistant also ran our checks on the match data: the sanity
  checks, the reproducibility check and the submission build. This was after the config freeze and
  the locked test. No model, rule or parameter choice used a result from the match data.
