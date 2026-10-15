# Design

## Context

During playback of Attack on Titan Episode 16, a batch translation produced duplicate cues (repeating cue 63 at cue 64 and dropping cue 99), preserving the overall batch count (`len == 50`) while causing a +1 cue timing offset across 35 cues.

The subtitle translation pipeline in `src/ani_cli_sync/subtitles.py` currently relies on:
1. `_build_translation_payload`: serializes cues as `i: <text>`.
2. `_parse_translation_response`: parses JSON array strings.
3. `_translate_single_batch`: validates only `len(parsed) == len(batch)` before re-pairing with source timestamps.

See `proposal.md` for motivation and background.

## Goals / Non-Goals

**Goals:**
- Detect and reject adjacent duplicate translated cues when original source cues differ, preventing silent cue phase shifts.
- Accept key-indexed JSON objects (`{"0": "...", "1": "..."}`) in addition to JSON arrays for explicit 1:1 index fidelity.
- Trigger recursive bisection upon duplicate detection to isolate hallucinating cues while keeping surrounding dialogue translated and perfectly aligned.
- Fall back gracefully to source cues on indivisible leaf batches (`len(batch) <= 2`) without altering timestamps or shifting neighboring cues.
- Maintain zero external runtime dependencies (Python standard library only).

**Non-Goals:**
- Global audio VAD alignment or offset search (`--sub-sync`), which operates on media stream timing rather than LLM translation alignment.
- Altering the LiteLLM proxy configuration or model selection.
- Modifying AniList synchronization logic.

## Decisions

### 1. Semantic Adjacent-Duplicate Rejection in `_translate_single_batch`
- **Approach**: Compare each adjacent pair `(parsed[i], parsed[i-1])` against source `(batch[i], batch[i-1])`. If translated text is identical but source text was distinct, reject the batch response and bisect.
- **Why**: LLM cue shift errors characteristically repeat a dialogue line across two timestamps. Legitimate repetitions (e.g. source has "Yes." followed by "Yes.") are preserved because source lines match.
- **Alternatives considered**:
  - *Full vocabulary n-gram overlap*: Too brittle for short anime dialogue utterances ("Ja", "Nein", "Hier").
  - *Embeddings / Cosine similarity*: Requires external ML libraries, violating the stdlib-only constraint.

### 2. Dual-Format Parsing in `_parse_translation_response` (Array and Key-Indexed Object)
- **Approach**: Support both JSON array (`["..."]`) and JSON object (`{"0": "...", "1": "..."}`). When a dictionary is parsed, verify all integer keys `0..N-1` are present and sort into index order.
- **Why**: Allows future prompt updates or models returning key-value dictionaries to be parsed deterministically, while remaining fully backward-compatible with array responses.
- **Alternatives considered**:
  - *Strict object-only format*: Would break if LiteLLM model falls back to standard array format or if older prompts are used.

### 3. Bisecting on Duplicate Hallucinations
- **Approach**: When a batch contains adjacent duplicates, trigger the existing bisection logic (`batch[:mid]` and `batch[mid:]`). Leaf batches (`len(batch) <= 2`) that fail fall back to the original cues.
- **Why**: Bisection isolates the single problematic cue to a small sub-batch. The rest of the episode remains translated into German, and timestamps are never perturbed.
- **Alternatives considered**:
  - *Immediate whole-batch fallback to English*: Discards 49 good translations because of 1 duplicate.
  - *Local deduplication shift heuristic*: Heuristics risk guessing incorrectly on multi-cue dialogue and corrupting timing downstream.

## Risks / Trade-offs

- **[Risk] Legitimate identical dialogue lines rejected** → **Mitigation**: The check explicitly permits duplicate translations if source cues also have identical normalized lines (`curr_orig == prev_orig`).
- **[Risk] Increased latency if bisection is triggered** → **Mitigation**: Bisection only runs on batches that exhibit duplicate hallucinations; normal well-formed batches complete in a single roundtrip.
