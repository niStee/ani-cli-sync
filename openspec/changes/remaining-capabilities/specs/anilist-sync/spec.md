# AniList synchronization baseline

## Purpose

Describes supported authenticated watchlist reads, explicit progress corrections,
post-playback updates, and unambiguous sequel transitions without redefining playback completion.

## ADDED Requirements

### Requirement: Authentication precedes private watchlist commands
The system SHALL require a stored token for listing the current watchlist and
setting progress. Login SHALL validate the submitted token before saving it.

#### Scenario: Authenticated list
- **WHEN** an authenticated user requests the list
- **THEN** CURRENT anime entries and their progress and known or unknown totals are displayed

#### Scenario: Missing token
- **WHEN** an unauthenticated user requests list or set
- **THEN** the command reports the login instruction and exits with status 1 without writing progress

#### Scenario: Empty current list
- **WHEN** an authenticated user's CURRENT list is empty
- **THEN** the command reports the empty list without treating it as a failure

#### Scenario: Token validation fails
- **WHEN** login cannot validate the submitted token
- **THEN** that token is not saved as a successful login

### Requirement: Manual progress correction within supported bounds
The system SHALL accept explicit manual progress in season-relative AniList
numbering. It SHALL reject only episodes above a known total; acceptance of
nonpositive integers is excluded from this baseline pending a hardening decision.
The final known episode SHALL set COMPLETED and any other accepted episode SHALL set CURRENT.

#### Scenario: Final episode
- **WHEN** the user explicitly sets episode 12 for a resolved 12-episode entry
- **THEN** progress 12 and status COMPLETED are submitted

#### Scenario: Deliberate correction reopens an entry
- **WHEN** the user explicitly sets episode 3 for a resolved 12-episode entry
- **THEN** progress 3 and status CURRENT are submitted even if this lowers prior progress

#### Scenario: Episode exceeds total
- **WHEN** the user sets episode 13 for a resolved 12-episode entry
- **THEN** the command rejects it with status 1 and explains season-relative numbering without writing progress

#### Scenario: Unknown total
- **WHEN** the user explicitly sets positive episode 5 for an entry without a known total
- **THEN** progress 5 and status CURRENT are submitted without inferring completion

### Requirement: Post-playback update follows completion decision
After a watchlisted episode is played, the system SHALL submit its
season-relative progress only when the playback completion contract approves
progression. A rejected playback SHALL stop continuation without that episode update.

#### Scenario: Accepted non-final playback
- **WHEN** watchlisted episode 4 of 12 satisfies the playback completion contract
- **THEN** progress 4 and status CURRENT are submitted

#### Scenario: Accepted final playback
- **WHEN** watchlisted episode 12 of 12 satisfies the playback completion contract
- **THEN** progress 12 and status COMPLETED are submitted before considering a sequel

#### Scenario: Abnormal or early playback
- **WHEN** watchlisted playback exits abnormally or below its completion threshold
- **THEN** no post-playback episode update is submitted and continuation stops

### Requirement: Supported sequel rollover preserves known progress
The system SHALL offer rollover only for one eligible TV or ONA sequel not
marked not-yet-released. An interactive offer SHALL require an affirmative
answer; autoplay SHALL accept the offer. A successfully read completed sequel SHALL remain untouched.

#### Scenario: Resume known sequel progress
- **WHEN** rollover is accepted and a sequel entry is successfully read with progress 5
- **THEN** playback resumes at episode 6 without resetting that progress

#### Scenario: Completed sequel
- **WHEN** the sequel entry is successfully read as COMPLETED
- **THEN** rollover stops without modifying it

#### Scenario: Ambiguous or unreleased sequel
- **WHEN** multiple eligible sequels exist or the single sequel is marked not-yet-released
- **THEN** rollover does not select or mutate a sequel

#### Scenario: Declined interactive offer
- **WHEN** the user does not answer yes to an interactive sequel offer
- **THEN** no sequel enrollment is performed
