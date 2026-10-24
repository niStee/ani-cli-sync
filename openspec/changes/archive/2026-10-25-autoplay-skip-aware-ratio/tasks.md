# Tasks

- [x] 1.1 (tier: frontier) Write the failing tests for the spec delta scenarios in `tests/test_autoplay_stop.py`: a skipped episode at 1028s of 1463s with 176s skipped advances; a skipped episode at 600s of 1463s with 177s skipped still stops; a no-skip episode at 1008s of 1440s stops; a no-skip episode at 1152s of 1440s advances. Prove the change is red via `PYTHONPATH=src python3 -m unittest tests.test_autoplay_stop`.
- [x] 1.2 (tier: frontier) Record the positive/negative pair: the skip-aware advance case is the positive half, the 600s early quit and the no-skip 1008s case are the negative halves that prove the relaxation did not weaken the early-quit protection and did not leak into the no-skip regime.
- [x] 2.1 (tier: low) Lower the skip-aware completion ratio from 0.85 to 0.70 in `src/ani_cli_sync/cli.py`. Verified green via `PYTHONPATH=src python3 -m unittest tests.test_autoplay_stop` -> `Ran 15 tests ... OK`.
- [x] 2.2 (tier: low) Update the `_should_advance()` docstring so it states the 70% skip-aware floor and the unchanged 80% no-skip baseline, rather than the previous 85% figure.
- [x] 2.3 (tier: low) Update the `autoplay-completion-threshold` spec's Purpose line, which still describes the industry-standard ratios as "80%-85%".
- [x] 2.4 (tier: low) Update the autoplay stop-semantics table in `AGENTS.md` so the skip-case threshold reads 70% and the no-skip case stays 80%.
- [x] 3.1 (tier: low) Run an ADR-012 sensitivity probe: raise the skip-aware ratio back to 0.85 and confirm the 1028s scenario fails; restore 0.70 and confirm green. Round trip recorded below.
- [x] 3.2 (tier: low) Run the full unit suite via `PYTHONPATH=src python3 -m unittest discover -s tests`. Result: `Ran 239 tests ... OK`.
- [x] 3.3 (tier: low) Run `python3 scripts/ruff_count_ratchet.py`. Result: `OK (count == baseline 0)`.
- [x] 3.4 (tier: low) Validate the OpenSpec change via `openspec validate autoplay-skip-aware-ratio --strict`. Result: `Change 'autoplay-skip-aware-ratio' is valid`.

## Sensitivity probe 3.1 (ADR-012)

The skip-aware ratio raised back to 0.85:

```
FAIL: test_playback_with_skips_and_recap_advances
AssertionError: False is not true : stopped after 1028s (needed 1094s to count as watched)
Ran 15 tests in 0.002s
FAILED (failures=1)
```

Restored to 0.70:

```
Ran 15 tests in 0.001s
OK
```

The probe is also the reason the no-skip pair matters. Raising the ratio back
fails exactly one test. If the change had accidentally moved the no-skip
branch too, the two no-skip tests would have failed as well, which would have
shown that the relaxation leaked into a regime it must not touch.

A note on the probe method: the `__pycache__` directories must be cleared
between a source edit and the probe run. Python's bytecode cache otherwise
served the pre-edit module, and the "restored" run failed even though the
source already read 0.70. The recorded round trip above is the one after the
cache was cleared in both directions.
