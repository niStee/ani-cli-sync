# ADR-001: Battletested Architecture for Subtitle Translation, Neural VAD Sync, and Playback Integrity

- **Status**: Accepted
- **Date**: 2026-10-15
- **Context**: `ani-cli-sync` media playback, translation, and synchronization pipeline

## Context & Problem Statement

`ani-cli-sync` orchestrates streaming media playback, dual-subtitle display, real-time LLM-based subtitle translation (primarily English to German), Voice Activity Detection (VAD) audio-subtitle alignment, and AniList watch progress synchronization.

Automated subtitle translation and media synchronization pipelines frequently succumb to established industry anti-patterns:
1. **Timestamp Hallucination / Drift**: Passing raw subtitle timestamps to an LLM leads to token drift, misaligned dialogue, or malformed timecodes.
2. **Context Fragmentation vs. Latency Tradeoff**: Translating line-by-line produces fractured grammar and pronoun shifts (*du* vs *Sie*), while overly complex multi-agent critique loops cause unacceptable 60s–180s playback startup stalls.
3. **Quota Lockout & Fragile Endpoints**: A single HTTP 429 quota exhaustion or transient 503 error stalls episode playback if retried blindly without a fast-failing cascade.
4. **VAD Dependency Bloat & Music Bed False Positives**: Pulling PyTorch/CUDA wheels (~5.4GB) for Silero VAD creates massive installation overhead; naive energy or FFT cross-correlation locks onto opening/ending theme songs (OP/ED) or music beds rather than true speech onset.
5. **Watchlist Progress Corruption**: Prematurely marking episodes watched upon early player exits, player crashes, or unverified duration.
6. **Lint Debt & Quality Creep**: Gating inconsistencies between advisory external bots (Codacy) and deterministic local/CI gates (Ruff count ratchet).

## Decision Drivers

- **Zero Runtime Dependencies**: The core package must run purely on Python standard library modules (`urllib.request`, `json`, `dataclasses`, `concurrent.futures`, `time`). Optional extras (like VAD) remain strictly decoupled.
- **Instant Video Startup**: Playback must never hang or stall on translation or synchronization; fallbacks must be fast, deterministic, and graceful.
- **Linguistic Precision**: Consistent register (informal German), accurate idiomatic translation, and dialogue continuity without multi-agent token overhead.
- **AniList Safety**: Never clobber or advance user watchlist progress on incomplete or unverified playback.
- **Spec-Driven Quality**: OpenSpec SDD workflow, ADR-012 sensitivity probes, and strict ratchet enforcement.

## Architectural Decisions

### 1. Structural Isolation & Timestamp Immutability

- **Rule**: Never expose VTT/SRT timestamps, sequence indices, or styling tags to the LLM.
- **Mechanism**: The VTT parser separates structural metadata in Python memory. Only clean text payloads are sent to the LLM via structured key-indexed JSON (`{"0": "...", "1": "..."}`). Python code reinjects translations back onto immutable source timestamps.
- **Ingestion Hygiene**: Cue styling tags (`<c.color>`, `<ruby>`, `<i>`), zero-width spaces, and BOM headers must be sanitized before batching to prevent parser confusion.

### 2. Single-Pass Contextual Batching with Hallucination Circuit Breakers

- **Anti-Pattern Rejected**: Multi-agent critique loops (which inflate latency by 5x–10x and token cost with negligible benefit for real-time subtitle translation).
- **Architecture**: Single-pass batching (25–50 cues per batch). Context is provided via system prompts specifying target language register (informal German, anime context).
- **Hallucination Circuit Breakers**:
  - *Duplicate Rejection*: Reject adjacent duplicate translations when source cues differ; bisect the batch to isolate faulty cues.
  - *Untranslated Echo Rejection*: Reject multi-word English cues echoed identically in German target output.
  - *Anchor Phase Shift Rejection*: Detect and reject named entity shifts across adjacent cues.
  - *Leaf Fallback*: Retain original cue text if alignment or translation cannot be deterministically verified.

### 3. Tiered Translation Failover Cascade

- **Rule**: Cloud models can quota-exhaust (429) at any time. Playback must never fail silently or hang.
- **Architecture**: A prioritized candidate cascade:
  1. High-speed cloud model (`minimax-m3`)
  2. Fallback cloud model (`gemini-2.5-flash`)
  3. Local LLM tower endpoint (`llm-tower`)
- **Fast Failover**: Immediate circuit break on HTTP 429 (no retries, instantly advance to next candidate model). Exponential backoff only on transient 503/502.

### 4. Lightweight ONNX-First Neural VAD & Theme Song Immunity

- **Anti-Pattern Rejected**: 5.4GB PyTorch CUDA wheels and whole-file FFT cross-correlation (which plateaus in dialogue-dense anime).
- **Architecture**:
  - Neural VAD (Silero) using CPU-only `onnxruntime` (~50MB footprint).
  - Audio extraction via `ffmpeg` capped to a minimal demux window (e.g. 90s–180s) with `-extension_picky 0` and Referer headers.
  - Dialogue onset must account for intro music: when `intro_skip` timestamps exist, onset detection either ignores the intro window or compares post-intro speech.

### 5. Non-Destructive Autoplay & Progress Integrity

- **Rule**: AniList progress is a strictly monotonic, user-approved state.
- **Architecture**:
  - Effective duration threshold: `(total_duration - skip_seconds) * 0.80`.
  - Manual stop, player error, or abort always preserves current progress without mutation.

### 6. Dual-Gate Quality Standard (Deterministic Ratchet vs. Advisory Bot)

- **Architecture**:
  - The deterministic, binding gate is the local & CI Ruff count ratchet (`ruff_count_ratchet.py`) with zero slack.
  - External static analyzers (Codacy) are non-blocking advisory signals. Agent workspaces (`.agents/`, `.claude/`, `openspec/`) and markdown documentation are excluded via `.codacy.yaml` to eliminate prose false-positives.

## Consequences

- Zero runtime dependencies in core remain inviolate.
- Clear separation between mandatory CI gates (ratchet + tests) and advisory bot signals.
- Robust, deterministic subtitle alignment and failover across cloud and local model towers.
