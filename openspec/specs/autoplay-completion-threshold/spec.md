# autoplay-completion-threshold Specification

## Purpose
Evaluates media playback completion using effective duration adjusted for skipped intros/outros and a completion ratio (70% when skip metadata is known, 80% otherwise) to prevent false-negative early quit stops.

## Requirements

### Requirement: Skip-Aware Effective Duration Calculation

The playback tracker SHALL subtract scheduled intro and outro skip durations
from the total media duration when calculating the completion threshold for
automated progression.

When skip durations are known, the completion threshold SHALL be 70% of the
effective duration. When no skip metadata is available, the tracker SHALL
apply the industry-standard 80% baseline of the total duration instead.

#### Scenario: Automated intro and outro skips reduce required playback threshold
- **WHEN** an episode with total duration of 1463 seconds has 176 seconds of scheduled intro and outro skips and plays for 1308 seconds with return code 0
- **THEN** the completion tracker calculates the threshold from the effective narrative duration and approves advancing to the next episode

#### Scenario: Playback with skips and a recap advances
- **WHEN** an episode with total duration of 1463 seconds has 176 seconds of scheduled intro and outro skips and plays for 1028 seconds with return code 0
- **THEN** the effective duration is 1287 seconds, the threshold is 70% of it, and the completion tracker approves advancing to the next episode

#### Scenario: Playback with skips stopped well before the threshold halts autoplay
- **WHEN** an episode with total duration of 1463 seconds has 177 seconds of scheduled intro and outro skips and the player exits with return code 0 after 600 seconds
- **THEN** the completion tracker classifies the session as stopped early, preserves progress, and halts autoplay

### Requirement: Industry Standard Baseline Threshold

The playback tracker SHALL require playback to reach at least 80% of total
duration before advancing when no automated skip metadata is available.

#### Scenario: Playback without explicit skip markers advances past 80% duration
- **WHEN** playback exits with return code 0 after 1260 seconds of a 1440-second episode without automated skip metadata
- **THEN** the completion tracker marks the episode completed and allows autoplay to advance

#### Scenario: Early termination under 80% halts autoplay
- **WHEN** playback exits after 660 seconds of a 1440-second episode
- **THEN** the completion tracker classifies the session as stopped early, preserves progress, and halts autoplay

#### Scenario: Skip-aware ratio does not apply without skip metadata
- **WHEN** playback exits with return code 0 after 1008 seconds of a 1440-second episode without automated skip metadata
- **THEN** the completion tracker applies the 80% baseline, classifies the session as stopped early, and halts autoplay

### Requirement: Conservative Fallback for Unknown Duration
The playback tracker SHALL require at least 1150 seconds of playback when stream duration cannot be determined, minus any known skip durations.

#### Scenario: Unknown duration playback advances after full-length episode minus skips
- **WHEN** stream duration is unknown and playback exits with return code 0 after 1200 seconds
- **THEN** the completion tracker approves advancing to the next episode

#### Scenario: Unknown duration early quit halts autoplay
- **WHEN** stream duration is unknown and playback exits after 660 seconds
- **THEN** the completion tracker halts autoplay and preserves progress

### Requirement: Non-Zero Exit Stops Playback Progression

The playback tracker SHALL stop automated progression whenever the player
exits with a non-zero status, regardless of how much of the episode was
watched and regardless of whether the stream duration is known.

The exit status SHALL be evaluated before any duration-based threshold is
computed, so that a session which ends abnormally is never treated as a
played-through episode.

#### Scenario: Abnormal exit during a known-duration episode stops progression
- **WHEN** the player exits with a non-zero status after 1440 seconds of a
  1440-second episode
- **THEN** the completion tracker classifies the session as stopped,
  preserves watch progress, and halts autoplay

#### Scenario: Abnormal exit with an unknown stream duration stops progression
- **WHEN** the player exits with a non-zero status after 1500 seconds and the
  stream duration is unknown
- **THEN** the completion tracker classifies the session as stopped,
  preserves watch progress, and halts autoplay

#### Scenario: Abnormal exit after automated skips stops progression
- **WHEN** an episode with total duration of 1463 seconds has 176 seconds of
  scheduled intro and outro skips and the player exits with a non-zero status
  after 1308 seconds
- **THEN** the completion tracker classifies the session as stopped,
  preserves watch progress, and halts autoplay
