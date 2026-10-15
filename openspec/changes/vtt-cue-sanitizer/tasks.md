# Tasks

## 1. Test Scaffolding (TDD Red Phase)

- [x] 1.1 Add failing unit test in `tests/test_subtitles.py` for `sanitize_cue_text` stripping WebVTT classes (`<c.color>`), voice spans (`<v Speaker>`), and HTML tags (`<i>`, `<b>`) while preserving readable text
- [x] 1.2 Add failing unit test in `tests/test_subtitles.py` for stripping ruby phonetic tags (`<rt>phonetic</rt>`) while preserving the base kanji/character text
- [x] 1.3 Add failing unit test in `tests/test_subtitles.py` for HTML entity decoding (`&amp;`, `&quot;`, `&nbsp;`, `&lt;`, `&gt;`) and invisible unicode artifact removal (`\u200b`, `\u200e`)
- [x] 1.4 Add failing unit test in `tests/test_subtitles.py` for empty tag-only cue pruning and non-tag punctuation preservation (`<3`, `x < y`)

## 2. Core Implementation (Green Phase)

- [x] 2.1 Implement `sanitize_cue_text` in `src/ani_cli_sync/subtitles.py` and wire it into `parse_vtt`
- [x] 2.2 Verify all sanitization unit tests pass green
- [x] 2.3 Run ADR-012 sensitivity probe on tag stripping regex (weaken regex to leave tags intact, observe test failure red, restore, observe pass green) and record verification

## 3. Quality & Regression Verification

- [x] 3.1 Run full unit test suite via `PYTHONPATH=src python3 -m unittest discover -s tests` and verify all tests pass
- [x] 3.2 Run `python3 scripts/ruff_count_ratchet.py` and verify ruff count matches baseline (16) with no new lint errors
- [x] 3.3 Validate OpenSpec change completeness via `mise exec -- openspec validate vtt-cue-sanitizer`
