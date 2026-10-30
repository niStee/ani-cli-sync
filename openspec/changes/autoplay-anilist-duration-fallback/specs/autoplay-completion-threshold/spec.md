# Spec Delta

## Purpose

Use release-specific HLS duration first, the selected AniList media's general per-episode duration as the next fallback, and the conservative constant only when neither source is usable, without weakening any existing autoplay stop rule.

## MODIFIED Requirements

### Requirement: Conservative Fallback for Unknown Duration

The playback tracker SHALL determine playback duration in strict precedence order: a positive duration summed from the stream's HLS media playlist first; otherwise the selected media's valid positive integer AniList episode duration converted from minutes to seconds; otherwise 1150 seconds. Missing, null, boolean, non-integer, zero, negative, or non-finite AniList duration metadata SHALL be treated as unavailable and SHALL NOT produce a zero or negative completion threshold.

When HLS duration is unavailable and valid AniList duration is used, the tracker SHALL apply the existing 70% skip-aware or 80% no-skip threshold to that fallback duration. When both are unavailable, the tracker SHALL require at least 1150 seconds of playback minus any known skip durations.

The tracker SHALL carry duration metadata for the actual selected media through watchlist, global-search, and interactive selection routes without adding a per-episode AniList request. On sequel rollover, it SHALL replace that metadata with the sequel's duration from the existing sequel relation response; a missing or invalid sequel duration SHALL become unknown rather than inheriting the previous media's duration.

#### Scenario: HLS duration overrides AniList metadata

- **WHEN** HLS reports 1463 seconds, AniList reports 24 minutes, and playback exits with return code 0 after 1308 seconds with 176 seconds of scheduled skips
- **THEN** the tracker uses the HLS duration, applies 70% of 1287 effective seconds, and approves advancing

#### Scenario: AniList minutes supply the no-skip fallback

- **WHEN** HLS duration is unavailable, the selected media reports 24 minutes, no skip metadata is available, and playback exits with return code 0 after 1150 seconds
- **THEN** the tracker uses 1440 seconds, applies the 80% threshold of 1152 seconds, and halts autoplay rather than accepting the 1150-second constant

#### Scenario: AniList fallback preserves the exact no-skip boundary

- **WHEN** HLS duration is unavailable, the selected media reports 24 minutes, no skip metadata is available, and playback exits with return code 0 after 1152 seconds
- **THEN** the tracker approves advancing at exactly 80% of the metadata-derived duration

#### Scenario: AniList fallback preserves skip-aware behavior

- **WHEN** HLS duration is unavailable, the selected media reports 24 minutes, 180 seconds of scheduled skips are known, and playback exits with return code 0 after 882 seconds
- **THEN** the tracker uses 1440 seconds, subtracts the skips, and approves advancing at exactly 70% of 1260 effective seconds

#### Scenario: Missing metadata retains the conservative constant

- **WHEN** HLS duration and AniList duration are both unavailable, no skips are known, and playback exits with return code 0 after 1150 seconds
- **THEN** the tracker approves advancing using the unchanged 1150-second last resort

#### Scenario: Missing metadata with skips retains the adjusted constant

- **WHEN** HLS duration and AniList duration are both unavailable, 176 seconds of skips are known, and playback exits with return code 0 after 973 seconds
- **THEN** the tracker halts autoplay because the last-resort threshold is 974 seconds, and advancing at 974 seconds is permitted

#### Scenario: Invalid metadata cannot bypass completion

- **WHEN** HLS is unavailable and AniList duration is null, a boolean, a non-integer number or string, zero, negative, NaN, or infinite
- **THEN** the tracker ignores that value and applies the 1150-second-minus-skips last resort without raising a playback-fatal metadata error

#### Scenario: Unknown HLS with valid metadata does not need stream information

- **WHEN** playback uses a path without resolvable stream information but the selected media has a valid positive integer duration
- **THEN** the tracker uses that metadata instead of the constant and performs no additional per-episode AniList request

#### Scenario: Unknown duration playback advances after full-length episode minus skips
- **WHEN** stream duration is unknown and playback exits with return code 0 after 1200 seconds
- **THEN** the completion tracker approves advancing to the next episode

#### Scenario: Unknown duration early quit halts autoplay
- **WHEN** stream duration is unknown and playback exits after 660 seconds
- **THEN** the completion tracker halts autoplay and preserves progress

#### Scenario: Interactive selection retains the chosen media's duration
- **WHEN** multiple watchlist entries have different durations and the user selects one interactively
- **THEN** the tracker uses the selected entry's duration, not another entry's value or a title-derived lookup

#### Scenario: Global-search selection retains returned duration

- **WHEN** autoplay selects media through the existing global-search fallback and its response includes duration
- **THEN** the tracker retains that selected media's duration without issuing another media query

#### Scenario: Sequel rollover replaces duration metadata

- **WHEN** a 24-minute media completes and rollover selects a sequel whose existing relation node reports 30 minutes
- **THEN** subsequent fallback decisions use 1800 seconds and never inherit the previous media's 1440 seconds

#### Scenario: Unknown sequel duration does not inherit the prior season

- **WHEN** the prior media has valid duration metadata but the selected sequel's duration is missing or invalid
- **THEN** subsequent decisions use HLS if available and otherwise the 1150-second last resort, not the prior media's metadata

### Requirement: Non-Zero Exit Stops Playback Progression

The playback tracker SHALL stop automated progression whenever the player
exits with a non-zero status, regardless of how much of the episode was
watched and regardless of whether the stream duration is known.

The tracker SHALL report the abnormal exit as the cause of the stop, so that
an abnormal session is distinguishable from one the user ended early.

#### Scenario: Abnormal exit during a known-duration episode stops progression

- **WHEN** the player exits with a non-zero status after 1440 seconds of a
  1440-second episode
- **THEN** the completion tracker classifies the session as stopped,
  preserves watch progress, reports the abnormal exit as the cause of the
  stop, and halts autoplay

#### Scenario: Abnormal exit with an unknown stream duration stops progression

- **WHEN** the player exits with a non-zero status after 1500 seconds and the
  stream duration is unknown
- **THEN** the completion tracker classifies the session as stopped,
  preserves watch progress, reports the abnormal exit as the cause of the
  stop, and halts autoplay

#### Scenario: Abnormal exit after automated skips stops progression

- **WHEN** an episode with total duration of 1463 seconds has 176 seconds of
  scheduled intro and outro skips and the player exits with a non-zero status
  after 1308 seconds
- **THEN** the completion tracker classifies the session as stopped,
  preserves watch progress, reports the abnormal exit as the cause of the
  stop, and halts autoplay

#### Scenario: Abnormal exit bypasses every duration fallback

- **WHEN** the player exits with a non-zero status after enough elapsed time to satisfy HLS, AniList-metadata, or constant thresholds
- **THEN** the tracker stops, preserves progress, reports the abnormal exit, and performs no HLS probe or progress mutation
