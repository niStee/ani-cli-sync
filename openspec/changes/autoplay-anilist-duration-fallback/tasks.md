# Tasks

Under the 2026-10-30 pilot override in `design.md`, GPT orchestrator spec/test approvals replace intermediate human approvals. GLM-5.3 owns task group 1 after GPT spec approval; MiniMax-M3.1-Flash starts group 2 only after GPT reviews frozen tests and sensitivity evidence. Final human acceptance remains required.

Status note (2026-10-30, implementation session): group 1 was authored by Kimi, not by a GLM
model, because the GLM-5.3 routes were unavailable; the deviation is recorded in
`tests-review.md`. Group 2 was implemented by MiniMax-M3.1-Flash after the GPT review of the
frozen tests. Task 3.2 (the GPT traceability review of the implementation) is **not** done
and is not claimed here. Final human acceptance is also still outstanding. Nothing in this
change has been archived, committed, pushed, or run in CI.

## 1. Approved scenarios to frozen tests (Kimi; GPT-approved before implementation)

- [x] 1.1 (tier: frontier) Add D01-D09 positive/negative duration precedence, minute-conversion, invalid-metadata, skip, constant, and non-zero-exit tests; verify intended new cases fail on pinned implementation for the stated reason and existing ratio/stop cases remain green without live calls.
      Result: `tests/test_autoplay_duration_fallback.py` with 15 test methods. Red on the pinned implementation: `Ran 266 tests` with 11 expected failures, all 251 pre-existing tests green. No live call, no credential, no real player.
- [x] 1.2 (tier: frontier) Add D10-D16 command-level watchlist/global-search/interactive-selection, sequel replacement/invalidation, and request-count tests with deterministic mocks; verify selected identity and no additional per-episode AniList or nonzero-exit HLS request are asserted.
      Result: the same file. GraphQL, HLS probing, the player, fzf, the clock, sleeps, progress writes and subtitle resolution are mocked; `HOME` and `XDG_CACHE_HOME` are redirected to a fresh temporary directory per run. Selected identity is asserted through the observable completion target and the exact GraphQL call count.
- [x] 1.3 (tier: frontier) Record every required sensitivity probe as focused red after weakening exactly one guard and restored green with the later implementation; verify the probe log covers precedence, conversion, invalid values, ratios, abnormal exit, selected media, sequel replacement, and request counts before GPT test review.
      Result: 23 probes, one surgical mutation each, run against disposable copies outside the worktree. All 23 SENSITIVE (mutated exit 1, restored exit 0), `.pyc` counts 0 before/during/after every run, frozen test SHA-256 `c261e755248922c1cb262472027046f99e63868c3cf8df3953286fbbf6c70750` unchanged in all of them. Full table in `implementation-review.md`. The planned "sequel read safety" row is deliberately not probed: it is a fixture constraint, not a production sensitivity claim.

## 2. Minimal implementation (MiniMax-M3.1-Flash, after GPT test review)

- [x] 2.1 (tier: mid) Implement HLS -> valid positive integer AniList minutes -> 1150 precedence and defensive invalid-value handling while preserving the exact 70%/80% and nonzero-exit rules; verify D01-D09 frozen tests pass unchanged.
      Result: `_anilist_duration_seconds()` rejects `bool`, non-`int`, and values `<= 0`; `_should_advance()` gained one optional trailing parameter, so the existing callers in `tests/test_autoplay_stop.py` are unchanged. Focused suite: `Ran 15 tests ... OK`.
- [x] 2.2 (tier: mid) Extend only the existing watchlist/search/sequel queries and carry/replace selected-media duration across all selection and rollover routes; verify D10-D16 frozen tests pass, no display protocol change occurs, and no per-episode request was added.
      Result: `duration` added to the three existing selection sets only. The duration travels in a `media_duration_minutes` map keyed by media id and is resolved by the parsed media id, so it follows the selection rather than the list order; the fzf line format is unchanged. On rollover it is replaced with the sequel's own value, and a missing or invalid value becomes unknown. Probe 20 confirms that adding one per-episode request fails the request-count assertions.
- [x] 2.3 (tier: low) Update the AGENTS autoplay fallback description and directly affected comments to describe all three tiers and metadata limitations; verify relative links, `git diff --check`, and consistency with the approved delta without unrelated documentation edits.
      Result: `AGENTS.md` gained a "Duration evidence: three tiers" subsection; `README.md` gained a "Completion Detection" section. `git diff --check` is clean.

## 3. Verification and acceptance

- [x] 3.1 (tier: mid) Run focused autoplay/sequel/subdelay tests, then `PYTHONPATH=src python3 -m unittest discover -s tests`, `ruff check .`, and `python3 scripts/ruff_count_ratchet.py`; read and report actual results, separating any pre-existing failure rather than hiding it.
      Result: focused `Ran 15 tests ... OK`; full suite `Ran 266 tests ... OK`; `ruff check .` -> `All checks passed!`; `python3 scripts/ruff_count_ratchet.py` -> `OK (count == baseline 0).`; `openspec validate autoplay-anilist-duration-fallback --strict` -> valid; `openspec validate --all --strict` -> `Totals: 8 passed, 0 failed (8 items)`. No pre-existing failure was hidden: the 11 expected red assertions from task 1.1 are the only tests that failed before the implementation, and all of them are green now. The unrelated pre-existing D1/D2 pre-play write/read behavior observed during the work was **not** fixed; it is outside this change's scope.
- [ ] 3.2 (tier: frontier) GPT performs final spec/test/code traceability review against issue #60 and D01-D16; verify VAD stayed out of scope, frozen tests were not weakened, no live service or extra query was used, and all sensitivity evidence exists before final human acceptance.
      Not performed in this session. The evidence it needs is assembled in `implementation-review.md`; the reviewer still has to perform the review.

## Workflow follow-up

- Do not archive or apply this planning change during planning.
- Keep any future per-release duration probing or VAD follow-up in a separate proposal; this change ends at the three documented duration tiers.
- The canonical spec `openspec/specs/autoplay-completion-threshold/spec.md` is deliberately **unchanged** by this change. The delta in `openspec/changes/autoplay-anilist-duration-fallback/specs/` is the only spec text, and it validates cleanly. Promotion belongs to the archive step, not to this implementation step: `openspec-apply-change` ends at "review or verify the change as appropriate before archiving", and this repository's own history follows that order (PR #100 implemented and touched only the Purpose line, PR #105 landed its delta through `openspec archive`, PR #103 is the separate "archive ... and sync the deltas" commit).
- One tool-verified consequence must be handled at promotion time: the delta's `Conservative Fallback for Unknown Duration` requirement body is 1233 characters, over the validator's `MAX_REQUIREMENT_TEXT_LENGTH` of 500, so promoting it as one block makes `openspec validate --specs --strict` exit 1 with `requirements[2]: Requirement text is very long (>500 characters)`. This is not an artifact of hand-merging: running `openspec archive` in a disposable copy produces the same warning. The change delta itself passes strict validation because the validator exempts MODIFIED requirements from the length check. The repository's own remedy for this exact situation is recorded in `openspec/changes/archive/2026-10-25-aot-final-season-offset-mapping/tasks.md` task 1.3: split the requirement into single-behaviour requirements before it lands in the canonical spec. The split was **not** performed here, because it would change the GPT-approved delta; it is left to the archive step or to an explicit review decision.
