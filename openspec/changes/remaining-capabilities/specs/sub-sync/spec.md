# Automatic subtitle timing baseline

## Purpose

Describes optional primary-track timing measurement and episode-local application,
including defined confidence limits and playback-preserving failure behavior.

## ADDED Requirements

### Requirement: Automatic timing is opt-in with nonzero manual precedence
Automatic subtitle timing SHALL default to off. When auto is requested, a nonzero
manual delay SHALL suppress measurement. Zero manual delay, including explicit
zero, SHALL permit measurement on the managed subtitle path.

#### Scenario: Off by default
- **WHEN** no automatic timing request is configured
- **THEN** no automatic audio/subtitle offset measurement is performed

#### Scenario: Manual nonzero delay
- **WHEN** auto is requested with manual delay -3.8 seconds
- **THEN** -3.8 seconds is used without automatic measurement

#### Scenario: Explicit zero
- **WHEN** auto is requested with --sub-delay=0 and a managed primary track is available
- **THEN** automatic measurement is attempted

### Requirement: Primary first-cue measurement uses the player delay sign
Automatic measurement SHALL compare the first parsed primary subtitle cue with
the detected speech onset. The shift SHALL equal speech onset minus cue time;
it SHALL NOT claim to identify dialogue or exclude opening lyrics automatically.

#### Scenario: Late subtitles
- **WHEN** the first cue is at 41.87 seconds and detected speech begins at 38.5 seconds
- **THEN** the calculated shift is -3.37 seconds, pulling subtitles earlier

#### Scenario: Early subtitles
- **WHEN** the first cue is at 21.54 seconds and detected speech begins at 21.79 seconds
- **THEN** the calculated shift is +0.25 seconds, delaying subtitles

#### Scenario: Two subtitle tracks
- **WHEN** primary and secondary tracks are attached
- **THEN** the primary track determines the measured global subtitle shift

### Requirement: Missing evidence leaves timing unchanged
Missing optional VAD support, missing primary cues, audio extraction failure,
subtitle fetch failure, no detected speech, or a measurement exception SHALL
leave automatic timing unchanged and SHALL NOT abort otherwise viable playback.

#### Scenario: VAD unavailable
- **WHEN** auto is requested but the optional VAD support is unavailable
- **THEN** the missing support is reported and playback continues without an automatic shift

#### Scenario: No cues or no speech
- **WHEN** measurement cannot find a first primary cue or usable speech onset
- **THEN** timing remains unchanged and playback continues

#### Scenario: Measurement failure
- **WHEN** audio extraction, subtitle access, or measurement raises an error
- **THEN** the failure is reported and no guessed automatic shift is applied

### Requirement: Plausibility and negligible-shift limits
An absolute measured offset greater than 60 seconds SHALL be rejected. A
confident offset of absolute magnitude less than 0.05 seconds SHALL not emit
a timing correction. Exactly 60 seconds SHALL pass the plausibility limit.

#### Scenario: Implausible first cue
- **WHEN** the calculated shift is +84.8 seconds
- **THEN** it is reported as unconfident and no automatic correction is applied

#### Scenario: Plausibility boundary
- **WHEN** an otherwise confident measured shift is exactly -60 seconds
- **THEN** it is not rejected solely by the plausibility limit

#### Scenario: Negligible shift
- **WHEN** a confident measured shift is +0.04 seconds
- **THEN** no subtitle-delay flag is added

#### Scenario: Non-negligible boundary
- **WHEN** a confident measured shift is +0.05 seconds
- **THEN** that shift is applied

### Requirement: Measured shifts are episode-local
An automatic shift SHALL apply only to its measured episode. A subsequent
episode SHALL start from the invocation's manual configuration and be measured
independently when eligible, not inherit the previous automatic shift.

#### Scenario: Consecutive different offsets
- **WHEN** two eligible episodes measure -3.37 and +0.25 seconds respectively
- **THEN** each receives its own correction rather than replaying the first shift

#### Scenario: Second measurement fails
- **WHEN** the first episode has a measured shift and the second has no confident result
- **THEN** the second episode receives no inherited automatic correction

### Requirement: Unsupported playback paths do not measure
Dub playback, disabled managed subtitle fallback, and absence of a primary
subtitle track SHALL bypass automatic timing measurement.

#### Scenario: Native or dubbed path
- **WHEN** dub or --no-sub-fallback is selected with auto configured
- **THEN** no automatic measurement is performed

#### Scenario: No primary track
- **WHEN** the managed subtitle plan has no primary track
- **THEN** no measurement-based correction is applied
