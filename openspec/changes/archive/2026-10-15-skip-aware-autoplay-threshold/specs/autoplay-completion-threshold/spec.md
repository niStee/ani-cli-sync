# Spec Delta

## Purpose

Evaluates media playback completion using effective duration adjusted for skipped intros/outros and industry-standard completion ratios (80%–85%) to prevent false-negative early quit stops.

## ADDED Requirements

### Requirement: Skip-Aware Effective Duration Calculation
The playback tracker SHALL subtract scheduled intro and outro skip durations from the total media duration when calculating the completion threshold for automated progression.

#### Scenario: Automated intro and outro skips reduce required playback threshold
- **WHEN** an episode with total duration of 1463 seconds has 176 seconds of scheduled intro and outro skips and plays for 1308 seconds with return code 0
- **THEN** the completion tracker calculates the threshold from the effective narrative duration and approves advancing to the next episode

### Requirement: Industry Standard Baseline Threshold
The playback tracker SHALL require playback to reach at least 80% of total duration before advancing when no automated skip metadata is available.

#### Scenario: Playback without explicit skip markers advances past 80% duration
- **WHEN** playback exits with return code 0 after 1260 seconds of a 1440-second episode without automated skip metadata
- **THEN** the completion tracker marks the episode completed and allows autoplay to advance

#### Scenario: Early termination under 80% halts autoplay
- **WHEN** playback exits after 660 seconds of a 1440-second episode
- **THEN** the completion tracker classifies the session as stopped early, preserves progress, and halts autoplay

### Requirement: Conservative Fallback for Unknown Duration
The playback tracker SHALL require at least 1150 seconds of playback when stream duration cannot be determined, minus any known skip durations.

#### Scenario: Unknown duration playback advances after full-length episode minus skips
- **WHEN** stream duration is unknown and playback exits with return code 0 after 1200 seconds
- **THEN** the completion tracker approves advancing to the next episode

#### Scenario: Unknown duration early quit halts autoplay
- **WHEN** stream duration is unknown and playback exits after 660 seconds
- **THEN** the completion tracker halts autoplay and preserves progress
