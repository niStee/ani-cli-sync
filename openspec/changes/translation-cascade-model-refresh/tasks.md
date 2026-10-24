# Tasks

## 1. Test Suite Scaffolding (TDD Red Phase)

- [x] 1.1 (tier: frontier) Add failing test in `tests/test_subtitles.py` pinning the default cascade to `minimax-m3, minimax-m3.1-flash, gemini-3.1-flash-lite`, and verify it fails red via `PYTHONPATH=src python3 -m unittest tests.test_subtitles`. Red run observed: `AssertionError: ['minimax-m3', 'gemini-2.5-flash', 'llm-tower'] != ['minimax-m3', 'minimax-m3.1-flash', 'gemini-3.1-flash-lite']`.
- [x] 1.2 (tier: frontier) Add failing test in `tests/test_model_registry.py` asserting every default cascade member is a registered translation model, and that no retired handle reappears in the cascade. Red run observed: 5 failures, including `gemini-2.5-flash` and `llm-tower` flagged by the retired-handle check.
- [x] 1.3 (tier: mid) Add the negative half of the registry guard: a synthetic handle that is not in the registry is detected as unregistered. This pins the guard's own detection so it cannot rot into a no-op (ai-infra ADR-012). Proven by `test_removed_handle_would_be_caught`, which injects a retired handle and asserts it is flagged.

## 2. Implementation (Green Phase)

- [x] 2.1 (tier: low) Add `src/ani_cli_sync/model_registry.py` with the vendored registry of tier-T2 translation handles and the retired-handle tombstone.
- [x] 2.2 (tier: low) Replace `DEFAULT_FALLBACK_MODELS` in `src/ani_cli_sync/subtitles.py` with the three measured, live, tier-T2-governed handles. Verified green.
- [x] 2.3 (tier: mid) Run the ADR-012 sensitivity probe on the registry guard: add a retired handle to the cascade, observe the test fail red, revert, observe it pass green. Record the probe output.

## 3. Documentation (DoD for a behaviour change)

- [x] 3.1 (tier: low) Amend `docs/adr/ADR-001` section 3 so the ADR records the new cascade and the governance rule it depends on, plus a dated amendment recording why the two dead handles were removed and why `llm-tower` is not restored. The Consequences line referring to "local model towers" was corrected in the same edit.
- [x] 3.2 (tier: low) Update `AGENTS.md` with the new cascade, the 2026-10-24 measurements, and the "Model Governance Contract" section stating the governance rule, the read-only live probe, and the offline vendored list as the CI-checkable source of truth.
- [x] 3.3 (tier: low) Port the missing process rules into `openspec/config.yaml`: the task tier rule and the Mermaid design rules from ai-infra ADR-017. The ported tier rule is YAML-quoted; ai-infra's own copy of that rule is missing the quotes and therefore parses as a mapping instead of a string (see the follow-up issue).

## 4. Quality & Regression Verification

- [x] 4.1 (tier: low) Run the full unit suite via `PYTHONPATH=src python3 -m unittest discover -s tests` and verify all tests pass. Result: `Ran 235 tests ... OK`.
- [x] 4.2 (tier: low) Run `python3 scripts/ruff_count_ratchet.py` and verify the ruff count matches the baseline with no new findings. Result: `OK (count == baseline 16)`.
- [x] 4.3 (tier: low) Validate the OpenSpec change via `openspec validate translation-cascade-model-refresh`. Result: `Change 'translation-cascade-model-refresh' is valid`.
- [x] 4.4 (tier: mid) Cross-check the vendored registry against the live gateway: every handle in `TRANSLATION_MODELS` appears in `http://localhost:4000/v1/models`. Result: live catalogue holds 52 handles; all 10 registry entries present, 3 default cascade members present, no missing entries.
