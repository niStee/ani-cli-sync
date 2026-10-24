# Tasks

- [x] 1.1 (tier: frontier) Write the failing tests for the spec delta scenarios in `tests/test_subtitles.py`: default playback attaches only the primary track even when the stream carries an English track; an explicitly requested English secondary is attached without a translation call; a requested secondary that could not be produced leaves the secondary track disabled; the stream English track serves as the primary when the German primary could not be produced; a requested secondary stays secondary when that primary fallback is used. Prove the change is red via `PYTHONPATH=src python3 -m unittest tests.test_subtitles`.
- [x] 1.2 (tier: frontier) Record the positive/negative pair: the default case and the requested-English case are the positive halves, the unavailable-secondary case is the negative half that proves a failed request does not leave the player pointing at a non-existent track index. The two primary-fallback cases pin the edge behaviour the move of the English track into the primary chain repairs, measured against the pre-change implementation rather than assumed.
- [x] 2.1 (tier: low) Gate the secondary track attachment behind an explicit secondary language request in `src/ani_cli_sync/subtitles.py`, so the stream English track is not appended when nothing was requested. Verified green via `PYTHONPATH=src python3 -m unittest tests.test_subtitles` -> `Ran 79 tests ... OK`.
- [x] 2.2 (tier: low) Skip the secondary translation when the requested secondary language is English, since the source track already is English. Verified by the same suite.
- [x] 2.3 (tier: low) Move the stream English track into the primary-track chain in `src/ani_cli_sync/subtitles.py`, so the primary fallback does not depend on the secondary branch firing. Verified by the same suite, and by the measured before/after comparison recorded below.
- [x] 2.3 (tier: low) Update the `prepare_subtitles()` docstring so step 5 states that the secondary track is disabled and the English track is not attached, rather than describing the old fallback.
- [x] 2.4 (tier: low) Update the `--sub-secondary` CLI help text in `src/ani_cli_sync/cli.py` to state that the default is disabled.
- [x] 3.1 (tier: low) Run ADR-012 sensitivity probe A: restore the unconditional English append and confirm the default-subtitle test fails. Round trip recorded below.
- [x] 3.2 (tier: low) Run ADR-012 sensitivity probe B: restore the English round-trip translation and confirm the not-translated test fails. Round trip recorded below.
- [x] 3.3 (tier: low) Run ADR-012 sensitivity probe C: remove the English track from the primary chain and confirm the primary-fallback tests fail. Round trip recorded below.
- [x] 3.4 (tier: low) Run the full unit suite via `PYTHONPATH=src python3 -m unittest discover -s tests`. Result: `Ran 239 tests ... OK`.
- [x] 3.5 (tier: low) Run `python3 scripts/ruff_count_ratchet.py`. Result: `OK (count == baseline 0)`.
- [x] 3.6 (tier: low) Validate the OpenSpec change via `openspec validate secondary-subtitle-disabled-by-default --strict`. Result: `Change 'secondary-subtitle-disabled-by-default' is valid`.

## Sensitivity probe A (3.1)

The conditional-attach guard removed, restoring the unconditional English append:

```
FAIL: test_prepare_subtitles_default_secondary_none
AssertionError: 2 != 1
Ran 77 tests in 0.633s
FAILED (failures=1)
```

Restored:

```
Ran 77 tests in 0.514s
OK
```

## Sensitivity probe B (3.2)

The `secondary_lang != "en"` guard removed, restoring the English round-trip:

```
FAIL: test_prepare_subtitles_explicit_secondary_en_is_not_translated
AssertionError: '/tmp/.../slime_ep15_en.vtt' != 'https://stream.example/en.vtt'
Ran 77 tests in 0.477s
FAILED (failures=1)
```

Restored:

```
Ran 77 tests in 0.514s
OK
```

## Sensitivity probe C (2.3)

The English track removed from the primary-track chain:

```
FAIL: test_prepare_subtitles_forwards_the_stream_referrer
FAIL: test_prepare_subtitles_english_primary_when_german_translation_fails
FAIL: test_prepare_subtitles_requested_secondary_keeps_english_primary_when_german_fails
Ran 79 tests in 1.319s
FAILED (failures=3)
```

Restored:

```
Ran 79 tests in 0.621s
OK
```

This probe fails three tests, one of them pre-existing. That is the point:
the English track in the primary chain is not only reachable through the new
fallback test, it is load-bearing for behaviour that already existed. A change
that dropped it would have broken the referer-forwarding path as well.

## The three probes together

| probe | guard removed | tests failed |
|---|---|---|
| A | conditional-attach guard | `default_secondary_none` |
| B | `secondary_lang != "en"` guard | `explicit_secondary_en_is_not_translated` |
| C | English track in the primary chain | `english_primary_when_german_translation_fails`, `requested_secondary_keeps_english_primary_when_german_fails`, `forwards_the_stream_referrer` |

Each probe fails exactly the tests that pin its own guard, and the failures do
not overlap. That is the property that makes the set meaningful: the three
decisions are separable, and the suite can tell them apart.

Note on method: `__pycache__` must be cleared between a source edit and the
probe run, otherwise Python serves the pre-edit module and the "restored" run
fails while the source is already correct.
