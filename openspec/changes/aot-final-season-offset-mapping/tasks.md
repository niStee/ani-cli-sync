# Tasks

- [x] 1.1 (tier: frontier) Write the failing tests for the spec delta scenarios in `tests/test_cli.py`: Part 1 ep 1 resolves to (`Attack on Titan: Final Season, Part 1`, 1); Part 2 ep 1 resolves to (`Attack on Titan: Final Season, Part 2`, 1); a Part 2 title does not match the Part 1 entry; an episode beyond a season bound is not remapped; an unlisted series still uses the computed prequel offset. Prove the change is red via `PYTHONPATH=src python3 -m unittest tests.test_cli`. Red run observed: `AssertionError: 60 != 1`, `AssertionError: 76 != 1`, `AssertionError: 80 != 5`, `FAILED (failures=3)`.
- [x] 1.2 (tier: frontier) Record the positive/negative pair: the positive cases prove the new entries resolve the season, the negative case (an unlisted series still using the computed chain) proves the table did not displace the prequel walker.
- [x] 1.3 (tier: low) Split the spec delta into three single-behaviour requirements (`Static Offset Table Precedence`, `Static Offset Table Entry Bounds and Ordering`, `Static Offset Table Provider Search Override`) after `openspec validate --strict` rejected a requirement whose text exceeded 500 characters. Re-validated: `Change 'aot-final-season-offset-mapping' is valid`. The new search-override scenario is already covered by the existing assertions: the tests pass the AniList title (`Shingeki no Kyojin: The Final Season`) as `title_search` and assert the resolver returns the provider title.
- [x] 1.4 (tier: low) Link the proposal to its tracking issue niStee/ani-cli-sync#97 (the repo's proposal rule requires a linked issue) and bring the proposal under the 500-word limit it states. Verified: 496 prose words; `openspec validate aot-final-season-offset-mapping --strict` -> valid.
- [x] 2.1 (tier: low) Add the five `_EPISODE_OFFSETS` entries in `src/ani_cli_sync/cli.py`: three Part 2 variants (bound 12) before two Part 1 variants (bound 16), each with an explicit provider search override. Verified green via `PYTHONPATH=src python3 -m unittest tests.test_cli` -> `Ran 64 tests ... OK`.
- [x] 2.2 (tier: low) Run an ADR-012 sensitivity probe on the ordering constraint: move the Part 1 entries ahead of the Part 2 entries and confirm the Part 2 scenarios fail; restore the order and confirm green. Round trip recorded below.
- [x] 2.3 (tier: low) Leave `scripts/ruff_count_baseline.txt` unchanged. The originating commit lowered it to 15 as a side effect of flipping `src/ani_cli_sync/cli.py` from mode 644 to 755, which silences ruff `EXE001` for an imported library module. The `EXE001` finding was instead fixed on its own terms in the separate lint-debt change (`chore/clear-ruff-debt`, PR #96), which removed the vestigial shebang and took the baseline from 16 to 0. Verified via `python3 scripts/ruff_count_ratchet.py` -> `OK (count == baseline 0)`.
- [x] 3.1 (tier: low) Run the full unit suite via `PYTHONPATH=src python3 -m unittest discover -s tests`. Result: `Ran 240 tests ... OK`.
- [x] 3.2 (tier: low) Run `python3 scripts/ruff_count_ratchet.py`. Result: `OK (count == baseline 0)`.
- [x] 3.3 (tier: low) Validate the OpenSpec change via `openspec validate aot-final-season-offset-mapping --strict`. Result: `Change 'aot-final-season-offset-mapping' is valid`.
- [x] 3.4 (tier: mid) Verify the two search override strings against the live provider, read-only, without starting playback: both resolve to their expected release pages. Part 1 -> `hianime.at/attack-on-titan-final-season-1372`, Part 2 -> `hianime.at/attack-on-titan-final-season-part-2-868`.
- [x] 3.5 (tier: mid) Verify the resolved search and episode number through the shipped resolver for a Part 1 episode and a Part 2 episode. Result: ep 1 -> (`Attack on Titan: Final Season, Part 2`, 1); ep 8 -> (`Attack on Titan: Final Season, Part 2`, 8); Part 1 ep 1 -> (`Attack on Titan: Final Season, Part 1`, 1).
- [x] 4.1 (tier: low) Update `AGENTS.md`'s offset table with the two Attack on Titan rows, and document that the table's entry order is load-bearing.

## Sensitivity probe 2.2 (ADR-012)

Ordering constraint, Part 2 entries moved after Part 1 entries:

```
FAIL: test_aot_final_season_part2_ep1_resolves_to_part2
AssertionError: 'Attack on Titan: Final Season, Part 1' != 'Attack on Titan: Final Season, Part 2'
FAIL: test_aot_part2_title_does_not_match_the_part1_entry
AssertionError: 'Attack on Titan: Final Season, Part 1' != 'Attack on Titan: Final Season, Part 2'
Ran 64 tests in 4.074s
FAILED (failures=2)
```

Restored order:

```
Ran 64 tests in 3.039s
OK
```

The probe observes the failure the ordering exists to prevent: with Part 1
first, the Part 2 title matches the Part 1 fragment and the episode is
remapped to the wrong release.

## Note on the provider probe (3.4)

The first attempt used `ani-cli -d` (download), which began fetching a
full episode rather than probing. It was interrupted and the partial
fragments it left in the repository were removed. The provider's search
endpoint was queried directly instead, which is read-only and answers in one
request.

The episode-count bound could not be read from the provider's HTML with the
available endpoints, so the `max_ep` values (16 for Part 1, 12 for Part 2)
rest on the AniList season lengths rather than on an independent read of the
provider's episode list. They are the same numbers the local branch used.
