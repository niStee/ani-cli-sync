## ADDED Requirements

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
