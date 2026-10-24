# Spec Delta

## Purpose

Replace the two dead default models in the subtitle translation cascade with
live, tier-T2-governed models, so that a quota exhaustion on the primary
model advances to a working candidate instead of to an unknown model handle.

## MODIFIED Requirements

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
