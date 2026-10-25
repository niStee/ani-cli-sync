# Tasks

- [x] 1.1 (tier: frontier) Confirm the gap: read `openspec/specs/autoplay-completion-threshold/spec.md` and verify that all six existing scenarios specify "return code 0" or a duration shortfall, and that none of the three requirements mentions a non-zero exit. Verified: `grep -n "^### Requirement"` returns three requirements, none of which mentions an exit status.
- [x] 1.2 (tier: frontier) Confirm the implementation and its tests: read `_should_advance()` in `src/ani_cli_sync/cli.py` and confirm the exit check precedes the duration logic; confirm `test_nonzero_exit_never_advances` and `test_unknown_duration_nonzero_exit_still_stops` in `tests/test_autoplay_stop.py` assert the behaviour. Verified by running the three cases directly: exit 1 at 1440s of 1440s -> `False, 'player exited with code 1'`; exit 2 at 1500s with unknown duration -> `False, 'player exited with code 2'`; exit 0 at 1440s of 1440s -> `True`.
- [x] 2.1 (tier: low) Write the spec delta in `openspec/changes/autoplay-nonzero-exit-stop-rule/specs/autoplay-completion-threshold/spec.md`: one added requirement stating that a non-zero exit stops progression and that the exit status is evaluated before the duration threshold, with three scenarios.
- [x] 2.2 (tier: low) Validate the change via `openspec validate autoplay-nonzero-exit-stop-rule --strict`. Result: `Change 'autoplay-nonzero-exit-stop-rule' is valid`.
- [x] 3.1 (tier: low) Run the existing autoplay tests to confirm the spec describes verified behaviour: `PYTHONPATH=src python3 -m unittest tests.test_autoplay_stop`. Result: `Ran 15 tests ... OK`.
- [x] 3.2 (tier: low) Run the full unit suite via `PYTHONPATH=src python3 -m unittest discover -s tests`. Result: `Ran 248 tests ... OK`.
- [x] 3.3 (tier: low) Run `ruff check .`. Result: `All checks passed!`.
- [x] 3.4 (tier: low) Run `python3 scripts/ruff_count_ratchet.py`. Result: `OK (count == baseline 0)`.
- [x] 3.5 (tier: low) Run `openspec validate --all --strict` to confirm the live specs are still consistent. Result: `Totals: 8 passed, 0 failed (8 items)` - the seven live capabilities plus this change.
- [x] 4.1 (tier: low) Archive the change with `openspec archive autoplay-nonzero-exit-stop-rule --yes`, so the added requirement lands in the canonical spec `openspec/specs/autoplay-completion-threshold/spec.md` and the change directory moves to `openspec/changes/archive/2026-10-25-autoplay-nonzero-exit-stop-rule/`. This is the mechanism the repository uses to apply a delta to a canonical spec (as PR #95 and PR #103 did).
- [x] 4.2 (tier: low) Re-validate after the archive: `openspec validate --all --strict`. Result: `Totals: 7 passed, 0 failed (7 items)` - the change is archived, so the count returns to the seven live capabilities, now including the fourth requirement of `autoplay-completion-threshold`.

## Note on the test task

`openspec/config.yaml` states "A spec never replaces tests", and this change
adds no test because the behaviour it specifies is already asserted by two
existing tests. `tasks.md` for the sibling change that shipped the 70% ratio
started with "write the failing tests for the spec delta scenarios"; that step
is absent here by design, because there is no unimplemented behaviour to
red-test.

The sensitivity probe was run, because the new requirement rests on those
two tests and a guard never observed failing is assumed vacuous (ADR-012).

1. **Probe** -- the exit check was temporarily removed from `_should_advance()`
   in `src/ani_cli_sync/cli.py` (`if returncode != 0: return False, ...`),
   `__pycache__` cleared, and the suite re-run.
2. **Red** -- `Ran 15 tests ... FAILED (failures=2)`. Both guard tests failed
   for the right reason:
   - `test_nonzero_exit_never_advances`:
     `AssertionError: 'exit' not found in 'stopped after 60s (needed 1152s to count as watched)'`
   - `test_unknown_duration_nonzero_exit_still_stops`:
     `AssertionError: True is not false`
   The first failure is the sharper one: without the exit check the function
   stops for a *duration* reason, so the requirement's "the exit status is
   evaluated before the duration threshold" clause would be violated even
   though the outcome happened to match.
3. **Revert** -- the original file was restored byte-for-byte (`git diff
   --stat src/ani_cli_sync/cli.py` empty).
4. **Green** -- `Ran 15 tests ... OK`.

The implementation is unchanged in the committed tree; the probe edits were
scratch and are not part of this change.
