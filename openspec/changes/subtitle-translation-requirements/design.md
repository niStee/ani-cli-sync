# Design

## Context

This package captures documentation edits only. No runtime requirement changes are proposed, and `skip_specs: true` is intentional. Source and current specs at pinned main `87314dc54de181b928a49c2711f3783efca5c532` are the evidence baseline; no live gateway was queried.

Observed behavior:
- `pyproject.toml:15` has `dependencies = []`; only the separate `subsync` extra installs VAD packages (`pyproject.toml:34-37`).
- `subtitles.py:22-25` uses standard-library HTTP and concurrency. `DEFAULT_API_BASE` is `http://localhost:4000/v1` unless `LITELLM_API_BASE` was set before module import (`:41`).
- `DEFAULT_FALLBACK_MODELS` is exactly `minimax-m3.1-flash`, then `gemini-3.1-flash-lite` (`:47-50`), with the documented environment override order (`:54-66`).
- Requests carry `Authorization: Bearer dummy` (`:637`). No `LITELLM_API_KEY` read exists; setting it is unsupported and has no effect in this client.
- Translation can be skipped by existing cache files or a usable native track (`prepare_subtitles`, `:869-1022`). An explicit secondary English track is reused rather than translated; no secondary request disables it.
- Exhausted translation returns `None` with warnings (`:860-866`), and the stream English track is used as primary when available (`:1001-1006`). The current specs promise this fallback. Batches are 50 cues with five workers and a 45-second per-batch socket timeout; cold misses and retries can delay playback.
- `--no-sub-fallback` takes the native ani-cli command path without `resolve_stream_info` or this translation plan. `--dub` also bypasses measurement/subtitle fallback as already documented.

## Goals / Non-Goals

**Goals:**
- One accurate, non-duplicative explanation for users and maintainers.
- Bounded corrections to known stale claims, not a wholesale README rewrite.

**Non-Goals:**
- New authentication, primary-language behavior, models, dependencies, runtime code, tests, or canonical spec changes.

## Exact edit plan

### 1. README.md

**Features, current line 26:** Replace the implication that Traditional Chinese/Pinyin is always generated and that caching is zero-latency. Say a secondary track is generated/attached only on explicit request; cached subtitles avoid a repeated translation request, not every source of startup latency.

**Prerequisites, after current line 39:** Add a short `Optional subtitle translation service` subsection with:
- No LiteLLM Python package is required. Core Python dependencies are zero; HTTP is standard-library `urllib`.
- An OpenAI-compatible LiteLLM HTTP service is required only when a requested track must be synthesized. It normally runs at `http://localhost:4000/v1`; `LITELLM_API_BASE` overrides the base before startup.
- Default cascade is `minimax-m3.1-flash`, then `gemini-3.1-flash-lite`. Keep existing override names `ANI_CLI_SYNC_LLM_MODELS` and `ANI_CLI_SYNC_LLM_MODEL` and their precedence in the architecture section rather than duplicating a long reference here.
- This client sends fixed `Bearer dummy`, intended for a local proxy that accepts it. `LITELLM_API_KEY` is not read and does not configure authentication. Do not claim remote authenticated endpoints are supported by setting that variable.
- The user must provision and run that service separately. This package neither installs nor starts it.

**Subtitle architecture, current lines 182-197:**
1. Replace `deepseek-v4-flash` at line 191 with the actual cascade and existing override precedence.
2. Keep secondary disabled by default; say explicit `en` reuses the native English track with no translation request, not `0s` overall latency.
3. Explain full native tracks and cached generated tracks avoid translation. Preserve cache location but replace `0.0003s instant` with `avoids another translation request`.
4. Replace next-episode `0s wait time` at line 195 with `can hide translation work during current playback when prefetch succeeds`; note a cold translation or failed prefetch can still delay playback.
5. Add `Failure and bypass` text: batch/model failures emit warnings; when no requested track can be produced, a stream English track is the primary fallback where available; playback is not described as guaranteed translated. `--no-sub-fallback` bypasses synthesis/fallback and uses native ani-cli tracks. Secondary remains disabled if its requested track cannot be produced.
6. Add one explicit separation sentence: `--sub-sync=auto` and its `subsync` extra concern optional VAD timing measurement; they are not needed for ordinary LLM subtitle translation and do not supply the HTTP service.

**CLI reference:** No generated help rewrite beyond ensuring any surrounding prose agrees with secondary-disabled and no-sub-fallback behavior. Do not invent flags or authentication options.

### 2. AGENTS.md

**Key Architectural Principles item 5, current line 25:** Add that the service is an optional HTTP dependency used only when synthesis is needed, while core remains zero-dependency. Retain the two-model default and secondary-disabled statements.

**Translation Model Cascade, after current line 70:** Add a compact `Runtime requirements` paragraph stating normal endpoint, `LITELLM_API_BASE` override, fixed `Bearer dummy`, and unsupported `LITELLM_API_KEY`. Do not suggest credential lookup, add KWallet keys, or change model governance.

**Subtitle architecture context, after current line 133 or before Commands:** Document cache/native-track avoidance, warnings and English fallback, cold-run delay, `--no-sub-fallback`, and separation of the optional `subsync` extra. Avoid repeating the full measured model table elsewhere. Correct any absolute prefetch/cache latency statement introduced by the edit; the existing cold `~34s` measurement is a dated measurement, not a guarantee, and must remain labeled as such.

### 3. docs/adr/ADR-001-media-subtitle-translation-and-sync.md

**Tiered Translation Failover Cascade, current lines 45-53:** Replace `the three measured, tier-T2-governed models above` with `the two governed models above`. Do not retroactively alter the historical fact that two dead handles were replaced; clarify only the current count.

**Decision Drivers, current line 22:** Replace `Playback must never hang or stall on translation` with the actual bounded/graceful goal: failures warn and fall back, while cold translation, retries, and socket timeouts may delay playback. Keep this an ADR clarification, not a new runtime guarantee.

**Optional small boundary note under Decision 3:** State that LiteLLM is an external HTTP service, not a Python runtime dependency, and translation is skipped when suitable cached/native tracks exist. Do not redesign authentication or VAD in this ADR cleanup.

### 4. Source docstrings/comments only

**`src/ani_cli_sync/subtitles.py` module docstring, current lines 1-11:** Replace `deepseek-v4-flash` with `minimax-m3.1-flash then gemini-3.1-flash-lite by default`; say the secondary track is opt-in. This is a comment-only edit and must not alter imports or executable statements.

**`prepare_subtitles` docstring, current lines 880-888:** Add one sentence that cached/native tracks avoid model calls, and failed generation can fall back to stream English. Do not add unsupported guarantees about warnings beyond the observed logger behavior.

**`translate_cues_llm` docstring, current lines 759-765:** Identify the endpoint as an OpenAI-compatible HTTP service, not a required Python LiteLLM package. No function signature or default changes.

No other source file needs an edit for this issue.

## Acceptance matrix

| Check | Required result |
|---|---|
| Dependency clarity | README, AGENTS, and ADR distinguish empty core Python dependencies from an optional external HTTP translation service |
| Endpoint/auth | Normal `localhost:4000/v1`, `LITELLM_API_BASE`, fixed `Bearer dummy`, and no `LITELLM_API_KEY` support match source |
| Cascade | No stale DeepSeek translation default remains in README, AGENTS, ADR, or module docstring; two defaults appear in the correct order |
| Tracks | Secondary is explicitly opt-in; native English secondary avoids translation; unavailable secondary stays disabled |
| Cache/native | Docs say these avoid translation, not that all playback or prefetch has zero latency |
| Failure/bypass | Warnings, English primary fallback where available, possible delay, and `--no-sub-fallback` are documented |
| Extras | `subsync` is separate from translation requirements |
| Scope | No canonical `openspec/specs/` change, executable Python diff, dependency change, auth feature, or general primary-language work |
| Mechanics | `git diff --check` passes; every relative Markdown link resolves; no live service is needed for the edit review |

## Delegated mechanical edit brief

After GPT orchestrator approves this plan, assign only the bounded edit to a low-tier mechanical implementer (MiniMax-M3.1-Flash is suitable, but no separate GLM test stage is needed). Touch exactly `README.md`, `AGENTS.md`, `docs/adr/ADR-001-media-subtitle-translation-and-sync.md`, and docstrings in `src/ani_cli_sync/subtitles.py`. Do not change runtime logic, tests, canonical specs, dependencies, or service configuration. Preserve existing measured tables as dated historical measurements. Run `git diff --check`, inspect `git diff` against this matrix, and check relative links. GPT then reviews the rendered diff for factual consistency and scope; final human acceptance remains required.

## Practice review

- **Repository source and current specs at pinned SHA, read 2026-10-30: confirmed.** The concrete defaults and behaviors above are source-verified; the package deliberately introduces no external runtime practice to review.
- [Python `urllib.request` documentation](https://docs.python.org/3/library/urllib.request.html), current standard-library reference read 2026-10-30: **confirmed** HTTP is provided by the standard library; no LiteLLM Python SDK is implied.

**Reuse check: adopt.** Reuse existing README/AGENTS/ADR/docstrings and existing runtime terminology; do not add a documentation framework, duplicate guide, or new service wrapper.

## Risks / Trade-offs

- **[Risk]** Repeating details in four places creates future drift. **Mitigation:** README carries user essentials, AGENTS carries maintainer constraints, ADR carries architectural rationale, and docstrings only fix immediate stale descriptions.
- **[Risk]** Describing fixed dummy auth could be mistaken for secure remote configuration. **Mitigation:** explicitly scope it to a normally local proxy and state that `LITELLM_API_KEY` is unsupported.
- **[Risk]** Comment-only source edits accidentally alter code. **Mitigation:** review executable diff absence and run only the focused documentation/diff checks, not network tests.

## Pilot override and traceability

The operator authorized the pilot on 2026-10-30 without intermediate human spec/test approval. GPT orchestrator plan and diff review are the quality gates; final human acceptance remains. No behavioral spec, GLM tests, or production implementation is introduced by this docs-only package. Proposal items map to exact edits 1-4 and every acceptance row above.
