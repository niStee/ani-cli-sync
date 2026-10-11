# Tasks

## 1. Test Suite Scaffolding (TDD Red Phase)

- [x] 1.1 Add failing unit tests in `tests/test_subtitles.py` for adjacent duplicate cue rejection (`_translate_single_batch` rejects duplicate translations when source cues differ and bisects) and verify test fails red via `PYTHONPATH=src python3 -m unittest tests/test_subtitles.py`
- [x] 1.2 Add failing unit tests in `tests/test_subtitles.py` for key-indexed dictionary parsing in `_parse_translation_response` (`{"0": "...", "1": "..."}`, missing key refusal, non-integer keys) and verify test fails red
- [x] 1.3 Add positive/negative test pair in `tests/test_subtitles.py` ensuring legitimate identical source dialogue is preserved and leaf fallback preserves timestamps without shifting dialogue

## 2. Implementation & Sensitivity Verification (Green Phase)

- [x] 2.1 Implement key-indexed dictionary parsing in `_parse_translation_response` in `src/ani_cli_sync/subtitles.py` and verify `TestParseTranslationResponse` passes green
- [x] 2.2 Implement semantic adjacent-duplicate rejection in `_translate_single_batch` in `src/ani_cli_sync/subtitles.py` and verify batch duplicate rejection and bisection tests pass green
- [x] 2.3 Run sensitivity probe on duplicate rejection guard (temporarily weaken check to accept duplicate, observe test failure, restore check, observe test pass) and record verification

## 3. Quality & Regression Verification

- [x] 3.1 Run full unit test suite via `PYTHONPATH=src python3 -m unittest discover -s tests` and verify all tests pass
- [x] 3.2 Run `python3 scripts/ruff_count_ratchet.py` and verify ruff count matches baseline (18) with no new lint errors
- [x] 3.3 Validate OpenSpec change completeness via `mise exec -- openspec validate robust-subtitle-alignment`
