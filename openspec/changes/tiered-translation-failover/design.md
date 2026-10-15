# Design: Tiered Translation Failover

## Context

`src/ani_cli_sync/subtitles.py` currently binds a single model (`DEFAULT_MODEL = "minimax-m3"`). Translation is invoked via `translate_cues_llm(cues, target_lang, model=...)`. In `_translate_single_batch`, `urllib.request.urlopen` executes against the LiteLLM proxy endpoint. If the model encounters HTTP 429 (Resource Exhausted) or persistent 5xx server spikes, the retry loop either exhausts retries on the dead model or aborts, causing `translate_cues_llm` to fail completely.

The project operates under a strict constraint: standard library only (zero external runtime dependencies).

## Goals / Non-Goals

**Goals:**
- Implement candidate model cascade resolution via `get_candidate_models()`: supports `ANI_CLI_SYNC_LLM_MODELS` (comma-separated list), falls back to `ANI_CLI_SYNC_LLM_MODEL` if set, and defaults to `["minimax-m3", "gemini-2.5-flash", "llm-tower"]`.
- Enforce differentiated error handling:
  - HTTP 429 quota exhaustion signals immediate model failover across the batch pipeline without wasting retry delays.
  - HTTP 500/502/503/504 errors trigger bounded exponential backoff on the active model before escalating to the next model in the cascade.
- Maintain consistent translation style and client-side cue alignment by failover at the episode cue-list level when quota is exhausted.

**Non-Goals:**
- External proxy configuration or modifying LiteLLM server deployment files.
- Implementing asynchronous event loops (threads via `concurrent.futures.ThreadPoolExecutor` remain the standard library concurrency model).

## Decisions

### Decision 1: Model Failover Hierarchy at the Episode Level
When a model encounters HTTP 429 (quota exhaustion), it is exhausted across the entire account or deployment. Rather than letting every batch worker independently suffer 429 errors and retries, a 429 error escalates to fail over the remaining translation attempts to the next candidate model in the cascade.

*Alternatives considered:*
- Per-batch independent failover: Rejected because mixing different models across 50-cue batches within the same episode causes stylistic jumps and wastes worker slots retrying known-exhausted quotas.

### Decision 2: Differentiated HTTP Error Handling via urllib
`urllib.error.HTTPError` provides explicit status codes:
- `code == 429` (or `RESOURCE_EXHAUSTED` in response payload): raise a distinct `QuotaExhaustedError` (or signal) that immediately breaks the current model's attempt and triggers candidate failover.
- `code in (500, 502, 503, 504)`: transient gateway/upstream failure; retry with backoff (`time.sleep(min(2.0 * (1.5 ** attempt), 10.0))`).

*Alternatives considered:*
- Generic exception catch: Flattens 429 into a standard retry loop, wasting 45–90s waiting on quota that will not replenish in seconds.

### Decision 3: Backward-Compatible Configuration
`get_candidate_models(model_arg: str | None = None) -> list[str]`:
1. If explicit `model_arg` is passed and non-empty, use `[model_arg]`.
2. If `ANI_CLI_SYNC_LLM_MODELS` is defined in `os.environ`, parse comma-separated items.
3. If `ANI_CLI_SYNC_LLM_MODEL` is defined in `os.environ`, use `[val]`.
4. Otherwise, default to `["minimax-m3", "gemini-2.5-flash", "llm-tower"]`.

## Risks / Trade-offs

- [Secondary cloud model rate limits] → The cascade cascades down to the sovereign unmetered `llm-tower` endpoint.
- [Model output variation across tiers] → All outputs pass through the identical `_parse_translation_response`, `_has_hallucinated_duplicates`, `_has_untranslated_echo`, and `_has_anchor_phase_shift` validation pipeline.
