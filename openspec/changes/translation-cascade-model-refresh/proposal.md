# Proposal: Translation Cascade Model Refresh

## Why

The subtitle translation cascade resolves three models by default:
`minimax-m3`, `gemini-2.5-flash`, `llm-tower`.

Two of the three no longer exist. `gemini-2.5-flash` was pruned from the
LiteLLM gateway on 2026-07-21 (ai-infra commit `1f26d7a`, "prune retired
models"), and `llm-tower` was never a gateway model handle in the current
configuration. Both now answer HTTP 400 "Invalid model name" on the local
proxy, and the tower's inference ports (8000, 8080, 11434, 1234) do not
answer at all.

The failover cascade is only exercised on a quota exhaustion, which is
exactly when a stalled episode matters most. A 429 on `minimax-m3` therefore
advances into two dead models, each burning a retry with backoff before the
cascade reports exhaustion and the episode falls back to the raw English
track.

Measured 2026-10-24 against the local proxy through the shipped translation
code path, one 50-cue batch per model:

| model | wall time | result | same-model backup |
|---|---|---|---|
| `gemini-3.1-flash-lite` | 2.9s | OK | none |
| `minimax-m3` | 7.6s | OK | yes (OpenCode Go) |
| `minimax-m3.1-flash` | 15.9s | OK | yes (OpenCode Go) |
| `gemini-3.8-flash` | 9.2s | FAIL | 429 quota exhausted |
| `qwen-3.8-flash` | 39.6s | OK | yes (OpenCode Go) |
| `glm-5.3-flash` | 45.0s | FAIL | socket timeout |

All six are already registered in ai-infra's `model-governance.json` at tier
T2, so no gateway change and no new credential is required.

Serves issue: [#92](https://github.com/niStee/ani-cli-sync/issues/92)

## What Changes

- Replace the two dead default candidates with live, tier-T2-governed models
  that each answer the translation workload.
- Keep `minimax-m3` as the primary: it is the ADR-001-recommended
  non-reasoning model, it is the fastest candidate that also has a
  same-model backup deployment under ADR-006, and its measured German output
  is sound.
- Add `minimax-m3.1-flash` as the second candidate: the current MiniMax
  generation, tier T2, with the same-model OpenCode Go backup, and the second
  fastest measured candidate that survives a quota event.
- Add `gemini-3.1-flash-lite` as the third candidate: the measured-fastest
  model (2.9s), which covers the case where both MiniMax deployments are
  quota-exhausted on the shared Token Plan.
- Update the cascade recorded in `docs/adr/ADR-001` section 3 and in
  `AGENTS.md`, so the documentation does not describe a cascade that cannot
  run.

## Out of Scope

- Changing the LiteLLM gateway, its model routes, or `model-governance.json`.
  Every candidate is already registered and routed; this change only consumes
  existing handles.
- Adding a model that is not already registered in `model-governance.json`.
  A model without a governance entry would fail the gateway's closed check
  and is therefore not a candidate.
- Restoring `llm-tower` as a translation endpoint. The tower's inference
  service is not part of the current fleet deployment contract
  (`machines.yaml` lists only `actions-runner` for that node), so re-adding
  it would encode a dependency that fleet health does not maintain.
- Changing the failover *policy*: 429 still fast-fails to the next candidate,
  transient 5xx still retries with backoff. Only the membership of the
  candidate list changes.
- Changing `qwen-3.8-flash` or `glm-5.3-flash` behaviour. `qwen-3.8-flash`
  measured 39.6s, which is too slow to sit in front of a viewer waiting for
  playback; `glm-5.3-flash` timed out at the 45s per-batch budget.

## Impact

- `src/ani_cli_sync/subtitles.py`: `DEFAULT_FALLBACK_MODELS`.
- `tests/test_subtitles.py`: the two assertions that pin the old cascade.
- `docs/adr/ADR-001-media-subtitle-translation-and-sync.md`: section 3.
- `AGENTS.md`: the cascade list and the measurement table.

## Capabilities

### Modified Capabilities
- `subtitle-translation-failover`: the default cascade order changes from
  two dead handles to three live, tier-T2-governed models.
