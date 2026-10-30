# Proposal

## Why

[Issue #54](https://github.com/niStee/ani-cli-sync/issues/54) asks to reduce the ratchet script's historical complexity delta. The implementation now guards CI against lint regressions, but `main()` combines argument, base-ref, execution, baseline, update, and reporting decisions. Refactoring it without first expanding black-box characterization could change a fail-closed gate into a fail-open one.

## What Changes

- Add characterization coverage for supported parsing, tracked-file, subprocess, base-ref, exact-count, monotonic-update, output, and exit-code behavior before restructuring.
- Decompose the ratchet into small decision and execution helpers while preserving existing public helper contracts and observable CLI behavior.
- Exercise positive/negative pairs and temporary-mutant sensitivity probes for every load-bearing guard.
- Record the exact historical Codacy PR 53 evidence separately from current or future closure evidence.
- Keep non-object-JSON and baseline-write-error defects visible as out-of-scope defects rather than silently fixing or redefining them.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None. This is a behavior-preserving refactor and sets `skip_specs: true`; no behavior proposal is fabricated for a refactor.

## Impact

The later change is bounded to `scripts/ruff_count_ratchet.py` and `tests/test_ruff_ratchet.py`. The baseline, CI workflows, Ruff rule selection, canonical specs, and unrelated tests remain unchanged. Historical `test_ci_config.py` complexity is evidence, not a reason to edit that file.

## Out of scope

Changing exit meanings, accepting lower counts without `--update`, broadening/narrowing tracked-file scope, replacing subprocess execution, hardening PATH/executable resolution, non-object-JSON policy, write-error translation, dependency/tool-version changes, blanket `nosec`/`nosemgrep` suppressions, and unrelated cleanup. GPT orchestrator approves the characterization and refactor plan and reviews tests; final human acceptance remains required.
