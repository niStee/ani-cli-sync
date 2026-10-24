# Design: Translation Cascade Model Refresh

## Context

The subtitle translation cascade is a client-side concern in
`src/ani_cli_sync/subtitles.py`. It resolves a list of candidate model
handles and tries them in order. The handles are names served by the local
LiteLLM proxy at `http://localhost:4000/v1`, which is the only endpoint the
translator talks to.

Two properties matter for candidate selection:

1. **The handle must exist at the gateway.** An unregistered name is
   rejected with HTTP 400 before any provider is contacted. The gateway
   checks the name against `model-governance.json` and fails closed for
   undeclared models (ai-infra `model-alignment-flash-refresh` spec).
2. **The handle must survive the workload.** The workload is a 50-cue batch
   of anime dialogue with a strict JSON response contract, inside a 45s
   per-batch socket timeout, with no `max_tokens` set on the request.

## Decision

Replace the default candidate list with:

| position | model | rationale |
|---|---|---|
| 1 | `minimax-m3.1-flash` | Current MiniMax generation, tier T2, same-model OpenCode Go backup under ADR-006. Measured 15.9s, sound German output. |
| 2 | `gemini-3.1-flash-lite` | Measured-fastest candidate (2.9s). Covers the case where the MiniMax Token Plan deployment is quota-exhausted. |

The previous primary `minimax-m3` is retired from the cascade. It measured
faster (7.6s) and is still registered and reachable, but the M3.1 generation
supersedes it, and a two-member cascade spends fewer retries per failover
than a three-member one.

### Why not the other measured candidates

- `minimax-m3` (7.6s): qualified, but superseded by the M3.1 generation.
- `gemini-3.8-flash` (9.2s): returned HTTP 429 on the measurement run. It
  stays out of the cascade because a candidate that is quota-exhausted right
  now would consume the fast-fail path on the first quota event.
- `qwen-3.8-flash` (39.6s): correct output, but nearly 40s for one batch is
  too slow to sit in front of a viewer waiting for playback to start.
- `glm-5.3-flash` (45.0s): exceeded the 45s per-batch socket timeout.

### Why `llm-tower` is not restored

The tower's inference ports (8000, 8080, 11434, 1234) do not answer. The
fleet manifest declares only `actions-runner` as a deployed service for
`llm-tower`, so the tower's inference endpoint is not maintained by
`fleet-deploy.sh` and is not covered by `fleet-health.sh`. Re-adding it would
encode a dependency the estate does not keep alive. This is a deliberate
omission, not an oversight, and the proposal states it as out of scope.

### Governance alignment

All three candidates are already registered in ai-infra's
`home/dot_config/litellm/model-governance.json`:

- `minimax-m3.1-flash`: tier T2, `anthropic/MiniMax-M3.1-Flash` primary,
  `openai/minimax-m3.1-flash-free` backup.
- `gemini-3.1-flash-lite`: tier T2, `gemini/gemini-3.1-flash-lite` primary.
- `minimax-m3`: tier T2, `anthropic/MiniMax-M3` primary,
  `openai/minimax-m3` backup. Registered and reachable, retired from the
  cascade in favour of the M3.1 generation.

ADR-006 prohibits cross-model fallback at the gateway; the cascade here is a
client-side cross-model failover, which is the layer ADR-006 delegates that
responsibility to. The two MiniMax candidates additionally have same-model
backups inside the gateway, so a gateway-level retry of the primary does not
need to reach the cascade.

`gemini-3.1-flash-lite` has no same-model backup. It is placed last for
exactly that reason: it is the candidate of last resort for the shared
Token Plan exhaustion case, not the one expected to carry a failover.

## Behavioural impact

`get_candidate_models()` resolution order changes. The failover policy is
untouched:

- HTTP 429 still fast-fails to the next candidate without consuming retries.
- Transient 5xx and socket timeouts still retry with backoff before the
  candidate is abandoned.

The only difference in failure behaviour is that the cascade no longer walks
into unknown model handles. A 429 on the primary now advances to a model
that answers.

## Test design

The cascade membership is observable behaviour and is pinned by two
assertions in `tests/test_subtitles.py`:

- `test_get_candidate_models_default` pins the resolved default list.
- The failover tests pin that a failing candidate advances to the next one.

A third test asserts the stronger property the spec adds: every default
candidate is a handle the gateway accepts. That test is a guard with a
positive/negative pair per ADR-012:

- positive: every default candidate is present in the gateway's
  `/v1/models` catalogue (read-only, no generation).
- negative: a synthetic handle that the gateway does not serve is detected
  as absent.

The negative case pins the detection itself, so the guard cannot rot into a
no-op that passes because the catalogue endpoint is unreachable.

## Documentation impact

- `docs/adr/ADR-001` section 3 lists the cascade. It is amended in the same
  change so the ADR does not describe dead handles.
- `AGENTS.md` lists the cascade and the measurement table. Both are updated
  to the 2026-10-24 measurements.
