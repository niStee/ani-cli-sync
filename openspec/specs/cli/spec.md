# cli Specification

## Purpose
Describes the supported command surface, playback fallback, selection cancellation,
and subtitle option defaults without imposing a new global error-handling policy.

## Requirements

### Requirement: Explicit commands and implicit watching
Both ani-cli-sync and ani-sync SHALL expose login, list, set, import-netflix,
and watch. In the absence of a recognized command or a help request, ordinary
watch options and an optional non-command title SHALL invoke watching.

#### Scenario: Bare invocation
- **WHEN** the user invokes the program without arguments
- **THEN** the watch workflow starts

#### Scenario: Implicit title
- **WHEN** the user supplies a title that is not a command name without a subcommand
- **THEN** the title is used as the watch query

#### Scenario: Explicit watch query is command-like
- **WHEN** the user invokes watch with the title list
- **THEN** list is treated as the watch query rather than executing the list command

#### Scenario: Help request
- **WHEN** the user requests --help
- **THEN** usage information is displayed with status 0 without starting playback

### Requirement: Explicit argument validation
The CLI SHALL reject unknown options, missing required command arguments,
non-integer set episodes, and explicit --sub-sync values other than off or auto
with usage status 2 before executing the command.

#### Scenario: Invalid progress argument
- **WHEN** set is invoked with a non-integer episode
- **THEN** usage fails with status 2 and no progress update is attempted

#### Scenario: Invalid explicit sync mode
- **WHEN** watch is invoked with --sub-sync=guess
- **THEN** usage fails with status 2 without launching a player

#### Scenario: Supported sync mode
- **WHEN** watch is invoked with --sub-sync=auto
- **THEN** the automatic subtitle-sync request is accepted

### Requirement: Unauthenticated watching does not synchronize
Watching without a stored AniList token SHALL delegate to native ani-cli without
AniList synchronization. An authenticated empty current list without a query
SHALL also offer native playback without enrolling a selected anime automatically.

#### Scenario: No token
- **WHEN** watch starts without a stored token
- **THEN** native playback is invoked without AniList progress mutations

#### Scenario: Empty watchlist without query
- **WHEN** watch starts with an empty current list and no query
- **THEN** native search is invoked without synchronized progress updates

### Requirement: Selection can be cancelled
Interactive watching SHALL allow the user to cancel selection. Where fzf is
unavailable, a numbered selection SHALL be offered. Invalid or empty numbered
input SHALL cancel rather than select an arbitrary episode.

#### Scenario: Valid numbered choice
- **WHEN** fzf is unavailable and the user enters a displayed valid index
- **THEN** the corresponding watchlist entry is selected

#### Scenario: Cancelled selection
- **WHEN** selection is cancelled or the numbered input is empty or invalid
- **THEN** the watch command returns without launching the selected episode or updating its progress

### Requirement: Subtitle options preserve supported defaults
Without environment overrides, watch SHALL request German primary subtitles,
no secondary track, zero manual delay, and automatic sync off. A secondary
language SHALL be requested only through explicit configuration or a flag.

#### Scenario: Defaults
- **WHEN** watch starts without subtitle flags or subtitle environment overrides
- **THEN** German primary, disabled secondary, zero manual delay, and sync off are requested

#### Scenario: Explicit secondary
- **WHEN** watch is invoked with --sub-secondary=en
- **THEN** English is requested as the secondary language under the subtitle-track contract

#### Scenario: Disable managed subtitle fallback
- **WHEN** watch is invoked with --no-sub-fallback
- **THEN** native playback is used instead of managed subtitle synthesis and automatic measurement
