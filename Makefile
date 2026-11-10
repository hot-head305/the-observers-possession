.PHONY: test firewall-test cv freeze locked-test check-repo submission evidence sensitivity idsse-download idsse-profile idsse-transfer

PY := uv run python -I

test:
	uv run python -m pytest -q tests

firewall-test:
	uv run python -m pytest -q tests/test_firewall.py

# CV gate on degraded IDSSE (external data only); appends to experiments/registry.jsonl.
cv:
	uv run python experiments/run_cv.py

# Nov 13: record the submitted config hash, then score it once on the 2 locked IDSSE test matches.
freeze:
	uv run python experiments/locked_test.py freeze

locked-test:
	uv run python experiments/locked_test.py run

# Refuse data-like files among tracked files (videos, archives, big CSVs, > 5 MB).
check-repo:
	/usr/bin/python3 tools/check_repo.py $$(git ls-files)

# Reproduce the submission from the provided bundle:
#   make submission DATA=/path/to/unpacked/bundle OUT=out
OUT ?= out
submission:
	@test -n "$(DATA)" || { echo "usage: make submission DATA=/path/to/bundle [OUT=out]"; exit 2; }
	uv run --frozen python private/submission.py --data "$(DATA)" --out "$(OUT)"

# Public / external / synthetic evidence used by PLAN.md. None of these touch match data.
evidence: sensitivity idsse-profile idsse-transfer

IDSSE_HF := https://huggingface.co/datasets/pysport/idsse-data/resolve/main
IDSSE_IDS := 000001_DFL-MAT-J03WMX 000001_DFL-MAT-J03WN1 000002_DFL-MAT-J03WOH 000002_DFL-MAT-J03WOY \
             000002_DFL-MAT-J03WPY 000002_DFL-MAT-J03WQQ 000002_DFL-MAT-J03WR9

idsse-download:
	mkdir -p scratch/data/idsse
	for m in $(IDSSE_IDS); do for k in 02_01_matchinformation 03_02_events_raw 04_03_positions_raw_observed; do \
	  f=DFL_$${k}_DFL-COM-$${m}.xml; [ -s scratch/data/idsse/$$f ] || curl -sSL -o scratch/data/idsse/$$f $(IDSSE_HF)/$$f; \
	done; done

sensitivity:
	$(PY) scratch/metric/sensitivity.py > scratch/out/sensitivity.txt
	$(PY) scratch/metric/calibrate_lag.py > scratch/out/calibrate_lag.txt

idsse-profile:
	$(PY) scratch/external/idsse_profile.py scratch/data/idsse > scratch/out/idsse_profile.txt
	$(PY) scratch/external/idsse_lag_curve.py > scratch/out/idsse_lag_curve.txt

idsse-transfer:
	$(PY) scratch/external/idsse_transfer_v2.py scratch/data/idsse > scratch/out/idsse_baseline_transfer_v2.txt
	$(PY) scratch/external/idsse_oracle_decomp.py scratch/data/idsse > scratch/out/idsse_oracle_decomp.txt

# Human-run targets on the match data live in Makefile.private (gitignored, created by Fadel from
# the template in PLAN.md section 5). They print PASS/FAIL only. The agent never runs them.
private-%:
	$(MAKE) -f Makefile.private $@
