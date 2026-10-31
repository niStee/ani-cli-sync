# Proposal

## Why

[Issue #89](https://github.com/niStee/ani-cli-sync/issues/89) needs a clear explanation of what subtitle translation requires. Current documentation names a stale model, implies an always-on secondary track, and makes absolute latency claims; it does not clearly distinguish an optional HTTP service from Python dependencies.

## What Changes

- Document the existing translation requirements and behavior in README, AGENTS.md, ADR-001, and the relevant source docstrings.
- State that core Python dependencies remain empty and HTTP uses `urllib`; a normally local OpenAI-compatible LiteLLM service is needed only when translation is actually required.
- Document the default endpoint and model cascade, fixed `Bearer dummy` behavior, unsupported `LITELLM_API_KEY`, opt-in secondary track, cache/native-track avoidance, warnings and English fallback, possible translation delay, and `--no-sub-fallback` bypass.
- Keep the optional `subsync` extra and VAD installation separate from subtitle translation.
- Correct stale DeepSeek references, absolute latency wording, and ADR-001's three-versus-two model inconsistency without changing runtime behavior or canonical specs.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None. This is documentation-only synchronization; `.openspec.yaml` sets `skip_specs: true`.

## Impact

Only documentation and comments/docstrings are in scope for the later mechanical edit. No Python logic, tests, dependency declarations, service configuration, credentials, or live calls.

## Out of scope

Authentication configurability, generalized primary-language support, new runtime options, model changes, VAD redesign, and all implementation. Under the pilot, GPT orchestrator reviews this documentation plan and the resulting edits; final human acceptance remains required. No GLM test stage or MiniMax production implementation is needed.
