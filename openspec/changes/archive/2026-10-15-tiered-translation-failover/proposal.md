# Proposal: Tiered Translation Failover

## Why

Automated subtitle translation currently relies on a single configured model (`DEFAULT_MODEL = "minimax-m3"`). When the primary model encounters rate limits or cloud quota exhaustion (HTTP 429), or transient provider errors (HTTP 500/502/503/504), the pipeline aborts translation entirely and falls back to English without attempting available secondary models or the local sovereign `llm-tower`.

A tiered model failover cascade with differentiated error semantics—instant model advancement on 429 quota exhaustion and bounded exponential backoff on 5xx errors—guarantees translation completion without manual intervention.

Serves issue: [#60](https://github.com/niStee/ani-cli-sync/issues/60)

## What Changes

- Add multi-model fallback cascade support configured via `ANI_CLI_SYNC_LLM_MODELS` (comma-separated list, defaulting to `minimax-m3,gemini-2.5-flash,llm-tower`).
- Implement differentiated error handling in batch translation:
  - **HTTP 429 / RESOURCE_EXHAUSTED**: Immediately advance to the next candidate model without consuming retry budgets on an exhausted endpoint.
  - **HTTP 5xx / Network Timeouts**: Retry with exponential backoff before escalating to the next candidate model.
- Retain strict client-side index alignment, duplicate detection, and bisection safety across all model transitions.
- Fully log failover events for observability without stalling player startup.

### Out of Scope

- Modifying the external LiteLLM proxy routing tables or upstream provider tokens.
- Re-architecting MPV player subtitle rendering.
- VAD speech-to-cue offset measurement (handled independently in `subsync.py`).

## Capabilities

### New Capabilities
- `subtitle-translation-failover`: Manages multi-tier model selection and automatic failover cascade for batch cue translation, enforcing distinct retry policies for quota exhaustion versus transient infrastructure faults.

### Modified Capabilities
<!-- None: baseline specs are in the pilot phase. -->

## Impact

- `src/ani_cli_sync/subtitles.py`: `_translate_single_batch`, `translate_cues_llm`, candidate model resolution.
- `tests/test_subtitles.py`: Unit tests for 429 instant failover, 5xx retry escalation, and multi-model exhaustion fallback.
