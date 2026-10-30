# Tasks

This docs-only package uses the pilot override in `design.md`: GPT orchestrator review replaces intermediate human approval and final human acceptance remains required. There is deliberately no behavioral spec, GLM test stage, or production implementation.

## 1. Documentation plan review

- [x] 1.1 (tier: frontier) GPT compares the exact edit plan and acceptance matrix against pinned source and current subtitle specs; verify every claimed default is supported, the two ADR models are counted correctly, no new runtime behavior is specified, and auth/general-primary-language changes remain excluded.

## 2. Bounded mechanical edit

- [x] 2.1 (tier: low) After GPT plan approval, edit only README, AGENTS, ADR-001, and the identified subtitle docstrings to capture the optional HTTP service, cascade/auth behavior, track/cache avoidance, graceful fallback, possible latency, bypass, and separate subsync extra; verify the diff contains no executable Python or canonical-spec change.
- [x] 2.2 (tier: low) Run `git diff --check`, search the edited documents for stale DeepSeek/default-secondary/absolute-zero-latency/three-model wording, and resolve every relative Markdown link; verify the acceptance matrix row by row without live calls or a full-suite rerun.

## 3. Review and acceptance

- [ ] 3.1 (tier: frontier) GPT reviews the final rendered diff against source evidence and issue #89; verify no contradictory duplicated guidance or out-of-scope feature was introduced, then present the docs change for final human acceptance.

## Workflow follow-up

- Do not archive or apply this planning change during planning.
- Keep future runtime behavior changes in their own OpenSpec proposals; this package only aligns descriptions with existing behavior.

## Execution notes (2026-10-30, low-tier mechanical edit)

Task 2.1 and 2.2 were executed on `docs/subtitle-translation-requirements` at pinned base
`87314dc54de181b928a49c2711f3783efca5c532`. Changed paths: `README.md`, `AGENTS.md`,
`docs/adr/ADR-001-media-subtitle-translation-and-sync.md`, and docstrings only in
`src/ani_cli_sync/subtitles.py`. No canonical spec, dependency, test, or runtime-logic change.
Evidence and remaining limitations are recorded in `implementation-review.md` next to this
file. Task 3.1 remains open: it is the GPT orchestrator's diff review and the operator's
final human acceptance.
