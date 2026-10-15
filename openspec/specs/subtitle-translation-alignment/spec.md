# subtitle-translation-alignment Specification

## Purpose
Enforces strict 1:1 index alignment between original subtitle cues and translated subtitles, detecting duplicate cue hallucinations and triggering bisection to preserve accurate dialogue timing.

## Requirements

### Requirement: Reject Hallucinated Adjacent Cue Duplicates

The translation pipeline SHALL reject any translated cue batch where adjacent output cues are identical while the corresponding input source cues contain distinct text.

#### Scenario: Adjacent duplicate rejection
- **WHEN** a translation batch returns identical text for two consecutive cues whose source cues have different text
- **THEN** the pipeline rejects the batch response and initiates recursive bisection

#### Scenario: Legitimate adjacent duplicate accepted
- **WHEN** a translation batch returns identical text for consecutive cues whose source cues also contain identical text
- **THEN** the pipeline accepts the batch without triggering rejection

### Requirement: Key-Indexed Cue Translation Validation

The translation pipeline SHALL enforce key-indexed mapping between source cues and translated cues, verifying that every requested cue index is present in the response exactly once.

#### Scenario: Complete index mapping
- **WHEN** the translation response provides a valid mapping containing all requested cue indices
- **THEN** each translated cue is assigned strictly to its matching source cue timestamp

#### Scenario: Missing or duplicated index
- **WHEN** the translation response omits any requested cue index or provides duplicate indices
- **THEN** the batch validation fails and the pipeline initiates recursive bisection

### Requirement: Fallback on Indivisible Cue Mismatch

When recursive bisection reaches an indivisible leaf batch that continues to fail alignment validation, the pipeline SHALL fall back to preserving the original source cues for the failed items without shifting neighboring cues.

#### Scenario: Leaf failure fallback
- **WHEN** an indivisible leaf cue batch fails translation alignment after all bisection and retry attempts
- **THEN** the pipeline retains the original source text for those cues and preserves their exact timestamps without shifting subsequent dialogue

### Requirement: Reject Untranslated English Echoes

The translation pipeline SHALL reject any translated cue batch where a target non-English cue echoes a multi-word source dialogue line verbatim while neighboring cues are translated.

#### Scenario: Untranslated source echo rejection
- **WHEN** a translation batch into German contains a multi-word cue identical to its source English text while previous cues in the batch are translated
- **THEN** the pipeline rejects the batch response and initiates recursive bisection

### Requirement: Reject Named Entity Phase Shifts

The translation pipeline SHALL reject any translated cue batch where a capitalized entity anchor present in a source cue appears shifted into an adjacent translated cue.

#### Scenario: Entity anchor shift rejection
- **WHEN** a source cue contains a distinct capitalized entity anchor that is absent in its translated cue but present in the adjacent translated cue
- **THEN** the pipeline rejects the batch response and initiates recursive bisection
