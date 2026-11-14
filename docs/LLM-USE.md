# Use of AI on the competition data

- **2026-11-14:** Fadel asked the organisers whether an AI assistant may be used on the competition
  data. Per Fadel, the answer was yes, and they recommended it.
- **Not in writing.** The answer is informal. There is no written text to quote.
- **Effect:** the data firewall (PLAN.md §0) was lifted the same day. Claude then ran
  `private-sanity`, `private-repro` and `make submission` on the match data, after the config freeze
  (hash `4185e57a0bad`) and the one-shot locked test. No model change followed.
