# Tasks

## 1. Test Scaffolding (TDD Red Phase)

- [x] 1.1 Add failing unit test in `tests/test_subtitles.py` for `get_candidate_models` resolving default cascade (`minimax-m3, gemini-2.5-flash, llm-tower`), single override (`ANI_CLI_SYNC_LLM_MODEL`), and comma-separated cascade (`ANI_CLI_SYNC_LLM_MODELS`), and verify test fails red via `PYTHONPATH=src python3 -m unittest tests/test_subtitles.py`
- [x] 1.2 Add failing unit test in `tests/test_subtitles.py` for immediate model failover on HTTP 429 quota exhaustion (verifying the exhausted model is not retried and next candidate model succeeds)
- [x] 1.3 Add failing unit test in `tests/test_subtitles.py` for transient 503 error retry with backoff before escalating to the next model, and complete cascade exhaustion fallback returning None

## 2. Core Implementation (Green Phase)

- [x] 2.1 Implement `get_candidate_models` in `src/ani_cli_sync/subtitles.py` and verify candidate resolution test passes green
- [x] 2.2 Implement 429 quota exhaustion fast-failover in `_translate_single_batch` and candidate model cascade loop in `translate_cues_llm`, and verify failover tests pass green
- [x] 2.3 Run ADR-012 sensitivity probe on 429 failover guard (temporarily remove 429 short-circuit to observe test failure, restore guard, observe test pass) and record verification

## 3. Quality & Regression Verification

- [x] 3.1 Run full unit test suite via `PYTHONPATH=src python3 -m unittest discover -s tests` and verify all tests pass
- [x] 3.2 Run `python3 scripts/ruff_count_ratchet.py` and verify ruff count matches baseline (lowered to 16 from 18) with no new lint errors
- [x] 3.3 Validate OpenSpec change completeness via `mise exec -- openspec validate tiered-translation-failover`
