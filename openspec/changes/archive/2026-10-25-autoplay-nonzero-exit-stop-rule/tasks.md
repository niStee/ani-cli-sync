# Tasks

- [x] 1.1 (tier: frontier) Confirm the gap: read `openspec/specs/autoplay-completion-threshold/spec.md` and verify that all six existing scenarios specify "return code 0" or a duration shortfall, and that none of the three requirements mentions a non-zero exit. Verified: `grep -n "^### Requirement"` returns three requirements, none of which mentions an exit status.
- [x] 1.2 (tier: frontier) Confirm the implementation and its tests: read `_should_advance()` in `src/ani_cli_sync/cli.py` and confirm the exit check precedes the duration logic; confirm `test_nonzero_exit_never_advances` and `test_unknown_duration_nonzero_exit_still_stops` in `tests/test_autoplay_stop.py` assert the behaviour. Verified by running the three cases directly: exit 1 at 1440s of 1440s -> `False, 'player exited with code 1'`; exit 2 at 1500s with unknown duration -> `False, 'player exited with code 2'`; exit 0 at 1440s of 1440s -> `True`.
- [x] 2.1 (tier: low) Write the spec delta in `openspec/changes/autoplay-nonzero-exit-stop-rule/specs/autoplay-completion-threshold/spec.md`: one added requirement stating that a non-zero exit stops progression and that the abnormal exit is reported as the cause of the stop, with three scenarios.
- [x] 2.2 (tier: low) Validate the change via `openspec validate autoplay-nonzero-exit-stop-rule --strict`. Result: `Change 'autoplay-nonzero-exit-stop-rule' is valid`.
- [x] 3.1 (tier: low) Run the existing autoplay tests to confirm the spec describes verified behaviour: `PYTHONPATH=src python3 -m unittest tests.test_autoplay_stop`. Result: `Ran 15 tests ... OK`.
- [x] 3.2 (tier: low) Run the full unit suite via `PYTHONPATH=src python3 -m unittest discover -s tests`. Result: `Ran 248 tests ... OK`.
- [x] 3.3 (tier: low) Run `ruff check .`. Result: `All checks passed!`.
- [x] 3.4 (tier: low) Run `python3 scripts/ruff_count_ratchet.py`. Result: `OK (count == baseline 0)`.
- [x] 3.5 (tier: low) Run `openspec validate --all --strict` to confirm the live specs are still consistent. Result: `Totals: 8 passed, 0 failed (8 items)` - the seven live capabilities plus this change.
- [x] 4.1 (tier: low) Archive the change with `openspec archive autoplay-nonzero-exit-stop-rule --yes`, so the added requirement lands in the canonical spec `openspec/specs/autoplay-completion-threshold/spec.md` and the change directory moves to `openspec/changes/archive/2026-10-25-autoplay-nonzero-exit-stop-rule/`. This is the mechanism the repository uses to apply a delta to a canonical spec (as PR #95 and PR #103 did).
- [x] 4.2 (tier: low) Re-validate after the archive: `openspec validate --all --strict`. Result: `Totals: 7 passed, 0 failed (7 items)` - the change is archived, so the count returns to the seven live capabilities, now including the fourth requirement of `autoplay-completion-threshold`.

- [x] 5.1 (tier: low) Add the missing per-scenario tests to `tests/test_autoplay_stop.py`: a non-zero exit after the full duration of a known episode, a non-zero exit in the skip regime, and a positive/negative pair pinning the reported stop cause to the abnormal exit rather than a duration shortfall. Result: `Ran 18 tests ... OK`.
- [x] 5.2 (tier: low) Run the sensitivity probe over the three new tests, because a guard never observed failing is assumed vacuous (ADR-012). Result: see the note below.

## Note on the test task

`openspec/config.yaml` states "A spec never replaces tests". This change
originally added no test, on the reasoning that two existing tests already
assert the behaviour. That reasoning was incomplete.

The two pre-existing tests cover two different regimes, and neither is the
spec's scenario.

`test_nonzero_exit_never_advances` exits after 60s of a 1440s episode, which
is short of the 80% baseline, so a duration rule would *also* have stopped the
chain. That case does not distinguish "the exit status stopped this" from "the
duration stopped this".

`test_unknown_duration_nonzero_exit_still_stops` exits after 1500s with an
unknown duration, which is *past* the 1150s fallback, so on elapsed time alone
it would advance. That case therefore already detects the removal of the exit
guard (it fails by advancing, as mutation A showed). What it does not pin is
which cause is reported.

The spec's two consequential scenarios -- a non-zero exit at full duration, and
a non-zero exit in the skip regime -- clear every elapsed-time threshold on
their own, so the exit status is the only thing that can stop them, and
neither scenario had a direct assertion.

Three tests were therefore added, one per scenario, plus the reported-cause
pair.

## Sensitivity probe

Three mutations were applied to `_should_advance()` in `src/ani_cli_sync/cli.py`
in turn. `__pycache__` was cleared before each run, and the file was restored
byte-for-byte afterwards (`git diff --stat src/ani_cli_sync/cli.py` empty).

| mutation | change | result |
|---|---|---|
| A | the exit check removed entirely | `Ran 18 tests ... FAILED (failures=5)` |
| B | the exit check moved after the duration block, still before the advance decision | `Ran 18 tests ... OK` -- **invisible** |
| C | the exit check moved after the advance decision | `Ran 18 tests ... FAILED (failures=3)` |

Under mutation A the failures were:

- `test_abnormal_exit_reason_names_the_exit_not_the_duration`
- `test_nonzero_exit_after_full_duration_does_not_advance`
- `test_nonzero_exit_after_skips_does_not_advance`
- `test_nonzero_exit_never_advances`
- `test_unknown_duration_nonzero_exit_still_stops`

The first failure is the sharpest: without the exit check the tracker stops
for a *duration* reason, which is exactly what the reported-cause clause
forbids.

Mutation B is the interesting one, and it changed the requirement. It is the
mutation the requirement's original "the exit status SHALL be evaluated before
any duration-based threshold is computed" clause was written to forbid -- and
**no test caught it**, because whether the duration was computed is not
observable. The clause constrained an implementation detail rather than a
behaviour, and a specification that pins an unobservable detail is a
specification that cannot be verified.

The requirement was therefore rewritten to state the observable instead: the
tracker reports the abnormal exit as the cause of the stop. Mutation C, which
is the defect that actually matters -- a non-zero exit that nevertheless
advances -- is caught by two of the new tests.

The implementation is unchanged in the committed tree; the probe edits were
scratch and are not part of this change.
