# subtitle-translation-failover Specification

## Purpose
Enforces resilient multi-tier model selection and automatic failover for subtitle translation, differentiating quota exhaustion from transient server errors while preserving cue alignment.

## Requirements

### Requirement: Configurable Model Cascade Order

The translation pipeline SHALL resolve a prioritized list of candidate models
from configuration, attempting translation against each model in sequence.

The default cascade SHALL contain only models that are registered in the
gateway's model governance registry and reachable through the local proxy.
The default cascade SHALL NOT contain a model that the gateway rejects as an
unknown model handle.

#### Scenario: Default model cascade
- **WHEN** no custom model list is configured via `ANI_CLI_SYNC_LLM_MODELS`
- **THEN** the pipeline resolves the default prioritized cascade (`minimax-m3.1-flash`, `gemini-3.1-flash-lite`)

#### Scenario: Every default candidate is a live gateway handle
- **WHEN** the default cascade is resolved
- **THEN** each candidate is registered in the gateway's model governance registry
- **AND** each candidate is accepted by the gateway as a known model handle

#### Scenario: Custom model cascade configuration
- **WHEN** `ANI_CLI_SYNC_LLM_MODELS` is set to a comma-separated list of model identifiers
- **THEN** the pipeline attempts candidate models strictly in the configured order

#### Scenario: Explicit override of a default candidate
- **WHEN** `ANI_CLI_SYNC_LLM_MODEL` names a model that is not part of the default cascade
- **THEN** the pipeline attempts that model as the sole candidate
- **AND** the pipeline does not fall back to the default cascade

### Requirement: Immediate Failover on Quota Exhaustion

When a model endpoint signals quota exhaustion or rate limits (HTTP 429), the pipeline SHALL immediately advance to the next candidate model without wasting retry attempts.

#### Scenario: Fast failover on HTTP 429
- **WHEN** a batch translation request returns HTTP 429 or indicates resource exhaustion
- **THEN** the pipeline logs the quota exhaustion and immediately submits the batch to the next candidate model in the cascade

### Requirement: Bounded Retry with Backoff on Transient Errors

When a model endpoint encounters transient errors (HTTP 500, 502, 503, 504, or network timeouts), the pipeline SHALL retry with exponential backoff before escalating to the next model.

#### Scenario: Transient error recovery on retry
- **WHEN** a translation request encounters a transient 503 error and the retry attempt succeeds
- **THEN** the pipeline accepts the response without switching models

#### Scenario: Transient error exhaustion triggers failover
- **WHEN** all retry attempts for the active model fail due to transient errors
- **THEN** the pipeline logs the failure and advances to the next candidate model in the cascade

### Requirement: Graceful Exhaustion Fallback

When all candidate models in the cascade are exhausted without a successful translation, the pipeline SHALL cleanly report failure and retain original source cues without corrupting playback.

#### Scenario: Complete cascade failure
- **WHEN** every candidate model in the cascade fails or exhausts its retry budget
- **THEN** the pipeline logs a complete exhaustion warning and cleanly falls back to the original source subtitle cues without shifting timestamps
