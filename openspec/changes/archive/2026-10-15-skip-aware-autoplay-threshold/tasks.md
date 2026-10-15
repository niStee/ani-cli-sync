# Tasks

## 1. Test Suite Scaffolding (TDD Red Phase)

- [x] 1.1 Add failing unit test in `tests/test_autoplay_stop.py` for skip-aware threshold (`_should_advance` with `duration=1463.5`, `skip_seconds=176.0`, `elapsed=1308.0` returns `(True, ...)`) and verify test fails red via `PYTHONPATH=src python3 -m unittest tests/test_autoplay_stop.py`
- [x] 1.2 Add unit test in `tests/test_autoplay_stop.py` for 80% baseline without skip metadata (`elapsed=1260.0`, `duration=1440.0`, `skip_seconds=0.0` advances; `elapsed=1080.0` stops)
- [x] 1.3 Add unit test in `tests/test_autoplay_stop.py` for unknown-duration fallback at 1150s (`elapsed=1200.0` advances; `elapsed=660.0` stops)

## 2. Implementation & Sensitivity Verification (Green Phase)

- [x] 2.1 Implement `_calculate_skip_seconds` and update `_should_advance` in `src/ani_cli_sync/cli.py` to calculate threshold based on effective narrative duration and updated 80% / 1150s baseline
- [x] 2.2 Wire `_calculate_skip_seconds(stream_info)` into the `cmd_watch` playback loop in `src/ani_cli_sync/cli.py`
- [x] 2.3 Run ADR-012 sensitivity probe on skip-aware threshold (temporarily weaken check or ignore skip_seconds, observe test failure red, restore, observe test pass green)

## 3. Quality & Regression Verification

- [x] 3.1 Run full unit test suite via `PYTHONPATH=src python3 -m unittest discover -s tests` and verify all tests pass
- [x] 3.2 Run `python3 scripts/ruff_count_ratchet.py` and verify ruff count matches baseline (18) with no new lint errors
- [x] 3.3 Validate OpenSpec change completeness via `mise exec -- openspec validate skip-aware-autoplay-threshold`
