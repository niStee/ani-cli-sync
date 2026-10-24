# Spec Delta

## Purpose

Lower the completion ratio applied when automated intro and outro skips are
known, so that an episode which played through its narrative content but
stopped short of the effective-duration threshold is not misclassified as an
early quit. The no-skip baseline is deliberately unchanged.

## MODIFIED Requirements

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
