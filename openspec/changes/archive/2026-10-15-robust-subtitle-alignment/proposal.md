# Proposal: Robust Subtitle Translation Alignment

## Why

Issue #64 and live playback of Attack on Titan Episode 16 revealed that when an LLM batch response duplicates a translated cue and omits another, the overall batch count remains equal to the input count (`len(parsed) == len(batch)`). The previous count-only check failed to catch the duplicate, causing all subsequent lines in the batch to shift by +1 cue against source audio.

Strict cue alignment must reject duplicate translations that do not exist in the source text and support key-indexed payloads, ensuring bisection isolates the failure without shifting neighboring dialogue.

## What Changes

- Add semantic duplicate detection in `_translate_single_batch`: reject any batch where adjacent translated lines are identical while the source lines differed.
- Support key-value indexed JSON responses (`{"0": "...", "1": "..."}`) in `_parse_translation_response` and prompt instructions to guarantee 1:1 index fidelity.
- Trigger bisection recursion whenever duplicate hallucinations or index gaps are detected.
- Maintain fallback to original English cues for isolated 1–2 cue mismatch leaves.

### Out of Scope

- Modifying the underlying LLM model or proxy configuration.
- Audio VAD offset adjustment (`--sub-sync`), which addresses global stream timing rather than intra-batch LLM shifts.

## Capabilities

### New Capabilities
- `subtitle-translation-alignment`: Enforces 1:1 index alignment between original subtitle cues and LLM translations, rejecting duplicate translations that do not exist in source text and triggering recursive bisection.

### Modified Capabilities
<!-- None: openspec baseline specs are being introduced with this pilot. -->

## Impact

- `src/ani_cli_sync/subtitles.py`: `_translate_single_batch`, `_parse_translation_response`, `_build_translation_payload`.
- `tests/test_subtitles.py`: New unit tests for duplicate detection, key-value index parsing, and regression scenarios.
