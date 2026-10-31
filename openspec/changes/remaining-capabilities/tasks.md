# Tasks

## Workflow override (recorded 2026-10-30)

This round ran under the user pilot, which removes the intermediate HUMAN gates.
No task below is marked complete on the strength of a human approval. Each
completed box records what was actually executed and where the evidence lives.

- 1.1, 1.2, 1.3: the Kimi test package, reviewed by the GPT orchestrator.
- 1.4: the 18 recorded mutation probes in `tests-review.md`.
- 2.1, 2.2: the GPT orchestrator reviewed the source-grounded deltas and the
  D1-D9 disposition. No explicit user approval exists for this round.
- 2.3, 2.4, 3.1, 3.2, 3.3: performed in this round; evidence in
  `implementation-review.md`.

## 1. Baseline characterization after user approval

- [x] 1.1 (tier: mid) Derive hermetic failing-then-passing characterization tests from the four delta scenarios, without production changes or live services; verify each scenario maps to an existing test or a new positive/negative pair and record the coverage matrix against `design.md`. Evidence: the per-scenario coverage matrix in `tests-review.md` maps every scenario of the four deltas to a named test. Production source was not modified; `git status` shows `src/` clean.
- [x] 1.2 (tier: mid) Add missing CLI and AniList fixtures for authentication, aliases, bare titles, selection cancellation, supported progress, playback updates, and successful sequel reads; verify with `PYTHONPATH=src python3 -m unittest discover -s tests` and do not encode exclusions D1-D6 as approved behavior. Evidence: `tests-review.md` records 30 new cases in `tests/test_cli.py`; the "Exclusions honored" section states that no test asserts the D1-D6 behavior. Suite result: `Ran 294 tests ... OK`.
- [x] 1.3 (tier: mid) Add missing matching and sub-sync fixtures, including exact-among-many selection, normalized groups, explicit zero delay, first-cue limits, early-onset rejection, and exact 60/0.05 boundaries; verify with focused unittest modules and the full suite. Evidence: `tests-review.md` records 3 new cases in `tests/test_menu.py`, 4 in `tests/test_subsync.py`, and 4 in `tests/test_subdelay_auto.py`, including the exactly-60 and 0.04/0.05 boundary pairs and the early-onset rejection pair. Focused run: `Ran 157 tests ... OK`.
- [x] 1.4 (tier: frontier) Perform sensitivity probes for every new guard pair by injecting its bad state in a disposable fixture, observing the intended failure, restoring the fixture, and observing a pass; record commands and outcomes without retaining production mutations. Evidence: the 18-row probe table in `tests-review.md` (P1-P16, G1, G2); every mutation fails its focused test and every restore passes. One caveat is carried forward: P12 was vacuous on its first run and was fixed by adding the both-cuts-marked fixture, so the count is 18 only after that fix.

## 2. Specification review and promotion

- [x] 2.1 (tier: frontier) Review the source-grounded deltas, discrepancies D1-D9, and coverage omissions with the user; verify explicit approval names the four deltas and confirms that excluded unsafe behavior is not being endorsed. Evidence: reviewed by the GPT orchestrator, not by the user; the pilot removes the intermediate human gate for this round, so no explicit user approval is claimed. The four deltas are the ones named in `proposal.md` (anilist-sync, cli, matching, sub-sync). The D1-D9 disposition is unchanged in `design.md` and the exclusions are still recorded as exclusions, not as requirements.
- [x] 2.2 (tier: mid) Reconcile only approved characterization findings into the delta text and `design.md`, keeping canonical completion and subtitle-track requirements unchanged; verify no discrepancy was silently converted into a requirement. Evidence: the four delta spec files and `design.md` are byte-identical to their pre-sync state; the sync only added the four canonical spec files and left `autoplay-completion-threshold`, `subtitles`, and the five other adjacent specs byte-identical. D1-D9 appear in the canonical specs only as exclusion wording (anilist-sync "excluded from this baseline", sub-sync "SHALL NOT claim to identify dialogue").
- [x] 2.3 (tier: mid) After approval, sync the four deltas into canonical specs using the existing OpenSpec workflow; verify `openspec/specs/` contains exactly the four approved additions and no changes to unrelated capabilities. Evidence: `openspec/specs/` now holds 11 capabilities, the 7 previous ones byte-identical plus `anilist-sync` (4 requirements), `cli` (5), `matching` (3), and `sub-sync` (6). The sync output is byte-identical to what `openspec archive` produces for the same change, verified on a disposable copy.
- [x] 2.4 (tier: low) Check all changed artifact text is ASCII and the change touches only approved specification, test, and traceability files; verify `git diff --name-only` and an ASCII scan show no production, workflow, credential, or generated-cache changes. Evidence: see `implementation-review.md` for the ASCII scan and the scoped `git status` listing. The working tree holds only the four modified test files, the untracked change directory, and the four new canonical spec directories.

## 3. Final verification gates

- [x] 3.1 (tier: low) Run `openspec validate remaining-capabilities --strict` and `openspec validate --all --strict`; verify both succeed after the approved canonical sync and report any pre-existing failure separately rather than suppressing it. Result: `Change 'remaining-capabilities' is valid` and `Totals: 12 passed, 0 failed (12 items)`. No pre-existing failure was observed; the pre-sync baseline was `8 passed, 0 failed`.
- [x] 3.2 (tier: mid) Run `PYTHONPATH=src python3 -m unittest discover -s tests`, `ruff check .`, and `python3 scripts/ruff_count_ratchet.py`; verify all succeed with no live AniList, player, translation, or service actions. Result: `Ran 294 tests ... OK`, `All checks passed!`, `OK (count == baseline 0)`. No live AniList, player, translation, or service action was performed.
- [x] 3.3 (tier: frontier) Perform a final behavior-neutral review against `design.md`; verify production source is unchanged, all new tests have recorded sensitivity evidence, and D1-D9 remain assigned to separate future decisions. Evidence: `git status` shows `src/` unchanged; the 18 probes in `tests-review.md` are the recorded sensitivity evidence; D1-D9 remain listed in `design.md` under "Explicit discrepancies and exclusions" and are not carried into the canonical specs as requirements. This box records a review that was performed, not a human sign-off.

## Workflow follow-up

- Archive only after separate user approval and completion of the repository review requirements. Not done in this round: the change is deliberately left active under `openspec/changes/remaining-capabilities/`.
- Address defects and documentation conflicts through new scoped proposals or regression changes; this baseline is not their fix. D1-D9 stay assigned to separate future decisions.
- Two items remain open for the final reviewer, both carried in `implementation-review.md`: the static half of the prefetch hermeticity guard (the behavioral half is proven sensitive) and the D7 help-text wording conflict, which needs a later reviewed docs change.
