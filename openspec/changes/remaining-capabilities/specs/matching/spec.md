# Title matching baseline

## Purpose

Describes supported exact and unique title matching and release-cut preference,
while keeping unresolved ambiguous mutation behavior outside this baseline.

## ADDED Requirements

### Requirement: Manual progress resolution checks the current watchlist first
Manual progress correction SHALL prefer a current-watchlist match over global
search. A case-insensitive exact English or romaji title match SHALL take
precedence over substring matching. A unique substring match SHALL be accepted.

#### Scenario: Exact match before longer season title
- **WHEN** a query exactly names one current entry and is also a substring of another
- **THEN** the exact entry is selected for the manual correction

#### Scenario: Romaji match
- **WHEN** the query matches a current entry's romaji title case-insensitively
- **THEN** that entry is selected without requiring its English title

#### Scenario: Unique substring
- **WHEN** no exact match exists and exactly one current title contains the query
- **THEN** that entry is selected

#### Scenario: No watchlist title matches
- **WHEN** no current title matches the manual correction query
- **THEN** global AniList title search is attempted

### Requirement: Interactive watch queries can narrow the current list
Watching SHALL directly select a unique matching current entry. When several
current entries match but one title exactly matches, that exact entry SHALL win.
Otherwise interactive watching SHALL offer the narrowed matching candidates.

#### Scenario: Unique watch title
- **WHEN** an ordinary title query matches one current entry
- **THEN** that entry is selected directly

#### Scenario: Exact watch title among several
- **WHEN** several current entries match and one English or romaji title matches exactly
- **THEN** that exact title is selected

#### Scenario: Several interactive title matches
- **WHEN** several current titles match, none exactly, and autoplay is disabled
- **THEN** the matching entries are offered for user selection rather than playing one without selection

### Requirement: Provider selection prefers a matching normalized title group
Provider selection SHALL compare normalized titles without punctuation or
bracketed release tags. Within a matched normalized-title group, it SHALL prefer
the requested censored or uncensored cut and fall back to the first matched member when that cut is unavailable.

#### Scenario: Uncensored cut available
- **WHEN** exact normalized-title candidates contain ordinary and tagged uncensored cuts and uncensored preference is enabled
- **THEN** the uncensored cut is selected within that group

#### Scenario: Censored preference
- **WHEN** exact normalized-title candidates contain both cuts and uncensored preference is disabled
- **THEN** a candidate without an uncensored tag is selected

#### Scenario: Preferred cut absent
- **WHEN** a matched normalized group contains no preferred cut
- **THEN** its first member is selected without inventing a new result

#### Scenario: Empty provider results
- **WHEN** the provider supplies no candidates
- **THEN** no candidate is selected
