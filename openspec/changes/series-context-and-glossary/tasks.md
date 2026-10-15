# Tasks

## 1. Test Scaffolding (TDD Red Phase)

- [x] 1.1 Add failing unit test in `tests/test_subtitles.py` for `get_series_glossary` resolving built-in canonical terms for Attack on Titan (e.g. `ODM gear` -> `3D-Manöver-Apparat`, `Survey Corps` -> `Aufklärungstrupp`)
- [x] 1.2 Add failing unit test in `tests/test_subtitles.py` for `extract_active_glossary` extracting only terms present in the given cues and ignoring absent terms
- [x] 1.3 Add failing unit test in `tests/test_subtitles.py` for `get_series_glossary` user config overrides from `~/.config/ani-cli/glossary.json`
- [x] 1.4 Add failing unit test in `tests/test_subtitles.py` for `_build_translation_payload` including `anime_title` and active glossary with inflection instruction in system prompt

## 2. Core Implementation (Green Phase)

- [x] 2.1 Implement `get_series_glossary` and `extract_active_glossary` in `src/ani_cli_sync/subtitles.py`
- [x] 2.2 Wire `anime_title` into `translate_cues_llm`, `_translate_single_batch`, and `prepare_subtitles`
- [x] 2.3 Verify all series context and glossary unit tests pass green
- [x] 2.4 Run ADR-012 sensitivity probe on glossary injection (weaken glossary injector to omit terms or prompt block, observe test failure red, restore, observe pass green) and record verification

## 3. Quality & Regression Verification

- [x] 3.1 Run full unit test suite via `PYTHONPATH=src python3 -m unittest discover -s tests` and verify all tests pass
- [x] 3.2 Run `python3 scripts/ruff_count_ratchet.py` and verify ruff count matches baseline (16) with no new lint errors
- [x] 3.3 Validate OpenSpec change completeness via `mise exec -- openspec validate series-context-and-glossary`
