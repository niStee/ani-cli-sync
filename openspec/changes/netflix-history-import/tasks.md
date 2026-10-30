# Tasks

All work follows the pilot override in `design.md`: GPT orchestrator approval replaces intermediate human spec/test approvals, and final human acceptance remains required. GPT has selected and recorded explicit contiguous-prefix inference (P1) and conservative absent/`CURRENT`-only status handling (S1). GLM-5.3 owns task group 1 from this approved contract. GPT reviews the tests and sensitivity evidence before MiniMax-M3.1-Flash starts groups 2-3.

## 1. Approved scenarios to frozen tests (GLM-5.3)

- [ ] 1.1 (tier: frontier) Translate the approved delta and F01-F21 into synthetic positive/negative tests covering preview versus apply, strict input with nonblank uninterpreted locale dates, dispositions, the bounded `Episode N` grammar, conservative candidates without missing-season inference, and exact contiguous-set evidence; verify the focused tests fail on the pinned implementation for the intended reasons without any live call.
- [ ] 1.2 (tier: frontier) Add inference-label, absent/`CURRENT` status-transition, full-known-total completion, current-state, GraphQL failure, fresh monotonic guard, response verification, partial result, and idempotence pairs; verify mutation counts and exact exit 0/1/2 behavior against the approved contract, with sequential mocks rather than an impossible atomic-concurrency assertion.
- [ ] 1.3 (tier: frontier) Perform and record the required sensitivity probes, restoring each guard after observing focused red; verify restored focused tests are green only with the later implementation and hand the frozen tests plus probe log to GPT for review before implementation.

## 2. Minimal implementation (MiniMax-M3.1-Flash, after GPT test review)

- [ ] 2.1 (tier: mid) Implement strict CSV validation with nonblank date metadata, the right-anchored release/episode grammar, candidate resolution without inferred missing seasons, identity deduplication, exact `1..N` proposals, and deterministic preview dispositions with inference labels; verify F01-F14, F16, and F21 frozen tests pass with zero preview mutations.
- [ ] 2.2 (tier: mid) Implement the selected absent/`CURRENT` progress and completion decisions, fresh state reads, monotonic/no-reopen guards, GraphQL failure propagation, and verified apply results; verify F11-F20 frozen tests pass, no failed read becomes absence, and no strict simultaneous-write guarantee is claimed.
- [ ] 2.3 (tier: mid) Implement truthful summaries and exit precedence without claiming unresolved or failed rows imported or inferred events verified as playback; verify command-level partial and idempotence tests pass with the frozen assertions unchanged.

## 3. Documentation and verification (MiniMax-M3.1-Flash)

- [ ] 3.1 (tier: low) Update importer help and the README Netflix section for preview default, explicit `--apply`, bounded episode evidence, inferred rather than verified playback, safe absent/`CURRENT` status behavior, nonblank date metadata, dispositions, exit meanings, and the non-atomic fresh-read/write limitation; verify relative links, help output, and documentation consistency with the approved spec, leaving the expanded #88 guide separate.
- [ ] 3.2 (tier: mid) Run the focused importer tests, `PYTHONPATH=src python3 -m unittest discover -s tests`, `ruff check .`, and `python3 scripts/ruff_count_ratchet.py`; verify all results are read and report any pre-existing failure rather than concealing it.
- [ ] 3.3 (tier: frontier) GPT performs final spec/test/code traceability and safety review; verify no unresolved orchestrator decision, unapproved test edit, live write, unsupported date/grammar claim, atomicity claim, or out-of-scope helper change remains before proposing the behavioral PR for final human acceptance.

## Workflow follow-up

- Do not archive or apply this planning change during the planning stage.
- After #90 is approved, keep #88 documentation aligned with the exact shipped CLI and decisions rather than duplicating a second contract.
