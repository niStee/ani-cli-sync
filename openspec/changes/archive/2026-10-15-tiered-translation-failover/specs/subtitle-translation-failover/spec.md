# Spec Delta

## Purpose

Enforces resilient multi-tier model selection and automatic failover for subtitle translation, differentiating quota exhaustion from transient server errors while preserving cue alignment.

## ADDED Requirements

### Requirement: Configurable Model Cascade Order

The translation pipeline SHALL resolve a prioritized list of candidate models from configuration, attempting translation against each model in sequence.

#### Scenario: Default model cascade
- **WHEN** no custom model list is configured via `ANI_CLI_SYNC_LLM_MODELS`
- **THEN** the pipeline resolves the default prioritized cascade (`minimax-m3`, `gemini-2.5-flash`, `llm-tower`)

#### Scenario: Custom model cascade configuration
- **WHEN** `ANI_CLI_SYNC_LLM_MODELS` is set to a comma-separated list of model identifiers
- **THEN** the pipeline attempts candidate models strictly in the configured order

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
