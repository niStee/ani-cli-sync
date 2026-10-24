# Spec Delta

## Purpose

Governs which subtitle tracks are attached to playback and which of them the
player activates. A secondary track is a user-visible overlay at the top of the
screen, so it is attached only when it was explicitly asked for.

## ADDED Requirements

### Requirement: Single Primary Subtitle Track By Default

The playback tracker SHALL attach only the primary subtitle track and SHALL NOT
attach or activate any secondary subtitle track when no secondary subtitle
language was requested.

#### Scenario: Playback with default settings
- **WHEN** playback begins without a secondary subtitle language being requested
- **THEN** the system attaches only the primary subtitle track and disables the secondary track identifier

#### Scenario: Stream provides an English track without a secondary request
- **WHEN** the stream contains an English subtitle track but no secondary subtitle language was requested
- **THEN** the English track is omitted from the subtitle plan and no secondary track identifier is configured

### Requirement: Secondary Subtitle Track On Explicit Request

The playback tracker SHALL attach and activate the secondary subtitle track
when the user explicitly requests a secondary subtitle language.

#### Scenario: Secondary subtitle explicitly requested as English
- **WHEN** the user requests English as the secondary subtitle language and the stream provides an English track
- **THEN** the system attaches the English track as the secondary track with secondary track identifier 2
- **AND** does not translate the track, because the requested language is already the language of the source track

#### Scenario: Secondary subtitle explicitly requested in another language
- **WHEN** the user requests a secondary subtitle language other than English and the stream provides an English track
- **THEN** the system translates the source track into the requested language and attaches it as the secondary track with secondary track identifier 2

### Requirement: Secondary Track Requested But Unavailable

The playback tracker SHALL leave the secondary track disabled when a secondary
subtitle language was requested but the requested track could not be produced.

#### Scenario: Requested secondary language cannot be produced
- **WHEN** the user requests a secondary subtitle language and neither a cached nor a translated track could be produced for it
- **THEN** the system attaches only the primary subtitle track and disables the secondary track identifier

### Requirement: Primary Track Fallback When The Preferred Track Is Unavailable

The playback tracker SHALL fall back to the stream's English track as the
primary subtitle track when the preferred primary track could not be produced.

#### Scenario: English track serves as the primary when German is unavailable
- **WHEN** the preferred primary track could not be produced and the stream provides an English track
- **THEN** the system attaches the English track as the primary track

#### Scenario: A requested secondary track stays secondary when the primary fallback is used
- **WHEN** the preferred primary track could not be produced, the stream provides an English track, and a secondary subtitle language was requested
- **THEN** the system attaches the English track as the primary track and the requested secondary track as the secondary track
- **AND** does not demote the requested secondary track into the primary position
