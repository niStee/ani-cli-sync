# Spec Delta

## Purpose

Establish the offset resolution capability, and require that static offset
table entries carry an explicit provider search override and a season bound,
so that a series whose provider numbering does not follow the AniList relation
graph resolves to the correct release and episode.

## ADDED Requirements

### Requirement: Static Offset Table Precedence

The offset resolver SHALL consult the static franchise offset table before
the computed prequel offset, and SHALL return the first matching entry.

#### Scenario: Static table entry resolves a series absent from the relation graph
- **WHEN** a series is resolved whose AniList relation graph does not express the provider's season split
- **AND** the series has a static offset table entry
- **THEN** the resolver applies the static entry's search override and offset
- **AND** the resolved episode number is the season-relative episode number within that entry's bound

#### Scenario: Computed prequel offset remains the fallback
- **WHEN** a series has no static offset table entry
- **THEN** the resolver computes the offset from the AniList prequel relation graph
- **AND** applies a season-relative episode number unchanged when the series has no prequel

### Requirement: Static Offset Table Entry Bounds and Ordering

Every static table entry SHALL carry a season bound, and the resolver SHALL
NOT apply an entry to an episode number beyond that bound.

Static table entries whose fragments are substrings of one another SHALL be
ordered most-specific first, so that the resolver's first-match scan selects
the entry identifying the more specific season.

#### Scenario: Longer matching fragment takes precedence over a shorter one
- **WHEN** two static table entries' fragments both occur in the series display title
- **THEN** the resolver applies the entry whose fragment identifies the more specific season

#### Scenario: Episode beyond the entry bound is not remapped
- **WHEN** the AniList episode number exceeds the bound of the matching static table entry
- **THEN** the resolver does not apply that entry's offset

### Requirement: Static Offset Table Provider Search Override

Every static table entry for a series whose provider titles differ from the
AniList titles SHALL carry an explicit provider search override.

#### Scenario: Provider title differs from the AniList title
- **WHEN** a series has a static offset table entry
- **AND** the provider publishes the series under a different title
- **THEN** the resolver searches the provider using the entry's explicit search override
- **AND** does not fall back to the AniList title for that entry
